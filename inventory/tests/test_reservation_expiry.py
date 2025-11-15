import datetime as dt

import pytest
from catalog.tests.factories import ProductVariantFactory
from django.core.management import call_command
from django.utils import timezone
from inventory.models import StockItem, StockReservation
from inventory.services import create_reservation


@pytest.mark.django_db
def test_expire_reservations_releases_active_expired():
    variant = ProductVariantFactory()
    # Ensure stock exists
    StockItem.objects.create(variant=variant, quantity=10, reserved=0)

    expired_at = timezone.now() - dt.timedelta(minutes=5)
    res = create_reservation(variant_id=variant.id, quantity=3, reference="test:expiry", expires_at=expired_at)

    item = StockItem.objects.get(variant=variant)
    assert item.reserved == 3
    assert res.state == StockReservation.STATE_ACTIVE

    call_command("expire_reservations")

    item.refresh_from_db()
    res.refresh_from_db()
    assert item.reserved == 0
    assert res.state == StockReservation.STATE_RELEASED


@pytest.mark.django_db
def test_non_expired_reservations_remain_active():
    variant = ProductVariantFactory()
    StockItem.objects.create(variant=variant, quantity=5, reserved=0)

    future = timezone.now() + dt.timedelta(minutes=30)
    res = create_reservation(variant_id=variant.id, quantity=2, reference="test:expiry", expires_at=future)

    call_command("expire_reservations")

    res.refresh_from_db()
    item = StockItem.objects.get(variant=variant)
    assert res.state == StockReservation.STATE_ACTIVE
    assert item.reserved == 2
