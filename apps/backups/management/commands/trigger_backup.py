"""
Management command to trigger backups manually.

This command is used by:
- CI/CD pipeline before production deployments
- Manual backup operations
- Scheduled backup tasks
"""

from django.core.management.base import BaseCommand, CommandError

from apps.backups.tasks import (
    perform_configuration_backup,
    perform_full_database_backup,
    perform_tenant_backup,
)


class Command(BaseCommand):
    help = 'Trigger a backup manually'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['full', 'tenant', 'config'],
            default='full',
            help='Type of backup to perform (full, tenant, or config)'
        )
        parser.add_argument(
            '--tenant-id',
            type=str,
            help='Tenant ID for tenant-specific backup'
        )
        parser.add_argument(
            '--async',
            action='store_true',
            help='Run backup asynchronously using Celery'
        )

    def handle(self, *args, **options):
        backup_type = options['type']
        tenant_id = options.get('tenant_id')
        run_async = options.get('async', False)

        self.stdout.write(f"Triggering {backup_type} backup...")

        try:
            if backup_type == 'full':
                if run_async:
                    task = perform_full_database_backup.delay()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Full database backup task queued: {task.id}'
                        )
                    )
                else:
                    result = perform_full_database_backup()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Full database backup completed: {result}'
                        )
                    )

            elif backup_type == 'tenant':
                if not tenant_id:
                    raise CommandError('--tenant-id is required for tenant backups')

                if run_async:
                    task = perform_tenant_backup.delay(tenant_id)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Tenant backup task queued: {task.id}'
                        )
                    )
                else:
                    result = perform_tenant_backup(tenant_id)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Tenant backup completed: {result}'
                        )
                    )

            elif backup_type == 'config':
                if run_async:
                    task = perform_configuration_backup.delay()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Configuration backup task queued: {task.id}'
                        )
                    )
                else:
                    result = perform_configuration_backup()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Configuration backup completed: {result}'
                        )
                    )

        except Exception as e:
            raise CommandError(f'Backup failed: {str(e)}')
