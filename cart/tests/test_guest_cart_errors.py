import pytest
from cart.tests.factories import StockItemFactory, UserFactory
from catalog.tests.factories import ProductVariantFactory
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_guest_cart_detail_missing_header_returns_400():
    client = APIClient()
    r = client.get("/api/v1/cart/guest/")
    assert r.status_code == 400
    assert r.json()["detail"] == "Missing X-Session-Id."


@pytest.mark.django_db
def test_guest_add_item_missing_session_id_returns_400():
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=5, reserved=0)
    client = APIClient()

    # No header and no session_id in body -> serializer error
    r = client.post(
        "/api/v1/cart/guest/items/",
        {"variant_id": variant.id, "quantity": 1},
        format="json",
    )
    assert r.status_code == 400
    # DRF field error for required session_id
    assert "session_id" in r.json()


@pytest.mark.django_db
def test_guest_update_item_missing_header_returns_400():
    session_id = "s-upd-missing"
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=5, reserved=0)

    # Create an item under the guest session
    anon = APIClient()
    r_add = anon.post(
        "/api/v1/cart/guest/items/",
        {"variant_id": variant.id, "quantity": 1},
        format="json",
        HTTP_X_SESSION_ID=session_id,
    )
    assert r_add.status_code == 201
    item_id = r_add.json()["id"]

    # Attempt to update without header (and without session_id in body)
    r_upd = anon.patch(
        f"/api/v1/cart/guest/items/{item_id}/",
        {"quantity": 2},
        format="json",
    )
    assert r_upd.status_code == 400
    assert r_upd.json()["detail"] == "Missing X-Session-Id."


@pytest.mark.django_db
def test_guest_delete_item_missing_header_returns_400():
    session_id = "s-del-missing"
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=5, reserved=0)

    anon = APIClient()
    r_add = anon.post(
        "/api/v1/cart/guest/items/",
        {"variant_id": variant.id, "quantity": 1},
        format="json",
        HTTP_X_SESSION_ID=session_id,
    )
    assert r_add.status_code == 201
    item_id = r_add.json()["id"]

    r_del = anon.delete(f"/api/v1/cart/guest/items/{item_id}/delete/")
    assert r_del.status_code == 400
    assert r_del.json()["detail"] == "Missing X-Session-Id."


@pytest.mark.django_db
def test_guest_clear_missing_header_returns_400():
    client = APIClient()
    r = client.post("/api/v1/cart/guest/clear/")
    assert r.status_code == 400
    assert r.json()["detail"] == "Missing X-Session-Id."


@pytest.mark.django_db
def test_merge_guest_cart_missing_header_returns_400():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)

    r = client.post("/api/v1/cart/merge-guest/")
    assert r.status_code == 400
    assert r.json()["detail"] == "Missing X-Session-Id."


@pytest.mark.django_db
def test_merge_guest_cart_unauthenticated_returns_401():
    client = APIClient()
    r = client.post("/api/v1/cart/merge-guest/", HTTP_X_SESSION_ID="s-any")
    assert r.status_code == 401
