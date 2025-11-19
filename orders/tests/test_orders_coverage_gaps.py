from decimal import Decimal
from unittest.mock import patch

import pytest
from catalog.tests.factories import ProductVariantFactory
from django.contrib.auth import get_user_model
from django.urls import reverse
from orders.models import IdempotencyKey, Order, OrderItem
from orders.serializers import OrderSerializer
from orders.services import compute_request_hash, pay_order, with_idempotency
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def _create_order_with_item(user=None):
    User = get_user_model()
    user = user or User.objects.create_user(username="u1", email="u1@example.com", password="x")
    order = Order.objects.create(user=user, email=user.email)
    variant = ProductVariantFactory(price=Decimal("25.00"))
    OrderItem.objects.create(
        order=order,
        variant=variant,
        product_title=variant.product.title,
        variant_sku=variant.sku,
        quantity=2,
        unit_price=Decimal("25.00"),
    )
    return order


def test_serializer_initial_data_overrides():
    order = _create_order_with_item()
    s = OrderSerializer(instance=order, data={"tax": "4.00", "shipping": "5.00", "discount": "3.00"})
    # Access methods directly to hit initial_data path in _pricing_value
    assert s.get_tax(order) == Decimal("4.00")
    assert s.get_shipping(order) == Decimal("5.00")
    assert s.get_discount(order) == Decimal("3.00")


def test_pay_order_handles_logging_and_email_failures():
    order = _create_order_with_item()
    with patch("orders.services.logger.info", side_effect=Exception("log failure")):
        with patch("orders.services.send_order_paid_email", side_effect=Exception("email failure")):
            updated = pay_order(order)
            assert updated.status == Order.STATUS_PAID


def test_with_idempotency_returns_persisted_response_on_reuse_same_hash():
    key = "key-same-hash"

    def handler():
        return {"detail": "ok", "value": Decimal("1.23")}, 200

    body1, code1 = with_idempotency(
        key=key,
        user=None,
        path="/api/v1/orders/1/pay/",
        method="POST",
        request_hash=compute_request_hash({"a": 1}),
        handler=handler,
    )
    assert code1 == 200
    assert body1["detail"] == "ok"

    body2, code2 = with_idempotency(
        key=key,
        user=None,
        path="/api/v1/orders/1/pay/",
        method="POST",
        request_hash=compute_request_hash({"a": 1}),
        handler=handler,
    )
    assert code2 == 200
    assert body2["detail"] == body1["detail"]
    # Persisted response stores Decimal values as strings; normalize for comparison
    assert Decimal(str(body2["value"])) == Decimal("1.23")


def test_with_idempotency_conflict_on_different_hash_without_response():
    key = "key-conflict"
    IdempotencyKey.objects.create(
        key=key,
        scope="anon",
        path="/api/v1/orders/1/pay/",
        method="POST",
        request_hash=compute_request_hash({"a": 1}),
        expires_at=None,
    )

    def handler():
        return {"detail": "ok"}, 200

    body, code = with_idempotency(
        key=key,
        user=None,
        path="/api/v1/orders/1/pay/",
        method="POST",
        request_hash=compute_request_hash({"a": 2}),
        handler=handler,
    )
    assert code == 409
    assert "Idempotency key reused" in body["detail"]


def test_compute_request_hash_handles_unserializable_input():
    class Unserializable:
        pass

    bad = {"x": Unserializable()}
    h = compute_request_hash(bad)
    assert h is None


def test_webhook_validation_errors(client: APIClient):
    # unsupported event
    url = reverse("orders:order-webhook-payment")
    resp = client.post(url, data={"order_id": 1, "event": "noop"}, format="json")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Unsupported event"

    # missing fields
    resp2 = client.post(url, data={"event": "payment_succeeded"}, format="json")
    assert resp2.status_code == 400
    assert resp2.json()["detail"] == "Missing order_id or event"
