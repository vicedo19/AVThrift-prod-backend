"""Serializers for inventory domain.

Read-only serializers for stock items, movements, and reservations.
"""

from rest_framework import serializers

from .models import StockItem, StockMovement, StockReservation


class StockItemSerializer(serializers.ModelSerializer):
    """Read-only representation of stock for a variant.

    Exposes computed ``available`` and the variant SKU for convenience.
    """

    sku = serializers.CharField(source="variant.sku", read_only=True)
    available = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = StockItem
        fields = [
            "id",
            "variant",
            "sku",
            "quantity",
            "reserved",
            "available",
            "updated_at",
        ]
        read_only_fields = fields

    def get_available(self, obj) -> int:
        return int(obj.quantity) - int(obj.reserved)


class StockMovementSerializer(serializers.ModelSerializer):
    """Read-only representation of stock movements."""

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "stock_item",
            "movement_type",
            "quantity",
            "reason",
            "reference",
            "created_at",
        ]
        read_only_fields = fields


class StockReservationSerializer(serializers.ModelSerializer):
    """Read-only representation of stock reservations."""

    class Meta:
        model = StockReservation
        fields = [
            "id",
            "variant",
            "quantity",
            "reference",
            "state",
            "expires_at",
            "created_at",
        ]
        read_only_fields = fields


# EOF
