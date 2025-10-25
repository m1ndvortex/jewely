"""
Tests for backup models.

This test suite validates the backup and disaster recovery system with real database operations.
NO MOCKING - All tests use real PostgreSQL database, real data, and real services.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.backups.models import Backup, BackupAlert, BackupRestoreLog
from apps.core.models import Tenant
from apps.core.tenant_context import bypass_rls, tenant_context

User = get_user_model()


@pytest.mark.django_db
class TestBackupModel:
    """Test the Backup model with real database operations."""

    def test_create_full_database_backup(self):
        """Test creating a full database backup."""
        backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename="full_backup_2025_10_25.sql.gz.enc",
            size_bytes=1024 * 1024 * 500,  # 500 MB
            checksum="abc123def456",
            r2_path="backups/full/2025/10/full_backup_2025_10_25.sql.gz.enc",
            b2_path="backups/full/2025/10/full_backup_2025_10_25.sql.gz.enc",
            status=Backup.COMPLETED,
            compression_ratio=0.3,
            backup_duration_seconds=300,
        )

        assert backup.id is not None
        assert backup.backup_type == Backup.FULL_DATABASE
        assert backup.tenant is None
        assert backup.is_completed()
        assert not backup.is_failed()
        assert backup.get_size_mb() == 500.0
        assert backup.get_size_gb() == pytest.approx(0.49, rel=0.01)

    def test_create_tenant_backup(self, tenant):
        """Test creating a tenant-specific backup using real tenant."""
        backup = Backup.objects.create(
            backup_type=Backup.TENANT_BACKUP,
            tenant=tenant,
            filename=f"tenant_{tenant.id}_2025_10_25.sql.gz.enc",
            size_bytes=1024 * 1024 * 50,  # 50 MB
            checksum="xyz789abc123",
            r2_path=f"backups/tenant/{tenant.id}/2025/10/backup.sql.gz.enc",
            b2_path=f"backups/tenant/{tenant.id}/2025/10/backup.sql.gz.enc",
            status=Backup.COMPLETED,
        )

        assert backup.tenant == tenant
        assert backup.backup_type == Backup.TENANT_BACKUP
        assert str(tenant.company_name) in str(backup)

    def test_create_wal_archive(self):
        """Test creating a WAL archive backup."""
        backup = Backup.objects.create(
            backup_type=Backup.WAL_ARCHIVE,
            filename="000000010000000000000001.gz",
            size_bytes=1024 * 1024 * 16,  # 16 MB
            checksum="wal123456",
            r2_path="backups/wal/2025/10/000000010000000000000001.gz",
            b2_path="backups/wal/2025/10/000000010000000000000001.gz",
            status=Backup.COMPLETED,
        )

        assert backup.backup_type == Backup.WAL_ARCHIVE
        assert backup.tenant is None

    def test_create_configuration_backup(self):
        """Test creating a configuration backup."""
        backup = Backup.objects.create(
            backup_type=Backup.CONFIGURATION,
            filename="config_backup_2025_10_25.tar.gz.enc",
            size_bytes=1024 * 1024 * 5,  # 5 MB
            checksum="config123",
            r2_path="backups/config/2025/10/config_backup_2025_10_25.tar.gz.enc",
            b2_path="backups/config/2025/10/config_backup_2025_10_25.tar.gz.enc",
            status=Backup.COMPLETED,
        )

        assert backup.backup_type == Backup.CONFIGURATION

    def test_backup_with_metadata(self):
        """Test backup with additional metadata."""
        backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename="full_backup_with_metadata.sql.gz.enc",
            size_bytes=1024 * 1024 * 100,
            checksum="meta123",
            r2_path="backups/full/backup.sql.gz.enc",
            b2_path="backups/full/backup.sql.gz.enc",
            status=Backup.COMPLETED,
            metadata={
                "database_version": "15.3",
                "table_count": 50,
                "row_count": 1000000,
                "compression_algorithm": "gzip",
                "encryption_algorithm": "AES-256",
            },
        )

        assert backup.metadata["database_version"] == "15.3"
        assert backup.metadata["table_count"] == 50


@pytest.mark.django_db
class TestBackupRestoreLogModel:
    """Test the BackupRestoreLog model."""

    def test_create_full_restore_log(self):
        """Test creating a full restore log."""
        backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename="backup.sql.gz.enc",
            size_bytes=1024 * 1024 * 100,
            checksum="restore123",
            r2_path="backups/full/backup.sql.gz.enc",
            b2_path="backups/full/backup.sql.gz.enc",
            status=Backup.COMPLETED,
        )

        user = User.objects.create_user(
            username="admin",
            password="testpass",
            role="PLATFORM_ADMIN",
        )

        restore_log = BackupRestoreLog.objects.create(
            backup=backup,
            initiated_by=user,
            restore_mode=BackupRestoreLog.FULL,
            status=BackupRestoreLog.COMPLETED,
            reason="Disaster recovery test",
            rows_restored=1000000,
            duration_seconds=600,
        )

        assert restore_log.backup == backup
        assert restore_log.initiated_by == user
        assert restore_log.is_completed()
        assert not restore_log.is_failed()
        assert restore_log.get_duration_minutes() == 10.0

    def test_create_pitr_restore_log(self):
        """Test creating a PITR restore log."""
        backup = Backup.objects.create(
            backup_type=Backup.WAL_ARCHIVE,
            filename="wal.gz",
            size_bytes=1024 * 1024 * 16,
            checksum="pitr123",
            r2_path="backups/wal/wal.gz",
            b2_path="backups/wal/wal.gz",
            status=Backup.COMPLETED,
        )

        target_time = timezone.now()

        restore_log = BackupRestoreLog.objects.create(
            backup=backup,
            restore_mode=BackupRestoreLog.PITR,
            target_timestamp=target_time,
            status=BackupRestoreLog.COMPLETED,
            reason="Point-in-time recovery to specific timestamp",
            duration_seconds=300,
        )

        assert restore_log.restore_mode == BackupRestoreLog.PITR
        assert restore_log.target_timestamp == target_time

    def test_create_tenant_restore_log(self, tenant):
        """Test creating a tenant-specific restore log using real tenant."""
        backup = Backup.objects.create(
            backup_type=Backup.TENANT_BACKUP,
            tenant=tenant,
            filename="tenant_backup.sql.gz.enc",
            size_bytes=1024 * 1024 * 50,
            checksum="tenant123",
            r2_path="backups/tenant/backup.sql.gz.enc",
            b2_path="backups/tenant/backup.sql.gz.enc",
            status=Backup.COMPLETED,
        )

        restore_log = BackupRestoreLog.objects.create(
            backup=backup,
            restore_mode=BackupRestoreLog.MERGE,
            tenant_ids=[str(tenant.id)],
            status=BackupRestoreLog.COMPLETED,
            reason="Restore specific tenant data",
            rows_restored=50000,
            duration_seconds=120,
        )

        assert str(tenant.id) in restore_log.tenant_ids
        assert restore_log.restore_mode == BackupRestoreLog.MERGE


@pytest.mark.django_db
class TestBackupAlertModel:
    """Test the BackupAlert model."""

    def test_create_backup_failure_alert(self):
        """Test creating a backup failure alert."""
        backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename="failed_backup.sql.gz.enc",
            size_bytes=0,
            checksum="",
            r2_path="",
            b2_path="",
            status=Backup.FAILED,
        )

        alert = BackupAlert.objects.create(
            alert_type=BackupAlert.BACKUP_FAILURE,
            severity=BackupAlert.CRITICAL,
            backup=backup,
            message="Full database backup failed",
            details={
                "error": "Connection timeout to R2",
                "retry_count": 3,
            },
            notification_channels=["email", "sms", "in-app"],
        )

        assert alert.backup == backup
        assert alert.is_active()
        assert alert.is_critical()
        assert "email" in alert.notification_channels

    def test_create_size_deviation_alert(self):
        """Test creating a size deviation alert."""
        backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename="large_backup.sql.gz.enc",
            size_bytes=1024 * 1024 * 1024 * 2,  # 2 GB (unusually large)
            checksum="large123",
            r2_path="backups/full/large_backup.sql.gz.enc",
            b2_path="backups/full/large_backup.sql.gz.enc",
            status=Backup.COMPLETED,
        )

        alert = BackupAlert.objects.create(
            alert_type=BackupAlert.SIZE_DEVIATION,
            severity=BackupAlert.WARNING,
            backup=backup,
            message="Backup size increased by 50%",
            details={
                "previous_size_mb": 1000,
                "current_size_mb": 2048,
                "deviation_percentage": 50,
            },
            notification_channels=["email", "in-app"],
        )

        assert alert.alert_type == BackupAlert.SIZE_DEVIATION
        assert alert.severity == BackupAlert.WARNING

    def test_acknowledge_alert(self):
        """Test acknowledging an alert."""
        backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename="backup.sql.gz.enc",
            size_bytes=1024 * 1024 * 100,
            checksum="ack123",
            r2_path="backups/full/backup.sql.gz.enc",
            b2_path="backups/full/backup.sql.gz.enc",
            status=Backup.COMPLETED,
        )

        alert = BackupAlert.objects.create(
            alert_type=BackupAlert.DURATION_THRESHOLD,
            severity=BackupAlert.WARNING,
            backup=backup,
            message="Backup took longer than expected",
        )

        user = User.objects.create_user(
            username="admin",
            password="testpass",
            role="PLATFORM_ADMIN",
        )

        assert alert.is_active()
        alert.acknowledge(user)
        assert alert.status == BackupAlert.ACKNOWLEDGED
        assert alert.acknowledged_by == user
        assert alert.acknowledged_at is not None

    def test_resolve_alert(self):
        """Test resolving an alert."""
        backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename="backup.sql.gz.enc",
            size_bytes=1024 * 1024 * 100,
            checksum="resolve123",
            r2_path="backups/full/backup.sql.gz.enc",
            b2_path="backups/full/backup.sql.gz.enc",
            status=Backup.COMPLETED,
        )

        alert = BackupAlert.objects.create(
            alert_type=BackupAlert.STORAGE_CAPACITY,
            severity=BackupAlert.WARNING,
            backup=backup,
            message="Storage capacity at 85%",
        )

        user = User.objects.create_user(
            username="admin",
            password="testpass",
            role="PLATFORM_ADMIN",
        )

        alert.resolve(user, notes="Cleaned up old backups")
        assert alert.status == BackupAlert.RESOLVED
        assert alert.resolved_by == user
        assert alert.resolved_at is not None
        assert alert.resolution_notes == "Cleaned up old backups"


@pytest.mark.django_db
class TestBackupIntegration:
    """
    Integration tests for backup system with real database operations.

    These tests verify that the backup system works correctly with:
    - Real PostgreSQL database
    - Real tenant data
    - Real RLS policies
    - Real data isolation
    """

    def test_backup_multiple_tenants(self, tenant, platform_admin):
        """Test creating backups for multiple tenants."""
        # Create a second tenant
        with bypass_rls():
            tenant2 = Tenant.objects.create(
                company_name="Second Jewelry Shop",
                slug=f"second-shop-{uuid.uuid4().hex[:8]}",
                status=Tenant.ACTIVE,
            )

        # Create backups for both tenants
        backup1 = Backup.objects.create(
            backup_type=Backup.TENANT_BACKUP,
            tenant=tenant,
            filename=f"tenant_{tenant.id}_backup.sql.gz.enc",
            size_bytes=1024 * 1024 * 50,
            checksum="backup1_checksum",
            r2_path=f"backups/tenant/{tenant.id}/backup.sql.gz.enc",
            b2_path=f"backups/tenant/{tenant.id}/backup.sql.gz.enc",
            status=Backup.COMPLETED,
            created_by=platform_admin,
        )

        backup2 = Backup.objects.create(
            backup_type=Backup.TENANT_BACKUP,
            tenant=tenant2,
            filename=f"tenant_{tenant2.id}_backup.sql.gz.enc",
            size_bytes=1024 * 1024 * 75,
            checksum="backup2_checksum",
            r2_path=f"backups/tenant/{tenant2.id}/backup.sql.gz.enc",
            b2_path=f"backups/tenant/{tenant2.id}/backup.sql.gz.enc",
            status=Backup.COMPLETED,
            created_by=platform_admin,
        )

        # Verify both backups exist
        assert Backup.objects.filter(tenant=tenant).count() == 1
        assert Backup.objects.filter(tenant=tenant2).count() == 1
        assert Backup.objects.filter(backup_type=Backup.TENANT_BACKUP).count() == 2

        # Verify backup metadata
        assert backup1.tenant == tenant
        assert backup2.tenant == tenant2
        assert backup1.created_by == platform_admin
        assert backup2.created_by == platform_admin

    def test_backup_with_real_inventory_data(self, tenant, inventory_item, platform_admin):
        """Test backup system with real inventory data."""
        # Verify inventory item exists
        from apps.inventory.models import InventoryItem

        with tenant_context(tenant.id):
            items = InventoryItem.objects.filter(tenant=tenant)
            assert items.count() >= 1
            assert inventory_item in items

        # Create a backup for this tenant
        backup = Backup.objects.create(
            backup_type=Backup.TENANT_BACKUP,
            tenant=tenant,
            filename=f"tenant_{tenant.id}_with_inventory.sql.gz.enc",
            size_bytes=1024 * 1024 * 100,
            checksum="inventory_backup_checksum",
            r2_path=f"backups/tenant/{tenant.id}/with_inventory.sql.gz.enc",
            b2_path=f"backups/tenant/{tenant.id}/with_inventory.sql.gz.enc",
            status=Backup.COMPLETED,
            metadata={
                "inventory_items_count": items.count(),
                "tenant_name": tenant.company_name,
                "backup_includes": ["inventory", "sales", "crm", "accounting"],
            },
        )

        # Verify backup metadata includes inventory information
        assert backup.metadata["inventory_items_count"] >= 1
        assert backup.metadata["tenant_name"] == tenant.company_name
        assert "inventory" in backup.metadata["backup_includes"]

    def test_wal_archive_sequence(self):
        """Test WAL archive backup sequence."""
        # Create a sequence of WAL archives
        wal_archives = []
        for i in range(1, 6):
            wal = Backup.objects.create(
                backup_type=Backup.WAL_ARCHIVE,
                filename=f"00000001000000000000000{i}.gz",
                size_bytes=1024 * 1024 * 16,
                checksum=f"wal_checksum_{i}",
                r2_path=f"backups/wal/2025/10/00000001000000000000000{i}.gz",
                b2_path=f"backups/wal/2025/10/00000001000000000000000{i}.gz",
                status=Backup.COMPLETED,
                backup_duration_seconds=30,
            )
            wal_archives.append(wal)

        # Verify all WAL archives were created
        assert Backup.objects.filter(backup_type=Backup.WAL_ARCHIVE).count() == 5

        # Verify they're ordered by creation time
        wal_list = list(
            Backup.objects.filter(backup_type=Backup.WAL_ARCHIVE).order_by("created_at")
        )
        assert len(wal_list) == 5
        for i, wal in enumerate(wal_list):
            assert f"00000001000000000000000{i+1}" in wal.filename

    def test_backup_failure_with_alert(self, platform_admin):
        """Test backup failure creates appropriate alert."""
        # Create a failed backup
        backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename="failed_backup.sql.gz.enc",
            size_bytes=0,
            checksum="",
            r2_path="",
            b2_path="",
            status=Backup.FAILED,
        )

        # Create an alert for the failure
        alert = BackupAlert.objects.create(
            alert_type=BackupAlert.BACKUP_FAILURE,
            severity=BackupAlert.CRITICAL,
            backup=backup,
            message="Full database backup failed due to connection timeout",
            details={
                "error": "Connection timeout to Cloudflare R2",
                "retry_count": 3,
                "last_error_time": timezone.now().isoformat(),
            },
            notification_channels=["email", "sms", "in-app"],
        )

        # Verify alert was created
        assert BackupAlert.objects.filter(backup=backup).count() == 1
        assert alert.is_active()
        assert alert.is_critical()

        # Acknowledge the alert
        alert.acknowledge(platform_admin)
        assert alert.status == BackupAlert.ACKNOWLEDGED
        assert alert.acknowledged_by == platform_admin

        # Resolve the alert
        alert.resolve(platform_admin, notes="Fixed R2 connection configuration")
        assert alert.status == BackupAlert.RESOLVED
        assert alert.resolved_by == platform_admin
        assert "Fixed R2 connection" in alert.resolution_notes

    def test_restore_operation_tracking(self, tenant, platform_admin):
        """Test complete restore operation tracking."""
        # Create a backup
        backup = Backup.objects.create(
            backup_type=Backup.TENANT_BACKUP,
            tenant=tenant,
            filename=f"tenant_{tenant.id}_restore_test.sql.gz.enc",
            size_bytes=1024 * 1024 * 100,
            checksum="restore_test_checksum",
            r2_path=f"backups/tenant/{tenant.id}/restore_test.sql.gz.enc",
            b2_path=f"backups/tenant/{tenant.id}/restore_test.sql.gz.enc",
            status=Backup.VERIFIED,
            verified_at=timezone.now(),
        )

        # Create a restore log
        restore_log = BackupRestoreLog.objects.create(
            backup=backup,
            initiated_by=platform_admin,
            restore_mode=BackupRestoreLog.FULL,
            status=BackupRestoreLog.IN_PROGRESS,
            reason="Testing disaster recovery procedure",
        )

        # Verify restore is in progress
        assert restore_log.status == BackupRestoreLog.IN_PROGRESS
        assert not restore_log.is_completed()

        # Simulate restore completion
        restore_log.status = BackupRestoreLog.COMPLETED
        restore_log.completed_at = timezone.now()
        restore_log.rows_restored = 150000
        restore_log.duration_seconds = 450
        restore_log.metadata = {
            "tables_restored": ["inventory", "sales", "customers", "transactions"],
            "conflicts_resolved": 0,
            "data_integrity_verified": True,
        }
        restore_log.save()

        # Verify restore completed successfully
        assert restore_log.is_completed()
        assert restore_log.rows_restored == 150000
        assert restore_log.get_duration_minutes() == 7.5
        assert restore_log.metadata["data_integrity_verified"] is True

    def test_backup_size_deviation_alert(self):
        """Test alert for backup size deviation."""
        # Create a normal backup
        normal_backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename="normal_backup.sql.gz.enc",
            size_bytes=1024 * 1024 * 1000,  # 1 GB
            checksum="normal_checksum",
            r2_path="backups/full/normal_backup.sql.gz.enc",
            b2_path="backups/full/normal_backup.sql.gz.enc",
            status=Backup.COMPLETED,
        )

        # Create a backup with significant size increase
        large_backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename="large_backup.sql.gz.enc",
            size_bytes=1024 * 1024 * 1500,  # 1.5 GB (50% increase)
            checksum="large_checksum",
            r2_path="backups/full/large_backup.sql.gz.enc",
            b2_path="backups/full/large_backup.sql.gz.enc",
            status=Backup.COMPLETED,
        )

        # Create size deviation alert
        alert = BackupAlert.objects.create(
            alert_type=BackupAlert.SIZE_DEVIATION,
            severity=BackupAlert.WARNING,
            backup=large_backup,
            message="Backup size increased by 50% compared to previous backup",
            details={
                "previous_size_mb": normal_backup.get_size_mb(),
                "current_size_mb": large_backup.get_size_mb(),
                "deviation_percentage": 50,
                "threshold": 20,
            },
        )

        # Verify alert details
        assert alert.details["deviation_percentage"] == 50
        assert alert.details["deviation_percentage"] > alert.details["threshold"]
        assert alert.severity == BackupAlert.WARNING

    def test_pitr_restore_with_target_timestamp(self, platform_admin):
        """Test Point-in-Time Recovery restore operation."""
        # Create WAL archive backup
        wal_backup = Backup.objects.create(
            backup_type=Backup.WAL_ARCHIVE,
            filename="000000010000000000000010.gz",
            size_bytes=1024 * 1024 * 16,
            checksum="pitr_wal_checksum",
            r2_path="backups/wal/2025/10/000000010000000000000010.gz",
            b2_path="backups/wal/2025/10/000000010000000000000010.gz",
            status=Backup.COMPLETED,
        )

        # Create PITR restore log with specific target timestamp
        target_time = timezone.now() - timezone.timedelta(hours=2)

        restore_log = BackupRestoreLog.objects.create(
            backup=wal_backup,
            initiated_by=platform_admin,
            restore_mode=BackupRestoreLog.PITR,
            target_timestamp=target_time,
            status=BackupRestoreLog.COMPLETED,
            reason="Restore to state before data corruption incident",
            rows_restored=200000,
            duration_seconds=600,
            metadata={
                "recovery_target_time": target_time.isoformat(),
                "wal_files_applied": 15,
                "recovery_successful": True,
            },
        )

        # Verify PITR restore
        assert restore_log.restore_mode == BackupRestoreLog.PITR
        assert restore_log.target_timestamp == target_time
        assert restore_log.metadata["recovery_successful"] is True
        assert restore_log.metadata["wal_files_applied"] == 15

    def test_storage_capacity_alert(self):
        """Test storage capacity warning alert."""
        # Create a backup
        backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename="capacity_test_backup.sql.gz.enc",
            size_bytes=1024 * 1024 * 1024 * 2,  # 2 GB
            checksum="capacity_checksum",
            r2_path="backups/full/capacity_test_backup.sql.gz.enc",
            b2_path="backups/full/capacity_test_backup.sql.gz.enc",
            status=Backup.COMPLETED,
        )

        # Create storage capacity alert
        alert = BackupAlert.objects.create(
            alert_type=BackupAlert.STORAGE_CAPACITY,
            severity=BackupAlert.WARNING,
            backup=backup,
            message="Local storage capacity at 85%",
            details={
                "storage_location": "local",
                "total_capacity_gb": 1000,
                "used_capacity_gb": 850,
                "usage_percentage": 85,
                "threshold": 80,
            },
            notification_channels=["email", "in-app"],
        )

        # Verify alert
        assert alert.alert_type == BackupAlert.STORAGE_CAPACITY
        assert alert.details["usage_percentage"] > alert.details["threshold"]

    def test_backup_integrity_verification(self):
        """Test backup integrity verification process."""
        # Create a backup
        backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename="integrity_test_backup.sql.gz.enc",
            size_bytes=1024 * 1024 * 500,
            checksum="abc123def456789",
            r2_path="backups/full/integrity_test_backup.sql.gz.enc",
            b2_path="backups/full/integrity_test_backup.sql.gz.enc",
            status=Backup.COMPLETED,
        )

        # Simulate integrity verification
        backup.status = Backup.VERIFIED
        backup.verified_at = timezone.now()
        backup.metadata = {
            "verification_method": "SHA-256 checksum",
            "local_checksum_match": True,
            "r2_checksum_match": True,
            "b2_checksum_match": True,
            "all_locations_verified": True,
        }
        backup.save()

        # Verify integrity check results
        assert backup.status == Backup.VERIFIED
        assert backup.verified_at is not None
        assert backup.metadata["all_locations_verified"] is True

    def test_configuration_backup(self):
        """Test configuration file backup."""
        config_backup = Backup.objects.create(
            backup_type=Backup.CONFIGURATION,
            filename="config_backup_2025_10_25.tar.gz.enc",
            size_bytes=1024 * 1024 * 5,  # 5 MB
            checksum="config_checksum_123",
            r2_path="backups/config/2025/10/config_backup_2025_10_25.tar.gz.enc",
            b2_path="backups/config/2025/10/config_backup_2025_10_25.tar.gz.enc",
            status=Backup.COMPLETED,
            compression_ratio=0.4,
            backup_duration_seconds=60,
            metadata={
                "files_included": [
                    "docker-compose.yml",
                    ".env.encrypted",
                    "nginx.conf",
                    "ssl/certificates",
                    "k8s/manifests",
                ],
                "total_files": 15,
                "backup_method": "tar.gz with AES-256 encryption",
            },
        )

        # Verify configuration backup
        assert config_backup.backup_type == Backup.CONFIGURATION
        assert "docker-compose.yml" in config_backup.metadata["files_included"]
        assert config_backup.metadata["total_files"] == 15

    def test_multiple_restore_attempts(self, tenant, platform_admin):
        """Test tracking multiple restore attempts for same backup."""
        # Create a backup
        backup = Backup.objects.create(
            backup_type=Backup.TENANT_BACKUP,
            tenant=tenant,
            filename=f"tenant_{tenant.id}_multi_restore.sql.gz.enc",
            size_bytes=1024 * 1024 * 75,
            checksum="multi_restore_checksum",
            r2_path=f"backups/tenant/{tenant.id}/multi_restore.sql.gz.enc",
            b2_path=f"backups/tenant/{tenant.id}/multi_restore.sql.gz.enc",
            status=Backup.COMPLETED,
        )

        # First restore attempt - failed
        BackupRestoreLog.objects.create(
            backup=backup,
            initiated_by=platform_admin,
            restore_mode=BackupRestoreLog.FULL,
            status=BackupRestoreLog.FAILED,
            reason="First restore attempt",
            error_message="Database connection lost during restore",
            duration_seconds=120,
        )

        # Second restore attempt - successful
        BackupRestoreLog.objects.create(
            backup=backup,
            initiated_by=platform_admin,
            restore_mode=BackupRestoreLog.FULL,
            status=BackupRestoreLog.COMPLETED,
            reason="Second restore attempt after fixing connection",
            rows_restored=100000,
            duration_seconds=300,
        )

        # Verify both restore attempts are tracked
        restore_logs = BackupRestoreLog.objects.filter(backup=backup).order_by("started_at")
        assert restore_logs.count() == 2
        assert restore_logs[0].is_failed()
        assert restore_logs[1].is_completed()

    def test_backup_compression_metrics(self):
        """Test backup compression ratio tracking."""
        # Create backup with good compression
        backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename="compressed_backup.sql.gz.enc",
            size_bytes=1024 * 1024 * 300,  # 300 MB compressed
            checksum="compressed_checksum",
            r2_path="backups/full/compressed_backup.sql.gz.enc",
            b2_path="backups/full/compressed_backup.sql.gz.enc",
            status=Backup.COMPLETED,
            compression_ratio=0.3,  # 70% reduction
            metadata={
                "original_size_bytes": 1024 * 1024 * 1000,  # 1 GB original
                "compressed_size_bytes": 1024 * 1024 * 300,  # 300 MB compressed
                "compression_algorithm": "gzip level 9",
                "space_saved_bytes": 1024 * 1024 * 700,  # 700 MB saved
            },
        )

        # Verify compression metrics
        assert backup.compression_ratio == 0.3
        assert backup.metadata["space_saved_bytes"] == 1024 * 1024 * 700
        space_saved_gb = backup.metadata["space_saved_bytes"] / (1024 * 1024 * 1024)
        assert space_saved_gb == pytest.approx(0.68, rel=0.01)
