"""
Bank account models for cash management and bank reconciliation.

This module contains models for managing bank accounts, bank transactions,
and bank reconciliations with proper tenant isolation.
"""

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from django_ledger.models import BankAccountModel

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


class BankAccount(models.Model):
    """
    Bank account model for cash management.

    Extends django-ledger's BankAccountModel functionality with
    tenant-specific features and additional tracking fields.
    """

    ACCOUNT_TYPE_CHOICES = [
        ("CHECKING", "Checking Account"),
        ("SAVINGS", "Savings Account"),
        ("MONEY_MARKET", "Money Market Account"),
        ("CREDIT_CARD", "Credit Card"),
        ("LINE_OF_CREDIT", "Line of Credit"),
        ("OTHER", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="bank_accounts",
        help_text="Tenant that owns this bank account",
    )

    # Bank Account Information
    account_name = models.CharField(
        max_length=100,
        help_text="Name/description of the bank account",
    )
    account_number = models.CharField(
        max_length=50,
        help_text="Bank account number (last 4 digits recommended for security)",
    )
    bank_name = models.CharField(
        max_length=100,
        help_text="Name of the financial institution",
    )
    account_type = models.CharField(
        max_length=20,
        choices=ACCOUNT_TYPE_CHOICES,
        default="CHECKING",
        help_text="Type of bank account",
    )

    # Balance Information
    opening_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Opening balance when account was added to system",
    )
    current_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Current book balance",
    )
    reconciled_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Last reconciled balance",
    )
    last_reconciled_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of last successful reconciliation",
    )

    # Integration with django-ledger
    ledger_account = models.ForeignKey(
        BankAccountModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="jewelry_bank_accounts",
        help_text="Linked django-ledger bank account",
    )

    # Direct link to GL Account (Chart of Accounts)
    gl_account = models.ForeignKey(
        "django_ledger.AccountModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_accounts",
        help_text="General Ledger account this bank account represents (e.g., 1001 - Cash)",
    )

    # Additional Information
    routing_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Bank routing number",
    )
    swift_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="SWIFT/BIC code for international transfers",
    )
    currency = models.CharField(
        max_length=3,
        default="USD",
        help_text="Currency code (ISO 4217)",
    )
    notes = models.TextField(
        blank=True,
        help_text="Internal notes about this bank account",
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this account is currently active",
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the default bank account for transactions",
    )

    # Audit Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_bank_accounts",
        help_text="User who created this bank account",
    )

    # Custom manager
    objects = TenantManager()

    class Meta:
        db_table = "accounting_bank_accounts"
        unique_together = [["tenant", "account_number", "bank_name"]]
        indexes = [
            models.Index(fields=["tenant", "is_active"]),
            models.Index(fields=["tenant", "account_type"]),
            models.Index(fields=["is_default"]),
            models.Index(fields=["last_reconciled_date"]),
        ]
        ordering = ["-is_default", "account_name"]
        verbose_name = "Bank Account"
        verbose_name_plural = "Bank Accounts"

    def __str__(self):
        return f"{self.account_name} - {self.bank_name} (****{self.account_number[-4:]})"

    def clean(self):
        """Validate bank account data."""
        super().clean()

        # Ensure only one default account per tenant
        if self.is_default:
            existing_default = (
                BankAccount.objects.filter(tenant=self.tenant, is_default=True)
                .exclude(pk=self.pk)
                .first()
            )
            if existing_default:
                raise ValidationError(
                    {
                        "is_default": f"Account '{existing_default.account_name}' "
                        f"is already set as default. Please unset it first."
                    }
                )

    @property
    def unreconciled_balance(self):
        """Calculate the difference between current and reconciled balance."""
        return self.current_balance - self.reconciled_balance

    @property
    def masked_account_number(self):
        """Return masked account number for display."""
        if len(self.account_number) <= 4:
            return self.account_number
        return f"****{self.account_number[-4:]}"

    @property
    def days_since_reconciliation(self):
        """Calculate days since last reconciliation."""
        if not self.last_reconciled_date:
            return None
        return (timezone.now().date() - self.last_reconciled_date).days

    @property
    def needs_reconciliation(self):
        """Check if account needs reconciliation (>30 days)."""
        days = self.days_since_reconciliation
        return days is None or days > 30

    def update_balance(self, amount, is_debit=True):
        """
        Update current balance.

        Args:
            amount: Amount to add or subtract
            is_debit: True if debit (increase for asset accounts), False if credit
        """
        if is_debit:
            self.current_balance += amount
        else:
            self.current_balance -= amount
        self.save(update_fields=["current_balance", "updated_at"])

    def mark_reconciled(self, reconciled_balance, reconciliation_date=None):
        """
        Mark account as reconciled with given balance.

        Args:
            reconciled_balance: The reconciled balance from bank statement
            reconciliation_date: Date of reconciliation (defaults to today)
        """
        self.reconciled_balance = reconciled_balance
        self.last_reconciled_date = reconciliation_date or timezone.now().date()
        self.save(update_fields=["reconciled_balance", "last_reconciled_date", "updated_at"])

    def deactivate(self):
        """Deactivate this bank account."""
        if self.is_default:
            raise ValidationError("Cannot deactivate the default bank account")

        self.is_active = False
        self.save(update_fields=["is_active", "updated_at"])

    def set_as_default(self):
        """Set this account as the default bank account for the tenant."""
        # Unset any existing default
        BankAccount.objects.filter(tenant=self.tenant, is_default=True).update(is_default=False)

        # Set this as default
        self.is_default = True
        self.save(update_fields=["is_default", "updated_at"])

    def save(self, *args, **kwargs):
        """Override save to handle default account logic."""
        # If this is the first active account for the tenant, make it default
        if self.is_active and not self.is_default:
            has_default = BankAccount.objects.filter(
                tenant=self.tenant, is_active=True, is_default=True
            ).exists()
            if not has_default:
                self.is_default = True

        super().save(*args, **kwargs)


class BankTransaction(models.Model):
    """
    Individual bank transaction for reconciliation tracking.

    Represents transactions that appear on bank statements and need to be
    matched with journal entries for reconciliation purposes.
    """

    TRANSACTION_TYPE_CHOICES = [
        ("DEBIT", "Debit (Money Out)"),
        ("CREDIT", "Credit (Money In)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="bank_transactions",
        help_text="Tenant that owns this transaction",
    )
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name="transactions",
        help_text="Bank account this transaction belongs to",
    )

    # Transaction Details
    transaction_date = models.DateField(
        help_text="Date the transaction occurred",
    )
    description = models.CharField(
        max_length=255,
        help_text="Transaction description from bank statement",
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Transaction amount (always positive)",
    )
    transaction_type = models.CharField(
        max_length=10,
        choices=TRANSACTION_TYPE_CHOICES,
        help_text="Whether this is a debit or credit transaction",
    )
    reference_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="Check number, wire reference, or other reference",
    )

    # Reconciliation Status
    is_reconciled = models.BooleanField(
        default=False,
        help_text="Whether this transaction has been reconciled",
    )
    reconciled_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when transaction was reconciled",
    )
    reconciled_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reconciled_transactions",
        help_text="User who reconciled this transaction",
    )
    reconciliation = models.ForeignKey(
        "BankReconciliation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
        help_text="Reconciliation session this transaction belongs to",
    )

    # Matching
    matched_journal_entry = models.ForeignKey(
        "django_ledger.JournalEntryModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matched_bank_transactions",
        help_text="Journal entry that matches this bank transaction",
    )

    # Import Tracking
    statement_import = models.ForeignKey(
        "BankStatementImport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="imported_transactions",
        help_text="Import session that created this transaction",
    )

    # Additional Information
    notes = models.TextField(
        blank=True,
        help_text="Internal notes about this transaction",
    )
    unreconcile_reason = models.TextField(
        blank=True,
        help_text="Reason for unreconciling this transaction (audit trail)",
    )

    # Audit Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_bank_transactions",
        help_text="User who created this transaction",
    )

    # Custom manager
    objects = TenantManager()

    class Meta:
        db_table = "accounting_bank_transactions"
        indexes = [
            models.Index(fields=["tenant", "bank_account", "transaction_date"]),
            models.Index(fields=["tenant", "is_reconciled"]),
            models.Index(fields=["transaction_date"]),
            models.Index(fields=["reconciliation"]),
            models.Index(fields=["matched_journal_entry"]),
        ]
        ordering = ["-transaction_date", "-created_at"]
        verbose_name = "Bank Transaction"
        verbose_name_plural = "Bank Transactions"

    def __str__(self):
        return f"{self.transaction_date} - {self.description[:50]} - {self.amount}"

    def clean(self):
        """Validate bank transaction data."""
        super().clean()

        # Ensure amount is positive
        if self.amount and self.amount < 0:
            raise ValidationError(
                {
                    "amount": "Amount must be positive. Use transaction_type to indicate debit/credit."
                }
            )

        # Ensure tenant matches bank account tenant
        if self.bank_account and self.bank_account.tenant != self.tenant:
            raise ValidationError({"bank_account": "Bank account must belong to the same tenant."})

    @property
    def signed_amount(self):
        """Return amount with sign based on transaction type."""
        if self.transaction_type == "DEBIT":
            return -self.amount
        return self.amount

    def mark_reconciled(self, reconciliation, user):
        """
        Mark this transaction as reconciled.

        Args:
            reconciliation: BankReconciliation instance
            user: User performing the reconciliation
        """
        self.is_reconciled = True
        self.reconciled_date = timezone.now().date()
        self.reconciled_by = user
        self.reconciliation = reconciliation
        self.save(
            update_fields=[
                "is_reconciled",
                "reconciled_date",
                "reconciled_by",
                "reconciliation",
                "updated_at",
            ]
        )

    def unreconcile(self, reason, user):
        """
        Unreconcile this transaction.

        Args:
            reason: Reason for unreconciling
            user: User performing the unreconciliation
        """
        self.is_reconciled = False
        self.reconciled_date = None
        self.reconciled_by = None
        self.reconciliation = None
        self.unreconcile_reason = (
            f"{timezone.now()}: {user.get_full_name() or user.username} - {reason}"
        )
        self.save(
            update_fields=[
                "is_reconciled",
                "reconciled_date",
                "reconciled_by",
                "reconciliation",
                "unreconcile_reason",
                "updated_at",
            ]
        )

    def match_journal_entry(self, journal_entry):
        """
        Match this transaction with a journal entry.

        Args:
            journal_entry: JournalEntryModel instance to match
        """
        self.matched_journal_entry = journal_entry
        self.save(update_fields=["matched_journal_entry", "updated_at"])


class BankReconciliation(models.Model):
    """
    Bank reconciliation session.

    Represents a reconciliation process where bank statement transactions
    are matched with accounting records to ensure accuracy.
    """

    STATUS_CHOICES = [
        ("IN_PROGRESS", "In Progress"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="bank_reconciliations",
        help_text="Tenant that owns this reconciliation",
    )
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name="reconciliations",
        help_text="Bank account being reconciled",
    )

    # Reconciliation Period
    reconciliation_date = models.DateField(
        help_text="Date of the bank statement being reconciled",
    )
    period_start_date = models.DateField(
        null=True,
        blank=True,
        help_text="Start date of reconciliation period",
    )
    period_end_date = models.DateField(
        null=True,
        blank=True,
        help_text="End date of reconciliation period",
    )

    # Statement Balances
    statement_beginning_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Beginning balance from bank statement",
    )
    statement_ending_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Ending balance from bank statement",
    )

    # Book Balances
    book_beginning_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Beginning balance from accounting records",
    )
    book_ending_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Ending balance from accounting records",
    )

    # Reconciliation Totals
    total_deposits = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total deposits reconciled",
    )
    total_withdrawals = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total withdrawals reconciled",
    )
    total_adjustments = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total adjustments made during reconciliation",
    )

    # Reconciliation Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="IN_PROGRESS",
        help_text="Current status of reconciliation",
    )
    is_balanced = models.BooleanField(
        default=False,
        help_text="Whether the reconciliation is balanced (statement = book)",
    )
    variance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Difference between statement and book balances",
    )

    # Completion Information
    completed_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date and time when reconciliation was completed",
    )
    completed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="completed_reconciliations",
        help_text="User who completed this reconciliation",
    )

    # Additional Information
    notes = models.TextField(
        blank=True,
        help_text="Notes about this reconciliation",
    )
    statement_file = models.FileField(
        upload_to="bank_statements/%Y/%m/",
        null=True,
        blank=True,
        help_text="Uploaded bank statement file",
    )

    # Audit Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_reconciliations",
        help_text="User who started this reconciliation",
    )

    # Custom manager
    objects = TenantManager()

    class Meta:
        db_table = "accounting_bank_reconciliations"
        indexes = [
            models.Index(fields=["tenant", "bank_account", "reconciliation_date"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["reconciliation_date"]),
            models.Index(fields=["status", "is_balanced"]),
        ]
        ordering = ["-reconciliation_date", "-created_at"]
        verbose_name = "Bank Reconciliation"
        verbose_name_plural = "Bank Reconciliations"

    def __str__(self):
        return f"{self.bank_account.account_name} - {self.reconciliation_date} ({self.status})"

    def clean(self):
        """Validate bank reconciliation data."""
        super().clean()

        # Ensure tenant matches bank account tenant
        if self.bank_account and self.bank_account.tenant != self.tenant:
            raise ValidationError({"bank_account": "Bank account must belong to the same tenant."})

        # Validate period dates
        if self.period_start_date and self.period_end_date:
            if self.period_start_date > self.period_end_date:
                raise ValidationError({"period_end_date": "End date must be after start date."})

    def calculate_variance(self):
        """Calculate variance between statement and book balances."""
        self.variance = self.statement_ending_balance - self.book_ending_balance
        self.is_balanced = abs(self.variance) < Decimal("0.01")  # Allow for rounding
        self.save(update_fields=["variance", "is_balanced", "updated_at"])

    def calculate_totals(self):
        """Calculate total deposits and withdrawals from reconciled transactions."""
        reconciled_txns = self.transactions.filter(is_reconciled=True)

        self.total_deposits = sum(
            txn.amount for txn in reconciled_txns if txn.transaction_type == "CREDIT"
        ) or Decimal("0.00")

        self.total_withdrawals = sum(
            txn.amount for txn in reconciled_txns if txn.transaction_type == "DEBIT"
        ) or Decimal("0.00")

        self.save(update_fields=["total_deposits", "total_withdrawals", "updated_at"])

    def complete(self, user):
        """
        Complete this reconciliation.

        Args:
            user: User completing the reconciliation
        """
        if self.status == "COMPLETED":
            raise ValidationError("Reconciliation is already completed.")

        # Calculate final totals and variance
        self.calculate_totals()
        self.calculate_variance()

        # Update status
        self.status = "COMPLETED"
        self.completed_date = timezone.now()
        self.completed_by = user

        # Update bank account reconciled balance
        self.bank_account.mark_reconciled(self.statement_ending_balance, self.reconciliation_date)

        self.save(update_fields=["status", "completed_date", "completed_by", "updated_at"])

    def cancel(self, reason=""):
        """
        Cancel this reconciliation.

        Args:
            reason: Reason for cancellation
        """
        if self.status == "COMPLETED":
            raise ValidationError("Cannot cancel a completed reconciliation.")

        self.status = "CANCELLED"
        if reason:
            self.notes = (
                f"{self.notes}\n\nCancelled: {reason}" if self.notes else f"Cancelled: {reason}"
            )

        # Unreconcile all transactions
        self.transactions.filter(is_reconciled=True).update(
            is_reconciled=False,
            reconciled_date=None,
            reconciled_by=None,
            reconciliation=None,
        )

        self.save(update_fields=["status", "notes", "updated_at"])

    @property
    def reconciled_transaction_count(self):
        """Count of reconciled transactions in this session."""
        return self.transactions.filter(is_reconciled=True).count()

    @property
    def unreconciled_transaction_count(self):
        """Count of unreconciled transactions in this session."""
        return self.transactions.filter(is_reconciled=False).count()


class BankStatementImport(models.Model):
    """
    Bank statement import tracking.

    Tracks the import of bank statements from files (CSV, OFX, QFX)
    and the transactions created from them.
    """

    FILE_FORMAT_CHOICES = [
        ("CSV", "CSV (Comma-Separated Values)"),
        ("OFX", "OFX (Open Financial Exchange)"),
        ("QFX", "QFX (Quicken Financial Exchange)"),
        ("QBO", "QBO (QuickBooks Online)"),
        ("OTHER", "Other"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("PROCESSING", "Processing"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
        ("PARTIALLY_COMPLETED", "Partially Completed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="bank_statement_imports",
        help_text="Tenant that owns this import",
    )
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name="statement_imports",
        help_text="Bank account for this import",
    )

    # Import Details
    import_date = models.DateTimeField(
        auto_now_add=True,
        help_text="Date and time of import",
    )
    file_name = models.CharField(
        max_length=255,
        help_text="Original filename of imported statement",
    )
    file_format = models.CharField(
        max_length=20,
        choices=FILE_FORMAT_CHOICES,
        help_text="Format of the imported file",
    )
    file = models.FileField(
        upload_to="bank_statement_imports/%Y/%m/",
        help_text="Uploaded statement file",
    )

    # Import Statistics
    transactions_imported = models.IntegerField(
        default=0,
        help_text="Number of transactions imported from file",
    )
    transactions_matched = models.IntegerField(
        default=0,
        help_text="Number of transactions automatically matched",
    )
    transactions_duplicates = models.IntegerField(
        default=0,
        help_text="Number of duplicate transactions skipped",
    )
    transactions_errors = models.IntegerField(
        default=0,
        help_text="Number of transactions that failed to import",
    )

    # Statement Period
    statement_start_date = models.DateField(
        null=True,
        blank=True,
        help_text="Start date from statement",
    )
    statement_end_date = models.DateField(
        null=True,
        blank=True,
        help_text="End date from statement",
    )
    statement_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Ending balance from statement",
    )

    # Import Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
        help_text="Current status of import",
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message if import failed",
    )

    # Processing Information
    processing_started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When processing started",
    )
    processing_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When processing completed",
    )

    # Additional Information
    notes = models.TextField(
        blank=True,
        help_text="Notes about this import",
    )

    # Audit Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    imported_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="bank_statement_imports",
        help_text="User who performed this import",
    )

    # Custom manager
    objects = TenantManager()

    class Meta:
        db_table = "accounting_bank_statement_imports"
        indexes = [
            models.Index(fields=["tenant", "bank_account", "import_date"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["import_date"]),
            models.Index(fields=["status"]),
        ]
        ordering = ["-import_date"]
        verbose_name = "Bank Statement Import"
        verbose_name_plural = "Bank Statement Imports"

    def __str__(self):
        return f"{self.bank_account.account_name} - {self.file_name} ({self.import_date.date()})"

    def clean(self):
        """Validate bank statement import data."""
        super().clean()

        # Ensure tenant matches bank account tenant
        if self.bank_account and self.bank_account.tenant != self.tenant:
            raise ValidationError({"bank_account": "Bank account must belong to the same tenant."})

        # Validate statement dates
        if self.statement_start_date and self.statement_end_date:
            if self.statement_start_date > self.statement_end_date:
                raise ValidationError({"statement_end_date": "End date must be after start date."})

    def start_processing(self):
        """Mark import as processing."""
        self.status = "PROCESSING"
        self.processing_started_at = timezone.now()
        self.save(update_fields=["status", "processing_started_at", "updated_at"])

    def complete_processing(self, success=True, error_message=""):
        """
        Mark import as completed or failed.

        Args:
            success: Whether import was successful
            error_message: Error message if failed
        """
        if success:
            if self.transactions_errors > 0:
                self.status = "PARTIALLY_COMPLETED"
            else:
                self.status = "COMPLETED"
        else:
            self.status = "FAILED"
            self.error_message = error_message

        self.processing_completed_at = timezone.now()
        self.save(
            update_fields=["status", "error_message", "processing_completed_at", "updated_at"]
        )

    @property
    def processing_duration(self):
        """Calculate processing duration in seconds."""
        if self.processing_started_at and self.processing_completed_at:
            return (self.processing_completed_at - self.processing_started_at).total_seconds()
        return None

    @property
    def success_rate(self):
        """Calculate success rate as percentage."""
        if self.transactions_imported == 0:
            return 0
        successful = self.transactions_imported - self.transactions_errors
        return (successful / self.transactions_imported) * 100

    @property
    def match_rate(self):
        """Calculate automatic match rate as percentage."""
        if self.transactions_imported == 0:
            return 0
        return (self.transactions_matched / self.transactions_imported) * 100
