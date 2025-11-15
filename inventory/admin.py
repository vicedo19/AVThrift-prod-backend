"""Admin registrations for inventory app."""

from django.contrib import admin

from .models import StockItem, StockMovement, StockReservation


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = ("id", "variant", "quantity", "reserved", "updated_at")
    search_fields = ("variant__sku",)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("id", "stock_item", "movement_type", "quantity", "reason", "reference", "created_at")
    list_filter = ("movement_type",)
    search_fields = ("stock_item__variant__sku", "reference")


@admin.register(StockReservation)
class StockReservationAdmin(admin.ModelAdmin):
    list_display = ("id", "variant", "quantity", "state", "reference", "expires_at", "created_at")
    list_filter = ("state",)
    search_fields = ("variant__sku", "reference")


# EOF
