from .base import BASE_DIR
from .base import REST_FRAMEWORK as BASE_REST_FRAMEWORK

# Test settings: force SQLite to avoid MySQL-specific FK issues during CI/pytest
DEBUG = False

# Use a local SQLite database for reliability and speed in tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test_db.sqlite3",
    }
}

# Keep console email backend in tests
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Slightly relax throttling for tests to reduce flakiness
REST_FRAMEWORK = {**BASE_REST_FRAMEWORK}
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    **BASE_REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}),
    "cart": "1000/min",
    "cart_write": "1000/min",
    "orders": "1000/min",
    "orders_write": "1000/min",
}
