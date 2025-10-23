"""
Admin configuration for procurement models.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import (
    GoodsReceipt,
    PurchaseOrder,
    PurchaseOrderApprovalThreshold,
    PurchaseOrderItem,
    Supplier,
    SupplierCommunication,
    SupplierDocument,
)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    """Admin interface for Supplier model."""

    list_display = [
        "name",
        "contact_person",
        "email",
        "phone",
        "rating_display",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "rating", "created_at"]
    search_fields = ["name", "contact_person", "email", "phone"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "contact_person", "is_active")}),
        ("Contact Information", {"fields": ("email", "phone", "address")}),
        ("Business Information", {"fields": ("tax_id", "payment_terms", "rating")}),
        ("Notes", {"fields": ("notes",)}),
        (
            "Audit Information",
            {"fields": ("created_by", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def rating_display(self, obj):
        """Display rating as stars."""
        stars = "★" * obj.rating + "☆" * (5 - obj.rating)
        return format_html('<span title="{}/5">{}</span>', obj.rating, stars)

    rating_display.short_description = "Rating"


class PurchaseOrderItemInline(admin.TabularInline):
    """Inline admin for PurchaseOrderItem."""

    model = PurchaseOrderItem
    extra = 0
    fields = [
        "product_name",
        "product_sku",
        "quantity",
        "received_quantity",
        "unit_price",
        "total_price",
    ]
    readonly_fields = ["total_price"]


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    """Admin interface for PurchaseOrder model."""

    list_display = [
        "po_number",
        "supplier",
        "status",
        "priority",
        "total_amount",
        "order_date",
        "expected_delivery",
    ]
    list_filter = ["status", "priority", "order_date", "expected_delivery"]
    search_fields = ["po_number", "supplier__name", "supplier_reference"]
    readonly_fields = ["created_at", "updated_at", "approved_at", "sent_at", "completed_at"]
    inlines = [PurchaseOrderItemInline]

    fieldsets = (
        ("Order Information", {"fields": ("po_number", "supplier", "branch")}),
        ("Financial Information", {"fields": ("subtotal", "tax_amount", "total_amount")}),
        ("Status and Priority", {"fields": ("status", "priority")}),
        ("Dates", {"fields": ("order_date", "expected_delivery")}),
        ("Additional Information", {"fields": ("supplier_reference", "notes")}),
        (
            "Audit Information",
            {
                "fields": (
                    "created_by",
                    "created_at",
                    "updated_at",
                    "approved_by",
                    "approved_at",
                    "sent_at",
                    "completed_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    actions = ["approve_orders", "send_to_supplier"]

    def approve_orders(self, request, queryset):
        """Bulk approve purchase orders."""
        count = 0
        for order in queryset.filter(status="DRAFT"):
            order.approve(request.user)
            order.save()
            count += 1

        self.message_user(request, f"{count} purchase orders were approved.")

    approve_orders.short_description = "Approve selected orders"

    def send_to_supplier(self, request, queryset):
        """Bulk send orders to suppliers."""
        count = 0
        for order in queryset.filter(status="APPROVED"):
            order.send_to_supplier()
            order.save()
            count += 1

        self.message_user(request, f"{count} purchase orders were sent to suppliers.")

    send_to_supplier.short_description = "Send selected orders to suppliers"


@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    """Admin interface for PurchaseOrderItem model."""

    list_display = [
        "purchase_order",
        "product_name",
        "product_sku",
        "quantity",
        "received_quantity",
        "unit_price",
        "total_price",
    ]
    list_filter = ["purchase_order__status", "created_at"]
    search_fields = ["product_name", "product_sku", "purchase_order__po_number"]
    readonly_fields = ["total_price", "created_at", "updated_at"]


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    """Admin interface for GoodsReceipt model."""

    list_display = [
        "receipt_number",
        "purchase_order",
        "status",
        "received_date",
        "quality_check_passed",
        "has_discrepancy",
    ]
    list_filter = ["status", "received_date", "quality_check_passed", "has_discrepancy"]
    search_fields = [
        "receipt_number",
        "purchase_order__po_number",
        "supplier_invoice_number",
        "tracking_number",
    ]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Receipt Information", {"fields": ("receipt_number", "purchase_order")}),
        ("Shipment Information", {"fields": ("supplier_invoice_number", "tracking_number")}),
        ("Status and Dates", {"fields": ("status", "received_date")}),
        ("Quality Control", {"fields": ("quality_check_passed", "inspection_notes")}),
        ("Discrepancy Tracking", {"fields": ("has_discrepancy", "discrepancy_notes")}),
        (
            "Audit Information",
            {
                "fields": ("received_by", "inspected_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    actions = ["mark_completed", "mark_quality_passed"]

    def mark_completed(self, request, queryset):
        """Mark selected receipts as completed."""
        count = 0
        for receipt in queryset.exclude(status="COMPLETED"):
            receipt.mark_completed()
            count += 1

        self.message_user(request, f"{count} goods receipts were marked as completed.")

    mark_completed.short_description = "Mark selected receipts as completed"

    def mark_quality_passed(self, request, queryset):
        """Mark quality check as passed for selected receipts."""
        count = queryset.update(quality_check_passed=True)
        self.message_user(request, f"{count} goods receipts were marked as quality passed.")

    mark_quality_passed.short_description = "Mark quality check as passed"


@admin.register(SupplierCommunication)
class SupplierCommunicationAdmin(admin.ModelAdmin):
    """Admin interface for SupplierCommunication model."""

    list_display = [
        "supplier",
        "subject",
        "communication_type",
        "communication_date",
        "contact_person",
        "requires_followup",
        "is_completed",
    ]
    list_filter = [
        "communication_type",
        "requires_followup",
        "is_completed",
        "communication_date",
    ]
    search_fields = [
        "supplier__name",
        "subject",
        "content",
        "contact_person",
    ]
    readonly_fields = ["created_at", "updated_at"]
    filter_horizontal = ["internal_participants"]

    fieldsets = (
        (
            "Communication Details",
            {"fields": ("supplier", "communication_type", "subject", "content")},
        ),
        ("Participants", {"fields": ("contact_person", "internal_participants")}),
        ("Follow-up", {"fields": ("requires_followup", "followup_date", "is_completed")}),
        (
            "Metadata",
            {
                "fields": ("communication_date", "created_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related("supplier", "created_by")


@admin.register(SupplierDocument)
class SupplierDocumentAdmin(admin.ModelAdmin):
    """Admin interface for SupplierDocument model."""

    list_display = [
        "supplier",
        "title",
        "document_type",
        "issue_date",
        "expiry_date",
        "is_expired_display",
        "is_active",
    ]
    list_filter = [
        "document_type",
        "is_active",
        "issue_date",
        "expiry_date",
    ]
    search_fields = [
        "supplier__name",
        "title",
        "description",
    ]
    readonly_fields = ["file_size", "mime_type", "created_at", "updated_at"]

    fieldsets = (
        ("Document Information", {"fields": ("supplier", "document_type", "title", "description")}),
        ("File Information", {"fields": ("file", "file_size", "mime_type")}),
        ("Validity", {"fields": ("issue_date", "expiry_date", "is_active")}),
        (
            "Metadata",
            {"fields": ("uploaded_by", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def is_expired_display(self, obj):
        """Display expiry status with color coding."""
        if obj.is_expired:
            return format_html('<span style="color: red;">Expired</span>')
        elif obj.expires_soon:
            return format_html('<span style="color: orange;">Expires Soon</span>')
        else:
            return format_html('<span style="color: green;">Valid</span>')

    is_expired_display.short_description = "Status"

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related("supplier", "uploaded_by")


@admin.register(PurchaseOrderApprovalThreshold)
class PurchaseOrderApprovalThresholdAdmin(admin.ModelAdmin):
    """Admin interface for PurchaseOrderApprovalThreshold model."""

    list_display = [
        "tenant",
        "min_amount",
        "max_amount_display",
        "required_role",
        "is_active",
        "created_at",
    ]
    list_filter = ["required_role", "is_active", "created_at"]
    search_fields = ["tenant__company_name"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Threshold Configuration", {"fields": ("tenant", "min_amount", "max_amount")}),
        ("Approval Requirements", {"fields": ("required_role", "is_active")}),
        (
            "Audit Information",
            {"fields": ("created_by", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def max_amount_display(self, obj):
        """Display max amount with 'No Limit' for null values."""
        if obj.max_amount:
            return f"${obj.max_amount:,.2f}"
        return "No Limit"

    max_amount_display.short_description = "Max Amount"

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related("tenant", "created_by")
