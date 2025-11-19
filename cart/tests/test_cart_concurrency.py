import threading
from typing import List

import pytest
from cart.services import add_item, update_item_quantity
from cart.tests.factories import StockItemFactory, UserFactory
from catalog.tests.factories import ProductVariantFactory
from django.db import close_old_connections, connection
from inventory.models import StockItem, StockReservation
from inventory.services import MovementError


@pytest.mark.django_db
def test_rapid_quantity_updates_syncs_to_latest_reservation():
    user = UserFactory()
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=10, reserved=0)

    # Start with quantity=1
    item = add_item(user=user, variant_id=variant.id, quantity=1)
    # Rapid updates to different quantities
    update_item_quantity(user=user, item_id=item.id, quantity=2)
    update_item_quantity(user=user, item_id=item.id, quantity=5)
    item = update_item_quantity(user=user, item_id=item.id, quantity=3)

    # Final reservation should reflect latest quantity
    stock_item = StockItem.objects.get(variant_id=variant.id)
    assert stock_item.reserved == 3

    # Only one active reservation should remain for the variant
    active = list(StockReservation.objects.filter(variant_id=variant.id, state=StockReservation.STATE_ACTIVE))
    assert len(active) == 1
    assert active[0].quantity == 3


@pytest.mark.django_db
def test_competing_reservations_two_users_exceeds_available():
    user1 = UserFactory()
    user2 = UserFactory()
    variant = ProductVariantFactory()
    # Only 5 available
    StockItemFactory(variant=variant, quantity=5, reserved=0)

    # First user reserves 3 successfully
    item1 = add_item(user=user1, variant_id=variant.id, quantity=3)
    stock_item = StockItem.objects.get(variant_id=variant.id)
    assert stock_item.reserved == 3

    # Second user attempts to reserve 3 (would exceed available=2 -> 3)
    with pytest.raises(MovementError):
        add_item(user=user2, variant_id=variant.id, quantity=3)

    stock_item.refresh_from_db()
    assert stock_item.reserved == 3

    # Only one active reservation exists
    active = list(StockReservation.objects.filter(variant_id=variant.id, state=StockReservation.STATE_ACTIVE))
    assert len(active) == 1
    assert active[0].quantity == 3
    assert active[0].id == item1.reservation_id


@pytest.mark.django_db
def test_update_failure_leaves_consistent_state_and_allows_future_updates():
    user = UserFactory()
    variant = ProductVariantFactory()
    # Make 3 available, reserve 2 via add_item
    StockItemFactory(variant=variant, quantity=3, reserved=0)
    item = add_item(user=user, variant_id=variant.id, quantity=2)

    # Attempt to update to 5 -> should fail; previous reservation should remain due to atomic rollback
    with pytest.raises(MovementError):
        update_item_quantity(user=user, item_id=item.id, quantity=5)

    stock_item = StockItem.objects.get(variant_id=variant.id)
    assert stock_item.reserved == 2  # unchanged because the whole transaction rolled back

    # The item's reservation record should still be active
    res = StockReservation.objects.get(id=item.reservation_id)
    assert res.state == StockReservation.STATE_ACTIVE

    # Future update within availability should succeed and create a new active reservation
    item = update_item_quantity(user=user, item_id=item.id, quantity=1)
    stock_item.refresh_from_db()
    assert stock_item.reserved == 1
    res2 = StockReservation.objects.get(id=item.reservation_id)
    assert res2.state == StockReservation.STATE_ACTIVE


def _update_worker(
    barrier: threading.Barrier, user, item_id: int, qty: int, successes: List[int], errors: List[Exception]
):
    # Ensure this thread uses its own DB connection
    close_old_connections()
    barrier.wait()
    try:
        update_item_quantity(user=user, item_id=item_id, quantity=qty)
        successes.append(qty)
    except Exception as exc:  # pragma: no cover
        errors.append(exc)


def _add_item_worker(
    barrier: threading.Barrier, user, variant_id: int, qty: int, successes: List[int], errors: List[Exception]
):
    close_old_connections()
    barrier.wait()
    try:
        add_item(user=user, variant_id=variant_id, quantity=qty)
        successes.append(qty)
    except Exception as exc:  # pragma: no cover
        errors.append(exc)


@pytest.mark.django_db(transaction=True)
def test_threaded_concurrent_updates_same_item():
    if connection.vendor == "sqlite":
        pytest.skip("SQLite lacks real concurrent transactions; skipping threaded test.")
    # Start with a stock item and a cart item at quantity 1
    user = UserFactory()
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=10, reserved=0)
    item = add_item(user=user, variant_id=variant.id, quantity=1)

    barrier = threading.Barrier(2)
    successes: List[int] = []
    errors: List[Exception] = []

    t1 = threading.Thread(target=_update_worker, args=(barrier, user, item.id, 4, successes, errors))
    t2 = threading.Thread(target=_update_worker, args=(barrier, user, item.id, 3, successes, errors))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Reload entities
    stock_item = StockItem.objects.get(variant_id=variant.id)
    item.refresh_from_db()

    # Invariants: one active reservation, reserved matches item.quantity, quantity is either 3 or 4
    active = list(StockReservation.objects.filter(variant_id=variant.id, state=StockReservation.STATE_ACTIVE))
    assert len(active) == 1
    assert stock_item.reserved == item.quantity
    assert item.quantity in {3, 4}
    # Ensure both threads attempted updates; at least one succeeded
    assert len(successes) >= 1
    assert len(errors) >= 0


@pytest.mark.django_db(transaction=True)
def test_threaded_competing_add_item_two_users():
    if connection.vendor == "sqlite":
        pytest.skip("SQLite lacks real concurrent transactions; skipping threaded test.")
    # Limited stock so both cannot reserve the full requested quantity
    user1 = UserFactory()
    user2 = UserFactory()
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=3, reserved=0)

    barrier = threading.Barrier(2)
    successes: List[int] = []
    errors: List[Exception] = []

    t1 = threading.Thread(target=_add_item_worker, args=(barrier, user1, variant.id, 3, successes, errors))
    t2 = threading.Thread(target=_add_item_worker, args=(barrier, user2, variant.id, 3, successes, errors))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    stock_item = StockItem.objects.get(variant_id=variant.id)

    # Exactly one should succeed; overbooking is prevented
    assert len(successes) == 1
    assert len(errors) == 1
    assert stock_item.reserved == 3
    # Only one active reservation exists
    active = list(StockReservation.objects.filter(variant_id=variant.id, state=StockReservation.STATE_ACTIVE))
    assert len(active) == 1
