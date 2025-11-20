from datetime import timedelta
from decimal import Decimal

import pytest
from catalog.tests.factories import ProductVariantFactory
from django.utils import timezone
from inventory.models import StockItem
from inventory.services import (
    MovementError,
    apply_movement,
    convert_reservation_to_order,
    create_reservation,
    release_reservation,
)

pytestmark = pytest.mark.django_db


def setup_stock(variant=None):
    variant = variant or ProductVariantFactory(price=Decimal("10.00"))
    item = StockItem.objects.create(variant=variant, quantity=10, reserved=2)
    return variant, item


def test_apply_movement_inbound_and_outbound_and_errors():
    _, item = setup_stock()
    # Zero quantity -> None
    assert apply_movement(stock_item_id=item.id, movement_type="adjust", quantity=0) is None
    # Outbound exceeding available -> error
    with pytest.raises(MovementError):
        apply_movement(stock_item_id=item.id, movement_type="outbound", quantity=-9)
    # Inbound increases
    mv_in = apply_movement(stock_item_id=item.id, movement_type="inbound", quantity=5)
    assert mv_in.quantity == 5
    # Outbound within available
    mv_out = apply_movement(stock_item_id=item.id, movement_type="outbound", quantity=-3)
    assert mv_out.quantity == -3


def test_reservation_create_release_convert_and_errors():
    variant, item = setup_stock()
    # Invalid qty
    with pytest.raises(MovementError):
        create_reservation(variant_id=variant.id, quantity=0, reference="r0")
    # Insufficient available
    with pytest.raises(MovementError):
        create_reservation(variant_id=variant.id, quantity=9, reference="rX")
    # Valid reservation
    res = create_reservation(
        variant_id=variant.id, quantity=3, reference="r1", expires_at=timezone.now() + timedelta(days=1)
    )
    item.refresh_from_db()
    assert item.reserved == 5
    # Release reservation
    release_reservation(reservation_id=res.id)
    item.refresh_from_db()
    assert item.reserved == 2
    # Recreate and convert to order
    res2 = create_reservation(variant_id=variant.id, quantity=2, reference="r2")
    convert_reservation_to_order(reservation_id=res2.id, reason="order", reference="ORD-1")
    item.refresh_from_db()
    assert item.quantity == 8 and item.reserved == 2
    # Non-existent operations are no-op
    release_reservation(reservation_id=999999)
    convert_reservation_to_order(reservation_id=999999)
