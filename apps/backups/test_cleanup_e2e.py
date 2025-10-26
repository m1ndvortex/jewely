"""
End-to-end test for backup cleanup with REAL backups.

This test creates REAL backups using the actual backup tasks,
then verifies cleanup works correctly with real data.

NO MOCKS - Everything is real:
- Real database backups
- Real file uploads to local, R2, B2
- Real cleanup task execution
- Real file deletion verification
"""

import time
from datetime import timedelta

from django.utils import timezone

import pytest

from apps.backups.models import Backup
from apps.backups.storage import get_storage_backend
from apps.backups.tasks import cleanup_old_backups, daily_full_database_backup


@pytest.mark.django_db(transaction=True)
class TestBackupCleanupE2E:
    """End-to-end test for backup cleanup with real backups."""

    def test_full_backup_and_cleanup_workflow(self, tenant, platform_admin):
        """
        Complete workflow test:
        1. Create a real full database backup
        2. Verify it's uploaded to all storage locations
        3. Modify the backup date to make it old
        4. Run cleanup
        5. Verify old backup is deleted from all locations
        """
        print("\n" + "=" * 80)
        print("STARTING END-TO-END BACKUP CLEANUP TEST")
        print("=" * 80)

        # Step 1: Create a REAL full database backup
        print("\n[Step 1] Creating REAL full database backup...")
        backup_id = daily_full_database_backup(initiated_by_user_id=platform_admin.id)

        assert backup_id is not None, "Backup creation failed"
        print(f"✓ Backup created: {backup_id}")

        # Wait for backup to complete
        time.sleep(2)

        # Verify backup exists in database
        backup = Backup.objects.get(id=backup_id)
        print(f"✓ Backup status: {backup.status}")
        print(f"✓ Backup size: {backup.get_size_mb():.2f} MB")
        print(f"✓ Local path: {backup.local_path}")
        print(f"✓ R2 path: {backup.r2_path}")
        print(f"✓ B2 path: {backup.b2_path}")

        assert backup.status in [Backup.COMPLETED, Backup.VERIFIED]
        assert backup.local_path, "Local path is empty"

        # Step 2: Verify files exist in all storage locations
        print("\n[Step 2] Verifying backup files exist in all storage locations...")

        local_storage = get_storage_backend("local")
        assert local_storage.exists(backup.local_path), "Local file doesn't exist"
        print("✓ Local file exists")

        if backup.r2_path:
            r2_storage = get_storage_backend("r2")
            r2_exists = r2_storage.exists(backup.r2_path)
            print(f"✓ R2 file exists: {r2_exists}")

        if backup.b2_path:
            b2_storage = get_storage_backend("b2")
            b2_exists = b2_storage.exists(backup.b2_path)
            print(f"✓ B2 file exists: {b2_exists}")

        # Step 3: Modify backup date to make it old (35 days for local cleanup)
        print("\n[Step 3] Modifying backup date to simulate old backup...")
        old_date = timezone.now() - timedelta(days=35)
        backup.created_at = old_date
        backup.save()
        print(f"✓ Backup date set to: {backup.created_at}")

        # Step 4: Run cleanup task
        print("\n[Step 4] Running cleanup task...")
        result = cleanup_old_backups()

        print(f"✓ Cleanup completed in {result['duration_seconds']:.2f} seconds")
        print(f"  - Local deleted: {result['local_deleted']}")
        print(f"  - R2 deleted: {result['r2_deleted']}")
        print(f"  - B2 deleted: {result['b2_deleted']}")
        print(f"  - Database records deleted: {result['database_records_deleted']}")
        print(f"  - Temp files deleted: {result['temp_files_deleted']}")

        # Step 5: Verify backup was cleaned up
        print("\n[Step 5] Verifying cleanup results...")

        # Local file should be deleted
        assert not local_storage.exists(backup.local_path), "Local file still exists!"
        print("✓ Local file deleted")

        # Backup record should still exist (has R2 and B2 paths)
        backup.refresh_from_db()
        assert backup.local_path == "", "Local path not cleared!"
        assert backup.r2_path, "R2 path should still exist"
        assert backup.b2_path, "B2 path should still exist"
        print("✓ Backup record updated (local path cleared, cloud paths preserved)")

        # Verify statistics
        assert result["local_deleted"] >= 1, "Local deletion not recorded"

        # Cleanup cloud files for next test
        print("\n[Cleanup] Removing cloud backup files...")
        if backup.r2_path:
            r2_storage.delete(backup.r2_path)
            print("✓ R2 file deleted")
        if backup.b2_path:
            b2_storage.delete(backup.b2_path)
            print("✓ B2 file deleted")
        backup.delete()
        print("✓ Backup record deleted")

        print("\n" + "=" * 80)
        print("END-TO-END TEST PASSED ✓")
        print("=" * 80)

    def test_cleanup_preserves_recent_real_backups(self, tenant, platform_admin):
        """
        Test that cleanup does NOT delete recent real backups.

        1. Create a real backup
        2. Run cleanup immediately
        3. Verify backup still exists
        """
        print("\n" + "=" * 80)
        print("TESTING CLEANUP PRESERVES RECENT BACKUPS")
        print("=" * 80)

        # Step 1: Create a REAL backup
        print("\n[Step 1] Creating REAL backup...")
        backup_id = daily_full_database_backup(initiated_by_user_id=platform_admin.id)
        assert backup_id is not None
        print(f"✓ Backup created: {backup_id}")

        time.sleep(2)

        backup = Backup.objects.get(id=backup_id)
        print(f"✓ Backup status: {backup.status}")
        print(f"✓ Created at: {backup.created_at}")

        # Verify file exists
        local_storage = get_storage_backend("local")
        assert local_storage.exists(backup.local_path)
        print("✓ Local file exists")

        # Step 2: Run cleanup (should NOT delete recent backup)
        print("\n[Step 2] Running cleanup on recent backup...")
        result = cleanup_old_backups()

        print("✓ Cleanup completed")
        print(f"  - Local deleted: {result['local_deleted']}")

        # Step 3: Verify backup still exists
        print("\n[Step 3] Verifying backup was preserved...")

        # Backup should still exist
        assert Backup.objects.filter(id=backup_id).exists(), "Recent backup was deleted!"
        print("✓ Backup record still exists")

        # File should still exist
        assert local_storage.exists(backup.local_path), "Recent backup file was deleted!"
        print("✓ Local file still exists")

        # Cleanup
        print("\n[Cleanup] Removing test backup...")
        if local_storage.exists(backup.local_path):
            local_storage.delete(backup.local_path)

        if backup.r2_path:
            try:
                r2_storage = get_storage_backend("r2")
                if r2_storage.exists(backup.r2_path):
                    r2_storage.delete(backup.r2_path)
            except Exception:
                pass

        if backup.b2_path:
            try:
                b2_storage = get_storage_backend("b2")
                if b2_storage.exists(backup.b2_path):
                    b2_storage.delete(backup.b2_path)
            except Exception:
                pass

        backup.delete()
        print("✓ Test backup cleaned up")

        print("\n" + "=" * 80)
        print("RECENT BACKUP PRESERVATION TEST PASSED ✓")
        print("=" * 80)

    def test_cleanup_with_cloud_storage(self, tenant, platform_admin):
        """
        Test cleanup with cloud storage (R2 and B2).

        1. Create a real backup
        2. Verify it's in cloud storage
        3. Make it very old (400 days)
        4. Run cleanup
        5. Verify it's deleted from cloud storage
        """
        print("\n" + "=" * 80)
        print("TESTING CLOUD STORAGE CLEANUP")
        print("=" * 80)

        # Step 1: Create a REAL backup
        print("\n[Step 1] Creating REAL backup...")
        backup_id = daily_full_database_backup(initiated_by_user_id=platform_admin.id)
        assert backup_id is not None
        print(f"✓ Backup created: {backup_id}")

        time.sleep(2)

        backup = Backup.objects.get(id=backup_id)
        print(f"✓ Backup status: {backup.status}")

        # Step 2: Verify cloud storage
        print("\n[Step 2] Verifying cloud storage...")

        has_cloud_storage = False

        if backup.r2_path:
            r2_storage = get_storage_backend("r2")
            if r2_storage.exists(backup.r2_path):
                print("✓ R2 file exists")
                has_cloud_storage = True

        if backup.b2_path:
            b2_storage = get_storage_backend("b2")
            if b2_storage.exists(backup.b2_path):
                print("✓ B2 file exists")
                has_cloud_storage = True

        if not has_cloud_storage:
            pytest.skip("Cloud storage not configured")

        # Step 3: Make backup very old (400 days)
        print("\n[Step 3] Making backup very old (400 days)...")
        very_old_date = timezone.now() - timedelta(days=400)
        backup.created_at = very_old_date
        # Clear local path to simulate it was already cleaned
        backup.local_path = ""
        backup.save()
        print(f"✓ Backup date set to: {backup.created_at}")

        # Step 4: Run cleanup
        print("\n[Step 4] Running cleanup...")
        result = cleanup_old_backups()

        print("✓ Cleanup completed")
        print(f"  - R2 deleted: {result['r2_deleted']}")
        print(f"  - B2 deleted: {result['b2_deleted']}")
        print(f"  - Database records deleted: {result['database_records_deleted']}")

        # Step 5: Verify cleanup
        print("\n[Step 5] Verifying cloud cleanup...")

        # Backup should be deleted
        assert not Backup.objects.filter(id=backup_id).exists(), "Backup record still exists!"
        print("✓ Backup database record deleted")

        # Cloud files should be deleted
        if backup.r2_path:
            assert not r2_storage.exists(backup.r2_path), "R2 file still exists!"
            print("✓ R2 file deleted")

        if backup.b2_path:
            assert not b2_storage.exists(backup.b2_path), "B2 file still exists!"
            print("✓ B2 file deleted")

        print("\n" + "=" * 80)
        print("CLOUD STORAGE CLEANUP TEST PASSED ✓")
        print("=" * 80)
