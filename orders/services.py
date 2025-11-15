import hashlib
import json
import logging
from datetime import timedelta
from decimal import Decimal
from typing import Callable, Optional, Tuple

from cart.models import Cart, CartItem
from django.db import IntegrityError, transaction
from django.utils import timezone

from .emails import send_order_paid_email
from .models import IdempotencyKey, Order, OrderItem

logger = logging.getLogger(__name__)


def create_order_from_cart(cart: Cart) -> Order:
    """Create an Order and OrderItems from the given cart snapshot.

    Snapshots variant SKU and product title on each line item.
    """

    with transaction.atomic():
        order = Order.objects.create(user=cart.user, email=getattr(cart.user, "email", None))
        for item in CartItem.objects.select_related("variant", "variant__product").filter(cart=cart):
            unit_price = item.unit_price or item.variant.price or Decimal("0.00")
            OrderItem.objects.create(
                order=order,
                variant=item.variant,
                product_title=item.variant.product.title,
                variant_sku=item.variant.sku,
                quantity=item.quantity,
                unit_price=unit_price,
            )
        # Generate user-friendly order number (unique)
        order.number = f"ORD-{int(order.id):06d}"
        order.save(update_fields=["number"])
        return order


def pay_order(order: Order) -> Order:
    """Mark an order as paid, if currently pending.

    Returns the updated order.
    """

    if order.status == Order.STATUS_CANCELLED:
        raise ValueError("Cannot pay a cancelled order")
    if order.status == Order.STATUS_PAID:
        return order
    prev = order.status
    order.status = Order.STATUS_PAID
    order.save(update_fields=["status", "updated_at"])
    try:
        logger.info(
            "order_status_changed",
            extra={
                "order_id": order.id,
                "user_id": order.user_id,
                "status_from": prev,
                "status_to": order.status,
            },
        )
    except Exception:
        # Logging should never break mutations
        pass
    # Notify customer of payment confirmation
    try:
        send_order_paid_email(order)
    except Exception:
        # Email sending should not block the mutation
        pass
    return order


def cancel_order(order: Order) -> Order:
    """Cancel an order unless it is already paid.

    Returns the updated order.
    """

    if order.status == Order.STATUS_PAID:
        raise ValueError("Cannot cancel a paid order")
    if order.status == Order.STATUS_CANCELLED:
        return order
    prev = order.status
    order.status = Order.STATUS_CANCELLED
    order.save(update_fields=["status", "updated_at"])
    try:
        logger.info(
            "order_status_changed",
            extra={
                "order_id": order.id,
                "user_id": order.user_id,
                "status_from": prev,
                "status_to": order.status,
            },
        )
    except Exception:
        pass
    return order


def with_idempotency(
    *,
    key: str,
    user,
    path: str,
    method: str,
    handler: Callable[[], Tuple[dict, int]],
    request_hash: Optional[str] = None,
) -> Tuple[dict, int]:
    """Run handler idempotently and persist its response for the given key and scope.

    - Scope is derived from the caller: for authenticated users, "user:<id>"; otherwise "anon".
    - If a record exists and the stored `request_hash` differs from the provided one, returns 409.
    - If a record exists but response is not yet stored, returns 409 to indicate in-progress.
    """

    scope = f"user:{getattr(user, 'id', None)}" if getattr(user, "id", None) else "anon"
    method = str(method).upper()
    path = str(path)

    try:
        with transaction.atomic():
            idem = IdempotencyKey.objects.create(
                key=key,
                user=user if getattr(user, "id", None) else None,
                scope=scope,
                path=path,
                method=method,
                request_hash=request_hash,
                expires_at=timezone.now() + timedelta(hours=24),
            )
    except IntegrityError:
        idem = IdempotencyKey.objects.get(key=key, scope=scope, path=path, method=method)
        # Guard against key reuse with different fingerprints
        if idem.request_hash and request_hash and idem.request_hash != request_hash:
            return {"detail": "Idempotency key reused with different request payload"}, 409
        if idem.response_json is not None and idem.response_code is not None:
            return idem.response_json, int(idem.response_code)
        # If another process is currently handling it, return a safe 409
        return {"detail": "Request in progress"}, 409

    # Fresh request; execute and persist the response
    body, code = handler()

    def _json_safe(value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, dict):
            return {k: _json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_json_safe(v) for v in value]
        return value

    safe_body = _json_safe(body)
    IdempotencyKey.objects.filter(id=idem.id).update(response_json=safe_body, response_code=code)
    return body, code


def compute_request_hash(data: Optional[dict]) -> Optional[str]:
    """Compute a canonical SHA256 hash of the request body.

    Uses sorted keys JSON representation to stabilize the hash across equivalent payloads.
    Returns None when data is falsy.
    """
    if not data:
        return None
    try:
        payload = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
    except Exception:
        return None
