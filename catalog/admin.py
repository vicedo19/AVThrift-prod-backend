from django.contrib import admin

from .models import (
    Attribute,
    Category,
    Collection,
    CollectionProduct,
    Media,
    Product,
    ProductAttributeValue,
    ProductVariant,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent", "is_active", "sort_order", "created_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "description")
    ordering = ("sort_order", "name")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "status", "created_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("title", "slug", "description")
    ordering = ("title",)
    prepopulated_fields = {"slug": ("title",)}


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("sku", "product", "price", "status", "created_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("sku",)
    ordering = ("sku",)
    raw_id_fields = ("product",)


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "input_type", "is_filterable", "sort_order")
    list_filter = ("input_type", "is_filterable")
    search_fields = ("name", "code")
    ordering = ("sort_order", "name")


@admin.register(ProductAttributeValue)
class ProductAttributeValueAdmin(admin.ModelAdmin):
    list_display = ("attribute", "product", "variant", "value", "created_at", "updated_at")
    search_fields = ("value",)
    raw_id_fields = ("attribute", "product", "variant")
    ordering = ("attribute",)


@admin.register(Media)
class MediaAdmin(admin.ModelAdmin):
    list_display = ("product", "variant", "url", "is_primary", "sort_order", "created_at", "updated_at")
    list_filter = ("is_primary",)
    search_fields = ("url", "alt_text")
    raw_id_fields = ("product", "variant")
    ordering = ("sort_order", "id")


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "sort_order", "created_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    ordering = ("sort_order", "name")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(CollectionProduct)
class CollectionProductAdmin(admin.ModelAdmin):
    list_display = ("collection", "product", "sort_order", "created_at", "updated_at")
    raw_id_fields = ("collection", "product")
    ordering = ("collection", "sort_order")