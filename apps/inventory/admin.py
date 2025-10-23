"""
Admin configuration for inventory models.
"""

from django.contrib import admin

from .models import InventoryItem, InventoryTransfer, InventoryTransferItem, ProductCategory


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


class InventoryTransferItemInline(admin.TabularInline):
    """Inline admin for transfer items."""

    model = InventoryTransferItem
    extra = 0
    readonly_fields = ["unit_cost", "received_quantity", "has_discrepancy", "discrepancy_notes"]
    fields = [
        "inventory_item",
        "quantity",
        "unit_cost",
        "received_quantity",
        "has_discrepancy",
        "discrepancy_notes",
        "notes",
    ]

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("inventory_item")


@admin.register(InventoryTransfer)
class InventoryTransferAdmin(admin.ModelAdmin):
    """Admin interface for InventoryTransfer."""

    list_display = [
        "transfer_number",
        "from_branch",
        "to_branch",
        "status",
        "requested_by",
        "total_value",
        "requires_approval",
        "created_at",
    ]
    list_filter = [
        "status",
        "requires_approval",
        "from_branch",
        "to_branch",
        "created_at",
    ]
    search_fields = [
        "transfer_number",
        "notes",
    ]
    readonly_fields = [
        "transfer_number",
        "status",
        "total_value",
        "created_at",
        "approved_at",
        "rejected_at",
        "shipped_at",
        "received_at",
    ]
    inlines = [InventoryTransferItemInline]
    fieldsets = (
        (
            "Transfer Information",
            {
                "fields": (
                    "tenant",
                    "transfer_number",
                    "from_branch",
                    "to_branch",
                    "status",
                    "total_value",
                    "requires_approval",
                ),
            },
        ),
        (
            "Workflow Tracking",
            {
                "fields": (
                    "requested_by",
                    "approved_by",
                    "rejected_by",
                    "shipped_by",
                    "received_by",
                ),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "approved_at",
                    "rejected_at",
                    "shipped_at",
                    "received_at",
                ),
            },
        ),
        (
            "Additional Information",
            {
                "fields": ("notes", "rejection_reason"),
            },
        ),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related(
            "tenant",
            "from_branch",
            "to_branch",
            "requested_by",
            "approved_by",
            "rejected_by",
            "shipped_by",
            "received_by",
        )


@admin.register(InventoryTransferItem)
class InventoryTransferItemAdmin(admin.ModelAdmin):
    """Admin interface for InventoryTransferItem."""

    list_display = [
        "transfer",
        "inventory_item",
        "quantity",
        "received_quantity",
        "has_discrepancy",
        "unit_cost",
    ]
    list_filter = [
        "has_discrepancy",
        "created_at",
    ]
    search_fields = [
        "transfer__transfer_number",
        "inventory_item__sku",
        "inventory_item__name",
        "notes",
        "discrepancy_notes",
    ]
    readonly_fields = ["unit_cost", "created_at", "updated_at"]
    fieldsets = (
        (
            "Transfer Item Information",
            {
                "fields": (
                    "transfer",
                    "inventory_item",
                    "quantity",
                    "unit_cost",
                ),
            },
        ),
        (
            "Receiving Information",
            {
                "fields": (
                    "received_quantity",
                    "has_discrepancy",
                    "discrepancy_notes",
                ),
            },
        ),
        (
            "Additional Information",
            {
                "fields": ("notes",),
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
        return qs.select_related("transfer", "inventory_item")
