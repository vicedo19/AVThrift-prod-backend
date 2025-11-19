import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_inventory_health_and_roadmap():
    client = APIClient()
    resp_health = client.get("/api/v1/inventory/health/")
    assert resp_health.status_code == 200
    assert resp_health.json()["app"] == "inventory"

    resp_roadmap = client.get("/api/v1/inventory/")
    assert resp_roadmap.status_code == 200
    assert "endpoints" in resp_roadmap.json()


# EOF
