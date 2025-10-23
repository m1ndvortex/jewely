"""
Forms for procurement management.

This module contains forms for supplier management including
communication and document forms with proper tenant filtering.
"""

from django import forms
from django.contrib.auth import get_user_model

from .models import SupplierCommunication, SupplierDocument

User = get_user_model()


class SupplierCommunicationForm(forms.ModelForm):
    """Form for creating supplier communications."""

    class Meta:
        model = SupplierCommunication
        fields = [
            "communication_type",
            "subject",
            "content",
            "contact_person",
            "internal_participants",
            "requires_followup",
            "followup_date",
            "communication_date",
        ]
        widgets = {
            "communication_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "followup_date": forms.DateInput(attrs={"type": "date"}),
            "content": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        # Filter internal participants to current tenant
        if tenant:
            self.fields["internal_participants"].queryset = User.objects.filter(
                tenant=tenant, role__in=["TENANT_OWNER", "TENANT_MANAGER", "TENANT_EMPLOYEE"]
            )
        else:
            self.fields["internal_participants"].queryset = User.objects.none()


class SupplierDocumentForm(forms.ModelForm):
    """Form for uploading supplier documents."""

    class Meta:
        model = SupplierDocument
        fields = [
            "document_type",
            "title",
            "description",
            "file",
            "issue_date",
            "expiry_date",
        ]
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date"}),
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }
