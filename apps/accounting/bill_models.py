"""
Bill models for Accounts Payable management.

This module contains models for managing supplier bills, bill line items,
and bill payments with proper tenant isolation.
"""

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from django_ledger.models import JournalEntryModel

from apps.core.models import Tenant

User = get_user_model()


class TenantManager(models.Manager):
    """
    Custom manager for tenant-aware models.
    Automatically filters queries by tenant for data isolation.
    """

    def get_queryset(self):
        """Override to filter by tenant if available in context."""
        try:
            # Import here to avoid circular imports at module load time
            from apps.core.tenant_context import get_current_tenant

            current = get_current_tenant()
            if current:
                return super().get_queryset().filter(tenant=current)
        except Exception:
            # If anything goes wrong (no DB connection, missing function, etc.),
            # fall back to the unfiltered queryset to avoid breaking callers.
            pass

        return super().get_queryset()

    def for_tenant(self, tenant):
        """Get queryset filtered by specific tenant."""
        return self.get_queryset().filter(tenant=tenant)

    def all_tenants(self):
        """Get all objects without tenant filtering (admin use only)."""
        return super().get_queryset()


class Bill(models.Model):
    """
    Supplier bill/invoice model for Accounts Payable.

    Tracks bills from suppliers with line items, payments, and
    automatic journal entry creation for double-entry bookkeeping.
    """

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("APPROVED", "Approved"),
        ("PARTIALLY_PAID", "Partially Paid"),
        ("PAID", "Paid"),
        ("VOID", "Void"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="bills",
        help_text="Tenant that owns this bill",
    )
    supplier = models.ForeignKey(
        "procurement.Supplier",
        on_delete=models.PROTECT,
        related_name="bills",
        help_text="Supplier who issued this bill",
    )

    # Bill Information
    bill_number = models.CharField(
        max_length=50,
        help_text="Unique bill number (can be supplier's invoice number)",
    )
    bill_date = models.DateField(
        default=timezone.now,
        help_text="Date when bill was issued",
    )
    due_date = models.DateField(
        help_text="Date when payment is due",
    )

    # Financial Information
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Subtotal before tax",
    )
    tax = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Tax amount",
    )
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Total amount including tax",
    )
    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Amount paid so far",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT",
        help_text="Current status of the bill",
    )

    # Accounting Integration
    journal_entry = models.ForeignKey(
        JournalEntryModel,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bills",
        help_text="Journal entry created for this bill",
    )

    # Additional Information
    notes = models.TextField(
        blank=True,
        help_text="Internal notes about this bill",
    )
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Additional reference number",
    )

    # Audit Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_bills",
        help_text="User who created this bill",
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approved_bills",
        help_text="User who approved this bill",
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when bill was approved",
    )

    # Custom manager
    objects = TenantManager()

    class Meta:
        db_table = "accounting_bills"
        unique_together = [["tenant", "bill_number"]]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "supplier"]),
            models.Index(fields=["tenant", "bill_date"]),
            models.Index(fields=["due_date"]),
            models.Index(fields=["status", "due_date"]),
        ]
        ordering = ["-bill_date", "-created_at"]
        verbose_name = "Bill"
        verbose_name_plural = "Bills"

    def __str__(self):
        return f"Bill {self.bill_number} - {self.supplier.name}"

    def clean(self):
        """Validate bill data."""
        super().clean()

        # Validate dates
        if self.due_date and self.bill_date and self.due_date < self.bill_date:
            raise ValidationError({"due_date": "Due date cannot be before bill date"})

        # Validate amounts
        expected_total = self.subtotal + self.tax
        if abs(self.total - expected_total) > Decimal("0.01"):  # Allow for rounding
            raise ValidationError({"total": f"Total must equal subtotal + tax ({expected_total})"})

        # Validate payment amount
        if self.amount_paid > self.total:
            raise ValidationError({"amount_paid": "Amount paid cannot exceed total bill amount"})

    @property
    def amount_due(self):
        """Calculate remaining amount due."""
        return self.total - self.amount_paid

    @property
    def is_paid(self):
        """Check if bill is fully paid."""
        return self.amount_paid >= self.total and self.total > 0

    @property
    def is_overdue(self):
        """Check if bill is overdue."""
        if self.status in ["PAID", "VOID"]:
            return False
        return timezone.now().date() > self.due_date

    @property
    def days_overdue(self):
        """Calculate number of days overdue."""
        if not self.is_overdue:
            return 0
        return (timezone.now().date() - self.due_date).days

    @property
    def aging_bucket(self):
        """Get aging bucket for this bill (Current, 30, 60, 90, 90+)."""
        if not self.is_overdue:
            return "Current"
        days = self.days_overdue
        if days <= 30:
            return "1-30 days"
        elif days <= 60:
            return "31-60 days"
        elif days <= 90:
            return "61-90 days"
        else:
            return "90+ days"

    def calculate_totals(self):
        """Calculate subtotal and total from line items."""
        lines = self.lines.all()
        self.subtotal = sum(line.amount for line in lines)
        # Tax is set separately or calculated based on tax codes
        self.total = self.subtotal + self.tax
        self.save(update_fields=["subtotal", "total"])

    def mark_approved(self, user):
        """Mark bill as approved."""
        if self.status != "DRAFT":
            raise ValidationError("Only draft bills can be approved")

        self.status = "APPROVED"
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save(update_fields=["status", "approved_by", "approved_at"])

    def mark_paid(self):
        """Mark bill as fully paid."""
        if self.is_paid:
            self.status = "PAID"
            self.save(update_fields=["status"])

    def mark_void(self):
        """Mark bill as void."""
        if self.status == "PAID":
            raise ValidationError("Cannot void a paid bill")

        self.status = "VOID"
        self.save(update_fields=["status"])

    def add_payment(self, amount):
        """Add a payment amount to this bill."""
        if amount <= 0:
            raise ValueError("Payment amount must be positive")

        if self.amount_paid + amount > self.total:
            raise ValueError("Payment amount exceeds remaining balance")

        self.amount_paid += amount

        # Update status based on payment
        if self.is_paid:
            self.status = "PAID"
        elif self.amount_paid > 0:
            self.status = "PARTIALLY_PAID"

        self.save(update_fields=["amount_paid", "status"])

    def generate_bill_number(self):
        """Generate a unique bill number for this tenant."""
        today = timezone.now().date()
        year_month = today.strftime("%Y%m")

        # Find the last bill number for this tenant and month
        last_bill = (
            Bill.objects.filter(
                tenant=self.tenant,
                bill_number__startswith=f"BILL-{year_month}-",
            )
            .order_by("-bill_number")
            .first()
        )

        if last_bill:
            try:
                last_sequence = int(last_bill.bill_number.split("-")[-1])
                sequence = last_sequence + 1
            except (ValueError, IndexError):
                sequence = 1
        else:
            sequence = 1

        return f"BILL-{year_month}-{sequence:04d}"

    def save(self, *args, **kwargs):
        """Auto-generate bill number if not set."""
        if not self.bill_number:
            self.bill_number = self.generate_bill_number()
        super().save(*args, **kwargs)


class BillLine(models.Model):
    """
    Line items for bills.

    Tracks individual expense or asset items within a bill
    with account codes for proper GL posting.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bill = models.ForeignKey(
        Bill,
        on_delete=models.CASCADE,
        related_name="lines",
        help_text="Bill this line belongs to",
    )

    # Account Information
    account = models.CharField(
        max_length=20,
        help_text="GL account code for this expense/asset",
    )
    description = models.CharField(
        max_length=255,
        help_text="Description of the item or service",
    )

    # Quantity and Pricing
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Quantity",
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Price per unit",
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Total amount for this line (quantity × unit_price)",
    )

    # Additional Information
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this line item",
    )

    # Audit Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Custom manager
    objects = TenantManager()

    class Meta:
        db_table = "accounting_bill_lines"
        indexes = [
            models.Index(fields=["bill"]),
            models.Index(fields=["account"]),
        ]
        ordering = ["created_at"]
        verbose_name = "Bill Line"
        verbose_name_plural = "Bill Lines"

    def __str__(self):
        return f"{self.description} - {self.amount}"

    def clean(self):
        """Validate line item data."""
        super().clean()

        # Validate amount calculation. Be defensive: formsets may call clean()
        # when some numeric fields are not yet provided (None). Treat None as 0.00
        # for the purposes of validation to avoid TypeErrors.
        qty = self.quantity if self.quantity is not None else Decimal("0.00")
        up = self.unit_price if self.unit_price is not None else Decimal("0.00")
        amt = self.amount if self.amount is not None else Decimal("0.00")

        expected_amount = qty * up
        if abs(amt - expected_amount) > Decimal("0.01"):  # Allow for rounding
            raise ValidationError(
                {"amount": f"Amount must equal quantity × unit_price ({expected_amount})"}
            )

    def save(self, *args, **kwargs):
        """Auto-calculate amount on save."""
        from decimal import Decimal

        # Handle None values
        quantity = self.quantity if self.quantity is not None else Decimal("0.00")
        unit_price = self.unit_price if self.unit_price is not None else Decimal("0.00")

        self.amount = quantity * unit_price
        super().save(*args, **kwargs)

    @property
    def tenant(self):
        """Get tenant from parent bill."""
        return self.bill.tenant if self.bill else None


class BillPayment(models.Model):
    """
    Payment records for bills.

    Tracks individual payments made against bills with payment
    method, bank account, and reference information.
    """

    PAYMENT_METHOD_CHOICES = [
        ("CASH", "Cash"),
        ("CHECK", "Check"),
        ("CARD", "Credit/Debit Card"),
        ("BANK_TRANSFER", "Bank Transfer"),
        ("ACH", "ACH Transfer"),
        ("WIRE", "Wire Transfer"),
        ("OTHER", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="bill_payments",
        help_text="Tenant that owns this payment",
    )
    bill = models.ForeignKey(
        Bill,
        on_delete=models.PROTECT,
        related_name="payments",
        help_text="Bill this payment is for",
    )

    # Payment Information
    payment_date = models.DateField(
        default=timezone.now,
        help_text="Date when payment was made",
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Payment amount",
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default="CHECK",
        help_text="Method of payment",
    )

    # Bank and Reference Information
    bank_account = models.CharField(
        max_length=100,
        blank=True,
        help_text="Bank account used for payment",
    )
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Check number, transaction ID, or other reference",
    )

    # Accounting Integration
    journal_entry = models.ForeignKey(
        JournalEntryModel,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bill_payments",
        help_text="Journal entry created for this payment",
    )

    # Additional Information
    notes = models.TextField(
        blank=True,
        help_text="Notes about this payment",
    )

    # Audit Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_bill_payments",
        help_text="User who recorded this payment",
    )

    # Custom manager
    objects = TenantManager()

    class Meta:
        db_table = "accounting_bill_payments"
        indexes = [
            models.Index(fields=["tenant", "payment_date"]),
            models.Index(fields=["bill"]),
            models.Index(fields=["payment_method"]),
            models.Index(fields=["reference_number"]),
        ]
        ordering = ["-payment_date", "-created_at"]
        verbose_name = "Bill Payment"
        verbose_name_plural = "Bill Payments"

    def __str__(self):
        return f"Payment {self.amount} for {self.bill.bill_number}"

    def clean(self):
        """Validate payment data."""
        super().clean()

        # Validate payment amount doesn't exceed remaining balance
        if self.bill:
            remaining_balance = self.bill.amount_due
            if self.amount > remaining_balance:
                raise ValidationError(
                    {
                        "amount": f"Payment amount ({self.amount}) exceeds "
                        f"remaining balance ({remaining_balance})"
                    }
                )

    def save(self, *args, **kwargs):
        """Update bill payment amount on save."""
        is_new = self._state.adding

        super().save(*args, **kwargs)

        # Update bill's amount_paid if this is a new payment
        if is_new and self.bill:
            self.bill.add_payment(self.amount)
