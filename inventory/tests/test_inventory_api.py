import pytest
from catalog.tests.factories import ProductVariantFactory
from inventory.models import StockItem, StockMovement, StockReservation


@pytest.mark.django_db
def test_stock_items_list_basic(client):
    v1 = ProductVariantFactory(sku="SKU-TEST-001")
    v2 = ProductVariantFactory(sku="SKU-TEST-002")
    StockItem.objects.create(variant=v1, quantity=10, reserved=4)
    StockItem.objects.create(variant=v2, quantity=5, reserved=0)

    resp = client.get("/api/v1/inventory/stock-items/")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict) and "results" in data
    skus = [row["sku"] for row in data["results"]]
    assert "SKU-TEST-001" in skus and "SKU-TEST-002" in skus
    item1 = next(row for row in data["results"] if row["sku"] == "SKU-TEST-001")
    assert item1["available"] == 6


@pytest.mark.django_db
def test_movements_list_filters(client):
    v = ProductVariantFactory()
    si = StockItem.objects.create(variant=v, quantity=10, reserved=0)
    m_in = StockMovement.objects.create(stock_item=si, movement_type=StockMovement.TYPE_INBOUND, quantity=5)
    m_out = StockMovement.objects.create(stock_item=si, movement_type=StockMovement.TYPE_OUTBOUND, quantity=2)

    resp_all = client.get("/api/v1/inventory/movements/")
    assert resp_all.status_code == 200
    all_ids = {row["id"] for row in resp_all.json()["results"]}
    assert m_in.id in all_ids and m_out.id in all_ids

    resp_in = client.get(f"/api/v1/inventory/movements/?movement_type={StockMovement.TYPE_INBOUND}")
    assert resp_in.status_code == 200
    in_ids = {row["id"] for row in resp_in.json()["results"]}
    assert m_in.id in in_ids and m_out.id not in in_ids


@pytest.mark.django_db
def test_reservations_list_filters(client):
    v = ProductVariantFactory()
    r1 = StockReservation.objects.create(variant=v, quantity=1, reference="A", state=StockReservation.STATE_ACTIVE)
    r2 = StockReservation.objects.create(variant=v, quantity=2, reference="B", state=StockReservation.STATE_RELEASED)

    resp_active = client.get(f"/api/v1/inventory/reservations/?state={StockReservation.STATE_ACTIVE}")
    assert resp_active.status_code == 200
    active_ids = {row["id"] for row in resp_active.json()["results"]}
    assert r1.id in active_ids and r2.id not in active_ids


# EOF
