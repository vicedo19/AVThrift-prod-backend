from decimal import Decimal

from common.choices import OrderStatus
from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base model adding created/updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Order(TimeStampedModel):
    """Purchase order capturing a snapshot of a user's checkout.

    Totals are denormalized to support reporting and auditability.
    """

    STATUS_PENDING = OrderStatus.PENDING
    STATUS_PAID = OrderStatus.PAID
    STATUS_CANCELLED = OrderStatus.CANCELLED
    STATUS_CHOICES = OrderStatus.choices

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="orders", on_delete=models.CASCADE)
    number = models.CharField(max_length=32, unique=True, null=True, blank=True, db_index=True)
    email = models.EmailField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)

    class Meta:
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["user", "status", "created_at"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"Order#{self.id} user={self.user_id} status={self.status}"


class OrderItem(TimeStampedModel):
    """Line item within an order.

    Snapshots core product info for auditability (title, SKU, unit price).
    """

    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    variant = models.ForeignKey("catalog.ProductVariant", related_name="order_items", on_delete=models.PROTECT)
    product_title = models.CharField(max_length=200, blank=True)
    variant_sku = models.CharField(max_length=64, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["order", "variant"]),
        ]
        constraints = [
            models.CheckConstraint(name="orderitem_price_non_negative", check=models.Q(unit_price__gte=0)),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"OrderItem#{self.id} order={self.order_id} variant={self.variant_id} qty={self.quantity}"

    @property
    def line_total(self) -> Decimal:
        return (self.unit_price or Decimal("0.00")) * Decimal(int(self.quantity))


class IdempotencyKey(TimeStampedModel):
    """Stores idempotent request results to prevent duplicate processing."""

    key = models.CharField(max_length=128)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE)
    scope = models.CharField(max_length=128)
    path = models.CharField(max_length=255)
    method = models.CharField(max_length=16)
    request_hash = models.CharField(max_length=64, null=True, blank=True)
    response_code = models.IntegerField(null=True, blank=True)
    response_json = models.JSONField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["key", "scope", "path", "method"], name="uniq_idem_scope_path_method"),
        ]
