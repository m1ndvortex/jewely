"""
Job monitoring models for tracking Celery task execution.

This module provides models for:
- Job execution history
- Job statistics
- Job failure tracking

Per Requirement 33 - Scheduled Job Management
"""

from django.db import models
from django.utils import timezone


class JobExecution(models.Model):
    """
    Track individual job executions.

    Requirement 33.3: Display completed jobs with execution time and status.
    Requirement 33.4: Display failed jobs with error details and retry options.
    """

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("STARTED", "Started"),
        ("SUCCESS", "Success"),
        ("FAILURE", "Failure"),
        ("RETRY", "Retry"),
        ("REVOKED", "Revoked"),
    ]

    # Task identification
    task_id = models.CharField(max_length=255, unique=True, db_index=True)
    task_name = models.CharField(max_length=255, db_index=True)

    # Execution details
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="PENDING", db_index=True
    )
    args = models.JSONField(default=list, blank=True)
    kwargs = models.JSONField(default=dict, blank=True)

    # Timing
    queued_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    execution_time = models.FloatField(null=True, blank=True, help_text="Execution time in seconds")

    # Queue and priority
    queue = models.CharField(max_length=100, default="default", db_index=True)
    priority = models.IntegerField(default=5)

    # Result and error tracking
    result = models.TextField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    traceback = models.TextField(null=True, blank=True)

    # Retry tracking
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)

    # Worker information
    worker_name = models.CharField(max_length=255, null=True, blank=True)

    # Performance tracking (Requirement 33.9, 33.10)
    cpu_percent = models.FloatField(
        null=True, blank=True, help_text="CPU usage percentage during execution"
    )
    memory_mb = models.FloatField(
        null=True, blank=True, help_text="Memory usage in MB during execution"
    )
    peak_memory_mb = models.FloatField(null=True, blank=True, help_text="Peak memory usage in MB")

    class Meta:
        db_table = "job_executions"
        ordering = ["-queued_at"]
        indexes = [
            models.Index(fields=["task_name", "-queued_at"]),
            models.Index(fields=["status", "-queued_at"]),
            models.Index(fields=["queue", "-queued_at"]),
        ]

    def __str__(self):
        return f"{self.task_name} ({self.task_id}) - {self.status}"

    @property
    def duration_seconds(self):
        """Calculate execution duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def is_running(self):
        """Check if job is currently running."""
        return self.status == "STARTED"

    @property
    def is_failed(self):
        """Check if job has failed."""
        return self.status == "FAILURE"

    @property
    def can_retry(self):
        """Check if job can be retried."""
        return self.is_failed and self.retry_count < self.max_retries

    @property
    def eta_display(self):
        """Get estimated time of arrival display."""
        if self.status == "PENDING" and self.queued_at:
            # Simple estimation: assume 1 minute wait time
            eta = self.queued_at + timezone.timedelta(minutes=1)
            return eta
        return None


class JobStatistics(models.Model):
    """
    Aggregate statistics for job types.

    Requirement 33.9: Track execution times and identify slow jobs.
    Requirement 33.10: Track CPU and memory usage per job type.
    """

    task_name = models.CharField(max_length=255, unique=True, db_index=True)

    # Execution counts
    total_executions = models.IntegerField(default=0)
    successful_executions = models.IntegerField(default=0)
    failed_executions = models.IntegerField(default=0)

    # Timing statistics
    avg_execution_time = models.FloatField(
        default=0.0, help_text="Average execution time in seconds"
    )
    min_execution_time = models.FloatField(null=True, blank=True)
    max_execution_time = models.FloatField(null=True, blank=True)

    # Resource usage (Requirement 33.10)
    avg_cpu_percent = models.FloatField(
        null=True, blank=True, help_text="Average CPU usage percentage"
    )
    avg_memory_mb = models.FloatField(null=True, blank=True, help_text="Average memory usage in MB")
    peak_cpu_percent = models.FloatField(
        null=True, blank=True, help_text="Peak CPU usage percentage"
    )
    peak_memory_mb = models.FloatField(null=True, blank=True, help_text="Peak memory usage in MB")

    # Last execution
    last_execution_at = models.DateTimeField(null=True, blank=True)
    last_execution_status = models.CharField(max_length=20, null=True, blank=True)

    # Metadata
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "job_statistics"
        ordering = ["task_name"]
        verbose_name_plural = "Job statistics"

    def __str__(self):
        return f"{self.task_name} - {self.total_executions} executions"

    @property
    def success_rate(self):
        """Calculate success rate percentage."""
        if self.total_executions > 0:
            return round((self.successful_executions / self.total_executions) * 100, 2)
        return 0.0

    @property
    def failure_rate(self):
        """Calculate failure rate percentage."""
        if self.total_executions > 0:
            return round((self.failed_executions / self.total_executions) * 100, 2)
        return 0.0

    @property
    def is_slow(self):
        """Check if job is considered slow (>60 seconds average)."""
        return self.avg_execution_time > 60.0


class JobSchedule(models.Model):
    """
    Store job schedule configurations.

    Requirement 33.6: Allow administrators to configure job schedules.
    """

    SCHEDULE_TYPE_CHOICES = [
        ("cron", "Cron Expression"),
        ("interval", "Interval"),
    ]

    # Task identification
    name = models.CharField(max_length=255, unique=True, help_text="Unique schedule name")
    task_name = models.CharField(max_length=255, db_index=True, help_text="Celery task name")

    # Schedule configuration
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPE_CHOICES)

    # Cron configuration
    cron_expression = models.CharField(
        max_length=100, null=True, blank=True, help_text="Cron expression (e.g., '0 2 * * *')"
    )

    # Interval configuration
    interval_value = models.IntegerField(null=True, blank=True, help_text="Interval value")
    interval_unit = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=[
            ("seconds", "Seconds"),
            ("minutes", "Minutes"),
            ("hours", "Hours"),
            ("days", "Days"),
        ],
        help_text="Interval unit",
    )

    # Task arguments
    args = models.JSONField(default=list, blank=True, help_text="Task arguments")
    kwargs = models.JSONField(default=dict, blank=True, help_text="Task keyword arguments")

    # Queue and priority
    queue = models.CharField(max_length=100, default="default", help_text="Queue name")
    priority = models.IntegerField(default=5, help_text="Priority (0-10)")

    # Status
    enabled = models.BooleanField(default=True, help_text="Enable or disable this schedule")

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "core.User", on_delete=models.SET_NULL, null=True, related_name="created_schedules"
    )
    last_run_at = models.DateTimeField(null=True, blank=True, help_text="Last execution time")

    class Meta:
        db_table = "job_schedules"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} - {self.task_name}"

    @property
    def schedule_display(self):
        """Get human-readable schedule description."""
        if self.schedule_type == "cron":
            return f"Cron: {self.cron_expression}"
        elif self.schedule_type == "interval":
            return f"Every {self.interval_value} {self.interval_unit}"
        return "Unknown"

    def get_celery_schedule(self):
        """Convert to Celery schedule object."""
        from celery.schedules import crontab, schedule

        if self.schedule_type == "cron":
            parts = self.cron_expression.split()
            return crontab(
                minute=parts[0],
                hour=parts[1],
                day_of_month=parts[2],
                month_of_year=parts[3],
                day_of_week=parts[4],
            )
        elif self.schedule_type == "interval":
            unit_map = {
                "seconds": 1,
                "minutes": 60,
                "hours": 3600,
                "days": 86400,
            }
            seconds = self.interval_value * unit_map.get(self.interval_unit, 1)
            return schedule(run_every=seconds)

        return None
