"""
Sales models for jewelry shop management.

Implements Requirement 11: Point of Sale (POS) System
- Fast and intuitive POS interface for processing in-store sales
- Support for multiple payment methods (cash, card, store credit)
- Split payments across multiple payment methods
- Automatic tax calculation and discount application
- Immediate inventory updates upon sale completion
- Automatic accounting entries for each sale
- Receipt generation and printing
- Offline mode with automatic synchronization
- Transaction hold and resume functionality
- Sales tracking by terminal, employee, and branch

Implements Requirement 14: Multi-Branch and Terminal Management
- Multiple shop branches with separate configurations
- POS terminal registration and management
- Terminal assignment to branches and users
- Sales and transaction tracking by terminal and branch
"""

import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import Branch, Tenant, User
from apps.inventory.models import InventoryItem


class Terminal(models.Model):
    """
    POS Terminal model for tracking point-of-sale devices.

    Each terminal is registered and assigned to a specific branch.
    Terminals are used to track which device processed each sale
    for audit and reporting purposes per Requirement 14.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the terminal",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="terminals",
        help_text="Branch where this terminal is located",
    )

    terminal_id = models.CharField(
        max_length=50,
        help_text="Human-readable terminal identifier (e.g., 'POS-01', 'MAIN-COUNTER')",
    )

    description = models.TextField(
        blank=True,
        help_text="Optional description of the terminal location or purpose",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this terminal is currently active and can process sales",
    )

    # Terminal configuration (can be extended with JSON field for printer settings, etc.)
    configuration = models.JSONField(
        default=dict,
        blank=True,
        help_text="Terminal-specific configuration (printer settings, scanner config, etc.)",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the terminal was registered",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the terminal was last updated",
    )

    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the terminal was last used for a sale",
    )

    class Meta:
        db_table = "sales_terminals"
        ordering = ["branch", "terminal_id"]
        verbose_name = "Terminal"
        verbose_name_plural = "Terminals"
        unique_together = [["branch", "terminal_id"]]
        indexes = [
            models.Index(fields=["branch", "is_active"], name="term_branch_active_idx"),
            models.Index(fields=["terminal_id"], name="term_id_idx"),
        ]

    def __str__(self):
        return f"{self.terminal_id} ({self.branch.name})"

    def mark_as_used(self):
        """Update the last_used_at timestamp."""
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at"])


class Customer(models.Model):
    """
    Customer model for CRM functionality.

    Tracks customer information, purchase history, loyalty points,
    and store credit per Requirement 12.

    Note: This is a simplified version for sales. Full CRM features
    will be implemented in a separate CRM app.
    """

    # Loyalty tier choices
    BRONZE = "BRONZE"
    SILVER = "SILVER"
    GOLD = "GOLD"
    PLATINUM = "PLATINUM"

    TIER_CHOICES = [
        (BRONZE, "Bronze"),
        (SILVER, "Silver"),
        (GOLD, "Gold"),
        (PLATINUM, "Platinum"),
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
        related_name="customers",
        help_text="Tenant that owns this customer",
    )

    customer_number = models.CharField(
        max_length=50,
        help_text="Unique customer number within tenant",
    )

    # Contact information
    first_name = models.CharField(
        max_length=100,
        help_text="Customer's first name",
    )

    last_name = models.CharField(
        max_length=100,
        help_text="Customer's last name",
    )

    email = models.EmailField(
        null=True,
        blank=True,
        help_text="Customer's email address",
    )

    phone = models.CharField(
        max_length=20,
        help_text="Customer's phone number",
    )

    # Loyalty and credit
    loyalty_tier = models.CharField(
        max_length=20,
        choices=TIER_CHOICES,
        default=BRONZE,
        help_text="Customer's loyalty tier",
    )

    loyalty_points = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Current loyalty points balance",
    )

    store_credit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Store credit balance",
    )

    # Purchase tracking
    total_purchases = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Total lifetime purchase amount",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the customer was created",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the customer was last updated",
    )

    class Meta:
        db_table = "sales_customers"
        ordering = ["-created_at"]
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
        unique_together = [["tenant", "customer_number"]]
        indexes = [
            models.Index(fields=["tenant", "phone"], name="cust_tenant_phone_idx"),
            models.Index(fields=["tenant", "email"], name="cust_tenant_email_idx"),
            models.Index(fields=["tenant", "loyalty_tier"], name="cust_tenant_tier_idx"),
        ]

    def __str__(self):
        return f"{self.customer_number} - {self.first_name} {self.last_name}"

    def get_full_name(self):
        """Return the customer's full name."""
        return f"{self.first_name} {self.last_name}"


class Sale(models.Model):
    """
    Sale model for tracking point-of-sale transactions.

    Implements Requirement 11: POS System
    - Tracks all sales with complete transaction details
    - Supports multiple payment methods
    - Links to customer, branch, terminal, and employee
    - Calculates subtotal, tax, discount, and total
    - Tracks sale status (completed, refunded, cancelled)
    - Provides audit trail for all transactions

    Each sale is tenant-scoped and protected by RLS policies.
    """

    # Payment method choices
    CASH = "CASH"
    CARD = "CARD"
    STORE_CREDIT = "STORE_CREDIT"
    SPLIT = "SPLIT"
    OTHER = "OTHER"

    PAYMENT_METHOD_CHOICES = [
        (CASH, "Cash"),
        (CARD, "Card"),
        (STORE_CREDIT, "Store Credit"),
        (SPLIT, "Split Payment"),
        (OTHER, "Other"),
    ]

    # Status choices
    COMPLETED = "COMPLETED"
    REFUNDED = "REFUNDED"
    CANCELLED = "CANCELLED"
    ON_HOLD = "ON_HOLD"

    STATUS_CHOICES = [
        (COMPLETED, "Completed"),
        (REFUNDED, "Refunded"),
        (CANCELLED, "Cancelled"),
        (ON_HOLD, "On Hold"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the sale",
    )

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="sales",
        help_text="Tenant that owns this sale",
    )

    sale_number = models.CharField(
        max_length=50,
        help_text="Unique sale number within tenant (e.g., 'SALE-2024-00001')",
    )

    # Relationships
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales",
        help_text="Customer who made the purchase (optional for walk-in sales)",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="sales",
        help_text="Branch where the sale was made",
    )

    terminal = models.ForeignKey(
        Terminal,
        on_delete=models.PROTECT,
        related_name="sales",
        help_text="Terminal used to process the sale",
    )

    employee = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="sales_processed",
        help_text="Employee who processed the sale",
    )

    # Financial details
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Subtotal before tax and discount",
    )

    tax = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Tax amount",
    )

    discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Discount amount",
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Total amount (subtotal + tax - discount)",
    )

    # Payment details
    payment_method = models.CharField(
        max_length=50,
        choices=PAYMENT_METHOD_CHOICES,
        help_text="Primary payment method used",
    )

    payment_details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional payment details (split payment breakdown, card last 4 digits, etc.)",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=COMPLETED,
        help_text="Current status of the sale",
    )

    # Notes and metadata
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the sale",
    )

    # Offline sync support
    is_synced = models.BooleanField(
        default=True,
        help_text="Whether this sale has been synced from offline mode",
    )

    offline_created_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Original creation timestamp if created offline",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the sale was created",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the sale was last updated",
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the sale was completed",
    )

    class Meta:
        db_table = "sales"
        ordering = ["-created_at"]
        verbose_name = "Sale"
        verbose_name_plural = "Sales"
        unique_together = [["tenant", "sale_number"]]
        indexes = [
            # Common query patterns
            models.Index(fields=["tenant", "-created_at"], name="sale_tenant_date_idx"),
            models.Index(fields=["tenant", "status"], name="sale_tenant_status_idx"),
            models.Index(fields=["tenant", "branch", "-created_at"], name="sale_branch_date_idx"),
            models.Index(fields=["tenant", "employee", "-created_at"], name="sale_emp_date_idx"),
            models.Index(fields=["tenant", "terminal", "-created_at"], name="sale_term_date_idx"),
            models.Index(fields=["customer", "-created_at"], name="sale_cust_date_idx"),
            # Reporting queries
            models.Index(fields=["tenant", "payment_method"], name="sale_payment_idx"),
            models.Index(fields=["is_synced"], name="sale_synced_idx"),
        ]

    def __str__(self):
        return f"{self.sale_number} - {self.total}"

    def save(self, *args, **kwargs):
        """
        Override save to set completed_at timestamp when status changes to COMPLETED.
        """
        if self.status == self.COMPLETED and not self.completed_at:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)

    def calculate_totals(self):
        """
        Calculate subtotal, tax, discount, and total from sale items.
        This should be called after adding/removing sale items.
        """
        items = self.items.all()
        self.subtotal = sum(item.subtotal for item in items)
        # Tax and discount are set separately based on business rules
        self.total = self.subtotal + self.tax - self.discount
        self.save(update_fields=["subtotal", "total", "updated_at"])

    def can_be_refunded(self):
        """Check if this sale can be refunded."""
        return self.status == self.COMPLETED

    def can_be_cancelled(self):
        """Check if this sale can be cancelled."""
        return self.status in [self.COMPLETED, self.ON_HOLD]

    def mark_as_completed(self):
        """Mark the sale as completed."""
        self.status = self.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at", "updated_at"])

    def mark_as_refunded(self):
        """Mark the sale as refunded."""
        if not self.can_be_refunded():
            raise ValueError("This sale cannot be refunded")
        self.status = self.REFUNDED
        self.save(update_fields=["status", "updated_at"])

    def mark_as_cancelled(self):
        """Mark the sale as cancelled."""
        if not self.can_be_cancelled():
            raise ValueError("This sale cannot be cancelled")
        self.status = self.CANCELLED
        self.save(update_fields=["status", "updated_at"])

    def put_on_hold(self):
        """Put the sale on hold."""
        self.status = self.ON_HOLD
        self.save(update_fields=["status", "updated_at"])


class SaleItem(models.Model):
    """
    Sale item model for tracking individual items in a sale.

    Each sale can have multiple items. This model tracks:
    - Which inventory item was sold
    - Quantity sold
    - Unit price at time of sale
    - Subtotal for this line item

    Implements line-item tracking per Requirement 11.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the sale item",
    )

    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name="items",
        help_text="Sale that this item belongs to",
    )

    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name="sale_items",
        help_text="Inventory item that was sold",
    )

    # Quantity and pricing
    quantity = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Quantity sold",
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Unit price at time of sale (may differ from current inventory price)",
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Subtotal for this line item (quantity * unit_price)",
    )

    # Discount at item level (optional)
    discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Discount applied to this specific item",
    )

    # Notes
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this sale item",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the sale item was added",
    )

    class Meta:
        db_table = "sale_items"
        ordering = ["created_at"]
        verbose_name = "Sale Item"
        verbose_name_plural = "Sale Items"
        indexes = [
            models.Index(fields=["sale"], name="saleitem_sale_idx"),
            models.Index(fields=["inventory_item"], name="saleitem_inv_idx"),
        ]

    def __str__(self):
        return f"{self.inventory_item.name} x {self.quantity}"

    def save(self, *args, **kwargs):
        """
        Override save to calculate subtotal if not provided.
        """
        if not self.subtotal:
            self.subtotal = self.unit_price * self.quantity - self.discount
        super().save(*args, **kwargs)

    def calculate_subtotal(self):
        """Calculate and return the subtotal for this item."""
        return (self.unit_price * self.quantity) - self.discount
