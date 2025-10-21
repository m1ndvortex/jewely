"""
Django admin configuration for core models.
"""

from django.contrib import admin

from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    """Admin interface for Tenant model."""

    list_display = ["company_name", "slug", "status", "created_at", "updated_at"]

    list_filter = [
        "status",
        "created_at",
    ]

    search_fields = [
        "company_name",
        "slug",
        "id",
    ]

    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        ("Basic Information", {"fields": ("id", "company_name", "slug")}),
        ("Status", {"fields": ("status",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    ordering = ["-created_at"]

    def get_readonly_fields(self, request, obj=None):
        """Make slug readonly when editing existing tenant."""
        if obj:  # Editing an existing object
            return self.readonly_fields + ["slug"]
        return self.readonly_fields
