"""Admin registration for cart models.

Provides admin interfaces for `Cart` and `CartItem`, with inline items on
the cart page for easier moderation and support.
"""

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django.contrib.auth import get_user_model
from inventory.services import MovementError

from .models import Cart, CartItem
from .services import (
    CartError,
    abandon_cart,
    abandon_cart_guest,
    clear_cart,
    clear_cart_guest,
    merge_guest_cart_to_user,
)


class CartMergeActionForm(ActionForm):
    """Extra inputs for admin actions.

    Provides a `user` field so support can merge a guest cart into a user.
    """

    user = forms.ModelChoiceField(
        queryset=get_user_model().objects.all(),
        required=False,
        label="Target user for merge (guest carts only)",
        help_text="Select when using 'Merge guest cart into user'.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Enable autocomplete widget for selecting target user in the action form
        try:
            from django.contrib.admin.widgets import AutocompleteSelect

            rel = Cart._meta.get_field("user").remote_field
            self.fields["user"].widget = AutocompleteSelect(rel, admin.site)
        except Exception:
            # Fallback silently to default widget if autocomplete cannot be initialized
            pass


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    fields = ("variant", "quantity", "unit_price", "reservation", "created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("variant", "reservation")


class OwnerTypeFilter(admin.SimpleListFilter):
    title = "owner type"
    parameter_name = "owner_type"

    def lookups(self, request, model_admin):
        return (
            ("user", "User carts"),
            ("guest", "Guest carts"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == "user":
            return queryset.filter(user__isnull=False)
        if value == "guest":
            return queryset.filter(user__isnull=True)
        return queryset


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session_id", "status", "updated_at", "created_at")
    list_filter = ("status", OwnerTypeFilter)
    search_fields = ("session_id", "user__username", "user__email")
    ordering = ("-updated_at",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [CartItemInline]
    # Use autocomplete for user selection on the change page
    autocomplete_fields = ("user",)
    list_select_related = ("user",)

    # Enable action extra form input
    action_form = CartMergeActionForm

    @admin.action(description="Clear cart (release reservations, keep status active)")
    def action_clear_cart(self, request, queryset):
        successes = 0
        failures = 0
        for cart in queryset:
            try:
                if cart.user_id:
                    clear_cart(user=cart.user)
                else:
                    clear_cart_guest(session_id=cart.session_id or "")
                successes += 1
            except (CartError, MovementError, Exception):
                failures += 1
        if successes:
            messages.success(request, f"Cleared {successes} cart(s).")
        if failures:
            messages.error(request, f"Failed to clear {failures} cart(s).")

    @admin.action(description="Abandon cart (release reservations, mark abandoned)")
    def action_abandon_cart(self, request, queryset):
        successes = 0
        failures = 0
        for cart in queryset:
            try:
                if cart.user_id:
                    abandon_cart(user=cart.user)
                else:
                    abandon_cart_guest(session_id=cart.session_id or "")
                successes += 1
            except (CartError, MovementError, Exception):
                failures += 1
        if successes:
            messages.success(request, f"Abandoned {successes} cart(s).")
        if failures:
            messages.error(request, f"Failed to abandon {failures} cart(s).")

    @admin.action(description="Merge guest cart into selected user")
    def action_merge_guest_cart_to_user(self, request, queryset):
        User = get_user_model()
        user_id = request.POST.get("user")
        if not user_id:
            messages.error(request, "Please select a target user in the action form.")
            return
        try:
            target_user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            messages.error(request, "Selected user not found.")
            return

        successes = 0
        skipped = 0
        failures = 0
        for cart in queryset:
            # Only applicable to guest carts
            if cart.user_id:
                skipped += 1
                continue
            try:
                merge_guest_cart_to_user(session_id=cart.session_id or "", user=target_user)
                successes += 1
            except (CartError, MovementError, Exception):
                failures += 1
        if successes:
            messages.success(
                request, f"Merged {successes} guest cart(s) into {target_user.email or target_user.username}."
            )
        if skipped:
            messages.info(request, f"Skipped {skipped} user-bound cart(s); merge applies to guest carts only.")
        if failures:
            messages.error(request, f"Failed to merge {failures} cart(s).")

    actions = [
        "action_clear_cart",
        "action_abandon_cart",
        "action_merge_guest_cart_to_user",
    ]


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "cart", "variant", "quantity", "unit_price", "reservation", "updated_at")
    search_fields = ("variant__sku", "cart__user__email", "cart__session_id")
    ordering = ("id",)
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("cart", "variant", "reservation")


# EOF
