"""
Admin panel views for platform administrators.

This module contains views for the admin dashboard and platform management.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

import psutil

from apps.core.models import Tenant, User


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


# ============================================================================
# Tenant Management Views
# ============================================================================


class TenantListView(PlatformAdminRequiredMixin, ListView):
    """
    List view for all tenants with search and filters.

    Supports filtering by:
    - Status (active, suspended, pending_deletion)
    - Registration date range
    - Search by company name or slug
    """

    model = Tenant
    template_name = "admin/tenant_list.html"
    context_object_name = "tenants"
    paginate_by = 20

    def get_queryset(self):
        queryset = Tenant.objects.all().select_related()

        # Search filter
        search_query = self.request.GET.get("search", "").strip()
        if search_query:
            queryset = queryset.filter(
                Q(company_name__icontains=search_query) | Q(slug__icontains=search_query)
            )

        # Status filter
        status = self.request.GET.get("status", "").strip()
        if status:
            queryset = queryset.filter(status=status)

        # Date range filter
        date_from = self.request.GET.get("date_from", "").strip()
        date_to = self.request.GET.get("date_to", "").strip()

        if date_from:
            try:
                from datetime import datetime

                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
                queryset = queryset.filter(created_at__gte=date_from_obj)
            except ValueError:
                pass

        if date_to:
            try:
                from datetime import datetime

                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
                # Add one day to include the entire end date
                date_to_obj = date_to_obj + timedelta(days=1)
                queryset = queryset.filter(created_at__lt=date_to_obj)
            except ValueError:
                pass

        # Default ordering
        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add filter values to context for form persistence
        context["search_query"] = self.request.GET.get("search", "")
        context["status_filter"] = self.request.GET.get("status", "")
        context["date_from"] = self.request.GET.get("date_from", "")
        context["date_to"] = self.request.GET.get("date_to", "")

        # Add status choices for filter dropdown
        context["status_choices"] = Tenant.STATUS_CHOICES

        # Add statistics
        context["total_tenants"] = Tenant.objects.count()
        context["active_tenants"] = Tenant.objects.filter(status=Tenant.ACTIVE).count()
        context["suspended_tenants"] = Tenant.objects.filter(status=Tenant.SUSPENDED).count()
        context["pending_deletion_tenants"] = Tenant.objects.filter(
            status=Tenant.PENDING_DELETION
        ).count()

        return context


class TenantDetailView(PlatformAdminRequiredMixin, DetailView):
    """
    Detail view for a single tenant with tabs.

    Tabs:
    - Info: Basic tenant information
    - Users: List of tenant users
    - Subscription: Subscription details (placeholder for future)
    - Activity: Recent activity log (placeholder for future)
    """

    model = Tenant
    template_name = "admin/tenant_detail.html"
    context_object_name = "tenant"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.object

        # Get tenant users
        users = User.objects.filter(tenant=tenant).select_related("branch")
        context["users"] = users
        context["user_count"] = users.count()

        # Get tenant branches
        from apps.core.models import Branch

        branches = Branch.objects.filter(tenant=tenant)
        context["branches"] = branches
        context["branch_count"] = branches.count()

        # Get active tab from query parameter
        context["active_tab"] = self.request.GET.get("tab", "info")

        # Placeholder for subscription info (will be implemented in task 17)
        context["subscription"] = None

        # Placeholder for activity log (will be implemented in task 20)
        context["recent_activities"] = []

        return context


class TenantCreateView(PlatformAdminRequiredMixin, CreateView):
    """
    Create view for new tenants.

    Allows platform administrators to manually create tenant accounts.
    """

    model = Tenant
    form_class = None  # Will be set after creating the form
    template_name = "admin/tenant_form.html"
    success_url = reverse_lazy("core:admin_tenant_list")

    def get_form_class(self):
        from apps.core.forms import TenantCreateForm

        return TenantCreateForm

    def form_valid(self, form):
        response = super().form_valid(form)

        from django.contrib import messages

        messages.success(self.request, f'Tenant "{self.object.company_name}" created successfully.')

        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = "Create New Tenant"
        context["submit_text"] = "Create Tenant"
        return context


class TenantUpdateView(PlatformAdminRequiredMixin, UpdateView):
    """
    Update view for editing tenant information.

    Allows platform administrators to modify tenant details.
    """

    model = Tenant
    form_class = None  # Will be set after creating the form
    template_name = "admin/tenant_form.html"

    def get_form_class(self):
        from apps.core.forms import TenantEditForm

        return TenantEditForm

    def get_success_url(self):
        return reverse("core:admin_tenant_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)

        from django.contrib import messages

        messages.success(self.request, f'Tenant "{self.object.company_name}" updated successfully.')

        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = f"Edit Tenant: {self.object.company_name}"
        context["submit_text"] = "Save Changes"
        context["tenant"] = self.object
        return context


class TenantStatusChangeView(PlatformAdminRequiredMixin, View):
    """
    View to change tenant status (activate, suspend, mark for deletion).

    Handles POST requests to change tenant status with confirmation.
    Implements:
    - Suspend: Disables access, retains data
    - Schedule for deletion: Sets grace period before permanent deletion
    - Reactivate: Restores full access
    """

    def post(self, request, pk):
        tenant = get_object_or_404(Tenant, pk=pk)
        new_status = request.POST.get("status")

        if new_status not in [Tenant.ACTIVE, Tenant.SUSPENDED, Tenant.PENDING_DELETION]:
            messages.error(request, "Invalid status value.")
            return redirect("core:admin_tenant_detail", pk=pk)

        old_status = tenant.status
        tenant.status = new_status
        tenant.save(update_fields=["status", "updated_at"])

        # Log the status change (will be enhanced with audit log in task 20)
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"Tenant status changed: {tenant.company_name} ({tenant.id}) "
            f"from {old_status} to {new_status} by {request.user.username}"
        )

        messages.success(
            request, f'Tenant "{tenant.company_name}" status changed successfully.'
        )

        return redirect("core:admin_tenant_detail", pk=pk)


class TenantDeleteView(PlatformAdminRequiredMixin, DeleteView):
    """
    Delete view for permanently deleting a tenant.

    This is a destructive action and should be used with caution.
    Typically, tenants should be marked for deletion instead.
    """

    model = Tenant
    template_name = "admin/tenant_confirm_delete.html"
    success_url = reverse_lazy("core:admin_tenant_list")

    def delete(self, request, *args, **kwargs):
        tenant = self.get_object()
        tenant_name = tenant.company_name

        response = super().delete(request, *args, **kwargs)

        from django.contrib import messages

        messages.success(request, f'Tenant "{tenant_name}" has been permanently deleted.')

        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.object

        # Get counts of related data that will be deleted
        context["user_count"] = User.objects.filter(tenant=tenant).count()

        from apps.core.models import Branch

        context["branch_count"] = Branch.objects.filter(tenant=tenant).count()

        # Warning message
        context["warning_message"] = (
            "This action will permanently delete the tenant and ALL associated data, "
            "including users, branches, inventory, sales, and customer records. "
            "This action cannot be undone."
        )

        return context
