"""
Forms for accounting module.

This module provides forms for manual journal entry creation and management.
"""

from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.forms import BaseInlineFormSet, inlineformset_factory

from django_ledger.models import AccountModel, JournalEntryModel, TransactionModel

from .bill_models import Bill, BillLine


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


# ============================================================================
# Bill Management Forms (Task 2.5)
# ============================================================================


class BillForm(forms.ModelForm):
    """
    Form for creating and editing supplier bills.

    Includes supplier selection, dates, and financial information.
    Line items are handled by BillLineFormSet.

    Requirements: 2.1, 2.7
    """

    supplier = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=True,
        widget=forms.Select(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
            }
        ),
        help_text="Select the supplier for this bill",
    )

    bill_number = forms.CharField(
        max_length=50,
        required=False,  # Auto-generated if not provided
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "Auto-generated if left blank",
            }
        ),
        help_text="Bill/invoice number from supplier (auto-generated if blank)",
    )

    bill_date = forms.DateField(
        required=True,
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
            }
        ),
        help_text="Date when bill was issued",
    )

    due_date = forms.DateField(
        required=True,
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
            }
        ),
        help_text="Date when payment is due",
    )

    tax = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        initial=Decimal("0.00"),
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "0.00",
                "step": "0.01",
                "min": "0",
            }
        ),
        help_text="Tax amount",
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "Internal notes about this bill...",
            }
        ),
        help_text="Internal notes (not visible to supplier)",
    )

    reference_number = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "Additional reference number",
            }
        ),
        help_text="Additional reference number (optional)",
    )

    class Meta:
        from .bill_models import Bill

        model = Bill
        fields = [
            "supplier",
            "bill_number",
            "bill_date",
            "due_date",
            "tax",
            "notes",
            "reference_number",
        ]

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Filter suppliers by tenant
        if self.tenant:
            from apps.procurement.models import Supplier

            self.fields["supplier"].queryset = Supplier.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("name")

        # Set initial dates if creating new bill
        if not self.instance.pk:
            from datetime import date, timedelta

            today = date.today()
            self.initial["bill_date"] = today
            # Default due date is 30 days from today
            self.initial["due_date"] = today + timedelta(days=30)

    def clean(self):
        """Validate bill data."""
        cleaned_data = super().clean()
        bill_date = cleaned_data.get("bill_date")
        due_date = cleaned_data.get("due_date")

        # Validate dates
        if bill_date and due_date and due_date < bill_date:
            raise ValidationError({"due_date": "Due date cannot be before bill date"})

        return cleaned_data


class BillLineForm(forms.ModelForm):
    """
    Form for individual bill line items.

    Includes account, description, quantity, unit price, and amount.
    """

    account = forms.ChoiceField(
        choices=[],  # Will be set in __init__
        required=True,  # Account is required for proper accounting
        widget=forms.Select(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white account-select"
            }
        ),
        help_text="Select the expense/asset account",
    )

    description = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "Item description",
            }
        ),
        help_text="Description of the item or service",
    )

    quantity = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=True,
        initial=Decimal("1.00"),
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white quantity-input",
                "placeholder": "1.00",
                "step": "0.01",
                "min": "0.01",
            }
        ),
        help_text="Quantity",
    )

    unit_price = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=True,
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white unit-price-input",
                "placeholder": "0.00",
                "step": "0.01",
                "min": "0",
            }
        ),
        help_text="Price per unit",
    )

    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,  # Auto-calculated
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-gray-100 dark:bg-gray-600 dark:text-white amount-display",
                "readonly": "readonly",
                "placeholder": "0.00",
            }
        ),
        help_text="Total amount (auto-calculated)",
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "Additional notes...",
            }
        ),
        help_text="Additional notes about this line item",
    )

    class Meta:
        from .bill_models import BillLine

        model = BillLine
        fields = ["account", "description", "quantity", "unit_price", "amount", "notes"]

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        self.coa = kwargs.pop("coa", None)
        super().__init__(*args, **kwargs)

        # Filter accounts by chart of accounts (tenant-specific)
        # For bills, we typically use expense and asset accounts
        if self.coa:
            # Get all accounts and filter for expense/asset types
            # Django Ledger uses lowercase role names with underscores
            expense_and_asset_accounts = (
                AccountModel.objects.filter(
                    coa_model=self.coa,
                    active=True,
                )
                .filter(
                    # Expense accounts
                    models.Q(role__istartswith="ex_")
                    | models.Q(role__istartswith="cogs_")  # ex_regular, ex_depreciation, etc.
                    |  # cogs_regular, etc.
                    # Asset accounts
                    models.Q(role__istartswith="asset_")  # asset_ca_cash, asset_ppe_equip, etc.
                )
                .order_by("code", "name")
            )

            # Create choices list with account code as value and "code - name" as display
            account_choices = [("", "---------")]  # Empty choice
            for account in expense_and_asset_accounts:
                account_choices.append((account.code, f"{account.code} - {account.name}"))

            self.fields["account"].choices = account_choices
        else:
            # Set empty choices if no COA provided
            self.fields["account"].choices = [("", "---------")]

    def clean(self):
        """Validate line item data."""
        cleaned_data = super().clean()
        quantity = cleaned_data.get("quantity")
        unit_price = cleaned_data.get("unit_price")

        # Convert None to Decimal zero
        if quantity is None:
            quantity = Decimal("0.00")
        if unit_price is None:
            unit_price = Decimal("0.00")

        # Calculate amount
        cleaned_data["amount"] = quantity * unit_price

        # Validate positive values only if form is not being deleted
        if not cleaned_data.get("DELETE", False):
            if quantity <= Decimal("0.00"):
                raise ValidationError({"quantity": "Quantity must be greater than zero."})

            if unit_price < Decimal("0.00"):
                raise ValidationError({"unit_price": "Unit price cannot be negative."})

        return cleaned_data


class BillLineFormSet(BaseInlineFormSet):
    """
    Formset for managing multiple bill line items.

    Validates that at least one line item exists and calculates totals.
    """

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        self.coa = kwargs.pop("coa", None)
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        """Pass tenant and coa to each form instance."""
        kwargs["tenant"] = self.tenant
        kwargs["coa"] = self.coa
        return super()._construct_form(i, **kwargs)

    def clean(self):
        """Validate that at least one line item exists."""
        if any(self.errors):
            return

        valid_lines = 0
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                valid_lines += 1

        if valid_lines < 1:
            raise ValidationError("A bill must have at least one line item.")


# Factory for creating the inline formset
BillLineInlineFormSet = inlineformset_factory(
    Bill,
    BillLine,
    form=BillLineForm,
    formset=BillLineFormSet,
    extra=1,  # Show 1 empty form by default
    min_num=0,  # Don't require minimum (we validate in formset.clean())
    validate_min=False,
    can_delete=True,
    fields=["account", "description", "quantity", "unit_price", "amount", "notes"],
)


class BillPaymentForm(forms.ModelForm):
    """
    Form for recording payments against bills.

    Includes payment date, amount, method, and reference information.

    Requirements: 2.4, 2.6
    """

    payment_date = forms.DateField(
        required=True,
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
            }
        ),
        help_text="Date when payment was made",
    )

    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=True,
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "0.00",
                "step": "0.01",
                "min": "0.01",
            }
        ),
        help_text="Payment amount",
    )

    payment_method = forms.ChoiceField(
        required=True,
        widget=forms.Select(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
            }
        ),
        help_text="Method of payment",
    )

    bank_account = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "Bank account used",
            }
        ),
        help_text="Bank account used for payment (optional)",
    )

    reference_number = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "Check number, transaction ID, etc.",
            }
        ),
        help_text="Check number, transaction ID, or other reference",
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "Notes about this payment...",
            }
        ),
        help_text="Additional notes about this payment",
    )

    class Meta:
        from .bill_models import BillPayment

        model = BillPayment
        fields = [
            "payment_date",
            "amount",
            "payment_method",
            "bank_account",
            "reference_number",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        self.user = kwargs.pop("user", None)
        self.bill = kwargs.pop("bill", None)
        super().__init__(*args, **kwargs)

        # Set payment method choices from model
        from .bill_models import BillPayment

        self.fields["payment_method"].choices = BillPayment.PAYMENT_METHOD_CHOICES

        # Set initial payment date to today
        if not self.instance.pk:
            from datetime import date

            self.initial["payment_date"] = date.today()

            # Set initial amount to remaining balance if bill is provided
            if self.bill:
                self.initial["amount"] = self.bill.amount_due

    def clean_amount(self):
        """Validate payment amount doesn't exceed remaining balance."""
        amount = self.cleaned_data.get("amount")

        if amount and amount <= Decimal("0.00"):
            raise ValidationError("Payment amount must be greater than zero.")

        if self.bill and amount:
            remaining_balance = self.bill.amount_due
            if amount > remaining_balance:
                raise ValidationError(
                    f"Payment amount (${amount:,.2f}) exceeds remaining balance (${remaining_balance:,.2f})"
                )

        return amount
