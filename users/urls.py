"""Aggregate user namespaces under /api/v1/.

This module re-exports the "auth" and "account" URLconfs so the project can
include a single users URL entry point without duplicating route definitions.
"""

from django.urls import include, path

urlpatterns = [
    path("auth/", include("users.auth_urls")),
    path("account/", include("users.account_urls")),
    path("admin/", include("users.admin_urls")),
]
