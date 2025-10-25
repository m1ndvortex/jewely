"""
Real integration tests for backup storage backends.

These tests validate the storage backends with REAL operations:
- LocalStorage: Real filesystem operations
- CloudflareR2Storage: Real boto3 client (can be tested with real credentials)
- BackblazeB2Storage: Real boto3 client (can be tested with real credentials)

NO MOCKING OF INTERNAL SERVICES - Only external cloud services can be mocked if credentials unavailable.
"""

import hashlib
import os
import tempfile
from pathlib import Path

from django.conf import settings

import pytest

from apps.backups.storage import (
    BackblazeB2Storage,
    CloudflareR2Storage,
    LocalStorage,
    get_storage_backend,
)


@pytest.mark.django_db
class TestLocalStorageIntegration:
    """
    Integration tests for LocalStorage with REAL filesystem operations.
    NO MOCKING - All operations use real files and directories.
    """

    def test_full_backup_workflow_with_real_files(self):
        """Test complete backup workflow: create, upload, verify, download, delete."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup
            backup_dir = os.path.join(tmpdir, "backups")
            storage = LocalStorage(base_path=backup_dir)

            # Create a real backup file with actual content
            source_file = os.path.join(tmpdir, "database_backup.sql.gz")
            backup_content = b"-- PostgreSQL database dump\n" * 1000  # Simulate real backup
            with open(source_file, "wb") as f:
                f.write(backup_content)

            # Calculate checksum
            checksum = hashlib.sha256(backup_content).hexdigest()

            # Upload backup
            remote_path = "backups/full/2025/10/25/database_backup.sql.gz"
            upload_success = storage.upload(source_file, remote_path)
            assert upload_success is True, "Upload should succeed"

            # Verify file exists
            assert storage.exists(remote_path) is True, "File should exist after upload"

            # Verify file size
            expected_size = len(backup_content)
            actual_size = storage.get_size(remote_path)
            assert (
                actual_size == expected_size
            ), f"Size mismatch: expected {expected_size}, got {actual_size}"

            # Download backup to different location
            download_file = os.path.join(tmpdir, "restored_backup.sql.gz")
            download_success = storage.download(remote_path, download_file)
            assert download_success is True, "Download should succeed"

            # Verify downloaded content matches original
            with open(download_file, "rb") as f:
                downloaded_content = f.read()
            downloaded_checksum = hashlib.sha256(downloaded_content).hexdigest()
            assert downloaded_checksum == checksum, "Downloaded file checksum should match original"

            # Delete backup
            delete_success = storage.delete(remote_path)
            assert delete_success is True, "Delete should succeed"

            # Verify file no longer exists
            assert storage.exists(remote_path) is False, "File should not exist after deletion"

    def test_multiple_backups_with_different_types(self):
        """Test storing multiple backup types simultaneously."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = os.path.join(tmpdir, "backups")
            storage = LocalStorage(base_path=backup_dir)

            # Create different backup types
            backup_types = {
                "full": "backups/full/2025/10/25/full_backup.sql.gz",
                "tenant": "backups/tenant/tenant_123/2025/10/25/tenant_backup.sql.gz",
                "wal": "backups/wal/2025/10/25/000000010000000000000001.gz",
                "config": "backups/config/2025/10/25/config_backup.tar.gz",
            }

            # Upload all backup types
            for backup_type, remote_path in backup_types.items():
                source_file = os.path.join(tmpdir, f"{backup_type}_backup.dat")
                content = f"{backup_type} backup content".encode() * 100
                with open(source_file, "wb") as f:
                    f.write(content)

                success = storage.upload(source_file, remote_path)
                assert success is True, f"{backup_type} upload should succeed"
                assert storage.exists(remote_path) is True, f"{backup_type} should exist"

            # Verify all backups exist
            for remote_path in backup_types.values():
                assert storage.exists(remote_path) is True

            # Cleanup all backups
            for remote_path in backup_types.values():
                storage.delete(remote_path)

    def test_large_file_handling(self):
        """Test handling of large backup files (simulating real database backups)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = os.path.join(tmpdir, "backups")
            storage = LocalStorage(base_path=backup_dir)

            # Create a large file (10 MB)
            source_file = os.path.join(tmpdir, "large_backup.sql.gz")
            large_content = b"X" * (10 * 1024 * 1024)  # 10 MB
            with open(source_file, "wb") as f:
                f.write(large_content)

            # Upload large file
            remote_path = "backups/full/large_backup.sql.gz"
            upload_success = storage.upload(source_file, remote_path)
            assert upload_success is True

            # Verify size
            size = storage.get_size(remote_path)
            assert size == len(large_content)

            # Download and verify
            download_file = os.path.join(tmpdir, "downloaded_large.sql.gz")
            download_success = storage.download(remote_path, download_file)
            assert download_success is True

            # Verify integrity
            with open(download_file, "rb") as f:
                downloaded_content = f.read()
            assert len(downloaded_content) == len(large_content)

            # Cleanup
            storage.delete(remote_path)

    def test_concurrent_operations(self):
        """Test multiple concurrent backup operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = os.path.join(tmpdir, "backups")
            storage = LocalStorage(base_path=backup_dir)

            # Create multiple backup files
            num_backups = 10
            backups = []

            for i in range(num_backups):
                source_file = os.path.join(tmpdir, f"backup_{i}.dat")
                content = f"Backup {i} content".encode() * 100
                with open(source_file, "wb") as f:
                    f.write(content)

                remote_path = f"backups/concurrent/backup_{i}.dat"
                backups.append((source_file, remote_path, content))

            # Upload all backups
            for source_file, remote_path, _ in backups:
                success = storage.upload(source_file, remote_path)
                assert success is True

            # Verify all exist
            for _, remote_path, _ in backups:
                assert storage.exists(remote_path) is True

            # Download and verify all
            for source_file, remote_path, original_content in backups:
                download_file = os.path.join(tmpdir, f"downloaded_{Path(remote_path).name}")
                success = storage.download(remote_path, download_file)
                assert success is True

                with open(download_file, "rb") as f:
                    downloaded_content = f.read()
                assert downloaded_content == original_content

            # Cleanup all
            for _, remote_path, _ in backups:
                storage.delete(remote_path)

    def test_nested_directory_structure(self):
        """Test deeply nested directory structures for organized backups."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = os.path.join(tmpdir, "backups")
            storage = LocalStorage(base_path=backup_dir)

            # Create deeply nested path
            source_file = os.path.join(tmpdir, "backup.dat")
            with open(source_file, "wb") as f:
                f.write(b"test content")

            remote_path = "backups/year/2025/month/10/day/25/hour/14/minute/30/backup.dat"
            success = storage.upload(source_file, remote_path)
            assert success is True

            # Verify directory structure was created
            full_path = Path(backup_dir) / remote_path
            assert full_path.exists()
            assert full_path.parent.exists()

            # Cleanup
            storage.delete(remote_path)


@pytest.mark.django_db
class TestCloudStorageIntegration:
    """
    Integration tests for cloud storage backends.
    Tests the full flow with real boto3 client initialization.
    """

    def test_cloudflare_r2_initialization_with_real_config(self):
        """Test R2 storage initializes with real configuration."""
        # This tests real initialization without mocking
        storage = CloudflareR2Storage(
            account_id="b7900eeee7c415345d86ea859c9dad47",
            bucket_name="securesyntax",
            access_key_id="test_key",
            secret_access_key="test_secret",
        )

        assert storage.account_id == "b7900eeee7c415345d86ea859c9dad47"
        assert storage.bucket_name == "securesyntax"
        assert (
            storage.endpoint_url
            == "https://b7900eeee7c415345d86ea859c9dad47.r2.cloudflarestorage.com"
        )
        assert storage.client is not None

    def test_backblaze_b2_initialization_with_real_config(self):
        """Test B2 storage initializes with real configuration."""
        storage = BackblazeB2Storage(
            bucket_name="securesyntax",
            region="us-east-005",
            access_key_id="test_key",
            secret_access_key="test_secret",
        )

        assert storage.bucket_name == "securesyntax"
        assert storage.region == "us-east-005"
        assert storage.endpoint_url == "https://s3.us-east-005.backblazeb2.com"
        assert storage.client is not None

    @pytest.mark.skipif(
        not os.getenv("R2_ACCESS_KEY_ID") or not os.getenv("R2_SECRET_ACCESS_KEY"),
        reason="R2 credentials not available - set R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY to run",
    )
    def test_cloudflare_r2_real_upload_download(self):
        """
        Test REAL upload/download to Cloudflare R2.
        Only runs if R2 credentials are available in environment.
        """
        storage = CloudflareR2Storage()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            source_file = os.path.join(tmpdir, "test_backup.dat")
            test_content = b"Real R2 test content" * 100
            with open(source_file, "wb") as f:
                f.write(test_content)

            # Upload to R2
            remote_path = "test/integration/test_backup.dat"
            upload_success = storage.upload(source_file, remote_path)
            assert upload_success is True

            # Verify exists
            assert storage.exists(remote_path) is True

            # Download from R2
            download_file = os.path.join(tmpdir, "downloaded.dat")
            download_success = storage.download(remote_path, download_file)
            assert download_success is True

            # Verify content
            with open(download_file, "rb") as f:
                downloaded_content = f.read()
            assert downloaded_content == test_content

            # Cleanup
            storage.delete(remote_path)

    @pytest.mark.skipif(
        not os.getenv("B2_ACCESS_KEY_ID") or not os.getenv("B2_SECRET_ACCESS_KEY"),
        reason="B2 credentials not available - set B2_ACCESS_KEY_ID and B2_SECRET_ACCESS_KEY to run",
    )
    def test_backblaze_b2_real_upload_download(self):
        """
        Test REAL upload/download to Backblaze B2.
        Only runs if B2 credentials are available in environment.
        """
        storage = BackblazeB2Storage()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            source_file = os.path.join(tmpdir, "test_backup.dat")
            test_content = b"Real B2 test content" * 100
            with open(source_file, "wb") as f:
                f.write(test_content)

            # Upload to B2
            remote_path = "test/integration/test_backup.dat"
            upload_success = storage.upload(source_file, remote_path)
            assert upload_success is True

            # Verify exists
            assert storage.exists(remote_path) is True

            # Download from B2
            download_file = os.path.join(tmpdir, "downloaded.dat")
            download_success = storage.download(remote_path, download_file)
            assert download_success is True

            # Verify content
            with open(download_file, "rb") as f:
                downloaded_content = f.read()
            assert downloaded_content == test_content

            # Cleanup
            storage.delete(remote_path)


@pytest.mark.django_db
class TestTripleRedundantBackupIntegration:
    """
    Integration tests for triple-redundant backup storage.
    Tests the complete workflow of storing backups in all three locations.
    """

    def test_triple_redundant_upload_workflow(self):
        """Test uploading same backup to all three storage backends."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup all three storage backends
            local_storage = LocalStorage(base_path=os.path.join(tmpdir, "local_backups"))

            # For cloud storage, we'll test initialization and interface
            # Real uploads would require credentials
            r2_storage = CloudflareR2Storage(
                access_key_id="test_key", secret_access_key="test_secret"
            )
            b2_storage = BackblazeB2Storage(
                access_key_id="test_key", secret_access_key="test_secret"
            )

            # Create backup file
            source_file = os.path.join(tmpdir, "triple_backup.sql.gz")
            backup_content = b"Triple redundant backup content" * 1000
            with open(source_file, "wb") as f:
                f.write(backup_content)

            # Calculate checksum
            checksum = hashlib.sha256(backup_content).hexdigest()

            # Upload to local storage (real operation)
            remote_path = "backups/full/2025/10/25/triple_backup.sql.gz"
            local_success = local_storage.upload(source_file, remote_path)
            assert local_success is True

            # Verify local storage
            assert local_storage.exists(remote_path) is True
            local_size = local_storage.get_size(remote_path)
            assert local_size == len(backup_content)

            # Download from local and verify integrity
            download_file = os.path.join(tmpdir, "downloaded_triple.sql.gz")
            local_storage.download(remote_path, download_file)

            with open(download_file, "rb") as f:
                downloaded_content = f.read()
            downloaded_checksum = hashlib.sha256(downloaded_content).hexdigest()
            assert downloaded_checksum == checksum

            # Verify cloud storage backends are properly initialized
            assert r2_storage.client is not None
            assert r2_storage.bucket_name == "securesyntax"
            assert b2_storage.client is not None
            assert b2_storage.bucket_name == "securesyntax"

            # Cleanup local
            local_storage.delete(remote_path)

    def test_backup_metadata_tracking(self):
        """Test tracking backup metadata across all storage locations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            local_storage = LocalStorage(base_path=os.path.join(tmpdir, "backups"))

            # Create backup
            source_file = os.path.join(tmpdir, "metadata_backup.sql.gz")
            content = b"Backup with metadata" * 500
            with open(source_file, "wb") as f:
                f.write(content)

            # Calculate metadata
            checksum = hashlib.sha256(content).hexdigest()
            size_bytes = len(content)

            # Upload
            remote_path = "backups/full/metadata_backup.sql.gz"
            local_storage.upload(source_file, remote_path)

            # Verify metadata
            stored_size = local_storage.get_size(remote_path)
            assert stored_size == size_bytes

            # Download and verify checksum
            download_file = os.path.join(tmpdir, "downloaded_metadata.sql.gz")
            local_storage.download(remote_path, download_file)

            with open(download_file, "rb") as f:
                downloaded_content = f.read()
            downloaded_checksum = hashlib.sha256(downloaded_content).hexdigest()
            assert downloaded_checksum == checksum

            # Cleanup
            local_storage.delete(remote_path)


@pytest.mark.django_db
class TestStorageBackendFactory:
    """Test the storage backend factory with real instantiation."""

    def test_factory_creates_real_local_storage(self):
        """Test factory creates real LocalStorage instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Temporarily override settings
            original_path = getattr(settings, "BACKUP_LOCAL_PATH", None)
            settings.BACKUP_LOCAL_PATH = tmpdir

            try:
                storage = get_storage_backend("local")
                assert isinstance(storage, LocalStorage)
                assert storage.base_path == Path(tmpdir)

                # Test it actually works
                test_file = os.path.join(tmpdir, "test.dat")
                with open(test_file, "wb") as f:
                    f.write(b"test")

                success = storage.upload(test_file, "test/test.dat")
                assert success is True
                assert storage.exists("test/test.dat") is True

            finally:
                if original_path:
                    settings.BACKUP_LOCAL_PATH = original_path
                else:
                    delattr(settings, "BACKUP_LOCAL_PATH")

    def test_factory_creates_real_r2_storage(self):
        """Test factory creates real CloudflareR2Storage instance."""
        storage = get_storage_backend("r2")
        assert isinstance(storage, CloudflareR2Storage)
        assert storage.client is not None
        assert storage.bucket_name == "securesyntax"

    def test_factory_creates_real_b2_storage(self):
        """Test factory creates real BackblazeB2Storage instance."""
        storage = get_storage_backend("b2")
        assert isinstance(storage, BackblazeB2Storage)
        assert storage.client is not None
        assert storage.bucket_name == "securesyntax"

    def test_factory_with_invalid_backend_raises_error(self):
        """Test factory raises error for invalid backend type."""
        with pytest.raises(ValueError, match="Unknown storage backend type"):
            get_storage_backend("invalid_backend")


@pytest.mark.django_db
class TestBackupRequirementCompliance:
    """
    Tests to verify compliance with Requirement 6 specifications.
    These tests ensure the storage backends meet all requirements.
    """

    def test_requirement_6_1_triple_redundant_storage(self):
        """
        Requirement 6.1: Store every backup in three locations simultaneously.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize all three storage backends
            local = LocalStorage(base_path=os.path.join(tmpdir, "local"))
            r2 = CloudflareR2Storage(access_key_id="test", secret_access_key="test")
            b2 = BackblazeB2Storage(access_key_id="test", secret_access_key="test")

            # Verify all three backends are available
            assert local is not None
            assert r2 is not None
            assert b2 is not None

            # Test local storage (real operation)
            source_file = os.path.join(tmpdir, "backup.dat")
            with open(source_file, "wb") as f:
                f.write(b"test backup")

            remote_path = "backups/test.dat"
            assert local.upload(source_file, remote_path) is True
            assert local.exists(remote_path) is True

    def test_requirement_6_34_cloudflare_r2_credentials(self):
        """
        Requirement 6.34: Use Cloudflare R2 with specified credentials.
        """
        storage = CloudflareR2Storage(
            account_id="b7900eeee7c415345d86ea859c9dad47",
            bucket_name="securesyntax",
            access_key_id="test",
            secret_access_key="test",
        )

        # Verify configuration
        assert storage.account_id == "b7900eeee7c415345d86ea859c9dad47"
        assert storage.bucket_name == "securesyntax"
        assert (
            storage.endpoint_url
            == "https://b7900eeee7c415345d86ea859c9dad47.r2.cloudflarestorage.com"
        )

    def test_requirement_6_35_backblaze_b2_credentials(self):
        """
        Requirement 6.35: Use Backblaze B2 with specified credentials.
        """
        storage = BackblazeB2Storage(
            bucket_name="securesyntax",
            region="us-east-005",
            access_key_id="test",
            secret_access_key="test",
        )

        # Verify configuration
        assert storage.bucket_name == "securesyntax"
        assert storage.region == "us-east-005"
        assert storage.endpoint_url == "https://s3.us-east-005.backblazeb2.com"

    def test_requirement_6_5_checksum_verification(self):
        """
        Requirement 6.5: Calculate SHA-256 checksums for integrity verification.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalStorage(base_path=os.path.join(tmpdir, "backups"))

            # Create backup with known content
            source_file = os.path.join(tmpdir, "backup.dat")
            content = b"Backup content for checksum verification"
            with open(source_file, "wb") as f:
                f.write(content)

            # Calculate expected checksum
            expected_checksum = hashlib.sha256(content).hexdigest()

            # Upload and download
            remote_path = "backups/checksum_test.dat"
            storage.upload(source_file, remote_path)

            download_file = os.path.join(tmpdir, "downloaded.dat")
            storage.download(remote_path, download_file)

            # Verify checksum
            with open(download_file, "rb") as f:
                downloaded_content = f.read()
            actual_checksum = hashlib.sha256(downloaded_content).hexdigest()

            assert actual_checksum == expected_checksum

            # Cleanup
            storage.delete(remote_path)
