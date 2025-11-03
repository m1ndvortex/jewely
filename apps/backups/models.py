"""
Backup and disaster recovery models for the jewelry shop SaaS platform.

This module implements the enterprise-grade backup system with triple-redundant storage,
automated disaster recovery, and comprehensive tracking of all backup and restore operations.
"""

import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Backup(models.Model):
    """
    Track all backup operations with comprehensive metadata.

    Supports multiple backup types:
    - Full database backups (daily)
    - Tenant-specific backups (weekly)
    - WAL archives for PITR (every 5 minutes)
    - Configuration backups (daily)

    All backups are stored in three locations:
    - Local storage (30-day retention)
    - Cloudflare R2 (1-year retention)
    - Backblaze B2 (1-year retention)
    """

    # Backup type choices
    FULL_DATABASE = "FULL_DATABASE"
    TENANT_BACKUP = "TENANT_BACKUP"
    WAL_ARCHIVE = "WAL_ARCHIVE"
    CONFIGURATION = "CONFIGURATION"

    BACKUP_TYPE_CHOICES = [
        (FULL_DATABASE, "Full Database Backup"),
        (TENANT_BACKUP, "Tenant-Specific Backup"),
        (WAL_ARCHIVE, "WAL Archive for PITR"),
        (CONFIGURATION, "Configuration Backup"),
    ]

    # Status choices
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    VERIFIED = "VERIFIED"

    STATUS_CHOICES = [
        (IN_PROGRESS, "In Progress"),
        (COMPLETED, "Completed"),
        (FAILED, "Failed"),
        (VERIFIED, "Verified"),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the backup",
    )

    # Backup metadata
    backup_type = models.CharField(
        max_length=50,
        choices=BACKUP_TYPE_CHOICES,
        help_text="Type of backup operation",
    )

    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="backups",
        help_text="Tenant for tenant-specific backups (null for full database backups)",
    )

    filename = models.CharField(
        max_length=255,
        help_text="Name of the backup file",
    )

    size_bytes = models.BigIntegerField(
        help_text="Size of the backup file in bytes",
    )

    checksum = models.CharField(
        max_length=64,
        help_text="SHA-256 checksum for integrity verification",
    )

    # Storage paths
    local_path = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Path to backup file in local storage",
    )

    r2_path = models.CharField(
        max_length=500,
        help_text="Path to backup file in Cloudflare R2",
    )

    b2_path = models.CharField(
        max_length=500,
        help_text="Path to backup file in Backblaze B2",
    )

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=IN_PROGRESS,
        help_text="Current status of the backup operation",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the backup was initiated",
    )

    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the backup integrity was verified",
    )

    # Job tracking
    backup_job_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Celery task ID for the backup job",
    )

    # Performance metrics
    compression_ratio = models.FloatField(
        null=True,
        blank=True,
        help_text="Compression ratio achieved (e.g., 0.3 means 70% reduction)",
    )

    backup_duration_seconds = models.IntegerField(
        null=True,
        blank=True,
        help_text="Duration of the backup operation in seconds",
    )

    # Additional information
    notes = models.TextField(
        blank=True,
        help_text="Additional notes or comments about the backup",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_backups",
        help_text="User who initiated the backup (null for automated backups)",
    )

    # Metadata for advanced features
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (e.g., database version, table counts, etc.)",
    )

    class Meta:
        db_table = "backups_backup"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["backup_type", "-created_at"], name="backup_type_created_idx"),
            models.Index(fields=["tenant", "-created_at"], name="backup_tenant_created_idx"),
            models.Index(fields=["status"], name="backup_status_idx"),
            models.Index(fields=["created_at"], name="backup_created_idx"),
        ]
        verbose_name = "Backup"
        verbose_name_plural = "Backups"

    def __str__(self):
        tenant_info = f" - {self.tenant.company_name}" if self.tenant else ""
        return f"{self.get_backup_type_display()}{tenant_info} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    def is_completed(self):
        """Check if backup completed successfully."""
        return self.status in [self.COMPLETED, self.VERIFIED]

    def is_failed(self):
        """Check if backup failed."""
        return self.status == self.FAILED

    def get_size_mb(self):
        """Get backup size in megabytes."""
        return round(self.size_bytes / (1024 * 1024), 2)

    def get_size_gb(self):
        """Get backup size in gigabytes."""
        return round(self.size_bytes / (1024 * 1024 * 1024), 2)

    def get_average_speed_mbps(self):
        """Calculate average backup speed in MB/s."""
        if self.backup_duration_seconds and self.backup_duration_seconds > 0:
            return round(self.get_size_mb() / self.backup_duration_seconds, 2)
        return 0


class BackupRestoreLog(models.Model):
    """
    Track all restore operations for audit and troubleshooting.

    Records complete history of restore attempts including:
    - What was restored
    - Who initiated it
    - When it happened
    - Success/failure status
    - Performance metrics
    """

    # Restore mode choices
    FULL = "FULL"
    MERGE = "MERGE"
    PITR = "PITR"

    RESTORE_MODE_CHOICES = [
        (FULL, "Full Restore (Replace)"),
        (MERGE, "Merge Restore (Preserve)"),
        (PITR, "Point-in-Time Recovery"),
    ]

    # Status choices
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (IN_PROGRESS, "In Progress"),
        (COMPLETED, "Completed"),
        (FAILED, "Failed"),
        (CANCELLED, "Cancelled"),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the restore operation",
    )

    # Backup reference
    backup = models.ForeignKey(
        "Backup",
        on_delete=models.CASCADE,
        related_name="restore_logs",
        help_text="Backup that was restored",
    )

    # Restore metadata
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="initiated_restores",
        help_text="User who initiated the restore (null for automated DR)",
    )

    tenant_ids = models.JSONField(
        null=True,
        blank=True,
        help_text="List of tenant IDs to restore (for selective restore)",
    )

    restore_mode = models.CharField(
        max_length=20,
        choices=RESTORE_MODE_CHOICES,
        help_text="Type of restore operation",
    )

    target_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Target timestamp for PITR (Point-in-Time Recovery)",
    )

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=IN_PROGRESS,
        help_text="Current status of the restore operation",
    )

    # Timestamps
    started_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the restore was initiated",
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the restore completed",
    )

    # Error tracking
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Error message if restore failed",
    )

    # Performance metrics
    rows_restored = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Number of database rows restored",
    )

    duration_seconds = models.IntegerField(
        null=True,
        blank=True,
        help_text="Duration of the restore operation in seconds",
    )

    # Justification
    reason = models.TextField(
        help_text="Reason for the restore operation",
    )

    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the restore operation",
    )

    # Metadata for advanced features
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (e.g., tables restored, conflicts resolved, etc.)",
    )

    class Meta:
        db_table = "backups_restore_log"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["-started_at"], name="restore_started_idx"),
            models.Index(fields=["status"], name="restore_status_idx"),
            models.Index(fields=["backup", "-started_at"], name="restore_backup_started_idx"),
        ]
        verbose_name = "Backup Restore Log"
        verbose_name_plural = "Backup Restore Logs"

    def __str__(self):
        return f"{self.get_restore_mode_display()} - {self.started_at.strftime('%Y-%m-%d %H:%M')} - {self.status}"

    def is_completed(self):
        """Check if restore completed successfully."""
        return self.status == self.COMPLETED

    def is_failed(self):
        """Check if restore failed."""
        return self.status == self.FAILED

    def get_duration_minutes(self):
        """Get restore duration in minutes."""
        if self.duration_seconds:
            return round(self.duration_seconds / 60, 2)
        return None


class BackupAlert(models.Model):
    """
    Track backup-related alerts and notifications.

    Monitors backup health and sends alerts for:
    - Backup failures
    - Size deviations (>20% change)
    - Duration threshold violations
    - Storage capacity warnings (>80%)
    - Integrity verification failures
    """

    # Alert type choices
    BACKUP_FAILURE = "BACKUP_FAILURE"
    SIZE_DEVIATION = "SIZE_DEVIATION"
    DURATION_THRESHOLD = "DURATION_THRESHOLD"
    STORAGE_CAPACITY = "STORAGE_CAPACITY"
    INTEGRITY_FAILURE = "INTEGRITY_FAILURE"
    RESTORE_FAILURE = "RESTORE_FAILURE"

    ALERT_TYPE_CHOICES = [
        (BACKUP_FAILURE, "Backup Failure"),
        (SIZE_DEVIATION, "Size Deviation"),
        (DURATION_THRESHOLD, "Duration Threshold Exceeded"),
        (STORAGE_CAPACITY, "Storage Capacity Warning"),
        (INTEGRITY_FAILURE, "Integrity Verification Failure"),
        (RESTORE_FAILURE, "Restore Operation Failure"),
    ]

    # Severity choices
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    SEVERITY_CHOICES = [
        (INFO, "Info"),
        (WARNING, "Warning"),
        (ERROR, "Error"),
        (CRITICAL, "Critical"),
    ]

    # Status choices
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"

    STATUS_CHOICES = [
        (ACTIVE, "Active"),
        (ACKNOWLEDGED, "Acknowledged"),
        (RESOLVED, "Resolved"),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the alert",
    )

    # Alert metadata
    alert_type = models.CharField(
        max_length=50,
        choices=ALERT_TYPE_CHOICES,
        help_text="Type of alert",
    )

    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        help_text="Severity level of the alert",
    )

    # Related objects
    backup = models.ForeignKey(
        "Backup",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="alerts",
        help_text="Related backup (if applicable)",
    )

    restore_log = models.ForeignKey(
        "BackupRestoreLog",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="alerts",
        help_text="Related restore log (if applicable)",
    )

    # Alert content
    message = models.TextField(
        help_text="Alert message describing the issue",
    )

    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional details about the alert (e.g., metrics, thresholds, etc.)",
    )

    # Notification tracking
    notification_channels = models.JSONField(
        default=list,
        help_text="Channels where alert was sent (email, SMS, in-app, webhook)",
    )

    notification_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when notifications were sent",
    )

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=ACTIVE,
        help_text="Current status of the alert",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the alert was created",
    )

    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the alert was acknowledged",
    )

    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acknowledged_alerts",
        help_text="User who acknowledged the alert",
    )

    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the alert was resolved",
    )

    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_alerts",
        help_text="User who resolved the alert",
    )

    # Resolution notes
    resolution_notes = models.TextField(
        blank=True,
        help_text="Notes about how the alert was resolved",
    )

    class Meta:
        db_table = "backups_alert"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["alert_type", "-created_at"], name="alert_type_created_idx"),
            models.Index(fields=["severity", "status"], name="alert_severity_status_idx"),
            models.Index(fields=["status", "-created_at"], name="alert_status_created_idx"),
            models.Index(fields=["-created_at"], name="alert_created_idx"),
        ]
        verbose_name = "Backup Alert"
        verbose_name_plural = "Backup Alerts"

    def __str__(self):
        return f"{self.get_alert_type_display()} - {self.severity} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    def is_active(self):
        """Check if alert is still active."""
        return self.status == self.ACTIVE

    def is_critical(self):
        """Check if alert is critical severity."""
        return self.severity == self.CRITICAL

    def acknowledge(self, user):
        """Acknowledge the alert."""
        from django.utils import timezone

        self.status = self.ACKNOWLEDGED
        self.acknowledged_at = timezone.now()
        self.acknowledged_by = user
        self.save(update_fields=["status", "acknowledged_at", "acknowledged_by"])

    def resolve(self, user, notes=""):
        """Resolve the alert."""
        from django.utils import timezone

        self.status = self.RESOLVED
        self.resolved_at = timezone.now()
        self.resolved_by = user
        self.resolution_notes = notes
        self.save(update_fields=["status", "resolved_at", "resolved_by", "resolution_notes"])


class BackupConfiguration(models.Model):
    """
    Singleton model to store backup system configuration.
    Only one instance should exist in the database.
    """

    # WAL archiving interval in seconds
    wal_archiving_interval_seconds = models.IntegerField(
        default=3600,  # 1 hour default
        help_text="How often to run WAL archiving (in seconds). Minimum: 300 (5 min), Maximum: 86400 (24 hours)",
        validators=[
            MinValueValidator(300, message="Interval must be at least 5 minutes (300 seconds)"),
            MaxValueValidator(86400, message="Interval must not exceed 24 hours (86400 seconds)"),
        ],
    )

    # Audit fields
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="backup_config_modifications",
    )
    modified_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Backup Configuration"
        verbose_name_plural = "Backup Configuration"

    def __str__(self):
        minutes = self.wal_archiving_interval_seconds // 60
        return f"WAL Archiving: Every {minutes} minutes"

    def save(self, *args, **kwargs):
        """Enforce singleton pattern."""
        if not self.pk and BackupConfiguration.objects.exists():
            # If trying to create a new instance when one exists, update the existing one
            instance = BackupConfiguration.objects.first()
            instance.wal_archiving_interval_seconds = self.wal_archiving_interval_seconds
            instance.modified_by = self.modified_by
            instance.save()
            self.pk = instance.pk
        super().save(*args, **kwargs)

    @classmethod
    def get_config(cls):
        """Get the singleton configuration instance, create if doesn't exist."""
        config, created = cls.objects.get_or_create(pk=1)
        return config

    @property
    def wal_interval_display(self):
        """Human-readable interval display."""
        seconds = self.wal_archiving_interval_seconds
        if seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        else:
            hours = seconds // 3600
            remaining_mins = (seconds % 3600) // 60
            result = f"{hours} hour{'s' if hours != 1 else ''}"
            if remaining_mins:
                result += f" {remaining_mins} minute{'s' if remaining_mins != 1 else ''}"
            return result
