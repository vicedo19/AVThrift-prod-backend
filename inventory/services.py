"""Inventory services (single-location): transactional stock movements."""

from django.db import transaction

from .models import StockItem, StockMovement


class MovementError(Exception):
    pass


@transaction.atomic
def apply_movement(*, stock_item_id: int, movement_type: str, quantity: int, reason: str = "", reference: str = ""):
    """Apply a signed movement to a stock item.

    quantity: positive for inbound/additions, negative for outbound/deductions.
    movement_type: label for admin/documentation; logic is driven by sign.
    """
    if quantity == 0:
        return None
    try:
        item = StockItem.objects.select_for_update().select_related("variant").get(id=stock_item_id)
    except StockItem.DoesNotExist:
        raise MovementError("StockItem not found")

    if quantity < 0:
        available = int(item.quantity) - int(item.reserved)
        if abs(quantity) > available:
            raise MovementError("Insufficient available quantity")
    item.quantity = int(item.quantity) + int(quantity)

    item.save(update_fields=["quantity", "updated_at"])
    movement = StockMovement.objects.create(
        stock_item=item,
        movement_type=movement_type,
        quantity=quantity,
        reason=reason,
        reference=reference,
    )
    return movement


# Reservation services
@transaction.atomic
def create_reservation(*, variant_id: int, quantity: int, reference: str, expires_at=None):
    from .models import StockReservation

    if quantity <= 0:
        raise MovementError("Reservation quantity must be positive")
    # Ensure a stock item exists for the variant
    item, _ = StockItem.objects.select_for_update().get_or_create(
        variant_id=variant_id, defaults={"quantity": 0, "reserved": 0}
    )
    available = int(item.quantity) - int(item.reserved)
    if quantity > available:
        raise MovementError("Insufficient available quantity to reserve")
    item.reserved = int(item.reserved) + int(quantity)
    item.save(update_fields=["reserved", "updated_at"])
    return StockReservation.objects.create(
        variant_id=variant_id,
        quantity=quantity,
        reference=reference,
        expires_at=expires_at,
        state=StockReservation.STATE_ACTIVE,
    )


@transaction.atomic
def release_reservation(*, reservation_id: int):
    from .models import StockReservation

    try:
        res = StockReservation.objects.select_for_update().get(id=reservation_id)
    except StockReservation.DoesNotExist:
        return
    if res.state != StockReservation.STATE_ACTIVE:
        return
    item = StockItem.objects.select_for_update().get(variant_id=res.variant_id)
    item.reserved = max(0, int(item.reserved) - int(res.quantity))
    item.save(update_fields=["reserved", "updated_at"])
    res.state = StockReservation.STATE_RELEASED
    res.save(update_fields=["state", "updated_at"])


@transaction.atomic
def convert_reservation_to_order(*, reservation_id: int, reason: str = "order", reference: str = ""):
    from .models import StockReservation

    try:
        res = StockReservation.objects.select_for_update().get(id=reservation_id)
    except StockReservation.DoesNotExist:
        return
    if res.state != StockReservation.STATE_ACTIVE:
        return
    item = StockItem.objects.select_for_update().get(variant_id=res.variant_id)
    # Deduct reserved and quantity atomically
    item.reserved = max(0, int(item.reserved) - int(res.quantity))
    # Use signed movement for fulfillment
    if res.quantity > (int(item.quantity)):
        raise MovementError("Insufficient stock to fulfill reservation")
    item.quantity = int(item.quantity) - int(res.quantity)
    item.save(update_fields=["quantity", "reserved", "updated_at"])
    StockMovement.objects.create(
        stock_item=item,
        movement_type=StockMovement.TYPE_OUTBOUND,
        quantity=-int(res.quantity),
        reason=reason,
        reference=reference,
    )
    res.state = StockReservation.STATE_CONVERTED
    res.save(update_fields=["state", "updated_at"])


# EOF
