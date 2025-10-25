"""
Tests for backup storage backends.

This test suite validates the storage backend implementations with real file operations.
Tests use real filesystem for LocalStorage and mock boto3 for cloud storage backends.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from apps.backups.storage import (
    BackblazeB2Storage,
    CloudflareR2Storage,
    LocalStorage,
    get_storage_backend,
)


class TestLocalStorage:
    """Test LocalStorage backend with real filesystem operations."""

    def test_init_creates_base_directory(self):
        """Test that LocalStorage creates base directory on initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = os.path.join(tmpdir, "test_backups")
            storage = LocalStorage(base_path=base_path)

            assert storage.base_path == Path(base_path)
            assert storage.base_path.exists()
            assert storage.base_path.is_dir()

    def test_upload_file(self):
        """Test uploading a file to local storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source file
            source_file = os.path.join(tmpdir, "source.txt")
            with open(source_file, "w") as f:
                f.write("Test backup content")

            # Initialize storage
            base_path = os.path.join(tmpdir, "backups")
            storage = LocalStorage(base_path=base_path)

            # Upload file
            result = storage.upload(source_file, "test/backup.txt")

            assert result is True
            assert storage.exists("test/backup.txt")

            # Verify content
            uploaded_path = storage._get_full_path("test/backup.txt")
            with open(uploaded_path, "r") as f:
                content = f.read()
            assert content == "Test backup content"

    def test_upload_creates_parent_directories(self):
        """Test that upload creates parent directories if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source file
            source_file = os.path.join(tmpdir, "source.txt")
            with open(source_file, "w") as f:
                f.write("Test content")

            # Initialize storage
            base_path = os.path.join(tmpdir, "backups")
            storage = LocalStorage(base_path=base_path)

            # Upload to nested path
            result = storage.upload(source_file, "year/month/day/backup.txt")

            assert result is True
            assert storage.exists("year/month/day/backup.txt")

    def test_download_file(self):
        """Test downloading a file from local storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and upload a file
            source_file = os.path.join(tmpdir, "source.txt")
            with open(source_file, "w") as f:
                f.write("Download test content")

            base_path = os.path.join(tmpdir, "backups")
            storage = LocalStorage(base_path=base_path)
            storage.upload(source_file, "test/backup.txt")

            # Download to different location
            download_path = os.path.join(tmpdir, "downloaded.txt")
            result = storage.download("test/backup.txt", download_path)

            assert result is True
            assert os.path.exists(download_path)

            # Verify content
            with open(download_path, "r") as f:
                content = f.read()
            assert content == "Download test content"

    def test_download_nonexistent_file(self):
        """Test downloading a file that doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = os.path.join(tmpdir, "backups")
            storage = LocalStorage(base_path=base_path)

            download_path = os.path.join(tmpdir, "downloaded.txt")
            result = storage.download("nonexistent/file.txt", download_path)

            assert result is False
            assert not os.path.exists(download_path)

    def test_exists_file_present(self):
        """Test exists() returns True for existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and upload a file
            source_file = os.path.join(tmpdir, "source.txt")
            with open(source_file, "w") as f:
                f.write("Test content")

            base_path = os.path.join(tmpdir, "backups")
            storage = LocalStorage(base_path=base_path)
            storage.upload(source_file, "test/backup.txt")

            assert storage.exists("test/backup.txt") is True

    def test_exists_file_absent(self):
        """Test exists() returns False for non-existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = os.path.join(tmpdir, "backups")
            storage = LocalStorage(base_path=base_path)

            assert storage.exists("nonexistent/file.txt") is False

    def test_delete_file(self):
        """Test deleting a file from local storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and upload a file
            source_file = os.path.join(tmpdir, "source.txt")
            with open(source_file, "w") as f:
                f.write("Test content")

            base_path = os.path.join(tmpdir, "backups")
            storage = LocalStorage(base_path=base_path)
            storage.upload(source_file, "test/backup.txt")

            # Verify file exists
            assert storage.exists("test/backup.txt") is True

            # Delete file
            result = storage.delete("test/backup.txt")

            assert result is True
            assert storage.exists("test/backup.txt") is False

    def test_delete_nonexistent_file(self):
        """Test deleting a file that doesn't exist returns True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = os.path.join(tmpdir, "backups")
            storage = LocalStorage(base_path=base_path)

            # Deleting non-existent file should return True (idempotent)
            result = storage.delete("nonexistent/file.txt")
            assert result is True

    def test_get_size(self):
        """Test getting file size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create file with known size
            source_file = os.path.join(tmpdir, "source.txt")
            content = "A" * 1024  # 1 KB
            with open(source_file, "w") as f:
                f.write(content)

            base_path = os.path.join(tmpdir, "backups")
            storage = LocalStorage(base_path=base_path)
            storage.upload(source_file, "test/backup.txt")

            size = storage.get_size("test/backup.txt")
            assert size == 1024

    def test_get_size_nonexistent_file(self):
        """Test getting size of non-existent file returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = os.path.join(tmpdir, "backups")
            storage = LocalStorage(base_path=base_path)

            size = storage.get_size("nonexistent/file.txt")
            assert size is None


class TestCloudflareR2Storage:
    """Test CloudflareR2Storage backend with mocked boto3."""

    @patch("apps.backups.storage.boto3")
    def test_init_creates_client(self, mock_boto3):
        """Test that CloudflareR2Storage initializes boto3 client correctly."""
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        storage = CloudflareR2Storage(
            account_id="test_account",
            bucket_name="test_bucket",
            access_key_id="test_key",
            secret_access_key="test_secret",
        )

        assert storage.account_id == "test_account"
        assert storage.bucket_name == "test_bucket"
        assert storage.endpoint_url == "https://test_account.r2.cloudflarestorage.com"

        mock_boto3.client.assert_called_once_with(
            "s3",
            endpoint_url="https://test_account.r2.cloudflarestorage.com",
            aws_access_key_id="test_key",
            aws_secret_access_key="test_secret",
            region_name="auto",
        )

    @patch("apps.backups.storage.boto3")
    def test_upload_file(self, mock_boto3):
        """Test uploading a file to R2."""
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source file
            source_file = os.path.join(tmpdir, "source.txt")
            with open(source_file, "w") as f:
                f.write("Test R2 upload")

            storage = CloudflareR2Storage()
            result = storage.upload(source_file, "backups/test.txt")

            assert result is True
            mock_client.upload_fileobj.assert_called_once()

    @patch("apps.backups.storage.boto3")
    def test_upload_file_failure(self, mock_boto3):
        """Test upload failure handling."""
        mock_client = Mock()
        mock_client.upload_fileobj.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Internal Server Error"}},
            "upload_fileobj",
        )
        mock_boto3.client.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            source_file = os.path.join(tmpdir, "source.txt")
            with open(source_file, "w") as f:
                f.write("Test content")

            storage = CloudflareR2Storage()
            result = storage.upload(source_file, "backups/test.txt")

            assert result is False

    @patch("apps.backups.storage.boto3")
    def test_download_file(self, mock_boto3):
        """Test downloading a file from R2."""
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            download_path = os.path.join(tmpdir, "downloaded.txt")

            storage = CloudflareR2Storage()
            result = storage.download("backups/test.txt", download_path)

            assert result is True
            mock_client.download_fileobj.assert_called_once()

    @patch("apps.backups.storage.boto3")
    def test_download_file_failure(self, mock_boto3):
        """Test download failure handling."""
        mock_client = Mock()
        mock_client.download_fileobj.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}},
            "download_fileobj",
        )
        mock_boto3.client.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            download_path = os.path.join(tmpdir, "downloaded.txt")

            storage = CloudflareR2Storage()
            result = storage.download("backups/nonexistent.txt", download_path)

            assert result is False

    @patch("apps.backups.storage.boto3")
    def test_exists_file_present(self, mock_boto3):
        """Test exists() returns True when file exists in R2."""
        mock_client = Mock()
        mock_client.head_object.return_value = {"ContentLength": 1024}
        mock_boto3.client.return_value = mock_client

        storage = CloudflareR2Storage()
        result = storage.exists("backups/test.txt")

        assert result is True
        mock_client.head_object.assert_called_once_with(
            Bucket="securesyntax", Key="backups/test.txt"
        )

    @patch("apps.backups.storage.boto3")
    def test_exists_file_absent(self, mock_boto3):
        """Test exists() returns False when file doesn't exist in R2."""
        mock_client = Mock()
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}},
            "head_object",
        )
        mock_boto3.client.return_value = mock_client

        storage = CloudflareR2Storage()
        result = storage.exists("backups/nonexistent.txt")

        assert result is False

    @patch("apps.backups.storage.boto3")
    def test_delete_file(self, mock_boto3):
        """Test deleting a file from R2."""
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        storage = CloudflareR2Storage()
        result = storage.delete("backups/test.txt")

        assert result is True
        mock_client.delete_object.assert_called_once_with(
            Bucket="securesyntax", Key="backups/test.txt"
        )

    @patch("apps.backups.storage.boto3")
    def test_delete_file_failure(self, mock_boto3):
        """Test delete failure handling."""
        mock_client = Mock()
        mock_client.delete_object.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Internal Server Error"}},
            "delete_object",
        )
        mock_boto3.client.return_value = mock_client

        storage = CloudflareR2Storage()
        result = storage.delete("backups/test.txt")

        assert result is False

    @patch("apps.backups.storage.boto3")
    def test_get_size(self, mock_boto3):
        """Test getting file size from R2."""
        mock_client = Mock()
        mock_client.head_object.return_value = {"ContentLength": 2048}
        mock_boto3.client.return_value = mock_client

        storage = CloudflareR2Storage()
        size = storage.get_size("backups/test.txt")

        assert size == 2048

    @patch("apps.backups.storage.boto3")
    def test_get_size_nonexistent_file(self, mock_boto3):
        """Test getting size of non-existent file returns None."""
        mock_client = Mock()
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}},
            "head_object",
        )
        mock_boto3.client.return_value = mock_client

        storage = CloudflareR2Storage()
        size = storage.get_size("backups/nonexistent.txt")

        assert size is None


class TestBackblazeB2Storage:
    """Test BackblazeB2Storage backend with mocked boto3."""

    @patch("apps.backups.storage.boto3")
    def test_init_creates_client(self, mock_boto3):
        """Test that BackblazeB2Storage initializes boto3 client correctly."""
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        storage = BackblazeB2Storage(
            bucket_name="test_bucket",
            region="us-west-001",
            access_key_id="test_key",
            secret_access_key="test_secret",
        )

        assert storage.bucket_name == "test_bucket"
        assert storage.region == "us-west-001"
        assert storage.endpoint_url == "https://s3.us-west-001.backblazeb2.com"

        mock_boto3.client.assert_called_once_with(
            "s3",
            endpoint_url="https://s3.us-west-001.backblazeb2.com",
            aws_access_key_id="test_key",
            aws_secret_access_key="test_secret",
            region_name="us-west-001",
        )

    @patch("apps.backups.storage.boto3")
    def test_upload_file(self, mock_boto3):
        """Test uploading a file to B2."""
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source file
            source_file = os.path.join(tmpdir, "source.txt")
            with open(source_file, "w") as f:
                f.write("Test B2 upload")

            storage = BackblazeB2Storage()
            result = storage.upload(source_file, "backups/test.txt")

            assert result is True
            mock_client.upload_fileobj.assert_called_once()

    @patch("apps.backups.storage.boto3")
    def test_upload_file_failure(self, mock_boto3):
        """Test upload failure handling."""
        mock_client = Mock()
        mock_client.upload_fileobj.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Internal Server Error"}},
            "upload_fileobj",
        )
        mock_boto3.client.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            source_file = os.path.join(tmpdir, "source.txt")
            with open(source_file, "w") as f:
                f.write("Test content")

            storage = BackblazeB2Storage()
            result = storage.upload(source_file, "backups/test.txt")

            assert result is False

    @patch("apps.backups.storage.boto3")
    def test_download_file(self, mock_boto3):
        """Test downloading a file from B2."""
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            download_path = os.path.join(tmpdir, "downloaded.txt")

            storage = BackblazeB2Storage()
            result = storage.download("backups/test.txt", download_path)

            assert result is True
            mock_client.download_fileobj.assert_called_once()

    @patch("apps.backups.storage.boto3")
    def test_exists_file_present(self, mock_boto3):
        """Test exists() returns True when file exists in B2."""
        mock_client = Mock()
        mock_client.head_object.return_value = {"ContentLength": 1024}
        mock_boto3.client.return_value = mock_client

        storage = BackblazeB2Storage()
        result = storage.exists("backups/test.txt")

        assert result is True

    @patch("apps.backups.storage.boto3")
    def test_exists_file_absent(self, mock_boto3):
        """Test exists() returns False when file doesn't exist in B2."""
        mock_client = Mock()
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}},
            "head_object",
        )
        mock_boto3.client.return_value = mock_client

        storage = BackblazeB2Storage()
        result = storage.exists("backups/nonexistent.txt")

        assert result is False

    @patch("apps.backups.storage.boto3")
    def test_delete_file(self, mock_boto3):
        """Test deleting a file from B2."""
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        storage = BackblazeB2Storage()
        result = storage.delete("backups/test.txt")

        assert result is True
        mock_client.delete_object.assert_called_once()

    @patch("apps.backups.storage.boto3")
    def test_get_size(self, mock_boto3):
        """Test getting file size from B2."""
        mock_client = Mock()
        mock_client.head_object.return_value = {"ContentLength": 4096}
        mock_boto3.client.return_value = mock_client

        storage = BackblazeB2Storage()
        size = storage.get_size("backups/test.txt")

        assert size == 4096


class TestStorageBackendFactory:
    """Test the storage backend factory function."""

    @patch("apps.backups.storage.LocalStorage")
    def test_get_local_storage(self, mock_local_storage):
        """Test getting LocalStorage backend."""
        mock_instance = Mock()
        mock_local_storage.return_value = mock_instance

        storage = get_storage_backend("local")
        assert storage == mock_instance
        mock_local_storage.assert_called_once()

    @patch("apps.backups.storage.boto3")
    def test_get_r2_storage(self, mock_boto3):
        """Test getting CloudflareR2Storage backend."""
        mock_boto3.client.return_value = Mock()
        storage = get_storage_backend("r2")
        assert isinstance(storage, CloudflareR2Storage)

    @patch("apps.backups.storage.boto3")
    def test_get_b2_storage(self, mock_boto3):
        """Test getting BackblazeB2Storage backend."""
        mock_boto3.client.return_value = Mock()
        storage = get_storage_backend("b2")
        assert isinstance(storage, BackblazeB2Storage)

    def test_get_invalid_storage(self):
        """Test getting invalid storage backend raises ValueError."""
        with pytest.raises(ValueError, match="Unknown storage backend type"):
            get_storage_backend("invalid")

    @patch("apps.backups.storage.LocalStorage")
    def test_case_insensitive_backend_type(self, mock_local_storage):
        """Test that backend type is case-insensitive."""
        mock_instance = Mock()
        mock_local_storage.return_value = mock_instance

        storage1 = get_storage_backend("LOCAL")
        storage2 = get_storage_backend("Local")
        storage3 = get_storage_backend("local")

        assert storage1 == mock_instance
        assert storage2 == mock_instance
        assert storage3 == mock_instance
        assert mock_local_storage.call_count == 3
