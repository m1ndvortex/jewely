"""
Django admin configuration for pricing models.
"""

from django.contrib import admin

from .models import GoldRate, PriceAlert, PricingRule


@admin.register(GoldRate)
class GoldRateAdmin(admin.ModelAdmin):
    """Admin interface for GoldRate model."""

    list_display = [
        "timestamp",
        "market",
        "currency",
        "rate_per_gram",
        "rate_per_tola",
        "rate_per_ounce",
        "is_active",
        "source",
    ]

    list_filter = [
        "market",
        "currency",
        "is_active",
        "timestamp",
    ]

    search_fields = [
        "market",
        "currency",
        "source",
    ]

    ordering = ["-timestamp"]

    readonly_fields = [
        "timestamp",
        "fetched_at",
    ]

    fieldsets = (
        (
            "Rate Information",
            {
                "fields": (
                    "rate_per_gram",
                    "rate_per_tola",
                    "rate_per_ounce",
                )
            },
        ),
        (
            "Market Information",
            {
                "fields": (
                    "market",
                    "currency",
                    "source",
                )
            },
        ),
        ("Status", {"fields": ("is_active",)}),
        (
            "Timestamps",
            {
                "fields": (
                    "timestamp",
                    "fetched_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        """Optimize queryset for admin list view."""
        return super().get_queryset(request).select_related()


@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    """Admin interface for PricingRule model."""

    list_display = [
        "name",
        "tenant",
        "karat",
        "product_type",
        "craftsmanship_level",
        "customer_tier",
        "markup_percentage",
        "making_charge_per_gram",
        "is_active",
        "priority",
    ]

    list_filter = [
        "tenant",
        "karat",
        "product_type",
        "craftsmanship_level",
        "customer_tier",
        "is_active",
    ]

    search_fields = [
        "name",
        "description",
        "tenant__company_name",
    ]

    ordering = ["-priority", "tenant", "karat", "customer_tier"]

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
                    "name",
                    "description",
                    "is_active",
                    "priority",
                )
            },
        ),
        (
            "Rule Criteria",
            {
                "fields": (
                    "karat",
                    "product_type",
                    "craftsmanship_level",
                    "customer_tier",
                )
            },
        ),
        (
            "Pricing Configuration",
            {
                "fields": (
                    "markup_percentage",
                    "fixed_markup_amount",
                    "minimum_price",
                )
            },
        ),
        (
            "Additional Charges",
            {
                "fields": (
                    "making_charge_per_gram",
                    "stone_charge_percentage",
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

    def get_queryset(self, request):
        """Optimize queryset for admin list view."""
        return super().get_queryset(request).select_related("tenant")


@admin.register(PriceAlert)
class PriceAlertAdmin(admin.ModelAdmin):
    """Admin interface for PriceAlert model."""

    list_display = [
        "name",
        "tenant",
        "alert_type",
        "market",
        "get_condition_display",
        "is_active",
        "trigger_count",
        "last_triggered_at",
    ]

    list_filter = [
        "tenant",
        "alert_type",
        "market",
        "is_active",
        "notify_email",
        "notify_sms",
        "notify_in_app",
    ]

    search_fields = [
        "name",
        "tenant__company_name",
    ]

    ordering = ["-created_at"]

    readonly_fields = [
        "last_triggered_at",
        "trigger_count",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "tenant",
                    "name",
                    "is_active",
                )
            },
        ),
        (
            "Alert Condition",
            {
                "fields": (
                    "alert_type",
                    "market",
                    "threshold_rate",
                    "percentage_threshold",
                )
            },
        ),
        (
            "Notification Settings",
            {
                "fields": (
                    "notify_email",
                    "notify_sms",
                    "notify_in_app",
                )
            },
        ),
        (
            "Statistics",
            {
                "fields": (
                    "trigger_count",
                    "last_triggered_at",
                ),
                "classes": ("collapse",),
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

    def get_condition_display(self, obj):
        """Display the alert condition in a readable format."""
        return obj.get_condition_description()

    get_condition_display.short_description = "Condition"

    def get_queryset(self, request):
        """Optimize queryset for admin list view."""
        return super().get_queryset(request).select_related("tenant")
