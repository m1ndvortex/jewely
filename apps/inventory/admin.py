"""
Admin configuration for inventory models.
"""

from django.contrib import admin

from .models import InventoryItem, ProductCategory


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    """Admin interface for ProductCategory."""

    list_display = ["name", "parent", "tenant", "is_active", "created_at"]
    list_filter = ["is_active", "created_at", "tenant"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("tenant", "name", "parent", "description", "is_active"),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    """Admin interface for InventoryItem."""

    list_display = [
        "sku",
        "name",
        "category",
        "karat",
        "weight_grams",
        "quantity",
        "branch",
        "is_active",
    ]
    list_filter = [
        "is_active",
        "karat",
        "craftsmanship_level",
        "category",
        "branch",
        "created_at",
    ]
    search_fields = [
        "sku",
        "name",
        "serial_number",
        "lot_number",
        "barcode",
        "description",
    ]
    readonly_fields = ["created_at", "updated_at", "markup_percentage"]
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "tenant",
                    "sku",
                    "name",
                    "category",
                    "description",
                    "is_active",
                ),
            },
        ),
        (
            "Jewelry Attributes",
            {
                "fields": ("karat", "weight_grams", "craftsmanship_level"),
            },
        ),
        (
            "Pricing",
            {
                "fields": ("cost_price", "selling_price", "markup_percentage"),
            },
        ),
        (
            "Inventory Tracking",
            {
                "fields": ("quantity", "min_quantity", "branch"),
            },
        ),
        (
            "Traceability",
            {
                "fields": ("serial_number", "lot_number", "barcode", "qr_code"),
            },
        ),
        (
            "Supplier Information",
            {
                "fields": ("supplier_name", "supplier_sku"),
                "classes": ("collapse",),
            },
        ),
        (
            "Additional Information",
            {
                "fields": ("notes",),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("tenant", "category", "branch")
