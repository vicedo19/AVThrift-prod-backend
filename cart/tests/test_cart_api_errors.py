import pytest
from cart.tests.factories import StockItemFactory, UserFactory
from catalog.tests.factories import ProductVariantFactory
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_add_item_zero_quantity_returns_400():
    user = UserFactory()
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=5, reserved=0)
    client = APIClient()
    client.force_authenticate(user=user)

    r = client.post("/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 0}, format="json")
    assert r.status_code == 400
    # DRF serializer validation returns field-level error for quantity
    assert "quantity" in r.json()


@pytest.mark.django_db
def test_add_item_insufficient_stock_returns_400():
    user = UserFactory()
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=1, reserved=0)
    client = APIClient()
    client.force_authenticate(user=user)

    r = client.post("/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 10}, format="json")
    assert r.status_code == 400
    assert "detail" in r.json()


@pytest.mark.django_db
def test_update_item_insufficient_stock_returns_400():
    user = UserFactory()
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=3, reserved=0)
    client = APIClient()
    client.force_authenticate(user=user)

    r_add = client.post("/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 2}, format="json")
    item_id = r_add.json()["id"]

    # Attempt to update beyond available stock
    r_upd = client.patch(f"/api/v1/cart/items/{item_id}/", {"quantity": 10}, format="json")
    assert r_upd.status_code == 400
    assert "detail" in r_upd.json()


@pytest.mark.django_db
def test_add_item_nonexistent_variant_returns_404():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)

    # Use a variant id that does not exist
    r = client.post("/api/v1/cart/items/", {"variant_id": 999999, "quantity": 1}, format="json")
    assert r.status_code == 404
    assert "detail" in r.json()


@pytest.mark.django_db
def test_update_item_zero_quantity_returns_400():
    user = UserFactory()
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=5, reserved=0)
    client = APIClient()
    client.force_authenticate(user=user)

    r_add = client.post("/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 2}, format="json")
    item_id = r_add.json()["id"]

    r_upd = client.patch(f"/api/v1/cart/items/{item_id}/", {"quantity": 0}, format="json")
    assert r_upd.status_code == 400
    # DRF validation error returns field-level messages
    assert "quantity" in r_upd.json()
