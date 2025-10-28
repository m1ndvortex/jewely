"""
Forms for external service integration management.

Per Requirement 32.9: Manage API keys for external services
Per Requirement 32.10: Support OAuth2 for third-party service connections
"""

from django import forms

from .integration_models import ExternalService


class ExternalServiceForm(forms.ModelForm):
    """
    Form for creating and editing external service integrations.

    Requirement 32.9: Manage API keys for external services including
    payment gateways and SMS providers.
    """

    class Meta:
        model = ExternalService
        fields = [
            "name",
            "service_type",
            "provider_name",
            "description",
            "auth_type",
            "api_key",
            "api_secret",
            "base_url",
            "is_active",
            "is_test_mode",
        ]

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "e.g., Stripe Payment Gateway",
                    "required": True,
                }
            ),
            "service_type": forms.Select(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
                }
            ),
            "provider_name": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "e.g., Stripe, Twilio, SendGrid",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "Optional description of this integration",
                    "rows": 3,
                }
            ),
            "auth_type": forms.Select(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
                }
            ),
            "api_key": forms.PasswordInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm font-mono",
                    "placeholder": "Enter API key or client ID",
                }
            ),
            "api_secret": forms.PasswordInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm font-mono",
                    "placeholder": "Enter API secret or client secret",
                }
            ),
            "base_url": forms.URLInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "https://api.example.com",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={"class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"}
            ),
            "is_test_mode": forms.CheckboxInput(
                attrs={"class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"}
            ),
        }

        labels = {
            "name": "Service Name",
            "service_type": "Service Type",
            "provider_name": "Provider Name",
            "description": "Description",
            "auth_type": "Authentication Type",
            "api_key": "API Key / Client ID",
            "api_secret": "API Secret / Client Secret",
            "base_url": "Base URL",
            "is_active": "Active",
            "is_test_mode": "Test Mode",
        }

        help_texts = {
            "name": "A descriptive name for this service integration",
            "service_type": "Type of external service",
            "provider_name": "Name of the service provider (e.g., Stripe, Twilio)",
            "description": "Optional notes about this integration",
            "auth_type": "Authentication method used by this service",
            "api_key": "API key or client ID (will be encrypted)",
            "api_secret": "API secret or client secret (will be encrypted)",
            "base_url": "Base URL for API endpoints",
            "is_active": "Inactive services will not be used",
            "is_test_mode": "Use test/sandbox mode for this service",
        }

    def __init__(self, *args, **kwargs):
        """
        Initialize form and handle password field rendering.
        """
        super().__init__(*args, **kwargs)

        # If editing existing service, show placeholder for credentials
        if self.instance and self.instance.pk:
            if self.instance.api_key:
                self.fields["api_key"].widget.attrs["placeholder"] = "••••••••••••••••"
                self.fields["api_key"].required = False
            if self.instance.api_secret:
                self.fields["api_secret"].widget.attrs["placeholder"] = "••••••••••••••••"
                self.fields["api_secret"].required = False

    def clean_base_url(self):
        """
        Validate base URL format.
        """
        base_url = self.cleaned_data.get("base_url")

        if base_url and not base_url.startswith(("https://", "http://")):
            raise forms.ValidationError("Base URL must start with http:// or https://")

        return base_url

    def save(self, commit=True):
        """
        Save service, preserving existing credentials if not changed.
        """
        service = super().save(commit=False)

        # If editing and credentials are empty, preserve existing values
        if self.instance and self.instance.pk:
            if not self.cleaned_data.get("api_key"):
                service.api_key = self.instance.api_key
            if not self.cleaned_data.get("api_secret"):
                service.api_secret = self.instance.api_secret

        if commit:
            service.save()

        return service


class ServiceHealthCheckForm(forms.Form):
    """
    Form for manually triggering a health check.
    """

    service_id = forms.UUIDField(
        widget=forms.HiddenInput(),
        required=True,
    )


class OAuth2AuthorizationForm(forms.Form):
    """
    Form for initiating OAuth2 authorization flow.

    Requirement 32.10: Support OAuth2 for third-party service connections.
    """

    service_id = forms.UUIDField(
        widget=forms.HiddenInput(),
        required=True,
    )

    redirect_uri = forms.URLField(
        widget=forms.HiddenInput(),
        required=True,
    )

    scope = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                "placeholder": "e.g., read write",
                "rows": 2,
            }
        ),
        required=False,
        label="OAuth2 Scopes",
        help_text="Space-separated list of OAuth2 scopes to request",
    )


class OAuth2CallbackForm(forms.Form):
    """
    Form for handling OAuth2 callback.
    """

    code = forms.CharField(
        required=True,
        widget=forms.HiddenInput(),
    )

    state = forms.CharField(
        required=True,
        widget=forms.HiddenInput(),
    )
