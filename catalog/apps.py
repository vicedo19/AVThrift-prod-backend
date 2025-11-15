"""Django app configuration for catalog."""

from django.apps import AppConfig


class CatalogConfig(AppConfig):
    """Configure default auto field and app name."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "catalog"
