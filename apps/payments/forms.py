"""
Forms for subscription purchase and payment processing.

This module contains forms for:
- Subscription plan selection
- Billing period selection with discount calculation
- Payment method selection
- Payment confirmation
"""

from decimal import Decimal

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from dateutil.relativedelta import relativedelta

from apps.core.models import SubscriptionPlan
from apps.payments.models import PaymentTransaction, SubscriptionDiscount, SubscriptionPurchase


class SubscriptionPlanSelectionForm(forms.Form):
    """Form for selecting a subscription plan."""

    plan = forms.UUIDField(
        widget=forms.HiddenInput(),
        required=True,
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        self.available_plans = SubscriptionPlan.objects.filter(status="active").order_by("price")

    def clean_plan(self):
        """Validate plan selection."""
        plan_id = self.cleaned_data.get("plan")
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id, status="active")
            return plan
        except SubscriptionPlan.DoesNotExist:
            raise forms.ValidationError(_("Selected plan is not available."))


class BillingPeriodForm(forms.Form):
    """Form for selecting billing period with discount preview."""

    BILLING_PERIOD_CHOICES = [
        (1, _("1 Month")),
        (3, _("3 Months")),
        (6, _("6 Months")),
        (12, _("12 Months")),
    ]

    billing_period = forms.ChoiceField(
        choices=BILLING_PERIOD_CHOICES,
        widget=forms.RadioSelect(),
        initial=1,
        label=_("Billing Period"),
        help_text=_("Select how long you want to subscribe. Longer periods have higher discounts."),
    )

    def __init__(self, *args, plan=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.plan = plan

        # Get active discounts
        self.discounts = {
            d.billing_period_months: d.discount_percentage
            for d in SubscriptionDiscount.objects.filter(is_active=True)
        }

    def get_pricing_breakdown(self, billing_period):
        """Calculate pricing for a billing period."""
        if not self.plan:
            return None

        months = int(billing_period)
        base_price = self.plan.price * months
        discount_percentage = self.discounts.get(months, 0)
        discount_amount = base_price * (discount_percentage / 100)
        final_price = base_price - discount_amount

        return {
            "billing_period": months,
            "base_price": base_price,
            "discount_percentage": discount_percentage,
            "discount_amount": discount_amount,
            "final_price": final_price,
            "monthly_equivalent": final_price / months,
        }

    def get_all_pricing_options(self):
        """Get pricing for all available billing periods."""
        if not self.plan:
            return []

        return [self.get_pricing_breakdown(period) for period, _ in self.BILLING_PERIOD_CHOICES]


class PaymentMethodForm(forms.Form):
    """Form for selecting payment method/gateway."""

    PAYMENT_METHOD_CHOICES = [
        ("placeholder", _("Placeholder (For Testing)")),
        # Iranian Payment Gateways - To be enabled
        # ("saman_bank", _("Saman Bank Gateway")),
        # ("mellat_bank", _("Mellat Bank Gateway")),
        # ("pasargad_bank", _("Pasargad Bank Gateway")),
        # ("zarinpal", _("ZarinPal")),
        # International Gateways - To be enabled
        # ("paypal", _("PayPal")),
        # ("stripe", _("Stripe (Credit/Debit Card)")),
        # Crypto - To be enabled
        # ("crypto_bitcoin", _("Bitcoin (BTC)")),
        # ("crypto_ethereum", _("Ethereum (ETH)")),
        # ("crypto_usdt", _("USDT (Tether)")),
    ]

    payment_method = forms.ChoiceField(
        choices=PAYMENT_METHOD_CHOICES,
        widget=forms.RadioSelect(),
        initial="placeholder",
        label=_("Payment Method"),
        help_text=_("Select how you want to pay."),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically add more payment methods based on configuration
        # This will be enhanced when actual gateways are implemented


class SubscriptionPurchaseConfirmForm(forms.Form):
    """Form for confirming subscription purchase."""

    plan_id = forms.UUIDField(widget=forms.HiddenInput())
    billing_period = forms.IntegerField(widget=forms.HiddenInput())
    payment_method = forms.CharField(widget=forms.HiddenInput())

    terms_accepted = forms.BooleanField(
        required=True,
        label=_("I agree to the terms of service and subscription agreement"),
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant

    def clean(self):
        """Validate the purchase details."""
        cleaned_data = super().clean()

        # Validate plan exists
        plan_id = cleaned_data.get("plan_id")
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id, status=SubscriptionPlan.STATUS_ACTIVE)
            cleaned_data["plan"] = plan
        except SubscriptionPlan.DoesNotExist:
            raise forms.ValidationError(_("Selected plan is not available."))

        # Validate billing period
        billing_period = cleaned_data.get("billing_period")
        if billing_period not in [1, 3, 6, 12]:
            raise forms.ValidationError(_("Invalid billing period selected."))

        # Check tenant doesn't have pending purchase
        if self.tenant:
            pending_purchases = SubscriptionPurchase.objects.filter(
                tenant=self.tenant, payment_status__in=["pending", "processing"]
            ).exists()
            if pending_purchases:
                raise forms.ValidationError(
                    _(
                        "You have a pending subscription purchase. Please complete or cancel it first."
                    )
                )

        return cleaned_data

    def create_purchase(self):
        """Create the subscription purchase record."""
        if not self.is_valid():
            return None

        plan = self.cleaned_data["plan"]
        billing_period = self.cleaned_data["billing_period"]
        payment_method = self.cleaned_data["payment_method"]

        # Calculate dates
        start_date = timezone.now().date()
        end_date = start_date + relativedelta(months=billing_period)

        # Calculate pricing
        base_price = plan.price * billing_period

        # Discount percentages based on billing period
        discount_rates = {
            1: Decimal("0.00"),  # No discount for monthly
            3: Decimal("5.00"),  # 5% discount for quarterly
            6: Decimal("10.00"),  # 10% discount for semi-annual
            12: Decimal("20.00"),  # 20% discount for annual
        }
        discount_percentage = discount_rates.get(billing_period, Decimal("0.00"))
        discount_amount = (base_price * discount_percentage / Decimal("100")).quantize(
            Decimal("0.01")
        )
        final_price = base_price - discount_amount

        # Create purchase record with all required fields
        purchase = SubscriptionPurchase.objects.create(
            tenant=self.tenant,
            subscription_plan=plan,
            billing_period_months=billing_period,
            start_date=start_date,
            end_date=end_date,
            base_price=base_price,
            discount_percentage=discount_percentage,
            discount_amount=discount_amount,
            final_price=final_price,
            payment_method=payment_method,
            payment_status="pending",
        )

        return purchase


class SubscriptionRenewalForm(forms.Form):
    """Form for renewing an existing subscription."""

    billing_period = forms.ChoiceField(
        choices=BillingPeriodForm.BILLING_PERIOD_CHOICES,
        widget=forms.RadioSelect(),
        label=_("Renewal Period"),
    )

    payment_method = forms.ChoiceField(
        choices=PaymentMethodForm.PAYMENT_METHOD_CHOICES,
        widget=forms.RadioSelect(),
        label=_("Payment Method"),
    )

    def __init__(self, *args, current_subscription=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_subscription = current_subscription

        if current_subscription:
            # Pre-select previous billing period
            self.fields["billing_period"].initial = current_subscription.billing_period


class SubscriptionUpgradeForm(forms.Form):
    """Form for upgrading to a higher-tier plan."""

    new_plan = forms.UUIDField(
        widget=forms.HiddenInput(),
        required=True,
    )

    prorate = forms.BooleanField(
        required=False,
        initial=True,
        label=_("Apply prorated credit from current subscription"),
        help_text=_(
            "If checked, unused time on your current plan will be credited toward the upgrade."
        ),
    )

    def __init__(self, *args, tenant=None, current_plan=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        self.current_plan = current_plan

        # Only show plans higher than current
        if current_plan:
            self.upgrade_plans = SubscriptionPlan.objects.filter(
                status=SubscriptionPlan.STATUS_ACTIVE, price__gt=current_plan.price
            ).order_by("price")
        else:
            self.upgrade_plans = SubscriptionPlan.objects.filter(
                status=SubscriptionPlan.STATUS_ACTIVE
            ).order_by("price")

    def clean_new_plan(self):
        """Validate upgrade plan selection."""
        plan_id = self.cleaned_data.get("new_plan")
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id, status=SubscriptionPlan.STATUS_ACTIVE)

            # Verify it's actually an upgrade
            if self.current_plan and plan.price <= self.current_plan.price:
                raise forms.ValidationError(
                    _("You can only upgrade to a plan with a higher price.")
                )

            return plan
        except SubscriptionPlan.DoesNotExist:
            raise forms.ValidationError(_("Selected plan is not available."))


class SubscriptionCancellationForm(forms.Form):
    """Form for cancelling a subscription."""

    CANCELLATION_REASONS = [
        ("too_expensive", _("Too expensive")),
        ("not_using", _("Not using the features")),
        ("switching_competitor", _("Switching to a competitor")),
        ("closing_business", _("Closing my business")),
        ("missing_features", _("Missing features I need")),
        ("technical_issues", _("Technical issues")),
        ("other", _("Other")),
    ]

    reason = forms.ChoiceField(
        choices=CANCELLATION_REASONS,
        widget=forms.RadioSelect(),
        label=_("Why are you cancelling?"),
        required=True,
    )

    feedback = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": _("Please share any additional feedback..."),
            }
        ),
        required=False,
        label=_("Additional Feedback"),
    )

    confirm_cancellation = forms.BooleanField(
        required=True,
        label=_(
            "I understand that my subscription will be cancelled and I will lose access to premium features."
        ),
        widget=forms.CheckboxInput(),
    )

    def __init__(self, *args, subscription=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.subscription = subscription


# Admin forms for managing payments


class SubscriptionDiscountAdminForm(forms.ModelForm):
    """Admin form for managing subscription discounts."""

    class Meta:
        model = SubscriptionDiscount
        fields = ["billing_period_months", "discount_percentage", "description", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_discount_percentage(self):
        """Validate discount percentage."""
        percentage = self.cleaned_data.get("discount_percentage")
        if percentage < 0 or percentage > 100:
            raise forms.ValidationError(_("Discount must be between 0 and 100 percent."))
        return percentage


class PaymentRefundForm(forms.Form):
    """Form for processing payment refunds."""

    refund_amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        label=_("Refund Amount"),
        help_text=_("Enter the amount to refund. Leave blank for full refund."),
        required=False,
    )

    refund_reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        label=_("Refund Reason"),
        required=True,
    )

    def __init__(self, *args, purchase=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.purchase = purchase

        if purchase:
            self.fields["refund_amount"].initial = purchase.final_amount
            self.fields["refund_amount"].max_value = purchase.final_amount

    def clean_refund_amount(self):
        """Validate refund amount."""
        amount = self.cleaned_data.get("refund_amount")
        if amount and self.purchase:
            if amount > self.purchase.final_amount:
                raise forms.ValidationError(
                    _("Refund amount cannot exceed the original payment amount.")
                )
        return amount or (self.purchase.final_amount if self.purchase else None)
