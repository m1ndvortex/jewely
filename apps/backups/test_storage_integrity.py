"""
Tests for storage integrity verification task.

This module tests the hourly storage integrity verification task that checks
checksums across all storage locations (local, R2, B2) and alerts on mismatches.
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

import pytest

from apps.backups.models import Backup, BackupAlert
from apps.backups.tasks import verify_storage_integrity
from apps.core.models import Tenant


@pytest.mark.django_db
class TestStorageIntegrityVerification(TestCase):
    """
    Test storage integrity verification task.

    Requirement 6.31: Verify storage integrity hourly by checking checksums
    """

    def setUp(self):
        """Set up test data."""
        # Create a test tenant
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        # Create test backups
        self.backup1 = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename="backup_full_database_20250126_120000.dump.gz.enc",
            size_bytes=1024 * 1024 * 100,  # 100 MB
            checksum="abc123def456",
            local_path="backup_full_database_20250126_120000.dump.gz.enc",
            r2_path="backup_full_database_20250126_120000.dump.gz.enc",
            b2_path="backup_full_database_20250126_120000.dump.gz.enc",
            status=Backup.COMPLETED,
        )

        self.backup2 = Backup.objects.create(
            backup_type=Backup.TENANT_BACKUP,
            tenant=self.tenant,
            filename="backup_tenant_backup_tenant1_20250126_120000.dump.gz.enc",
            size_bytes=1024 * 1024 * 50,  # 50 MB
            checksum="xyz789uvw012",
            local_path="backup_tenant_backup_tenant1_20250126_120000.dump.gz.enc",
            r2_path="backup_tenant_backup_tenant1_20250126_120000.dump.gz.enc",
            b2_path="backup_tenant_backup_tenant1_20250126_120000.dump.gz.enc",
            status=Backup.VERIFIED,
        )

        # Create an old backup (should not be checked) - set created_at explicitly
        from django.utils import timezone as django_timezone

        old_date = django_timezone.now() - timedelta(days=60)
        self.old_backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename="backup_full_database_20240101_120000.dump.gz.enc",
            size_bytes=1024 * 1024 * 100,
            checksum="old123backup",
            local_path="backup_full_database_20240101_120000.dump.gz.enc",
            r2_path="backup_full_database_20240101_120000.dump.gz.enc",
            b2_path="backup_full_database_20240101_120000.dump.gz.enc",
            status=Backup.COMPLETED,
        )
        # Manually update created_at to bypass auto_now_add
        Backup.objects.filter(id=self.old_backup.id).update(created_at=old_date)

    @patch("apps.backups.tasks.get_storage_backend")
    def test_verify_storage_integrity_all_pass(self, mock_get_storage):
        """
        Test storage integrity verification when all checks pass.

        Requirement 6.31: Verify storage integrity hourly
        """
        # Mock storage backends - use spec to avoid MagicMock serialization issues
        mock_local = MagicMock()
        mock_local.exists = MagicMock(return_value=True)
        mock_local.get_size = MagicMock(return_value=1024 * 1024 * 100)  # 100 MB

        mock_r2 = MagicMock()
        mock_r2.exists = MagicMock(return_value=True)
        mock_r2.get_size = MagicMock(return_value=1024 * 1024 * 100)

        mock_b2 = MagicMock()
        mock_b2.exists = MagicMock(return_value=True)
        mock_b2.get_size = MagicMock(return_value=1024 * 1024 * 100)

        def get_backend(backend_type):
            if backend_type == "local":
                return mock_local
            elif backend_type == "r2":
                return mock_r2
            elif backend_type == "b2":
                return mock_b2

        mock_get_storage.side_effect = get_backend

        # Run verification
        result = verify_storage_integrity()

        # Verify results
        assert result is not None
        assert result["total_backups_checked"] == 2  # Only recent backups
        assert result["verified_successfully"] == 2
        assert result["integrity_failures"] == 0
        assert result["missing_files"] == 0
        assert result["storage_mismatches"] == 0

        # Verify no alerts were created
        assert BackupAlert.objects.filter(alert_type=BackupAlert.INTEGRITY_FAILURE).count() == 0

        # Verify backup metadata was updated
        self.backup1.refresh_from_db()
        assert "last_integrity_check" in self.backup1.metadata
        assert self.backup1.metadata["last_integrity_check"]["status"] == "passed"

    @patch("apps.backups.tasks.get_storage_backend")
    def test_verify_storage_integrity_missing_file(self, mock_get_storage):
        """
        Test storage integrity verification when a file is missing.

        Requirement 6.31: Alert on mismatches
        """
        # Mock storage backends - R2 file is missing
        mock_local = MagicMock()
        mock_local.exists = MagicMock(return_value=True)
        mock_local.get_size = MagicMock(return_value=1024 * 1024 * 100)

        mock_r2 = MagicMock()
        mock_r2.exists = MagicMock(return_value=False)  # File missing in R2

        mock_b2 = MagicMock()
        mock_b2.exists = MagicMock(return_value=True)
        mock_b2.get_size = MagicMock(return_value=1024 * 1024 * 100)

        def get_backend(backend_type):
            if backend_type == "local":
                return mock_local
            elif backend_type == "r2":
                return mock_r2
            elif backend_type == "b2":
                return mock_b2

        mock_get_storage.side_effect = get_backend

        # Run verification
        result = verify_storage_integrity()

        # Verify results
        assert result is not None
        assert result["total_backups_checked"] == 2
        assert result["verified_successfully"] == 0  # All backups have R2 missing
        assert result["integrity_failures"] == 2
        assert result["missing_files"] == 2  # One missing file per backup

        # Verify alerts were created
        alerts = BackupAlert.objects.filter(alert_type=BackupAlert.INTEGRITY_FAILURE)
        assert alerts.count() >= 2  # At least one per backup + summary

        # Verify backup metadata was updated with failure
        self.backup1.refresh_from_db()
        assert "last_integrity_check" in self.backup1.metadata
        assert self.backup1.metadata["last_integrity_check"]["status"] == "failed"
        assert "file_not_found" in str(self.backup1.metadata["last_integrity_check"]["errors"])

    @patch("apps.backups.tasks.get_storage_backend")
    def test_verify_storage_integrity_size_mismatch(self, mock_get_storage):
        """
        Test storage integrity verification when file sizes don't match.

        Requirement 6.31: Alert on mismatches
        """
        # Mock storage backends - B2 has wrong size
        mock_local = MagicMock()
        mock_local.exists = MagicMock(return_value=True)
        mock_local.get_size = MagicMock(return_value=1024 * 1024 * 100)

        mock_r2 = MagicMock()
        mock_r2.exists = MagicMock(return_value=True)
        mock_r2.get_size = MagicMock(return_value=1024 * 1024 * 100)

        mock_b2 = MagicMock()
        mock_b2.exists = MagicMock(return_value=True)
        mock_b2.get_size = MagicMock(return_value=1024 * 1024 * 90)  # Wrong size

        def get_backend(backend_type):
            if backend_type == "local":
                return mock_local
            elif backend_type == "r2":
                return mock_r2
            elif backend_type == "b2":
                return mock_b2

        mock_get_storage.side_effect = get_backend

        # Run verification
        result = verify_storage_integrity()

        # Verify results
        assert result is not None
        assert result["integrity_failures"] == 2
        assert result["storage_mismatches"] == 2

        # Verify alerts were created
        alerts = BackupAlert.objects.filter(alert_type=BackupAlert.INTEGRITY_FAILURE)
        assert alerts.count() >= 2

    @patch("apps.backups.tasks.get_storage_backend")
    def test_verify_storage_integrity_wal_archive(self, mock_get_storage):
        """
        Test storage integrity verification for WAL archives (no local storage).

        WAL archives skip local storage and only use R2 and B2.
        """
        # Create a WAL archive backup
        wal_backup = Backup.objects.create(
            backup_type=Backup.WAL_ARCHIVE,
            filename="000000010000000000000001.gz",
            size_bytes=1024 * 1024 * 16,  # 16 MB
            checksum="wal123checksum",
            local_path="",  # WAL files skip local storage
            r2_path="wal/000000010000000000000001.gz",
            b2_path="wal/000000010000000000000001.gz",
            status=Backup.COMPLETED,
        )

        # Mock storage backends
        mock_local = MagicMock()

        mock_r2 = MagicMock()
        mock_r2.exists = MagicMock(return_value=True)
        mock_r2.get_size = MagicMock(return_value=1024 * 1024 * 16)

        mock_b2 = MagicMock()
        mock_b2.exists = MagicMock(return_value=True)
        mock_b2.get_size = MagicMock(return_value=1024 * 1024 * 16)

        def get_backend(backend_type):
            if backend_type == "local":
                return mock_local
            elif backend_type == "r2":
                return mock_r2
            elif backend_type == "b2":
                return mock_b2

        mock_get_storage.side_effect = get_backend

        # Run verification
        result = verify_storage_integrity()

        # Verify results - WAL backup should be verified successfully
        # even though local storage is not used
        assert result is not None
        assert result["verified_successfully"] >= 1

        # Verify local storage was not checked for WAL backup
        wal_backup.refresh_from_db()
        assert "last_integrity_check" in wal_backup.metadata
        assert wal_backup.metadata["last_integrity_check"]["status"] == "passed"

    @patch("apps.backups.tasks.get_storage_backend")
    def test_verify_storage_integrity_limits_backups(self, mock_get_storage):
        """
        Test that verification limits the number of backups checked per run.

        To avoid long-running tasks, verification should limit to 100 backups per hour.
        """
        # Create 150 backups
        for i in range(150):
            Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                filename=f"backup_{i}.dump.gz.enc",
                size_bytes=1024 * 1024,
                checksum=f"checksum_{i}",
                local_path=f"backup_{i}.dump.gz.enc",
                r2_path=f"backup_{i}.dump.gz.enc",
                b2_path=f"backup_{i}.dump.gz.enc",
                status=Backup.COMPLETED,
            )

        # Mock storage backends
        mock_local = MagicMock()
        mock_local.exists = MagicMock(return_value=True)
        mock_local.get_size = MagicMock(return_value=1024 * 1024)

        mock_r2 = MagicMock()
        mock_r2.exists = MagicMock(return_value=True)
        mock_r2.get_size = MagicMock(return_value=1024 * 1024)

        mock_b2 = MagicMock()
        mock_b2.exists = MagicMock(return_value=True)
        mock_b2.get_size = MagicMock(return_value=1024 * 1024)

        def get_backend(backend_type):
            if backend_type == "local":
                return mock_local
            elif backend_type == "r2":
                return mock_r2
            elif backend_type == "b2":
                return mock_b2

        mock_get_storage.side_effect = get_backend

        # Run verification
        result = verify_storage_integrity()

        # Verify that only 100 backups were checked (limit)
        assert result is not None
        assert result["total_backups_checked"] == 100

    @patch("apps.backups.tasks.get_storage_backend")
    def test_verify_storage_integrity_storage_error(self, mock_get_storage):
        """
        Test storage integrity verification when storage backend raises an error.

        Requirement 6.31: Alert on mismatches
        """
        # Mock storage backends - R2 raises an error
        mock_local = MagicMock()
        mock_local.exists = MagicMock(return_value=True)
        mock_local.get_size = MagicMock(return_value=1024 * 1024 * 100)

        mock_r2 = MagicMock()
        mock_r2.exists = MagicMock(side_effect=Exception("R2 connection error"))

        mock_b2 = MagicMock()
        mock_b2.exists = MagicMock(return_value=True)
        mock_b2.get_size = MagicMock(return_value=1024 * 1024 * 100)

        def get_backend(backend_type):
            if backend_type == "local":
                return mock_local
            elif backend_type == "r2":
                return mock_r2
            elif backend_type == "b2":
                return mock_b2

        mock_get_storage.side_effect = get_backend

        # Run verification
        result = verify_storage_integrity()

        # Verify results
        assert result is not None
        assert result["integrity_failures"] == 2  # Both backups fail R2 check

        # Verify alerts were created
        alerts = BackupAlert.objects.filter(alert_type=BackupAlert.INTEGRITY_FAILURE)
        assert alerts.count() >= 2

    @patch("apps.backups.tasks.get_storage_backend")
    def test_verify_storage_integrity_no_backups(self, mock_get_storage):
        """
        Test storage integrity verification when there are no backups to check.
        """
        # Delete all backups
        Backup.objects.all().delete()

        # Run verification
        result = verify_storage_integrity()

        # Verify results
        assert result is not None
        assert result["total_backups_checked"] == 0
        assert result["verified_successfully"] == 0
        assert result["integrity_failures"] == 0

    @patch("apps.backups.tasks.get_storage_backend")
    def test_verify_storage_integrity_only_old_backups(self, mock_get_storage):
        """
        Test that only backups from the last 30 days are verified.
        """
        # Delete recent backups, keep only old backup
        Backup.objects.filter(created_at__gte=timezone.now() - timedelta(days=30)).delete()

        # Run verification
        result = verify_storage_integrity()

        # Verify that no backups were checked (old backup is > 30 days)
        assert result is not None
        assert result["total_backups_checked"] == 0
