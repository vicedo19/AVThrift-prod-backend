from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from catalog.tests.factories import ProductVariantFactory
from django.urls import reverse
from inventory.models import StockItem, StockMovement, StockReservation
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_stock_item_list_filters_updated_after_and_ids():
    api = APIClient()
    variant = ProductVariantFactory(price=Decimal("10.00"))
    StockItem.objects.create(variant=variant, quantity=5, reserved=2)
    # No filters
    r0 = api.get(reverse("stock-item-list"))
    assert r0.status_code == 200
    # product_id filter
    r1 = api.get(reverse("stock-item-list"), {"product_id": variant.product_id})
    assert r1.status_code == 200 and r1.json()["count"] >= 1
    # variant_id filter
    r2 = api.get(reverse("stock-item-list"), {"variant_id": variant.id})
    assert r2.status_code == 200 and r2.json()["count"] >= 1
    # sku filter
    r3 = api.get(reverse("stock-item-list"), {"sku": variant.sku})
    assert r3.status_code == 200 and r3.json()["count"] >= 1
    # updated_after invalid -> ignored
    r4 = api.get(reverse("stock-item-list"), {"updated_after": "not-a-date"})
    assert r4.status_code == 200
    # updated_after valid -> filter
    ts = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    r5 = api.get(reverse("stock-item-list"), {"updated_after": ts})
    assert r5.status_code == 200


def test_movement_list_filters_created_after_and_type():
    api = APIClient()
    variant = ProductVariantFactory(price=Decimal("10.00"))
    item = StockItem.objects.create(variant=variant, quantity=5, reserved=0)
    StockMovement.objects.create(stock_item=item, movement_type="inbound", quantity=5)
    # stock_item filter
    r1 = api.get(reverse("movement-list"), {"stock_item": item.id})
    assert r1.status_code == 200 and r1.json()["count"] >= 1
    # movement_type filter
    r2 = api.get(reverse("movement-list"), {"movement_type": "inbound"})
    assert r2.status_code == 200
    # created_after invalid -> ignored
    r3 = api.get(reverse("movement-list"), {"created_after": "bad-date"})
    assert r3.status_code == 200
    # created_after valid -> filtered
    ts = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    r4 = api.get(reverse("movement-list"), {"created_after": ts})
    assert r4.status_code == 200


def test_reservation_list_filters_state_and_expires():
    api = APIClient()
    variant = ProductVariantFactory(price=Decimal("10.00"))
    res = StockReservation.objects.create(variant=variant, quantity=1, reference="r1")
    # variant filter
    r1 = api.get(reverse("reservation-list"), {"variant_id": variant.id})
    assert r1.status_code == 200 and r1.json()["count"] >= 1
    # state filter
    r2 = api.get(reverse("reservation-list"), {"state": res.state})
    assert r2.status_code == 200
    # expires_before invalid -> ignored
    r3 = api.get(reverse("reservation-list"), {"expires_before": "bad-date"})
    assert r3.status_code == 200
    # expires_before valid -> filtered
    ts = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    r4 = api.get(reverse("reservation-list"), {"expires_before": ts})
    assert r4.status_code == 200
