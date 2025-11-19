"""Cart serializers for read and write operations."""

from rest_framework import serializers

from .models import CartItem
from .selectors import cart_totals
from .services import add_item, add_item_guest, update_item_quantity, update_item_quantity_guest


class CartItemReadSerializer(serializers.ModelSerializer):
    """Read serializer for a cart item."""

    variant_id = serializers.IntegerField(source="variant.id")
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = [
            "id",
            "variant_id",
            "quantity",
            "unit_price",
            "line_total",
        ]


class CartReadSerializer(serializers.Serializer):
    """Read serializer for the cart summary and items."""

    id = serializers.IntegerField()
    items = CartItemReadSerializer(many=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    total = serializers.DecimalField(max_digits=12, decimal_places=2)

    @classmethod
    def from_cart(cls, *, cart):
        totals = cart_totals(cart=cart)
        return cls(
            {
                "id": cart.id,
                "items": list(cart.items.select_related("variant").all()),
                "subtotal": totals["subtotal"],
                "total": totals["total"],
            }
        )


class AddItemSerializer(serializers.Serializer):
    """Write serializer for adding an item to the cart."""

    variant_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)

    def create(self, validated_data):  # type: ignore[override]
        user = self.context["request"].user
        item = add_item(user=user, **validated_data)
        return item


class UpdateItemQuantitySerializer(serializers.Serializer):
    """Write serializer for updating a cart item quantity."""

    quantity = serializers.IntegerField(min_value=1)

    def update(self, instance, validated_data):  # type: ignore[override]
        user = self.context["request"].user
        item = update_item_quantity(user=user, item_id=instance.id, quantity=validated_data["quantity"])
        return item


class AddItemGuestSerializer(serializers.Serializer):
    """Write serializer for adding an item to a guest cart."""

    session_id = serializers.CharField(max_length=64)
    variant_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)

    def create(self, validated_data):  # type: ignore[override]
        session_id = validated_data.pop("session_id")
        item = add_item_guest(session_id=session_id, **validated_data)
        return item


class UpdateItemQuantityGuestSerializer(serializers.Serializer):
    """Write serializer for updating a guest cart item quantity."""

    session_id = serializers.CharField(max_length=64)
    quantity = serializers.IntegerField(min_value=1)

    def update(self, instance, validated_data):  # type: ignore[override]
        session_id = validated_data["session_id"]
        item = update_item_quantity_guest(
            session_id=session_id, item_id=instance.id, quantity=validated_data["quantity"]
        )
        return item
