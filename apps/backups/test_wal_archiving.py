"""
Tests for continuous WAL archiving functionality.

This module tests the WAL archiving task that runs every 5 minutes to:
- Identify new WAL files
- Compress them
- Upload to R2 and B2
- Mark as archived
- Clean up old archives
"""

import os
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from django.utils import timezone

import pytest

from apps.backups.models import Backup, BackupAlert
from apps.backups.tasks import cleanup_old_wal_archives, continuous_wal_archiving


@pytest.mark.django_db
class TestWALArchiving:
    """Test continuous WAL archiving functionality."""

    def test_wal_archiving_no_wal_directory(self):
        """Test WAL archiving when pg_wal directory doesn't exist."""
        with patch.dict(os.environ, {"PGDATA": "/nonexistent/path"}):
            result = continuous_wal_archiving()

        # Should return 0 when directory doesn't exist
        assert result == 0

    def test_wal_archiving_no_new_files(self):
        """Test WAL archiving when there are no new WAL files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create pg_wal directory
            pg_wal_dir = Path(temp_dir) / "pg_wal"
            pg_wal_dir.mkdir()

            with patch.dict(os.environ, {"PGDATA": temp_dir}):
                result = continuous_wal_archiving()

            # Should return 0 when no WAL files exist
            assert result == 0

    @patch("apps.backups.tasks.get_storage_backend")
    def test_wal_archiving_success(self, mock_get_storage):
        """Test successful WAL archiving."""
        # Create mock storage backends
        mock_r2 = Mock()
        mock_r2.upload.return_value = True
        mock_b2 = Mock()
        mock_b2.upload.return_value = True

        def get_backend(backend_type):
            if backend_type == "r2":
                return mock_r2
            elif backend_type == "b2":
                return mock_b2
            return Mock()

        mock_get_storage.side_effect = get_backend

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create pg_wal directory
            pg_wal_dir = Path(temp_dir) / "pg_wal"
            pg_wal_dir.mkdir()

            # Create a mock WAL file (24 character alphanumeric name)
            wal_filename = "000000010000000000000001"
            wal_file = pg_wal_dir / wal_filename
            wal_file.write_text("Mock WAL data" * 1000)  # Create some content

            with patch.dict(os.environ, {"PGDATA": temp_dir}):
                result = continuous_wal_archiving()

            # Should return 1 (one file archived)
            assert result == 1

            # Verify backup record was created
            backup = Backup.objects.filter(
                backup_type=Backup.WAL_ARCHIVE, filename=f"{wal_filename}.gz"
            ).first()

            assert backup is not None
            assert backup.status == Backup.VERIFIED
            assert backup.size_bytes > 0
            assert backup.checksum != ""
            assert backup.local_path == ""  # WAL files skip local storage
            assert backup.r2_path == f"wal/{wal_filename}.gz"
            assert backup.b2_path == f"wal/{wal_filename}.gz"
            assert backup.compression_ratio > 0
            assert backup.metadata["wal_filename"] == wal_filename

            # Verify storage backends were called
            assert mock_r2.upload.called
            assert mock_b2.upload.called

            # Verify WAL file was removed after archiving
            assert not wal_file.exists()

    @patch("apps.backups.tasks.get_storage_backend")
    def test_wal_archiving_already_archived(self, mock_get_storage):
        """Test that already archived WAL files are skipped."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create pg_wal directory
            pg_wal_dir = Path(temp_dir) / "pg_wal"
            pg_wal_dir.mkdir()

            # Create a mock WAL file
            wal_filename = "000000010000000000000002"
            wal_file = pg_wal_dir / wal_filename
            wal_file.write_text("Mock WAL data" * 1000)

            # Create a backup record for this WAL file (already archived)
            Backup.objects.create(
                backup_type=Backup.WAL_ARCHIVE,
                filename=f"{wal_filename}.gz",
                size_bytes=1000,
                checksum="abc123",
                local_path="",
                r2_path=f"wal/{wal_filename}.gz",
                b2_path=f"wal/{wal_filename}.gz",
                status=Backup.COMPLETED,
            )

            with patch.dict(os.environ, {"PGDATA": temp_dir}):
                result = continuous_wal_archiving()

            # Should return 0 (no new files archived)
            assert result == 0

            # Verify storage backends were not called
            assert not mock_get_storage.called

            # Verify WAL file still exists (not removed)
            assert wal_file.exists()

    @patch("apps.backups.tasks.get_storage_backend")
    def test_wal_archiving_upload_failure(self, mock_get_storage):
        """Test WAL archiving when upload fails."""
        # Create mock storage backends that fail
        mock_r2 = Mock()
        mock_r2.upload.return_value = False
        mock_b2 = Mock()
        mock_b2.upload.return_value = False

        def get_backend(backend_type):
            if backend_type == "r2":
                return mock_r2
            elif backend_type == "b2":
                return mock_b2
            return Mock()

        mock_get_storage.side_effect = get_backend

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create pg_wal directory
            pg_wal_dir = Path(temp_dir) / "pg_wal"
            pg_wal_dir.mkdir()

            # Create a mock WAL file
            wal_filename = "000000010000000000000003"
            wal_file = pg_wal_dir / wal_filename
            wal_file.write_text("Mock WAL data" * 1000)

            with patch.dict(os.environ, {"PGDATA": temp_dir}):
                result = continuous_wal_archiving()

            # Should return 0 (no files successfully archived)
            assert result == 0

            # Verify backup record was created but marked as failed
            backup = Backup.objects.filter(
                backup_type=Backup.WAL_ARCHIVE, filename=f"{wal_filename}.gz"
            ).first()

            assert backup is not None
            assert backup.status == Backup.FAILED

            # Verify alert was created
            alert = BackupAlert.objects.filter(
                alert_type=BackupAlert.BACKUP_FAILURE, backup=backup
            ).first()

            assert alert is not None
            assert alert.severity == BackupAlert.ERROR

            # Verify WAL file still exists (not removed due to failure)
            assert wal_file.exists()

    @patch("apps.backups.tasks.get_storage_backend")
    def test_wal_archiving_multiple_files(self, mock_get_storage):
        """Test archiving multiple WAL files in one run."""
        # Create mock storage backends
        mock_r2 = Mock()
        mock_r2.upload.return_value = True
        mock_b2 = Mock()
        mock_b2.upload.return_value = True

        def get_backend(backend_type):
            if backend_type == "r2":
                return mock_r2
            elif backend_type == "b2":
                return mock_b2
            return Mock()

        mock_get_storage.side_effect = get_backend

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create pg_wal directory
            pg_wal_dir = Path(temp_dir) / "pg_wal"
            pg_wal_dir.mkdir()

            # Create multiple mock WAL files
            wal_files = [
                "000000010000000000000004",
                "000000010000000000000005",
                "000000010000000000000006",
            ]

            for wal_filename in wal_files:
                wal_file = pg_wal_dir / wal_filename
                wal_file.write_text("Mock WAL data" * 1000)

            with patch.dict(os.environ, {"PGDATA": temp_dir}):
                result = continuous_wal_archiving()

            # Should return 3 (three files archived)
            assert result == 3

            # Verify backup records were created for all files
            for wal_filename in wal_files:
                backup = Backup.objects.filter(
                    backup_type=Backup.WAL_ARCHIVE, filename=f"{wal_filename}.gz"
                ).first()

                assert backup is not None
                assert backup.status == Backup.VERIFIED

                # Verify WAL file was removed
                assert not (pg_wal_dir / wal_filename).exists()

    @patch("apps.backups.tasks.get_storage_backend")
    def test_wal_archiving_partial_failure(self, mock_get_storage):
        """Test WAL archiving when some files succeed and some fail."""

        # Create mock storage backends
        # Make one succeed and one fail based on filename
        def get_backend(backend_type):
            mock = Mock()

            def upload_side_effect(local_path, remote_path):
                # Fail for file ending in 007, succeed for others
                if "000000010000000000000007" in remote_path:
                    return False
                return True

            mock.upload.side_effect = upload_side_effect
            return mock

        mock_get_storage.side_effect = get_backend

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create pg_wal directory
            pg_wal_dir = Path(temp_dir) / "pg_wal"
            pg_wal_dir.mkdir()

            # Create two mock WAL files
            wal_file1 = pg_wal_dir / "000000010000000000000007"
            wal_file1.write_text("Mock WAL data" * 1000)
            wal_file2 = pg_wal_dir / "000000010000000000000008"
            wal_file2.write_text("Mock WAL data" * 1000)

            with patch.dict(os.environ, {"PGDATA": temp_dir}):
                result = continuous_wal_archiving()

            # Should return 1 (one file archived successfully)
            assert result == 1

            # Verify one file was archived successfully
            successful_backups = Backup.objects.filter(
                backup_type=Backup.WAL_ARCHIVE, status=Backup.VERIFIED
            )
            assert successful_backups.count() == 1

            # Verify one file failed
            failed_backups = Backup.objects.filter(
                backup_type=Backup.WAL_ARCHIVE, status=Backup.FAILED
            )
            assert failed_backups.count() == 1

            # Verify the failed one is file 007
            failed_backup = failed_backups.first()
            assert "000000010000000000000007" in failed_backup.filename


@pytest.mark.django_db
class TestWALArchiveCleanup:
    """Test WAL archive cleanup functionality."""

    @patch("apps.backups.tasks.get_storage_backend")
    def test_cleanup_old_wal_archives(self, mock_get_storage):
        """Test cleanup of old WAL archives."""
        from apps.core.tenant_context import bypass_rls

        # Create mock storage backends
        mock_r2 = Mock()
        mock_r2.delete.return_value = True
        mock_b2 = Mock()
        mock_b2.delete.return_value = True

        def get_backend(backend_type):
            if backend_type == "r2":
                return mock_r2
            elif backend_type == "b2":
                return mock_b2
            return Mock()

        mock_get_storage.side_effect = get_backend

        # Create old WAL archives (older than 30 days)
        old_date = timezone.now() - timedelta(days=31)

        with bypass_rls():
            old_backup1 = Backup.objects.create(
                backup_type=Backup.WAL_ARCHIVE,
                filename="000000010000000000000010.gz",
                size_bytes=1000,
                checksum="abc123",
                local_path="",
                r2_path="wal/000000010000000000000010.gz",
                b2_path="wal/000000010000000000000010.gz",
                status=Backup.COMPLETED,
            )
            # Update created_at manually (auto_now_add prevents setting it on create)
            Backup.objects.filter(id=old_backup1.id).update(created_at=old_date)
            old_backup1.refresh_from_db()

            old_backup2 = Backup.objects.create(
                backup_type=Backup.WAL_ARCHIVE,
                filename="000000010000000000000011.gz",
                size_bytes=1000,
                checksum="def456",
                local_path="",
                r2_path="wal/000000010000000000000011.gz",
                b2_path="wal/000000010000000000000011.gz",
                status=Backup.COMPLETED,
            )
            # Update created_at manually
            Backup.objects.filter(id=old_backup2.id).update(created_at=old_date)
            old_backup2.refresh_from_db()

            # Create recent WAL archive (should not be deleted)
            recent_backup = Backup.objects.create(
                backup_type=Backup.WAL_ARCHIVE,
                filename="000000010000000000000012.gz",
                size_bytes=1000,
                checksum="ghi789",
                local_path="",
                r2_path="wal/000000010000000000000012.gz",
                b2_path="wal/000000010000000000000012.gz",
                status=Backup.COMPLETED,
            )

        # Run cleanup
        cleanup_old_wal_archives()

        # Verify old backups were deleted
        with bypass_rls():
            assert not Backup.objects.filter(id=old_backup1.id).exists()
            assert not Backup.objects.filter(id=old_backup2.id).exists()

            # Verify recent backup still exists
            assert Backup.objects.filter(id=recent_backup.id).exists()

        # Verify storage backends were called to delete files
        assert mock_r2.delete.call_count == 2
        assert mock_b2.delete.call_count == 2

    def test_cleanup_no_old_archives(self):
        """Test cleanup when there are no old archives."""
        from apps.core.tenant_context import bypass_rls

        # Create only recent WAL archives
        with bypass_rls():
            Backup.objects.create(
                backup_type=Backup.WAL_ARCHIVE,
                filename="000000010000000000000013.gz",
                size_bytes=1000,
                checksum="abc123",
                local_path="",
                r2_path="wal/000000010000000000000013.gz",
                b2_path="wal/000000010000000000000013.gz",
                status=Backup.COMPLETED,
            )

        # Run cleanup (should not delete anything)
        cleanup_old_wal_archives()

        # Verify backup still exists
        with bypass_rls():
            assert Backup.objects.filter(backup_type=Backup.WAL_ARCHIVE).count() == 1

    @patch("apps.backups.tasks.get_storage_backend")
    def test_cleanup_storage_deletion_failure(self, mock_get_storage):
        """Test cleanup when storage deletion fails."""
        from apps.core.tenant_context import bypass_rls

        # Create mock storage backends that fail
        mock_r2 = Mock()
        mock_r2.delete.return_value = False
        mock_b2 = Mock()
        mock_b2.delete.return_value = False

        def get_backend(backend_type):
            if backend_type == "r2":
                return mock_r2
            elif backend_type == "b2":
                return mock_b2
            return Mock()

        mock_get_storage.side_effect = get_backend

        # Create old WAL archive
        old_date = timezone.now() - timedelta(days=31)
        with bypass_rls():
            old_backup = Backup.objects.create(
                backup_type=Backup.WAL_ARCHIVE,
                filename="000000010000000000000014.gz",
                size_bytes=1000,
                checksum="abc123",
                local_path="",
                r2_path="wal/000000010000000000000014.gz",
                b2_path="wal/000000010000000000000014.gz",
                status=Backup.COMPLETED,
            )
            # Update created_at manually (auto_now_add prevents setting it on create)
            Backup.objects.filter(id=old_backup.id).update(created_at=old_date)
            old_backup.refresh_from_db()

        # Run cleanup
        cleanup_old_wal_archives()

        # Verify backup record was still deleted even though storage deletion failed
        with bypass_rls():
            assert not Backup.objects.filter(id=old_backup.id).exists()

        # Verify storage backends were called
        assert mock_r2.delete.called
        assert mock_b2.delete.called
