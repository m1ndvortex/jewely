"""
Secrets Management System

This module provides comprehensive secrets management including:
1. Environment variable encryption/decryption
2. Quarterly key rotation with audit trail
3. Secure key storage and handling
4. Secrets masking in logs and error reports

Security Features:
- AES-256 encryption using Fernet (CBC mode with HMAC-SHA256)
- Master key stored in environment variable (not in .env file)
- Encrypted .env files safe to commit to version control
- Automatic key rotation tracking
- Audit logging for all key operations
"""

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

from django.conf import settings
from django.utils import timezone

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


class SecretsManagementError(Exception):
    """Base exception for secrets management errors."""

    pass


class KeyRotationError(SecretsManagementError):
    """Raised when key rotation fails."""

    pass


class EncryptionKeyError(SecretsManagementError):
    """Raised when encryption key is invalid or missing."""

    pass


# Sensitive keys that should be masked in logs
SENSITIVE_KEYS = {
    "DJANGO_SECRET_KEY",
    "DB_SUPERUSER_PASSWORD",
    "APP_DB_PASSWORD",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_ACCOUNT_SID",
    "GOLDAPI_KEY",
    "METALS_API_KEY",
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "BACKUP_ENCRYPTION_KEY",
    "SECRETS_MASTER_KEY",
    "GRAFANA_ADMIN_PASSWORD",
    "AWS_SECRET_ACCESS_KEY",
    "CLOUDFLARE_R2_SECRET_KEY",
    "BACKBLAZE_B2_APPLICATION_KEY",
}


class SecretsManager:
    """
    Manages encryption, decryption, and rotation of secrets.

    The master encryption key is stored in the SECRETS_MASTER_KEY environment
    variable and should never be stored in the .env file itself.
    """

    def __init__(self):
        """Initialize the secrets manager."""
        self.master_key = self._get_master_key()
        self.fernet = Fernet(self.master_key)

    def _get_master_key(self) -> bytes:
        """
        Get the master encryption key from environment.

        The master key should be:
        1. Stored in SECRETS_MASTER_KEY environment variable
        2. Generated with: Fernet.generate_key()
        3. Kept secure and never committed to version control

        Returns:
            Master encryption key as bytes

        Raises:
            EncryptionKeyError: If master key is not configured
        """
        # Try to get from environment variable
        key = os.environ.get("SECRETS_MASTER_KEY")

        if not key:
            # Try to get from Django settings (for development)
            key = getattr(settings, "SECRETS_MASTER_KEY", None)

        if not key:
            raise EncryptionKeyError(
                "SECRETS_MASTER_KEY not found in environment. "
                "Generate a key with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )

        # Convert string to bytes if necessary
        if isinstance(key, str):
            key = key.encode("utf-8")

        # Validate key format
        try:
            Fernet(key)
        except Exception as e:
            raise EncryptionKeyError(f"Invalid master key format: {e}")

        return key

    def encrypt_env_file(self, env_path: str, output_path: Optional[str] = None) -> str:
        """
        Encrypt an .env file.

        Args:
            env_path: Path to the .env file to encrypt
            output_path: Path for encrypted file (defaults to env_path + '.encrypted')

        Returns:
            Path to the encrypted file

        Raises:
            FileNotFoundError: If .env file doesn't exist
            SecretsManagementError: If encryption fails
        """
        try:
            env_file = Path(env_path)

            if not env_file.exists():
                raise FileNotFoundError(f".env file not found: {env_path}")

            # Default output path
            if output_path is None:
                output_path = f"{env_path}.encrypted"

            # Read .env file
            with open(env_file, "rb") as f:
                plaintext = f.read()

            # Encrypt
            ciphertext = self.fernet.encrypt(plaintext)

            # Write encrypted file
            with open(output_path, "wb") as f:
                f.write(ciphertext)

            logger.info(f"Encrypted {env_path} -> {output_path}")

            return output_path

        except FileNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to encrypt .env file: {e}")
            raise SecretsManagementError(f"Encryption failed: {e}") from e

    def decrypt_env_file(self, encrypted_path: str, output_path: Optional[str] = None) -> str:
        """
        Decrypt an encrypted .env file.

        Args:
            encrypted_path: Path to the encrypted .env file
            output_path: Path for decrypted file (defaults to removing .encrypted)

        Returns:
            Path to the decrypted file

        Raises:
            FileNotFoundError: If encrypted file doesn't exist
            SecretsManagementError: If decryption fails
        """
        try:
            encrypted_file = Path(encrypted_path)

            if not encrypted_file.exists():
                raise FileNotFoundError(f"Encrypted file not found: {encrypted_path}")

            # Default output path
            if output_path is None:
                if encrypted_path.endswith(".encrypted"):
                    output_path = encrypted_path[:-10]  # Remove .encrypted
                else:
                    output_path = f"{encrypted_path}.decrypted"

            # Read encrypted file
            with open(encrypted_file, "rb") as f:
                ciphertext = f.read()

            # Decrypt
            try:
                plaintext = self.fernet.decrypt(ciphertext)
            except InvalidToken:
                raise SecretsManagementError(
                    "Invalid encryption key or corrupted file. "
                    "Ensure SECRETS_MASTER_KEY is correct."
                )

            # Write decrypted file
            with open(output_path, "wb") as f:
                f.write(plaintext)

            logger.info(f"Decrypted {encrypted_path} -> {output_path}")

            return output_path

        except FileNotFoundError:
            raise
        except SecretsManagementError:
            raise
        except Exception as e:
            logger.error(f"Failed to decrypt .env file: {e}")
            raise SecretsManagementError(f"Decryption failed: {e}") from e

    def rotate_master_key(
        self, new_key: bytes, env_path: str = ".env", backup: bool = True
    ) -> Tuple[str, str]:
        """
        Rotate the master encryption key.

        This process:
        1. Decrypts .env with old key
        2. Encrypts .env with new key
        3. Creates backup of old encrypted file
        4. Updates encrypted file with new encryption

        Args:
            new_key: New master encryption key
            env_path: Path to .env file
            backup: Whether to backup old encrypted file

        Returns:
            Tuple of (new_encrypted_path, backup_path)

        Raises:
            KeyRotationError: If rotation fails
        """
        try:
            encrypted_path = f"{env_path}.encrypted"
            backup_path = None

            # Step 1: Backup old encrypted file if requested
            if backup and Path(encrypted_path).exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"{encrypted_path}.backup_{timestamp}"
                Path(encrypted_path).rename(backup_path)
                logger.info(f"Backed up old encrypted file to {backup_path}")

            # Step 2: Decrypt with old key
            if Path(encrypted_path).exists() or backup_path:
                source = backup_path if backup_path else encrypted_path
                decrypted_path = self.decrypt_env_file(source, env_path)
                logger.info("Decrypted .env file with old key")
            else:
                # No encrypted file exists, use plain .env
                if not Path(env_path).exists():
                    raise KeyRotationError(f".env file not found: {env_path}")
                decrypted_path = env_path

            # Step 3: Create new Fernet instance with new key
            new_fernet = Fernet(new_key)
            old_fernet = self.fernet
            self.fernet = new_fernet
            self.master_key = new_key

            # Step 4: Encrypt with new key
            new_encrypted_path = self.encrypt_env_file(decrypted_path, encrypted_path)
            logger.info("Encrypted .env file with new key")

            # Step 5: Verify new encryption works
            try:
                self.decrypt_env_file(new_encrypted_path, f"{env_path}.test")
                Path(f"{env_path}.test").unlink()
                logger.info("Verified new encryption key works")
            except Exception as e:
                # Rollback
                self.fernet = old_fernet
                self.master_key = self._get_master_key()
                if backup_path:
                    Path(backup_path).rename(encrypted_path)
                raise KeyRotationError(f"New key verification failed: {e}")

            logger.info(
                f"Successfully rotated master key. New encrypted file: {new_encrypted_path}"
            )

            return new_encrypted_path, backup_path

        except Exception as e:
            logger.error(f"Key rotation failed: {e}")
            raise KeyRotationError(f"Failed to rotate key: {e}") from e

    @staticmethod
    def generate_new_key() -> str:
        """
        Generate a new Fernet encryption key.

        Returns:
            New encryption key as string
        """
        key = Fernet.generate_key()
        return key.decode("utf-8")

    @staticmethod
    def mask_sensitive_value(key: str, value: str) -> str:
        """
        Mask a sensitive value for logging.

        Args:
            key: The environment variable key
            value: The value to potentially mask

        Returns:
            Masked value if key is sensitive, otherwise original value
        """
        # Check if key contains any sensitive keywords
        key_upper = key.upper()
        is_sensitive = (
            key_upper in SENSITIVE_KEYS
            or "PASSWORD" in key_upper
            or "SECRET" in key_upper
            or "KEY" in key_upper
            or "TOKEN" in key_upper
        )

        if is_sensitive:
            if len(value) <= 8:
                return "***"
            return f"{value[:4]}...{value[-4:]}"
        return value

    @staticmethod
    def mask_env_dict(env_dict: Dict[str, str]) -> Dict[str, str]:
        """
        Mask sensitive values in an environment dictionary.

        Args:
            env_dict: Dictionary of environment variables

        Returns:
            Dictionary with sensitive values masked
        """
        masked = {}
        for key, value in env_dict.items():
            masked[key] = SecretsManager.mask_sensitive_value(key, value)
        return masked

    @staticmethod
    def parse_env_file(env_path: str) -> Dict[str, str]:
        """
        Parse an .env file into a dictionary.

        Args:
            env_path: Path to .env file

        Returns:
            Dictionary of environment variables

        Raises:
            FileNotFoundError: If .env file doesn't exist
        """
        env_dict = {}

        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Parse KEY=VALUE
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]

                    env_dict[key] = value

        return env_dict

    def should_rotate_key(self, last_rotation_date: datetime) -> bool:
        """
        Check if key should be rotated based on quarterly schedule.

        Args:
            last_rotation_date: Date of last key rotation

        Returns:
            True if key should be rotated (>90 days since last rotation)
        """
        days_since_rotation = (timezone.now() - last_rotation_date).days
        return days_since_rotation >= 90

    def get_next_rotation_date(self, last_rotation_date: datetime) -> datetime:
        """
        Calculate next scheduled rotation date (90 days from last rotation).

        Args:
            last_rotation_date: Date of last key rotation

        Returns:
            Next rotation date
        """
        return last_rotation_date + timedelta(days=90)


def mask_sensitive_settings():
    """
    Mask sensitive settings in Django settings for logging.

    This should be called during Django startup to ensure sensitive
    values are never logged in plain text.
    """
    sensitive_settings = [
        "SECRET_KEY",
        "DATABASES",
        "EMAIL_HOST_PASSWORD",
        "AWS_SECRET_ACCESS_KEY",
        "STRIPE_SECRET_KEY",
        "TWILIO_AUTH_TOKEN",
    ]

    for setting_name in sensitive_settings:
        if hasattr(settings, setting_name):
            value = getattr(settings, setting_name)

            # Handle different types
            if isinstance(value, dict):
                # Mask nested dictionary values (like DATABASES)
                masked_value = _mask_dict_recursive(value)
            elif isinstance(value, str):
                masked_value = SecretsManager.mask_sensitive_value(setting_name, value)
            else:
                masked_value = "***"

            # Store masked version for logging
            setattr(settings, f"_MASKED_{setting_name}", masked_value)


def _mask_dict_recursive(d: dict) -> dict:
    """Recursively mask sensitive values in nested dictionaries."""
    masked = {}
    for key, value in d.items():
        if isinstance(value, dict):
            masked[key] = _mask_dict_recursive(value)
        elif isinstance(value, str) and any(
            sensitive in key.upper() for sensitive in ["PASSWORD", "SECRET", "KEY", "TOKEN"]
        ):
            masked[key] = SecretsManager.mask_sensitive_value(key, value)
        else:
            masked[key] = value
    return masked
