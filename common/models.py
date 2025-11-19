"""Common base models and mixins shared across apps.

Provides a single `TimeStampedModel` abstract base to keep models DRY.
"""

from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base model adding `created_at` and `updated_at` timestamps.

    Use this as a base for models that need automatic timestamp fields.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
