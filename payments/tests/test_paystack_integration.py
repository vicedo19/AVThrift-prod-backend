import hashlib
import hmac
import json
from decimal import Decimal

import pytest
from cart.tests.factories import UserFactory
from catalog.tests.factories import ProductVariantFactory
from orders.models import Order, OrderItem
from payments.models import PaymentIntent
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_initialize_paystack_transaction(monkeypatch, settings):
    settings.PAYSTACK_SECRET_KEY = "sk_test_xxx"
    settings.PAYSTACK_BASE_URL = "https://api.paystack.co"
    settings.PAYSTACK_CURRENCY = "NGN"

    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)

    order = Order.objects.create(user=user, email=getattr(user, "email", None))
    variant = ProductVariantFactory()
    OrderItem.objects.create(
        order=order,
        variant=variant,
        product_title="Test",
        variant_sku=variant.sku,
        quantity=2,
        unit_price=Decimal("25.00"),
    )

    class DummyResp:
        status_code = 200

        def json(self):
            return {
                "status": True,
                "data": {
                    "authorization_url": "https://paystack.com/authorize/abc",
                    "access_code": "AC_code",
                },
            }

    def fake_post(url, headers=None, json=None, timeout=None):
        return DummyResp()

    monkeypatch.setattr("httpx.post", fake_post)

    r = client.post(
        "/api/v1/payments/paystack/initialize/",
        {"order_id": order.id},
        format="json",
        HTTP_IDEMPOTENCY_KEY="idem-init-1",
    )
    assert r.status_code == 200
    body = r.json()
    assert body["authorization_url"].startswith("https://paystack.com/")
    assert PaymentIntent.objects.filter(order=order).exists()


@pytest.mark.django_db
def test_initialize_paystack_with_custom_currency(monkeypatch, settings):
    settings.PAYSTACK_SECRET_KEY = "sk_test_xxx"
    settings.PAYSTACK_BASE_URL = "https://api.paystack.co"
    settings.PAYSTACK_CURRENCY = "NGN"
    settings.PAYSTACK_SUPPORTED_CURRENCIES = ["NGN", "USD"]

    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)

    order = Order.objects.create(user=user, email=getattr(user, "email", None))
    variant = ProductVariantFactory()
    OrderItem.objects.create(
        order=order,
        variant=variant,
        product_title="Test",
        variant_sku=variant.sku,
        quantity=1,
        unit_price=Decimal("10.00"),
    )

    captured = {"payload": None}

    class DummyResp:
        status_code = 200

        def json(self):
            return {
                "status": True,
                "data": {
                    "authorization_url": "https://paystack.com/authorize/abc",
                    "access_code": "AC_code",
                },
            }

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["payload"] = json
        return DummyResp()

    monkeypatch.setattr("httpx.post", fake_post)

    r = client.post(
        "/api/v1/payments/paystack/initialize/",
        {"order_id": order.id, "currency": "USD"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="idem-init-2",
    )
    assert r.status_code == 200
    assert captured["payload"]["currency"] == "USD"
    body = r.json()
    assert body["currency"] == "USD"


@pytest.mark.django_db
def test_initialize_paystack_rejects_unsupported_currency(monkeypatch, settings):
    settings.PAYSTACK_SECRET_KEY = "sk_test_xxx"
    settings.PAYSTACK_BASE_URL = "https://api.paystack.co"
    settings.PAYSTACK_CURRENCY = "NGN"
    settings.PAYSTACK_SUPPORTED_CURRENCIES = ["NGN", "USD"]

    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)

    order = Order.objects.create(user=user, email=getattr(user, "email", None))

    class DummyResp:
        status_code = 200

        def json(self):
            return {"status": True, "data": {"authorization_url": "", "access_code": ""}}

    def fake_post(url, headers=None, json=None, timeout=None):
        return DummyResp()

    monkeypatch.setattr("httpx.post", fake_post)

    r = client.post(
        "/api/v1/payments/paystack/initialize/",
        {"order_id": order.id, "currency": "EUR"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="idem-init-3",
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Unsupported currency"


@pytest.mark.django_db
def test_paystack_webhook_marks_order_paid(settings, monkeypatch):
    settings.PAYSTACK_SECRET_KEY = "sk_test_xxx"

    user = UserFactory()
    order = Order.objects.create(user=user)
    intent = PaymentIntent.objects.create(
        order=order,
        reference="ref-123",
        amount=Decimal("50.00"),
        currency="NGN",
    )

    payload = {
        "event": "charge.success",
        "data": {"reference": "ref-123", "amount": 5000},
    }
    raw = json.dumps(payload).encode("utf-8")
    sig = hmac.new(settings.PAYSTACK_SECRET_KEY.encode("utf-8"), msg=raw, digestmod=hashlib.sha512).hexdigest()

    client = APIClient()
    r = client.post(
        "/api/v1/payments/webhooks/paystack/",
        data=raw,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=sig,
    )
    assert r.status_code == 200
    intent.refresh_from_db()
    order.refresh_from_db()
    assert intent.status == PaymentIntent.STATUS_SUCCEEDED
    assert order.status == Order.STATUS_PAID


@pytest.mark.django_db
def test_paystack_webhook_respects_currency_minor_units(settings):
    settings.PAYSTACK_SECRET_KEY = "sk_test_xxx"

    user = UserFactory()
    order = Order.objects.create(user=user)
    intent = PaymentIntent.objects.create(
        order=order,
        reference="ref-USD-1",
        amount=Decimal("12.34"),
        currency="USD",
    )

    # Paystack sends minor units; for USD, cents -> 1234
    payload = {
        "event": "charge.success",
        "data": {"reference": "ref-USD-1", "amount": 1234},
    }
    raw = json.dumps(payload).encode("utf-8")
    sig = hmac.new(settings.PAYSTACK_SECRET_KEY.encode("utf-8"), msg=raw, digestmod=hashlib.sha512).hexdigest()

    client = APIClient()
    r = client.post(
        "/api/v1/payments/webhooks/paystack/",
        data=raw,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=sig,
    )
    assert r.status_code == 200
    intent.refresh_from_db()
    order.refresh_from_db()
    assert intent.status == PaymentIntent.STATUS_SUCCEEDED
    assert order.status == Order.STATUS_PAID
