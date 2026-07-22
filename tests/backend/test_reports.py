"""
Tests for reports API endpoints.
"""
import pytest


class TestQuarterlyReportsEndpoint:
    """Test suite for the /api/reports/quarterly endpoint."""

    def test_get_quarterly_reports(self, client):
        """Test getting quarterly reports without filters."""
        response = client.get("/api/reports/quarterly")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        first_quarter = data[0]
        assert "quarter" in first_quarter
        assert "total_orders" in first_quarter
        assert "total_revenue" in first_quarter
        assert "avg_order_value" in first_quarter
        assert "fulfillment_rate" in first_quarter

    def test_quarterly_reports_are_sorted(self, client):
        """Test that quarters come back in chronological order."""
        response = client.get("/api/reports/quarterly")
        data = response.json()

        quarters = [q["quarter"] for q in data]
        assert quarters == sorted(quarters)

    def test_quarterly_reports_value_types(self, client):
        """Test that quarterly numeric fields have proper types and ranges."""
        response = client.get("/api/reports/quarterly")
        data = response.json()

        for quarter in data:
            assert isinstance(quarter["total_orders"], int)
            assert isinstance(quarter["total_revenue"], (int, float))
            assert isinstance(quarter["avg_order_value"], (int, float))
            assert isinstance(quarter["fulfillment_rate"], (int, float))
            assert quarter["total_orders"] > 0
            assert quarter["total_revenue"] >= 0
            assert 0 <= quarter["fulfillment_rate"] <= 100

    def test_quarterly_avg_order_value_calculation(self, client):
        """Test that avg_order_value equals revenue divided by order count."""
        response = client.get("/api/reports/quarterly")
        data = response.json()

        for quarter in data:
            expected = quarter["total_revenue"] / quarter["total_orders"]
            assert abs(quarter["avg_order_value"] - expected) < 0.01

    def test_quarterly_totals_match_orders_endpoint(self, client):
        """Test that quarterly order counts sum to the full order list."""
        orders = client.get("/api/orders").json()
        data = client.get("/api/reports/quarterly").json()

        assert sum(q["total_orders"] for q in data) == len(orders)

    def test_get_quarterly_by_warehouse(self, client):
        """Test filtering quarterly reports by warehouse."""
        response = client.get("/api/reports/quarterly?warehouse=Tokyo")
        assert response.status_code == 200

        data = response.json()
        expected = len(client.get("/api/orders?warehouse=Tokyo").json())
        assert sum(q["total_orders"] for q in data) == expected

    def test_get_quarterly_by_category(self, client):
        """Test filtering quarterly reports by category."""
        response = client.get("/api/reports/quarterly?category=Sensors")
        assert response.status_code == 200

        data = response.json()
        expected = len(client.get("/api/orders?category=Sensors").json())
        assert sum(q["total_orders"] for q in data) == expected

    def test_get_quarterly_by_status(self, client):
        """Test filtering quarterly reports by status."""
        response = client.get("/api/reports/quarterly?status=Delivered")
        assert response.status_code == 200

        data = response.json()
        expected = len(client.get("/api/orders?status=Delivered").json())
        assert sum(q["total_orders"] for q in data) == expected

        # Filtering to delivered orders only makes every quarter fully fulfilled
        for quarter in data:
            assert quarter["fulfillment_rate"] == 100.0

    def test_get_quarterly_by_month_narrows_to_one_quarter(self, client):
        """Test that a single-month filter returns only that month's quarter."""
        response = client.get("/api/reports/quarterly?month=2025-03")
        assert response.status_code == 200

        data = response.json()
        assert [q["quarter"] for q in data] == ["Q1-2025"]

    def test_get_quarterly_by_quarter(self, client):
        """Test filtering quarterly reports by a quarter value."""
        response = client.get("/api/reports/quarterly?month=Q2-2025")
        assert response.status_code == 200

        data = response.json()
        assert [q["quarter"] for q in data] == ["Q2-2025"]

    def test_get_quarterly_multiple_filters(self, client):
        """Test filtering quarterly reports with multiple filters combined."""
        query = "warehouse=Tokyo&category=Sensors&status=Delivered"
        response = client.get(f"/api/reports/quarterly?{query}")
        assert response.status_code == 200

        data = response.json()
        expected = len(client.get(f"/api/orders?{query}").json())
        assert sum(q["total_orders"] for q in data) == expected

    def test_get_quarterly_all_is_unfiltered(self, client):
        """Test that 'all' filter values are treated as no filter."""
        unfiltered = client.get("/api/reports/quarterly").json()
        response = client.get(
            "/api/reports/quarterly?warehouse=all&category=all&status=all&month=all"
        )
        assert response.status_code == 200
        assert response.json() == unfiltered

    def test_get_quarterly_no_matches_returns_empty(self, client):
        """Test that a filter matching nothing returns an empty list."""
        response = client.get("/api/reports/quarterly?warehouse=Atlantis")
        assert response.status_code == 200
        assert response.json() == []


class TestMonthlyTrendsEndpoint:
    """Test suite for the /api/reports/monthly-trends endpoint."""

    def test_get_monthly_trends(self, client):
        """Test getting monthly trends without filters."""
        response = client.get("/api/reports/monthly-trends")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        first_month = data[0]
        assert "month" in first_month
        assert "order_count" in first_month
        assert "revenue" in first_month
        assert "delivered_count" in first_month

    def test_monthly_trends_are_sorted(self, client):
        """Test that months come back in chronological order."""
        response = client.get("/api/reports/monthly-trends")
        data = response.json()

        months = [m["month"] for m in data]
        assert months == sorted(months)

    def test_monthly_trends_month_format(self, client):
        """Test that month keys use YYYY-MM format."""
        response = client.get("/api/reports/monthly-trends")
        data = response.json()

        for entry in data:
            assert len(entry["month"]) == 7
            year, month = entry["month"].split("-")
            assert year == "2025"
            assert 1 <= int(month) <= 12

    def test_monthly_trends_value_types(self, client):
        """Test that monthly numeric fields have proper types and ranges."""
        response = client.get("/api/reports/monthly-trends")
        data = response.json()

        for entry in data:
            assert isinstance(entry["order_count"], int)
            assert isinstance(entry["revenue"], (int, float))
            assert isinstance(entry["delivered_count"], int)
            assert entry["order_count"] > 0
            assert entry["revenue"] >= 0
            assert 0 <= entry["delivered_count"] <= entry["order_count"]

    def test_monthly_totals_match_orders_endpoint(self, client):
        """Test that monthly order counts sum to the full order list."""
        orders = client.get("/api/orders").json()
        data = client.get("/api/reports/monthly-trends").json()

        assert sum(m["order_count"] for m in data) == len(orders)

    def test_monthly_revenue_matches_quarterly_revenue(self, client):
        """Test that monthly and quarterly revenue agree on the same orders."""
        monthly = client.get("/api/reports/monthly-trends").json()
        quarterly = client.get("/api/reports/quarterly").json()

        monthly_total = sum(m["revenue"] for m in monthly)
        quarterly_total = sum(q["total_revenue"] for q in quarterly)
        assert abs(monthly_total - quarterly_total) < 0.01

    def test_get_monthly_trends_by_warehouse(self, client):
        """Test filtering monthly trends by warehouse."""
        response = client.get("/api/reports/monthly-trends?warehouse=London")
        assert response.status_code == 200

        data = response.json()
        expected = len(client.get("/api/orders?warehouse=London").json())
        assert sum(m["order_count"] for m in data) == expected

    def test_get_monthly_trends_by_category(self, client):
        """Test filtering monthly trends by category."""
        response = client.get("/api/reports/monthly-trends?category=Sensors")
        assert response.status_code == 200

        data = response.json()
        expected = len(client.get("/api/orders?category=Sensors").json())
        assert sum(m["order_count"] for m in data) == expected

    def test_get_monthly_trends_by_status(self, client):
        """Test filtering monthly trends by status."""
        response = client.get("/api/reports/monthly-trends?status=Delivered")
        assert response.status_code == 200

        data = response.json()
        expected = len(client.get("/api/orders?status=Delivered").json())
        assert sum(m["order_count"] for m in data) == expected

        # Every remaining order is delivered
        for entry in data:
            assert entry["delivered_count"] == entry["order_count"]

    def test_get_monthly_trends_by_month(self, client):
        """Test that a single-month filter returns only that month."""
        response = client.get("/api/reports/monthly-trends?month=2025-03")
        assert response.status_code == 200

        data = response.json()
        assert [m["month"] for m in data] == ["2025-03"]

    def test_get_monthly_trends_by_quarter(self, client):
        """Test that a quarter filter returns only that quarter's months."""
        response = client.get("/api/reports/monthly-trends?month=Q1-2025")
        assert response.status_code == 200

        data = response.json()
        assert [m["month"] for m in data] == ["2025-01", "2025-02", "2025-03"]

    def test_get_monthly_trends_multiple_filters(self, client):
        """Test filtering monthly trends with multiple filters combined."""
        query = "warehouse=Tokyo&category=Sensors&status=Delivered"
        response = client.get(f"/api/reports/monthly-trends?{query}")
        assert response.status_code == 200

        data = response.json()
        expected = len(client.get(f"/api/orders?{query}").json())
        assert sum(m["order_count"] for m in data) == expected

    def test_get_monthly_trends_all_is_unfiltered(self, client):
        """Test that 'all' filter values are treated as no filter."""
        unfiltered = client.get("/api/reports/monthly-trends").json()
        response = client.get(
            "/api/reports/monthly-trends?warehouse=all&category=all&status=all&month=all"
        )
        assert response.status_code == 200
        assert response.json() == unfiltered

    def test_get_monthly_trends_no_matches_returns_empty(self, client):
        """Test that a filter matching nothing returns an empty list."""
        response = client.get("/api/reports/monthly-trends?warehouse=Atlantis")
        assert response.status_code == 200
        assert response.json() == []
