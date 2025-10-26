"""
Backup monitoring and alerting services.

This module implements comprehensive backup monitoring including:
- Backup failure detection
- Size deviation alerts (>20% change)
- Duration threshold alerts
- Storage capacity alerts (>80%)
- Multi-channel notifications (email, SMS, in-app, webhooks)
"""

import logging
from datetime import timedelta
from typing import Dict, List, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Avg
from django.utils import timezone

from apps.notifications.services import create_notification, send_system_email

from .models import Backup, BackupAlert, BackupRestoreLog
from .storage import get_storage_backend

User = get_user_model()
logger = logging.getLogger(__name__)


def send_backup_alert_notifications(  # noqa: C901
    alert: BackupAlert,
    recipients: Optional[List[User]] = None,
) -> Dict[str, bool]:
    """
    Send backup alert notifications via multiple channels.

    Args:
        alert: BackupAlert instance to send notifications for
        recipients: Optional list of users to notify (defaults to platform admins)

    Returns:
        Dictionary with notification status for each channel
    """
    results = {
        "in_app": False,
        "email": False,
        "sms": False,
        "webhook": False,
    }

    # Get recipients (platform admins if not specified)
    if recipients is None:
        recipients = list(User.objects.filter(role="PLATFORM_ADMIN", is_active=True))

    if not recipients:
        logger.warning("No recipients found for backup alert notifications")
        return results

    # Prepare alert context
    context = {
        "alert": alert,
        "alert_type": alert.get_alert_type_display(),
        "severity": alert.get_severity_display(),
        "message": alert.message,
        "details": alert.details,
        "created_at": alert.created_at,
        "backup": alert.backup,
        "restore_log": alert.restore_log,
    }

    # Send in-app notifications
    try:
        for user in recipients:
            create_notification(
                user=user,
                title=f"Backup Alert: {alert.get_alert_type_display()}",
                message=alert.message,
                notification_type="ERROR" if alert.severity in ["ERROR", "CRITICAL"] else "WARNING",
                action_url=f"/admin/backups/alert/{alert.id}/",
                action_text="View Alert",
            )
        results["in_app"] = True
        logger.info(f"Sent in-app notifications for alert {alert.id} to {len(recipients)} users")
    except Exception as e:
        logger.error(f"Failed to send in-app notifications for alert {alert.id}: {e}")

    # Send email notifications
    try:
        email_subject = f"[{alert.severity}] Backup Alert: {alert.get_alert_type_display()}"

        for user in recipients:
            if user.email:
                # For now, send a simple system email
                # In production, you would use a proper email template
                send_system_email(
                    user=user,
                    template_name="backup_alert",  # Would need to create this template
                    context=context,
                    subject=email_subject,
                )

        results["email"] = True
        logger.info(f"Sent email notifications for alert {alert.id} to {len(recipients)} users")
    except Exception as e:
        logger.error(f"Failed to send email notifications for alert {alert.id}: {e}")

    # Send SMS notifications (for critical alerts only)
    if alert.severity == BackupAlert.CRITICAL:
        try:
            from apps.notifications.services import send_sms_notification

            sms_message = f"CRITICAL BACKUP ALERT: {alert.message[:140]}"

            sms_sent_count = 0
            for user in recipients:
                if user.phone:
                    sms_result = send_sms_notification(
                        user=user,
                        message=sms_message,
                        sms_type="ALERT",
                        create_in_app_notification=False,  # Already created above
                    )
                    if sms_result:
                        sms_sent_count += 1

            results["sms"] = sms_sent_count > 0
            logger.info(f"Sent SMS notifications for alert {alert.id} to {sms_sent_count} users")
        except Exception as e:
            logger.error(f"Failed to send SMS notifications for alert {alert.id}: {e}")

    # Send webhook notifications
    try:
        webhook_sent = send_webhook_notification(alert)
        results["webhook"] = webhook_sent
    except Exception as e:
        logger.error(f"Failed to send webhook notification for alert {alert.id}: {e}")

    # Update alert with notification channels
    channels_sent = [channel for channel, success in results.items() if success]
    alert.notification_channels = channels_sent
    alert.notification_sent_at = timezone.now()
    alert.save(update_fields=["notification_channels", "notification_sent_at"])

    return results


def send_webhook_notification(alert: BackupAlert) -> bool:
    """
    Send webhook notification for backup alert.

    Args:
        alert: BackupAlert instance

    Returns:
        True if webhook sent successfully, False otherwise
    """
    webhook_url = getattr(settings, "BACKUP_ALERT_WEBHOOK_URL", None)

    if not webhook_url:
        logger.debug("No backup alert webhook URL configured")
        return False

    try:
        import requests

        payload = {
            "alert_id": str(alert.id),
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "message": alert.message,
            "details": alert.details,
            "created_at": alert.created_at.isoformat(),
            "backup_id": str(alert.backup.id) if alert.backup else None,
            "restore_log_id": str(alert.restore_log.id) if alert.restore_log else None,
        }

        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code in [200, 201, 202]:
            logger.info(f"Webhook notification sent successfully for alert {alert.id}")
            return True
        else:
            logger.warning(
                f"Webhook notification failed for alert {alert.id}: "
                f"status={response.status_code}"
            )
            return False

    except Exception as e:
        logger.error(f"Failed to send webhook notification for alert {alert.id}: {e}")
        return False


def create_backup_alert_with_notifications(
    alert_type: str,
    severity: str,
    message: str,
    backup: Optional[Backup] = None,
    restore_log: Optional[BackupRestoreLog] = None,
    details: Optional[dict] = None,
    recipients: Optional[List[User]] = None,
) -> BackupAlert:
    """
    Create a backup alert and send notifications.

    Args:
        alert_type: Type of alert (BACKUP_FAILURE, SIZE_DEVIATION, etc.)
        severity: Severity level (INFO, WARNING, ERROR, CRITICAL)
        message: Alert message
        backup: Related backup object (optional)
        restore_log: Related restore log (optional)
        details: Additional details (optional)
        recipients: Optional list of users to notify

    Returns:
        Created BackupAlert instance
    """
    alert = BackupAlert.objects.create(
        alert_type=alert_type,
        severity=severity,
        message=message,
        backup=backup,
        restore_log=restore_log,
        details=details or {},
    )

    logger.info(f"Created backup alert: {alert_type} - {severity} - {message}")

    # Send notifications
    send_backup_alert_notifications(alert, recipients=recipients)

    return alert


def check_backup_size_deviation(backup: Backup) -> Optional[BackupAlert]:
    """
    Check if backup size deviates significantly from recent backups.

    Creates an alert if size deviation exceeds 20%.

    Args:
        backup: Backup instance to check

    Returns:
        BackupAlert instance if deviation detected, None otherwise
    """
    # Get recent backups of the same type (last 7 days, excluding current backup)
    recent_backups = (
        Backup.objects.filter(
            backup_type=backup.backup_type,
            status__in=[Backup.COMPLETED, Backup.VERIFIED],
            created_at__gte=timezone.now() - timedelta(days=7),
        )
        .exclude(id=backup.id)
        .order_by("-created_at")[:10]
    )

    if not recent_backups:
        logger.debug(f"No recent backups found for comparison (backup {backup.id})")
        return None

    # Calculate average size of recent backups
    avg_size = recent_backups.aggregate(avg=Avg("size_bytes"))["avg"]

    if not avg_size or avg_size == 0:
        logger.debug(f"Cannot calculate average size for backup {backup.id}")
        return None

    # Calculate deviation percentage
    deviation = abs(backup.size_bytes - avg_size) / avg_size * 100

    # Create alert if deviation exceeds 20%
    if deviation > 20:
        severity = BackupAlert.CRITICAL if deviation > 50 else BackupAlert.WARNING

        message = (
            f"Backup size deviation detected: {backup.filename} is "
            f"{deviation:.1f}% {'larger' if backup.size_bytes > avg_size else 'smaller'} "
            f"than average ({backup.get_size_mb():.2f} MB vs {avg_size / (1024**2):.2f} MB avg)"
        )

        details = {
            "backup_size_bytes": backup.size_bytes,
            "backup_size_mb": backup.get_size_mb(),
            "average_size_bytes": int(avg_size),
            "average_size_mb": round(avg_size / (1024**2), 2),
            "deviation_percentage": round(deviation, 2),
            "recent_backups_count": len(recent_backups),
        }

        alert = create_backup_alert_with_notifications(
            alert_type=BackupAlert.SIZE_DEVIATION,
            severity=severity,
            message=message,
            backup=backup,
            details=details,
        )

        return alert

    return None


def check_backup_duration_threshold(backup: Backup) -> Optional[BackupAlert]:
    """
    Check if backup duration exceeds expected thresholds.

    Creates an alert if duration is significantly longer than usual.

    Args:
        backup: Backup instance to check

    Returns:
        BackupAlert instance if threshold exceeded, None otherwise
    """
    if not backup.backup_duration_seconds:
        return None

    # Get recent backups of the same type for comparison
    recent_backups = (
        Backup.objects.filter(
            backup_type=backup.backup_type,
            status__in=[Backup.COMPLETED, Backup.VERIFIED],
            backup_duration_seconds__isnull=False,
            created_at__gte=timezone.now() - timedelta(days=7),
        )
        .exclude(id=backup.id)
        .order_by("-created_at")[:10]
    )

    if not recent_backups:
        logger.debug(f"No recent backups found for duration comparison (backup {backup.id})")
        return None

    # Calculate average duration
    avg_duration = recent_backups.aggregate(avg=Avg("backup_duration_seconds"))["avg"]

    if not avg_duration or avg_duration == 0:
        return None

    # Calculate deviation percentage
    deviation = abs(backup.backup_duration_seconds - avg_duration) / avg_duration * 100

    # Create alert if duration is 50% longer than average
    if backup.backup_duration_seconds > avg_duration and deviation > 50:
        severity = BackupAlert.CRITICAL if deviation > 100 else BackupAlert.WARNING

        message = (
            f"Backup duration threshold exceeded: {backup.filename} took "
            f"{backup.backup_duration_seconds}s ({backup.backup_duration_seconds / 60:.1f} min), "
            f"{deviation:.1f}% longer than average ({int(avg_duration)}s avg)"
        )

        details = {
            "backup_duration_seconds": backup.backup_duration_seconds,
            "backup_duration_minutes": round(backup.backup_duration_seconds / 60, 2),
            "average_duration_seconds": int(avg_duration),
            "average_duration_minutes": round(avg_duration / 60, 2),
            "deviation_percentage": round(deviation, 2),
            "recent_backups_count": len(recent_backups),
        }

        alert = create_backup_alert_with_notifications(
            alert_type=BackupAlert.DURATION_THRESHOLD,
            severity=severity,
            message=message,
            backup=backup,
            details=details,
        )

        return alert

    return None


def check_storage_capacity() -> List[BackupAlert]:
    """
    Check storage capacity across all storage backends.

    Creates alerts if storage usage exceeds 80%.

    Returns:
        List of BackupAlert instances created
    """
    alerts = []

    storage_backends = ["local", "r2", "b2"]

    for backend_name in storage_backends:
        try:
            backend = get_storage_backend(backend_name)

            # Get storage usage information
            usage_info = backend.get_storage_usage()

            if not usage_info:
                logger.warning(f"Could not get storage usage for {backend_name}")
                continue

            total_bytes = usage_info.get("total_bytes", 0)
            used_bytes = usage_info.get("used_bytes", 0)

            if total_bytes == 0:
                continue

            usage_percentage = (used_bytes / total_bytes) * 100

            # Create alert if usage exceeds 80%
            if usage_percentage > 80:
                severity = BackupAlert.CRITICAL if usage_percentage > 90 else BackupAlert.WARNING

                message = (
                    f"Storage capacity warning for {backend_name.upper()}: "
                    f"{usage_percentage:.1f}% used "
                    f"({used_bytes / (1024**3):.2f} GB / {total_bytes / (1024**3):.2f} GB)"
                )

                details = {
                    "storage_backend": backend_name,
                    "total_bytes": total_bytes,
                    "used_bytes": used_bytes,
                    "available_bytes": total_bytes - used_bytes,
                    "usage_percentage": round(usage_percentage, 2),
                    "total_gb": round(total_bytes / (1024**3), 2),
                    "used_gb": round(used_bytes / (1024**3), 2),
                    "available_gb": round((total_bytes - used_bytes) / (1024**3), 2),
                }

                alert = create_backup_alert_with_notifications(
                    alert_type=BackupAlert.STORAGE_CAPACITY,
                    severity=severity,
                    message=message,
                    details=details,
                )

                alerts.append(alert)

        except Exception as e:
            logger.error(f"Failed to check storage capacity for {backend_name}: {e}")

    return alerts


def monitor_backup_completion(backup: Backup) -> List[BackupAlert]:
    """
    Monitor backup completion and create alerts for any issues.

    This function should be called after a backup completes.

    Args:
        backup: Backup instance to monitor

    Returns:
        List of BackupAlert instances created
    """
    alerts = []

    # Check for backup failure
    if backup.is_failed():
        message = f"Backup failed: {backup.filename}"

        if backup.notes:
            message += f" - {backup.notes}"

        alert = create_backup_alert_with_notifications(
            alert_type=BackupAlert.BACKUP_FAILURE,
            severity=BackupAlert.CRITICAL,
            message=message,
            backup=backup,
            details={
                "backup_type": backup.backup_type,
                "tenant_id": str(backup.tenant.id) if backup.tenant else None,
                "error": backup.notes,
            },
        )
        alerts.append(alert)

    # Check for size deviation (only for completed backups)
    elif backup.is_completed():
        size_alert = check_backup_size_deviation(backup)
        if size_alert:
            alerts.append(size_alert)

        # Check for duration threshold
        duration_alert = check_backup_duration_threshold(backup)
        if duration_alert:
            alerts.append(duration_alert)

    return alerts


def monitor_restore_completion(restore_log: BackupRestoreLog) -> Optional[BackupAlert]:
    """
    Monitor restore completion and create alert if failed.

    Args:
        restore_log: BackupRestoreLog instance to monitor

    Returns:
        BackupAlert instance if restore failed, None otherwise
    """
    if restore_log.is_failed():
        message = f"Restore operation failed: {restore_log.get_restore_mode_display()}"

        if restore_log.error_message:
            message += f" - {restore_log.error_message}"

        details = {
            "restore_mode": restore_log.restore_mode,
            "backup_id": str(restore_log.backup.id),
            "tenant_ids": restore_log.tenant_ids,
            "error": restore_log.error_message,
            "duration_seconds": restore_log.duration_seconds,
        }

        alert = create_backup_alert_with_notifications(
            alert_type=BackupAlert.RESTORE_FAILURE,
            severity=BackupAlert.CRITICAL,
            message=message,
            restore_log=restore_log,
            details=details,
        )

        return alert

    return None


def get_active_alerts(severity: Optional[str] = None) -> List[BackupAlert]:
    """
    Get all active backup alerts.

    Args:
        severity: Optional severity filter (INFO, WARNING, ERROR, CRITICAL)

    Returns:
        List of active BackupAlert instances
    """
    queryset = BackupAlert.objects.filter(status=BackupAlert.ACTIVE).order_by("-created_at")

    if severity:
        queryset = queryset.filter(severity=severity)

    return list(queryset)


def get_alert_summary() -> Dict:
    """
    Get summary of backup alerts.

    Returns:
        Dictionary with alert statistics
    """
    total_alerts = BackupAlert.objects.count()
    active_alerts = BackupAlert.objects.filter(status=BackupAlert.ACTIVE).count()
    critical_alerts = BackupAlert.objects.filter(
        status=BackupAlert.ACTIVE, severity=BackupAlert.CRITICAL
    ).count()

    # Get alerts by type
    alerts_by_type = {}
    for alert_type, _ in BackupAlert.ALERT_TYPE_CHOICES:
        count = BackupAlert.objects.filter(alert_type=alert_type, status=BackupAlert.ACTIVE).count()
        alerts_by_type[alert_type] = count

    # Get recent alerts (last 24 hours)
    recent_alerts = BackupAlert.objects.filter(
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).count()

    return {
        "total_alerts": total_alerts,
        "active_alerts": active_alerts,
        "critical_alerts": critical_alerts,
        "alerts_by_type": alerts_by_type,
        "recent_alerts_24h": recent_alerts,
    }
