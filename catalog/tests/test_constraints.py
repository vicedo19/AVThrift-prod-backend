import pytest
from catalog.models import Media, ProductAttributeValue
from catalog.tests.factories import AttributeFactory, MediaFactory, ProductFactory, ProductVariantFactory
from django.db import IntegrityError


@pytest.mark.django_db
def test_media_primary_uniqueness_enforced_for_product():
    p = ProductFactory()
    # Create one primary
    MediaFactory(product=p, is_primary=True)
    # Attempt to create another primary for same product should violate constraint
    with pytest.raises(IntegrityError):
        Media.objects.create(product=p, url="https://example.com/dup.jpg", is_primary=True)


@pytest.mark.django_db
def test_media_primary_uniqueness_enforced_for_variant():
    v = ProductVariantFactory()
    MediaFactory(product=v.product, variant=v, is_primary=True)
    with pytest.raises(IntegrityError):
        Media.objects.create(product=v.product, variant=v, url="https://example.com/dup2.jpg", is_primary=True)


@pytest.mark.django_db
def test_attribute_value_both_set_fails():
    p = ProductFactory()
    v = ProductVariantFactory(product=p)
    attr = AttributeFactory()
    with pytest.raises(IntegrityError):
        ProductAttributeValue.objects.create(product=p, variant=v, attribute=attr, value="x")


@pytest.mark.django_db
def test_attribute_value_neither_set_fails():
    attr = AttributeFactory()
    with pytest.raises(IntegrityError):
        ProductAttributeValue.objects.create(attribute=attr, value="y")
