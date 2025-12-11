"""
Subscription Plan Forms

This module provides Django forms for subscription plan management with
comprehensive validation, multi-currency support, and JSON field handling.

Author: Enterprise Subscription System
Version: 1.0.0
"""

import json
from decimal import Decimal

from django import forms
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _

from apps.core.models import SubscriptionPlan, TenantSubscription


class JSONFieldWidget(forms.Textarea):
    """Custom widget for JSON fields with validation and formatting."""

    def __init__(self, attrs=None):
        default_attrs = {
            "class": "font-mono text-sm",
            "rows": 4,
            "placeholder": '{"key": "value"}',
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)

    def format_value(self, value):
        """Format JSON for display."""
        if value is None:
            return "{}"
        if isinstance(value, dict):
            return json.dumps(value, indent=2, ensure_ascii=False)
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return json.dumps(parsed, indent=2, ensure_ascii=False)
            except json.JSONDecodeError:
                return value
        return str(value)


class SubscriptionPlanForm(forms.ModelForm):
    """
    Comprehensive form for creating and editing subscription plans.

    Features:
    - Multi-currency pricing (USD and IRR/Toman)
    - Extensive resource limits
    - Feature flags
    - Custom JSON configuration
    - Proper validation and error messages
    """

    # Boolean fields need explicit definition to handle unchecked state properly
    is_free = forms.BooleanField(
        label=_("Free Plan"),
        required=False,
        initial=False,
        help_text=_("Mark as free plan (no payment required)"),
    )

    enable_multi_branch = forms.BooleanField(
        label=_("Multi-Branch Management"),
        required=False,
        initial=False,
        help_text=_("Allow managing multiple shop locations"),
    )

    enable_advanced_reporting = forms.BooleanField(
        label=_("Advanced Reporting"),
        required=False,
        initial=False,
        help_text=_("Enable custom analytics and reports"),
    )

    enable_api_access = forms.BooleanField(
        label=_("API Access"),
        required=False,
        initial=False,
        help_text=_("Enable REST API for integrations"),
    )

    enable_custom_branding = forms.BooleanField(
        label=_("Custom Branding"),
        required=False,
        initial=False,
        help_text=_("Enable white-label with custom logos"),
    )

    enable_priority_support = forms.BooleanField(
        label=_("Priority Support"),
        required=False,
        initial=False,
        help_text=_("Enable faster response times"),
    )

    enable_export_import = forms.BooleanField(
        label=_("Data Export/Import"),
        required=False,
        initial=False,
        help_text=_("Enable data export and import functionality"),
    )

    enable_email_notifications = forms.BooleanField(
        label=_("Email Notifications"),
        required=False,
        initial=True,
        help_text=_("Enable email alerts and reminders"),
    )

    enable_sms_notifications = forms.BooleanField(
        label=_("SMS Notifications"),
        required=False,
        initial=False,
        help_text=_("Enable SMS alerts to customers"),
    )

    # Override price fields with better widgets
    price = forms.DecimalField(
        label=_("Price (USD)"),
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.00"),
        widget=forms.NumberInput(
            attrs={
                "class": "pl-8",
                "step": "0.01",
                "min": "0",
                "placeholder": "29.99",
            }
        ),
        help_text=_("Monthly price in US Dollars"),
    )

    price_irr = forms.IntegerField(
        label=_("Price (Toman)"),
        min_value=0,
        required=False,
        widget=forms.NumberInput(
            attrs={
                "min": "0",
                "placeholder": "500000",
            }
        ),
        help_text=_("Monthly price in Iranian Toman (0 to hide)"),
    )

    # Resource limits with -1 = unlimited support
    user_limit = forms.IntegerField(
        label=_("User Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum team members (-1 for unlimited)"),
    )

    branch_limit = forms.IntegerField(
        label=_("Branch Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum shop locations (-1 for unlimited)"),
    )

    inventory_limit = forms.IntegerField(
        label=_("Inventory Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum inventory items (-1 for unlimited)"),
    )

    contacts_limit = forms.IntegerField(
        label=_("Contacts Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum contacts/customers (-1 for unlimited)"),
    )

    products_limit = forms.IntegerField(
        label=_("Products Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum products (-1 for unlimited)"),
    )

    invoices_limit = forms.IntegerField(
        label=_("Monthly Invoices Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum invoices per month (-1 for unlimited)"),
    )

    transactions_limit = forms.IntegerField(
        label=_("Monthly Transactions Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum transactions per month (-1 for unlimited)"),
    )

    storage_limit_gb = forms.IntegerField(
        label=_("Storage (GB)"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Storage space in GB (-1 for unlimited)"),
    )

    api_calls_per_month = forms.IntegerField(
        label=_("API Calls per Month"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Monthly API call limit (-1 for unlimited)"),
    )

    # ===== Sales & POS Limits =====
    pos_terminals_limit = forms.IntegerField(
        label=_("POS Terminals Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum POS terminals (-1 for unlimited)"),
    )

    sales_per_month_limit = forms.IntegerField(
        label=_("Monthly Sales Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum sales per month (-1 for unlimited)"),
    )

    gift_cards_limit = forms.IntegerField(
        label=_("Gift Cards Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum active gift cards (-1 for unlimited)"),
    )

    # ===== Business Operations Limits =====
    suppliers_limit = forms.IntegerField(
        label=_("Suppliers Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum suppliers (-1 for unlimited)"),
    )

    categories_limit = forms.IntegerField(
        label=_("Categories Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum product categories (-1 for unlimited)"),
    )

    custom_orders_limit = forms.IntegerField(
        label=_("Monthly Custom Orders Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum custom/goldsmith orders per month (-1 for unlimited)"),
    )

    repair_orders_limit = forms.IntegerField(
        label=_("Monthly Repair Orders Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum repair orders per month (-1 for unlimited)"),
    )

    purchase_orders_limit = forms.IntegerField(
        label=_("Monthly Purchase Orders Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum purchase orders per month (-1 for unlimited)"),
    )

    # ===== Marketing & Communication Limits =====
    email_campaigns_limit = forms.IntegerField(
        label=_("Monthly Email Campaigns Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum email campaigns per month (-1 for unlimited)"),
    )

    sms_campaigns_limit = forms.IntegerField(
        label=_("Monthly SMS Campaigns Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum SMS campaigns per month (-1 for unlimited)"),
    )

    emails_per_month_limit = forms.IntegerField(
        label=_("Monthly Emails Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum emails per month (-1 for unlimited)"),
    )

    sms_per_month_limit = forms.IntegerField(
        label=_("Monthly SMS Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum SMS per month (-1 for unlimited)"),
    )

    # ===== Advanced Features Limits =====
    reports_per_month_limit = forms.IntegerField(
        label=_("Monthly Reports Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum reports per month (-1 for unlimited)"),
    )

    pricing_rules_limit = forms.IntegerField(
        label=_("Pricing Rules Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum pricing rules (-1 for unlimited)"),
    )

    journal_entries_limit = forms.IntegerField(
        label=_("Monthly Journal Entries Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum journal entries per month (-1 for unlimited)"),
    )

    loyalty_tiers_limit = forms.IntegerField(
        label=_("Loyalty Tiers Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum loyalty tiers (-1 for unlimited)"),
    )

    # ===== System Limits =====
    backup_retention_days = forms.IntegerField(
        label=_("Backup Retention Days"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Days to retain backups (-1 for unlimited)"),
    )

    concurrent_sessions_limit = forms.IntegerField(
        label=_("Concurrent Sessions Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum concurrent sessions (-1 for unlimited)"),
    )

    documents_limit = forms.IntegerField(
        label=_("Documents Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum document attachments (-1 for unlimited)"),
    )

    webhooks_limit = forms.IntegerField(
        label=_("Webhooks Limit"),
        validators=[MinValueValidator(-1)],
        widget=forms.NumberInput(attrs={"min": "-1"}),
        help_text=_("Maximum webhooks (-1 for unlimited)"),
    )

    trial_days = forms.IntegerField(
        label=_("Trial Days"),
        min_value=0,
        initial=14,
        required=False,
        widget=forms.NumberInput(attrs={"min": "0"}),
        help_text=_("Number of days for free trial"),
    )

    # JSON fields with custom widget
    custom_limits = forms.CharField(
        label=_("Custom Limits (JSON)"),
        required=False,
        widget=JSONFieldWidget(
            attrs={
                "placeholder": '{"reports_per_day": 10, "backup_retention_days": 30}',
            }
        ),
        help_text=_("Additional limits in JSON format"),
    )

    custom_features = forms.CharField(
        label=_("Custom Features (JSON)"),
        required=False,
        widget=JSONFieldWidget(
            attrs={
                "placeholder": '{"beta_features": true, "advanced_analytics": false}',
            }
        ),
        help_text=_("Additional features in JSON format"),
    )

    class Meta:
        model = SubscriptionPlan
        fields = [
            # Basic Info
            "name",
            "description",
            "is_free",
            "display_order",
            "trial_days",
            # Pricing
            "price",
            "price_irr",
            "billing_cycle",
            # Core Resource Limits
            "user_limit",
            "branch_limit",
            "inventory_limit",
            "contacts_limit",
            "products_limit",
            "suppliers_limit",
            "categories_limit",
            # Sales & POS Limits
            "pos_terminals_limit",
            "sales_per_month_limit",
            "gift_cards_limit",
            # Monthly Operation Limits
            "invoices_limit",
            "transactions_limit",
            "custom_orders_limit",
            "repair_orders_limit",
            "purchase_orders_limit",
            # Marketing & Communication Limits
            "email_campaigns_limit",
            "sms_campaigns_limit",
            "emails_per_month_limit",
            "sms_per_month_limit",
            # Advanced Feature Limits
            "api_calls_per_month",
            "reports_per_month_limit",
            "pricing_rules_limit",
            "journal_entries_limit",
            "loyalty_tiers_limit",
            # System Limits
            "storage_limit_gb",
            "backup_retention_days",
            "concurrent_sessions_limit",
            "documents_limit",
            "webhooks_limit",
            # Feature Flags
            "enable_multi_branch",
            "enable_advanced_reporting",
            "enable_api_access",
            "enable_custom_branding",
            "enable_priority_support",
            "enable_export_import",
            "enable_email_notifications",
            "enable_sms_notifications",
            # Custom
            "custom_limits",
            "custom_features",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": _("e.g., Starter, Professional, Enterprise"),
                    "class": "w-full",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": _("Describe the plan features and target audience..."),
                }
            ),
            "billing_cycle": forms.Select(
                attrs={"class": "w-full"},
            ),
            "display_order": forms.NumberInput(
                attrs={"min": "0"},
            ),
        }
        labels = {
            "name": _("Plan Name"),
            "description": _("Description"),
            "is_free": _("Free Plan"),
            "display_order": _("Display Order"),
            "billing_cycle": _("Billing Cycle"),
            "enable_multi_branch": _("Multi-Branch Management"),
            "enable_advanced_reporting": _("Advanced Reporting"),
            "enable_api_access": _("API Access"),
            "enable_custom_branding": _("Custom Branding"),
            "enable_priority_support": _("Priority Support"),
            "enable_export_import": _("Data Export/Import"),
            "enable_email_notifications": _("Email Notifications"),
            "enable_sms_notifications": _("SMS Notifications"),
        }
        help_texts = {
            "is_free": _("Mark as free plan (no payment required)"),
            "display_order": _("Lower numbers appear first in plan listings"),
        }

    def clean_custom_limits(self):
        """Validate and parse custom_limits JSON."""
        value = self.cleaned_data.get("custom_limits", "")
        if not value or value.strip() == "":
            return {}

        try:
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise forms.ValidationError(_("Custom limits must be a JSON object (dictionary)."))
            return parsed
        except json.JSONDecodeError as e:
            raise forms.ValidationError(_("Invalid JSON format: %(error)s") % {"error": str(e)})

    def clean_custom_features(self):
        """Validate and parse custom_features JSON."""
        value = self.cleaned_data.get("custom_features", "")
        if not value or value.strip() == "":
            return {}

        try:
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise forms.ValidationError(
                    _("Custom features must be a JSON object (dictionary).")
                )
            return parsed
        except json.JSONDecodeError as e:
            raise forms.ValidationError(_("Invalid JSON format: %(error)s") % {"error": str(e)})

    def clean_price_irr(self):
        """Ensure price_irr defaults to 0 if not provided."""
        value = self.cleaned_data.get("price_irr")
        if value is None:
            return 0
        return value

    def clean(self):
        """Cross-field validation."""
        cleaned_data = super().clean()
        is_free = cleaned_data.get("is_free", False)
        price = cleaned_data.get("price", Decimal("0"))

        # Free plans should have price = 0
        if is_free and price > 0:
            self.add_error(
                "price",
                _("Free plans should have a price of 0."),
            )

        # Ensure at least basic limits are set
        if cleaned_data.get("user_limit") == 0:
            self.add_error(
                "user_limit",
                _("User limit cannot be 0. Use -1 for unlimited."),
            )

        return cleaned_data


class TenantSubscriptionForm(forms.ModelForm):
    """
    Form for managing tenant subscriptions with override capabilities.

    Allows administrators to customize subscription parameters for
    specific tenants beyond the base plan limits.
    """

    class Meta:
        model = TenantSubscription
        fields = [
            "plan",
            "status",
            "current_period_start",
            "current_period_end",
            "next_billing_date",
            "trial_start",
            "trial_end",
            # Override fields
            "user_limit_override",
            "branch_limit_override",
            "inventory_limit_override",
            "storage_limit_gb_override",
            "api_calls_per_month_override",
            "contacts_limit_override",
            "invoices_limit_override",
            "products_limit_override",
            "transactions_limit_override",
            # JSON overrides
            "custom_limits_override",
            "custom_features_override",
        ]
        widgets = {
            "current_period_start": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
            ),
            "current_period_end": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
            ),
            "next_billing_date": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
            ),
            "trial_start": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
            ),
            "trial_end": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
            ),
        }
        labels = {
            "user_limit_override": _("User Limit Override"),
            "branch_limit_override": _("Branch Limit Override"),
            "inventory_limit_override": _("Inventory Limit Override"),
            "storage_limit_gb_override": _("Storage (GB) Override"),
            "api_calls_per_month_override": _("API Calls Override"),
            "contacts_limit_override": _("Contacts Limit Override"),
            "invoices_limit_override": _("Invoices Limit Override"),
            "products_limit_override": _("Products Limit Override"),
            "transactions_limit_override": _("Transactions Limit Override"),
        }
        help_texts = {
            "user_limit_override": _("Leave blank to use plan default"),
            "branch_limit_override": _("Leave blank to use plan default"),
            "inventory_limit_override": _("Leave blank to use plan default"),
            "storage_limit_gb_override": _("Leave blank to use plan default"),
            "api_calls_per_month_override": _("Leave blank to use plan default"),
            "contacts_limit_override": _("Leave blank to use plan default"),
            "invoices_limit_override": _("Leave blank to use plan default"),
            "products_limit_override": _("Leave blank to use plan default"),
            "transactions_limit_override": _("Leave blank to use plan default"),
        }

    def clean_custom_limits_override(self):
        """Validate and parse custom_limits_override JSON."""
        value = self.cleaned_data.get("custom_limits_override", "")
        if not value or value == "" or value == "{}":
            return {}

        if isinstance(value, dict):
            return value

        try:
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise forms.ValidationError(_("Custom limits must be a JSON object."))
            return parsed
        except json.JSONDecodeError as e:
            raise forms.ValidationError(_("Invalid JSON format: %(error)s") % {"error": str(e)})

    def clean_custom_features_override(self):
        """Validate and parse custom_features_override JSON."""
        value = self.cleaned_data.get("custom_features_override", "")
        if not value or value == "" or value == "{}":
            return {}

        if isinstance(value, dict):
            return value

        try:
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise forms.ValidationError(_("Custom features must be a JSON object."))
            return parsed
        except json.JSONDecodeError as e:
            raise forms.ValidationError(_("Invalid JSON format: %(error)s") % {"error": str(e)})


class SubscriptionUpgradeForm(forms.Form):
    """
    Form for tenant subscription upgrades/downgrades.

    Used by both platform admins and tenants themselves
    (when self-service is enabled).
    """

    plan = forms.ModelChoiceField(
        queryset=SubscriptionPlan.objects.filter(status="active").order_by("display_order"),
        label=_("New Plan"),
        widget=forms.Select(attrs={"class": "w-full"}),
    )

    apply_immediately = forms.BooleanField(
        required=False,
        initial=True,
        label=_("Apply Immediately"),
        help_text=_("If checked, changes apply now. Otherwise, at next billing cycle."),
    )

    prorate = forms.BooleanField(
        required=False,
        initial=True,
        label=_("Prorate Charges"),
        help_text=_("Calculate prorated charges/credits for plan change."),
    )

    notes = forms.CharField(
        required=False,
        label=_("Internal Notes"),
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text=_("Optional notes about this plan change (admin only)."),
    )
