from decimal import Decimal

import pytest
from cart.tests.factories import UserFactory
from catalog.tests.factories import ProductVariantFactory
from django.urls import reverse
from orders.models import Order, OrderItem
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_initialize_idempotency_conflict_returns_409(monkeypatch, settings):
    settings.PAYSTACK_SECRET_KEY = "sk_test_xxx"
    settings.PAYSTACK_BASE_URL = "https://api.paystack.co"
    settings.PAYSTACK_CURRENCY = "NGN"

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

    url = reverse("payments:paystack-initialize")
    idem_key = "idem-conflict-1"
    # First call with NGN, amount omitted -> computes from order
    r1 = client.post(url, {"order_id": order.id, "currency": "NGN"}, format="json", HTTP_IDEMPOTENCY_KEY=idem_key)
    assert r1.status_code == 200

    # Second call reusing same key but different payload hash via reference field
    r2 = client.post(
        url,
        {"order_id": order.id, "currency": "NGN", "reference": "DIFF-REF"},
        format="json",
        HTTP_IDEMPOTENCY_KEY=idem_key,
    )
    assert r2.status_code == 409
    assert r2.json()["detail"].startswith("Idempotency key reused")
