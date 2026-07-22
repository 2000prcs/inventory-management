"""
Tests for dashboard API endpoints.
"""
import pytest


class TestDashboardEndpoints:
    """Test suite for dashboard-related endpoints."""

    def test_get_dashboard_summary(self, client):
        """Test getting dashboard summary."""
        response = client.get("/api/dashboard/summary")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, dict)

        # Check required fields
        required_fields = [
            "total_inventory_value",
            "low_stock_items",
            "pending_orders",
            "total_backlog_items",
            "total_orders_value"
        ]

        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_dashboard_summary_data_types(self, client):
        """Test that dashboard summary has correct data types."""
        response = client.get("/api/dashboard/summary")
        data = response.json()

        assert isinstance(data["total_inventory_value"], (int, float))
        assert isinstance(data["low_stock_items"], int)
        assert isinstance(data["pending_orders"], int)
        assert isinstance(data["total_backlog_items"], int)
        assert isinstance(data["total_orders_value"], (int, float))

    def test_dashboard_summary_non_negative_values(self, client):
        """Test that dashboard summary values are non-negative."""
        response = client.get("/api/dashboard/summary")
        data = response.json()

        assert data["total_inventory_value"] >= 0
        assert data["low_stock_items"] >= 0
        assert data["pending_orders"] >= 0
        assert data["total_backlog_items"] >= 0
        assert data["total_orders_value"] >= 0

    def test_dashboard_summary_with_warehouse_filter(self, client):
        """Test dashboard summary with warehouse filter."""
        response = client.get("/api/dashboard/summary?warehouse=San Francisco")
        assert response.status_code == 200

        data = response.json()
        assert "total_inventory_value" in data
        assert "total_orders_value" in data

    def test_dashboard_summary_with_category_filter(self, client):
        """Test dashboard summary with category filter."""
        response = client.get("/api/dashboard/summary?category=Sensors")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, dict)

    def test_dashboard_summary_with_status_filter(self, client):
        """Test dashboard summary with status filter."""
        response = client.get("/api/dashboard/summary?status=Processing")
        assert response.status_code == 200

        data = response.json()
        # Pending orders should reflect the filter
        assert "pending_orders" in data

    def test_dashboard_summary_with_month_filter(self, client):
        """Test dashboard summary with month filter."""
        response = client.get("/api/dashboard/summary?month=2025-01")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, dict)

    def test_dashboard_summary_with_multiple_filters(self, client):
        """Test dashboard summary with multiple filters."""
        response = client.get(
            "/api/dashboard/summary?warehouse=London&category=Sensors&status=Delivered&month=2025-01"
        )
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, dict)
        # All required fields should still be present
        assert "total_inventory_value" in data
        assert "total_orders_value" in data

    def test_dashboard_summary_with_all_filters(self, client):
        """Test that 'all' filter values work correctly."""
        response = client.get(
            "/api/dashboard/summary?warehouse=all&category=all&status=all&month=all"
        )
        assert response.status_code == 200

        # Should return same as no filters
        response_no_filter = client.get("/api/dashboard/summary")
        assert response.json() == response_no_filter.json()

    def test_dashboard_summary_power_supplies_filter(self, client):
        """Test dashboard summary with Power Supplies category filter."""
        response = client.get("/api/dashboard/summary?category=Power Supplies")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, dict)
        # Should have inventory value for Power Supplies items
        assert data["total_inventory_value"] >= 0

    def test_dashboard_pending_orders_calculation(self, client):
        """Test that pending orders are calculated correctly."""
        # Get all orders
        orders_response = client.get("/api/orders")
        all_orders = orders_response.json()

        # Count processing and backordered orders
        pending_count = sum(
            1 for order in all_orders
            if order["status"].lower() in ["processing", "backordered"]
        )

        # Get dashboard summary
        dashboard_response = client.get("/api/dashboard/summary")
        dashboard_data = dashboard_response.json()

        assert dashboard_data["pending_orders"] == pending_count

    def test_dashboard_low_stock_items_calculation(self, client):
        """Test that low stock items are calculated correctly."""
        # Get all inventory
        inventory_response = client.get("/api/inventory")
        all_inventory = inventory_response.json()

        # Count items at or below reorder point
        low_stock_count = sum(
            1 for item in all_inventory
            if item["quantity_on_hand"] <= item["reorder_point"]
        )

        # Get dashboard summary
        dashboard_response = client.get("/api/dashboard/summary")
        dashboard_data = dashboard_response.json()

        assert dashboard_data["low_stock_items"] == low_stock_count

    def test_dashboard_inventory_value_calculation(self, client):
        """Test that total inventory value is calculated correctly."""
        # Get all inventory
        inventory_response = client.get("/api/inventory")
        all_inventory = inventory_response.json()

        # Calculate total value
        expected_value = sum(
            item["quantity_on_hand"] * item["unit_cost"]
            for item in all_inventory
        )

        # Get dashboard summary
        dashboard_response = client.get("/api/dashboard/summary")
        dashboard_data = dashboard_response.json()

        # Allow small floating point differences
        assert abs(dashboard_data["total_inventory_value"] - expected_value) < 0.01


class TestDashboardKPIs:
    """Test suite for the derived headline KPIs on the dashboard summary."""

    def test_summary_includes_kpi_fields(self, client):
        """Test that the summary exposes the headline KPI fields."""
        data = client.get("/api/dashboard/summary").json()

        for field in [
            "orders_fulfilled",
            "total_orders",
            "fill_rate",
            "avg_processing_days",
            "inventory_turnover",
        ]:
            assert field in data

    def test_orders_fulfilled_matches_delivered_orders(self, client):
        """Test that orders_fulfilled equals the delivered order count."""
        orders = client.get("/api/orders").json()
        delivered = len([o for o in orders if o["status"] == "Delivered"])

        data = client.get("/api/dashboard/summary").json()
        assert data["orders_fulfilled"] == delivered

    def test_total_orders_matches_orders_endpoint(self, client):
        """Test that total_orders matches the full order list."""
        orders = client.get("/api/orders").json()
        data = client.get("/api/dashboard/summary").json()
        assert data["total_orders"] == len(orders)

    def test_fill_rate_excludes_only_backordered(self, client):
        """Test that fill rate counts everything except backordered as filled."""
        orders = client.get("/api/orders").json()
        backordered = len([o for o in orders if o["status"] == "Backordered"])
        expected = round(((len(orders) - backordered) / len(orders)) * 100, 1)

        data = client.get("/api/dashboard/summary").json()
        assert data["fill_rate"] == expected

    def test_fill_rate_is_a_percentage(self, client):
        """Test that fill rate stays within 0-100."""
        data = client.get("/api/dashboard/summary").json()
        assert 0 <= data["fill_rate"] <= 100

    def test_avg_processing_days_is_positive(self, client):
        """Test that average processing time is a sane positive number."""
        data = client.get("/api/dashboard/summary").json()
        assert data["avg_processing_days"] > 0

    def test_kpis_respond_to_warehouse_filter(self, client):
        """Test that KPIs are recalculated for a filtered order set."""
        unfiltered = client.get("/api/dashboard/summary").json()
        filtered = client.get("/api/dashboard/summary?warehouse=Tokyo").json()

        tokyo_orders = client.get("/api/orders?warehouse=Tokyo").json()
        assert filtered["total_orders"] == len(tokyo_orders)
        assert filtered["total_orders"] < unfiltered["total_orders"]

    def test_kpis_respond_to_status_filter(self, client):
        """Test that filtering to delivered orders yields a 100% fill rate."""
        data = client.get("/api/dashboard/summary?status=Delivered").json()
        assert data["fill_rate"] == 100.0
        assert data["orders_fulfilled"] == data["total_orders"]

    def test_kpis_handle_empty_order_set(self, client):
        """Test that KPIs degrade gracefully when nothing matches."""
        data = client.get("/api/dashboard/summary?warehouse=Atlantis").json()

        assert data["total_orders"] == 0
        assert data["orders_fulfilled"] == 0
        assert data["fill_rate"] == 0
        assert data["avg_processing_days"] == 0
