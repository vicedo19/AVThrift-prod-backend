"""Admin registration for catalog models."""

from django.contrib import admin

from .models import Category, Collection, CollectionProduct, Media, Product, ProductVariant


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent", "is_active", "sort_order")
    search_fields = ("name", "slug")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}


class MediaInline(admin.TabularInline):
    model = Media
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "status")
    search_fields = ("title", "slug")
    list_filter = ("status", "categories")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [MediaInline]


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "sort_order")
    search_fields = ("name", "slug")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = []


class CollectionProductInline(admin.TabularInline):
    model = CollectionProduct
    extra = 0
    fields = ("product", "sort_order")
    ordering = ("sort_order",)


# Attach inline after class definition to avoid forward reference issues
CollectionAdmin.inlines = [CollectionProductInline]


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("product", "sku", "status", "price")
    search_fields = ("sku",)
    list_filter = ("status",)
