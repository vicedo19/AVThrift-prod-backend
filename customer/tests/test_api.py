import pytest
from customer.models import Address, Profile
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    User = get_user_model()
    return User.objects.create_user(
        username="alice", email="alice@example.com", password="pass1234", phone="+2348032222222"
    )


@pytest.fixture
def auth_client(api_client, user):
    access = AccessToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return api_client


def test_profile_get_returns_profile_and_shipping_contact(auth_client, user):
    # Create profile and a default shipping address without phone -> falls back to user.phone
    profile, _ = Profile.objects.get_or_create(user=user)
    addr = Address.objects.create(
        user=user,
        name="Ship To",
        addr1="123 Main",
        city="Lagos",
        state="Lagos",
        postal_code="123456",
        country_code="NG",
        phone="",  # trigger fallback
    )
    profile.default_shipping_address = addr
    profile.save(update_fields=["default_shipping_address"])

    url = "/api/v1/customer/profile/"
    resp = auth_client.get(url)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == profile.id
    assert data["shipping_address"] == addr.id
    assert data["shipping_contact"] == "+2348032222222"


def test_profile_patch_validates_address_ownership(auth_client, user):
    # Another user with an address
    User = get_user_model()
    other = User.objects.create_user(username="bob", email="bob@example.com", password="pass1234")
    other_addr = Address.objects.create(
        user=other,
        name="Bob Addr",
        addr1="456 Broad",
        city="Abuja",
        state="FCT",
        postal_code="654321",
        country_code="NG",
    )

    url = "/api/v1/customer/profile/"
    resp = auth_client.patch(url, {"shipping_address": other_addr.id}, format="json")
    assert resp.status_code == 400
    # Error structure may vary; ensure message presence
    body = resp.json()
    values = body.values() if isinstance(body, dict) else body
    assert any("address" in str(v).lower() or "profile" in str(v).lower() for v in values)


def test_addresses_list_scoped_to_user(auth_client, user):
    # Create two addresses for user and one for someone else
    Address.objects.create(
        user=user, name="A1", addr1="123", city="Lagos", state="Lagos", postal_code="111111", country_code="NG"
    )
    Address.objects.create(
        user=user, name="A2", addr1="456", city="Lagos", state="Lagos", postal_code="222222", country_code="NG"
    )

    User = get_user_model()
    other = User.objects.create_user(username="chris", email="chris@example.com", password="pass1234")
    Address.objects.create(
        user=other, name="Other", addr1="789", city="Abuja", state="FCT", postal_code="333333", country_code="NG"
    )

    url = "/api/v1/customer/addresses/"
    resp = auth_client.get(url)
    assert resp.status_code == 200
    data = resp.json()
    # ListAPIView default pagination may be disabled; handle both cases
    results = data.get("results", data)
    assert len(results) == 2
    for item in results:
        assert item["effective_contact_phone"] in (None, "+2348032222222")


def test_address_crud_flow(auth_client, user):
    # Create
    create = auth_client.post(
        "/api/v1/customer/addresses/",
        {
            "name": "John Doe",
            "addr1": "123 Main St",
            "city": "Lagos",
            "state": "Lagos",
            "postal_code": "123456",
            "country_code": "NG",
            "phone": "+2347012345678",
        },
        format="json",
    )
    assert create.status_code == 201
    addr_id = create.json()["id"]

    # Retrieve
    get = auth_client.get(f"/api/v1/customer/addresses/{addr_id}/")
    assert get.status_code == 200
    assert get.json()["phone"] == "+2347012345678"

    # Patch
    patch = auth_client.patch(f"/api/v1/customer/addresses/{addr_id}/", {"name": "JD"}, format="json")
    assert patch.status_code == 200
    assert patch.json()["name"] == "JD"

    # Delete
    delete = auth_client.delete(f"/api/v1/customer/addresses/{addr_id}/")
    assert delete.status_code == 204

    # Ensure gone
    gone = auth_client.get(f"/api/v1/customer/addresses/{addr_id}/")
    assert gone.status_code == 404


def test_delete_address_clears_profile_defaults(auth_client, user):
    # Prepare profile with defaults pointing to the same address
    profile, _ = Profile.objects.get_or_create(user=user)
    addr = Address.objects.create(
        user=user,
        name="Default",
        addr1="123",
        city="Lagos",
        state="Lagos",
        postal_code="111111",
        country_code="NG",
    )
    profile.default_shipping_address = addr
    profile.default_billing_address = addr
    profile.save(update_fields=["default_shipping_address", "default_billing_address"])

    # Delete address
    resp = auth_client.delete(f"/api/v1/customer/addresses/{addr.id}/")
    assert resp.status_code == 204

    # Refresh profile from DB and assert defaults cleared
    profile = Profile.objects.get(id=profile.id)
    assert profile.default_shipping_address_id is None
    assert profile.default_billing_address_id is None


def test_addresses_list_pagination_and_filters(auth_client, user):
    # Create multiple addresses to trigger pagination
    cities = ["Lagos", "Abuja", "Ibadan", "Lagos", "Kano", "Lagos", "Port Harcourt"]
    for i, c in enumerate(cities, start=1):
        Address.objects.create(
            user=user,
            name=f"A{i}",
            addr1=str(100 + i),
            city=c,
            state="State",
            postal_code=str(100000 + i),
            country_code="NG",
        )

    # Filter by city=Lagos and order by -updated_at
    url = "/api/v1/customer/addresses/?city=Lagos&ordering=-updated_at"
    resp = auth_client.get(url)
    assert resp.status_code == 200
    data = resp.json()
    results = data.get("results", data)
    # Expect only entries where city is Lagos
    assert all(item["city"] == "Lagos" for item in results)
    # If paginated, ensure count and page size constraints
    if isinstance(data, dict) and "count" in data:
        assert data["count"] == len([c for c in cities if c == "Lagos"])  # total filtered count
        # Page size is configured globally; ensure not exceeding it
        assert len(results) <= 20
