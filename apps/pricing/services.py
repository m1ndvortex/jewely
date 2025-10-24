"""
Pricing services for dynamic pricing calculations.

Implements Requirement 17: Gold Rate and Dynamic Pricing
- Pricing calculation engine based on gold rate and markup rules
- Automatic price recalculation when rates change
- Pricing tier system (wholesale, retail, VIP)
- Manager approval for manual price overrides
"""

from decimal import Decimal
from typing import Dict, Optional

from django.db import transaction

from apps.core.models import Tenant, User
from apps.inventory.models import InventoryItem
from apps.pricing.models import GoldRate, PriceAlert, PricingRule


class PricingCalculationEngine:
    """
    Engine for calculating dynamic prices based on gold rates and markup rules.

    Handles:
    - Price calculation using current gold rates
    - Markup rule matching and application
    - Tier-based pricing (wholesale, retail, VIP)
    - Stone and making charges
    """

    def __init__(self, tenant: Tenant):
        """
        Initialize the pricing engine for a specific tenant.

        Args:
            tenant: Tenant instance
        """
        self.tenant = tenant

    def calculate_price(
        self,
        karat: int,
        weight_grams: Decimal,
        product_type: Optional[str] = None,
        craftsmanship_level: Optional[str] = None,
        customer_tier: str = PricingRule.RETAIL,
        stone_value: Decimal = Decimal("0.00"),
        market: str = GoldRate.INTERNATIONAL,
        currency: str = "USD",
    ) -> Dict[str, Decimal]:
        """
        Calculate the selling price for a jewelry item.

        Args:
            karat: Gold karat (1-24)
            weight_grams: Weight in grams
            product_type: Product type (optional)
            craftsmanship_level: Craftsmanship level (optional)
            customer_tier: Customer tier (WHOLESALE, RETAIL, VIP, EMPLOYEE)
            stone_value: Value of stones/gems (default: 0.00)
            market: Gold market to use (default: INTERNATIONAL)
            currency: Currency code (default: USD)

        Returns:
            Dict with price breakdown:
            {
                'gold_value': Decimal,
                'markup_amount': Decimal,
                'making_charges': Decimal,
                'stone_charges': Decimal,
                'fixed_markup': Decimal,
                'total_price': Decimal,
                'gold_rate_per_gram': Decimal,
                'rule_applied': str or None
            }

        Raises:
            ValueError: If no gold rate or pricing rule found
        """
        # Get current gold rate
        gold_rate = GoldRate.get_latest_rate(market=market, currency=currency)
        if not gold_rate:
            raise ValueError(
                f"No active gold rate found for market {market} and currency {currency}"
            )

        # Find matching pricing rule
        pricing_rule = PricingRule.find_matching_rule(
            tenant=self.tenant,
            karat=karat,
            product_type=product_type,
            craftsmanship_level=craftsmanship_level,
            customer_tier=customer_tier,
        )

        if not pricing_rule:
            raise ValueError(
                f"No pricing rule found for {karat}K, {product_type or 'any type'}, "
                f"{craftsmanship_level or 'any craftsmanship'}, {customer_tier}"
            )

        # Calculate price using the rule
        total_price = pricing_rule.calculate_price(
            weight_grams=weight_grams,
            gold_rate_per_gram=gold_rate.rate_per_gram,
            stone_value=stone_value,
        )

        # Calculate breakdown
        gold_value = weight_grams * gold_rate.rate_per_gram
        markup_amount = gold_value * (pricing_rule.markup_percentage / 100)
        making_charges = weight_grams * pricing_rule.making_charge_per_gram
        stone_charges = stone_value * (pricing_rule.stone_charge_percentage / 100)

        return {
            "gold_value": gold_value.quantize(Decimal("0.01")),
            "markup_amount": markup_amount.quantize(Decimal("0.01")),
            "making_charges": making_charges.quantize(Decimal("0.01")),
            "stone_charges": stone_charges.quantize(Decimal("0.01")),
            "fixed_markup": pricing_rule.fixed_markup_amount,
            "total_price": total_price,
            "gold_rate_per_gram": gold_rate.rate_per_gram,
            "rule_applied": str(pricing_rule),
        }

    def calculate_item_price(
        self,
        inventory_item: InventoryItem,
        customer_tier: str = PricingRule.RETAIL,
        stone_value: Decimal = Decimal("0.00"),
    ) -> Dict[str, Decimal]:
        """
        Calculate price for an existing inventory item.

        Args:
            inventory_item: InventoryItem instance
            customer_tier: Customer tier for pricing
            stone_value: Value of stones/gems

        Returns:
            Dict with price breakdown (same as calculate_price)
        """
        return self.calculate_price(
            karat=inventory_item.karat,
            weight_grams=inventory_item.weight_grams,
            product_type=inventory_item.category.name if inventory_item.category else None,
            craftsmanship_level=inventory_item.craftsmanship_level,
            customer_tier=customer_tier,
            stone_value=stone_value,
        )

    def get_tiered_prices(
        self,
        karat: int,
        weight_grams: Decimal,
        product_type: Optional[str] = None,
        craftsmanship_level: Optional[str] = None,
        stone_value: Decimal = Decimal("0.00"),
    ) -> Dict[str, Dict[str, Decimal]]:
        """
        Calculate prices for all customer tiers.

        Args:
            karat: Gold karat
            weight_grams: Weight in grams
            product_type: Product type (optional)
            craftsmanship_level: Craftsmanship level (optional)
            stone_value: Value of stones/gems

        Returns:
            Dict mapping tier names to price breakdowns:
            {
                'WHOLESALE': {...},
                'RETAIL': {...},
                'VIP': {...},
                'EMPLOYEE': {...}
            }
        """
        tiers = [
            PricingRule.WHOLESALE,
            PricingRule.RETAIL,
            PricingRule.VIP,
            PricingRule.EMPLOYEE,
        ]

        tiered_prices = {}
        for tier in tiers:
            try:
                price_breakdown = self.calculate_price(
                    karat=karat,
                    weight_grams=weight_grams,
                    product_type=product_type,
                    craftsmanship_level=craftsmanship_level,
                    customer_tier=tier,
                    stone_value=stone_value,
                )
                tiered_prices[tier] = price_breakdown
            except ValueError:
                # No rule for this tier, skip it
                continue

        return tiered_prices


class PriceRecalculationService:
    """
    Service for automatic price recalculation when gold rates change.

    Handles:
    - Bulk recalculation of inventory prices
    - Selective recalculation based on criteria
    - Price change tracking and logging
    """

    def __init__(self, tenant: Tenant):
        """
        Initialize the recalculation service for a specific tenant.

        Args:
            tenant: Tenant instance
        """
        self.tenant = tenant
        self.engine = PricingCalculationEngine(tenant)

    @transaction.atomic
    def recalculate_all_prices(
        self,
        market: str = GoldRate.INTERNATIONAL,
        currency: str = "USD",
        customer_tier: str = PricingRule.RETAIL,
    ) -> Dict[str, int]:
        """
        Recalculate prices for all active inventory items.

        Args:
            market: Gold market to use
            currency: Currency code
            customer_tier: Customer tier for pricing (default: RETAIL)

        Returns:
            Dict with statistics:
            {
                'total_items': int,
                'updated_items': int,
                'failed_items': int,
                'skipped_items': int
            }
        """
        items = InventoryItem.objects.filter(tenant=self.tenant, is_active=True)

        stats = {
            "total_items": items.count(),
            "updated_items": 0,
            "failed_items": 0,
            "skipped_items": 0,
        }

        for item in items:
            try:
                # Calculate new price
                price_breakdown = self.engine.calculate_item_price(
                    inventory_item=item,
                    customer_tier=customer_tier,
                )

                new_price = price_breakdown["total_price"]

                # Update if price changed
                if item.selling_price != new_price:
                    old_price = item.selling_price
                    item.selling_price = new_price
                    item.save(update_fields=["selling_price", "updated_at"])

                    # Log price change
                    self._log_price_change(item, old_price, new_price, "Automatic recalculation")

                    stats["updated_items"] += 1
                else:
                    stats["skipped_items"] += 1

            except (ValueError, Exception) as e:
                # Log error but continue with other items
                print(f"Failed to recalculate price for {item.sku}: {str(e)}")
                stats["failed_items"] += 1

        return stats

    @transaction.atomic
    def recalculate_by_karat(
        self,
        karat: int,
        customer_tier: str = PricingRule.RETAIL,
    ) -> Dict[str, int]:
        """
        Recalculate prices for items of a specific karat.

        Args:
            karat: Gold karat to recalculate
            customer_tier: Customer tier for pricing

        Returns:
            Dict with statistics (same as recalculate_all_prices)
        """
        items = InventoryItem.objects.filter(
            tenant=self.tenant,
            is_active=True,
            karat=karat,
        )

        stats = {
            "total_items": items.count(),
            "updated_items": 0,
            "failed_items": 0,
            "skipped_items": 0,
        }

        for item in items:
            try:
                price_breakdown = self.engine.calculate_item_price(
                    inventory_item=item,
                    customer_tier=customer_tier,
                )

                new_price = price_breakdown["total_price"]

                if item.selling_price != new_price:
                    old_price = item.selling_price
                    item.selling_price = new_price
                    item.save(update_fields=["selling_price", "updated_at"])

                    self._log_price_change(
                        item, old_price, new_price, f"Recalculation for {karat}K items"
                    )

                    stats["updated_items"] += 1
                else:
                    stats["skipped_items"] += 1

            except (ValueError, Exception) as e:
                print(f"Failed to recalculate price for {item.sku}: {str(e)}")
                stats["failed_items"] += 1

        return stats

    def _log_price_change(
        self,
        item: InventoryItem,
        old_price: Decimal,
        new_price: Decimal,
        reason: str,
    ):
        """
        Log a price change for audit trail.

        Args:
            item: InventoryItem that changed
            old_price: Previous price
            new_price: New price
            reason: Reason for change
        """
        # Import here to avoid circular imports
        from apps.pricing.models import PriceChangeLog

        change_percentage = (
            ((new_price - old_price) / old_price * 100) if old_price > 0 else Decimal("0.00")
        )

        PriceChangeLog.objects.create(
            tenant=self.tenant,
            inventory_item=item,
            old_price=old_price,
            new_price=new_price,
            change_percentage=change_percentage,
            reason=reason,
        )


class PriceOverrideService:
    """
    Service for handling manual price overrides with manager approval.

    Implements manager approval workflow for manual price changes that
    deviate from calculated prices.
    """

    def __init__(self, tenant: Tenant):
        """
        Initialize the override service for a specific tenant.

        Args:
            tenant: Tenant instance
        """
        self.tenant = tenant

    def request_price_override(
        self,
        inventory_item: InventoryItem,
        new_price: Decimal,
        reason: str,
        requested_by: User,
    ):
        """
        Request a manual price override.

        Args:
            inventory_item: Item to override price for
            new_price: Requested new price
            reason: Reason for override
            requested_by: User requesting the override

        Returns:
            PriceOverrideRequest instance

        Raises:
            ValueError: If user doesn't have permission
        """
        # Import here to avoid circular imports
        from apps.pricing.models import PriceOverrideRequest

        # Check if user can request overrides
        if not self._can_request_override(requested_by):
            raise ValueError("User does not have permission to request price overrides")

        # Calculate suggested price for comparison
        engine = PricingCalculationEngine(self.tenant)
        try:
            price_breakdown = engine.calculate_item_price(inventory_item)
            calculated_price = price_breakdown["total_price"]
        except ValueError:
            calculated_price = inventory_item.selling_price

        # Calculate deviation
        deviation_amount = new_price - calculated_price
        deviation_percentage = (
            (deviation_amount / calculated_price * 100) if calculated_price > 0 else Decimal("0.00")
        )

        # Create override request
        override_request = PriceOverrideRequest.objects.create(
            tenant=self.tenant,
            inventory_item=inventory_item,
            current_price=inventory_item.selling_price,
            calculated_price=calculated_price,
            requested_price=new_price,
            deviation_amount=deviation_amount,
            deviation_percentage=deviation_percentage,
            reason=reason,
            requested_by=requested_by,
        )

        return override_request

    @transaction.atomic
    def approve_override(
        self,
        override_request,
        approved_by: User,
        notes: str = "",
    ) -> bool:
        """
        Approve a price override request.

        Args:
            override_request: PriceOverrideRequest to approve
            approved_by: User approving the request
            notes: Optional approval notes

        Returns:
            bool: True if approved successfully

        Raises:
            ValueError: If user cannot approve or request already processed
        """
        # Check if user can approve
        if not self._can_approve_override(approved_by, override_request):
            raise ValueError("User does not have permission to approve this override")

        # Check if already processed
        if override_request.status != "PENDING":
            raise ValueError(f"Override request already {override_request.status}")

        # Approve the request
        override_request.approve(approved_by, notes)

        # Apply the price change
        item = override_request.inventory_item
        old_price = item.selling_price
        item.selling_price = override_request.requested_price
        item.save(update_fields=["selling_price", "updated_at"])

        # Log the price change
        recalc_service = PriceRecalculationService(self.tenant)
        recalc_service._log_price_change(
            item,
            old_price,
            override_request.requested_price,
            f"Manual override approved by {approved_by.username}: {override_request.reason}",
        )

        return True

    def reject_override(
        self,
        override_request,
        rejected_by: User,
        rejection_reason: str,
    ) -> bool:
        """
        Reject a price override request.

        Args:
            override_request: PriceOverrideRequest to reject
            rejected_by: User rejecting the request
            rejection_reason: Reason for rejection

        Returns:
            bool: True if rejected successfully

        Raises:
            ValueError: If user cannot reject or request already processed
        """
        # Check if user can reject
        if not self._can_approve_override(rejected_by, override_request):
            raise ValueError("User does not have permission to reject this override")

        # Check if already processed
        if override_request.status != "PENDING":
            raise ValueError(f"Override request already {override_request.status}")

        # Reject the request
        override_request.reject(rejected_by, rejection_reason)

        return True

    def _can_request_override(self, user: User) -> bool:
        """
        Check if user can request price overrides.

        Args:
            user: User to check

        Returns:
            bool: True if user can request overrides
        """
        # Any employee can request overrides
        return user.tenant_id == self.tenant.id

    def _can_approve_override(
        self,
        user: User,
        override_request,
    ) -> bool:
        """
        Check if user can approve/reject price overrides.

        Args:
            user: User to check
            override_request: Override request to approve/reject

        Returns:
            bool: True if user can approve/reject
        """
        # Must be a manager or owner
        if user.role not in ["TENANT_OWNER", "TENANT_MANAGER"]:
            return False

        # Must be from same tenant
        if user.tenant_id != self.tenant.id:
            return False

        # Cannot approve own requests
        if user == override_request.requested_by:
            return False

        return True


class PriceAlertService:
    """
    Service for checking and triggering price alerts.

    Monitors gold rate changes and triggers alerts when conditions are met.
    """

    def __init__(self, tenant: Tenant):
        """
        Initialize the alert service for a specific tenant.

        Args:
            tenant: Tenant instance
        """
        self.tenant = tenant

    def check_alerts(
        self,
        current_rate: GoldRate,
        previous_rate: Optional[GoldRate] = None,
    ) -> list:
        """
        Check all active alerts for the tenant and trigger if conditions met.

        Args:
            current_rate: Current GoldRate instance
            previous_rate: Previous GoldRate instance (for percentage change alerts)

        Returns:
            List of triggered PriceAlert instances
        """
        alerts = PriceAlert.objects.filter(
            tenant=self.tenant,
            is_active=True,
            market=current_rate.market,
        )

        triggered_alerts = []

        for alert in alerts:
            if alert.check_condition(current_rate, previous_rate):
                alert.trigger_alert()
                triggered_alerts.append(alert)

                # Send notifications
                self._send_alert_notifications(alert, current_rate)

        return triggered_alerts

    def _send_alert_notifications(self, alert: PriceAlert, current_rate: GoldRate):
        """
        Send notifications for a triggered alert.

        Args:
            alert: Triggered PriceAlert instance
            current_rate: Current GoldRate instance
        """
        # TODO: Implement actual notification sending
        # This would integrate with the notification system (email, SMS, in-app)

        message = (
            f"Price Alert: {alert.name}\n"
            f"Condition: {alert.get_condition_description()}\n"
            f"Current Rate: {current_rate.rate_per_gram}/g\n"
            f"Market: {current_rate.market}\n"
            f"Time: {current_rate.timestamp}"
        )

        # Placeholder for notification sending
        print(f"Alert triggered: {message}")
