"""
URL configuration for backup management.
"""

from django.urls import path

from . import views

app_name = "backups"

urlpatterns = [
    # Dashboard
    path("", views.backup_dashboard, name="dashboard"),
    # WAL Monitoring
    path("wal-monitoring/", views.wal_monitoring, name="wal_monitoring"),
    path("api/wal-status/", views.wal_status_api, name="wal_status_api"),
    # Daily Backup Monitoring
    path("daily-backup-monitoring/", views.daily_backup_monitoring, name="daily_backup_monitoring"),
    path("api/daily-backup-status/", views.daily_backup_status_api, name="daily_backup_status_api"),
    # Weekly Backup Monitoring
    path("weekly-backup-monitoring/",
         views.weekly_backup_monitoring,
         name="weekly_backup_monitoring"),
    path("api/weekly-backup-status/",
         views.weekly_backup_status_api,
         name="weekly_backup_status_api"),
    # Backup management
    path("backups/", views.backup_list, name="backup_list"),
    path("backups/<uuid:backup_id>/", views.backup_detail, name="backup_detail"),
    path("backups/manual/", views.manual_backup, name="manual_backup"),
    path("backups/progress/", views.backup_progress, name="backup_progress"),
    # API endpoints
    path("api/backup-status/", views.backup_status_api, name="backup_status_api"),
    path("api/cancel-backup/", views.cancel_backup_api, name="cancel_backup_api"),
    # Restore management
    path("restore/", views.restore_backup, name="restore_backup"),
    path("restore/<uuid:backup_id>/", views.restore_backup, name="restore_backup_with_id"),
    path("restores/", views.restore_list, name="restore_list"),
    path("restores/<uuid:restore_log_id>/", views.restore_detail, name="restore_detail"),
    # Disaster recovery
    path("disaster-recovery/", views.disaster_recovery_runbook, name="disaster_recovery_runbook"),
    # Alert management
    path("alerts/", views.alert_list, name="alert_list"),
    path("alerts/<uuid:alert_id>/acknowledge/", views.acknowledge_alert, name="acknowledge_alert"),
    path("alerts/<uuid:alert_id>/resolve/", views.resolve_alert, name="resolve_alert"),
]
