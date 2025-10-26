"""
Tests for configuration backup functionality.

This module tests the configuration backup task including:
- Configuration file collection
- Tar.gz archive creation
- Encryption and upload
- Backup verification
"""

import tarfile
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from django.test import TestCase

import pytest

from apps.backups.models import Backup, BackupAlert
from apps.backups.tasks import collect_configuration_files, configuration_backup, create_tar_archive


class TestCollectConfigurationFiles(TestCase):
    """Test configuration file collection."""

    def test_collect_configuration_files_basic(self):
        """Test that configuration files are collected."""
        with tempfile.TemporaryDirectory() as temp_dir:
            collected_files, metadata = collect_configuration_files(temp_dir)

            # Should collect at least some files
            assert len(collected_files) > 0

            # Check metadata structure
            assert "docker_files" in metadata
            assert "env_files" in metadata
            assert "nginx_files" in metadata
            assert "ssl_files" in metadata
            assert "k8s_files" in metadata
            assert "postgres_files" in metadata
            assert "other_files" in metadata

            # Verify files were actually copied
            for file_path in collected_files:
                assert Path(file_path).exists()

    def test_collect_docker_files(self):
        """Test that Docker configuration files are collected."""
        with tempfile.TemporaryDirectory() as temp_dir:
            collected_files, metadata = collect_configuration_files(temp_dir)

            # Should collect docker-compose.yml
            docker_files = metadata["docker_files"]
            assert any("docker-compose.yml" in f for f in docker_files)

    def test_collect_env_files(self):
        """Test that environment files are collected."""
        with tempfile.TemporaryDirectory() as temp_dir:
            collected_files, metadata = collect_configuration_files(temp_dir)

            # Should collect .env.example or .env.sanitized
            env_files = metadata["env_files"]
            assert len(env_files) > 0

    def test_sanitized_env_file(self):
        """Test that .env file is sanitized (sensitive values redacted)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            collected_files, metadata = collect_configuration_files(temp_dir)

            # Find the sanitized .env file
            sanitized_env = None
            for file_path in collected_files:
                if ".env.sanitized" in file_path:
                    sanitized_env = file_path
                    break

            if sanitized_env:
                # Read the sanitized file
                with open(sanitized_env, "r") as f:
                    content = f.read()

                # Should contain REDACTED for sensitive values
                if "=" in content:
                    assert "***REDACTED***" in content


class TestCreateTarArchive(TestCase):
    """Test tar.gz archive creation."""

    def test_create_tar_archive_success(self):
        """Test successful tar.gz archive creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create some test files
            source_dir = Path(temp_dir) / "source"
            source_dir.mkdir()

            test_file1 = source_dir / "test1.txt"
            test_file1.write_text("Test content 1")

            test_file2 = source_dir / "test2.txt"
            test_file2.write_text("Test content 2")

            # Create subdirectory
            subdir = source_dir / "subdir"
            subdir.mkdir()
            test_file3 = subdir / "test3.txt"
            test_file3.write_text("Test content 3")

            # Create tar archive
            output_path = Path(temp_dir) / "test_archive.tar.gz"
            success, error_msg, archive_size = create_tar_archive(str(source_dir), str(output_path))

            # Verify success
            assert success is True
            assert error_msg is None
            assert archive_size > 0
            assert output_path.exists()

            # Verify archive contents
            with tarfile.open(output_path, "r:gz") as tar:
                members = tar.getmembers()
                assert len(members) >= 4  # source dir + 3 files

    def test_create_tar_archive_empty_directory(self):
        """Test tar.gz archive creation with empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create empty directory
            source_dir = Path(temp_dir) / "empty"
            source_dir.mkdir()

            # Create tar archive
            output_path = Path(temp_dir) / "empty_archive.tar.gz"
            success, error_msg, archive_size = create_tar_archive(str(source_dir), str(output_path))

            # Should still succeed
            assert success is True
            assert output_path.exists()

    def test_create_tar_archive_nonexistent_directory(self):
        """Test tar.gz archive creation with nonexistent directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Try to archive nonexistent directory
            source_dir = Path(temp_dir) / "nonexistent"
            output_path = Path(temp_dir) / "archive.tar.gz"

            success, error_msg, archive_size = create_tar_archive(str(source_dir), str(output_path))

            # Should fail
            assert success is False
            assert error_msg is not None
            assert archive_size == 0


@pytest.mark.django_db
class TestConfigurationBackupTask(TestCase):
    """Test configuration backup Celery task."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_task = Mock()
        self.mock_task.request.id = "test-task-id"

    @patch("apps.backups.tasks.upload_to_all_storages")
    @patch("apps.backups.tasks.compress_and_encrypt_file")
    @patch("apps.backups.tasks.verify_backup_integrity")
    def test_configuration_backup_success(self, mock_verify, mock_compress_encrypt, mock_upload):
        """Test successful configuration backup."""
        # Mock compress_and_encrypt_file
        mock_compress_encrypt.return_value = (
            "/tmp/test.tar.gz.enc",  # encrypted_path
            "abc123checksum",  # checksum
            1000,  # original_size
            800,  # final_size
        )

        # Mock upload_to_all_storages
        mock_upload.return_value = (
            True,  # all_succeeded
            {
                "local": "backup_configuration_test.tar.gz.enc",
                "r2": "backup_configuration_test.tar.gz.enc",
                "b2": "backup_configuration_test.tar.gz.enc",
            },
        )

        # Mock verify_backup_integrity
        mock_verify.return_value = {
            "valid": True,
            "locations": {
                "local": {"exists": True, "checksum_valid": True, "size": 800},
                "r2": {"exists": True, "checksum_valid": True, "size": 800},
                "b2": {"exists": True, "checksum_valid": True, "size": 800},
            },
            "errors": [],
        }

        # Run the task
        backup_id = configuration_backup.apply(kwargs={"initiated_by_user_id": None}).get()

        # Verify backup was created
        assert backup_id is not None

        backup = Backup.objects.get(id=backup_id)
        assert backup.backup_type == Backup.CONFIGURATION
        assert backup.status == Backup.VERIFIED
        assert backup.checksum == "abc123checksum"
        assert backup.size_bytes == 800
        assert backup.local_path != ""
        assert backup.r2_path != ""
        assert backup.b2_path != ""

        # Verify metadata
        assert "files_collected" in backup.metadata
        assert "file_categories" in backup.metadata

    @patch("apps.backups.tasks.collect_configuration_files")
    def test_configuration_backup_no_files(self, mock_collect):
        """Test configuration backup when no files are found."""
        # Mock collect_configuration_files to return empty list
        mock_collect.return_value = ([], {})

        # Run the task - should fail
        with pytest.raises(Exception):
            configuration_backup.apply(kwargs={"initiated_by_user_id": None}).get()

        # Verify backup record was created and marked as failed
        backup = Backup.objects.filter(backup_type=Backup.CONFIGURATION).first()
        assert backup is not None
        assert backup.status == Backup.FAILED

    @patch("apps.backups.tasks.upload_to_all_storages")
    @patch("apps.backups.tasks.compress_and_encrypt_file")
    def test_configuration_backup_upload_failure(self, mock_compress_encrypt, mock_upload):
        """Test configuration backup when upload fails."""
        # Mock compress_and_encrypt_file
        mock_compress_encrypt.return_value = (
            "/tmp/test.tar.gz.enc",
            "abc123checksum",
            1000,
            800,
        )

        # Mock upload_to_all_storages to fail
        mock_upload.return_value = (
            False,  # all_succeeded
            {
                "local": None,  # Failed
                "r2": None,
                "b2": None,
            },
        )

        # Run the task - should fail
        with pytest.raises(Exception):
            configuration_backup.apply(kwargs={"initiated_by_user_id": None}).get()

        # Verify backup record was created and marked as failed
        backup = Backup.objects.filter(backup_type=Backup.CONFIGURATION).first()
        assert backup is not None
        assert backup.status == Backup.FAILED

        # Verify alert was created
        alert = BackupAlert.objects.filter(
            alert_type=BackupAlert.BACKUP_FAILURE, backup=backup
        ).first()
        assert alert is not None
        assert alert.severity == BackupAlert.CRITICAL

    @patch("apps.backups.tasks.upload_to_all_storages")
    @patch("apps.backups.tasks.compress_and_encrypt_file")
    @patch("apps.backups.tasks.verify_backup_integrity")
    def test_configuration_backup_verification_failure(
        self, mock_verify, mock_compress_encrypt, mock_upload
    ):
        """Test configuration backup when verification fails."""
        # Mock compress_and_encrypt_file
        mock_compress_encrypt.return_value = (
            "/tmp/test.tar.gz.enc",
            "abc123checksum",
            1000,
            800,
        )

        # Mock upload_to_all_storages
        mock_upload.return_value = (
            True,
            {
                "local": "backup_configuration_test.tar.gz.enc",
                "r2": "backup_configuration_test.tar.gz.enc",
                "b2": "backup_configuration_test.tar.gz.enc",
            },
        )

        # Mock verify_backup_integrity to fail
        mock_verify.return_value = {
            "valid": False,
            "locations": {
                "local": {"exists": True, "checksum_valid": False, "size": 800},
                "r2": {"exists": True, "checksum_valid": True, "size": 800},
                "b2": {"exists": True, "checksum_valid": True, "size": 800},
            },
            "errors": ["Checksum mismatch in local: test.tar.gz.enc"],
        }

        # Run the task - should succeed but with warning
        backup_id = configuration_backup.apply(kwargs={"initiated_by_user_id": None}).get()

        # Verify backup was created but not verified
        backup = Backup.objects.get(id=backup_id)
        assert backup.status == Backup.COMPLETED  # Not VERIFIED

        # Verify alert was created
        alert = BackupAlert.objects.filter(
            alert_type=BackupAlert.INTEGRITY_FAILURE, backup=backup
        ).first()
        assert alert is not None
        assert alert.severity == BackupAlert.WARNING


@pytest.mark.django_db
class TestConfigurationBackupIntegration(TestCase):
    """Integration tests for configuration backup."""

    @patch("apps.backups.tasks.get_storage_backend")
    def test_configuration_backup_end_to_end(self, mock_get_storage):
        """Test end-to-end configuration backup process."""
        # Mock storage backends
        mock_local_storage = Mock()
        mock_local_storage.upload.return_value = True
        mock_local_storage.exists.return_value = True
        mock_local_storage.get_size.return_value = 1000
        mock_local_storage.download.return_value = True

        mock_r2_storage = Mock()
        mock_r2_storage.upload.return_value = True
        mock_r2_storage.exists.return_value = True
        mock_r2_storage.get_size.return_value = 1000
        mock_r2_storage.download.return_value = True

        mock_b2_storage = Mock()
        mock_b2_storage.upload.return_value = True
        mock_b2_storage.exists.return_value = True
        mock_b2_storage.get_size.return_value = 1000
        mock_b2_storage.download.return_value = True

        def get_storage_side_effect(backend_type):
            if backend_type == "local":
                return mock_local_storage
            elif backend_type == "r2":
                return mock_r2_storage
            elif backend_type == "b2":
                return mock_b2_storage

        mock_get_storage.side_effect = get_storage_side_effect

        # Run the task
        backup_id = configuration_backup.apply(kwargs={"initiated_by_user_id": None}).get()

        # Verify backup was created
        assert backup_id is not None

        backup = Backup.objects.get(id=backup_id)
        assert backup.backup_type == Backup.CONFIGURATION
        assert backup.status in [Backup.COMPLETED, Backup.VERIFIED]
        assert backup.size_bytes > 0
        assert backup.checksum != ""

        # Verify storage backends were called
        assert mock_local_storage.upload.called
        assert mock_r2_storage.upload.called
        assert mock_b2_storage.upload.called
