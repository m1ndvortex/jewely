"""
Views for backup management.

This module contains views for:
- Backup management dashboard
- Manual backup triggers
- Restore wizard
- Backup health monitoring
"""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import BackupFilterForm, ManualBackupForm, RestoreBackupForm
from .models import Backup, BackupAlert, BackupRestoreLog
from .services import BackupService

logger = logging.getLogger(__name__)


def is_platform_admin(user):
    """Check if user is a platform administrator."""
    return user.is_authenticated and user.role == "PLATFORM_ADMIN"


@login_required
@user_passes_test(is_platform_admin)
def backup_dashboard(request):
    """
    Backup management dashboard.

    Displays:
    - Backup health status
    - Storage usage
    - Recent backups
    - Active alerts
    - Quick actions
    """
    # Get backup statistics
    stats = BackupService.get_backup_statistics()

    # Get recent backups
    recent_backups = Backup.objects.all()[:10]

    # Get active alerts
    active_alerts = BackupAlert.objects.filter(status=BackupAlert.ACTIVE).order_by("-created_at")[
        :10
    ]

    # Get recent restore operations
    recent_restores = BackupRestoreLog.objects.all()[:5]

    # Calculate backup health score (0-100)
    health_score = 100
    if stats["failed_backups"] > 0:
        health_score -= min(stats["failed_backups"] * 10, 50)
    if active_alerts.filter(severity=BackupAlert.CRITICAL).exists():
        health_score -= 30
    elif active_alerts.filter(severity=BackupAlert.ERROR).exists():
        health_score -= 20
    health_score = max(health_score, 0)

    context = {
        "stats": stats,
        "recent_backups": recent_backups,
        "active_alerts": active_alerts,
        "recent_restores": recent_restores,
        "health_score": health_score,
    }

    return render(request, "backups/dashboard.html", context)


@login_required
@user_passes_test(is_platform_admin)
def backup_list(request):
    """
    List all backups with filtering and pagination.
    """
    # Get filter form
    filter_form = BackupFilterForm(request.GET or None)

    # Start with all backups
    backups = Backup.objects.all()

    # Apply filters
    if filter_form.is_valid():
        if filter_form.cleaned_data.get("backup_type"):
            backups = backups.filter(backup_type=filter_form.cleaned_data["backup_type"])

        if filter_form.cleaned_data.get("status"):
            backups = backups.filter(status=filter_form.cleaned_data["status"])

        if filter_form.cleaned_data.get("tenant"):
            backups = backups.filter(tenant=filter_form.cleaned_data["tenant"])

        if filter_form.cleaned_data.get("date_from"):
            backups = backups.filter(created_at__gte=filter_form.cleaned_data["date_from"])

        if filter_form.cleaned_data.get("date_to"):
            # Add one day to include the entire end date
            date_to = filter_form.cleaned_data["date_to"]
            backups = backups.filter(created_at__lt=date_to + timezone.timedelta(days=1))

    # Paginate results
    paginator = Paginator(backups, 25)  # 25 backups per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "filter_form": filter_form,
        "page_obj": page_obj,
        "backups": page_obj.object_list,
    }

    return render(request, "backups/backup_list.html", context)


@login_required
@user_passes_test(is_platform_admin)
def backup_detail(request, backup_id):
    """
    Display detailed information about a specific backup.
    """
    backup = get_object_or_404(Backup, id=backup_id)

    # Get related restore logs
    restore_logs = backup.restore_logs.all()

    # Get related alerts
    alerts = backup.alerts.all()

    context = {
        "backup": backup,
        "restore_logs": restore_logs,
        "alerts": alerts,
    }

    return render(request, "backups/backup_detail.html", context)


@login_required
@user_passes_test(is_platform_admin)
@require_http_methods(["GET", "POST"])
def manual_backup(request):
    """
    Manual backup trigger interface.

    Allows administrators to:
    - Backup all tenants
    - Backup specific tenant(s)
    - Backup multiple tenants
    - Execute immediately or schedule for later
    - Include configuration files
    """
    if request.method == "POST":
        form = ManualBackupForm(request.POST)

        if form.is_valid():
            # Extract form data
            backup_scope = form.cleaned_data["backup_scope"]
            tenants = form.cleaned_data.get("tenants")
            execution_timing = form.cleaned_data["execution_timing"]
            scheduled_time = form.cleaned_data.get("scheduled_time")
            include_configuration = form.cleaned_data["include_configuration"]
            notes = form.cleaned_data.get("notes", "")

            # Trigger backup
            result = BackupService.trigger_manual_backup(
                backup_scope=backup_scope,
                tenants=list(tenants) if tenants else None,
                execution_timing=execution_timing,
                scheduled_time=scheduled_time,
                include_configuration=include_configuration,
                notes=notes,
                user=request.user,
            )

            if result["success"]:
                # Display success message
                if execution_timing == "immediate":
                    job_count = len(result["backup_jobs"])
                    messages.success(
                        request,
                        f"Successfully queued {job_count} backup job(s). "
                        f"Check the backup list for progress.",
                    )
                else:
                    job_count = len(result["scheduled_jobs"])
                    messages.success(
                        request,
                        f"Successfully scheduled {job_count} backup job(s) for "
                        f"{scheduled_time.strftime('%Y-%m-%d %H:%M')}.",
                    )

                # Log the action
                logger.info(
                    f"Manual backup triggered by {request.user.username}: "
                    f"scope={backup_scope}, timing={execution_timing}, jobs={job_count}"
                )

                return redirect("backups:backup_list")
            else:
                # Display error messages
                for error in result["errors"]:
                    if isinstance(error, dict):
                        messages.error(
                            request,
                            f"Error for {error.get('tenant_name', 'unknown')}: {error.get('error')}",
                        )
                    else:
                        messages.error(request, f"Error: {error}")

                logger.error(f"Manual backup failed: {result['errors']}")

    else:
        form = ManualBackupForm()

    context = {
        "form": form,
    }

    return render(request, "backups/manual_backup.html", context)


@login_required
@user_passes_test(is_platform_admin)
@require_http_methods(["GET", "POST"])
def restore_backup(request, backup_id=None):
    """
    Restore wizard interface.

    Allows administrators to:
    - Select backup to restore
    - Choose restore mode (full, merge, PITR)
    - Configure selective restore options
    - Provide justification
    """
    if request.method == "POST":
        form = RestoreBackupForm(request.POST)

        if form.is_valid():
            # Extract form data
            backup = form.cleaned_data["backup"]
            restore_mode = form.cleaned_data["restore_mode"]
            selective_restore = form.cleaned_data["selective_restore"]
            tenant_ids = form.cleaned_data.get("tenant_ids")
            target_timestamp = form.cleaned_data.get("target_timestamp")
            reason = form.cleaned_data["reason"]

            # Trigger restore
            result = BackupService.trigger_restore(
                backup_id=backup.id,
                restore_mode=restore_mode,
                selective_restore=selective_restore,
                tenant_ids=list(tenant_ids) if tenant_ids else None,
                target_timestamp=target_timestamp,
                reason=reason,
                user=request.user,
            )

            if result["success"]:
                messages.success(
                    request,
                    f"Restore operation queued successfully. "
                    f"Restore log ID: {result['restore_log_id']}",
                )

                logger.info(
                    f"Restore triggered by {request.user.username}: "
                    f"backup={backup.id}, mode={restore_mode}"
                )

                return redirect("backups:restore_detail", restore_log_id=result["restore_log_id"])
            else:
                messages.error(request, f"Failed to trigger restore: {result['error']}")
                logger.error(f"Restore failed: {result['error']}")

    else:
        # Pre-populate form with backup_id if provided
        initial = {}
        if backup_id:
            try:
                backup = Backup.objects.get(id=backup_id)
                initial["backup"] = backup
            except Backup.DoesNotExist:
                messages.error(request, f"Backup not found: {backup_id}")

        form = RestoreBackupForm(initial=initial)

    context = {
        "form": form,
    }

    return render(request, "backups/restore_backup.html", context)


@login_required
@user_passes_test(is_platform_admin)
def restore_list(request):
    """
    List all restore operations with pagination.
    """
    restore_logs = BackupRestoreLog.objects.all()

    # Paginate results
    paginator = Paginator(restore_logs, 25)  # 25 restores per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "restore_logs": page_obj.object_list,
    }

    return render(request, "backups/restore_list.html", context)


@login_required
@user_passes_test(is_platform_admin)
def restore_detail(request, restore_log_id):
    """
    Display detailed information about a specific restore operation.
    """
    restore_log = get_object_or_404(BackupRestoreLog, id=restore_log_id)

    # Get related alerts
    alerts = restore_log.alerts.all()

    context = {
        "restore_log": restore_log,
        "alerts": alerts,
    }

    return render(request, "backups/restore_detail.html", context)


@login_required
@user_passes_test(is_platform_admin)
def alert_list(request):
    """
    List all backup alerts with filtering.
    """
    # Get filter parameters
    status_filter = request.GET.get("status", "")
    severity_filter = request.GET.get("severity", "")

    # Start with all alerts
    alerts = BackupAlert.objects.all()

    # Apply filters
    if status_filter:
        alerts = alerts.filter(status=status_filter)

    if severity_filter:
        alerts = alerts.filter(severity=severity_filter)

    # Paginate results
    paginator = Paginator(alerts, 25)  # 25 alerts per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "alerts": page_obj.object_list,
        "status_filter": status_filter,
        "severity_filter": severity_filter,
        "status_choices": BackupAlert.STATUS_CHOICES,
        "severity_choices": BackupAlert.SEVERITY_CHOICES,
    }

    return render(request, "backups/alert_list.html", context)


@login_required
@user_passes_test(is_platform_admin)
@require_http_methods(["POST"])
def acknowledge_alert(request, alert_id):
    """
    Acknowledge a backup alert.
    """
    alert = get_object_or_404(BackupAlert, id=alert_id)

    if alert.status == BackupAlert.ACTIVE:
        alert.acknowledge(request.user)
        messages.success(request, f"Alert acknowledged: {alert.get_alert_type_display()}")
        logger.info(f"Alert {alert.id} acknowledged by {request.user.username}")
    else:
        messages.warning(request, "Alert is not active")

    # Redirect back to the referring page or alert list
    return redirect(request.META.get("HTTP_REFERER", "backups:alert_list"))


@login_required
@user_passes_test(is_platform_admin)
@require_http_methods(["POST"])
def resolve_alert(request, alert_id):
    """
    Resolve a backup alert.
    """
    alert = get_object_or_404(BackupAlert, id=alert_id)

    if alert.status in [BackupAlert.ACTIVE, BackupAlert.ACKNOWLEDGED]:
        resolution_notes = request.POST.get("resolution_notes", "")
        alert.resolve(request.user, notes=resolution_notes)
        messages.success(request, f"Alert resolved: {alert.get_alert_type_display()}")
        logger.info(f"Alert {alert.id} resolved by {request.user.username}")
    else:
        messages.warning(request, "Alert is already resolved")

    # Redirect back to the referring page or alert list
    return redirect(request.META.get("HTTP_REFERER", "backups:alert_list"))
