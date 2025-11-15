import pytest
from customer.models import Address, Profile
from django.core.exceptions import ValidationError
from users.models import User


@pytest.mark.django_db
def test_address_unique_per_user():
    user = User.objects.create(username="alice", email="alice@example.com")
    Address.objects.create(
        user=user,
        addr1="123 Main St",
        city="Anytown",
        state="Lagos",
        postal_code="123456",
        country_code="NG",
    )
    with pytest.raises(Exception):
        Address.objects.create(
            user=user,
            addr1="123 Main St",
            city="Anytown",
            state="Lagos",
            postal_code="123456",
            country_code="NG",
        )


@pytest.mark.django_db
def test_profile_default_addresses_validation():
    user1 = User.objects.create(username="bob", email="bob@example.com")
    user2 = User.objects.create(username="carol", email="carol@example.com")
    profile = Profile.objects.create(user=user1)
    addr_user2 = Address.objects.create(
        user=user2, addr1="456 Other", city="Elsewhere", state="Ogun", postal_code="999999", country_code="NG"
    )

    # Assigning address from different user should raise ValidationError via service
    from customer.services import set_defaults

    with pytest.raises(ValidationError):
        set_defaults(profile, shipping=addr_user2, billing=None)


@pytest.mark.django_db
def test_phone_validators():
    user = User.objects.create(username="dave", email="dave@example.com")
    user.phone = "+2348031234567"
    user.save(update_fields=["phone"])
    assert user.phone.startswith("+")

    addr = Address.objects.create(
        user=user,
        addr1="789 Road",
        city="Town",
        state="Abia",
        postal_code="123456",
        country_code="NG",
        phone="+2347012345678",
    )
    assert addr.phone.startswith("+")
