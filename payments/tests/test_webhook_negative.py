import hashlib
import hmac
import json

import pytest
from cart.tests.factories import UserFactory
from orders.models import Order
from payments.models import PaymentIntent
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_webhook_invalid_signature_returns_401(settings):
    settings.PAYSTACK_SECRET_KEY = "sk_test_xxx"

    user = UserFactory()
    order = Order.objects.create(user=user)
    PaymentIntent.objects.create(order=order, reference="BAD-SIG-1", amount=0, currency="NGN")

    payload = {"event": "charge.success", "data": {"reference": "BAD-SIG-1", "amount": 0}}
    raw = json.dumps(payload).encode("utf-8")
    # Provide wrong signature
    bad_sig = "deadbeef"

    client = APIClient()
    r = client.post(
        "/api/v1/payments/webhooks/paystack/",
        data=raw,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=bad_sig,
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid signature"


@pytest.mark.django_db
def test_webhook_forbidden_ip_returns_403(settings):
    settings.PAYSTACK_SECRET_KEY = "sk_test_xxx"
    # Whitelist a different IP than the test client's default
    settings.PAYSTACK_WEBHOOK_IPS = ["1.2.3.4"]

    user = UserFactory()
    order = Order.objects.create(user=user)
    PaymentIntent.objects.create(order=order, reference="IP-FORB-1", amount=0, currency="NGN")

    payload = {"event": "charge.success", "data": {"reference": "IP-FORB-1", "amount": 0}}
    raw = json.dumps(payload).encode("utf-8")
    sig = hmac.new(settings.PAYSTACK_SECRET_KEY.encode("utf-8"), msg=raw, digestmod=hashlib.sha512).hexdigest()

    client = APIClient()
    r = client.post(
        "/api/v1/payments/webhooks/paystack/",
        data=raw,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=sig,
    )
    # Test client REMOTE_ADDR defaults to 127.0.0.1 which is not whitelisted
    assert r.status_code == 403
    assert r.json()["detail"] == "Forbidden"


@pytest.mark.django_db
def test_webhook_missing_reference_returns_400(settings):
    settings.PAYSTACK_SECRET_KEY = "sk_test_xxx"

    payload = {"event": "charge.success", "data": {"amount": 100}}
    raw = json.dumps(payload).encode("utf-8")
    sig = hmac.new(settings.PAYSTACK_SECRET_KEY.encode("utf-8"), msg=raw, digestmod=hashlib.sha512).hexdigest()

    client = APIClient()
    r = client.post(
        "/api/v1/payments/webhooks/paystack/",
        data=raw,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=sig,
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Missing reference"


@pytest.mark.django_db
def test_webhook_duplicate_payload_is_ignored(settings):
    settings.PAYSTACK_SECRET_KEY = "sk_test_xxx"

    user = UserFactory()
    order = Order.objects.create(user=user)
    PaymentIntent.objects.create(order=order, reference="DUP-1", amount=0, currency="NGN")

    payload = {"event": "charge.success", "data": {"reference": "DUP-1", "amount": 0}}
    raw = json.dumps(payload).encode("utf-8")
    sig = hmac.new(settings.PAYSTACK_SECRET_KEY.encode("utf-8"), msg=raw, digestmod=hashlib.sha512).hexdigest()

    client = APIClient()
    # First call processes
    r1 = client.post(
        "/api/v1/payments/webhooks/paystack/",
        data=raw,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=sig,
    )
    assert r1.status_code == 200
    # Second identical payload should be ignored idempotently
    r2 = client.post(
        "/api/v1/payments/webhooks/paystack/",
        data=raw,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=sig,
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "ignored"
