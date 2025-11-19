import json
from decimal import Decimal

import pytest
from cart.tests.factories import UserFactory
from catalog.tests.factories import ProductVariantFactory
from django.core import mail
from django.urls import reverse
from orders.emails import send_order_paid_email
from orders.models import IdempotencyKey, Order, OrderItem, OrderStatusEvent
from orders.services import compute_request_hash, with_idempotency
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_order_update_email_and_address():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)

    order = Order.objects.create(user=user, email="old@example.com")
    variant = ProductVariantFactory()
    OrderItem.objects.create(
        order=order,
        variant=variant,
        product_title="Vintage",
        variant_sku=variant.sku,
        quantity=1,
        unit_price=Decimal("10.00"),
    )

    url = reverse("orders:order-update", kwargs={"order_id": order.id})
    payload = {
        "email": "new@example.com",
        "shipping_address": {
            "recipient": "Jane Doe",
            "line1": "123 Main St",
            "city": "Lagos",
            "country": "ng",
        },
    }
    r = client.patch(url, data=payload, format="json")
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "new@example.com"
    assert (body.get("shipping_address") or {}).get("country") == "NG"


@pytest.mark.django_db
def test_order_update_invalid_email_returns_400():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)

    order = Order.objects.create(user=user)
    url = reverse("orders:order-update", kwargs={"order_id": order.id})
    r = client.patch(url, data={"email": "bad"}, format="json")
    assert r.status_code == 400
    assert r.json()["detail"]


@pytest.mark.django_db
def test_order_update_requires_pending():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)

    order = Order.objects.create(user=user, status=Order.STATUS_PAID)
    url = reverse("orders:order-update", kwargs={"order_id": order.id})
    r = client.patch(url, data={"email": "new@example.com"}, format="json")
    assert r.status_code == 400


@pytest.mark.django_db
def test_status_event_created_on_pay_and_cancel():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)
    order = Order.objects.create(user=user)
    variant = ProductVariantFactory()
    OrderItem.objects.create(
        order=order,
        variant=variant,
        product_title="Vintage",
        variant_sku=variant.sku,
        quantity=1,
        unit_price=Decimal("10.00"),
    )

    # Pay
    pay_url = reverse("orders:order-pay", kwargs={"order_id": order.id})
    r1 = client.post(pay_url)
    assert r1.status_code == 200
    order.refresh_from_db()
    assert OrderStatusEvent.objects.filter(order=order, to_status=Order.STATUS_PAID).exists()

    # Cancel
    # Reset to pending to allow cancellation path to run
    order.status = Order.STATUS_PENDING
    order.save(update_fields=["status"])
    cancel_url = reverse("orders:order-cancel", kwargs={"order_id": order.id})
    r2 = client.post(cancel_url)
    assert r2.status_code == 200
    order.refresh_from_db()
    assert OrderStatusEvent.objects.filter(order=order, to_status=Order.STATUS_CANCELLED).exists()


@pytest.mark.django_db
def test_orders_webhook_requires_signature_when_configured(settings):
    # Configure secret to force signature validation
    settings.ORDERS_WEBHOOK_SECRET = "sk_test_xxx"

    client = APIClient()
    user = UserFactory()
    order = Order.objects.create(user=user)
    payload = {"order_id": order.id, "event": "payment_succeeded"}
    raw = json.dumps(payload).encode("utf-8")
    # No signature header provided → rejected
    r = client.post(
        "/api/v1/orders/webhooks/payment/",
        data=raw,
        content_type="application/json",
    )
    assert r.status_code == 401


@pytest.mark.django_db
def test_orders_list_filters():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)

    o1 = Order.objects.create(user=user, number="ORD-100001", status=Order.STATUS_PENDING)
    o2 = Order.objects.create(user=user, number="ORD-100002", status=Order.STATUS_CANCELLED)

    # Filter by status
    url = reverse("orders:order-list")
    r1 = client.get(url + "?status=cancelled")
    assert r1.status_code == 200
    assert len(r1.json().get("results", [])) == 1
    assert r1.json()["results"][0]["number"] == o2.number

    # Filter by number
    r2 = client.get(url + "?number=ORD-100001")
    assert r2.status_code == 200
    assert len(r2.json().get("results", [])) == 1
    assert r2.json()["results"][0]["number"] == o1.number

    # Filter by start/end with simple ISO dates
    r3 = client.get(url + "?start=2020-01-01")
    assert r3.status_code == 200
    assert len(r3.json().get("results", [])) >= 1

    r4 = client.get(url + "?end=2100-01-01")
    assert r4.status_code == 200
    assert len(r4.json().get("results", [])) >= 1


@pytest.mark.django_db
def test_order_detail_pricing_params():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)
    order = Order.objects.create(user=user)
    variant = ProductVariantFactory()
    OrderItem.objects.create(
        order=order,
        variant=variant,
        product_title="Vintage",
        variant_sku=variant.sku,
        quantity=2,
        unit_price=Decimal("10.00"),
    )

    url = reverse("orders:order-detail", kwargs={"order_id": order.id})
    r = client.get(url + "?tax=2.50&shipping=5&discount=1.25")
    assert r.status_code == 200
    body = r.json()
    # Subtotal 20.00 + 2.50 + 5.00 - 1.25 = 26.25
    assert str(body["total"]) == "26.25"


def test_compute_request_hash_variants():
    # Empty → None
    assert compute_request_hash(None) is None
    # Valid dict
    assert isinstance(compute_request_hash({"a": 1, "b": 2}), str)

    # Non-serializable → None
    class X:
        pass

    assert compute_request_hash({"x": X()}) is None


@pytest.mark.django_db
def test_with_idempotency_conflict_and_cached_returns(user=None):
    user = user or UserFactory()

    # Pre-create a record to trigger IntegrityError path
    key = "idem-key-1"
    scope = f"user:{user.id}"
    idem = IdempotencyKey.objects.create(
        key=key,
        user=user,
        scope=scope,
        path="/api/v1/orders/pay/1",
        method="POST",
        request_hash="abc",
    )
    # In-progress branch: no response stored
    body, code = with_idempotency(
        key=key,
        user=user,
        path="/api/v1/orders/pay/1",
        method="POST",
        request_hash="xyz",
        handler=lambda: ({"ok": True}, 200),
    )
    assert code == 409
    assert body["detail"] in {"Idempotency key reused with different request payload", "Request in progress"}

    # Cached response branch
    idem.response_json = {"ok": True}
    idem.response_code = 200
    idem.save(update_fields=["response_json", "response_code"])
    body2, code2 = with_idempotency(
        key=key,
        user=user,
        path="/api/v1/orders/pay/1",
        method="POST",
        request_hash="abc",
        handler=lambda: ({"ok": False}, 500),
    )
    assert code2 == 200
    assert body2 == {"ok": True}


@pytest.mark.django_db
def test_send_order_paid_email_variants(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.DEFAULT_FROM_EMAIL = "noreply@example.com"
    user = UserFactory()
    order = Order.objects.create(user=user, email="buyer@example.com", number="ORD-123")

    # Without FRONTEND_URL → fallback link
    settings.FRONTEND_URL = ""
    send_order_paid_email(order)
    assert len(mail.outbox) == 1
    assert "Order: ORD-123" in mail.outbox[0].body

    # With FRONTEND_URL → order link
    mail.outbox.clear()
    settings.FRONTEND_URL = "https://shop.example.com"
    send_order_paid_email(order)
    assert len(mail.outbox) == 1
    assert f"/orders/{order.id}" in mail.outbox[0].body


@pytest.mark.django_db
def test_send_order_paid_email_no_recipient(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    user = UserFactory()
    # Ensure user has no email and order has none
    user.email = ""
    user.save(update_fields=["email"])
    order = Order.objects.create(user=user, email="")
    send_order_paid_email(order)
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_orderitem_line_total_property():
    user = UserFactory()
    order = Order.objects.create(user=user)
    variant = ProductVariantFactory()
    item = OrderItem.objects.create(
        order=order,
        variant=variant,
        product_title="Vintage",
        variant_sku=variant.sku,
        quantity=3,
        unit_price=Decimal("7.50"),
    )
    assert item.line_total == Decimal("22.50")


@pytest.mark.django_db
def test_pay_order_cannot_pay_cancelled():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)
    order = Order.objects.create(user=user, status=Order.STATUS_CANCELLED)
    url = reverse("orders:order-pay", kwargs={"order_id": order.id})
    r = client.post(url)
    assert r.status_code == 400


@pytest.mark.django_db
def test_cancel_order_cannot_cancel_paid():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)
    order = Order.objects.create(user=user, status=Order.STATUS_PAID)
    url = reverse("orders:order-cancel", kwargs={"order_id": order.id})
    r = client.post(url)
    assert r.status_code == 400


@pytest.mark.django_db
def test_orders_webhook_allowed_ip(settings):
    settings.ORDERS_WEBHOOK_SECRET = ""
    settings.ORDERS_WEBHOOK_ALLOWED_IPS = ["1.2.3.4"]
    client = APIClient()
    user = UserFactory()
    order = Order.objects.create(user=user)
    payload = {"order_id": order.id, "event": "payment_succeeded"}
    raw = json.dumps(payload).encode("utf-8")
    r = client.post(
        "/api/v1/orders/webhooks/payment/",
        data=raw,
        content_type="application/json",
        HTTP_X_FORWARDED_FOR="1.2.3.4",
    )
    assert r.status_code == 200


@pytest.mark.django_db
def test_order_update_invalid_address_type():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)
    order = Order.objects.create(user=user)
    url = reverse("orders:order-update", kwargs={"order_id": order.id})
    r = client.patch(url, data={"shipping_address": "oops"}, format="json")
    assert r.status_code == 400
