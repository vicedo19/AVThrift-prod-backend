import pytest
from cart.tests.factories import UserFactory
from orders.models import Order
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_pay_order_idempotent():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)

    order = Order.objects.create(user=user)
    key = "idem-pay-123"

    r1 = client.post(f"/api/v1/orders/{order.id}/pay/", HTTP_IDEMPOTENCY_KEY=key)
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["id"] == order.id
    assert body1["status"] == Order.STATUS_PAID

    r2 = client.post(f"/api/v1/orders/{order.id}/pay/", HTTP_IDEMPOTENCY_KEY=key)
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["id"] == body1["id"]
    assert body2["status"] == body1["status"]


@pytest.mark.django_db
def test_cancel_order_idempotent():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)

    order = Order.objects.create(user=user)
    key = "idem-cancel-123"

    r1 = client.post(f"/api/v1/orders/{order.id}/cancel/", HTTP_IDEMPOTENCY_KEY=key)
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["id"] == order.id
    assert body1["status"] == Order.STATUS_CANCELLED

    r2 = client.post(f"/api/v1/orders/{order.id}/cancel/", HTTP_IDEMPOTENCY_KEY=key)
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["id"] == body1["id"]
    assert body2["status"] == body1["status"]


@pytest.mark.django_db
def test_guards_cannot_cancel_paid_cannot_pay_cancelled():
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)

    order = Order.objects.create(user=user)

    # Pay then cancel should error
    rp = client.post(f"/api/v1/orders/{order.id}/pay/")
    assert rp.status_code == 200
    rc = client.post(f"/api/v1/orders/{order.id}/cancel/")
    assert rc.status_code == 400
    assert rc.json()["detail"] == "Unable to update order."

    # Make a new order, cancel then pay should error
    order2 = Order.objects.create(user=user)
    rc2 = client.post(f"/api/v1/orders/{order2.id}/cancel/")
    assert rc2.status_code == 200
    rp2 = client.post(f"/api/v1/orders/{order2.id}/pay/")
    assert rp2.status_code == 400
    assert rp2.json()["detail"] == "Unable to update order."


@pytest.mark.django_db
def test_ownership_required():
    owner = UserFactory()
    other = UserFactory()
    client = APIClient()
    client.force_authenticate(user=other)

    order = Order.objects.create(user=owner)
    r = client.post(f"/api/v1/orders/{order.id}/pay/")
    assert r.status_code == 404
