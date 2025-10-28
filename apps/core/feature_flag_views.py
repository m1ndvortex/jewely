"""
Feature flag management interface views.
Per Requirement 30 - Feature Flag Management

Provides:
1. Flag list view with status
2. Flag configuration form (name, rollout %, target tenants)
3. A/B test configuration
4. Metrics dashboard
5. Emergency kill switch
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from waffle.models import Flag, Sample, Switch

from .feature_flags import (
    ABTestVariant,
    EmergencyKillSwitch,
    FeatureFlagHistory,
    FeatureFlagMetric,
    TenantFeatureFlag,
    emergency_disable_flag,
    get_ab_test_metrics,
    get_flag_conversion_metrics,
)
from .forms import (
    ABTestVariantForm,
    EmergencyKillSwitchForm,
    FeatureFlagForm,
    TenantFeatureFlagForm,
)
from .models import Tenant


class PlatformAdminRequiredMixin(UserPassesTestMixin):
    """Mixin to require platform admin role."""

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == "PLATFORM_ADMIN"


class FeatureFlagListView(LoginRequiredMixin, PlatformAdminRequiredMixin, ListView):
    """List all feature flags with their status."""

    model = Flag
    template_name = "core/feature_flags/flag_list.html"
    context_object_name = "flags"
    paginate_by = 20

    def get_queryset(self):
        queryset = Flag.objects.all().order_by("name")
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(note__icontains=search))
        status = self.request.GET.get("status")
        if status == "active":
            queryset = queryset.filter(everyone=True)
        elif status == "inactive":
            queryset = queryset.filter(everyone=False)
        elif status == "percentage":
            queryset = queryset.filter(everyone=None).exclude(percent=None)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["switches"] = Switch.objects.all().order_by("name")
        context["samples"] = Sample.objects.all().order_by("name")
        context["kill_switches"] = EmergencyKillSwitch.objects.filter(is_active=True).order_by(
            "-disabled_at"
        )
        context["stats"] = {
            "total_flags": Flag.objects.count(),
            "active_flags": Flag.objects.filter(everyone=True).count(),
            "inactive_flags": Flag.objects.filter(everyone=False).count(),
            "percentage_flags": Flag.objects.filter(everyone=None).exclude(percent=None).count(),
            "active_kill_switches": EmergencyKillSwitch.objects.filter(is_active=True).count(),
            "active_ab_tests": ABTestVariant.objects.filter(is_active=True).count(),
        }
        return context


class FeatureFlagCreateView(LoginRequiredMixin, PlatformAdminRequiredMixin, CreateView):
    """Create a new feature flag."""

    model = Flag
    form_class = FeatureFlagForm
    template_name = "core/feature_flags/flag_form.html"
    success_url = reverse_lazy("core:feature_flag_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        FeatureFlagHistory.objects.create(
            flag_name=self.object.name,
            flag_type="flag",
            action="created",
            new_value={
                "everyone": self.object.everyone,
                "percent": float(self.object.percent) if self.object.percent else None,
                "note": self.object.note,
            },
            changed_by=self.request.user,
            reason=f"Flag created by {self.request.user.username}",
        )
        messages.success(self.request, f"Feature flag '{self.object.name}' created successfully.")
        return response


class FeatureFlagUpdateView(LoginRequiredMixin, PlatformAdminRequiredMixin, UpdateView):
    """Update a feature flag configuration."""

    model = Flag
    form_class = FeatureFlagForm
    template_name = "core/feature_flags/flag_form.html"
    success_url = reverse_lazy("core:feature_flag_list")

    def get_object(self, queryset=None):
        """Get object and store original values."""
        obj = super().get_object(queryset)
        # Store original values before form modifies them
        self._original_everyone = obj.everyone
        self._original_percent = obj.percent
        return obj

    def form_valid(self, form):
        response = super().form_valid(form)
        # Compare with stored original values
        if (
            self._original_everyone != self.object.everyone
            or self._original_percent != self.object.percent
        ):
            # Determine action based on what changed
            if self._original_everyone != self.object.everyone:
                action = (
                    "enabled"
                    if self.object.everyone is True
                    else "disabled" if self.object.everyone is False else "percentage_changed"
                )
            else:
                action = "percentage_changed"

            FeatureFlagHistory.objects.create(
                flag_name=self.object.name,
                flag_type="flag",
                action=action,
                old_value={
                    "everyone": self._original_everyone,
                    "percent": float(self._original_percent) if self._original_percent else None,
                },
                new_value={
                    "everyone": self.object.everyone,
                    "percent": float(self.object.percent) if self.object.percent else None,
                },
                changed_by=self.request.user,
                reason=form.cleaned_data.get("reason", ""),
            )
        messages.success(self.request, f"Feature flag '{self.object.name}' updated successfully.")
        return response


class FeatureFlagDetailView(LoginRequiredMixin, PlatformAdminRequiredMixin, DetailView):
    """View feature flag details including history and metrics."""

    model = Flag
    template_name = "core/feature_flags/flag_detail.html"
    context_object_name = "flag"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["history"] = FeatureFlagHistory.objects.filter(flag_name=self.object.name).order_by(
            "-timestamp"
        )[:50]
        context["tenant_overrides"] = (
            TenantFeatureFlag.objects.filter(flag=self.object)
            .select_related("tenant", "created_by")
            .order_by("-created_at")
        )
        context["ab_tests"] = ABTestVariant.objects.filter(flag=self.object).order_by("-created_at")
        context["metrics"] = get_flag_conversion_metrics(self.object.name)
        return context


class TenantFeatureFlagListView(LoginRequiredMixin, PlatformAdminRequiredMixin, ListView):
    """List tenant-specific feature flag overrides."""

    model = TenantFeatureFlag
    template_name = "core/feature_flags/tenant_flag_list.html"
    context_object_name = "tenant_flags"
    paginate_by = 20

    def get_queryset(self):
        queryset = TenantFeatureFlag.objects.select_related(
            "tenant", "flag", "created_by"
        ).order_by("-created_at")
        tenant_id = self.request.GET.get("tenant")
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        flag_id = self.request.GET.get("flag")
        if flag_id:
            queryset = queryset.filter(flag_id=flag_id)
        status = self.request.GET.get("status")
        if status == "enabled":
            queryset = queryset.filter(enabled=True)
        elif status == "disabled":
            queryset = queryset.filter(enabled=False)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tenants"] = Tenant.objects.filter(status="ACTIVE").order_by("company_name")
        context["flags"] = Flag.objects.all().order_by("name")
        return context


class TenantFeatureFlagCreateView(LoginRequiredMixin, PlatformAdminRequiredMixin, CreateView):
    """Create tenant-specific feature flag override."""

    model = TenantFeatureFlag
    form_class = TenantFeatureFlagForm
    template_name = "core/feature_flags/tenant_flag_form.html"
    success_url = reverse_lazy("core:tenant_feature_flag_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        FeatureFlagHistory.objects.create(
            flag_name=self.object.flag.name,
            flag_type="tenant_override",
            tenant=self.object.tenant,
            action="enabled" if self.object.enabled else "disabled",
            new_value={"enabled": self.object.enabled, "notes": self.object.notes},
            changed_by=self.request.user,
            reason=self.object.notes,
        )
        messages.success(
            self.request,
            f"Feature flag '{self.object.flag.name}' override created for {self.object.tenant.company_name}.",
        )
        return response


class ABTestListView(LoginRequiredMixin, PlatformAdminRequiredMixin, ListView):
    """List all A/B tests."""

    model = ABTestVariant
    template_name = "core/feature_flags/ab_test_list.html"
    context_object_name = "ab_tests"
    paginate_by = 20

    def get_queryset(self):
        queryset = ABTestVariant.objects.select_related("flag", "created_by").order_by(
            "-created_at"
        )
        status = self.request.GET.get("status")
        if status == "active":
            queryset = queryset.filter(is_active=True)
        elif status == "completed":
            queryset = queryset.filter(is_active=False)
        return queryset


class ABTestCreateView(LoginRequiredMixin, PlatformAdminRequiredMixin, CreateView):
    """Create a new A/B test."""

    model = ABTestVariant
    form_class = ABTestVariantForm
    template_name = "core/feature_flags/ab_test_form.html"
    success_url = reverse_lazy("core:ab_test_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, f"A/B test '{self.object.name}' created successfully.")
        return response


class ABTestDetailView(LoginRequiredMixin, PlatformAdminRequiredMixin, DetailView):
    """View A/B test details and metrics."""

    model = ABTestVariant
    template_name = "core/feature_flags/ab_test_detail.html"
    context_object_name = "ab_test"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["metrics"] = get_ab_test_metrics(self.object.id)
        control_metrics = context["metrics"]["control"]
        variant_metrics = context["metrics"]["variant"]
        control_conversions = sum(
            item["count"]
            for item in control_metrics["events_by_type"]
            if item["event_type"] == "converted"
        )
        variant_conversions = sum(
            item["count"]
            for item in variant_metrics["events_by_type"]
            if item["event_type"] == "converted"
        )
        control_rate = (
            (control_conversions / control_metrics["unique_users"] * 100)
            if control_metrics["unique_users"] > 0
            else 0
        )
        variant_rate = (
            (variant_conversions / variant_metrics["unique_users"] * 100)
            if variant_metrics["unique_users"] > 0
            else 0
        )
        context["conversion_rates"] = {
            "control": round(control_rate, 2),
            "variant": round(variant_rate, 2),
            "improvement": round(variant_rate - control_rate, 2),
        }
        return context


class ABTestStopView(LoginRequiredMixin, PlatformAdminRequiredMixin, View):
    """Stop an A/B test."""

    def post(self, request, pk):
        ab_test = get_object_or_404(ABTestVariant, pk=pk)
        ab_test.stop_test()
        messages.success(request, f"A/B test '{ab_test.name}' stopped successfully.")
        return redirect("core:ab_test_detail", pk=pk)


class EmergencyKillSwitchListView(LoginRequiredMixin, PlatformAdminRequiredMixin, ListView):
    """List all emergency kill switches."""

    model = EmergencyKillSwitch
    template_name = "core/feature_flags/kill_switch_list.html"
    context_object_name = "kill_switches"
    paginate_by = 20

    def get_queryset(self):
        queryset = EmergencyKillSwitch.objects.select_related(
            "disabled_by", "re_enabled_by"
        ).order_by("-disabled_at")
        status = self.request.GET.get("status")
        if status == "active":
            queryset = queryset.filter(is_active=True)
        elif status == "resolved":
            queryset = queryset.filter(is_active=False)
        return queryset


class EmergencyKillSwitchCreateView(LoginRequiredMixin, PlatformAdminRequiredMixin, CreateView):
    """Activate emergency kill switch for a flag."""

    model = EmergencyKillSwitch
    form_class = EmergencyKillSwitchForm
    template_name = "core/feature_flags/kill_switch_form.html"
    success_url = reverse_lazy("core:kill_switch_list")

    def form_valid(self, form):
        flag_name = form.cleaned_data["flag_name"]
        reason = form.cleaned_data["reason"]
        emergency_disable_flag(flag_name, self.request.user, reason)
        messages.warning(
            self.request, f"EMERGENCY: Feature '{flag_name}' has been disabled immediately!"
        )
        return redirect(self.success_url)


class EmergencyKillSwitchReEnableView(LoginRequiredMixin, PlatformAdminRequiredMixin, View):
    """Re-enable a feature after emergency disable."""

    def post(self, request, pk):
        kill_switch = get_object_or_404(EmergencyKillSwitch, pk=pk)
        kill_switch.re_enable(request.user)
        messages.success(request, f"Feature '{kill_switch.flag_name}' has been re-enabled.")
        return redirect("core:kill_switch_list")


class FeatureFlagMetricsDashboardView(LoginRequiredMixin, PlatformAdminRequiredMixin, View):
    """Dashboard showing metrics for all feature flags."""

    template_name = "core/feature_flags/metrics_dashboard.html"

    def get(self, request):
        flags = Flag.objects.all().order_by("name")
        flag_metrics = []
        for flag in flags:
            metrics = get_flag_conversion_metrics(flag.name)
            flag_metrics.append({"flag": flag, "metrics": metrics})
        ab_tests = ABTestVariant.objects.filter(is_active=True).select_related("flag")
        context = {"flag_metrics": flag_metrics, "ab_tests": ab_tests}
        return render(request, self.template_name, context)


class FeatureFlagStatsAPIView(LoginRequiredMixin, PlatformAdminRequiredMixin, View):
    """API endpoint for feature flag statistics."""

    def get(self, request):
        stats = {
            "total_flags": Flag.objects.count(),
            "active_flags": Flag.objects.filter(everyone=True).count(),
            "inactive_flags": Flag.objects.filter(everyone=False).count(),
            "percentage_flags": Flag.objects.filter(everyone=None).exclude(percent=None).count(),
            "tenant_overrides": TenantFeatureFlag.objects.count(),
            "active_kill_switches": EmergencyKillSwitch.objects.filter(is_active=True).count(),
            "active_ab_tests": ABTestVariant.objects.filter(is_active=True).count(),
            "total_metrics": FeatureFlagMetric.objects.count(),
        }
        return JsonResponse(stats)


class FeatureFlagToggleAPIView(LoginRequiredMixin, PlatformAdminRequiredMixin, View):
    """API endpoint to quickly toggle a flag on/off."""

    def post(self, request, pk):
        flag = get_object_or_404(Flag, pk=pk)
        if flag.everyone is True:
            flag.everyone = False
            action = "disabled"
        else:
            flag.everyone = True
            action = "enabled"
        flag.save()
        FeatureFlagHistory.objects.create(
            flag_name=flag.name,
            flag_type="flag",
            action=action,
            new_value={"everyone": flag.everyone},
            changed_by=request.user,
            reason=f"Quick toggle by {request.user.username}",
        )
        return JsonResponse({"success": True, "flag_name": flag.name, "enabled": flag.everyone})
