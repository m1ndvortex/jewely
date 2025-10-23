"""
Forms for procurement management.

This module contains forms for supplier management including
communication and document forms with proper tenant filtering.
"""

from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import (
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseOrder,
    PurchaseOrderItem,
    SupplierCommunication,
    SupplierDocument,
)

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


class PurchaseOrderForm(forms.ModelForm):
    """Form for creating and editing purchase orders."""

    class Meta:
        model = PurchaseOrder
        fields = [
            "supplier",
            "priority",
            "expected_delivery",
            "branch",
            "notes",
            "supplier_reference",
        ]
        widgets = {
            "expected_delivery": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if tenant:
            # Filter suppliers and branches to current tenant
            self.fields["supplier"].queryset = tenant.suppliers.filter(is_active=True)
            self.fields["branch"].queryset = tenant.branches.filter(is_active=True)
        else:
            self.fields["supplier"].queryset = self.fields["supplier"].queryset.none()
            self.fields["branch"].queryset = self.fields["branch"].queryset.none()

        # Make branch optional
        self.fields["branch"].required = False

    def clean_expected_delivery(self):
        """Validate that expected delivery is in the future."""
        expected_delivery = self.cleaned_data.get("expected_delivery")
        if expected_delivery:
            from django.utils import timezone

            if expected_delivery <= timezone.now().date():
                raise ValidationError("Expected delivery date must be in the future.")
        return expected_delivery


class PurchaseOrderItemForm(forms.ModelForm):
    """Form for purchase order line items."""

    class Meta:
        model = PurchaseOrderItem
        fields = [
            "product_name",
            "product_sku",
            "quantity",
            "unit_price",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
            "unit_price": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "quantity": forms.NumberInput(attrs={"min": "1"}),
        }

    def clean_quantity(self):
        """Validate quantity is positive."""
        quantity = self.cleaned_data.get("quantity")
        if quantity and quantity <= 0:
            raise ValidationError("Quantity must be greater than zero.")
        return quantity

    def clean_unit_price(self):
        """Validate unit price is positive."""
        unit_price = self.cleaned_data.get("unit_price")
        if unit_price and unit_price <= Decimal("0.00"):
            raise ValidationError("Unit price must be greater than zero.")
        return unit_price


# Formset for handling multiple purchase order items
PurchaseOrderItemFormSet = forms.inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderItem,
    form=PurchaseOrderItemForm,
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True,
)


class PurchaseOrderApprovalForm(forms.Form):
    """Form for approving purchase orders."""

    approval_notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Optional approval notes..."}),
        required=False,
        help_text="Optional notes about the approval decision",
    )

    def __init__(self, *args, **kwargs):
        self.purchase_order = kwargs.pop("purchase_order", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        """Validate that the purchase order can be approved."""
        cleaned_data = super().clean()
        if self.purchase_order and self.purchase_order.status != "DRAFT":
            raise ValidationError("Only draft purchase orders can be approved.")
        return cleaned_data


class PurchaseOrderSendForm(forms.Form):
    """Form for sending purchase orders to suppliers."""

    SEND_METHODS = [
        ("EMAIL", "Send via Email"),
        ("PRINT", "Generate PDF for Printing"),
        ("BOTH", "Email and Print"),
    ]

    send_method = forms.ChoiceField(
        choices=SEND_METHODS,
        widget=forms.RadioSelect,
        initial="EMAIL",
        help_text="Choose how to send the purchase order to the supplier",
    )

    email_subject = forms.CharField(
        max_length=255,
        initial="Purchase Order from {company_name}",
        help_text="Email subject line (use {company_name} and {po_number} as placeholders)",
    )

    email_message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 5}),
        initial="""Dear {supplier_name},

Please find attached our purchase order #{po_number}.

Expected delivery date: {expected_delivery}
Total amount: {total_amount}

Please confirm receipt and provide your estimated delivery schedule.

Best regards,
{company_name}""",
        help_text="Email message body (use placeholders: {supplier_name}, {po_number}, {expected_delivery}, {total_amount}, {company_name})",
    )

    include_terms = forms.BooleanField(
        initial=True,
        required=False,
        help_text="Include standard terms and conditions in the purchase order",
    )

    def __init__(self, *args, **kwargs):
        self.purchase_order = kwargs.pop("purchase_order", None)
        super().__init__(*args, **kwargs)

        if self.purchase_order:
            # Pre-populate email fields with PO data
            self.fields["email_subject"].initial = self.fields["email_subject"].initial.format(
                company_name=self.purchase_order.tenant.company_name
            )

    def clean(self):
        """Validate that the purchase order can be sent."""
        cleaned_data = super().clean()
        if self.purchase_order and self.purchase_order.status != "APPROVED":
            raise ValidationError("Only approved purchase orders can be sent.")
        return cleaned_data


class GoodsReceiptForm(forms.ModelForm):
    """Form for creating goods receipts."""

    class Meta:
        model = GoodsReceipt
        fields = [
            "purchase_order",
            "supplier_invoice_number",
            "tracking_number",
            "received_date",
            "inspection_notes",
        ]
        widgets = {
            "received_date": forms.DateInput(attrs={"type": "date"}),
            "inspection_notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if tenant:
            # Filter purchase orders to current tenant and only sent/partially received orders
            self.fields["purchase_order"].queryset = PurchaseOrder.objects.filter(
                tenant=tenant, status__in=["SENT", "PARTIALLY_RECEIVED"]
            )
        else:
            self.fields["purchase_order"].queryset = PurchaseOrder.objects.none()

    def clean_received_date(self):
        """Validate that received date is not in the future."""
        received_date = self.cleaned_data.get("received_date")
        if received_date:
            from django.utils import timezone

            if received_date > timezone.now().date():
                raise ValidationError("Received date cannot be in the future.")
        return received_date


class GoodsReceiptItemForm(forms.ModelForm):
    """Form for goods receipt line items."""

    class Meta:
        model = GoodsReceiptItem
        fields = [
            "purchase_order_item",
            "quantity_received",
            "quantity_rejected",
            "quality_check_passed",
            "quality_notes",
            "discrepancy_reason",
        ]
        widgets = {
            "quality_notes": forms.Textarea(attrs={"rows": 2}),
            "quantity_received": forms.NumberInput(attrs={"min": "0"}),
            "quantity_rejected": forms.NumberInput(attrs={"min": "0", "value": "0"}),
        }

    def __init__(self, *args, **kwargs):
        purchase_order = kwargs.pop("purchase_order", None)
        super().__init__(*args, **kwargs)

        if purchase_order:
            # Filter to items from the selected purchase order
            self.fields["purchase_order_item"].queryset = purchase_order.items.all()
        else:
            self.fields["purchase_order_item"].queryset = PurchaseOrderItem.objects.none()

        # Make some fields optional initially
        self.fields["quality_check_passed"].required = False
        self.fields["quality_notes"].required = False
        self.fields["discrepancy_reason"].required = False

    def clean(self):
        """Validate quantities and quality check."""
        cleaned_data = super().clean()
        quantity_received = cleaned_data.get("quantity_received", 0)
        quantity_rejected = cleaned_data.get("quantity_rejected", 0)
        purchase_order_item = cleaned_data.get("purchase_order_item")

        # Validate that rejected quantity doesn't exceed received quantity
        if quantity_rejected > quantity_received:
            raise ValidationError("Rejected quantity cannot exceed received quantity.")

        # Validate that we don't receive more than ordered
        if purchase_order_item and quantity_received > purchase_order_item.remaining_quantity:
            raise ValidationError(
                f"Cannot receive more than remaining quantity. "
                f"Remaining: {purchase_order_item.remaining_quantity}, "
                f"Trying to receive: {quantity_received}"
            )

        # If quality check failed, require quality notes
        quality_check_passed = cleaned_data.get("quality_check_passed")
        quality_notes = cleaned_data.get("quality_notes")
        if quality_check_passed is False and not quality_notes:
            raise ValidationError("Quality notes are required when quality check fails.")

        # If there are rejected items, require discrepancy reason
        discrepancy_reason = cleaned_data.get("discrepancy_reason")
        if quantity_rejected > 0 and not discrepancy_reason:
            raise ValidationError("Discrepancy reason is required when rejecting items.")

        return cleaned_data


# Formset for handling multiple goods receipt items
GoodsReceiptItemFormSet = forms.inlineformset_factory(
    GoodsReceipt,
    GoodsReceiptItem,
    form=GoodsReceiptItemForm,
    extra=0,
    min_num=1,
    validate_min=True,
    can_delete=False,
)
