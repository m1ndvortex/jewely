"""
Admin configuration for accounting models.
"""

from django.contrib import admin

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
