"""Serializers for payments workflows.

Defines input validation for initializing Paystack transactions.
"""

from decimal import Decimal

from common.choices import Currency, PaymentProvider
from django.conf import settings
from rest_framework import serializers

from .models import PaymentIntent


class PaystackInitializeSerializer(serializers.Serializer):
    """Validate input for initializing a Paystack transaction.

    Fields:
    - order_id: required order identifier owned by the current user
    - amount: optional decimal; if omitted, computed from order items
    - currency: optional; defaults to NGN, validated against supported choices
    - reference: optional custom reference; sensible default applied in view
    """

    order_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    currency = serializers.CharField(required=False, default=Currency.NGN)
    reference = serializers.CharField(max_length=64, required=False, allow_blank=True)

    def validate_amount(self, value: Decimal) -> Decimal:
        if value < Decimal("0.00"):
            raise serializers.ValidationError("Amount must be non-negative")
        return value

    def validate_currency(self, value: str) -> str:
        # Normalize to uppercase and check optional supported list
        norm = (value or "").upper()
        supported = getattr(settings, "PAYSTACK_SUPPORTED_CURRENCIES", None)
        if supported and norm not in set(supported):
            raise serializers.ValidationError("Unsupported currency")
        return norm


class PaymentIntentUpsertSerializer(serializers.Serializer):
    """Create or update a PaymentIntent by reference with enums."""

    order_id = serializers.IntegerField(required=True)
    reference = serializers.CharField(required=True, max_length=64)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    currency = serializers.ChoiceField(choices=Currency.choices, default=Currency.NGN)
    provider = serializers.ChoiceField(choices=PaymentProvider.choices, default=PaymentProvider.PAYSTACK)
    metadata = serializers.DictField(required=False)

    def validate_amount(self, value):
        if value is None:
            return value
        if value < Decimal("0.00"):
            raise serializers.ValidationError("Amount must be non-negative")
        return value


class PaymentIntentSerializer(serializers.ModelSerializer):
    """Read serializer exposing intent state and enums."""

    order_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = PaymentIntent
        fields = (
            "reference",
            "order_id",
            "provider",
            "amount",
            "currency",
            "status",
            "authorization_url",
            "access_code",
            "metadata",
            "created_at",
            "updated_at",
        )
