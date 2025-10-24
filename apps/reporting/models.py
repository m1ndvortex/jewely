"""
Reporting models for the jewelry shop SaaS platform.

Implements Requirement 15: Advanced Reporting and Analytics
- Report model for saved reports
- Report parameter system (filters, date ranges, grouping)
- Report scheduling with Celery
- Report delivery via email
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

User = get_user_model()


class ReportCategory(models.Model):
    """Categories for organizing reports."""

    CATEGORY_CHOICES = [
        ("SALES", "Sales Reports"),
        ("INVENTORY", "Inventory Reports"),
        ("FINANCIAL", "Financial Reports"),
        ("CUSTOMER", "Customer Reports"),
        ("EMPLOYEE", "Employee Reports"),
        ("CUSTOM", "Custom Reports"),
    ]

    name = models.CharField(max_length=100)
    category_type = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="CSS icon class")
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "reporting_categories"
        ordering = ["sort_order", "name"]
        verbose_name_plural = "Report Categories"

    def __str__(self):
        return self.name


class Report(models.Model):
    """
    Main report model for saved reports.

    Supports both pre-built and custom reports with flexible parameter system.
    """

    REPORT_TYPES = [
        ("PREDEFINED", "Pre-defined Report"),
        ("CUSTOM", "Custom Report"),
        ("TEMPLATE", "Report Template"),
    ]

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("ACTIVE", "Active"),
        ("ARCHIVED", "Archived"),
    ]

    OUTPUT_FORMATS = [
        ("PDF", "PDF Document"),
        ("EXCEL", "Excel Spreadsheet"),
        ("CSV", "CSV File"),
        ("JSON", "JSON Data"),
        ("HTML", "HTML Page"),
    ]

    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.ForeignKey(ReportCategory, on_delete=models.PROTECT)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES, default="CUSTOM")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")

    # Report Configuration
    query_config = models.JSONField(
        help_text="SQL query or data source configuration", default=dict
    )
    parameters = models.JSONField(
        help_text="Report parameters schema (filters, date ranges, grouping)", default=dict
    )
    default_parameters = models.JSONField(help_text="Default parameter values", default=dict)

    # Layout and Formatting
    layout_config = models.JSONField(
        help_text="Report layout configuration (columns, charts, formatting)", default=dict
    )
    output_formats = models.JSONField(help_text="Supported output formats", default=list)

    # Access Control
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="created_reports")
    is_public = models.BooleanField(
        default=False, help_text="Whether this report is available to all users in the tenant"
    )
    allowed_roles = models.JSONField(
        help_text="List of roles allowed to access this report", default=list
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    run_count = models.IntegerField(default=0)

    class Meta:
        db_table = "reporting_reports"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "category"]),
            models.Index(fields=["created_by"]),
            models.Index(fields=["report_type"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="unique_report_name_per_tenant")
        ]

    def __str__(self):
        return f"{self.name} ({self.tenant.company_name})"

    def clean(self):
        """Validate report configuration."""
        super().clean()

        # Validate query_config based on report_type
        if self.report_type == "CUSTOM" and not self.query_config:
            raise ValidationError("Custom reports must have query configuration")

        # Validate output_formats
        if self.output_formats:
            valid_formats = [choice[0] for choice in self.OUTPUT_FORMATS]
            for format_type in self.output_formats:
                if format_type not in valid_formats:
                    raise ValidationError(f"Invalid output format: {format_type}")

    def get_parameter_schema(self) -> Dict[str, Any]:
        """Get the parameter schema for this report."""
        return self.parameters or {}

    def get_default_parameters(self) -> Dict[str, Any]:
        """Get default parameter values."""
        return self.default_parameters or {}

    def can_user_access(self, user: User) -> bool:
        """Check if user can access this report."""
        if user.tenant_id != self.tenant_id:
            return False

        if self.created_by == user:
            return True

        if self.is_public:
            return True

        if self.allowed_roles and user.role in self.allowed_roles:
            return True

        return False

    def increment_run_count(self):
        """Increment the run count and update last run time."""
        self.run_count += 1
        self.last_run_at = timezone.now()
        self.save(update_fields=["run_count", "last_run_at"])


class ReportSchedule(models.Model):
    """
    Report scheduling configuration for automated report generation.
    """

    FREQUENCY_CHOICES = [
        ("ONCE", "Run Once"),
        ("DAILY", "Daily"),
        ("WEEKLY", "Weekly"),
        ("MONTHLY", "Monthly"),
        ("QUARTERLY", "Quarterly"),
        ("YEARLY", "Yearly"),
        ("CUSTOM", "Custom Cron"),
    ]

    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("PAUSED", "Paused"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
    ]

    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="schedules")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Scheduling Configuration
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    cron_expression = models.CharField(
        max_length=100, blank=True, help_text="Custom cron expression (only for CUSTOM frequency)"
    )
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)

    # Report Parameters
    parameters = models.JSONField(
        help_text="Parameters to use when running the report", default=dict
    )
    output_format = models.CharField(max_length=10, choices=Report.OUTPUT_FORMATS, default="PDF")

    # Delivery Configuration
    email_recipients = models.JSONField(
        help_text="List of email addresses to send the report to", default=list
    )
    email_subject = models.CharField(max_length=255, blank=True)
    email_body = models.TextField(blank=True)

    # Status and Metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Execution Tracking
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    run_count = models.IntegerField(default=0)

    class Meta:
        db_table = "reporting_schedules"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["report", "status"]),
            models.Index(fields=["next_run_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.report.name}"

    def clean(self):
        """Validate schedule configuration."""
        super().clean()

        if self.frequency == "CUSTOM" and not self.cron_expression:
            raise ValidationError("Custom frequency requires cron expression")

        if self.end_date and self.end_date <= self.start_date:
            raise ValidationError("End date must be after start date")

        if not self.email_recipients:
            raise ValidationError("At least one email recipient is required")

    def calculate_next_run(self) -> Optional[datetime]:  # noqa: C901
        """Calculate the next run time based on frequency."""
        if self.status != "ACTIVE":
            return None

        if self.end_date and timezone.now() >= self.end_date:
            return None

        base_time = self.last_run_at or self.start_date

        if self.frequency == "ONCE":
            return self.start_date if not self.last_run_at else None
        elif self.frequency == "DAILY":
            return base_time + timedelta(days=1)
        elif self.frequency == "WEEKLY":
            return base_time + timedelta(weeks=1)
        elif self.frequency == "MONTHLY":
            # Add one month (approximate)
            if base_time.month == 12:
                return base_time.replace(year=base_time.year + 1, month=1)
            else:
                return base_time.replace(month=base_time.month + 1)
        elif self.frequency == "QUARTERLY":
            # Add 3 months
            month = base_time.month + 3
            year = base_time.year
            if month > 12:
                month -= 12
                year += 1
            return base_time.replace(year=year, month=month)
        elif self.frequency == "YEARLY":
            return base_time.replace(year=base_time.year + 1)
        elif self.frequency == "CUSTOM":
            # For custom cron, this would need a cron parser library
            # For now, return None and handle in Celery Beat
            return None

        return None

    def update_next_run(self):
        """Update the next_run_at field."""
        self.next_run_at = self.calculate_next_run()
        self.save(update_fields=["next_run_at"])


class ReportExecution(models.Model):
    """
    Track report execution history and results.
    """

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("RUNNING", "Running"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
        ("CANCELLED", "Cancelled"),
    ]

    TRIGGER_TYPES = [
        ("MANUAL", "Manual"),
        ("SCHEDULED", "Scheduled"),
        ("API", "API"),
    ]

    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="executions")
    schedule = models.ForeignKey(
        ReportSchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name="executions"
    )

    # Execution Details
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_TYPES)
    parameters = models.JSONField(help_text="Parameters used for this execution", default=dict)
    output_format = models.CharField(max_length=10, choices=Report.OUTPUT_FORMATS)

    # Status and Timing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)

    # Results
    result_file_path = models.CharField(max_length=500, blank=True)
    result_file_size = models.BigIntegerField(null=True, blank=True)
    row_count = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    # User and Delivery
    executed_by = models.ForeignKey(User, on_delete=models.PROTECT)
    email_sent = models.BooleanField(default=False)
    email_recipients = models.JSONField(default=list)

    # Celery Task
    celery_task_id = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "reporting_executions"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["report", "-started_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["executed_by", "-started_at"]),
            models.Index(fields=["celery_task_id"]),
        ]

    def __str__(self):
        return f"{self.report.name} - {self.started_at.strftime('%Y-%m-%d %H:%M')}"

    def mark_completed(self, result_file_path: str = "", row_count: int = None):
        """Mark execution as completed."""
        self.status = "COMPLETED"
        self.completed_at = timezone.now()
        self.result_file_path = result_file_path
        self.row_count = row_count

        if self.started_at:
            duration = self.completed_at - self.started_at
            self.duration_seconds = int(duration.total_seconds())

        self.save(
            update_fields=[
                "status",
                "completed_at",
                "result_file_path",
                "row_count",
                "duration_seconds",
            ]
        )

    def mark_failed(self, error_message: str):
        """Mark execution as failed."""
        self.status = "FAILED"
        self.completed_at = timezone.now()
        self.error_message = error_message

        if self.started_at:
            duration = self.completed_at - self.started_at
            self.duration_seconds = int(duration.total_seconds())

        self.save(update_fields=["status", "completed_at", "error_message", "duration_seconds"])

    @property
    def is_running(self) -> bool:
        """Check if execution is currently running."""
        return self.status in ["PENDING", "RUNNING"]

    @property
    def is_completed(self) -> bool:
        """Check if execution completed successfully."""
        return self.status == "COMPLETED"

    @property
    def duration_display(self) -> str:
        """Get human-readable duration."""
        if not self.duration_seconds:
            return "N/A"

        if self.duration_seconds < 60:
            return f"{self.duration_seconds}s"
        elif self.duration_seconds < 3600:
            minutes = self.duration_seconds // 60
            seconds = self.duration_seconds % 60
            return f"{minutes}m {seconds}s"
        else:
            hours = self.duration_seconds // 3600
            minutes = (self.duration_seconds % 3600) // 60
            return f"{hours}h {minutes}m"


class ReportParameter(models.Model):
    """
    Define parameter schemas for reports.

    This model helps create a UI for report parameters and validates input.
    """

    PARAMETER_TYPES = [
        ("TEXT", "Text Input"),
        ("NUMBER", "Number Input"),
        ("DATE", "Date Picker"),
        ("DATERANGE", "Date Range Picker"),
        ("SELECT", "Dropdown Select"),
        ("MULTISELECT", "Multi-Select"),
        ("BOOLEAN", "Checkbox"),
        ("BRANCH", "Branch Selector"),
        ("EMPLOYEE", "Employee Selector"),
        ("CUSTOMER", "Customer Selector"),
        ("PRODUCT", "Product Selector"),
    ]

    report = models.ForeignKey(
        Report, on_delete=models.CASCADE, related_name="parameter_definitions"
    )
    name = models.CharField(max_length=100, help_text="Parameter name (used in queries)")
    label = models.CharField(max_length=255, help_text="Display label for UI")
    parameter_type = models.CharField(max_length=20, choices=PARAMETER_TYPES)
    description = models.TextField(blank=True)

    # Validation
    is_required = models.BooleanField(default=False)
    default_value = models.JSONField(null=True, blank=True)
    validation_rules = models.JSONField(
        help_text="Validation rules (min, max, pattern, etc.)", default=dict
    )

    # Options for SELECT/MULTISELECT
    options = models.JSONField(
        help_text="Options for select parameters [{value, label}]", default=list
    )

    # UI Configuration
    sort_order = models.IntegerField(default=0)
    group_name = models.CharField(max_length=100, blank=True, help_text="Group parameters in UI")
    help_text = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "reporting_parameters"
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["report", "name"], name="unique_parameter_name_per_report"
            )
        ]

    def __str__(self):
        return f"{self.report.name} - {self.label}"

    def validate_value(self, value: Any) -> bool:  # noqa: C901
        """Validate a parameter value against the rules."""
        if self.is_required and (value is None or value == ""):
            return False

        if value is None or value == "":
            return True  # Optional parameter

        # Type-specific validation
        if self.parameter_type == "NUMBER":
            try:
                float(value)
            except (ValueError, TypeError):
                return False

        elif self.parameter_type == "DATE":
            try:
                if isinstance(value, str):
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return False

        elif self.parameter_type in ["SELECT", "MULTISELECT"]:
            valid_values = [opt["value"] for opt in self.options]
            if self.parameter_type == "SELECT":
                return value in valid_values
            else:  # MULTISELECT
                return all(v in valid_values for v in value)

        # Additional validation rules
        rules = self.validation_rules or {}

        if "min_length" in rules and len(str(value)) < rules["min_length"]:
            return False

        if "max_length" in rules and len(str(value)) > rules["max_length"]:
            return False

        if "min_value" in rules and float(value) < rules["min_value"]:
            return False

        if "max_value" in rules and float(value) > rules["max_value"]:
            return False

        return True
