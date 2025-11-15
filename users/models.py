"""User models for authentication and account management.

This module defines the custom `User` model which extends Django's
`AbstractUser` to enable email uniqueness, verification state, and
pending email changes for secure email updates.
"""

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models


class User(AbstractUser):
    """Custom user with unique email and verification state.

    Fields:
    - email: the primary email, unique at the database level (normalized).
    - email_verified: whether the primary email has been verified.
    - pending_email: a temporary email awaiting verification and confirmation.
    """

    email = models.EmailField(unique=True)
    email_verified = models.BooleanField(default=False)
    pending_email = models.EmailField(null=True, blank=True)
    phone = models.CharField(
        max_length=16,
        blank=True,
        validators=[RegexValidator(r"^\+?[1-9]\d{1,14}$", message="Use E.164 format (e.g., +14155552671)")],
        help_text="Primary contact number for the account in E.164 format",
    )

    def save(self, *args, **kwargs):
        """Normalize email fields and persist.

        Ensures both `email` and `pending_email` are stored in lowercase
        without surrounding whitespace so uniqueness checks are reliable.
        """
        if self.email:
            self.email = self.email.strip().lower()
        if self.pending_email:
            self.pending_email = self.pending_email.strip().lower()
        # Normalize phone whitespace; leave format enforcement to validator
        if self.phone:
            self.phone = self.phone.strip()
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["pending_email"],
                condition=models.Q(pending_email__isnull=False),
                name="unique_pending_email_non_null",
            )
        ]
        indexes = [
            models.Index(fields=["pending_email"]),
        ]
