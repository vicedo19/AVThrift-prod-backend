"""Django app configuration for the users app."""

from django.apps import AppConfig


class UsersConfig(AppConfig):
    """Configure app defaults and name for Django registration."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "users"
