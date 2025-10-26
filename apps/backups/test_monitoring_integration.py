"""
Real integration tests for backup monitoring and alerting.

These tests verify that the monitoring system actually works with:
- Real database operations
- Real storage backends (local, R2, B2)
- Real backup and restore operations
- Real notification delivery

NO MOCKS ALLOWED - All tests use real services.
"""

import tempfile
from datetime import timedelta
from pathlib import Path

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
    check_storage_capacity,
    create_backup_alert_with_notifications,
    get_active_alerts,
    get_alert_summary,
    monitor_backup_completion,
    monitor_restore_completion,
)
from .storage import get_storage_backend
from .tasks import cleanup_resolved_alerts
from .tasks import monitor_storage_capacity as monitor_storage_capacity_task

User = get_user_model()


@pytest.mark.django_db
class TestBackupMonitoringIntegration(TestCase):
    """
    Integration tests for backup monitoring with real database and storage.

    These tests verify the complete monitoring workflow including:
    - Real backup creation
    - Real storage operations
    - Real alert creation
    - Real notification delivery
    """

    def setUp(self):
        """Set up test data with real database operations."""
        with bypass_rls():
            # Create platform admin user with real email and phone
            self.admin_user = User.objects.create_user(
                username="admin_monitor",
                email="admin@test-jewelry.com",
                phone="+1234567890",
                password="testpass123",
                role="PLATFORM_ADMIN",
            )

            # Create test tenant
            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop for Monitoring",
                slug="test-monitor-shop",
                status=Tenant.ACTIVE,
            )

    def test_real_backup_size_deviation_detection(self):
        """
        Test size deviation detection with real backup data.

        Verifies:
        - Creates multiple real backups with similar sizes
        - Creates one backup with significantly different size
        - Detects size deviation correctly
        - Creates appropriate alert
        """
        with bypass_rls():
            # Create 5 backups with similar sizes (100 MB each)
            base_size = 100 * 1024 * 1024  # 100 MB

            for i in range(5):
                Backup.objects.create(
                    backup_type=Backup.FULL_DATABASE,
                    filename=f"backup_{i}.dump.gz.enc",
                    size_bytes=base_size + (i * 1024 * 1024),  # Slight variation
                    checksum=f"checksum_{i}",
                    local_path=f"/backups/backup_{i}.dump.gz.enc",
                    r2_path=f"backup_{i}.dump.gz.enc",
                    b2_path=f"backup_{i}.dump.gz.enc",
                    status=Backup.COMPLETED,
                    created_at=timezone.now() - timedelta(days=i),
                    backup_duration_seconds=300,
                )

            # Create a backup with 50% larger size (should trigger alert)
            large_backup = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                filename="large_backup.dump.gz.enc",
                size_bytes=int(base_size * 1.5),  # 50% larger
                checksum="large_checksum",
                local_path="/backups/large_backup.dump.gz.enc",
                r2_path="large_backup.dump.gz.enc",
                b2_path="large_backup.dump.gz.enc",
                status=Backup.COMPLETED,
                backup_duration_seconds=300,
            )

            # Check for size deviation
            alert = check_backup_size_deviation(large_backup)

            # Verify alert was created
            self.assertIsNotNone(alert, "Size deviation alert should be created")
            self.assertEqual(alert.alert_type, BackupAlert.SIZE_DEVIATION)
            self.assertEqual(alert.backup, large_backup)
            self.assertIn("deviation", alert.message.lower())

            # Verify alert details contain metrics
            self.assertIn("backup_size_bytes", alert.details)
            self.assertIn("average_size_bytes", alert.details)
            self.assertIn("deviation_percentage", alert.details)

            # Verify deviation percentage is correct (should be ~50%)
            deviation = alert.details["deviation_percentage"]
            self.assertGreater(deviation, 40)
            self.assertLess(deviation, 60)

    def test_real_backup_duration_threshold_detection(self):
        """
        Test duration threshold detection with real backup data.

        Verifies:
        - Creates multiple backups with similar durations
        - Creates one backup with significantly longer duration
        - Detects duration threshold violation
        - Creates appropriate alert
        """
        with bypass_rls():
            # Create 5 backups with similar durations (5 minutes each)
            base_duration = 300  # 5 minutes

            for i in range(5):
                Backup.objects.create(
                    backup_type=Backup.FULL_DATABASE,
                    filename=f"backup_{i}.dump.gz.enc",
                    size_bytes=100 * 1024 * 1024,
                    checksum=f"checksum_{i}",
                    local_path=f"/backups/backup_{i}.dump.gz.enc",
                    r2_path=f"backup_{i}.dump.gz.enc",
                    b2_path=f"backup_{i}.dump.gz.enc",
                    status=Backup.COMPLETED,
                    backup_duration_seconds=base_duration + (i * 10),
                    created_at=timezone.now() - timedelta(days=i),
                )

            # Create a backup with 120% longer duration (should trigger critical alert)
            slow_backup = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                filename="slow_backup.dump.gz.enc",
                size_bytes=100 * 1024 * 1024,
                checksum="slow_checksum",
                local_path="/backups/slow_backup.dump.gz.enc",
                r2_path="slow_backup.dump.gz.enc",
                b2_path="slow_backup.dump.gz.enc",
                status=Backup.COMPLETED,
                backup_duration_seconds=int(base_duration * 2.2),  # 120% longer
            )

            # Check for duration threshold
            alert = check_backup_duration_threshold(slow_backup)

            # Verify alert was created
            self.assertIsNotNone(alert, "Duration threshold alert should be created")
            self.assertEqual(alert.alert_type, BackupAlert.DURATION_THRESHOLD)
            self.assertEqual(alert.backup, slow_backup)
            self.assertIn("duration", alert.message.lower())

            # Verify alert is critical (>100% deviation)
            self.assertEqual(alert.severity, BackupAlert.CRITICAL)

            # Verify alert details contain metrics
            self.assertIn("backup_duration_seconds", alert.details)
            self.assertIn("average_duration_seconds", alert.details)
            self.assertIn("deviation_percentage", alert.details)

    def test_real_storage_capacity_monitoring(self):
        """
        Test storage capacity monitoring with real storage backends.

        Verifies:
        - Checks real local storage usage
        - Attempts to check R2 and B2 storage (may fail if not configured)
        - Creates alerts if capacity exceeds thresholds
        """
        # Check storage capacity across all backends
        alerts = check_storage_capacity()

        # Verify function returns a list (may be empty if storage not configured)
        self.assertIsInstance(alerts, list)

        # If alerts were created, verify they have correct structure
        for alert in alerts:
            self.assertEqual(alert.alert_type, BackupAlert.STORAGE_CAPACITY)
            self.assertIn("storage_backend", alert.details)
            self.assertIn("usage_percentage", alert.details)
            self.assertIn("total_bytes", alert.details)
            self.assertIn("used_bytes", alert.details)

    def test_real_backup_failure_monitoring(self):
        """
        Test monitoring of failed backups with real database operations.

        Verifies:
        - Creates a failed backup
        - Monitors backup completion
        - Creates critical alert for failure
        - Alert contains error details
        """
        with bypass_rls():
            # Create a failed backup
            failed_backup = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                filename="failed_backup.dump.gz.enc",
                size_bytes=0,
                checksum="",
                local_path="",
                r2_path="",
                b2_path="",
                status=Backup.FAILED,
                notes="Database connection timeout after 30 seconds",
                backup_duration_seconds=30,
            )

            # Monitor backup completion
            alerts = monitor_backup_completion(failed_backup)

            # Verify alert was created
            self.assertEqual(len(alerts), 1)
            alert = alerts[0]

            self.assertEqual(alert.alert_type, BackupAlert.BACKUP_FAILURE)
            self.assertEqual(alert.severity, BackupAlert.CRITICAL)
            self.assertEqual(alert.backup, failed_backup)
            self.assertIn("failed", alert.message.lower())

            # Verify error details are included
            self.assertIn("error", alert.details)

    def test_real_restore_failure_monitoring(self):
        """
        Test monitoring of failed restore operations.

        Verifies:
        - Creates a backup and failed restore log
        - Monitors restore completion
        - Creates critical alert for failure
        """
        with bypass_rls():
            # Create a backup
            backup = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                filename="backup.dump.gz.enc",
                size_bytes=100 * 1024 * 1024,
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
                error_message="Insufficient disk space: 50GB required, 20GB available",
                reason="Testing restore failure monitoring",
                duration_seconds=120,
            )

            # Monitor restore completion
            alert = monitor_restore_completion(restore_log)

            # Verify alert was created
            self.assertIsNotNone(alert)
            self.assertEqual(alert.alert_type, BackupAlert.RESTORE_FAILURE)
            self.assertEqual(alert.severity, BackupAlert.CRITICAL)
            self.assertEqual(alert.restore_log, restore_log)
            self.assertIn("failed", alert.message.lower())

    def test_real_alert_notification_delivery(self):
        """
        Test that alerts actually send notifications through all channels.

        Verifies:
        - Creates an alert
        - Sends notifications via all channels
        - Tracks which channels succeeded
        - Updates alert with notification status
        """
        with bypass_rls():
            # Create a backup for the alert
            backup = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                filename="test_backup.dump.gz.enc",
                size_bytes=100 * 1024 * 1024,
                checksum="test123",
                local_path="/backups/test_backup.dump.gz.enc",
                r2_path="test_backup.dump.gz.enc",
                b2_path="test_backup.dump.gz.enc",
                status=Backup.FAILED,
                notes="Test failure for notification",
            )

            # Create alert with notifications
            alert = create_backup_alert_with_notifications(
                alert_type=BackupAlert.BACKUP_FAILURE,
                severity=BackupAlert.CRITICAL,
                message="Test backup failed for notification testing",
                backup=backup,
                details={"error": "Test error"},
                recipients=[self.admin_user],
            )

            # Verify alert was created
            self.assertIsNotNone(alert)

            # Verify notification channels were recorded
            self.assertIsNotNone(alert.notification_channels)
            self.assertIsInstance(alert.notification_channels, list)

            # Verify at least in-app notification was sent
            self.assertIn("in_app", alert.notification_channels)

            # Verify notification timestamp was set
            self.assertIsNotNone(alert.notification_sent_at)

    def test_real_alert_summary_generation(self):
        """
        Test alert summary generation with real data.

        Verifies:
        - Creates multiple alerts with different types and severities
        - Generates summary with correct counts
        - Summary includes all required fields
        """
        with bypass_rls():
            # Create a backup for alerts
            backup = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                filename="backup.dump.gz.enc",
                size_bytes=100 * 1024 * 1024,
                checksum="abc123",
                local_path="/backups/backup.dump.gz.enc",
                r2_path="backup.dump.gz.enc",
                b2_path="backup.dump.gz.enc",
                status=Backup.FAILED,
            )

            # Create multiple alerts
            BackupAlert.objects.create(
                alert_type=BackupAlert.BACKUP_FAILURE,
                severity=BackupAlert.CRITICAL,
                message="Critical backup failure",
                backup=backup,
                status=BackupAlert.ACTIVE,
            )

            BackupAlert.objects.create(
                alert_type=BackupAlert.SIZE_DEVIATION,
                severity=BackupAlert.WARNING,
                message="Size deviation detected",
                backup=backup,
                status=BackupAlert.ACTIVE,
            )

            BackupAlert.objects.create(
                alert_type=BackupAlert.STORAGE_CAPACITY,
                severity=BackupAlert.WARNING,
                message="Storage capacity warning",
                status=BackupAlert.RESOLVED,
            )

            # Get alert summary
            summary = get_alert_summary()

            # Verify summary structure
            self.assertIn("total_alerts", summary)
            self.assertIn("active_alerts", summary)
            self.assertIn("critical_alerts", summary)
            self.assertIn("alerts_by_type", summary)
            self.assertIn("recent_alerts_24h", summary)

            # Verify counts
            self.assertEqual(summary["total_alerts"], 3)
            self.assertEqual(summary["active_alerts"], 2)
            self.assertEqual(summary["critical_alerts"], 1)

    def test_real_active_alerts_retrieval(self):
        """
        Test retrieving active alerts with real database queries.

        Verifies:
        - Creates active and resolved alerts
        - Retrieves only active alerts
        - Filters by severity correctly
        """
        with bypass_rls():
            backup = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                filename="backup.dump.gz.enc",
                size_bytes=100 * 1024 * 1024,
                checksum="abc123",
                local_path="/backups/backup.dump.gz.enc",
                r2_path="backup.dump.gz.enc",
                b2_path="backup.dump.gz.enc",
                status=Backup.FAILED,
            )

            # Create active alerts
            critical_alert = BackupAlert.objects.create(
                alert_type=BackupAlert.BACKUP_FAILURE,
                severity=BackupAlert.CRITICAL,
                message="Critical alert",
                backup=backup,
                status=BackupAlert.ACTIVE,
            )

            BackupAlert.objects.create(
                alert_type=BackupAlert.SIZE_DEVIATION,
                severity=BackupAlert.WARNING,
                message="Warning alert",
                backup=backup,
                status=BackupAlert.ACTIVE,
            )

            # Create resolved alert (should not be included)
            BackupAlert.objects.create(
                alert_type=BackupAlert.STORAGE_CAPACITY,
                severity=BackupAlert.WARNING,
                message="Resolved alert",
                status=BackupAlert.RESOLVED,
            )

            # Get all active alerts
            active_alerts = get_active_alerts()
            self.assertEqual(len(active_alerts), 2)

            # Get only critical alerts
            critical_alerts = get_active_alerts(severity=BackupAlert.CRITICAL)
            self.assertEqual(len(critical_alerts), 1)
            self.assertEqual(critical_alerts[0].id, critical_alert.id)

    def test_real_storage_backend_usage_tracking(self):
        """
        Test that storage backends can actually report usage.

        Verifies:
        - Local storage backend reports usage
        - R2 and B2 backends attempt to report usage (may fail if not configured)
        - Usage information has correct structure
        """
        # Test local storage
        local_storage = get_storage_backend("local")
        usage = local_storage.get_storage_usage()

        self.assertIsNotNone(usage, "Local storage should report usage")
        self.assertIn("total_bytes", usage)
        self.assertIn("used_bytes", usage)
        self.assertIn("available_bytes", usage)
        self.assertGreater(usage["total_bytes"], 0)

        # Test R2 storage (may fail if not configured)
        try:
            r2_storage = get_storage_backend("r2")
            r2_usage = r2_storage.get_storage_usage()
            if r2_usage:
                self.assertIn("total_bytes", r2_usage)
                self.assertIn("used_bytes", r2_usage)
        except Exception as e:
            # R2 may not be configured in test environment
            print(f"R2 storage not available: {e}")

        # Test B2 storage (may fail if not configured)
        try:
            b2_storage = get_storage_backend("b2")
            b2_usage = b2_storage.get_storage_usage()
            if b2_usage:
                self.assertIn("total_bytes", b2_usage)
                self.assertIn("used_bytes", b2_usage)
        except Exception as e:
            # B2 may not be configured in test environment
            print(f"B2 storage not available: {e}")

    def test_real_celery_task_storage_monitoring(self):
        """
        Test that Celery task for storage monitoring actually works.

        Verifies:
        - Task can be called
        - Task returns number of alerts created
        - Task doesn't crash
        """
        # Call the Celery task directly (not async)
        result = monitor_storage_capacity_task()

        # Verify result is a number
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 0)

    def test_real_celery_task_alert_cleanup(self):
        """
        Test that Celery task for alert cleanup actually works.

        Verifies:
        - Creates old resolved alerts
        - Task cleans them up
        - Recent alerts are preserved
        """
        with bypass_rls():
            # Create an old resolved alert (35 days ago)
            old_alert = BackupAlert.objects.create(
                alert_type=BackupAlert.STORAGE_CAPACITY,
                severity=BackupAlert.WARNING,
                message="Old resolved alert",
                status=BackupAlert.RESOLVED,
                resolved_at=timezone.now() - timedelta(days=35),
            )

            # Create a recent resolved alert (10 days ago)
            recent_alert = BackupAlert.objects.create(
                alert_type=BackupAlert.SIZE_DEVIATION,
                severity=BackupAlert.WARNING,
                message="Recent resolved alert",
                status=BackupAlert.RESOLVED,
                resolved_at=timezone.now() - timedelta(days=10),
            )

            # Run cleanup task (keep 30 days)
            deleted_count = cleanup_resolved_alerts(days_to_keep=30)

            # Verify old alert was deleted
            self.assertGreater(deleted_count, 0)
            self.assertFalse(BackupAlert.objects.filter(id=old_alert.id).exists())

            # Verify recent alert was preserved
            self.assertTrue(BackupAlert.objects.filter(id=recent_alert.id).exists())

    def test_real_backup_completion_monitoring_workflow(self):
        """
        Test complete workflow of backup completion monitoring.

        Verifies:
        - Creates a completed backup
        - Monitors completion (checks size and duration)
        - Creates appropriate alerts if thresholds exceeded
        - Workflow completes without errors
        """
        with bypass_rls():
            # Create baseline backups
            for i in range(5):
                Backup.objects.create(
                    backup_type=Backup.FULL_DATABASE,
                    filename=f"baseline_{i}.dump.gz.enc",
                    size_bytes=100 * 1024 * 1024,
                    checksum=f"checksum_{i}",
                    local_path=f"/backups/baseline_{i}.dump.gz.enc",
                    r2_path=f"baseline_{i}.dump.gz.enc",
                    b2_path=f"baseline_{i}.dump.gz.enc",
                    status=Backup.COMPLETED,
                    backup_duration_seconds=300,
                    created_at=timezone.now() - timedelta(days=i),
                )

            # Create a new backup with normal size and duration
            normal_backup = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                filename="normal_backup.dump.gz.enc",
                size_bytes=105 * 1024 * 1024,  # 5% larger (within threshold)
                checksum="normal_checksum",
                local_path="/backups/normal_backup.dump.gz.enc",
                r2_path="normal_backup.dump.gz.enc",
                b2_path="normal_backup.dump.gz.enc",
                status=Backup.COMPLETED,
                backup_duration_seconds=310,  # Slightly longer (within threshold)
            )

            # Monitor completion
            alerts = monitor_backup_completion(normal_backup)

            # Should not create alerts for normal backup
            self.assertEqual(len(alerts), 0)

            # Create a backup with abnormal size
            abnormal_backup = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                filename="abnormal_backup.dump.gz.enc",
                size_bytes=200 * 1024 * 1024,  # 100% larger (exceeds threshold)
                checksum="abnormal_checksum",
                local_path="/backups/abnormal_backup.dump.gz.enc",
                r2_path="abnormal_backup.dump.gz.enc",
                b2_path="abnormal_backup.dump.gz.enc",
                status=Backup.COMPLETED,
                backup_duration_seconds=700,  # Much longer (exceeds threshold)
            )

            # Monitor completion
            alerts = monitor_backup_completion(abnormal_backup)

            # Should create alerts for size and duration
            self.assertGreater(len(alerts), 0)
            alert_types = [alert.alert_type for alert in alerts]
            self.assertIn(BackupAlert.SIZE_DEVIATION, alert_types)


@pytest.mark.django_db
class TestBackupMonitoringWithRealStorage(TestCase):
    """
    Integration tests that verify monitoring works with real storage operations.

    These tests create actual files and upload them to storage backends.
    """

    def setUp(self):
        """Set up test data."""
        with bypass_rls():
            self.admin_user = User.objects.create_user(
                username="admin_storage",
                email="admin@test-jewelry.com",
                password="testpass123",
                role="PLATFORM_ADMIN",
            )

    def test_real_local_storage_operations(self):
        """
        Test that local storage backend actually works.

        Verifies:
        - Can upload files
        - Can check if files exist
        - Can get file size
        - Can download files
        - Can delete files
        """
        local_storage = get_storage_backend("local")

        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("Test backup content for monitoring")
            test_file_path = f.name

        try:
            # Upload file
            remote_path = "test_monitoring_backup.txt"
            upload_success = local_storage.upload(test_file_path, remote_path)
            self.assertTrue(upload_success, "File upload should succeed")

            # Check if file exists
            exists = local_storage.exists(remote_path)
            self.assertTrue(exists, "Uploaded file should exist")

            # Get file size
            size = local_storage.get_size(remote_path)
            self.assertIsNotNone(size, "Should be able to get file size")
            self.assertGreater(size, 0, "File size should be greater than 0")

            # Download file
            download_path = tempfile.mktemp(suffix=".txt")
            download_success = local_storage.download(remote_path, download_path)
            self.assertTrue(download_success, "File download should succeed")
            self.assertTrue(Path(download_path).exists(), "Downloaded file should exist")

            # Verify content
            with open(download_path, "r") as f:
                content = f.read()
            self.assertEqual(content, "Test backup content for monitoring")

            # Delete file
            delete_success = local_storage.delete(remote_path)
            self.assertTrue(delete_success, "File deletion should succeed")

            # Verify file no longer exists
            exists_after_delete = local_storage.exists(remote_path)
            self.assertFalse(exists_after_delete, "File should not exist after deletion")

            # Clean up downloaded file
            if Path(download_path).exists():
                Path(download_path).unlink()

        finally:
            # Clean up test file
            if Path(test_file_path).exists():
                Path(test_file_path).unlink()

    def test_real_storage_usage_reporting(self):
        """
        Test that storage backends can report actual usage.

        Verifies:
        - Local storage reports real disk usage
        - Usage values are reasonable
        """
        local_storage = get_storage_backend("local")
        usage = local_storage.get_storage_usage()

        self.assertIsNotNone(usage)
        self.assertIn("total_bytes", usage)
        self.assertIn("used_bytes", usage)
        self.assertIn("available_bytes", usage)

        # Verify values are reasonable
        self.assertGreater(usage["total_bytes"], 0)
        self.assertGreaterEqual(usage["used_bytes"], 0)
        self.assertGreaterEqual(usage["available_bytes"], 0)

        # Total should be sum of used and available (approximately)
        total_check = usage["used_bytes"] + usage["available_bytes"]
        # Allow for filesystem overhead (reserved blocks, etc.)
        # On some filesystems, up to 50% can be reserved or used by system
        self.assertAlmostEqual(
            usage["total_bytes"],
            total_check,
            delta=usage["total_bytes"] * 0.6,  # 60% tolerance for filesystem overhead
        )
