"""Inventory models (single-location, focused).

Tracks stock at the SKU (variant) or product level without warehouses.
"""

from common.choices import MovementType, ReservationState
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class StockItem(TimeStampedModel):
    # SKU-centric stock: track by variant only
    variant = models.ForeignKey("catalog.ProductVariant", null=True, blank=True, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=0)
    reserved = models.IntegerField(default=0)

    class Meta:
        ordering = ["-updated_at", "id"]
        constraints = [
            models.CheckConstraint(name="stock_non_negative", check=models.Q(quantity__gte=0)),
            models.CheckConstraint(name="reserved_non_negative", check=models.Q(reserved__gte=0)),
            models.CheckConstraint(
                name="reserved_le_quantity",
                check=models.Q(reserved__lte=models.F("quantity")),
            ),
            models.UniqueConstraint(fields=["variant"], name="unique_stockitem_per_variant"),
            models.CheckConstraint(name="stockitem_variant_not_null", check=models.Q(variant__isnull=False)),
        ]
        indexes = [
            models.Index(fields=["variant"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        target = self.variant_id or "-"
        return f"StockItem<{target}> q={self.quantity} r={self.reserved}"


class StockMovement(TimeStampedModel):
    TYPE_INBOUND = MovementType.INBOUND
    TYPE_OUTBOUND = MovementType.OUTBOUND
    TYPE_ADJUST = MovementType.ADJUST
    TYPE_CHOICES = MovementType.choices

    stock_item = models.ForeignKey(StockItem, on_delete=models.CASCADE, related_name="movements")
    movement_type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    quantity = models.IntegerField()  # signed: +inbound, -outbound
    reason = models.CharField(max_length=200, blank=True)
    reference = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(name="movement_non_zero", check=~models.Q(quantity=0)),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.movement_type} {self.quantity} for {self.stock_item_id}"


class StockReservation(TimeStampedModel):
    STATE_ACTIVE = ReservationState.ACTIVE
    STATE_RELEASED = ReservationState.RELEASED
    STATE_CONVERTED = ReservationState.CONVERTED
    STATE_CHOICES = ReservationState.choices

    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.CASCADE)
    quantity = models.IntegerField()
    reference = models.CharField(max_length=120)
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default=STATE_ACTIVE)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(name="reservation_positive_qty", check=models.Q(quantity__gt=0)),
        ]
        indexes = [
            models.Index(fields=["variant"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["reference"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"Reservation<{self.variant_id}> qty={self.quantity} state={self.state}"


# EOF
