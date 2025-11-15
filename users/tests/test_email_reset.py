from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase


class EmailResetTests(APITestCase):
    def setUp(self):
        self.User = get_user_model()
        self.password = "StrongPass123!"
        self.user = self.User.objects.create_user(
            username="changeemail",
            email="old@example.com",
            password=self.password,
        )
        # Authenticate
        signin = self.client.post(
            "/api/v1/auth/signin/",
            {"identifier": self.user.email, "password": self.password},
            format="json",
        )
        access = signin.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_email_reset_request_and_confirm(self):
        req = self.client.post(
            "/api/v1/account/email-reset/",
            {"new_email": "new@example.com"},
            format="json",
        )
        self.assertEqual(req.status_code, status.HTTP_200_OK)
        self.assertIn("uid", req.data)
        self.assertIn("token", req.data)

        # Confirm change
        confirm = self.client.post(
            "/api/v1/account/email-reset/confirm/",
            {"uid": req.data["uid"], "token": req.data["token"]},
            format="json",
        )
        self.assertEqual(confirm.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new@example.com")
        self.assertTrue(self.user.email_verified)
