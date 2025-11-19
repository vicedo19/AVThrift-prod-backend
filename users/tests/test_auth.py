from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase


class AuthFlowTests(APITestCase):
    def setUp(self):
        self.User = get_user_model()
        self.password = "StrongPass123!"
        self.user = self.User.objects.create_user(
            username="jdoe",
            email="jdoe@example.com",
            password=self.password,
            first_name="John",
            last_name="Doe",
        )

    def test_login_returns_tokens(self):
        resp = self.client.post(
            "/api/v1/auth/signin/",
            {"identifier": self.user.email, "password": self.password},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)

    def test_profile_requires_auth(self):
        resp = self.client.get("/api/v1/account/profile/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_with_access_token(self):
        signin = self.client.post(
            "/api/v1/auth/signin/",
            {"identifier": self.user.email, "password": self.password},
            format="json",
        )
        access = signin.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        resp = self.client.get("/api/v1/account/profile/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["email"], self.user.email)

    def test_logout_blacklists_refresh(self):
        signin = self.client.post(
            "/api/v1/auth/signin/",
            {"identifier": self.user.email, "password": self.password},
            format="json",
        )
        refresh = signin.data["refresh"]
        resp = self.client.post("/api/v1/auth/signout/", {"refresh": refresh}, format="json")
        self.assertIn(resp.status_code, (status.HTTP_205_RESET_CONTENT, status.HTTP_200_OK))
        # Try refreshing with the blacklisted token
        resp2 = self.client.post("/api/v1/auth/refresh/", {"refresh": refresh}, format="json")
        self.assertEqual(resp2.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_with_phone_returns_tokens(self):
        # Add phone and login using phone
        self.user.phone = "+14155552671"
        self.user.save(update_fields=["phone"])
        resp = self.client.post(
            "/api/v1/auth/signin/",
            {"identifier": self.user.phone, "password": self.password},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)
