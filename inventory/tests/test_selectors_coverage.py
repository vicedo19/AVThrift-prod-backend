from decimal import Decimal

import pytest
from catalog.tests.factories import ProductVariantFactory
from inventory.models import StockItem, StockReservation
from inventory.selectors import (
    available_quantity_for_stock_item,
    list_active_reservations_for_variant,
    list_stock_for_product,
)

pytestmark = pytest.mark.django_db


def test_available_quantity_handles_missing_and_present():
    assert available_quantity_for_stock_item(9999) == 0
    variant = ProductVariantFactory(price=Decimal("10.00"))
    item = StockItem.objects.create(variant=variant, quantity=10, reserved=3)
    assert available_quantity_for_stock_item(item.id) == 7


def test_list_stock_for_product_returns_computed_fields():
    variant = ProductVariantFactory(price=Decimal("10.00"))
    StockItem.objects.create(variant=variant, quantity=5, reserved=2)
    out = list_stock_for_product(variant.product_id)
    assert out and out[0]["variant"] == variant.sku and out[0]["available"] == 3


def test_list_active_reservations_for_variant():
    variant = ProductVariantFactory(price=Decimal("10.00"))
    StockReservation.objects.create(variant=variant, quantity=2, reference="r1")
    out = list_active_reservations_for_variant(variant.id)
    assert out and out[0]["reference"] == "r1"
