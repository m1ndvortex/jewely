"""
Celery configuration for jewelry shop SaaS platform.
"""

import os

from celery import Celery
from celery.schedules import crontab  # noqa: F401

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("jewelry_shop")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery Beat Schedule for periodic tasks
app.conf.beat_schedule = {
    # Daily full database backup at 2:00 AM
    "daily-full-database-backup": {
        "task": "apps.backups.tasks.daily_full_database_backup",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "backups", "priority": 10},
    },
    # Weekly per-tenant backup every Sunday at 3:00 AM
    "weekly-per-tenant-backup": {
        "task": "apps.backups.tasks.weekly_per_tenant_backup",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),  # Sunday = 0
        "options": {"queue": "backups", "priority": 9},
    },
    # Continuous WAL archiving - interval controlled by BackupConfiguration model
    "continuous-wal-archiving": {
        "task": "apps.backups.tasks.continuous_wal_archiving",
        "schedule": 3600.0,  # Default: Every 1 hour (3600 seconds), adjustable via admin UI
        "options": {"queue": "backups", "priority": 10},
    },
    # Daily configuration backup at 4:00 AM
    "daily-configuration-backup": {
        "task": "apps.backups.tasks.configuration_backup",
        "schedule": crontab(hour=4, minute=0),
        "options": {"queue": "backups", "priority": 9},
    },
    # Fetch gold rates every 5 minutes
    "fetch-gold-rates": {
        "task": "apps.pricing.tasks.fetch_gold_rates",
        "schedule": crontab(minute="*/5"),
        "options": {"queue": "pricing", "priority": 8},
    },
    # Update inventory prices daily at 2 AM
    "update-inventory-prices": {
        "task": "apps.pricing.tasks.update_inventory_prices",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "pricing", "priority": 8},
    },
    # Clean up old gold rates daily at 3 AM
    "cleanup-old-gold-rates": {
        "task": "apps.pricing.tasks.cleanup_old_rates",
        "schedule": crontab(hour=3, minute=0),
        "options": {"queue": "pricing", "priority": 3},
    },
    # Execute scheduled reports every 15 minutes
    "execute-scheduled-reports": {
        "task": "apps.reporting.tasks.execute_scheduled_reports",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "reports", "priority": 7},
    },
    # Clean up old report files daily at 4:30 AM (moved from 4:00 AM to avoid conflict with config backup)
    "cleanup-old-report-files": {
        "task": "apps.reporting.tasks.cleanup_old_report_files",
        "schedule": crontab(hour=4, minute=30),
        "options": {"queue": "reports", "priority": 2},
    },
    # Clean up old execution records weekly on Sunday at 5 AM
    "cleanup-old-executions": {
        "task": "apps.reporting.tasks.cleanup_old_executions",
        "schedule": crontab(hour=5, minute=0, day_of_week=0),
        "options": {"queue": "reports", "priority": 2},
    },
    # Update schedule next runs daily at 1 AM
    "update-schedule-next-runs": {
        "task": "apps.reporting.tasks.update_schedule_next_runs",
        "schedule": crontab(hour=1, minute=0),
        "options": {"queue": "reports", "priority": 5},
    },
    # Generate usage stats weekly on Monday at 6 AM
    "generate-report-usage-stats": {
        "task": "apps.reporting.tasks.generate_report_usage_stats",
        "schedule": crontab(hour=6, minute=0, day_of_week=1),
        "options": {"queue": "reports", "priority": 3},
    },
    # Run monthly depreciation on the 1st of each month at 1:00 AM
    "monthly-depreciation-run": {
        "task": "apps.accounting.tasks.run_monthly_depreciation_all_tenants",
        "schedule": crontab(hour=1, minute=0, day_of_month=1),
        "options": {"queue": "accounting", "priority": 8},
    },
    # Check system metrics for alerts every 5 minutes
    "check-system-metrics": {
        "task": "check_system_metrics",
        "schedule": 300.0,  # Every 5 minutes (300 seconds)
        "options": {"queue": "monitoring", "priority": 9},
    },
    # Check service health every 5 minutes
    "check-service-health": {
        "task": "check_service_health",
        "schedule": 300.0,  # Every 5 minutes (300 seconds)
        "options": {"queue": "monitoring", "priority": 9},
    },
    # Check for alert escalations every 5 minutes
    "check-alert-escalations": {
        "task": "check_alert_escalations",
        "schedule": 300.0,  # Every 5 minutes (300 seconds)
        "options": {"queue": "monitoring", "priority": 8},
    },
    # Auto-resolve alerts every 10 minutes
    "auto-resolve-alerts": {
        "task": "auto_resolve_alerts",
        "schedule": 600.0,  # Every 10 minutes (600 seconds)
        "options": {"queue": "monitoring", "priority": 7},
    },
    # Retry failed webhooks every minute
    "retry-failed-webhooks": {
        "task": "apps.core.webhook_tasks.retry_failed_webhooks",
        "schedule": 60.0,  # Every minute (60 seconds)
        "options": {"queue": "webhooks", "priority": 8},
    },
    # Clean up old webhook deliveries weekly on Sunday at 4 AM
    "cleanup-old-webhook-deliveries": {
        "task": "apps.core.webhook_tasks.cleanup_old_deliveries",
        "schedule": crontab(hour=4, minute=0, day_of_week=0),  # Sunday = 0
        "options": {"queue": "webhooks", "priority": 2},
    },
}

# Task routing configuration
app.conf.task_routes = {
    "apps.backups.tasks.*": {"queue": "backups", "priority": 10},
    "apps.notifications.tasks.*": {"queue": "notifications", "priority": 5},
    "apps.pricing.tasks.*": {"queue": "pricing", "priority": 8},
    "apps.reporting.tasks.*": {"queue": "reports", "priority": 7},
    "apps.accounting.tasks.*": {"queue": "accounting", "priority": 8},
    "apps.core.alert_tasks.*": {"queue": "monitoring", "priority": 9},
    "apps.core.webhook_tasks.*": {"queue": "webhooks", "priority": 8},
    "check_system_metrics": {"queue": "monitoring", "priority": 9},
    "check_service_health": {"queue": "monitoring", "priority": 9},
    "check_alert_escalations": {"queue": "monitoring", "priority": 8},
    "auto_resolve_alerts": {"queue": "monitoring", "priority": 7},
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f"Request: {self.request!r}")
