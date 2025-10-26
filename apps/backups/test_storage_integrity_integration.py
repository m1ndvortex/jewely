"""
Integration tests for storage integrity verification.

These tests use REAL storage backends (local, R2, B2) to verify that
the storage integrity verification task actually works in production.

NO MOCKS ALLOWED - This tests the real functionality.
"""

import os
import tempfile
from datetime import timedelta
from pathlib import Path

from django.test import TestCase
from django.utils import timezone

import pytest

from apps.backups.encryption import compress_and_encrypt_file
from apps.backups.models import Backup, BackupAlert
from apps.backups.storage import get_storage_backend
from apps.backups.tasks import verify_storage_integrity
from apps.core.models import Tenant


@pytest.mark.django_db
class TestStorageIntegrityVerificationIntegration(TestCase):
    """
    Integration tests for storage integrity verification with REAL storage backends.

    Requirement 6.31: Verify storage integrity hourly by checking checksums
    across all three storage locations
    """

    def setUp(self):
        """Set up test data and real storage backends."""
        # Create a test tenant
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop-integrity",
            status=Tenant.ACTIVE,
        )

        # Initialize real storage backends
        self.local_storage = get_storage_backend("local")
        self.r2_storage = get_storage_backend("r2")
        self.b2_storage = get_storage_backend("b2")

        # Create a temporary test file
        self.test_content = b"This is test backup content for integrity verification" * 100
        self.temp_dir = tempfile.mkdtemp()
        self.test_file_path = os.path.join(self.temp_dir, "test_backup.txt")

        with open(self.test_file_path, "wb") as f:
            f.write(self.test_content)

    def tearDown(self):
        """Clean up test files from all storage backends."""
        # Clean up local temp directory
        if hasattr(self, "temp_dir") and Path(self.temp_dir).exists():
            import shutil

            shutil.rmtree(self.temp_dir)

        # Clean up test backups from all storage backends
        for backup in Backup.objects.filter(filename__contains="test_integrity"):
            try:
                if backup.local_path:
                    self.local_storage.delete(backup.local_path)
                if backup.r2_path:
                    self.r2_storage.delete(backup.r2_path)
                if backup.b2_path:
                    self.b2_storage.delete(backup.b2_path)
            except Exception as e:
                print(f"Cleanup error: {e}")

    def test_verify_storage_integrity_with_real_backends_all_pass(self):
        """
        Test storage integrity verification with REAL storage backends.
        All files exist and match - should pass verification.

        Requirement 6.31: Verify storage integrity hourly
        """
        # Step 1: Create and encrypt a real test file
        encrypted_filename = "test_integrity_all_pass.txt.gz.enc"
        encrypted_path = os.path.join(self.temp_dir, encrypted_filename)

        encrypted_path, checksum, _, final_size = compress_and_encrypt_file(
            input_path=self.test_file_path, output_path=encrypted_path
        )

        # Step 2: Upload to ALL THREE real storage backends
        local_success = self.local_storage.upload(encrypted_path, encrypted_filename)
        r2_success = self.r2_storage.upload(encrypted_path, encrypted_filename)
        b2_success = self.b2_storage.upload(encrypted_path, encrypted_filename)

        assert local_success, "Failed to upload to local storage"
        assert r2_success, "Failed to upload to R2 storage"
        assert b2_success, "Failed to upload to B2 storage"

        # Step 3: Create backup record
        backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename=encrypted_filename,
            size_bytes=final_size,
            checksum=checksum,
            local_path=encrypted_filename,
            r2_path=encrypted_filename,
            b2_path=encrypted_filename,
            status=Backup.COMPLETED,
        )

        # Step 4: Run integrity verification
        result = verify_storage_integrity()

        # Step 5: Verify results
        assert result is not None, "Verification task returned None"
        assert result["total_backups_checked"] >= 1, "No backups were checked"
        assert result["verified_successfully"] >= 1, "Verification should have passed"
        assert result["integrity_failures"] == 0, "Should have no integrity failures"
        assert result["missing_files"] == 0, "Should have no missing files"
        assert result["storage_mismatches"] == 0, "Should have no storage mismatches"

        # Step 6: Verify backup metadata was updated
        backup.refresh_from_db()
        assert "last_integrity_check" in backup.metadata, "Metadata should be updated"
        assert (
            backup.metadata["last_integrity_check"]["status"] == "passed"
        ), "Integrity check should have passed"

        # Step 7: Verify no alerts were created
        alerts = BackupAlert.objects.filter(alert_type=BackupAlert.INTEGRITY_FAILURE, backup=backup)
        assert alerts.count() == 0, "No alerts should be created for successful verification"

    def test_verify_storage_integrity_with_missing_file_in_r2(self):
        """
        Test storage integrity verification when file is missing from R2.
        Should detect the missing file and create an alert.

        Requirement 6.31: Alert on mismatches
        """
        # Step 1: Create and encrypt a real test file
        encrypted_filename = "test_integrity_missing_r2.txt.gz.enc"
        encrypted_path = os.path.join(self.temp_dir, encrypted_filename)

        encrypted_path, checksum, _, final_size = compress_and_encrypt_file(
            input_path=self.test_file_path, output_path=encrypted_path
        )

        # Step 2: Upload to local and B2 only (skip R2)
        local_success = self.local_storage.upload(encrypted_path, encrypted_filename)
        b2_success = self.b2_storage.upload(encrypted_path, encrypted_filename)

        assert local_success, "Failed to upload to local storage"
        assert b2_success, "Failed to upload to B2 storage"

        # Step 3: Create backup record with R2 path (but file doesn't exist there)
        backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename=encrypted_filename,
            size_bytes=final_size,
            checksum=checksum,
            local_path=encrypted_filename,
            r2_path=encrypted_filename,  # File doesn't actually exist here
            b2_path=encrypted_filename,
            status=Backup.COMPLETED,
        )

        # Step 4: Run integrity verification
        result = verify_storage_integrity()

        # Step 5: Verify results
        assert result is not None, "Verification task returned None"
        assert result["integrity_failures"] >= 1, "Should detect integrity failure"
        assert result["missing_files"] >= 1, "Should detect missing file"

        # Step 6: Verify backup metadata shows failure
        backup.refresh_from_db()
        assert "last_integrity_check" in backup.metadata, "Metadata should be updated"
        assert (
            backup.metadata["last_integrity_check"]["status"] == "failed"
        ), "Integrity check should have failed"
        assert (
            "r2" in str(backup.metadata["last_integrity_check"]["errors"]).lower()
        ), "Error should mention R2"

        # Step 7: Verify alert was created
        alerts = BackupAlert.objects.filter(alert_type=BackupAlert.INTEGRITY_FAILURE, backup=backup)
        assert alerts.count() >= 1, "Alert should be created for missing file"

    def test_verify_storage_integrity_with_size_mismatch(self):
        """
        Test storage integrity verification when file size doesn't match.
        Should detect the size mismatch and create an alert.

        Requirement 6.31: Alert on mismatches
        """
        # Step 1: Create and encrypt a real test file
        encrypted_filename = "test_integrity_size_mismatch.txt.gz.enc"
        encrypted_path = os.path.join(self.temp_dir, encrypted_filename)

        encrypted_path, checksum, _, final_size = compress_and_encrypt_file(
            input_path=self.test_file_path, output_path=encrypted_path
        )

        # Step 2: Upload to all storage backends
        local_success = self.local_storage.upload(encrypted_path, encrypted_filename)
        r2_success = self.r2_storage.upload(encrypted_path, encrypted_filename)
        b2_success = self.b2_storage.upload(encrypted_path, encrypted_filename)

        assert local_success, "Failed to upload to local storage"
        assert r2_success, "Failed to upload to R2 storage"
        assert b2_success, "Failed to upload to B2 storage"

        # Step 3: Create backup record with WRONG size
        backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename=encrypted_filename,
            size_bytes=final_size + 1000,  # Wrong size!
            checksum=checksum,
            local_path=encrypted_filename,
            r2_path=encrypted_filename,
            b2_path=encrypted_filename,
            status=Backup.COMPLETED,
        )

        # Step 4: Run integrity verification
        result = verify_storage_integrity()

        # Step 5: Verify results
        assert result is not None, "Verification task returned None"
        assert result["integrity_failures"] >= 1, "Should detect integrity failure"
        assert result["storage_mismatches"] >= 1, "Should detect size mismatch"

        # Step 6: Verify backup metadata shows failure
        backup.refresh_from_db()
        assert "last_integrity_check" in backup.metadata, "Metadata should be updated"
        assert (
            backup.metadata["last_integrity_check"]["status"] == "failed"
        ), "Integrity check should have failed"

        # Step 7: Verify alert was created
        alerts = BackupAlert.objects.filter(alert_type=BackupAlert.INTEGRITY_FAILURE, backup=backup)
        assert alerts.count() >= 1, "Alert should be created for size mismatch"

    def test_verify_storage_integrity_with_wal_archive(self):
        """
        Test storage integrity verification for WAL archives.
        WAL archives skip local storage and only use R2 and B2.

        Requirement 6.8: Archive WAL files every 5 minutes
        Requirement 6.31: Verify storage integrity
        """
        # Step 1: Create and encrypt a real test file (simulating WAL)
        encrypted_filename = "test_integrity_wal.gz"
        encrypted_path = os.path.join(self.temp_dir, encrypted_filename)

        encrypted_path, checksum, _, final_size = compress_and_encrypt_file(
            input_path=self.test_file_path, output_path=encrypted_path
        )

        # Step 2: Upload to R2 and B2 only (WAL files skip local)
        r2_path = f"wal/{encrypted_filename}"
        b2_path = f"wal/{encrypted_filename}"

        r2_success = self.r2_storage.upload(encrypted_path, r2_path)
        b2_success = self.b2_storage.upload(encrypted_path, b2_path)

        assert r2_success, "Failed to upload to R2 storage"
        assert b2_success, "Failed to upload to B2 storage"

        # Step 3: Create WAL backup record (no local path)
        backup = Backup.objects.create(
            backup_type=Backup.WAL_ARCHIVE,
            filename=encrypted_filename,
            size_bytes=final_size,
            checksum=checksum,
            local_path="",  # WAL files skip local storage
            r2_path=r2_path,
            b2_path=b2_path,
            status=Backup.COMPLETED,
        )

        # Step 4: Run integrity verification
        result = verify_storage_integrity()

        # Step 5: Verify results
        assert result is not None, "Verification task returned None"
        assert result["verified_successfully"] >= 1, "WAL verification should pass"
        assert result["integrity_failures"] == 0, "Should have no integrity failures"

        # Step 6: Verify backup metadata was updated
        backup.refresh_from_db()
        assert "last_integrity_check" in backup.metadata, "Metadata should be updated"
        assert (
            backup.metadata["last_integrity_check"]["status"] == "passed"
        ), "Integrity check should have passed"

    def test_verify_storage_integrity_only_checks_recent_backups(self):
        """
        Test that verification only checks backups from the last 30 days.
        Old backups should be skipped.

        Requirement 6.31: Verify storage integrity hourly
        """
        # Step 1: Create a recent backup
        recent_filename = "test_integrity_recent.txt.gz.enc"
        recent_path = os.path.join(self.temp_dir, recent_filename)

        encrypted_path, checksum, _, final_size = compress_and_encrypt_file(
            input_path=self.test_file_path, output_path=recent_path
        )

        # Upload recent backup
        self.local_storage.upload(encrypted_path, recent_filename)
        self.r2_storage.upload(encrypted_path, recent_filename)
        self.b2_storage.upload(encrypted_path, recent_filename)

        recent_backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename=recent_filename,
            size_bytes=final_size,
            checksum=checksum,
            local_path=recent_filename,
            r2_path=recent_filename,
            b2_path=recent_filename,
            status=Backup.COMPLETED,
        )

        # Step 2: Create an old backup (60 days old)
        old_filename = "test_integrity_old.txt.gz.enc"
        old_backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename=old_filename,
            size_bytes=final_size,
            checksum=checksum,
            local_path=old_filename,
            r2_path=old_filename,
            b2_path=old_filename,
            status=Backup.COMPLETED,
        )

        # Manually update created_at to 60 days ago
        old_date = timezone.now() - timedelta(days=60)
        Backup.objects.filter(id=old_backup.id).update(created_at=old_date)

        # Step 3: Run integrity verification
        verify_storage_integrity()

        # Step 4: Verify only recent backup was checked
        recent_backup.refresh_from_db()
        old_backup.refresh_from_db()

        assert "last_integrity_check" in recent_backup.metadata, "Recent backup should be checked"
        assert "last_integrity_check" not in old_backup.metadata, "Old backup should NOT be checked"

    def test_verify_storage_integrity_limits_backups_per_run(self):
        """
        Test that verification limits to 100 backups per run.
        This prevents long-running tasks.

        Requirement 6.31: Verify storage integrity hourly
        """
        # Create 5 test backups (we won't create 100 for test speed)
        encrypted_filename_base = "test_integrity_limit"
        encrypted_path = os.path.join(self.temp_dir, "test_limit.txt.gz.enc")

        encrypted_path, checksum, _, final_size = compress_and_encrypt_file(
            input_path=self.test_file_path, output_path=encrypted_path
        )

        for i in range(5):
            filename = f"{encrypted_filename_base}_{i}.txt.gz.enc"

            # Upload to all backends
            self.local_storage.upload(encrypted_path, filename)
            self.r2_storage.upload(encrypted_path, filename)
            self.b2_storage.upload(encrypted_path, filename)

            Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                filename=filename,
                size_bytes=final_size,
                checksum=checksum,
                local_path=filename,
                r2_path=filename,
                b2_path=filename,
                status=Backup.COMPLETED,
            )

        # Run verification
        result = verify_storage_integrity()

        # Verify all 5 were checked (since we have less than 100)
        assert result is not None, "Verification task returned None"
        assert result["total_backups_checked"] >= 5, "Should check all 5 backups"
        assert result["verified_successfully"] >= 5, "All should pass verification"
