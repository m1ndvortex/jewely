"""
Alert management views for platform administrators.

This module provides:
- Alert rule configuration interface
- Alert history and acknowledgment
- Alert dashboard

Per Requirements 7 - System Monitoring and Health Dashboard
"""

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)

from apps.core.admin_views import PlatformAdminRequiredMixin
from apps.core.alert_models import AlertRule, MonitoringAlert


class AlertDashboardView(PlatformAdminRequiredMixin, TemplateView):
    """
    Alert dashboard showing active alerts and statistics.

    Requirement 7.8: Log all alerts with timestamps and resolution status.
    """

    template_name = "monitoring/alerts/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get active alerts
        context["active_alerts"] = MonitoringAlert.objects.filter(
            status=MonitoringAlert.ACTIVE
        ).select_related("alert_rule")[:10]

        # Get alert statistics
        context["stats"] = {
            "active_count": MonitoringAlert.objects.filter(status=MonitoringAlert.ACTIVE).count(),
            "acknowledged_count": MonitoringAlert.objects.filter(
                status=MonitoringAlert.ACKNOWLEDGED
            ).count(),
            "resolved_today": MonitoringAlert.objects.filter(
                status=MonitoringAlert.RESOLVED,
                resolved_at__date=timezone.now().date(),
            ).count(),
            "escalated_count": MonitoringAlert.objects.filter(
                status=MonitoringAlert.ESCALATED
            ).count(),
        }

        # Get alert rules
        context["alert_rules"] = AlertRule.objects.all()[:5]
        context["enabled_rules_count"] = AlertRule.objects.filter(is_enabled=True).count()

        # Get recent alerts by severity
        context["critical_alerts"] = MonitoringAlert.objects.filter(
            alert_rule__severity=AlertRule.CRITICAL, status=MonitoringAlert.ACTIVE
        ).count()

        context["warning_alerts"] = MonitoringAlert.objects.filter(
            alert_rule__severity=AlertRule.WARNING, status=MonitoringAlert.ACTIVE
        ).count()

        return context


class AlertRuleListView(PlatformAdminRequiredMixin, ListView):
    """
    List all alert rules.

    Requirement 7.6: Provide alert configuration for CPU, memory, disk space, and other metrics.
    """

    model = AlertRule
    template_name = "monitoring/alerts/rule_list.html"
    context_object_name = "rules"
    paginate_by = 20

    def get_queryset(self):
        queryset = AlertRule.objects.all()

        # Filter by metric type
        metric_type = self.request.GET.get("metric_type")
        if metric_type:
            queryset = queryset.filter(metric_type=metric_type)

        # Filter by enabled status
        enabled = self.request.GET.get("enabled")
        if enabled == "true":
            queryset = queryset.filter(is_enabled=True)
        elif enabled == "false":
            queryset = queryset.filter(is_enabled=False)

        # Filter by severity
        severity = self.request.GET.get("severity")
        if severity:
            queryset = queryset.filter(severity=severity)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["metric_types"] = AlertRule.METRIC_TYPE_CHOICES
        context["severities"] = AlertRule.SEVERITY_CHOICES
        return context


class AlertRuleCreateView(PlatformAdminRequiredMixin, CreateView):
    """
    Create a new alert rule.

    Requirement 7.6: Provide alert configuration for CPU, memory, disk space, and other metrics.
    """

    model = AlertRule
    template_name = "monitoring/alerts/rule_form.html"
    fields = [
        "name",
        "description",
        "metric_type",
        "operator",
        "threshold",
        "severity",
        "is_enabled",
        "check_interval_minutes",
        "cooldown_minutes",
        "send_email",
        "send_sms",
        "send_slack",
        "email_recipients",
        "sms_recipients",
        "slack_channel",
        "escalate_after_minutes",
        "escalation_email_recipients",
    ]
    success_url = reverse_lazy("monitoring:alert_rule_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Alert rule created successfully.")
        return super().form_valid(form)


class AlertRuleUpdateView(PlatformAdminRequiredMixin, UpdateView):
    """Update an existing alert rule."""

    model = AlertRule
    template_name = "monitoring/alerts/rule_form.html"
    fields = [
        "name",
        "description",
        "metric_type",
        "operator",
        "threshold",
        "severity",
        "is_enabled",
        "check_interval_minutes",
        "cooldown_minutes",
        "send_email",
        "send_sms",
        "send_slack",
        "email_recipients",
        "sms_recipients",
        "slack_channel",
        "escalate_after_minutes",
        "escalation_email_recipients",
    ]
    success_url = reverse_lazy("monitoring:alert_rule_list")

    def form_valid(self, form):
        messages.success(self.request, "Alert rule updated successfully.")
        return super().form_valid(form)


class AlertRuleDeleteView(PlatformAdminRequiredMixin, DeleteView):
    """Delete an alert rule."""

    model = AlertRule
    template_name = "monitoring/alerts/rule_confirm_delete.html"
    success_url = reverse_lazy("monitoring:alert_rule_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Alert rule deleted successfully.")
        return super().delete(request, *args, **kwargs)


class AlertRuleToggleView(PlatformAdminRequiredMixin, View):
    """Toggle alert rule enabled status."""

    def post(self, request, pk):
        rule = get_object_or_404(AlertRule, pk=pk)
        rule.is_enabled = not rule.is_enabled
        rule.save()

        status = "enabled" if rule.is_enabled else "disabled"
        messages.success(request, f"Alert rule {status} successfully.")

        return redirect("monitoring:alert_rule_list")


class MonitoringAlertListView(PlatformAdminRequiredMixin, ListView):
    """
    List all monitoring alerts.

    Requirement 7.8: Log all alerts with timestamps and resolution status.
    """

    model = MonitoringAlert
    template_name = "monitoring/alerts/alert_list.html"
    context_object_name = "alerts"
    paginate_by = 50

    def get_queryset(self):
        queryset = MonitoringAlert.objects.select_related(
            "alert_rule", "acknowledged_by", "resolved_by"
        )

        # Filter by status
        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)

        # Filter by severity
        severity = self.request.GET.get("severity")
        if severity:
            queryset = queryset.filter(alert_rule__severity=severity)

        # Filter by date range
        date_from = self.request.GET.get("date_from")
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)

        date_to = self.request.GET.get("date_to")
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["statuses"] = MonitoringAlert.STATUS_CHOICES
        context["severities"] = AlertRule.SEVERITY_CHOICES
        return context


class MonitoringAlertDetailView(PlatformAdminRequiredMixin, DetailView):
    """View alert details."""

    model = MonitoringAlert
    template_name = "monitoring/alerts/alert_detail.html"
    context_object_name = "alert"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get delivery logs
        context["delivery_logs"] = self.object.delivery_logs.all()

        return context


class AlertAcknowledgeView(PlatformAdminRequiredMixin, View):
    """
    Acknowledge an alert.

    Requirement 7.8: Create alert history and acknowledgment.
    """

    def post(self, request, pk):
        alert = get_object_or_404(MonitoringAlert, pk=pk)

        if alert.status == MonitoringAlert.ACTIVE:
            notes = request.POST.get("notes", "")
            alert.acknowledge(request.user, notes)
            messages.success(request, "Alert acknowledged successfully.")
        else:
            messages.warning(request, "Alert is not active.")

        # Redirect back to referrer or alert list
        return redirect(request.META.get("HTTP_REFERER", "monitoring:alert_list"))


class AlertResolveView(PlatformAdminRequiredMixin, View):
    """
    Resolve an alert.

    Requirement 7.8: Create alert history and acknowledgment.
    """

    def post(self, request, pk):
        alert = get_object_or_404(MonitoringAlert, pk=pk)

        if alert.status in [MonitoringAlert.ACTIVE, MonitoringAlert.ACKNOWLEDGED]:
            notes = request.POST.get("notes", "")
            alert.resolve(request.user, notes)
            messages.success(request, "Alert resolved successfully.")
        else:
            messages.warning(request, "Alert is already resolved.")

        # Redirect back to referrer or alert list
        return redirect(request.META.get("HTTP_REFERER", "monitoring:alert_list"))


class AlertBulkActionView(PlatformAdminRequiredMixin, View):
    """Perform bulk actions on alerts."""

    def post(self, request):
        action = request.POST.get("action")
        alert_ids = request.POST.getlist("alert_ids")

        if not alert_ids:
            messages.warning(request, "No alerts selected.")
            return redirect("monitoring:alert_list")

        alerts = MonitoringAlert.objects.filter(id__in=alert_ids)

        if action == "acknowledge":
            count = 0
            for alert in alerts:
                if alert.status == MonitoringAlert.ACTIVE:
                    alert.acknowledge(request.user, "Bulk acknowledged")
                    count += 1
            messages.success(request, f"{count} alerts acknowledged.")

        elif action == "resolve":
            count = 0
            for alert in alerts:
                if alert.status in [MonitoringAlert.ACTIVE, MonitoringAlert.ACKNOWLEDGED]:
                    alert.resolve(request.user, "Bulk resolved")
                    count += 1
            messages.success(request, f"{count} alerts resolved.")

        return redirect("monitoring:alert_list")


class AlertStatsAPIView(PlatformAdminRequiredMixin, View):
    """API endpoint for alert statistics."""

    def get(self, request):
        """Get alert statistics."""

        # Get counts by status
        status_counts = {}
        for status, _ in MonitoringAlert.STATUS_CHOICES:
            status_counts[status.lower()] = MonitoringAlert.objects.filter(status=status).count()

        # Get counts by severity
        severity_counts = {}
        for severity, _ in AlertRule.SEVERITY_CHOICES:
            severity_counts[severity.lower()] = MonitoringAlert.objects.filter(
                alert_rule__severity=severity, status=MonitoringAlert.ACTIVE
            ).count()

        # Get recent alerts
        recent_alerts = []
        for alert in MonitoringAlert.objects.select_related("alert_rule")[:10]:
            recent_alerts.append(
                {
                    "id": str(alert.id),
                    "rule_name": alert.alert_rule.name,
                    "message": alert.message,
                    "severity": alert.alert_rule.severity,
                    "status": alert.status,
                    "created_at": alert.created_at.isoformat(),
                }
            )

        return JsonResponse(
            {
                "status_counts": status_counts,
                "severity_counts": severity_counts,
                "recent_alerts": recent_alerts,
                "timestamp": timezone.now().isoformat(),
            }
        )
