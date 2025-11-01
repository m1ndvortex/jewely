"""
Invoice models for Accounts Receivable management.

This module contains models for managing customer invoices, invoice line items,
invoice payments, and credit memos with proper tenant isolation.
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


class Invoice(models.Model):
    """
    Customer invoice model for Accounts Receivable.

    Tracks invoices to customers with line items, payments, and
    automatic journal entry creation for double-entry bookkeeping.
    """

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("SENT", "Sent"),
        ("PARTIALLY_PAID", "Partially Paid"),
        ("PAID", "Paid"),
        ("OVERDUE", "Overdue"),
        ("VOID", "Void"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="invoices",
        help_text="Tenant that owns this invoice",
    )
    customer = models.ForeignKey(
        "crm.Customer",
        on_delete=models.PROTECT,
        related_name="invoices",
        help_text="Customer who will pay this invoice",
    )

    # Invoice Information
    invoice_number = models.CharField(
        max_length=50,
        help_text="Unique invoice number",
    )
    invoice_date = models.DateField(
        default=timezone.now,
        help_text="Date when invoice was issued",
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
        help_text="Current status of the invoice",
    )

    # Accounting Integration
    journal_entry = models.ForeignKey(
        JournalEntryModel,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="invoices",
        help_text="Journal entry created for this invoice",
    )

    # Additional Information
    notes = models.TextField(
        blank=True,
        help_text="Internal notes about this invoice",
    )
    customer_notes = models.TextField(
        blank=True,
        help_text="Notes visible to customer",
    )
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Additional reference number (PO number, etc.)",
    )

    # Audit Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_invoices",
        help_text="User who created this invoice",
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when invoice was sent to customer",
    )
    sent_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sent_invoices",
        help_text="User who sent this invoice",
    )

    # Custom manager
    objects = TenantManager()

    class Meta:
        db_table = "accounting_invoices"
        unique_together = [["tenant", "invoice_number"]]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "customer"]),
            models.Index(fields=["tenant", "invoice_date"]),
            models.Index(fields=["due_date"]),
            models.Index(fields=["status", "due_date"]),
        ]
        ordering = ["-invoice_date", "-created_at"]
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.customer}"

    def clean(self):
        """Validate invoice data."""
        super().clean()

        # Validate dates
        if self.due_date and self.invoice_date and self.due_date < self.invoice_date:
            raise ValidationError({"due_date": "Due date cannot be before invoice date"})

        # Validate amounts
        expected_total = self.subtotal + self.tax
        if abs(self.total - expected_total) > Decimal("0.01"):  # Allow for rounding
            raise ValidationError({"total": f"Total must equal subtotal + tax ({expected_total})"})

        # Validate payment amount
        if self.amount_paid > self.total:
            raise ValidationError({"amount_paid": "Amount paid cannot exceed total invoice amount"})

    @property
    def amount_due(self):
        """Calculate remaining amount due."""
        return self.total - self.amount_paid

    @property
    def is_paid(self):
        """Check if invoice is fully paid."""
        return self.amount_paid >= self.total and self.total > 0

    @property
    def is_overdue(self):
        """Check if invoice is overdue."""
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
        """Get aging bucket for this invoice (Current, 30, 60, 90, 90+)."""
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

    def mark_sent(self, user):
        """Mark invoice as sent to customer."""
        if self.status == "DRAFT":
            self.status = "SENT"
            self.sent_by = user
            self.sent_at = timezone.now()
            self.save(update_fields=["status", "sent_by", "sent_at"])

    def mark_paid(self):
        """Mark invoice as fully paid."""
        if self.is_paid:
            self.status = "PAID"
            self.save(update_fields=["status"])

    def mark_void(self):
        """Mark invoice as void."""
        if self.status == "PAID":
            raise ValidationError("Cannot void a paid invoice")

        self.status = "VOID"
        self.save(update_fields=["status"])

    def update_status(self):
        """Update invoice status based on payment and due date."""
        if self.status == "VOID":
            return

        if self.is_paid:
            self.status = "PAID"
        elif self.amount_paid > 0:
            self.status = "PARTIALLY_PAID"
        elif self.is_overdue:
            self.status = "OVERDUE"
        elif self.status == "DRAFT":
            pass  # Keep as draft
        else:
            self.status = "SENT"

        self.save(update_fields=["status"])

    def add_payment(self, amount):
        """Add a payment amount to this invoice."""
        if amount <= 0:
            raise ValueError("Payment amount must be positive")

        if self.amount_paid + amount > self.total:
            raise ValueError("Payment amount exceeds remaining balance")

        self.amount_paid += amount
        self.update_status()

    def apply_credit(self, credit_amount):
        """Apply a credit memo amount to this invoice."""
        if credit_amount <= 0:
            raise ValueError("Credit amount must be positive")

        if self.amount_paid + credit_amount > self.total:
            raise ValueError("Credit amount exceeds remaining balance")

        self.amount_paid += credit_amount
        self.update_status()

    def generate_invoice_number(self):
        """Generate a unique invoice number for this tenant."""
        today = timezone.now().date()
        year_month = today.strftime("%Y%m")

        # Find the last invoice number for this tenant and month
        last_invoice = (
            Invoice.objects.filter(
                tenant=self.tenant,
                invoice_number__startswith=f"INV-{year_month}-",
            )
            .order_by("-invoice_number")
            .first()
        )

        if last_invoice:
            try:
                last_sequence = int(last_invoice.invoice_number.split("-")[-1])
                sequence = last_sequence + 1
            except (ValueError, IndexError):
                sequence = 1
        else:
            sequence = 1

        return f"INV-{year_month}-{sequence:04d}"

    def save(self, *args, **kwargs):
        """Auto-generate invoice number if not set."""
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        super().save(*args, **kwargs)


class InvoiceLine(models.Model):
    """
    Line items for invoices.

    Tracks individual products or services within an invoice
    with descriptions, quantities, and pricing.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="lines",
        help_text="Invoice this line belongs to",
    )

    # Item Information
    item = models.CharField(
        max_length=255,
        help_text="Product or service name",
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed description of the item or service",
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
        db_table = "accounting_invoice_lines"
        indexes = [
            models.Index(fields=["invoice"]),
        ]
        ordering = ["created_at"]
        verbose_name = "Invoice Line"
        verbose_name_plural = "Invoice Lines"

    def __str__(self):
        return f"{self.item} - {self.amount}"

    def clean(self):
        """Validate line item data."""
        super().clean()

        # Validate amount calculation
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
        # Handle None values
        quantity = self.quantity if self.quantity is not None else Decimal("0.00")
        unit_price = self.unit_price if self.unit_price is not None else Decimal("0.00")

        self.amount = quantity * unit_price
        super().save(*args, **kwargs)

    @property
    def tenant(self):
        """Get tenant from parent invoice."""
        return self.invoice.tenant if self.invoice else None


class InvoicePayment(models.Model):
    """
    Payment records for invoices.

    Tracks individual payments received from customers with payment
    method, bank account, and reference information.
    """

    PAYMENT_METHOD_CHOICES = [
        ("CASH", "Cash"),
        ("CHECK", "Check"),
        ("CARD", "Credit/Debit Card"),
        ("BANK_TRANSFER", "Bank Transfer"),
        ("ACH", "ACH Transfer"),
        ("WIRE", "Wire Transfer"),
        ("PAYPAL", "PayPal"),
        ("STRIPE", "Stripe"),
        ("OTHER", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="invoice_payments",
        help_text="Tenant that owns this payment",
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name="payments",
        help_text="Invoice this payment is for",
    )

    # Payment Information
    payment_date = models.DateField(
        default=timezone.now,
        help_text="Date when payment was received",
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
        help_text="Bank account where payment was deposited",
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
        related_name="invoice_payments",
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
        related_name="created_invoice_payments",
        help_text="User who recorded this payment",
    )

    # Custom manager
    objects = TenantManager()

    class Meta:
        db_table = "accounting_invoice_payments"
        indexes = [
            models.Index(fields=["tenant", "payment_date"]),
            models.Index(fields=["invoice"]),
            models.Index(fields=["payment_method"]),
            models.Index(fields=["reference_number"]),
        ]
        ordering = ["-payment_date", "-created_at"]
        verbose_name = "Invoice Payment"
        verbose_name_plural = "Invoice Payments"

    def __str__(self):
        return f"Payment {self.amount} for {self.invoice.invoice_number}"

    def clean(self):
        """Validate payment data."""
        super().clean()

        # Validate payment amount doesn't exceed remaining balance
        if self.invoice:
            remaining_balance = self.invoice.amount_due
            if self.amount > remaining_balance:
                raise ValidationError(
                    {
                        "amount": f"Payment amount ({self.amount}) exceeds "
                        f"remaining balance ({remaining_balance})"
                    }
                )

    def save(self, *args, **kwargs):
        """Update invoice payment amount on save."""
        is_new = self._state.adding

        super().save(*args, **kwargs)

        # Update invoice's amount_paid if this is a new payment
        if is_new and self.invoice:
            self.invoice.add_payment(self.amount)


class CreditMemo(models.Model):
    """
    Credit memo model for customer credits.

    Tracks credits issued to customers that can be applied to invoices
    or kept as store credit for future purchases.
    """

    STATUS_CHOICES = [
        ("AVAILABLE", "Available"),
        ("APPLIED", "Applied"),
        ("VOID", "Void"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="credit_memos",
        help_text="Tenant that owns this credit memo",
    )
    customer = models.ForeignKey(
        "crm.Customer",
        on_delete=models.PROTECT,
        related_name="credit_memos",
        help_text="Customer who receives this credit",
    )

    # Credit Memo Information
    credit_memo_number = models.CharField(
        max_length=50,
        help_text="Unique credit memo number",
    )
    credit_date = models.DateField(
        default=timezone.now,
        help_text="Date when credit was issued",
    )

    # Financial Information
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Credit amount",
    )
    amount_used = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Amount already applied to invoices",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="AVAILABLE",
        help_text="Current status of the credit memo",
    )

    # Reason and Reference
    reason = models.CharField(
        max_length=255,
        help_text="Reason for issuing this credit",
    )
    original_invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="credit_memos",
        help_text="Original invoice this credit is related to (if any)",
    )
    applied_to_invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="applied_credits",
        help_text="Invoice this credit was applied to (if any)",
    )

    # Accounting Integration
    journal_entry = models.ForeignKey(
        JournalEntryModel,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="credit_memos",
        help_text="Journal entry created for this credit memo",
    )

    # Additional Information
    notes = models.TextField(
        blank=True,
        help_text="Internal notes about this credit memo",
    )

    # Audit Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_credit_memos",
        help_text="User who created this credit memo",
    )
    applied_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when credit was applied",
    )
    applied_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="applied_credit_memos",
        help_text="User who applied this credit",
    )

    # Custom manager
    objects = TenantManager()

    class Meta:
        db_table = "accounting_credit_memos"
        unique_together = [["tenant", "credit_memo_number"]]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "customer"]),
            models.Index(fields=["credit_date"]),
            models.Index(fields=["status"]),
        ]
        ordering = ["-credit_date", "-created_at"]
        verbose_name = "Credit Memo"
        verbose_name_plural = "Credit Memos"

    def __str__(self):
        return f"Credit Memo {self.credit_memo_number} - {self.customer}"

    def clean(self):
        """Validate credit memo data."""
        super().clean()

        # Validate amount used doesn't exceed total amount
        if self.amount_used > self.amount:
            raise ValidationError({"amount_used": "Amount used cannot exceed total credit amount"})

    @property
    def amount_available(self):
        """Calculate remaining credit available."""
        return self.amount - self.amount_used

    @property
    def is_fully_used(self):
        """Check if credit is fully used."""
        return self.amount_used >= self.amount

    def apply_to_invoice(self, invoice, amount, user):
        """Apply this credit memo to an invoice."""
        if self.status == "VOID":
            raise ValidationError("Cannot apply a void credit memo")

        if amount <= 0:
            raise ValueError("Application amount must be positive")

        if amount > self.amount_available:
            raise ValueError(f"Amount exceeds available credit ({self.amount_available})")

        if amount > invoice.amount_due:
            raise ValueError(f"Amount exceeds invoice balance ({invoice.amount_due})")

        # Update credit memo
        self.amount_used += amount
        if self.is_fully_used:
            self.status = "APPLIED"
        self.applied_to_invoice = invoice
        self.applied_by = user
        self.applied_at = timezone.now()
        self.save(
            update_fields=[
                "amount_used",
                "status",
                "applied_to_invoice",
                "applied_by",
                "applied_at",
            ]
        )

        # Update invoice
        invoice.apply_credit(amount)

    def mark_void(self):
        """Mark credit memo as void."""
        if self.amount_used > 0:
            raise ValidationError("Cannot void a credit memo that has been partially used")

        self.status = "VOID"
        self.save(update_fields=["status"])

    def generate_credit_memo_number(self):
        """Generate a unique credit memo number for this tenant."""
        today = timezone.now().date()
        year_month = today.strftime("%Y%m")

        # Find the last credit memo number for this tenant and month
        last_credit = (
            CreditMemo.objects.filter(
                tenant=self.tenant,
                credit_memo_number__startswith=f"CM-{year_month}-",
            )
            .order_by("-credit_memo_number")
            .first()
        )

        if last_credit:
            try:
                last_sequence = int(last_credit.credit_memo_number.split("-")[-1])
                sequence = last_sequence + 1
            except (ValueError, IndexError):
                sequence = 1
        else:
            sequence = 1

        return f"CM-{year_month}-{sequence:04d}"

    def save(self, *args, **kwargs):
        """Auto-generate credit memo number if not set."""
        if not self.credit_memo_number:
            self.credit_memo_number = self.generate_credit_memo_number()
        super().save(*args, **kwargs)
