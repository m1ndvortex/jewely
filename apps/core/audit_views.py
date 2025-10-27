"""
Audit log explorer views for the jewelry shop SaaS platform.

This module provides comprehensive audit log viewing, searching, filtering,
and export functionality per Requirement 8.2.
"""

import csv
from datetime import datetime, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from apps.core.audit_models import APIRequestLog, AuditLog, DataChangeLog, LoginAttempt
from apps.core.permissions import is_platform_admin


class PlatformAdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin to require platform admin access."""

    def test_func(self):
        return is_platform_admin(self.request.user)


class AuditLogExplorerView(PlatformAdminRequiredMixin, ListView):
    """
    Main audit log explorer with advanced search and filtering.

    Per Requirement 8.2 - Implement audit log list view with advanced search.
    """

    model = AuditLog
    template_name = "core/audit/audit_log_explorer.html"
    context_object_name = "audit_logs"
    paginate_by = 50

    def get_queryset(self):  # noqa: C901
        """
        Get filtered and searched audit logs.

        Supports filtering by:
        - User
        - Action type
        - Date range
        - Tenant
        - IP address
        - Category
        - Severity
        - Search query (description, user, IP)
        """
        queryset = AuditLog.objects.select_related("user", "tenant", "content_type").order_by(
            "-timestamp"
        )

        # Search query
        search_query = self.request.GET.get("q", "").strip()
        if search_query:
            queryset = queryset.filter(
                Q(description__icontains=search_query)
                | Q(user__username__icontains=search_query)
                | Q(user__email__icontains=search_query)
                | Q(ip_address__icontains=search_query)
                | Q(request_path__icontains=search_query)
            )

        # Filter by user
        user_id = self.request.GET.get("user")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        # Filter by action
        action = self.request.GET.get("action")
        if action:
            queryset = queryset.filter(action=action)

        # Filter by category
        category = self.request.GET.get("category")
        if category:
            queryset = queryset.filter(category=category)

        # Filter by severity
        severity = self.request.GET.get("severity")
        if severity:
            queryset = queryset.filter(severity=severity)

        # Filter by tenant
        tenant_id = self.request.GET.get("tenant")
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)

        # Filter by IP address
        ip_address = self.request.GET.get("ip")
        if ip_address:
            queryset = queryset.filter(ip_address=ip_address)

        # Filter by date range
        date_from = self.request.GET.get("date_from")
        date_to = self.request.GET.get("date_to")

        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
                queryset = queryset.filter(timestamp__gte=date_from_obj)
            except ValueError:
                pass

        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
                # Include the entire day
                date_to_obj = date_to_obj.replace(hour=23, minute=59, second=59)
                queryset = queryset.filter(timestamp__lte=date_to_obj)
            except ValueError:
                pass

        # Quick date filters
        quick_filter = self.request.GET.get("quick_filter")
        if quick_filter:
            now = timezone.now()
            if quick_filter == "today":
                queryset = queryset.filter(timestamp__date=now.date())
            elif quick_filter == "yesterday":
                yesterday = now - timedelta(days=1)
                queryset = queryset.filter(timestamp__date=yesterday.date())
            elif quick_filter == "last_7_days":
                queryset = queryset.filter(timestamp__gte=now - timedelta(days=7))
            elif quick_filter == "last_30_days":
                queryset = queryset.filter(timestamp__gte=now - timedelta(days=30))
            elif quick_filter == "last_90_days":
                queryset = queryset.filter(timestamp__gte=now - timedelta(days=90))

        return queryset

    def get_context_data(self, **kwargs):
        """Add filter options and statistics to context."""
        context = super().get_context_data(**kwargs)

        # Get unique values for filters
        context["categories"] = AuditLog.CATEGORY_CHOICES
        context["actions"] = AuditLog.ACTION_CHOICES
        context["severities"] = AuditLog.SEVERITY_CHOICES

        # Get current filter values
        context["current_filters"] = {
            "q": self.request.GET.get("q", ""),
            "user": self.request.GET.get("user", ""),
            "action": self.request.GET.get("action", ""),
            "category": self.request.GET.get("category", ""),
            "severity": self.request.GET.get("severity", ""),
            "tenant": self.request.GET.get("tenant", ""),
            "ip": self.request.GET.get("ip", ""),
            "date_from": self.request.GET.get("date_from", ""),
            "date_to": self.request.GET.get("date_to", ""),
            "quick_filter": self.request.GET.get("quick_filter", ""),
        }

        # Get statistics for current filter
        queryset = self.get_queryset()
        context["total_count"] = queryset.count()
        context["category_counts"] = dict(
            queryset.values("category").annotate(count=Count("id")).values_list("category", "count")
        )
        context["severity_counts"] = dict(
            queryset.values("severity").annotate(count=Count("id")).values_list("severity", "count")
        )

        return context


class AuditLogDetailView(PlatformAdminRequiredMixin, DetailView):
    """
    Detailed view of a single audit log entry.

    Shows all metadata, changes, and related information.
    """

    model = AuditLog
    template_name = "core/audit/audit_log_detail.html"
    context_object_name = "audit_log"

    def get_context_data(self, **kwargs):
        """Add related audit logs to context."""
        context = super().get_context_data(**kwargs)

        audit_log = self.object

        # Get related audit logs (same user, same day)
        if audit_log.user:
            context["related_logs"] = (
                AuditLog.objects.filter(
                    user=audit_log.user, timestamp__date=audit_log.timestamp.date()
                )
                .exclude(id=audit_log.id)
                .order_by("-timestamp")[:10]
            )

        # Get related data changes if applicable
        if audit_log.content_type and audit_log.object_id:
            context["related_data_changes"] = DataChangeLog.objects.filter(
                content_type=audit_log.content_type, object_id=audit_log.object_id
            ).order_by("-timestamp")[:10]

        return context


class AuditLogExportView(PlatformAdminRequiredMixin, View):
    """
    Export audit logs to CSV.

    Per Requirement 8.2 - Create export to CSV functionality.
    """

    def get(self, request, *args, **kwargs):
        """Export filtered audit logs to CSV."""
        # Use the same filtering logic as the list view
        queryset = self._get_filtered_queryset()

        # Limit export to prevent memory issues
        max_export = 10000
        if queryset.count() > max_export:
            return JsonResponse(
                {"error": f"Export limited to {max_export} records. Please refine your filters."},
                status=400,
            )

        # Create CSV response
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="audit_logs_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        )

        writer = csv.writer(response)

        # Write header
        writer.writerow(
            [
                "Timestamp",
                "Category",
                "Action",
                "Severity",
                "User",
                "Tenant",
                "Description",
                "IP Address",
                "Request Method",
                "Request Path",
                "Response Status",
                "Affected Object",
            ]
        )

        # Write data
        for log in queryset.select_related("user", "tenant", "content_type"):
            writer.writerow(
                [
                    log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    log.get_category_display(),
                    log.get_action_display(),
                    log.get_severity_display(),
                    log.user.username if log.user else "System",
                    log.tenant.company_name if log.tenant else "Platform",
                    log.description,
                    log.ip_address or "",
                    log.request_method or "",
                    log.request_path or "",
                    log.response_status or "",
                    log.get_affected_object_display(),
                ]
            )

        return response

    def _get_filtered_queryset(self):  # noqa: C901
        """Get filtered queryset using same logic as list view."""
        queryset = AuditLog.objects.select_related("user", "tenant", "content_type").order_by(
            "-timestamp"
        )

        # Apply all filters from request
        search_query = self.request.GET.get("q", "").strip()
        if search_query:
            queryset = queryset.filter(
                Q(description__icontains=search_query)
                | Q(user__username__icontains=search_query)
                | Q(user__email__icontains=search_query)
                | Q(ip_address__icontains=search_query)
            )

        user_id = self.request.GET.get("user")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        action = self.request.GET.get("action")
        if action:
            queryset = queryset.filter(action=action)

        category = self.request.GET.get("category")
        if category:
            queryset = queryset.filter(category=category)

        severity = self.request.GET.get("severity")
        if severity:
            queryset = queryset.filter(severity=severity)

        tenant_id = self.request.GET.get("tenant")
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)

        ip_address = self.request.GET.get("ip")
        if ip_address:
            queryset = queryset.filter(ip_address=ip_address)

        date_from = self.request.GET.get("date_from")
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
                queryset = queryset.filter(timestamp__gte=date_from_obj)
            except ValueError:
                pass

        date_to = self.request.GET.get("date_to")
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
                date_to_obj = date_to_obj.replace(hour=23, minute=59, second=59)
                queryset = queryset.filter(timestamp__lte=date_to_obj)
            except ValueError:
                pass

        quick_filter = self.request.GET.get("quick_filter")
        if quick_filter:
            now = timezone.now()
            if quick_filter == "today":
                queryset = queryset.filter(timestamp__date=now.date())
            elif quick_filter == "yesterday":
                yesterday = now - timedelta(days=1)
                queryset = queryset.filter(timestamp__date=yesterday.date())
            elif quick_filter == "last_7_days":
                queryset = queryset.filter(timestamp__gte=now - timedelta(days=7))
            elif quick_filter == "last_30_days":
                queryset = queryset.filter(timestamp__gte=now - timedelta(days=30))
            elif quick_filter == "last_90_days":
                queryset = queryset.filter(timestamp__gte=now - timedelta(days=90))

        return queryset


class LoginAttemptExplorerView(PlatformAdminRequiredMixin, ListView):
    """
    Explorer for login attempts with filtering.

    Useful for security monitoring and brute force detection.
    """

    model = LoginAttempt
    template_name = "core/audit/login_attempt_explorer.html"
    context_object_name = "login_attempts"
    paginate_by = 50

    def get_queryset(self):  # noqa: C901
        """Get filtered login attempts."""
        queryset = LoginAttempt.objects.select_related("user").order_by("-timestamp")

        # Filter by username
        username = self.request.GET.get("username")
        if username:
            queryset = queryset.filter(username__icontains=username)

        # Filter by result
        result = self.request.GET.get("result")
        if result:
            queryset = queryset.filter(result=result)

        # Filter by IP address
        ip_address = self.request.GET.get("ip")
        if ip_address:
            queryset = queryset.filter(ip_address=ip_address)

        # Filter by date range
        date_from = self.request.GET.get("date_from")
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
                queryset = queryset.filter(timestamp__gte=date_from_obj)
            except ValueError:
                pass

        date_to = self.request.GET.get("date_to")
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
                date_to_obj = date_to_obj.replace(hour=23, minute=59, second=59)
                queryset = queryset.filter(timestamp__lte=date_to_obj)
            except ValueError:
                pass

        # Quick filters
        quick_filter = self.request.GET.get("quick_filter")
        if quick_filter:
            now = timezone.now()
            if quick_filter == "failed_only":
                queryset = queryset.exclude(result=LoginAttempt.RESULT_SUCCESS)
            elif quick_filter == "last_hour":
                queryset = queryset.filter(timestamp__gte=now - timedelta(hours=1))
            elif quick_filter == "last_24_hours":
                queryset = queryset.filter(timestamp__gte=now - timedelta(hours=24))

        return queryset

    def get_context_data(self, **kwargs):
        """Add filter options and statistics."""
        context = super().get_context_data(**kwargs)

        context["results"] = LoginAttempt.RESULT_CHOICES

        # Current filters
        context["current_filters"] = {
            "username": self.request.GET.get("username", ""),
            "result": self.request.GET.get("result", ""),
            "ip": self.request.GET.get("ip", ""),
            "date_from": self.request.GET.get("date_from", ""),
            "date_to": self.request.GET.get("date_to", ""),
            "quick_filter": self.request.GET.get("quick_filter", ""),
        }

        # Statistics
        queryset = self.get_queryset()
        context["total_count"] = queryset.count()
        context["failed_count"] = queryset.exclude(result=LoginAttempt.RESULT_SUCCESS).count()
        context["success_count"] = queryset.filter(result=LoginAttempt.RESULT_SUCCESS).count()

        return context


class DataChangeLogExplorerView(PlatformAdminRequiredMixin, ListView):
    """
    Explorer for data change logs with filtering.

    Shows detailed before/after values for all data modifications.
    """

    model = DataChangeLog
    template_name = "core/audit/data_change_explorer.html"
    context_object_name = "data_changes"
    paginate_by = 50

    def get_queryset(self):  # noqa: C901
        """Get filtered data changes."""
        queryset = DataChangeLog.objects.select_related("user", "tenant", "content_type").order_by(
            "-timestamp"
        )

        # Filter by user
        user_id = self.request.GET.get("user")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        # Filter by change type
        change_type = self.request.GET.get("change_type")
        if change_type:
            queryset = queryset.filter(change_type=change_type)

        # Filter by model type
        model_type = self.request.GET.get("model_type")
        if model_type:
            queryset = queryset.filter(content_type__model=model_type)

        # Filter by tenant
        tenant_id = self.request.GET.get("tenant")
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)

        # Filter by date range
        date_from = self.request.GET.get("date_from")
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
                queryset = queryset.filter(timestamp__gte=date_from_obj)
            except ValueError:
                pass

        date_to = self.request.GET.get("date_to")
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
                date_to_obj = date_to_obj.replace(hour=23, minute=59, second=59)
                queryset = queryset.filter(timestamp__lte=date_to_obj)
            except ValueError:
                pass

        return queryset

    def get_context_data(self, **kwargs):
        """Add filter options."""
        context = super().get_context_data(**kwargs)

        context["change_types"] = DataChangeLog.CHANGE_CHOICES

        context["current_filters"] = {
            "user": self.request.GET.get("user", ""),
            "change_type": self.request.GET.get("change_type", ""),
            "model_type": self.request.GET.get("model_type", ""),
            "tenant": self.request.GET.get("tenant", ""),
            "date_from": self.request.GET.get("date_from", ""),
            "date_to": self.request.GET.get("date_to", ""),
        }

        queryset = self.get_queryset()
        context["total_count"] = queryset.count()

        return context


class APIRequestLogExplorerView(PlatformAdminRequiredMixin, ListView):
    """
    Explorer for API request logs with filtering.

    Useful for monitoring API usage and debugging.
    """

    model = APIRequestLog
    template_name = "core/audit/api_request_explorer.html"
    context_object_name = "api_requests"
    paginate_by = 50

    def get_queryset(self):  # noqa: C901
        """Get filtered API requests."""
        queryset = APIRequestLog.objects.select_related("user", "tenant").order_by("-timestamp")

        # Filter by user
        user_id = self.request.GET.get("user")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        # Filter by method
        method = self.request.GET.get("method")
        if method:
            queryset = queryset.filter(method=method)

        # Filter by path
        path = self.request.GET.get("path")
        if path:
            queryset = queryset.filter(path__icontains=path)

        # Filter by status code
        status_code = self.request.GET.get("status_code")
        if status_code:
            queryset = queryset.filter(status_code=status_code)

        # Filter by status range
        status_range = self.request.GET.get("status_range")
        if status_range:
            if status_range == "2xx":
                queryset = queryset.filter(status_code__gte=200, status_code__lt=300)
            elif status_range == "4xx":
                queryset = queryset.filter(status_code__gte=400, status_code__lt=500)
            elif status_range == "5xx":
                queryset = queryset.filter(status_code__gte=500, status_code__lt=600)

        # Filter by tenant
        tenant_id = self.request.GET.get("tenant")
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)

        # Filter by date range
        date_from = self.request.GET.get("date_from")
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
                queryset = queryset.filter(timestamp__gte=date_from_obj)
            except ValueError:
                pass

        date_to = self.request.GET.get("date_to")
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
                date_to_obj = date_to_obj.replace(hour=23, minute=59, second=59)
                queryset = queryset.filter(timestamp__lte=date_to_obj)
            except ValueError:
                pass

        # Filter by slow requests
        slow_only = self.request.GET.get("slow_only")
        if slow_only:
            queryset = queryset.filter(response_time_ms__gte=1000)  # > 1 second

        return queryset

    def get_context_data(self, **kwargs):
        """Add filter options and statistics."""
        context = super().get_context_data(**kwargs)

        context["methods"] = ["GET", "POST", "PUT", "PATCH", "DELETE"]

        context["current_filters"] = {
            "user": self.request.GET.get("user", ""),
            "method": self.request.GET.get("method", ""),
            "path": self.request.GET.get("path", ""),
            "status_code": self.request.GET.get("status_code", ""),
            "status_range": self.request.GET.get("status_range", ""),
            "tenant": self.request.GET.get("tenant", ""),
            "date_from": self.request.GET.get("date_from", ""),
            "date_to": self.request.GET.get("date_to", ""),
            "slow_only": self.request.GET.get("slow_only", ""),
        }

        queryset = self.get_queryset()
        context["total_count"] = queryset.count()
        context["error_count"] = queryset.filter(status_code__gte=400).count()

        return context


class AuditLogRetentionView(PlatformAdminRequiredMixin, TemplateView):
    """
    Manage audit log retention policies.

    Per Requirement 8.2 - Implement log retention policies.
    """

    template_name = "core/audit/retention_policy.html"

    def get_context_data(self, **kwargs):
        """Add retention statistics."""
        context = super().get_context_data(**kwargs)

        now = timezone.now()

        # Calculate counts by age
        context["stats"] = {
            "total": AuditLog.objects.count(),
            "last_30_days": AuditLog.objects.filter(
                timestamp__gte=now - timedelta(days=30)
            ).count(),
            "last_90_days": AuditLog.objects.filter(
                timestamp__gte=now - timedelta(days=90)
            ).count(),
            "last_year": AuditLog.objects.filter(timestamp__gte=now - timedelta(days=365)).count(),
            "older_than_year": AuditLog.objects.filter(
                timestamp__lt=now - timedelta(days=365)
            ).count(),
        }

        # Login attempts
        context["login_stats"] = {
            "total": LoginAttempt.objects.count(),
            "last_30_days": LoginAttempt.objects.filter(
                timestamp__gte=now - timedelta(days=30)
            ).count(),
            "last_90_days": LoginAttempt.objects.filter(
                timestamp__gte=now - timedelta(days=90)
            ).count(),
        }

        # Data changes
        context["data_change_stats"] = {
            "total": DataChangeLog.objects.count(),
            "last_30_days": DataChangeLog.objects.filter(
                timestamp__gte=now - timedelta(days=30)
            ).count(),
            "last_90_days": DataChangeLog.objects.filter(
                timestamp__gte=now - timedelta(days=90)
            ).count(),
        }

        # API requests
        context["api_stats"] = {
            "total": APIRequestLog.objects.count(),
            "last_30_days": APIRequestLog.objects.filter(
                timestamp__gte=now - timedelta(days=30)
            ).count(),
            "last_90_days": APIRequestLog.objects.filter(
                timestamp__gte=now - timedelta(days=90)
            ).count(),
        }

        return context


class AuditLogRetentionExecuteView(PlatformAdminRequiredMixin, View):
    """
    Execute audit log retention policy (cleanup old logs).

    Per Requirement 8.2 - Implement log retention policies.
    """

    def post(self, request, *args, **kwargs):
        """Execute retention policy based on provided parameters."""
        retention_days = request.POST.get("retention_days")
        log_type = request.POST.get("log_type", "all")

        if not retention_days:
            return JsonResponse({"error": "Retention days required"}, status=400)

        try:
            retention_days = int(retention_days)
        except ValueError:
            return JsonResponse({"error": "Invalid retention days"}, status=400)

        if retention_days < 30:
            return JsonResponse(
                {"error": "Minimum retention period is 30 days for compliance"}, status=400
            )

        cutoff_date = timezone.now() - timedelta(days=retention_days)

        deleted_counts = {}

        # Delete based on log type
        if log_type in ["all", "audit_logs"]:
            deleted_counts["audit_logs"] = AuditLog.objects.filter(
                timestamp__lt=cutoff_date
            ).delete()[0]

        if log_type in ["all", "login_attempts"]:
            deleted_counts["login_attempts"] = LoginAttempt.objects.filter(
                timestamp__lt=cutoff_date
            ).delete()[0]

        if log_type in ["all", "data_changes"]:
            deleted_counts["data_changes"] = DataChangeLog.objects.filter(
                timestamp__lt=cutoff_date
            ).delete()[0]

        if log_type in ["all", "api_requests"]:
            deleted_counts["api_requests"] = APIRequestLog.objects.filter(
                timestamp__lt=cutoff_date
            ).delete()[0]

        # Log the retention execution
        from apps.core.audit import log_security_event

        log_security_event(
            event_type="system",
            description=f"Executed audit log retention policy: deleted logs older than {retention_days} days",
            user=request.user,
            severity="INFO",
            request=request,
            metadata={
                "retention_days": retention_days,
                "log_type": log_type,
                "deleted_counts": deleted_counts,
            },
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Successfully deleted old logs",
                "deleted_counts": deleted_counts,
            }
        )


class AuditLogStatsAPIView(PlatformAdminRequiredMixin, View):
    """
    API endpoint for audit log statistics.

    Used for dashboard widgets and charts.
    """

    def get(self, request, *args, **kwargs):
        """Get audit log statistics."""
        now = timezone.now()

        # Get counts by category
        category_stats = {}
        for category, label in AuditLog.CATEGORY_CHOICES:
            category_stats[category] = AuditLog.objects.filter(category=category).count()

        # Get counts by severity
        severity_stats = {}
        for severity, label in AuditLog.SEVERITY_CHOICES:
            severity_stats[severity] = AuditLog.objects.filter(severity=severity).count()

        # Get recent activity (last 24 hours)
        last_24h = now - timedelta(hours=24)
        recent_activity = {
            "total": AuditLog.objects.filter(timestamp__gte=last_24h).count(),
            "admin_actions": AuditLog.objects.filter(
                timestamp__gte=last_24h, category=AuditLog.CATEGORY_ADMIN
            ).count(),
            "user_activity": AuditLog.objects.filter(
                timestamp__gte=last_24h, category=AuditLog.CATEGORY_USER
            ).count(),
            "security_events": AuditLog.objects.filter(
                timestamp__gte=last_24h, category=AuditLog.CATEGORY_SECURITY
            ).count(),
        }

        # Get failed login attempts (last 24 hours)
        failed_logins = (
            LoginAttempt.objects.filter(timestamp__gte=last_24h)
            .exclude(result=LoginAttempt.RESULT_SUCCESS)
            .count()
        )

        return JsonResponse(
            {
                "category_stats": category_stats,
                "severity_stats": severity_stats,
                "recent_activity": recent_activity,
                "failed_logins_24h": failed_logins,
            }
        )
