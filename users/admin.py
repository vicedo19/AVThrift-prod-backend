"""Admin registration for the custom User model.

Uses Django's built-in `UserAdmin` to manage the `users.User` model
in the admin interface.
"""

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User
from .services import send_email_verification


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration leveraging the default fieldsets and filters.

    Adds email verification and pending email fields, improves list display,
    search, filters, and ordering for better moderation and management.
    """

    list_display = (
        "username",
        "email",
        "email_verified",
        "is_staff",
        "is_active",
        "last_login",
        "date_joined",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "email_verified", "groups")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("-date_joined",)
    readonly_fields = ("last_login", "date_joined")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            "Personal info",
            {"fields": ("first_name", "last_name", "email", "email_verified", "pending_email")},
        ),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "password1", "password2"),
            },
        ),
    )

    filter_horizontal = ("groups", "user_permissions")

    actions = ["send_verification_email"]

    def send_verification_email(self, request, queryset):
        """Admin action to send email verification to selected users.

        Skips users without an email or those already verified.
        """
        sent = 0
        skipped = 0
        for user in queryset:
            email = (user.email or "").strip()
            if not email or user.email_verified:
                skipped += 1
                continue
            try:
                send_email_verification(user)
                sent += 1
            except Exception as exc:  # pragma: no cover - admin UI feedback
                skipped += 1
                messages.warning(
                    request,
                    f"Failed to send verification to {user.username or user.id}: {exc}",
                )

        if sent:
            messages.success(request, f"Sent verification email to {sent} user(s).")
        if skipped:
            messages.info(request, f"Skipped {skipped} user(s) without email or already verified.")

    send_verification_email.short_description = "Send verification email"


# Additional admin registrations can be added here as new models land.
