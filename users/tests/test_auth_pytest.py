import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_login_and_profile_pytest():
    User = get_user_model()
    user = User.objects.create_user(
        username="jdoe",
        email="jdoe@example.com",
        password="StrongPass123!",
    )
    client = APIClient()

    resp = client.post(
        "/api/v1/auth/signin/",
        {"identifier": "jdoe@example.com", "password": "StrongPass123!"},
        format="json",
    )
    assert resp.status_code == 200
    access = resp.data["access"]

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    profile = client.get("/api/v1/account/profile/")
    assert profile.status_code == 200
    assert profile.data["email"] == user.email
