from decimal import Decimal

import pytest
from cart.models import Cart
from cart.tests.factories import StockItemFactory, UserFactory
from catalog.tests.factories import ProductVariantFactory
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_guest_cart_endpoints_add_update_delete_clear():
    session_id = "sess-123"
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=5, reserved=0)
    client = APIClient()

    # Detail should auto-create empty cart
    r_detail = client.get("/api/v1/cart/guest/", HTTP_X_SESSION_ID=session_id)
    assert r_detail.status_code == 200
    assert r_detail.json()["items"] == []
    assert r_detail.json()["subtotal"] == "0.00"

    # Add item
    r_add = client.post(
        "/api/v1/cart/guest/items/",
        {"variant_id": variant.id, "quantity": 2},
        format="json",
        HTTP_X_SESSION_ID=session_id,
    )
    assert r_add.status_code == 201
    item_id = r_add.json()["id"]

    # Update quantity
    r_upd = client.patch(
        f"/api/v1/cart/guest/items/{item_id}/",
        {"quantity": 3},
        format="json",
        HTTP_X_SESSION_ID=session_id,
    )
    assert r_upd.status_code == 200
    assert r_upd.json()["id"] == item_id

    # Detail reflects totals
    r_detail2 = client.get("/api/v1/cart/guest/", HTTP_X_SESSION_ID=session_id)
    assert r_detail2.status_code == 200
    body = r_detail2.json()
    assert len(body["items"]) == 1
    assert Decimal(body["subtotal"]) == Decimal(body["items"][0]["unit_price"]) * Decimal(body["items"][0]["quantity"])

    # Delete item
    r_del = client.delete(f"/api/v1/cart/guest/items/{item_id}/delete/", HTTP_X_SESSION_ID=session_id)
    assert r_del.status_code == 204

    # Clear (idempotent)
    r_clear = client.post("/api/v1/cart/guest/clear/", HTTP_X_SESSION_ID=session_id)
    assert r_clear.status_code == 200
    assert r_clear.json()["status"] == "cleared"


@pytest.mark.django_db
def test_merge_guest_cart_into_user_cart():
    session_id = "sess-merge-1"
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)
    anon = APIClient()

    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=20, reserved=0)

    # Guest adds 1
    r_g_add = anon.post(
        "/api/v1/cart/guest/items/",
        {"variant_id": variant.id, "quantity": 1},
        format="json",
        HTTP_X_SESSION_ID=session_id,
    )
    assert r_g_add.status_code == 201

    # User adds 2
    r_u_add = client.post(
        "/api/v1/cart/items/",
        {"variant_id": variant.id, "quantity": 2},
        format="json",
    )
    assert r_u_add.status_code == 201

    # Merge
    r_merge = client.post("/api/v1/cart/merge-guest/", HTTP_X_SESSION_ID=session_id)
    assert r_merge.status_code == 200
    assert r_merge.json()["status"] == "merged"

    # User cart should have qty=3
    r_detail = client.get("/api/v1/cart/")
    assert r_detail.status_code == 200
    items = r_detail.json()["items"]
    assert len(items) == 1
    assert int(items[0]["quantity"]) == 3

    # Guest active cart should be gone (not recreated until accessed)
    assert not Cart.objects.filter(session_id=session_id, status=Cart.STATUS_ACTIVE).exists()
