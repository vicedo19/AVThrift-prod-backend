import pytest
from catalog.tests.factories import CategoryFactory, CollectionFactory, MediaFactory, ProductFactory
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_products_list_filters_ordering_pagination_search(django_assert_num_queries):
    audio = CategoryFactory(name="Audio", slug="audio")
    video = CategoryFactory(name="Video", slug="video")

    p1 = ProductFactory(title="Studio Monitor Speakers", categories=[audio])
    MediaFactory(product=p1, is_primary=True, url="https://images.example.com/monitor-speakers.jpg")

    p2 = ProductFactory(title="4K Camcorder", categories=[video])
    MediaFactory(product=p2, is_primary=True, url="https://images.example.com/camcorder.jpg")

    client = APIClient()

    # Ensure query counts stay reasonable thanks to prefetch (upper bound)
    with django_assert_num_queries(8, exact=False):
        resp = client.get("/api/v1/catalog/products/?ordering=title")
        assert resp.status_code == 200
        assert resp.data["count"] >= 2
    # Check stabilized fields for product cards
    first = resp.data["results"][0]
    assert {
        "id",
        "title",
        "slug",
        "primary_media_url",
        "primary_category",
    } <= set(first.keys())

    # Filter by category slug
    resp_audio = client.get("/api/v1/catalog/products/?category=audio")
    assert resp_audio.status_code == 200
    assert all(r["slug"] == p1.slug for r in resp_audio.data["results"])  # type: ignore[index]

    # Pagination edge: very high page number should return empty results
    resp_page = client.get("/api/v1/catalog/products/?page=9999")
    # DRF PageNumberPagination returns 404 for out-of-range pages
    assert resp_page.status_code == 404

    # Ordering validation: ascending title
    resp_order = client.get("/api/v1/catalog/products/?ordering=title")
    titles = [r["title"] for r in resp_order.data["results"]]
    assert titles == sorted(titles)

    # Search by title using `q` alias
    resp_search = client.get("/api/v1/catalog/products/?q=camcorder")
    assert resp_search.status_code == 200
    assert any(r["slug"] == p2.slug for r in resp_search.data["results"])  # type: ignore[index]


@pytest.mark.django_db
def test_product_detail_includes_categories_and_media():
    audio = CategoryFactory(name="Audio", slug="audio")
    p = ProductFactory(title="Studio Monitor Speakers", categories=[audio])
    MediaFactory(product=p, is_primary=True, url="https://images.example.com/monitor-speakers.jpg")

    client = APIClient()
    resp = client.get(f"/api/v1/catalog/products/{p.slug}/")
    assert resp.status_code == 200
    assert {"categories", "media"} <= set(resp.data.keys())
    assert resp.data["categories"][0]["slug"] == "audio"
    assert resp.data["media"][0]["is_primary"] is True


@pytest.mark.django_db
def test_categories_list_and_detail():
    c = CategoryFactory(name="Audio", slug="audio")
    client = APIClient()
    resp_list = client.get("/api/v1/catalog/categories/")
    assert resp_list.status_code == 200
    resp_detail = client.get("/api/v1/catalog/categories/audio/")
    assert resp_detail.status_code == 200
    assert resp_detail.data["slug"] == c.slug


@pytest.mark.django_db
def test_collections_list_and_detail():
    p = ProductFactory(title="HDMI 2.1 Cable")
    coll = CollectionFactory(name="Featured", slug="featured", products=[p])
    client = APIClient()
    resp_list = client.get("/api/v1/catalog/collections/")
    assert resp_list.status_code == 200
    resp_detail = client.get("/api/v1/catalog/collections/featured/")
    assert resp_detail.status_code == 200
    assert resp_detail.data["slug"] == coll.slug
