"""URL routes for the customer app."""

from django.urls import path

from .views import AddressDetailView, AddressListCreateView, ProfileView

urlpatterns = [
    # Profile endpoints
    path("profile/", ProfileView.as_view(), name="profile"),
    # Address endpoints
    path("addresses/", AddressListCreateView.as_view(), name="address-list-create"),
    path("addresses/<int:pk>/", AddressDetailView.as_view(), name="address-detail"),
]

# EOF
