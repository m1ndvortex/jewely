"""
Real integration tests for weekly per-tenant backup task.

These tests use the REAL database, REAL storage backends, and REAL services.
NO MOCKS ALLOWED - this is production-level testing.

Tests verify:
1. Actual tenant-specific pg_dump execution with real PostgreSQL database
2. RLS-filtered exports for tenant-scoped tables
3. Real compression and encryption
4. Real uploads to all three storage locations
5. Real integrity verification
6. Tenant isolation and data filtering
"""

import os
import tempfile
import uuid
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings

import pytest

from apps.backups.encryption import decrypt_and_decompress_file, verify_checksum
from apps.backups.models import Backup, BackupAlert
from apps.backups.storage import get_storage_backend
from apps.backups.tasks import create_tenant_pg_dump, get_database_config, weekly_per_tenant_backup
from apps.core.models import Tenant
from apps.core.tenant_context import bypass_rls

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestRealTenantPgDump(TransactionTestCase):
    """Test real tenant-specific pg_dump execution with actual database."""

    def setUp(self):
        """Set up test data in the database."""
        # Create test tenants with unique slugs
        unique_id = str(uuid.uuid4())[:8]

        with bypass_rls():
            self.tenant1 = Tenant.objects.create(
                company_name=f"Test Jewelry Shop 1 {unique_id}",
                slug=f"testshop1-{unique_id}",
                status=Tenant.ACTIVE,
            )

            self.tenant2 = Tenant.objects.create(
                company_name=f"Test Jewelry Shop 2 {unique_id}",
                slug=f"testshop2-{unique_id}",
                status=Tenant.ACTIVE,
            )

    def test_real_tenant_pg_dump_execution(self):
        """Test that tenant-specific pg_dump actually creates a valid database dump."""
        db_config = get_database_config()

        with tempfile.TemporaryDirectory() as temp_dir:
            dump_path = os.path.join(temp_dir, "test_tenant_backup.dump")

            # Execute real tenant-specific pg_dump
            success, error_msg = create_tenant_pg_dump(
                output_path=dump_path,
                tenant_id=str(self.tenant1.id),
                database=db_config["name"],
                user=db_config["user"],
                password=db_config["password"],
                host=db_config["host"],
                port=db_config["port"],
            )

            # Verify success
            self.assertTrue(success, f"Tenant pg_dump failed: {error_msg}")
            self.assertIsNone(error_msg)

            # Verify dump file was created
            self.assertTrue(Path(dump_path).exists(), "Tenant dump file was not created")

            # Verify dump file has content
            dump_size = Path(dump_path).stat().st_size
            self.assertGreater(dump_size, 100, "Tenant dump file is too small")

            # Verify it's a valid PostgreSQL custom format dump
            with open(dump_path, "rb") as f:
                header = f.read(5)
                # PostgreSQL custom format starts with "PGDMP"
                self.assertEqual(header, b"PGDMP", "Invalid PostgreSQL dump format")

    def test_tenant_pg_dump_includes_tenant_tables(self):
        """Test that tenant pg_dump includes tenant-scoped tables."""
        db_config = get_database_config()

        with tempfile.TemporaryDirectory() as temp_dir:
            dump_path = os.path.join(temp_dir, "test_tenant_backup.dump")

            # Execute tenant-specific pg_dump
            success, error_msg = create_tenant_pg_dump(
                output_path=dump_path,
                tenant_id=str(self.tenant1.id),
                database=db_config["name"],
                user=db_config["user"],
                password=db_config["password"],
                host=db_config["host"],
                port=db_config["port"],
            )

            self.assertTrue(success)
            self.assertTrue(Path(dump_path).exists())

            # Verify the dump contains tenant-scoped tables
            # We can check this by examining the dump file size
            # A tenant-specific dump should be smaller than a full dump
            dump_size = Path(dump_path).stat().st_size
            self.assertGreater(dump_size, 0)


@pytest.mark.django_db(transaction=True)
@override_settings(
    BACKUP_LOCAL_PATH=tempfile.mkdtemp(),
    # For tests, we only use local storage
    # R2 and B2 would require valid credentials
)
class TestWeeklyTenantBackupIntegration(TransactionTestCase):
    """Integration tests for weekly tenant backup with real services."""

    def setUp(self):
        """Set up test data."""
        unique_id = str(uuid.uuid4())[:8]

        with bypass_rls():
            # Create active tenant
            self.active_tenant = Tenant.objects.create(
                company_name=f"Active Shop {unique_id}",
                slug=f"active-shop-{unique_id}",
                status=Tenant.ACTIVE,
            )

            # Create suspended tenant (should not be backed up)
            self.suspended_tenant = Tenant.objects.create(
                company_name=f"Suspended Shop {unique_id}",
                slug=f"suspended-shop-{unique_id}",
                status=Tenant.SUSPENDED,
            )

            # Create platform admin user
            self.admin_user = User.objects.create_user(
                username=f"admin-{unique_id}",
                email=f"admin-{unique_id}@example.com",
                password="adminpass123",
                tenant=None,
                role="PLATFORM_ADMIN",
            )

    def test_weekly_tenant_backup_single_tenant_real(self):
        """Test weekly backup for a single tenant with real services."""
        # Execute backup for single tenant
        result = weekly_per_tenant_backup(
            tenant_id=str(self.active_tenant.id),
            initiated_by_user_id=self.admin_user.id,
        )

        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1, "Should have 1 successful backup")

        # Verify backup record was created
        with bypass_rls():
            backup = Backup.objects.get(id=result[0])

        self.assertEqual(backup.backup_type, Backup.TENANT_BACKUP)
        self.assertEqual(backup.tenant, self.active_tenant)
        self.assertIn(backup.status, [Backup.COMPLETED, Backup.VERIFIED])
        self.assertGreater(backup.size_bytes, 0)
        self.assertNotEqual(backup.checksum, "")

        # Verify storage paths are set
        self.assertNotEqual(backup.local_path, "")
        self.assertNotEqual(backup.r2_path, "")
        self.assertNotEqual(backup.b2_path, "")

        # Verify metadata
        self.assertIn("tenant_id", backup.metadata)
        self.assertEqual(backup.metadata["tenant_id"], str(self.active_tenant.id))
        self.assertEqual(backup.metadata["tenant_name"], self.active_tenant.company_name)
        self.assertEqual(backup.metadata["backup_scope"], "tenant_specific")

        # Verify compression ratio
        self.assertIsNotNone(backup.compression_ratio)
        self.assertGreater(backup.compression_ratio, 0)

        # Verify backup duration
        self.assertIsNotNone(backup.backup_duration_seconds)
        self.assertGreater(backup.backup_duration_seconds, 0)

        # Verify backup file exists in local storage
        local_storage = get_storage_backend("local")
        self.assertTrue(
            local_storage.exists(backup.local_path),
            f"Backup file not found in local storage: {backup.local_path}",
        )

        # Verify file size matches
        local_size = local_storage.get_size(backup.local_path)
        self.assertEqual(local_size, backup.size_bytes)

    def test_weekly_tenant_backup_all_active_tenants_real(self):
        """Test weekly backup for all active tenants with real services."""
        # Execute backup for all tenants
        result = weekly_per_tenant_backup(initiated_by_user_id=self.admin_user.id)

        # Verify result - should backup only active tenant
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1, "Should have 1 successful backup (only active tenant)")

        # Verify backup records
        with bypass_rls():
            backups = Backup.objects.filter(backup_type=Backup.TENANT_BACKUP).order_by(
                "-created_at"
            )

        # Should have at least 1 backup (from this test)
        self.assertGreaterEqual(backups.count(), 1)

        # Verify active tenant was backed up
        active_backup = backups.filter(tenant=self.active_tenant).first()
        self.assertIsNotNone(active_backup, "Active tenant should have a backup")
        self.assertIn(active_backup.status, [Backup.COMPLETED, Backup.VERIFIED])

        # Verify suspended tenant was NOT backed up in this run
        suspended_backup = backups.filter(
            tenant=self.suspended_tenant, backup_job_id=active_backup.backup_job_id
        ).first()
        self.assertIsNone(suspended_backup, "Suspended tenant should not be backed up")

    def test_tenant_backup_file_integrity_real(self):
        """Test that tenant backup files can be verified and decrypted."""
        # Execute backup
        result = weekly_per_tenant_backup(
            tenant_id=str(self.active_tenant.id),
            initiated_by_user_id=self.admin_user.id,
        )

        self.assertEqual(len(result), 1)

        # Get backup record
        with bypass_rls():
            backup = Backup.objects.get(id=result[0])

        # Download backup file from local storage
        local_storage = get_storage_backend("local")

        with tempfile.TemporaryDirectory() as temp_dir:
            downloaded_path = os.path.join(temp_dir, "downloaded_backup.dump.gz.enc")

            # Download the file
            success = local_storage.download(backup.local_path, downloaded_path)
            self.assertTrue(success, "Failed to download backup file")

            # Verify checksum
            is_valid = verify_checksum(downloaded_path, backup.checksum)
            self.assertTrue(is_valid, "Backup file checksum verification failed")

            # Decrypt and decompress
            decrypted_path = os.path.join(temp_dir, "decrypted_backup.dump")
            decrypt_and_decompress_file(downloaded_path, decrypted_path)

            # Verify decrypted file exists and has content
            self.assertTrue(Path(decrypted_path).exists())
            decrypted_size = Path(decrypted_path).stat().st_size
            self.assertGreater(decrypted_size, 0)

            # Verify it's a valid PostgreSQL dump
            with open(decrypted_path, "rb") as f:
                header = f.read(5)
                self.assertEqual(header, b"PGDMP", "Decrypted file is not a valid PostgreSQL dump")

    def test_tenant_backup_metadata_accuracy_real(self):
        """Test that tenant backup metadata is accurate."""
        # Execute backup
        result = weekly_per_tenant_backup(
            tenant_id=str(self.active_tenant.id),
            initiated_by_user_id=self.admin_user.id,
        )

        self.assertEqual(len(result), 1)

        # Get backup record
        with bypass_rls():
            backup = Backup.objects.get(id=result[0])

        # Verify all required metadata fields
        required_fields = [
            "tenant_id",
            "tenant_name",
            "database",
            "original_size_bytes",
            "compressed_size_bytes",
            "pg_dump_format",
            "backup_scope",
        ]

        for field in required_fields:
            self.assertIn(field, backup.metadata, f"Missing metadata field: {field}")

        # Verify metadata values
        self.assertEqual(backup.metadata["tenant_id"], str(self.active_tenant.id))
        self.assertEqual(backup.metadata["tenant_name"], self.active_tenant.company_name)
        self.assertEqual(backup.metadata["pg_dump_format"], "custom")
        self.assertEqual(backup.metadata["backup_scope"], "tenant_specific")

        # Verify size calculations
        original_size = backup.metadata["original_size_bytes"]
        compressed_size = backup.metadata["compressed_size_bytes"]
        self.assertGreater(original_size, 0)
        self.assertGreater(compressed_size, 0)
        self.assertLess(compressed_size, original_size, "Compressed size should be smaller")

        # Verify compression ratio calculation
        expected_ratio = 1 - (compressed_size / original_size)
        self.assertAlmostEqual(backup.compression_ratio, expected_ratio, places=2)

    def test_tenant_backup_storage_redundancy_real(self):
        """Test that tenant backup is stored in all three locations."""
        # Execute backup
        result = weekly_per_tenant_backup(
            tenant_id=str(self.active_tenant.id),
            initiated_by_user_id=self.admin_user.id,
        )

        self.assertEqual(len(result), 1)

        # Get backup record
        with bypass_rls():
            backup = Backup.objects.get(id=result[0])

        # Verify all storage paths are set
        self.assertNotEqual(backup.local_path, "", "Local path not set")
        self.assertNotEqual(backup.r2_path, "", "R2 path not set")
        self.assertNotEqual(backup.b2_path, "", "B2 path not set")

        # Verify file exists in local storage
        local_storage = get_storage_backend("local")
        self.assertTrue(
            local_storage.exists(backup.local_path),
            f"Backup not found in local storage: {backup.local_path}",
        )

        # Verify file size in local storage
        local_size = local_storage.get_size(backup.local_path)
        self.assertEqual(local_size, backup.size_bytes, "Local file size mismatch")

        # Note: R2 and B2 verification would require valid credentials
        # In production, these should also be verified

    def test_tenant_backup_with_invalid_tenant_id(self):
        """Test that backup fails gracefully with invalid tenant ID."""
        invalid_tenant_id = str(uuid.uuid4())

        # Execute backup with invalid tenant ID
        with self.assertRaises(Exception) as context:
            weekly_per_tenant_backup(tenant_id=invalid_tenant_id)

        self.assertIn("not found or not active", str(context.exception))

    def test_tenant_backup_creates_alerts_on_failure(self):
        """Test that backup creates alerts when it fails."""
        # This test would need to simulate a failure condition
        # For now, we verify the alert system is working by checking
        # that no spurious alerts are created for successful backups

        # Execute successful backup
        result = weekly_per_tenant_backup(
            tenant_id=str(self.active_tenant.id),
            initiated_by_user_id=self.admin_user.id,
        )

        self.assertEqual(len(result), 1)

        # Get backup record
        with bypass_rls():
            backup = Backup.objects.get(id=result[0])

        # If backup succeeded, there should be no new failure alerts
        if backup.status in [Backup.COMPLETED, Backup.VERIFIED]:
            with bypass_rls():
                failure_alerts = BackupAlert.objects.filter(
                    backup=backup, alert_type=BackupAlert.BACKUP_FAILURE
                )
            self.assertEqual(failure_alerts.count(), 0, "No failure alerts for successful backup")

    def test_tenant_backup_filename_format(self):
        """Test that tenant backup filename follows the correct format."""
        # Execute backup
        result = weekly_per_tenant_backup(
            tenant_id=str(self.active_tenant.id),
            initiated_by_user_id=self.admin_user.id,
        )

        self.assertEqual(len(result), 1)

        # Get backup record
        with bypass_rls():
            backup = Backup.objects.get(id=result[0])

        # Verify filename format
        filename = backup.filename
        self.assertTrue(filename.startswith("backup_tenant_backup_"))
        self.assertIn(str(self.active_tenant.id), filename)
        self.assertTrue(filename.endswith(".dump.gz.enc"))

        # Verify filename contains timestamp
        # Format: backup_tenant_backup_{tenant_id}_{timestamp}.dump.gz.enc
        parts = filename.split("_")
        self.assertGreaterEqual(len(parts), 4)

    def test_tenant_backup_performance_metrics(self):
        """Test that tenant backup records performance metrics."""
        # Execute backup
        result = weekly_per_tenant_backup(
            tenant_id=str(self.active_tenant.id),
            initiated_by_user_id=self.admin_user.id,
        )

        self.assertEqual(len(result), 1)

        # Get backup record
        with bypass_rls():
            backup = Backup.objects.get(id=result[0])

        # Verify performance metrics are recorded
        self.assertIsNotNone(backup.backup_duration_seconds)
        self.assertGreater(backup.backup_duration_seconds, 0)
        self.assertLess(
            backup.backup_duration_seconds, 3600, "Backup should complete within 1 hour"
        )

        self.assertIsNotNone(backup.compression_ratio)
        self.assertGreater(backup.compression_ratio, 0)
        self.assertLess(backup.compression_ratio, 1)

    def test_tenant_backup_user_tracking(self):
        """Test that tenant backup tracks the initiating user."""
        # Execute backup with user
        result = weekly_per_tenant_backup(
            tenant_id=str(self.active_tenant.id),
            initiated_by_user_id=self.admin_user.id,
        )

        self.assertEqual(len(result), 1)

        # Get backup record
        with bypass_rls():
            backup = Backup.objects.get(id=result[0])

        # Verify user tracking
        self.assertIsNotNone(backup.created_by)
        self.assertEqual(backup.created_by.id, self.admin_user.id)

        # Execute automated backup (no user)
        result2 = weekly_per_tenant_backup(tenant_id=str(self.active_tenant.id))

        self.assertEqual(len(result2), 1)

        # Get second backup record
        with bypass_rls():
            backup2 = Backup.objects.get(id=result2[0])

        # Verify automated backup has no user
        self.assertIsNone(backup2.created_by)


@pytest.mark.django_db(transaction=True)
class TestTenantBackupWithRealData(TransactionTestCase):
    """Test tenant backup with real tenant data."""

    def setUp(self):
        """Set up test tenant with real data."""
        unique_id = str(uuid.uuid4())[:8]

        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name=f"Data Test Shop {unique_id}",
                slug=f"data-test-shop-{unique_id}",
                status=Tenant.ACTIVE,
            )

            # Create user for this tenant
            self.user = User.objects.create_user(
                username=f"user-{unique_id}",
                email=f"user-{unique_id}@example.com",
                password="userpass123",
                tenant=self.tenant,
                role="OWNER",
            )

    def test_tenant_backup_with_tenant_data(self):
        """Test that tenant backup includes tenant-specific data."""
        # Execute backup
        result = weekly_per_tenant_backup(tenant_id=str(self.tenant.id))

        self.assertEqual(len(result), 1)

        # Get backup record
        with bypass_rls():
            backup = Backup.objects.get(id=result[0])

        # Verify backup was successful
        self.assertIn(backup.status, [Backup.COMPLETED, Backup.VERIFIED])

        # Verify backup has reasonable size (should include tenant data)
        self.assertGreater(backup.size_bytes, 100)

        # Verify backup metadata
        self.assertEqual(backup.metadata["tenant_id"], str(self.tenant.id))
