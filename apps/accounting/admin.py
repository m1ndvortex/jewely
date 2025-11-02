"""
Admin configuration for accounting models.
"""

from django.contrib import admin

from .bank_models import (
    BankAccount,
    BankReconciliation,
    BankStatementImport,
    BankTransaction,
)
from .bill_models import Bill, BillLine, BillPayment


class BillLineInline(admin.TabularInline):
    """Inline admin for bill lines."""

    model = BillLine
    extra = 1
    fields = ["account", "description", "quantity", "unit_price", "amount", "notes"]
    readonly_fields = ["amount"]


class BillPaymentInline(admin.TabularInline):
    """Inline admin for bill payments."""

    model = BillPayment
    extra = 0
    fields = ["payment_date", "amount", "payment_method", "reference_number", "notes"]
    readonly_fields = ["created_at", "created_by"]


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    """Admin interface for Bill model."""

    list_display = [
        "bill_number",
        "supplier",
        "bill_date",
        "due_date",
        "total",
        "amount_paid",
        "amount_due",
        "status",
        "is_overdue",
    ]
    list_filter = ["status", "bill_date", "due_date", "tenant"]
    search_fields = ["bill_number", "supplier__name", "reference_number"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "created_by",
        "approved_by",
        "approved_at",
        "amount_due",
        "is_paid",
        "is_overdue",
        "days_overdue",
        "aging_bucket",
    ]
    inlines = [BillLineInline, BillPaymentInline]
    fieldsets = [
        (
            "Bill Information",
            {
                "fields": [
                    "tenant",
                    "supplier",
                    "bill_number",
                    "bill_date",
                    "due_date",
                    "reference_number",
                ]
            },
        ),
        (
            "Financial Information",
            {"fields": ["subtotal", "tax", "total", "amount_paid", "amount_due", "status"]},
        ),
        (
            "Accounting",
            {"fields": ["journal_entry"]},
        ),
        (
            "Additional Information",
            {"fields": ["notes"]},
        ),
        (
            "Audit Information",
            {
                "fields": [
                    "created_at",
                    "created_by",
                    "updated_at",
                    "approved_by",
                    "approved_at",
                    "is_paid",
                    "is_overdue",
                    "days_overdue",
                    "aging_bucket",
                ],
                "classes": ["collapse"],
            },
        ),
    ]

    def amount_due(self, obj):
        """Display amount due."""
        return obj.amount_due

    amount_due.short_description = "Amount Due"


@admin.register(BillLine)
class BillLineAdmin(admin.ModelAdmin):
    """Admin interface for BillLine model."""

    list_display = ["bill", "account", "description", "quantity", "unit_price", "amount"]
    list_filter = ["account", "bill__tenant"]
    search_fields = ["description", "bill__bill_number", "account"]
    readonly_fields = ["created_at", "updated_at", "amount"]


@admin.register(BillPayment)
class BillPaymentAdmin(admin.ModelAdmin):
    """Admin interface for BillPayment model."""

    list_display = [
        "bill",
        "payment_date",
        "amount",
        "payment_method",
        "reference_number",
        "created_by",
    ]
    list_filter = ["payment_method", "payment_date", "tenant"]
    search_fields = ["bill__bill_number", "reference_number"]
    readonly_fields = ["created_at", "updated_at", "created_by"]
    fieldsets = [
        (
            "Payment Information",
            {
                "fields": [
                    "tenant",
                    "bill",
                    "payment_date",
                    "amount",
                    "payment_method",
                ]
            },
        ),
        (
            "Bank and Reference",
            {"fields": ["bank_account", "reference_number"]},
        ),
        (
            "Accounting",
            {"fields": ["journal_entry"]},
        ),
        (
            "Additional Information",
            {"fields": ["notes"]},
        ),
        (
            "Audit Information",
            {"fields": ["created_at", "created_by", "updated_at"], "classes": ["collapse"]},
        ),
    ]


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    """Admin interface for BankAccount model."""

    list_display = [
        "account_name",
        "bank_name",
        "masked_account_number",
        "account_type",
        "current_balance",
        "is_active",
        "is_default",
        "needs_reconciliation",
    ]
    list_filter = ["account_type", "is_active", "is_default", "tenant"]
    search_fields = ["account_name", "bank_name", "account_number"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "created_by",
        "masked_account_number",
        "unreconciled_balance",
        "days_since_reconciliation",
        "needs_reconciliation",
    ]
    fieldsets = [
        (
            "Bank Account Information",
            {
                "fields": [
                    "tenant",
                    "account_name",
                    "account_number",
                    "masked_account_number",
                    "bank_name",
                    "account_type",
                ]
            },
        ),
        (
            "Balance Information",
            {
                "fields": [
                    "opening_balance",
                    "current_balance",
                    "reconciled_balance",
                    "unreconciled_balance",
                    "last_reconciled_date",
                    "days_since_reconciliation",
                    "needs_reconciliation",
                ]
            },
        ),
        (
            "Additional Details",
            {
                "fields": [
                    "routing_number",
                    "swift_code",
                    "currency",
                    "notes",
                ]
            },
        ),
        (
            "Integration",
            {"fields": ["ledger_account"]},
        ),
        (
            "Status",
            {"fields": ["is_active", "is_default"]},
        ),
        (
            "Audit Information",
            {
                "fields": ["created_at", "created_by", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]

    def masked_account_number(self, obj):
        """Display masked account number."""
        return obj.masked_account_number

    masked_account_number.short_description = "Account Number"

    def unreconciled_balance(self, obj):
        """Display unreconciled balance."""
        return obj.unreconciled_balance

    unreconciled_balance.short_description = "Unreconciled Balance"

    def days_since_reconciliation(self, obj):
        """Display days since last reconciliation."""
        days = obj.days_since_reconciliation
        return days if days is not None else "Never"

    days_since_reconciliation.short_description = "Days Since Reconciliation"

    def needs_reconciliation(self, obj):
        """Display if account needs reconciliation."""
        return obj.needs_reconciliation

    needs_reconciliation.boolean = True
    needs_reconciliation.short_description = "Needs Reconciliation"



@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    """Admin interface for BankTransaction model."""

    list_display = [
        "transaction_date",
        "bank_account",
        "description",
        "transaction_type",
        "amount",
        "is_reconciled",
        "reconciled_date",
    ]
    list_filter = [
        "transaction_type",
        "is_reconciled",
        "transaction_date",
        "reconciled_date",
        "tenant",
    ]
    search_fields = [
        "description",
        "reference_number",
        "bank_account__account_name",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
        "created_by",
        "reconciled_by",
        "signed_amount",
    ]
    fieldsets = [
        (
            "Transaction Information",
            {
                "fields": [
                    "tenant",
                    "bank_account",
                    "transaction_date",
                    "description",
                    "amount",
                    "signed_amount",
                    "transaction_type",
                    "reference_number",
                ]
            },
        ),
        (
            "Reconciliation Status",
            {
                "fields": [
                    "is_reconciled",
                    "reconciled_date",
                    "reconciled_by",
                    "reconciliation",
                    "unreconcile_reason",
                ]
            },
        ),
        (
            "Matching",
            {"fields": ["matched_journal_entry"]},
        ),
        (
            "Import Tracking",
            {"fields": ["statement_import"]},
        ),
        (
            "Additional Information",
            {"fields": ["notes"]},
        ),
        (
            "Audit Information",
            {
                "fields": ["created_at", "created_by", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]

    def signed_amount(self, obj):
        """Display signed amount."""
        return obj.signed_amount

    signed_amount.short_description = "Signed Amount"


@admin.register(BankReconciliation)
class BankReconciliationAdmin(admin.ModelAdmin):
    """Admin interface for BankReconciliation model."""

    list_display = [
        "reconciliation_date",
        "bank_account",
        "status",
        "is_balanced",
        "variance",
        "statement_ending_balance",
        "completed_date",
    ]
    list_filter = [
        "status",
        "is_balanced",
        "reconciliation_date",
        "completed_date",
        "tenant",
    ]
    search_fields = [
        "bank_account__account_name",
        "notes",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
        "created_by",
        "completed_by",
        "variance",
        "is_balanced",
        "reconciled_transaction_count",
        "unreconciled_transaction_count",
    ]
    fieldsets = [
        (
            "Reconciliation Information",
            {
                "fields": [
                    "tenant",
                    "bank_account",
                    "reconciliation_date",
                    "period_start_date",
                    "period_end_date",
                    "status",
                ]
            },
        ),
        (
            "Statement Balances",
            {
                "fields": [
                    "statement_beginning_balance",
                    "statement_ending_balance",
                ]
            },
        ),
        (
            "Book Balances",
            {
                "fields": [
                    "book_beginning_balance",
                    "book_ending_balance",
                ]
            },
        ),
        (
            "Reconciliation Totals",
            {
                "fields": [
                    "total_deposits",
                    "total_withdrawals",
                    "total_adjustments",
                    "variance",
                    "is_balanced",
                ]
            },
        ),
        (
            "Transaction Counts",
            {
                "fields": [
                    "reconciled_transaction_count",
                    "unreconciled_transaction_count",
                ]
            },
        ),
        (
            "Completion Information",
            {
                "fields": [
                    "completed_date",
                    "completed_by",
                ]
            },
        ),
        (
            "Additional Information",
            {
                "fields": [
                    "notes",
                    "statement_file",
                ]
            },
        ),
        (
            "Audit Information",
            {
                "fields": ["created_at", "created_by", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]

    def reconciled_transaction_count(self, obj):
        """Display count of reconciled transactions."""
        return obj.reconciled_transaction_count

    reconciled_transaction_count.short_description = "Reconciled Transactions"

    def unreconciled_transaction_count(self, obj):
        """Display count of unreconciled transactions."""
        return obj.unreconciled_transaction_count

    unreconciled_transaction_count.short_description = "Unreconciled Transactions"


@admin.register(BankStatementImport)
class BankStatementImportAdmin(admin.ModelAdmin):
    """Admin interface for BankStatementImport model."""

    list_display = [
        "import_date",
        "bank_account",
        "file_name",
        "file_format",
        "status",
        "transactions_imported",
        "transactions_matched",
        "success_rate_display",
    ]
    list_filter = [
        "status",
        "file_format",
        "import_date",
        "tenant",
    ]
    search_fields = [
        "file_name",
        "bank_account__account_name",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
        "imported_by",
        "import_date",
        "processing_started_at",
        "processing_completed_at",
        "processing_duration",
        "success_rate",
        "match_rate",
    ]
    fieldsets = [
        (
            "Import Information",
            {
                "fields": [
                    "tenant",
                    "bank_account",
                    "import_date",
                    "file_name",
                    "file_format",
                    "file",
                ]
            },
        ),
        (
            "Import Statistics",
            {
                "fields": [
                    "transactions_imported",
                    "transactions_matched",
                    "transactions_duplicates",
                    "transactions_errors",
                    "success_rate",
                    "match_rate",
                ]
            },
        ),
        (
            "Statement Period",
            {
                "fields": [
                    "statement_start_date",
                    "statement_end_date",
                    "statement_balance",
                ]
            },
        ),
        (
            "Import Status",
            {
                "fields": [
                    "status",
                    "error_message",
                ]
            },
        ),
        (
            "Processing Information",
            {
                "fields": [
                    "processing_started_at",
                    "processing_completed_at",
                    "processing_duration",
                ]
            },
        ),
        (
            "Additional Information",
            {"fields": ["notes"]},
        ),
        (
            "Audit Information",
            {
                "fields": ["created_at", "imported_by", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]

    def success_rate_display(self, obj):
        """Display success rate as percentage."""
        return f"{obj.success_rate:.1f}%"

    success_rate_display.short_description = "Success Rate"

    def processing_duration(self, obj):
        """Display processing duration."""
        duration = obj.processing_duration
        if duration is not None:
            return f"{duration:.2f} seconds"
        return "N/A"

    processing_duration.short_description = "Processing Duration"
