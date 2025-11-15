"""Cart services: mutations with inventory reservations."""

import logging
from datetime import timedelta
from decimal import Decimal

from catalog.models import ProductVariant
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from inventory.services import convert_reservation_to_order, create_reservation, release_reservation

from .models import Cart, CartItem
from .selectors import get_active_cart_for_session, get_active_cart_for_user


class CartError(Exception):
    """Raised for cart mutation failures."""


logger = logging.getLogger("avthrift.cart")


@transaction.atomic
def add_item(*, user, variant_id: int, quantity: int) -> CartItem:
    """Add a variant to the user's cart, creating or updating the line item.

    Reserves inventory equal to the desired quantity.
    """

    if quantity <= 0:
        raise CartError("Quantity must be positive")
    cart = get_active_cart_for_user(user=user)
    variant = get_object_or_404(ProductVariant, id=variant_id)

    try:
        item = CartItem.objects.select_for_update().get(cart=cart, variant=variant)
        # Re-reserve to match new quantity
        if item.reservation_id:
            release_reservation(reservation_id=item.reservation_id)
        from django.conf import settings as dj_settings

        expires_at = timezone.now() + timedelta(minutes=getattr(dj_settings, "CART_RESERVATION_TTL_MINUTES", 30))
        reservation = create_reservation(
            variant_id=variant.id,
            quantity=quantity,
            reference=f"cart:{cart.id}",
            expires_at=expires_at,
        )
        # Safety: reservation must match the variant being added
        if reservation.variant_id != variant.id:
            release_reservation(reservation_id=reservation.id)
            raise CartError("Reservation variant mismatch")
        item.quantity = quantity
        item.unit_price = variant.price or Decimal("0.00")
        item.reservation = reservation
        item.save(update_fields=["quantity", "unit_price", "reservation", "updated_at"])
        logger.info(
            "cart.item_updated",
            extra={
                "event": "cart.item_updated",
                "cart_id": cart.id,
                "user_id": getattr(user, "id", None),
                "variant_id": variant.id,
                "quantity": quantity,
                "guest": False,
            },
        )
        return item
    except CartItem.DoesNotExist:
        from django.conf import settings as dj_settings

        expires_at = timezone.now() + timedelta(minutes=getattr(dj_settings, "CART_RESERVATION_TTL_MINUTES", 30))
        reservation = create_reservation(
            variant_id=variant.id,
            quantity=quantity,
            reference=f"cart:{cart.id}",
            expires_at=expires_at,
        )
        if reservation.variant_id != variant.id:
            release_reservation(reservation_id=reservation.id)
            raise CartError("Reservation variant mismatch")
        created = CartItem.objects.create(
            cart=cart,
            variant=variant,
            quantity=quantity,
            unit_price=variant.price or Decimal("0.00"),
            reservation=reservation,
        )
        logger.info(
            "cart.item_added",
            extra={
                "event": "cart.item_added",
                "cart_id": cart.id,
                "user_id": getattr(user, "id", None),
                "variant_id": variant.id,
                "quantity": quantity,
                "guest": False,
            },
        )
        return created


@transaction.atomic
def update_item_quantity(*, user, item_id: int, quantity: int) -> CartItem:
    """Update a cart item's quantity, re-syncing reservations."""

    if quantity <= 0:
        raise CartError("Quantity must be positive")
    cart = get_active_cart_for_user(user=user)
    item = get_object_or_404(CartItem.objects.select_for_update(), id=item_id, cart=cart)

    # Replace reservation with the new quantity
    if item.reservation_id:
        release_reservation(reservation_id=item.reservation_id)
    from django.conf import settings as dj_settings

    expires_at = timezone.now() + timedelta(minutes=getattr(dj_settings, "CART_RESERVATION_TTL_MINUTES", 30))
    reservation = create_reservation(
        variant_id=item.variant_id,
        quantity=quantity,
        reference=f"cart:{cart.id}",
        expires_at=expires_at,
    )
    if reservation.variant_id != item.variant_id:
        release_reservation(reservation_id=reservation.id)
        raise CartError("Reservation variant mismatch")
    item.quantity = quantity
    item.unit_price = item.variant.price or Decimal("0.00")
    item.reservation = reservation
    item.save(update_fields=["quantity", "unit_price", "reservation", "updated_at"])
    return item


@transaction.atomic
def remove_item(*, user, item_id: int) -> None:
    """Remove an item from the cart and release its reservation."""

    cart = get_active_cart_for_user(user=user)
    try:
        item = CartItem.objects.select_for_update().get(id=item_id, cart=cart)
    except CartItem.DoesNotExist:
        return
    if item.reservation_id:
        release_reservation(reservation_id=item.reservation_id)
    item.delete()
    logger.info(
        "cart.item_removed",
        extra={
            "event": "cart.item_removed",
            "cart_id": cart.id,
            "user_id": getattr(user, "id", None),
            "item_id": item_id,
            "guest": False,
        },
    )


@transaction.atomic
def clear_cart(*, user) -> None:
    """Clear the user's cart and release all reservations."""

    cart = get_active_cart_for_user(user=user)
    for item in CartItem.objects.select_for_update().filter(cart=cart):
        if item.reservation_id:
            release_reservation(reservation_id=item.reservation_id)
    CartItem.objects.filter(cart=cart).delete()
    logger.info(
        "cart.cleared",
        extra={"event": "cart.cleared", "cart_id": cart.id, "user_id": getattr(user, "id", None), "guest": False},
    )


@transaction.atomic
def checkout_cart(*, user) -> int:
    """Checkout the active cart: convert reservations, create order, mark cart ordered.

    Returns the created order ID.
    """

    from orders.services import create_order_from_cart

    cart = get_active_cart_for_user(user=user)
    # Convert all active reservations to orders
    for item in CartItem.objects.select_for_update().filter(cart=cart):
        if item.reservation_id:
            convert_reservation_to_order(
                reservation_id=item.reservation_id,
                reason="cart checkout",
                reference=f"cart:{cart.id}",
            )
    # Create an order snapshot from the cart
    order = create_order_from_cart(cart)
    # Clear items after conversion
    CartItem.objects.filter(cart=cart).delete()
    cart.status = Cart.STATUS_ORDERED
    cart.save(update_fields=["status", "updated_at"])
    logger.info(
        "cart.checked_out",
        extra={
            "event": "cart.checked_out",
            "cart_id": cart.id,
            "user_id": getattr(user, "id", None),
            "order_id": int(order.id),
            "guest": False,
        },
    )
    return int(order.id)


@transaction.atomic
def abandon_cart(*, user) -> None:
    """Abandon the active cart: release reservations and mark as abandoned."""

    cart = get_active_cart_for_user(user=user)
    for item in CartItem.objects.select_for_update().filter(cart=cart):
        if item.reservation_id:
            release_reservation(reservation_id=item.reservation_id)
    CartItem.objects.filter(cart=cart).delete()
    cart.status = Cart.STATUS_ABANDONED
    cart.save(update_fields=["status", "updated_at"])
    logger.info(
        "cart.abandoned",
        extra={
            "event": "cart.abandoned",
            "cart_id": cart.id,
            "user_id": getattr(user, "id", None),
            "guest": False,
        },
    )


# Guest cart operations


@transaction.atomic
def add_item_guest(*, session_id: str, variant_id: int, quantity: int) -> CartItem:
    """Add a variant to a guest cart by session id."""

    if quantity <= 0:
        raise CartError("Quantity must be positive")
    cart = get_active_cart_for_session(session_id=session_id)
    variant = get_object_or_404(ProductVariant, id=variant_id)
    try:
        item = CartItem.objects.select_for_update().get(cart=cart, variant=variant)
        if item.reservation_id:
            release_reservation(reservation_id=item.reservation_id)
        from django.conf import settings as dj_settings

        expires_at = timezone.now() + timedelta(minutes=getattr(dj_settings, "CART_RESERVATION_TTL_MINUTES", 30))
        reservation = create_reservation(
            variant_id=variant.id,
            quantity=quantity,
            reference=f"cart:{cart.id}",
            expires_at=expires_at,
        )
        if reservation.variant_id != variant.id:
            release_reservation(reservation_id=reservation.id)
            raise CartError("Reservation variant mismatch")
        item.quantity = quantity
        item.unit_price = variant.price or Decimal("0.00")
        item.reservation = reservation
        item.save(update_fields=["quantity", "unit_price", "reservation", "updated_at"])
        logger.info(
            "cart.item_updated",
            extra={
                "event": "cart.item_updated",
                "cart_id": cart.id,
                "session_id": session_id,
                "variant_id": variant.id,
                "quantity": quantity,
                "guest": True,
            },
        )
        return item
    except CartItem.DoesNotExist:
        from django.conf import settings as dj_settings

        expires_at = timezone.now() + timedelta(minutes=getattr(dj_settings, "CART_RESERVATION_TTL_MINUTES", 30))
        reservation = create_reservation(
            variant_id=variant.id,
            quantity=quantity,
            reference=f"cart:{cart.id}",
            expires_at=expires_at,
        )
        if reservation.variant_id != variant.id:
            release_reservation(reservation_id=reservation.id)
            raise CartError("Reservation variant mismatch")
        created = CartItem.objects.create(
            cart=cart,
            variant=variant,
            quantity=quantity,
            unit_price=variant.price or Decimal("0.00"),
            reservation=reservation,
        )
        logger.info(
            "cart.item_added",
            extra={
                "event": "cart.item_added",
                "cart_id": cart.id,
                "session_id": session_id,
                "variant_id": variant.id,
                "quantity": quantity,
                "guest": True,
            },
        )
        return created


@transaction.atomic
def update_item_quantity_guest(*, session_id: str, item_id: int, quantity: int) -> CartItem:
    """Update a guest cart item's quantity, re-syncing its reservation."""

    if quantity <= 0:
        raise CartError("Quantity must be positive")
    cart = get_active_cart_for_session(session_id=session_id)
    item = get_object_or_404(CartItem.objects.select_for_update(), id=item_id, cart=cart)
    if item.reservation_id:
        release_reservation(reservation_id=item.reservation_id)
    from django.conf import settings as dj_settings

    expires_at = timezone.now() + timedelta(minutes=getattr(dj_settings, "CART_RESERVATION_TTL_MINUTES", 30))
    reservation = create_reservation(
        variant_id=item.variant_id,
        quantity=quantity,
        reference=f"cart:{cart.id}",
        expires_at=expires_at,
    )
    if reservation.variant_id != item.variant_id:
        release_reservation(reservation_id=reservation.id)
        raise CartError("Reservation variant mismatch")
    item.quantity = quantity
    item.unit_price = item.variant.price or Decimal("0.00")
    item.reservation = reservation
    item.save(update_fields=["quantity", "unit_price", "reservation", "updated_at"])
    return item


@transaction.atomic
def remove_item_guest(*, session_id: str, item_id: int) -> None:
    cart = get_active_cart_for_session(session_id=session_id)
    try:
        item = CartItem.objects.select_for_update().get(id=item_id, cart=cart)
    except CartItem.DoesNotExist:
        return
    if item.reservation_id:
        release_reservation(reservation_id=item.reservation_id)
    item.delete()
    logger.info(
        "cart.item_removed",
        extra={
            "event": "cart.item_removed",
            "cart_id": cart.id,
            "session_id": session_id,
            "item_id": item_id,
            "guest": True,
        },
    )


@transaction.atomic
def clear_cart_guest(*, session_id: str) -> None:
    cart = get_active_cart_for_session(session_id=session_id)
    for item in CartItem.objects.select_for_update().filter(cart=cart):
        if item.reservation_id:
            release_reservation(reservation_id=item.reservation_id)
    CartItem.objects.filter(cart=cart).delete()
    logger.info(
        "cart.cleared",
        extra={"event": "cart.cleared", "cart_id": cart.id, "session_id": session_id, "guest": True},
    )


@transaction.atomic
def abandon_cart_guest(*, session_id: str) -> None:
    cart = get_active_cart_for_session(session_id=session_id)
    for item in CartItem.objects.select_for_update().filter(cart=cart):
        if item.reservation_id:
            release_reservation(reservation_id=item.reservation_id)
    CartItem.objects.filter(cart=cart).delete()
    cart.status = Cart.STATUS_ABANDONED
    cart.save(update_fields=["status", "updated_at"])
    logger.info(
        "cart.abandoned",
        extra={"event": "cart.abandoned", "cart_id": cart.id, "session_id": session_id, "guest": True},
    )


@transaction.atomic
def merge_guest_cart_to_user(*, session_id: str, user) -> Cart:
    """Merge a guest session cart into the user's active cart."""

    dest = get_active_cart_for_user(user=user)
    src = get_active_cart_for_session(session_id=session_id)
    if src.id == dest.id:
        return dest
    # Build aggregate quantities per variant
    target = {}
    for item in dest.items.select_related("variant"):
        target[item.variant_id] = target.get(item.variant_id, 0) + int(item.quantity)
    for item in src.items.select_related("variant"):
        target[item.variant_id] = target.get(item.variant_id, 0) + int(item.quantity)
    # Apply
    for variant_id, qty in target.items():
        try:
            d_item = CartItem.objects.select_for_update().get(cart=dest, variant_id=variant_id)
            if d_item.reservation_id:
                release_reservation(reservation_id=d_item.reservation_id)
            from django.conf import settings as dj_settings

            expires_at = timezone.now() + timedelta(minutes=getattr(dj_settings, "CART_RESERVATION_TTL_MINUTES", 30))
            reservation = create_reservation(
                variant_id=variant_id,
                quantity=qty,
                reference=f"cart:{dest.id}",
                expires_at=expires_at,
            )
            if reservation.variant_id != variant_id:
                release_reservation(reservation_id=reservation.id)
                raise CartError("Reservation variant mismatch")
            d_item.quantity = qty
            d_item.unit_price = d_item.variant.price or Decimal("0.00")
            d_item.reservation = reservation
            d_item.save(update_fields=["quantity", "unit_price", "reservation", "updated_at"])
        except CartItem.DoesNotExist:
            from django.conf import settings as dj_settings

            expires_at = timezone.now() + timedelta(minutes=getattr(dj_settings, "CART_RESERVATION_TTL_MINUTES", 30))
            reservation = create_reservation(
                variant_id=variant_id,
                quantity=qty,
                reference=f"cart:{dest.id}",
                expires_at=expires_at,
            )
            if reservation.variant_id != variant_id:
                release_reservation(reservation_id=reservation.id)
                raise CartError("Reservation variant mismatch")
            CartItem.objects.create(
                cart=dest,
                variant_id=variant_id,
                quantity=qty,
                unit_price=ProductVariant.objects.get(id=variant_id).price or Decimal("0.00"),
                reservation=reservation,
            )
    # Release all src reservations and delete source cart
    for s_item in CartItem.objects.select_for_update().filter(cart=src):
        if s_item.reservation_id:
            release_reservation(reservation_id=s_item.reservation_id)
    CartItem.objects.filter(cart=src).delete()
    src.delete()
    logger.info(
        "cart.merged",
        extra={
            "event": "cart.merged",
            "src_cart_id": src.id,
            "dest_cart_id": dest.id,
            "user_id": getattr(user, "id", None),
            "session_id": session_id,
        },
    )
    return dest
