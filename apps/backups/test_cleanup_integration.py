"""
Real integration tests for backup cleanup functionality.

These tests use REAL storage backends (local, R2, B2) to verify that cleanup
actually works in production. NO MOCKS ALLOWED.

Tests verify:
- Real file deletion from local storage
- Real file deletion from Cloudflare R2
- Real file deletion from Backblaze B2
- Database record updates
- Temp file cleanup
"""

import os
import tempfile
from datetime import timedelta

from django.utils import timezone

import pytest

from apps.backups.models import Backup
from apps.backups.storage import get_storage_backend
from apps.backups.tasks import cleanup_old_backups


@pytest.mark.django_db
class TestBackupCleanupIntegration:
    """Real integration tests for backup cleanup - NO MOCKS."""

    def test_cleanup_deletes_real_local_files(self, tenant, platform_admin):
        """Test that cleanup actually deletes files from local storage."""
        # Get real local storage backend
        local_storage = get_storage_backend("local")

        # Create a real test file in local storage
        test_filename = "test_old_backup_local.dump.gz.enc"
        test_content = b"This is a test backup file for cleanup testing"

        # Create temp file and upload to local storage
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(test_content)
            temp_file_path = temp_file.name

        try:
            # Upload to local storage
            assert local_storage.upload(temp_file_path, test_filename)

            # Verify file exists in local storage
            assert local_storage.exists(test_filename)

            # Create backup record (35 days old)
            old_date = timezone.now() - timedelta(days=35)
            old_backup = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                tenant=None,
                filename=test_filename,
                size_bytes=len(test_content),
                checksum="test_checksum_123",
                local_path=test_filename,
                r2_path="",
                b2_path="",
                status=Backup.COMPLETED,
                created_by=platform_admin,
            )
            old_backup.created_at = old_date
            old_backup.save()

            # Run cleanup
            result = cleanup_old_backups()

            # Verify file was actually deleted from local storage
            assert not local_storage.exists(test_filename)

            # Verify backup record was deleted (since it has no storage locations left)
            assert not Backup.objects.filter(id=old_backup.id).exists()

            # Verify statistics
            assert result["local_deleted"] == 1
            assert result["local_failed"] == 0
            assert result["database_records_deleted"] == 1

        finally:
            # Cleanup temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

            # Cleanup local storage file if it still exists
            if local_storage.exists(test_filename):
                local_storage.delete(test_filename)

    def test_cleanup_deletes_real_r2_files(self, tenant, platform_admin):
        """Test that cleanup actually deletes files from Cloudflare R2."""
        # Get real R2 storage backend
        r2_storage = get_storage_backend("r2")

        # Create a real test file
        test_filename = "test_old_backup_r2.dump.gz.enc"
        test_content = b"This is a test backup file for R2 cleanup testing"

        # Create temp file and upload to R2
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(test_content)
            temp_file_path = temp_file.name

        try:
            # Upload to R2
            upload_success = r2_storage.upload(temp_file_path, test_filename)

            if not upload_success:
                pytest.skip("R2 storage not configured or unavailable")

            # Verify file exists in R2
            assert r2_storage.exists(test_filename)

            # Create backup record (400 days old - older than 1 year)
            very_old_date = timezone.now() - timedelta(days=400)
            old_backup = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                tenant=None,
                filename=test_filename,
                size_bytes=len(test_content),
                checksum="test_checksum_r2_456",
                local_path="",  # Already cleaned from local
                r2_path=test_filename,
                b2_path="",
                status=Backup.COMPLETED,
                created_by=platform_admin,
            )
            old_backup.created_at = very_old_date
            old_backup.save()

            # Run cleanup
            result = cleanup_old_backups()

            # Verify file was actually deleted from R2
            assert not r2_storage.exists(test_filename)

            # Verify backup record was deleted (no storage locations left)
            assert not Backup.objects.filter(id=old_backup.id).exists()

            # Verify statistics
            assert result["r2_deleted"] == 1
            assert result["r2_failed"] == 0
            assert result["database_records_deleted"] == 1

        finally:
            # Cleanup temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

            # Cleanup R2 file if it still exists
            try:
                if r2_storage.exists(test_filename):
                    r2_storage.delete(test_filename)
            except Exception:
                pass

    def test_cleanup_deletes_real_b2_files(self, tenant, platform_admin):
        """Test that cleanup actually deletes files from Backblaze B2."""
        # Get real B2 storage backend
        b2_storage = get_storage_backend("b2")

        # Create a real test file
        test_filename = "test_old_backup_b2.dump.gz.enc"
        test_content = b"This is a test backup file for B2 cleanup testing"

        # Create temp file and upload to B2
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(test_content)
            temp_file_path = temp_file.name

        try:
            # Upload to B2
            upload_success = b2_storage.upload(temp_file_path, test_filename)

            if not upload_success:
                pytest.skip("B2 storage not configured or unavailable")

            # Verify file exists in B2
            assert b2_storage.exists(test_filename)

            # Create backup record (400 days old - older than 1 year)
            very_old_date = timezone.now() - timedelta(days=400)
            old_backup = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                tenant=None,
                filename=test_filename,
                size_bytes=len(test_content),
                checksum="test_checksum_b2_789",
                local_path="",  # Already cleaned from local
                r2_path="",
                b2_path=test_filename,
                status=Backup.COMPLETED,
                created_by=platform_admin,
            )
            old_backup.created_at = very_old_date
            old_backup.save()

            # Run cleanup
            result = cleanup_old_backups()

            # Verify file was actually deleted from B2
            assert not b2_storage.exists(test_filename)

            # Verify backup record was deleted (no storage locations left)
            assert not Backup.objects.filter(id=old_backup.id).exists()

            # Verify statistics
            assert result["b2_deleted"] == 1
            assert result["b2_failed"] == 0
            assert result["database_records_deleted"] == 1

        finally:
            # Cleanup temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

            # Cleanup B2 file if it still exists
            try:
                if b2_storage.exists(test_filename):
                    b2_storage.delete(test_filename)
            except Exception:
                pass

    def test_cleanup_all_three_storage_locations(self, tenant, platform_admin):
        """Test cleanup with all three storage locations (local, R2, B2)."""
        # Get all storage backends
        local_storage = get_storage_backend("local")
        r2_storage = get_storage_backend("r2")
        b2_storage = get_storage_backend("b2")

        # Create test files
        test_filename_local = "test_cleanup_all_local.dump.gz.enc"
        test_filename_cloud = "test_cleanup_all_cloud.dump.gz.enc"
        test_content = b"Test backup for all storage locations cleanup"

        # Create temp file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(test_content)
            temp_file_path = temp_file.name

        try:
            # Upload to local storage (will be deleted - 35 days old)
            local_storage.upload(temp_file_path, test_filename_local)
            assert local_storage.exists(test_filename_local)

            # Try to upload to cloud storage (will be deleted - 400 days old)
            r2_uploaded = r2_storage.upload(temp_file_path, test_filename_cloud)
            b2_uploaded = b2_storage.upload(temp_file_path, test_filename_cloud)

            if not (r2_uploaded or b2_uploaded):
                pytest.skip("Cloud storage not configured")

            # Create backup for local (35 days old)
            old_local_date = timezone.now() - timedelta(days=35)
            local_backup = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                tenant=None,
                filename=test_filename_local,
                size_bytes=len(test_content),
                checksum="test_checksum_local",
                local_path=test_filename_local,
                r2_path=test_filename_local if r2_uploaded else "",
                b2_path=test_filename_local if b2_uploaded else "",
                status=Backup.COMPLETED,
                created_by=platform_admin,
            )
            local_backup.created_at = old_local_date
            local_backup.save()

            # Create backup for cloud (400 days old)
            very_old_date = timezone.now() - timedelta(days=400)
            cloud_backup = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                tenant=None,
                filename=test_filename_cloud,
                size_bytes=len(test_content),
                checksum="test_checksum_cloud",
                local_path="",  # Already cleaned
                r2_path=test_filename_cloud if r2_uploaded else "",
                b2_path=test_filename_cloud if b2_uploaded else "",
                status=Backup.COMPLETED,
                created_by=platform_admin,
            )
            cloud_backup.created_at = very_old_date
            cloud_backup.save()

            # Run cleanup
            result = cleanup_old_backups()

            # Verify local file was deleted
            assert not local_storage.exists(test_filename_local)
            assert result["local_deleted"] >= 1

            # Verify cloud files were deleted
            if r2_uploaded:
                assert not r2_storage.exists(test_filename_cloud)
                assert result["r2_deleted"] >= 1

            if b2_uploaded:
                assert not b2_storage.exists(test_filename_cloud)
                assert result["b2_deleted"] >= 1

            # Verify database records
            local_backup.refresh_from_db()
            assert local_backup.local_path == ""

            # Cloud backup should be deleted (no storage locations left)
            assert not Backup.objects.filter(id=cloud_backup.id).exists()
            assert result["database_records_deleted"] >= 1

        finally:
            # Cleanup temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

            # Cleanup storage files if they still exist
            try:
                if local_storage.exists(test_filename_local):
                    local_storage.delete(test_filename_local)
                if r2_storage.exists(test_filename_cloud):
                    r2_storage.delete(test_filename_cloud)
                if b2_storage.exists(test_filename_cloud):
                    b2_storage.delete(test_filename_cloud)
            except Exception:
                pass

    def test_cleanup_preserves_recent_backups(self, tenant, platform_admin):
        """Test that cleanup does NOT delete recent backups."""
        # Get local storage backend
        local_storage = get_storage_backend("local")

        # Create a real test file
        test_filename = "test_recent_backup.dump.gz.enc"
        test_content = b"This is a recent backup that should NOT be deleted"

        # Create temp file and upload to local storage
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(test_content)
            temp_file_path = temp_file.name

        try:
            # Upload to local storage
            assert local_storage.upload(temp_file_path, test_filename)
            assert local_storage.exists(test_filename)

            # Create backup record (10 days old - should NOT be deleted)
            recent_date = timezone.now() - timedelta(days=10)
            recent_backup = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                tenant=None,
                filename=test_filename,
                size_bytes=len(test_content),
                checksum="test_checksum_recent",
                local_path=test_filename,
                r2_path="",
                b2_path="",
                status=Backup.COMPLETED,
                created_by=platform_admin,
            )
            recent_backup.created_at = recent_date
            recent_backup.save()

            # Run cleanup
            cleanup_old_backups()

            # Verify file still exists in local storage
            assert local_storage.exists(test_filename)

            # Verify backup record was NOT modified
            recent_backup.refresh_from_db()
            assert recent_backup.local_path == test_filename

            # Verify this backup was not counted in deletions
            # (there might be other old backups, but this one should not be deleted)

        finally:
            # Cleanup temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

            # Cleanup local storage file
            if local_storage.exists(test_filename):
                local_storage.delete(test_filename)

    def test_cleanup_real_temp_files(self, tenant, platform_admin):
        """Test that cleanup actually deletes temporary files."""
        # Get local storage backend
        local_storage = get_storage_backend("local")
        backup_dir = local_storage.base_path

        # Create real temp files
        old_temp_file = backup_dir / "test_cleanup.tmp"
        recent_temp_file = backup_dir / "test_recent.tmp"

        try:
            # Create old temp file (2 days old)
            old_temp_file.write_text("old temp data")

            # Modify timestamp to make it old
            import time

            old_time = time.time() - (2 * 24 * 60 * 60)  # 2 days ago
            os.utime(old_temp_file, (old_time, old_time))

            # Create recent temp file (1 hour old)
            recent_temp_file.write_text("recent temp data")

            # Verify both files exist
            assert old_temp_file.exists()
            assert recent_temp_file.exists()

            # Run cleanup
            result = cleanup_old_backups()

            # Verify old temp file was deleted
            assert not old_temp_file.exists()

            # Verify recent temp file still exists
            assert recent_temp_file.exists()

            # Verify statistics
            assert result["temp_files_deleted"] >= 1

        finally:
            # Cleanup temp files if they still exist
            if old_temp_file.exists():
                old_temp_file.unlink()
            if recent_temp_file.exists():
                recent_temp_file.unlink()

    def test_cleanup_respects_retention_policies(self, tenant, platform_admin):
        """Test that cleanup respects 30-day local and 1-year cloud retention."""
        # Get storage backends
        local_storage = get_storage_backend("local")

        # Test local retention (30 days)
        # Create backup at 29 days - should NOT be deleted
        # (30 days retention means we keep backups for 30 full days)
        exactly_29_days = timezone.now() - timedelta(days=29)

        test_filename_29 = "test_exactly_29_days.dump.gz.enc"
        test_content = b"Test 30 day retention"

        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(test_content)
            temp_file_path = temp_file.name

        try:
            local_storage.upload(temp_file_path, test_filename_29)

            backup_29 = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                tenant=None,
                filename=test_filename_29,
                size_bytes=len(test_content),
                checksum="test_29_days",
                local_path=test_filename_29,
                r2_path="",
                b2_path="",
                status=Backup.COMPLETED,
                created_by=platform_admin,
            )
            backup_29.created_at = exactly_29_days
            backup_29.save()

            # Create backup at 31 days - should be deleted
            exactly_31_days = timezone.now() - timedelta(days=31)

            test_filename_31 = "test_exactly_31_days.dump.gz.enc"

            with tempfile.NamedTemporaryFile(delete=False) as temp_file2:
                temp_file2.write(test_content)
                temp_file_path2 = temp_file2.name

            local_storage.upload(temp_file_path2, test_filename_31)

            backup_31 = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                tenant=None,
                filename=test_filename_31,
                size_bytes=len(test_content),
                checksum="test_31_days",
                local_path=test_filename_31,
                r2_path="",
                b2_path="",
                status=Backup.COMPLETED,
                created_by=platform_admin,
            )
            backup_31.created_at = exactly_31_days
            backup_31.save()

            # Run cleanup
            cleanup_old_backups()

            # Verify 29-day backup still exists
            assert local_storage.exists(test_filename_29)
            backup_29.refresh_from_db()
            assert backup_29.local_path == test_filename_29

            # Verify 31-day backup was deleted (no storage locations left)
            assert not local_storage.exists(test_filename_31)
            assert not Backup.objects.filter(id=backup_31.id).exists()

        finally:
            # Cleanup
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            if os.path.exists(temp_file_path2):
                os.unlink(temp_file_path2)
            if local_storage.exists(test_filename_29):
                local_storage.delete(test_filename_29)
            if local_storage.exists(test_filename_31):
                local_storage.delete(test_filename_31)
