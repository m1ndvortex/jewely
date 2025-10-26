"""
URL configuration for backup management.
"""

from django.urls import path

from . import views

app_name = "backups"

urlpatterns = [
    # Dashboard
    path("", views.backup_dashboard, name="dashboard"),
    # Backup management
    path("backups/", views.backup_list, name="backup_list"),
    path("backups/<uuid:backup_id>/", views.backup_detail, name="backup_detail"),
    path("backups/manual/", views.manual_backup, name="manual_backup"),
    # Restore management
    path("restore/", views.restore_backup, name="restore_backup"),
    path("restore/<uuid:backup_id>/", views.restore_backup, name="restore_backup_with_id"),
    path("restores/", views.restore_list, name="restore_list"),
    path("restores/<uuid:restore_log_id>/", views.restore_detail, name="restore_detail"),
    # Alert management
    path("alerts/", views.alert_list, name="alert_list"),
    path("alerts/<uuid:alert_id>/acknowledge/", views.acknowledge_alert, name="acknowledge_alert"),
    path("alerts/<uuid:alert_id>/resolve/", views.resolve_alert, name="resolve_alert"),
]
