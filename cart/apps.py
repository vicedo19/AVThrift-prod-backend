"""Django app configuration for the Cart app."""

from django.apps import AppConfig


class CartConfig(AppConfig):
    """AppConfig for the cart domain (shopping cart)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "cart"
