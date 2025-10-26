"""
Tests for backup monitoring and alerting functionality.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

import pytest

from apps.core.models import Tenant
from apps.core.tenant_context import bypass_rls

from .models import Backup, BackupAlert, BackupRestoreLog
from .monitoring import (
    check_backup_duration_threshold,
    check_backup_size_deviation,
    create_backup_alert_with_notifications,
    get_active_alerts,
    get_alert_summary,
    monitor_backup_completion,
    monitor_restore_completion,
)

User = get_user_model()


@pytest.mark.django_db
class TestBackupMonitoring(TestCase):
    """Test backup monitoring functionality."""

    def setUp(self):
        """Set up test data."""
        with bypass_rls():
            # Create platform admin user
            self.admin_user = User.objects.create_user(
                username="admin",
                email="admin@example.com",
                password="testpass123",
                role="PLATFORM_ADMIN",
            )

            # Create test tenant
            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop",
                slug="test-shop",
                status=Tenant.ACTIVE,
            )

    def test_create_backup_alert_with_notifications(self):
        """Test creating a backup alert with notifications."""
        with bypass_rls():
            # Create a test backup
            backup = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                filename="test_backup.dump.gz.enc",
                size_bytes=1024 * 1024 * 100,  # 100 MB
                checksum="abc123",
                local_path="/backups/test_backup.dump.gz.enc",
                r2_path="test_backup.dump.gz.enc",
                b2_path="test_backup.dump.gz.enc",
                status=Backup.FAILED,
            )

            # Create alert with notifications
            alert = create_backup_alert_with_notifications(
                alert_type=BackupAlert.BACKUP_FAILURE,
                severity=BackupAlert.CRITICAL,
                message="Test backup failed",
                backup=backup,
                details={"error": "Test error"},
            )

            # Verify alert was created
            self.assertIsNotNone(alert)
            self.assertEqual(alert.alert_type, BackupAlert.BACKUP_FAILURE)
            self.assertEqual(alert.severity, BackupAlert.CRITICAL)
            self.assertEqual(alert.message, "Test backup failed")
            self.assertEqual(alert.backup, backup)
            self.assertEqual(alert.status, BackupAlert.ACTIVE)

    def test_check_backup_size_deviation(self):
        """Test checking for backup size deviations."""
        with bypass_rls():
            # Create several backups with similar sizes
            for i in range(5):
                Backup.objects.create(
                    backup_type=Backup.FULL_DATABASE,
                    filename=f"backup_{i}.dump.gz.enc",
                    size_bytes=1024 * 1024 * 100,  # 100 MB
                    checksum=f"checksum_{i}",
                    local_path=f"/backups/backup_{i}.dump.gz.enc",
                    r2_path=f"backup_{i}.dump.gz.enc",
                    b2_path=f"backup_{i}.dump.gz.enc",
                    status=Backup.COMPLETED,
                    created_at=timezone.now() - timedelta(days=i),
                )

            # Create a backup with significantly different size (50% larger)
            large_backup = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                filename="large_backup.dump.gz.enc",
                size_bytes=1024 * 1024 * 150,  # 150 MB (50% larger)
                checksum="large_checksum",
                local_path="/backups/large_backup.dump.gz.enc",
                r2_path="large_backup.dump.gz.enc",
                b2_path="large_backup.dump.gz.enc",
                status=Backup.COMPLETED,
            )

            # Check for size deviation
            alert = check_backup_size_deviation(large_backup)

            # Verify alert was created
            self.assertIsNotNone(alert)
            self.assertEqual(alert.alert_type, BackupAlert.SIZE_DEVIATION)
            self.assertEqual(alert.backup, large_backup)
            self.assertIn("deviation", alert.message.lower())

    def test_check_backup_duration_threshold(self):
        """Test checking for backup duration thresholds."""
        with bypass_rls():
            # Create several backups with similar durations
            for i in range(5):
                Backup.objects.create(
                    backup_type=Backup.FULL_DATABASE,
                    filename=f"backup_{i}.dump.gz.enc",
                    size_bytes=1024 * 1024 * 100,
                    checksum=f"checksum_{i}",
                    local_path=f"/backups/backup_{i}.dump.gz.enc",
                    r2_path=f"backup_{i}.dump.gz.enc",
                    b2_path=f"backup_{i}.dump.gz.enc",
                    status=Backup.COMPLETED,
                    backup_duration_seconds=300,  # 5 minutes
                    created_at=timezone.now() - timedelta(days=i),
                )

            # Create a backup with significantly longer duration (100% longer)
            slow_backup = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                filename="slow_backup.dump.gz.enc",
                size_bytes=1024 * 1024 * 100,
                checksum="slow_checksum",
                local_path="/backups/slow_backup.dump.gz.enc",
                r2_path="slow_backup.dump.gz.enc",
                b2_path="slow_backup.dump.gz.enc",
                status=Backup.COMPLETED,
                backup_duration_seconds=600,  # 10 minutes (100% longer)
            )

            # Check for duration threshold
            alert = check_backup_duration_threshold(slow_backup)

            # Verify alert was created
            self.assertIsNotNone(alert)
            self.assertEqual(alert.alert_type, BackupAlert.DURATION_THRESHOLD)
            self.assertEqual(alert.backup, slow_backup)
            self.assertIn("duration", alert.message.lower())

    def test_monitor_backup_completion_failed(self):
        """Test monitoring a failed backup."""
        with bypass_rls():
            # Create a failed backup
            backup = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                filename="failed_backup.dump.gz.enc",
                size_bytes=0,
                checksum="",
                local_path="",
                r2_path="",
                b2_path="",
                status=Backup.FAILED,
                notes="Database connection failed",
            )

            # Monitor backup completion
            alerts = monitor_backup_completion(backup)

            # Verify alert was created for failure
            self.assertEqual(len(alerts), 1)
            self.assertEqual(alerts[0].alert_type, BackupAlert.BACKUP_FAILURE)
            self.assertEqual(alerts[0].severity, BackupAlert.CRITICAL)

    def test_monitor_restore_completion_failed(self):
        """Test monitoring a failed restore operation."""
        with bypass_rls():
            # Create a backup
            backup = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                filename="backup.dump.gz.enc",
                size_bytes=1024 * 1024 * 100,
                checksum="abc123",
                local_path="/backups/backup.dump.gz.enc",
                r2_path="backup.dump.gz.enc",
                b2_path="backup.dump.gz.enc",
                status=Backup.COMPLETED,
            )

            # Create a failed restore log
            restore_log = BackupRestoreLog.objects.create(
                backup=backup,
                initiated_by=self.admin_user,
                restore_mode=BackupRestoreLog.FULL,
                status=BackupRestoreLog.FAILED,
                error_message="Restore failed due to disk space",
                reason="Testing restore failure",
            )

            # Monitor restore completion
            alert = monitor_restore_completion(restore_log)

            # Verify alert was created
            self.assertIsNotNone(alert)
            self.assertEqual(alert.alert_type, BackupAlert.RESTORE_FAILURE)
            self.assertEqual(alert.severity, BackupAlert.CRITICAL)
            self.assertEqual(alert.restore_log, restore_log)

    def test_get_active_alerts(self):
        """Test getting active alerts."""
        with bypass_rls():
            # Create some alerts
            backup = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                filename="backup.dump.gz.enc",
                size_bytes=1024 * 1024 * 100,
                checksum="abc123",
                local_path="/backups/backup.dump.gz.enc",
                r2_path="backup.dump.gz.enc",
                b2_path="backup.dump.gz.enc",
                status=Backup.FAILED,
            )

            alert1 = BackupAlert.objects.create(
                alert_type=BackupAlert.BACKUP_FAILURE,
                severity=BackupAlert.CRITICAL,
                message="Backup failed",
                backup=backup,
                status=BackupAlert.ACTIVE,
            )

            alert2 = BackupAlert.objects.create(
                alert_type=BackupAlert.SIZE_DEVIATION,
                severity=BackupAlert.WARNING,
                message="Size deviation detected",
                backup=backup,
                status=BackupAlert.ACTIVE,
            )

            # Create a resolved alert (should not be included)
            BackupAlert.objects.create(
                alert_type=BackupAlert.STORAGE_CAPACITY,
                severity=BackupAlert.WARNING,
                message="Storage capacity warning",
                status=BackupAlert.RESOLVED,
            )

            # Get active alerts
            active_alerts = get_active_alerts()

            # Verify only active alerts are returned
            self.assertEqual(len(active_alerts), 2)
            alert_ids = [alert.id for alert in active_alerts]
            self.assertIn(alert1.id, alert_ids)
            self.assertIn(alert2.id, alert_ids)

    def test_get_alert_summary(self):
        """Test getting alert summary."""
        with bypass_rls():
            # Create some alerts
            backup = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                filename="backup.dump.gz.enc",
                size_bytes=1024 * 1024 * 100,
                checksum="abc123",
                local_path="/backups/backup.dump.gz.enc",
                r2_path="backup.dump.gz.enc",
                b2_path="backup.dump.gz.enc",
                status=Backup.FAILED,
            )

            BackupAlert.objects.create(
                alert_type=BackupAlert.BACKUP_FAILURE,
                severity=BackupAlert.CRITICAL,
                message="Backup failed",
                backup=backup,
                status=BackupAlert.ACTIVE,
            )

            BackupAlert.objects.create(
                alert_type=BackupAlert.SIZE_DEVIATION,
                severity=BackupAlert.WARNING,
                message="Size deviation",
                backup=backup,
                status=BackupAlert.ACTIVE,
            )

            BackupAlert.objects.create(
                alert_type=BackupAlert.STORAGE_CAPACITY,
                severity=BackupAlert.WARNING,
                message="Storage warning",
                status=BackupAlert.RESOLVED,
            )

            # Get alert summary
            summary = get_alert_summary()

            # Verify summary
            self.assertEqual(summary["total_alerts"], 3)
            self.assertEqual(summary["active_alerts"], 2)
            self.assertEqual(summary["critical_alerts"], 1)
            self.assertIn("alerts_by_type", summary)
            self.assertIn("recent_alerts_24h", summary)
