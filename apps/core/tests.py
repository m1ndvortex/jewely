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


class TenantSettingsTestCase(TestCase):
    """Test cases for TenantSettings model."""

    def setUp(self):
        """Set up test data."""
        from apps.core.tenant_context import enable_rls_bypass

        enable_rls_bypass()

        self.tenant = Tenant.objects.create(
            company_name="Settings Test Shop", slug="settings-test-shop"
        )

    def tearDown(self):
        """Clean up after tests."""
        from apps.core.tenant_context import clear_tenant_context

        try:
            clear_tenant_context()
        except Exception:
            pass

    def test_tenant_settings_creation(self):
        """Test creating tenant settings."""
        from apps.core.models import TenantSettings

        settings = TenantSettings.objects.create(
            tenant=self.tenant,
            business_name="Official Business Name",
            business_registration_number="REG123456",
            tax_identification_number="TAX789012",
            address_line_1="123 Business St",
            city="Business City",
            country="Business Country",
            phone="555-0123",
            email="business@example.com",
            currency=TenantSettings.CURRENCY_USD,
            timezone="America/New_York",
            default_tax_rate=0.0825,
        )

        self.assertEqual(settings.tenant, self.tenant)
        self.assertEqual(settings.business_name, "Official Business Name")
        self.assertEqual(settings.currency, "USD")
        self.assertEqual(settings.default_tax_rate, 0.0825)

    def test_tenant_settings_str_method(self):
        """Test TenantSettings string representation."""
        from apps.core.models import TenantSettings

        settings = TenantSettings.objects.create(tenant=self.tenant)
        expected_str = f"Settings for {self.tenant.company_name}"
        self.assertEqual(str(settings), expected_str)

    def test_get_full_address_method(self):
        """Test get_full_address method."""
        from apps.core.models import TenantSettings

        settings = TenantSettings.objects.create(
            tenant=self.tenant,
            address_line_1="123 Main St",
            address_line_2="Suite 100",
            city="New York",
            state_province="NY",
            postal_code="10001",
            country="USA",
        )

        expected_address = "123 Main St, Suite 100, New York, NY, 10001, USA"
        self.assertEqual(settings.get_full_address(), expected_address)

    def test_get_full_address_with_empty_fields(self):
        """Test get_full_address with some empty fields."""
        from apps.core.models import TenantSettings

        settings = TenantSettings.objects.create(
            tenant=self.tenant,
            address_line_1="123 Main St",
            city="New York",
            country="USA",
        )

        expected_address = "123 Main St, New York, USA"
        self.assertEqual(settings.get_full_address(), expected_address)

    def test_is_business_day_method(self):
        """Test is_business_day method."""
        import datetime

        from apps.core.models import TenantSettings

        settings = TenantSettings.objects.create(
            tenant=self.tenant,
            business_hours={
                "monday": {"open": "09:00", "close": "18:00", "closed": False},
                "tuesday": {"open": "09:00", "close": "18:00", "closed": False},
                "sunday": {"closed": True},
            },
            holidays=[{"date": "2024-01-01", "name": "New Year's Day"}],
        )

        # Test regular business day
        monday = datetime.date(2024, 1, 8)  # A Monday
        self.assertTrue(settings.is_business_day(monday))

        # Test holiday
        new_year = datetime.date(2024, 1, 1)
        self.assertFalse(settings.is_business_day(new_year))

    def test_get_business_hours_for_day(self):
        """Test get_business_hours_for_day method."""
        from apps.core.models import TenantSettings

        settings = TenantSettings.objects.create(
            tenant=self.tenant,
            business_hours={
                "monday": {"open": "09:00", "close": "18:00", "closed": False},
                "sunday": {"closed": True},
            },
        )

        monday_hours = settings.get_business_hours_for_day("Monday")
        self.assertEqual(monday_hours["open"], "09:00")
        self.assertEqual(monday_hours["close"], "18:00")
        self.assertFalse(monday_hours["closed"])

        # Test day not in business_hours (should return default)
        saturday_hours = settings.get_business_hours_for_day("Saturday")
        self.assertTrue(saturday_hours["closed"])


class InvoiceSettingsTestCase(TestCase):
    """Test cases for InvoiceSettings model."""

    def setUp(self):
        """Set up test data."""
        from apps.core.tenant_context import enable_rls_bypass

        enable_rls_bypass()

        self.tenant = Tenant.objects.create(
            company_name="Invoice Test Shop", slug="invoice-test-shop"
        )

    def tearDown(self):
        """Clean up after tests."""
        from apps.core.tenant_context import clear_tenant_context

        try:
            clear_tenant_context()
        except Exception:
            pass

    def test_invoice_settings_creation(self):
        """Test creating invoice settings."""
        from apps.core.models import InvoiceSettings

        settings = InvoiceSettings.objects.create(
            tenant=self.tenant,
            invoice_template=InvoiceSettings.TEMPLATE_STANDARD,
            invoice_number_prefix="INV",
            next_invoice_number=1001,
            receipt_number_prefix="RCP",
            next_receipt_number=2001,
        )

        self.assertEqual(settings.tenant, self.tenant)
        self.assertEqual(settings.invoice_number_prefix, "INV")
        self.assertEqual(settings.next_invoice_number, 1001)

    def test_invoice_settings_str_method(self):
        """Test InvoiceSettings string representation."""
        from apps.core.models import InvoiceSettings

        settings = InvoiceSettings.objects.create(tenant=self.tenant)
        expected_str = f"Invoice Settings for {self.tenant.company_name}"
        self.assertEqual(str(settings), expected_str)

    def test_generate_invoice_number_sequential(self):
        """Test generating sequential invoice numbers."""
        from apps.core.models import InvoiceSettings

        settings = InvoiceSettings.objects.create(
            tenant=self.tenant,
            invoice_numbering_scheme=InvoiceSettings.NUMBERING_SEQUENTIAL,
            invoice_number_prefix="INV",
            invoice_number_format="{prefix}-{number:06d}",
            next_invoice_number=1,
        )

        # Generate first invoice number
        invoice_num1 = settings.generate_invoice_number()
        self.assertEqual(invoice_num1, "INV-000001")

        # Check that counter was incremented by fetching from database
        updated_settings = InvoiceSettings.objects.get(id=settings.id)
        self.assertEqual(updated_settings.next_invoice_number, 2)

        # Generate second invoice number
        invoice_num2 = settings.generate_invoice_number()
        self.assertEqual(invoice_num2, "INV-000002")

    def test_generate_receipt_number_sequential(self):
        """Test generating sequential receipt numbers."""
        from apps.core.models import InvoiceSettings

        settings = InvoiceSettings.objects.create(
            tenant=self.tenant,
            receipt_numbering_scheme=InvoiceSettings.NUMBERING_SEQUENTIAL,
            receipt_number_prefix="RCP",
            receipt_number_format="{prefix}-{number:06d}",
            next_receipt_number=1,
        )

        # Generate first receipt number
        receipt_num1 = settings.generate_receipt_number()
        self.assertEqual(receipt_num1, "RCP-000001")

        # Check that counter was incremented by fetching from database
        updated_settings = InvoiceSettings.objects.get(id=settings.id)
        self.assertEqual(updated_settings.next_receipt_number, 2)


class IntegrationSettingsTestCase(TestCase):
    """Test cases for IntegrationSettings model."""

    def setUp(self):
        """Set up test data."""
        from apps.core.tenant_context import enable_rls_bypass

        enable_rls_bypass()

        self.tenant = Tenant.objects.create(
            company_name="Integration Test Shop", slug="integration-test-shop"
        )

    def tearDown(self):
        """Clean up after tests."""
        from apps.core.tenant_context import clear_tenant_context

        try:
            clear_tenant_context()
        except Exception:
            pass

    def test_integration_settings_creation(self):
        """Test creating integration settings."""
        from apps.core.models import IntegrationSettings

        settings = IntegrationSettings.objects.create(
            tenant=self.tenant,
            payment_gateway_enabled=True,
            payment_gateway_provider="stripe",
            sms_provider_enabled=True,
            sms_provider="twilio",
            email_provider_enabled=True,
            email_provider="sendgrid",
        )

        self.assertEqual(settings.tenant, self.tenant)
        self.assertTrue(settings.payment_gateway_enabled)
        self.assertEqual(settings.payment_gateway_provider, "stripe")

    def test_integration_settings_str_method(self):
        """Test IntegrationSettings string representation."""
        from apps.core.models import IntegrationSettings

        settings = IntegrationSettings.objects.create(tenant=self.tenant)
        expected_str = f"Integration Settings for {self.tenant.company_name}"
        self.assertEqual(str(settings), expected_str)

    def test_encrypt_decrypt_field_methods(self):
        """Test field encryption and decryption methods."""
        from django.conf import settings as django_settings

        from apps.core.models import IntegrationSettings

        # Skip test if encryption key not configured
        if not hasattr(django_settings, "FIELD_ENCRYPTION_KEY"):
            self.skipTest("FIELD_ENCRYPTION_KEY not configured")

        integration_settings = IntegrationSettings.objects.create(tenant=self.tenant)

        # Test encryption/decryption
        test_value = "secret_api_key_12345"
        encrypted = integration_settings.encrypt_field(test_value)

        # Encrypted value should be different from original
        self.assertNotEqual(encrypted, test_value)

        # Decrypted value should match original
        decrypted = integration_settings.decrypt_field(encrypted)
        self.assertEqual(decrypted, test_value)

    def test_payment_gateway_key_methods(self):
        """Test payment gateway key setter/getter methods."""
        from django.conf import settings as django_settings

        from apps.core.models import IntegrationSettings

        # Skip test if encryption key not configured
        if not hasattr(django_settings, "FIELD_ENCRYPTION_KEY"):
            self.skipTest("FIELD_ENCRYPTION_KEY not configured")

        integration_settings = IntegrationSettings.objects.create(tenant=self.tenant)

        # Test API key
        test_api_key = "pk_test_12345"
        integration_settings.set_payment_gateway_api_key(test_api_key)
        retrieved_key = integration_settings.get_payment_gateway_api_key()
        self.assertEqual(retrieved_key, test_api_key)

        # Test secret key
        test_secret_key = "sk_test_67890"
        integration_settings.set_payment_gateway_secret_key(test_secret_key)
        retrieved_secret = integration_settings.get_payment_gateway_secret_key()
        self.assertEqual(retrieved_secret, test_secret_key)

    def test_sms_api_key_methods(self):
        """Test SMS API key setter/getter methods."""
        from django.conf import settings as django_settings

        from apps.core.models import IntegrationSettings

        # Skip test if encryption key not configured
        if not hasattr(django_settings, "FIELD_ENCRYPTION_KEY"):
            self.skipTest("FIELD_ENCRYPTION_KEY not configured")

        integration_settings = IntegrationSettings.objects.create(tenant=self.tenant)

        test_sms_key = "twilio_api_key_12345"
        integration_settings.set_sms_api_key(test_sms_key)
        retrieved_key = integration_settings.get_sms_api_key()
        self.assertEqual(retrieved_key, test_sms_key)

    def test_email_api_key_methods(self):
        """Test email API key setter/getter methods."""
        from django.conf import settings as django_settings

        from apps.core.models import IntegrationSettings

        # Skip test if encryption key not configured
        if not hasattr(django_settings, "FIELD_ENCRYPTION_KEY"):
            self.skipTest("FIELD_ENCRYPTION_KEY not configured")

        integration_settings = IntegrationSettings.objects.create(tenant=self.tenant)

        test_email_key = "sendgrid_api_key_12345"
        integration_settings.set_email_api_key(test_email_key)
        retrieved_key = integration_settings.get_email_api_key()
        self.assertEqual(retrieved_key, test_email_key)
