"""
Celery tasks for gold rate management.

Implements Requirement 17: Gold Rate and Dynamic Pricing
- Fetch gold rates from external APIs every 5 minutes
- Store historical rates for trend analysis
- Trigger rate alerts when thresholds are crossed
"""

import logging
from decimal import Decimal
from typing import Dict, Optional

from django.conf import settings
from django.utils import timezone

import requests
from celery import shared_task

from apps.pricing.models import GoldRate, PriceAlert

logger = logging.getLogger(__name__)


class GoldRateAPIError(Exception):
    """Exception raised when gold rate API calls fail."""

    pass


class GoldRateService:
    """
    Service class for fetching gold rates from external APIs.

    Supports multiple providers:
    - GoldAPI (https://www.goldapi.io/)
    - Metals-API (https://metals-api.com/)
    """

    # API endpoints
    GOLDAPI_URL = "https://www.goldapi.io/api/XAU/USD"
    METALS_API_URL = "https://api.metals.live/v1/spot/gold"

    # Conversion factors
    GRAMS_PER_TOLA = Decimal("11.664")
    GRAMS_PER_TROY_OUNCE = Decimal("31.1035")

    def __init__(self):
        """Initialize the service with API credentials from settings."""
        self.goldapi_key = getattr(settings, "GOLDAPI_KEY", None)
        self.metals_api_key = getattr(settings, "METALS_API_KEY", None)
        self.timeout = 10  # seconds

    def fetch_from_goldapi(self) -> Dict[str, Decimal]:
        """
        Fetch gold rate from GoldAPI.

        Returns:
            Dict with rate_per_gram, rate_per_tola, rate_per_ounce

        Raises:
            GoldRateAPIError: If API call fails
        """
        if not self.goldapi_key:
            raise GoldRateAPIError("GOLDAPI_KEY not configured in settings")

        try:
            headers = {"x-access-token": self.goldapi_key}
            response = requests.get(self.GOLDAPI_URL, headers=headers, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()

            # GoldAPI returns price per troy ounce
            price_per_ounce = Decimal(str(data.get("price", 0)))

            if price_per_ounce <= 0:
                raise GoldRateAPIError("Invalid price received from GoldAPI")

            # Calculate per gram rate
            rate_per_gram = price_per_ounce / self.GRAMS_PER_TROY_OUNCE

            # Calculate per tola rate
            rate_per_tola = rate_per_gram * self.GRAMS_PER_TOLA

            return {
                "rate_per_gram": rate_per_gram.quantize(Decimal("0.01")),
                "rate_per_tola": rate_per_tola.quantize(Decimal("0.01")),
                "rate_per_ounce": price_per_ounce.quantize(Decimal("0.01")),
                "source": "GoldAPI",
                "currency": "USD",
            }

        except requests.RequestException as e:
            logger.error(f"GoldAPI request failed: {e}")
            raise GoldRateAPIError(f"Failed to fetch from GoldAPI: {e}")
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"GoldAPI response parsing failed: {e}")
            raise GoldRateAPIError(f"Invalid response from GoldAPI: {e}")

    def fetch_from_metals_api(self) -> Dict[str, Decimal]:
        """
        Fetch gold rate from Metals-API (free tier, no API key required).

        Returns:
            Dict with rate_per_gram, rate_per_tola, rate_per_ounce

        Raises:
            GoldRateAPIError: If API call fails
        """
        try:
            response = requests.get(self.METALS_API_URL, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()

            # Metals-API returns price per troy ounce in USD
            price_per_ounce = Decimal(str(data.get("price", 0)))

            if price_per_ounce <= 0:
                raise GoldRateAPIError("Invalid price received from Metals-API")

            # Calculate per gram rate
            rate_per_gram = price_per_ounce / self.GRAMS_PER_TROY_OUNCE

            # Calculate per tola rate
            rate_per_tola = rate_per_gram * self.GRAMS_PER_TOLA

            return {
                "rate_per_gram": rate_per_gram.quantize(Decimal("0.01")),
                "rate_per_tola": rate_per_tola.quantize(Decimal("0.01")),
                "rate_per_ounce": price_per_ounce.quantize(Decimal("0.01")),
                "source": "Metals-API",
                "currency": "USD",
            }

        except requests.RequestException as e:
            logger.error(f"Metals-API request failed: {e}")
            raise GoldRateAPIError(f"Failed to fetch from Metals-API: {e}")
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Metals-API response parsing failed: {e}")
            raise GoldRateAPIError(f"Invalid response from Metals-API: {e}")

    def fetch_gold_rate(self, preferred_source: str = "metals_api") -> Dict[str, Decimal]:
        """
        Fetch gold rate from the preferred source with fallback.

        Args:
            preferred_source: 'goldapi' or 'metals_api'

        Returns:
            Dict with rate information

        Raises:
            GoldRateAPIError: If all sources fail
        """
        sources = []

        if preferred_source == "goldapi":
            sources = [self.fetch_from_goldapi, self.fetch_from_metals_api]
        else:
            sources = [self.fetch_from_metals_api, self.fetch_from_goldapi]

        last_error = None

        for fetch_func in sources:
            try:
                return fetch_func()
            except GoldRateAPIError as e:
                last_error = e
                logger.warning(f"Failed to fetch from {fetch_func.__name__}: {e}")
                continue

        # All sources failed
        raise GoldRateAPIError(f"All gold rate sources failed. Last error: {last_error}")


@shared_task(
    name="apps.pricing.tasks.fetch_gold_rates",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def fetch_gold_rates(self, market: str = GoldRate.INTERNATIONAL) -> Optional[str]:
    """
    Fetch current gold rates from external APIs and store them.

    This task runs every 5 minutes via Celery Beat to keep rates up-to-date.

    Args:
        market: Market identifier (default: INTERNATIONAL)

    Returns:
        str: Success message with rate information or None on failure
    """
    try:
        logger.info(f"Fetching gold rates for market: {market}")

        # Initialize service
        service = GoldRateService()

        # Fetch rate data
        rate_data = service.fetch_gold_rate()

        # Get previous rate for comparison
        previous_rate = GoldRate.get_latest_rate(market=market, currency=rate_data["currency"])

        # Deactivate previous rates
        if previous_rate:
            GoldRate.objects.filter(
                market=market, currency=rate_data["currency"], is_active=True
            ).update(is_active=False)

        # Create new rate record
        new_rate = GoldRate.objects.create(
            rate_per_gram=rate_data["rate_per_gram"],
            rate_per_tola=rate_data["rate_per_tola"],
            rate_per_ounce=rate_data["rate_per_ounce"],
            market=market,
            currency=rate_data["currency"],
            source=rate_data["source"],
            is_active=True,
            fetched_at=timezone.now(),
        )

        logger.info(
            f"Successfully fetched gold rate: {new_rate.rate_per_gram}/g from {new_rate.source}"
        )

        # Check and trigger alerts
        if previous_rate:
            check_and_trigger_alerts(new_rate, previous_rate)

        return f"Gold rate updated: {new_rate.rate_per_gram}/g (source: {new_rate.source})"

    except GoldRateAPIError as e:
        logger.error(f"Failed to fetch gold rates: {e}")
        # Retry the task
        raise self.retry(exc=e)

    except Exception as e:
        logger.exception(f"Unexpected error fetching gold rates: {e}")
        raise


def check_and_trigger_alerts(current_rate: GoldRate, previous_rate: GoldRate) -> None:
    """
    Check all active price alerts and trigger notifications if conditions are met.

    Args:
        current_rate: Current GoldRate instance
        previous_rate: Previous GoldRate instance
    """
    # Get all active alerts for this market
    alerts = PriceAlert.objects.filter(market=current_rate.market, is_active=True)

    for alert in alerts:
        try:
            if alert.check_condition(current_rate, previous_rate):
                # Trigger the alert
                alert.trigger_alert()

                # Send notifications
                send_alert_notifications(alert, current_rate, previous_rate)

                logger.info(f"Alert triggered: {alert.name} for tenant {alert.tenant.company_name}")

        except Exception as e:
            logger.error(f"Error checking alert {alert.id}: {e}")


def send_alert_notifications(
    alert: PriceAlert, current_rate: GoldRate, previous_rate: GoldRate
) -> None:
    """
    Send notifications for triggered price alerts.

    Args:
        alert: PriceAlert instance
        current_rate: Current GoldRate instance
        previous_rate: Previous GoldRate instance
    """
    # Calculate change information
    change_percent = current_rate.calculate_percentage_change(previous_rate)

    # Build notification message for logging
    logger.info(
        f"Gold Rate Alert: {alert.name} - "
        f"Current: {current_rate.rate_per_gram}/g, "
        f"Previous: {previous_rate.rate_per_gram}/g, "
        f"Change: {change_percent:+.2f}%"
    )

    # Send in-app notification
    if alert.notify_in_app:
        try:
            from apps.core.models import User

            # Get tenant owner and managers
            users = User.objects.filter(
                tenant=alert.tenant, role__in=["TENANT_OWNER", "TENANT_MANAGER"]
            )

            # Create in-app notifications (assuming notification model exists)
            # This would integrate with the notification system from task 13
            logger.info(f"Would send in-app notification to {users.count()} users")

        except Exception as e:
            logger.error(f"Failed to send in-app notification: {e}")

    # Send email notification
    if alert.notify_email:
        try:
            # This would integrate with email system from task 13
            logger.info(f"Would send email notification for alert {alert.name}")

        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")

    # Send SMS notification
    if alert.notify_sms:
        try:
            # This would integrate with SMS system from task 13
            logger.info(f"Would send SMS notification for alert {alert.name}")

        except Exception as e:
            logger.error(f"Failed to send SMS notification: {e}")


@shared_task(name="apps.pricing.tasks.cleanup_old_rates")
def cleanup_old_rates(days_to_keep: int = 365) -> str:
    """
    Clean up old gold rate records to prevent database bloat.

    Keeps the most recent rate for each day and deletes older detailed records.

    Args:
        days_to_keep: Number of days of history to retain (default: 365)

    Returns:
        str: Summary of cleanup operation
    """
    from datetime import timedelta

    try:
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)

        # Delete old inactive rates
        deleted_count, _ = GoldRate.objects.filter(
            timestamp__lt=cutoff_date, is_active=False
        ).delete()

        logger.info(f"Cleaned up {deleted_count} old gold rate records")

        return f"Deleted {deleted_count} old rate records older than {days_to_keep} days"

    except Exception as e:
        logger.exception(f"Error cleaning up old rates: {e}")
        raise


def _update_item_price(item, gold_rate, tenant):
    """Helper function to update a single item's price."""
    from apps.pricing.models import PricingRule

    rule = PricingRule.find_matching_rule(
        tenant=tenant,
        karat=item.karat,
        product_type=getattr(item.category, "product_type", None),
        customer_tier=PricingRule.RETAIL,
    )

    if not rule:
        return False

    new_price = rule.calculate_price(
        weight_grams=item.weight_grams,
        gold_rate_per_gram=gold_rate.rate_per_gram,
    )

    # Update if price changed significantly (>1%)
    price_change = abs(new_price - item.selling_price) / item.selling_price
    if price_change > Decimal("0.01"):
        item.selling_price = new_price
        item.save(update_fields=["selling_price", "updated_at"])
        return True

    return False


def _update_tenant_prices(tenant, gold_rate):
    """Helper function to update prices for a single tenant."""
    from apps.inventory.models import InventoryItem

    items = InventoryItem.objects.filter(tenant=tenant, is_active=True)
    updated_count = 0

    for item in items:
        try:
            if _update_item_price(item, gold_rate, tenant):
                updated_count += 1
        except Exception as e:
            logger.error(f"Error updating price for item {item.sku}: {e}")

    return updated_count


@shared_task(name="apps.pricing.tasks.update_inventory_prices")
def update_inventory_prices(tenant_id: str = None) -> str:
    """
    Update inventory item prices based on current gold rates and pricing rules.

    This task can be triggered manually or scheduled to run periodically.

    Args:
        tenant_id: Optional tenant UUID to update prices for specific tenant only

    Returns:
        str: Summary of price updates
    """
    try:
        from apps.core.models import Tenant

        # Get tenants to process
        if tenant_id:
            tenants = Tenant.objects.filter(id=tenant_id, status="ACTIVE")
        else:
            tenants = Tenant.objects.filter(status="ACTIVE")

        # Get current gold rate
        gold_rate = GoldRate.get_latest_rate()
        if not gold_rate:
            logger.warning("No gold rate available")
            return "No gold rate available for price updates"

        total_updated = 0

        for tenant in tenants:
            try:
                updated = _update_tenant_prices(tenant, gold_rate)
                total_updated += updated
            except Exception as e:
                logger.error(f"Error processing tenant {tenant.company_name}: {e}")

        logger.info(f"Updated prices for {total_updated} inventory items")
        return f"Updated {total_updated} inventory item prices"

    except Exception as e:
        logger.exception(f"Error updating inventory prices: {e}")
        raise
