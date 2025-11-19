import pytest
from catalog.tests.factories import ProductVariantFactory
from inventory.models import StockItem, StockMovement, StockReservation
from inventory.services import (
    MovementError,
    apply_movement,
    convert_reservation_to_order,
    create_reservation,
    release_reservation,
)


@pytest.mark.django_db
def test_signed_movement_inbound_and_outbound():
    v = ProductVariantFactory()
    item = StockItem.objects.create(variant=v, quantity=10, reserved=0)

    # Inbound (+5)
    apply_movement(stock_item_id=item.id, movement_type=StockMovement.TYPE_INBOUND, quantity=5)
    item.refresh_from_db()
    assert item.quantity == 15

    # Outbound (-3)
    apply_movement(stock_item_id=item.id, movement_type=StockMovement.TYPE_OUTBOUND, quantity=-3)
    item.refresh_from_db()
    assert item.quantity == 12

    # Prevent overdraft
    with pytest.raises(MovementError):
        apply_movement(stock_item_id=item.id, movement_type=StockMovement.TYPE_OUTBOUND, quantity=-20)


@pytest.mark.django_db
def test_reservation_create_release_convert():
    v = ProductVariantFactory()
    item = StockItem.objects.create(variant=v, quantity=8, reserved=0)

    # Create reservation of 3
    res = create_reservation(variant_id=v.id, quantity=3, reference="cart#1")
    item.refresh_from_db()
    assert item.reserved == 3
    assert res.state == StockReservation.STATE_ACTIVE

    # Release reservation
    release_reservation(reservation_id=res.id)
    item.refresh_from_db()
    res.refresh_from_db()
    assert item.reserved == 0
    assert res.state == StockReservation.STATE_RELEASED

    # Reserve and convert
    res2 = create_reservation(variant_id=v.id, quantity=2, reference="cart#2")
    convert_reservation_to_order(reservation_id=res2.id)
    item.refresh_from_db()
    res2.refresh_from_db()
    assert item.reserved == 0
    assert item.quantity == 6  # 8 - 2
    assert res2.state == StockReservation.STATE_CONVERTED
