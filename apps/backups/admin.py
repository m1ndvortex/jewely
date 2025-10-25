"""
Admin interface for backup models.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import Backup, BackupAlert, BackupRestoreLog


@admin.register(Backup)
class BackupAdmin(admin.ModelAdmin):
    """Admin interface for Backup model."""

    list_display = [
        "id",
        "backup_type",
        "tenant_link",
        "filename",
        "size_display",
        "status_badge",
        "created_at",
        "backup_duration_seconds",
    ]
    list_filter = [
        "backup_type",
        "status",
        "created_at",
    ]
    search_fields = [
        "filename",
        "tenant__company_name",
        "checksum",
    ]
    readonly_fields = [
        "id",
        "created_at",
        "verified_at",
        "checksum",
        "size_bytes",
        "compression_ratio",
        "backup_duration_seconds",
    ]
    fieldsets = (
        (
            "Backup Information",
            {
                "fields": (
                    "id",
                    "backup_type",
                    "tenant",
                    "filename",
                    "status",
                )
            },
        ),
        (
            "Storage Locations",
            {
                "fields": (
                    "local_path",
                    "r2_path",
                    "b2_path",
                )
            },
        ),
        (
            "Integrity & Performance",
            {
                "fields": (
                    "size_bytes",
                    "checksum",
                    "compression_ratio",
                    "backup_duration_seconds",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "verified_at",
                )
            },
        ),
        (
            "Additional Information",
            {
                "fields": (
                    "backup_job_id",
                    "created_by",
                    "notes",
                    "metadata",
                )
            },
        ),
    )
    date_hierarchy = "created_at"
    ordering = ["-created_at"]

    def tenant_link(self, obj):
        """Display tenant as a link."""
        if obj.tenant:
            return format_html(
                '<a href="/admin/core/tenant/{}/change/">{}</a>',
                obj.tenant.id,
                obj.tenant.company_name,
            )
        return "-"

    tenant_link.short_description = "Tenant"

    def size_display(self, obj):
        """Display size in human-readable format."""
        if obj.size_bytes < 1024 * 1024:  # Less than 1 MB
            return f"{obj.size_bytes / 1024:.2f} KB"
        elif obj.size_bytes < 1024 * 1024 * 1024:  # Less than 1 GB
            return f"{obj.get_size_mb()} MB"
        else:
            return f"{obj.get_size_gb()} GB"

    size_display.short_description = "Size"

    def status_badge(self, obj):
        """Display status as a colored badge."""
        colors = {
            "IN_PROGRESS": "blue",
            "COMPLETED": "green",
            "FAILED": "red",
            "VERIFIED": "darkgreen",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"


@admin.register(BackupRestoreLog)
class BackupRestoreLogAdmin(admin.ModelAdmin):
    """Admin interface for BackupRestoreLog model."""

    list_display = [
        "id",
        "backup_link",
        "restore_mode",
        "status_badge",
        "initiated_by",
        "started_at",
        "duration_display",
    ]
    list_filter = [
        "restore_mode",
        "status",
        "started_at",
    ]
    search_fields = [
        "backup__filename",
        "initiated_by__username",
        "reason",
    ]
    readonly_fields = [
        "id",
        "started_at",
        "completed_at",
        "duration_seconds",
        "rows_restored",
    ]
    fieldsets = (
        (
            "Restore Information",
            {
                "fields": (
                    "id",
                    "backup",
                    "restore_mode",
                    "status",
                    "initiated_by",
                )
            },
        ),
        (
            "Restore Configuration",
            {
                "fields": (
                    "tenant_ids",
                    "target_timestamp",
                    "reason",
                )
            },
        ),
        (
            "Performance Metrics",
            {
                "fields": (
                    "rows_restored",
                    "duration_seconds",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "started_at",
                    "completed_at",
                )
            },
        ),
        (
            "Error Information",
            {"fields": ("error_message",)},
        ),
        (
            "Additional Information",
            {
                "fields": (
                    "notes",
                    "metadata",
                )
            },
        ),
    )
    date_hierarchy = "started_at"
    ordering = ["-started_at"]

    def backup_link(self, obj):
        """Display backup as a link."""
        return format_html(
            '<a href="/admin/backups/backup/{}/change/">{}</a>',
            obj.backup.id,
            obj.backup.filename,
        )

    backup_link.short_description = "Backup"

    def status_badge(self, obj):
        """Display status as a colored badge."""
        colors = {
            "IN_PROGRESS": "blue",
            "COMPLETED": "green",
            "FAILED": "red",
            "CANCELLED": "orange",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def duration_display(self, obj):
        """Display duration in human-readable format."""
        if obj.duration_seconds:
            minutes = obj.get_duration_minutes()
            if minutes < 1:
                return f"{obj.duration_seconds}s"
            elif minutes < 60:
                return f"{minutes}m"
            else:
                hours = minutes / 60
                return f"{hours:.1f}h"
        return "-"

    duration_display.short_description = "Duration"


@admin.register(BackupAlert)
class BackupAlertAdmin(admin.ModelAdmin):
    """Admin interface for BackupAlert model."""

    list_display = [
        "id",
        "alert_type",
        "severity_badge",
        "status_badge",
        "backup_link",
        "created_at",
        "acknowledged_by",
    ]
    list_filter = [
        "alert_type",
        "severity",
        "status",
        "created_at",
    ]
    search_fields = [
        "message",
        "backup__filename",
    ]
    readonly_fields = [
        "id",
        "created_at",
        "acknowledged_at",
        "resolved_at",
        "notification_sent_at",
    ]
    fieldsets = (
        (
            "Alert Information",
            {
                "fields": (
                    "id",
                    "alert_type",
                    "severity",
                    "status",
                    "message",
                )
            },
        ),
        (
            "Related Objects",
            {
                "fields": (
                    "backup",
                    "restore_log",
                )
            },
        ),
        (
            "Notification",
            {
                "fields": (
                    "notification_channels",
                    "notification_sent_at",
                )
            },
        ),
        (
            "Status Tracking",
            {
                "fields": (
                    "acknowledged_at",
                    "acknowledged_by",
                    "resolved_at",
                    "resolved_by",
                    "resolution_notes",
                )
            },
        ),
        (
            "Additional Information",
            {"fields": ("details",)},
        ),
    )
    date_hierarchy = "created_at"
    ordering = ["-created_at"]
    actions = ["acknowledge_alerts", "resolve_alerts"]

    def backup_link(self, obj):
        """Display backup as a link."""
        if obj.backup:
            return format_html(
                '<a href="/admin/backups/backup/{}/change/">{}</a>',
                obj.backup.id,
                obj.backup.filename,
            )
        return "-"

    backup_link.short_description = "Backup"

    def severity_badge(self, obj):
        """Display severity as a colored badge."""
        colors = {
            "INFO": "lightblue",
            "WARNING": "orange",
            "ERROR": "red",
            "CRITICAL": "darkred",
        }
        color = colors.get(obj.severity, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_severity_display(),
        )

    severity_badge.short_description = "Severity"

    def status_badge(self, obj):
        """Display status as a colored badge."""
        colors = {
            "ACTIVE": "red",
            "ACKNOWLEDGED": "orange",
            "RESOLVED": "green",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def acknowledge_alerts(self, request, queryset):
        """Bulk acknowledge alerts."""
        count = 0
        for alert in queryset.filter(status=BackupAlert.ACTIVE):
            alert.acknowledge(request.user)
            count += 1
        self.message_user(request, f"{count} alert(s) acknowledged.")

    acknowledge_alerts.short_description = "Acknowledge selected alerts"

    def resolve_alerts(self, request, queryset):
        """Bulk resolve alerts."""
        count = 0
        for alert in queryset.filter(status__in=[BackupAlert.ACTIVE, BackupAlert.ACKNOWLEDGED]):
            alert.resolve(request.user, notes="Bulk resolved from admin")
            count += 1
        self.message_user(request, f"{count} alert(s) resolved.")

    resolve_alerts.short_description = "Resolve selected alerts"
