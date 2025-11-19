"""URL routes for the payments app (v1)."""

from django.urls import path

from .views import (
    PaymentIntentCreateUpdateView,
    PaymentIntentDetailView,
    PaymentsHealthView,
    PaystackInitializeView,
    PaystackWebhookView,
)

app_name = "payments"

urlpatterns = [
    path("health/", PaymentsHealthView.as_view(), name="payments-health"),
    path("intents/", PaymentIntentCreateUpdateView.as_view(), name="payment-intent-upsert"),
    path("intents/<str:reference>/", PaymentIntentDetailView.as_view(), name="payment-intent-detail"),
    path("paystack/initialize/", PaystackInitializeView.as_view(), name="paystack-initialize"),
    # Canonical webhook path
    path("webhooks/paystack/", PaystackWebhookView.as_view(), name="paystack-webhook"),
]
