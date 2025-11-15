import pytest
from cart.tests.factories import StockItemFactory, UserFactory
from catalog.tests.factories import ProductVariantFactory
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_unauthenticated_requests_return_401():
    client = APIClient()

    # Cart detail requires auth
    r_detail = client.get("/api/v1/cart/")
    assert r_detail.status_code == 401

    # Add item requires auth
    r_add = client.post("/api/v1/cart/items/", {"variant_id": 1, "quantity": 1}, format="json")
    assert r_add.status_code == 401


@pytest.mark.django_db
def test_cross_user_item_access_returns_404():
    # User 1 creates an item
    user1 = UserFactory()
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=10, reserved=0)
    c1 = APIClient()
    c1.force_authenticate(user=user1)
    r_add = c1.post("/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 2}, format="json")
    assert r_add.status_code == 201
    item_id = r_add.json()["id"]

    # User 2 attempts to update/delete user1's item -> 404
    user2 = UserFactory()
    c2 = APIClient()
    c2.force_authenticate(user=user2)

    r_upd = c2.patch(f"/api/v1/cart/items/{item_id}/", {"quantity": 3}, format="json")
    assert r_upd.status_code == 404

    r_del = c2.delete(f"/api/v1/cart/items/{item_id}/delete/")
    assert r_del.status_code == 404
