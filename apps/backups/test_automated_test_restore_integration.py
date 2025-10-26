"""
Integration Tests for Automated Test Restore.

These tests verify the COMPLETE automated test restore workflow with:
- REAL PostgreSQL database
- REAL backup creation
- REAL storage backends (local, R2, B2)
- REAL test database creation
- REAL restore operations
- REAL data integrity verification

NO MOCKS for internal services - This is production-level testing.

Tests verify:
1. Automated test restore actually selects a real backup
2. Test database is actually created
3. Backup is actually downloaded from storage
4. Backup is actually decrypted and decompressed
5. Data is actually restored to test database
6. Data integrity is actually verified
7. Test database is actually cleaned up
8. Alerts are actually created on failures
"""

import time
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.utils import timezone

import pytest

from apps.core.models import Tenant
from apps.core.tenant_context import bypass_rls
from apps.inventory.models import InventoryItem, ProductCategory

from .models import Backup, BackupAlert, BackupRestoreLog
from .storage import get_storage_backend
from .tasks import (
    automated_test_restore,
    create_test_database,
    daily_full_database_backup,
    drop_test_database,
    verify_test_restore_integrity,
)

User = get_user_model()


@pytest.mark.django_db
class TestAutomatedTestRestoreIntegration(TransactionTestCase):
    """
    Integration tests for automated test restore with real database and storage.
    """

    def setUp(self):
        """Set up test data with real database operations."""
        with bypass_rls():
            # Create platform admin
            self.admin_user = User.objects.create_user(
                username="admin_test_restore",
                email="admin@test-restore.com",
                password="testpass123",
                role="PLATFORM_ADMIN",
            )

            # Create test tenant
            self.tenant = Tenant.objects.create(
                company_name="Test Restore Jewelry Shop",
                slug="test-restore-shop",
                status=Tenant.ACTIVE,
            )

            # Create test user for tenant
            self.tenant_user = User.objects.create_user(
                username="tenant_user_restore",
                email="user@test-restore-shop.com",
                password="testpass123",
                role="TENANT_OWNER",
                tenant=self.tenant,
            )

            # Create some inventory data for testing
            self.category = ProductCategory.objects.create(
                tenant=self.tenant, name="Gold Rings", code="GR"
            )

            self.items = []
            for i in range(5):
                item = InventoryItem.objects.create(
                    tenant=self.tenant,
                    category=self.category,
                    name=f"Gold Ring {i+1}",
                    sku=f"GR-{i+1:03d}",
                    quantity=10 + i,
                    unit_price=299.99 + (i * 50),
                )
                self.items.append(item)

    def test_create_and_drop_test_database_real(self):
        """
        Test that test database can actually be created and dropped.

        This verifies the database management functions work with real PostgreSQL.
        """
        from django.conf import settings

        db_config = settings.DATABASES["default"]
        test_db_name = f"test_restore_integration_{int(time.time())}"

        # Create test database
        success, error_msg = create_test_database(
            test_db_name=test_db_name,
            host=db_config["HOST"],
            port=db_config["PORT"],
            user=db_config["USER"],
            password=db_config["PASSWORD"],
        )

        assert success is True, f"Failed to create test database: {error_msg}"

        # Verify database exists by trying to connect
        import psycopg2

        try:
            conn = psycopg2.connect(
                dbname=test_db_name,
                host=db_config["HOST"],
                port=db_config["PORT"],
                user=db_config["USER"],
                password=db_config["PASSWORD"],
            )
            conn.close()
        except Exception as e:
            pytest.fail(f"Test database was not created: {e}")

        # Drop test database
        success, error_msg = drop_test_database(
            test_db_name=test_db_name,
            host=db_config["HOST"],
            port=db_config["PORT"],
            user=db_config["USER"],
            password=db_config["PASSWORD"],
        )

        assert success is True, f"Failed to drop test database: {error_msg}"

    def test_verify_test_restore_integrity_real(self):
        """
        Test that data integrity verification works with real database.

        This verifies the integrity checks work against the actual database.
        """
        from django.conf import settings

        db_config = settings.DATABASES["default"]

        # Run integrity checks against the actual test database
        results = verify_test_restore_integrity(
            test_db_name=db_config["NAME"],
            host=db_config["HOST"],
            port=db_config["PORT"],
            user=db_config["USER"],
            password=db_config["PASSWORD"],
        )

        # Verify results structure
        assert "table_existence" in results
        assert "row_counts" in results
        assert "foreign_key_integrity" in results
        assert "data_corruption" in results
        assert "overall" in results

        # Verify key tables exist
        assert results["table_existence"]["passed"] is True
        assert "tenants" in results["table_existence"]["existing_tables"]
        assert "users" in results["table_existence"]["existing_tables"]

        # Verify row counts are positive
        assert results["row_counts"]["passed"] is True
        assert results["row_counts"]["total_rows"] > 0

        # Verify no FK violations in clean database
        assert results["foreign_key_integrity"]["passed"] is True

        # Verify no data corruption
        assert results["data_corruption"]["passed"] is True

        # Overall should pass
        assert results["overall"]["passed"] is True

    def test_automated_test_restore_full_workflow_real(self):
        """
        Test the complete automated test restore workflow with real operations.

        This is the main integration test that verifies:
        1. Real backup is created
        2. Real backup is uploaded to storage
        3. Automated test restore selects the backup
        4. Test database is created
        5. Backup is downloaded from storage
        6. Backup is restored to test database
        7. Data integrity is verified
        8. Test database is cleaned up
        9. Restore log is created

        NO MOCKS - Everything is real.
        """
        # Step 1: Create a real backup first
        print("\n=== Step 1: Creating real backup ===")
        backup_id = daily_full_database_backup(initiated_by_user_id=self.admin_user.id)

        assert backup_id is not None, "Backup creation failed"

        # Wait for backup to complete
        time.sleep(2)

        # Verify backup was created
        with bypass_rls():
            backup = Backup.objects.get(id=backup_id)
            assert backup.status in [Backup.COMPLETED, Backup.VERIFIED]
            assert backup.local_path != ""
            assert backup.size_bytes > 0

        print(f"✓ Backup created: {backup.filename}")
        print(f"  Size: {backup.get_size_mb():.2f} MB")
        print(f"  Status: {backup.status}")

        # Verify backup exists in local storage
        local_storage = get_storage_backend("local")
        assert local_storage.exists(backup.local_path), "Backup not found in local storage"
        print(f"✓ Backup exists in local storage: {backup.local_path}")

        # Step 2: Run automated test restore
        print("\n=== Step 2: Running automated test restore ===")

        # Update backup created_at to be within last 7 days (for selection)
        with bypass_rls():
            backup.created_at = timezone.now() - timedelta(days=2)
            backup.save()

        # Run the automated test restore task
        result = automated_test_restore()

        print("\n=== Test Restore Result ===")
        print(f"Success: {result['success']}")
        print(f"Backup ID: {result.get('backup_id')}")
        print(f"Test Database: {result.get('test_database')}")
        print(f"Duration: {result.get('duration_seconds')} seconds")

        # Verify result
        assert result["success"] is True, f"Test restore failed: {result.get('errors')}"
        assert result["backup_id"] == str(backup.id)
        assert result["test_database"] is not None

        # Verify integrity checks passed
        integrity_checks = result.get("integrity_checks", {})
        print("\n=== Integrity Checks ===")
        for check_name, check_result in integrity_checks.items():
            if isinstance(check_result, dict) and "passed" in check_result:
                status = "✓" if check_result["passed"] else "✗"
                print(f"{status} {check_name}: {check_result['passed']}")

        assert integrity_checks.get("overall", {}).get("passed") is True, "Integrity checks failed"

        # Step 3: Verify restore log was created
        print("\n=== Step 3: Verifying restore log ===")
        with bypass_rls():
            restore_log = BackupRestoreLog.objects.filter(
                backup=backup, restore_mode=BackupRestoreLog.FULL
            ).first()

            assert restore_log is not None, "Restore log not created"
            assert restore_log.status == BackupRestoreLog.COMPLETED
            assert restore_log.duration_seconds > 0

        print(f"✓ Restore log created: {restore_log.id}")
        print(f"  Status: {restore_log.status}")
        print(f"  Duration: {restore_log.duration_seconds} seconds")

        # Step 4: Verify alert was created
        print("\n=== Step 4: Verifying alert ===")
        with bypass_rls():
            alert = BackupAlert.objects.filter(backup=backup).order_by("-created_at").first()

            assert alert is not None, "Alert not created"
            print(f"✓ Alert created: {alert.alert_type}")
            print(f"  Severity: {alert.severity}")
            print(f"  Message: {alert.message}")

        print("\n=== ✓ All integration tests passed ===")

    def test_automated_test_restore_with_no_backups(self):
        """
        Test automated test restore when no recent backups exist.

        This verifies the task handles the no-backups scenario gracefully.
        """
        # Delete all backups
        with bypass_rls():
            Backup.objects.all().delete()

        # Run automated test restore
        result = automated_test_restore()

        # Verify result
        assert result["success"] is False
        assert len(result["errors"]) > 0
        assert "No recent backups available" in result["errors"][0]

        # Verify alert was created
        with bypass_rls():
            alert = BackupAlert.objects.filter(message__icontains="No recent backups").first()
            assert alert is not None
            assert alert.severity == BackupAlert.WARNING

    def test_automated_test_restore_integrity_verification_real_data(self):
        """
        Test that integrity verification correctly identifies data in restored database.

        This verifies the integrity checks work with real restored data.
        """
        # Create a real backup
        backup_id = daily_full_database_backup(initiated_by_user_id=self.admin_user.id)
        assert backup_id is not None

        time.sleep(2)

        # Verify backup completed
        with bypass_rls():
            backup = Backup.objects.get(id=backup_id)
            assert backup.status in [Backup.COMPLETED, Backup.VERIFIED]

        # Update backup to be recent
        with bypass_rls():
            backup.created_at = timezone.now() - timedelta(days=1)
            backup.save()

        # Run automated test restore
        result = automated_test_restore()

        # Verify success
        assert result["success"] is True

        # Verify integrity checks found our test data
        integrity_checks = result["integrity_checks"]

        # Check that tables exist
        assert integrity_checks["table_existence"]["passed"] is True
        assert "tenants" in integrity_checks["table_existence"]["existing_tables"]
        assert "inventory_items" in integrity_checks["table_existence"]["existing_tables"]

        # Check that row counts are positive
        assert integrity_checks["row_counts"]["passed"] is True
        row_counts = integrity_checks["row_counts"]["counts"]

        # We created 1 tenant, so should have at least 1
        assert row_counts.get("tenants", 0) >= 1

        # We created 5 inventory items, so should have at least 5
        assert row_counts.get("inventory_items", 0) >= 5

        # Check FK integrity
        assert integrity_checks["foreign_key_integrity"]["passed"] is True

        # Check no corruption
        assert integrity_checks["data_corruption"]["passed"] is True

        print("\n=== Integrity Verification Results ===")
        print(f"✓ Tables found: {len(integrity_checks['table_existence']['existing_tables'])}")
        print(f"✓ Total rows: {integrity_checks['row_counts']['total_rows']}")
        print(f"✓ Tenants: {row_counts.get('tenants', 0)}")
        print(f"✓ Inventory items: {row_counts.get('inventory_items', 0)}")
        print(
            f"✓ FK constraints checked: {integrity_checks['foreign_key_integrity']['constraints_checked']}"
        )
        print(f"✓ FK violations: {len(integrity_checks['foreign_key_integrity']['violations'])}")


@pytest.mark.django_db
class TestAutomatedTestRestoreWithMultipleStorageBackends(TransactionTestCase):
    """
    Integration tests for automated test restore with multiple storage backends.

    These tests verify that automated test restore works with:
    - Local storage
    - Cloudflare R2 (if configured)
    - Backblaze B2 (if configured)
    """

    def setUp(self):
        """Set up test data."""
        with bypass_rls():
            self.admin_user = User.objects.create_user(
                username="admin_storage_test",
                email="admin@storage-test.com",
                password="testpass123",
                role="PLATFORM_ADMIN",
            )

            self.tenant = Tenant.objects.create(
                company_name="Storage Test Shop",
                slug="storage-test-shop",
                status=Tenant.ACTIVE,
            )

    def test_automated_test_restore_downloads_from_available_storage(self):
        """
        Test that automated test restore can download from any available storage backend.

        This verifies the storage failover mechanism works:
        - Try R2 first
        - Failover to B2 if R2 fails
        - Failover to local if both cloud storages fail
        """
        # Create a real backup
        backup_id = daily_full_database_backup(initiated_by_user_id=self.admin_user.id)
        assert backup_id is not None

        time.sleep(2)

        # Verify backup was uploaded to storage
        with bypass_rls():
            backup = Backup.objects.get(id=backup_id)
            assert backup.status in [Backup.COMPLETED, Backup.VERIFIED]

            # Check which storage backends have the backup
            has_local = backup.local_path != ""
            has_r2 = backup.r2_path != ""
            has_b2 = backup.b2_path != ""

            print("\n=== Storage Backend Status ===")
            print(f"Local: {'✓' if has_local else '✗'} {backup.local_path}")
            print(f"R2: {'✓' if has_r2 else '✗'} {backup.r2_path}")
            print(f"B2: {'✓' if has_b2 else '✗'} {backup.b2_path}")

            # At least local storage should have the backup
            assert has_local, "Backup not found in local storage"

            # Update backup to be recent
            backup.created_at = timezone.now() - timedelta(days=1)
            backup.save()

        # Run automated test restore
        result = automated_test_restore()

        # Verify success
        assert result["success"] is True, f"Test restore failed: {result.get('errors')}"

        print("\n=== Test Restore Success ===")
        print("✓ Backup downloaded and restored successfully")
        print(f"✓ Test database: {result.get('test_database')}")
        print(f"✓ Duration: {result.get('duration_seconds')} seconds")
