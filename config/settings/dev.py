from decouple import config as _config

from .base import REST_FRAMEWORK as BASE_REST_FRAMEWORK
from .base import *  # noqa

DEBUG = True

# In dev, allow the browsable API and relaxed CORS
CORS_ALLOW_ALL_ORIGINS = True

# Email backend for dev
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Optional Redis cache for local parity

_REDIS_URL = _config("REDIS_URL", default="")
if _REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _REDIS_URL,
        }
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

# DRF throttling scopes for cart and orders endpoints in development
REST_FRAMEWORK = {**BASE_REST_FRAMEWORK}
_rates = {**BASE_REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})}
_rates.update(
    {
        # Use minute-based units consistent with base; reads > writes
        "cart": "120/min",
        "cart_write": "60/min",
        "orders": "60/min",
        "orders_write": "30/min",
    }
)
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = _rates
