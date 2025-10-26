"""
Forms for backup management interface.

This module provides forms for:
- Manual backup triggers
- Restore operations
- Backup configuration
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models import Tenant

from .models import Backup, BackupRestoreLog


class ManualBackupForm(forms.Form):
    """
    Form for triggering manual backups with flexible options.

    Supports:
    - Specific tenant(s)
    - Multiple tenants
    - All tenants
    - Immediate or scheduled execution
    """

    BACKUP_SCOPE_CHOICES = [
        ("all", "All Tenants"),
        ("specific", "Specific Tenant(s)"),
        ("multiple", "Multiple Tenants"),
    ]

    EXECUTION_TIMING_CHOICES = [
        ("immediate", "Execute Immediately"),
        ("scheduled", "Schedule for Later"),
    ]

    # Backup scope
    backup_scope = forms.ChoiceField(
        choices=BACKUP_SCOPE_CHOICES,
        widget=forms.RadioSelect,
        initial="all",
        help_text="Select which tenants to backup",
    )

    # Tenant selection (for specific/multiple)
    tenants = forms.ModelMultipleChoiceField(
        queryset=Tenant.objects.filter(status=Tenant.ACTIVE).order_by("company_name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select one or more tenants to backup",
    )

    # Execution timing
    execution_timing = forms.ChoiceField(
        choices=EXECUTION_TIMING_CHOICES,
        widget=forms.RadioSelect,
        initial="immediate",
        help_text="When to execute the backup",
    )

    # Scheduled time (for scheduled execution)
    scheduled_time = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        help_text="When to execute the backup (leave empty for immediate execution)",
    )

    # Additional options
    include_configuration = forms.BooleanField(
        required=False,
        initial=False,
        help_text="Include configuration files in the backup",
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Optional notes about this backup",
    )

    def clean(self):
        """Validate form data."""
        cleaned_data = super().clean()
        backup_scope = cleaned_data.get("backup_scope")
        tenants = cleaned_data.get("tenants")
        execution_timing = cleaned_data.get("execution_timing")
        scheduled_time = cleaned_data.get("scheduled_time")

        # Validate tenant selection
        if backup_scope in ["specific", "multiple"] and not tenants:
            raise ValidationError(
                {"tenants": "Please select at least one tenant for this backup scope."}
            )

        # Validate scheduled time
        if execution_timing == "scheduled":
            if not scheduled_time:
                raise ValidationError(
                    {"scheduled_time": "Please specify when to execute the backup."}
                )
            if scheduled_time <= timezone.now():
                raise ValidationError({"scheduled_time": "Scheduled time must be in the future."})

        return cleaned_data


class RestoreBackupForm(forms.Form):
    """
    Form for restoring backups with flexible options.

    Supports:
    - Full restore (replace all data)
    - Merge restore (preserve existing data)
    - Selective restore (specific tenants only)
    """

    RESTORE_MODE_CHOICES = [
        (BackupRestoreLog.FULL, "Full Restore - Replace all data (DESTRUCTIVE)"),
        (BackupRestoreLog.MERGE, "Merge Restore - Preserve existing data"),
        (BackupRestoreLog.PITR, "Point-in-Time Recovery - Restore to specific timestamp"),
    ]

    # Backup selection
    backup = forms.ModelChoiceField(
        queryset=Backup.objects.filter(status__in=[Backup.COMPLETED, Backup.VERIFIED]).order_by(
            "-created_at"
        ),
        help_text="Select the backup to restore",
    )

    # Restore mode
    restore_mode = forms.ChoiceField(
        choices=RESTORE_MODE_CHOICES,
        widget=forms.RadioSelect,
        initial=BackupRestoreLog.MERGE,
        help_text="How to restore the backup",
    )

    # Selective restore options
    selective_restore = forms.BooleanField(
        required=False,
        initial=False,
        help_text="Restore only specific tenants (for tenant backups)",
    )

    tenant_ids = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select tenants to restore (only for selective restore)",
    )

    # Point-in-time recovery
    target_timestamp = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        help_text="Target timestamp for point-in-time recovery",
    )

    # Justification
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Reason for this restore operation (required for audit trail)",
    )

    # Confirmation
    confirm_restore = forms.BooleanField(
        required=True,
        help_text="I understand this operation may affect production data",
    )

    def __init__(self, *args, **kwargs):
        """Initialize form with dynamic tenant choices."""
        super().__init__(*args, **kwargs)

        # Populate tenant_ids choices dynamically
        tenants = Tenant.objects.filter(status=Tenant.ACTIVE).order_by("company_name")
        self.fields["tenant_ids"].choices = [
            (str(tenant.id), tenant.company_name) for tenant in tenants
        ]

    def clean(self):
        """Validate form data."""
        cleaned_data = super().clean()
        restore_mode = cleaned_data.get("restore_mode")
        selective_restore = cleaned_data.get("selective_restore")
        tenant_ids = cleaned_data.get("tenant_ids")
        target_timestamp = cleaned_data.get("target_timestamp")
        backup = cleaned_data.get("backup")

        # Validate selective restore
        if selective_restore and not tenant_ids:
            raise ValidationError(
                {"tenant_ids": "Please select at least one tenant for selective restore."}
            )

        # Validate PITR
        if restore_mode == BackupRestoreLog.PITR:
            if not target_timestamp:
                raise ValidationError(
                    {"target_timestamp": "Please specify target timestamp for PITR."}
                )
            if backup and target_timestamp < backup.created_at:
                raise ValidationError(
                    {"target_timestamp": "Target timestamp cannot be before backup creation time."}
                )

        # Validate selective restore is only for tenant backups
        if selective_restore and backup and backup.backup_type != Backup.TENANT_BACKUP:
            raise ValidationError(
                {"selective_restore": "Selective restore is only available for tenant backups."}
            )

        return cleaned_data


class BackupFilterForm(forms.Form):
    """Form for filtering backup list."""

    backup_type = forms.ChoiceField(
        choices=[("", "All Types")] + Backup.BACKUP_TYPE_CHOICES,
        required=False,
        help_text="Filter by backup type",
    )

    status = forms.ChoiceField(
        choices=[("", "All Statuses")] + Backup.STATUS_CHOICES,
        required=False,
        help_text="Filter by status",
    )

    tenant = forms.ModelChoiceField(
        queryset=Tenant.objects.filter(status=Tenant.ACTIVE).order_by("company_name"),
        required=False,
        empty_label="All Tenants",
        help_text="Filter by tenant",
    )

    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="From date",
    )

    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="To date",
    )
