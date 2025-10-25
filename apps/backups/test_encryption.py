"""
Tests for backup encryption and compression utilities.

These tests verify:
1. Gzip compression with level 9
2. AES-256 encryption using Fernet
3. SHA-256 checksum calculation
4. Backup verification across storage locations
5. Combined compress-and-encrypt operations
"""

import tempfile
from pathlib import Path

from django.test import TestCase, override_settings

from cryptography.fernet import Fernet

from apps.backups.encryption import (
    EncryptionError,
    calculate_checksum,
    compress_and_encrypt_file,
    compress_file,
    decompress_file,
    decrypt_and_decompress_file,
    decrypt_file,
    encrypt_file,
    get_encryption_key,
    verify_backup_integrity,
    verify_checksum,
)


class EncryptionKeyTests(TestCase):
    """Test encryption key management."""

    def test_get_encryption_key_from_settings(self):
        """Test retrieving encryption key from settings."""
        # Generate a test key
        test_key = Fernet.generate_key()

        with override_settings(BACKUP_ENCRYPTION_KEY=test_key):
            key = get_encryption_key()
            self.assertEqual(key, test_key)

    def test_get_encryption_key_string_conversion(self):
        """Test that string keys are converted to bytes."""
        test_key = Fernet.generate_key().decode("utf-8")

        with override_settings(BACKUP_ENCRYPTION_KEY=test_key):
            key = get_encryption_key()
            self.assertIsInstance(key, bytes)

    def test_get_encryption_key_not_configured(self):
        """Test error when encryption key is not configured."""
        with override_settings(BACKUP_ENCRYPTION_KEY=None):
            with self.assertRaises(ValueError) as context:
                get_encryption_key()
            self.assertIn("not configured", str(context.exception))


class CompressionTests(TestCase):
    """Test file compression and decompression."""

    def setUp(self):
        """Create temporary directory for test files."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary files."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_compress_file_basic(self):
        """Test basic file compression."""
        # Create a test file with compressible content
        test_file = Path(self.temp_dir) / "test.txt"
        test_content = b"This is a test file. " * 1000  # Repeating content compresses well
        test_file.write_bytes(test_content)

        # Compress the file
        compressed_path, original_size, compressed_size = compress_file(str(test_file))

        # Verify compression
        self.assertTrue(Path(compressed_path).exists())
        self.assertEqual(original_size, len(test_content))
        self.assertLess(compressed_size, original_size)
        self.assertTrue(compressed_path.endswith(".gz"))

    def test_compress_file_custom_output(self):
        """Test compression with custom output path."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_bytes(b"Test content")

        output_path = str(Path(self.temp_dir) / "custom.gz")
        compressed_path, _, _ = compress_file(str(test_file), output_path)

        self.assertEqual(compressed_path, output_path)
        self.assertTrue(Path(output_path).exists())

    def test_compress_file_not_found(self):
        """Test compression with non-existent file."""
        with self.assertRaises(FileNotFoundError):
            compress_file("/nonexistent/file.txt")

    def test_decompress_file_basic(self):
        """Test basic file decompression."""
        # Create and compress a test file
        test_file = Path(self.temp_dir) / "test.txt"
        test_content = b"This is test content for decompression"
        test_file.write_bytes(test_content)

        compressed_path, _, _ = compress_file(str(test_file))

        # Decompress the file
        decompressed_path = decompress_file(compressed_path)

        # Verify decompression
        self.assertTrue(Path(decompressed_path).exists())
        self.assertEqual(Path(decompressed_path).read_bytes(), test_content)

    def test_decompress_file_custom_output(self):
        """Test decompression with custom output path."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_bytes(b"Test content")

        compressed_path, _, _ = compress_file(str(test_file))

        output_path = str(Path(self.temp_dir) / "custom_output.txt")
        decompressed_path = decompress_file(compressed_path, output_path)

        self.assertEqual(decompressed_path, output_path)
        self.assertTrue(Path(output_path).exists())

    def test_compress_decompress_roundtrip(self):
        """Test that compress -> decompress preserves content."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_content = b"Original content that should be preserved"
        test_file.write_bytes(test_content)

        # Compress
        compressed_path, _, _ = compress_file(str(test_file))

        # Decompress
        decompressed_path = decompress_file(compressed_path)

        # Verify content is preserved
        self.assertEqual(Path(decompressed_path).read_bytes(), test_content)

    def test_compression_ratio(self):
        """Test that compression achieves good ratio on repetitive data."""
        test_file = Path(self.temp_dir) / "test.txt"
        # Create highly compressible content
        test_content = b"A" * 10000
        test_file.write_bytes(test_content)

        compressed_path, original_size, compressed_size = compress_file(str(test_file))

        # Should achieve at least 90% compression on this data
        compression_ratio = (1 - compressed_size / original_size) * 100
        self.assertGreater(compression_ratio, 90)


class EncryptionTests(TestCase):
    """Test file encryption and decryption."""

    def setUp(self):
        """Create temporary directory and set up encryption key."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_key = Fernet.generate_key()

    def tearDown(self):
        """Clean up temporary files."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_encrypt_file_basic(self):
        """Test basic file encryption."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_content = b"Secret content to encrypt"
        test_file.write_bytes(test_content)

        with override_settings(BACKUP_ENCRYPTION_KEY=self.test_key):
            encrypted_path = encrypt_file(str(test_file))

        # Verify encryption
        self.assertTrue(Path(encrypted_path).exists())
        self.assertTrue(encrypted_path.endswith(".enc"))

        # Verify content is encrypted (not readable as plaintext)
        encrypted_content = Path(encrypted_path).read_bytes()
        self.assertNotEqual(encrypted_content, test_content)

    def test_encrypt_file_custom_output(self):
        """Test encryption with custom output path."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_bytes(b"Test content")

        output_path = str(Path(self.temp_dir) / "custom.enc")

        with override_settings(BACKUP_ENCRYPTION_KEY=self.test_key):
            encrypted_path = encrypt_file(str(test_file), output_path)

        self.assertEqual(encrypted_path, output_path)
        self.assertTrue(Path(output_path).exists())

    def test_encrypt_file_not_found(self):
        """Test encryption with non-existent file."""
        with override_settings(BACKUP_ENCRYPTION_KEY=self.test_key):
            with self.assertRaises(FileNotFoundError):
                encrypt_file("/nonexistent/file.txt")

    def test_decrypt_file_basic(self):
        """Test basic file decryption."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_content = b"Secret content to decrypt"
        test_file.write_bytes(test_content)

        with override_settings(BACKUP_ENCRYPTION_KEY=self.test_key):
            encrypted_path = encrypt_file(str(test_file))
            decrypted_path = decrypt_file(encrypted_path)

        # Verify decryption
        self.assertTrue(Path(decrypted_path).exists())
        self.assertEqual(Path(decrypted_path).read_bytes(), test_content)

    def test_decrypt_file_wrong_key(self):
        """Test decryption with wrong key fails."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_bytes(b"Secret content")

        # Encrypt with one key
        with override_settings(BACKUP_ENCRYPTION_KEY=self.test_key):
            encrypted_path = encrypt_file(str(test_file))

        # Try to decrypt with different key
        wrong_key = Fernet.generate_key()
        with override_settings(BACKUP_ENCRYPTION_KEY=wrong_key):
            with self.assertRaises(EncryptionError) as context:
                decrypt_file(encrypted_path)
            self.assertIn("Invalid encryption key", str(context.exception))

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encrypt -> decrypt preserves content."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_content = b"Original secret content"
        test_file.write_bytes(test_content)

        with override_settings(BACKUP_ENCRYPTION_KEY=self.test_key):
            encrypted_path = encrypt_file(str(test_file))
            decrypted_path = decrypt_file(encrypted_path)

        # Verify content is preserved
        self.assertEqual(Path(decrypted_path).read_bytes(), test_content)


class ChecksumTests(TestCase):
    """Test checksum calculation and verification."""

    def setUp(self):
        """Create temporary directory for test files."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary files."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_calculate_checksum_sha256(self):
        """Test SHA-256 checksum calculation."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_content = b"Test content for checksum"
        test_file.write_bytes(test_content)

        checksum = calculate_checksum(str(test_file), "sha256")

        # Verify checksum format (64 hex characters for SHA-256)
        self.assertEqual(len(checksum), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in checksum))

    def test_calculate_checksum_sha512(self):
        """Test SHA-512 checksum calculation."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_bytes(b"Test content")

        checksum = calculate_checksum(str(test_file), "sha512")

        # Verify checksum format (128 hex characters for SHA-512)
        self.assertEqual(len(checksum), 128)

    def test_calculate_checksum_md5(self):
        """Test MD5 checksum calculation."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_bytes(b"Test content")

        checksum = calculate_checksum(str(test_file), "md5")

        # Verify checksum format (32 hex characters for MD5)
        self.assertEqual(len(checksum), 32)

    def test_calculate_checksum_unsupported_algorithm(self):
        """Test error with unsupported algorithm."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_bytes(b"Test content")

        with self.assertRaises(ValueError):
            calculate_checksum(str(test_file), "unsupported")

    def test_calculate_checksum_file_not_found(self):
        """Test error with non-existent file."""
        with self.assertRaises(FileNotFoundError):
            calculate_checksum("/nonexistent/file.txt")

    def test_verify_checksum_valid(self):
        """Test checksum verification with valid checksum."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_bytes(b"Test content")

        checksum = calculate_checksum(str(test_file))
        is_valid = verify_checksum(str(test_file), checksum)

        self.assertTrue(is_valid)

    def test_verify_checksum_invalid(self):
        """Test checksum verification with invalid checksum."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_bytes(b"Test content")

        wrong_checksum = "0" * 64
        is_valid = verify_checksum(str(test_file), wrong_checksum)

        self.assertFalse(is_valid)

    def test_checksum_consistency(self):
        """Test that same content produces same checksum."""
        test_file1 = Path(self.temp_dir) / "test1.txt"
        test_file2 = Path(self.temp_dir) / "test2.txt"

        test_content = b"Identical content"
        test_file1.write_bytes(test_content)
        test_file2.write_bytes(test_content)

        checksum1 = calculate_checksum(str(test_file1))
        checksum2 = calculate_checksum(str(test_file2))

        self.assertEqual(checksum1, checksum2)

    def test_checksum_different_content(self):
        """Test that different content produces different checksums."""
        test_file1 = Path(self.temp_dir) / "test1.txt"
        test_file2 = Path(self.temp_dir) / "test2.txt"

        test_file1.write_bytes(b"Content A")
        test_file2.write_bytes(b"Content B")

        checksum1 = calculate_checksum(str(test_file1))
        checksum2 = calculate_checksum(str(test_file2))

        self.assertNotEqual(checksum1, checksum2)


class CombinedOperationsTests(TestCase):
    """Test combined compress-and-encrypt operations."""

    def setUp(self):
        """Create temporary directory and set up encryption key."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_key = Fernet.generate_key()

    def tearDown(self):
        """Clean up temporary files."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_compress_and_encrypt_file(self):
        """Test combined compression and encryption."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_content = b"Test content for compression and encryption" * 100
        test_file.write_bytes(test_content)

        with override_settings(BACKUP_ENCRYPTION_KEY=self.test_key):
            final_path, checksum, original_size, final_size = compress_and_encrypt_file(
                str(test_file)
            )

        # Verify output
        self.assertTrue(Path(final_path).exists())
        self.assertTrue(final_path.endswith(".gz.enc"))
        self.assertEqual(original_size, len(test_content))
        self.assertLess(final_size, original_size)
        self.assertEqual(len(checksum), 64)  # SHA-256

    def test_compress_and_encrypt_keep_intermediate(self):
        """Test keeping intermediate compressed file."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_bytes(b"Test content")

        with override_settings(BACKUP_ENCRYPTION_KEY=self.test_key):
            final_path, _, _, _ = compress_and_encrypt_file(str(test_file), keep_intermediate=True)

        # Verify intermediate file exists
        compressed_path = str(test_file) + ".gz"
        self.assertTrue(Path(compressed_path).exists())

    def test_decrypt_and_decompress_file(self):
        """Test combined decryption and decompression."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_content = b"Original content to preserve"
        test_file.write_bytes(test_content)

        with override_settings(BACKUP_ENCRYPTION_KEY=self.test_key):
            # Compress and encrypt
            encrypted_path, _, _, _ = compress_and_encrypt_file(str(test_file))

            # Decrypt and decompress
            final_path = decrypt_and_decompress_file(encrypted_path)

        # Verify content is preserved
        self.assertTrue(Path(final_path).exists())
        self.assertEqual(Path(final_path).read_bytes(), test_content)

    def test_full_roundtrip(self):
        """Test complete compress-encrypt-decrypt-decompress cycle."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_content = b"Complete roundtrip test content" * 50
        test_file.write_bytes(test_content)

        with override_settings(BACKUP_ENCRYPTION_KEY=self.test_key):
            # Compress and encrypt
            encrypted_path, checksum, original_size, final_size = compress_and_encrypt_file(
                str(test_file)
            )

            # Verify checksum
            self.assertTrue(verify_checksum(encrypted_path, checksum))

            # Decrypt and decompress
            output_path = str(Path(self.temp_dir) / "restored.txt")
            restored_path = decrypt_and_decompress_file(encrypted_path, output_path)

        # Verify content is exactly preserved
        restored_content = Path(restored_path).read_bytes()
        self.assertEqual(restored_content, test_content)
        self.assertEqual(len(restored_content), original_size)


class BackupVerificationTests(TestCase):
    """Test backup integrity verification across storage locations."""

    def setUp(self):
        """Create temporary directory and set up encryption key."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_key = Fernet.generate_key()

    def tearDown(self):
        """Clean up temporary files."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_verify_backup_integrity_local_only(self):
        """Test backup verification with local storage only."""
        # Create a test backup file
        test_file = Path(self.temp_dir) / "backup.gz.enc"
        test_content = b"Backup content"
        test_file.write_bytes(test_content)

        checksum = calculate_checksum(str(test_file))

        # Mock local storage to use our temp directory
        with override_settings(BACKUP_LOCAL_PATH=self.temp_dir):
            result = verify_backup_integrity("backup.gz.enc", checksum, storage_backends=["local"])

        # Verify results
        self.assertTrue(result["valid"])
        self.assertTrue(result["locations"]["local"]["exists"])
        self.assertTrue(result["locations"]["local"]["checksum_valid"])
        self.assertEqual(len(result["errors"]), 0)

    def test_verify_backup_integrity_file_not_found(self):
        """Test verification when file doesn't exist."""
        with override_settings(BACKUP_LOCAL_PATH=self.temp_dir):
            result = verify_backup_integrity(
                "nonexistent.gz.enc", "0" * 64, storage_backends=["local"]
            )

        # Verify results
        self.assertFalse(result["valid"])
        self.assertFalse(result["locations"]["local"]["exists"])
        self.assertGreater(len(result["errors"]), 0)

    def test_verify_backup_integrity_checksum_mismatch(self):
        """Test verification when checksum doesn't match."""
        test_file = Path(self.temp_dir) / "backup.gz.enc"
        test_file.write_bytes(b"Backup content")

        wrong_checksum = "0" * 64

        with override_settings(BACKUP_LOCAL_PATH=self.temp_dir):
            result = verify_backup_integrity(
                "backup.gz.enc", wrong_checksum, storage_backends=["local"]
            )

        # Verify results
        self.assertFalse(result["valid"])
        self.assertTrue(result["locations"]["local"]["exists"])
        self.assertFalse(result["locations"]["local"]["checksum_valid"])
        self.assertGreater(len(result["errors"]), 0)
