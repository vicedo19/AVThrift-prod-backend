"""Cart app models.

Defines shopping cart entities scoped to authenticated users for now.
Guest carts (session-based) can be added in a follow-up.
"""

from decimal import Decimal

from common.choices import CartStatus
from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base model adding created/updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Cart(TimeStampedModel):
    """Shopping cart bound to a user.

    Future support may include guest carts via `session_id`.
    """

    STATUS_ACTIVE = CartStatus.ACTIVE
    STATUS_ORDERED = CartStatus.ORDERED
    STATUS_ABANDONED = CartStatus.ABANDONED
    STATUS_CHOICES = CartStatus.choices

    # Either bound to a user (authenticated) or a guest session via session_id
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="carts", on_delete=models.CASCADE, null=True, blank=True
    )
    session_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["session_id", "status"]),
        ]
        constraints = [
            # Ensure one of user or session_id is set, but not both
            models.CheckConstraint(
                name="cart_user_xor_session",
                check=(
                    (models.Q(user__isnull=False) & models.Q(session_id__isnull=True))
                    | (models.Q(user__isnull=True) & models.Q(session_id__isnull=False))
                ),
            ),
            # Single active cart per user (Postgres honors partial uniques; MySQL will be handled via app logic)
            models.UniqueConstraint(
                fields=["user", "status"],
                condition=models.Q(status=CartStatus.ACTIVE),
                name="unique_active_cart_per_user",
            ),
            # Single active cart per session
            models.UniqueConstraint(
                fields=["session_id", "status"],
                condition=models.Q(status=CartStatus.ACTIVE),
                name="unique_active_cart_per_session",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        owner = self.user_id if self.user_id else self.session_id
        return f"Cart#{self.id} ({owner})"


class CartItem(TimeStampedModel):
    """Line item in a shopping cart for a product variant."""

    cart = models.ForeignKey(Cart, related_name="items", on_delete=models.CASCADE)
    variant = models.ForeignKey("catalog.ProductVariant", related_name="cart_items", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    reservation = models.ForeignKey(
        "inventory.StockReservation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cart_items",
    )

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["cart", "variant"], name="unique_variant_per_cart"),
            models.CheckConstraint(
                name="quantity_positive",
                check=models.Q(quantity__gte=1),
            ),
        ]
        indexes = [
            models.Index(fields=["cart", "variant"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"CartItem#{self.id} cart={self.cart_id} variant={self.variant_id} qty={self.quantity}"

    @property
    def line_total(self) -> Decimal:
        return (self.unit_price or Decimal("0.00")) * Decimal(int(self.quantity))
