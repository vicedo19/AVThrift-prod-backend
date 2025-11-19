from django.apps import AppConfig


class CustomerConfig(AppConfig):
    """App configuration for the customer bounded context."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "customer"
    verbose_name = "Customer"
