"""
Tests for secrets management system.

Tests cover:
1. Environment file encryption/decryption
2. Key rotation functionality
3. Sensitive value masking
4. Key rotation tracking
"""

import os
import tempfile
from datetime import timedelta
from pathlib import Path

from django.test import TestCase
from django.utils import timezone

import pytest
from cryptography.fernet import Fernet

from apps.core.models import SecretsKeyRotation
from apps.core.secrets_management import EncryptionKeyError, SecretsManagementError, SecretsManager


class SecretsManagerTest(TestCase):
    """Test SecretsManager class."""

    def setUp(self):
        """Set up test environment."""
        # Generate a test master key
        self.test_key = Fernet.generate_key()
        os.environ["SECRETS_MASTER_KEY"] = self.test_key.decode()

        # Create temporary .env file
        self.temp_dir = tempfile.mkdtemp()
        self.env_path = os.path.join(self.temp_dir, ".env")

        with open(self.env_path, "w") as f:
            f.write("# Test .env file\n")
            f.write("DJANGO_SECRET_KEY=test-secret-key-12345\n")
            f.write("DB_PASSWORD=test-db-password\n")
            f.write("API_KEY=test-api-key\n")

    def tearDown(self):
        """Clean up test environment."""
        # Clean up temp files
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

        # Clean up environment
        if "SECRETS_MASTER_KEY" in os.environ:
            del os.environ["SECRETS_MASTER_KEY"]

    def test_initialization(self):
        """Test SecretsManager initialization."""
        manager = SecretsManager()
        self.assertIsNotNone(manager.master_key)
        self.assertIsNotNone(manager.fernet)

    def test_initialization_without_key(self):
        """Test initialization fails without master key."""
        del os.environ["SECRETS_MASTER_KEY"]

        with self.assertRaises(EncryptionKeyError):
            SecretsManager()

    def test_encrypt_env_file(self):
        """Test encrypting .env file."""
        manager = SecretsManager()

        # Encrypt
        encrypted_path = manager.encrypt_env_file(self.env_path)

        # Verify encrypted file exists
        self.assertTrue(Path(encrypted_path).exists())

        # Verify encrypted file is different from original
        with open(self.env_path, "rb") as f1, open(encrypted_path, "rb") as f2:
            original = f1.read()
            encrypted = f2.read()
            self.assertNotEqual(original, encrypted)

    def test_decrypt_env_file(self):
        """Test decrypting .env file."""
        manager = SecretsManager()

        # Encrypt first
        encrypted_path = manager.encrypt_env_file(self.env_path)

        # Decrypt
        decrypted_path = os.path.join(self.temp_dir, ".env.decrypted")
        result_path = manager.decrypt_env_file(encrypted_path, decrypted_path)

        # Verify decrypted file exists
        self.assertTrue(Path(result_path).exists())

        # Verify content matches original
        with open(self.env_path, "r") as f1, open(result_path, "r") as f2:
            original = f1.read()
            decrypted = f2.read()
            self.assertEqual(original, decrypted)

    def test_decrypt_with_wrong_key(self):
        """Test decryption fails with wrong key."""
        manager = SecretsManager()

        # Encrypt with first key
        encrypted_path = manager.encrypt_env_file(self.env_path)

        # Change to different key
        new_key = Fernet.generate_key()
        os.environ["SECRETS_MASTER_KEY"] = new_key.decode()

        # Try to decrypt with wrong key
        manager2 = SecretsManager()
        with self.assertRaises(SecretsManagementError):
            manager2.decrypt_env_file(encrypted_path)

    def test_encrypt_nonexistent_file(self):
        """Test encrypting nonexistent file raises error."""
        manager = SecretsManager()

        with self.assertRaises(FileNotFoundError):
            manager.encrypt_env_file("/nonexistent/file.env")

    def test_decrypt_nonexistent_file(self):
        """Test decrypting nonexistent file raises error."""
        manager = SecretsManager()

        with self.assertRaises(FileNotFoundError):
            manager.decrypt_env_file("/nonexistent/file.encrypted")

    def test_generate_new_key(self):
        """Test generating new encryption key."""
        key = SecretsManager.generate_new_key()

        # Verify key is valid
        self.assertIsInstance(key, str)
        self.assertTrue(len(key) > 0)

        # Verify key can be used with Fernet
        key_bytes = key.encode("utf-8")
        fernet = Fernet(key_bytes)
        self.assertIsNotNone(fernet)

    def test_mask_sensitive_value(self):
        """Test masking sensitive values."""
        # Test sensitive key
        masked = SecretsManager.mask_sensitive_value("DJANGO_SECRET_KEY", "my-secret-key-12345")
        self.assertEqual(masked, "my-s...2345")

        # Test non-sensitive key
        masked = SecretsManager.mask_sensitive_value("DEBUG", "True")
        self.assertEqual(masked, "True")

        # Test short value
        masked = SecretsManager.mask_sensitive_value("API_KEY", "short")
        self.assertEqual(masked, "***")

    def test_mask_env_dict(self):
        """Test masking environment dictionary."""
        env_dict = {
            "DJANGO_SECRET_KEY": "my-secret-key-12345",
            "DEBUG": "True",
            "DB_PASSWORD": "my-password-12345",
            "ALLOWED_HOSTS": "localhost",
        }

        masked = SecretsManager.mask_env_dict(env_dict)

        # Verify sensitive values are masked
        self.assertEqual(masked["DJANGO_SECRET_KEY"], "my-s...2345")
        self.assertEqual(masked["DB_PASSWORD"], "my-p...2345")

        # Verify non-sensitive values are not masked
        self.assertEqual(masked["DEBUG"], "True")
        self.assertEqual(masked["ALLOWED_HOSTS"], "localhost")

    def test_parse_env_file(self):
        """Test parsing .env file."""
        parsed = SecretsManager.parse_env_file(self.env_path)

        # Verify parsed values
        self.assertEqual(parsed["DJANGO_SECRET_KEY"], "test-secret-key-12345")
        self.assertEqual(parsed["DB_PASSWORD"], "test-db-password")
        self.assertEqual(parsed["API_KEY"], "test-api-key")

        # Verify comments are ignored
        self.assertNotIn("# Test .env file", parsed)

    def test_should_rotate_key(self):
        """Test key rotation schedule check."""
        manager = SecretsManager()

        # Test recent rotation (should not rotate)
        recent_date = timezone.now() - timedelta(days=30)
        self.assertFalse(manager.should_rotate_key(recent_date))

        # Test old rotation (should rotate)
        old_date = timezone.now() - timedelta(days=100)
        self.assertTrue(manager.should_rotate_key(old_date))

        # Test exactly 90 days (should rotate)
        ninety_days = timezone.now() - timedelta(days=90)
        self.assertTrue(manager.should_rotate_key(ninety_days))

    def test_get_next_rotation_date(self):
        """Test calculating next rotation date."""
        manager = SecretsManager()

        last_rotation = timezone.now() - timedelta(days=30)
        next_rotation = manager.get_next_rotation_date(last_rotation)

        # Should be 60 days from now (90 - 30)
        expected = last_rotation + timedelta(days=90)
        self.assertEqual(next_rotation.date(), expected.date())


class KeyRotationTest(TestCase):
    """Test key rotation functionality."""

    def setUp(self):
        """Set up test environment."""
        # Generate test keys
        self.old_key = Fernet.generate_key()
        self.new_key = Fernet.generate_key()
        os.environ["SECRETS_MASTER_KEY"] = self.old_key.decode()

        # Create temporary .env file
        self.temp_dir = tempfile.mkdtemp()
        self.env_path = os.path.join(self.temp_dir, ".env")

        with open(self.env_path, "w") as f:
            f.write("DJANGO_SECRET_KEY=test-secret-key\n")
            f.write("DB_PASSWORD=test-password\n")

    def tearDown(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

        if "SECRETS_MASTER_KEY" in os.environ:
            del os.environ["SECRETS_MASTER_KEY"]

    def test_rotate_master_key(self):
        """Test rotating master encryption key."""
        manager = SecretsManager()

        # Encrypt with old key first
        encrypted_path = manager.encrypt_env_file(self.env_path)
        self.assertTrue(Path(encrypted_path).exists())

        # Rotate key
        new_encrypted_path, backup_path = manager.rotate_master_key(
            self.new_key, self.env_path, backup=True
        )

        # Verify new encrypted file exists
        self.assertTrue(Path(new_encrypted_path).exists())

        # Verify backup exists
        self.assertIsNotNone(backup_path)
        self.assertTrue(Path(backup_path).exists())

        # Verify can decrypt with new key
        decrypted_path = os.path.join(self.temp_dir, ".env.test")
        manager.decrypt_env_file(new_encrypted_path, decrypted_path)

        # Verify content matches original
        with open(self.env_path, "r") as f1, open(decrypted_path, "r") as f2:
            self.assertEqual(f1.read(), f2.read())

    def test_rotate_key_without_backup(self):
        """Test key rotation without backup."""
        manager = SecretsManager()

        # Encrypt with old key
        manager.encrypt_env_file(self.env_path)

        # Rotate without backup
        new_encrypted_path, backup_path = manager.rotate_master_key(
            self.new_key, self.env_path, backup=False
        )

        # Verify no backup was created
        self.assertIsNone(backup_path)

        # Verify new encrypted file exists
        self.assertTrue(Path(new_encrypted_path).exists())


class SecretsKeyRotationModelTest(TestCase):
    """Test SecretsKeyRotation model."""

    def test_create_rotation_record(self):
        """Test creating key rotation record."""
        rotation = SecretsKeyRotation.objects.create(
            status=SecretsKeyRotation.INITIATED,
            old_key_fingerprint="old_fingerprint_123",
            new_key_fingerprint="new_fingerprint_456",
            rotation_reason="Quarterly rotation",
        )

        self.assertIsNotNone(rotation.id)
        self.assertEqual(rotation.status, SecretsKeyRotation.INITIATED)
        self.assertIsNotNone(rotation.rotation_date)

    def test_is_overdue(self):
        """Test checking if rotation is overdue."""
        # Create completed rotation with past due date
        rotation = SecretsKeyRotation.objects.create(
            status=SecretsKeyRotation.COMPLETED,
            old_key_fingerprint="old",
            new_key_fingerprint="new",
            rotation_reason="Test",
            completed_at=timezone.now(),
            next_rotation_due=timezone.now() - timedelta(days=1),
        )

        self.assertTrue(rotation.is_overdue())

        # Create rotation with future due date
        rotation2 = SecretsKeyRotation.objects.create(
            status=SecretsKeyRotation.COMPLETED,
            old_key_fingerprint="old",
            new_key_fingerprint="new",
            rotation_reason="Test",
            completed_at=timezone.now(),
            next_rotation_due=timezone.now() + timedelta(days=30),
        )

        self.assertFalse(rotation2.is_overdue())

    def test_duration_seconds(self):
        """Test calculating rotation duration."""
        start_time = timezone.now()
        end_time = start_time + timedelta(seconds=120)

        rotation = SecretsKeyRotation.objects.create(
            status=SecretsKeyRotation.COMPLETED,
            old_key_fingerprint="old",
            new_key_fingerprint="new",
            rotation_reason="Test",
            rotation_date=start_time,
            completed_at=end_time,
        )

        duration = rotation.duration_seconds()
        # Allow small floating point differences
        self.assertAlmostEqual(duration, 120.0, places=0)

    def test_rotation_without_completion(self):
        """Test rotation record without completion time."""
        rotation = SecretsKeyRotation.objects.create(
            status=SecretsKeyRotation.IN_PROGRESS,
            old_key_fingerprint="old",
            new_key_fingerprint="new",
            rotation_reason="Test",
        )

        # Duration should be None if not completed
        self.assertIsNone(rotation.duration_seconds())

        # Should not be overdue if not completed
        self.assertFalse(rotation.is_overdue())


@pytest.mark.django_db
class TestSecretsManagementIntegration:
    """Integration tests for secrets management."""

    def test_full_encryption_workflow(self, tmp_path):
        """Test complete encryption workflow."""
        # Set up master key
        master_key = Fernet.generate_key()
        os.environ["SECRETS_MASTER_KEY"] = master_key.decode()

        try:
            # Create .env file
            env_file = tmp_path / ".env"
            env_file.write_text("SECRET_KEY=my-secret\nDB_PASSWORD=my-password\n")

            # Initialize manager
            manager = SecretsManager()

            # Encrypt
            encrypted_path = manager.encrypt_env_file(str(env_file))
            assert Path(encrypted_path).exists()

            # Decrypt
            decrypted_path = tmp_path / ".env.decrypted"
            manager.decrypt_env_file(encrypted_path, str(decrypted_path))

            # Verify content
            assert env_file.read_text() == decrypted_path.read_text()

        finally:
            if "SECRETS_MASTER_KEY" in os.environ:
                del os.environ["SECRETS_MASTER_KEY"]

    def test_key_rotation_workflow(self, tmp_path):
        """Test complete key rotation workflow."""
        # Set up old key
        old_key = Fernet.generate_key()
        os.environ["SECRETS_MASTER_KEY"] = old_key.decode()

        try:
            # Create and encrypt .env file
            env_file = tmp_path / ".env"
            env_file.write_text("SECRET_KEY=my-secret\n")

            manager = SecretsManager()
            manager.encrypt_env_file(str(env_file))

            # Generate new key
            new_key = Fernet.generate_key()

            # Rotate
            new_encrypted, backup = manager.rotate_master_key(new_key, str(env_file), backup=True)

            # Verify backup exists
            assert backup is not None
            assert Path(backup).exists()

            # Verify can decrypt with new key
            decrypted = tmp_path / ".env.test"
            manager.decrypt_env_file(new_encrypted, str(decrypted))
            assert env_file.read_text() == decrypted.read_text()

        finally:
            if "SECRETS_MASTER_KEY" in os.environ:
                del os.environ["SECRETS_MASTER_KEY"]
