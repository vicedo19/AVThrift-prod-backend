"""Business logic for payments.

Implements Paystack initialization, verification, signature validation,
and order finalization logic coordinated via PaymentIntent.
"""

import hashlib
import hmac
import logging
from decimal import Decimal
from typing import Dict, Optional, Tuple

import httpx
from common.choices import Currency, PaymentProvider
from django.conf import settings
from orders.services import pay_order
from payments.models import PaymentIntent

# Use a dedicated payments logger to align with production logging config
logger = logging.getLogger("avthrift.payments")

try:  # Optional Sentry capture for critical errors
    import sentry_sdk  # type: ignore
except Exception:  # pragma: no cover
    sentry_sdk = None  # type: ignore


def _to_minor_units(amount: Decimal, currency: str) -> int:
    """Convert a decimal amount in major units to minor units (integer).

    Uses 100 as default multiplier; NGN/GHS/USD all use 100. Adjust here if
    supporting zero-decimal or different subunit currencies later.
    """

    if amount is None:
        return 0
    # Use Currency enums to drive mapping to avoid free-form strings
    code = (currency or Currency.NGN).upper()
    multipliers = {Currency.NGN: 100, Currency.GHS: 100, Currency.USD: 100}
    m = multipliers.get(code, 100)
    return int(Decimal(amount) * Decimal(m))


def create_or_update_intent(
    *,
    order,
    reference: str,
    amount: Decimal,
    currency: str,
    provider: Optional[str] = None,
    authorization_url: Optional[str] = None,
    access_code: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> PaymentIntent:
    """Create or update a PaymentIntent for the given order and reference."""

    intent, _created = PaymentIntent.objects.update_or_create(
        reference=reference,
        defaults={
            "order": order,
            "amount": amount,
            "currency": currency,
            "provider": (provider or PaymentProvider.PAYSTACK),
            "authorization_url": authorization_url or "",
            "access_code": access_code or "",
            "status": PaymentIntent.STATUS_INITIALIZED,
            "metadata": metadata or {},
        },
    )
    return intent


def initialize_paystack_transaction(
    *,
    order,
    amount: Decimal,
    customer_email: Optional[str] = None,
    reference: str,
    metadata: Optional[dict] = None,
    currency: Optional[str] = None,
) -> Tuple[PaymentIntent, Dict]:
    """Initialize a Paystack transaction and persist PaymentIntent.

    Returns the intent and Paystack's response body.
    """

    base_url = getattr(settings, "PAYSTACK_BASE_URL", "https://api.paystack.co")
    url = f"{base_url}/transaction/initialize"
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}", "Content-Type": "application/json"}
    txn_currency = (currency or Currency.NGN).upper()
    payload = {
        "email": customer_email or order.email,
        "amount": _to_minor_units(amount, txn_currency),
        "currency": txn_currency,
        "reference": reference,
        "metadata": metadata or {},
    }

    r = httpx.post(url, headers=headers, json=payload, timeout=15)
    data = r.json()
    if r.status_code != 200 or not data.get("status"):
        logger.error(
            "paystack_initialize_failed",
            extra={
                "code": r.status_code,
                "path": url,
                "order_id": getattr(order, "id", None),
                "reference": reference,
                "currency": txn_currency,
            },
        )
        if sentry_sdk:
            try:
                sentry_sdk.capture_message("paystack_initialize_failed", level="error")
            except Exception:
                pass
        raise ValueError("Failed to initialize Paystack transaction")

    auth_url = data.get("data", {}).get("authorization_url", "")
    access_code = data.get("data", {}).get("access_code", "")

    intent = create_or_update_intent(
        order=order,
        reference=reference,
        amount=amount,
        currency=txn_currency,
        authorization_url=auth_url,
        access_code=access_code,
        metadata=metadata,
    )
    return intent, data


def verify_paystack_transaction(*, reference: str) -> Dict:
    """Verify a Paystack transaction by reference via API."""

    base_url = getattr(settings, "PAYSTACK_BASE_URL", "https://api.paystack.co")
    url = f"{base_url}/transaction/verify/{reference}"
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    r = httpx.get(url, headers=headers, timeout=15)
    return r.json()


def validate_paystack_signature(raw_body: bytes, signature: str) -> bool:
    """Validate webhook signature using Paystack secret key (HMAC SHA512)."""

    if not signature:
        return False
    secret = settings.PAYSTACK_SECRET_KEY.encode("utf-8")
    digest = hmac.new(secret, msg=raw_body, digestmod=hashlib.sha512).hexdigest()
    return hmac.compare_digest(signature, digest)


def finalize_intent_and_order(*, intent: PaymentIntent, event: Dict) -> None:
    """Mark intent as succeeded and pay the order if amounts match.

    Guard against double fulfillment by checking current status.
    """

    if intent.status == PaymentIntent.STATUS_SUCCEEDED:
        return

    # Optional: validate that webhook amount matches our expected amount
    try:
        amount_kobo = int(event.get("data", {}).get("amount", 0))
    except Exception:
        amount_kobo = 0
    expected_kobo = _to_minor_units(intent.amount, intent.currency)
    if amount_kobo and expected_kobo and amount_kobo != expected_kobo:
        logger.error(
            "paystack_amount_mismatch",
            extra={
                "reference": intent.reference,
                "expected_kobo": expected_kobo,
                "actual_kobo": amount_kobo,
                "order_id": intent.order_id,
            },
        )
        if sentry_sdk:
            try:
                sentry_sdk.capture_message("paystack_amount_mismatch", level="warning")
            except Exception:
                pass
        # Persist webhook for audit, but do not mark success
        intent.webhook_event = event
        intent.status = PaymentIntent.STATUS_FAILED
        intent.save(update_fields=["webhook_event", "status", "updated_at"])
        return

    intent.webhook_event = event
    intent.status = PaymentIntent.STATUS_SUCCEEDED
    intent.save(update_fields=["webhook_event", "status", "updated_at"])

    try:
        pay_order(intent.order)
    except Exception as e:
        # Never let order mutation exception interrupt webhook handling
        logger.exception("paystack_finalize_order_failed", extra={"order_id": intent.order_id})
        if sentry_sdk:
            try:
                sentry_sdk.capture_exception(e)
            except Exception:
                pass
