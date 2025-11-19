import pytest
from catalog.tests.factories import CategoryFactory, ProductFactory
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_admin_create_product_requires_staff():
    User = get_user_model()
    staff = User.objects.create_user(username="admin", email="admin@example.com", password="pass1234", is_staff=True)
    regular = User.objects.create_user(username="user", email="user@example.com", password="pass1234")

    c = CategoryFactory()
    client = APIClient()

    # Regular user forbidden
    client.force_authenticate(user=regular)
    resp_forbidden = client.post(
        "/api/v1/admin/catalog/products/",
        {"title": "Admin Product", "slug": "admin-product", "status": "published", "categories": [c.id]},
        format="json",
    )
    assert resp_forbidden.status_code in (401, 403)

    # Staff can create
    client.force_authenticate(user=staff)
    resp = client.post(
        "/api/v1/admin/catalog/products/",
        {"title": "Admin Product", "slug": "admin-product", "status": "published", "categories": [c.id]},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["slug"] == "admin-product"


@pytest.mark.django_db
def test_admin_update_product_categories():
    User = get_user_model()
    staff = User.objects.create_user(username="admin2", email="admin2@example.com", password="pass1234", is_staff=True)
    p = ProductFactory(status="draft")
    c1 = CategoryFactory()
    c2 = CategoryFactory()

    client = APIClient()
    client.force_authenticate(user=staff)

    resp = client.patch(
        f"/api/v1/admin/catalog/products/{p.id}/",
        {"categories": [c1.id, c2.id], "status": "published"},
        format="json",
    )
    assert resp.status_code == 200
    assert set(resp.data.get("categories", [])) == {c1.id, c2.id}
    assert resp.data["status"] == "published"
