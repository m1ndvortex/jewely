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
    # Clean up old report files daily at 4 AM
    "cleanup-old-report-files": {
        "task": "apps.reporting.tasks.cleanup_old_report_files",
        "schedule": crontab(hour=4, minute=0),
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
}

# Task routing configuration
app.conf.task_routes = {
    "apps.backups.tasks.*": {"queue": "backups", "priority": 10},
    "apps.notifications.tasks.*": {"queue": "notifications", "priority": 5},
    "apps.pricing.tasks.*": {"queue": "pricing", "priority": 8},
    "apps.reporting.tasks.*": {"queue": "reports", "priority": 7},
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f"Request: {self.request!r}")
