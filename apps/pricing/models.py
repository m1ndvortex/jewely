"""
Pricing models for gold rate management and dynamic pricing.

Implements Requirement 17: Gold Rate and Dynamic Pricing
- Real-time gold rate tracking per gram, tola, and ounce
- Historical rate storage for trend analysis
- Configurable markup rules based on karat, product type, and customer tier
- Support for different pricing tiers (wholesale, retail, VIP)
"""

import uuid
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import Tenant


class GoldRate(models.Model):
    """
    Gold rate tracking model for real-time and historical pricing.

    Stores gold rates from external APIs with support for multiple markets
    and different weight units (gram, tola, ounce).
    """

    # Market choices
    INTERNATIONAL = "INTERNATIONAL"
    LOCAL = "LOCAL"
    LONDON = "LONDON"
    NEW_YORK = "NEW_YORK"
    DUBAI = "DUBAI"
    MUMBAI = "MUMBAI"

    MARKET_CHOICES = [
        (INTERNATIONAL, "International"),
        (LOCAL, "Local Market"),
        (LONDON, "London Gold Market"),
        (NEW_YORK, "New York Gold Market"),
        (DUBAI, "Dubai Gold Market"),
        (MUMBAI, "Mumbai Gold Market"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the gold rate record",
    )

    # Rate information
    rate_per_gram = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Gold rate per gram in local currency",
    )

    rate_per_tola = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Gold rate per tola (11.664 grams) in local currency",
    )

    rate_per_ounce = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Gold rate per troy ounce (31.1035 grams) in local currency",
    )

    # Market and currency information
    market = models.CharField(
        max_length=20,
        choices=MARKET_CHOICES,
        default=INTERNATIONAL,
        help_text="Market from which this rate was fetched",
    )

    currency = models.CharField(
        max_length=3,
        default="USD",
        help_text="Currency code (ISO 4217) for the rates",
    )

    # Metadata
    source = models.CharField(
        max_length=100,
        blank=True,
        help_text="Source API or provider (e.g., GoldAPI, Metals-API)",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this rate is currently active/latest",
    )

    # Timestamps
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="When this rate was recorded",
    )

    fetched_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this rate was fetched from external API",
    )

    class Meta:
        db_table = "pricing_gold_rates"
        ordering = ["-timestamp"]
        verbose_name = "Gold Rate"
        verbose_name_plural = "Gold Rates"
        indexes = [
            # Query patterns for latest rates
            models.Index(
                fields=["market", "is_active", "-timestamp"], name="gold_rate_market_active_idx"
            ),
            models.Index(
                fields=["currency", "is_active", "-timestamp"], name="gold_rate_currency_active_idx"
            ),
            models.Index(fields=["-timestamp"], name="gold_rate_timestamp_idx"),
            # Historical analysis
            models.Index(fields=["market", "currency", "-timestamp"], name="gold_rate_history_idx"),
        ]

    def __str__(self):
        return (
            f"{self.market} - {self.rate_per_gram}/g ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"
        )

    def save(self, *args, **kwargs):
        """
        Override save to calculate derived rates if not provided.

        Conversion factors:
        - 1 tola = 11.664 grams
        - 1 troy ounce = 31.1035 grams
        """
        # Calculate tola rate from gram rate if not provided
        if not self.rate_per_tola and self.rate_per_gram:
            self.rate_per_tola = self.rate_per_gram * Decimal("11.664")

        # Calculate ounce rate from gram rate if not provided
        if not self.rate_per_ounce and self.rate_per_gram:
            self.rate_per_ounce = self.rate_per_gram * Decimal("31.1035")

        super().save(*args, **kwargs)

    @classmethod
    def get_latest_rate(cls, market=INTERNATIONAL, currency="USD"):
        """
        Get the latest active gold rate for a specific market and currency.

        Args:
            market: Market identifier (default: INTERNATIONAL)
            currency: Currency code (default: USD)

        Returns:
            GoldRate instance or None if not found
        """
        return cls.objects.filter(market=market, currency=currency, is_active=True).first()

    @classmethod
    def get_rate_history(cls, market=INTERNATIONAL, currency="USD", days=30):
        """
        Get historical gold rates for trend analysis.

        Args:
            market: Market identifier
            currency: Currency code
            days: Number of days to look back

        Returns:
            QuerySet of GoldRate instances
        """
        from datetime import timedelta

        from django.utils import timezone

        start_date = timezone.now() - timedelta(days=days)
        return cls.objects.filter(
            market=market, currency=currency, timestamp__gte=start_date
        ).order_by("-timestamp")

    def calculate_percentage_change(self, previous_rate):
        """
        Calculate percentage change from a previous rate.

        Args:
            previous_rate: Previous GoldRate instance

        Returns:
            Decimal: Percentage change (positive for increase, negative for decrease)
        """
        if not previous_rate or previous_rate.rate_per_gram == 0:
            return Decimal("0.00")

        change = (
            (self.rate_per_gram - previous_rate.rate_per_gram) / previous_rate.rate_per_gram
        ) * 100
        return change.quantize(Decimal("0.01"))

    def is_significant_change(self, previous_rate, threshold_percent=Decimal("2.00")):
        """
        Check if the rate change is significant enough to trigger alerts.

        Args:
            previous_rate: Previous GoldRate instance
            threshold_percent: Threshold percentage for significant change

        Returns:
            bool: True if change exceeds threshold
        """
        change = abs(self.calculate_percentage_change(previous_rate))
        return change >= threshold_percent


class PricingRule(models.Model):
    """
    Pricing rule model for configurable markup calculations.

    Defines markup rules based on karat, product type, craftsmanship level,
    and customer tier for dynamic pricing calculations.
    """

    # Customer tier choices
    WHOLESALE = "WHOLESALE"
    RETAIL = "RETAIL"
    VIP = "VIP"
    EMPLOYEE = "EMPLOYEE"

    CUSTOMER_TIER_CHOICES = [
        (WHOLESALE, "Wholesale"),
        (RETAIL, "Retail"),
        (VIP, "VIP Customer"),
        (EMPLOYEE, "Employee Discount"),
    ]

    # Product type choices (can be extended)
    RING = "RING"
    NECKLACE = "NECKLACE"
    BRACELET = "BRACELET"
    EARRING = "EARRING"
    PENDANT = "PENDANT"
    CHAIN = "CHAIN"
    BANGLE = "BANGLE"
    OTHER = "OTHER"

    PRODUCT_TYPE_CHOICES = [
        (RING, "Ring"),
        (NECKLACE, "Necklace"),
        (BRACELET, "Bracelet"),
        (EARRING, "Earring"),
        (PENDANT, "Pendant"),
        (CHAIN, "Chain"),
        (BANGLE, "Bangle"),
        (OTHER, "Other"),
    ]

    # Craftsmanship level choices
    HANDMADE = "HANDMADE"
    MACHINE_MADE = "MACHINE_MADE"
    SEMI_HANDMADE = "SEMI_HANDMADE"

    CRAFTSMANSHIP_CHOICES = [
        (HANDMADE, "Handmade"),
        (MACHINE_MADE, "Machine Made"),
        (SEMI_HANDMADE, "Semi-Handmade"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the pricing rule",
    )

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="pricing_rules",
        help_text="Tenant that owns this pricing rule",
    )

    # Rule criteria
    karat = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(24)],
        help_text="Gold karat this rule applies to (1-24)",
    )

    product_type = models.CharField(
        max_length=20,
        choices=PRODUCT_TYPE_CHOICES,
        null=True,
        blank=True,
        help_text="Product type this rule applies to (optional, null means all types)",
    )

    craftsmanship_level = models.CharField(
        max_length=20,
        choices=CRAFTSMANSHIP_CHOICES,
        null=True,
        blank=True,
        help_text="Craftsmanship level this rule applies to (optional, null means all levels)",
    )

    customer_tier = models.CharField(
        max_length=20,
        choices=CUSTOMER_TIER_CHOICES,
        default=RETAIL,
        help_text="Customer tier this rule applies to",
    )

    # Pricing configuration
    markup_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("999.99"))],
        help_text="Markup percentage over gold rate (e.g., 25.50 for 25.5%)",
    )

    fixed_markup_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Fixed amount to add to the calculated price",
    )

    minimum_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Minimum price regardless of calculation (optional)",
    )

    # Labor and making charges
    making_charge_per_gram = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Making charge per gram of gold",
    )

    stone_charge_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
        help_text="Additional charge percentage for stones/gems",
    )

    # Rule metadata
    name = models.CharField(
        max_length=100,
        help_text="Descriptive name for this pricing rule",
    )

    description = models.TextField(
        blank=True,
        help_text="Detailed description of when this rule applies",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this rule is currently active",
    )

    priority = models.IntegerField(
        default=0,
        help_text="Rule priority (higher numbers take precedence in case of conflicts)",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this rule was created",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When this rule was last updated",
    )

    class Meta:
        db_table = "pricing_rules"
        ordering = ["-priority", "karat", "customer_tier"]
        verbose_name = "Pricing Rule"
        verbose_name_plural = "Pricing Rules"
        indexes = [
            # Query patterns for rule matching
            models.Index(
                fields=["tenant", "is_active", "-priority"], name="pricing_rule_tenant_active_idx"
            ),
            models.Index(
                fields=["tenant", "karat", "customer_tier"], name="pricing_rule_lookup_idx"
            ),
            models.Index(
                fields=["tenant", "product_type", "is_active"], name="pricing_rule_product_idx"
            ),
            models.Index(
                fields=["tenant", "craftsmanship_level", "is_active"], name="pricing_rule_craft_idx"
            ),
        ]
        # Ensure unique rules per tenant for specific combinations
        unique_together = [
            ["tenant", "karat", "product_type", "craftsmanship_level", "customer_tier"]
        ]

    def __str__(self):
        parts = [f"{self.karat}K"]
        if self.product_type:
            parts.append(self.product_type)
        if self.craftsmanship_level:
            parts.append(self.craftsmanship_level)
        parts.append(f"{self.customer_tier} ({self.markup_percentage}%)")
        return " - ".join(parts)

    def calculate_price(self, weight_grams, gold_rate_per_gram, stone_value=Decimal("0.00")):
        """
        Calculate the selling price based on this rule.

        Args:
            weight_grams: Weight of the item in grams
            gold_rate_per_gram: Current gold rate per gram
            stone_value: Value of stones/gems in the item (optional)

        Returns:
            Decimal: Calculated selling price
        """
        # Base gold value
        gold_value = weight_grams * gold_rate_per_gram

        # Apply markup percentage
        markup_amount = gold_value * (self.markup_percentage / 100)

        # Add making charges
        making_charges = weight_grams * self.making_charge_per_gram

        # Add stone charges
        stone_charges = stone_value * (self.stone_charge_percentage / 100)

        # Calculate total price
        total_price = (
            gold_value + markup_amount + making_charges + stone_charges + self.fixed_markup_amount
        )

        # Apply minimum price if specified
        if self.minimum_price and total_price < self.minimum_price:
            total_price = self.minimum_price

        return total_price.quantize(Decimal("0.01"))

    def matches_criteria(
        self, karat, product_type=None, craftsmanship_level=None, customer_tier=RETAIL
    ):
        """
        Check if this rule matches the given criteria.

        Args:
            karat: Gold karat
            product_type: Product type (optional)
            craftsmanship_level: Craftsmanship level (optional)
            customer_tier: Customer tier

        Returns:
            bool: True if this rule matches the criteria
        """
        # Check karat match
        if self.karat != karat:
            return False

        # Check customer tier match
        if self.customer_tier != customer_tier:
            return False

        # Check product type match (null means applies to all)
        if self.product_type and self.product_type != product_type:
            return False

        # Check craftsmanship level match (null means applies to all)
        if self.craftsmanship_level and self.craftsmanship_level != craftsmanship_level:
            return False

        return True

    @classmethod
    def find_matching_rule(
        cls, tenant, karat, product_type=None, craftsmanship_level=None, customer_tier=RETAIL
    ):
        """
        Find the best matching pricing rule for given criteria.

        Args:
            tenant: Tenant instance
            karat: Gold karat
            product_type: Product type (optional)
            craftsmanship_level: Craftsmanship level (optional)
            customer_tier: Customer tier

        Returns:
            PricingRule instance or None if no match found
        """
        # Build filter criteria
        filters = {
            "tenant": tenant,
            "karat": karat,
            "customer_tier": customer_tier,
            "is_active": True,
        }

        # Try to find exact match first (including product_type and craftsmanship_level)
        if product_type:
            filters["product_type"] = product_type
        if craftsmanship_level:
            filters["craftsmanship_level"] = craftsmanship_level

        rule = cls.objects.filter(**filters).order_by("-priority").first()
        if rule:
            return rule

        # If no exact match, try without craftsmanship_level
        if craftsmanship_level:
            filters.pop("craftsmanship_level", None)
            rule = cls.objects.filter(**filters).order_by("-priority").first()
            if rule:
                return rule

        # If still no match, try without product_type
        if product_type:
            filters.pop("product_type", None)
            rule = cls.objects.filter(**filters).order_by("-priority").first()
            if rule:
                return rule

        # Finally, try with generic rules (no product_type or craftsmanship_level)
        generic_filters = {
            "tenant": tenant,
            "karat": karat,
            "customer_tier": customer_tier,
            "is_active": True,
            "product_type__isnull": True,
            "craftsmanship_level__isnull": True,
        }

        return cls.objects.filter(**generic_filters).order_by("-priority").first()

    def get_effective_markup(self):
        """
        Get the effective markup percentage including making charges.

        Returns:
            str: Human-readable description of the markup
        """
        parts = [f"{self.markup_percentage}% markup"]

        if self.making_charge_per_gram > 0:
            parts.append(f"{self.making_charge_per_gram}/g making")

        if self.stone_charge_percentage > 0:
            parts.append(f"{self.stone_charge_percentage}% stone charge")

        if self.fixed_markup_amount > 0:
            parts.append(f"+{self.fixed_markup_amount} fixed")

        return ", ".join(parts)


class PriceAlert(models.Model):
    """
    Price alert model for notifying users of significant gold rate changes.

    Allows tenants to set up alerts when gold rates cross specific thresholds
    or change by certain percentages.
    """

    # Alert type choices
    THRESHOLD_ABOVE = "THRESHOLD_ABOVE"
    THRESHOLD_BELOW = "THRESHOLD_BELOW"
    PERCENTAGE_CHANGE = "PERCENTAGE_CHANGE"

    ALERT_TYPE_CHOICES = [
        (THRESHOLD_ABOVE, "Rate Above Threshold"),
        (THRESHOLD_BELOW, "Rate Below Threshold"),
        (PERCENTAGE_CHANGE, "Percentage Change"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the price alert",
    )

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="price_alerts",
        help_text="Tenant that owns this alert",
    )

    # Alert configuration
    name = models.CharField(
        max_length=100,
        help_text="Descriptive name for this alert",
    )

    alert_type = models.CharField(
        max_length=20,
        choices=ALERT_TYPE_CHOICES,
        help_text="Type of alert condition",
    )

    market = models.CharField(
        max_length=20,
        choices=GoldRate.MARKET_CHOICES,
        default=GoldRate.INTERNATIONAL,
        help_text="Market to monitor for this alert",
    )

    # Threshold values
    threshold_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Rate threshold for THRESHOLD_ABOVE/BELOW alerts",
    )

    percentage_threshold = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("100.00"))],
        help_text="Percentage change threshold for PERCENTAGE_CHANGE alerts",
    )

    # Alert settings
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this alert is currently active",
    )

    notify_email = models.BooleanField(
        default=True,
        help_text="Send email notifications",
    )

    notify_sms = models.BooleanField(
        default=False,
        help_text="Send SMS notifications",
    )

    notify_in_app = models.BooleanField(
        default=True,
        help_text="Send in-app notifications",
    )

    # Tracking
    last_triggered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this alert was last triggered",
    )

    trigger_count = models.IntegerField(
        default=0,
        help_text="Number of times this alert has been triggered",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this alert was created",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When this alert was last updated",
    )

    class Meta:
        db_table = "pricing_alerts"
        ordering = ["-created_at"]
        verbose_name = "Price Alert"
        verbose_name_plural = "Price Alerts"
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="price_alert_tenant_active_idx"),
            models.Index(fields=["market", "is_active"], name="price_alert_market_active_idx"),
            models.Index(fields=["alert_type", "is_active"], name="price_alert_type_active_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.tenant.company_name})"

    def check_condition(self, current_rate, previous_rate=None):
        """
        Check if the alert condition is met.

        Args:
            current_rate: Current GoldRate instance
            previous_rate: Previous GoldRate instance (for percentage change alerts)

        Returns:
            bool: True if alert condition is met
        """
        if not self.is_active:
            return False

        if self.alert_type == self.THRESHOLD_ABOVE:
            return current_rate.rate_per_gram >= self.threshold_rate

        elif self.alert_type == self.THRESHOLD_BELOW:
            return current_rate.rate_per_gram <= self.threshold_rate

        elif self.alert_type == self.PERCENTAGE_CHANGE:
            if not previous_rate:
                return False
            change = abs(current_rate.calculate_percentage_change(previous_rate))
            return change >= self.percentage_threshold

        return False

    def trigger_alert(self):
        """
        Mark the alert as triggered and update counters.
        """
        from django.utils import timezone

        self.last_triggered_at = timezone.now()
        self.trigger_count += 1
        self.save(update_fields=["last_triggered_at", "trigger_count"])

    def get_condition_description(self):
        """
        Get a human-readable description of the alert condition.

        Returns:
            str: Description of the alert condition
        """
        if self.alert_type == self.THRESHOLD_ABOVE:
            return f"Rate above {self.threshold_rate}/g"
        elif self.alert_type == self.THRESHOLD_BELOW:
            return f"Rate below {self.threshold_rate}/g"
        elif self.alert_type == self.PERCENTAGE_CHANGE:
            return f"Change ≥ {self.percentage_threshold}%"
        return "Unknown condition"


class PriceChangeLog(models.Model):
    """
    Log of all price changes for audit trail.

    Tracks automatic and manual price changes with reasons and timestamps.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the price change log",
    )

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="price_change_logs",
        help_text="Tenant that owns this log entry",
    )

    inventory_item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.CASCADE,
        related_name="price_changes",
        help_text="Inventory item whose price changed",
    )

    old_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Previous selling price",
    )

    new_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="New selling price",
    )

    change_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Price change amount (new - old)",
    )

    change_percentage = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        help_text="Price change percentage",
    )

    reason = models.TextField(
        help_text="Reason for price change",
    )

    changed_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="price_changes_made",
        help_text="User who made the change (null for automatic changes)",
    )

    changed_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the price was changed",
    )

    class Meta:
        db_table = "pricing_change_logs"
        ordering = ["-changed_at"]
        verbose_name = "Price Change Log"
        verbose_name_plural = "Price Change Logs"
        indexes = [
            models.Index(fields=["tenant", "-changed_at"], name="price_log_tenant_date_idx"),
            models.Index(fields=["inventory_item", "-changed_at"], name="price_log_item_date_idx"),
            models.Index(fields=["-changed_at"], name="price_log_date_idx"),
        ]

    def __str__(self):
        return f"{self.inventory_item.sku}: {self.old_price} → {self.new_price}"

    def save(self, *args, **kwargs):
        """Calculate change amount and percentage if not provided."""
        if not self.change_amount:
            self.change_amount = self.new_price - self.old_price

        if not self.change_percentage and self.old_price > 0:
            self.change_percentage = (self.change_amount / self.old_price) * 100

        super().save(*args, **kwargs)

    def is_increase(self):
        """Check if this was a price increase."""
        return self.new_price > self.old_price

    def is_decrease(self):
        """Check if this was a price decrease."""
        return self.new_price < self.old_price


class PriceOverrideRequest(models.Model):
    """
    Price override request model for manager approval workflow.

    Implements Requirement 17: Manager approval for manual price overrides
    Tracks requests to manually override calculated prices with approval workflow.
    """

    # Status choices
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (PENDING, "Pending Approval"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
        (CANCELLED, "Cancelled"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the override request",
    )

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="price_override_requests",
        help_text="Tenant that owns this request",
    )

    inventory_item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.CASCADE,
        related_name="price_override_requests",
        help_text="Inventory item to override price for",
    )

    # Price information
    current_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Current selling price",
    )

    calculated_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Price calculated by pricing engine",
    )

    requested_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Requested new price",
    )

    deviation_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Deviation from calculated price (requested - calculated)",
    )

    deviation_percentage = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        help_text="Deviation percentage from calculated price",
    )

    # Request details
    reason = models.TextField(
        help_text="Reason for requesting price override",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PENDING,
        help_text="Current status of the request",
    )

    # Workflow tracking
    requested_by = models.ForeignKey(
        "core.User",
        on_delete=models.PROTECT,
        related_name="price_overrides_requested",
        help_text="User who requested the override",
    )

    requested_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the override was requested",
    )

    reviewed_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="price_overrides_reviewed",
        help_text="User who reviewed (approved/rejected) the request",
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the request was reviewed",
    )

    review_notes = models.TextField(
        blank=True,
        help_text="Notes from reviewer",
    )

    rejection_reason = models.TextField(
        blank=True,
        help_text="Reason for rejection",
    )

    class Meta:
        db_table = "pricing_override_requests"
        ordering = ["-requested_at"]
        verbose_name = "Price Override Request"
        verbose_name_plural = "Price Override Requests"
        indexes = [
            models.Index(
                fields=["tenant", "status", "-requested_at"], name="override_tenant_status_idx"
            ),
            models.Index(fields=["inventory_item", "-requested_at"], name="override_item_date_idx"),
            models.Index(fields=["requested_by", "-requested_at"], name="override_requester_idx"),
            models.Index(fields=["status", "-requested_at"], name="override_status_date_idx"),
        ]

    def __str__(self):
        return f"{self.inventory_item.sku}: {self.requested_price} ({self.status})"

    def approve(self, approved_by, notes: str = ""):
        """
        Approve the override request.

        Args:
            approved_by: User approving the request
            notes: Optional approval notes
        """
        from django.utils import timezone

        self.status = self.APPROVED
        self.reviewed_by = approved_by
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        self.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes"])

    def reject(self, rejected_by, rejection_reason: str):
        """
        Reject the override request.

        Args:
            rejected_by: User rejecting the request
            rejection_reason: Reason for rejection
        """
        from django.utils import timezone

        self.status = self.REJECTED
        self.reviewed_by = rejected_by
        self.reviewed_at = timezone.now()
        self.rejection_reason = rejection_reason
        self.save(update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason"])

    def cancel(self):
        """Cancel the override request."""
        self.status = self.CANCELLED
        self.save(update_fields=["status"])

    def is_pending(self):
        """Check if request is pending approval."""
        return self.status == self.PENDING

    def is_approved(self):
        """Check if request was approved."""
        return self.status == self.APPROVED

    def is_rejected(self):
        """Check if request was rejected."""
        return self.status == self.REJECTED

    def get_deviation_display(self):
        """Get human-readable deviation display."""
        sign = "+" if self.deviation_amount >= 0 else ""
        return f"{sign}{self.deviation_amount} ({sign}{self.deviation_percentage:.2f}%)"
