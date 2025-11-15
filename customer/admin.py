from django.contrib import admin

from .models import Address, Profile


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "name", "city", "state", "postal_code", "country_code")
    list_filter = ("state",)
    search_fields = ("name", "addr1", "city", "postal_code", "user__email", "user__username")
    ordering = ("-updated_at", "id")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "email_opt_in",
        "sms_opt_in",
        "default_shipping_address",
        "default_billing_address",
    )
    search_fields = ("user__email", "user__username")
    ordering = ("-updated_at", "id")
