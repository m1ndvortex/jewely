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
    Form for creating new tenants (basic version).

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


class EnhancedTenantCreateForm(forms.Form):
    """
    Enhanced form for creating new tenants with comprehensive configuration.

    This form includes:
    - Basic Info: company_name, slug, status
    - Business Settings: business_name, registration_number, tax_id, address, phone, fax, email, website
    - Localization: timezone, currency, date_format
    - Domain: subdomain (auto-generated), custom_domain
    - Initial Admin User: admin_username, admin_email, admin_password, admin_password_confirm, admin_phone

    Used by platform administrators to create fully configured tenant accounts.

    Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.8
    """

    # Common widget class for text inputs
    TEXT_INPUT_CLASS = (
        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
    )

    SELECT_CLASS = (
        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
    )

    # =========================================================================
    # Basic Info Section (Requirement 1.1, 1.2)
    # =========================================================================
    company_name = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Enter company name",
            }
        ),
        help_text="The official name of the jewelry shop business (required)",
    )

    slug = forms.SlugField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "URL-friendly identifier (auto-generated if left blank)",
            }
        ),
        help_text="Leave blank to auto-generate from company name",
    )

    status = forms.ChoiceField(
        choices=Tenant.STATUS_CHOICES,
        initial=Tenant.ACTIVE,
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
        help_text="Initial status for the tenant account",
    )

    # =========================================================================
    # Business Settings Section (Requirement 1.3)
    # =========================================================================
    business_name = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Official business name (if different from company name)",
            }
        ),
        help_text="Official business name (can differ from company name)",
    )

    business_registration_number = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Business registration number",
            }
        ),
        help_text="Business registration or license number",
    )

    tax_identification_number = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Tax ID or VAT number",
            }
        ),
        help_text="Tax identification number",
    )

    address_line_1 = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Street address",
            }
        ),
    )

    address_line_2 = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Apartment, suite, etc.",
            }
        ),
    )

    city = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "City",
            }
        ),
    )

    state_province = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "State or Province",
            }
        ),
    )

    postal_code = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Postal code",
            }
        ),
    )

    country = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Country",
            }
        ),
    )

    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "+1 (555) 123-4567",
                "type": "tel",
            }
        ),
        help_text="Business phone number",
    )

    fax = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "+1 (555) 123-4568",
                "type": "tel",
            }
        ),
        help_text="Business fax number",
    )

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "contact@yourshop.com",
            }
        ),
        help_text="Business contact email (required)",
    )

    website = forms.URLField(
        required=False,
        widget=forms.URLInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "https://www.yourshop.com",
            }
        ),
        help_text="Business website URL",
    )

    # =========================================================================
    # Localization Section (Requirement 1.4)
    # =========================================================================
    timezone = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
        help_text="Business timezone",
    )

    currency = forms.ChoiceField(
        choices=TenantSettings.CURRENCY_CHOICES,
        initial=TenantSettings.CURRENCY_USD,
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
        help_text="Default currency for transactions",
    )

    date_format = forms.ChoiceField(
        choices=TenantSettings.DATE_FORMAT_CHOICES,
        initial=TenantSettings.DATE_FORMAT_MDY,
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
        help_text="Preferred date format for display",
    )

    # =========================================================================
    # Domain Section (Requirement 1.5)
    # =========================================================================
    subdomain = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Auto-generated from slug",
                "readonly": "readonly",
            }
        ),
        help_text="Subdomain will be auto-generated from slug (e.g., your-shop.jewelry-shop.local)",
    )

    custom_domain = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "shop.example.com",
            }
        ),
        help_text="Optional custom domain (requires DNS verification)",
    )

    # =========================================================================
    # Initial Admin User Section (Requirement 1.2, 1.8)
    # =========================================================================
    admin_username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "admin_username",
                "autocomplete": "off",
            }
        ),
        help_text="Username for the initial tenant owner (required)",
    )

    admin_email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "admin@yourshop.com",
                "autocomplete": "off",
            }
        ),
        help_text="Email for the initial tenant owner (required)",
    )

    admin_password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Enter password",
                "autocomplete": "new-password",
            }
        ),
        help_text="Password must be at least 8 characters with 1 uppercase, 1 number, and 1 special character",
    )

    admin_password_confirm = forms.CharField(
        required=True,
        widget=forms.PasswordInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Confirm password",
                "autocomplete": "new-password",
            }
        ),
        help_text="Re-enter the password to confirm",
    )

    admin_phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "+1 (555) 123-4567",
                "type": "tel",
            }
        ),
        help_text="Phone number for the initial tenant owner",
    )

    def __init__(self, *args, **kwargs):
        """Initialize the form with timezone choices."""
        super().__init__(*args, **kwargs)

        # Populate timezone choices from zoneinfo (Python 3.9+)
        try:
            from zoneinfo import available_timezones

            # Get common timezones (filter out obscure ones)
            all_timezones = sorted(available_timezones())
            # Filter to common timezones (those with region/city format)
            common_timezones = [
                tz for tz in all_timezones if "/" in tz and not tz.startswith(("Etc/", "SystemV/"))
            ]
            timezone_choices = [("UTC", "UTC")] + [(tz, tz) for tz in common_timezones]
        except ImportError:
            # Fallback for older Python versions
            timezone_choices = [
                ("UTC", "UTC"),
                ("America/New_York", "America/New_York"),
                ("America/Los_Angeles", "America/Los_Angeles"),
                ("America/Chicago", "America/Chicago"),
                ("Europe/London", "Europe/London"),
                ("Europe/Paris", "Europe/Paris"),
                ("Asia/Tokyo", "Asia/Tokyo"),
                ("Asia/Tehran", "Asia/Tehran"),
                ("Asia/Dubai", "Asia/Dubai"),
            ]

        self.fields["timezone"].choices = timezone_choices
        self.fields["timezone"].initial = "UTC"

    def clean_company_name(self):
        """Validate company name (Requirement 1.2)."""
        company_name = self.cleaned_data.get("company_name", "").strip()

        if not company_name:
            raise forms.ValidationError("Company name is required.")

        if len(company_name) < 2:
            raise forms.ValidationError("Company name must be at least 2 characters long.")

        return company_name

    def clean_slug(self):
        """Validate and prepare slug."""
        import re

        slug = self.cleaned_data.get("slug", "").strip().lower()

        if not slug:
            # Will be auto-generated from company_name
            return slug

        # Validate slug format
        if not re.match(r"^[a-z0-9-]+$", slug):
            raise forms.ValidationError(
                "Slug can only contain lowercase letters, numbers, and hyphens."
            )

        # Check for uniqueness
        if Tenant.objects.filter(slug=slug).exists():
            raise forms.ValidationError("This slug is already in use.")

        return slug

    def clean_admin_username(self):
        """Validate admin username uniqueness (Requirement 1.8)."""
        from apps.core.models import User

        username = self.cleaned_data.get("admin_username", "").strip()

        if not username:
            raise forms.ValidationError("Admin username is required.")

        # Check for uniqueness
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already in use.")

        return username

    def clean_admin_email(self):
        """Validate admin email (Requirement 1.2)."""
        email = self.cleaned_data.get("admin_email", "").strip().lower()

        if not email:
            raise forms.ValidationError("Admin email is required.")

        return email

    def clean_admin_password(self):
        """Validate password strength (Requirement 1.8)."""
        from apps.core.services.credential_service import CredentialService

        password = self.cleaned_data.get("admin_password", "")

        if not password:
            raise forms.ValidationError("Password is required.")

        # Use CredentialService for password validation
        credential_service = CredentialService()
        is_valid, errors = credential_service.validate_password_strength(password)

        if not is_valid:
            raise forms.ValidationError(errors)

        return password

    def clean_custom_domain(self):
        """Validate custom domain format."""
        import re

        domain = self.cleaned_data.get("custom_domain", "").strip().lower()

        if not domain:
            return domain

        # Basic hostname validation
        hostname_pattern = r"^(?!-)[a-z0-9-]{1,63}(?<!-)(\.[a-z0-9-]{1,63})*\.[a-z]{2,}$"
        if not re.match(hostname_pattern, domain):
            raise forms.ValidationError(
                "Invalid domain format. Please enter a valid hostname (e.g., shop.example.com)."
            )

        # Check if domain is already in use
        from apps.core.models import TenantDomain

        if TenantDomain.objects.filter(domain=domain).exists():
            raise forms.ValidationError("This domain is already in use.")

        return domain

    def clean(self):
        """Cross-field validation."""
        cleaned_data = super().clean()

        # Validate password confirmation
        password = cleaned_data.get("admin_password")
        password_confirm = cleaned_data.get("admin_password_confirm")

        if password and password_confirm and password != password_confirm:
            self.add_error("admin_password_confirm", "Passwords do not match.")

        return cleaned_data

    def get_tenant_data(self):
        """Extract tenant model data from cleaned form data."""
        return {
            "company_name": self.cleaned_data.get("company_name"),
            "slug": self.cleaned_data.get("slug"),
            "status": self.cleaned_data.get("status"),
        }

    def get_settings_data(self):
        """Extract TenantSettings data from cleaned form data."""
        return {
            "business_name": self.cleaned_data.get("business_name"),
            "business_registration_number": self.cleaned_data.get("business_registration_number"),
            "tax_identification_number": self.cleaned_data.get("tax_identification_number"),
            "address_line_1": self.cleaned_data.get("address_line_1"),
            "address_line_2": self.cleaned_data.get("address_line_2"),
            "city": self.cleaned_data.get("city"),
            "state_province": self.cleaned_data.get("state_province"),
            "postal_code": self.cleaned_data.get("postal_code"),
            "country": self.cleaned_data.get("country"),
            "phone": self.cleaned_data.get("phone"),
            "fax": self.cleaned_data.get("fax"),
            "email": self.cleaned_data.get("email"),
            "website": self.cleaned_data.get("website"),
            "timezone": self.cleaned_data.get("timezone"),
            "currency": self.cleaned_data.get("currency"),
            "date_format": self.cleaned_data.get("date_format"),
        }

    def get_owner_data(self):
        """Extract initial admin user data from cleaned form data."""
        return {
            "username": self.cleaned_data.get("admin_username"),
            "email": self.cleaned_data.get("admin_email"),
            "password": self.cleaned_data.get("admin_password"),
            "phone": self.cleaned_data.get("admin_phone"),
        }

    def get_domain_data(self):
        """Extract domain configuration data from cleaned form data."""
        return {
            "subdomain": self.cleaned_data.get("subdomain"),
            "custom_domain": self.cleaned_data.get("custom_domain"),
        }


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


class EnhancedTenantEditForm(forms.Form):
    """
    Enhanced form for editing existing tenants with comprehensive configuration.

    This form includes all configurable fields organized in sections:
    - Basic Info: company_name, slug, status
    - Business Settings: business_name, registration_number, tax_id, address, phone, fax, email, website
    - Localization: timezone, currency, date_format
    - Domain: subdomain (read-only), custom_domain
    - Security: require_mfa_for_managers, password_expiry_days
    - Branding: logo, primary_color, secondary_color

    Used by platform administrators to modify tenant configuration.

    Requirements: 2.1, 2.2, 2.3, 2.4, 2.6
    """

    # Common widget class for text inputs
    TEXT_INPUT_CLASS = (
        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
    )

    SELECT_CLASS = (
        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
    )

    CHECKBOX_CLASS = (
        "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 "
        "dark:border-gray-600 rounded dark:bg-gray-700"
    )

    # =========================================================================
    # Basic Info Section (Requirement 2.2)
    # =========================================================================
    company_name = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Enter company name",
            }
        ),
        help_text="The official name of the jewelry shop business (required)",
    )

    slug = forms.SlugField(
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "URL-friendly identifier",
            }
        ),
        help_text="URL-friendly identifier (must be unique)",
    )

    status = forms.ChoiceField(
        choices=Tenant.STATUS_CHOICES,
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
        help_text="Current operational status of the tenant",
    )

    # =========================================================================
    # Business Settings Section (Requirement 2.3)
    # =========================================================================
    business_name = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Official business name (if different from company name)",
            }
        ),
        help_text="Official business name (can differ from company name)",
    )

    business_registration_number = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Business registration number",
            }
        ),
        help_text="Business registration or license number",
    )

    tax_identification_number = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Tax ID or VAT number",
            }
        ),
        help_text="Tax identification number",
    )

    address_line_1 = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Street address",
            }
        ),
    )

    address_line_2 = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Apartment, suite, etc.",
            }
        ),
    )

    city = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "City",
            }
        ),
    )

    state_province = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "State or Province",
            }
        ),
    )

    postal_code = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Postal code",
            }
        ),
    )

    country = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Country",
            }
        ),
    )

    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "+1 (555) 123-4567",
                "type": "tel",
            }
        ),
        help_text="Business phone number",
    )

    fax = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "+1 (555) 123-4568",
                "type": "tel",
            }
        ),
        help_text="Business fax number",
    )

    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "contact@yourshop.com",
            }
        ),
        help_text="Business contact email",
    )

    website = forms.URLField(
        required=False,
        widget=forms.URLInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "https://www.yourshop.com",
            }
        ),
        help_text="Business website URL",
    )

    # =========================================================================
    # Localization Section (Requirement 2.3)
    # =========================================================================
    timezone = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
        help_text="Business timezone",
    )

    currency = forms.ChoiceField(
        choices=TenantSettings.CURRENCY_CHOICES,
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
        help_text="Default currency for transactions",
    )

    date_format = forms.ChoiceField(
        choices=TenantSettings.DATE_FORMAT_CHOICES,
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
        help_text="Preferred date format for display",
    )

    # =========================================================================
    # Domain Section (Requirement 2.4)
    # =========================================================================
    subdomain = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Subdomain",
                "readonly": "readonly",
            }
        ),
        help_text="Subdomain (auto-generated from slug, read-only)",
    )

    custom_domain = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "shop.example.com",
            }
        ),
        help_text="Optional custom domain (requires DNS verification)",
    )

    # =========================================================================
    # Security Section (Requirement 2.3 - TenantSettings security fields)
    # =========================================================================
    require_mfa_for_managers = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
        help_text="Require MFA for tenant managers and owners",
    )

    password_expiry_days = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=365,
        widget=forms.NumberInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "0",
                "min": "0",
                "max": "365",
            }
        ),
        help_text="Password expiry in days (0 = no expiry)",
    )

    # =========================================================================
    # Branding Section (Requirement 2.3 - TenantSettings branding fields)
    # =========================================================================
    logo = forms.ImageField(
        required=False,
        widget=forms.FileInput(
            attrs={
                "class": "mt-1 block w-full text-sm text-gray-500 dark:text-gray-400 "
                "file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 "
                "file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 "
                "hover:file:bg-blue-100 dark:file:bg-gray-700 dark:file:text-gray-300",
                "accept": "image/*",
            }
        ),
        help_text="Business logo for invoices and receipts",
    )

    primary_color = forms.CharField(
        max_length=7,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "#1f2937",
                "type": "color",
            }
        ),
        help_text="Primary brand color (hex format, e.g., #1f2937)",
    )

    secondary_color = forms.CharField(
        max_length=7,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "#6b7280",
                "type": "color",
            }
        ),
        help_text="Secondary brand color (hex format)",
    )

    # =========================================================================
    # Tax Configuration (Requirement 2.3 - TenantSettings tax fields)
    # =========================================================================
    default_tax_rate = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=4,
        min_value=0,
        max_value=1,
        widget=forms.NumberInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "0.0825",
                "step": "0.0001",
                "min": "0",
                "max": "1",
            }
        ),
        help_text="Default tax rate as decimal (e.g., 0.0825 for 8.25%)",
    )

    tax_inclusive_pricing = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
        help_text="Whether prices include tax by default",
    )

    def __init__(self, *args, tenant=None, **kwargs):
        """
        Initialize the form with tenant data.

        Args:
            tenant: The Tenant instance being edited (optional, for pre-populating fields)
        """
        self.tenant = tenant
        super().__init__(*args, **kwargs)

        # Populate timezone choices
        try:
            from zoneinfo import available_timezones

            all_timezones = sorted(available_timezones())
            common_timezones = [
                tz for tz in all_timezones if "/" in tz and not tz.startswith(("Etc/", "SystemV/"))
            ]
            timezone_choices = [("UTC", "UTC")] + [(tz, tz) for tz in common_timezones]
        except ImportError:
            timezone_choices = [
                ("UTC", "UTC"),
                ("America/New_York", "America/New_York"),
                ("America/Los_Angeles", "America/Los_Angeles"),
                ("America/Chicago", "America/Chicago"),
                ("Europe/London", "Europe/London"),
                ("Europe/Paris", "Europe/Paris"),
                ("Asia/Tokyo", "Asia/Tokyo"),
                ("Asia/Tehran", "Asia/Tehran"),
                ("Asia/Dubai", "Asia/Dubai"),
            ]

        self.fields["timezone"].choices = timezone_choices

        # Pre-populate fields if tenant is provided
        if tenant and not self.is_bound:
            self._populate_from_tenant(tenant)

    def _populate_from_tenant(self, tenant):
        """Populate form fields from tenant and related models."""
        from apps.core.models import TenantDomain

        # Basic Info
        self.initial["company_name"] = tenant.company_name
        self.initial["slug"] = tenant.slug
        self.initial["status"] = tenant.status

        # TenantSettings fields
        if hasattr(tenant, "settings") and tenant.settings:
            settings = tenant.settings
            self.initial["business_name"] = settings.business_name
            self.initial["business_registration_number"] = settings.business_registration_number
            self.initial["tax_identification_number"] = settings.tax_identification_number
            self.initial["address_line_1"] = settings.address_line_1
            self.initial["address_line_2"] = settings.address_line_2
            self.initial["city"] = settings.city
            self.initial["state_province"] = settings.state_province
            self.initial["postal_code"] = settings.postal_code
            self.initial["country"] = settings.country
            self.initial["phone"] = settings.phone
            self.initial["fax"] = settings.fax
            self.initial["email"] = settings.email
            self.initial["website"] = settings.website
            self.initial["timezone"] = settings.timezone
            self.initial["currency"] = settings.currency
            self.initial["date_format"] = settings.date_format
            self.initial["require_mfa_for_managers"] = settings.require_mfa_for_managers
            self.initial["password_expiry_days"] = settings.password_expiry_days
            self.initial["primary_color"] = settings.primary_color
            self.initial["secondary_color"] = settings.secondary_color
            self.initial["default_tax_rate"] = settings.default_tax_rate
            self.initial["tax_inclusive_pricing"] = settings.tax_inclusive_pricing

        # Domain fields
        try:
            subdomain = TenantDomain.objects.filter(
                tenant=tenant, domain_type=TenantDomain.DOMAIN_TYPE_SUBDOMAIN
            ).first()
            if subdomain:
                self.initial["subdomain"] = subdomain.domain
        except TenantDomain.DoesNotExist:
            pass

        try:
            custom_domain = TenantDomain.objects.filter(
                tenant=tenant, domain_type=TenantDomain.DOMAIN_TYPE_CUSTOM
            ).first()
            if custom_domain:
                self.initial["custom_domain"] = custom_domain.domain
        except TenantDomain.DoesNotExist:
            pass

    def clean_company_name(self):
        """Validate company name (Requirement 2.6)."""
        company_name = self.cleaned_data.get("company_name", "").strip()

        if not company_name:
            raise forms.ValidationError("Company name is required.")

        if len(company_name) < 2:
            raise forms.ValidationError("Company name must be at least 2 characters long.")

        return company_name

    def clean_slug(self):
        """Validate slug uniqueness (Requirement 2.6)."""
        import re

        slug = self.cleaned_data.get("slug", "").strip().lower()

        if not slug:
            raise forms.ValidationError("Slug is required.")

        # Validate slug format
        if not re.match(r"^[a-z0-9-]+$", slug):
            raise forms.ValidationError(
                "Slug can only contain lowercase letters, numbers, and hyphens."
            )

        # Check for uniqueness (excluding current tenant)
        existing = Tenant.objects.filter(slug=slug)
        if self.tenant:
            existing = existing.exclude(pk=self.tenant.pk)
        if existing.exists():
            raise forms.ValidationError("This slug is already in use.")

        return slug

    def clean_custom_domain(self):
        """Validate custom domain format (Requirement 2.6)."""
        import re

        from apps.core.models import TenantDomain

        domain = self.cleaned_data.get("custom_domain", "").strip().lower()

        if not domain:
            return domain

        # Basic hostname validation
        hostname_pattern = r"^(?!-)[a-z0-9-]{1,63}(?<!-)(\.[a-z0-9-]{1,63})*\.[a-z]{2,}$"
        if not re.match(hostname_pattern, domain):
            raise forms.ValidationError(
                "Invalid domain format. Please enter a valid hostname (e.g., shop.example.com)."
            )

        # Check if domain is already in use (excluding current tenant's domains)
        existing = TenantDomain.objects.filter(domain=domain)
        if self.tenant:
            existing = existing.exclude(tenant=self.tenant)
        if existing.exists():
            raise forms.ValidationError("This domain is already in use.")

        return domain

    def clean_primary_color(self):
        """Validate primary color hex format (Requirement 2.6)."""
        import re

        color = self.cleaned_data.get("primary_color", "").strip()

        if not color:
            return "#1f2937"  # Default color

        if not re.match(r"^#[0-9a-fA-F]{6}$", color):
            raise forms.ValidationError(
                "Invalid color format. Please use hex format (e.g., #1f2937)."
            )

        return color.lower()

    def clean_secondary_color(self):
        """Validate secondary color hex format (Requirement 2.6)."""
        import re

        color = self.cleaned_data.get("secondary_color", "").strip()

        if not color:
            return "#6b7280"  # Default color

        if not re.match(r"^#[0-9a-fA-F]{6}$", color):
            raise forms.ValidationError(
                "Invalid color format. Please use hex format (e.g., #6b7280)."
            )

        return color.lower()

    def clean_password_expiry_days(self):
        """Validate password expiry days (Requirement 2.6)."""
        days = self.cleaned_data.get("password_expiry_days")

        if days is None:
            return 0

        if days < 0:
            raise forms.ValidationError("Password expiry days cannot be negative.")

        if days > 365:
            raise forms.ValidationError("Password expiry days cannot exceed 365.")

        return days

    def clean_default_tax_rate(self):
        """Validate default tax rate (Requirement 2.6)."""
        from decimal import Decimal

        rate = self.cleaned_data.get("default_tax_rate")

        if rate is None:
            return Decimal("0.0000")

        if rate < 0:
            raise forms.ValidationError("Tax rate cannot be negative.")

        if rate > 1:
            raise forms.ValidationError(
                "Tax rate must be a decimal between 0 and 1 (e.g., 0.0825 for 8.25%)."
            )

        return rate

    def get_tenant_data(self):
        """Extract tenant model data from cleaned form data."""
        return {
            "company_name": self.cleaned_data.get("company_name"),
            "slug": self.cleaned_data.get("slug"),
            "status": self.cleaned_data.get("status"),
        }

    def get_settings_data(self):
        """Extract TenantSettings data from cleaned form data."""
        return {
            "business_name": self.cleaned_data.get("business_name") or "",
            "business_registration_number": self.cleaned_data.get("business_registration_number")
            or "",
            "tax_identification_number": self.cleaned_data.get("tax_identification_number") or "",
            "address_line_1": self.cleaned_data.get("address_line_1") or "",
            "address_line_2": self.cleaned_data.get("address_line_2") or "",
            "city": self.cleaned_data.get("city") or "",
            "state_province": self.cleaned_data.get("state_province") or "",
            "postal_code": self.cleaned_data.get("postal_code") or "",
            "country": self.cleaned_data.get("country") or "",
            "phone": self.cleaned_data.get("phone") or "",
            "fax": self.cleaned_data.get("fax") or "",
            "email": self.cleaned_data.get("email") or "",
            "website": self.cleaned_data.get("website") or "",
            "timezone": self.cleaned_data.get("timezone") or "UTC",
            "currency": self.cleaned_data.get("currency") or TenantSettings.CURRENCY_USD,
            "date_format": self.cleaned_data.get("date_format") or TenantSettings.DATE_FORMAT_MDY,
            "require_mfa_for_managers": self.cleaned_data.get("require_mfa_for_managers") or False,
            "password_expiry_days": self.cleaned_data.get("password_expiry_days") or 0,
            "primary_color": self.cleaned_data.get("primary_color") or "#1f2937",
            "secondary_color": self.cleaned_data.get("secondary_color") or "#6b7280",
            "default_tax_rate": self.cleaned_data.get("default_tax_rate") or 0,
            "tax_inclusive_pricing": self.cleaned_data.get("tax_inclusive_pricing") or False,
        }

    def get_domain_data(self):
        """Extract domain configuration data from cleaned form data."""
        return {
            "subdomain": self.cleaned_data.get("subdomain") or "",
            "custom_domain": self.cleaned_data.get("custom_domain") or "",
        }

    def get_branding_data(self):
        """Extract branding data from cleaned form data."""
        return {
            "logo": self.cleaned_data.get("logo"),
            "primary_color": self.cleaned_data.get("primary_color") or "#1f2937",
            "secondary_color": self.cleaned_data.get("secondary_color") or "#6b7280",
        }

    def get_security_data(self):
        """Extract security settings data from cleaned form data."""
        return {
            "require_mfa_for_managers": self.cleaned_data.get("require_mfa_for_managers") or False,
            "password_expiry_days": self.cleaned_data.get("password_expiry_days") or 0,
        }

    def get_localization_data(self):
        """Extract localization settings data from cleaned form data."""
        return {
            "timezone": self.cleaned_data.get("timezone") or "UTC",
            "currency": self.cleaned_data.get("currency") or TenantSettings.CURRENCY_USD,
            "date_format": self.cleaned_data.get("date_format") or TenantSettings.DATE_FORMAT_MDY,
        }

    def get_tax_data(self):
        """Extract tax configuration data from cleaned form data."""
        return {
            "default_tax_rate": self.cleaned_data.get("default_tax_rate") or 0,
            "tax_inclusive_pricing": self.cleaned_data.get("tax_inclusive_pricing") or False,
        }


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


class TenantUserCreateForm(forms.Form):
    """
    Form for creating new users within a tenant.

    This form is used by platform administrators to create users directly
    from the tenant detail Users tab. It includes all user fields and
    validates password strength.

    The form requires a tenant parameter to filter branch choices and
    validate username uniqueness within the tenant.

    Requirements: 3.3, 3.4
    """

    # Common widget class for text inputs
    TEXT_INPUT_CLASS = (
        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
    )

    SELECT_CLASS = (
        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
    )

    CHECKBOX_CLASS = (
        "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 "
        "dark:border-gray-600 rounded dark:bg-gray-700"
    )

    # =========================================================================
    # User Account Fields (Requirement 3.3)
    # =========================================================================
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Enter username",
                "autocomplete": "off",
            }
        ),
        help_text="Username for the new user (required, must be unique)",
    )

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "user@example.com",
                "autocomplete": "off",
            }
        ),
        help_text="Email address for the new user (required)",
    )

    password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Enter password",
                "autocomplete": "new-password",
            }
        ),
        help_text="Password must be at least 8 characters with 1 uppercase, 1 number, and 1 special character",
    )

    password_confirm = forms.CharField(
        required=True,
        widget=forms.PasswordInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Confirm password",
                "autocomplete": "new-password",
            }
        ),
        help_text="Re-enter the password to confirm",
    )

    # =========================================================================
    # Role and Assignment Fields (Requirement 3.3)
    # =========================================================================
    role = forms.ChoiceField(
        required=True,
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
        help_text="User's role within the tenant",
    )

    branch = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
        help_text="Branch assignment (optional)",
    )

    # =========================================================================
    # Contact and Preferences Fields (Requirement 3.3)
    # =========================================================================
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "+1 (555) 123-4567",
                "type": "tel",
            }
        ),
        help_text="User's phone number (optional)",
    )

    language = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
        help_text="User's preferred language",
    )

    theme = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
        help_text="User's preferred theme",
    )

    # =========================================================================
    # Security Fields (Requirement 3.3)
    # =========================================================================
    force_mfa = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
        help_text="Require user to enable MFA on first login",
    )

    def __init__(self, *args, tenant=None, **kwargs):
        """
        Initialize the form with tenant-specific choices.

        Args:
            tenant: The Tenant instance to filter branch choices and validate
                   username uniqueness within.
        """
        super().__init__(*args, **kwargs)

        self.tenant = tenant

        # Import here to avoid circular imports
        from apps.core.models import Branch, User

        # Set role choices (exclude PLATFORM_ADMIN - only tenant roles)
        self.fields["role"].choices = [
            (User.TENANT_OWNER, "Shop Owner"),
            (User.TENANT_MANAGER, "Shop Manager"),
            (User.TENANT_EMPLOYEE, "Shop Employee"),
        ]
        self.fields["role"].initial = User.TENANT_EMPLOYEE

        # Set language choices
        self.fields["language"].choices = User.LANGUAGE_CHOICES
        self.fields["language"].initial = User.LANGUAGE_ENGLISH

        # Set theme choices
        self.fields["theme"].choices = User.THEME_CHOICES
        self.fields["theme"].initial = User.THEME_LIGHT

        # Filter branch choices by tenant
        if tenant:
            self.fields["branch"].queryset = Branch.objects.filter(
                tenant=tenant, is_active=True
            ).order_by("name")
        else:
            self.fields["branch"].queryset = Branch.objects.none()

        # Add empty option for branch
        self.fields["branch"].empty_label = "-- No branch assignment --"

    def clean_username(self):
        """
        Validate username uniqueness within the tenant.

        Per Requirement 3.3 for user creation.
        """
        from apps.core.models import User

        username = self.cleaned_data.get("username", "").strip()

        if not username:
            raise forms.ValidationError("Username is required.")

        if len(username) < 3:
            raise forms.ValidationError("Username must be at least 3 characters long.")

        # Check for uniqueness within the tenant
        if self.tenant:
            if User.objects.filter(tenant=self.tenant, username=username).exists():
                raise forms.ValidationError("This username is already in use within this tenant.")
        else:
            # If no tenant, check global uniqueness
            if User.objects.filter(username=username).exists():
                raise forms.ValidationError("This username is already in use.")

        return username

    def clean_email(self):
        """Validate email format."""
        email = self.cleaned_data.get("email", "").strip().lower()

        if not email:
            raise forms.ValidationError("Email is required.")

        return email

    def clean_password(self):
        """
        Validate password strength.

        Per Requirement 3.3 for password validation using CredentialService.
        """
        from apps.core.services.credential_service import CredentialService

        password = self.cleaned_data.get("password", "")

        if not password:
            raise forms.ValidationError("Password is required.")

        # Use CredentialService for password validation
        credential_service = CredentialService()
        is_valid, errors = credential_service.validate_password_strength(password)

        if not is_valid:
            raise forms.ValidationError(errors)

        return password

    def clean_branch(self):
        """
        Validate that branch belongs to the tenant.

        Per Requirement 3.3 for branch assignment.
        """
        branch = self.cleaned_data.get("branch")

        if branch and self.tenant:
            if branch.tenant_id != self.tenant.id:
                raise forms.ValidationError("Selected branch does not belong to this tenant.")

        return branch

    def clean(self):
        """
        Cross-field validation.

        Validates password confirmation matches.
        """
        cleaned_data = super().clean()

        # Validate password confirmation
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            self.add_error("password_confirm", "Passwords do not match.")

        return cleaned_data

    def get_user_data(self):
        """
        Extract user model data from cleaned form data.

        Returns a dictionary suitable for creating a User instance.
        """
        return {
            "username": self.cleaned_data.get("username"),
            "email": self.cleaned_data.get("email"),
            "password": self.cleaned_data.get("password"),
            "role": self.cleaned_data.get("role"),
            "branch": self.cleaned_data.get("branch"),
            "phone": self.cleaned_data.get("phone", ""),
            "language": self.cleaned_data.get("language"),
            "theme": self.cleaned_data.get("theme"),
            "force_mfa": self.cleaned_data.get("force_mfa", False),
        }


class TenantUserEditForm(forms.Form):
    """
    Form for editing existing users within a tenant.

    This form is used by platform administrators to edit user details
    from the tenant detail Users tab. It includes editable user fields
    but excludes username (not editable) and password (handled separately).

    The form requires a tenant parameter to filter branch choices and
    optionally a user instance to pre-populate values.

    Requirements: 3.5
    """

    # Common widget class for text inputs
    TEXT_INPUT_CLASS = (
        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
    )

    SELECT_CLASS = (
        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
    )

    # =========================================================================
    # User Account Fields (Requirement 3.5)
    # =========================================================================
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "user@example.com",
                "autocomplete": "off",
            }
        ),
        help_text="Email address for the user (required)",
    )

    # =========================================================================
    # Role and Assignment Fields (Requirement 3.5)
    # =========================================================================
    role = forms.ChoiceField(
        required=True,
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
        help_text="User's role within the tenant",
    )

    branch = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
        help_text="Branch assignment (optional)",
    )

    # =========================================================================
    # Contact and Preferences Fields (Requirement 3.5)
    # =========================================================================
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "+1 (555) 123-4567",
                "type": "tel",
            }
        ),
        help_text="User's phone number (optional)",
    )

    language = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
        help_text="User's preferred language",
    )

    theme = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
        help_text="User's preferred theme",
    )

    def __init__(self, *args, tenant=None, user=None, **kwargs):
        """
        Initialize the form with tenant-specific choices and optional user data.

        Args:
            tenant: The Tenant instance to filter branch choices.
            user: Optional User instance to pre-populate form values.
        """
        super().__init__(*args, **kwargs)

        self.tenant = tenant
        self.user = user

        # Import here to avoid circular imports
        from apps.core.models import Branch, User

        # Set role choices (exclude PLATFORM_ADMIN - only tenant roles)
        self.fields["role"].choices = [
            (User.TENANT_OWNER, "Shop Owner"),
            (User.TENANT_MANAGER, "Shop Manager"),
            (User.TENANT_EMPLOYEE, "Shop Employee"),
        ]

        # Set language choices
        self.fields["language"].choices = User.LANGUAGE_CHOICES

        # Set theme choices
        self.fields["theme"].choices = User.THEME_CHOICES

        # Filter branch choices by tenant
        if tenant:
            self.fields["branch"].queryset = Branch.objects.filter(
                tenant=tenant, is_active=True
            ).order_by("name")
        else:
            self.fields["branch"].queryset = Branch.objects.none()

        # Add empty option for branch
        self.fields["branch"].empty_label = "-- No branch assignment --"

        # Pre-populate form with user data if provided
        if user and not self.is_bound:
            self.initial["email"] = user.email
            self.initial["role"] = user.role
            self.initial["branch"] = user.branch
            self.initial["phone"] = user.phone or ""
            self.initial["language"] = user.language
            self.initial["theme"] = user.theme

    def clean_email(self):
        """Validate email format."""
        email = self.cleaned_data.get("email", "").strip().lower()

        if not email:
            raise forms.ValidationError("Email is required.")

        return email

    def clean_branch(self):
        """
        Validate that branch belongs to the tenant.

        Per Requirement 3.5 for branch assignment.
        """
        branch = self.cleaned_data.get("branch")

        if branch and self.tenant:
            if branch.tenant_id != self.tenant.id:
                raise forms.ValidationError("Selected branch does not belong to this tenant.")

        return branch

    def clean_role(self):
        """
        Validate role change doesn't violate last owner protection.

        Per Requirement 3.8 - prevent role change of last active TENANT_OWNER.
        """
        from apps.core.models import User

        new_role = self.cleaned_data.get("role")

        # If we have a user and they're currently an owner
        if self.user and self.user.role == User.TENANT_OWNER:
            # Check if role is being changed away from owner
            if new_role != User.TENANT_OWNER:
                # Count other active owners in the tenant
                other_owners = (
                    User.objects.filter(tenant=self.tenant, role=User.TENANT_OWNER, is_active=True)
                    .exclude(id=self.user.id)
                    .count()
                )

                if other_owners == 0:
                    raise forms.ValidationError(
                        "Cannot change role of the last active owner. "
                        "Assign another user as owner first."
                    )

        return new_role

    def get_user_data(self):
        """
        Extract user model data from cleaned form data.

        Returns a dictionary suitable for updating a User instance.
        """
        return {
            "email": self.cleaned_data.get("email"),
            "role": self.cleaned_data.get("role"),
            "branch": self.cleaned_data.get("branch"),
            "phone": self.cleaned_data.get("phone", ""),
            "language": self.cleaned_data.get("language"),
            "theme": self.cleaned_data.get("theme"),
        }


# =============================================================================
# Tenant Settings Section Forms (Requirement 5.1-5.5)
# =============================================================================
# These forms are used for inline editing of tenant settings in the Settings tab.
# Each form handles a specific section of settings with its own save functionality.


class BusinessInfoForm(forms.ModelForm):
    """
    Form for editing business information settings.

    This form handles the Business Info section of the Settings tab,
    allowing inline editing of business identification fields.

    Requirements: 5.1
    """

    # Common widget class for text inputs
    TEXT_INPUT_CLASS = (
        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
    )

    class Meta:
        model = TenantSettings
        fields = [
            "business_name",
            "business_registration_number",
            "tax_identification_number",
        ]
        widgets = {
            "business_name": forms.TextInput(
                attrs={
                    "class": (
                        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
                        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
                    ),
                    "placeholder": "Official business name",
                }
            ),
            "business_registration_number": forms.TextInput(
                attrs={
                    "class": (
                        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
                        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
                    ),
                    "placeholder": "Business registration or license number",
                }
            ),
            "tax_identification_number": forms.TextInput(
                attrs={
                    "class": (
                        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
                        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
                    ),
                    "placeholder": "Tax ID or VAT number",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # All fields are optional
        for field_name in self.fields:
            self.fields[field_name].required = False


class ContactForm(forms.ModelForm):
    """
    Form for editing contact information settings.

    This form handles the Contact section of the Settings tab,
    allowing inline editing of address and contact fields.

    Requirements: 5.1
    """

    class Meta:
        model = TenantSettings
        fields = [
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
        ]
        widgets = {
            "address_line_1": forms.TextInput(
                attrs={
                    "class": (
                        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
                        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
                    ),
                    "placeholder": "Street address",
                }
            ),
            "address_line_2": forms.TextInput(
                attrs={
                    "class": (
                        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
                        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
                    ),
                    "placeholder": "Apartment, suite, etc.",
                }
            ),
            "city": forms.TextInput(
                attrs={
                    "class": (
                        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
                        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
                    ),
                    "placeholder": "City",
                }
            ),
            "state_province": forms.TextInput(
                attrs={
                    "class": (
                        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
                        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
                    ),
                    "placeholder": "State or Province",
                }
            ),
            "postal_code": forms.TextInput(
                attrs={
                    "class": (
                        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
                        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
                    ),
                    "placeholder": "Postal code",
                }
            ),
            "country": forms.TextInput(
                attrs={
                    "class": (
                        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
                        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
                    ),
                    "placeholder": "Country",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": (
                        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
                        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
                    ),
                    "placeholder": "+1 (555) 123-4567",
                    "type": "tel",
                }
            ),
            "fax": forms.TextInput(
                attrs={
                    "class": (
                        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
                        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
                    ),
                    "placeholder": "+1 (555) 123-4568",
                    "type": "tel",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": (
                        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
                        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
                    ),
                    "placeholder": "contact@yourshop.com",
                }
            ),
            "website": forms.URLInput(
                attrs={
                    "class": (
                        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
                        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
                    ),
                    "placeholder": "https://www.yourshop.com",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # All fields are optional
        for field_name in self.fields:
            self.fields[field_name].required = False


class LocalizationForm(forms.ModelForm):
    """
    Form for editing localization settings.

    This form handles the Localization section of the Settings tab,
    allowing inline editing of timezone, currency, and date format.

    Requirements: 5.4
    """

    class Meta:
        model = TenantSettings
        fields = [
            "timezone",
            "currency",
            "date_format",
        ]
        widgets = {
            "timezone": forms.Select(
                attrs={
                    "class": (
                        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
                        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
                    ),
                    "data-searchable": "true",
                }
            ),
            "currency": forms.Select(
                attrs={
                    "class": (
                        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
                        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
                    ),
                }
            ),
            "date_format": forms.Select(
                attrs={
                    "class": (
                        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
                        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
                    ),
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Use zoneinfo for timezone choices (Python 3.9+)
        from zoneinfo import available_timezones

        # Get common timezones (filter out some obscure ones)
        all_timezones = sorted(available_timezones())
        # Filter to common timezones (those with / in the name, excluding some system ones)
        common_timezones = [
            tz
            for tz in all_timezones
            if "/" in tz and not tz.startswith(("Etc/", "SystemV/", "posix/", "right/"))
        ]

        timezone_choices = [("", "-- Select Timezone --")] + [(tz, tz) for tz in common_timezones]
        self.fields["timezone"].widget = forms.Select(
            attrs={
                "class": (
                    "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
                    "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
                ),
                "data-searchable": "true",
            },
            choices=timezone_choices,
        )

        # Set currency choices from model
        self.fields["currency"].choices = TenantSettings.CURRENCY_CHOICES

        # Set date format choices from model
        self.fields["date_format"].choices = TenantSettings.DATE_FORMAT_CHOICES

    def clean_timezone(self):
        """Validate timezone is a valid IANA timezone."""
        from zoneinfo import available_timezones

        timezone = self.cleaned_data.get("timezone", "")

        if timezone and timezone not in available_timezones():
            raise forms.ValidationError(
                f"'{timezone}' is not a valid timezone. Please select from the list."
            )

        return timezone


class SecurityForm(forms.ModelForm):
    """
    Form for editing security settings.

    This form handles the Security section of the Settings tab,
    allowing inline editing of MFA and password policy settings.

    Requirements: 5.3
    """

    class Meta:
        model = TenantSettings
        fields = [
            "require_mfa_for_managers",
            "password_expiry_days",
        ]
        widgets = {
            "require_mfa_for_managers": forms.CheckboxInput(
                attrs={
                    "class": (
                        "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 "
                        "dark:border-gray-600 rounded dark:bg-gray-700"
                    ),
                }
            ),
            "password_expiry_days": forms.NumberInput(
                attrs={
                    "class": (
                        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
                        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
                    ),
                    "placeholder": "0 (no expiry)",
                    "min": "0",
                    "max": "365",
                }
            ),
        }
        help_texts = {
            "require_mfa_for_managers": "Require multi-factor authentication for tenant managers and owners",
            "password_expiry_days": "Number of days before passwords expire (0 = no expiry)",
        }

    def clean_password_expiry_days(self):
        """Validate password expiry days is within acceptable range."""
        days = self.cleaned_data.get("password_expiry_days", 0)

        if days is None:
            days = 0

        if days < 0:
            raise forms.ValidationError("Password expiry days cannot be negative.")

        if days > 365:
            raise forms.ValidationError("Password expiry days cannot exceed 365 days.")

        return days


class BrandingForm(forms.ModelForm):
    """
    Form for editing branding settings.

    This form handles the Branding section of the Settings tab,
    allowing inline editing of logo and brand colors.

    Requirements: 5.5
    """

    class Meta:
        model = TenantSettings
        fields = [
            "logo",
            "primary_color",
            "secondary_color",
        ]
        widgets = {
            "logo": forms.ClearableFileInput(
                attrs={
                    "class": (
                        "mt-1 block w-full text-sm text-gray-500 dark:text-gray-400 "
                        "file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 "
                        "file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 "
                        "hover:file:bg-blue-100 dark:file:bg-gray-700 dark:file:text-gray-300"
                    ),
                    "accept": "image/*",
                }
            ),
            "primary_color": forms.TextInput(
                attrs={
                    "class": (
                        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
                        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
                    ),
                    "type": "color",
                    "data-color-picker": "true",
                }
            ),
            "secondary_color": forms.TextInput(
                attrs={
                    "class": (
                        "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm "
                        "focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
                    ),
                    "type": "color",
                    "data-color-picker": "true",
                }
            ),
        }
        help_texts = {
            "logo": "Business logo for invoices and receipts (recommended: 200x200px, PNG or JPG)",
            "primary_color": "Primary brand color (hex format, e.g., #1f2937)",
            "secondary_color": "Secondary brand color (hex format)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Logo is optional
        self.fields["logo"].required = False

    def clean_primary_color(self):
        """Validate primary color is a valid hex color."""
        color = self.cleaned_data.get("primary_color", "")
        return self._validate_hex_color(color, "Primary color")

    def clean_secondary_color(self):
        """Validate secondary color is a valid hex color."""
        color = self.cleaned_data.get("secondary_color", "")
        return self._validate_hex_color(color, "Secondary color")

    def _validate_hex_color(self, color, field_name):
        """
        Validate that a color value is a valid hex color.

        Args:
            color: The color value to validate
            field_name: The name of the field for error messages

        Returns:
            The validated color value (normalized to lowercase)

        Raises:
            ValidationError: If the color is not a valid hex color
        """
        import re

        if not color:
            return color

        # Normalize to lowercase
        color = color.lower().strip()

        # Check if it's a valid hex color (with or without #)
        hex_pattern = r"^#?([a-f0-9]{6}|[a-f0-9]{3})$"

        if not re.match(hex_pattern, color):
            raise forms.ValidationError(
                f"{field_name} must be a valid hex color (e.g., #1f2937 or #fff)."
            )

        # Ensure it starts with #
        if not color.startswith("#"):
            color = f"#{color}"

        # Expand 3-character hex to 6-character
        if len(color) == 4:
            color = f"#{color[1]*2}{color[2]*2}{color[3]*2}"

        return color

    def clean_logo(self):
        """Validate logo file type and size."""
        logo = self.cleaned_data.get("logo")

        if logo and hasattr(logo, "content_type"):
            # Check file type
            allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
            if logo.content_type not in allowed_types:
                raise forms.ValidationError("Logo must be a JPEG, PNG, GIF, or WebP image.")

            # Check file size (max 2MB)
            max_size = 2 * 1024 * 1024  # 2MB
            if logo.size > max_size:
                raise forms.ValidationError("Logo file size must be less than 2MB.")

        return logo
