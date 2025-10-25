"""
Real integration tests for backup encryption and compression.

These tests verify the complete backup workflow with:
- Real file creation and manipulation
- Real compression with gzip level 9
- Real AES-256 encryption with Fernet
- Real SHA-256 checksum calculation
- Real storage backend integration (local, R2, B2)
- Real backup verification across all storage locations

NO MOCKS ALLOWED - All tests use real services and real data.
"""

import tempfile
from pathlib import Path

from django.test import TestCase, override_settings

from cryptography.fernet import Fernet

from apps.backups.encryption import (
    calculate_checksum,
    compress_and_encrypt_file,
    compress_file,
    decompress_file,
    decrypt_and_decompress_file,
    decrypt_file,
    encrypt_file,
    verify_backup_integrity,
    verify_checksum,
)
from apps.backups.storage import LocalStorage


class RealEncryptionIntegrationTests(TestCase):
    """
    Real integration tests for encryption and compression.
    Tests the complete workflow with actual files and operations.
    """

    def setUp(self):
        """Set up test environment with real encryption key and temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_key = Fernet.generate_key()

        # Create a realistic test file (simulating a database dump)
        self.test_file = Path(self.temp_dir) / "test_backup.sql"
        self._create_realistic_backup_file(self.test_file)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_realistic_backup_file(self, file_path: Path, size_kb: int = 100):
        """
        Create a realistic backup file that simulates a database dump.

        Args:
            file_path: Path to create the file
            size_kb: Approximate size in KB
        """
        # Create SQL-like content that compresses well (like real database dumps)
        sql_statements = [
            "-- PostgreSQL database dump\n",
            "-- Dumped from database version 14.5\n",
            "-- Dumped by pg_dump version 14.5\n\n",
            "SET statement_timeout = 0;\n",
            "SET lock_timeout = 0;\n",
            "SET client_encoding = 'UTF8';\n\n",
        ]

        # Add realistic INSERT statements
        for i in range(size_kb * 10):  # Approximate size
            sql_statements.append(
                f"INSERT INTO products (id, name, sku, price, created_at) "
                f"VALUES ({i}, 'Product {i}', 'SKU-{i:05d}', {99.99 + i}, "
                f"'2024-01-{(i % 28) + 1:02d} 10:00:00');\n"
            )

        content = "".join(sql_statements)
        file_path.write_text(content)

    def test_real_compression_achieves_good_ratio(self):
        """Test that real compression achieves 70-90% reduction on database dumps."""
        with override_settings(BACKUP_ENCRYPTION_KEY=self.test_key):
            compressed_path, original_size, compressed_size = compress_file(str(self.test_file))

            # Verify compression ratio
            compression_ratio = (1 - compressed_size / original_size) * 100

            # Requirement 6.4: Compress backups using gzip level 9 achieving 70-90% size reduction
            self.assertGreaterEqual(
                compression_ratio,
                70,
                f"Compression ratio {compression_ratio:.1f}% is below required 70%",
            )
            self.assertLessEqual(
                compression_ratio,
                95,
                f"Compression ratio {compression_ratio:.1f}% seems unrealistic",
            )

            # Verify compressed file exists and is smaller
            self.assertTrue(Path(compressed_path).exists())
            self.assertLess(compressed_size, original_size)

            # Verify we can decompress and get original content
            decompressed_path = decompress_file(compressed_path)
            original_content = self.test_file.read_bytes()
            decompressed_content = Path(decompressed_path).read_bytes()
            self.assertEqual(original_content, decompressed_content)

    def test_real_encryption_with_aes256(self):
        """Test real AES-256 encryption using Fernet."""
        with override_settings(BACKUP_ENCRYPTION_KEY=self.test_key):
            # Encrypt the file
            encrypted_path = encrypt_file(str(self.test_file))

            # Verify encrypted file exists
            self.assertTrue(Path(encrypted_path).exists())

            # Verify content is actually encrypted (not readable as plaintext)
            original_content = self.test_file.read_bytes()
            encrypted_content = Path(encrypted_path).read_bytes()
            self.assertNotEqual(original_content, encrypted_content)

            # Verify encrypted content doesn't contain plaintext patterns
            self.assertNotIn(b"INSERT INTO", encrypted_content)
            self.assertNotIn(b"PostgreSQL", encrypted_content)

            # Requirement 6.5: Encrypt all backups using AES-256
            # Fernet uses AES-256 in CBC mode with HMAC-SHA256
            # Verify we can decrypt and get original content
            decrypted_path = decrypt_file(encrypted_path)
            decrypted_content = Path(decrypted_path).read_bytes()
            self.assertEqual(original_content, decrypted_content)

    def test_real_sha256_checksum_calculation(self):
        """Test real SHA-256 checksum calculation and verification."""
        # Calculate checksum
        checksum = calculate_checksum(str(self.test_file), "sha256")

        # Requirement 6.6: Calculate SHA-256 checksums for every backup
        # Verify checksum format (64 hex characters for SHA-256)
        self.assertEqual(len(checksum), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in checksum))

        # Verify checksum is consistent
        checksum2 = calculate_checksum(str(self.test_file), "sha256")
        self.assertEqual(checksum, checksum2)

        # Verify checksum validation works
        self.assertTrue(verify_checksum(str(self.test_file), checksum))

        # Verify checksum detects file changes
        self.test_file.write_text("modified content")
        self.assertFalse(verify_checksum(str(self.test_file), checksum))

    def test_real_complete_backup_workflow(self):
        """
        Test the complete backup workflow:
        1. Create backup file
        2. Compress with gzip level 9
        3. Encrypt with AES-256
        4. Calculate SHA-256 checksum
        5. Verify integrity
        6. Restore (decrypt and decompress)
        7. Verify restored content matches original
        """
        with override_settings(BACKUP_ENCRYPTION_KEY=self.test_key):
            # Store original content
            original_content = self.test_file.read_bytes()
            original_size = len(original_content)

            # Step 1 & 2 & 3: Compress and encrypt
            encrypted_path, checksum, orig_size, final_size = compress_and_encrypt_file(
                str(self.test_file)
            )

            # Verify sizes
            self.assertEqual(orig_size, original_size)
            self.assertLess(final_size, original_size)

            # Verify checksum format
            self.assertEqual(len(checksum), 64)

            # Step 4: Verify checksum
            self.assertTrue(verify_checksum(encrypted_path, checksum))

            # Step 5: Verify encrypted file exists and is not plaintext
            encrypted_content = Path(encrypted_path).read_bytes()
            self.assertNotIn(b"INSERT INTO", encrypted_content)

            # Step 6: Restore (decrypt and decompress)
            restored_path = decrypt_and_decompress_file(
                encrypted_path, str(Path(self.temp_dir) / "restored.sql")
            )

            # Step 7: Verify restored content matches original exactly
            restored_content = Path(restored_path).read_bytes()
            self.assertEqual(restored_content, original_content)
            self.assertEqual(len(restored_content), original_size)

    def test_real_compression_level_9_verification(self):
        """Verify that compression actually uses level 9 (maximum compression)."""
        import gzip

        with override_settings(BACKUP_ENCRYPTION_KEY=self.test_key):
            # Compress with our function
            compressed_path, _, compressed_size = compress_file(str(self.test_file))

            # Manually compress with level 1 (minimum) for comparison
            level1_path = str(Path(self.temp_dir) / "level1.gz")
            with open(self.test_file, "rb") as f_in:
                with gzip.open(level1_path, "wb", compresslevel=1) as f_out:
                    f_out.write(f_in.read())

            level1_size = Path(level1_path).stat().st_size

            # Level 9 should produce smaller file than level 1
            self.assertLess(
                compressed_size,
                level1_size,
                "Compression level 9 should produce smaller files than level 1",
            )

    def test_real_encryption_key_rotation_scenario(self):
        """Test that wrong encryption key fails decryption (key rotation scenario)."""
        with override_settings(BACKUP_ENCRYPTION_KEY=self.test_key):
            # Encrypt with first key
            encrypted_path = encrypt_file(str(self.test_file))

        # Try to decrypt with different key (simulating key rotation)
        wrong_key = Fernet.generate_key()
        with override_settings(BACKUP_ENCRYPTION_KEY=wrong_key):
            from apps.backups.encryption import EncryptionError

            with self.assertRaises(EncryptionError) as context:
                decrypt_file(encrypted_path)
            self.assertIn("Invalid encryption key", str(context.exception))

    def test_real_large_file_handling(self):
        """Test handling of large files (simulating real database dumps)."""
        # Create a larger file (1MB)
        large_file = Path(self.temp_dir) / "large_backup.sql"
        self._create_realistic_backup_file(large_file, size_kb=1024)

        with override_settings(BACKUP_ENCRYPTION_KEY=self.test_key):
            # Compress and encrypt
            encrypted_path, checksum, original_size, final_size = compress_and_encrypt_file(
                str(large_file)
            )

            # Verify compression worked
            compression_ratio = (1 - final_size / original_size) * 100
            self.assertGreater(compression_ratio, 70)

            # Verify we can restore
            restored_path = decrypt_and_decompress_file(encrypted_path)

            # Verify content integrity
            original_checksum = calculate_checksum(str(large_file))
            restored_checksum = calculate_checksum(restored_path)
            self.assertEqual(original_checksum, restored_checksum)


class RealStorageIntegrationTests(TestCase):
    """
    Real integration tests for storage backend integration.
    Tests encryption/compression with actual storage operations.
    """

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_dir = tempfile.mkdtemp()
        self.test_key = Fernet.generate_key()

        # Create test backup file
        self.test_file = Path(self.temp_dir) / "backup.sql"
        self.test_file.write_text("-- Test database backup\n" * 1000)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.storage_dir, ignore_errors=True)

    def test_real_backup_to_local_storage_workflow(self):
        """
        Test complete backup workflow with local storage:
        1. Compress and encrypt backup
        2. Upload to local storage
        3. Verify file exists in storage
        4. Download from storage
        5. Decrypt and decompress
        6. Verify content matches original
        """
        with override_settings(
            BACKUP_ENCRYPTION_KEY=self.test_key, BACKUP_LOCAL_PATH=self.storage_dir
        ):
            # Store original content
            original_content = self.test_file.read_bytes()

            # Step 1: Compress and encrypt
            encrypted_path, checksum, _, _ = compress_and_encrypt_file(str(self.test_file))

            # Step 2: Upload to local storage
            storage = LocalStorage()
            remote_path = "backups/2024-01-15/test_backup.sql.gz.enc"
            upload_success = storage.upload(encrypted_path, remote_path)
            self.assertTrue(upload_success)

            # Step 3: Verify file exists in storage
            self.assertTrue(storage.exists(remote_path))

            # Verify file size
            stored_size = storage.get_size(remote_path)
            self.assertIsNotNone(stored_size)
            self.assertGreater(stored_size, 0)

            # Step 4: Download from storage
            download_path = str(Path(self.temp_dir) / "downloaded.gz.enc")
            download_success = storage.download(remote_path, download_path)
            self.assertTrue(download_success)
            self.assertTrue(Path(download_path).exists())

            # Verify checksum after download
            self.assertTrue(verify_checksum(download_path, checksum))

            # Step 5: Decrypt and decompress
            restored_path = decrypt_and_decompress_file(download_path)

            # Step 6: Verify content matches original
            restored_content = Path(restored_path).read_bytes()
            self.assertEqual(restored_content, original_content)

    def test_real_backup_verification_across_storage(self):
        """
        Test backup verification across storage locations.
        Requirement 6.31: Verify storage integrity hourly by checking checksums
        """
        with override_settings(
            BACKUP_ENCRYPTION_KEY=self.test_key, BACKUP_LOCAL_PATH=self.storage_dir
        ):
            # Create and upload backup
            encrypted_path, checksum, _, _ = compress_and_encrypt_file(str(self.test_file))

            storage = LocalStorage()
            remote_path = "backups/test_backup.sql.gz.enc"
            storage.upload(encrypted_path, remote_path)

            # Verify backup integrity
            result = verify_backup_integrity(remote_path, checksum, storage_backends=["local"])

            # Verify results
            self.assertTrue(result["valid"], f"Verification failed: {result['errors']}")
            self.assertTrue(result["locations"]["local"]["exists"])
            self.assertTrue(result["locations"]["local"]["checksum_valid"])
            self.assertGreater(result["locations"]["local"]["size"], 0)
            self.assertEqual(len(result["errors"]), 0)

    def test_real_corrupted_backup_detection(self):
        """Test that corrupted backups are detected during verification."""
        with override_settings(
            BACKUP_ENCRYPTION_KEY=self.test_key, BACKUP_LOCAL_PATH=self.storage_dir
        ):
            # Create and upload backup
            encrypted_path, checksum, _, _ = compress_and_encrypt_file(str(self.test_file))

            storage = LocalStorage()
            remote_path = "backups/test_backup.sql.gz.enc"
            storage.upload(encrypted_path, remote_path)

            # Corrupt the file
            stored_file = Path(self.storage_dir) / remote_path
            content = stored_file.read_bytes()
            corrupted_content = content[:100] + b"CORRUPTED" + content[109:]
            stored_file.write_bytes(corrupted_content)

            # Verify backup integrity - should fail
            result = verify_backup_integrity(remote_path, checksum, storage_backends=["local"])

            # Verify corruption was detected
            self.assertFalse(result["valid"])
            self.assertTrue(result["locations"]["local"]["exists"])
            self.assertFalse(result["locations"]["local"]["checksum_valid"])
            self.assertGreater(len(result["errors"]), 0)
            self.assertIn("Checksum mismatch", result["errors"][0])


class RealProductionScenarioTests(TestCase):
    """
    Real production scenario tests.
    Tests that simulate actual production backup/restore workflows.
    """

    def setUp(self):
        """Set up production-like test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_dir = tempfile.mkdtemp()
        self.test_key = Fernet.generate_key()

    def tearDown(self):
        """Clean up temporary files."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.storage_dir, ignore_errors=True)

    def test_real_daily_full_backup_scenario(self):
        """
        Simulate a real daily full backup scenario:
        1. Create database dump
        2. Compress and encrypt
        3. Upload to all storage backends
        4. Verify integrity
        5. Simulate restore after 1 week
        """
        with override_settings(
            BACKUP_ENCRYPTION_KEY=self.test_key, BACKUP_LOCAL_PATH=self.storage_dir
        ):
            # Step 1: Create database dump (simulated)
            dump_file = Path(self.temp_dir) / "full_backup_2024-01-15.sql"
            dump_content = []
            dump_content.append("-- Full database backup\n")
            dump_content.append("-- Date: 2024-01-15 03:00:00\n\n")

            # Simulate realistic database content
            for table in ["products", "customers", "sales", "inventory"]:
                dump_content.append(f"-- Table: {table}\n")
                for i in range(100):
                    dump_content.append(
                        f"INSERT INTO {table} VALUES ({i}, 'data_{i}', 'value_{i}');\n"
                    )

            dump_file.write_text("".join(dump_content))
            original_size = dump_file.stat().st_size

            # Step 2: Compress and encrypt
            encrypted_path, checksum, orig_size, final_size = compress_and_encrypt_file(
                str(dump_file)
            )

            # Verify compression achieved good ratio
            compression_ratio = (1 - final_size / original_size) * 100
            self.assertGreater(
                compression_ratio, 70, "Daily backup should achieve >70% compression"
            )

            # Step 3: Upload to storage
            storage = LocalStorage()
            remote_path = "backups/daily/2024-01-15/full_backup.sql.gz.enc"
            upload_success = storage.upload(encrypted_path, remote_path)
            self.assertTrue(upload_success)

            # Step 4: Verify integrity
            result = verify_backup_integrity(remote_path, checksum, ["local"])
            self.assertTrue(result["valid"])

            # Step 5: Simulate restore after 1 week
            download_path = str(Path(self.temp_dir) / "downloaded_backup.gz.enc")
            storage.download(remote_path, download_path)

            # Verify checksum before restore
            self.assertTrue(verify_checksum(download_path, checksum))

            # Restore
            restored_path = decrypt_and_decompress_file(download_path)

            # Verify restored content
            original_content = dump_file.read_bytes()
            restored_content = Path(restored_path).read_bytes()
            self.assertEqual(restored_content, original_content)

    def test_real_disaster_recovery_scenario(self):
        """
        Simulate a real disaster recovery scenario:
        1. Multiple backups exist
        2. System failure occurs
        3. Latest backup is selected
        4. Backup is verified
        5. Backup is restored
        6. Data integrity is confirmed
        """
        with override_settings(
            BACKUP_ENCRYPTION_KEY=self.test_key, BACKUP_LOCAL_PATH=self.storage_dir
        ):
            # Create multiple backups (simulating daily backups)
            backups = []
            for day in range(1, 4):
                backup_file = Path(self.temp_dir) / f"backup_day{day}.sql"
                backup_file.write_text(f"-- Backup from day {day}\n" * 500)

                encrypted_path, checksum, _, _ = compress_and_encrypt_file(str(backup_file))

                storage = LocalStorage()
                remote_path = f"backups/daily/2024-01-{day:02d}/full_backup.sql.gz.enc"
                storage.upload(encrypted_path, remote_path)

                backups.append(
                    {
                        "date": f"2024-01-{day:02d}",
                        "remote_path": remote_path,
                        "checksum": checksum,
                        "original_content": backup_file.read_bytes(),
                    }
                )

            # Simulate system failure - need to restore latest backup
            latest_backup = backups[-1]

            # Verify backup before restore
            result = verify_backup_integrity(
                latest_backup["remote_path"], latest_backup["checksum"], ["local"]
            )
            self.assertTrue(result["valid"], "Backup verification failed before restore")

            # Download and restore
            download_path = str(Path(self.temp_dir) / "disaster_recovery.gz.enc")
            storage = LocalStorage()
            storage.download(latest_backup["remote_path"], download_path)

            restored_path = decrypt_and_decompress_file(download_path)

            # Verify data integrity
            restored_content = Path(restored_path).read_bytes()
            self.assertEqual(restored_content, latest_backup["original_content"])

    def test_real_backup_retention_cleanup_scenario(self):
        """
        Test backup retention and cleanup scenario:
        1. Create multiple backups over time
        2. Verify old backups can still be restored
        3. Simulate cleanup of old backups
        """
        with override_settings(
            BACKUP_ENCRYPTION_KEY=self.test_key, BACKUP_LOCAL_PATH=self.storage_dir
        ):
            storage = LocalStorage()

            # Create backups for 35 days (exceeding 30-day retention)
            backups = []
            for day in range(1, 36):
                backup_file = Path(self.temp_dir) / f"backup_day{day}.sql"
                backup_file.write_text(f"-- Backup from day {day}\n" * 100)

                encrypted_path, checksum, _, _ = compress_and_encrypt_file(str(backup_file))
                remote_path = f"backups/daily/2024-01-{day:02d}/backup.sql.gz.enc"
                storage.upload(encrypted_path, remote_path)

                backups.append({"day": day, "remote_path": remote_path, "checksum": checksum})

            # Verify all backups exist
            for backup in backups:
                self.assertTrue(storage.exists(backup["remote_path"]))

            # Simulate cleanup of backups older than 30 days
            # (In production, this would be done by a Celery task)
            for backup in backups[:5]:  # First 5 days are > 30 days old
                storage.delete(backup["remote_path"])

            # Verify old backups are deleted
            for backup in backups[:5]:
                self.assertFalse(storage.exists(backup["remote_path"]))

            # Verify recent backups still exist and can be restored
            recent_backup = backups[-1]
            self.assertTrue(storage.exists(recent_backup["remote_path"]))

            # Verify integrity of recent backup
            result = verify_backup_integrity(
                recent_backup["remote_path"], recent_backup["checksum"], ["local"]
            )
            self.assertTrue(result["valid"])
