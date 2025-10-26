"""
Management command to test backup functionality.

This command triggers a backup and waits for it to complete,
providing real-time feedback on the backup process.
"""

from django.core.management.base import BaseCommand

from apps.backups.tasks import daily_full_database_backup


class Command(BaseCommand):
    help = "Test backup functionality by creating a full database backup"

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("Starting backup test..."))
        self.stdout.write("=" * 80)

        try:
            # Call the task directly (synchronously)
            backup_id = daily_full_database_backup()

            if backup_id:
                self.stdout.write(self.style.SUCCESS("\n✓ Backup completed successfully!"))
                self.stdout.write(f"Backup ID: {backup_id}")

                # Verify the backup
                from apps.backups.models import Backup
                from apps.core.tenant_context import bypass_rls

                with bypass_rls():
                    backup = Backup.objects.get(id=backup_id)
                    self.stdout.write("\nBackup Details:")
                    self.stdout.write(f"  Filename: {backup.filename}")
                    self.stdout.write(f"  Status: {backup.status}")
                    self.stdout.write(f"  Size: {backup.get_size_mb()} MB")
                    self.stdout.write(f"  Compression: {backup.compression_ratio * 100:.1f}%")
                    self.stdout.write(f"  Local: {'✓' if backup.local_path else '✗'}")
                    self.stdout.write(f"  R2: {'✓' if backup.r2_path else '✗'}")
                    self.stdout.write(f"  B2: {'✓' if backup.b2_path else '✗'}")
                    self.stdout.write(f"  Checksum: {backup.checksum[:32]}...")

                self.stdout.write("\n" + "=" * 80)
                self.stdout.write(self.style.SUCCESS("Backup test PASSED"))
                self.stdout.write("=" * 80)
            else:
                self.stdout.write(self.style.ERROR("\n✗ Backup failed - no backup ID returned"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n✗ Backup failed with error: {e}"))
            import traceback

            traceback.print_exc()
            raise
