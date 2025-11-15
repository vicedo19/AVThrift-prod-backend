import pytest
from catalog.tests.factories import AttributeFactory, ProductFactory, ProductVariantFactory
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_variants_list_and_detail_respects_product_visibility():
    p_published = ProductFactory(status="published")
    p_draft = ProductFactory(status="draft")
    v1 = ProductVariantFactory(product=p_published)
    v2 = ProductVariantFactory(product=p_draft)

    client = APIClient()
    resp_list = client.get("/api/v1/catalog/variants/?ordering=sku")
    assert resp_list.status_code == 200
    skus = [r["sku"] for r in resp_list.data["results"]]
    assert v1.sku in skus
    assert v2.sku not in skus  # hidden because product is draft

    resp_detail = client.get(f"/api/v1/catalog/variants/{v1.id}/")
    assert resp_detail.status_code == 200
    assert resp_detail.data["sku"] == v1.sku


@pytest.mark.django_db
def test_attributes_list_and_detail():
    a = AttributeFactory(name="Color", code="color")
    client = APIClient()
    resp_list = client.get("/api/v1/catalog/attributes/")
    assert resp_list.status_code == 200
    assert any(r["code"] == "color" for r in resp_list.data["results"])  # type: ignore[index]

    resp_detail = client.get(f"/api/v1/catalog/attributes/{a.id}/")
    assert resp_detail.status_code == 200
    assert resp_detail.data["code"] == "color"
