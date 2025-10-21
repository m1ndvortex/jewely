"""
Django admin configuration for core models.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Branch, Tenant, User


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


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    """Admin interface for Branch model."""

    list_display = ["name", "tenant", "phone", "is_active", "created_at"]

    list_filter = [
        "is_active",
        "created_at",
        "tenant",
    ]

    search_fields = [
        "name",
        "address",
        "phone",
        "tenant__company_name",
    ]

    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        ("Basic Information", {"fields": ("id", "tenant", "name")}),
        ("Contact Information", {"fields": ("address", "phone")}),
        ("Status", {"fields": ("is_active",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    ordering = ["tenant", "name"]

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("tenant")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin interface for User model."""

    list_display = [
        "username",
        "email",
        "first_name",
        "last_name",
        "role",
        "tenant",
        "branch",
        "is_active",
        "is_mfa_enabled",
    ]

    list_filter = [
        "role",
        "is_active",
        "is_staff",
        "is_superuser",
        "is_mfa_enabled",
        "language",
        "theme",
        "tenant",
    ]

    search_fields = [
        "username",
        "email",
        "first_name",
        "last_name",
        "phone",
        "tenant__company_name",
    ]

    readonly_fields = [
        "date_joined",
        "last_login",
    ]

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            "Personal Information",
            {"fields": ("first_name", "last_name", "email", "phone")},
        ),
        (
            "Tenant & Role",
            {"fields": ("tenant", "role", "branch")},
        ),
        (
            "Preferences",
            {"fields": ("language", "theme")},
        ),
        (
            "Security",
            {"fields": ("is_mfa_enabled",)},
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Important Dates",
            {"fields": ("last_login", "date_joined"), "classes": ("collapse",)},
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "password1",
                    "password2",
                    "email",
                    "first_name",
                    "last_name",
                    "tenant",
                    "role",
                    "branch",
                    "language",
                    "theme",
                    "phone",
                ),
            },
        ),
    )

    ordering = ["username"]

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("tenant", "branch")
