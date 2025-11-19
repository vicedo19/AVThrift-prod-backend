from django.contrib import admin

from .models import IdempotencyKey, Order, OrderItem, OrderStatusEvent


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "number", "status", "user", "email", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("number", "email")
    date_hierarchy = "created_at"


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "variant", "quantity", "unit_price")
    list_filter = ("order",)
    search_fields = ("variant__sku", "product_title")


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ("id", "key", "scope", "path", "method", "response_code", "created_at")
    list_filter = ("method", "response_code", "created_at")
    search_fields = ("key", "scope", "path")
    date_hierarchy = "created_at"


@admin.register(OrderStatusEvent)
class OrderStatusEventAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "from_status", "to_status", "reason", "created_at")
    list_filter = ("from_status", "to_status", "created_at")
    search_fields = ("order__number", "reason")
    date_hierarchy = "created_at"
