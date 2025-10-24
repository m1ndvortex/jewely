"""
Tests for dynamic pricing functionality.

Tests Requirement 17: Gold Rate and Dynamic Pricing
- Pricing calculation engine based on gold rate and markup rules
- Automatic price recalculation when rates change
- Pricing tier system (wholesale, retail, VIP)
- Manager approval for manual price overrides
"""

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.core.models import Tenant, User
from apps.inventory.models import Branch, InventoryItem, ProductCategory
from apps.pricing.models import GoldRate, PriceChangeLog, PriceOverrideRequest, PricingRule
from apps.pricing.services import (
    PriceOverrideService,
    PriceRecalculationService,
    PricingCalculationEngine,
)


class DynamicPricingTestCase(TestCase):
    """Base test case with common setup for dynamic pricing tests."""

    def setUp(self):
        """Set up test data."""
        # Import RLS bypass functions
        from apps.core.tenant_context import disable_rls_bypass, enable_rls_bypass

        # Enable RLS bypass to create tenant
        enable_rls_bypass()

        # Create tenant
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop", slug="test-shop", status="ACTIVE"
        )

        # Create users
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@test.com",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_OWNER",
        )

        self.manager = User.objects.create_user(
            username="manager",
            email="manager@test.com",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_MANAGER",
        )

        self.employee = User.objects.create_user(
            username="employee",
            email="employee@test.com",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_EMPLOYEE",
        )

        # Create branch
        self.branch = Branch.objects.create(
            tenant=self.tenant, name="Main Branch", address="123 Main St", phone="555-0123"
        )

        # Create product category
        self.category = ProductCategory.objects.create(tenant=self.tenant, name="Rings")

        # Disable RLS bypass after setup
        disable_rls_bypass()

        # Create gold rate
        self.gold_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("60.00"),
            rate_per_tola=Decimal("699.84"),
            rate_per_ounce=Decimal("1866.21"),
            market=GoldRate.INTERNATIONAL,
            currency="USD",
            source="Test",
            is_active=True,
        )

        # Create pricing rules
        self.retail_rule = PricingRule.objects.create(
            tenant=self.tenant,
            name="22K Retail Rule",
            karat=22,
            customer_tier=PricingRule.RETAIL,
            markup_percentage=Decimal("25.00"),
            making_charge_per_gram=Decimal("5.00"),
            is_active=True,
        )

        self.wholesale_rule = PricingRule.objects.create(
            tenant=self.tenant,
            name="22K Wholesale Rule",
            karat=22,
            customer_tier=PricingRule.WHOLESALE,
            markup_percentage=Decimal("15.00"),
            making_charge_per_gram=Decimal("3.00"),
            is_active=True,
        )

        self.vip_rule = PricingRule.objects.create(
            tenant=self.tenant,
            name="22K VIP Rule",
            karat=22,
            customer_tier=PricingRule.VIP,
            markup_percentage=Decimal("20.00"),
            making_charge_per_gram=Decimal("4.00"),
            is_active=True,
        )

        # Create inventory item
        self.inventory_item = InventoryItem.objects.create(
            tenant=self.tenant,
            sku="RING-001",
            name="22K Gold Ring",
            category=self.category,
            karat=22,
            weight_grams=Decimal("10.0"),
            craftsmanship_level=InventoryItem.HANDMADE,
            cost_price=Decimal("500.00"),
            selling_price=Decimal("750.00"),
            quantity=5,
            branch=self.branch,
        )


class PricingCalculationEngineTest(DynamicPricingTestCase):
    """Test the pricing calculation engine."""

    def test_calculate_price_retail(self):
        """Test price calculation for retail customer."""
        engine = PricingCalculationEngine(self.tenant)

        result = engine.calculate_price(
            karat=22, weight_grams=Decimal("10.0"), customer_tier=PricingRule.RETAIL
        )

        # Expected calculation:
        # Gold value: 10 * 60 = 600
        # Markup (25%): 600 * 0.25 = 150
        # Making charges: 10 * 5 = 50
        # Total: 600 + 150 + 50 = 800

        self.assertEqual(result["gold_value"], Decimal("600.00"))
        self.assertEqual(result["markup_amount"], Decimal("150.00"))
        self.assertEqual(result["making_charges"], Decimal("50.00"))
        self.assertEqual(result["total_price"], Decimal("800.00"))
        self.assertEqual(result["gold_rate_per_gram"], Decimal("60.00"))

    def test_calculate_price_wholesale(self):
        """Test price calculation for wholesale customer."""
        engine = PricingCalculationEngine(self.tenant)

        result = engine.calculate_price(
            karat=22, weight_grams=Decimal("10.0"), customer_tier=PricingRule.WHOLESALE
        )

        # Expected calculation:
        # Gold value: 10 * 60 = 600
        # Markup (15%): 600 * 0.15 = 90
        # Making charges: 10 * 3 = 30
        # Total: 600 + 90 + 30 = 720

        self.assertEqual(result["total_price"], Decimal("720.00"))

    def test_calculate_price_vip(self):
        """Test price calculation for VIP customer."""
        engine = PricingCalculationEngine(self.tenant)

        result = engine.calculate_price(
            karat=22, weight_grams=Decimal("10.0"), customer_tier=PricingRule.VIP
        )

        # Expected calculation:
        # Gold value: 10 * 60 = 600
        # Markup (20%): 600 * 0.20 = 120
        # Making charges: 10 * 4 = 40
        # Total: 600 + 120 + 40 = 760

        self.assertEqual(result["total_price"], Decimal("760.00"))

    def test_calculate_price_with_stones(self):
        """Test price calculation with stone charges."""
        # Add stone charge to retail rule
        self.retail_rule.stone_charge_percentage = Decimal("10.00")
        self.retail_rule.save()

        engine = PricingCalculationEngine(self.tenant)

        result = engine.calculate_price(
            karat=22,
            weight_grams=Decimal("10.0"),
            customer_tier=PricingRule.RETAIL,
            stone_value=Decimal("100.00"),
        )

        # Expected calculation:
        # Gold value: 10 * 60 = 600
        # Markup (25%): 600 * 0.25 = 150
        # Making charges: 10 * 5 = 50
        # Stone charges: 100 * 0.10 = 10
        # Total: 600 + 150 + 50 + 10 = 810

        self.assertEqual(result["stone_charges"], Decimal("10.00"))
        self.assertEqual(result["total_price"], Decimal("810.00"))

    def test_calculate_item_price(self):
        """Test price calculation for existing inventory item."""
        engine = PricingCalculationEngine(self.tenant)

        result = engine.calculate_item_price(
            inventory_item=self.inventory_item, customer_tier=PricingRule.RETAIL
        )

        # Should use item's karat (22) and weight (10.0)
        self.assertEqual(result["total_price"], Decimal("800.00"))

    def test_get_tiered_prices(self):
        """Test getting prices for all customer tiers."""
        engine = PricingCalculationEngine(self.tenant)

        tiered_prices = engine.get_tiered_prices(karat=22, weight_grams=Decimal("10.0"))

        # Should have prices for all tiers
        self.assertIn(PricingRule.RETAIL, tiered_prices)
        self.assertIn(PricingRule.WHOLESALE, tiered_prices)
        self.assertIn(PricingRule.VIP, tiered_prices)

        # Wholesale should be cheapest, retail most expensive
        wholesale_price = tiered_prices[PricingRule.WHOLESALE]["total_price"]
        vip_price = tiered_prices[PricingRule.VIP]["total_price"]
        retail_price = tiered_prices[PricingRule.RETAIL]["total_price"]

        self.assertLess(wholesale_price, vip_price)
        self.assertLess(vip_price, retail_price)

    def test_no_pricing_rule_error(self):
        """Test error when no pricing rule is found."""
        engine = PricingCalculationEngine(self.tenant)

        with self.assertRaises(ValueError) as context:
            engine.calculate_price(
                karat=18,  # No rule for 18K
                weight_grams=Decimal("10.0"),
                customer_tier=PricingRule.RETAIL,
            )

        self.assertIn("No pricing rule found", str(context.exception))

    def test_no_gold_rate_error(self):
        """Test error when no gold rate is available."""
        # Deactivate gold rate
        self.gold_rate.is_active = False
        self.gold_rate.save()

        engine = PricingCalculationEngine(self.tenant)

        with self.assertRaises(ValueError) as context:
            engine.calculate_price(
                karat=22, weight_grams=Decimal("10.0"), customer_tier=PricingRule.RETAIL
            )

        self.assertIn("No active gold rate found", str(context.exception))


class PriceRecalculationServiceTest(DynamicPricingTestCase):
    """Test the price recalculation service."""

    def test_recalculate_all_prices(self):
        """Test recalculating all inventory prices."""
        # Create additional inventory items
        InventoryItem.objects.create(
            tenant=self.tenant,
            sku="RING-002",
            name="22K Gold Ring 2",
            category=self.category,
            karat=22,
            weight_grams=Decimal("8.0"),
            craftsmanship_level=InventoryItem.HANDMADE,
            cost_price=Decimal("400.00"),
            selling_price=Decimal("600.00"),  # Will be recalculated
            quantity=3,
            branch=self.branch,
        )

        service = PriceRecalculationService(self.tenant)
        stats = service.recalculate_all_prices()

        # Should have processed 2 items
        self.assertEqual(stats["total_items"], 2)
        self.assertEqual(stats["updated_items"], 2)
        self.assertEqual(stats["failed_items"], 0)

        # Check that prices were updated
        self.inventory_item.refresh_from_db()
        self.assertEqual(self.inventory_item.selling_price, Decimal("800.00"))

        # Check price change log
        change_logs = PriceChangeLog.objects.filter(tenant=self.tenant)
        self.assertEqual(change_logs.count(), 2)

    def test_recalculate_by_karat(self):
        """Test recalculating prices for specific karat."""
        # Create item with different karat
        InventoryItem.objects.create(
            tenant=self.tenant,
            sku="RING-18K",
            name="18K Gold Ring",
            category=self.category,
            karat=18,
            weight_grams=Decimal("10.0"),
            craftsmanship_level=InventoryItem.HANDMADE,
            cost_price=Decimal("450.00"),
            selling_price=Decimal("650.00"),
            quantity=2,
            branch=self.branch,
        )

        service = PriceRecalculationService(self.tenant)
        stats = service.recalculate_by_karat(karat=22)

        # Should only process 22K items (1 item)
        self.assertEqual(stats["total_items"], 1)
        self.assertEqual(stats["updated_items"], 1)

    def test_price_change_logging(self):
        """Test that price changes are logged."""
        service = PriceRecalculationService(self.tenant)
        service.recalculate_all_prices()

        # Check price change log
        change_log = PriceChangeLog.objects.filter(
            tenant=self.tenant, inventory_item=self.inventory_item
        ).first()

        self.assertIsNotNone(change_log)
        self.assertEqual(change_log.old_price, Decimal("750.00"))
        self.assertEqual(change_log.new_price, Decimal("800.00"))
        self.assertEqual(change_log.change_amount, Decimal("50.00"))
        self.assertIn("Automatic recalculation", change_log.reason)


class PriceOverrideServiceTest(DynamicPricingTestCase):
    """Test the price override service."""

    def test_request_price_override(self):
        """Test requesting a price override."""
        service = PriceOverrideService(self.tenant)

        override_request = service.request_price_override(
            inventory_item=self.inventory_item,
            new_price=Decimal("900.00"),
            reason="Customer negotiation",
            requested_by=self.employee,
        )

        self.assertIsNotNone(override_request)
        self.assertEqual(override_request.inventory_item, self.inventory_item)
        self.assertEqual(override_request.requested_price, Decimal("900.00"))
        self.assertEqual(override_request.status, PriceOverrideRequest.PENDING)
        self.assertEqual(override_request.requested_by, self.employee)

        # Check deviation calculation
        self.assertEqual(override_request.deviation_amount, Decimal("100.00"))  # 900 - 800
        self.assertEqual(override_request.deviation_percentage, Decimal("12.50"))  # 100/800 * 100

    def test_approve_override(self):
        """Test approving a price override."""
        service = PriceOverrideService(self.tenant)

        # Create override request
        override_request = service.request_price_override(
            inventory_item=self.inventory_item,
            new_price=Decimal("900.00"),
            reason="Customer negotiation",
            requested_by=self.employee,
        )

        # Approve the request
        success = service.approve_override(
            override_request=override_request,
            approved_by=self.manager,
            notes="Approved for VIP customer",
        )

        self.assertTrue(success)

        # Check override status
        override_request.refresh_from_db()
        self.assertEqual(override_request.status, PriceOverrideRequest.APPROVED)
        self.assertEqual(override_request.reviewed_by, self.manager)
        self.assertIsNotNone(override_request.reviewed_at)

        # Check that item price was updated
        self.inventory_item.refresh_from_db()
        self.assertEqual(self.inventory_item.selling_price, Decimal("900.00"))

        # Check price change log
        change_log = PriceChangeLog.objects.filter(
            tenant=self.tenant, inventory_item=self.inventory_item
        ).first()
        self.assertIsNotNone(change_log)
        self.assertIn("Manual override approved", change_log.reason)

    def test_reject_override(self):
        """Test rejecting a price override."""
        service = PriceOverrideService(self.tenant)

        # Create override request
        override_request = service.request_price_override(
            inventory_item=self.inventory_item,
            new_price=Decimal("900.00"),
            reason="Customer negotiation",
            requested_by=self.employee,
        )

        # Reject the request
        success = service.reject_override(
            override_request=override_request,
            rejected_by=self.manager,
            rejection_reason="Price too low for this item",
        )

        self.assertTrue(success)

        # Check override status
        override_request.refresh_from_db()
        self.assertEqual(override_request.status, PriceOverrideRequest.REJECTED)
        self.assertEqual(override_request.reviewed_by, self.manager)
        self.assertIsNotNone(override_request.reviewed_at)

        # Check that item price was NOT updated
        self.inventory_item.refresh_from_db()
        self.assertEqual(self.inventory_item.selling_price, Decimal("750.00"))

    def test_cannot_approve_own_request(self):
        """Test that users cannot approve their own override requests."""
        service = PriceOverrideService(self.tenant)

        # Create override request
        override_request = service.request_price_override(
            inventory_item=self.inventory_item,
            new_price=Decimal("900.00"),
            reason="Customer negotiation",
            requested_by=self.manager,
        )

        # Try to approve own request
        with self.assertRaises(ValueError) as context:
            service.approve_override(
                override_request=override_request,
                approved_by=self.manager,  # Same user
                notes="Self approval",
            )

        self.assertIn("does not have permission", str(context.exception))

    def test_employee_cannot_approve(self):
        """Test that employees cannot approve override requests."""
        service = PriceOverrideService(self.tenant)

        # Create override request
        override_request = service.request_price_override(
            inventory_item=self.inventory_item,
            new_price=Decimal("900.00"),
            reason="Customer negotiation",
            requested_by=self.employee,
        )

        # Try to approve as employee
        with self.assertRaises(ValueError) as context:
            service.approve_override(
                override_request=override_request,
                approved_by=self.employee,  # Employee role
                notes="Employee approval",
            )

        self.assertIn("does not have permission", str(context.exception))


class DynamicPricingViewsTest(DynamicPricingTestCase):
    """Test the dynamic pricing views."""

    def test_pricing_dashboard_view(self):
        """Test the pricing dashboard view."""
        self.client.login(username="owner", password="testpass123")

        response = self.client.get(reverse("pricing:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pricing Dashboard")
        self.assertContains(response, "Live Gold Rates")  # Gold rate widget

    def test_calculate_price_view_get(self):
        """Test the calculate price view (GET)."""
        self.client.login(username="owner", password="testpass123")

        response = self.client.get(reverse("pricing:calculate_price"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Price Calculator")

    def test_calculate_price_view_post(self):
        """Test the calculate price view (POST)."""
        self.client.login(username="owner", password="testpass123")

        response = self.client.post(
            reverse("pricing:calculate_price"),
            {"karat": 22, "weight_grams": "10.0", "customer_tier": "RETAIL", "stone_value": "0.00"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "$800.00")  # Expected total price

    def test_recalculate_all_prices_view(self):
        """Test the recalculate all prices view."""
        self.client.login(username="owner", password="testpass123")

        response = self.client.post(reverse("pricing:recalculate_all"), {"customer_tier": "RETAIL"})

        self.assertEqual(response.status_code, 302)  # Redirect after success

        # Check that price was updated
        self.inventory_item.refresh_from_db()
        self.assertEqual(self.inventory_item.selling_price, Decimal("800.00"))

    def test_recalculate_permission_required(self):
        """Test that only managers/owners can recalculate prices."""
        self.client.login(username="employee", password="testpass123")

        response = self.client.post(reverse("pricing:recalculate_all"), {"customer_tier": "RETAIL"})

        self.assertEqual(response.status_code, 302)  # Redirect due to permission error

    def test_api_calculate_item_price(self):
        """Test the API endpoint for calculating item price."""
        self.client.login(username="owner", password="testpass123")

        response = self.client.get(
            reverse("pricing:api_calculate_item_price", args=[self.inventory_item.id]),
            {"customer_tier": "RETAIL"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data["success"])
        self.assertEqual(data["price_breakdown"]["total_price"], "800.00")
        self.assertIn("tiered_prices", data)


class AutomaticPriceUpdateTest(DynamicPricingTestCase):
    """Test automatic price updates when gold rates change."""

    @patch("apps.pricing.tasks.update_inventory_prices.delay")
    def test_price_update_triggered_on_rate_change(self, mock_task):
        """Test that price updates are triggered when gold rates change."""
        # This would normally be triggered by the Celery task
        # We're testing the integration here

        # Create new gold rate
        GoldRate.objects.create(
            rate_per_gram=Decimal("65.00"),  # Higher rate
            rate_per_tola=Decimal("758.16"),
            rate_per_ounce=Decimal("2021.73"),
            market=GoldRate.INTERNATIONAL,
            currency="USD",
            source="Test",
            is_active=True,
        )

        # Deactivate old rate
        self.gold_rate.is_active = False
        self.gold_rate.save()

        # Manually trigger price recalculation
        service = PriceRecalculationService(self.tenant)
        stats = service.recalculate_all_prices()

        # Check that prices were updated with new rate
        self.inventory_item.refresh_from_db()

        # Expected calculation with new rate (65.00):
        # Gold value: 10 * 65 = 650
        # Markup (25%): 650 * 0.25 = 162.50
        # Making charges: 10 * 5 = 50
        # Total: 650 + 162.50 + 50 = 862.50

        self.assertEqual(self.inventory_item.selling_price, Decimal("862.50"))
        self.assertEqual(stats["updated_items"], 1)

    def test_price_change_percentage_calculation(self):
        """Test that price change percentages are calculated correctly."""
        # Update price manually to test percentage calculation
        old_price = self.inventory_item.selling_price
        new_price = Decimal("900.00")

        # Create price change log manually
        change_log = PriceChangeLog.objects.create(
            tenant=self.tenant,
            inventory_item=self.inventory_item,
            old_price=old_price,
            new_price=new_price,
            reason="Test price change",
        )

        # Check calculations
        expected_change = new_price - old_price
        expected_percentage = (expected_change / old_price) * 100

        self.assertEqual(change_log.change_amount, expected_change)
        self.assertEqual(
            change_log.change_percentage, expected_percentage.quantize(Decimal("0.01"))
        )
        self.assertTrue(change_log.is_increase())
        self.assertFalse(change_log.is_decrease())


class PricingRuleMatchingTest(DynamicPricingTestCase):
    """Test pricing rule matching logic."""

    def test_specific_rule_takes_precedence(self):
        """Test that specific rules take precedence over generic ones."""
        # Create specific rule for rings
        PricingRule.objects.create(
            tenant=self.tenant,
            name="22K Ring Specific Rule",
            karat=22,
            product_type=PricingRule.RING,
            customer_tier=PricingRule.RETAIL,
            markup_percentage=Decimal("30.00"),  # Higher markup
            making_charge_per_gram=Decimal("6.00"),
            priority=10,  # Higher priority
            is_active=True,
        )

        engine = PricingCalculationEngine(self.tenant)

        result = engine.calculate_price(
            karat=22,
            weight_grams=Decimal("10.0"),
            product_type=PricingRule.RING,
            customer_tier=PricingRule.RETAIL,
        )

        # Should use specific rule with 30% markup
        # Gold value: 10 * 60 = 600
        # Markup (30%): 600 * 0.30 = 180
        # Making charges: 10 * 6 = 60
        # Total: 600 + 180 + 60 = 840

        self.assertEqual(result["total_price"], Decimal("840.00"))
        self.assertIn("RING", result["rule_applied"])  # Check for product type instead

    def test_fallback_to_generic_rule(self):
        """Test fallback to generic rule when specific rule not found."""
        engine = PricingCalculationEngine(self.tenant)

        result = engine.calculate_price(
            karat=22,
            weight_grams=Decimal("10.0"),
            product_type=PricingRule.NECKLACE,  # No specific rule for necklace
            customer_tier=PricingRule.RETAIL,
        )

        # Should use generic retail rule (25% markup)
        self.assertEqual(result["total_price"], Decimal("800.00"))

    def test_priority_ordering(self):
        """Test that higher priority rules are selected first."""
        # Create high priority rule
        PricingRule.objects.create(
            tenant=self.tenant,
            name="22K High Priority Rule",
            karat=22,
            customer_tier=PricingRule.RETAIL,
            markup_percentage=Decimal("35.00"),
            making_charge_per_gram=Decimal("7.00"),
            priority=20,  # Higher than existing rule
            is_active=True,
        )

        engine = PricingCalculationEngine(self.tenant)

        result = engine.calculate_price(
            karat=22, weight_grams=Decimal("10.0"), customer_tier=PricingRule.RETAIL
        )

        # Should use high priority rule
        # Gold value: 10 * 60 = 600
        # Markup (35%): 600 * 0.35 = 210
        # Making charges: 10 * 7 = 70
        # Total: 600 + 210 + 70 = 880

        self.assertEqual(result["total_price"], Decimal("880.00"))
        self.assertIn("35.00%", result["rule_applied"])  # Check for the markup percentage instead
