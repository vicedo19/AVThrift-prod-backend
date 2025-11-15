"""URL routes for the orders app (v1)."""

from django.urls import path

from .views import OrderCancelView, OrderDetailView, OrderListView, OrderPaymentWebhookView, OrderPayView

app_name = "orders"

urlpatterns = [
    path("", OrderListView.as_view(), name="order-list"),
    path("<int:order_id>/", OrderDetailView.as_view(), name="order-detail"),
    path("<int:order_id>/pay/", OrderPayView.as_view(), name="order-pay"),
    path("<int:order_id>/cancel/", OrderCancelView.as_view(), name="order-cancel"),
    path("webhooks/payment/", OrderPaymentWebhookView.as_view(), name="order-webhook-payment"),
]
