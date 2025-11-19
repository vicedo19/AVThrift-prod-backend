"""User-related service functions for email and token workflows.

Provides helpers to build frontend links and send emails for password
reset, email verification, and email change confirmation. These are
pure functions used by views to keep business logic organized.
"""

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import email_change_token, email_verification_token


def build_frontend_url(path: str, query: dict | None = None) -> str:
    """Construct a full frontend URL for the given path and query.

    Reads `FRONTEND_URL` from settings, trims trailing slashes, and
    attaches query parameters for token-based flows.
    """
    base = getattr(settings, "FRONTEND_URL", None) or ""
    if not base:
        base = ""
    if base.endswith("/"):
        base = base[:-1]
    url = f"{base}{path}"
    if query:
        from urllib.parse import urlencode

        url = f"{url}?{urlencode(query)}"
    return url


def send_password_reset_email(user):
    """Send a password reset email with uid/token to the user's address."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = build_frontend_url(
        "/reset-password",
        {"uid": uid, "token": token},
    )
    send_mail(
        subject="Reset your AVThrift password",
        message=f"Use this link to reset your password: {link}",
        from_email=None,
        recipient_list=[user.email],
    )
    return uid, token


def send_email_verification(user):
    """Send an email verification link to the user's current email."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    link = build_frontend_url(
        "/verify-email",
        {"uid": uid, "token": token},
    )
    send_mail(
        subject="Verify your AVThrift email",
        message=f"Confirm your email with this link: {link}",
        from_email=None,
        recipient_list=[user.email],
    )
    return uid, token


def send_email_change(user):
    """Send an email change confirmation link to the pending address."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_change_token.make_token(user)
    link = build_frontend_url(
        "/change-email",
        {"uid": uid, "token": token, "new_email": user.pending_email},
    )
    send_mail(
        subject="Confirm your new AVThrift email",
        message=f"Confirm your new email with this link: {link}",
        from_email=None,
        recipient_list=[user.pending_email],
    )
    return uid, token
