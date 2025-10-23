"""
Tests for gold rate integration and API fetching.

Tests Requirement 17: Gold Rate and Dynamic Pricing
- External API integration
- Rate fetching and storage
- Historical rate tracking
- Alert system
"""

from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase

from apps.core.models import Tenant
from apps.pricing.models import GoldRate, PriceAlert
from apps.pricing.tasks import (
    GoldRateAPIError,
    GoldRateService,
    check_and_trigger_alerts,
    fetch_gold_rates,
)


class TestGoldRateService(TestCase):
    """Test the GoldRateService class for API integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = GoldRateService()

    @patch("apps.pricing.tasks.requests.get")
    def test_fetch_from_goldapi_success(self, mock_get):
        """Test successful gold rate fetch from GoldAPI."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "price": 2000.50,  # Price per troy ounce
            "currency": "USD",
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Create service with API key
        service = GoldRateService()
        service.goldapi_key = "test-api-key"
        result = service.fetch_from_goldapi()

        # Verify result
        self.assertIsInstance(result, dict)
        self.assertIn("rate_per_gram", result)
        self.assertIn("rate_per_tola", result)
        self.assertIn("rate_per_ounce", result)
        self.assertEqual(result["source"], "GoldAPI")
        self.assertEqual(result["currency"], "USD")

        # Verify calculations
        expected_per_gram = Decimal("2000.50") / Decimal("31.1035")
        self.assertAlmostEqual(float(result["rate_per_gram"]), float(expected_per_gram), places=2)

    @patch("apps.pricing.tasks.requests.get")
    def test_fetch_from_goldapi_no_api_key(self, mock_get):
        """Test GoldAPI fetch fails without API key."""
        with patch("apps.pricing.tasks.settings.GOLDAPI_KEY", None):
            with self.assertRaises(GoldRateAPIError) as context:
                self.service.fetch_from_goldapi()

            self.assertIn("not configured", str(context.exception))

    @patch("apps.pricing.tasks.requests.get")
    def test_fetch_from_goldapi_request_failure(self, mock_get):
        """Test GoldAPI fetch handles request failures."""
        # Mock request exception
        mock_get.side_effect = Exception("Network error")

        with patch("apps.pricing.tasks.settings.GOLDAPI_KEY", "test-api-key"):
            with self.assertRaises(GoldRateAPIError):
                self.service.fetch_from_goldapi()

    @patch("apps.pricing.tasks.requests.get")
    def test_fetch_from_goldapi_invalid_response(self, mock_get):
        """Test GoldAPI fetch handles invalid response data."""
        # Mock invalid response
        mock_response = Mock()
        mock_response.json.return_value = {"invalid": "data"}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with patch("apps.pricing.tasks.settings.GOLDAPI_KEY", "test-api-key"):
            with self.assertRaises(GoldRateAPIError):
                self.service.fetch_from_goldapi()

    @patch("apps.pricing.tasks.requests.get")
    def test_fetch_from_metals_api_success(self, mock_get):
        """Test successful gold rate fetch from Metals-API."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "price": 1950.75,  # Price per troy ounce
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = self.service.fetch_from_metals_api()

        # Verify result
        self.assertIsInstance(result, dict)
        self.assertEqual(result["source"], "Metals-API")
        self.assertEqual(result["currency"], "USD")

        # Verify calculations
        expected_per_gram = Decimal("1950.75") / Decimal("31.1035")
        self.assertAlmostEqual(float(result["rate_per_gram"]), float(expected_per_gram), places=2)

    @patch("apps.pricing.tasks.requests.get")
    def test_fetch_gold_rate_with_fallback(self, mock_get):
        """Test gold rate fetch with fallback to secondary source."""
        import requests

        # First call fails, second succeeds
        mock_response = Mock()
        mock_response.json.return_value = {"price": 2000.00}
        mock_response.raise_for_status = Mock()

        # First call to metals-api fails, second call to goldapi succeeds
        def side_effect(*args, **kwargs):
            url = args[0] if args else kwargs.get("url", "")
            if "metals" in url:
                raise requests.RequestException("First source failed")
            return mock_response

        mock_get.side_effect = side_effect

        # Should fallback to second source
        service = GoldRateService()
        service.goldapi_key = "test-api-key"
        result = service.fetch_gold_rate(preferred_source="metals_api")

        self.assertIsInstance(result, dict)
        self.assertIn("rate_per_gram", result)

    @patch("apps.pricing.tasks.requests.get")
    def test_fetch_gold_rate_all_sources_fail(self, mock_get):
        """Test gold rate fetch when all sources fail."""
        import requests

        # All sources fail
        mock_get.side_effect = requests.RequestException("Network error")

        service = GoldRateService()
        service.goldapi_key = "test-api-key"

        with self.assertRaises(GoldRateAPIError) as context:
            service.fetch_gold_rate()

        self.assertIn("All gold rate sources failed", str(context.exception))


class TestFetchGoldRatesTask(TestCase):
    """Test the fetch_gold_rates Celery task."""

    def setUp(self):
        """Set up test fixtures."""
        # Clean up any existing rates
        GoldRate.objects.all().delete()

    @patch("apps.pricing.tasks.GoldRateService.fetch_gold_rate")
    def test_fetch_gold_rates_success(self, mock_fetch):
        """Test successful gold rate fetching and storage."""
        # Mock API response
        mock_fetch.return_value = {
            "rate_per_gram": Decimal("65.50"),
            "rate_per_tola": Decimal("764.00"),
            "rate_per_ounce": Decimal("2037.00"),
            "source": "Metals-API",
            "currency": "USD",
        }

        # Execute task
        result = fetch_gold_rates(market=GoldRate.INTERNATIONAL)

        # Verify result
        self.assertIsNotNone(result)
        self.assertIn("Gold rate updated", result)

        # Verify database record
        latest_rate = GoldRate.get_latest_rate()
        self.assertIsNotNone(latest_rate)
        self.assertEqual(latest_rate.rate_per_gram, Decimal("65.50"))
        self.assertEqual(latest_rate.source, "Metals-API")
        self.assertTrue(latest_rate.is_active)

    @patch("apps.pricing.tasks.GoldRateService.fetch_gold_rate")
    def test_fetch_gold_rates_deactivates_previous(self, mock_fetch):
        """Test that fetching new rates deactivates previous rates."""
        # Create existing rate
        old_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("60.00"),
            rate_per_tola=Decimal("700.00"),
            rate_per_ounce=Decimal("1900.00"),
            market=GoldRate.INTERNATIONAL,
            currency="USD",
            source="Test",
            is_active=True,
        )

        # Mock new API response
        mock_fetch.return_value = {
            "rate_per_gram": Decimal("65.50"),
            "rate_per_tola": Decimal("764.00"),
            "rate_per_ounce": Decimal("2037.00"),
            "source": "Metals-API",
            "currency": "USD",
        }

        # Execute task
        fetch_gold_rates(market=GoldRate.INTERNATIONAL)

        # Verify old rate is deactivated
        old_rate.refresh_from_db()
        self.assertFalse(old_rate.is_active)

        # Verify new rate is active
        latest_rate = GoldRate.get_latest_rate()
        self.assertTrue(latest_rate.is_active)
        self.assertEqual(latest_rate.rate_per_gram, Decimal("65.50"))

    @patch("apps.pricing.tasks.GoldRateService.fetch_gold_rate")
    def test_fetch_gold_rates_stores_historical_data(self, mock_fetch):
        """Test that historical rates are preserved."""
        # Create multiple rates over time
        mock_fetch.return_value = {
            "rate_per_gram": Decimal("65.50"),
            "rate_per_tola": Decimal("764.00"),
            "rate_per_ounce": Decimal("2037.00"),
            "source": "Metals-API",
            "currency": "USD",
        }

        # Fetch rate multiple times
        fetch_gold_rates(market=GoldRate.INTERNATIONAL)
        fetch_gold_rates(market=GoldRate.INTERNATIONAL)
        fetch_gold_rates(market=GoldRate.INTERNATIONAL)

        # Verify all rates are stored
        all_rates = GoldRate.objects.filter(market=GoldRate.INTERNATIONAL)
        self.assertEqual(all_rates.count(), 3)

        # Verify only latest is active
        active_rates = all_rates.filter(is_active=True)
        self.assertEqual(active_rates.count(), 1)


class TestPriceAlertSystem(TestCase):
    """Test the price alert system."""

    def setUp(self):
        """Set up test fixtures."""
        # Import RLS bypass functions
        from apps.core.tenant_context import disable_rls_bypass, enable_rls_bypass

        # Enable RLS bypass to create tenant
        enable_rls_bypass()

        # Create tenant
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop", slug="test-shop", status="ACTIVE"
        )

        # Disable RLS bypass after setup
        disable_rls_bypass()

        # Clean up existing data
        GoldRate.objects.all().delete()
        PriceAlert.objects.all().delete()

    def test_threshold_above_alert(self):
        """Test alert triggers when rate goes above threshold."""
        # Create alert
        alert = PriceAlert.objects.create(
            tenant=self.tenant,
            name="High Rate Alert",
            alert_type=PriceAlert.THRESHOLD_ABOVE,
            market=GoldRate.INTERNATIONAL,
            threshold_rate=Decimal("70.00"),
            is_active=True,
        )

        # Create rates
        previous_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("65.00"),
            rate_per_tola=Decimal("758.00"),
            rate_per_ounce=Decimal("2020.00"),
            market=GoldRate.INTERNATIONAL,
            currency="USD",
            source="Test",
        )

        current_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("72.00"),
            rate_per_tola=Decimal("840.00"),
            rate_per_ounce=Decimal("2240.00"),
            market=GoldRate.INTERNATIONAL,
            currency="USD",
            source="Test",
        )

        # Check condition
        self.assertTrue(alert.check_condition(current_rate, previous_rate))

        # Trigger alert
        check_and_trigger_alerts(current_rate, previous_rate)

        # Verify alert was triggered
        alert.refresh_from_db()
        self.assertIsNotNone(alert.last_triggered_at)
        self.assertEqual(alert.trigger_count, 1)

    def test_threshold_below_alert(self):
        """Test alert triggers when rate goes below threshold."""
        # Create alert
        alert = PriceAlert.objects.create(
            tenant=self.tenant,
            name="Low Rate Alert",
            alert_type=PriceAlert.THRESHOLD_BELOW,
            market=GoldRate.INTERNATIONAL,
            threshold_rate=Decimal("60.00"),
            is_active=True,
        )

        # Create rates
        previous_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("65.00"),
            rate_per_tola=Decimal("758.00"),
            rate_per_ounce=Decimal("2020.00"),
            market=GoldRate.INTERNATIONAL,
            currency="USD",
            source="Test",
        )

        current_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("58.00"),
            rate_per_tola=Decimal("677.00"),
            rate_per_ounce=Decimal("1804.00"),
            market=GoldRate.INTERNATIONAL,
            currency="USD",
            source="Test",
        )

        # Check condition
        self.assertTrue(alert.check_condition(current_rate, previous_rate))

    def test_percentage_change_alert(self):
        """Test alert triggers on percentage change."""
        # Create alert for 5% change
        alert = PriceAlert.objects.create(
            tenant=self.tenant,
            name="Significant Change Alert",
            alert_type=PriceAlert.PERCENTAGE_CHANGE,
            market=GoldRate.INTERNATIONAL,
            percentage_threshold=Decimal("5.00"),
            is_active=True,
        )

        # Create rates with >5% change
        previous_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("60.00"),
            rate_per_tola=Decimal("700.00"),
            rate_per_ounce=Decimal("1866.00"),
            market=GoldRate.INTERNATIONAL,
            currency="USD",
            source="Test",
        )

        current_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("64.00"),  # 6.67% increase
            rate_per_tola=Decimal("746.00"),
            rate_per_ounce=Decimal("1990.00"),
            market=GoldRate.INTERNATIONAL,
            currency="USD",
            source="Test",
        )

        # Check condition
        self.assertTrue(alert.check_condition(current_rate, previous_rate))

    def test_inactive_alert_not_triggered(self):
        """Test that inactive alerts are not triggered."""
        # Create inactive alert
        alert = PriceAlert.objects.create(
            tenant=self.tenant,
            name="Inactive Alert",
            alert_type=PriceAlert.THRESHOLD_ABOVE,
            market=GoldRate.INTERNATIONAL,
            threshold_rate=Decimal("70.00"),
            is_active=False,  # Inactive
        )

        # Create rates that would trigger the alert
        previous_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("65.00"),
            rate_per_tola=Decimal("758.00"),
            rate_per_ounce=Decimal("2020.00"),
            market=GoldRate.INTERNATIONAL,
            currency="USD",
            source="Test",
        )

        current_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("72.00"),
            rate_per_tola=Decimal("840.00"),
            rate_per_ounce=Decimal("2240.00"),
            market=GoldRate.INTERNATIONAL,
            currency="USD",
            source="Test",
        )

        # Check condition - should return False for inactive alert
        self.assertFalse(alert.check_condition(current_rate, previous_rate))

        # Trigger alerts
        check_and_trigger_alerts(current_rate, previous_rate)

        # Verify alert was NOT triggered
        alert.refresh_from_db()
        self.assertIsNone(alert.last_triggered_at)
        self.assertEqual(alert.trigger_count, 0)


class TestGoldRateModel(TestCase):
    """Test GoldRate model methods."""

    def setUp(self):
        """Set up test fixtures."""
        GoldRate.objects.all().delete()

    def test_get_latest_rate(self):
        """Test retrieving the latest active rate."""
        # Create multiple rates
        GoldRate.objects.create(
            rate_per_gram=Decimal("60.00"),
            rate_per_tola=Decimal("700.00"),
            rate_per_ounce=Decimal("1866.00"),
            market=GoldRate.INTERNATIONAL,
            currency="USD",
            source="Test",
            is_active=False,
        )

        latest_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("65.00"),
            rate_per_tola=Decimal("758.00"),
            rate_per_ounce=Decimal("2020.00"),
            market=GoldRate.INTERNATIONAL,
            currency="USD",
            source="Test",
            is_active=True,
        )

        # Get latest rate
        result = GoldRate.get_latest_rate()

        self.assertEqual(result.id, latest_rate.id)
        self.assertEqual(result.rate_per_gram, Decimal("65.00"))

    def test_calculate_percentage_change(self):
        """Test percentage change calculation."""
        previous_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("60.00"),
            rate_per_tola=Decimal("700.00"),
            rate_per_ounce=Decimal("1866.00"),
            market=GoldRate.INTERNATIONAL,
            currency="USD",
            source="Test",
        )

        current_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("66.00"),  # 10% increase
            rate_per_tola=Decimal("770.00"),
            rate_per_ounce=Decimal("2053.00"),
            market=GoldRate.INTERNATIONAL,
            currency="USD",
            source="Test",
        )

        change = current_rate.calculate_percentage_change(previous_rate)

        self.assertEqual(change, Decimal("10.00"))

    def test_is_significant_change(self):
        """Test significant change detection."""
        previous_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("60.00"),
            rate_per_tola=Decimal("700.00"),
            rate_per_ounce=Decimal("1866.00"),
            market=GoldRate.INTERNATIONAL,
            currency="USD",
            source="Test",
        )

        # Small change (1%)
        small_change_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("60.60"),
            rate_per_tola=Decimal("707.00"),
            rate_per_ounce=Decimal("1885.00"),
            market=GoldRate.INTERNATIONAL,
            currency="USD",
            source="Test",
        )

        # Large change (5%)
        large_change_rate = GoldRate.objects.create(
            rate_per_gram=Decimal("63.00"),
            rate_per_tola=Decimal("735.00"),
            rate_per_ounce=Decimal("1960.00"),
            market=GoldRate.INTERNATIONAL,
            currency="USD",
            source="Test",
        )

        # Test with default threshold (2%)
        self.assertFalse(small_change_rate.is_significant_change(previous_rate))
        self.assertTrue(large_change_rate.is_significant_change(previous_rate))

    def test_get_rate_history(self):
        """Test retrieving historical rates."""
        # Create rates over time
        for i in range(5):
            GoldRate.objects.create(
                rate_per_gram=Decimal(f"{60 + i}.00"),
                rate_per_tola=Decimal(f"{700 + i * 10}.00"),
                rate_per_ounce=Decimal(f"{1866 + i * 30}.00"),
                market=GoldRate.INTERNATIONAL,
                currency="USD",
                source="Test",
            )

        # Get history
        history = GoldRate.get_rate_history(days=30)

        self.assertEqual(history.count(), 5)
        # Should be ordered by timestamp descending
        self.assertEqual(history.first().rate_per_gram, Decimal("64.00"))
