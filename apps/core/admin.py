"""
Django admin configuration for core models.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from waffle.admin import FlagAdmin as BaseFlagAdmin
from waffle.admin import SampleAdmin as BaseSampleAdmin
from waffle.admin import SwitchAdmin as BaseSwitchAdmin
from waffle.models import Flag, Sample, Switch

from apps.core.announcement_models import (
    Announcement,
    AnnouncementRead,
    CommunicationLog,
    CommunicationTemplate,
    DirectMessage,
)
from apps.core.audit_models import APIRequestLog, AuditLog, DataChangeLog, LoginAttempt
from apps.core.feature_flags import (
    ABTestVariant,
    EmergencyKillSwitch,
    FeatureFlagHistory,
    FeatureFlagMetric,
    TenantFeatureFlag,
)
from apps.core.integration_models import (
    ExternalService,
    IntegrationHealthCheck,
    IntegrationLog,
    OAuth2Token,
)
from apps.core.job_models import JobExecution, JobSchedule, JobStatistics
from apps.core.webhook_models import Webhook, WebhookDelivery

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


# ============================================================================
# Feature Flag Admin Interfaces (django-waffle)
# Per Requirement 30 - Feature Flag Management
# ============================================================================

# Unregister default waffle admin
admin.site.unregister(Flag)
admin.site.unregister(Switch)
admin.site.unregister(Sample)


@admin.register(Flag)
class CustomFlagAdmin(BaseFlagAdmin):
    """
    Enhanced admin interface for Feature Flags.
    Flags are user/group/tenant-specific features that can be enabled selectively.
    """

    list_display = [
        "name",
        "note",
        "everyone",
        "percent",
        "testing",
        "superusers",
        "staff",
        "authenticated",
        "languages",
        "rollout",
        "created",
        "modified",
    ]

    list_filter = [
        "everyone",
        "testing",
        "superusers",
        "staff",
        "authenticated",
        "created",
        "modified",
    ]

    search_fields = [
        "name",
        "note",
    ]

    readonly_fields = [
        "created",
        "modified",
    ]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "name",
                    "note",
                ),
                "description": "Flag name should be descriptive and use snake_case (e.g., 'new_pos_interface')",
            },
        ),
        (
            "Global Rollout",
            {
                "fields": (
                    "everyone",
                    "percent",
                ),
                "description": (
                    "Set 'everyone' to True to enable for all users, False to disable for all, "
                    "or None to use other criteria. 'percent' enables for a percentage of users (0-100)."
                ),
            },
        ),
        (
            "User Type Targeting",
            {
                "fields": (
                    "superusers",
                    "staff",
                    "authenticated",
                ),
                "description": "Enable flag for specific user types",
            },
        ),
        (
            "Selective Targeting",
            {
                "fields": (
                    "users",
                    "groups",
                ),
                "description": "Enable flag for specific users or groups",
            },
        ),
        (
            "Advanced Options",
            {
                "fields": (
                    "testing",
                    "languages",
                    "rollout",
                ),
                "classes": ("collapse",),
                "description": (
                    "'testing' mode always returns False. "
                    "'languages' restricts to specific language codes. "
                    "'rollout' enables gradual rollout."
                ),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created",
                    "modified",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    ordering = ["name"]

    actions = ["enable_for_everyone", "disable_for_everyone", "enable_testing_mode"]

    def enable_for_everyone(self, request, queryset):
        """Enable selected flags for everyone."""
        count = queryset.update(everyone=True)
        self.message_user(request, f"Enabled {count} flag(s) for everyone.")

    enable_for_everyone.short_description = "Enable for everyone"

    def disable_for_everyone(self, request, queryset):
        """Disable selected flags for everyone."""
        count = queryset.update(everyone=False)
        self.message_user(request, f"Disabled {count} flag(s) for everyone.")

    disable_for_everyone.short_description = "Disable for everyone"

    def enable_testing_mode(self, request, queryset):
        """Enable testing mode (always returns False)."""
        count = queryset.update(testing=True)
        self.message_user(request, f"Enabled testing mode for {count} flag(s).")

    enable_testing_mode.short_description = "Enable testing mode"


@admin.register(Switch)
class CustomSwitchAdmin(BaseSwitchAdmin):
    """
    Enhanced admin interface for Feature Switches.
    Switches are simple on/off toggles that apply globally.
    """

    list_display = [
        "name",
        "active",
        "note",
        "created",
        "modified",
    ]

    list_filter = [
        "active",
        "created",
        "modified",
    ]

    search_fields = [
        "name",
        "note",
    ]

    readonly_fields = [
        "created",
        "modified",
    ]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "name",
                    "active",
                    "note",
                ),
                "description": (
                    "Switches are simple on/off toggles. "
                    "Use for features that should be enabled/disabled globally."
                ),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created",
                    "modified",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    ordering = ["name"]

    actions = ["activate_switches", "deactivate_switches"]

    def activate_switches(self, request, queryset):
        """Activate selected switches."""
        count = queryset.update(active=True)
        self.message_user(request, f"Activated {count} switch(es).")

    activate_switches.short_description = "Activate switches"

    def deactivate_switches(self, request, queryset):
        """Deactivate selected switches."""
        count = queryset.update(active=False)
        self.message_user(request, f"Deactivated {count} switch(es).")

    deactivate_switches.short_description = "Deactivate switches"


@admin.register(Sample)
class CustomSampleAdmin(BaseSampleAdmin):
    """
    Enhanced admin interface for Feature Samples.
    Samples enable features for a percentage of users (A/B testing).
    """

    list_display = [
        "name",
        "percent",
        "note",
        "created",
        "modified",
    ]

    list_filter = [
        "created",
        "modified",
    ]

    search_fields = [
        "name",
        "note",
    ]

    readonly_fields = [
        "created",
        "modified",
    ]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "name",
                    "percent",
                    "note",
                ),
                "description": (
                    "Samples enable features for a percentage of users. "
                    "Useful for A/B testing and gradual rollouts. "
                    "Percent should be between 0.0 and 100.0."
                ),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created",
                    "modified",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    ordering = ["name"]

    actions = ["set_to_0_percent", "set_to_50_percent", "set_to_100_percent"]

    def set_to_0_percent(self, request, queryset):
        """Set selected samples to 0% (disabled)."""
        count = queryset.update(percent=0.0)
        self.message_user(request, f"Set {count} sample(s) to 0%.")

    set_to_0_percent.short_description = "Set to 0% (disabled)"

    def set_to_50_percent(self, request, queryset):
        """Set selected samples to 50% (A/B test)."""
        count = queryset.update(percent=50.0)
        self.message_user(request, f"Set {count} sample(s) to 50%.")

    set_to_50_percent.short_description = "Set to 50% (A/B test)"

    def set_to_100_percent(self, request, queryset):
        """Set selected samples to 100% (fully enabled)."""
        count = queryset.update(percent=100.0)
        self.message_user(request, f"Set {count} sample(s) to 100%.")

    set_to_100_percent.short_description = "Set to 100% (fully enabled)"


# ============================================================================
# Feature Flag Extended Models Admin
# Per Requirement 30 - Feature Flag Management
# ============================================================================


@admin.register(TenantFeatureFlag)
class TenantFeatureFlagAdmin(admin.ModelAdmin):
    """
    Admin interface for tenant-specific feature flag overrides.
    Acceptance Criteria 1, 3
    """

    list_display = [
        "tenant",
        "flag",
        "enabled",
        "created_by",
        "created_at",
        "updated_at",
    ]

    list_filter = [
        "enabled",
        "flag",
        "created_at",
    ]

    search_fields = [
        "tenant__company_name",
        "flag__name",
        "notes",
    ]

    readonly_fields = [
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "tenant",
                    "flag",
                    "enabled",
                )
            },
        ),
        (
            "Details",
            {
                "fields": (
                    "notes",
                    "created_by",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    ordering = ["-updated_at"]

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("tenant", "flag", "created_by")


@admin.register(FeatureFlagHistory)
class FeatureFlagHistoryAdmin(admin.ModelAdmin):
    """
    Admin interface for feature flag change history.
    Acceptance Criteria 4
    """

    list_display = [
        "flag_name",
        "flag_type",
        "action",
        "tenant",
        "changed_by",
        "timestamp",
    ]

    list_filter = [
        "flag_type",
        "action",
        "timestamp",
    ]

    search_fields = [
        "flag_name",
        "tenant__company_name",
        "reason",
    ]

    readonly_fields = [
        "flag_name",
        "flag_type",
        "tenant",
        "action",
        "old_value",
        "new_value",
        "changed_by",
        "reason",
        "timestamp",
    ]

    fieldsets = (
        (
            "Change Details",
            {
                "fields": (
                    "flag_name",
                    "flag_type",
                    "action",
                    "tenant",
                    "timestamp",
                )
            },
        ),
        (
            "Values",
            {
                "fields": (
                    "old_value",
                    "new_value",
                )
            },
        ),
        (
            "Audit",
            {
                "fields": (
                    "changed_by",
                    "reason",
                )
            },
        ),
    )

    ordering = ["-timestamp"]

    def has_add_permission(self, request):
        """History records cannot be manually added."""
        return False

    def has_change_permission(self, request, obj=None):
        """History records cannot be modified."""
        return False

    def has_delete_permission(self, request, obj=None):
        """History records cannot be deleted (except by superusers)."""
        return request.user.is_superuser

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("tenant", "changed_by")


@admin.register(ABTestVariant)
class ABTestVariantAdmin(admin.ModelAdmin):
    """
    Admin interface for A/B test variants.
    Acceptance Criteria 6
    """

    list_display = [
        "name",
        "flag",
        "control_group_percentage",
        "variant_group_percentage",
        "is_active",
        "start_date",
        "end_date",
        "created_by",
    ]

    list_filter = [
        "is_active",
        "start_date",
        "end_date",
    ]

    search_fields = [
        "name",
        "flag__name",
        "description",
        "hypothesis",
    ]

    readonly_fields = [
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "name",
                    "flag",
                    "is_active",
                )
            },
        ),
        (
            "Group Distribution",
            {
                "fields": (
                    "control_group_percentage",
                    "variant_group_percentage",
                ),
                "description": "Percentages should add up to 100",
            },
        ),
        (
            "Test Details",
            {
                "fields": (
                    "description",
                    "hypothesis",
                )
            },
        ),
        (
            "Timeline",
            {
                "fields": (
                    "start_date",
                    "end_date",
                )
            },
        ),
        (
            "Audit",
            {
                "fields": (
                    "created_by",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    ordering = ["-start_date"]

    actions = ["stop_tests", "activate_tests"]

    def stop_tests(self, request, queryset):
        """Stop selected A/B tests."""
        count = 0
        for test in queryset.filter(is_active=True):
            test.stop_test()
            count += 1
        self.message_user(request, f"Stopped {count} A/B test(s).")

    stop_tests.short_description = "Stop selected A/B tests"

    def activate_tests(self, request, queryset):
        """Activate selected A/B tests."""
        count = queryset.filter(is_active=False).update(is_active=True)
        self.message_user(request, f"Activated {count} A/B test(s).")

    activate_tests.short_description = "Activate selected A/B tests"

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("flag", "created_by")


@admin.register(FeatureFlagMetric)
class FeatureFlagMetricAdmin(admin.ModelAdmin):
    """
    Admin interface for feature flag metrics.
    Acceptance Criteria 7
    """

    list_display = [
        "flag_name",
        "event_type",
        "variant_group",
        "tenant",
        "user",
        "ab_test",
        "timestamp",
    ]

    list_filter = [
        "event_type",
        "variant_group",
        "timestamp",
    ]

    search_fields = [
        "flag_name",
        "tenant__company_name",
        "user__username",
        "event_type",
    ]

    readonly_fields = [
        "flag_name",
        "ab_test",
        "tenant",
        "user",
        "variant_group",
        "event_type",
        "event_data",
        "timestamp",
    ]

    fieldsets = (
        (
            "Event Details",
            {
                "fields": (
                    "flag_name",
                    "event_type",
                    "timestamp",
                )
            },
        ),
        (
            "A/B Testing",
            {
                "fields": (
                    "ab_test",
                    "variant_group",
                )
            },
        ),
        (
            "User Context",
            {
                "fields": (
                    "tenant",
                    "user",
                )
            },
        ),
        (
            "Event Data",
            {
                "fields": ("event_data",),
                "classes": ("collapse",),
            },
        ),
    )

    ordering = ["-timestamp"]

    def has_add_permission(self, request):
        """Metrics cannot be manually added."""
        return False

    def has_change_permission(self, request, obj=None):
        """Metrics cannot be modified."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Metrics cannot be deleted (except by superusers)."""
        return request.user.is_superuser

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("ab_test", "tenant", "user")


@admin.register(EmergencyKillSwitch)
class EmergencyKillSwitchAdmin(admin.ModelAdmin):
    """
    Admin interface for emergency kill switches.
    Acceptance Criteria 5
    """

    list_display = [
        "flag_name",
        "is_active",
        "disabled_at",
        "disabled_by",
        "re_enabled_at",
        "re_enabled_by",
        "reason_short",
    ]

    list_filter = [
        "is_active",
        "disabled_at",
        "re_enabled_at",
    ]

    search_fields = [
        "flag_name",
        "reason",
    ]

    readonly_fields = [
        "flag_name",
        "disabled_at",
        "disabled_by",
        "re_enabled_at",
        "re_enabled_by",
    ]

    fieldsets = (
        (
            "Kill Switch Details",
            {
                "fields": (
                    "flag_name",
                    "is_active",
                    "reason",
                )
            },
        ),
        (
            "Disabled",
            {
                "fields": (
                    "disabled_at",
                    "disabled_by",
                )
            },
        ),
        (
            "Re-enabled",
            {
                "fields": (
                    "re_enabled_at",
                    "re_enabled_by",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    ordering = ["-disabled_at"]

    def reason_short(self, obj):
        """Return truncated reason."""
        if len(obj.reason) > 100:
            return obj.reason[:100] + "..."
        return obj.reason

    reason_short.short_description = "Reason"

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("disabled_by", "re_enabled_by")


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    """Admin interface for Announcement model."""

    list_display = [
        "title",
        "severity",
        "status",
        "target_all_tenants",
        "scheduled_at",
        "sent_at",
        "created_by",
        "created_at",
    ]

    list_filter = [
        "severity",
        "status",
        "target_all_tenants",
        "requires_acknowledgment",
        "is_dismissible",
        "created_at",
        "scheduled_at",
    ]

    search_fields = [
        "title",
        "message",
        "created_by__username",
    ]

    readonly_fields = [
        "id",
        "sent_at",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "id",
                    "title",
                    "message",
                    "severity",
                )
            },
        ),
        (
            "Targeting",
            {
                "fields": (
                    "target_all_tenants",
                    "target_filter",
                )
            },
        ),
        (
            "Delivery",
            {
                "fields": (
                    "channels",
                    "scheduled_at",
                    "sent_at",
                    "status",
                )
            },
        ),
        (
            "Display Settings",
            {
                "fields": (
                    "requires_acknowledgment",
                    "is_dismissible",
                    "display_until",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_by",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    ordering = ["-created_at"]

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("created_by")

    def save_model(self, request, obj, form, change):
        """Set created_by to current user if creating new announcement."""
        if not change:  # Creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AnnouncementRead)
class AnnouncementReadAdmin(admin.ModelAdmin):
    """Admin interface for AnnouncementRead model."""

    list_display = [
        "announcement",
        "tenant",
        "user",
        "read_at",
        "acknowledged",
        "acknowledged_at",
        "dismissed",
    ]

    list_filter = [
        "acknowledged",
        "dismissed",
        "read_at",
        "acknowledged_at",
    ]

    search_fields = [
        "announcement__title",
        "tenant__company_name",
        "user__username",
    ]

    readonly_fields = [
        "id",
        "read_at",
        "acknowledged_at",
        "dismissed_at",
    ]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "id",
                    "announcement",
                    "tenant",
                    "user",
                )
            },
        ),
        (
            "Read Tracking",
            {"fields": ("read_at",)},
        ),
        (
            "Acknowledgment",
            {
                "fields": (
                    "acknowledged",
                    "acknowledged_at",
                    "acknowledged_by",
                )
            },
        ),
        (
            "Dismissal",
            {
                "fields": (
                    "dismissed",
                    "dismissed_at",
                )
            },
        ),
    )

    ordering = ["-read_at"]

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("announcement", "tenant", "user", "acknowledged_by")


@admin.register(DirectMessage)
class DirectMessageAdmin(admin.ModelAdmin):
    """Admin interface for DirectMessage model."""

    list_display = [
        "subject",
        "tenant",
        "status",
        "sent_at",
        "read_at",
        "created_by",
        "created_at",
    ]

    list_filter = [
        "status",
        "email_sent",
        "sms_sent",
        "in_app_sent",
        "created_at",
        "sent_at",
    ]

    search_fields = [
        "subject",
        "message",
        "tenant__company_name",
        "created_by__username",
    ]

    readonly_fields = [
        "id",
        "sent_at",
        "read_at",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "id",
                    "tenant",
                    "subject",
                    "message",
                )
            },
        ),
        (
            "Delivery",
            {
                "fields": (
                    "channels",
                    "status",
                    "sent_at",
                )
            },
        ),
        (
            "Delivery Status",
            {
                "fields": (
                    "email_sent",
                    "sms_sent",
                    "in_app_sent",
                )
            },
        ),
        (
            "Read Tracking",
            {"fields": ("read_at",)},
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_by",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    ordering = ["-created_at"]

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("tenant", "created_by")

    def save_model(self, request, obj, form, change):
        """Set created_by to current user if creating new message."""
        if not change:  # Creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(CommunicationTemplate)
class CommunicationTemplateAdmin(admin.ModelAdmin):
    """Admin interface for CommunicationTemplate model."""

    list_display = [
        "name",
        "template_type",
        "default_severity",
        "usage_count",
        "is_active",
        "created_at",
    ]

    list_filter = [
        "template_type",
        "default_severity",
        "is_active",
        "created_at",
    ]

    search_fields = [
        "name",
        "subject",
        "message",
    ]

    readonly_fields = [
        "id",
        "usage_count",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "id",
                    "name",
                    "template_type",
                )
            },
        ),
        (
            "Template Content",
            {
                "fields": (
                    "subject",
                    "message",
                )
            },
        ),
        (
            "Default Settings",
            {
                "fields": (
                    "default_severity",
                    "default_channels",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "is_active",
                    "usage_count",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_by",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    ordering = ["name"]

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("created_by")

    def save_model(self, request, obj, form, change):
        """Set created_by to current user if creating new template."""
        if not change:  # Creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(CommunicationLog)
class CommunicationLogAdmin(admin.ModelAdmin):
    """Admin interface for CommunicationLog model."""

    list_display = [
        "communication_type",
        "subject",
        "tenant",
        "sent_at",
        "sent_by",
    ]

    list_filter = [
        "communication_type",
        "sent_at",
    ]

    search_fields = [
        "subject",
        "message_preview",
        "tenant__company_name",
        "sent_by__username",
    ]

    readonly_fields = [
        "id",
        "communication_type",
        "announcement",
        "direct_message",
        "tenant",
        "subject",
        "message_preview",
        "channels_used",
        "delivery_status",
        "sent_at",
        "sent_by",
    ]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "id",
                    "communication_type",
                    "subject",
                    "message_preview",
                )
            },
        ),
        (
            "References",
            {
                "fields": (
                    "announcement",
                    "direct_message",
                    "tenant",
                )
            },
        ),
        (
            "Delivery Details",
            {
                "fields": (
                    "channels_used",
                    "delivery_status",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "sent_at",
                    "sent_by",
                )
            },
        ),
    )

    ordering = ["-sent_at"]

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("announcement", "direct_message", "tenant", "sent_by")

    def has_add_permission(self, request):
        """Disable manual creation of communication logs."""
        return False

    def has_change_permission(self, request, obj=None):
        """Make communication logs read-only."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Disable deletion of communication logs."""
        return False


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    """Admin interface for Webhook model."""

    list_display = [
        "name",
        "tenant",
        "url",
        "is_active",
        "consecutive_failures",
        "last_success_at",
        "last_failure_at",
        "created_at",
    ]

    list_filter = [
        "is_active",
        "created_at",
        "last_success_at",
        "last_failure_at",
    ]

    search_fields = [
        "name",
        "url",
        "description",
        "tenant__company_name",
    ]

    readonly_fields = [
        "id",
        "secret",
        "consecutive_failures",
        "last_success_at",
        "last_failure_at",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "id",
                    "tenant",
                    "name",
                    "description",
                )
            },
        ),
        (
            "Configuration",
            {
                "fields": (
                    "url",
                    "events",
                    "is_active",
                )
            },
        ),
        (
            "Security",
            {
                "fields": ("secret",),
                "classes": ("collapse",),
            },
        ),
        (
            "Status Tracking",
            {
                "fields": (
                    "consecutive_failures",
                    "last_success_at",
                    "last_failure_at",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_by",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    ordering = ["-created_at"]

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("tenant", "created_by")

    def save_model(self, request, obj, form, change):
        """Set created_by to current user if creating new webhook."""
        if not change:  # Creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    """Admin interface for WebhookDelivery model."""

    list_display = [
        "webhook",
        "event_type",
        "status",
        "attempt_count",
        "response_status_code",
        "duration_ms",
        "sent_at",
        "created_at",
    ]

    list_filter = [
        "status",
        "event_type",
        "created_at",
        "sent_at",
        "webhook",
    ]

    search_fields = [
        "webhook__name",
        "event_type",
        "event_id",
        "error_message",
    ]

    readonly_fields = [
        "id",
        "webhook",
        "event_type",
        "event_id",
        "payload",
        "signature",
        "status",
        "attempt_count",
        "max_attempts",
        "next_retry_at",
        "response_status_code",
        "response_body",
        "response_headers",
        "error_message",
        "sent_at",
        "completed_at",
        "duration_ms",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "id",
                    "webhook",
                    "event_type",
                    "event_id",
                )
            },
        ),
        (
            "Payload",
            {
                "fields": (
                    "payload",
                    "signature",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "status",
                    "attempt_count",
                    "max_attempts",
                    "next_retry_at",
                )
            },
        ),
        (
            "Response",
            {
                "fields": (
                    "response_status_code",
                    "response_body",
                    "response_headers",
                    "duration_ms",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Error",
            {
                "fields": ("error_message",),
                "classes": ("collapse",),
            },
        ),
        (
            "Timing",
            {
                "fields": (
                    "sent_at",
                    "completed_at",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    ordering = ["-created_at"]

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("webhook", "webhook__tenant")

    def has_add_permission(self, request):
        """Disable manual creation of webhook deliveries."""
        return False

    def has_change_permission(self, request, obj=None):
        """Make webhook deliveries read-only."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow deletion of old webhook deliveries for cleanup."""
        return True


# External Service Integration Admin


@admin.register(ExternalService)
class ExternalServiceAdmin(admin.ModelAdmin):
    """Admin interface for ExternalService model."""

    list_display = [
        "name",
        "tenant",
        "service_type",
        "provider_name",
        "auth_type",
        "is_active",
        "health_status",
        "created_at",
    ]

    list_filter = [
        "service_type",
        "auth_type",
        "is_active",
        "health_status",
        "is_test_mode",
        "created_at",
    ]

    search_fields = [
        "name",
        "provider_name",
        "description",
        "tenant__company_name",
    ]

    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
        "last_health_check_at",
        "last_used_at",
        "total_requests",
        "failed_requests",
        "consecutive_failures",
    ]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "id",
                    "tenant",
                    "name",
                    "service_type",
                    "provider_name",
                    "description",
                )
            },
        ),
        (
            "Authentication",
            {
                "fields": (
                    "auth_type",
                    "api_key",
                    "api_secret",
                    "base_url",
                    "config",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "is_active",
                    "is_test_mode",
                    "health_status",
                    "last_health_check_at",
                    "consecutive_failures",
                    "last_error_message",
                )
            },
        ),
        (
            "Usage Statistics",
            {
                "fields": (
                    "total_requests",
                    "failed_requests",
                    "last_used_at",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_by",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related("tenant", "created_by")


@admin.register(OAuth2Token)
class OAuth2TokenAdmin(admin.ModelAdmin):
    """Admin interface for OAuth2Token model."""

    list_display = [
        "service",
        "token_type",
        "expires_at",
        "created_at",
        "updated_at",
    ]

    list_filter = [
        "token_type",
        "created_at",
    ]

    search_fields = [
        "service__name",
        "service__tenant__company_name",
    ]

    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Service",
            {"fields": ("id", "service")},
        ),
        (
            "Tokens",
            {
                "fields": (
                    "access_token",
                    "refresh_token",
                    "token_type",
                    "expires_at",
                    "scope",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related("service", "service__tenant")


@admin.register(IntegrationHealthCheck)
class IntegrationHealthCheckAdmin(admin.ModelAdmin):
    """Admin interface for IntegrationHealthCheck model."""

    list_display = [
        "service",
        "status",
        "response_time_ms",
        "status_code",
        "checked_at",
    ]

    list_filter = [
        "status",
        "checked_at",
    ]

    search_fields = [
        "service__name",
        "service__tenant__company_name",
        "error_message",
    ]

    readonly_fields = [
        "id",
        "service",
        "status",
        "response_time_ms",
        "status_code",
        "error_message",
        "checked_at",
    ]

    fieldsets = (
        (
            "Health Check",
            {
                "fields": (
                    "id",
                    "service",
                    "status",
                    "response_time_ms",
                    "status_code",
                    "error_message",
                    "checked_at",
                )
            },
        ),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related("service", "service__tenant")

    def has_add_permission(self, request):
        """Disable manual creation of health checks."""
        return False

    def has_change_permission(self, request, obj=None):
        """Disable editing of health checks."""
        return False


@admin.register(IntegrationLog)
class IntegrationLogAdmin(admin.ModelAdmin):
    """Admin interface for IntegrationLog model."""

    list_display = [
        "service",
        "method",
        "endpoint",
        "response_status_code",
        "success",
        "response_time_ms",
        "created_at",
    ]

    list_filter = [
        "method",
        "success",
        "created_at",
    ]

    search_fields = [
        "service__name",
        "service__tenant__company_name",
        "endpoint",
        "error_message",
    ]

    readonly_fields = [
        "id",
        "service",
        "method",
        "endpoint",
        "request_headers",
        "request_body",
        "response_status_code",
        "response_body",
        "response_time_ms",
        "success",
        "error_message",
        "created_at",
    ]

    fieldsets = (
        (
            "Request",
            {
                "fields": (
                    "id",
                    "service",
                    "method",
                    "endpoint",
                    "request_headers",
                    "request_body",
                )
            },
        ),
        (
            "Response",
            {
                "fields": (
                    "response_status_code",
                    "response_body",
                    "response_time_ms",
                    "success",
                    "error_message",
                )
            },
        ),
        (
            "Metadata",
            {"fields": ("created_at",)},
        ),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related("service", "service__tenant")

    def has_add_permission(self, request):
        """Disable manual creation of logs."""
        return False

    def has_change_permission(self, request, obj=None):
        """Disable editing of logs."""
        return False


@admin.register(JobExecution)
class JobExecutionAdmin(admin.ModelAdmin):
    """Admin interface for JobExecution model."""

    list_display = (
        "task_id",
        "task_name",
        "status",
        "queue",
        "priority",
        "execution_time",
        "queued_at",
        "completed_at",
    )
    list_filter = ("status", "queue", "queued_at", "completed_at")
    search_fields = ("task_id", "task_name", "error")
    readonly_fields = (
        "task_id",
        "task_name",
        "status",
        "args",
        "kwargs",
        "queued_at",
        "started_at",
        "completed_at",
        "execution_time",
        "queue",
        "priority",
        "result",
        "error",
        "traceback",
        "retry_count",
        "max_retries",
        "worker_name",
    )
    ordering = ("-queued_at",)

    def has_add_permission(self, request):
        """Disable manual creation of job executions."""
        return False

    def has_change_permission(self, request, obj=None):
        """Disable editing of job executions."""
        return False


@admin.register(JobStatistics)
class JobStatisticsAdmin(admin.ModelAdmin):
    """Admin interface for JobStatistics model."""

    list_display = (
        "task_name",
        "total_executions",
        "successful_executions",
        "failed_executions",
        "avg_execution_time",
        "last_execution_at",
    )
    search_fields = ("task_name",)
    readonly_fields = (
        "task_name",
        "total_executions",
        "successful_executions",
        "failed_executions",
        "avg_execution_time",
        "min_execution_time",
        "max_execution_time",
        "avg_cpu_percent",
        "avg_memory_mb",
        "last_execution_at",
        "last_execution_status",
        "updated_at",
    )
    ordering = ("-total_executions",)

    def has_add_permission(self, request):
        """Disable manual creation of statistics."""
        return False

    def has_change_permission(self, request, obj=None):
        """Disable editing of statistics."""
        return False


@admin.register(JobSchedule)
class JobScheduleAdmin(admin.ModelAdmin):
    """Admin interface for JobSchedule model."""

    list_display = (
        "name",
        "task_name",
        "schedule_type",
        "schedule_display",
        "queue",
        "priority",
        "enabled",
        "last_run_at",
        "created_at",
    )
    list_filter = ("schedule_type", "enabled", "queue")
    search_fields = ("name", "task_name")
    readonly_fields = ("created_at", "updated_at", "last_run_at")
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "name",
                    "task_name",
                    "enabled",
                )
            },
        ),
        (
            "Schedule Configuration",
            {
                "fields": (
                    "schedule_type",
                    "cron_expression",
                    "interval_value",
                    "interval_unit",
                )
            },
        ),
        (
            "Task Configuration",
            {
                "fields": (
                    "args",
                    "kwargs",
                    "queue",
                    "priority",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_by",
                    "created_at",
                    "updated_at",
                    "last_run_at",
                )
            },
        ),
    )
    ordering = ("-enabled", "name")
