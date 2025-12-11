"""
Views for tenant subscription purchase and management.

This module provides views for:
- Subscription dashboard (current status)
- Available plans listing
- Multi-step purchase flow
- Payment callbacks
- Purchase history
- Subscription renewal
- Subscription upgrade
- Subscription cancellation
"""

import logging
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DetailView, FormView, ListView, TemplateView

from apps.core.mixins import TenantOwnerRequiredMixin, TenantRequiredMixin
from apps.core.models import SubscriptionPlan, Tenant, TenantSubscription
from apps.payments.forms import (
    BillingPeriodForm,
    PaymentMethodForm,
    SubscriptionCancellationForm,
    SubscriptionPlanSelectionForm,
    SubscriptionPurchaseConfirmForm,
    SubscriptionRenewalForm,
    SubscriptionUpgradeForm,
)
from apps.payments.models import PaymentTransaction, SubscriptionDiscount, SubscriptionPurchase

logger = logging.getLogger(__name__)


class SubscriptionDashboardView(LoginRequiredMixin, TenantRequiredMixin, TemplateView):
    """
    Subscription dashboard showing current subscription status.

    Displays:
    - Current plan details
    - Subscription status (active, trial, expired)
    - Days remaining
    - Usage statistics vs plan limits
    - Quick actions (upgrade, renew, cancel)
    """

    template_name = "payments/subscription_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.user.tenant

        # Get current subscription
        current_subscription = (
            TenantSubscription.objects.filter(tenant=tenant, status="active")
            .select_related("plan")
            .first()
        )

        # Calculate subscription status
        subscription_status = {
            "is_active": False,
            "is_trial": False,
            "is_expired": False,
            "days_remaining": 0,
            "trial_days_remaining": 0,
        }

        if current_subscription:
            subscription_status["is_active"] = True

            # Check if in trial
            if current_subscription.trial_end:
                if current_subscription.trial_end > timezone.now():
                    subscription_status["is_trial"] = True
                    subscription_status["trial_days_remaining"] = (
                        current_subscription.trial_end - timezone.now()
                    ).days

            # Calculate days remaining
            if current_subscription.current_period_end:
                days_remaining = (current_subscription.current_period_end - timezone.now()).days
                subscription_status["days_remaining"] = max(0, days_remaining)

                if days_remaining < 0:
                    subscription_status["is_expired"] = True
                    subscription_status["is_active"] = False

        # Get usage statistics
        usage_stats = self._get_usage_stats(tenant, current_subscription)

        # Get available plans for upgrade
        upgrade_plans = []
        if current_subscription and current_subscription.plan:
            upgrade_plans = SubscriptionPlan.objects.filter(
                status=SubscriptionPlan.STATUS_ACTIVE, price__gt=current_subscription.plan.price
            ).order_by("price")[:3]

        # Get recent purchase history
        recent_purchases = SubscriptionPurchase.objects.filter(tenant=tenant).order_by(
            "-created_at"
        )[:5]

        context.update(
            {
                "tenant": tenant,
                "current_subscription": current_subscription,
                "subscription_status": subscription_status,
                "usage_stats": usage_stats,
                "upgrade_plans": upgrade_plans,
                "recent_purchases": recent_purchases,
                "active_tab": "subscription",
            }
        )

        return context

    def _get_usage_stats(self, tenant, subscription):
        """Calculate usage statistics against plan limits."""
        stats = []

        if not subscription or not subscription.plan:
            return stats

        plan = subscription.plan

        # Example usage metrics - these would be calculated from actual data
        # Import the actual counts from the tenant's data
        from apps.core.models import Branch, User
        from apps.crm.models import Customer
        from apps.inventory.models import InventoryItem

        # Products (InventoryItem in this system)
        product_count = (
            InventoryItem.objects.filter(tenant=tenant).count()
            if hasattr(InventoryItem, "tenant")
            else 0
        )
        products_limit = (
            plan.products_limit if plan.products_limit and plan.products_limit > 0 else None
        )
        stats.append(
            {
                "name": _("Products"),
                "current": product_count,
                "limit": products_limit or float("inf"),
                "percentage": (
                    min(100, (product_count / products_limit * 100)) if products_limit else 0
                ),
            }
        )

        # Customers
        customer_count = (
            Customer.objects.filter(tenant=tenant).count() if hasattr(Customer, "tenant") else 0
        )
        contacts_limit = (
            plan.contacts_limit if plan.contacts_limit and plan.contacts_limit > 0 else None
        )
        stats.append(
            {
                "name": _("Customers"),
                "current": customer_count,
                "limit": contacts_limit or float("inf"),
                "percentage": (
                    min(100, (customer_count / contacts_limit * 100)) if contacts_limit else 0
                ),
            }
        )

        # Users
        user_count = User.objects.filter(tenant=tenant).count()
        user_limit = plan.user_limit if plan.user_limit and plan.user_limit > 0 else None
        stats.append(
            {
                "name": _("Users"),
                "current": user_count,
                "limit": user_limit or float("inf"),
                "percentage": min(100, (user_count / user_limit * 100)) if user_limit else 0,
            }
        )

        # Branches
        branch_count = Branch.objects.filter(tenant=tenant).count()
        branch_limit = plan.branch_limit if plan.branch_limit and plan.branch_limit > 0 else None
        stats.append(
            {
                "name": _("Branches"),
                "current": branch_count,
                "limit": branch_limit or float("inf"),
                "percentage": min(100, (branch_count / branch_limit * 100)) if branch_limit else 0,
            }
        )

        return stats


class SubscriptionPlansView(LoginRequiredMixin, TenantRequiredMixin, TemplateView):
    """
    Display available subscription plans with pricing.

    Shows:
    - All active subscription plans
    - Feature comparison
    - Pricing with discounts for longer periods
    - Current plan indicator
    """

    template_name = "payments/subscription_plans.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.user.tenant

        # Get all active plans
        plans = SubscriptionPlan.objects.filter(status=SubscriptionPlan.STATUS_ACTIVE).order_by(
            "price"
        )

        # Get discounts
        discounts = {
            d.billing_period_months: d for d in SubscriptionDiscount.objects.filter(is_active=True)
        }

        # Get current subscription
        current_subscription = (
            TenantSubscription.objects.filter(tenant=tenant, status="active")
            .select_related("plan")
            .first()
        )

        current_plan_id = None
        if current_subscription and current_subscription.plan:
            current_plan_id = current_subscription.plan.id

        # Add pricing info to each plan
        plans_with_pricing = []
        for plan in plans:
            plan_data = {
                "plan": plan,
                "is_current": plan.id == current_plan_id,
                "pricing": {},
            }

            for period in [1, 3, 6, 12]:
                discount = discounts.get(period)
                discount_percentage = discount.discount_percentage if discount else 0

                base_price = plan.price * period
                discount_amount = base_price * (discount_percentage / 100)
                final_price = base_price - discount_amount

                plan_data["pricing"][period] = {
                    "base_price": base_price,
                    "discount_percentage": discount_percentage,
                    "discount_amount": discount_amount,
                    "final_price": final_price,
                    "monthly_equivalent": final_price / period,
                }

            plans_with_pricing.append(plan_data)

        context.update(
            {
                "plans": plans_with_pricing,
                "discounts": discounts,
                "current_plan_id": current_plan_id,
                "billing_periods": [
                    {"months": 1, "label": _("Monthly")},
                    {"months": 3, "label": _("Quarterly")},
                    {"months": 6, "label": _("Semi-Annual")},
                    {"months": 12, "label": _("Annual")},
                ],
                "active_tab": "subscription",
            }
        )

        return context


class PurchaseSubscriptionView(LoginRequiredMixin, TenantOwnerRequiredMixin, TemplateView):
    """
    Multi-step subscription purchase wizard.

    Steps:
    1. Select plan
    2. Select billing period
    3. Select payment method
    4. Review and confirm
    5. Process payment
    """

    template_name = "payments/purchase_subscription.html"

    def get(self, request, *args, **kwargs):
        # Get step from query params or default to plan selection
        step = request.GET.get("step", "plan")
        plan_id = request.GET.get("plan")
        billing_period = request.GET.get("billing_period")

        context = self.get_context_data(**kwargs)
        context["current_step"] = step
        context["plan_id"] = plan_id
        context["billing_period"] = billing_period

        # Get selected plan if provided
        if plan_id:
            try:
                context["selected_plan"] = SubscriptionPlan.objects.get(
                    id=plan_id, status=SubscriptionPlan.STATUS_ACTIVE
                )
            except SubscriptionPlan.DoesNotExist:
                messages.error(request, _("Selected plan is not available."))
                return redirect("payments:subscription_plans")

        # Initialize forms based on step
        if step == "plan":
            context["form"] = SubscriptionPlanSelectionForm(tenant=request.user.tenant)
            context["plans"] = SubscriptionPlan.objects.filter(
                status=SubscriptionPlan.STATUS_ACTIVE
            ).order_by("price")

        elif step == "billing_period":
            if not context.get("selected_plan"):
                return redirect(f"{reverse('payments:purchase_subscription')}?step=plan")
            context["form"] = BillingPeriodForm(plan=context["selected_plan"])
            context["pricing_options"] = context["form"].get_all_pricing_options()

        elif step == "payment_method":
            if not context.get("selected_plan") or not billing_period:
                return redirect(f"{reverse('payments:purchase_subscription')}?step=plan")
            context["form"] = PaymentMethodForm()

        elif step == "confirm":
            if not all(
                [context.get("selected_plan"), billing_period, request.GET.get("payment_method")]
            ):
                return redirect(f"{reverse('payments:purchase_subscription')}?step=plan")

            context["form"] = SubscriptionPurchaseConfirmForm(
                tenant=request.user.tenant,
                initial={
                    "plan_id": plan_id,
                    "billing_period": billing_period,
                    "payment_method": request.GET.get("payment_method"),
                },
            )

            # Calculate final pricing for review
            context["billing_period"] = int(billing_period)
            context["payment_method"] = request.GET.get("payment_method")
            context["pricing"] = self._calculate_pricing(
                context["selected_plan"], int(billing_period)
            )

        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        step = request.POST.get("step", "plan")

        if step == "plan":
            form = SubscriptionPlanSelectionForm(request.POST, tenant=request.user.tenant)
            if form.is_valid():
                plan = form.cleaned_data["plan"]
                return redirect(
                    f"{reverse('payments:purchase_subscription')}?step=billing_period&plan={plan.id}"
                )

        elif step == "billing_period":
            plan_id = request.POST.get("plan_id")
            try:
                plan = SubscriptionPlan.objects.get(
                    id=plan_id, status=SubscriptionPlan.STATUS_ACTIVE
                )
            except SubscriptionPlan.DoesNotExist:
                messages.error(request, _("Selected plan is not available."))
                return redirect("payments:subscription_plans")

            form = BillingPeriodForm(request.POST, plan=plan)
            if form.is_valid():
                billing_period = form.cleaned_data["billing_period"]
                return redirect(
                    f"{reverse('payments:purchase_subscription')}?step=payment_method&plan={plan_id}&billing_period={billing_period}"
                )

        elif step == "payment_method":
            form = PaymentMethodForm(request.POST)
            if form.is_valid():
                plan_id = request.POST.get("plan_id")
                billing_period = request.POST.get("billing_period")
                payment_method = form.cleaned_data["payment_method"]
                return redirect(
                    f"{reverse('payments:purchase_subscription')}?step=confirm&plan={plan_id}&billing_period={billing_period}&payment_method={payment_method}"
                )

        elif step == "confirm":
            form = SubscriptionPurchaseConfirmForm(request.POST, tenant=request.user.tenant)
            if form.is_valid():
                with transaction.atomic():
                    purchase = form.create_purchase()

                    if purchase:
                        # Create initial payment transaction
                        PaymentTransaction.objects.create(
                            tenant=request.user.tenant,
                            subscription_purchase=purchase,
                            payment_gateway=purchase.payment_method,
                            amount=purchase.final_price,
                            currency=purchase.currency,
                            status="pending",
                        )

                        # For placeholder payment, auto-complete
                        if purchase.payment_method == "placeholder":
                            return redirect(
                                "payments:process_placeholder_payment", purchase_id=purchase.id
                            )

                        # For real gateways, redirect to payment page
                        return redirect("payments:payment_gateway", purchase_id=purchase.id)
            else:
                # Log form errors for debugging
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Form validation failed: {form.errors.as_json()}")

            # Handle failed form validation or purchase creation - repopulate context
            error_msg = _("Failed to create purchase. Please try again.")
            if form.errors:
                # Show specific field errors if any
                for field, errors in form.errors.items():
                    for error in errors:
                        if field == "__all__":
                            error_msg = error
                        else:
                            error_msg = f"{field}: {error}"
                        break
                    break
            messages.error(request, error_msg)

            # Repopulate context for confirm step re-render
            plan_id = request.POST.get("plan_id")
            billing_period = request.POST.get("billing_period")
            payment_method = request.POST.get("payment_method")

            context = self.get_context_data(**kwargs)
            context["form"] = form
            context["current_step"] = step

            # Repopulate template context for confirm step
            if plan_id:
                try:
                    selected_plan = SubscriptionPlan.objects.get(id=plan_id)
                    context["selected_plan"] = selected_plan
                    if billing_period:
                        billing_period_int = int(billing_period)
                        context["billing_period"] = billing_period_int
                        context["pricing"] = self._calculate_pricing(
                            selected_plan, billing_period_int
                        )
                except (SubscriptionPlan.DoesNotExist, ValueError):
                    pass
            if payment_method:
                context["payment_method"] = payment_method

            return self.render_to_response(context)

        # If we get here for non-confirm steps, form was invalid - re-render with errors
        context = self.get_context_data(**kwargs)
        context["form"] = form
        context["current_step"] = step
        return self.render_to_response(context)

    def _calculate_pricing(self, plan, billing_period):
        """Calculate pricing with discounts."""
        discount = SubscriptionDiscount.objects.filter(
            billing_period_months=billing_period, is_active=True
        ).first()

        discount_percentage = discount.discount_percentage if discount else 0
        base_price = plan.price * billing_period
        discount_amount = base_price * (discount_percentage / 100)
        final_price = base_price - discount_amount

        return {
            "base_price": base_price,
            "discount_percentage": discount_percentage,
            "discount_amount": discount_amount,
            "final_price": final_price,
            "monthly_equivalent": final_price / billing_period,
        }


class ProcessPlaceholderPaymentView(LoginRequiredMixin, TenantOwnerRequiredMixin, View):
    """
    Process placeholder payment (for testing).

    This automatically completes the payment and activates the subscription.
    In production, this would be replaced with actual payment gateway integration.
    """

    def get(self, request, purchase_id):
        tenant = request.user.tenant

        try:
            purchase = SubscriptionPurchase.objects.get(
                id=purchase_id, tenant=tenant, payment_status="pending"
            )
        except SubscriptionPurchase.DoesNotExist:
            messages.error(request, _("Purchase not found or already processed."))
            return redirect("payments:subscription_dashboard")

        with transaction.atomic():
            # Update payment transaction
            transaction_obj = PaymentTransaction.objects.filter(
                subscription_purchase=purchase, status="pending"
            ).first()

            if transaction_obj:
                transaction_obj.status = "completed"
                transaction_obj.gateway_transaction_id = f"PLACEHOLDER-{purchase.invoice_number}"
                transaction_obj.completed_at = timezone.now()
                transaction_obj.save()

            # Complete the purchase
            purchase.payment_status = "completed"
            purchase.payment_gateway_transaction_id = f"PLACEHOLDER-{purchase.invoice_number}"
            purchase.payment_completed_at = timezone.now()
            purchase.save()

            # Activate the subscription
            self._activate_subscription(purchase)

        messages.success(request, _("Payment successful! Your subscription has been activated."))
        return redirect("payments:subscription_dashboard")

    def _activate_subscription(self, purchase):
        """Activate or extend tenant subscription."""
        tenant = purchase.tenant
        plan = purchase.subscription_plan

        # Calculate subscription dates
        start_date = timezone.now()
        end_date = start_date + timezone.timedelta(days=30 * purchase.billing_period_months)

        # Get or create subscription
        subscription, created = TenantSubscription.objects.get_or_create(
            tenant=tenant,
            defaults={
                "plan": plan,
                "status": "active",
                "current_period_start": start_date,
                "current_period_end": end_date,
            },
        )

        if not created:
            # Extend existing subscription
            if subscription.current_period_end and subscription.current_period_end > start_date:
                # Add time to existing subscription
                end_date = subscription.current_period_end + timezone.timedelta(
                    days=30 * purchase.billing_period_months
                )

            subscription.plan = plan
            subscription.status = "active"
            subscription.current_period_end = end_date
            subscription.save()

        # The purchase already has start_date and end_date set from creation
        # No need to update subscription reference (purchase tracks its own dates)

        logger.info(
            f"Activated subscription for tenant {tenant.id}: "
            f"plan={plan.name}, expires={end_date}"
        )


class PaymentGatewayView(LoginRequiredMixin, TenantOwnerRequiredMixin, TemplateView):
    """
    Generic payment gateway redirect/iframe handler.

    This view handles the payment gateway integration:
    - For redirect-based gateways: redirects to gateway
    - For iframe-based gateways: loads gateway in iframe
    - For API-based gateways: shows form for card details
    """

    template_name = "payments/payment_gateway.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        purchase_id = self.kwargs.get("purchase_id")
        tenant = self.request.user.tenant

        try:
            purchase = SubscriptionPurchase.objects.get(
                id=purchase_id, tenant=tenant, payment_status="pending"
            )
        except SubscriptionPurchase.DoesNotExist:
            context["error"] = _("Purchase not found or already processed.")
            return context

        context["purchase"] = purchase
        context["payment_method"] = purchase.payment_method

        # Get gateway configuration
        # This would be populated based on the payment method
        context["gateway_config"] = {
            "type": "placeholder",  # Could be: redirect, iframe, form
            "url": None,
            "fields": [],
        }

        return context


class PaymentCallbackView(View):
    """
    Handle payment gateway callbacks.

    This view receives callbacks from payment gateways after
    a payment is completed (success or failure).
    """

    def get(self, request, *args, **kwargs):
        """Handle GET callbacks (typically success redirects)."""
        return self._process_callback(request, request.GET)

    def post(self, request, *args, **kwargs):
        """Handle POST callbacks (typically webhook notifications)."""
        return self._process_callback(request, request.POST)

    def _process_callback(self, request, data):
        """Process the payment callback."""
        gateway = self.kwargs.get("gateway")

        # Get purchase from callback data
        purchase_id = data.get("purchase_id") or data.get("order_id")

        if not purchase_id:
            logger.error(f"Payment callback missing purchase_id: {data}")
            messages.error(request, _("Invalid payment callback."))
            return redirect("payments:subscription_dashboard")

        try:
            purchase = SubscriptionPurchase.objects.get(id=purchase_id)
        except SubscriptionPurchase.DoesNotExist:
            logger.error(f"Payment callback for non-existent purchase: {purchase_id}")
            messages.error(request, _("Purchase not found."))
            return redirect("payments:subscription_dashboard")

        # Process based on gateway
        # This would be implemented for each specific gateway
        status = data.get("status", "unknown")

        if status in ["success", "completed", "approved"]:
            # Payment successful
            with transaction.atomic():
                purchase.payment_status = "completed"
                purchase.payment_gateway_transaction_id = data.get("transaction_id")
                purchase.payment_completed_at = timezone.now()
                purchase.save()

                # Update transaction record
                PaymentTransaction.objects.filter(
                    subscription_purchase=purchase, status="pending"
                ).update(
                    status="completed",
                    gateway_transaction_id=data.get("transaction_id"),
                    completed_at=timezone.now(),
                )

                # Activate subscription
                self._activate_subscription(purchase)

            messages.success(
                request, _("Payment successful! Your subscription has been activated.")
            )
        else:
            # Payment failed
            purchase.payment_status = "failed"
            purchase.save()

            PaymentTransaction.objects.filter(
                subscription_purchase=purchase, status="pending"
            ).update(
                status="failed",
                error_message=data.get("error", "Payment failed"),
            )

            messages.error(request, _("Payment failed. Please try again."))

        return redirect("payments:subscription_dashboard")

    def _activate_subscription(self, purchase):
        """Activate subscription after successful payment."""
        # Same logic as ProcessPlaceholderPaymentView._activate_subscription
        ProcessPlaceholderPaymentView()._activate_subscription(purchase)


class PurchaseHistoryView(LoginRequiredMixin, TenantRequiredMixin, ListView):
    """List of all subscription purchases for the tenant."""

    template_name = "payments/purchase_history.html"
    context_object_name = "purchases"
    paginate_by = 20

    def get_queryset(self):
        tenant = self.request.user.tenant
        return (
            SubscriptionPurchase.objects.filter(tenant=tenant)
            .select_related("plan")
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "subscription"
        return context


class PurchaseDetailView(LoginRequiredMixin, TenantRequiredMixin, DetailView):
    """Detail view for a subscription purchase."""

    template_name = "payments/purchase_detail.html"
    context_object_name = "purchase"

    def get_queryset(self):
        tenant = self.request.user.tenant
        return SubscriptionPurchase.objects.filter(tenant=tenant).select_related("plan")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get transactions for this purchase
        context["transactions"] = PaymentTransaction.objects.filter(purchase=self.object).order_by(
            "-initiated_at"
        )

        context["active_tab"] = "subscription"
        return context


class SubscriptionRenewalView(LoginRequiredMixin, TenantOwnerRequiredMixin, FormView):
    """View for renewing an expiring subscription."""

    template_name = "payments/subscription_renewal.html"
    form_class = SubscriptionRenewalForm
    success_url = reverse_lazy("payments:subscription_dashboard")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        tenant = self.request.user.tenant

        # Get current subscription
        current_subscription = TenantSubscription.objects.filter(
            tenant=tenant, status="active"
        ).first()

        kwargs["current_subscription"] = current_subscription
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.user.tenant

        current_subscription = (
            TenantSubscription.objects.filter(tenant=tenant, status="active")
            .select_related("plan")
            .first()
        )

        context["current_subscription"] = current_subscription
        context["active_tab"] = "subscription"

        # Calculate renewal pricing if plan exists
        if current_subscription and current_subscription.plan:
            form = BillingPeriodForm(plan=current_subscription.plan)
            context["pricing_options"] = form.get_all_pricing_options()

        return context

    def form_valid(self, form):
        tenant = self.request.user.tenant
        current_subscription = (
            TenantSubscription.objects.filter(tenant=tenant, status="active")
            .select_related("plan")
            .first()
        )

        if not current_subscription:
            messages.error(self.request, _("No active subscription to renew."))
            return redirect("payments:subscription_plans")

        # Create renewal purchase
        billing_period = int(form.cleaned_data["billing_period"])
        payment_method = form.cleaned_data["payment_method"]

        purchase = SubscriptionPurchase.objects.create(
            tenant=tenant,
            plan=current_subscription.plan,
            billing_period_months=billing_period,
            payment_method=payment_method,
            payment_status="pending",
            is_renewal=True,
        )
        purchase.calculate_pricing()
        purchase.save()

        # Redirect to payment
        if payment_method == "placeholder":
            return redirect("payments:process_placeholder_payment", purchase_id=purchase.id)
        return redirect("payments:payment_gateway", purchase_id=purchase.id)


class SubscriptionUpgradeView(LoginRequiredMixin, TenantOwnerRequiredMixin, FormView):
    """View for upgrading to a higher-tier plan."""

    template_name = "payments/subscription_upgrade.html"
    form_class = SubscriptionUpgradeForm
    success_url = reverse_lazy("payments:subscription_dashboard")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        tenant = self.request.user.tenant

        current_subscription = (
            TenantSubscription.objects.filter(tenant=tenant, status="active")
            .select_related("plan")
            .first()
        )

        kwargs["tenant"] = tenant
        kwargs["current_plan"] = current_subscription.plan if current_subscription else None
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.user.tenant

        current_subscription = (
            TenantSubscription.objects.filter(tenant=tenant, status="active")
            .select_related("plan")
            .first()
        )

        context["current_subscription"] = current_subscription
        context["active_tab"] = "subscription"

        # Get upgrade options
        if current_subscription and current_subscription.plan:
            context["upgrade_plans"] = SubscriptionPlan.objects.filter(
                status=SubscriptionPlan.STATUS_ACTIVE, price__gt=current_subscription.plan.price
            ).order_by("price")
        else:
            context["upgrade_plans"] = SubscriptionPlan.objects.filter(
                status=SubscriptionPlan.STATUS_ACTIVE
            ).order_by("price")

        return context

    def form_valid(self, form):
        tenant = self.request.user.tenant
        new_plan = form.cleaned_data["new_plan"]
        prorate = form.cleaned_data.get("prorate", True)

        # Create upgrade purchase
        # Note: Proration logic would be implemented here

        messages.success(self.request, _("Upgrade initiated. Please complete payment."))
        return super().form_valid(form)


class SubscriptionCancellationView(LoginRequiredMixin, TenantOwnerRequiredMixin, FormView):
    """View for cancelling subscription."""

    template_name = "payments/subscription_cancellation.html"
    form_class = SubscriptionCancellationForm
    success_url = reverse_lazy("payments:subscription_dashboard")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        tenant = self.request.user.tenant

        current_subscription = TenantSubscription.objects.filter(
            tenant=tenant, status="active"
        ).first()

        kwargs["subscription"] = current_subscription
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.user.tenant

        current_subscription = (
            TenantSubscription.objects.filter(tenant=tenant, status="active")
            .select_related("plan")
            .first()
        )

        context["current_subscription"] = current_subscription
        context["active_tab"] = "subscription"

        return context

    def form_valid(self, form):
        tenant = self.request.user.tenant
        reason = form.cleaned_data["reason"]
        feedback = form.cleaned_data.get("feedback", "")

        current_subscription = TenantSubscription.objects.filter(
            tenant=tenant, status="active"
        ).first()

        if current_subscription:
            # Mark subscription for cancellation (don't immediately cancel)
            current_subscription.status = "cancelled"
            current_subscription.cancelled_at = timezone.now()
            current_subscription.cancellation_reason = reason
            current_subscription.cancellation_feedback = feedback
            current_subscription.save()

            logger.info(f"Subscription cancelled for tenant {tenant.id}: " f"reason={reason}")

            messages.success(
                self.request,
                _(
                    "Your subscription has been cancelled. You will have access until the end of your billing period."
                ),
            )
        else:
            messages.error(self.request, _("No active subscription to cancel."))

        return super().form_valid(form)


# API Views for AJAX operations


class CalculatePricingAPIView(LoginRequiredMixin, TenantRequiredMixin, View):
    """API endpoint for calculating subscription pricing."""

    def get(self, request):
        plan_id = request.GET.get("plan_id")
        billing_period = request.GET.get("billing_period", 1)

        try:
            plan = SubscriptionPlan.objects.get(id=plan_id, status=SubscriptionPlan.STATUS_ACTIVE)
            billing_period = int(billing_period)
        except (SubscriptionPlan.DoesNotExist, ValueError):
            return JsonResponse({"error": "Invalid parameters"}, status=400)

        # Calculate pricing
        discount = SubscriptionDiscount.objects.filter(
            billing_period_months=billing_period, is_active=True
        ).first()

        discount_percentage = discount.discount_percentage if discount else 0
        base_price = float(plan.price * billing_period)
        discount_amount = base_price * (discount_percentage / 100)
        final_price = base_price - discount_amount

        return JsonResponse(
            {
                "plan_name": plan.name,
                "billing_period": billing_period,
                "base_price": base_price,
                "discount_percentage": float(discount_percentage),
                "discount_amount": discount_amount,
                "final_price": final_price,
                "monthly_equivalent": final_price / billing_period,
                "currency": "USD",
            }
        )
