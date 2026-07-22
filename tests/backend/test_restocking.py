"""
Tests for the restocking endpoints and the demand forecast fields they depend on.
"""
from datetime import datetime

import pytest

import main


@pytest.fixture(autouse=True)
def clear_restock_orders():
    """Reset the in-memory store between tests so order numbers stay predictable."""
    main.submitted_restock_orders.clear()
    yield
    main.submitted_restock_orders.clear()


@pytest.fixture
def restock_items():
    """Two forecast-derived line items with differing lead times."""
    return [
        {"sku": "FLT-405", "name": "Oil Filter Cartridge", "quantity": 150,
         "unit_cost": 12.0, "lead_time_days": 7},
        {"sku": "GSK-203", "name": "High-Temperature Gasket", "quantity": 100,
         "unit_cost": 18.5, "lead_time_days": 10},
    ]


class TestDemandForecastRestockFields:
    """The Restocking tab cannot price anything without these fields."""

    def test_every_forecast_has_pricing_and_lead_time(self, client):
        response = client.get("/api/demand")
        assert response.status_code == 200

        forecasts = response.json()
        assert len(forecasts) > 0

        for forecast in forecasts:
            assert forecast["unit_cost"] is not None, f"{forecast['item_sku']} has no unit_cost"
            assert forecast["unit_cost"] > 0
            assert forecast["lead_time_days"] is not None, f"{forecast['item_sku']} has no lead_time_days"
            assert forecast["lead_time_days"] > 0

    def test_psu_501_price_matches_inventory(self, client):
        """PSU-501 exists in both datasets - a mismatch would show two prices for one SKU."""
        forecast = next(
            f for f in client.get("/api/demand").json() if f["item_sku"] == "PSU-501"
        )
        inventory_item = next(
            i for i in client.get("/api/inventory").json() if i["sku"] == "PSU-501"
        )
        assert forecast["unit_cost"] == inventory_item["unit_cost"]


class TestCreateRestockOrder:

    def test_creates_order_with_generated_number(self, client, restock_items):
        response = client.post("/api/restock-orders", json={"budget": 5000, "items": restock_items})
        assert response.status_code == 200

        order = response.json()
        assert order["order_number"] == "RST-2025-0001"
        assert order["status"] == "Submitted"
        assert order["budget"] == 5000
        assert len(order["items"]) == 2

    def test_total_value_computed_server_side(self, client, restock_items):
        """Totals are derived from the line items, not trusted from the client."""
        response = client.post("/api/restock-orders", json={"budget": 5000, "items": restock_items})

        expected = sum(item["quantity"] * item["unit_cost"] for item in restock_items)
        assert response.json()["total_value"] == round(expected, 2)

    def test_lead_time_is_max_across_items(self, client, restock_items):
        """An order is only complete when its slowest item lands."""
        response = client.post("/api/restock-orders", json={"budget": 5000, "items": restock_items})
        assert response.json()["lead_time_days"] == 10

    def test_expected_delivery_matches_lead_time(self, client, restock_items):
        order = client.post("/api/restock-orders", json={"budget": 5000, "items": restock_items}).json()

        submitted = datetime.fromisoformat(order["submitted_date"])
        delivery = datetime.fromisoformat(order["expected_delivery"])
        assert (delivery - submitted).days == order["lead_time_days"]

    def test_empty_items_rejected(self, client):
        response = client.post("/api/restock-orders", json={"budget": 5000, "items": []})
        assert response.status_code == 400

    def test_order_numbers_increment(self, client, restock_items):
        first = client.post("/api/restock-orders", json={"budget": 5000, "items": restock_items}).json()
        second = client.post("/api/restock-orders", json={"budget": 3000, "items": restock_items}).json()

        assert first["order_number"] == "RST-2025-0001"
        assert second["order_number"] == "RST-2025-0002"
        assert first["id"] != second["id"]


class TestGetRestockOrders:

    def test_empty_by_default(self, client):
        response = client.get("/api/restock-orders")
        assert response.status_code == 200
        assert response.json() == []

    def test_submitted_order_appears_in_list(self, client, restock_items):
        created = client.post("/api/restock-orders", json={"budget": 5000, "items": restock_items}).json()

        orders = client.get("/api/restock-orders").json()
        assert len(orders) == 1
        assert orders[0]["order_number"] == created["order_number"]

    def test_newest_first(self, client, restock_items):
        client.post("/api/restock-orders", json={"budget": 5000, "items": restock_items})
        client.post("/api/restock-orders", json={"budget": 3000, "items": restock_items})

        orders = client.get("/api/restock-orders").json()
        assert [o["order_number"] for o in orders] == ["RST-2025-0002", "RST-2025-0001"]
