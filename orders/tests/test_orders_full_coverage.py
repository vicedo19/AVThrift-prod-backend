from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from cart.tests.factories import UserFactory
from catalog.tests.factories import ProductVariantFactory
from django.urls import reverse
from orders.models import IdempotencyKey, Order, OrderItem, OrderStatusEvent
from orders.serializers import OrderSerializer
from orders.services import (
    cancel_order,
    pay_order,
    update_order_contact,
    verify_orders_webhook,
    with_idempotency,
)
from rest_framework.test import APIClient, APIRequestFactory

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


def test_serializer_invalid_pricing_context_and_initial_data():
    order = make_order_with_item()
    s1 = OrderSerializer(instance=order, context={"pricing": {"tax": "abc"}})
    assert s1.get_tax(order) == Decimal("0.00")
    s2 = OrderSerializer(instance=order, data={"shipping": "xyz"})
    assert s2.get_shipping(order) == Decimal("0.00")


def test_pay_order_event_and_fulfillment_exceptions_are_swallowed():
    order = make_order_with_item()
    with patch.object(OrderStatusEvent.objects, "create", side_effect=Exception("evt fail")):
        with patch("orders.services.schedule_fulfillment", side_effect=Exception("sched fail")):
            updated = pay_order(order)
            assert updated.status == Order.STATUS_PAID


def test_pay_order_returns_when_already_paid():
    order = make_order_with_item()
    order.status = Order.STATUS_PAID
    order.save(update_fields=["status"])
    updated = pay_order(order)
    assert updated.status == Order.STATUS_PAID


def test_cancel_order_returns_when_already_cancelled():
    order = make_order_with_item()
    order.status = Order.STATUS_CANCELLED
    order.save(update_fields=["status"])
    updated = cancel_order(order)
    assert updated.status == Order.STATUS_CANCELLED


def test_cancel_order_exceptions_do_not_block():
    order = make_order_with_item()
    with patch.object(OrderStatusEvent.objects, "create", side_effect=Exception("evt fail")):
        with patch("orders.services.logger.info", side_effect=Exception("log fail")):
            with patch("orders.services.initiate_reimbursement_for_cancellation", side_effect=Exception("refund fail")):
                updated = cancel_order(order)
                assert updated.status == Order.STATUS_CANCELLED


def test_with_idempotency_in_progress_returns_409():
    key = "in-progress-key"
    IdempotencyKey.objects.create(
        key=key,
        scope="anon",
        path="/api/v1/orders/1/pay/",
        method="POST",
        request_hash="h1",
        expires_at=None,
    )

    def handler():
        return {"detail": "ok"}, 200

    body, code = with_idempotency(
        key=key,
        user=None,
        path="/api/v1/orders/1/pay/",
        method="POST",
        request_hash="h1",
        handler=handler,
    )
    assert code == 409 and "in progress" in body["detail"].lower()
    # Execute handler to cover branch
    assert handler()[1] == 200


def test_verify_webhook_signature_paths(settings):
    settings.ORDERS_WEBHOOK_SECRET = "secret"
    # missing signature
    req_missing = SimpleNamespace(headers={}, body=b"{}", META={})
    ok, reason = verify_orders_webhook(req_missing)
    assert not ok and reason == "missing_signature"
    # bad signature
    req_bad = SimpleNamespace(headers={"X-Paystack-Signature": "bad"}, body=b"{}", META={})
    ok2, reason2 = verify_orders_webhook(req_bad)
    assert not ok2 and reason2 == "bad_signature"
    # good signature
    import hashlib
    import hmac

    body = b"{}"
    sig = hmac.new(b"secret", body, hashlib.sha512).hexdigest()
    req_good = SimpleNamespace(headers={"X-Paystack-Signature": sig}, body=body, META={})
    ok3, reason3 = verify_orders_webhook(req_good)
    assert ok3 and reason3 is None


def test_verify_webhook_ip_allowlist_paths(settings):
    settings.ORDERS_WEBHOOK_SECRET = ""
    settings.ORDERS_WEBHOOK_ALLOWED_IPS = ["1.2.3.4"]
    req = SimpleNamespace(headers={}, body=b"{}", META={"REMOTE_ADDR": "5.6.7.8"})
    ok, reason = verify_orders_webhook(req)
    assert not ok and reason == "ip_not_allowed"


def test_verify_webhook_verification_error(settings):
    settings.ORDERS_WEBHOOK_SECRET = "secret"

    class BadHeaders:
        def get(self, *args, **kwargs):
            raise Exception("boom")

    req_bad = SimpleNamespace(headers=BadHeaders(), body=b"{}", META={})
    ok, reason = verify_orders_webhook(req_bad)
    assert not ok and reason == "verification_error"


def test_update_order_contact_validations_and_updates():
    order = make_order_with_item()
    with pytest.raises(ValueError):
        update_order_contact(order, email="bad-email")
    with pytest.raises(ValueError):
        update_order_contact(order, shipping_address="not-a-dict")
    with pytest.raises(ValueError):
        update_order_contact(order, shipping_address={"recipient": "X", "line1": "Y", "city": "Z"})
    updated = update_order_contact(
        order,
        email="New@Example.com",
        shipping_address={"recipient": "A", "line1": "B", "city": "C", "country": "ng"},
    )
    assert updated.email == "new@example.com" and updated.shipping_address["country"] == "NG"

    # No updates path
    unchanged = update_order_contact(order)
    assert unchanged.id == order.id

    # Address update without country should raise
    order3 = make_order_with_item()
    with pytest.raises(ValueError):
        update_order_contact(
            order3,
            shipping_address={"recipient": "A", "line1": "B", "city": "C"},
        )


def test_order_detail_get_object_value_error():
    user = UserFactory()
    factory = APIRequestFactory()
    req = factory.get("/api/v1/orders/abc/")
    req.user = user
    from orders.views import OrderDetailView

    view = OrderDetailView()
    view.request = req
    view.kwargs = {"order_id": "abc"}
    with pytest.raises(Exception):
        view.get_object()


def test_orders_views_edge_branches(settings):
    api = APIClient()
    # OrderDetail invalid id -> 404 via ValueError
    user = UserFactory()
    api.force_authenticate(user=user)
    r = api.get("/api/v1/orders/abc/")
    assert r.status_code == 404

    # OrderCancelView 404 for non-owner
    owner = UserFactory()
    other = UserFactory()
    order = Order.objects.create(user=owner)
    api.force_authenticate(user=other)
    r2 = api.post(f"/api/v1/orders/{order.id}/cancel/")
    assert r2.status_code == 404

    # OrderPaymentWebhookView logging exception during rejection
    settings.ORDERS_WEBHOOK_SECRET = ""
    settings.ORDERS_WEBHOOK_ALLOWED_IPS = ["1.2.3.4"]
    with patch("orders.views.logger.warning", side_effect=Exception("log fail")):
        resp = api.post(
            reverse("orders:order-webhook-payment"),
            data={"order_id": 1, "event": "payment_succeeded"},
            format="json",
            HTTP_X_FORWARDED_FOR="5.6.7.8",
        )
        assert resp.status_code == 403

    # OrderPaymentWebhookView invalid order id -> ValueError -> 404
    settings.ORDERS_WEBHOOK_ALLOWED_IPS = []
    settings.ORDERS_WEBHOOK_SECRET = ""
    resp2 = api.post(
        reverse("orders:order-webhook-payment"),
        data={"order_id": "foo", "event": "payment_succeeded"},
        format="json",
    )
    assert resp2.status_code == 404

    # OrderPaymentWebhookView handler ValueError when paying cancelled
    api.force_authenticate(user=owner)
    order2 = Order.objects.create(user=owner, status=Order.STATUS_CANCELLED)
    resp3 = api.post(
        reverse("orders:order-webhook-payment"),
        data={"order_id": order2.id, "event": "payment_succeeded"},
        format="json",
    )
    assert resp3.status_code == 400 and resp3.json()["detail"] == "Unable to update order."

    # OrderUpdateView 404 for non-owner
    api.force_authenticate(user=other)
    resp4 = api.patch(
        reverse("orders:order-update", kwargs={"order_id": order2.id}),
        data={"email": "x@example.com"},
        format="json",
    )
    assert resp4.status_code == 404
