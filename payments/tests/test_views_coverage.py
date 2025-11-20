import hashlib
import hmac
import json
from decimal import Decimal

import pytest
from cart.tests.factories import UserFactory
from catalog.tests.factories import ProductVariantFactory
from django.urls import reverse
from orders.models import Order, OrderItem
from payments.models import PaymentIntent
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def make_order_with_item(user=None) -> Order:
    user = user or UserFactory()
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


def test_payment_intent_detail_404s():
    api = APIClient()
    u1 = UserFactory()
    u2 = UserFactory()
    api.force_authenticate(user=u1)
    # Not found
    r1 = api.get(reverse("payments:payment-intent-detail", kwargs={"reference": "missing"}))
    assert r1.status_code == 404
    # Non-owner
    order = make_order_with_item(user=u2)
    intent = PaymentIntent.objects.create(order=order, reference="r-1", amount=Decimal("10.00"), currency="NGN")
    r2 = api.get(reverse("payments:payment-intent-detail", kwargs={"reference": intent.reference}))
    assert r2.status_code == 404


def test_paystack_initialize_validation_branches(settings):
    settings.PAYSTACK_SUPPORTED_CURRENCIES = ["NGN"]
    api = APIClient()
    user = UserFactory()
    api.force_authenticate(user=user)
    order = make_order_with_item(user=user)
    url = reverse("payments:paystack-initialize")
    # Missing order_id -> specific error
    r1 = api.post(url, data={"currency": "NGN"}, format="json")
    assert r1.status_code == 400 and r1.json()["detail"] == "order_id is required"
    # Invalid amount -> specific error
    r2 = api.post(url, data={"order_id": order.id, "amount": "x", "currency": "NGN"}, format="json")
    assert r2.status_code == 400 and r2.json()["detail"] == "Invalid amount"
    # Invalid currency -> specific error
    r3 = api.post(url, data={"order_id": order.id, "currency": "BAD"}, format="json")
    assert r3.status_code == 400 and r3.json()["detail"] == "Unsupported currency"
    # Order not found -> 404
    r4 = api.post(url, data={"order_id": 999999, "currency": "NGN"}, format="json")
    assert r4.status_code == 404
    # Supported list rejects USD
    r5 = api.post(url, data={"order_id": order.id, "currency": "USD"}, format="json")
    assert r5.status_code == 400 and r5.json()["detail"] == "Unsupported currency"


def test_paystack_webhook_paths(settings):
    settings.PAYSTACK_SECRET_KEY = "secret"
    settings.PAYSTACK_WEBHOOK_IPS = []
    api = APIClient()
    url = reverse("payments:paystack-webhook")

    # Invalid signature
    body = json.dumps({"event": "noop", "data": {}}).encode("utf-8")
    r1 = api.post(url, data=body, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE="bad")
    assert r1.status_code == 401

    # Invalid payload (signature matches raw body but JSON decode fails)
    raw_bad = b"not-json"
    sig_bad = hmac.new(b"secret", raw_bad, hashlib.sha512).hexdigest()
    r2 = api.post(url, data=raw_bad, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE=sig_bad)
    assert r2.status_code == 400

    # Missing reference
    good_sig2 = hmac.new(b"secret", body, hashlib.sha512).hexdigest()
    r3 = api.post(url, data=body, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE=good_sig2)
    assert r3.status_code == 400 and r3.json()["detail"] == "Missing reference"

    # Intent not found
    payload_nf = json.dumps({"event": "charge.success", "data": {"reference": "missing"}}).encode("utf-8")
    sig_nf = hmac.new(b"secret", payload_nf, hashlib.sha512).hexdigest()
    r4 = api.post(url, data=payload_nf, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE=sig_nf)
    assert r4.status_code == 404

    # Duplicate payload ignored (and idempotency tracking exception tolerated)
    user = UserFactory()
    order = make_order_with_item(user=user)
    intent = PaymentIntent.objects.create(order=order, reference="dup", amount=Decimal("10.00"), currency="NGN")
    payload_dup = json.dumps({"event": "noop", "data": {"reference": intent.reference}}).encode("utf-8")
    sig_dup = hmac.new(b"secret", payload_dup, hashlib.sha512).hexdigest()
    r5 = api.post(url, data=payload_dup, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE=sig_dup)
    assert r5.status_code == 200
    # Simulate exception during metadata save to hit tolerance branch
    from payments import views as payments_views

    original_save = payments_views.PaymentIntent.save

    def failing_save(self, *args, **kwargs):
        if kwargs.get("update_fields") == ["metadata", "updated_at"]:
            raise Exception("boom")
        return original_save(self, *args, **kwargs)

    payments_views.PaymentIntent.save = failing_save

    r6 = api.post(url, data=payload_dup, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE=sig_dup)
    assert r6.status_code == 200 and r6.json()["status"] == "ignored"
    payments_views.PaymentIntent.save = original_save

    # charge.success processed
    payload_ok = json.dumps({"event": "charge.success", "data": {"reference": intent.reference}}).encode("utf-8")
    sig_ok = hmac.new(b"secret", payload_ok, hashlib.sha512).hexdigest()
    r7 = api.post(url, data=payload_ok, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE=sig_ok)
    assert r7.status_code == 200 and r7.json()["status"] == "processed"

    # charge.failed processed
    payload_fail = json.dumps({"event": "charge.failed", "data": {"reference": intent.reference}}).encode("utf-8")
    sig_fail = hmac.new(b"secret", payload_fail, hashlib.sha512).hexdigest()
    r8 = api.post(url, data=payload_fail, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE=sig_fail)
    assert r8.status_code == 200 and r8.json()["status"] == "processed"
