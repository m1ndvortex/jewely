"""
Tests for core dashboard functionality.

Implements Task 12.3: Create interactive dashboards
- Test tenant dashboard view
- Test dashboard API endpoints
- Test KPI calculations
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


from apps.core.models import Branch, Tenant
from apps.inventory.models import InventoryItem, ProductCategory
from apps.sales.models import Customer, Sale, SaleItem, Terminal

User = get_user_model()


class TenantDashboardTestCase(TestCase):
    """Test cases for the tenant dashboard functionality."""

    def setUp(self):
        """Set up test data."""
        # Enable RLS bypass for tests
        from apps.core.tenant_context import enable_rls_bypass

        enable_rls_bypass()

        # Create tenant
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop", slug="test-jewelry-shop"
        )

        # Create user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_OWNER",
        )

        # Create branch
        self.branch = Branch.objects.create(
            tenant=self.tenant, name="Main Branch", address="123 Main St", phone="555-0123"
        )

        # Create terminal
        self.terminal = Terminal.objects.create(branch=self.branch, terminal_id="POS-01")

        # Create product category
        self.category = ProductCategory.objects.create(tenant=self.tenant, name="Rings")

        # Create inventory items
        self.inventory_item = InventoryItem.objects.create(
            tenant=self.tenant,
            sku="RING-001",
            name="Gold Ring",
            category=self.category,
            karat=18,
            weight_grams=Decimal("5.5"),
            cost_price=Decimal("200.00"),
            selling_price=Decimal("400.00"),
            quantity=10,
            min_quantity=2,
            branch=self.branch,
        )

        # Create customer
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            customer_number="CUST-001",
            first_name="John",
            last_name="Doe",
            phone="555-0456",
        )

        # Create sales
        self.sale = Sale.objects.create(
            tenant=self.tenant,
            sale_number="SALE-001",
            customer=self.customer,
            branch=self.branch,
            terminal=self.terminal,
            employee=self.user,
            subtotal=Decimal("400.00"),
            tax=Decimal("32.00"),
            discount=Decimal("0.00"),
            total=Decimal("432.00"),
            payment_method=Sale.CASH,
            status=Sale.COMPLETED,
        )

        # Create sale item
        SaleItem.objects.create(
            sale=self.sale,
            inventory_item=self.inventory_item,
            quantity=1,
            unit_price=Decimal("400.00"),
            subtotal=Decimal("400.00"),
        )

    def tearDown(self):
        """Clean up after tests."""
        from apps.core.tenant_context import clear_tenant_context

        try:
            clear_tenant_context()
        except Exception:
            pass

    def test_dashboard_view_requires_login(self):
        """Test that dashboard view requires authentication."""
        url = reverse("core:tenant_dashboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_dashboard_view_with_authenticated_user(self):
        """Test dashboard view with authenticated user."""
        self.client.login(username="testuser", password="testpass123")
        url = reverse("core:tenant_dashboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")
        self.assertContains(response, "Today's Sales")
        self.assertContains(response, "Inventory Value")
        self.assertContains(response, "Stock Alerts")
        self.assertContains(response, "Pending Orders")

    def test_dashboard_context_data(self):
        """Test that dashboard context contains expected data."""
        self.client.login(username="testuser", password="testpass123")
        url = reverse("core:tenant_dashboard")
        response = self.client.get(url)

        context = response.context

        # Check today's sales data
        self.assertIn("today_sales", context)
        today_sales = context["today_sales"]
        self.assertIn("amount", today_sales)
        self.assertIn("count", today_sales)
        self.assertIn("change_percent", today_sales)
        self.assertIn("change_direction", today_sales)

        # Check inventory value data
        self.assertIn("inventory_value", context)
        inventory_value = context["inventory_value"]
        self.assertIn("cost_value", inventory_value)
        self.assertIn("selling_value", inventory_value)
        self.assertIn("total_items", inventory_value)
        self.assertIn("total_quantity", inventory_value)

        # Check stock alerts data
        self.assertIn("stock_alerts", context)
        stock_alerts = context["stock_alerts"]
        self.assertIn("low_stock_count", stock_alerts)
        self.assertIn("out_of_stock_count", stock_alerts)
        self.assertIn("total_alerts", stock_alerts)

        # Check pending orders data
        self.assertIn("pending_orders", context)
        pending_orders = context["pending_orders"]
        self.assertIn("total_pending", pending_orders)
        self.assertIn("overdue_count", pending_orders)

    def test_sales_trend_api_endpoint(self):
        """Test the sales trend API endpoint."""
        self.client.login(username="testuser", password="testpass123")
        url = reverse("core:api_sales_trend")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("labels", data)
        self.assertIn("datasets", data)
        self.assertIn("comparison", data)
        self.assertIn("period", data)

        # Check comparison data
        comparison = data["comparison"]
        self.assertIn("current_total", comparison)
        self.assertIn("previous_total", comparison)
        self.assertIn("change_percent", comparison)
        self.assertIn("change_direction", comparison)

    def test_sales_trend_api_with_period_parameter(self):
        """Test sales trend API with different period parameters."""
        self.client.login(username="testuser", password="testpass123")
        url = reverse("core:api_sales_trend")

        periods = ["7d", "30d", "90d", "1y"]
        for period in periods:
            response = self.client.get(url, {"period": period})
            self.assertEqual(response.status_code, 200)

            data = response.json()
            self.assertEqual(data["period"], period)

    def test_inventory_drill_down_api_endpoint(self):
        """Test the inventory drill-down API endpoint."""
        self.client.login(username="testuser", password="testpass123")
        url = reverse("core:api_inventory_drill_down")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("data", data)
        self.assertIn("filters", data)

    def test_sales_drill_down_api_endpoint(self):
        """Test the sales drill-down API endpoint."""
        self.client.login(username="testuser", password="testpass123")
        url = reverse("core:api_sales_drill_down")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("data", data)
        self.assertIn("period", data)
        self.assertIn("filters", data)

    def test_dashboard_stats_api_endpoint(self):
        """Test the dashboard stats API endpoint."""
        self.client.login(username="testuser", password="testpass123")
        url = reverse("core:api_dashboard_stats")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("today_sales_amount", data)
        self.assertIn("today_sales_count", data)
        self.assertIn("total_customers", data)
        self.assertIn("active_inventory", data)
        self.assertIn("pending_orders", data)
        self.assertIn("timestamp", data)

    def test_dashboard_kpi_calculations(self):
        """Test that KPI calculations are correct."""
        self.client.login(username="testuser", password="testpass123")
        url = reverse("core:tenant_dashboard")
        response = self.client.get(url)

        context = response.context

        # Test inventory value calculation
        inventory_value = context["inventory_value"]
        expected_cost_value = self.inventory_item.cost_price * self.inventory_item.quantity
        expected_selling_value = self.inventory_item.selling_price * self.inventory_item.quantity

        self.assertEqual(inventory_value["cost_value"], expected_cost_value)
        self.assertEqual(inventory_value["selling_value"], expected_selling_value)
        self.assertEqual(inventory_value["total_items"], 1)
        self.assertEqual(inventory_value["total_quantity"], 10)

    def test_dashboard_requires_tenant(self):
        """Test that dashboard requires user to have a tenant."""
        # Create user without tenant (platform admin doesn't need tenant)
        User.objects.create_user(  # noqa: F841
            username="notenant",
            email="notenant@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        self.client.login(username="notenant", password="testpass123")
        url = reverse("core:tenant_dashboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)  # Forbidden

    def test_dashboard_chart_data_url(self):
        """Test that dashboard includes chart data URL."""
        self.client.login(username="testuser", password="testpass123")
        url = reverse("core:tenant_dashboard")
        response = self.client.get(url)

        context = response.context
        self.assertIn("chart_data_url", context)
        self.assertEqual(context["chart_data_url"], "/api/dashboard/sales-trend/")


class DashboardAPITestCase(TestCase):
    """Test cases for dashboard API endpoints."""

    def setUp(self):
        """Set up test data."""
        # Enable RLS bypass for tests
        from apps.core.tenant_context import enable_rls_bypass

        enable_rls_bypass()

        # Create tenant
        self.tenant = Tenant.objects.create(company_name="API Test Shop", slug="api-test-shop")

        # Create user
        self.user = User.objects.create_user(
            username="apiuser",
            email="api@example.com",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_MANAGER",
        )

    def tearDown(self):
        """Clean up after tests."""
        from apps.core.tenant_context import clear_tenant_context

        try:
            clear_tenant_context()
        except Exception:
            pass

    def test_api_endpoints_require_authentication(self):
        """Test that all API endpoints require authentication."""
        endpoints = [
            "core:api_sales_trend",
            "core:api_inventory_drill_down",
            "core:api_sales_drill_down",
            "core:api_dashboard_stats",
        ]

        for endpoint in endpoints:
            url = reverse(endpoint)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_api_endpoints_return_json(self):
        """Test that API endpoints return JSON responses."""
        self.client.login(username="apiuser", password="testpass123")

        endpoints = [
            "core:api_sales_trend",
            "core:api_inventory_drill_down",
            "core:api_sales_drill_down",
            "core:api_dashboard_stats",
        ]

        for endpoint in endpoints:
            url = reverse(endpoint)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "application/json")
