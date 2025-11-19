"""Selectors for inventory domain (single-location)."""

from .models import StockItem, StockReservation


def available_quantity_for_stock_item(stock_item_id: int) -> int:
    try:
        item = StockItem.objects.only("quantity", "reserved").get(id=stock_item_id)
    except StockItem.DoesNotExist:
        return 0
    return int(item.quantity) - int(item.reserved)


def list_stock_for_product(product_id: int):
    qs = StockItem.objects.filter(variant__product_id=product_id).select_related("variant")
    return [
        {
            "variant": s.variant.sku if s.variant else None,
            "quantity": s.quantity,
            "reserved": s.reserved,
            "available": int(s.quantity) - int(s.reserved),
        }
        for s in qs
    ]


def list_active_reservations_for_variant(variant_id: int):
    return list(
        StockReservation.objects.filter(variant_id=variant_id, state=StockReservation.STATE_ACTIVE)
        .order_by("-created_at")
        .values("id", "quantity", "reference", "expires_at")
    )


# EOF
