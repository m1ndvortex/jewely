"""
Tests for daily full database backup task.

This module tests the daily_full_database_backup Celery task including:
- pg_dump execution
- Compression and encryption
- Upload to all storage locations
- Metadata recording
- Error handling and retries
- Temporary file cleanup
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from apps.backups.models import Backup, BackupAlert
from apps.backups.tasks import (
    cleanup_temp_files,
    create_backup_alert,
    create_pg_dump,
    daily_full_database_backup,
    generate_backup_filename,
    get_database_config,
    upload_to_all_storages,
)


class TestGetDatabaseConfig(TestCase):
    """Test database configuration retrieval."""

    def test_get_database_config(self):
        """Test that database config is retrieved correctly from settings."""
        config = get_database_config()

        self.assertIn("name", config)
        self.assertIn("user", config)
        self.assertIn("password", config)
        self.assertIn("host", config)
        self.assertIn("port", config)

        # Verify types
        self.assertIsInstance(config["name"], str)
        self.assertIsInstance(config["user"], str)
        self.assertIsInstance(config["password"], str)
        self.assertIsInstance(config["host"], str)
        self.assertIsInstance(config["port"], str)


class TestGenerateBackupFilename(TestCase):
    """Test backup filename generation."""

    def test_generate_full_database_filename(self):
        """Test filename generation for full database backup."""
        filename = generate_backup_filename("FULL_DATABASE")

        self.assertIn("backup_full_database_", filename)
        self.assertTrue(filename.endswith(".dump"))
        # Should contain timestamp in format YYYYMMDD_HHMMSS
        self.assertRegex(filename, r"backup_full_database_\d{8}_\d{6}\.dump")

    def test_generate_tenant_backup_filename(self):
        """Test filename generation for tenant-specific backup."""
        tenant_id = "12345678-1234-1234-1234-123456789012"
        filename = generate_backup_filename("TENANT_BACKUP", tenant_id=tenant_id)

        self.assertIn("backup_tenant_backup_", filename)
        self.assertIn(tenant_id, filename)
        self.assertTrue(filename.endswith(".dump"))


class TestCreatePgDump(TestCase):
    """Test PostgreSQL dump creation."""

    @patch("apps.backups.tasks.subprocess.run")
    def test_create_pg_dump_success(self, mock_run):
        """Test successful pg_dump execution."""
        # Mock successful subprocess execution
        mock_run.return_value = Mock(returncode=0, stderr="", stdout="")

        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            output_path = temp_file.name

        try:
            success, error_msg = create_pg_dump(
                output_path=output_path,
                database="test_db",
                user="test_user",
                password="test_pass",
                host="localhost",
                port="5432",
            )

            self.assertTrue(success)
            self.assertIsNone(error_msg)

            # Verify pg_dump was called with correct arguments
            mock_run.assert_called_once()
            call_args = mock_run.call_args

            # Check command arguments
            cmd = call_args[0][0]
            self.assertIn("pg_dump", cmd)
            self.assertIn("-Fc", cmd)  # Custom format
            self.assertIn("-v", cmd)  # Verbose
            self.assertIn("--no-owner", cmd)
            self.assertIn("--no-acl", cmd)
            self.assertIn("-h", cmd)
            self.assertIn("localhost", cmd)
            self.assertIn("-p", cmd)
            self.assertIn("5432", cmd)
            self.assertIn("-U", cmd)
            self.assertIn("test_user", cmd)
            self.assertIn("-d", cmd)
            self.assertIn("test_db", cmd)
            self.assertIn("-f", cmd)
            self.assertIn(output_path, cmd)

            # Check environment
            env = call_args[1]["env"]
            self.assertEqual(env["PGPASSWORD"], "test_pass")

        finally:
            # Clean up
            if Path(output_path).exists():
                Path(output_path).unlink()

    @patch("apps.backups.tasks.subprocess.run")
    def test_create_pg_dump_failure(self, mock_run):
        """Test pg_dump failure handling."""
        # Mock failed subprocess execution
        mock_run.return_value = Mock(returncode=1, stderr="Error: connection failed", stdout="")

        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            output_path = temp_file.name

        try:
            success, error_msg = create_pg_dump(
                output_path=output_path,
                database="test_db",
                user="test_user",
                password="test_pass",
                host="localhost",
                port="5432",
            )

            self.assertFalse(success)
            self.assertIsNotNone(error_msg)
            self.assertIn("pg_dump failed", error_msg)
            self.assertIn("connection failed", error_msg)

        finally:
            # Clean up
            if Path(output_path).exists():
                Path(output_path).unlink()


class TestUploadToAllStorages(TestCase):
    """Test uploading to all storage backends."""

    @patch("apps.backups.tasks.get_storage_backend")
    def test_upload_to_all_storages_success(self, mock_get_backend):
        """Test successful upload to all storage backends."""
        # Create mock storage backends
        mock_local = Mock()
        mock_local.upload.return_value = True

        mock_r2 = Mock()
        mock_r2.upload.return_value = True

        mock_b2 = Mock()
        mock_b2.upload.return_value = True

        # Configure mock to return different backends
        def get_backend(backend_type):
            if backend_type == "local":
                return mock_local
            elif backend_type == "r2":
                return mock_r2
            elif backend_type == "b2":
                return mock_b2

        mock_get_backend.side_effect = get_backend

        # Create a temporary file to upload
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test data")
            local_path = temp_file.name

        try:
            all_succeeded, paths = upload_to_all_storages(local_path, "test_backup.dump")

            self.assertTrue(all_succeeded)
            self.assertEqual(paths["local"], "test_backup.dump")
            self.assertEqual(paths["r2"], "test_backup.dump")
            self.assertEqual(paths["b2"], "test_backup.dump")

            # Verify all backends were called
            mock_local.upload.assert_called_once_with(local_path, "test_backup.dump")
            mock_r2.upload.assert_called_once_with(local_path, "test_backup.dump")
            mock_b2.upload.assert_called_once_with(local_path, "test_backup.dump")

        finally:
            # Clean up
            if Path(local_path).exists():
                Path(local_path).unlink()

    @patch("apps.backups.tasks.get_storage_backend")
    def test_upload_to_all_storages_partial_failure(self, mock_get_backend):
        """Test handling of partial upload failures."""
        # Create mock storage backends with one failure
        mock_local = Mock()
        mock_local.upload.return_value = True

        mock_r2 = Mock()
        mock_r2.upload.return_value = False  # Simulate failure

        mock_b2 = Mock()
        mock_b2.upload.return_value = True

        # Configure mock to return different backends
        def get_backend(backend_type):
            if backend_type == "local":
                return mock_local
            elif backend_type == "r2":
                return mock_r2
            elif backend_type == "b2":
                return mock_b2

        mock_get_backend.side_effect = get_backend

        # Create a temporary file to upload
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test data")
            local_path = temp_file.name

        try:
            all_succeeded, paths = upload_to_all_storages(local_path, "test_backup.dump")

            self.assertFalse(all_succeeded)
            self.assertEqual(paths["local"], "test_backup.dump")
            self.assertIsNone(paths["r2"])  # Failed upload
            self.assertEqual(paths["b2"], "test_backup.dump")

        finally:
            # Clean up
            if Path(local_path).exists():
                Path(local_path).unlink()


class TestCleanupTempFiles(TestCase):
    """Test temporary file cleanup."""

    def test_cleanup_temp_files(self):
        """Test that temporary files are deleted."""
        # Create temporary files
        temp_files = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(b"test data")
                temp_files.append(temp_file.name)

        # Verify files exist
        for file_path in temp_files:
            self.assertTrue(Path(file_path).exists())

        # Clean up
        cleanup_temp_files(*temp_files)

        # Verify files are deleted
        for file_path in temp_files:
            self.assertFalse(Path(file_path).exists())

    def test_cleanup_nonexistent_files(self):
        """Test that cleanup handles nonexistent files gracefully."""
        # Should not raise an exception
        cleanup_temp_files("/nonexistent/file1.txt", "/nonexistent/file2.txt")


class TestCreateBackupAlert(TestCase):
    """Test backup alert creation."""

    def test_create_backup_alert(self):
        """Test creating a backup alert."""
        alert = create_backup_alert(
            alert_type=BackupAlert.BACKUP_FAILURE,
            severity=BackupAlert.CRITICAL,
            message="Test backup failure",
            details={"error": "Test error"},
        )

        self.assertIsNotNone(alert)
        self.assertEqual(alert.alert_type, BackupAlert.BACKUP_FAILURE)
        self.assertEqual(alert.severity, BackupAlert.CRITICAL)
        self.assertEqual(alert.message, "Test backup failure")
        self.assertEqual(alert.details["error"], "Test error")
        self.assertEqual(alert.status, BackupAlert.ACTIVE)


@override_settings(
    BACKUP_ENCRYPTION_KEY=b"test_key_32_bytes_long_for_aes256_encryption_here",
    CELERY_TASK_ALWAYS_EAGER=True,
)
class TestDailyFullDatabaseBackup(TestCase):
    """Test daily full database backup task."""

    @patch("apps.backups.tasks.verify_backup_integrity")
    @patch("apps.backups.tasks.upload_to_all_storages")
    @patch("apps.backups.tasks.compress_and_encrypt_file")
    @patch("apps.backups.tasks.create_pg_dump")
    def test_daily_full_database_backup_success(
        self, mock_pg_dump, mock_compress_encrypt, mock_upload, mock_verify
    ):
        """Test successful daily full database backup."""

        # Mock pg_dump success - create a dummy file
        def create_dummy_dump(output_path, **kwargs):
            Path(output_path).write_bytes(b"dummy pg_dump data" * 1000)
            return (True, None)

        mock_pg_dump.side_effect = create_dummy_dump

        # Mock compress and encrypt
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gz.enc") as temp_file:
            encrypted_path = temp_file.name
            temp_file.write(b"encrypted data")

        mock_compress_encrypt.return_value = (
            encrypted_path,
            "abc123checksum",
            1000000,  # original size
            500000,  # final size
        )

        # Mock upload success
        mock_upload.return_value = (
            True,
            {
                "local": "backup_full_database_20240101_020000.dump.gz.enc",
                "r2": "backup_full_database_20240101_020000.dump.gz.enc",
                "b2": "backup_full_database_20240101_020000.dump.gz.enc",
            },
        )

        # Mock verification success
        mock_verify.return_value = {"valid": True, "locations": {}, "errors": []}

        try:
            # Execute task
            backup_id = daily_full_database_backup()

            # Verify backup was created
            self.assertIsNotNone(backup_id)

            backup = Backup.objects.get(id=backup_id)
            self.assertEqual(backup.backup_type, Backup.FULL_DATABASE)
            self.assertEqual(backup.status, Backup.VERIFIED)
            self.assertIsNone(backup.tenant)
            self.assertEqual(backup.checksum, "abc123checksum")
            self.assertEqual(backup.size_bytes, 500000)
            self.assertIsNotNone(backup.local_path)
            self.assertIsNotNone(backup.r2_path)
            self.assertIsNotNone(backup.b2_path)
            self.assertIsNotNone(backup.backup_duration_seconds)
            self.assertIsNotNone(backup.compression_ratio)

            # Verify pg_dump was called
            mock_pg_dump.assert_called_once()

            # Verify compress and encrypt was called
            mock_compress_encrypt.assert_called_once()

            # Verify upload was called
            mock_upload.assert_called_once()

            # Verify integrity check was called
            mock_verify.assert_called_once()

        finally:
            # Clean up
            if Path(encrypted_path).exists():
                Path(encrypted_path).unlink()

    @patch("apps.backups.tasks.create_pg_dump")
    def test_daily_full_database_backup_pg_dump_failure(self, mock_pg_dump):
        """Test handling of pg_dump failure."""
        # Mock pg_dump failure
        mock_pg_dump.return_value = (False, "Connection refused")

        # Execute task (should raise exception and create alert)
        with self.assertRaises(Exception):
            daily_full_database_backup()

        # Verify backup record was created with FAILED status
        backup = Backup.objects.filter(backup_type=Backup.FULL_DATABASE).first()
        self.assertIsNotNone(backup)
        self.assertEqual(backup.status, Backup.FAILED)
        self.assertIn("Connection refused", backup.notes)

        # Verify alert was created
        alert = BackupAlert.objects.filter(alert_type=BackupAlert.BACKUP_FAILURE).first()
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, BackupAlert.CRITICAL)

    @patch("apps.backups.tasks.verify_backup_integrity")
    @patch("apps.backups.tasks.upload_to_all_storages")
    @patch("apps.backups.tasks.compress_and_encrypt_file")
    @patch("apps.backups.tasks.create_pg_dump")
    def test_daily_full_database_backup_upload_failure(
        self, mock_pg_dump, mock_compress_encrypt, mock_upload, mock_verify
    ):
        """Test handling of upload failure."""
        # Mock pg_dump success
        mock_pg_dump.return_value = (True, None)

        # Mock compress and encrypt
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gz.enc") as temp_file:
            encrypted_path = temp_file.name
            temp_file.write(b"encrypted data")

        mock_compress_encrypt.return_value = (
            encrypted_path,
            "abc123checksum",
            1000000,
            500000,
        )

        # Mock upload failure
        mock_upload.return_value = (
            False,
            {"local": "path", "r2": None, "b2": "path"},  # R2 upload failed
        )

        try:
            # Execute task (should raise exception)
            with self.assertRaises(Exception):
                daily_full_database_backup()

            # Verify backup record was created with FAILED status
            backup = Backup.objects.filter(backup_type=Backup.FULL_DATABASE).first()
            self.assertIsNotNone(backup)
            self.assertEqual(backup.status, Backup.FAILED)

            # Verify alert was created
            alert = BackupAlert.objects.filter(alert_type=BackupAlert.BACKUP_FAILURE).first()
            self.assertIsNotNone(alert)

        finally:
            # Clean up
            if Path(encrypted_path).exists():
                Path(encrypted_path).unlink()

    @patch("apps.backups.tasks.verify_backup_integrity")
    @patch("apps.backups.tasks.upload_to_all_storages")
    @patch("apps.backups.tasks.compress_and_encrypt_file")
    @patch("apps.backups.tasks.create_pg_dump")
    def test_daily_full_database_backup_verification_warning(
        self, mock_pg_dump, mock_compress_encrypt, mock_upload, mock_verify
    ):
        """Test handling of verification failure (warning, not critical)."""

        # Mock pg_dump success - create a dummy file
        def create_dummy_dump(output_path, **kwargs):
            Path(output_path).write_bytes(b"dummy pg_dump data" * 1000)
            return (True, None)

        mock_pg_dump.side_effect = create_dummy_dump

        # Mock compress and encrypt
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gz.enc") as temp_file:
            encrypted_path = temp_file.name
            temp_file.write(b"encrypted data")

        mock_compress_encrypt.return_value = (
            encrypted_path,
            "abc123checksum",
            1000000,
            500000,
        )

        # Mock upload success
        mock_upload.return_value = (
            True,
            {"local": "path", "r2": "path", "b2": "path"},
        )

        # Mock verification failure
        mock_verify.return_value = {
            "valid": False,
            "locations": {},
            "errors": ["Checksum mismatch in R2"],
        }

        try:
            # Execute task (should complete but with warning)
            backup_id = daily_full_database_backup()

            # Verify backup was created
            self.assertIsNotNone(backup_id)

            backup = Backup.objects.get(id=backup_id)
            # Status should be COMPLETED (not VERIFIED)
            self.assertEqual(backup.status, Backup.COMPLETED)

            # Verify warning alert was created
            alert = BackupAlert.objects.filter(alert_type=BackupAlert.INTEGRITY_FAILURE).first()
            self.assertIsNotNone(alert)
            self.assertEqual(alert.severity, BackupAlert.WARNING)

        finally:
            # Clean up
            if Path(encrypted_path).exists():
                Path(encrypted_path).unlink()
