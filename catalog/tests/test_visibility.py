import pytest
from catalog.tests.factories import ProductFactory
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_product_list_hides_drafts():
    ProductFactory(status="published", title="Visible One")
    ProductFactory(status="draft", title="Hidden One")

    client = APIClient()
    resp = client.get("/api/v1/catalog/products/")
    assert resp.status_code == 200
    titles = [r["title"] for r in resp.data["results"]]
    assert "Visible One" in titles
    assert "Hidden One" not in titles


@pytest.mark.django_db
def test_product_detail_draft_returns_404():
    p = ProductFactory(status="draft")

    client = APIClient()
    resp = client.get(f"/api/v1/catalog/products/{p.slug}/")
    assert resp.status_code == 404
