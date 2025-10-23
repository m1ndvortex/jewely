"""
Forms for repair order management.

This module contains forms for creating and managing repair orders,
including photo uploads and status updates.
"""

from datetime import date, timedelta

from django import forms
from django.core.exceptions import ValidationError

from .models import CustomOrder, RepairOrder, RepairOrderPhoto


class RepairOrderForm(forms.ModelForm):
    """
    Form for creating and editing repair orders.

    Includes validation for dates and cost estimates.
    """

    class Meta:
        model = RepairOrder
        fields = [
            "customer",
            "item_description",
            "service_type",
            "service_notes",
            "priority",
            "estimated_completion",
            "cost_estimate",
            "assigned_to",
        ]
        widgets = {
            "item_description": forms.Textarea(
                attrs={
                    "rows": 4,
                    "class": "form-control",
                    "placeholder": "Describe the item and any visible damage or issues...",
                }
            ),
            "service_notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "form-control",
                    "placeholder": "Additional notes about the service required...",
                }
            ),
            "estimated_completion": forms.DateInput(
                attrs={"type": "date", "class": "form-control", "min": date.today().isoformat()}
            ),
            "cost_estimate": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "customer": forms.Select(attrs={"class": "form-control"}),
            "service_type": forms.Select(attrs={"class": "form-control"}),
            "priority": forms.Select(attrs={"class": "form-control"}),
            "assigned_to": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        # Filter customers and staff by tenant
        if self.tenant:
            from django.contrib.auth import get_user_model

            from apps.crm.models import Customer

            User = get_user_model()

            self.fields["customer"].queryset = Customer.objects.filter(tenant=self.tenant)
            self.fields["assigned_to"].queryset = User.objects.filter(
                tenant=self.tenant, role__in=["TENANT_OWNER", "TENANT_MANAGER", "TENANT_EMPLOYEE"]
            )

        # Set default estimated completion to 7 days from now
        if not self.instance.pk:
            self.fields["estimated_completion"].initial = date.today() + timedelta(days=7)

    def clean_estimated_completion(self):
        """Validate that estimated completion is not in the past."""
        estimated_completion = self.cleaned_data.get("estimated_completion")
        if estimated_completion and estimated_completion < date.today():
            raise ValidationError("Estimated completion date cannot be in the past.")
        return estimated_completion

    def clean_cost_estimate(self):
        """Validate that cost estimate is positive."""
        cost_estimate = self.cleaned_data.get("cost_estimate")
        if cost_estimate and cost_estimate <= 0:
            raise ValidationError("Cost estimate must be greater than zero.")
        return cost_estimate


class RepairOrderPhotoForm(forms.ModelForm):
    """
    Form for uploading photos to repair orders.

    Supports multiple photo types with descriptions.
    """

    class Meta:
        model = RepairOrderPhoto
        fields = ["photo", "photo_type", "description"]
        widgets = {
            "photo": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "photo_type": forms.Select(attrs={"class": "form-control"}),
            "description": forms.Textarea(
                attrs={
                    "rows": 2,
                    "class": "form-control",
                    "placeholder": "Optional description of the photo...",
                }
            ),
        }

    def clean_photo(self):
        """Validate photo file size and type."""
        photo = self.cleaned_data.get("photo")
        if photo:
            # Check file size (max 10MB)
            if photo.size > 10 * 1024 * 1024:
                raise ValidationError("Photo file size cannot exceed 10MB.")

            # Check file type
            if not photo.content_type.startswith("image/"):
                raise ValidationError("File must be an image.")

        return photo


class RepairOrderStatusForm(forms.ModelForm):
    """
    Form for updating repair order status and related fields.

    Used by staff to update progress and completion details.
    """

    class Meta:
        model = RepairOrder
        fields = ["status", "assigned_to", "final_cost", "service_notes"]
        widgets = {
            "status": forms.Select(attrs={"class": "form-control"}),
            "assigned_to": forms.Select(attrs={"class": "form-control"}),
            "final_cost": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "service_notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "form-control",
                    "placeholder": "Update notes about the repair progress...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        # Filter staff by tenant
        if self.tenant:
            from django.contrib.auth import get_user_model

            User = get_user_model()

            self.fields["assigned_to"].queryset = User.objects.filter(
                tenant=self.tenant, role__in=["TENANT_OWNER", "TENANT_MANAGER", "TENANT_EMPLOYEE"]
            )

    def clean_final_cost(self):
        """Validate final cost if provided."""
        final_cost = self.cleaned_data.get("final_cost")
        if final_cost and final_cost <= 0:
            raise ValidationError("Final cost must be greater than zero.")
        return final_cost


class CustomOrderForm(forms.ModelForm):
    """
    Form for creating and editing custom orders.

    Handles design specifications and pricing details.
    """

    class Meta:
        model = CustomOrder
        fields = [
            "customer",
            "design_description",
            "complexity",
            "estimated_completion",
            "quoted_price",
            "deposit_amount",
            "designer",
            "craftsman",
        ]
        widgets = {
            "design_description": forms.Textarea(
                attrs={
                    "rows": 5,
                    "class": "form-control",
                    "placeholder": "Detailed description of the custom design...",
                }
            ),
            "complexity": forms.Select(attrs={"class": "form-control"}),
            "estimated_completion": forms.DateInput(
                attrs={"type": "date", "class": "form-control", "min": date.today().isoformat()}
            ),
            "quoted_price": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "deposit_amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "customer": forms.Select(attrs={"class": "form-control"}),
            "designer": forms.Select(attrs={"class": "form-control"}),
            "craftsman": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        # Filter customers and staff by tenant
        if self.tenant:
            from django.contrib.auth import get_user_model

            from apps.crm.models import Customer

            User = get_user_model()

            self.fields["customer"].queryset = Customer.objects.filter(tenant=self.tenant)
            staff_queryset = User.objects.filter(
                tenant=self.tenant, role__in=["TENANT_OWNER", "TENANT_MANAGER", "TENANT_EMPLOYEE"]
            )
            self.fields["designer"].queryset = staff_queryset
            self.fields["craftsman"].queryset = staff_queryset

    def clean_deposit_amount(self):
        """Validate that deposit doesn't exceed quoted price."""
        deposit_amount = self.cleaned_data.get("deposit_amount")
        quoted_price = self.cleaned_data.get("quoted_price")

        if deposit_amount and quoted_price and deposit_amount > quoted_price:
            raise ValidationError("Deposit amount cannot exceed quoted price.")

        return deposit_amount


class WorkOrderForm(forms.Form):
    """
    Form for generating work orders for craftsmen.

    Allows selection of repair orders to include in work order.
    """

    repair_orders = forms.ModelMultipleChoiceField(
        queryset=RepairOrder.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        required=True,
        help_text="Select repair orders to include in this work order",
    )

    craftsman = forms.ModelChoiceField(
        queryset=None,
        widget=forms.Select(attrs={"class": "form-control"}),
        required=True,
        help_text="Craftsman to assign these repairs to",
    )

    notes = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "form-control",
                "placeholder": "Additional instructions for the craftsman...",
            }
        ),
        required=False,
        help_text="Optional notes or special instructions",
    )

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if tenant:
            from django.contrib.auth import get_user_model

            User = get_user_model()

            # Only show repair orders that are ready for work
            self.fields["repair_orders"].queryset = RepairOrder.objects.filter(
                tenant=tenant, status__in=["received", "in_progress"]
            ).select_related("customer")

            # Only show staff members
            self.fields["craftsman"].queryset = User.objects.filter(
                tenant=tenant, role__in=["TENANT_OWNER", "TENANT_MANAGER", "TENANT_EMPLOYEE"]
            )
