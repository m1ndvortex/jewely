"""
Admin panel views for platform administrators.

This module contains views for the admin dashboard and platform management.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

import psutil

from apps.core.models import Tenant


class PlatformAdminRequiredMixin(LoginRequiredMixin):
    """Mixin to require platform admin access."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_platform_admin():
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied("You must be a platform administrator to access this page.")
        return super().dispatch(request, *args, **kwargs)


class AdminDashboardView(PlatformAdminRequiredMixin, TemplateView):
    """
    Main admin dashboard view for platform administrators.

    Displays:
    - Tenant metrics (signups, active, suspended)
    - Revenue metrics (MRR, ARR, churn rate)
    - System health (CPU, memory, disk, database)
    - Error feed (recent errors from Sentry)
    """

    template_name = "admin/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get tenant metrics
        context["tenant_metrics"] = self.get_tenant_metrics()

        # Get revenue metrics (placeholder - will be implemented with subscription system)
        context["revenue_metrics"] = self.get_revenue_metrics()

        # Get system health
        context["system_health"] = self.get_system_health()

        return context

    def get_tenant_metrics(self):
        """Get tenant signup and status metrics."""
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)

        # Total tenants by status
        total_tenants = Tenant.objects.count()
        active_tenants = Tenant.objects.filter(status=Tenant.ACTIVE).count()
        suspended_tenants = Tenant.objects.filter(status=Tenant.SUSPENDED).count()
        pending_deletion = Tenant.objects.filter(status=Tenant.PENDING_DELETION).count()

        # New signups in last 30 days
        new_signups_30d = Tenant.objects.filter(created_at__gte=thirty_days_ago).count()

        # New signups today
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        new_signups_today = Tenant.objects.filter(created_at__gte=today_start).count()

        return {
            "total": total_tenants,
            "active": active_tenants,
            "suspended": suspended_tenants,
            "pending_deletion": pending_deletion,
            "new_signups_30d": new_signups_30d,
            "new_signups_today": new_signups_today,
        }

    def get_revenue_metrics(self):
        """
        Get revenue metrics (MRR, ARR, churn rate).

        Note: This is a placeholder. Will be fully implemented when
        subscription and billing system is added (Task 17).
        """
        # Placeholder values - will be calculated from subscription data
        return {
            "mrr": Decimal("0.00"),  # Monthly Recurring Revenue
            "arr": Decimal("0.00"),  # Annual Recurring Revenue
            "churn_rate": Decimal("0.00"),  # Percentage
            "note": "Revenue metrics will be available after subscription system implementation",
        }

    def get_system_health(self):
        """Get system health metrics (CPU, memory, disk)."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_gb = memory.used / (1024**3)
            memory_total_gb = memory.total / (1024**3)

            # Disk usage
            disk = psutil.disk_usage("/")
            disk_percent = disk.percent
            disk_used_gb = disk.used / (1024**3)
            disk_total_gb = disk.total / (1024**3)

            # Database connections (PostgreSQL)
            from django.db import connection

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database();"
                )
                db_connections = cursor.fetchone()[0]

            return {
                "cpu_percent": round(cpu_percent, 1),
                "memory_percent": round(memory_percent, 1),
                "memory_used_gb": round(memory_used_gb, 2),
                "memory_total_gb": round(memory_total_gb, 2),
                "disk_percent": round(disk_percent, 1),
                "disk_used_gb": round(disk_used_gb, 2),
                "disk_total_gb": round(disk_total_gb, 2),
                "db_connections": db_connections,
                "status": (
                    "healthy"
                    if cpu_percent < 80 and memory_percent < 80 and disk_percent < 80
                    else "warning"
                ),
            }
        except Exception as e:
            return {
                "error": str(e),
                "status": "error",
            }


class TenantMetricsAPIView(PlatformAdminRequiredMixin, View):
    """API endpoint for real-time tenant metrics updates."""

    def get(self, request):
        """Return tenant metrics as JSON."""
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)

        # Get metrics
        total_tenants = Tenant.objects.count()
        active_tenants = Tenant.objects.filter(status=Tenant.ACTIVE).count()
        suspended_tenants = Tenant.objects.filter(status=Tenant.SUSPENDED).count()
        pending_deletion = Tenant.objects.filter(status=Tenant.PENDING_DELETION).count()
        new_signups_30d = Tenant.objects.filter(created_at__gte=thirty_days_ago).count()

        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        new_signups_today = Tenant.objects.filter(created_at__gte=today_start).count()

        return JsonResponse(
            {
                "total": total_tenants,
                "active": active_tenants,
                "suspended": suspended_tenants,
                "pending_deletion": pending_deletion,
                "new_signups_30d": new_signups_30d,
                "new_signups_today": new_signups_today,
                "timestamp": now.isoformat(),
            }
        )


class SystemHealthAPIView(PlatformAdminRequiredMixin, View):
    """API endpoint for real-time system health updates."""

    def get(self, request):
        """Return system health metrics as JSON."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_gb = memory.used / (1024**3)
            memory_total_gb = memory.total / (1024**3)

            # Disk usage
            disk = psutil.disk_usage("/")
            disk_percent = disk.percent
            disk_used_gb = disk.used / (1024**3)
            disk_total_gb = disk.total / (1024**3)

            # Database connections
            from django.db import connection

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database();"
                )
                db_connections = cursor.fetchone()[0]

            # Determine overall status
            status = "healthy"
            if cpu_percent > 90 or memory_percent > 90 or disk_percent > 90:
                status = "critical"
            elif cpu_percent > 80 or memory_percent > 80 or disk_percent > 80:
                status = "warning"

            return JsonResponse(
                {
                    "cpu_percent": round(cpu_percent, 1),
                    "memory_percent": round(memory_percent, 1),
                    "memory_used_gb": round(memory_used_gb, 2),
                    "memory_total_gb": round(memory_total_gb, 2),
                    "disk_percent": round(disk_percent, 1),
                    "disk_used_gb": round(disk_used_gb, 2),
                    "disk_total_gb": round(disk_total_gb, 2),
                    "db_connections": db_connections,
                    "status": status,
                    "timestamp": timezone.now().isoformat(),
                }
            )
        except Exception as e:
            return JsonResponse(
                {
                    "error": str(e),
                    "status": "error",
                    "timestamp": timezone.now().isoformat(),
                },
                status=500,
            )


class TenantSignupChartAPIView(PlatformAdminRequiredMixin, View):
    """API endpoint for tenant signup chart data."""

    def get(self, request):
        """Return tenant signup data for the last 30 days."""
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)

        # Get daily signup counts for last 30 days
        daily_signups = []
        for i in range(30):
            day_start = (thirty_days_ago + timedelta(days=i)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            day_end = day_start + timedelta(days=1)

            count = Tenant.objects.filter(created_at__gte=day_start, created_at__lt=day_end).count()

            daily_signups.append(
                {
                    "date": day_start.strftime("%Y-%m-%d"),
                    "count": count,
                }
            )

        return JsonResponse(
            {
                "labels": [item["date"] for item in daily_signups],
                "data": [item["count"] for item in daily_signups],
                "timestamp": now.isoformat(),
            }
        )


class ErrorFeedAPIView(PlatformAdminRequiredMixin, View):
    """
    API endpoint for recent errors from Sentry.

    Note: This is a placeholder. Will be fully implemented when
    Sentry integration is added (Task 29.4).
    """

    def get(self, request):
        """Return recent errors."""
        # Placeholder - will integrate with Sentry API
        return JsonResponse(
            {
                "errors": [],
                "note": "Error feed will be available after Sentry integration",
                "timestamp": timezone.now().isoformat(),
            }
        )
