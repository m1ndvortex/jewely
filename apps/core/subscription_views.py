"""
Subscription plan management views for platform administrators.

This module contains views for managing subscription plans including
CRUD operations and plan archiving per Requirement 5.2.
"""

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from apps.core.admin_views import PlatformAdminRequiredMixin
from apps.core.models import SubscriptionPlan


class SubscriptionPlanListView(PlatformAdminRequiredMixin, ListView):
    """
    List view for subscription plans.

    Displays all subscription plans with filtering by status.
    Requirement 5.2: Allow administrators to create, edit, and archive subscription plans.
    """

    model = SubscriptionPlan
    template_name = "admin/subscription_plan_list.html"
    context_object_name = "plans"
    paginate_by = 20

    def get_queryset(self):
        """Get subscription plans with optional status filtering."""
        queryset = SubscriptionPlan.objects.all()

        # Filter by status if provided
        status = self.request.GET.get("status")
        if status in [SubscriptionPlan.STATUS_ACTIVE, SubscriptionPlan.STATUS_ARCHIVED]:
            queryset = queryset.filter(status=status)

        # Search by name or description
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(description__icontains=search))

        # Annotate with tenant count
        queryset = queryset.annotate(tenant_count=Count("subscriptions"))

        return queryset.order_by("display_order", "name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add filter parameters to context
        context["current_status"] = self.request.GET.get("status", "")
        context["search_query"] = self.request.GET.get("search", "")

        # Add status counts
        context["active_count"] = SubscriptionPlan.objects.filter(
            status=SubscriptionPlan.STATUS_ACTIVE
        ).count()
        context["archived_count"] = SubscriptionPlan.objects.filter(
            status=SubscriptionPlan.STATUS_ARCHIVED
        ).count()

        return context


class SubscriptionPlanDetailView(PlatformAdminRequiredMixin, DetailView):
    """
    Detail view for a subscription plan.

    Shows plan details and list of tenants subscribed to this plan.
    Requirement 5.2: Display all tenants with their current subscription plan.
    """

    model = SubscriptionPlan
    template_name = "admin/subscription_plan_detail.html"
    context_object_name = "plan"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get tenants subscribed to this plan
        context["subscribed_tenants"] = (
            self.object.subscriptions.select_related("tenant")
            .filter(tenant__status="ACTIVE")
            .order_by("-created_at")[:10]
        )

        # Get subscription count
        context["subscription_count"] = self.object.subscriptions.count()

        return context


class SubscriptionPlanCreateView(PlatformAdminRequiredMixin, CreateView):
    """
    Create view for subscription plans.

    Requirement 5.2: Allow administrators to create subscription plans.
    """

    model = SubscriptionPlan
    template_name = "admin/subscription_plan_form.html"
    fields = [
        "name",
        "description",
        "price",
        "billing_cycle",
        "user_limit",
        "branch_limit",
        "inventory_limit",
        "storage_limit_gb",
        "api_calls_per_month",
        "enable_multi_branch",
        "enable_advanced_reporting",
        "enable_api_access",
        "enable_custom_branding",
        "enable_priority_support",
        "display_order",
    ]

    def get_success_url(self):
        return reverse("core:admin_subscription_plan_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(
            self.request,
            f"Subscription plan '{form.instance.name}' has been created successfully.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = "Create Subscription Plan"
        context["submit_text"] = "Create Plan"
        return context


class SubscriptionPlanUpdateView(PlatformAdminRequiredMixin, UpdateView):
    """
    Update view for subscription plans.

    Requirement 5.2: Allow administrators to edit subscription plans.
    """

    model = SubscriptionPlan
    template_name = "admin/subscription_plan_form.html"
    fields = [
        "name",
        "description",
        "price",
        "billing_cycle",
        "user_limit",
        "branch_limit",
        "inventory_limit",
        "storage_limit_gb",
        "api_calls_per_month",
        "enable_multi_branch",
        "enable_advanced_reporting",
        "enable_api_access",
        "enable_custom_branding",
        "enable_priority_support",
        "display_order",
    ]

    def get_success_url(self):
        return reverse("core:admin_subscription_plan_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(
            self.request,
            f"Subscription plan '{form.instance.name}' has been updated successfully.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = f"Edit Subscription Plan: {self.object.name}"
        context["submit_text"] = "Update Plan"
        return context


class SubscriptionPlanArchiveView(PlatformAdminRequiredMixin, View):
    """
    Archive a subscription plan.

    Archived plans cannot be assigned to new tenants but existing
    subscriptions remain active.
    Requirement 5.2: Allow administrators to archive subscription plans.
    """

    def post(self, request, pk):
        plan = get_object_or_404(SubscriptionPlan, pk=pk)

        if plan.is_archived():
            messages.warning(request, f"Plan '{plan.name}' is already archived.")
        else:
            plan.archive()
            messages.success(
                request,
                f"Plan '{plan.name}' has been archived. It can no longer be assigned to new tenants.",
            )

        return redirect("core:admin_subscription_plan_detail", pk=pk)


class SubscriptionPlanActivateView(PlatformAdminRequiredMixin, View):
    """
    Activate an archived subscription plan.

    Requirement 5.2: Allow administrators to reactivate archived plans.
    """

    def post(self, request, pk):
        plan = get_object_or_404(SubscriptionPlan, pk=pk)

        if plan.is_active():
            messages.warning(request, f"Plan '{plan.name}' is already active.")
        else:
            plan.activate()
            messages.success(
                request,
                f"Plan '{plan.name}' has been activated and can now be assigned to tenants.",
            )

        return redirect("core:admin_subscription_plan_detail", pk=pk)
