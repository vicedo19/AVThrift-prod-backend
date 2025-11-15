"""Custom throttles for the catalog app.

Overrides DRF's ScopedRateThrottle rate lookup to read from Django settings
at request-time, so tests using override_settings reliably affect rates.
"""

from django.conf import settings
from rest_framework.throttling import ScopedRateThrottle


class CatalogScopedRateThrottle(ScopedRateThrottle):
    def get_rate(self):
        rf = getattr(settings, "REST_FRAMEWORK", {})
        rates = rf.get("DEFAULT_THROTTLE_RATES", {})
        return rates.get(self.scope)

    def get_ident(self, request):
        # Prefer per-session identity to avoid cross-test interference with anonymous IP-based throttling.
        session = getattr(request, "session", None)
        if session is not None:
            if not session.session_key:
                try:
                    session.save()
                except Exception:
                    # Fall back to IP-based ident if session cannot be initialized
                    pass
            if session.session_key:
                return session.session_key
        return super().get_ident(request)
