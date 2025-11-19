"""Minimal test covering the payments health endpoint."""

from django.urls import reverse
from rest_framework.test import APIClient


def test_payments_health_ok():
    client = APIClient()
    url = reverse("payments:payments-health")
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
