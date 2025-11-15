"""Customer domain services for mutations and side-effects.

Keep business rules here and keep views thin.
"""

from typing import Optional

from django.core.exceptions import ValidationError

from .models import Address, Profile


def ensure_address_belongs_to_profile_user(profile: Profile, address: Optional[Address]) -> None:
    """Validate that the given address belongs to the same user as the profile.

    Raises ValidationError if invalid.
    """

    if address and address.user_id != profile.user_id:
        raise ValidationError("Default address must belong to the profile's user.")


def set_defaults(profile: Profile, shipping: Optional[Address], billing: Optional[Address]) -> Profile:
    """Set default shipping/billing addresses with validation.

    Returns the updated profile.
    """

    ensure_address_belongs_to_profile_user(profile, shipping)
    ensure_address_belongs_to_profile_user(profile, billing)
    profile.default_shipping_address = shipping
    profile.default_billing_address = billing
    profile.save(update_fields=["default_shipping_address", "default_billing_address"])
    return profile


def resolve_shipping_contact(profile: Profile, address: Optional[Address]) -> Optional[str]:
    """Determine the delivery contact phone.

    Returns the `Address.phone` when present (per-address override), otherwise
    falls back to the owning `User.phone`. Whitespace is stripped; empty values yield None.

    This centralizes contact resolution so views/serializers can keep logic thin.
    """

    # Prefer the per-address override if provided
    if address and address.phone:
        phone = address.phone.strip()
        return phone or None

    # Fall back to the user-level default
    user_phone = getattr(profile.user, "phone", "")
    if user_phone:
        phone = user_phone.strip()
        return phone or None

    return None
