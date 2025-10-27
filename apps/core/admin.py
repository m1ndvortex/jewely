"""
Django admin configuration for core models.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.core.audit_models import APIRequestLog, AuditLog, DataChangeLog, LoginAttempt

from .models import (
    Branch,
    IntegrationSettings,
    InvoiceSettings,
    SubscriptionPlan,
    Tenant,
    TenantSettings,
    TenantSubscription,
    User,
)


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


@admin.register(TenantSettings)
class TenantSettingsAdmin(admin.ModelAdmin):
    """Admin interface for TenantSettings model."""

    list_display = [
        "tenant",
        "business_name",
        "currency",
        "timezone",
        "require_mfa_for_managers",
        "updated_at",
    ]

    list_filter = [
        "currency",
        "timezone",
        "require_mfa_for_managers",
        "tax_inclusive_pricing",
        "created_at",
    ]

    search_fields = [
        "tenant__company_name",
        "business_name",
        "email",
        "phone",
    ]

    readonly_fields = [
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Business Information",
            {
                "fields": (
                    "tenant",
                    "business_name",
                    "business_registration_number",
                    "tax_identification_number",
                )
            },
        ),
        (
            "Contact Information",
            {
                "fields": (
                    "address_line_1",
                    "address_line_2",
                    "city",
                    "state_province",
                    "postal_code",
                    "country",
                    "phone",
                    "fax",
                    "email",
                    "website",
                )
            },
        ),
        (
            "Branding",
            {
                "fields": (
                    "logo",
                    "primary_color",
                    "secondary_color",
                )
            },
        ),
        (
            "Localization",
            {
                "fields": (
                    "timezone",
                    "currency",
                    "date_format",
                )
            },
        ),
        (
            "Business Operations",
            {
                "fields": (
                    "business_hours",
                    "holidays",
                )
            },
        ),
        (
            "Tax Configuration",
            {
                "fields": (
                    "default_tax_rate",
                    "tax_inclusive_pricing",
                )
            },
        ),
        (
            "Security Settings",
            {
                "fields": (
                    "require_mfa_for_managers",
                    "password_expiry_days",
                )
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

    ordering = ["tenant__company_name"]

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("tenant")


@admin.register(InvoiceSettings)
class InvoiceSettingsAdmin(admin.ModelAdmin):
    """Admin interface for InvoiceSettings model."""

    list_display = [
        "tenant",
        "invoice_template",
        "invoice_number_prefix",
        "next_invoice_number",
        "receipt_number_prefix",
        "next_receipt_number",
        "updated_at",
    ]

    list_filter = [
        "invoice_template",
        "receipt_template",
        "invoice_numbering_scheme",
        "receipt_numbering_scheme",
        "show_tax_breakdown",
        "created_at",
    ]

    search_fields = [
        "tenant__company_name",
        "invoice_number_prefix",
        "receipt_number_prefix",
    ]

    readonly_fields = [
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Basic Settings",
            {
                "fields": (
                    "tenant",
                    "invoice_template",
                    "receipt_template",
                )
            },
        ),
        (
            "Invoice Numbering",
            {
                "fields": (
                    "invoice_numbering_scheme",
                    "invoice_number_prefix",
                    "invoice_number_format",
                    "next_invoice_number",
                )
            },
        ),
        (
            "Receipt Numbering",
            {
                "fields": (
                    "receipt_numbering_scheme",
                    "receipt_number_prefix",
                    "receipt_number_format",
                    "next_receipt_number",
                )
            },
        ),
        (
            "Display Options",
            {
                "fields": (
                    "show_item_codes",
                    "show_item_descriptions",
                    "show_item_weights",
                    "show_karat_purity",
                    "show_tax_breakdown",
                    "show_payment_terms",
                )
            },
        ),
        (
            "Custom Fields",
            {
                "fields": (
                    "custom_field_1_label",
                    "custom_field_1_value",
                    "custom_field_2_label",
                    "custom_field_2_value",
                )
            },
        ),
        (
            "Footer & Terms",
            {
                "fields": (
                    "invoice_footer_text",
                    "receipt_footer_text",
                    "payment_terms",
                    "return_policy",
                )
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

    ordering = ["tenant__company_name"]

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("tenant")


@admin.register(IntegrationSettings)
class IntegrationSettingsAdmin(admin.ModelAdmin):
    """Admin interface for IntegrationSettings model."""

    list_display = [
        "tenant",
        "payment_gateway_enabled",
        "payment_gateway_provider",
        "sms_provider_enabled",
        "sms_provider",
        "email_provider_enabled",
        "email_provider",
        "gold_rate_api_enabled",
        "updated_at",
    ]

    list_filter = [
        "payment_gateway_enabled",
        "payment_gateway_provider",
        "sms_provider_enabled",
        "sms_provider",
        "email_provider_enabled",
        "email_provider",
        "gold_rate_api_enabled",
        "payment_gateway_test_mode",
        "created_at",
    ]

    search_fields = [
        "tenant__company_name",
        "payment_gateway_provider",
        "sms_provider",
        "email_provider",
        "email_from_address",
    ]

    readonly_fields = [
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Basic Settings",
            {"fields": ("tenant",)},
        ),
        (
            "Payment Gateway",
            {
                "fields": (
                    "payment_gateway_enabled",
                    "payment_gateway_provider",
                    "payment_gateway_api_key",
                    "payment_gateway_secret_key",
                    "payment_gateway_webhook_secret",
                    "payment_gateway_test_mode",
                )
            },
        ),
        (
            "SMS Provider",
            {
                "fields": (
                    "sms_provider_enabled",
                    "sms_provider",
                    "sms_api_key",
                    "sms_api_secret",
                    "sms_sender_id",
                )
            },
        ),
        (
            "Email Provider",
            {
                "fields": (
                    "email_provider_enabled",
                    "email_provider",
                    "email_api_key",
                    "email_from_address",
                    "email_from_name",
                )
            },
        ),
        (
            "SMTP Settings",
            {
                "fields": (
                    "smtp_host",
                    "smtp_port",
                    "smtp_username",
                    "smtp_password",
                    "smtp_use_tls",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Gold Rate API",
            {
                "fields": (
                    "gold_rate_api_enabled",
                    "gold_rate_api_provider",
                    "gold_rate_api_key",
                    "gold_rate_update_frequency",
                )
            },
        ),
        (
            "Webhooks",
            {
                "fields": (
                    "webhook_url",
                    "webhook_secret",
                    "webhook_events",
                )
            },
        ),
        (
            "Additional Configuration",
            {
                "fields": ("additional_config",),
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

    ordering = ["tenant__company_name"]

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("tenant")

    def get_form(self, request, obj=None, **kwargs):
        """Customize form to show encrypted fields as password inputs."""
        form = super().get_form(request, obj, **kwargs)

        # Make sensitive fields use password input
        sensitive_fields = [
            "payment_gateway_api_key",
            "payment_gateway_secret_key",
            "payment_gateway_webhook_secret",
            "sms_api_key",
            "sms_api_secret",
            "email_api_key",
            "smtp_password",
            "gold_rate_api_key",
            "webhook_secret",
        ]

        for field_name in sensitive_fields:
            if field_name in form.base_fields:
                form.base_fields[field_name].widget.attrs["type"] = "password"

        return form


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    """Admin interface for SubscriptionPlan model."""

    list_display = [
        "name",
        "price",
        "billing_cycle",
        "status",
        "user_limit",
        "branch_limit",
        "inventory_limit",
        "display_order",
        "created_at",
    ]

    list_filter = [
        "status",
        "billing_cycle",
        "enable_multi_branch",
        "enable_advanced_reporting",
        "enable_api_access",
        "enable_custom_branding",
        "enable_priority_support",
        "created_at",
    ]

    search_fields = [
        "name",
        "description",
    ]

    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
        "archived_at",
    ]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "id",
                    "name",
                    "description",
                    "status",
                    "display_order",
                )
            },
        ),
        (
            "Pricing",
            {
                "fields": (
                    "price",
                    "billing_cycle",
                )
            },
        ),
        (
            "Resource Limits",
            {
                "fields": (
                    "user_limit",
                    "branch_limit",
                    "inventory_limit",
                    "storage_limit_gb",
                    "api_calls_per_month",
                )
            },
        ),
        (
            "Feature Flags",
            {
                "fields": (
                    "enable_multi_branch",
                    "enable_advanced_reporting",
                    "enable_api_access",
                    "enable_custom_branding",
                    "enable_priority_support",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at", "archived_at"),
                "classes": ("collapse",),
            },
        ),
    )

    ordering = ["display_order", "name"]

    actions = ["archive_plans", "activate_plans"]

    def archive_plans(self, request, queryset):
        """Archive selected plans."""
        count = 0
        for plan in queryset:
            if plan.is_active():
                plan.archive()
                count += 1
        self.message_user(request, f"Successfully archived {count} plan(s).")

    archive_plans.short_description = "Archive selected plans"

    def activate_plans(self, request, queryset):
        """Activate selected plans."""
        count = 0
        for plan in queryset:
            if plan.is_archived():
                plan.activate()
                count += 1
        self.message_user(request, f"Successfully activated {count} plan(s).")

    activate_plans.short_description = "Activate selected plans"


@admin.register(TenantSubscription)
class TenantSubscriptionAdmin(admin.ModelAdmin):
    """Admin interface for TenantSubscription model."""

    list_display = [
        "tenant",
        "plan",
        "status",
        "current_period_start",
        "current_period_end",
        "next_billing_date",
        "created_at",
    ]

    list_filter = [
        "status",
        "plan",
        "current_period_start",
        "next_billing_date",
        "created_at",
    ]

    search_fields = [
        "tenant__company_name",
        "plan__name",
        "stripe_customer_id",
        "stripe_subscription_id",
        "notes",
    ]

    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
        "cancelled_at",
    ]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "id",
                    "tenant",
                    "plan",
                    "status",
                )
            },
        ),
        (
            "Billing Information",
            {
                "fields": (
                    "current_period_start",
                    "current_period_end",
                    "next_billing_date",
                )
            },
        ),
        (
            "Trial Period",
            {
                "fields": (
                    "trial_start",
                    "trial_end",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Resource Limit Overrides",
            {
                "fields": (
                    "user_limit_override",
                    "branch_limit_override",
                    "inventory_limit_override",
                    "storage_limit_gb_override",
                    "api_calls_per_month_override",
                ),
                "classes": ("collapse",),
                "description": "Leave blank to use plan defaults. Set a value to override for this specific tenant.",
            },
        ),
        (
            "Feature Flag Overrides",
            {
                "fields": (
                    "enable_multi_branch_override",
                    "enable_advanced_reporting_override",
                    "enable_api_access_override",
                    "enable_custom_branding_override",
                    "enable_priority_support_override",
                ),
                "classes": ("collapse",),
                "description": "Leave blank to use plan defaults. Set a value to override for this specific tenant.",
            },
        ),
        (
            "Payment Gateway Integration",
            {
                "fields": (
                    "stripe_customer_id",
                    "stripe_subscription_id",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Cancellation",
            {
                "fields": (
                    "cancelled_at",
                    "cancellation_reason",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Notes",
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

    ordering = ["-created_at"]

    actions = ["activate_subscriptions", "deactivate_subscriptions"]

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("tenant", "plan")

    def activate_subscriptions(self, request, queryset):
        """Activate selected subscriptions."""
        count = 0
        for subscription in queryset:
            if not subscription.is_active():
                subscription.activate()
                count += 1
        self.message_user(request, f"Successfully activated {count} subscription(s).")

    activate_subscriptions.short_description = "Activate selected subscriptions"

    def deactivate_subscriptions(self, request, queryset):
        """Deactivate selected subscriptions."""
        count = 0
        for subscription in queryset:
            if subscription.is_active():
                subscription.deactivate()
                count += 1
        self.message_user(request, f"Successfully deactivated {count} subscription(s).")

    deactivate_subscriptions.short_description = "Deactivate selected subscriptions"


# ============================================================================
# Audit Log Admin Interfaces
# ============================================================================


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin interface for comprehensive audit logs."""

    list_display = [
        "timestamp",
        "category",
        "action",
        "severity",
        "user",
        "tenant",
        "ip_address",
        "description_short",
    ]

    list_filter = [
        "category",
        "action",
        "severity",
        "timestamp",
    ]

    search_fields = [
        "user__username",
        "tenant__company_name",
        "description",
        "ip_address",
        "request_path",
    ]

    readonly_fields = [
        "id",
        "tenant",
        "user",
        "category",
        "action",
        "severity",
        "description",
        "content_type",
        "object_id",
        "old_values",
        "new_values",
        "ip_address",
        "user_agent",
        "request_method",
        "request_path",
        "request_params",
        "response_status",
        "metadata",
        "timestamp",
    ]

    fieldsets = (
        (
            "Action Details",
            {
                "fields": (
                    "id",
                    "timestamp",
                    "category",
                    "action",
                    "severity",
                    "description",
                )
            },
        ),
        (
            "User & Tenant",
            {
                "fields": (
                    "user",
                    "tenant",
                )
            },
        ),
        (
            "Affected Object",
            {
                "fields": (
                    "content_type",
                    "object_id",
                )
            },
        ),
        (
            "Data Changes",
            {
                "fields": (
                    "old_values",
                    "new_values",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Request Metadata",
            {
                "fields": (
                    "ip_address",
                    "user_agent",
                    "request_method",
                    "request_path",
                    "request_params",
                    "response_status",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Additional Metadata",
            {
                "fields": ("metadata",),
                "classes": ("collapse",),
            },
        ),
    )

    ordering = ["-timestamp"]

    def has_add_permission(self, request):
        """Audit logs cannot be manually added."""
        return False

    def has_change_permission(self, request, obj=None):
        """Audit logs cannot be modified."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Audit logs cannot be deleted (except by superusers)."""
        return request.user.is_superuser

    def description_short(self, obj):
        """Return truncated description."""
        if len(obj.description) > 100:
            return obj.description[:100] + "..."
        return obj.description

    description_short.short_description = "Description"


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """Admin interface for login attempts."""

    list_display = [
        "timestamp",
        "username",
        "result",
        "user",
        "ip_address",
        "country",
    ]

    list_filter = [
        "result",
        "timestamp",
        "country",
    ]

    search_fields = [
        "username",
        "user__username",
        "ip_address",
    ]

    readonly_fields = [
        "id",
        "user",
        "username",
        "result",
        "ip_address",
        "user_agent",
        "country",
        "city",
        "timestamp",
    ]

    fieldsets = (
        (
            "Login Details",
            {
                "fields": (
                    "id",
                    "timestamp",
                    "username",
                    "user",
                    "result",
                )
            },
        ),
        (
            "Location",
            {
                "fields": (
                    "ip_address",
                    "country",
                    "city",
                )
            },
        ),
        (
            "Request Metadata",
            {
                "fields": ("user_agent",),
                "classes": ("collapse",),
            },
        ),
    )

    ordering = ["-timestamp"]

    def has_add_permission(self, request):
        """Login attempts cannot be manually added."""
        return False

    def has_change_permission(self, request, obj=None):
        """Login attempts cannot be modified."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Login attempts cannot be deleted (except by superusers)."""
        return request.user.is_superuser


@admin.register(DataChangeLog)
class DataChangeLogAdmin(admin.ModelAdmin):
    """Admin interface for data change logs."""

    list_display = [
        "timestamp",
        "change_type",
        "object_repr",
        "user",
        "tenant",
    ]

    list_filter = [
        "change_type",
        "content_type",
        "timestamp",
    ]

    search_fields = [
        "user__username",
        "tenant__company_name",
        "object_repr",
        "object_id",
    ]

    readonly_fields = [
        "id",
        "tenant",
        "user",
        "change_type",
        "content_type",
        "object_id",
        "object_repr",
        "field_changes",
        "ip_address",
        "user_agent",
        "timestamp",
    ]

    fieldsets = (
        (
            "Change Details",
            {
                "fields": (
                    "id",
                    "timestamp",
                    "change_type",
                    "object_repr",
                )
            },
        ),
        (
            "User & Tenant",
            {
                "fields": (
                    "user",
                    "tenant",
                )
            },
        ),
        (
            "Object Details",
            {
                "fields": (
                    "content_type",
                    "object_id",
                )
            },
        ),
        (
            "Field Changes",
            {
                "fields": ("field_changes",),
            },
        ),
        (
            "Request Metadata",
            {
                "fields": (
                    "ip_address",
                    "user_agent",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    ordering = ["-timestamp"]

    def has_add_permission(self, request):
        """Data change logs cannot be manually added."""
        return False

    def has_change_permission(self, request, obj=None):
        """Data change logs cannot be modified."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Data change logs cannot be deleted (except by superusers)."""
        return request.user.is_superuser


@admin.register(APIRequestLog)
class APIRequestLogAdmin(admin.ModelAdmin):
    """Admin interface for API request logs."""

    list_display = [
        "timestamp",
        "method",
        "path_short",
        "status_code",
        "response_time_ms",
        "user",
        "tenant",
    ]

    list_filter = [
        "method",
        "status_code",
        "timestamp",
    ]

    search_fields = [
        "user__username",
        "tenant__company_name",
        "path",
        "ip_address",
    ]

    readonly_fields = [
        "id",
        "tenant",
        "user",
        "method",
        "path",
        "query_params",
        "request_body",
        "status_code",
        "response_time_ms",
        "response_size_bytes",
        "ip_address",
        "user_agent",
        "timestamp",
    ]

    fieldsets = (
        (
            "Request Details",
            {
                "fields": (
                    "id",
                    "timestamp",
                    "method",
                    "path",
                    "status_code",
                    "response_time_ms",
                    "response_size_bytes",
                )
            },
        ),
        (
            "User & Tenant",
            {
                "fields": (
                    "user",
                    "tenant",
                )
            },
        ),
        (
            "Request Data",
            {
                "fields": (
                    "query_params",
                    "request_body",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Request Metadata",
            {
                "fields": (
                    "ip_address",
                    "user_agent",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    ordering = ["-timestamp"]

    def has_add_permission(self, request):
        """API request logs cannot be manually added."""
        return False

    def has_change_permission(self, request, obj=None):
        """API request logs cannot be modified."""
        return False

    def has_delete_permission(self, request, obj=None):
        """API request logs cannot be deleted (except by superusers)."""
        return request.user.is_superuser

    def path_short(self, obj):
        """Return truncated path."""
        if len(obj.path) > 50:
            return obj.path[:50] + "..."
        return obj.path

    path_short.short_description = "Path"
