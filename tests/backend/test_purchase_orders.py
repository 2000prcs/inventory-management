"""
Tests for purchase order API endpoints.
"""
import pytest


@pytest.fixture(autouse=True)
def clear_purchase_orders():
    """Reset the in-memory purchase order store before and after each test."""
    from main import purchase_orders
    purchase_orders.clear()
    yield
    purchase_orders.clear()


@pytest.fixture
def backlog_item_id(client):
    """Return the id of the first backlog item."""
    backlog = client.get("/api/backlog").json()
    assert len(backlog) > 0
    return backlog[0]["id"]


def _payload(backlog_item_id, **overrides):
    """Build a valid purchase order payload."""
    payload = {
        "backlog_item_id": backlog_item_id,
        "supplier_name": "Acme Supply Co",
        "quantity": 350,
        "unit_cost": 12.5,
        "expected_delivery_date": "2026-08-15",
        "notes": "Rush order"
    }
    payload.update(overrides)
    return payload


class TestCreatePurchaseOrder:
    """Test suite for POST /api/purchase-orders."""

    def test_create_purchase_order(self, client, backlog_item_id):
        """Test raising a purchase order against a backlog item."""
        response = client.post("/api/purchase-orders", json=_payload(backlog_item_id))
        assert response.status_code == 200

        po = response.json()
        assert po["backlog_item_id"] == backlog_item_id
        assert po["supplier_name"] == "Acme Supply Co"
        assert po["quantity"] == 350
        assert po["unit_cost"] == 12.5
        assert po["expected_delivery_date"] == "2026-08-15"
        assert po["notes"] == "Rush order"
        assert po["status"] == "Pending"
        assert "id" in po
        assert "created_date" in po

    def test_create_purchase_order_without_notes(self, client, backlog_item_id):
        """Test that notes are optional."""
        payload = _payload(backlog_item_id)
        del payload["notes"]

        response = client.post("/api/purchase-orders", json=payload)
        assert response.status_code == 200
        assert response.json()["notes"] is None

    def test_create_purchase_order_nonexistent_backlog_item(self, client):
        """Test raising a purchase order against an unknown backlog item."""
        response = client.post("/api/purchase-orders", json=_payload("nonexistent-999"))
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_create_duplicate_purchase_order(self, client, backlog_item_id):
        """Test that a backlog item can only have one purchase order."""
        client.post("/api/purchase-orders", json=_payload(backlog_item_id))

        response = client.post("/api/purchase-orders", json=_payload(backlog_item_id))
        assert response.status_code == 400
        assert "already has" in response.json()["detail"].lower()

    def test_create_purchase_order_zero_quantity(self, client, backlog_item_id):
        """Test that a zero quantity is rejected."""
        response = client.post(
            "/api/purchase-orders", json=_payload(backlog_item_id, quantity=0)
        )
        assert response.status_code == 400
        assert "quantity" in response.json()["detail"].lower()

    def test_create_purchase_order_negative_quantity(self, client, backlog_item_id):
        """Test that a negative quantity is rejected."""
        response = client.post(
            "/api/purchase-orders", json=_payload(backlog_item_id, quantity=-5)
        )
        assert response.status_code == 400

    def test_create_purchase_order_missing_field(self, client, backlog_item_id):
        """Test that a missing required field returns a validation error."""
        payload = _payload(backlog_item_id)
        del payload["supplier_name"]

        response = client.post("/api/purchase-orders", json=payload)
        assert response.status_code == 422


class TestGetPurchaseOrder:
    """Test suite for GET /api/purchase-orders/{backlog_item_id}."""

    def test_get_purchase_order_by_backlog_item(self, client, backlog_item_id):
        """Test retrieving a purchase order by its backlog item id."""
        created = client.post(
            "/api/purchase-orders", json=_payload(backlog_item_id)
        ).json()

        response = client.get(f"/api/purchase-orders/{backlog_item_id}")
        assert response.status_code == 200
        assert response.json() == created

    def test_get_purchase_order_none_exists(self, client, backlog_item_id):
        """Test retrieving a purchase order that hasn't been raised."""
        response = client.get(f"/api/purchase-orders/{backlog_item_id}")
        assert response.status_code == 404
        assert "no purchase order" in response.json()["detail"].lower()


class TestBacklogPurchaseOrderFlag:
    """Test that /api/backlog reflects purchase order state."""

    def test_backlog_flag_false_initially(self, client, backlog_item_id):
        """Test that backlog items start without a purchase order."""
        backlog = client.get("/api/backlog").json()
        item = next(i for i in backlog if i["id"] == backlog_item_id)
        assert item["has_purchase_order"] is False

    def test_backlog_flag_true_after_create(self, client, backlog_item_id):
        """Test that raising a purchase order flips the backlog flag."""
        client.post("/api/purchase-orders", json=_payload(backlog_item_id))

        backlog = client.get("/api/backlog").json()
        item = next(i for i in backlog if i["id"] == backlog_item_id)
        assert item["has_purchase_order"] is True

    def test_backlog_flag_only_affects_target_item(self, client, backlog_item_id):
        """Test that other backlog items are unaffected."""
        client.post("/api/purchase-orders", json=_payload(backlog_item_id))

        backlog = client.get("/api/backlog").json()
        others = [i for i in backlog if i["id"] != backlog_item_id]
        assert len(others) > 0
        for item in others:
            assert item["has_purchase_order"] is False
