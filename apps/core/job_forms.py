"""
Forms for job management.

This module provides forms for:
- Manual job triggering
- Job scheduling configuration
- Job prioritization

Per Requirement 33 - Scheduled Job Management
"""

from django import forms
from django.core.exceptions import ValidationError

from celery import current_app


class ManualJobTriggerForm(forms.Form):
    """
    Form for manually triggering a job.

    Requirement 33.5: Allow administrators to manually trigger scheduled jobs.
    """

    AVAILABLE_JOBS = [
        ("apps.backups.tasks.perform_full_backup", "Full Database Backup"),
        ("apps.backups.tasks.perform_tenant_backup", "Tenant Backup"),
        ("apps.backups.tasks.archive_wal_files", "Archive WAL Files"),
        ("apps.backups.tasks.perform_configuration_backup", "Configuration Backup"),
        ("apps.backups.tasks.cleanup_old_backups", "Cleanup Old Backups"),
        ("apps.backups.tasks.verify_storage_integrity", "Verify Storage Integrity"),
        ("apps.pricing.tasks.fetch_gold_rates", "Fetch Gold Rates"),
        ("apps.reporting.tasks.generate_scheduled_report", "Generate Report"),
        ("apps.notifications.tasks.send_scheduled_notifications", "Send Notifications"),
        ("apps.core.data_tasks.export_tenant_data", "Export Tenant Data"),
    ]

    task_name = forms.ChoiceField(
        choices=AVAILABLE_JOBS,
        label="Job Type",
        help_text="Select the job to trigger",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    args = forms.CharField(
        required=False,
        label="Arguments (JSON array)",
        help_text='Example: ["arg1", "arg2"]',
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    kwargs = forms.CharField(
        required=False,
        label="Keyword Arguments (JSON object)",
        help_text='Example: {"key1": "value1", "key2": "value2"}',
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    queue = forms.ChoiceField(
        choices=[
            ("default", "Default"),
            ("high_priority", "High Priority"),
            ("low_priority", "Low Priority"),
            ("backups", "Backups"),
            ("reports", "Reports"),
        ],
        initial="default",
        label="Queue",
        help_text="Select the queue for this job",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    priority = forms.IntegerField(
        min_value=0,
        max_value=10,
        initial=5,
        label="Priority",
        help_text="Priority level (0-10, higher is more important)",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    countdown = forms.IntegerField(
        required=False,
        min_value=0,
        label="Countdown (seconds)",
        help_text="Delay before execution (optional)",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    def clean_args(self):
        """Validate and parse args JSON."""
        args = self.cleaned_data.get("args", "").strip()
        if not args:
            return []

        import json

        try:
            parsed = json.loads(args)
            if not isinstance(parsed, list):
                raise ValidationError("Arguments must be a JSON array")
            return parsed
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON: {e}")

    def clean_kwargs(self):
        """Validate and parse kwargs JSON."""
        kwargs = self.cleaned_data.get("kwargs", "").strip()
        if not kwargs:
            return {}

        import json

        try:
            parsed = json.loads(kwargs)
            if not isinstance(parsed, dict):
                raise ValidationError("Keyword arguments must be a JSON object")
            return parsed
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON: {e}")

    def clean_task_name(self):
        """Validate that the task exists in Celery."""
        task_name = self.cleaned_data.get("task_name")
        if task_name not in current_app.tasks:
            raise ValidationError(f"Task '{task_name}' not found in Celery registry")
        return task_name


class JobScheduleForm(forms.Form):
    """
    Form for configuring job schedules.

    Requirement 33.6: Allow administrators to configure job schedules.
    """

    SCHEDULE_TYPE_CHOICES = [
        ("cron", "Cron Expression"),
        ("interval", "Interval"),
    ]

    task_name = forms.ChoiceField(
        choices=ManualJobTriggerForm.AVAILABLE_JOBS,
        label="Job Type",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    schedule_type = forms.ChoiceField(
        choices=SCHEDULE_TYPE_CHOICES,
        initial="interval",
        label="Schedule Type",
        widget=forms.Select(attrs={"class": "form-select", "onchange": "toggleScheduleFields()"}),
    )

    # Cron fields
    cron_expression = forms.CharField(
        required=False,
        label="Cron Expression",
        help_text='Example: "0 2 * * *" (daily at 2:00 AM)',
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    # Interval fields
    interval_value = forms.IntegerField(
        required=False,
        min_value=1,
        label="Interval Value",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    interval_unit = forms.ChoiceField(
        required=False,
        choices=[
            ("seconds", "Seconds"),
            ("minutes", "Minutes"),
            ("hours", "Hours"),
            ("days", "Days"),
        ],
        label="Interval Unit",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    args = forms.CharField(
        required=False,
        label="Arguments (JSON array)",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )

    kwargs = forms.CharField(
        required=False,
        label="Keyword Arguments (JSON object)",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )

    queue = forms.ChoiceField(
        choices=[
            ("default", "Default"),
            ("high_priority", "High Priority"),
            ("low_priority", "Low Priority"),
            ("backups", "Backups"),
            ("reports", "Reports"),
        ],
        initial="default",
        label="Queue",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    priority = forms.IntegerField(
        min_value=0,
        max_value=10,
        initial=5,
        label="Priority",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    enabled = forms.BooleanField(
        required=False,
        initial=True,
        label="Enabled",
        help_text="Enable or disable this schedule",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def clean(self):
        """Validate schedule configuration."""
        cleaned_data = super().clean()
        schedule_type = cleaned_data.get("schedule_type")

        if schedule_type == "cron":
            cron_expression = cleaned_data.get("cron_expression")
            if not cron_expression:
                raise ValidationError({"cron_expression": "Cron expression is required"})

            # Validate cron expression
            try:
                from celery.schedules import crontab

                parts = cron_expression.split()
                if len(parts) != 5:
                    raise ValidationError(
                        {
                            "cron_expression": "Cron expression must have 5 parts: minute hour day month day_of_week"
                        }
                    )
                # Try to create crontab to validate
                crontab(
                    minute=parts[0],
                    hour=parts[1],
                    day_of_month=parts[2],
                    month_of_year=parts[3],
                    day_of_week=parts[4],
                )
            except Exception as e:
                raise ValidationError({"cron_expression": f"Invalid cron expression: {e}"})

        elif schedule_type == "interval":
            interval_value = cleaned_data.get("interval_value")
            interval_unit = cleaned_data.get("interval_unit")

            if not interval_value:
                raise ValidationError({"interval_value": "Interval value is required"})
            if not interval_unit:
                raise ValidationError({"interval_unit": "Interval unit is required"})

        return cleaned_data

    def clean_args(self):
        """Validate and parse args JSON."""
        args = self.cleaned_data.get("args", "").strip()
        if not args:
            return []

        import json

        try:
            parsed = json.loads(args)
            if not isinstance(parsed, list):
                raise ValidationError("Arguments must be a JSON array")
            return parsed
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON: {e}")

    def clean_kwargs(self):
        """Validate and parse kwargs JSON."""
        kwargs = self.cleaned_data.get("kwargs", "").strip()
        if not kwargs:
            return {}

        import json

        try:
            parsed = json.loads(kwargs)
            if not isinstance(parsed, dict):
                raise ValidationError("Keyword arguments must be a JSON object")
            return parsed
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON: {e}")


class JobPriorityForm(forms.Form):
    """
    Form for changing job priority.

    Requirement 33.7: Allow administrators to set job priorities.
    """

    priority = forms.IntegerField(
        min_value=0,
        max_value=10,
        label="Priority",
        help_text="Priority level (0-10, higher is more important)",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    queue = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Keep Current"),
            ("default", "Default"),
            ("high_priority", "High Priority"),
            ("low_priority", "Low Priority"),
            ("backups", "Backups"),
            ("reports", "Reports"),
        ],
        label="Queue",
        help_text="Optionally change the queue",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
