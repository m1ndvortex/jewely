"""
Forms for announcement and communication management.

Per Requirement 31 - Communication and Announcement System
"""

from django import forms
from django.utils import timezone

from apps.core.announcement_models import Announcement, CommunicationTemplate, DirectMessage
from apps.core.models import SubscriptionPlan, Tenant


class AnnouncementForm(forms.ModelForm):
    """
    Form for creating and editing announcements.

    Requirement 31.1: Create platform-wide announcements.
    Requirement 31.2: Schedule announcements for future delivery.
    Requirement 31.3: Target specific tenant segments.
    Requirement 31.4: Deliver via multiple channels.
    """

    # Channel selection
    channel_in_app = forms.BooleanField(
        required=False,
        initial=True,
        label="In-App Banner",
        help_text="Display as banner in tenant interface",
    )
    channel_email = forms.BooleanField(
        required=False,
        initial=False,
        label="Email",
        help_text="Send via email to tenant owners",
    )
    channel_sms = forms.BooleanField(
        required=False,
        initial=False,
        label="SMS",
        help_text="Send via SMS to tenant owners",
    )

    # Targeting options
    target_plans = forms.ModelMultipleChoiceField(
        queryset=SubscriptionPlan.objects.filter(status=SubscriptionPlan.STATUS_ACTIVE),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Target Subscription Plans",
        help_text="Leave empty to target all plans",
    )

    target_statuses = forms.MultipleChoiceField(
        choices=Tenant.STATUS_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Target Tenant Statuses",
        help_text="Leave empty to target only active tenants",
    )

    # Scheduling
    schedule_for_later = forms.BooleanField(
        required=False,
        initial=False,
        label="Schedule for Later",
        help_text="Schedule this announcement for future delivery",
    )

    class Meta:
        model = Announcement
        fields = [
            "title",
            "message",
            "severity",
            "target_all_tenants",
            "scheduled_at",
            "requires_acknowledgment",
            "is_dismissible",
            "display_until",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter announcement title",
                }
            ),
            "message": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": "Enter announcement message",
                }
            ),
            "severity": forms.Select(attrs={"class": "form-control"}),
            "scheduled_at": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                }
            ),
            "display_until": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # If editing existing announcement, populate channel checkboxes
        if self.instance and self.instance.pk:
            channels = self.instance.channels or []
            self.fields["channel_in_app"].initial = "in_app" in channels
            self.fields["channel_email"].initial = "email" in channels
            self.fields["channel_sms"].initial = "sms" in channels

            # Populate targeting fields
            if not self.instance.target_all_tenants and self.instance.target_filter:
                target_filter = self.instance.target_filter

                # Set plan targeting
                if "plans" in target_filter and target_filter["plans"]:
                    plan_names = target_filter["plans"]
                    self.fields["target_plans"].initial = SubscriptionPlan.objects.filter(
                        name__in=plan_names
                    )

                # Set status targeting
                if "statuses" in target_filter and target_filter["statuses"]:
                    self.fields["target_statuses"].initial = target_filter["statuses"]

            # Set schedule checkbox
            if self.instance.scheduled_at:
                self.fields["schedule_for_later"].initial = True

        # Make scheduled_at not required initially
        self.fields["scheduled_at"].required = False
        self.fields["display_until"].required = False

    def clean(self):
        cleaned_data = super().clean()

        # Validate at least one channel is selected
        channel_in_app = cleaned_data.get("channel_in_app")
        channel_email = cleaned_data.get("channel_email")
        channel_sms = cleaned_data.get("channel_sms")

        if not any([channel_in_app, channel_email, channel_sms]):
            raise forms.ValidationError("Please select at least one delivery channel.")

        # Validate scheduled_at if schedule_for_later is checked
        schedule_for_later = cleaned_data.get("schedule_for_later")
        scheduled_at = cleaned_data.get("scheduled_at")

        if schedule_for_later and not scheduled_at:
            raise forms.ValidationError("Please specify a scheduled time for future delivery.")

        if scheduled_at and scheduled_at <= timezone.now():
            raise forms.ValidationError("Scheduled time must be in the future.")

        # Validate display_until is after scheduled_at
        display_until = cleaned_data.get("display_until")
        if display_until and scheduled_at and display_until <= scheduled_at:
            raise forms.ValidationError("Display until time must be after scheduled time.")

        return cleaned_data

    def _build_channels(self):
        """Build channels list from form data."""
        channels = []
        if self.cleaned_data.get("channel_in_app"):
            channels.append("in_app")
        if self.cleaned_data.get("channel_email"):
            channels.append("email")
        if self.cleaned_data.get("channel_sms"):
            channels.append("sms")
        return channels

    def _build_target_filter(self):
        """Build target filter from form data."""
        target_filter = {}

        # Add plan targeting
        target_plans = self.cleaned_data.get("target_plans")
        if target_plans:
            target_filter["plans"] = [plan.name for plan in target_plans]

        # Add status targeting
        target_statuses = self.cleaned_data.get("target_statuses")
        if target_statuses:
            target_filter["statuses"] = target_statuses

        return target_filter

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Build channels list
        instance.channels = self._build_channels()

        # Build target_filter
        if not instance.target_all_tenants:
            instance.target_filter = self._build_target_filter()
        else:
            instance.target_filter = {}

        # Set status based on scheduling
        if self.cleaned_data.get("schedule_for_later") and self.cleaned_data.get("scheduled_at"):
            instance.status = Announcement.SCHEDULED
        elif not instance.pk:  # New announcement
            instance.status = Announcement.DRAFT

        # Clear scheduled_at if not scheduling
        if not self.cleaned_data.get("schedule_for_later"):
            instance.scheduled_at = None

        if commit:
            instance.save()

        return instance


class DirectMessageForm(forms.ModelForm):
    """
    Form for creating direct messages to specific tenants.

    Requirement 31.8: Send direct messages to specific tenants.
    """

    # Channel selection
    channel_email = forms.BooleanField(
        required=False,
        initial=True,
        label="Email",
        help_text="Send via email",
    )
    channel_sms = forms.BooleanField(
        required=False,
        initial=False,
        label="SMS",
        help_text="Send via SMS",
    )
    channel_in_app = forms.BooleanField(
        required=False,
        initial=True,
        label="In-App Notification",
        help_text="Create in-app notification",
    )

    class Meta:
        model = DirectMessage
        fields = [
            "tenant",
            "subject",
            "message",
        ]
        widgets = {
            "tenant": forms.Select(attrs={"class": "form-control"}),
            "subject": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter message subject",
                }
            ),
            "message": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": "Enter message content",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # If editing existing message, populate channel checkboxes
        if self.instance and self.instance.pk:
            channels = self.instance.channels or []
            self.fields["channel_email"].initial = "email" in channels
            self.fields["channel_sms"].initial = "sms" in channels
            self.fields["channel_in_app"].initial = "in_app" in channels

    def clean(self):
        cleaned_data = super().clean()

        # Validate at least one channel is selected
        channel_email = cleaned_data.get("channel_email")
        channel_sms = cleaned_data.get("channel_sms")
        channel_in_app = cleaned_data.get("channel_in_app")

        if not any([channel_email, channel_sms, channel_in_app]):
            raise forms.ValidationError("Please select at least one delivery channel.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Build channels list
        channels = []
        if self.cleaned_data.get("channel_email"):
            channels.append("email")
        if self.cleaned_data.get("channel_sms"):
            channels.append("sms")
        if self.cleaned_data.get("channel_in_app"):
            channels.append("in_app")
        instance.channels = channels

        # Set status to draft if new
        if not instance.pk:
            instance.status = DirectMessage.DRAFT

        if commit:
            instance.save()

        return instance


class CommunicationTemplateForm(forms.ModelForm):
    """
    Form for creating and editing communication templates.

    Requirement 31.9: Provide communication templates.
    """

    # Default channel selection
    default_channel_in_app = forms.BooleanField(
        required=False,
        initial=True,
        label="In-App Banner",
    )
    default_channel_email = forms.BooleanField(
        required=False,
        initial=False,
        label="Email",
    )
    default_channel_sms = forms.BooleanField(
        required=False,
        initial=False,
        label="SMS",
    )

    class Meta:
        model = CommunicationTemplate
        fields = [
            "name",
            "template_type",
            "subject",
            "message",
            "default_severity",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter template name",
                }
            ),
            "template_type": forms.Select(attrs={"class": "form-control"}),
            "subject": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter subject template (use {{variable}} for placeholders)",
                }
            ),
            "message": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 8,
                    "placeholder": "Enter message template (use {{variable}} for placeholders)",
                }
            ),
            "default_severity": forms.Select(attrs={"class": "form-control"}),
        }
        help_texts = {
            "subject": "Use {{variable_name}} for dynamic content (e.g., {{tenant_name}}, {{date}})",
            "message": "Use {{variable_name}} for dynamic content (e.g., {{tenant_name}}, {{date}}, {{time}})",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # If editing existing template, populate channel checkboxes
        if self.instance and self.instance.pk:
            channels = self.instance.default_channels or []
            self.fields["default_channel_in_app"].initial = "in_app" in channels
            self.fields["default_channel_email"].initial = "email" in channels
            self.fields["default_channel_sms"].initial = "sms" in channels

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Build default channels list
        channels = []
        if self.cleaned_data.get("default_channel_in_app"):
            channels.append("in_app")
        if self.cleaned_data.get("default_channel_email"):
            channels.append("email")
        if self.cleaned_data.get("default_channel_sms"):
            channels.append("sms")
        instance.default_channels = channels

        if commit:
            instance.save()

        return instance


class AnnouncementFilterForm(forms.Form):
    """Form for filtering announcements in list view."""

    status = forms.ChoiceField(
        choices=[("", "All Statuses")] + list(Announcement.STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    severity = forms.ChoiceField(
        choices=[("", "All Severities")] + list(Announcement.SEVERITY_CHOICES),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "date",
            }
        ),
        label="From Date",
    )

    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "date",
            }
        ),
        label="To Date",
    )

    search = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Search title or message...",
            }
        ),
    )
