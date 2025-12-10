"""
Payments app models.

This module contains models for subscription purchases, payment transactions,
and billing cycle discount configurations.

Models:
- SubscriptionDiscount: Configurable discount rules for multi-month purchases
- SubscriptionPurchase: Tracks subscription purchase transactions
- PaymentTransaction: Detailed payment transaction logs
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string


class SubscriptionDiscount(models.Model):
    """
    Configurable discount rules for multi-month subscription purchases.

    Platform administrators can configure discounts for different billing periods:
    - 1 month: typically 0%
    - 3 months: typically 10%
    - 6 months: typically 15%
    - 12 months: typically 20%

    These discounts are applied when tenants purchase subscriptions for
    longer billing periods, incentivizing longer commitments.
    """

    # Billing period choices
    BILLING_PERIOD_CHOICES = [
        (1, "1 Month"),
        (3, "3 Months"),
        (6, "6 Months"),
        (12, "12 Months (1 Year)"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the discount rule",
    )

    billing_period_months = models.IntegerField(
        choices=BILLING_PERIOD_CHOICES,
        unique=True,
        help_text="Number of months for this billing period",
    )

    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="Discount percentage (0-100) for this billing period",
    )

    description = models.CharField(
        max_length=255,
        blank=True,
        help_text="Human-readable description (e.g., 'Save 10% with 3-month billing')",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this discount rule is currently active",
    )

    # Audit fields
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the discount rule was created",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the discount rule was last updated",
    )

    class Meta:
        db_table = "subscription_discounts"
        ordering = ["billing_period_months"]
        verbose_name = "Subscription Discount"
        verbose_name_plural = "Subscription Discounts"

    def __str__(self):
        return f"{self.get_billing_period_months_display()} - {self.discount_percentage}% off"

    @classmethod
    def get_discount_for_period(cls, months: int) -> Decimal:
        """
        Get the discount percentage for a given billing period.

        Args:
            months: Number of months for the billing period

        Returns:
            Discount percentage as a Decimal, or 0 if not found
        """
        try:
            discount = cls.objects.get(billing_period_months=months, is_active=True)
            return discount.discount_percentage
        except cls.DoesNotExist:
            return Decimal("0.00")


class SubscriptionPurchase(models.Model):
    """
    Tracks subscription purchase transactions.

    Each purchase creates or extends a TenantSubscription. This model captures
    all financial and billing details for audit, reporting, and payment tracking.

    Security: This table is protected by Row-Level Security (RLS) to ensure
    tenants can only access their own purchase records.
    """

    # Payment status choices
    PAYMENT_STATUS_PENDING = "pending"
    PAYMENT_STATUS_PROCESSING = "processing"
    PAYMENT_STATUS_COMPLETED = "completed"
    PAYMENT_STATUS_FAILED = "failed"
    PAYMENT_STATUS_REFUNDED = "refunded"
    PAYMENT_STATUS_CANCELLED = "cancelled"

    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_STATUS_PENDING, "Pending"),
        (PAYMENT_STATUS_PROCESSING, "Processing"),
        (PAYMENT_STATUS_COMPLETED, "Completed"),
        (PAYMENT_STATUS_FAILED, "Failed"),
        (PAYMENT_STATUS_REFUNDED, "Refunded"),
        (PAYMENT_STATUS_CANCELLED, "Cancelled"),
    ]

    # Payment method choices (placeholders for future gateways)
    PAYMENT_METHOD_PLACEHOLDER = "placeholder"
    PAYMENT_METHOD_BANK_TRANSFER_IRAN = "bank_transfer_iran"
    PAYMENT_METHOD_PAYPAL = "paypal"
    PAYMENT_METHOD_STRIPE = "stripe"
    PAYMENT_METHOD_CRYPTO_BTC = "crypto_btc"
    PAYMENT_METHOD_CRYPTO_ETH = "crypto_eth"
    PAYMENT_METHOD_CRYPTO_USDT = "crypto_usdt"

    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_METHOD_PLACEHOLDER, "Test/Development"),
        (PAYMENT_METHOD_BANK_TRANSFER_IRAN, "Iranian Bank Transfer"),
        (PAYMENT_METHOD_PAYPAL, "PayPal"),
        (PAYMENT_METHOD_STRIPE, "Credit/Debit Card (Stripe)"),
        (PAYMENT_METHOD_CRYPTO_BTC, "Bitcoin"),
        (PAYMENT_METHOD_CRYPTO_ETH, "Ethereum"),
        (PAYMENT_METHOD_CRYPTO_USDT, "USDT (Tether)"),
    ]

    # Billing period choices
    BILLING_PERIOD_1_MONTH = 1
    BILLING_PERIOD_3_MONTHS = 3
    BILLING_PERIOD_6_MONTHS = 6
    BILLING_PERIOD_12_MONTHS = 12

    BILLING_PERIOD_CHOICES = [
        (BILLING_PERIOD_1_MONTH, "1 Month"),
        (BILLING_PERIOD_3_MONTHS, "3 Months"),
        (BILLING_PERIOD_6_MONTHS, "6 Months"),
        (BILLING_PERIOD_12_MONTHS, "12 Months (1 Year)"),
    ]

    # Currency choices
    CURRENCY_USD = "USD"
    CURRENCY_IRR = "IRR"
    CURRENCY_EUR = "EUR"
    CURRENCY_BTC = "BTC"
    CURRENCY_ETH = "ETH"
    CURRENCY_USDT = "USDT"

    CURRENCY_CHOICES = [
        (CURRENCY_USD, "US Dollar"),
        (CURRENCY_IRR, "Iranian Rial"),
        (CURRENCY_EUR, "Euro"),
        (CURRENCY_BTC, "Bitcoin"),
        (CURRENCY_ETH, "Ethereum"),
        (CURRENCY_USDT, "USDT"),
    ]

    # Purchase type choices
    PURCHASE_TYPE_NEW = "new"
    PURCHASE_TYPE_RENEWAL = "renewal"
    PURCHASE_TYPE_UPGRADE = "upgrade"
    PURCHASE_TYPE_DOWNGRADE = "downgrade"

    PURCHASE_TYPE_CHOICES = [
        (PURCHASE_TYPE_NEW, "New Subscription"),
        (PURCHASE_TYPE_RENEWAL, "Renewal"),
        (PURCHASE_TYPE_UPGRADE, "Plan Upgrade"),
        (PURCHASE_TYPE_DOWNGRADE, "Plan Downgrade"),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the purchase",
    )

    # Relationships
    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        related_name="subscription_purchases",
        help_text="Tenant making the purchase",
    )

    subscription_plan = models.ForeignKey(
        "core.SubscriptionPlan",
        on_delete=models.PROTECT,
        related_name="purchases",
        help_text="Subscription plan being purchased",
    )

    purchased_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="subscription_purchases",
        help_text="User who initiated the purchase",
    )

    # Purchase type
    purchase_type = models.CharField(
        max_length=20,
        choices=PURCHASE_TYPE_CHOICES,
        default=PURCHASE_TYPE_NEW,
        help_text="Type of purchase (new, renewal, upgrade, downgrade)",
    )

    # Previous plan (for upgrades/downgrades)
    previous_plan = models.ForeignKey(
        "core.SubscriptionPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="upgrade_from_purchases",
        help_text="Previous plan (for upgrades/downgrades)",
    )

    # Billing period
    billing_period_months = models.IntegerField(
        choices=BILLING_PERIOD_CHOICES,
        default=BILLING_PERIOD_1_MONTH,
        help_text="Billing period in months",
    )

    start_date = models.DateField(
        help_text="Start date of the subscription period",
    )

    end_date = models.DateField(
        help_text="End date of the subscription period",
    )

    # Pricing
    base_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Base price before discount (plan price × months)",
    )

    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Discount percentage applied",
    )

    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Discount amount in base currency",
    )

    final_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Final price after discount",
    )

    currency = models.CharField(
        max_length=5,
        choices=CURRENCY_CHOICES,
        default=CURRENCY_USD,
        help_text="Currency for the transaction",
    )

    # IRR pricing (for Iranian market)
    base_price_irr = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        null=True,
        blank=True,
        help_text="Base price in Iranian Rial (Toman × 10)",
    )

    final_price_irr = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        null=True,
        blank=True,
        help_text="Final price in Iranian Rial",
    )

    # Payment information
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_STATUS_PENDING,
        help_text="Current payment status",
    )

    payment_method = models.CharField(
        max_length=30,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_METHOD_PLACEHOLDER,
        help_text="Selected payment method",
    )

    payment_gateway_transaction_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Transaction ID from payment gateway",
    )

    payment_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when payment was completed",
    )

    # Invoice
    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique invoice number (e.g., INV-20251209-ABC123)",
    )

    invoice_pdf_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Path to generated invoice PDF",
    )

    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (gateway responses, etc.)",
    )

    # IP and user agent for fraud detection
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the purchaser",
    )

    user_agent = models.CharField(
        max_length=500,
        blank=True,
        help_text="User agent string of the purchaser",
    )

    # Notes
    notes = models.TextField(
        blank=True,
        help_text="Internal notes about this purchase",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the purchase was initiated",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the purchase was last updated",
    )

    class Meta:
        db_table = "subscription_purchases"
        ordering = ["-created_at"]
        verbose_name = "Subscription Purchase"
        verbose_name_plural = "Subscription Purchases"
        indexes = [
            models.Index(fields=["tenant", "payment_status"], name="purchase_tenant_status_idx"),
            models.Index(fields=["payment_status"], name="purchase_payment_status_idx"),
            models.Index(fields=["invoice_number"], name="purchase_invoice_number_idx"),
            models.Index(fields=["created_at"], name="purchase_created_at_idx"),
            models.Index(
                fields=["payment_method", "payment_status"],
                name="purchase_method_status_idx",
            ),
        ]

    def __str__(self):
        return f"{self.invoice_number} - {self.tenant.company_name} - {self.subscription_plan.name}"

    def save(self, *args, **kwargs):
        # Generate invoice number if not set
        if not self.invoice_number:
            self.invoice_number = self._generate_invoice_number()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_invoice_number() -> str:
        """Generate a unique invoice number."""
        date_part = timezone.now().strftime("%Y%m%d")
        random_part = get_random_string(6, "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
        return f"INV-{date_part}-{random_part}"

    def mark_as_completed(self, transaction_id: str = ""):
        """
        Mark the purchase as completed.

        Args:
            transaction_id: Payment gateway transaction ID
        """
        self.payment_status = self.PAYMENT_STATUS_COMPLETED
        self.payment_gateway_transaction_id = transaction_id
        self.payment_completed_at = timezone.now()
        self.save(update_fields=[
            "payment_status",
            "payment_gateway_transaction_id",
            "payment_completed_at",
            "updated_at",
        ])

    def mark_as_failed(self, error_message: str = ""):
        """Mark the purchase as failed."""
        self.payment_status = self.PAYMENT_STATUS_FAILED
        if error_message:
            self.metadata["error_message"] = error_message
        self.save(update_fields=["payment_status", "metadata", "updated_at"])

    def mark_as_refunded(self, reason: str = ""):
        """Mark the purchase as refunded."""
        self.payment_status = self.PAYMENT_STATUS_REFUNDED
        if reason:
            self.metadata["refund_reason"] = reason
        self.save(update_fields=["payment_status", "metadata", "updated_at"])

    @property
    def is_paid(self) -> bool:
        """Check if the purchase has been paid."""
        return self.payment_status == self.PAYMENT_STATUS_COMPLETED

    @property
    def can_be_cancelled(self) -> bool:
        """Check if the purchase can be cancelled."""
        return self.payment_status in [
            self.PAYMENT_STATUS_PENDING,
            self.PAYMENT_STATUS_PROCESSING,
        ]

    @property
    def billing_period_display(self) -> str:
        """Get human-readable billing period."""
        return dict(self.BILLING_PERIOD_CHOICES).get(self.billing_period_months, "Unknown")

    @property
    def savings_amount(self) -> Decimal:
        """Calculate the amount saved with discount."""
        return self.discount_amount

    @property
    def monthly_equivalent_price(self) -> Decimal:
        """Calculate the monthly equivalent price after discount."""
        if self.billing_period_months > 0:
            return self.final_price / self.billing_period_months
        return self.final_price


class PaymentTransaction(models.Model):
    """
    Detailed payment transaction log.

    One SubscriptionPurchase can have multiple payment attempts/transactions.
    This provides detailed logging for audit, debugging, and reconciliation.

    Security: This table is protected by Row-Level Security (RLS).
    """

    # Transaction status choices
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_TIMEOUT = "timeout"
    STATUS_CANCELLED = "cancelled"
    STATUS_REFUNDED = "refunded"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_TIMEOUT, "Timeout"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_REFUNDED, "Refunded"),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the transaction",
    )

    # Relationships
    subscription_purchase = models.ForeignKey(
        SubscriptionPurchase,
        on_delete=models.CASCADE,
        related_name="transactions",
        help_text="Associated subscription purchase",
    )

    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        related_name="payment_transactions",
        help_text="Tenant for RLS enforcement",
    )

    # Transaction details
    transaction_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        help_text="Unique transaction identifier",
    )

    payment_gateway = models.CharField(
        max_length=50,
        help_text="Payment gateway used (e.g., 'paypal', 'stripe', 'crypto')",
    )

    gateway_transaction_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Transaction ID from the payment gateway",
    )

    gateway_reference = models.CharField(
        max_length=255,
        blank=True,
        help_text="Additional gateway reference/tracking number",
    )

    # Amount
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Transaction amount",
    )

    currency = models.CharField(
        max_length=5,
        help_text="Transaction currency",
    )

    exchange_rate = models.DecimalField(
        max_digits=15,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Exchange rate used (for crypto/IRR conversions)",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        help_text="Current transaction status",
    )

    # Gateway response
    request_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Request data sent to gateway",
    )

    response_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Response data from gateway",
    )

    error_message = models.TextField(
        blank=True,
        help_text="Error message if transaction failed",
    )

    error_code = models.CharField(
        max_length=100,
        blank=True,
        help_text="Error code from gateway",
    )

    # Retry tracking
    attempt_number = models.PositiveIntegerField(
        default=1,
        help_text="Attempt number for this transaction",
    )

    is_retry = models.BooleanField(
        default=False,
        help_text="Whether this is a retry attempt",
    )

    # IP tracking for security
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address during transaction",
    )

    # Timestamps
    initiated_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when transaction was initiated",
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when transaction completed",
    )

    class Meta:
        db_table = "payment_transactions"
        ordering = ["-initiated_at"]
        verbose_name = "Payment Transaction"
        verbose_name_plural = "Payment Transactions"
        indexes = [
            models.Index(fields=["tenant", "status"], name="tx_tenant_status_idx"),
            models.Index(fields=["transaction_id"], name="tx_transaction_id_idx"),
            models.Index(fields=["gateway_transaction_id"], name="tx_gateway_id_idx"),
            models.Index(fields=["status"], name="tx_status_idx"),
            models.Index(fields=["initiated_at"], name="tx_initiated_at_idx"),
        ]

    def __str__(self):
        return f"{self.transaction_id} - {self.payment_gateway} - {self.status}"

    def mark_completed(self, gateway_transaction_id: str = "", response_data: dict = None):
        """Mark transaction as completed."""
        self.status = self.STATUS_COMPLETED
        self.completed_at = timezone.now()
        if gateway_transaction_id:
            self.gateway_transaction_id = gateway_transaction_id
        if response_data:
            self.response_data = response_data
        self.save()

    def mark_failed(self, error_message: str = "", error_code: str = "", response_data: dict = None):
        """Mark transaction as failed."""
        self.status = self.STATUS_FAILED
        self.completed_at = timezone.now()
        self.error_message = error_message
        self.error_code = error_code
        if response_data:
            self.response_data = response_data
        self.save()

    @property
    def is_successful(self) -> bool:
        """Check if transaction was successful."""
        return self.status == self.STATUS_COMPLETED

    @property
    def duration_seconds(self) -> float | None:
        """Get transaction duration in seconds."""
        if self.completed_at and self.initiated_at:
            return (self.completed_at - self.initiated_at).total_seconds()
        return None
