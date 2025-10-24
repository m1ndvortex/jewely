"""
Tests for gold rate display functionality.

Tests Requirement 17: Gold Rate and Dynamic Pricing
- Live gold rate widget for dashboard
- Rate history chart
- Display current rates on receipts
- Rate comparison interface
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Tenant
from apps.inventory.models import InventoryItem, ProductCategory
from apps.pricing.models import GoldRate
from apps.sales.models import Branch, Sale, SaleItem, Terminal

User = get_user_model()


class GoldRateDisplayTest(TestCase):
    """Test gold rate display functionality."""

    def setUp(self):
        """Set up test data."""
        # Import RLS bypass functions
        from apps.core.tenant_context import enable_rls_bypass

        # Enable RLS bypass to create tenant
        enable_rls_bypass()

        # Create tenant
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop", slug="test-shop", status="ACTIVE"
        )

        # Create test user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_OWNER",
        )

        # Create historical rates first (must be created before current rates)
        yesterday = timezone.now() - timedelta(days=1)
        self.historical_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("59.00"),
            rate_per_tola=Decimal("688.18"),
            rate_per_ounce=Decimal("1834.71"),
            market=GoldRate.INTERNATIONAL,
            currency="USD",
            source="TestAPI",
            is_active=False,
        )
        # Update timestamp to be earlier
        self.historical_rate.timestamp = yesterday
        self.historical_rate.save()

        # Create current gold rates for different markets
        self.international_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("60.00"),
            rate_per_tola=Decimal("699.84"),
            rate_per_ounce=Decimal("1866.21"),
            market=GoldRate.INTERNATIONAL,
            currency="USD",
            source="TestAPI",
            is_active=True,
        )

        self.local_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("58.50"),
            rate_per_tola=Decimal("682.34"),
            rate_per_ounce=Decimal("1819.55"),
            market=GoldRate.LOCAL,
            currency="USD",
            source="LocalAPI",
            is_active=True,
        )

    def test_gold_rate_widget_view(self):
        """Test the gold rate widget view."""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.get(reverse("pricing:gold_rate_widget"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Live Gold Rates")
        self.assertContains(response, "$60.00/g")  # International rate
        self.assertContains(response, "$58.50/g")  # Local rate
        self.assertContains(response, "International")
        self.assertContains(response, "Local Market")

    def test_gold_rate_history_view(self):
        """Test the gold rate history view."""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.get(reverse("pricing:gold_rate_history"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gold Rate History")
        self.assertContains(response, "Current Rate")
        self.assertContains(response, "$60.00/g")  # Current rate
        self.assertContains(response, "Period Change")

    def test_gold_rate_history_with_filters(self):
        """Test the gold rate history view with filters."""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.get(
            reverse("pricing:gold_rate_history"), {"market": GoldRate.LOCAL, "days": 7}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gold Rate History")
        self.assertContains(response, "Local Market")

    def test_gold_rate_comparison_view(self):
        """Test the gold rate comparison view."""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.get(reverse("pricing:gold_rate_comparison"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gold Rate Comparison")
        self.assertContains(response, "International")
        self.assertContains(response, "Local Market")
        self.assertContains(response, "$60.00/g")  # Highest rate
        self.assertContains(response, "$58.50/g")  # Lower rate

    def test_api_gold_rates_endpoint(self):
        """Test the API endpoint for gold rates."""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.get(
            reverse("pricing:api_gold_rates"), {"market": GoldRate.INTERNATIONAL}
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data["success"])
        self.assertEqual(data["rate"]["rate_per_gram"], "60.00")
        self.assertEqual(data["rate"]["market"], GoldRate.INTERNATIONAL)
        self.assertEqual(data["rate"]["currency"], "USD")

    def test_api_gold_rates_not_found(self):
        """Test API endpoint when no rate is found."""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.get(
            reverse("pricing:api_gold_rates"), {"market": GoldRate.DUBAI}  # No rate for this market
        )

        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertFalse(data["success"])

    def test_gold_rate_widget_auto_refresh(self):
        """Test that the gold rate widget includes auto-refresh functionality."""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.get(reverse("pricing:gold_rate_widget"))

        self.assertEqual(response.status_code, 200)
        # Check for HTMX auto-refresh attributes
        self.assertContains(response, 'hx-trigger="every 30s"')
        self.assertContains(response, "Auto-refreshes every 30 seconds")

    def test_gold_rate_change_indicators(self):
        """Test that rate change indicators are displayed correctly."""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.get(reverse("pricing:gold_rate_widget"))

        self.assertEqual(response.status_code, 200)
        # The international rate increased from 59.00 to 60.00
        # Should show positive change indicator
        self.assertContains(response, "text-green-600")  # Positive change color

    def test_receipt_includes_gold_rates(self):
        """Test that receipts include current gold rates."""
        # Create necessary objects for sale
        branch = Branch.objects.create(
            tenant=self.tenant, name="Main Branch", address="123 Test St"
        )

        terminal = Terminal.objects.create(branch=branch, terminal_id="TERM001", is_active=True)

        category = ProductCategory.objects.create(tenant=self.tenant, name="Rings")

        item = InventoryItem.objects.create(
            tenant=self.tenant,
            sku="RING001",
            name="Gold Ring",
            category=category,
            karat=18,
            weight_grams=Decimal("5.0"),
            cost_price=Decimal("200.00"),
            selling_price=Decimal("300.00"),
            quantity=10,
            branch=branch,
        )

        sale = Sale.objects.create(
            tenant=self.tenant,
            sale_number="SALE001",
            branch=branch,
            terminal=terminal,
            employee=self.user,
            subtotal=Decimal("300.00"),
            tax=Decimal("30.00"),
            total=Decimal("330.00"),
            payment_method="CASH",
            status="COMPLETED",
        )

        SaleItem.objects.create(
            sale=sale,
            inventory_item=item,
            quantity=1,
            unit_price=Decimal("300.00"),
            subtotal=Decimal("300.00"),
        )

        self.client.login(username="testuser", password="testpass123")

        # Test standard receipt
        response = self.client.get(reverse("sales:receipt_html", args=[sale.id, "standard"]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Current Gold Rates")
        self.assertContains(response, "$60.00")  # Current rate
        self.assertContains(response, "International")  # Market name

        # Test thermal receipt
        response = self.client.get(reverse("sales:receipt_html", args=[sale.id, "thermal"]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gold Rates")
        self.assertContains(response, "$60.00")  # Current rate

    def test_no_gold_rates_available(self):
        """Test display when no gold rates are available."""
        # Delete all gold rates
        GoldRate.objects.all().delete()

        self.client.login(username="testuser", password="testpass123")

        response = self.client.get(reverse("pricing:gold_rate_widget"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No gold rates available")

    def test_gold_rate_history_chart_data(self):
        """Test that chart data is properly formatted."""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.get(reverse("pricing:gold_rate_history"))

        self.assertEqual(response.status_code, 200)
        # Check for Chart.js script
        self.assertContains(response, "Chart.js")
        self.assertContains(response, "rateChart")

    def test_unauthorized_access(self):
        """Test that unauthorized users cannot access gold rate views."""
        # Test without login
        response = self.client.get(reverse("pricing:gold_rate_widget"))
        self.assertEqual(response.status_code, 302)  # Redirect to login

        response = self.client.get(reverse("pricing:gold_rate_history"))
        self.assertEqual(response.status_code, 302)  # Redirect to login

        response = self.client.get(reverse("pricing:gold_rate_comparison"))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_tenant_isolation(self):
        """Test that users can only see their tenant's data."""
        # Create another tenant and user
        other_tenant = Tenant.objects.create(company_name="Other Shop", slug="other-shop")

        User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="testpass123",
            tenant=other_tenant,
            role="TENANT_OWNER",
        )

        self.client.login(username="otheruser", password="testpass123")

        # Gold rates are global, so they should be visible
        response = self.client.get(reverse("pricing:gold_rate_widget"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "$60.00/g")  # Should see global rates
