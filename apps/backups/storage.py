"""
Storage backends for the backup system.

This module provides three storage backends for triple-redundant backup storage:
1. LocalStorage - Local filesystem storage (30-day retention)
2. CloudflareR2Storage - Cloudflare R2 object storage (1-year retention)
3. BackblazeB2Storage - Backblaze B2 object storage (1-year retention)

All backends implement a common interface with upload, download, exists, and delete methods.
"""

import logging
from pathlib import Path
from typing import Optional

from django.conf import settings

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class StorageBackend:
    """Base class for storage backends."""

    def upload(self, local_path: str, remote_path: str) -> bool:
        """
        Upload a file to the storage backend.

        Args:
            local_path: Path to the local file to upload
            remote_path: Destination path in the storage backend

        Returns:
            True if upload succeeded, False otherwise
        """
        raise NotImplementedError

    def download(self, remote_path: str, local_path: str) -> bool:
        """
        Download a file from the storage backend.

        Args:
            remote_path: Path to the file in the storage backend
            local_path: Destination path for the downloaded file

        Returns:
            True if download succeeded, False otherwise
        """
        raise NotImplementedError

    def exists(self, remote_path: str) -> bool:
        """
        Check if a file exists in the storage backend.

        Args:
            remote_path: Path to check in the storage backend

        Returns:
            True if file exists, False otherwise
        """
        raise NotImplementedError

    def delete(self, remote_path: str) -> bool:
        """
        Delete a file from the storage backend.

        Args:
            remote_path: Path to the file to delete

        Returns:
            True if deletion succeeded, False otherwise
        """
        raise NotImplementedError

    def get_size(self, remote_path: str) -> Optional[int]:
        """
        Get the size of a file in bytes.

        Args:
            remote_path: Path to the file in the storage backend

        Returns:
            Size in bytes, or None if file doesn't exist
        """
        raise NotImplementedError


class LocalStorage(StorageBackend):
    """
    Local filesystem storage backend.

    Stores backups on the local filesystem with 30-day retention.
    Used for quick access and as the first line of backup storage.
    """

    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize local storage backend.

        Args:
            base_path: Base directory for storing backups.
                      Defaults to settings.BACKUP_LOCAL_PATH or '/var/backups/jewelry-shop'
        """
        self.base_path = Path(
            base_path or getattr(settings, "BACKUP_LOCAL_PATH", "/var/backups/jewelry-shop")
        )
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalStorage initialized with base_path: {self.base_path}")

    def _get_full_path(self, remote_path: str) -> Path:
        """Get the full local path for a remote path."""
        return self.base_path / remote_path

    def upload(self, local_path: str, remote_path: str) -> bool:
        """
        Copy a file to local storage.

        Args:
            local_path: Path to the source file
            remote_path: Relative path within the backup directory

        Returns:
            True if copy succeeded, False otherwise
        """
        try:
            source = Path(local_path)
            destination = self._get_full_path(remote_path)

            # Create parent directories if they don't exist
            destination.parent.mkdir(parents=True, exist_ok=True)

            # Copy the file
            import shutil

            shutil.copy2(source, destination)

            logger.info(f"LocalStorage: Uploaded {local_path} to {destination}")
            return True

        except Exception as e:
            logger.error(f"LocalStorage: Failed to upload {local_path} to {remote_path}: {e}")
            return False

    def download(self, remote_path: str, local_path: str) -> bool:
        """
        Copy a file from local storage.

        Args:
            remote_path: Relative path within the backup directory
            local_path: Destination path for the file

        Returns:
            True if copy succeeded, False otherwise
        """
        try:
            source = self._get_full_path(remote_path)
            destination = Path(local_path)

            if not source.exists():
                logger.error(f"LocalStorage: File not found: {source}")
                return False

            # Create parent directories if they don't exist
            destination.parent.mkdir(parents=True, exist_ok=True)

            # Copy the file
            import shutil

            shutil.copy2(source, destination)

            logger.info(f"LocalStorage: Downloaded {source} to {local_path}")
            return True

        except Exception as e:
            logger.error(f"LocalStorage: Failed to download {remote_path} to {local_path}: {e}")
            return False

    def exists(self, remote_path: str) -> bool:
        """
        Check if a file exists in local storage.

        Args:
            remote_path: Relative path within the backup directory

        Returns:
            True if file exists, False otherwise
        """
        full_path = self._get_full_path(remote_path)
        exists = full_path.exists() and full_path.is_file()
        logger.debug(f"LocalStorage: File {remote_path} exists: {exists}")
        return exists

    def delete(self, remote_path: str) -> bool:
        """
        Delete a file from local storage.

        Args:
            remote_path: Relative path within the backup directory

        Returns:
            True if deletion succeeded, False otherwise
        """
        try:
            full_path = self._get_full_path(remote_path)

            if not full_path.exists():
                logger.warning(f"LocalStorage: File not found for deletion: {full_path}")
                return True  # Already deleted

            full_path.unlink()
            logger.info(f"LocalStorage: Deleted {full_path}")
            return True

        except Exception as e:
            logger.error(f"LocalStorage: Failed to delete {remote_path}: {e}")
            return False

    def get_size(self, remote_path: str) -> Optional[int]:
        """
        Get the size of a file in bytes.

        Args:
            remote_path: Relative path within the backup directory

        Returns:
            Size in bytes, or None if file doesn't exist
        """
        try:
            full_path = self._get_full_path(remote_path)
            if full_path.exists():
                return full_path.stat().st_size
            return None
        except Exception as e:
            logger.error(f"LocalStorage: Failed to get size of {remote_path}: {e}")
            return None


class CloudflareR2Storage(StorageBackend):
    """
    Cloudflare R2 object storage backend.

    Stores backups in Cloudflare R2 with 1-year retention.
    R2 is S3-compatible and provides fast, cost-effective object storage.

    Configuration:
    - Account ID: b7900eeee7c415345d86ea859c9dad47
    - Bucket: securesyntax
    - Endpoint: https://b7900eeee7c415345d86ea859c9dad47.r2.cloudflarestorage.com
    """

    def __init__(
        self,
        account_id: Optional[str] = None,
        bucket_name: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
    ):
        """
        Initialize Cloudflare R2 storage backend.

        Args:
            account_id: Cloudflare account ID (defaults to settings.R2_ACCOUNT_ID)
            bucket_name: R2 bucket name (defaults to settings.R2_BUCKET_NAME)
            access_key_id: R2 access key ID (defaults to settings.R2_ACCESS_KEY_ID)
            secret_access_key: R2 secret access key (defaults to settings.R2_SECRET_ACCESS_KEY)
        """
        self.account_id = account_id or getattr(
            settings, "R2_ACCOUNT_ID", "b7900eeee7c415345d86ea859c9dad47"
        )
        self.bucket_name = bucket_name or getattr(settings, "R2_BUCKET_NAME", "securesyntax")
        self.access_key_id = access_key_id or getattr(settings, "R2_ACCESS_KEY_ID", "")
        self.secret_access_key = secret_access_key or getattr(settings, "R2_SECRET_ACCESS_KEY", "")

        # Construct R2 endpoint URL
        self.endpoint_url = f"https://{self.account_id}.r2.cloudflarestorage.com"

        # Initialize boto3 S3 client for R2
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name="auto",  # R2 uses 'auto' for region
        )

        logger.info(f"CloudflareR2Storage initialized with bucket: {self.bucket_name}")

    def upload(self, local_path: str, remote_path: str) -> bool:
        """
        Upload a file to Cloudflare R2.

        Args:
            local_path: Path to the local file to upload
            remote_path: Destination key in the R2 bucket

        Returns:
            True if upload succeeded, False otherwise
        """
        try:
            with open(local_path, "rb") as file:
                self.client.upload_fileobj(
                    file,
                    self.bucket_name,
                    remote_path,
                    ExtraArgs={
                        "Metadata": {
                            "uploaded-from": "jewelry-shop-backup-system",
                        }
                    },
                )

            logger.info(f"CloudflareR2Storage: Uploaded {local_path} to {remote_path}")
            return True

        except ClientError as e:
            logger.error(
                f"CloudflareR2Storage: Failed to upload {local_path} to {remote_path}: {e}"
            )
            return False
        except Exception as e:
            logger.error(f"CloudflareR2Storage: Unexpected error uploading {local_path}: {e}")
            return False

    def download(self, remote_path: str, local_path: str) -> bool:
        """
        Download a file from Cloudflare R2.

        Args:
            remote_path: Key of the file in the R2 bucket
            local_path: Destination path for the downloaded file

        Returns:
            True if download succeeded, False otherwise
        """
        try:
            # Create parent directories if they don't exist
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)

            with open(local_path, "wb") as file:
                self.client.download_fileobj(self.bucket_name, remote_path, file)

            logger.info(f"CloudflareR2Storage: Downloaded {remote_path} to {local_path}")
            return True

        except ClientError as e:
            logger.error(
                f"CloudflareR2Storage: Failed to download {remote_path} to {local_path}: {e}"
            )
            return False
        except Exception as e:
            logger.error(f"CloudflareR2Storage: Unexpected error downloading {remote_path}: {e}")
            return False

    def exists(self, remote_path: str) -> bool:
        """
        Check if a file exists in Cloudflare R2.

        Args:
            remote_path: Key of the file in the R2 bucket

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=remote_path)
            logger.debug(f"CloudflareR2Storage: File {remote_path} exists")
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                logger.debug(f"CloudflareR2Storage: File {remote_path} does not exist")
                return False
            logger.error(f"CloudflareR2Storage: Error checking existence of {remote_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"CloudflareR2Storage: Unexpected error checking {remote_path}: {e}")
            return False

    def delete(self, remote_path: str) -> bool:
        """
        Delete a file from Cloudflare R2.

        Args:
            remote_path: Key of the file to delete

        Returns:
            True if deletion succeeded, False otherwise
        """
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=remote_path)
            logger.info(f"CloudflareR2Storage: Deleted {remote_path}")
            return True

        except ClientError as e:
            logger.error(f"CloudflareR2Storage: Failed to delete {remote_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"CloudflareR2Storage: Unexpected error deleting {remote_path}: {e}")
            return False

    def get_size(self, remote_path: str) -> Optional[int]:
        """
        Get the size of a file in bytes.

        Args:
            remote_path: Key of the file in the R2 bucket

        Returns:
            Size in bytes, or None if file doesn't exist
        """
        try:
            response = self.client.head_object(Bucket=self.bucket_name, Key=remote_path)
            return response["ContentLength"]
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return None
            logger.error(f"CloudflareR2Storage: Error getting size of {remote_path}: {e}")
            return None
        except Exception as e:
            logger.error(
                f"CloudflareR2Storage: Unexpected error getting size of {remote_path}: {e}"
            )
            return None


class BackblazeB2Storage(StorageBackend):
    """
    Backblaze B2 object storage backend.

    Stores backups in Backblaze B2 with 1-year retention.
    B2 is S3-compatible and provides cost-effective long-term storage.

    Configuration:
    - Bucket: securesyntax
    - Region: us-east-005
    - Endpoint: https://s3.us-east-005.backblazeb2.com
    - Bucket ID: 2a0cfb4aa9f8f8f29c820b18
    """

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        region: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
    ):
        """
        Initialize Backblaze B2 storage backend.

        Args:
            bucket_name: B2 bucket name (defaults to settings.B2_BUCKET_NAME)
            region: B2 region (defaults to settings.B2_REGION)
            access_key_id: B2 access key ID (defaults to settings.B2_ACCESS_KEY_ID)
            secret_access_key: B2 secret access key (defaults to settings.B2_SECRET_ACCESS_KEY)
        """
        self.bucket_name = bucket_name or getattr(settings, "B2_BUCKET_NAME", "securesyntax")
        self.region = region or getattr(settings, "B2_REGION", "us-east-005")
        self.access_key_id = access_key_id or getattr(settings, "B2_ACCESS_KEY_ID", "")
        self.secret_access_key = secret_access_key or getattr(settings, "B2_SECRET_ACCESS_KEY", "")

        # Construct B2 endpoint URL
        self.endpoint_url = f"https://s3.{self.region}.backblazeb2.com"

        # Initialize boto3 S3 client for B2
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region,
        )

        logger.info(
            f"BackblazeB2Storage initialized with bucket: {self.bucket_name}, region: {self.region}"
        )

    def upload(self, local_path: str, remote_path: str) -> bool:
        """
        Upload a file to Backblaze B2.

        Args:
            local_path: Path to the local file to upload
            remote_path: Destination key in the B2 bucket

        Returns:
            True if upload succeeded, False otherwise
        """
        try:
            with open(local_path, "rb") as file:
                self.client.upload_fileobj(
                    file,
                    self.bucket_name,
                    remote_path,
                    ExtraArgs={
                        "Metadata": {
                            "uploaded-from": "jewelry-shop-backup-system",
                        }
                    },
                )

            logger.info(f"BackblazeB2Storage: Uploaded {local_path} to {remote_path}")
            return True

        except ClientError as e:
            logger.error(f"BackblazeB2Storage: Failed to upload {local_path} to {remote_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"BackblazeB2Storage: Unexpected error uploading {local_path}: {e}")
            return False

    def download(self, remote_path: str, local_path: str) -> bool:
        """
        Download a file from Backblaze B2.

        Args:
            remote_path: Key of the file in the B2 bucket
            local_path: Destination path for the downloaded file

        Returns:
            True if download succeeded, False otherwise
        """
        try:
            # Create parent directories if they don't exist
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)

            with open(local_path, "wb") as file:
                self.client.download_fileobj(self.bucket_name, remote_path, file)

            logger.info(f"BackblazeB2Storage: Downloaded {remote_path} to {local_path}")
            return True

        except ClientError as e:
            logger.error(
                f"BackblazeB2Storage: Failed to download {remote_path} to {local_path}: {e}"
            )
            return False
        except Exception as e:
            logger.error(f"BackblazeB2Storage: Unexpected error downloading {remote_path}: {e}")
            return False

    def exists(self, remote_path: str) -> bool:
        """
        Check if a file exists in Backblaze B2.

        Args:
            remote_path: Key of the file in the B2 bucket

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=remote_path)
            logger.debug(f"BackblazeB2Storage: File {remote_path} exists")
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                logger.debug(f"BackblazeB2Storage: File {remote_path} does not exist")
                return False
            logger.error(f"BackblazeB2Storage: Error checking existence of {remote_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"BackblazeB2Storage: Unexpected error checking {remote_path}: {e}")
            return False

    def delete(self, remote_path: str) -> bool:
        """
        Delete a file from Backblaze B2.

        Args:
            remote_path: Key of the file to delete

        Returns:
            True if deletion succeeded, False otherwise
        """
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=remote_path)
            logger.info(f"BackblazeB2Storage: Deleted {remote_path}")
            return True

        except ClientError as e:
            logger.error(f"BackblazeB2Storage: Failed to delete {remote_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"BackblazeB2Storage: Unexpected error deleting {remote_path}: {e}")
            return False

    def get_size(self, remote_path: str) -> Optional[int]:
        """
        Get the size of a file in bytes.

        Args:
            remote_path: Key of the file in the B2 bucket

        Returns:
            Size in bytes, or None if file doesn't exist
        """
        try:
            response = self.client.head_object(Bucket=self.bucket_name, Key=remote_path)
            return response["ContentLength"]
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return None
            logger.error(f"BackblazeB2Storage: Error getting size of {remote_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"BackblazeB2Storage: Unexpected error getting size of {remote_path}: {e}")
            return None


def get_storage_backend(backend_type: str) -> StorageBackend:
    """
    Factory function to get a storage backend instance.

    Args:
        backend_type: Type of storage backend ('local', 'r2', or 'b2')

    Returns:
        Instance of the requested storage backend

    Raises:
        ValueError: If backend_type is not recognized
    """
    backend_type = backend_type.lower()

    if backend_type == "local":
        return LocalStorage()
    elif backend_type == "r2":
        return CloudflareR2Storage()
    elif backend_type == "b2":
        return BackblazeB2Storage()
    else:
        raise ValueError(f"Unknown storage backend type: {backend_type}")
