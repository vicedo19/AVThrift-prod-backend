import pytest
from cart.models import Cart, CartItem
from cart.tests.factories import UserFactory
from catalog.tests.factories import ProductVariantFactory
from django.db import IntegrityError


@pytest.mark.django_db
def test_unique_variant_per_cart_constraint():
    user = UserFactory()
    variant = ProductVariantFactory()
    # Create active cart for user
    cart, _ = Cart.objects.get_or_create(user=user, status=Cart.STATUS_ACTIVE)

    # Create one item
    CartItem.objects.create(cart=cart, variant=variant, quantity=1, unit_price=variant.price or 0)

    # Attempt to create duplicate item for same cart+variant should violate unique constraint
    with pytest.raises(IntegrityError):
        CartItem.objects.create(cart=cart, variant=variant, quantity=2, unit_price=variant.price or 0)


@pytest.mark.django_db
def test_quantity_positive_constraint():
    user = UserFactory()
    variant = ProductVariantFactory()
    cart, _ = Cart.objects.get_or_create(user=user, status=Cart.STATUS_ACTIVE)

    # Quantity of 0 should violate check constraint
    with pytest.raises(IntegrityError):
        CartItem.objects.create(cart=cart, variant=variant, quantity=0, unit_price=variant.price or 0)


@pytest.mark.django_db
def test_indexes_defined_for_cart_and_items():
    # Assert cart has index on (user, status)
    cart_index_fields = [tuple(idx.fields) for idx in Cart._meta.indexes]
    assert ("user", "status") in cart_index_fields

    # Assert cart item has index on (cart, variant)
    item_index_fields = [tuple(idx.fields) for idx in CartItem._meta.indexes]
    assert ("cart", "variant") in item_index_fields
