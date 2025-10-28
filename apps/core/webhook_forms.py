"""
Forms for webhook management interface.

Per Requirement 32 - Webhook and Integration Management
"""

from django import forms

from .webhook_models import Webhook


class WebhookForm(forms.ModelForm):
    """
    Form for creating and editing webhooks.

    Requirement 32.1: Allow tenants to register webhook URLs for event notifications.
    Requirement 32.2: Allow tenants to select which events trigger webhooks.
    """

    # Event selection as checkboxes
    event_choices = forms.MultipleChoiceField(
        choices=Webhook.EVENT_CHOICES,
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"}
        ),
        required=True,
        label="Events to Subscribe",
        help_text="Select which events should trigger this webhook",
    )

    class Meta:
        model = Webhook
        fields = ["name", "url", "description", "is_active"]

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "e.g., Inventory Sync Webhook",
                    "required": True,
                }
            ),
            "url": forms.URLInput(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "https://example.com/webhooks/inventory",
                    "required": True,
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm",
                    "placeholder": "Optional description of what this webhook does",
                    "rows": 3,
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={"class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"}
            ),
        }

        labels = {
            "name": "Webhook Name",
            "url": "Webhook URL",
            "description": "Description",
            "is_active": "Active",
        }

        help_texts = {
            "name": "A descriptive name for this webhook",
            "url": "The endpoint URL that will receive webhook events",
            "description": "Optional notes about this webhook's purpose",
            "is_active": "Inactive webhooks will not receive events",
        }

    def __init__(self, *args, **kwargs):
        """
        Initialize form and populate event_choices from instance if editing.
        """
        super().__init__(*args, **kwargs)

        # If editing existing webhook, populate event_choices
        if self.instance and self.instance.pk:
            self.fields["event_choices"].initial = self.instance.events

    def clean_url(self):
        """
        Validate webhook URL.
        """
        url = self.cleaned_data.get("url")

        # Ensure URL uses HTTPS in production
        if url and not url.startswith(("https://", "http://")):
            raise forms.ValidationError("Webhook URL must start with http:// or https://")

        # TODO: In production, enforce HTTPS only
        # if url and not url.startswith("https://"):
        #     raise forms.ValidationError("Webhook URL must use HTTPS for security")

        return url

    def save(self, commit=True):
        """
        Save webhook with selected events.
        """
        webhook = super().save(commit=False)

        # Save selected events to JSONField
        webhook.events = self.cleaned_data.get("event_choices", [])

        if commit:
            webhook.save()

        return webhook

        if commit:
            webhook.save()

        return webhook


class WebhookTestForm(forms.Form):
    """
    Form for testing webhook delivery.

    Requirement 32.8: Provide webhook testing capability before activation.
    """

    event_type = forms.ChoiceField(
        choices=Webhook.EVENT_CHOICES,
        widget=forms.Select(
            attrs={
                "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm"
            }
        ),
        label="Event Type",
        help_text="Select an event type to test",
    )

    test_payload = forms.JSONField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white sm:text-sm font-mono",
                "placeholder": '{\n  "id": "test-123",\n  "name": "Test Item"\n}',
                "rows": 10,
            }
        ),
        label="Test Payload (Optional)",
        help_text="Provide a custom JSON payload, or leave empty to use a default test payload",
    )

    def clean_test_payload(self):
        """
        Validate JSON payload if provided.
        """
        payload = self.cleaned_data.get("test_payload")

        if payload:
            # JSONField already validates JSON format
            # Additional validation can be added here if needed
            pass

        return payload
