"""Email utilities for the orders app.

Uses Django's email backend, with links composed from FRONTEND_URL.
"""

from django.conf import settings
from django.core.mail import send_mail


def send_order_paid_email(order) -> None:
    """Send a payment confirmation email to the order's email address.

    Includes a link to view the order on the frontend using `FRONTEND_URL`.
    Silently no-ops if no email is present.
    """
    to_email = order.email or getattr(order.user, "email", None)
    if not to_email:
        return

    subject = f"Your order {order.number or order.id} is confirmed"
    frontend = getattr(settings, "FRONTEND_URL", "")
    order_url = f"{frontend.rstrip('/')}\n"  # fallback: plain site link
    if frontend:
        order_url = f"{frontend.rstrip('/')}/orders/{order.id}"

    body = (
        "Thank you for your purchase!\n\n"
        f"Order: {order.number or order.id}\n"
        f"Status: {order.status}\n\n"
        f"You can view your order here: {order_url}\n"
    )

    send_mail(
        subject,
        body,
        getattr(settings, "DEFAULT_FROM_EMAIL", None),
        [to_email],
        fail_silently=True,
    )
