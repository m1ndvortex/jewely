"""
Tests for inventory reports.

Tests Requirement 9: Advanced Inventory Management
- Inventory valuation report
- Low stock alert report
- Dead stock analysis report
- Inventory turnover report

Tests Requirement 15: Advanced Reporting and Analytics
- Pre-built reports for inventory metrics
"""

from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

import pytest
from rest_framework import status

from apps.core.models import Branch, Tenant, User
from apps.inventory.models import InventoryItem, ProductCategory


@pytest.mark.django_db
class TestInventoryReports:
    """Test inventory reporting functionality."""

    @pytest.fixture
    def setup_data(self):
        """Set up test data for reports."""
        # Create tenant
        tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop", slug="test-shop", status="ACTIVE"
        )

        # Create user
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=tenant,
            role="TENANT_OWNER",
        )

        # Create branches
        branch1 = Branch.objects.create(
            tenant=tenant,
            name="Main Branch",
            address="123 Main St",
            phone="555-0001",
            is_active=True,
        )

        branch2 = Branch.objects.create(
            tenant=tenant,
            name="Second Branch",
            address="456 Second St",
            phone="555-0002",
            is_active=True,
        )

        # Create categories
        category1 = ProductCategory.objects.create(tenant=tenant, name="Rings", is_active=True)

        category2 = ProductCategory.objects.create(tenant=tenant, name="Necklaces", is_active=True)

        return {
            "tenant": tenant,
            "user": user,
            "branch1": branch1,
            "branch2": branch2,
            "category1": category1,
            "category2": category2,
        }

    def test_inventory_valuation_report(self, api_client, setup_data):
        """Test inventory valuation report generation."""
        # Create inventory items with different values
        InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="RING-001",
            name="Gold Ring",
            category=setup_data["category1"],
            branch=setup_data["branch1"],
            karat=18,
            weight_grams=Decimal("10.000"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1500.00"),
            quantity=5,
            min_quantity=2,
        )

        InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="NECK-001",
            name="Diamond Necklace",
            category=setup_data["category2"],
            branch=setup_data["branch2"],
            karat=24,
            weight_grams=Decimal("20.000"),
            cost_price=Decimal("5000.00"),
            selling_price=Decimal("7000.00"),
            quantity=2,
            min_quantity=1,
        )

        # Authenticate and make request
        api_client.force_authenticate(user=setup_data["user"])
        url = reverse("inventory:report_valuation")
        response = api_client.get(url)

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        assert response.data["report_type"] == "inventory_valuation"

        # Verify summary calculations
        summary = response.data["summary"]
        assert summary["total_items"] == 2
        assert summary["total_quantity"] == 7
        # Cost value: (1000 * 5) + (5000 * 2) = 15000
        assert summary["total_cost_value"] == 15000.0
        # Selling value: (1500 * 5) + (7000 * 2) = 21500
        assert summary["total_selling_value"] == 21500.0
        # Profit: 21500 - 15000 = 6500
        assert summary["potential_profit"] == 6500.0
        # Margin: 6500 / 15000 * 100 = 43.33%
        assert abs(summary["profit_margin_percentage"] - 43.33) < 0.1

        # Verify category breakdown
        assert len(response.data["by_category"]) == 2
        category_names = [cat["category"] for cat in response.data["by_category"]]
        assert "Rings" in category_names
        assert "Necklaces" in category_names

        # Verify branch breakdown
        assert len(response.data["by_branch"]) == 2
        branch_names = [br["branch"] for br in response.data["by_branch"]]
        assert "Main Branch" in branch_names
        assert "Second Branch" in branch_names

    def test_inventory_valuation_report_with_filters(self, api_client, setup_data):
        """Test inventory valuation report with branch filter."""
        # Create inventory items
        InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="RING-001",
            name="Gold Ring",
            category=setup_data["category1"],
            branch=setup_data["branch1"],
            karat=18,
            weight_grams=Decimal("10.000"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1500.00"),
            quantity=5,
            min_quantity=2,
        )

        InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="NECK-001",
            name="Diamond Necklace",
            category=setup_data["category2"],
            branch=setup_data["branch2"],
            karat=24,
            weight_grams=Decimal("20.000"),
            cost_price=Decimal("5000.00"),
            selling_price=Decimal("7000.00"),
            quantity=2,
            min_quantity=1,
        )

        # Authenticate and make request with branch filter
        api_client.force_authenticate(user=setup_data["user"])
        url = reverse("inventory:report_valuation")
        response = api_client.get(url, {"branch": str(setup_data["branch1"].id)})

        # Verify response - should only include branch1 items
        assert response.status_code == status.HTTP_200_OK
        summary = response.data["summary"]
        assert summary["total_items"] == 1
        assert summary["total_cost_value"] == 5000.0  # Only RING-001

    def test_low_stock_alert_report(self, api_client, setup_data):
        """Test low stock alert report generation."""
        # Create items with different stock levels
        # Out of stock item
        InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="RING-001",
            name="Gold Ring",
            category=setup_data["category1"],
            branch=setup_data["branch1"],
            karat=18,
            weight_grams=Decimal("10.000"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1500.00"),
            quantity=0,
            min_quantity=5,
        )

        # Low stock item
        InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="NECK-001",
            name="Diamond Necklace",
            category=setup_data["category2"],
            branch=setup_data["branch2"],
            karat=24,
            weight_grams=Decimal("20.000"),
            cost_price=Decimal("5000.00"),
            selling_price=Decimal("7000.00"),
            quantity=2,
            min_quantity=5,
        )

        # Normal stock item (should not appear in report)
        InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="RING-002",
            name="Silver Ring",
            category=setup_data["category1"],
            branch=setup_data["branch1"],
            karat=18,
            weight_grams=Decimal("8.000"),
            cost_price=Decimal("500.00"),
            selling_price=Decimal("750.00"),
            quantity=10,
            min_quantity=3,
        )

        # Authenticate and make request
        api_client.force_authenticate(user=setup_data["user"])
        url = reverse("inventory:report_low_stock")
        response = api_client.get(url)

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        assert response.data["report_type"] == "low_stock_alert"

        # Verify summary
        summary = response.data["summary"]
        assert summary["total_low_stock_items"] == 2
        assert summary["out_of_stock_count"] == 1
        assert summary["low_stock_count"] == 1

        # Verify out of stock items
        assert len(response.data["out_of_stock_items"]) == 1
        out_of_stock = response.data["out_of_stock_items"][0]
        assert out_of_stock["sku"] == "RING-001"
        assert out_of_stock["current_quantity"] == 0
        assert out_of_stock["shortage"] == 5

        # Verify low stock items
        assert len(response.data["low_stock_items"]) == 1
        low_stock = response.data["low_stock_items"][0]
        assert low_stock["sku"] == "NECK-001"
        assert low_stock["current_quantity"] == 2
        assert low_stock["shortage"] == 3

    def test_dead_stock_analysis_report(self, api_client, setup_data):
        """Test dead stock analysis report generation."""
        # Create items with different ages
        now = timezone.now()

        # Old item (dead stock - 100 days old)
        old_item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="RING-001",
            name="Old Gold Ring",
            category=setup_data["category1"],
            branch=setup_data["branch1"],
            karat=18,
            weight_grams=Decimal("10.000"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1500.00"),
            quantity=5,
            min_quantity=2,
        )
        # Manually set old date
        InventoryItem.objects.filter(id=old_item.id).update(updated_at=now - timedelta(days=100))

        # Recent item (not dead stock - 30 days old)
        recent_item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="NECK-001",
            name="New Diamond Necklace",
            category=setup_data["category2"],
            branch=setup_data["branch2"],
            karat=24,
            weight_grams=Decimal("20.000"),
            cost_price=Decimal("5000.00"),
            selling_price=Decimal("7000.00"),
            quantity=2,
            min_quantity=1,
        )
        # Manually set recent date
        InventoryItem.objects.filter(id=recent_item.id).update(updated_at=now - timedelta(days=30))

        # Authenticate and make request with 90-day threshold
        api_client.force_authenticate(user=setup_data["user"])
        url = reverse("inventory:report_dead_stock")
        response = api_client.get(url, {"days": "90"})

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        assert response.data["report_type"] == "dead_stock_analysis"

        # Verify summary - only old item should be in report
        summary = response.data["summary"]
        assert summary["total_dead_stock_items"] == 1

        # Verify dead stock items
        assert len(response.data["dead_stock_items"]) == 1
        dead_item = response.data["dead_stock_items"][0]
        assert dead_item["sku"] == "RING-001"
        assert dead_item["days_in_stock"] >= 90
        # Tied up capital: 1000 * 5 = 5000
        assert dead_item["tied_up_capital"] == 5000.0

    def test_inventory_turnover_report(self, api_client, setup_data):
        """Test inventory turnover report generation."""
        now = timezone.now()

        # Fast moving item (updated 5 days ago)
        fast_item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="RING-001",
            name="Popular Ring",
            category=setup_data["category1"],
            branch=setup_data["branch1"],
            karat=18,
            weight_grams=Decimal("10.000"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1500.00"),
            quantity=5,
            min_quantity=2,
        )
        InventoryItem.objects.filter(id=fast_item.id).update(updated_at=now - timedelta(days=5))

        # Slow moving item (updated 20 days ago)
        slow_item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="NECK-001",
            name="Slow Necklace",
            category=setup_data["category2"],
            branch=setup_data["branch2"],
            karat=24,
            weight_grams=Decimal("20.000"),
            cost_price=Decimal("5000.00"),
            selling_price=Decimal("7000.00"),
            quantity=2,
            min_quantity=1,
        )
        InventoryItem.objects.filter(id=slow_item.id).update(updated_at=now - timedelta(days=20))

        # No movement item (updated 50 days ago)
        no_move_item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="RING-002",
            name="Stagnant Ring",
            category=setup_data["category1"],
            branch=setup_data["branch1"],
            karat=18,
            weight_grams=Decimal("8.000"),
            cost_price=Decimal("500.00"),
            selling_price=Decimal("750.00"),
            quantity=3,
            min_quantity=1,
        )
        InventoryItem.objects.filter(id=no_move_item.id).update(updated_at=now - timedelta(days=50))

        # Authenticate and make request with 30-day period
        api_client.force_authenticate(user=setup_data["user"])
        url = reverse("inventory:report_turnover")
        response = api_client.get(url, {"period": "30"})

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        assert response.data["report_type"] == "inventory_turnover"

        # Verify summary
        summary = response.data["summary"]
        assert summary["total_items"] == 3
        assert summary["fast_moving_count"] == 1
        assert summary["slow_moving_count"] == 1
        assert summary["no_movement_count"] == 1

        # Verify category breakdown
        assert len(response.data["by_category"]) == 2

    def test_reports_require_authentication(self, api_client):
        """Test that all report endpoints require authentication."""
        endpoints = [
            "inventory:report_valuation",
            "inventory:report_low_stock",
            "inventory:report_dead_stock",
            "inventory:report_turnover",
        ]

        for endpoint in endpoints:
            url = reverse(endpoint)
            response = api_client.get(url)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_reports_respect_tenant_isolation(self, api_client, setup_data):
        """Test that reports only show data for the user's tenant."""
        # Create another tenant with data
        other_tenant = Tenant.objects.create(
            company_name="Other Shop", slug="other-shop", status="ACTIVE"
        )

        other_branch = Branch.objects.create(
            tenant=other_tenant,
            name="Other Branch",
            address="789 Other St",
            phone="555-9999",
            is_active=True,
        )

        other_category = ProductCategory.objects.create(
            tenant=other_tenant, name="Other Category", is_active=True
        )

        # Create item for other tenant
        InventoryItem.objects.create(
            tenant=other_tenant,
            sku="OTHER-001",
            name="Other Item",
            category=other_category,
            branch=other_branch,
            karat=18,
            weight_grams=Decimal("10.000"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1500.00"),
            quantity=5,
            min_quantity=2,
        )

        # Create item for test tenant
        InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="TEST-001",
            name="Test Item",
            category=setup_data["category1"],
            branch=setup_data["branch1"],
            karat=18,
            weight_grams=Decimal("10.000"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1500.00"),
            quantity=5,
            min_quantity=2,
        )

        # Authenticate as test tenant user
        api_client.force_authenticate(user=setup_data["user"])

        # Test valuation report
        url = reverse("inventory:report_valuation")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        # Should only see 1 item (from test tenant)
        assert response.data["summary"]["total_items"] == 1

    def test_low_stock_report_calculates_reorder_cost(self, api_client, setup_data):
        """Test that low stock report calculates reorder costs correctly."""
        # Create low stock item
        InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="RING-001",
            name="Gold Ring",
            category=setup_data["category1"],
            branch=setup_data["branch1"],
            karat=18,
            weight_grams=Decimal("10.000"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1500.00"),
            quantity=2,
            min_quantity=10,
        )

        # Authenticate and make request
        api_client.force_authenticate(user=setup_data["user"])
        url = reverse("inventory:report_low_stock")
        response = api_client.get(url)

        # Verify reorder cost calculation
        assert response.status_code == status.HTTP_200_OK
        low_stock_item = response.data["low_stock_items"][0]
        # Shortage: 10 - 2 = 8
        assert low_stock_item["shortage"] == 8
        # Reorder value: 1000 * 8 = 8000
        assert low_stock_item["reorder_value"] == 8000.0
        # Total reorder cost in summary
        assert response.data["summary"]["total_reorder_cost"] == 8000.0

    def test_dead_stock_report_with_custom_threshold(self, api_client, setup_data):
        """Test dead stock report with custom day threshold."""
        now = timezone.now()

        # Create item that's 60 days old
        item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="RING-001",
            name="Gold Ring",
            category=setup_data["category1"],
            branch=setup_data["branch1"],
            karat=18,
            weight_grams=Decimal("10.000"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1500.00"),
            quantity=5,
            min_quantity=2,
        )
        InventoryItem.objects.filter(id=item.id).update(updated_at=now - timedelta(days=60))

        # Authenticate
        api_client.force_authenticate(user=setup_data["user"])
        url = reverse("inventory:report_dead_stock")

        # Test with 90-day threshold - should not appear
        response = api_client.get(url, {"days": "90"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["summary"]["total_dead_stock_items"] == 0

        # Test with 30-day threshold - should appear
        response = api_client.get(url, {"days": "30"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["summary"]["total_dead_stock_items"] == 1

    def test_turnover_report_with_custom_period(self, api_client, setup_data):
        """Test turnover report with custom period."""
        now = timezone.now()

        # Create item updated 45 days ago
        item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="RING-001",
            name="Gold Ring",
            category=setup_data["category1"],
            branch=setup_data["branch1"],
            karat=18,
            weight_grams=Decimal("10.000"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1500.00"),
            quantity=5,
            min_quantity=2,
        )
        InventoryItem.objects.filter(id=item.id).update(updated_at=now - timedelta(days=45))

        # Authenticate
        api_client.force_authenticate(user=setup_data["user"])
        url = reverse("inventory:report_turnover")

        # Test with 30-day period - should be no movement
        response = api_client.get(url, {"period": "30"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["summary"]["no_movement_count"] == 1

        # Test with 60-day period - should be slow moving
        response = api_client.get(url, {"period": "60"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["summary"]["slow_moving_count"] == 1
