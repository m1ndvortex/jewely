"""
Tests for backup cleanup functionality.

This module tests the cleanup_old_backups task that:
- Deletes local backups older than 30 days
- Archives cloud backups older than 1 year
- Cleans up temporary files
"""

import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.utils import timezone

import pytest

from apps.backups.models import Backup
from apps.backups.tasks import cleanup_old_backups


@pytest.mark.django_db
class TestBackupCleanup:
    """Test backup cleanup task."""

    def test_cleanup_old_local_backups(self, tenant, platform_admin):
        """Test that local backups older than 30 days are deleted."""
        # Create old backup (35 days old)
        old_date = timezone.now() - timedelta(days=35)
        old_backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            tenant=None,
            filename="old_backup.dump.gz.enc",
            size_bytes=1024 * 1024,
            checksum="abc123",
            local_path="old_backup.dump.gz.enc",
            r2_path="old_backup.dump.gz.enc",
            b2_path="old_backup.dump.gz.enc",
            status=Backup.COMPLETED,
            created_by=platform_admin,
        )
        old_backup.created_at = old_date
        old_backup.save()

        # Create recent backup (10 days old)
        recent_date = timezone.now() - timedelta(days=10)
        recent_backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            tenant=None,
            filename="recent_backup.dump.gz.enc",
            size_bytes=1024 * 1024,
            checksum="def456",
            local_path="recent_backup.dump.gz.enc",
            r2_path="recent_backup.dump.gz.enc",
            b2_path="recent_backup.dump.gz.enc",
            status=Backup.COMPLETED,
            created_by=platform_admin,
        )
        recent_backup.created_at = recent_date
        recent_backup.save()

        # Mock storage backend
        with patch("apps.backups.tasks.get_storage_backend") as mock_storage:
            mock_local = MagicMock()
            mock_local.delete.return_value = True
            mock_local.base_path = Path(tempfile.gettempdir())
            mock_storage.return_value = mock_local

            # Run cleanup
            result = cleanup_old_backups()

            # Verify old backup was deleted from local storage
            assert result["local_deleted"] == 1
            assert result["local_failed"] == 0

            # Verify old backup record was updated
            old_backup.refresh_from_db()
            assert old_backup.local_path == ""

            # Verify recent backup was not touched
            recent_backup.refresh_from_db()
            assert recent_backup.local_path == "recent_backup.dump.gz.enc"

    def test_cleanup_old_cloud_backups(self, tenant, platform_admin):
        """Test that cloud backups older than 1 year are deleted."""
        # Create very old backup (400 days old)
        very_old_date = timezone.now() - timedelta(days=400)
        very_old_backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            tenant=None,
            filename="very_old_backup.dump.gz.enc",
            size_bytes=1024 * 1024,
            checksum="xyz789",
            local_path="",  # Already cleaned from local
            r2_path="very_old_backup.dump.gz.enc",
            b2_path="very_old_backup.dump.gz.enc",
            status=Backup.COMPLETED,
            created_by=platform_admin,
        )
        very_old_backup.created_at = very_old_date
        very_old_backup.save()

        # Create recent backup (100 days old)
        recent_date = timezone.now() - timedelta(days=100)
        recent_backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            tenant=None,
            filename="recent_backup.dump.gz.enc",
            size_bytes=1024 * 1024,
            checksum="def456",
            local_path="",
            r2_path="recent_backup.dump.gz.enc",
            b2_path="recent_backup.dump.gz.enc",
            status=Backup.COMPLETED,
            created_by=platform_admin,
        )
        recent_backup.created_at = recent_date
        recent_backup.save()

        # Mock storage backends
        with patch("apps.backups.tasks.get_storage_backend") as mock_storage:
            mock_local = MagicMock()
            mock_local.base_path = Path(tempfile.gettempdir())

            mock_r2 = MagicMock()
            mock_r2.delete.return_value = True

            mock_b2 = MagicMock()
            mock_b2.delete.return_value = True

            def get_backend(backend_type):
                if backend_type == "local":
                    return mock_local
                elif backend_type == "r2":
                    return mock_r2
                elif backend_type == "b2":
                    return mock_b2

            mock_storage.side_effect = get_backend

            # Run cleanup
            result = cleanup_old_backups()

            # Verify very old backup was deleted from cloud storage
            assert result["r2_deleted"] == 1
            assert result["b2_deleted"] == 1

            # Verify very old backup record was deleted (since all storage locations are empty)
            assert result["database_records_deleted"] == 1
            assert not Backup.objects.filter(id=very_old_backup.id).exists()

            # Verify recent backup was not touched
            recent_backup.refresh_from_db()
            assert recent_backup.r2_path == "recent_backup.dump.gz.enc"
            assert recent_backup.b2_path == "recent_backup.dump.gz.enc"

    def test_cleanup_orphaned_database_records(self, tenant, platform_admin):
        """Test that database records with no storage locations are deleted."""
        # Create backup with no storage locations
        orphaned_backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            tenant=None,
            filename="orphaned_backup.dump.gz.enc",
            size_bytes=1024 * 1024,
            checksum="orphan123",
            local_path="",
            r2_path="",
            b2_path="",
            status=Backup.COMPLETED,
            created_by=platform_admin,
        )

        # Create backup with at least one storage location
        valid_backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            tenant=None,
            filename="valid_backup.dump.gz.enc",
            size_bytes=1024 * 1024,
            checksum="valid123",
            local_path="",
            r2_path="valid_backup.dump.gz.enc",
            b2_path="",
            status=Backup.COMPLETED,
            created_by=platform_admin,
        )

        # Mock storage backend
        with patch("apps.backups.tasks.get_storage_backend") as mock_storage:
            mock_local = MagicMock()
            mock_local.base_path = Path(tempfile.gettempdir())
            mock_storage.return_value = mock_local

            # Run cleanup
            result = cleanup_old_backups()

            # Verify orphaned backup was deleted
            assert result["database_records_deleted"] == 1
            assert not Backup.objects.filter(id=orphaned_backup.id).exists()

            # Verify valid backup still exists
            assert Backup.objects.filter(id=valid_backup.id).exists()

    def test_cleanup_temp_files(self, tenant, platform_admin):
        """Test that temporary files are cleaned up."""
        # Create a temporary directory with temp files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create old temp file (2 days old)
            old_temp_file = temp_path / "test.tmp"
            old_temp_file.write_text("old temp data")

            # Modify the file's timestamp to make it old
            import os
            import time

            old_time = time.time() - (2 * 24 * 60 * 60)  # 2 days ago
            os.utime(old_temp_file, (old_time, old_time))

            # Create recent temp file (1 hour old)
            recent_temp_file = temp_path / "recent.tmp"
            recent_temp_file.write_text("recent temp data")

            # Mock storage backend to use our temp directory
            with patch("apps.backups.tasks.get_storage_backend") as mock_storage:
                mock_local = MagicMock()
                mock_local.base_path = temp_path
                mock_storage.return_value = mock_local

                # Run cleanup
                result = cleanup_old_backups()

                # Verify old temp file was deleted
                assert not old_temp_file.exists()
                assert result["temp_files_deleted"] >= 1

                # Verify recent temp file still exists
                assert recent_temp_file.exists()

    def test_cleanup_creates_info_alert_on_success(self, tenant, platform_admin):
        """Test that cleanup creates an info alert when backups are deleted."""
        # Create old backup
        old_date = timezone.now() - timedelta(days=35)
        old_backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            tenant=None,
            filename="old_backup.dump.gz.enc",
            size_bytes=1024 * 1024,
            checksum="abc123",
            local_path="old_backup.dump.gz.enc",
            r2_path="",
            b2_path="",
            status=Backup.COMPLETED,
            created_by=platform_admin,
        )
        old_backup.created_at = old_date
        old_backup.save()

        # Mock storage backend
        with patch("apps.backups.tasks.get_storage_backend") as mock_storage:
            mock_local = MagicMock()
            mock_local.delete.return_value = True
            mock_local.base_path = Path(tempfile.gettempdir())
            mock_storage.return_value = mock_local

            # Mock alert creation
            with patch("apps.backups.tasks.create_backup_alert") as mock_alert:
                # Run cleanup
                cleanup_old_backups()

                # Verify info alert was created
                assert mock_alert.call_count >= 1

                # Check that at least one call was for info severity
                info_calls = [
                    call for call in mock_alert.call_args_list if call[1]["severity"] == "INFO"
                ]
                assert len(info_calls) >= 1

    def test_cleanup_handles_storage_deletion_failures(self, tenant, platform_admin):
        """Test that cleanup handles storage deletion failures gracefully."""
        # Create old backup
        old_date = timezone.now() - timedelta(days=35)
        old_backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            tenant=None,
            filename="old_backup.dump.gz.enc",
            size_bytes=1024 * 1024,
            checksum="abc123",
            local_path="old_backup.dump.gz.enc",
            r2_path="",
            b2_path="",
            status=Backup.COMPLETED,
            created_by=platform_admin,
        )
        old_backup.created_at = old_date
        old_backup.save()

        # Mock storage backend to fail deletion
        with patch("apps.backups.tasks.get_storage_backend") as mock_storage:
            mock_local = MagicMock()
            mock_local.delete.return_value = False  # Simulate failure
            mock_local.base_path = Path(tempfile.gettempdir())
            mock_storage.return_value = mock_local

            # Run cleanup
            result = cleanup_old_backups()

            # Verify failure was recorded
            assert result["local_failed"] == 1
            assert result["local_deleted"] == 0

            # Verify backup record was not updated
            old_backup.refresh_from_db()
            assert old_backup.local_path == "old_backup.dump.gz.enc"

    def test_cleanup_returns_statistics(self, tenant, platform_admin):
        """Test that cleanup returns comprehensive statistics."""
        # Mock storage backend
        with patch("apps.backups.tasks.get_storage_backend") as mock_storage:
            mock_local = MagicMock()
            mock_local.base_path = Path(tempfile.gettempdir())
            mock_storage.return_value = mock_local

            # Run cleanup
            result = cleanup_old_backups()

            # Verify statistics structure
            assert "local_deleted" in result
            assert "local_failed" in result
            assert "r2_deleted" in result
            assert "r2_failed" in result
            assert "b2_deleted" in result
            assert "b2_failed" in result
            assert "temp_files_deleted" in result
            assert "database_records_deleted" in result
            assert "errors" in result
            assert "duration_seconds" in result

            # Verify all counts are non-negative
            assert result["local_deleted"] >= 0
            assert result["local_failed"] >= 0
            assert result["r2_deleted"] >= 0
            assert result["r2_failed"] >= 0
            assert result["b2_deleted"] >= 0
            assert result["b2_failed"] >= 0
            assert result["temp_files_deleted"] >= 0
            assert result["database_records_deleted"] >= 0
