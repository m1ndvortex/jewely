from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Customer, CustomerCommunication, GiftCard, LoyaltyTier, LoyaltyTransaction


@admin.register(LoyaltyTier)
class LoyaltyTierAdmin(admin.ModelAdmin):
    """Admin interface for LoyaltyTier model."""

    list_display = [
        "name",
        "tenant",
        "min_spending",
        "discount_percentage",
        "points_multiplier",
        "validity_months",
        "order",
        "is_active",
        "customer_count",
    ]

    list_filter = [
        "is_active",
        "tenant",
        "validity_months",
    ]

    search_fields = [
        "name",
        "tenant__company_name",
    ]

    ordering = ["tenant", "order", "min_spending"]

    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (None, {"fields": ("tenant", "name", "order", "is_active")}),
        ("Requirements", {"fields": ("min_spending",)}),
        (
            "Benefits",
            {
                "fields": (
                    "discount_percentage",
                    "points_multiplier",
                    "validity_months",
                    "benefits_description",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def customer_count(self, obj):
        """Display number of customers in this tier."""
        count = obj.customers.count()
        if count > 0:
            url = reverse("admin:crm_customer_changelist") + f"?loyalty_tier__id__exact={obj.id}"
            return format_html('<a href="{}">{} customers</a>', url, count)
        return "0 customers"

    customer_count.short_description = "Customers"


class LoyaltyTransactionInline(admin.TabularInline):
    """Inline for loyalty transactions."""

    model = LoyaltyTransaction
    extra = 0
    readonly_fields = ["created_at", "created_by"]
    fields = ["transaction_type", "points", "description", "expires_at", "created_at"]

    def has_add_permission(self, request, obj=None):
        return False  # Prevent adding transactions through inline


class CustomerCommunicationInline(admin.TabularInline):
    """Inline for customer communications."""

    model = CustomerCommunication
    extra = 0
    readonly_fields = ["created_at", "created_by"]
    fields = ["communication_type", "direction", "subject", "communication_date", "created_by"]

    def has_change_permission(self, request, obj=None):
        return False  # Make communications read-only in inline


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """Admin interface for Customer model."""

    list_display = [
        "customer_number",
        "get_full_name",
        "tenant",
        "phone",
        "email",
        "loyalty_tier",
        "loyalty_points",
        "store_credit",
        "total_purchases",
        "is_active",
        "last_purchase_at",
    ]

    list_filter = [
        "is_active",
        "loyalty_tier",
        "tenant",
        "marketing_opt_in",
        "sms_opt_in",
        "gender",
        "preferred_communication",
    ]

    search_fields = [
        "customer_number",
        "first_name",
        "last_name",
        "email",
        "phone",
        "tenant__company_name",
    ]

    ordering = ["-created_at"]

    readonly_fields = [
        "created_at",
        "updated_at",
        "last_purchase_at",
        "tier_achieved_at",
        "tier_expires_at",
        "referral_code",
        "total_points_earned",
        "total_points_redeemed",
    ]

    fieldsets = (
        (None, {"fields": ("tenant", "customer_number", "is_active")}),
        (
            "Personal Information",
            {"fields": ("first_name", "last_name", "date_of_birth", "gender")},
        ),
        ("Contact Information", {"fields": ("email", "phone", "alternate_phone")}),
        (
            "Address",
            {
                "fields": (
                    "address_line_1",
                    "address_line_2",
                    "city",
                    "state",
                    "postal_code",
                    "country",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Loyalty Program",
            {
                "fields": (
                    "loyalty_tier",
                    "loyalty_points",
                    "tier_achieved_at",
                    "tier_expires_at",
                    "total_points_earned",
                    "total_points_redeemed",
                )
            },
        ),
        ("Financial", {"fields": ("store_credit", "total_purchases", "last_purchase_at")}),
        ("Preferences", {"fields": ("preferred_communication", "marketing_opt_in", "sms_opt_in")}),
        (
            "Referral Program",
            {
                "fields": ("referral_code", "referred_by", "referral_reward_given"),
                "classes": ("collapse",),
            },
        ),
        ("Notes & Tags", {"fields": ("notes", "tags"), "classes": ("collapse",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    inlines = [LoyaltyTransactionInline, CustomerCommunicationInline]

    def get_full_name(self, obj):
        """Display customer's full name."""
        return obj.get_full_name()

    get_full_name.short_description = "Name"
    get_full_name.admin_order_field = "first_name"


@admin.register(LoyaltyTransaction)
class LoyaltyTransactionAdmin(admin.ModelAdmin):
    """Admin interface for LoyaltyTransaction model."""

    list_display = [
        "customer",
        "transaction_type",
        "points",
        "description",
        "created_at",
        "expires_at",
        "created_by",
    ]

    list_filter = [
        "transaction_type",
        "created_at",
        "expires_at",
        "customer__tenant",
    ]

    search_fields = [
        "customer__first_name",
        "customer__last_name",
        "customer__customer_number",
        "description",
    ]

    ordering = ["-created_at"]

    readonly_fields = ["created_at"]

    fieldsets = (
        (None, {"fields": ("customer", "transaction_type", "points", "description")}),
        ("Related Objects", {"fields": ("sale",), "classes": ("collapse",)}),
        ("Expiration", {"fields": ("expires_at",)}),
        ("Metadata", {"fields": ("metadata",), "classes": ("collapse",)}),
        ("Audit", {"fields": ("created_at", "created_by")}),
    )


@admin.register(GiftCard)
class GiftCardAdmin(admin.ModelAdmin):
    """Admin interface for GiftCard model."""

    list_display = [
        "card_number",
        "tenant",
        "initial_value",
        "current_balance",
        "status",
        "purchased_by",
        "recipient",
        "expires_at",
        "created_at",
    ]

    list_filter = [
        "status",
        "tenant",
        "expires_at",
        "created_at",
    ]

    search_fields = [
        "card_number",
        "purchased_by__first_name",
        "purchased_by__last_name",
        "recipient__first_name",
        "recipient__last_name",
        "tenant__company_name",
    ]

    ordering = ["-created_at"]

    readonly_fields = ["created_at", "updated_at", "card_number"]

    fieldsets = (
        (None, {"fields": ("tenant", "card_number", "status")}),
        ("Financial", {"fields": ("initial_value", "current_balance")}),
        ("Customers", {"fields": ("purchased_by", "recipient")}),
        ("Expiration", {"fields": ("expires_at",)}),
        ("Messages & Notes", {"fields": ("message", "notes"), "classes": ("collapse",)}),
        ("Audit", {"fields": ("created_at", "updated_at", "issued_by")}),
    )

    def get_readonly_fields(self, request, obj=None):
        """Make card_number readonly after creation."""
        readonly = list(self.readonly_fields)
        if obj:  # Editing existing object
            readonly.append("initial_value")
        return readonly


@admin.register(CustomerCommunication)
class CustomerCommunicationAdmin(admin.ModelAdmin):
    """Admin interface for CustomerCommunication model."""

    list_display = [
        "customer",
        "communication_type",
        "direction",
        "subject",
        "communication_date",
        "duration_minutes",
        "created_by",
    ]

    list_filter = [
        "communication_type",
        "direction",
        "communication_date",
        "customer__tenant",
    ]

    search_fields = [
        "customer__first_name",
        "customer__last_name",
        "customer__customer_number",
        "subject",
        "content",
    ]

    ordering = ["-communication_date"]

    readonly_fields = ["created_at"]

    fieldsets = (
        (None, {"fields": ("customer", "communication_type", "direction")}),
        ("Content", {"fields": ("subject", "content")}),
        ("Details", {"fields": ("communication_date", "duration_minutes")}),
        ("Audit", {"fields": ("created_at", "created_by")}),
    )
