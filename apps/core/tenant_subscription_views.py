"""
Tenant subscription management views for platform administrators.

This module contains views for managing tenant subscriptions including
manual plan assignment, limit overrides, and activation/deactivation
per Requirement 5.3, 5.4, and 5.5.
"""

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import DetailView, ListView, UpdateView, View

from apps.core.admin_views import PlatformAdminRequiredMixin
from apps.core.models import SubscriptionPlan, Tenant, TenantSubscription


class TenantSubscriptionListView(PlatformAdminRequiredMixin, ListView):
    """
    List view for tenant subscriptions with filters.

    Displays all tenant subscriptions with filtering by status, plan, and search.
    Requirement 5.3: Display all tenants with their current subscription plan, status, and next billing date.
    """

    model = TenantSubscription
    template_name = "admin/tenant_subscription_list.html"
    context_object_name = "subscriptions"
    paginate_by = 20

    def get_queryset(self):
        """Get tenant subscriptions with optional filtering."""
        queryset = TenantSubscription.objects.select_related("tenant", "plan").all()

        # Filter by status if provided
        status = self.request.GET.get("status")
        if status in [
            TenantSubscription.STATUS_ACTIVE,
            TenantSubscription.STATUS_TRIAL,
            TenantSubscription.STATUS_PAST_DUE,
            TenantSubscription.STATUS_CANCELLED,
            TenantSubscription.STATUS_EXPIRED,
        ]:
            queryset = queryset.filter(status=status)

        # Filter by plan if provided
        plan_id = self.request.GET.get("plan")
        if plan_id:
            queryset = queryset.filter(plan_id=plan_id)

        # Filter by tenant status
        tenant_status = self.request.GET.get("tenant_status")
        if tenant_status in [Tenant.ACTIVE, Tenant.SUSPENDED, Tenant.PENDING_DELETION]:
            queryset = queryset.filter(tenant__status=tenant_status)

        # Search by tenant name
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(tenant__company_name__icontains=search) | Q(tenant__slug__icontains=search)
            )

        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add filter parameters to context
        context["current_status"] = self.request.GET.get("status", "")
        context["current_plan"] = self.request.GET.get("plan", "")
        context["current_tenant_status"] = self.request.GET.get("tenant_status", "")
        context["search_query"] = self.request.GET.get("search", "")

        # Add status counts
        context["active_count"] = TenantSubscription.objects.filter(
            status=TenantSubscription.STATUS_ACTIVE
        ).count()
        context["trial_count"] = TenantSubscription.objects.filter(
            status=TenantSubscription.STATUS_TRIAL
        ).count()
        context["past_due_count"] = TenantSubscription.objects.filter(
            status=TenantSubscription.STATUS_PAST_DUE
        ).count()
        context["cancelled_count"] = TenantSubscription.objects.filter(
            status=TenantSubscription.STATUS_CANCELLED
        ).count()

        # Add available plans for filter dropdown
        context["available_plans"] = SubscriptionPlan.objects.filter(
            status=SubscriptionPlan.STATUS_ACTIVE
        ).order_by("name")

        return context


class TenantSubscriptionDetailView(PlatformAdminRequiredMixin, DetailView):
    """
    Detail view for a tenant subscription.

    Shows subscription details, current limits, and overrides.
    Requirement 5.3: Display tenant subscription details.
    """

    model = TenantSubscription
    template_name = "admin/tenant_subscription_detail.html"
    context_object_name = "subscription"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add available plans for plan change
        context["available_plans"] = (
            SubscriptionPlan.objects.filter(status=SubscriptionPlan.STATUS_ACTIVE)
            .exclude(id=self.object.plan.id)
            .order_by("name")
        )

        # Add effective limits (with overrides applied)
        context["effective_limits"] = {
            "user_limit": self.object.get_user_limit(),
            "branch_limit": self.object.get_branch_limit(),
            "inventory_limit": self.object.get_inventory_limit(),
            "storage_limit_gb": self.object.get_storage_limit_gb(),
            "api_calls_per_month": self.object.get_api_calls_per_month(),
        }

        # Add effective features (with overrides applied)
        context["effective_features"] = {
            "multi_branch": self.object.has_multi_branch_enabled(),
            "advanced_reporting": self.object.has_advanced_reporting_enabled(),
            "api_access": self.object.has_api_access_enabled(),
            "custom_branding": self.object.has_custom_branding_enabled(),
            "priority_support": self.object.has_priority_support_enabled(),
        }

        return context


class TenantSubscriptionChangePlanView(PlatformAdminRequiredMixin, View):
    """
    Change the subscription plan for a tenant.

    Requirement 5.3: Allow administrators to manually assign or change a tenant's subscription plan.
    """

    def post(self, request, pk):
        subscription = get_object_or_404(TenantSubscription, pk=pk)
        new_plan_id = request.POST.get("plan_id")

        if not new_plan_id:
            messages.error(request, "Please select a plan.")
            return redirect("core:admin_tenant_subscription_detail", pk=pk)

        new_plan = get_object_or_404(SubscriptionPlan, pk=new_plan_id)

        if new_plan.id == subscription.plan.id:
            messages.warning(request, "The tenant is already on this plan.")
            return redirect("core:admin_tenant_subscription_detail", pk=pk)

        old_plan_name = subscription.plan.name
        subscription.change_plan(new_plan)

        messages.success(
            request,
            f"Subscription plan changed from '{old_plan_name}' to '{new_plan.name}' for {subscription.tenant.company_name}.",
        )

        return redirect("core:admin_tenant_subscription_detail", pk=pk)


class TenantSubscriptionLimitOverrideView(PlatformAdminRequiredMixin, UpdateView):
    """
    Update limit overrides for a tenant subscription.

    Requirement 5.4: Allow administrators to override default plan limits for specific tenants.
    """

    model = TenantSubscription
    template_name = "admin/tenant_subscription_limit_override.html"
    fields = [
        "user_limit_override",
        "branch_limit_override",
        "inventory_limit_override",
        "storage_limit_gb_override",
        "api_calls_per_month_override",
        "enable_multi_branch_override",
        "enable_advanced_reporting_override",
        "enable_api_access_override",
        "enable_custom_branding_override",
        "enable_priority_support_override",
    ]

    def get_success_url(self):
        return reverse("core:admin_tenant_subscription_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(
            self.request,
            f"Limit overrides updated for {self.object.tenant.company_name}.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["subscription"] = self.object

        # Add plan defaults for reference
        context["plan_defaults"] = {
            "user_limit": self.object.plan.user_limit,
            "branch_limit": self.object.plan.branch_limit,
            "inventory_limit": self.object.plan.inventory_limit,
            "storage_limit_gb": self.object.plan.storage_limit_gb,
            "api_calls_per_month": self.object.plan.api_calls_per_month,
            "enable_multi_branch": self.object.plan.enable_multi_branch,
            "enable_advanced_reporting": self.object.plan.enable_advanced_reporting,
            "enable_api_access": self.object.plan.enable_api_access,
            "enable_custom_branding": self.object.plan.enable_custom_branding,
            "enable_priority_support": self.object.plan.enable_priority_support,
        }

        return context


class TenantSubscriptionActivateView(PlatformAdminRequiredMixin, View):
    """
    Manually activate a tenant subscription.

    Requirement 5.5: Allow administrators to manually activate tenant subscriptions.
    """

    def post(self, request, pk):
        subscription = get_object_or_404(TenantSubscription, pk=pk)

        if subscription.is_active():
            messages.warning(
                request,
                f"Subscription for {subscription.tenant.company_name} is already active.",
            )
        else:
            subscription.activate()
            messages.success(
                request,
                f"Subscription for {subscription.tenant.company_name} has been activated.",
            )

        return redirect("core:admin_tenant_subscription_detail", pk=pk)


class TenantSubscriptionDeactivateView(PlatformAdminRequiredMixin, View):
    """
    Manually deactivate a tenant subscription.

    Requirement 5.5: Allow administrators to manually deactivate tenant subscriptions.
    """

    def post(self, request, pk):
        subscription = get_object_or_404(TenantSubscription, pk=pk)

        if subscription.is_cancelled():
            messages.warning(
                request,
                f"Subscription for {subscription.tenant.company_name} is already deactivated.",
            )
        else:
            reason = request.POST.get("reason", "Manually deactivated by administrator")
            subscription.cancel(reason=reason)
            messages.success(
                request,
                f"Subscription for {subscription.tenant.company_name} has been deactivated.",
            )

        return redirect("core:admin_tenant_subscription_detail", pk=pk)


class TenantSubscriptionClearOverridesView(PlatformAdminRequiredMixin, View):
    """
    Clear all limit overrides for a tenant subscription.

    This resets all overrides to use the plan defaults.
    """

    def post(self, request, pk):
        subscription = get_object_or_404(TenantSubscription, pk=pk)

        # Clear all overrides
        subscription.user_limit_override = None
        subscription.branch_limit_override = None
        subscription.inventory_limit_override = None
        subscription.storage_limit_gb_override = None
        subscription.api_calls_per_month_override = None
        subscription.enable_multi_branch_override = None
        subscription.enable_advanced_reporting_override = None
        subscription.enable_api_access_override = None
        subscription.enable_custom_branding_override = None
        subscription.enable_priority_support_override = None

        subscription.save()

        messages.success(
            request,
            f"All limit overrides cleared for {subscription.tenant.company_name}. Using plan defaults.",
        )

        return redirect("core:admin_tenant_subscription_detail", pk=pk)
