"""Read-only viewsets for catalog resources (initial MVP)."""

from django.db.models.expressions import OuterRef, Subquery
from django.db.models.functions import Coalesce
from django_filters import rest_framework as filters
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, extend_schema_view
from inventory.models import StockItem
from rest_framework import filters as drf_filters
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from . import selectors
from .models import Attribute, Category, Collection, Product, ProductVariant
from .serializers import (
    AttributeSerializer,
    CategorySerializer,
    CollectionSerializer,
    MediaSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    ProductVariantSerializer,
)
from .throttling import CatalogScopedRateThrottle


@extend_schema_view(
    list=extend_schema(
        summary="List categories",
        description="Returns active categories ordered by sort_order then name",
        tags=["Catalog Endpoints"],
        examples=[
            OpenApiExample(
                "Category list",
                value={
                    "count": 3,
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": 1,
                            "name": "Audio",
                            "slug": "audio",
                            "description": "Audio equipment",
                            "parent": None,
                            "is_active": True,
                            "sort_order": 0,
                        }
                    ],
                },
                response_only=True,
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Get category by slug",
        description="Returns a single category by its slug",
        tags=["Catalog Endpoints"],
        examples=[
            OpenApiExample(
                "Category detail",
                value={
                    "id": 1,
                    "name": "Audio",
                    "slug": "audio",
                    "description": "Audio equipment",
                    "parent": None,
                    "is_active": True,
                    "sort_order": 0,
                },
                response_only=True,
            )
        ],
    ),
)
class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.filter(is_active=True).order_by("sort_order", "name")
    serializer_class = CategorySerializer
    lookup_field = "slug"
    throttle_scope = "catalog"
    throttle_classes = [CatalogScopedRateThrottle, UserRateThrottle, AnonRateThrottle]

    @extend_schema(
        tags=["Catalog Endpoints"],
        summary="List products in category",
        description="Returns products within a category by slug",
    )
    @action(detail=True, methods=["get"], url_path="products")
    def products(self, request, slug=None):
        qs = selectors.list_products_in_category(category_slug=slug)
        return Response(ProductListSerializer(qs, many=True).data)


class ProductFilterSet(filters.FilterSet):
    category = filters.CharFilter(field_name="categories__slug")

    class Meta:
        model = Product
        fields = ["category"]


@extend_schema_view(
    list=extend_schema(
        summary="List products",
        description=(
            "Returns published products. Supports filtering by `category`, ordering by `title` or `created_at`, "
            "and search via either `search` or `q`."
        ),
        tags=["Catalog Endpoints"],
        parameters=[
            OpenApiParameter("category", OpenApiTypes.STR, location="query", description="Filter by category slug"),
            OpenApiParameter(
                "ordering", OpenApiTypes.STR, location="query", description="Order by `title` or `created_at`"
            ),
            OpenApiParameter("search", OpenApiTypes.STR, location="query", description="Search products by text"),
            OpenApiParameter("q", OpenApiTypes.STR, location="query", description="Alias for `search`"),
        ],
    ),
    retrieve=extend_schema(
        summary="Get product by slug",
        description="Returns a published product with categories and media",
        tags=["Catalog Endpoints"],
    ),
)
class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    lookup_field = "slug"
    lookup_value_regex = "[^/]+"
    filterset_class = ProductFilterSet
    throttle_scope = "catalog"
    throttle_classes = [CatalogScopedRateThrottle, UserRateThrottle, AnonRateThrottle]

    # Support both `search` and `q` query params for search
    class QSearchFilter(drf_filters.SearchFilter):
        search_param = "q"

    filter_backends = [
        filters.DjangoFilterBackend,
        drf_filters.OrderingFilter,
        drf_filters.SearchFilter,
        QSearchFilter,
    ]
    ordering_fields = ["title", "created_at"]
    search_fields = ["title", "description", "categories__name"]

    def get_queryset(self):
        # Use selectors for list; prefetch full relations for detail.
        if self.action == "list":
            # Filtering/search is applied by DRF backends; selectors provide optimized prefetch for list.
            return selectors.list_products().filter(status=Product.STATUS_PUBLISHED)
        return (
            Product.objects.filter(status=Product.STATUS_PUBLISHED)
            .prefetch_related("media", "categories")
            .order_by("title")
        )

    def get_serializer_class(self):
        return ProductDetailSerializer if self.action == "retrieve" else ProductListSerializer

    @extend_schema(
        tags=["Catalog Endpoints"],
        summary="List product variants",
        description="Returns active variants for a published product",
    )
    @action(detail=True, methods=["get"], url_path="variants")
    def variants(self, request, slug=None):
        product = selectors.get_product_by_slug(slug)
        if not product or product.status != Product.STATUS_PUBLISHED:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        qs = selectors.list_variants_by_product_slug(product_slug=slug).filter(status=ProductVariant.STATUS_ACTIVE)
        return Response(ProductVariantSerializer(qs, many=True).data)

    @extend_schema(
        tags=["Catalog Endpoints"],
        summary="List product media",
        description="Returns media items for a published product",
    )
    @action(detail=True, methods=["get"], url_path="media")
    def media(self, request, slug=None):
        product = selectors.get_product_by_slug(slug)
        if not product or product.status != Product.STATUS_PUBLISHED:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        qs = selectors.list_media_by_product_slug(product_slug=slug)
        return Response(MediaSerializer(qs, many=True).data)


@extend_schema_view(
    list=extend_schema(
        summary="List collections",
        description=(
            "Returns active collections ordered by sort_order then name.\n\n"
            "Ordering of products within a collection is curated via the CollectionProduct through model."
        ),
        tags=["Catalog Endpoints"],
        examples=[
            OpenApiExample(
                "Collection list",
                value={
                    "count": 1,
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": 1,
                            "name": "Featured",
                            "slug": "featured",
                            "description": "Featured products",
                            "is_active": True,
                            "sort_order": 0,
                        }
                    ],
                },
                response_only=True,
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Get collection by slug",
        description=(
            "Returns a single collection by its slug.\n\n"
            "Products associated with a collection are presented in the curated order defined by CollectionProduct."
        ),
        tags=["Catalog Endpoints"],
        examples=[
            OpenApiExample(
                "Collection detail",
                value={
                    "id": 1,
                    "name": "Featured",
                    "slug": "featured",
                    "description": "Featured products",
                    "is_active": True,
                    "sort_order": 0,
                },
                response_only=True,
            )
        ],
    ),
)
class CollectionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Collection.objects.filter(is_active=True).order_by("sort_order", "name")
    serializer_class = CollectionSerializer
    lookup_field = "slug"
    throttle_scope = "catalog"
    throttle_classes = [CatalogScopedRateThrottle, UserRateThrottle, AnonRateThrottle]

    @extend_schema(
        tags=["Catalog Endpoints"],
        summary="List products in collection",
        description="Returns products in a collection by slug in curated order",
    )
    @action(detail=True, methods=["get"], url_path="products")
    def products(self, request, slug=None):
        qs = selectors.list_collection_products(collection_slug=slug)
        return Response(ProductListSerializer(qs, many=True).data)


class VariantFilterSet(filters.FilterSet):
    product = filters.CharFilter(field_name="product__slug")
    status = filters.CharFilter(field_name="status")

    class Meta:
        model = ProductVariant
        fields = ["product", "status"]


@extend_schema_view(
    list=extend_schema(
        summary="List variants",
        description="Returns variants for published products with availability annotated",
        tags=["Catalog Endpoints"],
        parameters=[
            OpenApiParameter("product", OpenApiTypes.STR, location="query", description="Filter by product slug"),
            OpenApiParameter("status", OpenApiTypes.STR, location="query", description="Filter by variant status"),
            OpenApiParameter("ordering", OpenApiTypes.STR, location="query", description="Order by `sku` or `id`"),
            OpenApiParameter("search", OpenApiTypes.STR, location="query", description="Search by `sku` or `barcode`"),
        ],
    ),
    retrieve=extend_schema(
        summary="Get variant",
        description="Returns a variant for a published product",
        tags=["Catalog Endpoints"],
    ),
)
class VariantViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductVariantSerializer
    filterset_class = VariantFilterSet
    filter_backends = [filters.DjangoFilterBackend, drf_filters.OrderingFilter, drf_filters.SearchFilter]
    ordering_fields = ["sku", "id"]
    search_fields = ["sku", "barcode"]
    throttle_scope = "catalog"
    throttle_classes = [CatalogScopedRateThrottle, UserRateThrottle, AnonRateThrottle]

    def get_queryset(self):
        qs = ProductVariant.objects.select_related("product").order_by("sku")
        # Enforce product visibility: only variants of published products in public API
        qs = qs.filter(product__status=Product.STATUS_PUBLISHED)
        # Annotate availability from inventory.StockItem
        qty_sub = Subquery(StockItem.objects.filter(variant_id=OuterRef("pk")).values("quantity")[:1])
        res_sub = Subquery(StockItem.objects.filter(variant_id=OuterRef("pk")).values("reserved")[:1])
        return qs.annotate(available=Coalesce(qty_sub, 0) - Coalesce(res_sub, 0))


class AttributeFilterSet(filters.FilterSet):
    is_filterable = filters.BooleanFilter(field_name="is_filterable")

    class Meta:
        model = Attribute
        fields = ["is_filterable"]


@extend_schema_view(
    list=extend_schema(
        summary="List attributes",
        description="Returns attributes with optional filtering by `is_filterable`",
        tags=["Catalog Endpoints"],
        parameters=[
            OpenApiParameter(
                "is_filterable", OpenApiTypes.BOOL, location="query", description="Filter by filterability"
            ),
            OpenApiParameter(
                "ordering", OpenApiTypes.STR, location="query", description="Order by `name` or `sort_order`"
            ),
            OpenApiParameter("search", OpenApiTypes.STR, location="query", description="Search by `name` or `code`"),
        ],
    ),
    retrieve=extend_schema(
        summary="Get attribute",
        description="Returns a single attribute",
        tags=["Catalog Endpoints"],
    ),
)
class AttributeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Attribute.objects.order_by("sort_order", "name")
    serializer_class = AttributeSerializer
    filterset_class = AttributeFilterSet
    filter_backends = [filters.DjangoFilterBackend, drf_filters.OrderingFilter, drf_filters.SearchFilter]
    ordering_fields = ["name", "sort_order"]
    search_fields = ["name", "code"]
    throttle_scope = "catalog"
    throttle_classes = [CatalogScopedRateThrottle, UserRateThrottle, AnonRateThrottle]
