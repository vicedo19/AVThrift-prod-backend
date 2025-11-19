from decimal import Decimal

import pytest
from cart.tests.factories import StockItemFactory, UserFactory
from catalog.tests.factories import ProductVariantFactory
from inventory.models import StockItem
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_cart_detail_initial_empty():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)

    resp = client.get("/api/v1/cart/")
    assert resp.status_code == 200
    body = resp.json()
    assert "id" in body
    assert body["items"] == []
    assert body["subtotal"] == "0.00"
    assert body["total"] == "0.00"


@pytest.mark.django_db
def test_add_item_endpoint_creates_item_and_reservation():
    user = UserFactory()
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=5, reserved=0)
    client = APIClient()
    client.force_authenticate(user=user)

    resp = client.post("/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 2}, format="json")
    assert resp.status_code == 201
    item_id = resp.json()["id"]

    # Cart detail reflects item and totals
    resp2 = client.get("/api/v1/cart/")
    assert resp2.status_code == 200
    body = resp2.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == item_id
    assert Decimal(body["subtotal"]) == Decimal(body["items"][0]["unit_price"]) * Decimal(body["items"][0]["quantity"])


@pytest.mark.django_db
def test_update_item_quantity_endpoint():
    user = UserFactory()
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=10, reserved=0)
    client = APIClient()
    client.force_authenticate(user=user)

    r_add = client.post("/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 2}, format="json")
    item_id = r_add.json()["id"]

    r_upd = client.patch(f"/api/v1/cart/items/{item_id}/", {"quantity": 3}, format="json")
    assert r_upd.status_code == 200
    assert r_upd.json()["id"] == item_id


@pytest.mark.django_db
def test_delete_item_endpoint():
    user = UserFactory()
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=10, reserved=0)
    client = APIClient()
    client.force_authenticate(user=user)

    r_add = client.post("/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 2}, format="json")
    item_id = r_add.json()["id"]

    r_del = client.delete(f"/api/v1/cart/items/{item_id}/delete/")
    assert r_del.status_code == 204


@pytest.mark.django_db
def test_clear_checkout_abandon_endpoints():
    user = UserFactory()
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=10, reserved=0)
    client = APIClient()
    client.force_authenticate(user=user)

    # Add item
    client.post("/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 2}, format="json")

    # Clear
    r_clear = client.post("/api/v1/cart/clear/")
    assert r_clear.status_code == 200
    assert r_clear.json()["status"] == "cleared"

    # Add again
    client.post("/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 3}, format="json")

    # Checkout
    r_checkout = client.post("/api/v1/cart/checkout/")
    assert r_checkout.status_code == 200
    assert r_checkout.json()["status"] == "ordered"

    # After checkout, adding a new item should recreate active cart
    StockItem.objects.filter(variant=variant).update(quantity=20)  # ensure stock available for new add
    client.post("/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 1}, format="json")

    # Abandon
    r_abandon = client.post("/api/v1/cart/abandon/")
    assert r_abandon.status_code == 200
    assert r_abandon.json()["status"] == "abandoned"
