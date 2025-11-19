"""Admin configuration for payments models."""

from django.contrib import admin

from .models import PaymentIntent


@admin.register(PaymentIntent)
class PaymentIntentAdmin(admin.ModelAdmin):
    """Admin for managing payment intents."""

    list_display = (
        "id",
        "order_id",
        "provider",
        "reference",
        "amount",
        "currency",
        "status",
        "created_at",
        "updated_at",
    )
    list_filter = ("provider", "status", "currency", "created_at")
    search_fields = ("reference", "order__id", "order__number")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-id",)
