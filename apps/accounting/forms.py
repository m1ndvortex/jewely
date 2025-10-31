"""
Forms for accounting module.

This module provides forms for manual journal entry creation and management.
"""

from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory

from django_ledger.models import AccountModel, JournalEntryModel, TransactionModel


class JournalEntryForm(forms.ModelForm):
    """
    Form for creating manual journal entries.

    Includes description, date, and reference fields.
    """

    description = forms.CharField(
        max_length=500,
        required=True,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "Enter journal entry description...",
            }
        ),
        help_text="Provide a clear description of this journal entry",
    )

    date = forms.DateField(
        required=True,
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
            }
        ),
        help_text="Transaction date",
    )

    reference = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "Reference number (optional)",
            }
        ),
        help_text="Optional reference number or document ID",
    )

    class Meta:
        model = JournalEntryModel
        fields = ["description", "date"]

    class Media:
        js = ("js/journal_entry_validation.js",)

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Set initial date to today if not provided
        if not self.instance.pk and "date" not in self.initial:
            from datetime import date

            self.initial["date"] = date.today()


class JournalEntryLineForm(forms.ModelForm):
    """
    Form for individual journal entry line items.

    Includes account, debit, credit, and description fields.
    """

    account = forms.ModelChoiceField(
        queryset=AccountModel.objects.none(),
        required=True,
        widget=forms.Select(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 account-select"
            }
        ),
        help_text="Select the account for this line",
    )

    debit = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        initial=Decimal("0.00"),
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 debit-input",
                "placeholder": "0.00",
                "step": "0.01",
                "min": "0",
            }
        ),
        help_text="Debit amount",
    )

    credit = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        initial=Decimal("0.00"),
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 credit-input",
                "placeholder": "0.00",
                "step": "0.01",
                "min": "0",
            }
        ),
        help_text="Credit amount",
    )

    description = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "Line description (optional)",
            }
        ),
        help_text="Optional description for this line",
    )

    class Meta:
        model = TransactionModel
        fields = ["account", "description"]

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        self.coa = kwargs.pop("coa", None)
        super().__init__(*args, **kwargs)

        # Filter accounts by chart of accounts (tenant-specific)
        if self.coa:
            self.fields["account"].queryset = AccountModel.objects.filter(
                coa_model=self.coa, active=True
            ).order_by("code", "name")

            # Update the label to show code and name
            self.fields["account"].label_from_instance = lambda obj: f"{obj.code} - {obj.name}"

    def clean(self):
        """
        Validate that either debit or credit is provided, but not both.
        """
        cleaned_data = super().clean()
        debit = cleaned_data.get("debit") or Decimal("0.00")
        credit = cleaned_data.get("credit") or Decimal("0.00")

        # Ensure at least one is non-zero
        if debit == Decimal("0.00") and credit == Decimal("0.00"):
            raise ValidationError("Either debit or credit must be greater than zero.")

        # Ensure both are not non-zero
        if debit > Decimal("0.00") and credit > Decimal("0.00"):
            raise ValidationError("A line cannot have both debit and credit amounts.")

        # Ensure amounts are positive
        if debit < Decimal("0.00") or credit < Decimal("0.00"):
            raise ValidationError("Amounts must be positive.")

        return cleaned_data


class JournalEntryLineFormSet(BaseInlineFormSet):
    """
    Formset for managing multiple journal entry lines.

    Validates that total debits equal total credits.
    """

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        self.coa = kwargs.pop("coa", None)
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        """
        Pass tenant and coa to each form instance.
        """
        kwargs["tenant"] = self.tenant
        kwargs["coa"] = self.coa
        return super()._construct_form(i, **kwargs)

    def clean(self):
        """
        Validate that total debits equal total credits.

        This is the core double-entry bookkeeping validation.
        """
        if any(self.errors):
            # Don't validate if there are already errors in individual forms
            return

        total_debits = Decimal("0.00")
        total_credits = Decimal("0.00")
        valid_lines = 0

        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                debit = form.cleaned_data.get("debit") or Decimal("0.00")
                credit = form.cleaned_data.get("credit") or Decimal("0.00")

                total_debits += debit
                total_credits += credit
                valid_lines += 1

        # Ensure at least 2 lines (minimum for a journal entry)
        if valid_lines < 2:
            raise ValidationError(
                "A journal entry must have at least 2 lines (one debit and one credit)."
            )

        # Validate that debits equal credits
        if total_debits != total_credits:
            raise ValidationError(
                f"Total debits (${total_debits:,.2f}) must equal total credits (${total_credits:,.2f}). "
                f"Difference: ${abs(total_debits - total_credits):,.2f}"
            )

        # Ensure total is not zero
        if total_debits == Decimal("0.00"):
            raise ValidationError("Journal entry cannot have zero total.")


# Factory for creating the inline formset
JournalEntryLineInlineFormSet = inlineformset_factory(
    JournalEntryModel,
    TransactionModel,
    form=JournalEntryLineForm,
    formset=JournalEntryLineFormSet,
    extra=4,  # Show 4 empty forms by default
    min_num=2,  # Require at least 2 lines
    validate_min=True,
    can_delete=True,
    fields=["account", "description"],
)
