"""
Admin configuration for payments app.
"""

from django.contrib import admin
from django.utils.html import format_html

from apps.payments.models import PaymentTransaction, SubscriptionDiscount, SubscriptionPurchase


@admin.register(SubscriptionDiscount)
class SubscriptionDiscountAdmin(admin.ModelAdmin):
    """Admin interface for SubscriptionDiscount model."""

    list_display = [
        "billing_period_months",
        "discount_percentage",
        "description",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "billing_period_months"]
    search_fields = ["description"]
    ordering = ["billing_period_months"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = [
        (
            "Discount Configuration",
            {
                "fields": [
                    "billing_period_months",
                    "discount_percentage",
                    "description",
                    "is_active",
                ]
            },
        ),
        (
            "Timestamps",
            {
                "fields": ["created_at", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]


@admin.register(SubscriptionPurchase)
class SubscriptionPurchaseAdmin(admin.ModelAdmin):
    """Admin interface for SubscriptionPurchase model."""

    list_display = [
        "invoice_number",
        "tenant_name",
        "plan_name",
        "purchase_type",
        "billing_period_months",
        "final_price_display",
        "payment_status_badge",
        "payment_method",
        "created_at",
    ]
    list_filter = [
        "payment_status",
        "payment_method",
        "purchase_type",
        "billing_period_months",
        "currency",
        "created_at",
    ]
    search_fields = [
        "invoice_number",
        "tenant__company_name",
        "subscription_plan__name",
        "payment_gateway_transaction_id",
    ]
    ordering = ["-created_at"]
    readonly_fields = [
        "id",
        "invoice_number",
        "created_at",
        "updated_at",
        "payment_completed_at",
    ]
    raw_id_fields = ["tenant", "subscription_plan", "purchased_by", "previous_plan"]
    date_hierarchy = "created_at"

    fieldsets = [
        (
            "Purchase Information",
            {
                "fields": [
                    "id",
                    "invoice_number",
                    "tenant",
                    "subscription_plan",
                    "purchased_by",
                    "purchase_type",
                    "previous_plan",
                ]
            },
        ),
        (
            "Billing Period",
            {
                "fields": [
                    "billing_period_months",
                    "start_date",
                    "end_date",
                ]
            },
        ),
        (
            "Pricing",
            {
                "fields": [
                    "base_price",
                    "discount_percentage",
                    "discount_amount",
                    "final_price",
                    "currency",
                    "base_price_irr",
                    "final_price_irr",
                ]
            },
        ),
        (
            "Payment",
            {
                "fields": [
                    "payment_status",
                    "payment_method",
                    "payment_gateway_transaction_id",
                    "payment_completed_at",
                ]
            },
        ),
        (
            "Additional Information",
            {
                "fields": [
                    "invoice_pdf_path",
                    "ip_address",
                    "user_agent",
                    "metadata",
                    "notes",
                ],
                "classes": ["collapse"],
            },
        ),
        (
            "Timestamps",
            {
                "fields": ["created_at", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]

    def tenant_name(self, obj):
        """Display tenant company name."""
        return obj.tenant.company_name

    tenant_name.short_description = "Tenant"
    tenant_name.admin_order_field = "tenant__company_name"

    def plan_name(self, obj):
        """Display subscription plan name."""
        return obj.subscription_plan.name

    plan_name.short_description = "Plan"
    plan_name.admin_order_field = "subscription_plan__name"

    def final_price_display(self, obj):
        """Display final price with currency."""
        return f"{obj.currency} {obj.final_price:,.2f}"

    final_price_display.short_description = "Price"
    final_price_display.admin_order_field = "final_price"

    def payment_status_badge(self, obj):
        """Display payment status with color badge."""
        colors = {
            "pending": "#FFA500",  # Orange
            "processing": "#0066CC",  # Blue
            "completed": "#28A745",  # Green
            "failed": "#DC3545",  # Red
            "refunded": "#6C757D",  # Gray
            "cancelled": "#6C757D",  # Gray
        }
        color = colors.get(obj.payment_status, "#6C757D")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_payment_status_display(),
        )

    payment_status_badge.short_description = "Status"
    payment_status_badge.admin_order_field = "payment_status"


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    """Admin interface for PaymentTransaction model."""

    list_display = [
        "transaction_id_short",
        "tenant_name",
        "payment_gateway",
        "amount_display",
        "status_badge",
        "attempt_number",
        "duration_display",
        "initiated_at",
    ]
    list_filter = [
        "status",
        "payment_gateway",
        "is_retry",
        "initiated_at",
    ]
    search_fields = [
        "transaction_id",
        "gateway_transaction_id",
        "tenant__company_name",
        "subscription_purchase__invoice_number",
    ]
    ordering = ["-initiated_at"]
    readonly_fields = [
        "id",
        "transaction_id",
        "initiated_at",
        "completed_at",
    ]
    raw_id_fields = ["subscription_purchase", "tenant"]
    date_hierarchy = "initiated_at"

    fieldsets = [
        (
            "Transaction Information",
            {
                "fields": [
                    "id",
                    "transaction_id",
                    "subscription_purchase",
                    "tenant",
                ]
            },
        ),
        (
            "Payment Details",
            {
                "fields": [
                    "payment_gateway",
                    "gateway_transaction_id",
                    "gateway_reference",
                    "amount",
                    "currency",
                    "exchange_rate",
                ]
            },
        ),
        (
            "Status",
            {
                "fields": [
                    "status",
                    "error_message",
                    "error_code",
                    "attempt_number",
                    "is_retry",
                ]
            },
        ),
        (
            "Gateway Data",
            {
                "fields": ["request_data", "response_data"],
                "classes": ["collapse"],
            },
        ),
        (
            "Security",
            {
                "fields": ["ip_address"],
                "classes": ["collapse"],
            },
        ),
        (
            "Timestamps",
            {
                "fields": ["initiated_at", "completed_at"],
                "classes": ["collapse"],
            },
        ),
    ]

    def transaction_id_short(self, obj):
        """Display shortened transaction ID."""
        return str(obj.transaction_id)[:8] + "..."

    transaction_id_short.short_description = "Transaction ID"

    def tenant_name(self, obj):
        """Display tenant company name."""
        return obj.tenant.company_name

    tenant_name.short_description = "Tenant"
    tenant_name.admin_order_field = "tenant__company_name"

    def amount_display(self, obj):
        """Display amount with currency."""
        return f"{obj.currency} {obj.amount:,.2f}"

    amount_display.short_description = "Amount"
    amount_display.admin_order_field = "amount"

    def status_badge(self, obj):
        """Display status with color badge."""
        colors = {
            "pending": "#FFA500",
            "processing": "#0066CC",
            "completed": "#28A745",
            "failed": "#DC3545",
            "timeout": "#DC3545",
            "cancelled": "#6C757D",
            "refunded": "#6C757D",
        }
        color = colors.get(obj.status, "#6C757D")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"
    status_badge.admin_order_field = "status"

    def duration_display(self, obj):
        """Display transaction duration."""
        duration = obj.duration_seconds
        if duration is not None:
            return f"{duration:.2f}s"
        return "-"

    duration_display.short_description = "Duration"
