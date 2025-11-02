"""
Accounting models for jewelry shop management.

This module integrates with django-ledger to provide double-entry accounting
functionality specifically tailored for jewelry businesses.
"""

from django.contrib.auth import get_user_model
from django.db import models

from django_ledger.models import EntityModel

from apps.core.models import Tenant

# Import bank models for Django to recognize them
from .bank_models import BankAccount  # noqa: F401

# Import bill models for Django to recognize them
from .bill_models import Bill, BillLine, BillPayment  # noqa: F401

# Import invoice models for Django to recognize them
from .invoice_models import CreditMemo, Invoice, InvoiceLine, InvoicePayment  # noqa: F401

# Import transaction models for Django to recognize them
from .transaction_models import Expense, Payment, PurchaseOrder  # noqa: F401

User = get_user_model()


class JewelryEntity(models.Model):
    """
    Extends django-ledger EntityModel for jewelry shop specific functionality.
    Each tenant gets their own accounting entity.
    """

    tenant = models.OneToOneField(
        Tenant, on_delete=models.CASCADE, related_name="accounting_entity"
    )
    ledger_entity = models.OneToOneField(
        EntityModel, on_delete=models.CASCADE, related_name="jewelry_entity"
    )
    fiscal_year_start_month = models.IntegerField(
        default=1,
        choices=[(i, i) for i in range(1, 13)],
        help_text="Month when fiscal year starts (1=January, 4=April, etc.)",
    )
    default_currency = models.CharField(
        max_length=3, default="USD", help_text="Default currency for this entity"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounting_jewelry_entity"
        verbose_name = "Jewelry Entity"
        verbose_name_plural = "Jewelry Entities"

    def __str__(self):
        return f"Accounting Entity for {self.tenant.company_name}"


class JewelryChartOfAccounts(models.Model):
    """
    Predefined chart of accounts template for jewelry businesses.
    """

    ACCOUNT_TYPES = [
        # Assets
        ("CASH", "Cash and Cash Equivalents"),
        ("INVENTORY", "Inventory"),
        ("ACCOUNTS_RECEIVABLE", "Accounts Receivable"),
        ("EQUIPMENT", "Equipment and Fixtures"),
        ("PREPAID_EXPENSES", "Prepaid Expenses"),
        # Liabilities
        ("ACCOUNTS_PAYABLE", "Accounts Payable"),
        ("ACCRUED_EXPENSES", "Accrued Expenses"),
        ("LOANS_PAYABLE", "Loans Payable"),
        ("SALES_TAX_PAYABLE", "Sales Tax Payable"),
        # Equity
        ("OWNERS_EQUITY", "Owner's Equity"),
        ("RETAINED_EARNINGS", "Retained Earnings"),
        # Revenue
        ("JEWELRY_SALES", "Jewelry Sales"),
        ("REPAIR_REVENUE", "Repair Services Revenue"),
        ("CUSTOM_ORDER_REVENUE", "Custom Order Revenue"),
        ("GIFT_CARD_REVENUE", "Gift Card Revenue"),
        # Expenses
        ("COST_OF_GOODS_SOLD", "Cost of Goods Sold"),
        ("RENT_EXPENSE", "Rent Expense"),
        ("UTILITIES_EXPENSE", "Utilities Expense"),
        ("INSURANCE_EXPENSE", "Insurance Expense"),
        ("MARKETING_EXPENSE", "Marketing Expense"),
        ("EMPLOYEE_WAGES", "Employee Wages"),
        ("PROFESSIONAL_FEES", "Professional Fees"),
        ("BANK_FEES", "Bank Fees"),
        ("DEPRECIATION_EXPENSE", "Depreciation Expense"),
    ]

    name = models.CharField(max_length=100)
    account_type = models.CharField(max_length=50, choices=ACCOUNT_TYPES)
    account_code = models.CharField(max_length=20, unique=True)
    parent_code = models.CharField(max_length=20, null=True, blank=True)
    description = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "accounting_chart_template"
        ordering = ["account_code"]
        verbose_name = "Chart of Accounts Template"
        verbose_name_plural = "Chart of Accounts Templates"

    def __str__(self):
        return f"{self.account_code} - {self.name}"


class AccountingConfiguration(models.Model):
    """
    Configuration settings for accounting module per tenant.
    """

    tenant = models.OneToOneField(
        Tenant, on_delete=models.CASCADE, related_name="accounting_config"
    )

    # Default accounts for automatic journal entries
    default_cash_account = models.CharField(
        max_length=20, default="1001", help_text="Default cash account for cash sales"
    )
    default_card_account = models.CharField(
        max_length=20, default="1002", help_text="Default account for card payments"
    )
    default_inventory_account = models.CharField(
        max_length=20, default="1200", help_text="Default inventory asset account"
    )
    default_cogs_account = models.CharField(
        max_length=20, default="5001", help_text="Default cost of goods sold account"
    )
    default_sales_account = models.CharField(
        max_length=20, default="4001", help_text="Default sales revenue account"
    )
    default_tax_account = models.CharField(
        max_length=20, default="2003", help_text="Default sales tax payable account"
    )

    # Accounting preferences
    use_automatic_journal_entries = models.BooleanField(
        default=True, help_text="Automatically create journal entries for sales and purchases"
    )
    inventory_valuation_method = models.CharField(
        max_length=20,
        choices=[
            ("FIFO", "First In, First Out"),
            ("LIFO", "Last In, First Out"),
            ("WEIGHTED_AVG", "Weighted Average"),
        ],
        default="FIFO",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounting_configuration"
        verbose_name = "Accounting Configuration"
        verbose_name_plural = "Accounting Configurations"

    def __str__(self):
        return f"Accounting Config for {self.tenant.company_name}"


class JournalEntryTemplate(models.Model):
    """
    Templates for common journal entries in jewelry business.
    """

    TEMPLATE_TYPES = [
        ("CASH_SALE", "Cash Sale"),
        ("CARD_SALE", "Card Sale"),
        ("INVENTORY_PURCHASE", "Inventory Purchase"),
        ("REPAIR_REVENUE", "Repair Service Revenue"),
        ("CUSTOM_ORDER", "Custom Order"),
        ("EXPENSE_PAYMENT", "Expense Payment"),
        ("LOAN_PAYMENT", "Loan Payment"),
    ]

    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=50, choices=TEMPLATE_TYPES)
    description = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "accounting_journal_templates"
        verbose_name = "Journal Entry Template"
        verbose_name_plural = "Journal Entry Templates"

    def __str__(self):
        return self.name


class JournalEntryTemplateLine(models.Model):
    """
    Individual lines for journal entry templates.
    """

    DEBIT_CREDIT_CHOICES = [
        ("DEBIT", "Debit"),
        ("CREDIT", "Credit"),
    ]

    template = models.ForeignKey(
        JournalEntryTemplate, on_delete=models.CASCADE, related_name="lines"
    )
    account_code = models.CharField(max_length=20)
    debit_credit = models.CharField(max_length=6, choices=DEBIT_CREDIT_CHOICES)
    amount_field = models.CharField(
        max_length=50,
        help_text="Field name from source transaction (e.g., 'total', 'tax', 'subtotal')",
    )
    description_template = models.CharField(
        max_length=200, help_text="Template for line description (e.g., 'Sale #{sale_number}')"
    )
    order = models.IntegerField(default=0)

    class Meta:
        db_table = "accounting_journal_template_lines"
        ordering = ["order"]
        verbose_name = "Journal Entry Template Line"
        verbose_name_plural = "Journal Entry Template Lines"

    def __str__(self):
        return f"{self.template.name} - {self.account_code} ({self.debit_credit})"
