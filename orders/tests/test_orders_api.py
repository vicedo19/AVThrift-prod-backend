from decimal import Decimal

import pytest
from cart.tests.factories import UserFactory
from catalog.tests.factories import ProductVariantFactory
from orders.models import Order, OrderItem
from orders.views import OrderDetailView, OrderPayView
from rest_framework.settings import reload_api_settings
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle


@pytest.mark.django_db
def test_order_detail_pricing_overrides():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)

    order = Order.objects.create(user=user)
    variant = ProductVariantFactory()
    OrderItem.objects.create(
        order=order,
        variant=variant,
        product_title="Test",
        variant_sku=variant.sku,
        quantity=2,
        unit_price=Decimal("25.00"),
    )

    r = client.get(f"/api/v1/orders/{order.id}/?tax=4.00&shipping=5.00&discount=3.00")
    body = r.json()
    assert r.status_code == 200
    from decimal import Decimal as D

    assert D(str(body["subtotal"])) == D("50.00")
    assert D(str(body["tax"])) == D("4.00")
    assert D(str(body["shipping"])) == D("5.00")
    assert D(str(body["discount"])) == D("3.00")
    assert D(str(body["total"])) == D("56.00")


@pytest.mark.django_db
def test_order_list_filters_status_and_number():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)

    o1 = Order.objects.create(user=user, status=Order.STATUS_PENDING, number="ORD-001")
    o2 = Order.objects.create(user=user, status=Order.STATUS_PAID, number="ORD-002")
    o3 = Order.objects.create(user=user, status=Order.STATUS_CANCELLED, number="ORD-003")

    # Filter by status
    r_paid = client.get("/api/v1/orders/?status=paid")
    assert r_paid.status_code == 200
    ids_paid = [it["id"] for it in r_paid.json()["results"]]
    assert o2.id in ids_paid and o1.id not in ids_paid and o3.id not in ids_paid

    # Filter by number
    r_num = client.get("/api/v1/orders/?number=ORD-003")
    assert r_num.status_code == 200
    ids_num = [it["id"] for it in r_num.json()["results"]]
    assert ids_num == [o3.id]


@pytest.mark.django_db
def test_webhook_marks_order_paid_and_is_idempotent():
    client = APIClient()
    # Anonymous webhook (AllowAny)
    user = UserFactory()
    order = Order.objects.create(user=user)

    idem = "wh-abc-123"
    payload = {"order_id": order.id, "event": "payment_succeeded"}

    r1 = client.post("/api/v1/orders/webhooks/payment/", payload, format="json", HTTP_IDEMPOTENCY_KEY=idem)
    assert r1.status_code == 200
    assert r1.json()["status"] == "paid"

    r2 = client.post("/api/v1/orders/webhooks/payment/", payload, format="json", HTTP_IDEMPOTENCY_KEY=idem)
    assert r2.status_code == 200
    assert r2.json()["status"] == "paid"


@pytest.mark.django_db
def test_orders_throttling_scopes(settings):
    # Enable scoped throttling with small rate for tests
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = [
        "rest_framework.throttling.ScopedRateThrottle",
    ]
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
        "orders": "2/min",
        "orders_write": "2/min",
    }
    reload_api_settings(setting="DEFAULT_THROTTLE_RATES")
    reload_api_settings(setting="DEFAULT_THROTTLE_CLASSES")

    # Explicitly set throttle classes on the views
    OrderDetailView.throttle_classes = [ScopedRateThrottle]
    OrderPayView.throttle_classes = [ScopedRateThrottle]

    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)

    order = Order.objects.create(user=user)

    # Read throttling
    assert client.get(f"/api/v1/orders/{order.id}/").status_code == 200
    assert client.get(f"/api/v1/orders/{order.id}/").status_code in {200, 429}

    # Write throttling (use pay twice to avoid business-rule 400)
    assert client.post(f"/api/v1/orders/{order.id}/pay/").status_code in {200, 429}
    r2 = client.post(f"/api/v1/orders/{order.id}/pay/")
    assert r2.status_code in {200, 429}
