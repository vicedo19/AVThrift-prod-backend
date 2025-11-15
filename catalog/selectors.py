"""Selectors for the catalog domain.

Expose read-only query helpers to keep views thin and allow reuse across
APIs and services. Selectors should return querysets or lightweight data
structures and avoid side effects.
"""

from typing import Iterable, Optional

from django.db.models import Prefetch, Q, QuerySet
from django.db.models.expressions import OuterRef, Subquery
from django.db.models.functions import Coalesce
from inventory.models import StockItem

from .models import Category, Collection, CollectionProduct, Media, Product, ProductVariant


def list_categories(ordering: Optional[Iterable[str]] = None) -> QuerySet[Category]:
    """Return active categories ordered by the provided fields.

    Defaults to sorting by ``sort_order`` then ``name``.
    """

    ordering = list(ordering or ("sort_order", "name"))
    return Category.objects.filter(is_active=True).order_by(*ordering)


def get_category_by_slug(slug: str) -> Optional[Category]:
    """Return a single active category by slug, or None if not found."""

    try:
        return Category.objects.get(slug=slug, is_active=True)
    except Category.DoesNotExist:
        return None


def list_products(
    *,
    category_slug: Optional[str] = None,
    status: Optional[str] = None,
    ordering: Optional[Iterable[str]] = None,
    search: Optional[str] = None,
) -> QuerySet[Product]:
    """Return products with common filters and optimized prefetching.

    Prefetches only primary media for list views and categories to avoid N+1.
    """

    qs = Product.objects.all().prefetch_related(
        Prefetch("media", queryset=Media.objects.filter(is_primary=True)),
        "categories",
    )

    if category_slug:
        qs = qs.filter(categories__slug=category_slug)
    if status:
        qs = qs.filter(status=status)

    if search:
        qs = qs.filter(
            Q(title__icontains=search) | Q(description__icontains=search) | Q(categories__name__icontains=search)
        )

    ordering = list(ordering or ("title",))
    return qs.order_by(*ordering).distinct()


def get_product_by_slug(slug: str) -> Optional[Product]:
    """Return a single product by slug with full media and categories prefetched."""

    qs = Product.objects.prefetch_related("media", "categories")
    try:
        return qs.get(slug=slug)
    except Product.DoesNotExist:
        return None


def list_collections(ordering: Optional[Iterable[str]] = None) -> QuerySet[Collection]:
    """Return active collections ordered by the provided fields."""

    ordering = list(ordering or ("sort_order", "name"))
    return Collection.objects.filter(is_active=True).order_by(*ordering)


def get_collection_with_ordered_products(slug: str) -> Optional[Collection]:
    """Return a collection by slug with curated ordered products prefetched.

    Prefetches ``collection_products`` selecting related product, ordered by ``sort_order``.
    """

    qs = Collection.objects.prefetch_related(
        Prefetch(
            "collection_products",
            queryset=CollectionProduct.objects.select_related("product").order_by("sort_order"),
        )
    )
    try:
        return qs.get(slug=slug, is_active=True)
    except Collection.DoesNotExist:
        return None


def list_products_in_category(*, category_slug: str, ordering: Optional[Iterable[str]] = None) -> QuerySet[Product]:
    """Return products scoped to a category slug.

    Delegates to list_products with the category filter.
    """

    return list_products(category_slug=category_slug, ordering=ordering)


def list_variants_by_product_slug(*, product_slug: str) -> QuerySet[ProductVariant]:
    """Return variants for a given product slug, annotated with availability.

    Availability is defined as ``quantity - reserved`` from the inventory StockItem.
    When no stock item exists for a variant, availability defaults to 0.
    """

    qty_sub = Subquery(StockItem.objects.filter(variant_id=OuterRef("pk")).values("quantity")[:1])
    res_sub = Subquery(StockItem.objects.filter(variant_id=OuterRef("pk")).values("reserved")[:1])
    available_expr = Coalesce(qty_sub, 0) - Coalesce(res_sub, 0)

    return (
        ProductVariant.objects.select_related("product")
        .prefetch_related("media")
        .annotate(available=available_expr)
        .filter(product__slug=product_slug)
    )


def list_media_by_product_slug(*, product_slug: str) -> QuerySet[Media]:
    """Return media items for a given product slug ordered by sort_order then id."""

    return Media.objects.filter(product__slug=product_slug).order_by("sort_order", "id")


def list_collection_products(*, collection_slug: str) -> QuerySet[Product]:
    """Return products in a collection in curated order, with basic prefetches."""

    return (
        Product.objects.filter(collection_products__collection__slug=collection_slug)
        .order_by("collection_products__sort_order", "id")
        .prefetch_related(
            Prefetch("media", queryset=Media.objects.filter(is_primary=True)),
            "categories",
        )
    )
