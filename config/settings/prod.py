import sentry_sdk
from decouple import Csv, config
from sentry_sdk.integrations.django import DjangoIntegration

from .base import REST_FRAMEWORK as BASE_REST_FRAMEWORK
from .base import *  # noqa

DEBUG = False

# Require explicit secret key and hosts in production
SECRET_KEY = config("SECRET_KEY")
ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="", cast=Csv())
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())
CORS_ALLOW_CREDENTIALS = config("CORS_ALLOW_CREDENTIALS", default=True, cast=bool)
SESSION_COOKIE_SAMESITE = config("SESSION_COOKIE_SAMESITE", default="Lax")
CSRF_COOKIE_SAMESITE = config("CSRF_COOKIE_SAMESITE", default="Lax")

# Security hardening (tune for DO App Platform / Droplets)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Email: default to SMTP backend in production (override via env if needed)
EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)

# Cache: use Redis in production when REDIS_URL is provided; otherwise keep base cache
_REDIS_URL = config("REDIS_URL", default="")
if _REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _REDIS_URL,
        }
    }

# Sessions: cached_db stores sessions in DB with cache acceleration
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

# Logging: JSON output with contextual extras
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "config.logging.JsonFormatter",
        },
    },
    "filters": {
        # Sample INFO logs for orders to reduce noise, while never sampling
        # explicit event names we consider critical for auditability.
        "orders_info_sample": {
            "()": "config.logging.SamplingFilter",
            "rate": config("ORDERS_LOG_SAMPLE_RATE", default=1.0, cast=float),
            "levels": ["INFO"],
            "allow_events": ["order_status_changed"],
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
        "orders_console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["orders_info_sample"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "auth": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "avthrift.cart": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        # Orders logger uses a dedicated handler with sampling
        "avthrift.orders": {
            "handlers": ["orders_console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Sentry
SENTRY_DSN = config("SENTRY_DSN", default="")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=config("SENTRY_ENV", default="production"),
        integrations=[DjangoIntegration()],
        traces_sample_rate=config("SENTRY_TRACES_SAMPLE_RATE", default=0.0, cast=float),
        send_default_pii=config("SENTRY_SEND_DEFAULT_PII", default=True, cast=bool),
    )

# DRF throttling scopes for cart and orders endpoints in production
REST_FRAMEWORK = {**BASE_REST_FRAMEWORK}
_rates = {**BASE_REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})}
_rates.update(
    {
        # Use minute-based units consistent with base settings; reads > writes
        "cart": "120/min",
        "cart_write": "60/min",
        "orders": "60/min",
        "orders_write": "30/min",
    }
)
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = _rates
