"""DRF serializers for Orders.

Separates API representation from data model by computing financial totals
as read-only serializer fields, rather than exposing denormalized DB columns.
"""

from decimal import Decimal

from rest_framework import serializers

from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    """API representation of an order line item with computed line_total."""

    line_total = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "variant",
            "product_title",
            "variant_sku",
            "quantity",
            "unit_price",
            "line_total",
        ]
        read_only_fields = ["id", "line_total"]

    def get_line_total(self, obj: OrderItem) -> Decimal:
        return (obj.unit_price or Decimal("0.00")) * Decimal(int(obj.quantity))


class OrderSerializer(serializers.ModelSerializer):
    """API representation for an order.

    Totals are computed on the fly for API responses to decouple from the
    denormalized DB columns.
    """

    items = OrderItemSerializer(many=True, read_only=True)
    subtotal = serializers.SerializerMethodField(read_only=True)
    tax = serializers.SerializerMethodField(read_only=True)
    shipping = serializers.SerializerMethodField(read_only=True)
    discount = serializers.SerializerMethodField(read_only=True)
    total = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "number",
            "status",
            "email",
            "created_at",
            "items",
            "subtotal",
            "tax",
            "shipping",
            "discount",
            "total",
        ]
        read_only_fields = ["id", "created_at", "subtotal", "tax", "shipping", "discount", "total"]

    def get_subtotal(self, obj: Order) -> Decimal:
        subtotal = Decimal("0.00")
        for item in obj.items.all():
            unit_price = item.unit_price or Decimal("0.00")
            subtotal += unit_price * Decimal(int(item.quantity))
        return subtotal

    def get_total(self, obj: Order) -> Decimal:
        subtotal = self.get_subtotal(obj)
        return subtotal + self.get_tax(obj) + self.get_shipping(obj) - self.get_discount(obj)

    def get_tax(self, obj: Order) -> Decimal:
        return self._pricing_value("tax")

    def get_shipping(self, obj: Order) -> Decimal:
        return self._pricing_value("shipping")

    def get_discount(self, obj: Order) -> Decimal:
        return self._pricing_value("discount")

    def _pricing_value(self, name: str) -> Decimal:
        """Return pricing input from context or initial data.

        Looks in `self.context['pricing']` or `self.context['pricing_overrides']`
        for a dict of values. Falls back to `self.initial_data` when present, and
        finally to Decimal("0.00"). Values are not persisted; they affect API
        representation only.
        """
        default = Decimal("0.00")
        ctx = self.context.get("pricing") or self.context.get("pricing_overrides")
        if isinstance(ctx, dict) and name in ctx:
            try:
                return Decimal(str(ctx[name]))
            except Exception:
                return default
        if hasattr(self, "initial_data") and isinstance(self.initial_data, dict) and name in self.initial_data:
            try:
                return Decimal(str(self.initial_data[name]))
            except Exception:
                return default
        return default
