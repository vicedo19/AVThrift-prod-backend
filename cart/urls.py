"""Cart URL routes (v1)."""

from django.urls import path

from .views import (
    CartAbandonView,
    CartAddItemView,
    CartCheckoutView,
    CartClearView,
    CartDetailView,
    CartItemDeleteView,
    CartItemUpdateView,
    GuestCartAddItemView,
    GuestCartClearView,
    GuestCartDetailView,
    GuestCartItemDeleteView,
    GuestCartItemUpdateView,
    MergeGuestCartView,
)

app_name = "cart"

urlpatterns = [
    path("", CartDetailView.as_view(), name="cart-detail"),
    path("items/", CartAddItemView.as_view(), name="cart-add-item"),
    path("items/<int:item_id>/", CartItemUpdateView.as_view(), name="cart-update-item"),
    path("items/<int:item_id>/delete/", CartItemDeleteView.as_view(), name="cart-delete-item"),
    path("checkout/", CartCheckoutView.as_view(), name="cart-checkout"),
    path("abandon/", CartAbandonView.as_view(), name="cart-abandon"),
    path("clear/", CartClearView.as_view(), name="cart-clear"),
    # Guest cart routes
    path("guest/", GuestCartDetailView.as_view(), name="guest-cart-detail"),
    path("guest/items/", GuestCartAddItemView.as_view(), name="guest-cart-add-item"),
    path("guest/items/<int:item_id>/", GuestCartItemUpdateView.as_view(), name="guest-cart-update-item"),
    path("guest/items/<int:item_id>/delete/", GuestCartItemDeleteView.as_view(), name="guest-cart-delete-item"),
    path("guest/clear/", GuestCartClearView.as_view(), name="guest-cart-clear"),
    path("merge-guest/", MergeGuestCartView.as_view(), name="cart-merge-guest"),
]
