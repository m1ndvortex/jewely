"""
Django admin configuration for sales models.
"""

from django.contrib import admin

from .models import Sale, SaleItem, Terminal


@admin.register(Terminal)
class TerminalAdmin(admin.ModelAdmin):
    """Admin interface for Terminal model."""

    list_display = ["terminal_id", "branch", "is_active", "last_used_at", "created_at"]
    list_filter = ["is_active", "branch", "created_at"]
    search_fields = ["terminal_id", "description"]
    readonly_fields = ["id", "created_at", "updated_at", "last_used_at"]
    fieldsets = [
        (
            "Basic Information",
            {
                "fields": ["id", "branch", "terminal_id", "description"],
            },
        ),
        (
            "Status",
            {
                "fields": ["is_active"],
            },
        ),
        (
            "Configuration",
            {
                "fields": ["configuration"],
            },
        ),
        (
            "Timestamps",
            {
                "fields": ["created_at", "updated_at", "last_used_at"],
            },
        ),
    ]


class SaleItemInline(admin.TabularInline):
    """Inline admin for SaleItem model."""

    model = SaleItem
    extra = 0
    readonly_fields = ["id", "subtotal", "created_at"]
    fields = ["inventory_item", "quantity", "unit_price", "discount", "subtotal", "notes"]


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    """Admin interface for Sale model."""

    list_display = [
        "sale_number",
        "customer",
        "branch",
        "terminal",
        "employee",
        "total",
        "payment_method",
        "status",
        "created_at",
    ]
    list_filter = ["status", "payment_method", "branch", "created_at"]
    search_fields = [
        "sale_number",
        "customer__customer_number",
        "customer__first_name",
        "customer__last_name",
    ]
    readonly_fields = ["id", "created_at", "updated_at", "completed_at"]
    inlines = [SaleItemInline]
    fieldsets = [
        (
            "Basic Information",
            {
                "fields": ["id", "tenant", "sale_number", "status"],
            },
        ),
        (
            "Relationships",
            {
                "fields": ["customer", "branch", "terminal", "employee"],
            },
        ),
        (
            "Financial Details",
            {
                "fields": ["subtotal", "tax", "discount", "total"],
            },
        ),
        (
            "Payment",
            {
                "fields": ["payment_method", "payment_details"],
            },
        ),
        (
            "Additional Information",
            {
                "fields": ["notes"],
            },
        ),
        (
            "Offline Sync",
            {
                "fields": ["is_synced", "offline_created_at"],
            },
        ),
        (
            "Timestamps",
            {
                "fields": ["created_at", "updated_at", "completed_at"],
            },
        ),
    ]


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    """Admin interface for SaleItem model."""

    list_display = [
        "sale",
        "inventory_item",
        "quantity",
        "unit_price",
        "discount",
        "subtotal",
        "created_at",
    ]
    list_filter = ["created_at"]
    search_fields = ["sale__sale_number", "inventory_item__name", "inventory_item__sku"]
    readonly_fields = ["id", "subtotal", "created_at"]
    fieldsets = [
        (
            "Basic Information",
            {
                "fields": ["id", "sale", "inventory_item"],
            },
        ),
        (
            "Pricing",
            {
                "fields": ["quantity", "unit_price", "discount", "subtotal"],
            },
        ),
        (
            "Additional Information",
            {
                "fields": ["notes"],
            },
        ),
        (
            "Timestamps",
            {
                "fields": ["created_at"],
            },
        ),
    ]
