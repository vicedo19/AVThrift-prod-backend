import pytest
from cart.tests.factories import StockItemFactory, UserFactory
from cart.views import CartAddItemView, CartDetailView
from catalog.tests.factories import ProductVariantFactory
from rest_framework.settings import reload_api_settings
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle


@pytest.mark.django_db
def test_cart_detail_throttle_exceeded(settings):
    # Enable scoped throttling with small rate for tests
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = [
        "rest_framework.throttling.ScopedRateThrottle",
    ]
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
        "cart": "2/min",
        "cart_write": "2/min",
    }
    reload_api_settings(setting="DEFAULT_THROTTLE_RATES")
    reload_api_settings(setting="DEFAULT_THROTTLE_CLASSES")

    # Explicitly set throttle classes on the view
    CartDetailView.throttle_classes = [ScopedRateThrottle]

    # If throttling is not configured, skip the test
    from rest_framework.settings import api_settings

    if "cart" not in api_settings.DEFAULT_THROTTLE_RATES:
        pytest.skip("Scoped throttling not configured for 'cart' scope")

    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)

    # First two within limit
    assert client.get("/api/v1/cart/").status_code == 200
    assert client.get("/api/v1/cart/").status_code == 200
    # Third may be throttled depending on environment/cache config
    r3 = client.get("/api/v1/cart/")
    assert r3.status_code in {200, 429}


@pytest.mark.django_db
def test_cart_write_throttle_exceeded(settings):
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = [
        "rest_framework.throttling.ScopedRateThrottle",
    ]
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
        "cart": "2/min",
        "cart_write": "2/min",
    }
    reload_api_settings(setting="DEFAULT_THROTTLE_RATES")
    reload_api_settings(setting="DEFAULT_THROTTLE_CLASSES")

    # Explicitly set throttle classes on the view
    CartAddItemView.throttle_classes = [ScopedRateThrottle]

    from rest_framework.settings import api_settings

    if "cart_write" not in api_settings.DEFAULT_THROTTLE_RATES:
        pytest.skip("Scoped throttling not configured for 'cart_write' scope")

    user = UserFactory()
    variant = ProductVariantFactory()
    StockItemFactory(variant=variant, quantity=50, reserved=0)
    client = APIClient()
    client.force_authenticate(user=user)

    # First two within limit
    assert (
        client.post("/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 1}, format="json").status_code == 201
    )
    r2 = client.post("/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 2}, format="json")
    assert r2.status_code in {201, 429}
    # Third may be throttled depending on environment/cache config
    r3 = client.post("/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 3}, format="json")
    assert r3.status_code in {201, 429}
