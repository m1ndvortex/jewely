"""
CRM models for jewelry shop management.

Implements Requirement 12: Customer Relationship Management (CRM)
- Store customer profiles with contact information, preferences, and notes
- Track complete purchase history for each customer
- Manage customer store credit balances with transaction history
- Implement loyalty program with points accrual and redemption
- Support loyalty tiers (Bronze, Silver, Gold, Platinum) with automatic upgrades
- Track customer communication history including emails, SMS, and calls
- Provide customer segmentation for targeted marketing campaigns
- Generate customer reports including top customers and purchase trends
- Support gift card issuance and balance tracking
- Implement referral program with tracking and rewards

Implements Requirement 36: Enhanced Loyalty Program
- Loyalty tiers with tier-specific benefits including discount percentages
- Automatic customer upgrades based on spending thresholds
- Tier validity periods with renewal requirements
- Point accrual rules based on purchase amount, product categories, and promotions
- Point multipliers during special events or for specific products
- Point redemption for discounts, products, or services
- Point expiration policies to encourage usage
- Point transfers between family members
- Referral tracking with unique referral codes
- Reward both referrer and referee with points, discounts, or credits
- Monitor referral program performance and ROI
"""

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import Tenant

User = get_user_model()


class LoyaltyTier(models.Model):
    """
    Loyalty tier model for customer segmentation and benefits.

    Implements Requirement 36: Enhanced Loyalty Program
    - Define tier-specific benefits including discount percentages
    - Set spending thresholds for automatic upgrades
    - Configure tier validity periods with renewal requirements
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the loyalty tier",
    )

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="loyalty_tiers",
        help_text="Tenant that owns this loyalty tier",
    )

    name = models.CharField(
        max_length=100, help_text="Name of the loyalty tier (e.g., Bronze, Silver, Gold, Platinum)"
    )

    # Tier requirements
    min_spending = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Minimum spending required to achieve this tier",
    )

    # Tier benefits
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
        help_text="Discount percentage for this tier (0-100)",
    )

    points_multiplier = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("1.00"))],
        help_text="Points multiplier for this tier (e.g., 1.5 for 50% bonus points)",
    )

    # Tier validity
    validity_months = models.IntegerField(
        default=12,
        validators=[MinValueValidator(1)],
        help_text="Number of months this tier remains valid without renewal",
    )

    # Benefits description
    benefits_description = models.TextField(
        blank=True,
        help_text="Description of tier benefits (exclusive access, priority service, etc.)",
    )

    # Tier ordering
    order = models.IntegerField(
        default=0, help_text="Order of this tier (0 = lowest, higher numbers = higher tiers)"
    )

    is_active = models.BooleanField(default=True, help_text="Whether this tier is currently active")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, help_text="When the tier was created")

    updated_at = models.DateTimeField(auto_now=True, help_text="When the tier was last updated")

    class Meta:
        db_table = "crm_loyalty_tiers"
        ordering = ["order", "min_spending"]
        verbose_name = "Loyalty Tier"
        verbose_name_plural = "Loyalty Tiers"
        unique_together = [["tenant", "name"]]
        indexes = [
            models.Index(fields=["tenant", "order"], name="tier_tenant_order_idx"),
            models.Index(fields=["tenant", "min_spending"], name="tier_tenant_spending_idx"),
        ]

    def __str__(self):
        return f"{self.name} (${self.min_spending}+)"


class Customer(models.Model):
    """
    Comprehensive customer model for CRM functionality.

    Implements Requirement 12: Customer Relationship Management (CRM)
    - Store customer profiles with contact information and preferences
    - Track purchase history and lifetime value
    - Manage store credit balances
    - Support loyalty program integration
    - Track communication history
    - Enable customer segmentation

    This extends the basic Customer model in sales app with full CRM features.
    """

    # Gender choices
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"
    PREFER_NOT_TO_SAY = "PREFER_NOT_TO_SAY"

    GENDER_CHOICES = [
        (MALE, "Male"),
        (FEMALE, "Female"),
        (OTHER, "Other"),
        (PREFER_NOT_TO_SAY, "Prefer not to say"),
    ]

    # Communication preferences
    EMAIL = "EMAIL"
    SMS = "SMS"
    PHONE = "PHONE"
    MAIL = "MAIL"

    COMMUNICATION_CHOICES = [
        (EMAIL, "Email"),
        (SMS, "SMS"),
        (PHONE, "Phone"),
        (MAIL, "Mail"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the customer",
    )

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="crm_customers",
        help_text="Tenant that owns this customer",
    )

    customer_number = models.CharField(
        max_length=50, help_text="Unique customer number within tenant"
    )

    # Personal information
    first_name = models.CharField(max_length=100, help_text="Customer's first name")

    last_name = models.CharField(max_length=100, help_text="Customer's last name")

    date_of_birth = models.DateField(null=True, blank=True, help_text="Customer's date of birth")

    gender = models.CharField(
        max_length=20, choices=GENDER_CHOICES, blank=True, help_text="Customer's gender"
    )

    # Contact information
    email = models.EmailField(null=True, blank=True, help_text="Customer's email address")

    phone = models.CharField(max_length=20, help_text="Customer's primary phone number")

    alternate_phone = models.CharField(
        max_length=20, blank=True, help_text="Customer's alternate phone number"
    )

    # Address information
    address_line_1 = models.CharField(max_length=255, blank=True, help_text="Address line 1")

    address_line_2 = models.CharField(max_length=255, blank=True, help_text="Address line 2")

    city = models.CharField(max_length=100, blank=True, help_text="City")

    state = models.CharField(max_length=100, blank=True, help_text="State/Province")

    postal_code = models.CharField(max_length=20, blank=True, help_text="Postal/ZIP code")

    country = models.CharField(max_length=100, blank=True, help_text="Country")

    # Loyalty program
    loyalty_tier = models.ForeignKey(
        LoyaltyTier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customers",
        help_text="Customer's current loyalty tier",
    )

    loyalty_points = models.IntegerField(
        default=0, validators=[MinValueValidator(0)], help_text="Current loyalty points balance"
    )

    tier_achieved_at = models.DateTimeField(
        null=True, blank=True, help_text="When the customer achieved their current tier"
    )

    tier_expires_at = models.DateTimeField(
        null=True, blank=True, help_text="When the customer's current tier expires"
    )

    # Financial information
    store_credit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Store credit balance",
    )

    total_purchases = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Total lifetime purchase amount",
    )

    total_points_earned = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Total loyalty points earned (lifetime)",
    )

    total_points_redeemed = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Total loyalty points redeemed (lifetime)",
    )

    # Preferences
    preferred_communication = models.CharField(
        max_length=20,
        choices=COMMUNICATION_CHOICES,
        default=EMAIL,
        help_text="Preferred communication method",
    )

    marketing_opt_in = models.BooleanField(
        default=True, help_text="Whether customer has opted in to marketing communications"
    )

    sms_opt_in = models.BooleanField(
        default=False, help_text="Whether customer has opted in to SMS communications"
    )

    # Referral program
    referral_code = models.CharField(
        max_length=20, unique=True, blank=True, help_text="Unique referral code for this customer"
    )

    referred_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referrals",
        help_text="Customer who referred this customer",
    )

    referral_reward_given = models.BooleanField(
        default=False, help_text="Whether referral reward has been given to the referrer"
    )

    # Customer notes and tags
    notes = models.TextField(blank=True, help_text="Internal notes about the customer")

    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Tags for customer segmentation (e.g., ['VIP', 'Wedding', 'Corporate'])",
    )

    # Customer status
    is_active = models.BooleanField(
        default=True, help_text="Whether the customer account is active"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, help_text="When the customer was created")

    updated_at = models.DateTimeField(auto_now=True, help_text="When the customer was last updated")

    last_purchase_at = models.DateTimeField(
        null=True, blank=True, help_text="When the customer made their last purchase"
    )

    class Meta:
        db_table = "crm_customers"
        ordering = ["-created_at"]
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
        unique_together = [["tenant", "customer_number"]]
        indexes = [
            models.Index(fields=["tenant", "phone"], name="crm_cust_tenant_phone_idx"),
            models.Index(fields=["tenant", "email"], name="crm_cust_tenant_email_idx"),
            models.Index(fields=["tenant", "loyalty_tier"], name="crm_cust_tenant_tier_idx"),
            models.Index(fields=["tenant", "-total_purchases"], name="crm_cust_tenant_purch_idx"),
            models.Index(fields=["tenant", "-last_purchase_at"], name="crm_cust_tenant_last_idx"),
            models.Index(fields=["referral_code"], name="crm_cust_referral_idx"),
            models.Index(fields=["referred_by"], name="crm_cust_referred_idx"),
        ]

    def __str__(self):
        return f"{self.customer_number} - {self.get_full_name()}"

    def get_full_name(self):
        """Return the customer's full name."""
        return f"{self.first_name} {self.last_name}"

    def get_full_address(self):
        """Return the customer's full address."""
        address_parts = [
            self.address_line_1,
            self.address_line_2,
            self.city,
            self.state,
            self.postal_code,
            self.country,
        ]
        return ", ".join(part for part in address_parts if part)

    def save(self, *args, **kwargs):
        """Override save to generate referral code if not provided."""
        if not self.referral_code:
            # Generate unique referral code
            import random
            import string

            while True:
                code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
                if not Customer.objects.filter(referral_code=code).exists():
                    self.referral_code = code
                    break
        super().save(*args, **kwargs)

    def update_loyalty_tier(self):
        """Update customer's loyalty tier based on total purchases."""
        if not self.tenant.loyalty_tiers.exists():
            return

        # Find the highest tier the customer qualifies for
        qualifying_tier = (
            self.tenant.loyalty_tiers.filter(min_spending__lte=self.total_purchases, is_active=True)
            .order_by("-min_spending")
            .first()
        )

        if qualifying_tier and qualifying_tier != self.loyalty_tier:
            self.loyalty_tier = qualifying_tier
            self.tier_achieved_at = timezone.now()

            # Set tier expiration based on tier validity
            if qualifying_tier.validity_months:
                from dateutil.relativedelta import relativedelta

                self.tier_expires_at = timezone.now() + relativedelta(
                    months=qualifying_tier.validity_months
                )

            self.save(update_fields=["loyalty_tier", "tier_achieved_at", "tier_expires_at"])

    def add_loyalty_points(self, points, description=""):
        """Add loyalty points to customer account."""
        if points <= 0:
            return

        # Apply tier multiplier if customer has a tier
        if self.loyalty_tier and self.loyalty_tier.points_multiplier:
            points = int(points * self.loyalty_tier.points_multiplier)

        self.loyalty_points += points
        self.total_points_earned += points
        self.save(update_fields=["loyalty_points", "total_points_earned"])

        # Create loyalty transaction record
        LoyaltyTransaction.objects.create(
            customer=self,
            transaction_type=LoyaltyTransaction.EARNED,
            points=points,
            description=description or f"Points earned: {points}",
        )

    def redeem_loyalty_points(self, points, description=""):
        """Redeem loyalty points from customer account."""
        if points <= 0 or points > self.loyalty_points:
            raise ValueError("Invalid points amount for redemption")

        self.loyalty_points -= points
        self.total_points_redeemed += points
        self.save(update_fields=["loyalty_points", "total_points_redeemed"])

        # Create loyalty transaction record
        LoyaltyTransaction.objects.create(
            customer=self,
            transaction_type=LoyaltyTransaction.REDEEMED,
            points=-points,  # Negative for redemption
            description=description or f"Points redeemed: {points}",
        )


class LoyaltyTransaction(models.Model):
    """
    Loyalty transaction model for tracking points accrual and redemption.

    Implements Requirement 36: Enhanced Loyalty Program
    - Track all loyalty point transactions
    - Support different transaction types (earned, redeemed, expired, adjusted)
    - Maintain audit trail for loyalty program
    """

    # Transaction types
    EARNED = "EARNED"
    REDEEMED = "REDEEMED"
    EXPIRED = "EXPIRED"
    ADJUSTED = "ADJUSTED"
    BONUS = "BONUS"
    REFERRAL = "REFERRAL"

    TRANSACTION_TYPE_CHOICES = [
        (EARNED, "Points Earned"),
        (REDEEMED, "Points Redeemed"),
        (EXPIRED, "Points Expired"),
        (ADJUSTED, "Points Adjusted"),
        (BONUS, "Bonus Points"),
        (REFERRAL, "Referral Points"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the loyalty transaction",
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="loyalty_transactions",
        help_text="Customer this transaction belongs to",
    )

    transaction_type = models.CharField(
        max_length=20, choices=TRANSACTION_TYPE_CHOICES, help_text="Type of loyalty transaction"
    )

    points = models.IntegerField(
        help_text="Points amount (positive for earned/bonus, negative for redeemed/expired)"
    )

    description = models.CharField(max_length=255, help_text="Description of the transaction")

    # Related objects
    sale = models.ForeignKey(
        "sales.Sale",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="loyalty_transactions",
        help_text="Sale that generated this transaction (if applicable)",
    )

    # Expiration tracking
    expires_at = models.DateTimeField(
        null=True, blank=True, help_text="When these points expire (if applicable)"
    )

    # Metadata
    metadata = models.JSONField(
        default=dict, blank=True, help_text="Additional transaction metadata"
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When the transaction was created"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who created this transaction (for manual adjustments)",
    )

    class Meta:
        db_table = "crm_loyalty_transactions"
        ordering = ["-created_at"]
        verbose_name = "Loyalty Transaction"
        verbose_name_plural = "Loyalty Transactions"
        indexes = [
            models.Index(fields=["customer", "-created_at"], name="loyalty_cust_date_idx"),
            models.Index(fields=["customer", "transaction_type"], name="loyalty_cust_type_idx"),
            models.Index(fields=["expires_at"], name="loyalty_expires_idx"),
        ]

    def __str__(self):
        return f"{self.customer.get_full_name()} - {self.transaction_type}: {self.points} points"


class GiftCard(models.Model):
    """
    Gift card model for managing gift card issuance and redemption.

    Implements Requirement 12: Customer Relationship Management (CRM)
    - Support gift card issuance and balance tracking
    - Track gift card transactions and usage
    """

    # Status choices
    ACTIVE = "ACTIVE"
    REDEEMED = "REDEEMED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (ACTIVE, "Active"),
        (REDEEMED, "Fully Redeemed"),
        (EXPIRED, "Expired"),
        (CANCELLED, "Cancelled"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the gift card",
    )

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="gift_cards",
        help_text="Tenant that owns this gift card",
    )

    card_number = models.CharField(max_length=50, unique=True, help_text="Unique gift card number")

    # Financial details
    initial_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Initial value of the gift card",
    )

    current_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Current balance of the gift card",
    )

    # Customer relationships
    purchased_by = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gift_cards_purchased",
        help_text="Customer who purchased this gift card",
    )

    recipient = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gift_cards_received",
        help_text="Customer who is the recipient of this gift card",
    )

    # Status and expiration
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=ACTIVE,
        help_text="Current status of the gift card",
    )

    expires_at = models.DateTimeField(null=True, blank=True, help_text="When the gift card expires")

    # Notes
    message = models.TextField(blank=True, help_text="Gift message")

    notes = models.TextField(blank=True, help_text="Internal notes about the gift card")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, help_text="When the gift card was created")

    updated_at = models.DateTimeField(
        auto_now=True, help_text="When the gift card was last updated"
    )

    issued_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who issued this gift card",
    )

    class Meta:
        db_table = "crm_gift_cards"
        ordering = ["-created_at"]
        verbose_name = "Gift Card"
        verbose_name_plural = "Gift Cards"
        unique_together = [["tenant", "card_number"]]
        indexes = [
            models.Index(fields=["tenant", "status"], name="gift_card_tenant_status_idx"),
            models.Index(fields=["card_number"], name="gift_card_number_idx"),
            models.Index(fields=["expires_at"], name="gift_card_expires_idx"),
        ]

    def __str__(self):
        return f"Gift Card {self.card_number} - ${self.current_balance}"

    def save(self, *args, **kwargs):
        """Override save to generate card number if not provided."""
        if not self.card_number:
            # Generate unique card number
            import random
            import string

            while True:
                number = "".join(random.choices(string.digits, k=16))
                if not GiftCard.objects.filter(card_number=number).exists():
                    self.card_number = number
                    break

        # Set current balance to initial value if not set (check for None, not falsy)
        if self.current_balance is None:
            self.current_balance = self.initial_value

        super().save(*args, **kwargs)

    def can_be_used(self):
        """Check if the gift card can be used."""
        return (
            self.status == self.ACTIVE
            and self.current_balance > 0
            and (not self.expires_at or self.expires_at > timezone.now())
        )

    def use_balance(self, amount):
        """Use a portion of the gift card balance."""
        if not self.can_be_used():
            raise ValueError("Gift card cannot be used")

        if amount > self.current_balance:
            raise ValueError("Amount exceeds gift card balance")

        self.current_balance -= amount

        # Mark as redeemed if balance is zero
        if self.current_balance == 0:
            self.status = self.REDEEMED

        self.save(update_fields=["current_balance", "status", "updated_at"])


class CustomerCommunication(models.Model):
    """
    Customer communication model for tracking all interactions.

    Implements Requirement 12: Customer Relationship Management (CRM)
    - Track customer communication history including emails, SMS, and calls
    - Log all customer communications for reference
    """

    # Communication types
    EMAIL = "EMAIL"
    SMS = "SMS"
    PHONE_CALL = "PHONE_CALL"
    IN_PERSON = "IN_PERSON"
    NOTE = "NOTE"

    COMMUNICATION_TYPE_CHOICES = [
        (EMAIL, "Email"),
        (SMS, "SMS"),
        (PHONE_CALL, "Phone Call"),
        (IN_PERSON, "In Person"),
        (NOTE, "Note"),
    ]

    # Direction choices
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"

    DIRECTION_CHOICES = [
        (INBOUND, "Inbound"),
        (OUTBOUND, "Outbound"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the communication",
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="communications",
        help_text="Customer this communication is with",
    )

    communication_type = models.CharField(
        max_length=20, choices=COMMUNICATION_TYPE_CHOICES, help_text="Type of communication"
    )

    direction = models.CharField(
        max_length=20, choices=DIRECTION_CHOICES, help_text="Direction of communication"
    )

    subject = models.CharField(
        max_length=255, blank=True, help_text="Subject or title of the communication"
    )

    content = models.TextField(help_text="Content or notes from the communication")

    # Metadata
    duration_minutes = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Duration in minutes (for calls or meetings)",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When the communication record was created"
    )

    communication_date = models.DateTimeField(
        default=timezone.now, help_text="When the actual communication took place"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who logged this communication",
    )

    class Meta:
        db_table = "crm_customer_communications"
        ordering = ["-communication_date"]
        verbose_name = "Customer Communication"
        verbose_name_plural = "Customer Communications"
        indexes = [
            models.Index(fields=["customer", "-communication_date"], name="comm_cust_date_idx"),
            models.Index(fields=["customer", "communication_type"], name="comm_cust_type_idx"),
        ]

    def __str__(self):
        return f"{self.customer.get_full_name()} - {self.communication_type} ({self.communication_date.date()})"
