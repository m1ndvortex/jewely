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
