"""URL routes for the catalog app."""

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import AttributeViewSet, CategoryViewSet, CollectionViewSet, ProductViewSet, VariantViewSet

router = SimpleRouter()
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"products", ProductViewSet, basename="product")
router.register(r"collections", CollectionViewSet, basename="collection")
router.register(r"variants", VariantViewSet, basename="variant")
router.register(r"attributes", AttributeViewSet, basename="attribute")

urlpatterns = [path("", include(router.urls))]
