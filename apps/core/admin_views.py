"""
Admin panel views for platform administrators.

This module contains views for the admin dashboard and platform management.
"""

import uuid
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
from django.views.generic import DeleteView, DetailView, ListView, TemplateView

import psutil

from apps.core.models import Tenant, User


class PlatformAdminRequiredMixin(LoginRequiredMixin):
    """
    Mixin to require platform admin access.

    Redirects unauthenticated users to platform admin login page,
    not the default tenant login page.
    """

    # Override login_url to point to platform admin login
    login_url = "/platform/login/"

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


class RecentActivityAPIView(PlatformAdminRequiredMixin, View):
    """API endpoint for recent platform activity."""

    def get(self, request):
        """Return recent tenant signups and changes."""
        limit = int(request.GET.get("limit", 10))

        # Get recent tenants
        recent_tenants = Tenant.objects.all().order_by("-created_at")[:limit]

        activities = []
        for tenant in recent_tenants:
            activities.append(
                {
                    "id": str(tenant.id),
                    "type": "tenant_created",
                    "tenant_name": tenant.company_name,
                    "tenant_slug": tenant.slug,
                    "status": tenant.status,
                    "created_at": tenant.created_at.isoformat(),
                    "description": f"New tenant '{tenant.company_name}' created",
                }
            )

        return JsonResponse(
            {
                "activities": activities,
                "count": len(activities),
                "timestamp": timezone.now().isoformat(),
            }
        )


# ============================================================================
# Tenant Management Views
# ============================================================================


class TenantListView(PlatformAdminRequiredMixin, ListView):
    """
    List view for all tenants with search, filters, sorting, and bulk operations.

    Supports:
    - Filtering by status, registration date range, search by company name or slug
    - Sorting by any column (ascending/descending) with visual indicators
    - Bulk selection with checkboxes and select all functionality
    - Quick action buttons (view detail, edit, impersonate owner, copy access URL)
    - CSV export functionality

    Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6
    """

    model = Tenant
    template_name = "admin/tenant_list.html"
    context_object_name = "tenants"
    paginate_by = 20

    # Valid sort columns mapping (Requirement 8.2)
    SORT_COLUMNS = {
        "company_name": "company_name",
        "slug": "slug",
        "status": "status",
        "user_count": "user_count",
        "storage_used": "storage_used",
        "created_at": "created_at",
        "last_activity": "last_activity",
    }

    def get_queryset(self):
        from django.db.models import Count, Max  # noqa: F401
        from django.db.models import OuterRef, Subquery, Value  # noqa: F401
        from django.db.models.functions import Coalesce  # noqa: F401

        queryset = Tenant.objects.all().select_related("settings")

        # Annotate with user count (Requirement 8.1)
        queryset = queryset.annotate(user_count=Count("users", distinct=True))

        # Annotate with last activity from AuditLog (Requirement 8.1)
        from apps.core.audit_models import AuditLog  # noqa: F401

        queryset = queryset.annotate(last_activity=Max("audit_logs__timestamp"))

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

        # Sorting (Requirement 8.2)
        sort_by = self.request.GET.get("sort_by", "created_at").strip()
        sort_order = self.request.GET.get("sort_order", "desc").strip()

        # Validate sort column
        if sort_by not in self.SORT_COLUMNS:
            sort_by = "created_at"

        # Build order_by clause
        order_field = self.SORT_COLUMNS[sort_by]
        if sort_order == "desc":
            order_field = f"-{order_field}"

        # Handle null values for last_activity
        if sort_by == "last_activity":
            from django.db.models import F

            if sort_order == "desc":
                queryset = queryset.order_by(F("last_activity").desc(nulls_last=True))
            else:
                queryset = queryset.order_by(F("last_activity").asc(nulls_first=True))
        else:
            queryset = queryset.order_by(order_field)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add filter values to context for form persistence
        context["search_query"] = self.request.GET.get("search", "")
        context["status_filter"] = self.request.GET.get("status", "")
        context["date_from"] = self.request.GET.get("date_from", "")
        context["date_to"] = self.request.GET.get("date_to", "")

        # Add sorting context (Requirement 8.2)
        context["sort_by"] = self.request.GET.get("sort_by", "created_at")
        context["sort_order"] = self.request.GET.get("sort_order", "desc")

        # Add status choices for filter dropdown
        context["status_choices"] = Tenant.STATUS_CHOICES

        # Add statistics
        context["total_tenants"] = Tenant.objects.count()
        context["active_tenants"] = Tenant.objects.filter(status=Tenant.ACTIVE).count()
        context["suspended_tenants"] = Tenant.objects.filter(status=Tenant.SUSPENDED).count()
        context["pending_deletion_tenants"] = Tenant.objects.filter(
            status=Tenant.PENDING_DELETION
        ).count()

        # Add tenant domains for quick access URL (Requirement 8.5)
        from apps.core.models import TenantDomain

        tenant_ids = [t.id for t in context["tenants"]]
        domains = TenantDomain.objects.filter(
            tenant_id__in=tenant_ids, is_primary=True
        ).select_related("tenant")
        context["tenant_domains"] = {str(d.tenant_id): d.domain for d in domains}

        # Add tenant owners for impersonation (Requirement 8.5)
        owners = User.objects.filter(
            tenant_id__in=tenant_ids, role=User.TENANT_OWNER, is_active=True
        ).values("tenant_id", "id", "username")
        context["tenant_owners"] = {str(o["tenant_id"]): o for o in owners}

        return context


class TenantDetailView(PlatformAdminRequiredMixin, DetailView):
    """
    Detail view for a single tenant with tabs.

    Tabs:
    - Info: Basic tenant information with statistics
    - Users: List of tenant users
    - Settings: Tenant settings management
    - Subscription: Subscription details (placeholder for future)
    - Activity: Recent activity log

    Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 7.1, 7.2, 7.6
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
        active_tab = self.request.GET.get("tab", "info")
        context["active_tab"] = active_tab

        # Load tab-specific context
        if active_tab == "info":
            context.update(self._get_info_context(tenant))
        elif active_tab == "users":
            context.update(self._get_users_context(tenant))
        elif active_tab == "settings":
            context.update(self._get_settings_context(tenant))
        elif active_tab == "activity":
            context.update(self._get_activity_context(tenant))

        # Placeholder for subscription info (will be implemented in task 17)
        context["subscription"] = None

        # Check if we should show the password modal (Requirement 1.9)
        # This happens when redirected from tenant creation
        show_password_modal = self.request.GET.get("show_password_modal") == "1"
        if show_password_modal:
            # Get password from session (one-time display)
            tenant_id = self.request.session.get("tenant_created_id")
            if tenant_id == str(tenant.id):
                context["show_password_modal"] = True
                context["initial_password"] = self.request.session.pop(
                    "tenant_created_password", None
                )
                context["initial_username"] = self.request.session.pop(
                    "tenant_created_username", None
                )
                # Clean up the tenant ID from session
                self.request.session.pop("tenant_created_id", None)

        # Check if we should show the user password modal (Requirement 3.4)
        show_user_password_modal = self.request.GET.get("show_user_password_modal") == "1"
        if show_user_password_modal:
            user_id = self.request.session.get("user_created_id")
            if user_id:
                context["show_user_password_modal"] = True
                context["user_initial_password"] = self.request.session.pop(
                    "user_created_password", None
                )
                context["user_initial_username"] = self.request.session.pop(
                    "user_created_username", None
                )
                self.request.session.pop("user_created_id", None)

        # Check if we should show the temp password modal (Requirement 3.7)
        show_temp_password_modal = self.request.GET.get("show_temp_password_modal") == "1"
        if show_temp_password_modal:
            temp_password = self.request.session.get("temp_password")
            if temp_password:
                context["show_temp_password_modal"] = True
                context["temp_password"] = self.request.session.pop("temp_password", None)
                context["temp_password_username"] = self.request.session.pop(
                    "temp_password_username", None
                )
                context["temp_password_expiry"] = self.request.session.pop(
                    "temp_password_expiry", None
                )

        # Security Summary (Requirement 10.4)
        # Count of users with MFA enabled
        context["mfa_enabled_count"] = users.filter(is_mfa_enabled=True).count()

        # Count of security events in last 7 days
        from apps.core.audit_models import AuditLog

        last_7_days = timezone.now() - timedelta(days=7)
        context["security_events_count"] = AuditLog.objects.filter(
            tenant=tenant, category=AuditLog.CATEGORY_SECURITY, timestamp__gte=last_7_days
        ).count()

        return context

    def _get_info_context(self, tenant) -> dict:
        """
        Get context for Information tab with comprehensive statistics.

        Provides:
        - User statistics (total, active, inactive, by role) - Requirement 6.1
        - Branch count and list with links - Requirement 6.2
        - Storage usage with progress bar - Requirement 6.3
        - Last activity and last active user - Requirement 6.4
        - Tenant access URLs with copy buttons - Requirement 6.5
        - Tenant owner info with verification status - Requirement 6.6, 7.1, 7.2, 7.6

        Args:
            tenant: The Tenant instance

        Returns:
            Dictionary with context data for the Information tab
        """
        from apps.core.models import Branch, TenantDomain
        from apps.core.services.tenant_service import TenantService

        # Get comprehensive statistics from TenantService
        tenant_service = TenantService()
        statistics = tenant_service.get_tenant_statistics(tenant)

        # Get tenant owner (Requirement 6.6, 7.1)
        owner = User.objects.filter(tenant=tenant, role=User.TENANT_OWNER, is_active=True).first()

        # Get owner email verification status (Requirement 7.6)
        owner_email_verified = False
        owner_email_verified_at = None
        if owner:
            # Check if email is verified using allauth if available
            try:
                from allauth.account.models import EmailAddress

                email_obj = EmailAddress.objects.filter(user=owner, email=owner.email).first()
                if email_obj:
                    owner_email_verified = email_obj.verified
                    # Note: allauth doesn't store verification date by default
            except ImportError:
                # allauth not installed, assume verified if user exists
                owner_email_verified = True

        # Get all tenant domains (Requirement 6.5, 7.2)
        domains = TenantDomain.objects.filter(tenant=tenant).order_by("-is_primary", "domain")
        subdomain = domains.filter(domain_type=TenantDomain.DOMAIN_TYPE_SUBDOMAIN).first()
        custom_domains = domains.filter(domain_type=TenantDomain.DOMAIN_TYPE_CUSTOM)

        # Get DNS verification records for custom domains (Requirement 9.4, 9.5)
        from apps.core.services.domain_service import DomainService

        domain_service = DomainService()

        custom_domains_with_dns = []
        for custom_domain in custom_domains:
            dns_records = domain_service.get_dns_verification_records(custom_domain.domain, tenant)
            custom_domains_with_dns.append(
                {
                    "domain": custom_domain,
                    "dns_records": dns_records,
                }
            )

        # Get branches with IDs for links (Requirement 6.2)
        branches_with_links = Branch.objects.filter(tenant=tenant).values("id", "name", "is_active")

        # Format storage for display
        storage_used_bytes = statistics.get("storage_used_bytes", 0)
        storage_percentage = statistics.get("storage_percentage", 0)

        # Convert bytes to human-readable format
        if storage_used_bytes >= 1024 * 1024 * 1024:
            storage_display = f"{storage_used_bytes / (1024 * 1024 * 1024):.2f} GB"
        elif storage_used_bytes >= 1024 * 1024:
            storage_display = f"{storage_used_bytes / (1024 * 1024):.2f} MB"
        elif storage_used_bytes >= 1024:
            storage_display = f"{storage_used_bytes / 1024:.2f} KB"
        else:
            storage_display = f"{storage_used_bytes} bytes"

        return {
            # User statistics (Requirement 6.1)
            "statistics": statistics,
            "user_count": statistics.get("user_count", 0),
            "active_users": statistics.get("active_users", 0),
            "inactive_users": statistics.get("inactive_users", 0),
            "users_by_role": statistics.get("users_by_role", {}),
            # Branch info (Requirement 6.2)
            "branch_count": statistics.get("branch_count", 0),
            "branch_names": statistics.get("branch_names", []),
            "branches_with_links": list(branches_with_links),
            # Storage usage (Requirement 6.3)
            "storage_used_bytes": storage_used_bytes,
            "storage_percentage": storage_percentage,
            "storage_display": storage_display,
            # Last activity (Requirement 6.4)
            "last_activity_timestamp": statistics.get("last_activity_timestamp"),
            "last_active_user": statistics.get("last_active_user"),
            # Tenant access URLs (Requirement 6.5, 7.2)
            "domains": domains,
            "subdomain": subdomain,
            "custom_domains": custom_domains,
            "custom_domains_with_dns": custom_domains_with_dns,
            # Tenant owner info (Requirement 6.6, 7.1, 7.6)
            "owner": owner,
            "owner_email_verified": owner_email_verified,
            "owner_email_verified_at": owner_email_verified_at,
            # Settings for display
            "settings": getattr(tenant, "settings", None),
        }

    def _get_users_context(self, tenant) -> dict:
        """
        Get context for Users tab with comprehensive user management.

        Provides:
        - Paginated user list with all columns - Requirement 3.1
        - Search by username/email - Requirement 3.2
        - Filters by role, status, branch - Requirement 3.2
        - Failed login count for each user - Requirement 10.2
        - Warning badge for >5 failed logins - Requirement 10.3
        - Login history for each user - Requirement 3.6
        - MFA status - Requirement 3.7

        Args:
            tenant: The Tenant instance

        Returns:
            Dictionary with context data for the Users tab
        """
        from datetime import timedelta

        from django.core.paginator import Paginator
        from django.db.models import Count
        from django.db.models import Q as DQ

        from apps.core.audit_models import LoginAttempt
        from apps.core.forms import TenantUserCreateForm
        from apps.core.models import Branch

        # Base queryset with related data
        users = User.objects.filter(tenant=tenant).select_related("branch").order_by("-date_joined")

        # Apply search filter (Requirement 3.2)
        search_query = self.request.GET.get("search", "").strip()
        if search_query:
            users = users.filter(
                DQ(username__icontains=search_query) | DQ(email__icontains=search_query)
            )

        # Apply role filter (Requirement 3.2)
        role_filter = self.request.GET.get("role", "").strip()
        if role_filter:
            users = users.filter(role=role_filter)

        # Apply status filter (Requirement 3.2)
        status_filter = self.request.GET.get("status", "").strip()
        if status_filter == "active":
            users = users.filter(is_active=True)
        elif status_filter == "inactive":
            users = users.filter(is_active=False)

        # Apply branch filter (Requirement 3.2)
        branch_filter = self.request.GET.get("branch", "").strip()
        if branch_filter:
            if branch_filter == "none":
                users = users.filter(branch__isnull=True)
            else:
                try:
                    users = users.filter(branch_id=branch_filter)
                except (ValueError, TypeError):
                    pass

        # Annotate with failed login count in last 24h (Requirement 10.2)
        last_24h = timezone.now() - timedelta(hours=24)
        users = users.annotate(
            failed_logins_24h=Count(
                "login_attempts",
                filter=DQ(
                    login_attempts__timestamp__gte=last_24h,
                )
                & ~DQ(login_attempts__result=LoginAttempt.RESULT_SUCCESS),
            )
        )

        # Get total count before pagination
        total_users = users.count()

        # Paginate (Requirement 3.1 - paginated list)
        paginator = Paginator(users, 20)
        page = self.request.GET.get("page", 1)
        users_page = paginator.get_page(page)

        # Get branches for filter dropdown
        branches = Branch.objects.filter(tenant=tenant).order_by("name")

        # Role choices for filter dropdown
        role_choices = [
            (User.TENANT_OWNER, "Shop Owner"),
            (User.TENANT_MANAGER, "Shop Manager"),
            (User.TENANT_EMPLOYEE, "Shop Employee"),
        ]

        # Create form for user creation modal
        create_form = TenantUserCreateForm(tenant=tenant)

        return {
            "users": users_page,
            "total_users": total_users,
            "search_query": search_query,
            "role_filter": role_filter,
            "status_filter": status_filter,
            "branch_filter": branch_filter,
            "role_choices": role_choices,
            "branches": branches,
            "create_form": create_form,
            "failed_login_threshold": 5,  # Requirement 10.3
        }

    def _get_settings_context(self, tenant) -> dict:
        """
        Get context for Settings tab with all TenantSettings fields.

        Provides:
        - Business Info form (business_name, registration_number, tax_id) - Requirement 5.1
        - Contact form (address, phone, email, website) - Requirement 5.1
        - Localization form (timezone, currency, date_format) - Requirement 5.4
        - Security form (require_mfa_for_managers, password_expiry_days) - Requirement 5.3
        - Branding form (logo, primary_color, secondary_color) - Requirement 5.5

        Args:
            tenant: The Tenant instance

        Returns:
            Dictionary with context data for the Settings tab
        """
        from apps.core.forms import (
            BrandingForm,
            BusinessInfoForm,
            ContactForm,
            LocalizationForm,
            SecurityForm,
        )

        # Get or create tenant settings
        settings = getattr(tenant, "settings", None)
        if not settings:
            from apps.core.models import TenantSettings

            settings, _ = TenantSettings.objects.get_or_create(tenant=tenant)

        # Create forms for each section with current settings data
        business_info_form = BusinessInfoForm(instance=settings, prefix="business")
        contact_form = ContactForm(instance=settings, prefix="contact")
        localization_form = LocalizationForm(instance=settings, prefix="localization")
        security_form = SecurityForm(instance=settings, prefix="security")
        branding_form = BrandingForm(instance=settings, prefix="branding")

        return {
            "settings": settings,
            "business_info_form": business_info_form,
            "contact_form": contact_form,
            "localization_form": localization_form,
            "security_form": security_form,
            "branding_form": branding_form,
        }

    def _get_activity_context(self, tenant) -> dict:
        """
        Get context for Activity tab with comprehensive audit log display.

        Provides:
        - Chronological AuditLog entries filtered by tenant - Requirement 4.1
        - Action, actor, timestamp, IP, user_agent, description - Requirement 4.2
        - Date range filter (24h, 7d, 30d, 90d, custom) - Requirement 4.3
        - Category filter - Requirement 4.4
        - Actor filter - Requirement 4.5
        - Pagination with 50 entries per page - Requirement 4.7
        - Security event highlighting - Requirement 10.1
        - Security events filter preset - Requirement 10.5

        Args:
            tenant: The Tenant instance

        Returns:
            Dictionary with context data for the Activity tab
        """
        from datetime import datetime

        from django.core.paginator import Paginator

        from apps.core.audit_models import AuditLog

        # Base queryset filtered by tenant (Requirement 4.1, 11.2)
        logs = AuditLog.objects.filter(tenant=tenant).select_related("user").order_by("-timestamp")

        # Date range filter (Requirement 4.3)
        date_range = self.request.GET.get("date_range", "7d")
        custom_start = self.request.GET.get("custom_start", "")
        custom_end = self.request.GET.get("custom_end", "")

        if date_range == "24h":
            since = timezone.now() - timedelta(hours=24)
            logs = logs.filter(timestamp__gte=since)
        elif date_range == "7d":
            since = timezone.now() - timedelta(days=7)
            logs = logs.filter(timestamp__gte=since)
        elif date_range == "30d":
            since = timezone.now() - timedelta(days=30)
            logs = logs.filter(timestamp__gte=since)
        elif date_range == "90d":
            since = timezone.now() - timedelta(days=90)
            logs = logs.filter(timestamp__gte=since)
        elif date_range == "custom":
            if custom_start:
                try:
                    start_date = datetime.strptime(custom_start, "%Y-%m-%d")
                    logs = logs.filter(timestamp__gte=start_date)
                except ValueError:
                    pass
            if custom_end:
                try:
                    end_date = datetime.strptime(custom_end, "%Y-%m-%d")
                    # Add one day to include the entire end date
                    end_date = end_date + timedelta(days=1)
                    logs = logs.filter(timestamp__lt=end_date)
                except ValueError:
                    pass

        # Category filter (Requirement 4.4)
        category_filter = self.request.GET.get("category", "")
        if category_filter:
            logs = logs.filter(category=category_filter)

        # Actor filter (Requirement 4.5)
        actor_filter = self.request.GET.get("actor", "")
        if actor_filter:
            try:
                logs = logs.filter(user_id=int(actor_filter))
            except (ValueError, TypeError):
                pass

        # Security events filter preset (Requirement 10.5)
        security_only = self.request.GET.get("security_only", "") == "1"
        if security_only:
            # Filter for security-related events
            security_actions = [
                AuditLog.ACTION_LOGIN_FAILED,
                AuditLog.ACTION_PASSWORD_CHANGE,
                AuditLog.ACTION_PASSWORD_RESET_REQUEST,
                AuditLog.ACTION_PASSWORD_RESET_COMPLETE,
                AuditLog.ACTION_MFA_ENABLE,
                AuditLog.ACTION_MFA_DISABLE,
                AuditLog.ACTION_MFA_VERIFY_FAILED,
                AuditLog.ACTION_SECURITY_BREACH_ATTEMPT,
                AuditLog.ACTION_SECURITY_SUSPICIOUS_ACTIVITY,
                AuditLog.ACTION_SECURITY_RATE_LIMIT_EXCEEDED,
                AuditLog.ACTION_SECURITY_UNAUTHORIZED_ACCESS,
                AuditLog.ACTION_IMPERSONATION_START,
                AuditLog.ACTION_IMPERSONATION_END,
            ]
            logs = logs.filter(
                Q(category=AuditLog.CATEGORY_SECURITY) | Q(action__in=security_actions)
            )

        # Get total count before pagination
        total_logs = logs.count()

        # Paginate with 50 entries per page (Requirement 4.7)
        paginator = Paginator(logs, 50)
        page = self.request.GET.get("page", 1)
        logs_page = paginator.get_page(page)

        # Get tenant users for actor filter dropdown
        tenant_users = User.objects.filter(tenant=tenant).order_by("username")

        # Define security actions for highlighting (Requirement 10.1)
        security_actions = [
            AuditLog.ACTION_LOGIN_FAILED,
            AuditLog.ACTION_PASSWORD_CHANGE,
            AuditLog.ACTION_PASSWORD_RESET_REQUEST,
            AuditLog.ACTION_PASSWORD_RESET_COMPLETE,
            AuditLog.ACTION_MFA_ENABLE,
            AuditLog.ACTION_MFA_DISABLE,
            AuditLog.ACTION_MFA_VERIFY_FAILED,
            AuditLog.ACTION_SECURITY_BREACH_ATTEMPT,
            AuditLog.ACTION_SECURITY_SUSPICIOUS_ACTIVITY,
            AuditLog.ACTION_SECURITY_RATE_LIMIT_EXCEEDED,
            AuditLog.ACTION_SECURITY_UNAUTHORIZED_ACCESS,
            AuditLog.ACTION_IMPERSONATION_START,
            AuditLog.ACTION_IMPERSONATION_END,
        ]

        return {
            "audit_logs": logs_page,
            "total_logs": total_logs,
            "date_range": date_range,
            "custom_start": custom_start,
            "custom_end": custom_end,
            "category_filter": category_filter,
            "actor_filter": actor_filter,
            "security_only": security_only,
            "category_choices": AuditLog.CATEGORY_CHOICES,
            "tenant_users": tenant_users,
            "security_actions": security_actions,
            "security_category": AuditLog.CATEGORY_SECURITY,
        }


class TenantCreateView(PlatformAdminRequiredMixin, View):
    """
    Create view for new tenants with comprehensive configuration.

    Allows platform administrators to manually create tenant accounts
    with full configuration including:
    - Basic Info (company_name, slug, status)
    - Business Settings (business_name, registration_number, tax_id, address, etc.)
    - Localization (timezone, currency, date_format)
    - Domain Configuration (subdomain, custom_domain)
    - Initial Admin User (username, email, password)

    Uses TenantService.create_tenant_with_owner() for atomic creation.
    Displays one-time password modal on success.
    Logs TENANT_CREATE in AuditLog.

    Requirements: 1.6, 1.7, 1.9, 1.11
    """

    template_name = "admin/tenant_create.html"

    def get(self, request):
        """Display the tenant creation form."""
        from apps.core.forms import EnhancedTenantCreateForm

        form = EnhancedTenantCreateForm()
        context = {
            "form": form,
            "form_title": "Create New Tenant",
            "submit_text": "Create Tenant",
        }
        from django.shortcuts import render

        return render(request, self.template_name, context)

    def post(self, request):
        """Handle tenant creation form submission."""
        from django.db import IntegrityError
        from django.shortcuts import render

        from apps.core.forms import EnhancedTenantCreateForm
        from apps.core.services.tenant_service import TenantService

        form = EnhancedTenantCreateForm(request.POST)

        if form.is_valid():
            try:
                # Extract data from form
                tenant_data = form.get_tenant_data()
                settings_data = form.get_settings_data()
                owner_data = form.get_owner_data()
                domain_data = form.get_domain_data()

                # Create tenant with owner using TenantService
                # This handles atomic creation and audit logging (Requirement 1.6, 1.7, 1.11)
                tenant_service = TenantService()
                tenant, owner_user, initial_password = tenant_service.create_tenant_with_owner(
                    tenant_data=tenant_data,
                    settings_data=settings_data,
                    owner_data=owner_data,
                    domain_data=domain_data,
                    created_by=request.user,
                )

                # Send welcome email with credentials (Requirement 1.10)
                # Note: Email verification URL would be generated here if email verification is enabled
                verification_url = None  # TODO: Generate verification URL if needed
                email_sent = tenant_service.send_welcome_email(
                    tenant=tenant,
                    owner=owner_user,
                    initial_password=initial_password,
                    verification_url=verification_url,
                )

                if email_sent:
                    messages.info(
                        request,
                        f"Welcome email sent to {owner_user.email} with login credentials.",
                    )
                else:
                    messages.warning(
                        request,
                        f"Tenant created successfully, but welcome email could not be sent to {owner_user.email}. "
                        "Please provide credentials manually.",
                    )

                # Store password in session for one-time display (Requirement 1.9)
                request.session["tenant_created_password"] = initial_password
                request.session["tenant_created_username"] = owner_user.username
                request.session["tenant_created_id"] = str(tenant.id)

                messages.success(
                    request,
                    f'Tenant "{tenant.company_name}" created successfully with owner "{owner_user.username}".',
                )

                # Redirect to tenant detail page with password modal flag
                return redirect(
                    reverse("core:admin_tenant_detail", kwargs={"pk": tenant.pk})
                    + "?show_password_modal=1"
                )

            except ValueError as e:
                # Handle validation errors from TenantService
                messages.error(request, f"Validation error: {str(e)}")
            except IntegrityError as e:
                # Handle database constraint violations
                error_msg = str(e)
                if "unique" in error_msg.lower():
                    if "slug" in error_msg.lower():
                        form.add_error("slug", "This slug is already in use.")
                    elif "username" in error_msg.lower():
                        form.add_error("admin_username", "This username is already in use.")
                    elif "domain" in error_msg.lower():
                        form.add_error("custom_domain", "This domain is already in use.")
                    else:
                        messages.error(
                            request, "A unique constraint was violated. Please check your input."
                        )
                else:
                    messages.error(request, f"Database error: {str(e)}")
            except Exception as e:
                # Handle unexpected errors
                import logging

                logger = logging.getLogger(__name__)
                logger.exception("Error creating tenant")
                messages.error(request, f"An unexpected error occurred: {str(e)}")

        # Re-render form with errors
        context = {
            "form": form,
            "form_title": "Create New Tenant",
            "submit_text": "Create Tenant",
        }
        return render(request, self.template_name, context)


class TenantUpdateView(PlatformAdminRequiredMixin, View):
    """
    Update view for editing tenant information with comprehensive configuration.

    Allows platform administrators to modify tenant details including:
    - Basic Info (company_name, slug, status)
    - Business Settings (business_name, registration_number, tax_id, address, etc.)
    - Localization (timezone, currency, date_format)
    - Domain Configuration (subdomain, custom_domain)
    - Security Settings (MFA requirements, password expiry)
    - Branding (logo, colors)

    Uses EnhancedTenantEditForm for comprehensive editing.
    Calls TenantService.update_tenant() for proper audit logging with old_values/new_values.
    Displays last modification info (updated_at and modifier username).

    Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7
    """

    template_name = "admin/tenant_edit.html"

    def get(self, request, pk):
        """Display the tenant edit form with current values."""
        from django.shortcuts import render

        from apps.core.forms import EnhancedTenantEditForm

        tenant = get_object_or_404(Tenant, pk=pk)
        form = EnhancedTenantEditForm(tenant=tenant)

        context = self._get_context(tenant, form)
        return render(request, self.template_name, context)

    def post(self, request, pk):
        """Handle tenant edit form submission."""
        from django.shortcuts import render

        from apps.core.forms import EnhancedTenantEditForm
        from apps.core.services.tenant_service import TenantService

        tenant = get_object_or_404(Tenant, pk=pk)
        form = EnhancedTenantEditForm(request.POST, request.FILES, tenant=tenant)

        if form.is_valid():
            try:
                # Extract data from form
                tenant_data = form.get_tenant_data()
                settings_data = form.get_settings_data()
                domain_data = form.get_domain_data()

                # Handle logo upload separately if provided
                logo = form.cleaned_data.get("logo")
                if logo:
                    settings_data["logo"] = logo

                # Update tenant using TenantService (Requirement 2.7 - audit logging)
                tenant_service = TenantService()
                updated_tenant = tenant_service.update_tenant(
                    tenant=tenant,
                    tenant_data=tenant_data,
                    settings_data=settings_data,
                    domain_data=domain_data,
                    modified_by=request.user,
                )

                messages.success(
                    request,
                    f'Tenant "{updated_tenant.company_name}" updated successfully.',
                )

                # Redirect to tenant detail page
                return redirect(
                    reverse("core:admin_tenant_detail", kwargs={"pk": updated_tenant.pk})
                )

            except ValueError as e:
                # Handle validation errors from TenantService
                messages.error(request, f"Validation error: {str(e)}")
            except Exception as e:
                # Handle unexpected errors
                import logging

                logger = logging.getLogger(__name__)
                logger.exception("Error updating tenant")
                messages.error(request, f"An unexpected error occurred: {str(e)}")

        # Re-render form with errors
        context = self._get_context(tenant, form)
        return render(request, self.template_name, context)

    def _get_context(self, tenant, form):
        """Build context for the template."""
        from apps.core.audit_models import AuditLog

        # Get last modification info (Requirement 2.5)
        last_modification = (
            AuditLog.objects.filter(
                tenant=tenant,
                action__in=[
                    AuditLog.ACTION_TENANT_UPDATE,
                    AuditLog.ACTION_TENANT_CREATE,
                ],
            )
            .select_related("user")
            .order_by("-timestamp")
            .first()
        )

        last_modified_at = tenant.updated_at
        last_modified_by = None
        if last_modification and last_modification.user:
            last_modified_by = last_modification.user.username

        # Get tenant domains for display
        from apps.core.models import TenantDomain

        domains = TenantDomain.objects.filter(tenant=tenant)
        subdomain = domains.filter(domain_type=TenantDomain.DOMAIN_TYPE_SUBDOMAIN).first()
        custom_domains = domains.filter(domain_type=TenantDomain.DOMAIN_TYPE_CUSTOM)

        return {
            "form": form,
            "tenant": tenant,
            "form_title": f"Edit Tenant: {tenant.company_name}",
            "submit_text": "Save Changes",
            "last_modified_at": last_modified_at,
            "last_modified_by": last_modified_by,
            "subdomain": subdomain,
            "custom_domains": custom_domains,
            "settings": getattr(tenant, "settings", None),
        }


class TenantStatusChangeView(PlatformAdminRequiredMixin, View):
    """
    View to change tenant status (activate, suspend, mark for deletion).

    Handles POST requests to change tenant status with confirmation.
    Implements:
    - Suspend: Disables access, retains data
    - Schedule for deletion: Sets grace period before permanent deletion
    - Reactivate: Restores full access
    """

    def _handle_activate(self, tenant):
        """Handle tenant activation."""
        tenant.activate()
        return "reactivated"

    def _handle_suspend(self, tenant, reason):
        """Handle tenant suspension."""
        tenant.suspend(reason=reason)
        return "suspended"

    def _handle_schedule_deletion(self, tenant, grace_period_days):
        """Handle scheduling tenant for deletion."""
        grace_days = int(grace_period_days)
        if grace_days < 1 or grace_days > 365:
            raise ValueError("Grace period must be between 1 and 365 days")
        tenant.schedule_for_deletion(grace_period_days=grace_days)
        return f"scheduled for deletion (grace period: {grace_days} days)"

    def post(self, request, pk):
        tenant = get_object_or_404(Tenant, pk=pk)
        new_status = request.POST.get("status")
        grace_period_days = request.POST.get("grace_period_days", "30")
        reason = request.POST.get("reason", "").strip()

        if new_status not in [Tenant.ACTIVE, Tenant.SUSPENDED, Tenant.PENDING_DELETION]:
            messages.error(request, "Invalid status value.")
            return redirect("core:admin_tenant_detail", pk=pk)

        old_status = tenant.status

        try:
            # Handle status change
            if new_status == Tenant.ACTIVE:
                action_message = self._handle_activate(tenant)
            elif new_status == Tenant.SUSPENDED:
                action_message = self._handle_suspend(tenant, reason)
            elif new_status == Tenant.PENDING_DELETION:
                action_message = self._handle_schedule_deletion(tenant, grace_period_days)

            # Log the status change
            import logging

            logger = logging.getLogger(__name__)
            logger.info(
                f"Tenant status changed: {tenant.company_name} ({tenant.id}) "
                f"from {old_status} to {new_status} by {request.user.username}. "
                f"Reason: {reason or 'Not provided'}"
            )

            messages.success(request, f'Tenant "{tenant.company_name}" has been {action_message}.')

            # Show deletion info if applicable
            if new_status == Tenant.PENDING_DELETION:
                deletion_date = tenant.get_deletion_date()
                if deletion_date:
                    messages.info(
                        request,
                        f'Tenant will be permanently deleted on {deletion_date.strftime("%B %d, %Y at %I:%M %p")}. '
                        f"You can reactivate the tenant before this date to cancel deletion.",
                    )

        except ValueError as e:
            messages.error(request, f"Invalid grace period: {e}")
        except Exception as e:
            messages.error(request, f"Error changing tenant status: {str(e)}")
            import logging

            logger = logging.getLogger(__name__)
            logger.error(
                f"Error changing tenant status for {tenant.company_name} ({tenant.id}): {str(e)}",
                exc_info=True,
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


# ============================================================================
# Tenant Bulk Operations Views
# ============================================================================


class TenantBulkStatusChangeView(PlatformAdminRequiredMixin, View):
    """
    View for bulk status change of multiple tenants.

    Allows platform administrators to change status of multiple tenants
    at once with confirmation. Uses TenantService.bulk_change_status()
    for atomic operations with audit logging.

    Requirements: 8.3, 8.4
    """

    def post(self, request):
        """Handle bulk status change request."""
        # Get selected tenant IDs
        tenant_ids_str = request.POST.get("tenant_ids", "")
        new_status = request.POST.get("status", "").strip()
        reason = request.POST.get("reason", "Bulk status change").strip()

        # Parse tenant IDs
        try:
            if tenant_ids_str:
                tenant_ids = [
                    uuid.UUID(tid.strip()) for tid in tenant_ids_str.split(",") if tid.strip()
                ]
            else:
                tenant_ids = []
        except (ValueError, AttributeError):
            messages.error(request, "Invalid tenant IDs provided.")
            return redirect("core:admin_tenant_list")

        if not tenant_ids:
            messages.error(request, "No tenants selected for bulk operation.")
            return redirect("core:admin_tenant_list")

        # Validate status
        valid_statuses = [Tenant.ACTIVE, Tenant.SUSPENDED]
        if new_status not in valid_statuses:
            messages.error(request, f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
            return redirect("core:admin_tenant_list")

        try:
            from apps.core.services.tenant_service import TenantService

            tenant_service = TenantService()
            updated_count = tenant_service.bulk_change_status(
                tenant_ids=tenant_ids,
                new_status=new_status,
                reason=reason,
                modified_by=request.user,
            )

            status_display = "activated" if new_status == Tenant.ACTIVE else "suspended"
            messages.success(
                request,
                f"Successfully {status_display} {updated_count} tenant(s).",
            )

        except ValueError as e:
            messages.error(request, f"Validation error: {str(e)}")
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.exception("Error in bulk status change")
            messages.error(request, f"An error occurred: {str(e)}")

        return redirect("core:admin_tenant_list")


class TenantExportCSVView(PlatformAdminRequiredMixin, View):
    """
    View for exporting tenant list to CSV.

    Exports filtered tenant list with all displayed columns including
    user count, storage used, and last activity.

    Requirements: 8.6
    """

    def get(self, request):
        """Export tenants to CSV."""
        import csv

        from django.db.models import Count, Max
        from django.http import HttpResponse

        # Build queryset with same filters as list view
        queryset = Tenant.objects.all().select_related("settings")

        # Annotate with user count and last activity
        queryset = queryset.annotate(
            user_count=Count("users", distinct=True),
            last_activity=Max("audit_logs__timestamp"),
        )

        # Apply filters
        search_query = request.GET.get("search", "").strip()
        if search_query:
            queryset = queryset.filter(
                Q(company_name__icontains=search_query) | Q(slug__icontains=search_query)
            )

        status = request.GET.get("status", "").strip()
        if status:
            queryset = queryset.filter(status=status)

        date_from = request.GET.get("date_from", "").strip()
        date_to = request.GET.get("date_to", "").strip()

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
                date_to_obj = date_to_obj + timedelta(days=1)
                queryset = queryset.filter(created_at__lt=date_to_obj)
            except ValueError:
                pass

        # Apply sorting
        sort_by = request.GET.get("sort_by", "created_at").strip()
        sort_order = request.GET.get("sort_order", "desc").strip()

        sort_columns = {
            "company_name": "company_name",
            "slug": "slug",
            "status": "status",
            "user_count": "user_count",
            "created_at": "created_at",
            "last_activity": "last_activity",
        }

        if sort_by in sort_columns:
            order_field = sort_columns[sort_by]
            if sort_order == "desc":
                order_field = f"-{order_field}"
            queryset = queryset.order_by(order_field)
        else:
            queryset = queryset.order_by("-created_at")

        # Get tenant domains for access URLs
        from apps.core.models import TenantDomain

        tenant_ids = list(queryset.values_list("id", flat=True))
        domains = TenantDomain.objects.filter(tenant_id__in=tenant_ids, is_primary=True)
        domain_map = {str(d.tenant_id): d.domain for d in domains}

        # Create CSV response
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="tenants_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        )

        writer = csv.writer(response)

        # Write header row
        writer.writerow(
            [
                "Company Name",
                "Slug",
                "Status",
                "User Count",
                "Storage Used",
                "Created At",
                "Last Activity",
                "Access URL",
            ]
        )

        # Write data rows
        for tenant in queryset:
            # Calculate storage (simplified - just check if logo exists)
            storage_used = "N/A"
            if hasattr(tenant, "settings") and tenant.settings and tenant.settings.logo:
                try:
                    storage_used = f"{tenant.settings.logo.size / 1024:.1f} KB"
                except (FileNotFoundError, ValueError):
                    storage_used = "N/A"

            # Format last activity
            last_activity = (
                tenant.last_activity.strftime("%Y-%m-%d %H:%M:%S")
                if tenant.last_activity
                else "Never"
            )

            # Get access URL
            access_url = domain_map.get(str(tenant.id), "N/A")

            writer.writerow(
                [
                    tenant.company_name,
                    tenant.slug,
                    tenant.get_status_display(),
                    tenant.user_count,
                    storage_used,
                    tenant.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    last_activity,
                    access_url,
                ]
            )

        return response


# ============================================================================
# Tenant User Management Views
# ============================================================================


class TenantUserPasswordResetView(PlatformAdminRequiredMixin, View):
    """
    View to initiate password reset for a tenant user.

    Platform administrators can trigger a password reset email for tenant users
    without viewing or setting passwords directly.
    """

    def post(self, request, tenant_pk, user_pk):
        tenant = get_object_or_404(Tenant, pk=tenant_pk)
        user = get_object_or_404(User, pk=user_pk, tenant=tenant)

        # Prevent resetting platform admin passwords
        if user.is_platform_admin():
            messages.error(request, "Cannot reset password for platform administrators.")
            return redirect(
                reverse("core:admin_tenant_detail", kwargs={"pk": tenant_pk}) + "?tab=users"
            )

        try:
            # Generate password reset token
            from django.contrib.auth.tokens import default_token_generator
            from django.utils.encoding import force_bytes
            from django.utils.http import urlsafe_base64_encode

            # Create reset token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            # In production, send email with reset link
            # For now, we'll just log it and show a success message
            import logging

            logger = logging.getLogger(__name__)
            logger.info(
                f"Password reset initiated for user {user.username} ({user.id}) "
                f"in tenant {tenant.company_name} ({tenant.id}) by admin {request.user.username}. "
                f"Token: {token}, UID: {uid}"
            )

            # TODO: Send email with reset link when email system is implemented (Task 13.3)
            # For now, show a success message
            messages.success(
                request,
                f'Password reset initiated for user "{user.username}". '
                f"A password reset email would be sent to {user.email}. "
                f"(Email system will be implemented in Task 13.3)",
            )

            # Log the action in audit trail
            logger.info(
                f"Admin {request.user.username} initiated password reset for "
                f"user {user.username} in tenant {tenant.company_name}"
            )

        except Exception as e:
            messages.error(request, f"Error initiating password reset: {str(e)}")
            import logging

            logger = logging.getLogger(__name__)
            logger.error(
                f"Error initiating password reset for user {user.username} ({user.id}): {str(e)}",
                exc_info=True,
            )

        return redirect(
            reverse("core:admin_tenant_detail", kwargs={"pk": tenant_pk}) + "?tab=users"
        )


class TenantUserRoleChangeView(PlatformAdminRequiredMixin, View):
    """
    View to change a tenant user's role.

    Platform administrators can change user roles within a tenant.
    Prevents changing platform admin roles.
    """

    def post(self, request, tenant_pk, user_pk):
        tenant = get_object_or_404(Tenant, pk=tenant_pk)
        user = get_object_or_404(User, pk=user_pk, tenant=tenant)
        new_role = request.POST.get("role")

        # Validate role
        valid_roles = [choice[0] for choice in User.ROLE_CHOICES]
        if new_role not in valid_roles:
            messages.error(request, "Invalid role selected.")
            return redirect(
                reverse("core:admin_tenant_detail", kwargs={"pk": tenant_pk}) + "?tab=users"
            )

        # Prevent changing platform admin roles
        if user.is_platform_admin() or new_role == User.PLATFORM_ADMIN:
            messages.error(
                request,
                "Cannot change platform administrator roles. "
                "Platform admin roles must be managed separately.",
            )
            return redirect(
                reverse("core:admin_tenant_detail", kwargs={"pk": tenant_pk}) + "?tab=users"
            )

        # Prevent changing own role if impersonating
        if request.user == user:
            messages.error(request, "Cannot change your own role.")
            return redirect(
                reverse("core:admin_tenant_detail", kwargs={"pk": tenant_pk}) + "?tab=users"
            )

        old_role = user.role

        try:
            # Change role
            user.role = new_role
            user.save(update_fields=["role"])

            # Log the action
            import logging

            logger = logging.getLogger(__name__)
            logger.info(
                f"User role changed: {user.username} ({user.id}) in tenant "
                f"{tenant.company_name} ({tenant.id}) from {old_role} to {new_role} "
                f"by admin {request.user.username}"
            )

            # Get display name for old role
            old_role_display = dict(User.ROLE_CHOICES).get(old_role, old_role)

            messages.success(
                request,
                f'Role for user "{user.username}" changed from '
                f'"{old_role_display}" to "{user.get_role_display()}".',
            )

        except Exception as e:
            messages.error(request, f"Error changing user role: {str(e)}")
            import logging

            logger = logging.getLogger(__name__)
            logger.error(
                f"Error changing role for user {user.username} ({user.id}): {str(e)}",
                exc_info=True,
            )

        return redirect(
            reverse("core:admin_tenant_detail", kwargs={"pk": tenant_pk}) + "?tab=users"
        )


class TenantUserToggleActiveView(PlatformAdminRequiredMixin, View):
    """
    View to activate or deactivate a tenant user.

    Platform administrators can enable/disable user accounts.
    """

    def post(self, request, tenant_pk, user_pk):
        tenant = get_object_or_404(Tenant, pk=tenant_pk)
        user = get_object_or_404(User, pk=user_pk, tenant=tenant)

        # Prevent deactivating platform admins
        if user.is_platform_admin():
            messages.error(request, "Cannot deactivate platform administrators.")
            return redirect(
                reverse("core:admin_tenant_detail", kwargs={"pk": tenant_pk}) + "?tab=users"
            )

        # Prevent deactivating self
        if request.user == user:
            messages.error(request, "Cannot deactivate your own account.")
            return redirect(
                reverse("core:admin_tenant_detail", kwargs={"pk": tenant_pk}) + "?tab=users"
            )

        try:
            # Toggle active status
            user.is_active = not user.is_active
            user.save(update_fields=["is_active"])

            # Log the action
            import logging

            logger = logging.getLogger(__name__)
            action = "activated" if user.is_active else "deactivated"
            logger.info(
                f"User {action}: {user.username} ({user.id}) in tenant "
                f"{tenant.company_name} ({tenant.id}) by admin {request.user.username}"
            )

            messages.success(
                request,
                f'User "{user.username}" has been {action}.',
            )

        except Exception as e:
            messages.error(request, f"Error changing user status: {str(e)}")
            import logging

            logger = logging.getLogger(__name__)
            logger.error(
                f"Error toggling active status for user {user.username} ({user.id}): {str(e)}",
                exc_info=True,
            )

        return redirect(
            reverse("core:admin_tenant_detail", kwargs={"pk": tenant_pk}) + "?tab=users"
        )


class TenantUserCreateView(PlatformAdminRequiredMixin, View):
    """
    View to create a new user within a tenant.

    Platform administrators can create users directly from the tenant detail
    Users tab. Displays one-time password modal on success.

    Requirements: 3.3, 3.4, 3.11
    """

    def post(self, request, tenant_pk):
        """Handle user creation form submission."""
        from apps.core.forms import TenantUserCreateForm
        from apps.core.services.user_service import UserManagementService

        tenant = get_object_or_404(Tenant, pk=tenant_pk)
        form = TenantUserCreateForm(request.POST, tenant=tenant)

        if form.is_valid():
            try:
                # Prepare user data
                user_data = {
                    "username": form.cleaned_data["username"],
                    "email": form.cleaned_data["email"],
                    "password": form.cleaned_data["password"],
                    "role": form.cleaned_data["role"],
                    "branch": form.cleaned_data.get("branch"),
                    "phone": form.cleaned_data.get("phone", ""),
                    "language": form.cleaned_data.get("language", User.LANGUAGE_ENGLISH),
                    "theme": form.cleaned_data.get("theme", User.THEME_LIGHT),
                    "force_mfa": form.cleaned_data.get("force_mfa", False),
                }

                # Create user using UserManagementService
                user_service = UserManagementService()
                new_user, initial_password = user_service.create_tenant_user(
                    tenant=tenant,
                    user_data=user_data,
                    created_by=request.user,
                )

                # Store password in session for one-time display (Requirement 3.4)
                request.session["user_created_password"] = initial_password
                request.session["user_created_username"] = new_user.username
                request.session["user_created_id"] = str(new_user.id)

                messages.success(
                    request,
                    f'User "{new_user.username}" created successfully.',
                )

                # Redirect to Users tab with password modal flag
                return redirect(
                    reverse("core:admin_tenant_detail", kwargs={"pk": tenant_pk})
                    + "?tab=users&show_user_password_modal=1"
                )

            except ValueError as e:
                messages.error(request, f"Validation error: {str(e)}")
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.exception("Error creating tenant user")
                messages.error(request, f"An unexpected error occurred: {str(e)}")
        else:
            # Collect form errors
            error_messages = []
            for field, errors in form.errors.items():
                for error in errors:
                    error_messages.append(f"{field}: {error}")
            messages.error(request, "Form validation failed: " + "; ".join(error_messages))

        return redirect(
            reverse("core:admin_tenant_detail", kwargs={"pk": tenant_pk}) + "?tab=users"
        )


class TenantUserEditView(PlatformAdminRequiredMixin, View):
    """
    View to edit a tenant user.

    Platform administrators can edit user details from the tenant detail
    Users tab.

    Requirements: 3.5, 3.11
    """

    def post(self, request, tenant_pk, user_pk):
        """Handle user edit form submission."""
        from apps.core.models import Branch
        from apps.core.services.user_service import UserManagementService

        tenant = get_object_or_404(Tenant, pk=tenant_pk)
        user = get_object_or_404(User, pk=user_pk, tenant=tenant)

        # Prevent editing platform admins
        if user.is_platform_admin():
            messages.error(request, "Cannot edit platform administrators.")
            return redirect(
                reverse("core:admin_tenant_detail", kwargs={"pk": tenant_pk}) + "?tab=users"
            )

        try:
            # Prepare user data from POST
            user_data = {}

            # Email
            email = request.POST.get("email", "").strip()
            if email and email != user.email:
                user_data["email"] = email

            # Role
            role = request.POST.get("role", "").strip()
            if role and role != user.role:
                user_data["role"] = role

            # Branch
            branch_id = request.POST.get("branch", "").strip()
            if branch_id:
                if branch_id == "none":
                    user_data["branch"] = None
                else:
                    try:
                        branch = Branch.objects.get(id=branch_id, tenant=tenant)
                        user_data["branch"] = branch
                    except Branch.DoesNotExist:
                        pass
            elif not branch_id and user.branch:
                user_data["branch"] = None

            # Phone
            phone = request.POST.get("phone", "").strip()
            if phone != (user.phone or ""):
                user_data["phone"] = phone

            # Language
            language = request.POST.get("language", "").strip()
            if language and language != user.language:
                user_data["language"] = language

            # Theme
            theme = request.POST.get("theme", "").strip()
            if theme and theme != user.theme:
                user_data["theme"] = theme

            # MFA
            is_mfa_enabled = request.POST.get("is_mfa_enabled") == "on"
            if is_mfa_enabled != user.is_mfa_enabled:
                user_data["is_mfa_enabled"] = is_mfa_enabled

            if user_data:
                # Update user using UserManagementService
                user_service = UserManagementService()
                user_service.update_tenant_user(
                    user=user,
                    user_data=user_data,
                    modified_by=request.user,
                )

                messages.success(
                    request,
                    f'User "{user.username}" updated successfully.',
                )
            else:
                messages.info(request, "No changes were made.")

        except ValueError as e:
            messages.error(request, f"Validation error: {str(e)}")
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.exception("Error updating tenant user")
            messages.error(request, f"An unexpected error occurred: {str(e)}")

        return redirect(
            reverse("core:admin_tenant_detail", kwargs={"pk": tenant_pk}) + "?tab=users"
        )


class TenantUserTemporaryPasswordView(PlatformAdminRequiredMixin, View):
    """
    View to generate a temporary password for a tenant user.

    Platform administrators can generate temporary passwords with
    configurable expiry times.

    Requirements: 3.9, 7.4
    """

    def post(self, request, tenant_pk, user_pk):
        """Handle temporary password generation."""
        from apps.core.services.user_service import UserManagementService

        tenant = get_object_or_404(Tenant, pk=tenant_pk)
        user = get_object_or_404(User, pk=user_pk, tenant=tenant)

        # Prevent generating temp password for platform admins
        if user.is_platform_admin():
            messages.error(
                request, "Cannot generate temporary password for platform administrators."
            )
            return redirect(
                reverse("core:admin_tenant_detail", kwargs={"pk": tenant_pk}) + "?tab=users"
            )

        try:
            # Get expiry hours from request (default 24 hours)
            expiry_hours = int(request.POST.get("expiry_hours", 24))
            if expiry_hours not in [1, 24, 168]:  # 1h, 24h, 7d
                expiry_hours = 24

            # Generate temporary password
            user_service = UserManagementService()
            temp_password = user_service.generate_temporary_password(
                user=user,
                expiry_hours=expiry_hours,
                generated_by=request.user,
            )

            # Store password in session for one-time display
            request.session["temp_password"] = temp_password
            request.session["temp_password_username"] = user.username
            request.session["temp_password_expiry"] = expiry_hours

            messages.success(
                request,
                f'Temporary password generated for user "{user.username}".',
            )

            # Redirect with flag to show temp password modal
            return redirect(
                reverse("core:admin_tenant_detail", kwargs={"pk": tenant_pk})
                + "?tab=users&show_temp_password_modal=1"
            )

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.exception("Error generating temporary password")
            messages.error(request, f"An unexpected error occurred: {str(e)}")

        return redirect(
            reverse("core:admin_tenant_detail", kwargs={"pk": tenant_pk}) + "?tab=users"
        )


class TenantUserLoginHistoryView(PlatformAdminRequiredMixin, View):
    """
    API view to get login history for a tenant user.

    Returns JSON with recent login attempts.

    Requirements: 3.6
    """

    def get(self, request, tenant_pk, user_pk):
        """Return login history as JSON."""
        from apps.core.services.user_service import UserManagementService

        tenant = get_object_or_404(Tenant, pk=tenant_pk)
        user = get_object_or_404(User, pk=user_pk, tenant=tenant)

        try:
            user_service = UserManagementService()
            login_history = user_service.get_login_history(user, limit=10)

            history_data = []
            for attempt in login_history:
                history_data.append(
                    {
                        "timestamp": attempt.timestamp.isoformat(),
                        "ip_address": attempt.ip_address,
                        "user_agent": attempt.user_agent[:100] if attempt.user_agent else "",
                        "result": attempt.result,
                        "result_display": (
                            attempt.get_result_display()
                            if hasattr(attempt, "get_result_display")
                            else attempt.result
                        ),
                    }
                )

            return JsonResponse(
                {
                    "success": True,
                    "username": user.username,
                    "history": history_data,
                }
            )

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.exception("Error fetching login history")
            return JsonResponse(
                {
                    "success": False,
                    "error": str(e),
                },
                status=500,
            )


class TenantUserSendPasswordResetView(PlatformAdminRequiredMixin, View):
    """
    View to send password reset email to a tenant user.

    Requirements: 3.10
    """

    def post(self, request, tenant_pk, user_pk):
        """Send password reset email."""
        from apps.core.services.user_service import UserManagementService

        tenant = get_object_or_404(Tenant, pk=tenant_pk)
        user = get_object_or_404(User, pk=user_pk, tenant=tenant)

        # Prevent sending reset for platform admins
        if user.is_platform_admin():
            messages.error(request, "Cannot send password reset for platform administrators.")
            return redirect(
                reverse("core:admin_tenant_detail", kwargs={"pk": tenant_pk}) + "?tab=users"
            )

        try:
            user_service = UserManagementService()
            user_service.send_password_reset_email(
                user=user,
                sent_by=request.user,
            )

            messages.success(
                request,
                f'Password reset email sent to "{user.email}".',
            )

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.exception("Error sending password reset email")
            messages.error(request, f"An unexpected error occurred: {str(e)}")

        return redirect(
            reverse("core:admin_tenant_detail", kwargs={"pk": tenant_pk}) + "?tab=users"
        )


class TenantSettingsSectionView(PlatformAdminRequiredMixin, View):
    """
    View to save a specific section of tenant settings.

    Handles AJAX form submissions for each settings section:
    - business: Business Info (business_name, registration_number, tax_id)
    - contact: Contact Info (address, phone, email, website)
    - localization: Localization (timezone, currency, date_format)
    - security: Security (require_mfa_for_managers, password_expiry_days)
    - branding: Branding (logo, primary_color, secondary_color)

    Logs changes in AuditLog with old_values and new_values.

    Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7
    """

    SECTION_FORMS = {
        "business": "BusinessInfoForm",
        "contact": "ContactForm",
        "localization": "LocalizationForm",
        "security": "SecurityForm",
        "branding": "BrandingForm",
    }

    def post(self, request, pk, section):
        """Handle settings section form submission."""
        from apps.core.audit_models import AuditLog
        from apps.core.models import TenantSettings

        tenant = get_object_or_404(Tenant, pk=pk)

        # Validate section
        if section not in self.SECTION_FORMS:
            return JsonResponse(
                {
                    "success": False,
                    "error": f"Invalid section: {section}",
                },
                status=400,
            )

        # Get or create tenant settings
        settings, _ = TenantSettings.objects.get_or_create(tenant=tenant)

        # Import the appropriate form
        from apps.core import forms as core_forms

        form_class = getattr(core_forms, self.SECTION_FORMS[section])

        # Create form with POST data
        form = form_class(
            request.POST,
            request.FILES if section == "branding" else None,
            instance=settings,
            prefix=section,
        )

        if form.is_valid():
            # Capture old values for audit log
            old_values = {}
            new_values = {}
            changed_fields = []

            for field_name in form.changed_data:
                old_value = getattr(settings, field_name, None)
                new_value = form.cleaned_data.get(field_name)

                # Handle file fields
                if hasattr(old_value, "url"):
                    old_value = old_value.url if old_value else None
                if hasattr(new_value, "url"):
                    new_value = new_value.name if new_value else None

                old_values[field_name] = str(old_value) if old_value is not None else None
                new_values[field_name] = str(new_value) if new_value is not None else None
                changed_fields.append(field_name)

            # Save the form
            form.save()

            # Log changes in AuditLog (Requirement 5.7)
            if changed_fields:
                AuditLog.objects.create(
                    tenant=tenant,
                    user=request.user,
                    category=AuditLog.CATEGORY_ADMIN,
                    action="SETTINGS_UPDATE",
                    severity=AuditLog.SEVERITY_INFO,
                    description=f"Updated {section} settings: {', '.join(changed_fields)}",
                    old_values=old_values,
                    new_values=new_values,
                    ip_address=self._get_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
                )

            # Return success response
            section_names = {
                "business": "Business Information",
                "contact": "Contact Information",
                "localization": "Localization",
                "security": "Security Settings",
                "branding": "Branding",
            }

            return JsonResponse(
                {
                    "success": True,
                    "message": f"{section_names.get(section, section.title())} saved successfully.",
                    "changed_fields": changed_fields,
                }
            )

        else:
            # Return validation errors
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = [str(e) for e in error_list]

            return JsonResponse(
                {
                    "success": False,
                    "error": "Validation failed. Please check the form.",
                    "field_errors": errors,
                },
                status=400,
            )

    def _get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")


class TenantActivityExportCSVView(PlatformAdminRequiredMixin, View):
    """
    View for exporting tenant activity logs to CSV.

    Exports filtered audit logs with all columns including old_values and new_values.

    Requirements: 4.6
    """

    def get(self, request, pk):
        """Export activity logs to CSV."""
        import csv
        import json
        from datetime import datetime

        from django.http import HttpResponse

        from apps.core.audit_models import AuditLog

        tenant = get_object_or_404(Tenant, pk=pk)

        # Build queryset with same filters as activity tab
        logs = AuditLog.objects.filter(tenant=tenant).select_related("user").order_by("-timestamp")

        # Date range filter
        date_range = request.GET.get("date_range", "7d")
        custom_start = request.GET.get("custom_start", "")
        custom_end = request.GET.get("custom_end", "")

        if date_range == "24h":
            since = timezone.now() - timedelta(hours=24)
            logs = logs.filter(timestamp__gte=since)
        elif date_range == "7d":
            since = timezone.now() - timedelta(days=7)
            logs = logs.filter(timestamp__gte=since)
        elif date_range == "30d":
            since = timezone.now() - timedelta(days=30)
            logs = logs.filter(timestamp__gte=since)
        elif date_range == "90d":
            since = timezone.now() - timedelta(days=90)
            logs = logs.filter(timestamp__gte=since)
        elif date_range == "custom":
            if custom_start:
                try:
                    start_date = datetime.strptime(custom_start, "%Y-%m-%d")
                    logs = logs.filter(timestamp__gte=start_date)
                except ValueError:
                    pass
            if custom_end:
                try:
                    end_date = datetime.strptime(custom_end, "%Y-%m-%d")
                    end_date = end_date + timedelta(days=1)
                    logs = logs.filter(timestamp__lt=end_date)
                except ValueError:
                    pass

        # Category filter
        category_filter = request.GET.get("category", "")
        if category_filter:
            logs = logs.filter(category=category_filter)

        # Actor filter
        actor_filter = request.GET.get("actor", "")
        if actor_filter:
            try:
                logs = logs.filter(user_id=int(actor_filter))
            except (ValueError, TypeError):
                pass

        # Security events filter
        security_only = request.GET.get("security_only", "") == "1"
        if security_only:
            security_actions = [
                AuditLog.ACTION_LOGIN_FAILED,
                AuditLog.ACTION_PASSWORD_CHANGE,
                AuditLog.ACTION_PASSWORD_RESET_REQUEST,
                AuditLog.ACTION_PASSWORD_RESET_COMPLETE,
                AuditLog.ACTION_MFA_ENABLE,
                AuditLog.ACTION_MFA_DISABLE,
                AuditLog.ACTION_MFA_VERIFY_FAILED,
                AuditLog.ACTION_SECURITY_BREACH_ATTEMPT,
                AuditLog.ACTION_SECURITY_SUSPICIOUS_ACTIVITY,
                AuditLog.ACTION_SECURITY_RATE_LIMIT_EXCEEDED,
                AuditLog.ACTION_SECURITY_UNAUTHORIZED_ACCESS,
                AuditLog.ACTION_IMPERSONATION_START,
                AuditLog.ACTION_IMPERSONATION_END,
            ]
            logs = logs.filter(
                Q(category=AuditLog.CATEGORY_SECURITY) | Q(action__in=security_actions)
            )

        # Create CSV response
        response = HttpResponse(content_type="text/csv")
        filename = f"activity_export_{tenant.slug}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)

        # Write header row
        writer.writerow(
            [
                "Timestamp",
                "Category",
                "Action",
                "Severity",
                "Actor",
                "Description",
                "IP Address",
                "User Agent",
                "Old Values",
                "New Values",
                "Metadata",
            ]
        )

        # Write data rows
        for log in logs:
            # Format JSON fields
            old_values = json.dumps(log.old_values) if log.old_values else ""
            new_values = json.dumps(log.new_values) if log.new_values else ""
            metadata = json.dumps(log.metadata) if log.metadata else ""

            writer.writerow(
                [
                    log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    log.get_category_display(),
                    log.get_action_display(),
                    log.get_severity_display(),
                    log.user.username if log.user else "System",
                    log.description,
                    log.ip_address or "",
                    log.user_agent[:200] if log.user_agent else "",
                    old_values,
                    new_values,
                    metadata,
                ]
            )

        return response


class TenantActivityDetailAPIView(PlatformAdminRequiredMixin, View):
    """
    API view to get activity log detail for modal display.

    Returns JSON with full audit log entry details including
    old_values, new_values, and metadata JSON fields.

    Requirements: 4.8
    """

    def get(self, request, pk, log_pk):
        """Return activity log detail as JSON."""
        from apps.core.audit_models import AuditLog

        tenant = get_object_or_404(Tenant, pk=pk)
        log = get_object_or_404(AuditLog, pk=log_pk, tenant=tenant)

        return JsonResponse(
            {
                "success": True,
                "log": {
                    "id": str(log.id),
                    "timestamp": log.timestamp.isoformat(),
                    "category": log.category,
                    "category_display": (
                        log.get_category_display()
                        if hasattr(log, "get_category_display")
                        else log.category
                    ),
                    "action": log.action,
                    "action_display": (
                        log.get_action_display()
                        if hasattr(log, "get_action_display")
                        else log.action
                    ),
                    "severity": log.severity,
                    "severity_display": (
                        log.get_severity_display()
                        if hasattr(log, "get_severity_display")
                        else log.severity
                    ),
                    "actor": log.user.username if log.user else "System",
                    "actor_email": log.user.email if log.user else None,
                    "description": log.description,
                    "ip_address": log.ip_address,
                    "user_agent": log.user_agent,
                    "request_method": log.request_method,
                    "request_path": log.request_path,
                    "response_status": log.response_status,
                    "old_values": log.old_values,
                    "new_values": log.new_values,
                    "metadata": log.metadata,
                },
            }
        )


# ============================================================================
# Domain Management Views
# ============================================================================


class TenantDomainCreateView(PlatformAdminRequiredMixin, View):
    """
    API view to add a custom domain to a tenant.

    Validates the domain, creates a TenantDomain record, and returns
    DNS verification instructions.

    Requirements: 9.2, 9.3
    """

    def post(self, request, pk):
        """Create a custom domain for the tenant."""
        import json

        from apps.core.audit_models import AuditLog
        from apps.core.models import TenantDomain
        from apps.core.services.domain_service import DomainService

        tenant = get_object_or_404(Tenant, pk=pk)

        try:
            # Parse request body
            data = json.loads(request.body)
            domain = data.get("domain", "").strip()

            if not domain:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Domain is required",
                    },
                    status=400,
                )

            # Initialize domain service
            domain_service = DomainService()

            # Validate domain
            is_valid, errors = domain_service.validate_custom_domain(domain)
            if not is_valid:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Domain validation failed",
                        "errors": errors,
                    },
                    status=400,
                )

            # Check if domain already exists
            if TenantDomain.objects.filter(domain=domain).exists():
                return JsonResponse(
                    {
                        "success": False,
                        "error": f"Domain {domain} is already registered",
                    },
                    status=400,
                )

            # Add custom domain
            tenant_domain, dns_records = domain_service.add_custom_domain(tenant, domain)

            # Log the action in AuditLog
            AuditLog.objects.create(
                tenant=tenant,
                user=request.user,
                category=AuditLog.CATEGORY_ADMIN,
                action="DOMAIN_ADD",
                severity=AuditLog.SEVERITY_INFO,
                description=f"Added custom domain: {domain}",
                new_values={
                    "domain": domain,
                    "domain_type": tenant_domain.domain_type,
                    "verification_status": tenant_domain.verification_status,
                },
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
            )

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Custom domain {domain} added successfully",
                    "domain": {
                        "id": str(tenant_domain.id),
                        "domain": tenant_domain.domain,
                        "domain_type": tenant_domain.domain_type,
                        "is_primary": tenant_domain.is_primary,
                        "verification_status": tenant_domain.verification_status,
                        "created_at": tenant_domain.created_at.isoformat(),
                    },
                    "dns_records": dns_records,
                }
            )

        except ValueError as e:
            return JsonResponse(
                {
                    "success": False,
                    "error": str(e),
                },
                status=400,
            )
        except Exception:
            import logging

            logger = logging.getLogger(__name__)
            logger.exception("Error adding custom domain")
            return JsonResponse(
                {
                    "success": False,
                    "error": "An error occurred while adding the domain",
                },
                status=500,
            )

    def _get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


class TenantDomainDeleteView(PlatformAdminRequiredMixin, View):
    """
    API view to remove a custom domain from a tenant.

    Prevents deletion of primary subdomains to maintain tenant access.

    Requirements: 9.2, 9.3
    """

    def post(self, request, pk, domain_pk):
        """Delete a domain from the tenant."""
        from apps.core.audit_models import AuditLog
        from apps.core.models import TenantDomain

        tenant = get_object_or_404(Tenant, pk=pk)
        domain = get_object_or_404(TenantDomain, pk=domain_pk, tenant=tenant)

        try:
            # Prevent deletion of primary subdomain
            if domain.domain_type == TenantDomain.DOMAIN_TYPE_SUBDOMAIN and domain.is_primary:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Cannot delete the primary subdomain. This is the tenant's main access URL.",
                    },
                    status=400,
                )

            # Store domain info for logging
            domain_name = domain.domain
            domain_type = domain.domain_type

            # Delete the domain
            domain.delete()

            # Log the action in AuditLog
            AuditLog.objects.create(
                tenant=tenant,
                user=request.user,
                category=AuditLog.CATEGORY_ADMIN,
                action="DOMAIN_DELETE",
                severity=AuditLog.SEVERITY_WARNING,
                description=f"Deleted domain: {domain_name}",
                old_values={
                    "domain": domain_name,
                    "domain_type": domain_type,
                },
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
            )

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Domain {domain_name} deleted successfully",
                }
            )

        except Exception:
            import logging

            logger = logging.getLogger(__name__)
            logger.exception("Error deleting domain")
            return JsonResponse(
                {
                    "success": False,
                    "error": "An error occurred while deleting the domain",
                },
                status=500,
            )

    def _get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


class TenantDomainVerifyView(PlatformAdminRequiredMixin, View):
    """
    API view to trigger DNS verification for a custom domain.

    Checks DNS records and updates the verification status.

    Requirements: 9.3, 9.4
    """

    def post(self, request, pk, domain_pk):
        """Trigger domain verification."""
        from apps.core.audit_models import AuditLog
        from apps.core.models import TenantDomain
        from apps.core.services.domain_service import DomainService

        tenant = get_object_or_404(Tenant, pk=pk)
        domain = get_object_or_404(TenantDomain, pk=domain_pk, tenant=tenant)

        try:
            # Only verify custom domains
            if domain.domain_type != TenantDomain.DOMAIN_TYPE_CUSTOM:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Only custom domains require verification. Subdomains are automatically verified.",
                    },
                    status=400,
                )

            # Initialize domain service
            domain_service = DomainService()

            # Store old status for logging
            old_status = domain.verification_status

            # Trigger verification
            new_status = domain_service.check_domain_verification(domain)

            # Refresh from database to get updated values
            domain.refresh_from_db()

            # Log the verification attempt
            AuditLog.objects.create(
                tenant=tenant,
                user=request.user,
                category=AuditLog.CATEGORY_ADMIN,
                action="DOMAIN_VERIFY",
                severity=AuditLog.SEVERITY_INFO,
                description=f"Triggered verification for domain: {domain.domain}",
                old_values={
                    "verification_status": old_status,
                },
                new_values={
                    "verification_status": new_status,
                    "verified_at": domain.verified_at.isoformat() if domain.verified_at else None,
                },
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
            )

            # Prepare response message
            if new_status == TenantDomain.VERIFICATION_VERIFIED:
                message = f"Domain {domain.domain} verified successfully!"
            elif new_status == TenantDomain.VERIFICATION_PENDING:
                message = f"Domain {domain.domain} verification is still pending. Please ensure DNS records are configured correctly."
            else:
                message = f"Domain {domain.domain} verification failed. Please check DNS records."

            return JsonResponse(
                {
                    "success": True,
                    "message": message,
                    "domain": {
                        "id": str(domain.id),
                        "domain": domain.domain,
                        "verification_status": domain.verification_status,
                        "verified_at": (
                            domain.verified_at.isoformat() if domain.verified_at else None
                        ),
                    },
                }
            )

        except Exception:
            import logging

            logger = logging.getLogger(__name__)
            logger.exception("Error verifying domain")
            return JsonResponse(
                {
                    "success": False,
                    "error": "An error occurred while verifying the domain",
                },
                status=500,
            )

    def _get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


class TenantUserImpersonateView(PlatformAdminRequiredMixin, View):
    """
    View to start impersonating a tenant user.

    Platform administrators can impersonate tenant users for support purposes.
    All impersonation sessions are fully audited.

    This view generates a secure one-time token and redirects to the tenant
    portal's impersonation transfer endpoint. This is necessary because the
    multi-portal session middleware uses separate session cookies for
    /platform/ and /dashboard/ paths.

    Requirements: 12.1, 12.2
    """

    def post(self, request, tenant_pk, user_pk):
        """Handle impersonation start request."""
        from django.urls import reverse

        from apps.core.services.impersonation_service import ImpersonationService

        tenant = get_object_or_404(Tenant, pk=tenant_pk)
        target_user = get_object_or_404(User, pk=user_pk, tenant=tenant)

        # Validate target user has a tenant (not a platform admin)
        if not target_user.tenant:
            messages.error(request, "Cannot impersonate platform administrators.")
            return redirect("core:admin_tenant_detail", pk=tenant_pk)

        # Validate admin user has permission
        if request.user.tenant is not None:
            messages.error(request, "Only platform administrators can impersonate users.")
            return redirect("core:admin_tenant_detail", pk=tenant_pk)

        # Initialize impersonation service
        impersonation_service = ImpersonationService()

        # Generate a one-time token for cross-portal transfer
        token = impersonation_service.generate_impersonation_token(
            admin_user=request.user,
            target_user=target_user,
        )

        # Redirect to the impersonation transfer endpoint in the tenant portal
        # This endpoint will validate the token and complete the login
        transfer_url = reverse("core:impersonation_transfer")
        return redirect(f"{transfer_url}?token={token}")


class EndImpersonationView(View):
    """
    View to end an impersonation session.

    Restores the original platform administrator session and logs the end
    of impersonation.

    Requirements: 12.3, 12.4

    Note: This view does NOT require PlatformAdminRequiredMixin because
    the user is currently impersonating a tenant user. The service validates
    that an impersonation session is active.
    """

    def post(self, request):
        """Handle impersonation end request."""
        from apps.core.services.impersonation_service import ImpersonationService

        # Initialize impersonation service
        impersonation_service = ImpersonationService()

        # Get the tenant before ending impersonation (for redirect)
        target_user = impersonation_service.get_target_user(request)
        tenant_id = target_user.tenant.id if target_user and target_user.tenant else None

        # End impersonation
        success, message = impersonation_service.end_impersonation(request)

        if success:
            messages.success(request, message)
            # Redirect back to tenant detail page (now as admin)
            if tenant_id:
                return redirect("core:admin_tenant_detail", pk=tenant_id)
            else:
                return redirect("core:admin_dashboard")
        else:
            messages.error(request, message)
            # If not impersonating, redirect to dashboard
            return redirect("core:admin_dashboard")

    def get(self, request):
        """Allow GET requests for convenience (e.g., from banner link)."""
        return self.post(request)


class TenantStatisticsAPIView(PlatformAdminRequiredMixin, View):
    """
    API view to get tenant statistics.

    Returns comprehensive statistics for a tenant including:
    - User counts (total, active, inactive, by role)
    - Branch count and names
    - Storage usage
    - Last activity information

    Requirements: 6.1, 6.2, 6.3, 6.4, 11.4

    Endpoint: GET /platform/tenants/<pk>/statistics/
    """

    def get(self, request, pk):
        """Get tenant statistics as JSON."""
        from apps.core.models import Tenant
        from apps.core.services.tenant_service import TenantService

        try:
            # Get tenant
            tenant = get_object_or_404(Tenant, id=pk)

            # Get statistics from service
            tenant_service = TenantService()
            statistics = tenant_service.get_tenant_statistics(tenant)

            # Format storage for human-readable display
            storage_used_bytes = statistics.get("storage_used_bytes", 0)

            # Convert bytes to human-readable format
            if storage_used_bytes < 1024:
                storage_display = f"{storage_used_bytes} B"
            elif storage_used_bytes < 1024 * 1024:
                storage_display = f"{storage_used_bytes / 1024:.2f} KB"
            elif storage_used_bytes < 1024 * 1024 * 1024:
                storage_display = f"{storage_used_bytes / (1024 * 1024):.2f} MB"
            else:
                storage_display = f"{storage_used_bytes / (1024 * 1024 * 1024):.2f} GB"

            # Add formatted storage to response
            statistics["storage_display"] = storage_display

            # Format last activity timestamp
            if statistics.get("last_activity_timestamp"):
                last_activity = statistics["last_activity_timestamp"]
                if isinstance(last_activity, str):
                    # Already formatted
                    statistics["last_activity_display"] = last_activity
                else:
                    # Format datetime
                    statistics["last_activity_display"] = last_activity.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )

            return JsonResponse({"success": True, "statistics": statistics})

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error getting tenant statistics: {str(e)}", exc_info=True)
            return JsonResponse(
                {"success": False, "error": "Failed to retrieve tenant statistics"}, status=500
            )
