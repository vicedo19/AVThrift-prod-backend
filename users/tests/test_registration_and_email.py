from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase


class RegistrationAndEmailVerificationTests(APITestCase):
    def test_register_creates_user_and_returns_verification(self):
        payload = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "StrongPass123!",
            "first_name": "New",
            "last_name": "User",
        }
        resp = self.client.post("/api/v1/account/register/", payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("email_verification", resp.data)
        self.assertIn("uid", resp.data["email_verification"])  # dev convenience
        self.assertIn("token", resp.data["email_verification"])  # dev convenience

        User = get_user_model()
        user = User.objects.get(username="newuser")
        self.assertFalse(user.email_verified)

        # Confirm verification
        confirm = self.client.post(
            "/api/v1/account/email-verify/confirm/",
            resp.data["email_verification"],
            format="json",
        )
        self.assertEqual(confirm.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.email_verified)
