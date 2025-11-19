from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    """AppConfig for the payments app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "payments"
    verbose_name = "Payments"
