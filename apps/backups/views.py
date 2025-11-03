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

    # Get active alerts (without slice for health check)
    active_alerts_queryset = BackupAlert.objects.filter(status=BackupAlert.ACTIVE)

    # Get limited alerts for display
    active_alerts = active_alerts_queryset.order_by("-created_at")[:10]

    # Get recent restore operations
    recent_restores = BackupRestoreLog.objects.all()[:5]

    # Calculate backup health score (0-100)
    health_score = 100
    if stats["failed_backups"] > 0:
        health_score -= min(stats["failed_backups"] * 10, 50)
    if active_alerts_queryset.filter(severity=BackupAlert.CRITICAL).exists():
        health_score -= 30
    elif active_alerts_queryset.filter(severity=BackupAlert.ERROR).exists():
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
                # Log the action
                if execution_timing == "immediate":
                    job_count = len(result["backup_jobs"])
                    logger.info(
                        f"Manual backup triggered by {request.user.username}: "
                        f"scope={backup_scope}, timing={execution_timing}, jobs={job_count}"
                    )

                    # Store backup job information in session for progress tracking
                    # Each job is a dict with tenant_id, tenant_name, task_id, status
                    request.session["backup_jobs"] = result["backup_jobs"]
                    request.session["backup_job_count"] = job_count
                    request.session["backup_start_time"] = timezone.now().isoformat()

                    # Redirect to progress page
                    return redirect("backups:backup_progress")
                else:
                    job_count = len(result["scheduled_jobs"])
                    messages.success(
                        request,
                        f"Successfully scheduled {job_count} backup job(s) for "
                        f"{scheduled_time.strftime('%Y-%m-%d %H:%M')}.",
                    )
                    logger.info(
                        f"Manual backup scheduled by {request.user.username}: "
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
def backup_progress(request):
    """
    Real-time backup progress monitoring page.

    Displays live status updates for running backup jobs.
    """
    # Get backup job info from session
    backup_jobs = request.session.get("backup_jobs", [])
    backup_job_count = request.session.get("backup_job_count", 0)
    start_time = request.session.get("backup_start_time")

    if not backup_jobs:
        messages.warning(request, "No active backup jobs found.")
        return redirect("backups:dashboard")

    context = {
        "backup_jobs": backup_jobs,  # Pass as Python list - will be converted to JSON in template
        "backup_job_count": backup_job_count,
        "start_time": start_time,
    }

    return render(request, "backups/backup_progress.html", context)


@login_required
@user_passes_test(is_platform_admin)
@require_http_methods(["POST"])
def backup_status_api(request):  # noqa: C901
    """
    API endpoint for polling backup status.

    Returns current status of multiple backup jobs using Celery task IDs.
    """
    import json
    from datetime import timedelta

    from django.http import JsonResponse

    from celery.result import AsyncResult

    try:
        data = json.loads(request.body)
        backup_jobs = data.get("backup_jobs", [])

        if not backup_jobs:
            return JsonResponse({"error": "No backup jobs provided"}, status=400)

        jobs = []
        completed = 0
        in_progress = 0
        failed = 0
        total = len(backup_jobs)

        for job_info in backup_jobs:
            task_id = job_info.get("task_id")
            tenant_id = job_info.get("tenant_id")
            tenant_name = job_info.get("tenant_name")

            # Get Celery task status
            task_result = AsyncResult(task_id)

            # Map Celery states to our status
            celery_state = task_result.state
            progress = 0
            status = "PENDING"

            if celery_state == "SUCCESS":
                progress = 100
                completed += 1
                status = "COMPLETED"
            elif celery_state == "FAILURE":
                progress = 0
                failed += 1
                status = "FAILED"
            elif celery_state == "STARTED":
                progress = 30
                in_progress += 1
                status = "IN_PROGRESS"
            elif celery_state == "PROGRESS":
                # Custom state with progress info
                info = task_result.info or {}
                progress = info.get("progress", 50)
                in_progress += 1
                status = "IN_PROGRESS"
            elif celery_state == "PENDING":
                progress = 0
                in_progress += 1
                status = "PENDING"

            # Try to get actual backup record if it was created
            duration = "--"
            size = "--"
            speed = "--"

            try:
                from apps.tenants.models import Tenant

                tenant = Tenant.objects.get(id=tenant_id)
                # Get most recent backup for this tenant
                recent_backup = Backup.objects.filter(tenant=tenant).order_by("-created_at").first()

                if recent_backup:
                    # Calculate duration
                    if recent_backup.started_at:
                        if recent_backup.completed_at:
                            elapsed = recent_backup.completed_at - recent_backup.started_at
                        else:
                            elapsed = timezone.now() - recent_backup.started_at
                        minutes = int(elapsed.total_seconds() / 60)
                        seconds = int(elapsed.total_seconds() % 60)
                        duration = f"{minutes}m {seconds}s"

                    # Format size
                    if recent_backup.size:
                        mb = recent_backup.size / (1024 * 1024)
                        size = f"{mb:.2f} MB"

                    # Calculate speed
                    if recent_backup.size and recent_backup.started_at:
                        elapsed_seconds = (
                            timezone.now() - recent_backup.started_at
                        ).total_seconds()
                        if elapsed_seconds > 0:
                            mb_per_sec = (recent_backup.size / (1024 * 1024)) / elapsed_seconds
                            speed = f"{mb_per_sec:.2f} MB/s"

                    # Update status from backup record
                    if recent_backup.status == Backup.COMPLETED:
                        status = "COMPLETED"
                        progress = 100
                    elif recent_backup.status == Backup.FAILED:
                        status = "FAILED"
                        progress = 0
                    elif recent_backup.status == Backup.IN_PROGRESS:
                        status = "IN_PROGRESS"
                    elif recent_backup.status == Backup.VERIFYING:
                        status = "VERIFYING"
                        progress = 90
                    elif recent_backup.status == Backup.UPLOADING:
                        status = "UPLOADING"
                        progress = 70
            except Exception as e:
                logger.debug(f"Could not fetch backup record: {str(e)}")

            jobs.append(
                {
                    "id": task_id,
                    "tenant_id": tenant_id,
                    "name": f"Tenant Backup: {tenant_name}",
                    "info": f"Task ID: {task_id[:8]}...",
                    "status": status,
                    "progress": progress,
                    "size": size,
                    "duration": duration,
                    "speed": speed,
                }
            )

        # Calculate ETA - simplified for now
        eta = ""
        if completed > 0 and in_progress > 0:
            # Estimate 5 minutes per backup on average
            remaining_minutes = in_progress * 5
            eta_time = timezone.now() + timedelta(minutes=remaining_minutes)
            eta = eta_time.strftime("%H:%M:%S")

        # Determine overall status
        overall_status = "IN_PROGRESS"
        if completed == total:
            overall_status = "COMPLETED"
        elif failed > 0 and (completed + failed) == total:
            overall_status = "FAILED"
        elif failed == 0 and (completed + in_progress) == total and in_progress == 0:
            overall_status = "COMPLETED"

        # Generate log entries based on job statuses
        log_entries = []
        for job in jobs:
            if job["status"] == "COMPLETED":
                log_entries.append(
                    {
                        "timestamp": timezone.now().strftime("%H:%M:%S"),
                        "level": "success",
                        "message": f"✓ {job['name']} completed successfully ({job['size']})",
                    }
                )
            elif job["status"] == "FAILED":
                log_entries.append(
                    {
                        "timestamp": timezone.now().strftime("%H:%M:%S"),
                        "level": "error",
                        "message": f"✗ {job['name']} failed",
                    }
                )
            elif job["status"] == "IN_PROGRESS":
                log_entries.append(
                    {
                        "timestamp": timezone.now().strftime("%H:%M:%S"),
                        "level": "info",
                        "message": f"⟳ {job['name']} in progress ({job['progress']}%)",
                    }
                )

        return JsonResponse(
            {
                "success": True,
                "total": total,
                "completed": completed,
                "in_progress": in_progress,
                "failed": failed,
                "overall_status": overall_status,
                "jobs": jobs,
                "eta": eta,
                "log_entries": log_entries[:10],  # Last 10 entries
                "all_complete": (completed + failed) == total,
            }
        )

    except Exception as e:
        logger.error(f"Error in backup_status_api: {str(e)}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@user_passes_test(is_platform_admin)
@require_http_methods(["POST"])
def cancel_backup_api(request):
    """
    API endpoint to cancel running backups.
    """
    import json

    from django.http import JsonResponse

    from celery.task.control import revoke

    try:
        data = json.loads(request.body)
        backup_jobs = data.get("backup_jobs", [])

        if not backup_jobs:
            return JsonResponse({"error": "No backup jobs provided"}, status=400)

        # Cancel Celery tasks
        cancelled_count = 0
        for job_info in backup_jobs:
            task_id = job_info.get("task_id")
            if task_id:
                revoke(task_id, terminate=True)
                cancelled_count += 1

        return JsonResponse(
            {
                "success": True,
                "cancelled_count": cancelled_count,
                "message": f"Cancelled {cancelled_count} backup(s)",
            }
        )

    except Exception as e:
        logger.error(f"Error in cancel_backup_api: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


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


@login_required
@user_passes_test(is_platform_admin)
@require_http_methods(["GET", "POST"])
def disaster_recovery_runbook(request):
    """
    Execute disaster recovery runbook.

    This view allows administrators to:
    - Trigger automated disaster recovery
    - Select specific backup or use latest
    - Provide justification for DR
    - Monitor DR progress

    The DR runbook implements:
    1. Download backup from R2 (with B2 failover)
    2. Decrypt and decompress
    3. Restore database with 4 parallel jobs
    4. Restart application pods
    5. Verify health checks
    6. Reroute traffic
    7. Log all DR events
    """
    if request.method == "POST":
        backup_id = request.POST.get("backup_id")
        reason = request.POST.get("reason", "Disaster recovery initiated")

        if not reason:
            messages.error(request, "Please provide a reason for disaster recovery")
            return redirect("backups:disaster_recovery_runbook")

        # Validate backup if specified
        backup = None
        if backup_id:
            try:
                backup = Backup.objects.get(id=backup_id)
                if not backup.is_completed():
                    messages.error(
                        request,
                        f"Selected backup is not completed (status: {backup.status})",
                    )
                    return redirect("backups:disaster_recovery_runbook")
            except Backup.DoesNotExist:
                messages.error(request, f"Backup not found: {backup_id}")
                return redirect("backups:disaster_recovery_runbook")

        # Trigger DR runbook
        result = BackupService.execute_disaster_recovery(
            backup_id=backup.id if backup else None,
            reason=reason,
            user=request.user,
        )

        if result["success"]:
            messages.success(
                request,
                f"Disaster recovery runbook initiated successfully. "
                f"Task ID: {result['task_id']}. "
                f"Target RTO: 1 hour. Monitor progress in restore logs.",
            )

            logger.info(
                f"Disaster recovery initiated by {request.user.username}: "
                f"backup={backup_id}, reason={reason}"
            )

            return redirect("backups:restore_list")
        else:
            messages.error(request, f"Failed to initiate disaster recovery: {result['error']}")
            logger.error(f"Disaster recovery failed: {result['error']}")

    # GET request - show DR form
    # Get latest successful full database backup
    latest_backup = (
        Backup.objects.filter(
            backup_type=Backup.FULL_DATABASE,
            status__in=[Backup.COMPLETED, Backup.VERIFIED],
        )
        .order_by("-created_at")
        .first()
    )

    # Get all successful full database backups for selection
    available_backups = Backup.objects.filter(
        backup_type=Backup.FULL_DATABASE,
        status__in=[Backup.COMPLETED, Backup.VERIFIED],
    ).order_by("-created_at")[:20]

    # Get recent DR operations
    recent_dr_operations = BackupRestoreLog.objects.filter(
        restore_mode=BackupRestoreLog.FULL,
        initiated_by__isnull=True,  # Automated DR has no user
    ).order_by("-started_at")[:5]

    context = {
        "latest_backup": latest_backup,
        "available_backups": available_backups,
        "recent_dr_operations": recent_dr_operations,
    }

    return render(request, "backups/disaster_recovery_runbook.html", context)


@login_required
@user_passes_test(is_platform_admin)
def wal_monitoring(request):
    """
    WAL (Write-Ahead Log) Monitoring Dashboard.

    Enterprise-grade monitoring interface for WAL archiving:
    - Real-time WAL generation and archiving status
    - Compression statistics and storage metrics
    - Archiving timeline and trends
    - Health indicators and alerts
    - Configuration management
    """
    from datetime import timedelta

    from django.db.models import Avg, Count, Max, Min, Sum

    from apps.backups.models import BackupConfiguration

    # Get WAL statistics for last 24 hours
    last_24h = timezone.now() - timedelta(hours=24)
    last_hour = timezone.now() - timedelta(hours=1)

    # Total WAL archives
    total_wals = Backup.objects.filter(backup_type=Backup.WAL_ARCHIVE).count()

    # Recent WAL archives (last 24 hours)
    recent_wals = Backup.objects.filter(backup_type=Backup.WAL_ARCHIVE, created_at__gte=last_24h)

    recent_count = recent_wals.count()

    # WAL statistics
    wal_stats = recent_wals.aggregate(
        total_size=Sum("size_bytes"),
        avg_compression=Avg("compression_ratio"),
        min_compression=Min("compression_ratio"),
        max_compression=Max("compression_ratio"),
        last_archived=Max("created_at"),
    )

    # Calculate space saved by compression
    if wal_stats["total_size"] and wal_stats["avg_compression"]:
        original_size = wal_stats["total_size"] / (1 - wal_stats["avg_compression"] / 100)
        space_saved = original_size - wal_stats["total_size"]
    else:
        space_saved = 0

    # Get last 50 WAL archives for timeline
    recent_wal_list = Backup.objects.filter(backup_type=Backup.WAL_ARCHIVE).order_by("-created_at")[
        :50
    ]

    # Status distribution
    status_counts = recent_wals.values("status").annotate(count=Count("id"))

    # Calculate WAL generation rate (per hour)
    if recent_count > 0:
        hours_covered = 24
        wal_rate = recent_count / hours_covered
    else:
        wal_rate = 0

    # Get configuration
    config = BackupConfiguration.get_config()

    # Calculate next run time
    if wal_stats["last_archived"]:
        next_run = wal_stats["last_archived"] + timedelta(
            seconds=config.wal_archiving_interval_seconds
        )
    else:
        next_run = None

    # Health check
    minutes_since_last = None
    health_status = "healthy"
    health_message = "WAL archiving is operating normally"

    if wal_stats["last_archived"]:
        minutes_since_last = (timezone.now() - wal_stats["last_archived"]).total_seconds() / 60

        # Check if last archive is overdue
        expected_interval_minutes = config.wal_archiving_interval_seconds / 60
        if minutes_since_last > (expected_interval_minutes * 1.5):
            health_status = "warning"
            health_message = f"Last WAL archived {int(minutes_since_last)} minutes ago (expected every {int(expected_interval_minutes)} minutes)"
        elif minutes_since_last > (expected_interval_minutes * 2):
            health_status = "critical"
            health_message = (
                f"WAL archiving is delayed! Last archive was {int(minutes_since_last)} minutes ago"
            )

    # Get active WAL-related alerts
    wal_alerts = BackupAlert.objects.filter(
        status=BackupAlert.ACTIVE,
        alert_type__in=[BackupAlert.BACKUP_FAILURE, BackupAlert.INTEGRITY_FAILURE],
    ).order_by("-created_at")[:5]

    context = {
        "total_wals": total_wals,
        "recent_count": recent_count,
        "wal_rate": round(wal_rate, 2),
        "wal_stats": wal_stats,
        "space_saved": space_saved,
        "recent_wal_list": recent_wal_list,
        "status_counts": {item["status"]: item["count"] for item in status_counts},
        "config": config,
        "next_run": next_run,
        "minutes_since_last": minutes_since_last,
        "health_status": health_status,
        "health_message": health_message,
        "wal_alerts": wal_alerts,
    }

    return render(request, "backups/wal_monitoring.html", context)


@login_required
@user_passes_test(is_platform_admin)
@require_http_methods(["GET"])
def wal_status_api(request):
    """
    API endpoint for real-time WAL status updates.
    Returns JSON data for AJAX updates.
    """
    from datetime import timedelta

    from django.db.models import Avg, Count, Max, Sum
    from django.http import JsonResponse

    from apps.backups.models import BackupConfiguration

    last_24h = timezone.now() - timedelta(hours=24)

    # Get recent WAL stats
    recent_wals = Backup.objects.filter(backup_type=Backup.WAL_ARCHIVE, created_at__gte=last_24h)

    stats = recent_wals.aggregate(
        count=Count("id"),
        total_size=Sum("size_bytes"),
        avg_compression=Avg("compression_ratio"),
        last_archived=Max("created_at"),
    )

    # Get last 10 WAL files
    last_wals = (
        Backup.objects.filter(backup_type=Backup.WAL_ARCHIVE)
        .order_by("-created_at")[:10]
        .values(
            "id",
            "filename",
            "status",
            "size_bytes",
            "compression_ratio",
            "created_at",
            "r2_path",
            "b2_path",
            "local_path",
        )
    )

    # Get config
    config = BackupConfiguration.get_config()

    # Calculate health
    health = "healthy"
    if stats["last_archived"]:
        minutes_since = (timezone.now() - stats["last_archived"]).total_seconds() / 60
        expected_minutes = config.wal_archiving_interval_seconds / 60

        if minutes_since > (expected_minutes * 2):
            health = "critical"
        elif minutes_since > (expected_minutes * 1.5):
            health = "warning"

    return JsonResponse(
        {
            "success": True,
            "stats": {
                "count_24h": stats["count"] or 0,
                "total_size": stats["total_size"] or 0,
                "avg_compression": (
                    float(stats["avg_compression"]) if stats["avg_compression"] else 0
                ),
                "last_archived": (
                    stats["last_archived"].isoformat() if stats["last_archived"] else None
                ),
            },
            "recent_wals": list(last_wals),
            "health": health,
            "config": {
                "interval_seconds": config.wal_archiving_interval_seconds,
                "interval_display": config.wal_interval_display,
            },
        }
    )
