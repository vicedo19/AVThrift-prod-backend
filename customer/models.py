"""Customer domain models.

Includes a profile tied to the auth user and normalized postal
addresses with validation suitable for multiple countries and
flexible formats.
"""

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base model adding created/updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Address(TimeStampedModel):
    """Normalized postal address tied to a user.

    Best practices:
    - Keep address lines minimal and avoid business logic here.
    - Store `country_code` as ISO 3166-1 alpha-2 uppercase.
    - Index common query fields for faster lookups.
    - Use a uniqueness constraint to reduce duplicate addresses per user.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses")
    name = models.CharField(
        max_length=120,
        blank=True,
        help_text="Optional recipient or label for the address",
    )
    addr1 = models.CharField(max_length=120)
    addr2 = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=80)
    state = models.CharField(
        max_length=40,
        blank=True,
        null=True,
        help_text="State/Province/Region (free-form to support multiple countries)",
    )
    postal_code = models.CharField(
        max_length=12,
        blank=True,
        null=True,
        validators=[RegexValidator(r"^[A-Za-z0-9\- ]{0,12}$", message="Use standard alphanumeric postal/zip code")],
        help_text="Flexible postal/zip code",
    )
    country_code = models.CharField(
        max_length=2,
        default="NG",
        validators=[RegexValidator(r"^[A-Z]{2}$", message="Use ISO 3166-1 alpha-2 country code (e.g., US)")],
        help_text="ISO 3166-1 alpha-2",
    )
    phone = models.CharField(
        max_length=16,
        blank=True,
        validators=[RegexValidator(r"^\+?[1-9]\d{1,14}$", message="Use E.164 format (e.g., +14155552671)")],
        help_text="Contact number for this specific address/recipient",
    )

    class Meta:
        indexes = [
            models.Index(fields=["user", "country_code", "postal_code"]),
            models.Index(fields=["user", "city"]),
            models.Index(fields=["user", "state"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "addr1", "city", "postal_code", "country_code"],
                name="unique_address_per_user",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        parts = [self.addr1]
        if self.addr2:
            parts.append(self.addr2)
        parts.extend([self.city, getattr(self, "state", ""), self.postal_code or "", self.country_code])
        return f"{self.name or ''} - " + ", ".join([p for p in parts if p])

    def shipping_contact(self) -> str | None:
        """Return the effective delivery contact phone for this address.

        Prefers this address's own `phone` if present; otherwise falls back
        to the owning user's phone. Whitespace-only values yield None.

        This is a convenience wrapper around the resolver in services.
        """

        # Defer import to avoid circulars at import time
        from .services import resolve_shipping_contact

        # Use profile if available; otherwise resolve based only on address
        profile = getattr(self.user, "profile", None)
        if profile is not None:
            return resolve_shipping_contact(profile, self)

        # No profile: prefer address phone, else None
        if self.phone:
            phone = self.phone.strip()
            return phone or None
        return None


class Profile(TimeStampedModel):
    """Per-user profile info and preferences.

    Best practices:
    - Keep auth identity in `users.User`; use Profile for domain preferences.
    - Use explicit booleans for opt-ins; default to opt-out.
    - Store defaults as FK pointers instead of flags on Address.
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    email_opt_in = models.BooleanField(default=False)
    sms_opt_in = models.BooleanField(default=False)
    default_shipping_address = models.ForeignKey(
        Address,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shipping_profiles",
    )
    default_billing_address = models.ForeignKey(
        Address,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="billing_profiles",
    )

    class Meta:
        indexes = [
            models.Index(fields=["user"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"Profile<{self.user_id}>"

    def get_shipping_contact(self, address: Address | None) -> str | None:
        """Return the effective delivery contact phone for a given address.

        Uses the per-address override when available, otherwise falls back to
        the owning user's `phone`. This centralizes resolution for views/serializers.
        """

        from .services import resolve_shipping_contact

        return resolve_shipping_contact(self, address)

    @property
    def default_shipping_contact(self) -> str | None:
        """Return the effective contact phone for the default shipping address."""

        return self.get_shipping_contact(self.default_shipping_address)
