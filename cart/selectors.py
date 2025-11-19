"""Selectors for read-only cart queries."""

from decimal import Decimal

from django.db.models import F, Sum

from .models import Cart


def get_active_cart_for_user(*, user):
    """Return the user's active cart, creating it if missing."""

    cart, _ = Cart.objects.get_or_create(user=user, session_id=None, status=Cart.STATUS_ACTIVE)
    return cart


def cart_totals(*, cart: Cart):
    """Compute cart totals based on items."""

    agg = cart.items.aggregate(
        subtotal=Sum(F("unit_price") * F("quantity")),
    )
    subtotal = agg.get("subtotal") or Decimal("0.00")
    # Taxes, shipping, discounts are future work; return subtotal only
    return {
        "subtotal": subtotal,
        "total": subtotal,
    }


def get_active_cart_for_session(*, session_id: str) -> Cart:
    """Return the guest session's active cart, creating it if missing."""

    cart, _ = Cart.objects.get_or_create(user=None, session_id=session_id, status=Cart.STATUS_ACTIVE)
    return cart
