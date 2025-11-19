"""Read-only data access helpers for the customer app."""

from typing import Optional

from django.db.models import QuerySet

from .models import Address, Profile


def get_profile(user_id: int) -> Optional[Profile]:
    """Return a profile for the given user id, if it exists."""

    return (
        Profile.objects.select_related("default_shipping_address", "default_billing_address")
        .filter(user_id=user_id)
        .first()
    )


def list_addresses(user_id: int) -> QuerySet[Address]:
    """Return all addresses owned by the given user id."""

    return Address.objects.filter(user_id=user_id).order_by("-updated_at", "id")
