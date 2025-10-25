"""
Data management models for export, import, and backup operations.

Implements Requirement 20: Settings and Configuration
- Data export functionality (CSV/Excel)
- Data import with validation
- Backup trigger interface
"""

import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()


class DataActivity(models.Model):
    """
    Track all data export, import, and backup activities.
    """

    ACTIVITY_TYPES = [
        ("EXPORT", "Data Export"),
        ("IMPORT", "Data Import"),
        ("BACKUP_TRIGGER", "Manual Backup Trigger"),
    ]

    DATA_TYPES = [
        ("inventory", "Inventory Items"),
        ("customers", "Customers"),
        ("sales", "Sales Records"),
        ("suppliers", "Suppliers"),
        ("settings", "Shop Settings"),
        ("all", "All Data"),
    ]

    FORMATS = [
        ("csv", "CSV"),
        ("excel", "Excel"),
        ("json", "JSON"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("IN_PROGRESS", "In Progress"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
        ("CANCELLED", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("Tenant", on_delete=models.CASCADE)
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    data_type = models.CharField(max_length=20, choices=DATA_TYPES)
    format = models.CharField(max_length=10, choices=FORMATS, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")

    # File information
    file_name = models.CharField(max_length=255, null=True, blank=True)
    file_path = models.CharField(max_length=500, null=True, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)  # Size in bytes

    # Processing information
    records_processed = models.IntegerField(null=True, blank=True)
    records_successful = models.IntegerField(null=True, blank=True)
    records_failed = models.IntegerField(null=True, blank=True)

    # Error information
    error_message = models.TextField(null=True, blank=True)
    error_details = models.JSONField(null=True, blank=True)

    # Metadata
    parameters = models.JSONField(null=True, blank=True)  # Store export/import parameters
    initiated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "core_data_activity"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "-created_at"]),
            models.Index(fields=["activity_type", "status"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return (
            f"{self.get_activity_type_display()} - {self.get_data_type_display()} ({self.status})"
        )

    @property
    def duration(self):
        """Calculate processing duration."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        elif self.started_at:
            return timezone.now() - self.started_at
        return None

    @property
    def success_rate(self):
        """Calculate success rate for import operations."""
        if self.records_processed and self.records_processed > 0:
            return (self.records_successful or 0) / self.records_processed * 100
        return None

    def mark_started(self):
        """Mark activity as started."""
        self.status = "IN_PROGRESS"
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at"])

    def mark_completed(self, records_processed=None, records_successful=None, records_failed=None):
        """Mark activity as completed."""
        self.status = "COMPLETED"
        self.completed_at = timezone.now()
        if records_processed is not None:
            self.records_processed = records_processed
        if records_successful is not None:
            self.records_successful = records_successful
        if records_failed is not None:
            self.records_failed = records_failed
        self.save(
            update_fields=[
                "status",
                "completed_at",
                "records_processed",
                "records_successful",
                "records_failed",
            ]
        )

    def mark_failed(self, error_message, error_details=None):
        """Mark activity as failed."""
        self.status = "FAILED"
        self.completed_at = timezone.now()
        self.error_message = error_message
        if error_details:
            self.error_details = error_details
        self.save(update_fields=["status", "completed_at", "error_message", "error_details"])


class DataExportTemplate(models.Model):
    """
    Store predefined export templates for different data types.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("Tenant", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    data_type = models.CharField(max_length=20, choices=DataActivity.DATA_TYPES)
    format = models.CharField(max_length=10, choices=DataActivity.FORMATS)

    # Template configuration
    fields = models.JSONField()  # List of fields to include
    filters = models.JSONField(null=True, blank=True)  # Default filters
    sort_order = models.JSONField(null=True, blank=True)  # Default sort order

    # Metadata
    is_default = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_data_export_template"
        unique_together = [["tenant", "name"]]
        indexes = [
            models.Index(fields=["tenant", "data_type"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_data_type_display()})"


class DataImportMapping(models.Model):
    """
    Store field mappings for data import operations.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("Tenant", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    data_type = models.CharField(max_length=20, choices=DataActivity.DATA_TYPES)

    # Mapping configuration
    field_mappings = models.JSONField()  # Map CSV columns to model fields
    validation_rules = models.JSONField(null=True, blank=True)  # Custom validation rules
    transformation_rules = models.JSONField(null=True, blank=True)  # Data transformation rules

    # Options
    skip_header_row = models.BooleanField(default=True)
    update_existing = models.BooleanField(default=False)
    create_missing_categories = models.BooleanField(default=False)

    # Metadata
    is_default = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_data_import_mapping"
        unique_together = [["tenant", "name"]]
        indexes = [
            models.Index(fields=["tenant", "data_type"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_data_type_display()})"


class BackupTrigger(models.Model):
    """
    Track manual backup trigger requests.
    """

    BACKUP_TYPES = [
        ("FULL", "Full Database Backup"),
        ("TENANT", "Tenant-Specific Backup"),
        ("INCREMENTAL", "Incremental Backup"),
    ]

    PRIORITY_CHOICES = [
        ("LOW", "Low Priority"),
        ("NORMAL", "Normal Priority"),
        ("HIGH", "High Priority"),
        ("URGENT", "Urgent"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("QUEUED", "Queued"),
        ("IN_PROGRESS", "In Progress"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
        ("CANCELLED", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("Tenant", on_delete=models.CASCADE, null=True, blank=True)
    backup_type = models.CharField(max_length=20, choices=BACKUP_TYPES)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="NORMAL")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")

    # Backup configuration
    include_media = models.BooleanField(default=True)
    compress_backup = models.BooleanField(default=True)
    encrypt_backup = models.BooleanField(default=True)

    # Scheduling
    scheduled_at = models.DateTimeField(null=True, blank=True)  # For delayed execution

    # Results
    backup_id = models.UUIDField(null=True, blank=True)  # Reference to created backup
    file_path = models.CharField(max_length=500, null=True, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)

    # Error information
    error_message = models.TextField(null=True, blank=True)

    # Metadata
    reason = models.TextField(null=True, blank=True)  # Why backup was triggered
    initiated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "core_backup_trigger"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["tenant", "-created_at"]),
            models.Index(fields=["scheduled_at"]),
        ]

    def __str__(self):
        return f"{self.get_backup_type_display()} - {self.status}"

    @property
    def duration(self):
        """Calculate backup duration."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        elif self.started_at:
            return timezone.now() - self.started_at
        return None

    def mark_queued(self):
        """Mark trigger as queued."""
        self.status = "QUEUED"
        self.save(update_fields=["status"])

    def mark_started(self):
        """Mark backup as started."""
        self.status = "IN_PROGRESS"
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at"])

    def mark_completed(self, backup_id=None, file_path=None, file_size=None):
        """Mark backup as completed."""
        self.status = "COMPLETED"
        self.completed_at = timezone.now()
        if backup_id:
            self.backup_id = backup_id
        if file_path:
            self.file_path = file_path
        if file_size:
            self.file_size = file_size
        self.save(update_fields=["status", "completed_at", "backup_id", "file_path", "file_size"])

    def mark_failed(self, error_message):
        """Mark backup as failed."""
        self.status = "FAILED"
        self.completed_at = timezone.now()
        self.error_message = error_message
        self.save(update_fields=["status", "completed_at", "error_message"])
