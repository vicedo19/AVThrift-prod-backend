import pytest
from catalog.tests.factories import (
    CategoryFactory,
    CollectionFactory,
    MediaFactory,
    ProductFactory,
    ProductVariantFactory,
)
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_product_nested_variants_and_media_visibility():
    p_pub = ProductFactory(status="published")
    p_draft = ProductFactory(status="draft")
    v_pub = ProductVariantFactory(product=p_pub)
    ProductVariantFactory(product=p_draft)
    MediaFactory(product=p_pub, is_primary=True)

    client = APIClient()
    # Variants for published product present
    r1 = client.get(f"/api/v1/catalog/products/{p_pub.slug}/variants/")
    assert r1.status_code == 200
    skus = [x["sku"] for x in r1.data]
    assert v_pub.sku in skus

    # Variants for draft product hidden
    r2 = client.get(f"/api/v1/catalog/products/{p_draft.slug}/variants/")
    assert r2.status_code == 404

    # Media for published product present
    r3 = client.get(f"/api/v1/catalog/products/{p_pub.slug}/media/")
    assert r3.status_code == 200
    assert len(r3.data) >= 1


@pytest.mark.django_db
def test_category_nested_products():
    c = CategoryFactory(name="Audio", slug="audio")
    p = ProductFactory(status="published", categories=[c])
    client = APIClient()
    r = client.get("/api/v1/catalog/categories/audio/products/")
    assert r.status_code == 200
    assert any(x["slug"] == p.slug for x in r.data)


@pytest.mark.django_db
def test_collection_nested_products_curated():
    p = ProductFactory(status="published")
    CollectionFactory(name="Featured", slug="featured", products=[p])
    client = APIClient()
    r = client.get("/api/v1/catalog/collections/featured/products/")
    assert r.status_code == 200
    assert any(x["slug"] == p.slug for x in r.data)
