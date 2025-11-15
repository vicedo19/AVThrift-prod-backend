"""Catalog app models.

Defines core entities for the catalog domain: categories, attributes,
products, variants, media, collections, and attribute values.
"""

from common.choices import ActiveInactive, DraftPublished
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base model adding created/updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStampedModel):
    """Hierarchical product categorization."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="children",
        on_delete=models.SET_NULL,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:  # pragma: no cover
        return self.name


class Attribute(TimeStampedModel):
    """Product attribute definition (e.g., color, size)."""

    INPUT_TEXT = "text"
    INPUT_NUMBER = "number"
    INPUT_BOOLEAN = "boolean"
    INPUT_SELECT = "select"
    INPUT_CHOICES = [
        (INPUT_TEXT, "Text"),
        (INPUT_NUMBER, "Number"),
        (INPUT_BOOLEAN, "Boolean"),
        (INPUT_SELECT, "Select"),
    ]

    name = models.CharField(max_length=120)
    code = models.CharField(max_length=64, unique=True)
    input_type = models.CharField(max_length=16, choices=INPUT_CHOICES, default=INPUT_TEXT)
    is_filterable = models.BooleanField(default=False)
    allowed_values = models.JSONField(null=True, blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:  # pragma: no cover
        return self.name


class Product(TimeStampedModel):
    """Core product entity."""

    STATUS_DRAFT = DraftPublished.DRAFT
    STATUS_PUBLISHED = DraftPublished.PUBLISHED
    STATUS_CHOICES = DraftPublished.choices

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    categories = models.ManyToManyField(Category, related_name="products", blank=True)
    # Currency fixed to NGN at the business level; field removed

    seo_title = models.CharField(max_length=200, blank=True)
    seo_description = models.TextField(blank=True)

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:  # pragma: no cover
        return self.title


class ProductVariant(TimeStampedModel):
    """Variant SKU under a product (e.g., size/color)."""

    STATUS_ACTIVE = ActiveInactive.ACTIVE
    STATUS_INACTIVE = ActiveInactive.INACTIVE
    STATUS_CHOICES = ActiveInactive.choices

    product = models.ForeignKey(Product, related_name="variants", on_delete=models.CASCADE)
    sku = models.CharField(max_length=64, unique=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    barcode = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    class Meta:
        ordering = ["sku"]
        constraints = [
            models.CheckConstraint(
                name="variant_price_non_negative",
                check=models.Q(price__gte=0) | models.Q(price__isnull=True),
            ),
        ]
        indexes = [
            models.Index(fields=["product", "status"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.product.title} [{self.sku}]"


class ProductAttributeValue(TimeStampedModel):
    """Assigned attribute values to products or variants."""

    attribute = models.ForeignKey(Attribute, related_name="values", on_delete=models.CASCADE)
    product = models.ForeignKey(
        Product, related_name="attribute_values", null=True, blank=True, on_delete=models.CASCADE
    )
    variant = models.ForeignKey(
        ProductVariant, related_name="attribute_values", null=True, blank=True, on_delete=models.CASCADE
    )
    value = models.TextField()

    class Meta:
        ordering = ["attribute__name"]
        constraints = [
            models.CheckConstraint(
                name="pav_xor_product_variant",
                check=(
                    models.Q(product__isnull=False, variant__isnull=True)
                    | models.Q(product__isnull=True, variant__isnull=False)
                ),
            ),
        ]
        indexes = [
            models.Index(fields=["attribute", "product", "variant"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        target = self.variant.sku if self.variant else (self.product.title if self.product else "-")
        return f"{self.attribute.code}={self.value} ({target})"


class Media(TimeStampedModel):
    """Product or variant imagery/media (URL-based placeholder)."""

    product = models.ForeignKey(Product, related_name="media", on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, related_name="media", null=True, blank=True, on_delete=models.CASCADE)
    url = models.URLField()
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["product"],
                condition=models.Q(is_primary=True, variant__isnull=True),
                name="unique_primary_media_per_product",
            ),
            models.UniqueConstraint(
                fields=["variant"],
                condition=models.Q(is_primary=True),
                name="unique_primary_media_per_variant",
            ),
        ]
        indexes = [
            models.Index(fields=["product", "sort_order", "is_primary"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return self.url


class Collection(TimeStampedModel):
    """Curated product collections."""

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    # Optional curated ordering within a collection via through model
    ordered_products = models.ManyToManyField(
        Product,
        through="CollectionProduct",
        related_name="ordered_collections",
        blank=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:  # pragma: no cover
        return self.name


class CollectionProduct(TimeStampedModel):
    """Curated ordering of products inside a collection."""

    collection = models.ForeignKey(Collection, related_name="collection_products", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name="collection_products", on_delete=models.CASCADE)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        indexes = [
            models.Index(fields=["collection", "sort_order"]),
        ]
        unique_together = ("collection", "product")

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.collection.slug}:{self.product.slug}#{self.sort_order}"
