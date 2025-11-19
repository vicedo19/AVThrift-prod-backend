"""Read-only query helpers for payments.

Selectors return data without side effects; add as flows evolve.
"""

from __future__ import annotations

from typing import Optional

from django.db.models import QuerySet
from payments.models import PaymentIntent


def get_intent_by_reference(reference: str) -> Optional[PaymentIntent]:
    """Return a single `PaymentIntent` by its `reference`, or None.

    Uses `select_related('order')` because most flows need order context.
    """

    if not reference:
        return None
    return PaymentIntent.objects.select_related("order").filter(reference=reference).first()


def list_intents_for_order(order_id: int, status: Optional[str] = None) -> QuerySet[PaymentIntent]:
    """List intents for a given order, optionally filtered by `status`.

    Returns a queryset respecting model ordering (newest first).
    """

    qs = PaymentIntent.objects.select_related("order").filter(order_id=order_id)
    if status:
        qs = qs.filter(status=status)
    return qs


def list_recent_failed_intents(limit: int = 20) -> QuerySet[PaymentIntent]:
    """Return recent failed intents, ordered by most recent first.

    The default `limit` is 20; callers may further slice the queryset.
    """

    qs = (
        PaymentIntent.objects.select_related("order").filter(status=PaymentIntent.STATUS_FAILED).order_by("-created_at")
    )
    # Slice for a LIMIT-like effect while still returning a queryset for chaining.
    return qs[:limit]
