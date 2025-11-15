"""Admin serializers for write endpoints in the catalog app.

Provide ModelSerializers with writable relationships for staff/admin use.
"""

from rest_framework import serializers

from .models import Category, Collection, CollectionProduct, Media, Product, ProductVariant


class CategoryAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "parent",
            "is_active",
            "sort_order",
        ]


class ProductAdminSerializer(serializers.ModelSerializer):
    categories = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), many=True, required=False)

    class Meta:
        model = Product
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "status",
            "seo_title",
            "seo_description",
            "categories",
        ]


class ProductVariantAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "product",
            "sku",
            "price",
            "barcode",
            "status",
        ]


class MediaAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Media
        fields = [
            "id",
            "product",
            "variant",
            "url",
            "alt_text",
            "is_primary",
            "sort_order",
        ]


class CollectionAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collection
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "is_active",
            "sort_order",
        ]


class CollectionProductAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollectionProduct
        fields = [
            "id",
            "collection",
            "product",
            "sort_order",
        ]
