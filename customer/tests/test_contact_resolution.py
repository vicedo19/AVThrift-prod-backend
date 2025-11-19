import pytest
from customer.models import Address, Profile
from customer.services import resolve_shipping_contact
from users.models import User


@pytest.mark.django_db
def test_resolve_shipping_contact_uses_address_override():
    user = User.objects.create(username="addr_override", email="override@example.com")
    profile = Profile.objects.create(user=user)
    address = Address.objects.create(
        user=user,
        addr1="1 Override St",
        city="Lagos",
        state="Lagos",
        postal_code="123456",
        country_code="NG",
        phone="+2347011111111",
    )

    phone = resolve_shipping_contact(profile, address)
    assert phone == "+2347011111111"


@pytest.mark.django_db
def test_resolve_shipping_contact_falls_back_to_profile():
    user = User.objects.create(username="fallback", email="fallback@example.com")
    user.phone = "+2348032222222"
    user.save(update_fields=["phone"])
    profile = Profile.objects.create(user=user)
    address = Address.objects.create(
        user=user,
        addr1="2 Fallback Rd",
        city="Abuja",
        state="FCT",
        postal_code="654321",
        country_code="NG",
        phone="",
    )

    phone = resolve_shipping_contact(profile, address)
    assert phone == "+2348032222222"


@pytest.mark.django_db
def test_resolve_shipping_contact_none_when_no_values():
    user = User.objects.create(username="none", email="none@example.com")
    profile = Profile.objects.create(user=user)
    address = Address.objects.create(
        user=user,
        addr1="3 Empty Ave",
        city="Ibadan",
        state="Oyo",
        postal_code="111111",
        country_code="NG",
        phone="",
    )

    phone = resolve_shipping_contact(profile, address)
    assert phone is None
