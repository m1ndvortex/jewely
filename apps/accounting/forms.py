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


# ============================================================================
# Invoice Management Forms (Task 3.5)
# ============================================================================


class InvoiceForm(forms.ModelForm):
    """
    Form for creating and editing customer invoices.

    Includes customer selection, dates, and financial information.
    Line items are handled by InvoiceLineFormSet.

    Requirements: 3.1, 3.2, 3.7
    """

    customer = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=True,
        widget=forms.Select(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
            }
        ),
        help_text="Select the customer for this invoice",
    )

    invoice_number = forms.CharField(
        max_length=50,
        required=False,  # Auto-generated if not provided
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "Auto-generated if left blank",
            }
        ),
        help_text="Invoice number (auto-generated if blank)",
    )

    invoice_date = forms.DateField(
        required=True,
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
            }
        ),
        help_text="Date when invoice was issued",
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
                "placeholder": "Internal notes about this invoice...",
            }
        ),
        help_text="Internal notes (not visible to customer)",
    )

    customer_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "Notes visible to customer...",
            }
        ),
        help_text="Notes visible to customer on invoice",
    )

    reference_number = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "PO number or other reference",
            }
        ),
        help_text="Purchase order number or other reference (optional)",
    )

    class Meta:
        from .invoice_models import Invoice

        model = Invoice
        fields = [
            "customer",
            "invoice_number",
            "invoice_date",
            "due_date",
            "tax",
            "notes",
            "customer_notes",
            "reference_number",
        ]

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Filter customers by tenant
        if self.tenant:
            from apps.crm.models import Customer

            self.fields["customer"].queryset = Customer.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name")

            # Update label to show full name
            self.fields["customer"].label_from_instance = (
                lambda obj: f"{obj.first_name} {obj.last_name} ({obj.customer_number})"
            )

        # Set initial dates if creating new invoice
        if not self.instance.pk:
            from datetime import date, timedelta

            today = date.today()
            self.initial["invoice_date"] = today
            # Default due date based on customer payment terms or 30 days
            self.initial["due_date"] = today + timedelta(days=30)

    def clean(self):
        """Validate invoice data."""
        cleaned_data = super().clean()
        invoice_date = cleaned_data.get("invoice_date")
        due_date = cleaned_data.get("due_date")
        customer = cleaned_data.get("customer")

        # Validate dates
        if invoice_date and due_date and due_date < invoice_date:
            raise ValidationError({"due_date": "Due date cannot be before invoice date"})

        # Check credit limit if customer is provided
        if customer and hasattr(customer, "credit_limit"):
            # Calculate total outstanding including this invoice
            from .invoice_models import Invoice

            outstanding = Invoice.objects.filter(
                customer=customer, status__in=["SENT", "PARTIALLY_PAID", "OVERDUE"]
            ).exclude(pk=self.instance.pk if self.instance.pk else None).aggregate(
                total=models.Sum("amount_due")
            )[
                "total"
            ] or Decimal(
                "0.00"
            )

            # Add current invoice total (will be calculated from lines)
            # For now, just warn if they're close to limit
            if customer.credit_limit > 0 and outstanding >= customer.credit_limit:
                self.add_error(
                    "customer",
                    f"Warning: Customer has ${outstanding:,.2f} outstanding "
                    f"against credit limit of ${customer.credit_limit:,.2f}",
                )

        return cleaned_data


class InvoiceLineForm(forms.ModelForm):
    """
    Form for individual invoice line items.

    Includes item, description, quantity, unit price, and amount.
    """

    item = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "Product or service name",
            }
        ),
        help_text="Product or service name",
    )

    description = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "Detailed description...",
            }
        ),
        help_text="Detailed description of the item or service",
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
        from .invoice_models import InvoiceLine

        model = InvoiceLine
        fields = ["item", "description", "quantity", "unit_price", "amount", "notes"]

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


class InvoiceLineFormSet(BaseInlineFormSet):
    """
    Formset for managing multiple invoice line items.

    Validates that at least one line item exists and calculates totals.
    """

    def clean(self):
        """Validate that at least one line item exists."""
        if any(self.errors):
            return

        valid_lines = 0
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                valid_lines += 1

        if valid_lines < 1:
            raise ValidationError("An invoice must have at least one line item.")


# Factory for creating the inline formset
# Import models here to avoid circular import at module level
def get_invoice_line_formset():
    """Factory function to create InvoiceLineInlineFormSet."""
    from .invoice_models import Invoice, InvoiceLine

    return inlineformset_factory(
        Invoice,
        InvoiceLine,
        form=InvoiceLineForm,
        formset=InvoiceLineFormSet,
        extra=1,  # Show 1 empty form by default
        min_num=0,  # Don't require minimum (we validate in formset.clean())
        validate_min=False,
        can_delete=True,
        fields=["item", "description", "quantity", "unit_price", "amount", "notes"],
    )


# Create the formset class
InvoiceLineInlineFormSet = get_invoice_line_formset()


class InvoicePaymentForm(forms.ModelForm):
    """
    Form for recording payments against invoices.

    Includes payment date, amount, method, and reference information.

    Requirements: 3.4, 3.6
    """

    payment_date = forms.DateField(
        required=True,
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
            }
        ),
        help_text="Date when payment was received",
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
                "placeholder": "Bank account where payment was deposited",
            }
        ),
        help_text="Bank account where payment was deposited (optional)",
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
        from .invoice_models import InvoicePayment

        model = InvoicePayment
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
        self.invoice = kwargs.pop("invoice", None)
        super().__init__(*args, **kwargs)

        # Set payment method choices from model
        from .invoice_models import InvoicePayment

        self.fields["payment_method"].choices = InvoicePayment.PAYMENT_METHOD_CHOICES

        # Set initial payment date to today
        if not self.instance.pk:
            from datetime import date

            self.initial["payment_date"] = date.today()

            # Set initial amount to remaining balance if invoice is provided
            if self.invoice:
                self.initial["amount"] = self.invoice.amount_due

    def clean_amount(self):
        """Validate payment amount doesn't exceed remaining balance."""
        amount = self.cleaned_data.get("amount")

        if amount and amount <= Decimal("0.00"):
            raise ValidationError("Payment amount must be greater than zero.")

        if self.invoice and amount:
            remaining_balance = self.invoice.amount_due
            if amount > remaining_balance:
                raise ValidationError(
                    f"Payment amount (${amount:,.2f}) exceeds remaining balance (${remaining_balance:,.2f})"
                )

        return amount


class CreditMemoForm(forms.ModelForm):
    """
    Form for creating credit memos for customers.

    Includes customer, amount, reason, and optional original invoice reference.

    Requirements: 3.6
    """

    customer = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=True,
        widget=forms.Select(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
            }
        ),
        help_text="Select the customer for this credit memo",
    )

    credit_memo_number = forms.CharField(
        max_length=50,
        required=False,  # Auto-generated if not provided
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "Auto-generated if left blank",
            }
        ),
        help_text="Credit memo number (auto-generated if blank)",
    )

    credit_date = forms.DateField(
        required=True,
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
            }
        ),
        help_text="Date when credit was issued",
    )

    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=True,
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "0.00",
                "step": "0.01",
                "min": "0.01",
            }
        ),
        help_text="Credit amount",
    )

    reason = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "Reason for issuing this credit...",
            }
        ),
        help_text="Reason for issuing this credit",
    )

    original_invoice = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        widget=forms.Select(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
            }
        ),
        help_text="Original invoice this credit is related to (optional)",
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "Internal notes about this credit memo...",
            }
        ),
        help_text="Internal notes (not visible to customer)",
    )

    class Meta:
        from .invoice_models import CreditMemo

        model = CreditMemo
        fields = [
            "customer",
            "credit_memo_number",
            "credit_date",
            "amount",
            "reason",
            "original_invoice",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Filter customers by tenant
        if self.tenant:
            from apps.crm.models import Customer

            self.fields["customer"].queryset = Customer.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name")

            # Update label to show full name
            self.fields["customer"].label_from_instance = (
                lambda obj: f"{obj.first_name} {obj.last_name} ({obj.customer_number})"
            )

            # Filter invoices by tenant for original_invoice field
            from .invoice_models import Invoice

            self.fields["original_invoice"].queryset = Invoice.objects.filter(
                tenant=self.tenant
            ).order_by("-invoice_date")

            # Update label to show invoice number and date
            self.fields["original_invoice"].label_from_instance = (
                lambda obj: f"{obj.invoice_number} - {obj.invoice_date} (${obj.total:,.2f})"
            )

        # Set initial credit date to today
        if not self.instance.pk:
            from datetime import date

            self.initial["credit_date"] = date.today()

    def clean_amount(self):
        """Validate credit amount is positive."""
        amount = self.cleaned_data.get("amount")

        if amount and amount <= Decimal("0.00"):
            raise ValidationError("Credit amount must be greater than zero.")

        return amount


# ============================================================================
# Bank Account Management Forms (Task 4.3)
# ============================================================================


class BankAccountForm(forms.ModelForm):
    """
    Form for creating and editing bank accounts.

    Includes account details, bank information, and configuration options.

    Requirements: 6.1, 6.3, 6.6, 6.7
    """

    account_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "e.g., Main Checking Account",
            }
        ),
        help_text="Name/description of the bank account",
    )

    account_number = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "Last 4 digits recommended for security",
            }
        ),
        help_text="Bank account number (last 4 digits recommended for security)",
    )

    bank_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "Name of the financial institution",
            }
        ),
        help_text="Name of the financial institution",
    )

    account_type = forms.ChoiceField(
        required=True,
        widget=forms.Select(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
            }
        ),
        help_text="Type of bank account",
    )

    gl_account = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        widget=forms.Select(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
            }
        ),
        help_text="Link this bank account to a General Ledger account (Cash/Bank accounts)",
        label="GL Account (Chart of Accounts)",
    )

    opening_balance = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        initial=Decimal("0.00"),
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "0.00",
                "step": "0.01",
            }
        ),
        help_text="Opening balance when account was added to system",
    )

    routing_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "Bank routing number",
            }
        ),
        help_text="Bank routing number (optional)",
    )

    swift_code = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "SWIFT/BIC code",
            }
        ),
        help_text="SWIFT/BIC code for international transfers (optional)",
    )

    currency = forms.CharField(
        max_length=3,
        required=False,
        initial="USD",
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "USD",
            }
        ),
        help_text="Currency code (ISO 4217)",
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "placeholder": "Internal notes about this bank account...",
            }
        ),
        help_text="Internal notes about this bank account",
    )

    is_active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(
            attrs={
                "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded",
            }
        ),
        help_text="Whether this account is currently active",
    )

    is_default = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(
            attrs={
                "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded",
            }
        ),
        help_text="Set as default bank account for transactions",
    )

    class Meta:
        from .bank_models import BankAccount

        model = BankAccount
        fields = [
            "account_name",
            "account_number",
            "bank_name",
            "account_type",
            "gl_account",
            "opening_balance",
            "routing_number",
            "swift_code",
            "currency",
            "notes",
            "is_active",
            "is_default",
        ]

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Set tenant on new instances immediately to ensure validation works
        if not self.instance.pk and self.tenant:
            self.instance.tenant = self.tenant

        # Set account type choices from model
        from .bank_models import BankAccount

        self.fields["account_type"].choices = BankAccount.ACCOUNT_TYPE_CHOICES

        # Set GL account queryset - only show cash/bank accounts
        if self.tenant:
            from apps.accounting.models import JewelryEntity

            try:
                jewelry_entity = JewelryEntity.objects.get(tenant=self.tenant)
                entity = jewelry_entity.ledger_entity
                coa = entity.chartofaccountmodel_set.first()

                if coa:
                    # Get cash/bank accounts (typically codes starting with 100x or role ASSET_CA_*)
                    self.fields["gl_account"].queryset = (
                        AccountModel.objects.filter(coa_model=coa, active=True)
                        .filter(
                            models.Q(code__startswith="100")
                            | models.Q(  # Cash accounts
                                role__startswith="ASSET_CA"
                            )  # Current Asset - Cash accounts
                        )
                        .order_by("code")
                    )

                    # Set label to show code and name
                    self.fields["gl_account"].label_from_instance = (
                        lambda obj: f"{obj.code} - {obj.name}"
                    )
            except JewelryEntity.DoesNotExist:
                self.fields["gl_account"].queryset = AccountModel.objects.none()

        # Set initial currency if not provided
        if not self.instance.pk and "currency" not in self.initial:
            self.initial["currency"] = "USD"

    def clean(self):
        """Validate bank account data."""
        cleaned_data = super().clean()
        opening_balance = cleaned_data.get("opening_balance")

        # Ensure opening balance is set
        if opening_balance is None:
            cleaned_data["opening_balance"] = Decimal("0.00")

        # Set current_balance to opening_balance for new accounts
        if not self.instance.pk:
            cleaned_data["current_balance"] = cleaned_data["opening_balance"]

        return cleaned_data

    def _post_clean(self):
        """
        Set tenant on instance before model validation.

        This is called by Django after the form's clean() but before the model's
        full_clean(). We need to set the tenant here so the model's clean() method
        can access it for validation.
        """
        # Set tenant before calling parent _post_clean which triggers model validation
        if not self.instance.pk and self.tenant:
            self.instance.tenant = self.tenant
            if self.user:
                self.instance.created_by = self.user

        super()._post_clean()

    def save(self, commit=True):
        """Save bank account with tenant and user information."""
        from decimal import Decimal

        from django.db import transaction as db_transaction
        from django.utils import timezone

        from django_ledger.models import JournalEntryModel, TransactionModel

        from apps.accounting.models import JewelryEntity

        instance = super().save(commit=False)
        is_new = instance._state.adding

        # Use _state.adding to check if this is a new instance (UUID PKs are generated immediately)
        if is_new:
            if self.tenant:
                instance.tenant = self.tenant
            else:
                raise ValidationError("Tenant is required for creating bank accounts")

            if self.user:
                instance.created_by = self.user
            else:
                raise ValidationError("User is required for creating bank accounts")

            # Set current_balance to opening_balance for new accounts
            instance.current_balance = instance.opening_balance

        if commit:
            with db_transaction.atomic():
                instance.save()

                # Create journal entry for opening balance if this is a new account with balance > 0
                if (
                    is_new
                    and instance.opening_balance
                    and instance.opening_balance > Decimal("0.00")
                    and instance.gl_account
                ):
                    try:
                        # Get the jewelry entity and ledger
                        jewelry_entity = JewelryEntity.objects.get(tenant=self.tenant)
                        entity = jewelry_entity.ledger_entity
                        ledger = entity.ledgermodel_set.first()

                        if ledger:
                            # Get the owner's equity account (typically 3001)
                            coa = entity.chartofaccountmodel_set.first()
                            equity_account = AccountModel.objects.filter(
                                coa_model=coa, code="3001"  # Owner's Equity
                            ).first()

                            if equity_account:
                                # Create journal entry for opening balance
                                journal_entry = JournalEntryModel.objects.create(
                                    ledger=ledger,
                                    description=f"Opening balance for {instance.account_name}",
                                    timestamp=timezone.now(),
                                    origin="bank_account_opening",
                                    activity="op",  # Operating activity
                                )

                                # Debit: Cash account (increase asset)
                                TransactionModel.objects.create(
                                    journal_entry=journal_entry,
                                    account=instance.gl_account,
                                    tx_type="debit",
                                    amount=instance.opening_balance,
                                    description=f"Opening balance - {instance.account_name}",
                                )

                                # Credit: Owner's Equity (source of funds)
                                TransactionModel.objects.create(
                                    journal_entry=journal_entry,
                                    account=equity_account,
                                    tx_type="credit",
                                    amount=instance.opening_balance,
                                    description=f"Opening balance - {instance.account_name}",
                                )

                                # Lock and post the journal entry
                                journal_entry.locked = True
                                journal_entry.posted = True
                                journal_entry.save(update_fields=["locked", "posted"])

                    except Exception as e:
                        # Log the error but don't fail the bank account creation
                        import logging

                        logger = logging.getLogger(__name__)
                        logger.error(f"Failed to create opening balance journal entry: {e}")

        return instance


class BankReconciliationStartForm(forms.Form):
    """
    Form for starting a new bank reconciliation.

    Allows user to select bank account and enter statement details.
    """

    bank_account = forms.ModelChoiceField(
        queryset=None,
        required=True,
        widget=forms.Select(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            }
        ),
        help_text="Select the bank account to reconcile",
    )

    statement_date = forms.DateField(
        required=True,
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
            }
        ),
        help_text="Date of the bank statement",
    )

    beginning_balance = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "step": "0.01",
                "placeholder": "0.00",
            }
        ),
        help_text="Beginning balance from bank statement (optional, will use last reconciled balance if not provided)",
    )

    ending_balance = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=True,
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "step": "0.01",
                "placeholder": "0.00",
            }
        ),
        help_text="Ending balance from bank statement",
    )

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        # Set bank account queryset with tenant filtering
        if self.tenant:
            from .bank_models import BankAccount

            self.fields["bank_account"].queryset = BankAccount.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("account_name")

        # Set initial statement date to today if not provided
        if "statement_date" not in self.initial:
            from datetime import date

            self.initial["statement_date"] = date.today()

    def clean(self):
        """Validate reconciliation start data."""
        cleaned_data = super().clean()

        bank_account = cleaned_data.get("bank_account")
        statement_date = cleaned_data.get("statement_date")

        if bank_account and statement_date:
            # Check if there's already an in-progress reconciliation for this account
            from .bank_models import BankReconciliation

            existing = BankReconciliation.objects.filter(
                bank_account=bank_account, status="IN_PROGRESS"
            ).first()

            if existing:
                raise ValidationError(
                    f"There is already an in-progress reconciliation for {bank_account.account_name}. "
                    f"Please complete or cancel it before starting a new one."
                )

            # Warn if statement date is before last reconciliation date
            if (
                bank_account.last_reconciled_date
                and statement_date < bank_account.last_reconciled_date
            ):
                raise ValidationError(
                    f"Statement date cannot be before the last reconciliation date "
                    f"({bank_account.last_reconciled_date})"
                )

        return cleaned_data


class BankStatementImportForm(forms.ModelForm):
    """
    Form for importing bank statements from files.

    Supports CSV, OFX, and QFX file formats for automatic transaction import.

    Requirements: 4.3, 6.4
    """

    bank_account = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=True,
        widget=forms.Select(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
            }
        ),
        help_text="Select the bank account for this statement",
    )

    file = forms.FileField(
        required=True,
        widget=forms.FileInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "accept": ".csv,.ofx,.qfx,.qbo",
            }
        ),
        help_text="Upload bank statement file (CSV, OFX, QFX, or QBO format)",
    )

    file_format = forms.ChoiceField(
        required=False,
        widget=forms.Select(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
            }
        ),
        help_text="File format (auto-detected if not specified)",
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                "rows": 3,
                "placeholder": "Optional notes about this import...",
            }
        ),
        help_text="Optional notes about this import",
    )

    class Meta:
        from .bank_models import BankStatementImport

        model = BankStatementImport
        fields = ["bank_account", "file", "file_format", "notes"]

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Set bank account queryset with tenant filtering
        if self.tenant:
            from .bank_models import BankAccount

            self.fields["bank_account"].queryset = BankAccount.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("account_name")

        # Set file format choices
        from .bank_models import BankStatementImport

        self.fields["file_format"].choices = [("", "Auto-detect")] + list(
            BankStatementImport.FILE_FORMAT_CHOICES
        )

    def clean_file(self):
        """Validate uploaded file."""
        file = self.cleaned_data.get("file")

        if file:
            # Check file size (max 10MB)
            if file.size > 10 * 1024 * 1024:
                raise ValidationError("File size must be less than 10MB")

            # Check file extension
            file_name = file.name.lower()
            valid_extensions = [".csv", ".ofx", ".qfx", ".qbo"]

            if not any(file_name.endswith(ext) for ext in valid_extensions):
                raise ValidationError(
                    f"Invalid file format. Supported formats: {', '.join(valid_extensions)}"
                )

        return file

    def clean(self):
        """Validate import data."""
        cleaned_data = super().clean()

        file = cleaned_data.get("file")
        file_format = cleaned_data.get("file_format")

        # Auto-detect file format if not specified
        if file and not file_format:
            file_name = file.name.lower()
            if file_name.endswith(".csv"):
                cleaned_data["file_format"] = "CSV"
            elif file_name.endswith(".ofx"):
                cleaned_data["file_format"] = "OFX"
            elif file_name.endswith(".qfx"):
                cleaned_data["file_format"] = "QFX"
            elif file_name.endswith(".qbo"):
                cleaned_data["file_format"] = "QBO"
            else:
                cleaned_data["file_format"] = "OTHER"

        return cleaned_data

    def save(self, commit=True):
        """Save the import record."""
        instance = super().save(commit=False)

        # Set tenant and user
        if self.tenant:
            instance.tenant = self.tenant
        if self.user:
            instance.imported_by = self.user

        # Set file name from uploaded file
        if instance.file:
            instance.file_name = instance.file.name

        if commit:
            instance.save()

        return instance


class FixedAssetForm(forms.ModelForm):
    """
    Form for creating and editing fixed assets.

    Includes all fields needed for asset registration including
    acquisition details, depreciation settings, and GL account references.

    Requirements: 5.1, 5.4, 5.6, 5.7
    """

    asset_name = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "Enter asset name (e.g., Display Case, Jewelry Tools)",
            }
        ),
        help_text="Name or description of the asset",
    )

    category = forms.ChoiceField(
        required=True,
        widget=forms.Select(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            }
        ),
        help_text="Category of the asset",
    )

    serial_number = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "Manufacturer's serial number (optional)",
            }
        ),
        help_text="Manufacturer's serial number",
    )

    manufacturer = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "Manufacturer or brand name (optional)",
            }
        ),
        help_text="Manufacturer or brand name",
    )

    model_number = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "Model number (optional)",
            }
        ),
        help_text="Model number",
    )

    acquisition_date = forms.DateField(
        required=True,
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
            }
        ),
        help_text="Date when asset was acquired",
    )

    acquisition_cost = forms.DecimalField(
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
        help_text="Original cost of the asset",
    )

    salvage_value = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        initial=Decimal("0.00"),
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "0.00",
                "step": "0.01",
                "min": "0.00",
            }
        ),
        help_text="Estimated salvage/residual value at end of useful life",
    )

    useful_life_months = forms.IntegerField(
        required=True,
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "60",
                "min": "1",
            }
        ),
        help_text="Useful life in months (e.g., 60 for 5 years)",
    )

    depreciation_method = forms.ChoiceField(
        required=True,
        widget=forms.Select(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "onchange": "toggleDepreciationRate()",
            }
        ),
        help_text="Method used to calculate depreciation",
    )

    depreciation_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "200.00",
                "step": "0.01",
                "min": "0.01",
                "id": "id_depreciation_rate",
            }
        ),
        help_text="Depreciation rate for declining balance method (e.g., 200 for double declining)",
    )

    asset_account = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "1300",
            }
        ),
        help_text="GL account code for the asset (e.g., 1300 - Equipment)",
    )

    accumulated_depreciation_account = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "1310",
            }
        ),
        help_text="GL account code for accumulated depreciation (e.g., 1310 - Accumulated Depreciation)",
    )

    depreciation_expense_account = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "5300",
            }
        ),
        help_text="GL account code for depreciation expense (e.g., 5300 - Depreciation Expense)",
    )

    location = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "Physical location (optional)",
            }
        ),
        help_text="Physical location of the asset",
    )

    department = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "Department (optional)",
            }
        ),
        help_text="Department responsible for the asset",
    )

    purchase_order_number = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "PO number (optional)",
            }
        ),
        help_text="Purchase order number for acquisition",
    )

    vendor = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "Vendor/supplier (optional)",
            }
        ),
        help_text="Vendor/supplier of the asset",
    )

    warranty_expiration = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
            }
        ),
        help_text="Warranty expiration date (optional)",
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "Additional notes about this asset (optional)",
            }
        ),
        help_text="Additional notes about this asset",
    )

    class Meta:
        from .fixed_asset_models import FixedAsset

        model = FixedAsset
        fields = [
            "asset_name",
            "category",
            "serial_number",
            "manufacturer",
            "model_number",
            "acquisition_date",
            "acquisition_cost",
            "salvage_value",
            "useful_life_months",
            "depreciation_method",
            "depreciation_rate",
            "asset_account",
            "accumulated_depreciation_account",
            "depreciation_expense_account",
            "location",
            "department",
            "purchase_order_number",
            "vendor",
            "warranty_expiration",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Set choices from model
        from .fixed_asset_models import FixedAsset

        self.fields["category"].choices = FixedAsset.CATEGORY_CHOICES
        self.fields["depreciation_method"].choices = FixedAsset.DEPRECIATION_METHOD_CHOICES

        # Set initial date to today if not provided
        if not self.instance.pk and "acquisition_date" not in self.initial:
            from datetime import date

            self.initial["acquisition_date"] = date.today()

        # Set default GL accounts if not provided
        if not self.instance.pk:
            if "asset_account" not in self.initial:
                self.initial["asset_account"] = "1300"
            if "accumulated_depreciation_account" not in self.initial:
                self.initial["accumulated_depreciation_account"] = "1310"
            if "depreciation_expense_account" not in self.initial:
                self.initial["depreciation_expense_account"] = "5300"

    def clean(self):
        cleaned_data = super().clean()

        # Validate salvage value is less than acquisition cost
        acquisition_cost = cleaned_data.get("acquisition_cost")
        salvage_value = cleaned_data.get("salvage_value") or Decimal("0.00")

        if acquisition_cost and salvage_value >= acquisition_cost:
            raise ValidationError(
                {"salvage_value": "Salvage value must be less than acquisition cost"}
            )

        # Validate depreciation rate for declining balance method
        depreciation_method = cleaned_data.get("depreciation_method")
        depreciation_rate = cleaned_data.get("depreciation_rate")

        if depreciation_method == "DECLINING_BALANCE" and not depreciation_rate:
            raise ValidationError(
                {"depreciation_rate": "Depreciation rate is required for declining balance method"}
            )

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Set tenant and created_by for new assets
        if not instance.pk:
            if self.tenant:
                instance.tenant = self.tenant
            if self.user:
                instance.created_by = self.user

        if commit:
            instance.save()

        return instance


class AssetDisposalForm(forms.ModelForm):
    """
    Form for recording asset disposals.

    Includes disposal date, method, proceeds, and reason.

    Requirements: 5.4, 5.6, 5.7
    """

    disposal_date = forms.DateField(
        required=True,
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
            }
        ),
        help_text="Date when asset was disposed",
    )

    disposal_method = forms.ChoiceField(
        required=True,
        widget=forms.Select(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            }
        ),
        help_text="Method of disposal",
    )

    proceeds = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        initial=Decimal("0.00"),
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "0.00",
                "step": "0.01",
                "min": "0.00",
            }
        ),
        help_text="Amount received from disposal (if sold)",
    )

    buyer_name = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "Name of buyer (if sold)",
            }
        ),
        help_text="Name of buyer (if sold)",
    )

    disposal_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "Reason for disposal",
            }
        ),
        help_text="Reason for disposal",
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "Additional notes about the disposal (optional)",
            }
        ),
        help_text="Additional notes about the disposal",
    )

    cash_account_code = forms.CharField(
        max_length=20,
        required=False,
        initial="1001",
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "1001",
            }
        ),
        help_text="GL account code for cash/bank account (if proceeds received)",
    )

    class Meta:
        from .fixed_asset_models import AssetDisposal

        model = AssetDisposal
        fields = [
            "disposal_date",
            "disposal_method",
            "proceeds",
            "buyer_name",
            "disposal_reason",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        self.user = kwargs.pop("user", None)
        self.fixed_asset = kwargs.pop("fixed_asset", None)
        super().__init__(*args, **kwargs)

        # Set choices from model
        from .fixed_asset_models import AssetDisposal

        self.fields["disposal_method"].choices = AssetDisposal.DISPOSAL_METHOD_CHOICES

        # Set initial date to today if not provided
        if not self.instance.pk and "disposal_date" not in self.initial:
            from datetime import date

            self.initial["disposal_date"] = date.today()

        # Add cash account code field (not in model, used for journal entry)
        if "cash_account_code" not in self.fields:
            self.fields["cash_account_code"] = forms.CharField(
                max_length=20,
                required=False,
                initial="1001",
                widget=forms.TextInput(
                    attrs={
                        "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                        "placeholder": "1001",
                    }
                ),
                help_text="GL account code for cash/bank account (if proceeds received)",
            )

    def clean(self):
        cleaned_data = super().clean()

        # Validate disposal date is not before acquisition date
        if self.fixed_asset:
            disposal_date = cleaned_data.get("disposal_date")
            if disposal_date and disposal_date < self.fixed_asset.acquisition_date:
                raise ValidationError(
                    {"disposal_date": "Disposal date cannot be before acquisition date"}
                )

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Set tenant, fixed_asset, and created_by for new disposals
        if not instance.pk:
            if self.tenant:
                instance.tenant = self.tenant
            if self.user:
                instance.created_by = self.user
            if self.fixed_asset:
                instance.fixed_asset = self.fixed_asset
                instance.book_value_at_disposal = self.fixed_asset.current_book_value

        if commit:
            instance.save()

        return instance
