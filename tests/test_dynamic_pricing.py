"""
Tests for dynamic pricing functionality.

Tests Requirement 17: Gold Rate and Dynamic Pricing
- Pricing calculation engine
- Automatic price recalculation
- Pricing tier system
- Manager approval for price overrides
"""

from decimal import Decimal

import pytest

from apps.core.models import User
from apps.inventory.models import InventoryItem, ProductCategory
from apps.pricing.models import GoldRate, PriceChangeLog, PriceOverrideRequest, PricingRule
from apps.pricing.services import (
    PriceOverrideService,
    PriceRecalculationService,
    PricingCalculationEngine,
)

# Use tenant fixture from conftest.py - no need to redefine


# Use branch fixture from conftest.py - no need to redefine


@pytest.fixture
def owner(tenant, branch):
    """Create a test owner user."""
    return User.objects.create_user(
        username="owner",
        email="owner@test.com",
        password="testpass123",
        tenant=tenant,
        branch=branch,
        role="TENANT_OWNER",
    )


@pytest.fixture
def manager(tenant, branch):
    """Create a test manager user."""
    return User.objects.create_user(
        username="manager",
        email="manager@test.com",
        password="testpass123",
        tenant=tenant,
        branch=branch,
        role="TENANT_MANAGER",
    )


@pytest.fixture
def employee(tenant, branch):
    """Create a test employee user."""
    return User.objects.create_user(
        username="employee",
        email="employee@test.com",
        password="testpass123",
        tenant=tenant,
        branch=branch,
        role="TENANT_EMPLOYEE",
    )


@pytest.fixture
def gold_rate(db):
    """Create a test gold rate."""
    return GoldRate.objects.create(
        rate_per_gram=Decimal("60.00"),
        rate_per_tola=Decimal("699.84"),  # 60 * 11.664
        rate_per_ounce=Decimal("1866.21"),  # 60 * 31.1035
        market=GoldRate.INTERNATIONAL,
        currency="USD",
        source="Test",
        is_active=True,
    )


@pytest.fixture
def pricing_rule_retail(tenant):
    """Create a retail pricing rule."""
    return PricingRule.objects.create(
        tenant=tenant,
        karat=22,
        customer_tier=PricingRule.RETAIL,
        markup_percentage=Decimal("25.00"),
        making_charge_per_gram=Decimal("5.00"),
        name="22K Retail",
        is_active=True,
    )


@pytest.fixture
def pricing_rule_wholesale(tenant):
    """Create a wholesale pricing rule."""
    return PricingRule.objects.create(
        tenant=tenant,
        karat=22,
        customer_tier=PricingRule.WHOLESALE,
        markup_percentage=Decimal("15.00"),
        making_charge_per_gram=Decimal("3.00"),
        name="22K Wholesale",
        is_active=True,
    )


@pytest.fixture
def pricing_rule_vip(tenant):
    """Create a VIP pricing rule."""
    return PricingRule.objects.create(
        tenant=tenant,
        karat=22,
        customer_tier=PricingRule.VIP,
        markup_percentage=Decimal("20.00"),
        making_charge_per_gram=Decimal("4.00"),
        name="22K VIP",
        is_active=True,
    )


@pytest.fixture
def category(tenant):
    """Create a test product category."""
    return ProductCategory.objects.create(
        tenant=tenant,
        name="Ring",
    )


@pytest.fixture
def inventory_item(tenant, branch, category):
    """Create a test inventory item."""
    return InventoryItem.objects.create(
        tenant=tenant,
        sku="TEST-001",
        name="22K Gold Ring",
        category=category,
        karat=22,
        weight_grams=Decimal("10.000"),
        cost_price=Decimal("600.00"),
        selling_price=Decimal("800.00"),
        quantity=5,
        branch=branch,
        craftsmanship_level=InventoryItem.HANDMADE,
    )


@pytest.mark.django_db
class TestPricingCalculationEngine:
    """Test the pricing calculation engine."""

    def test_calculate_price_basic(self, tenant, gold_rate, pricing_rule_retail):
        """Test basic price calculation."""
        engine = PricingCalculationEngine(tenant)

        result = engine.calculate_price(
            karat=22,
            weight_grams=Decimal("10.000"),
            customer_tier=PricingRule.RETAIL,
        )

        # Expected calculation:
        # Gold value: 10 * 60 = 600
        # Markup (25%): 600 * 0.25 = 150
        # Making charges: 10 * 5 = 50
        # Total: 600 + 150 + 50 = 800

        assert result["gold_value"] == Decimal("600.00")
        assert result["markup_amount"] == Decimal("150.00")
        assert result["making_charges"] == Decimal("50.00")
        assert result["total_price"] == Decimal("800.00")

    def test_calculate_price_with_stone_value(self, tenant, gold_rate, pricing_rule_retail):
        """Test price calculation with stone value."""
        # Add stone charge to the rule
        pricing_rule_retail.stone_charge_percentage = Decimal("10.00")
        pricing_rule_retail.save()

        engine = PricingCalculationEngine(tenant)

        result = engine.calculate_price(
            karat=22,
            weight_grams=Decimal("10.000"),
            customer_tier=PricingRule.RETAIL,
            stone_value=Decimal("100.00"),
        )

        # Stone charges: 100 * 0.10 = 10
        assert result["stone_charges"] == Decimal("10.00")
        assert result["total_price"] == Decimal("810.00")  # 800 + 10

    def test_get_tiered_prices(
        self, tenant, gold_rate, pricing_rule_retail, pricing_rule_wholesale, pricing_rule_vip
    ):
        """Test getting prices for all tiers."""
        engine = PricingCalculationEngine(tenant)

        tiered_prices = engine.get_tiered_prices(
            karat=22,
            weight_grams=Decimal("10.000"),
        )

        # Should have prices for all three tiers
        assert PricingRule.RETAIL in tiered_prices
        assert PricingRule.WHOLESALE in tiered_prices
        assert PricingRule.VIP in tiered_prices

        # Wholesale should be cheapest, retail most expensive
        assert (
            tiered_prices[PricingRule.WHOLESALE]["total_price"]
            < tiered_prices[PricingRule.VIP]["total_price"]
        )
        assert (
            tiered_prices[PricingRule.VIP]["total_price"]
            < tiered_prices[PricingRule.RETAIL]["total_price"]
        )

    def test_calculate_item_price(self, tenant, gold_rate, pricing_rule_retail, inventory_item):
        """Test calculating price for an existing inventory item."""
        engine = PricingCalculationEngine(tenant)

        result = engine.calculate_item_price(
            inventory_item=inventory_item,
            customer_tier=PricingRule.RETAIL,
        )

        assert result["total_price"] == Decimal("800.00")
        assert "rule_applied" in result

    def test_no_gold_rate_error(self, tenant, pricing_rule_retail):
        """Test error when no gold rate is available."""
        # Delete all gold rates
        GoldRate.objects.all().delete()

        engine = PricingCalculationEngine(tenant)

        with pytest.raises(ValueError, match="No active gold rate found"):
            engine.calculate_price(
                karat=22,
                weight_grams=Decimal("10.000"),
                customer_tier=PricingRule.RETAIL,
            )

    def test_no_pricing_rule_error(self, tenant, gold_rate):
        """Test error when no pricing rule is found."""
        engine = PricingCalculationEngine(tenant)

        with pytest.raises(ValueError, match="No pricing rule found"):
            engine.calculate_price(
                karat=24,  # No rule for 24K
                weight_grams=Decimal("10.000"),
                customer_tier=PricingRule.RETAIL,
            )


@pytest.mark.django_db
class TestPriceRecalculationService:
    """Test the price recalculation service."""

    def test_recalculate_all_prices(self, tenant, gold_rate, pricing_rule_retail, inventory_item):
        """Test recalculating all inventory prices."""
        # Set initial price different from calculated
        inventory_item.selling_price = Decimal("700.00")
        inventory_item.save()

        service = PriceRecalculationService(tenant)
        stats = service.recalculate_all_prices()

        # Should have updated the item
        assert stats["total_items"] == 1
        assert stats["updated_items"] == 1
        assert stats["failed_items"] == 0

        # Check price was updated
        inventory_item.refresh_from_db()
        assert inventory_item.selling_price == Decimal("800.00")

        # Check price change was logged
        assert PriceChangeLog.objects.filter(
            tenant=tenant,
            inventory_item=inventory_item,
        ).exists()

    def test_recalculate_by_karat(
        self, tenant, gold_rate, pricing_rule_retail, inventory_item, branch, category
    ):
        """Test recalculating prices for specific karat."""
        # Create another item with different karat
        item_24k = InventoryItem.objects.create(
            tenant=tenant,
            sku="TEST-002",
            name="24K Gold Ring",
            category=category,
            karat=24,
            weight_grams=Decimal("10.000"),
            cost_price=Decimal("700.00"),
            selling_price=Decimal("900.00"),
            quantity=3,
            branch=branch,
        )

        # Set initial price different from calculated
        inventory_item.selling_price = Decimal("700.00")
        inventory_item.save()

        service = PriceRecalculationService(tenant)
        stats = service.recalculate_by_karat(karat=22)

        # Should only update 22K item
        assert stats["total_items"] == 1
        assert stats["updated_items"] == 1

        # Check 22K item was updated
        inventory_item.refresh_from_db()
        assert inventory_item.selling_price == Decimal("800.00")

        # Check 24K item was not updated
        item_24k.refresh_from_db()
        assert item_24k.selling_price == Decimal("900.00")

    def test_skip_unchanged_prices(self, tenant, gold_rate, pricing_rule_retail, inventory_item):
        """Test that unchanged prices are skipped."""
        # Set price to calculated value
        inventory_item.selling_price = Decimal("800.00")
        inventory_item.save()

        service = PriceRecalculationService(tenant)
        stats = service.recalculate_all_prices()

        # Should skip the item
        assert stats["total_items"] == 1
        assert stats["updated_items"] == 0
        assert stats["skipped_items"] == 1


@pytest.mark.django_db
class TestPriceOverrideService:
    """Test the price override service."""

    def test_request_price_override(
        self, tenant, employee, inventory_item, gold_rate, pricing_rule_retail
    ):
        """Test requesting a price override."""
        service = PriceOverrideService(tenant)

        override = service.request_price_override(
            inventory_item=inventory_item,
            new_price=Decimal("750.00"),
            reason="Customer negotiation",
            requested_by=employee,
        )

        assert override.status == PriceOverrideRequest.PENDING
        assert override.requested_price == Decimal("750.00")
        assert override.current_price == inventory_item.selling_price
        assert override.requested_by == employee

        # Check deviation calculation
        assert override.deviation_amount == Decimal("750.00") - Decimal("800.00")
        assert override.deviation_percentage < 0  # Negative because it's a decrease

    def test_approve_price_override(
        self, tenant, employee, manager, inventory_item, gold_rate, pricing_rule_retail
    ):
        """Test approving a price override."""
        service = PriceOverrideService(tenant)

        # Request override
        override = service.request_price_override(
            inventory_item=inventory_item,
            new_price=Decimal("750.00"),
            reason="Customer negotiation",
            requested_by=employee,
        )

        # Approve override
        result = service.approve_override(
            override_request=override,
            approved_by=manager,
            notes="Approved for loyal customer",
        )

        assert result is True

        # Check override status
        override.refresh_from_db()
        assert override.status == PriceOverrideRequest.APPROVED
        assert override.reviewed_by == manager

        # Check item price was updated
        inventory_item.refresh_from_db()
        assert inventory_item.selling_price == Decimal("750.00")

        # Check price change was logged
        assert PriceChangeLog.objects.filter(
            tenant=tenant,
            inventory_item=inventory_item,
            new_price=Decimal("750.00"),
        ).exists()

    def test_reject_price_override(
        self, tenant, employee, manager, inventory_item, gold_rate, pricing_rule_retail
    ):
        """Test rejecting a price override."""
        service = PriceOverrideService(tenant)

        # Request override
        override = service.request_price_override(
            inventory_item=inventory_item,
            new_price=Decimal("600.00"),  # Too low
            reason="Customer request",
            requested_by=employee,
        )

        original_price = inventory_item.selling_price

        # Reject override
        result = service.reject_override(
            override_request=override,
            rejected_by=manager,
            rejection_reason="Price too low, below cost",
        )

        assert result is True

        # Check override status
        override.refresh_from_db()
        assert override.status == PriceOverrideRequest.REJECTED
        assert override.reviewed_by == manager
        assert "too low" in override.rejection_reason

        # Check item price was NOT updated
        inventory_item.refresh_from_db()
        assert inventory_item.selling_price == original_price

    def test_cannot_approve_own_request(
        self, tenant, manager, inventory_item, gold_rate, pricing_rule_retail
    ):
        """Test that users cannot approve their own override requests."""
        service = PriceOverrideService(tenant)

        # Manager requests override
        override = service.request_price_override(
            inventory_item=inventory_item,
            new_price=Decimal("750.00"),
            reason="Special discount",
            requested_by=manager,
        )

        # Manager tries to approve own request
        with pytest.raises(ValueError, match="does not have permission"):
            service.approve_override(
                override_request=override,
                approved_by=manager,
                notes="Self-approval",
            )

    def test_employee_cannot_approve(
        self, tenant, employee, inventory_item, gold_rate, pricing_rule_retail
    ):
        """Test that employees cannot approve override requests."""
        service = PriceOverrideService(tenant)

        # Create another employee
        employee2 = User.objects.create_user(
            username="employee2",
            email="employee2@test.com",
            password="testpass123",
            tenant=tenant,
            branch=inventory_item.branch,
            role="TENANT_EMPLOYEE",
        )

        # Employee requests override
        override = service.request_price_override(
            inventory_item=inventory_item,
            new_price=Decimal("750.00"),
            reason="Customer request",
            requested_by=employee,
        )

        # Another employee tries to approve
        with pytest.raises(ValueError, match="does not have permission"):
            service.approve_override(
                override_request=override,
                approved_by=employee2,
                notes="Approval",
            )

    def test_cannot_process_already_processed_request(
        self, tenant, employee, manager, inventory_item, gold_rate, pricing_rule_retail
    ):
        """Test that already processed requests cannot be processed again."""
        service = PriceOverrideService(tenant)

        # Request and approve override
        override = service.request_price_override(
            inventory_item=inventory_item,
            new_price=Decimal("750.00"),
            reason="Customer negotiation",
            requested_by=employee,
        )

        service.approve_override(
            override_request=override,
            approved_by=manager,
            notes="Approved",
        )

        # Try to approve again
        with pytest.raises(ValueError, match="already APPROVED"):
            service.approve_override(
                override_request=override,
                approved_by=manager,
                notes="Second approval",
            )


@pytest.mark.django_db
class TestPriceChangeLog:
    """Test price change logging."""

    def test_price_change_log_creation(self, tenant, inventory_item):
        """Test creating a price change log."""
        log = PriceChangeLog.objects.create(
            tenant=tenant,
            inventory_item=inventory_item,
            old_price=Decimal("800.00"),
            new_price=Decimal("850.00"),
            reason="Gold rate increase",
        )

        # Check calculations
        assert log.change_amount == Decimal("50.00")
        assert log.change_percentage == Decimal("6.25")  # 50/800 * 100

    def test_price_increase_decrease_detection(self, tenant, inventory_item):
        """Test detecting price increases and decreases."""
        increase_log = PriceChangeLog.objects.create(
            tenant=tenant,
            inventory_item=inventory_item,
            old_price=Decimal("800.00"),
            new_price=Decimal("850.00"),
            reason="Rate increase",
        )

        decrease_log = PriceChangeLog.objects.create(
            tenant=tenant,
            inventory_item=inventory_item,
            old_price=Decimal("850.00"),
            new_price=Decimal("800.00"),
            reason="Rate decrease",
        )

        assert increase_log.is_increase() is True
        assert increase_log.is_decrease() is False

        assert decrease_log.is_increase() is False
        assert decrease_log.is_decrease() is True
