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
    # Example: Run a task every 5 minutes
    # 'example-task': {
    #     'task': 'apps.core.tasks.example_task',
    #     'schedule': crontab(minute='*/5'),
    # },
}

# Task routing configuration
app.conf.task_routes = {
    "apps.backups.tasks.*": {"queue": "backups", "priority": 10},
    "apps.notifications.tasks.*": {"queue": "notifications", "priority": 5},
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f"Request: {self.request!r}")
