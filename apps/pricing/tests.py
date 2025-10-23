"""
Tests for pricing models.

Tests the GoldRate and PricingRule models functionality including:
- Model creation and validation
- Index usage for efficient querying
- Business logic methods
"""

from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase

from apps.core.models import Tenant

from .models import GoldRate, PriceAlert, PricingRule


class GoldRateModelTest(TestCase):
    """Test GoldRate model functionality."""

    def setUp(self):
        """Set up test data."""
        self.gold_rate_data = {
            "rate_per_gram": Decimal("50.00"),
            "rate_per_tola": Decimal("583.20"),  # 50 * 11.664
            "rate_per_ounce": Decimal("1555.18"),  # 50 * 31.1035
            "market": GoldRate.INTERNATIONAL,
            "currency": "USD",
            "source": "Test API",
        }

    def test_create_gold_rate(self):
        """Test creating a gold rate record."""
        gold_rate = GoldRate.objects.create(**self.gold_rate_data)

        self.assertEqual(gold_rate.rate_per_gram, Decimal("50.00"))
        self.assertEqual(gold_rate.market, GoldRate.INTERNATIONAL)
        self.assertEqual(gold_rate.currency, "USD")
        self.assertTrue(gold_rate.is_active)
        self.assertIsNotNone(gold_rate.timestamp)

    def test_auto_calculate_derived_rates(self):
        """Test automatic calculation of tola and ounce rates from gram rate."""
        # Create with only gram rate
        gold_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("60.00"), market=GoldRate.LOCAL, currency="USD"
        )

        # Should auto-calculate tola and ounce rates
        expected_tola = Decimal("60.00") * Decimal("11.664")
        expected_ounce = Decimal("60.00") * Decimal("31.1035")

        self.assertEqual(gold_rate.rate_per_tola, expected_tola)
        self.assertEqual(gold_rate.rate_per_ounce, expected_ounce)

    def test_get_latest_rate(self):
        """Test getting the latest active rate for a market."""
        # Create older rate
        GoldRate.objects.create(
            rate_per_gram=Decimal("45.00"), market=GoldRate.INTERNATIONAL, currency="USD"
        )

        # Create newer rate
        newer_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("50.00"), market=GoldRate.INTERNATIONAL, currency="USD"
        )

        latest = GoldRate.get_latest_rate(GoldRate.INTERNATIONAL, "USD")
        self.assertEqual(latest.id, newer_rate.id)
        self.assertEqual(latest.rate_per_gram, Decimal("50.00"))

    def test_calculate_percentage_change(self):
        """Test percentage change calculation between rates."""
        old_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("50.00"), market=GoldRate.INTERNATIONAL, currency="USD"
        )

        new_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("55.00"), market=GoldRate.INTERNATIONAL, currency="USD"
        )

        change = new_rate.calculate_percentage_change(old_rate)
        self.assertEqual(change, Decimal("10.00"))  # 10% increase

    def test_is_significant_change(self):
        """Test significant change detection."""
        old_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("50.00"), market=GoldRate.INTERNATIONAL, currency="USD"
        )

        # Small change (1%)
        small_change_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("50.50"), market=GoldRate.INTERNATIONAL, currency="USD"
        )

        # Large change (5%)
        large_change_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("52.50"), market=GoldRate.INTERNATIONAL, currency="USD"
        )

        self.assertFalse(small_change_rate.is_significant_change(old_rate, Decimal("2.00")))
        self.assertTrue(large_change_rate.is_significant_change(old_rate, Decimal("2.00")))


class PricingRuleModelTest(TestCase):
    """Test PricingRule model functionality."""

    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(company_name="Test Jewelry Shop", slug="test-shop")

        self.pricing_rule_data = {
            "tenant": self.tenant,
            "name": "Standard 22K Retail",
            "karat": 22,
            "customer_tier": PricingRule.RETAIL,
            "markup_percentage": Decimal("25.00"),
            "making_charge_per_gram": Decimal("5.00"),
        }

    def test_create_pricing_rule(self):
        """Test creating a pricing rule."""
        rule = PricingRule.objects.create(**self.pricing_rule_data)

        self.assertEqual(rule.tenant, self.tenant)
        self.assertEqual(rule.karat, 22)
        self.assertEqual(rule.markup_percentage, Decimal("25.00"))
        self.assertTrue(rule.is_active)

    def test_calculate_price(self):
        """Test price calculation using a pricing rule."""
        rule = PricingRule.objects.create(**self.pricing_rule_data)

        weight = Decimal("10.0")  # 10 grams
        gold_rate = Decimal("50.00")  # $50 per gram

        # Expected calculation:
        # Gold value: 10 * 50 = 500
        # Markup (25%): 500 * 0.25 = 125
        # Making charges: 10 * 5 = 50
        # Total: 500 + 125 + 50 = 675

        price = rule.calculate_price(weight, gold_rate)
        self.assertEqual(price, Decimal("675.00"))

    def test_calculate_price_with_stones(self):
        """Test price calculation with stone charges."""
        rule = PricingRule.objects.create(
            **self.pricing_rule_data, stone_charge_percentage=Decimal("10.00")
        )

        weight = Decimal("5.0")
        gold_rate = Decimal("60.00")
        stone_value = Decimal("100.00")

        # Expected calculation:
        # Gold value: 5 * 60 = 300
        # Markup (25%): 300 * 0.25 = 75
        # Making charges: 5 * 5 = 25
        # Stone charges: 100 * 0.10 = 10
        # Total: 300 + 75 + 25 + 10 = 410

        price = rule.calculate_price(weight, gold_rate, stone_value)
        self.assertEqual(price, Decimal("410.00"))

    def test_minimum_price_enforcement(self):
        """Test minimum price enforcement."""
        rule = PricingRule.objects.create(
            **self.pricing_rule_data, minimum_price=Decimal("1000.00")
        )

        # Calculate a price that would be below minimum
        weight = Decimal("1.0")
        gold_rate = Decimal("50.00")

        price = rule.calculate_price(weight, gold_rate)
        self.assertEqual(price, Decimal("1000.00"))  # Should be minimum price

    def test_matches_criteria(self):
        """Test rule matching criteria."""
        rule = PricingRule.objects.create(
            **self.pricing_rule_data,
            product_type=PricingRule.RING,
            craftsmanship_level=PricingRule.HANDMADE,
        )

        # Exact match
        self.assertTrue(
            rule.matches_criteria(
                karat=22,
                product_type=PricingRule.RING,
                craftsmanship_level=PricingRule.HANDMADE,
                customer_tier=PricingRule.RETAIL,
            )
        )

        # Karat mismatch
        self.assertFalse(
            rule.matches_criteria(
                karat=18,
                product_type=PricingRule.RING,
                craftsmanship_level=PricingRule.HANDMADE,
                customer_tier=PricingRule.RETAIL,
            )
        )

    def test_find_matching_rule(self):
        """Test finding the best matching rule."""
        # Create specific rule
        specific_rule = PricingRule.objects.create(
            tenant=self.tenant,
            name="22K Ring Handmade Retail",
            karat=22,
            product_type=PricingRule.RING,
            craftsmanship_level=PricingRule.HANDMADE,
            customer_tier=PricingRule.RETAIL,
            markup_percentage=Decimal("30.00"),
            priority=10,
        )

        # Create generic rule
        PricingRule.objects.create(
            tenant=self.tenant,
            name="22K Generic Retail",
            karat=22,
            customer_tier=PricingRule.RETAIL,
            markup_percentage=Decimal("25.00"),
            priority=5,
        )

        # Should find specific rule first
        found_rule = PricingRule.find_matching_rule(
            tenant=self.tenant,
            karat=22,
            product_type=PricingRule.RING,
            craftsmanship_level=PricingRule.HANDMADE,
            customer_tier=PricingRule.RETAIL,
        )

        self.assertEqual(found_rule.id, specific_rule.id)

    def test_unique_constraint(self):
        """Test unique constraint on tenant, karat, product_type, craftsmanship_level, customer_tier."""
        PricingRule.objects.create(**self.pricing_rule_data)

        # Try to create duplicate
        with self.assertRaises(IntegrityError):
            PricingRule.objects.create(**self.pricing_rule_data)

    def test_get_effective_markup(self):
        """Test effective markup description."""
        rule = PricingRule.objects.create(
            **self.pricing_rule_data,
            stone_charge_percentage=Decimal("5.00"),
            fixed_markup_amount=Decimal("10.00"),
        )

        markup_desc = rule.get_effective_markup()
        self.assertIn("25.0% markup", markup_desc)
        self.assertIn("5.0/g making", markup_desc)
        self.assertIn("5.0% stone charge", markup_desc)
        self.assertIn("+10.0 fixed", markup_desc)


class PriceAlertModelTest(TestCase):
    """Test PriceAlert model functionality."""

    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(company_name="Test Jewelry Shop", slug="test-shop")

    def test_create_price_alert(self):
        """Test creating a price alert."""
        alert = PriceAlert.objects.create(
            tenant=self.tenant,
            name="High Gold Rate Alert",
            alert_type=PriceAlert.THRESHOLD_ABOVE,
            market=GoldRate.INTERNATIONAL,
            threshold_rate=Decimal("60.00"),
        )

        self.assertEqual(alert.tenant, self.tenant)
        self.assertEqual(alert.alert_type, PriceAlert.THRESHOLD_ABOVE)
        self.assertTrue(alert.is_active)
        self.assertEqual(alert.trigger_count, 0)

    def test_check_threshold_above_condition(self):
        """Test threshold above alert condition."""
        alert = PriceAlert.objects.create(
            tenant=self.tenant,
            name="High Rate Alert",
            alert_type=PriceAlert.THRESHOLD_ABOVE,
            threshold_rate=Decimal("55.00"),
        )

        # Rate below threshold
        low_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("50.00"), market=GoldRate.INTERNATIONAL
        )
        self.assertFalse(alert.check_condition(low_rate))

        # Rate above threshold
        high_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("60.00"), market=GoldRate.INTERNATIONAL
        )
        self.assertTrue(alert.check_condition(high_rate))

    def test_check_percentage_change_condition(self):
        """Test percentage change alert condition."""
        alert = PriceAlert.objects.create(
            tenant=self.tenant,
            name="Rate Change Alert",
            alert_type=PriceAlert.PERCENTAGE_CHANGE,
            percentage_threshold=Decimal("5.00"),
        )

        old_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("50.00"), market=GoldRate.INTERNATIONAL
        )

        # Small change (2%)
        small_change_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("51.00"), market=GoldRate.INTERNATIONAL
        )
        self.assertFalse(alert.check_condition(small_change_rate, old_rate))

        # Large change (10%)
        large_change_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("55.00"), market=GoldRate.INTERNATIONAL
        )
        self.assertTrue(alert.check_condition(large_change_rate, old_rate))

    def test_trigger_alert(self):
        """Test triggering an alert."""
        alert = PriceAlert.objects.create(
            tenant=self.tenant,
            name="Test Alert",
            alert_type=PriceAlert.THRESHOLD_ABOVE,
            threshold_rate=Decimal("55.00"),
        )

        initial_count = alert.trigger_count
        alert.trigger_alert()

        alert.refresh_from_db()
        self.assertEqual(alert.trigger_count, initial_count + 1)
        self.assertIsNotNone(alert.last_triggered_at)

    def test_get_condition_description(self):
        """Test condition description generation."""
        # Threshold above alert
        above_alert = PriceAlert.objects.create(
            tenant=self.tenant,
            name="Above Alert",
            alert_type=PriceAlert.THRESHOLD_ABOVE,
            threshold_rate=Decimal("60.00"),
        )
        self.assertEqual(above_alert.get_condition_description(), "Rate above 60.00/g")

        # Percentage change alert
        change_alert = PriceAlert.objects.create(
            tenant=self.tenant,
            name="Change Alert",
            alert_type=PriceAlert.PERCENTAGE_CHANGE,
            percentage_threshold=Decimal("5.00"),
        )
        self.assertEqual(change_alert.get_condition_description(), "Change ≥ 5.00%")
