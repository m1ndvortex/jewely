from django.contrib import admin
from django.utils.html import format_html

from .models import CustomOrder, RepairOrder, RepairOrderPhoto


class RepairOrderPhotoInline(admin.TabularInline):
    """Inline admin for repair order photos."""

    model = RepairOrderPhoto
    extra = 0
    readonly_fields = ("taken_at", "taken_by")
    fields = ("photo", "photo_type", "description", "taken_at", "taken_by")


@admin.register(RepairOrder)
class RepairOrderAdmin(admin.ModelAdmin):
    """Admin interface for RepairOrder model."""

    list_display = [
        "order_number",
        "customer",
        "service_type",
        "status_badge",
        "priority",
        "estimated_completion",
        "is_overdue_display",
        "assigned_to",
    ]
    list_filter = [
        "status",
        "service_type",
        "priority",
        "tenant",
        "estimated_completion",
        "created_at",
    ]
    search_fields = [
        "order_number",
        "customer__first_name",
        "customer__last_name",
        "item_description",
        "service_notes",
    ]
    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
        "received_date",
        "actual_completion",
        "delivered_date",
        "is_overdue",
        "days_until_due",
    ]

    fieldsets = (
        (
            "Order Information",
            {"fields": ("id", "tenant", "order_number", "customer", "created_by")},
        ),
        ("Item Details", {"fields": ("item_description", "service_type", "service_notes")}),
        ("Status & Priority", {"fields": ("status", "priority", "assigned_to")}),
        (
            "Dates",
            {
                "fields": (
                    "received_date",
                    "estimated_completion",
                    "actual_completion",
                    "delivered_date",
                    "is_overdue",
                    "days_until_due",
                )
            },
        ),
        ("Pricing", {"fields": ("cost_estimate", "final_cost")}),
        ("Metadata", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    inlines = [RepairOrderPhotoInline]

    def status_badge(self, obj):
        """Display status with color coding."""
        colors = {
            "received": "blue",
            "in_progress": "orange",
            "quality_check": "purple",
            "completed": "green",
            "delivered": "darkgreen",
            "cancelled": "red",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>', color, obj.get_status_display()
        )

    status_badge.short_description = "Status"

    def is_overdue_display(self, obj):
        """Display overdue status with color coding."""
        if obj.is_overdue:
            return format_html('<span style="color: red; font-weight: bold;">Yes</span>')
        return format_html('<span style="color: green;">No</span>')

    is_overdue_display.short_description = "Overdue"

    def get_queryset(self, request):
        """Filter by tenant for non-superusers."""
        qs = super().get_queryset(request)
        if not request.user.is_superuser and hasattr(request.user, "tenant"):
            qs = qs.filter(tenant=request.user.tenant)
        return qs.select_related("tenant", "customer", "assigned_to", "created_by")

    def save_model(self, request, obj, form, change):
        """Set tenant and created_by on save."""
        if not change:  # Creating new object
            if hasattr(request.user, "tenant"):
                obj.tenant = request.user.tenant
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(RepairOrderPhoto)
class RepairOrderPhotoAdmin(admin.ModelAdmin):
    """Admin interface for RepairOrderPhoto model."""

    list_display = ["repair_order", "photo_type", "description_short", "taken_at", "taken_by"]
    list_filter = ["photo_type", "taken_at", "repair_order__tenant"]
    search_fields = [
        "repair_order__order_number",
        "description",
        "repair_order__customer__first_name",
        "repair_order__customer__last_name",
    ]
    readonly_fields = ["id", "taken_at", "created_at"]

    fieldsets = (
        (
            "Photo Information",
            {"fields": ("id", "repair_order", "photo", "photo_type", "description")},
        ),
        ("Metadata", {"fields": ("taken_at", "taken_by", "created_at"), "classes": ("collapse",)}),
    )

    def description_short(self, obj):
        """Display truncated description."""
        if obj.description:
            return obj.description[:50] + "..." if len(obj.description) > 50 else obj.description
        return "-"

    description_short.short_description = "Description"

    def get_queryset(self, request):
        """Filter by tenant for non-superusers."""
        qs = super().get_queryset(request)
        if not request.user.is_superuser and hasattr(request.user, "tenant"):
            qs = qs.filter(repair_order__tenant=request.user.tenant)
        return qs.select_related("repair_order", "repair_order__tenant", "taken_by")

    def save_model(self, request, obj, form, change):
        """Set taken_by on save."""
        if not change:  # Creating new object
            obj.taken_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(CustomOrder)
class CustomOrderAdmin(admin.ModelAdmin):
    """Admin interface for CustomOrder model."""

    list_display = [
        "order_number",
        "customer",
        "complexity",
        "status_badge",
        "quoted_price",
        "deposit_amount",
        "estimated_completion",
        "is_overdue_display",
    ]
    list_filter = ["status", "complexity", "tenant", "estimated_completion", "requested_date"]
    search_fields = [
        "order_number",
        "customer__first_name",
        "customer__last_name",
        "design_description",
    ]
    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
        "requested_date",
        "actual_completion",
        "delivered_date",
        "is_overdue",
        "remaining_balance",
    ]

    fieldsets = (
        (
            "Order Information",
            {"fields": ("id", "tenant", "order_number", "customer", "created_by")},
        ),
        (
            "Design Details",
            {"fields": ("design_description", "design_specifications", "complexity")},
        ),
        ("Status & Assignment", {"fields": ("status", "designer", "craftsman")}),
        (
            "Dates",
            {
                "fields": (
                    "requested_date",
                    "estimated_completion",
                    "actual_completion",
                    "delivered_date",
                    "is_overdue",
                )
            },
        ),
        (
            "Pricing",
            {"fields": ("quoted_price", "final_price", "deposit_amount", "remaining_balance")},
        ),
        ("Metadata", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def status_badge(self, obj):
        """Display status with color coding."""
        colors = {
            "quote_requested": "blue",
            "quote_provided": "lightblue",
            "approved": "green",
            "in_design": "orange",
            "design_approved": "lightgreen",
            "in_production": "purple",
            "quality_check": "darkpurple",
            "completed": "darkgreen",
            "delivered": "black",
            "cancelled": "red",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>', color, obj.get_status_display()
        )

    status_badge.short_description = "Status"

    def is_overdue_display(self, obj):
        """Display overdue status with color coding."""
        if obj.is_overdue:
            return format_html('<span style="color: red; font-weight: bold;">Yes</span>')
        return format_html('<span style="color: green;">No</span>')

    is_overdue_display.short_description = "Overdue"

    def get_queryset(self, request):
        """Filter by tenant for non-superusers."""
        qs = super().get_queryset(request)
        if not request.user.is_superuser and hasattr(request.user, "tenant"):
            qs = qs.filter(tenant=request.user.tenant)
        return qs.select_related("tenant", "customer", "designer", "craftsman", "created_by")

    def save_model(self, request, obj, form, change):
        """Set tenant and created_by on save."""
        if not change:  # Creating new object
            if hasattr(request.user, "tenant"):
                obj.tenant = request.user.tenant
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
