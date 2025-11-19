"""Token generators for user email verification and email change flows.

These extend Django's PasswordResetTokenGenerator to bind tokens to
verification state or pending email, ensuring tokens invalidate when
state changes.
"""

from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Token bound to a user's verification state.

    When `email_verified` flips to True, existing tokens become invalid.
    """

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{timestamp}{user.email_verified}"


email_verification_token = EmailVerificationTokenGenerator()


class EmailChangeTokenGenerator(PasswordResetTokenGenerator):
    """Token bound to the requested `pending_email`.

    Token validity depends on the current pending email value, making
    any change to that value revoke earlier tokens.
    """

    def _make_hash_value(self, user, timestamp):
        pending = (user.pending_email or "").lower()
        return f"{user.pk}{timestamp}{pending}"


email_change_token = EmailChangeTokenGenerator()
