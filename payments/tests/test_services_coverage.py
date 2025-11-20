from decimal import Decimal
from unittest.mock import patch

import pytest
from cart.tests.factories import UserFactory
from catalog.tests.factories import ProductVariantFactory
from orders.models import Order
from payments.models import PaymentIntent
from payments.services import (
    _to_minor_units,
    finalize_intent_and_order,
    initialize_paystack_transaction,
    validate_paystack_signature,
)

pytestmark = pytest.mark.django_db


def make_order():
    user = UserFactory()
    order = Order.objects.create(user=user, email=user.email)
    ProductVariantFactory(price=Decimal("25.00"))
    return order


def test_to_minor_units_maps_and_defaults():
    assert _to_minor_units(Decimal("12.34"), "NGN") == 1234
    assert _to_minor_units(Decimal("1"), "USD") == 100
    assert _to_minor_units(Decimal("2"), "XYZ") == 200
    assert _to_minor_units(None, "NGN") == 0


def test_initialize_paystack_transaction_success(settings):
    settings.PAYSTACK_SECRET_KEY = "sk"
    settings.PAYSTACK_BASE_URL = "https://api.paystack.co"
    order = make_order()

    class Resp:
        status_code = 200

        def json(self):
            return {
                "status": True,
                "data": {"authorization_url": "auth", "access_code": "code"},
            }

    with patch("payments.services.httpx.post", return_value=Resp()):
        intent, data = initialize_paystack_transaction(
            order=order,
            amount=Decimal("10.00"),
            customer_email=order.email,
            reference="ref-1",
            metadata={"a": 1},
            currency="ngn",
        )
        assert intent.reference == "ref-1" and intent.authorization_url == "auth"
        assert data["status"] is True


def test_initialize_paystack_transaction_failure(settings):
    settings.PAYSTACK_SECRET_KEY = "sk"
    order = make_order()

    class RespBad:
        status_code = 500

        def json(self):
            return {"status": False}

    with patch("payments.services.httpx.post", return_value=RespBad()):
        with pytest.raises(ValueError):
            initialize_paystack_transaction(
                order=order,
                amount=Decimal("10.00"),
                customer_email=order.email,
                reference="ref-2",
                metadata=None,
            )


def test_validate_paystack_signature_true_false(settings):
    settings.PAYSTACK_SECRET_KEY = "secret"
    body = b"{}"
    import hashlib
    import hmac

    sig = hmac.new(b"secret", body, hashlib.sha512).hexdigest()
    assert validate_paystack_signature(body, sig) is True
    assert validate_paystack_signature(body, "bad") is False
    assert validate_paystack_signature(body, "") is False


def test_finalize_intent_paths(settings):
    settings.PAYSTACK_SECRET_KEY = "sk"
    order = make_order()
    intent = PaymentIntent.objects.create(
        order=order,
        reference="r1",
        amount=Decimal("10.00"),
        currency="NGN",
        status=PaymentIntent.STATUS_INITIALIZED,
    )

    # amount mismatch -> failed
    event_bad = {"data": {"amount": _to_minor_units(Decimal("9.00"), "NGN")}}
    finalize_intent_and_order(intent=intent, event=event_bad)
    intent.refresh_from_db()
    assert intent.status == PaymentIntent.STATUS_FAILED

    # already succeeded -> return
    intent.status = PaymentIntent.STATUS_SUCCEEDED
    intent.save(update_fields=["status"])
    finalize_intent_and_order(intent=intent, event={"data": {"amount": 1000}})

    # reset and success path
    intent.status = PaymentIntent.STATUS_INITIALIZED
    intent.save(update_fields=["status"])
    event_ok = {"data": {"amount": _to_minor_units(intent.amount, intent.currency)}}
    with patch("payments.services.pay_order", side_effect=Exception("boom")):
        finalize_intent_and_order(intent=intent, event=event_ok)
    intent.refresh_from_db()
    assert intent.status == PaymentIntent.STATUS_SUCCEEDED
