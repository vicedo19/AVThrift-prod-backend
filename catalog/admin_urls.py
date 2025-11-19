"""Admin router for catalog write endpoints."""

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .admin_views import (
    CategoryAdminViewSet,
    CollectionAdminViewSet,
    CollectionProductAdminViewSet,
    MediaAdminViewSet,
    ProductAdminViewSet,
    ProductVariantAdminViewSet,
)

router = SimpleRouter()
router.register(r"categories", CategoryAdminViewSet, basename="admin-category")
router.register(r"products", ProductAdminViewSet, basename="admin-product")
router.register(r"variants", ProductVariantAdminViewSet, basename="admin-variant")
router.register(r"media", MediaAdminViewSet, basename="admin-media")
router.register(r"collections", CollectionAdminViewSet, basename="admin-collection")
router.register(r"collection-products", CollectionProductAdminViewSet, basename="admin-collection-product")

urlpatterns = [path("", include(router.urls))]
