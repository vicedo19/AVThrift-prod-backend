"""Serializers for the customer domain.

Expose Address and Profile data with clear contact resolution semantics.

Address.phone is an optional E.164 number used as a per-address override.
When not provided, downstream consumers should fall back to `users.User.phone`.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiExample, extend_schema_serializer
from rest_framework import serializers

from .models import Address, Profile

# Module metadata/exports
SERIALIZERS_MODULE = True
__all__ = ["AddressSerializer", "ProfileSerializer"]


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Address with phone override",
            value={
                "name": "John Doe",
                "addr1": "123 Main St",
                "addr2": "Apt 4",
                "city": "Lagos",
                "state": "Lagos",
                "postal_code": "123456",
                "country_code": "NG",
                "phone": "+2347012345678",
                "effective_contact_phone": "+2347012345678",
            },
            request_only=False,
            response_only=True,
        ),
        OpenApiExample(
            "Address without phone (falls back to user)",
            value={
                "name": "Jane Roe",
                "addr1": "456 Broad Ave",
                "city": "Abuja",
                "state": "FCT",
                "postal_code": "654321",
                "country_code": "NG",
                "phone": "",
                "effective_contact_phone": "+2348032222222",
            },
            request_only=False,
            response_only=True,
        ),
    ]
)
class AddressSerializer(serializers.ModelSerializer):
    """Serialize postal addresses with a computed contact phone.

    - `phone` is optional and validated as E.164 by the model.
    - `effective_contact_phone` is read-only, using precedence:
      Address.phone → User.phone → None.
    """

    effective_contact_phone = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Address
        fields = (
            "id",
            "name",
            "addr1",
            "addr2",
            "city",
            "state",
            "postal_code",
            "country_code",
            "phone",
            "effective_contact_phone",
        )
        read_only_fields = ("id", "effective_contact_phone")

    def get_effective_contact_phone(self, obj: Address) -> str | None:
        return obj.shipping_contact()

    def validate_phone(self, value: str | None) -> str | None:
        """Normalize whitespace for phone; model handles E.164 validation.

        Empty or whitespace-only values are treated as empty strings.
        """

        if value is None:
            return value
        value = value.strip()
        return value


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Profile with defaults",
            value={
                "id": 42,
                "email_opt_in": False,
                "sms_opt_in": False,
                "shipping_address": 10,
                "billing_address": 11,
                "shipping_contact": "+2348032222222",
            },
            request_only=False,
            response_only=True,
        )
    ]
)
class ProfileSerializer(serializers.ModelSerializer):
    """Serialize user profile preferences and defaults.

    Provides a read-only `shipping_contact` that reflects the same precedence
    for the default shipping address: Address.phone → User.phone → None.
    """

    # External API names: shipping_address/billing_address map to model defaults
    shipping_address = serializers.PrimaryKeyRelatedField(
        source="default_shipping_address",
        queryset=Address.objects.all(),
        allow_null=True,
        required=False,
    )
    billing_address = serializers.PrimaryKeyRelatedField(
        source="default_billing_address",
        queryset=Address.objects.all(),
        allow_null=True,
        required=False,
    )
    shipping_contact = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Profile
        fields = (
            "id",
            "email_opt_in",
            "sms_opt_in",
            "shipping_address",
            "billing_address",
            "shipping_contact",
        )
        read_only_fields = ("id", "shipping_contact")

    def get_shipping_contact(self, obj: Profile) -> str | None:
        return obj.default_shipping_contact


# EOF
