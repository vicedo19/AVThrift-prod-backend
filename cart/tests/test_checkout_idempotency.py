import pytest
from cart.tests.factories import StockItemFactory, UserFactory
from catalog.tests.factories import ProductVariantFactory
from orders.models import IdempotencyKey, Order
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_checkout_is_idempotent_with_header():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)

    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=10, reserved=0)

    # Add an item
    r_add = client.post("/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 2}, format="json")
    assert r_add.status_code == 201

    # First checkout
    key = "abc-idem-123"
    r1 = client.post("/api/v1/cart/checkout/", HTTP_IDEMPOTENCY_KEY=key)
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["status"] == "ordered"
    assert isinstance(body1.get("order_id"), int)
    order_id = body1["order_id"]

    # Second checkout with same key: should not create a new order
    r2 = client.post("/api/v1/cart/checkout/", HTTP_IDEMPOTENCY_KEY=key)
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2 == body1

    # Only one order exists for this user
    assert Order.objects.filter(id=order_id, user=user).count() == 1
    assert Order.objects.filter(user=user).count() == 1

    # Idempotency record stored
    idem = IdempotencyKey.objects.get(key=key, user=user, path="/api/v1/cart/checkout/", method="POST")
    assert idem.response_code == 200
    assert idem.response_json == body1
