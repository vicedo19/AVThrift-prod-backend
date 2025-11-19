"""Payments API endpoints.

Includes healthcheck, Paystack transaction initialization, and webhook handling.
"""

import json
import logging
from decimal import Decimal

from common.choices import Currency
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, inline_serializer
from orders.models import Order
from orders.services import compute_request_hash, with_idempotency
from payments.models import PaymentIntent
from payments.selectors import get_intent_by_reference
from payments.serializers import PaymentIntentSerializer, PaymentIntentUpsertSerializer, PaystackInitializeSerializer
from payments.services import (
    create_or_update_intent,
    finalize_intent_and_order,
    initialize_paystack_transaction,
    validate_paystack_signature,
)
from rest_framework import serializers as rf_serializers
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

logger = logging.getLogger("avthrift.payments")


class PaymentsHealthView(APIView):
    """Basic health endpoint for the payments app."""

    permission_classes = [AllowAny]
    throttle_scope = "payments"

    @extend_schema(tags=["Payments Endpoints"], summary="Payments health")
    def get(self, request, *args, **kwargs):
        return Response({"status": "ok"})


class PaymentIntentCreateUpdateView(APIView):
    """Create or update a PaymentIntent by reference.

    Accepts order_id, reference, optional amount/currency/provider/metadata.
    Returns the upserted intent state with enums.
    """

    permission_classes = [IsAuthenticated]
    throttle_scope = "payments_write"
    throttle_classes = [ScopedRateThrottle]

    @extend_schema(
        tags=["Payments Endpoints"],
        summary="Create or update payment intent",
        description=(
            "Creates or updates a PaymentIntent identified by `reference`. If `amount` is omitted, "
            "the total is computed from the order's items. Currency and provider are enumerated."
        ),
        request=PaymentIntentUpsertSerializer,
        responses={
            200: PaymentIntentSerializer,
            400: inline_serializer(name="PaymentsError", fields={"detail": rf_serializers.CharField()}),
            404: inline_serializer(name="PaymentsNotFound", fields={"detail": rf_serializers.CharField()}),
        },
        examples=[
            OpenApiExample(
                "Create NGN intent",
                value={"order_id": 123, "reference": "ORD-123-paystack", "currency": "NGN"},
                request_only=True,
            ),
            OpenApiExample(
                "Update USD intent",
                value={"order_id": 123, "reference": "ORD-123-paystack", "currency": "USD", "amount": "49.99"},
                request_only=True,
            ),
        ],
    )
    def post(self, request, *args, **kwargs):
        s = PaymentIntentUpsertSerializer(data=request.data)
        if not s.is_valid():
            return Response({"detail": "Invalid payload"}, status=status.HTTP_400_BAD_REQUEST)
        body = s.validated_data

        order_id = body.get("order_id")
        try:
            order = Order.objects.get(id=int(order_id), user=request.user)
        except Order.DoesNotExist:
            return Response({"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

        # Amount: compute if missing
        raw_amount = body.get("amount")
        if raw_amount is None:
            total = Decimal("0.00")
            for item in order.items.all():
                total += (item.unit_price or Decimal("0.00")) * Decimal(int(item.quantity))
            amount = total
        else:
            amount = Decimal(str(raw_amount))

        reference = body.get("reference")
        currency = body.get("currency")
        provider = body.get("provider")
        metadata = body.get("metadata") or {"order_id": order.id, "user_id": request.user.id}

        intent = create_or_update_intent(
            order=order,
            reference=reference,
            amount=amount,
            currency=currency,
            provider=provider,
            metadata=metadata,
        )

        return Response(PaymentIntentSerializer(intent).data)


class PaymentIntentDetailView(APIView):
    """Fetch a PaymentIntent state by reference for the current user."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "payments"
    throttle_classes = [ScopedRateThrottle]

    @extend_schema(
        tags=["Payments Endpoints"],
        summary="Get payment intent by reference",
        responses={
            200: PaymentIntentSerializer,
            404: inline_serializer(name="PaymentsNotFound", fields={"detail": rf_serializers.CharField()}),
        },
    )
    def get(self, request, reference: str, *args, **kwargs):
        intent = get_intent_by_reference(reference)
        if not intent:
            return Response({"detail": "Intent not found"}, status=status.HTTP_404_NOT_FOUND)
        if intent.order.user_id != request.user.id:
            return Response({"detail": "Intent not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(PaymentIntentSerializer(intent).data)


class PaystackInitializeView(APIView):
    """Initialize a Paystack transaction for an order.

    Expects: {"order_id": int, "amount": str?}
    If amount is omitted, computes sum of line items.
    Returns authorization URL and reference.
    """

    permission_classes = [IsAuthenticated]
    throttle_scope = "payments_write"
    throttle_classes = [ScopedRateThrottle]

    @extend_schema(
        tags=["Payments Endpoints"],
        summary="Initialize Paystack transaction",
        description=(
            "Initializes a Paystack transaction for an order. If `amount` is omitted, "
            "the total is computed from the order's items. Currency defaults to NGN and "
            "must be one of the supported `Currency` enum values."
        ),
        parameters=[
            OpenApiParameter(
                name="Idempotency-Key",
                location=OpenApiParameter.HEADER,
                required=False,
                description="Makes the initialize request idempotent for this user+path+method",
                type=str,
            )
        ],
        request=PaystackInitializeSerializer,
        responses={
            200: inline_serializer(
                name="PaystackInitializeResponse",
                fields={
                    "authorization_url": rf_serializers.URLField(),
                    "reference": rf_serializers.CharField(),
                    "access_code": rf_serializers.CharField(),
                    "currency": rf_serializers.CharField(),
                },
            ),
            400: inline_serializer(name="PaymentsError", fields={"detail": rf_serializers.CharField()}),
        },
        examples=[
            OpenApiExample(
                "Initialize NGN",
                value={"order_id": 123, "currency": "NGN"},
                request_only=True,
            ),
            OpenApiExample(
                "Initialize USD",
                value={"order_id": 123, "currency": "USD", "amount": "49.99"},
                request_only=True,
            ),
        ],
    )
    def post(self, request, *args, **kwargs):
        idem_key = request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key")
        serializer = PaystackInitializeSerializer(data=request.data)
        if not serializer.is_valid():
            errs = serializer.errors or {}
            if "currency" in errs:
                logger.warning(
                    "payments_init_invalid_currency",
                    extra={"user_id": getattr(request.user, "id", None), "body_keys": list(request.data.keys())},
                )
                return Response({"detail": "Unsupported currency"}, status=status.HTTP_400_BAD_REQUEST)
            if "amount" in errs:
                logger.warning(
                    "payments_init_invalid_amount",
                    extra={"user_id": getattr(request.user, "id", None), "body_keys": list(request.data.keys())},
                )
                return Response({"detail": "Invalid amount"}, status=status.HTTP_400_BAD_REQUEST)
            if "order_id" in errs:
                logger.warning(
                    "payments_init_missing_order_id",
                    extra={"user_id": getattr(request.user, "id", None), "body_keys": list(request.data.keys())},
                )
                return Response({"detail": "order_id is required"}, status=status.HTTP_400_BAD_REQUEST)
            logger.warning(
                "payments_init_invalid_payload",
                extra={"user_id": getattr(request.user, "id", None), "errors": errs},
            )
            return Response({"detail": "Invalid payload"}, status=status.HTTP_400_BAD_REQUEST)
        body = serializer.validated_data
        order_id = body.get("order_id")
        try:
            order = Order.objects.get(id=int(order_id), user=request.user)
        except Order.DoesNotExist:
            logger.error(
                "payments_init_order_not_found",
                extra={"user_id": getattr(request.user, "id", None), "order_id": order_id},
            )
            return Response({"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

        # Compute amount if not provided
        raw_amount = body.get("amount")
        if raw_amount is None:
            total = Decimal("0.00")
            for item in order.items.all():
                total += (item.unit_price or Decimal("0.00")) * Decimal(int(item.quantity))
            amount = total
        else:
            amount = Decimal(str(raw_amount))

        # Ensure normalized uppercase
        currency = (body.get("currency") or Currency.NGN).upper()
        supported = getattr(settings, "PAYSTACK_SUPPORTED_CURRENCIES", None)
        if supported and currency not in set(supported):
            logger.warning(
                "payments_init_unsupported_currency",
                extra={"user_id": getattr(request.user, "id", None), "currency": currency},
            )
            return Response({"detail": "Unsupported currency"}, status=status.HTTP_400_BAD_REQUEST)

        # Stable reference per request; client can override but we generate sane default
        reference = body.get("reference") or f"{order.number or 'ORD'}-{order.id}-paystack"
        metadata = {"order_id": order.id, "user_id": request.user.id}

        def handler():
            # Initialize Paystack and persist intent
            intent, init_resp = initialize_paystack_transaction(
                order=order,
                amount=amount,
                customer_email=getattr(order, "email", None),
                reference=reference,
                metadata=metadata,
                currency=currency,
            )
            return (
                {
                    "authorization_url": intent.authorization_url,
                    "reference": intent.reference,
                    "access_code": intent.access_code,
                    "currency": intent.currency,
                },
                status.HTTP_200_OK,
            )

        # Idempotent init to avoid duplicating references
        request_hash = compute_request_hash(body)
        resp_body, code = with_idempotency(
            key=idem_key or reference,
            user=request.user,
            path=request.path,
            method=request.method,
            handler=handler,
            request_hash=request_hash,
        )
        logger.info(
            "payments_init_result",
            extra={
                "user_id": getattr(request.user, "id", None),
                "order_id": order.id,
                "reference": reference,
                "status_code": int(code),
                "idem_key_provided": bool(idem_key),
            },
        )
        return Response(resp_body, status=code)


@method_decorator(csrf_exempt, name="dispatch")
class PaystackWebhookView(APIView):
    """Handle Paystack webhook events.

    Validates signature and finalizes intent and order on charge.success.
    """

    permission_classes = [AllowAny]
    throttle_scope = "payments"
    throttle_classes = [ScopedRateThrottle]

    @extend_schema(
        tags=["Payments Endpoints"],
        summary="Paystack webhook handler",
        description="Validates signature and processes charge.success events idempotently.",
        request=inline_serializer(
            name="PaystackWebhookPayload",
            fields={
                "event": rf_serializers.CharField(),
                "data": rf_serializers.JSONField(),
            },
        ),
        responses={
            200: inline_serializer(
                name="WebhookProcessed",
                fields={"status": rf_serializers.CharField(), "order_id": rf_serializers.IntegerField(required=False)},
            ),
            401: inline_serializer(name="WebhookAuthError", fields={"detail": rf_serializers.CharField()}),
            404: inline_serializer(name="WebhookNotFound", fields={"detail": rf_serializers.CharField()}),
        },
    )
    def post(self, request, *args, **kwargs):
        raw = request.body or b""
        sig = request.headers.get("x-paystack-signature") or request.headers.get("x-paystack-signature")
        if not validate_paystack_signature(raw, sig or ""):
            logger.warning(
                "payments_webhook_invalid_signature",
                extra={"remote_addr": request.META.get("REMOTE_ADDR"), "path": request.path},
            )
            return Response({"detail": "Invalid signature"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            event = json.loads(raw.decode("utf-8"))
        except Exception:
            logger.warning(
                "payments_webhook_invalid_payload",
                extra={"remote_addr": request.META.get("REMOTE_ADDR"), "path": request.path},
            )
            return Response({"detail": "Invalid payload"}, status=status.HTTP_400_BAD_REQUEST)

        # Optional: IP whitelist for production hardening
        ips = getattr(settings, "PAYSTACK_WEBHOOK_IPS", [])
        remote_ip = request.META.get("REMOTE_ADDR")
        if ips and remote_ip not in ips:
            logger.warning(
                "payments_webhook_forbidden_ip",
                extra={"remote_addr": remote_ip, "allowed": ips},
            )
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        ref = (event.get("data") or {}).get("reference") or (event.get("data") or {}).get("reference_code") or ""
        if not ref:
            logger.warning(
                "payments_webhook_missing_reference",
                extra={"remote_addr": remote_ip, "path": request.path},
            )
            return Response({"detail": "Missing reference"}, status=status.HTTP_400_BAD_REQUEST)

        # Upsert intent for resilience; prefer existing
        intent = get_intent_by_reference(ref)
        if not intent:
            logger.warning(
                "payments_webhook_intent_not_found",
                extra={"reference": ref},
            )
            # If no intent, we cannot finalize safely without order context
            return Response({"detail": "Intent not found"}, status=status.HTTP_404_NOT_FOUND)

        # Idempotency: short-circuit if we have already processed this exact payload
        try:
            import hashlib

            payload_hash = hashlib.sha256(raw).hexdigest()
            meta = intent.metadata or {}
            if meta.get("last_webhook_hash") == payload_hash:
                logger.info("payments_webhook_ignored_duplicate", extra={"reference": ref})
                return Response({"status": "ignored"})
            meta["last_webhook_hash"] = payload_hash
            intent.metadata = meta
            intent.save(update_fields=["metadata", "updated_at"])
        except Exception:
            # Do not block processing on idempotency tracking failures
            pass

        # Charge success is primary signal for fulfillment
        if event.get("event") == "charge.success":
            logger.info("payments_webhook_charge_success", extra={"reference": ref, "order_id": intent.order_id})
            finalize_intent_and_order(intent=intent, event=event)
            return Response({"status": "processed", "order_id": intent.order_id})

        # Explicitly handle failed charges to reflect status
        if event.get("event") == "charge.failed":
            intent.webhook_event = event
            intent.status = PaymentIntent.STATUS_FAILED
            intent.save(update_fields=["webhook_event", "status", "updated_at"])
            logger.info("payments_webhook_charge_failed", extra={"reference": ref, "order_id": intent.order_id})
            return Response({"status": "processed"})

        # Ignore non-payment events for now
        logger.info("payments_webhook_ignored_event", extra={"event": event.get("event"), "reference": ref})
        return Response({"status": "ignored"})
