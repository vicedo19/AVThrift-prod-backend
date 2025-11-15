from decimal import Decimal

import pytest
from cart.models import Cart
from cart.services import abandon_cart, add_item, checkout_cart, clear_cart, remove_item, update_item_quantity
from cart.tests.factories import StockItemFactory, UserFactory
from catalog.tests.factories import ProductVariantFactory
from inventory.models import StockReservation
from inventory.services import MovementError


@pytest.mark.django_db
def test_add_item_reserves_stock_and_sets_unit_price():
    user = UserFactory()
    variant = ProductVariantFactory()
    # Ensure stock is available
    StockItemFactory(variant=variant, quantity=10, reserved=0)

    item = add_item(user=user, variant_id=variant.id, quantity=2)

    assert item.cart.status == Cart.STATUS_ACTIVE
    assert item.variant_id == variant.id
    assert item.quantity == 2
    assert item.unit_price == (variant.price or Decimal("0.00"))
    assert item.reservation_id is not None
    res = StockReservation.objects.get(id=item.reservation_id)
    assert res.state == StockReservation.STATE_ACTIVE
    assert res.quantity == 2


@pytest.mark.django_db
def test_update_item_quantity_re_reserves_and_updates_snapshot_price():
    user = UserFactory()
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=10, reserved=0)

    item = add_item(user=user, variant_id=variant.id, quantity=2)
    # Change available price and update quantity
    variant.price = variant.price + Decimal("1.00")
    variant.save(update_fields=["price", "updated_at"])

    item = update_item_quantity(user=user, item_id=item.id, quantity=3)

    assert item.quantity == 3
    assert item.unit_price == variant.price
    assert item.reservation_id is not None
    res = StockReservation.objects.get(id=item.reservation_id)
    assert res.state == StockReservation.STATE_ACTIVE
    assert res.quantity == 3


@pytest.mark.django_db
def test_checkout_cart_converts_reservations_clears_items_and_marks_ordered():
    user = UserFactory()
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=10, reserved=0)

    item = add_item(user=user, variant_id=variant.id, quantity=4)

    checkout_cart(user=user)

    # Cart transitioned to ordered
    cart = Cart.objects.get(user=user)
    assert cart.status == Cart.STATUS_ORDERED
    # Items cleared
    assert cart.items.count() == 0
    # Reservation converted
    res = StockReservation.objects.get(id=item.reservation_id)
    assert res.state == StockReservation.STATE_CONVERTED


@pytest.mark.django_db
def test_abandon_cart_releases_reservations_clears_items_and_marks_abandoned():
    user = UserFactory()
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=10, reserved=0)

    item = add_item(user=user, variant_id=variant.id, quantity=1)

    abandon_cart(user=user)

    cart = Cart.objects.get(user=user)
    assert cart.status == Cart.STATUS_ABANDONED
    assert cart.items.count() == 0
    res = StockReservation.objects.get(id=item.reservation_id)
    assert res.state == StockReservation.STATE_RELEASED


@pytest.mark.django_db
def test_clear_cart_keeps_active_status_but_clears_items_and_releases_reservations():
    user = UserFactory()
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=10, reserved=0)

    item = add_item(user=user, variant_id=variant.id, quantity=2)

    clear_cart(user=user)

    cart = Cart.objects.get(user=user)
    assert cart.status == Cart.STATUS_ACTIVE
    assert cart.items.count() == 0
    res = StockReservation.objects.get(id=item.reservation_id)
    assert res.state == StockReservation.STATE_RELEASED


@pytest.mark.django_db
def test_remove_item_releases_reservation_and_deletes_item():
    user = UserFactory()
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=10, reserved=0)

    item = add_item(user=user, variant_id=variant.id, quantity=2)
    res_id = item.reservation_id

    remove_item(user=user, item_id=item.id)

    # Item deleted
    assert item.cart.items.count() == 0
    # Reservation released
    res = StockReservation.objects.get(id=res_id)
    assert res.state == StockReservation.STATE_RELEASED


@pytest.mark.django_db
def test_add_item_insufficient_stock_raises_error():
    user = UserFactory()
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=1, reserved=0)

    with pytest.raises(MovementError):
        add_item(user=user, variant_id=variant.id, quantity=5)


@pytest.mark.django_db
def test_update_item_insufficient_stock_raises_error():
    user = UserFactory()
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=3, reserved=0)

    item = add_item(user=user, variant_id=variant.id, quantity=2)
    # Make available low (reserved=2, quantity=3 => available=1)
    with pytest.raises(MovementError):
        update_item_quantity(user=user, item_id=item.id, quantity=5)
