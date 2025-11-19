from decimal import Decimal

import pytest
from cart.tests.factories import UserFactory
from catalog.tests.factories import ProductVariantFactory
from common.choices import Currency, PaymentProvider
from django.urls import reverse
from orders.models import Order, OrderItem
from payments.models import PaymentIntent
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_upsert_creates_intent_and_computes_amount():
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

    url = reverse("payments:payment-intent-upsert")
    payload = {"order_id": order.id, "reference": "ORD-{}-PAY".format(order.id)}
    r = client.post(url, payload, format="json")

    assert r.status_code == 200
    body = r.json()
    assert body["reference"] == payload["reference"]
    intent = PaymentIntent.objects.get(reference=payload["reference"])
    assert intent.amount == Decimal("50.00")
    assert intent.currency == Currency.NGN
    assert intent.provider == PaymentProvider.PAYSTACK


@pytest.mark.django_db
def test_upsert_respects_explicit_amount():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)

    order = Order.objects.create(user=user, email=getattr(user, "email", None))

    url = reverse("payments:payment-intent-upsert")
    payload = {
        "order_id": order.id,
        "reference": "ORD-{}-PAY".format(order.id),
        "amount": "12.34",
        "currency": Currency.USD,
    }
    r = client.post(url, payload, format="json")

    assert r.status_code == 200
    intent = PaymentIntent.objects.get(reference=payload["reference"])
    assert intent.amount == Decimal("12.34")
    assert intent.currency == Currency.USD


@pytest.mark.django_db
def test_upsert_invalid_currency_choice():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)

    order = Order.objects.create(user=user, email=getattr(user, "email", None))

    url = reverse("payments:payment-intent-upsert")
    payload = {"order_id": order.id, "reference": "ORD-{}-PAY".format(order.id), "currency": "EUR"}
    r = client.post(url, payload, format="json")

    assert r.status_code == 400
    # View wraps serializer errors into a generic message
    assert r.json()["detail"] == "Invalid payload"


@pytest.mark.django_db
def test_upsert_invalid_provider_choice():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)

    order = Order.objects.create(user=user, email=getattr(user, "email", None))

    url = reverse("payments:payment-intent-upsert")
    payload = {
        "order_id": order.id,
        "reference": "ORD-{}-PAY".format(order.id),
        "provider": "stripe",  # unsupported provider
    }
    r = client.post(url, payload, format="json")

    assert r.status_code == 400
    assert r.json()["detail"] == "Invalid payload"


@pytest.mark.django_db
def test_upsert_order_not_owned_returns_404():
    # authenticated user tries to upsert intent for someone else's order
    owner = UserFactory()
    other_user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=other_user)

    order = Order.objects.create(user=owner, email=getattr(owner, "email", None))

    url = reverse("payments:payment-intent-upsert")
    payload = {"order_id": order.id, "reference": "ORD-{}-PAY".format(order.id)}
    r = client.post(url, payload, format="json")

    assert r.status_code == 404
    assert r.json()["detail"] == "Order not found"
