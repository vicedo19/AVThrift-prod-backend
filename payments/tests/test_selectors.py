from datetime import timedelta
from decimal import Decimal

import pytest
from cart.tests.factories import UserFactory
from common.choices import Currency
from django.utils import timezone
from orders.models import Order
from payments.models import PaymentIntent
from payments.selectors import get_intent_by_reference, list_intents_for_order, list_recent_failed_intents


@pytest.mark.django_db
def test_get_intent_by_reference_returns_object_or_none():
    user = UserFactory()
    order = Order.objects.create(user=user, email=getattr(user, "email", None))
    intent = PaymentIntent.objects.create(
        order=order,
        reference="SEL-1",
        amount=Decimal("9.99"),
        currency=Currency.NGN,
    )

    assert get_intent_by_reference("SEL-1").id == intent.id
    assert get_intent_by_reference("missing-ref") is None
    assert get_intent_by_reference("") is None


@pytest.mark.django_db
def test_list_intents_for_order_filters_by_status():
    user = UserFactory()
    order = Order.objects.create(user=user, email=getattr(user, "email", None))
    other_order = Order.objects.create(user=user, email=getattr(user, "email", None))

    a = PaymentIntent.objects.create(order=order, reference="SEL-F-1", amount=Decimal("1.00"), currency=Currency.NGN)
    b = PaymentIntent.objects.create(order=order, reference="SEL-F-2", amount=Decimal("2.00"), currency=Currency.NGN)
    PaymentIntent.objects.create(order=other_order, reference="SEL-F-3", amount=Decimal("3.00"), currency=Currency.NGN)

    # mark one failed
    b.status = PaymentIntent.STATUS_FAILED
    b.save(update_fields=["status"])

    qs_all = list_intents_for_order(order_id=order.id)
    refs_all = {i.reference for i in qs_all}
    assert refs_all == {a.reference, b.reference}

    qs_failed = list_intents_for_order(order_id=order.id, status=PaymentIntent.STATUS_FAILED)
    refs_failed = [i.reference for i in qs_failed]
    assert refs_failed == [b.reference]


@pytest.mark.django_db
def test_list_recent_failed_intents_orders_by_created_at_and_limits():
    user = UserFactory()
    order = Order.objects.create(user=user, email=getattr(user, "email", None))

    now = timezone.now()
    i1 = PaymentIntent.objects.create(order=order, reference="FAIL-1", amount=Decimal("1.00"), currency=Currency.NGN)
    i2 = PaymentIntent.objects.create(order=order, reference="FAIL-2", amount=Decimal("2.00"), currency=Currency.NGN)
    i3 = PaymentIntent.objects.create(order=order, reference="FAIL-3", amount=Decimal("3.00"), currency=Currency.NGN)

    for i in (i1, i2, i3):
        i.status = PaymentIntent.STATUS_FAILED
        i.save(update_fields=["status"])

    # Stagger created_at to control ordering
    PaymentIntent.objects.filter(pk=i1.pk).update(created_at=now - timedelta(minutes=3))
    PaymentIntent.objects.filter(pk=i2.pk).update(created_at=now - timedelta(minutes=2))
    PaymentIntent.objects.filter(pk=i3.pk).update(created_at=now - timedelta(minutes=1))

    qs = list_recent_failed_intents(limit=2)
    refs = [i.reference for i in qs]
    # Expect most recent first, limited to 2
    assert refs == ["FAIL-3", "FAIL-2"]
