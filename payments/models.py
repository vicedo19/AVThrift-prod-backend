"""Payment domain models.

Defines the PaymentIntent used to track Paystack transactions.
"""

from decimal import Decimal

from common.choices import Currency, PaymentIntentStatus, PaymentProvider
from common.models import TimeStampedModel
from django.core.validators import MinValueValidator
from django.db import models


class PaymentIntent(TimeStampedModel):
    """Tracks a payment attempt/lifecycle for an order via Paystack.

    Stores the provider reference, amount, and status and is used to
    deduplicate webhook events and coordinate order finalization.
    """

    STATUS_INITIALIZED = PaymentIntentStatus.INITIALIZED
    STATUS_PROCESSING = PaymentIntentStatus.PROCESSING
    STATUS_SUCCEEDED = PaymentIntentStatus.SUCCEEDED
    STATUS_FAILED = PaymentIntentStatus.FAILED
    STATUS_CANCELLED = PaymentIntentStatus.CANCELLED
    STATUS_CHOICES = PaymentIntentStatus.choices

    order = models.ForeignKey(
        "orders.Order",
        related_name="payment_intents",
        on_delete=models.CASCADE,
        db_index=True,
    )
    reference = models.CharField(max_length=64, unique=True, db_index=True)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    currency = models.CharField(
        max_length=8,
        choices=Currency.choices,
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_INITIALIZED, db_index=True)
    authorization_url = models.URLField(blank=True)
    access_code = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    webhook_event = models.JSONField(null=True, blank=True)
    provider = models.CharField(
        max_length=32,
        choices=PaymentProvider.choices,
        default=PaymentProvider.PAYSTACK,
    )

    class Meta:
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["order", "status", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gte=0), name="paymentintent_amount_non_negative"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"PaymentIntent#{self.id} order={self.order_id} ref={self.reference} status={self.status}"

    def save(self, *args, **kwargs):
        # Normalize to match choices and avoid inconsistent casing
        if self.currency:
            self.currency = self.currency.upper()
        if self.provider:
            self.provider = self.provider.lower()
        super().save(*args, **kwargs)
