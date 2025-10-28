"""
Forms for core app settings and configuration.
"""

from django import forms

from waffle.models import Flag

from .feature_flags import ABTestVariant, TenantFeatureFlag
from .models import IntegrationSettings, InvoiceSettings, Tenant, TenantSettings


class TenantSettingsForm(forms.ModelForm):
    """
    Form for editing tenant settings.
    """

    class Meta:
        model = TenantSettings
        fields = [
            "business_name",
            "business_registration_number",
            "tax_identification_number",
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
            "timezone",
            "currency",
            "date_format",
            "default_tax_rate",
            "tax_inclusive_pricing",
        ]

        widgets = {
            "business_name": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "Enter your business name",
                }
            ),
            "business_registration_number": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "Business registration number",
                }
            ),
            "tax_identification_number": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "Tax identification number",
                }
            ),
            "address_line_1": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "Street address",
                }
            ),
            "address_line_2": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "Apartment, suite, etc.",
                }
            ),
            "city": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "City",
                }
            ),
            "state_province": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "State or Province",
                }
            ),
            "postal_code": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "Postal code",
                }
            ),
            "country": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "Country",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "+1 (555) 123-4567",
                    "type": "tel",
                }
            ),
            "fax": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "+1 (555) 123-4568",
                    "type": "tel",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "contact@yourshop.com",
                }
            ),
            "website": forms.URLInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "https://www.yourshop.com",
                }
            ),
            "timezone": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "America/New_York",
                }
            ),
            "currency": forms.Select(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                }
            ),
            "date_format": forms.Select(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                }
            ),
            "default_tax_rate": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "8.25",
                    "step": "0.01",
                    "min": "0",
                    "max": "100",
                }
            ),
            "tax_inclusive_pricing": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-600 rounded dark:bg-gray-700",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make some fields optional
        self.fields["business_registration_number"].required = False
        self.fields["tax_identification_number"].required = False
        self.fields["address_line_2"].required = False
        self.fields["fax"].required = False
        self.fields["website"].required = False


class InvoiceSettingsForm(forms.ModelForm):
    """
    Form for editing invoice settings including templates, numbering, and customization.
    """

    class Meta:
        model = InvoiceSettings
        fields = [
            "invoice_template",
            "receipt_template",
            "invoice_numbering_scheme",
            "invoice_number_prefix",
            "invoice_number_format",
            "receipt_numbering_scheme",
            "receipt_number_prefix",
            "receipt_number_format",
            "show_item_codes",
            "show_item_descriptions",
            "show_item_weights",
            "show_karat_purity",
            "show_tax_breakdown",
            "show_payment_terms",
            "custom_field_1_label",
            "custom_field_1_value",
            "custom_field_2_label",
            "custom_field_2_value",
            "invoice_footer_text",
            "receipt_footer_text",
            "payment_terms",
            "return_policy",
        ]

        widgets = {
            "invoice_template": forms.Select(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                }
            ),
            "receipt_template": forms.Select(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                }
            ),
            "invoice_numbering_scheme": forms.Select(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "onchange": "toggleCustomFormat('invoice')",
                }
            ),
            "invoice_number_prefix": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "INV",
                    "maxlength": "10",
                }
            ),
            "invoice_number_format": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "{prefix}-{number:06d}",
                    "id": "invoice_number_format",
                }
            ),
            "receipt_numbering_scheme": forms.Select(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "onchange": "toggleCustomFormat('receipt')",
                }
            ),
            "receipt_number_prefix": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "RCP",
                    "maxlength": "10",
                }
            ),
            "receipt_number_format": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "{prefix}-{number:06d}",
                    "id": "receipt_number_format",
                }
            ),
            "show_item_codes": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-600 rounded dark:bg-gray-700",
                }
            ),
            "show_item_descriptions": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-600 rounded dark:bg-gray-700",
                }
            ),
            "show_item_weights": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-600 rounded dark:bg-gray-700",
                }
            ),
            "show_karat_purity": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-600 rounded dark:bg-gray-700",
                }
            ),
            "show_tax_breakdown": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-600 rounded dark:bg-gray-700",
                }
            ),
            "show_payment_terms": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-600 rounded dark:bg-gray-700",
                }
            ),
            "custom_field_1_label": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "e.g., Certificate Number",
                    "maxlength": "50",
                }
            ),
            "custom_field_1_value": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "Default value (optional)",
                }
            ),
            "custom_field_2_label": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "e.g., Warranty Period",
                    "maxlength": "50",
                }
            ),
            "custom_field_2_value": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "Default value (optional)",
                }
            ),
            "invoice_footer_text": forms.Textarea(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "rows": "3",
                    "placeholder": "Thank you for your business!",
                }
            ),
            "receipt_footer_text": forms.Textarea(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "rows": "3",
                    "placeholder": "Please keep this receipt for your records.",
                }
            ),
            "payment_terms": forms.Textarea(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "rows": "4",
                    "placeholder": "Payment is due within 30 days of invoice date.",
                }
            ),
            "return_policy": forms.Textarea(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "rows": "4",
                    "placeholder": "Returns accepted within 30 days with original receipt.",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make custom fields optional
        self.fields["custom_field_1_label"].required = False
        self.fields["custom_field_1_value"].required = False
        self.fields["custom_field_2_label"].required = False
        self.fields["custom_field_2_value"].required = False
        self.fields["invoice_footer_text"].required = False
        self.fields["receipt_footer_text"].required = False
        self.fields["payment_terms"].required = False
        self.fields["return_policy"].required = False

    def clean_invoice_number_format(self):
        """Validate invoice number format string."""
        format_str = self.cleaned_data.get("invoice_number_format", "")

        if not format_str:
            return format_str

        # Check if format string contains required placeholders
        if "{number" not in format_str:
            raise forms.ValidationError("Format must contain {number} placeholder")

        # Test format string with sample data
        try:
            format_str.format(prefix="TEST", number=1, year=2024, month=1)
        except (KeyError, ValueError) as e:
            raise forms.ValidationError(f"Invalid format string: {e}")

        return format_str

    def clean_receipt_number_format(self):
        """Validate receipt number format string."""
        format_str = self.cleaned_data.get("receipt_number_format", "")

        if not format_str:
            return format_str

        # Check if format string contains required placeholders
        if "{number" not in format_str:
            raise forms.ValidationError("Format must contain {number} placeholder")

        # Test format string with sample data
        try:
            format_str.format(prefix="TEST", number=1, year=2024, month=1)
        except (KeyError, ValueError) as e:
            raise forms.ValidationError(f"Invalid format string: {e}")

        return format_str


class IntegrationSettingsForm(forms.ModelForm):
    """
    Form for editing integration settings including payment gateways, SMS providers, and email services.
    """

    # Custom fields for sensitive data that need special handling
    payment_gateway_api_key_input = forms.CharField(
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                "placeholder": "Enter API key (leave blank to keep existing)",
            }
        ),
        help_text="Leave blank to keep existing API key",
    )

    payment_gateway_secret_key_input = forms.CharField(
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                "placeholder": "Enter secret key (leave blank to keep existing)",
            }
        ),
        help_text="Leave blank to keep existing secret key",
    )

    sms_api_key_input = forms.CharField(
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                "placeholder": "Enter API key (leave blank to keep existing)",
            }
        ),
        help_text="Leave blank to keep existing API key",
    )

    sms_api_secret_input = forms.CharField(
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                "placeholder": "Enter API secret (leave blank to keep existing)",
            }
        ),
        help_text="Leave blank to keep existing API secret",
    )

    email_api_key_input = forms.CharField(
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                "placeholder": "Enter API key (leave blank to keep existing)",
            }
        ),
        help_text="Leave blank to keep existing API key",
    )

    smtp_password_input = forms.CharField(
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                "placeholder": "Enter SMTP password (leave blank to keep existing)",
            }
        ),
        help_text="Leave blank to keep existing SMTP password",
    )

    class Meta:
        model = IntegrationSettings
        fields = [
            # Payment Gateway
            "payment_gateway_enabled",
            "payment_gateway_provider",
            "payment_gateway_test_mode",
            # SMS Provider
            "sms_provider_enabled",
            "sms_provider",
            "sms_sender_id",
            # Email Provider
            "email_provider_enabled",
            "email_provider",
            "email_from_address",
            "email_from_name",
            # SMTP Settings
            "smtp_host",
            "smtp_port",
            "smtp_username",
            "smtp_use_tls",
            # Gold Rate API
            "gold_rate_api_enabled",
            "gold_rate_api_provider",
            "gold_rate_update_frequency",
            # Webhook Settings
            "webhook_url",
        ]

        widgets = {
            # Payment Gateway
            "payment_gateway_enabled": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-600 rounded dark:bg-gray-700",
                }
            ),
            "payment_gateway_provider": forms.Select(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                }
            ),
            "payment_gateway_test_mode": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-600 rounded dark:bg-gray-700",
                }
            ),
            # SMS Provider
            "sms_provider_enabled": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-600 rounded dark:bg-gray-700",
                }
            ),
            "sms_provider": forms.Select(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                }
            ),
            "sms_sender_id": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "+1234567890",
                }
            ),
            # Email Provider
            "email_provider_enabled": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-600 rounded dark:bg-gray-700",
                }
            ),
            "email_provider": forms.Select(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "onchange": "toggleEmailProvider()",
                }
            ),
            "email_from_address": forms.EmailInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "noreply@yourshop.com",
                }
            ),
            "email_from_name": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "Your Jewelry Shop",
                }
            ),
            # SMTP Settings
            "smtp_host": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "smtp.gmail.com",
                }
            ),
            "smtp_port": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "587",
                    "min": "1",
                    "max": "65535",
                }
            ),
            "smtp_username": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "your-email@gmail.com",
                }
            ),
            "smtp_use_tls": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-600 rounded dark:bg-gray-700",
                }
            ),
            # Gold Rate API
            "gold_rate_api_enabled": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-600 rounded dark:bg-gray-700",
                }
            ),
            "gold_rate_api_provider": forms.Select(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                }
            ),
            "gold_rate_update_frequency": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "60",
                    "min": "1",
                    "max": "1440",
                }
            ),
            # Webhook Settings
            "webhook_url": forms.URLInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "https://your-app.com/webhook",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add provider choices dynamically
        self.fields["payment_gateway_provider"].choices = [
            ("", "Select Provider"),
            ("stripe", "Stripe"),
            ("paypal", "PayPal"),
            ("square", "Square"),
            ("razorpay", "Razorpay"),
        ]

        self.fields["sms_provider"].choices = [
            ("", "Select Provider"),
            ("twilio", "Twilio"),
            ("nexmo", "Vonage (Nexmo)"),
            ("aws_sns", "AWS SNS"),
        ]

        self.fields["email_provider"].choices = [
            ("", "Select Provider"),
            ("sendgrid", "SendGrid"),
            ("mailgun", "Mailgun"),
            ("aws_ses", "AWS SES"),
            ("smtp", "SMTP"),
        ]

        self.fields["gold_rate_api_provider"].choices = [
            ("", "Select Provider"),
            ("goldapi", "GoldAPI"),
            ("metals_api", "Metals-API"),
            ("fixer", "Fixer.io"),
        ]

        # Make all fields optional by default
        for field_name, field in self.fields.items():
            if not field_name.endswith("_input"):
                field.required = False

    def clean_payment_gateway_provider(self):
        """Validate payment gateway provider when enabled."""
        enabled = self.cleaned_data.get("payment_gateway_enabled", False)
        provider = self.cleaned_data.get("payment_gateway_provider", "")

        if enabled and not provider:
            raise forms.ValidationError("Provider is required when payment gateway is enabled.")

        return provider

    def clean_sms_provider(self):
        """Validate SMS provider when enabled."""
        enabled = self.cleaned_data.get("sms_provider_enabled", False)
        provider = self.cleaned_data.get("sms_provider", "")

        if enabled and not provider:
            raise forms.ValidationError("Provider is required when SMS is enabled.")

        return provider

    def clean_email_provider(self):
        """Validate email provider when enabled."""
        enabled = self.cleaned_data.get("email_provider_enabled", False)
        provider = self.cleaned_data.get("email_provider", "")

        if enabled and not provider:
            raise forms.ValidationError("Provider is required when email is enabled.")

        return provider

    def clean_smtp_host(self):
        """Validate SMTP host when SMTP provider is selected."""
        email_provider = self.cleaned_data.get("email_provider", "")
        smtp_host = self.cleaned_data.get("smtp_host", "")

        if email_provider == "smtp" and not smtp_host:
            raise forms.ValidationError("SMTP host is required when using SMTP provider.")

        return smtp_host

    def clean_smtp_port(self):
        """Validate SMTP port when SMTP provider is selected."""
        email_provider = self.cleaned_data.get("email_provider", "")
        smtp_port = self.cleaned_data.get("smtp_port")

        if email_provider == "smtp" and not smtp_port:
            raise forms.ValidationError("SMTP port is required when using SMTP provider.")

        if smtp_port and (smtp_port < 1 or smtp_port > 65535):
            raise forms.ValidationError("SMTP port must be between 1 and 65535.")

        return smtp_port

    def save(self, commit=True):
        """Save the form and handle encrypted fields."""
        instance = super().save(commit=False)

        # Handle encrypted fields
        if self.cleaned_data.get("payment_gateway_api_key_input"):
            instance.set_payment_gateway_api_key(self.cleaned_data["payment_gateway_api_key_input"])

        if self.cleaned_data.get("payment_gateway_secret_key_input"):
            instance.set_payment_gateway_secret_key(
                self.cleaned_data["payment_gateway_secret_key_input"]
            )

        if self.cleaned_data.get("sms_api_key_input"):
            instance.set_sms_api_key(self.cleaned_data["sms_api_key_input"])

        if self.cleaned_data.get("sms_api_secret_input"):
            instance.set_sms_api_secret(self.cleaned_data["sms_api_secret_input"])

        if self.cleaned_data.get("email_api_key_input"):
            instance.set_email_api_key(self.cleaned_data["email_api_key_input"])

        if self.cleaned_data.get("smtp_password_input"):
            instance.set_smtp_password(self.cleaned_data["smtp_password_input"])

        if commit:
            instance.save()

        return instance


class TenantCreateForm(forms.ModelForm):
    """
    Form for creating new tenants.

    Used by platform administrators to manually create tenant accounts.
    """

    class Meta:
        model = Tenant
        fields = ["company_name", "slug", "status"]

        widgets = {
            "company_name": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "Enter company name",
                    "required": True,
                }
            ),
            "slug": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "URL-friendly identifier (auto-generated if left blank)",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                }
            ),
        }

        help_texts = {
            "company_name": "The official name of the jewelry shop business",
            "slug": "Leave blank to auto-generate from company name",
            "status": "Initial status for the tenant account",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make slug optional (will be auto-generated)
        self.fields["slug"].required = False

        # Set default status to ACTIVE
        self.fields["status"].initial = Tenant.ACTIVE

    def clean_company_name(self):
        """Validate company name."""
        company_name = self.cleaned_data.get("company_name", "").strip()

        if not company_name:
            raise forms.ValidationError("Company name is required.")

        if len(company_name) < 2:
            raise forms.ValidationError("Company name must be at least 2 characters long.")

        return company_name

    def clean_slug(self):
        """Validate and auto-generate slug if not provided."""
        slug = self.cleaned_data.get("slug", "").strip()

        # If slug is not provided, it will be auto-generated in the model's save method
        if not slug:
            return slug

        # Validate slug format
        import re

        if not re.match(r"^[a-z0-9-]+$", slug):
            raise forms.ValidationError(
                "Slug can only contain lowercase letters, numbers, and hyphens."
            )

        # Check for uniqueness
        if Tenant.objects.filter(slug=slug).exists():
            raise forms.ValidationError("This slug is already in use.")

        return slug


class TenantEditForm(forms.ModelForm):
    """
    Form for editing existing tenants.

    Used by platform administrators to modify tenant details.
    """

    class Meta:
        model = Tenant
        fields = ["company_name", "slug", "status"]

        widgets = {
            "company_name": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "Enter company name",
                    "required": True,
                }
            ),
            "slug": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "URL-friendly identifier",
                    "required": True,
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                }
            ),
        }

        help_texts = {
            "company_name": "The official name of the jewelry shop business",
            "slug": "URL-friendly identifier (must be unique)",
            "status": "Current operational status of the tenant",
        }

    def clean_company_name(self):
        """Validate company name."""
        company_name = self.cleaned_data.get("company_name", "").strip()

        if not company_name:
            raise forms.ValidationError("Company name is required.")

        if len(company_name) < 2:
            raise forms.ValidationError("Company name must be at least 2 characters long.")

        return company_name

    def clean_slug(self):
        """Validate slug uniqueness."""
        slug = self.cleaned_data.get("slug", "").strip()

        if not slug:
            raise forms.ValidationError("Slug is required.")

        # Validate slug format
        import re

        if not re.match(r"^[a-z0-9-]+$", slug):
            raise forms.ValidationError(
                "Slug can only contain lowercase letters, numbers, and hyphens."
            )

        # Check for uniqueness (excluding current instance)
        existing = Tenant.objects.filter(slug=slug).exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError("This slug is already in use.")

        return slug


# ============================================================================
# Feature Flag Management Forms
# ============================================================================


class FeatureFlagForm(forms.ModelForm):
    """Form for creating/editing feature flags."""

    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Reason for this change..."}),
        help_text="Explain why you're making this change (for audit trail)",
    )

    class Meta:
        model = Flag
        fields = ["name", "everyone", "percent", "note"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g., new_pos_interface"}),
            "note": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Description of this feature..."}
            ),
            "percent": forms.NumberInput(attrs={"min": 0, "max": 100, "step": 0.1}),
        }
        help_texts = {
            "everyone": "Enable for everyone (True), disable for everyone (False), or use percentage rollout (None)",
            "percent": "Percentage of users to enable this flag for (0-100). Only used when 'everyone' is None.",
        }


class TenantFeatureFlagForm(forms.ModelForm):
    """Form for creating tenant-specific feature flag overrides."""

    class Meta:
        model = TenantFeatureFlag
        fields = ["tenant", "flag", "enabled", "notes"]
        widgets = {
            "notes": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Reason for this override..."}
            ),
        }
        help_texts = {
            "tenant": "Select the tenant for this override",
            "flag": "Select the feature flag to override",
            "enabled": "Enable or disable this flag for the selected tenant",
            "notes": "Explain why this tenant needs a special override (e.g., beta testing, early access)",
        }


class ABTestVariantForm(forms.ModelForm):
    """Form for creating A/B test variants."""

    class Meta:
        model = ABTestVariant
        fields = [
            "name",
            "flag",
            "control_group_percentage",
            "variant_group_percentage",
            "description",
            "hypothesis",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g., checkout_flow_test_v1"}),
            "description": forms.Textarea(
                attrs={"rows": 3, "placeholder": "What are you testing?"}
            ),
            "hypothesis": forms.Textarea(
                attrs={"rows": 3, "placeholder": "What do you expect to learn?"}
            ),
            "control_group_percentage": forms.NumberInput(
                attrs={"min": 0, "max": 100, "step": 0.1}
            ),
            "variant_group_percentage": forms.NumberInput(
                attrs={"min": 0, "max": 100, "step": 0.1}
            ),
        }
        help_texts = {
            "control_group_percentage": "Percentage of users in control group (typically 50%)",
            "variant_group_percentage": "Percentage of users in variant group (typically 50%)",
        }

    def clean(self):
        """Validate that percentages add up to 100."""
        cleaned_data = super().clean()
        control = cleaned_data.get("control_group_percentage")
        variant = cleaned_data.get("variant_group_percentage")

        if control and variant:
            total = control + variant
            if total != 100:
                raise forms.ValidationError(
                    f"Control and variant percentages must add up to 100%. Currently: {total}%"
                )

        return cleaned_data


class EmergencyKillSwitchForm(forms.Form):
    """Form for activating emergency kill switch."""

    flag_name = forms.ChoiceField(
        label="Feature Flag",
        help_text="Select the feature flag to disable immediately",
    )

    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Explain the emergency..."}),
        help_text="Describe the critical issue that requires immediate disable",
    )

    def __init__(self, *args, **kwargs):
        # Remove instance kwarg if present (Forms don't use it, only ModelForms do)
        kwargs.pop("instance", None)
        super().__init__(*args, **kwargs)
        # Import here to avoid circular imports
        from waffle.models import Flag

        # Populate flag choices
        self.fields["flag_name"].choices = [
            (flag.name, f"{flag.name} - {flag.note}")
            for flag in Flag.objects.all().order_by("name")
        ]
