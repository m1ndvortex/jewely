"""
Forms for core app settings and configuration.
"""

from django import forms

from .models import InvoiceSettings, TenantSettings


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
