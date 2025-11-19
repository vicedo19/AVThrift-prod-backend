"""Admin viewsets for write endpoints in the catalog app.

Endpoints are restricted to staff users and use scoped throttling.
"""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, viewsets

from .admin_serializers import (
    CategoryAdminSerializer,
    CollectionAdminSerializer,
    CollectionProductAdminSerializer,
    MediaAdminSerializer,
    ProductAdminSerializer,
    ProductVariantAdminSerializer,
)
from .models import Category, Collection, CollectionProduct, Media, Product, ProductVariant


class AdminBaseViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAdminUser]
    throttle_scope = "catalog_admin_write"


@extend_schema_view(
    list=extend_schema(tags=["Admin Endpoints"], summary="List categories (admin)"),
    retrieve=extend_schema(tags=["Admin Endpoints"], summary="Get category (admin)"),
    create=extend_schema(tags=["Admin Endpoints"], summary="Create category"),
    update=extend_schema(tags=["Admin Endpoints"], summary="Update category"),
    partial_update=extend_schema(tags=["Admin Endpoints"], summary="Partial update category"),
    destroy=extend_schema(tags=["Admin Endpoints"], summary="Delete category"),
)
class CategoryAdminViewSet(AdminBaseViewSet):
    queryset = Category.objects.all().order_by("sort_order", "name")
    serializer_class = CategoryAdminSerializer


@extend_schema_view(
    list=extend_schema(tags=["Admin Endpoints"], summary="List products (admin)"),
    retrieve=extend_schema(tags=["Admin Endpoints"], summary="Get product (admin)"),
    create=extend_schema(tags=["Admin Endpoints"], summary="Create product"),
    update=extend_schema(tags=["Admin Endpoints"], summary="Update product"),
    partial_update=extend_schema(tags=["Admin Endpoints"], summary="Partial update product"),
    destroy=extend_schema(tags=["Admin Endpoints"], summary="Delete product"),
)
class ProductAdminViewSet(AdminBaseViewSet):
    queryset = Product.objects.all().prefetch_related("categories").order_by("title")
    serializer_class = ProductAdminSerializer


@extend_schema_view(
    list=extend_schema(tags=["Admin Endpoints"], summary="List variants (admin)"),
    retrieve=extend_schema(tags=["Admin Endpoints"], summary="Get variant (admin)"),
    create=extend_schema(tags=["Admin Endpoints"], summary="Create variant"),
    update=extend_schema(tags=["Admin Endpoints"], summary="Update variant"),
    partial_update=extend_schema(tags=["Admin Endpoints"], summary="Partial update variant"),
    destroy=extend_schema(tags=["Admin Endpoints"], summary="Delete variant"),
)
class ProductVariantAdminViewSet(AdminBaseViewSet):
    queryset = ProductVariant.objects.select_related("product").order_by("sku")
    serializer_class = ProductVariantAdminSerializer


@extend_schema_view(
    list=extend_schema(tags=["Admin Endpoints"], summary="List media (admin)"),
    retrieve=extend_schema(tags=["Admin Endpoints"], summary="Get media item (admin)"),
    create=extend_schema(tags=["Admin Endpoints"], summary="Create media item"),
    update=extend_schema(tags=["Admin Endpoints"], summary="Update media item"),
    partial_update=extend_schema(tags=["Admin Endpoints"], summary="Partial update media item"),
    destroy=extend_schema(tags=["Admin Endpoints"], summary="Delete media item"),
)
class MediaAdminViewSet(AdminBaseViewSet):
    queryset = Media.objects.select_related("product", "variant").order_by("sort_order", "id")
    serializer_class = MediaAdminSerializer


@extend_schema_view(
    list=extend_schema(tags=["Admin Endpoints"], summary="List collections (admin)"),
    retrieve=extend_schema(tags=["Admin Endpoints"], summary="Get collection (admin)"),
    create=extend_schema(tags=["Admin Endpoints"], summary="Create collection"),
    update=extend_schema(tags=["Admin Endpoints"], summary="Update collection"),
    partial_update=extend_schema(tags=["Admin Endpoints"], summary="Partial update collection"),
    destroy=extend_schema(tags=["Admin Endpoints"], summary="Delete collection"),
)
class CollectionAdminViewSet(AdminBaseViewSet):
    queryset = Collection.objects.all().order_by("sort_order", "name")
    serializer_class = CollectionAdminSerializer


@extend_schema_view(
    list=extend_schema(tags=["Admin Endpoints"], summary="List curated collection products (admin)"),
    retrieve=extend_schema(tags=["Admin Endpoints"], summary="Get curated entry (admin)"),
    create=extend_schema(tags=["Admin Endpoints"], summary="Add product to collection with ordering"),
    update=extend_schema(tags=["Admin Endpoints"], summary="Update curated entry"),
    partial_update=extend_schema(tags=["Admin Endpoints"], summary="Partial update curated entry"),
    destroy=extend_schema(tags=["Admin Endpoints"], summary="Remove product from collection"),
)
class CollectionProductAdminViewSet(AdminBaseViewSet):
    queryset = CollectionProduct.objects.select_related("collection", "product").order_by("sort_order", "id")
    serializer_class = CollectionProductAdminSerializer
