from decimal import Decimal

import pytest
from cart.tests.factories import UserFactory
from common.choices import Currency
from django.urls import reverse
from orders.models import Order
from payments.models import PaymentIntent
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_intent_detail_owner_can_access():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)

    order = Order.objects.create(user=user, email=getattr(user, "email", None))
    intent = PaymentIntent.objects.create(
        order=order,
        reference="REF-OWN-1",
        amount=Decimal("10.00"),
        currency=Currency.NGN,
    )

    url = reverse("payments:payment-intent-detail", kwargs={"reference": intent.reference})
    r = client.get(url)

    assert r.status_code == 200
    body = r.json()
    assert body["reference"] == intent.reference
    assert body["order_id"] == order.id


@pytest.mark.django_db
def test_intent_detail_other_user_gets_404():
    owner = UserFactory()
    other = UserFactory()
    client = APIClient()
    client.force_authenticate(user=other)

    order = Order.objects.create(user=owner, email=getattr(owner, "email", None))
    intent = PaymentIntent.objects.create(
        order=order,
        reference="REF-OWN-2",
        amount=Decimal("5.00"),
        currency=Currency.NGN,
    )

    url = reverse("payments:payment-intent-detail", kwargs={"reference": intent.reference})
    r = client.get(url)

    assert r.status_code == 404
    assert r.json()["detail"] == "Intent not found"


@pytest.mark.django_db
def test_intent_detail_unauthenticated_gets_401():
    owner = UserFactory()
    order = Order.objects.create(user=owner, email=getattr(owner, "email", None))
    intent = PaymentIntent.objects.create(
        order=order,
        reference="REF-OWN-3",
        amount=Decimal("7.00"),
        currency=Currency.NGN,
    )

    client = APIClient()  # no auth
    url = reverse("payments:payment-intent-detail", kwargs={"reference": intent.reference})
    r = client.get(url)

    assert r.status_code in (401, 403)
    # DRF typically returns 401 for IsAuthenticated without credentials
