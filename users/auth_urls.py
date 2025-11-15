"""Authentication routes grouped under /api/auth.

Includes JWT obtain (login), refresh, verify, and logout (blacklist).
"""

from django.urls import path

from .views import RefreshView, SignInView, SignOutView, VerifyView

urlpatterns = [
    path("signin/", SignInView.as_view(), name="signin"),
    path("refresh/", RefreshView.as_view(), name="token_refresh"),
    path("verify/", VerifyView.as_view(), name="token_verify"),
    path("signout/", SignOutView.as_view(), name="signout"),
]
