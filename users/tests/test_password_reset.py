from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase


class PasswordResetTests(APITestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username="resetme",
            email="resetme@example.com",
            password="OldPass123!",
        )

    def test_password_reset_request_and_confirm(self):
        req = self.client.post(
            "/api/v1/account/password-reset/",
            {"email": self.user.email},
            format="json",
        )
        # Generic response; dev includes uid/token
        self.assertEqual(req.status_code, status.HTTP_200_OK)
        self.assertIn("uid", req.data)
        self.assertIn("token", req.data)

        confirm = self.client.post(
            "/api/v1/account/password-reset/confirm/",
            {"uid": req.data["uid"], "token": req.data["token"], "new_password": "NewPass123!"},
            format="json",
        )
        self.assertEqual(confirm.status_code, status.HTTP_200_OK)

        # Login with new password
        signin = self.client.post(
            "/api/v1/auth/signin/",
            {"identifier": self.user.email, "password": "NewPass123!"},
            format="json",
        )
        self.assertEqual(signin.status_code, status.HTTP_200_OK)
        self.assertIn("access", signin.data)
