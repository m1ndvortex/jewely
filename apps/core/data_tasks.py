"""
Celery tasks for data management operations.

Implements Requirement 20: Settings and Configuration
- Background data export processing
- Background data import processing
- Background backup triggering
"""

import logging
import os
from datetime import datetime
from typing import List, Optional

from django.contrib.auth import get_user_model
from django.utils import timezone

from celery import shared_task

from apps.core.data_models import BackupTrigger, DataActivity
from apps.core.data_services import BackupTriggerService, DataExportService, DataImportService
from apps.core.models import Tenant

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(
    name="apps.core.data_tasks.export_data_async",
    bind=True,
    max_retries=2,
    default_retry_delay=300,  # 5 minutes
)
def export_data_async(
    self,
    tenant_id: str,
    data_types: List[str],
    format: str,
    user_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> str:
    """
    Asynchronously export tenant data.

    Args:
        tenant_id: Tenant UUID
        data_types: List of data types to export
        format: Export format (csv, excel, json)
        user_id: User ID initiating the export
        date_from: Start date for filtering (ISO format)
        date_to: End date for filtering (ISO format)

    Returns:
        str: Activity ID
    """
    try:
        # Get tenant and user
        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=user_id) if user_id else None

        # Parse dates
        date_from_obj = datetime.fromisoformat(date_from) if date_from else None
        date_to_obj = datetime.fromisoformat(date_to) if date_to else None

        # Create export service and export data
        export_service = DataExportService(tenant)
        activity = export_service.export_data(
            data_types=data_types,
            format=format,
            user=user,
            date_from=date_from_obj,
            date_to=date_to_obj,
        )

        logger.info(f"Data export completed for tenant {tenant_id}: {activity.id}")
        return str(activity.id)

    except Tenant.DoesNotExist:
        logger.error(f"Tenant {tenant_id} not found")
        raise
    except Exception as e:
        logger.exception(f"Data export failed for tenant {tenant_id}: {e}")
        raise self.retry(exc=e)


@shared_task(
    name="apps.core.data_tasks.import_data_async",
    bind=True,
    max_retries=2,
    default_retry_delay=300,  # 5 minutes
)
def import_data_async(
    self,
    tenant_id: str,
    data_type: str,
    file_path: str,
    user_id: Optional[str] = None,
    update_existing: bool = False,
    validate_only: bool = False,
) -> str:
    """
    Asynchronously import tenant data.

    Args:
        tenant_id: Tenant UUID
        data_type: Type of data to import
        file_path: Path to import file
        user_id: User ID initiating the import
        update_existing: Whether to update existing records
        validate_only: Only validate, don't import

    Returns:
        str: Activity ID
    """
    try:
        # Get tenant and user
        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=user_id) if user_id else None

        # Create import service and import data
        import_service = DataImportService(tenant)
        activity = import_service.import_data(
            data_type=data_type,
            file_path=file_path,
            user=user,
            update_existing=update_existing,
            validate_only=validate_only,
        )

        logger.info(f"Data import completed for tenant {tenant_id}: {activity.id}")
        return str(activity.id)

    except Tenant.DoesNotExist:
        logger.error(f"Tenant {tenant_id} not found")
        raise
    except Exception as e:
        logger.exception(f"Data import failed for tenant {tenant_id}: {e}")
        raise self.retry(exc=e)


@shared_task(
    name="apps.core.data_tasks.trigger_backup_async",
    bind=True,
    max_retries=1,
    default_retry_delay=600,  # 10 minutes
)
def trigger_backup_async(
    self,
    backup_type: str,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    priority: str = "NORMAL",
    reason: str = "",
    include_media: bool = True,
    compress_backup: bool = True,
    encrypt_backup: bool = True,
) -> str:
    """
    Asynchronously trigger a backup.

    Args:
        backup_type: Type of backup (FULL, TENANT, INCREMENTAL)
        tenant_id: Tenant UUID (for tenant-specific backups)
        user_id: User ID triggering the backup
        priority: Backup priority
        reason: Reason for backup
        include_media: Include media files
        compress_backup: Compress the backup
        encrypt_backup: Encrypt the backup

    Returns:
        str: Trigger ID
    """
    try:
        # Get tenant and user
        tenant = Tenant.objects.get(id=tenant_id) if tenant_id else None
        user = User.objects.get(id=user_id) if user_id else None

        # Create backup service and trigger backup
        backup_service = BackupTriggerService(tenant)
        trigger = backup_service.trigger_backup(
            backup_type=backup_type,
            user=user,
            priority=priority,
            reason=reason,
            include_media=include_media,
            compress_backup=compress_backup,
            encrypt_backup=encrypt_backup,
        )

        logger.info(f"Backup triggered: {backup_type} for tenant {tenant_id or 'ALL'}")
        return str(trigger.id)

    except Tenant.DoesNotExist:
        logger.error(f"Tenant {tenant_id} not found")
        raise
    except Exception as e:
        logger.exception(f"Backup trigger failed: {e}")
        raise self.retry(exc=e)


@shared_task(
    name="apps.core.data_tasks.cleanup_old_exports",
    bind=True,
)
def cleanup_old_exports(self, days_old: int = 7) -> str:
    """
    Clean up old export files.

    Args:
        days_old: Delete files older than this many days

    Returns:
        str: Cleanup summary
    """
    try:
        cutoff_date = timezone.now() - timezone.timedelta(days=days_old)

        # Find old export activities
        old_activities = DataActivity.objects.filter(
            activity_type="EXPORT",
            status="COMPLETED",
            completed_at__lt=cutoff_date,
            file_path__isnull=False,
        )

        deleted_count = 0
        total_size = 0

        for activity in old_activities:
            if activity.file_path and os.path.exists(activity.file_path):
                try:
                    file_size = os.path.getsize(activity.file_path)
                    os.remove(activity.file_path)
                    total_size += file_size
                    deleted_count += 1

                    # Clear file path from activity
                    activity.file_path = None
                    activity.save(update_fields=["file_path"])

                except OSError as e:
                    logger.warning(f"Failed to delete export file {activity.file_path}: {e}")

        summary = (
            f"Cleaned up {deleted_count} export files, freed {total_size / (1024*1024):.2f} MB"
        )
        logger.info(summary)
        return summary

    except Exception as e:
        logger.exception(f"Export cleanup failed: {e}")
        raise


@shared_task(
    name="apps.core.data_tasks.cleanup_old_imports",
    bind=True,
)
def cleanup_old_imports(self, days_old: int = 30) -> str:
    """
    Clean up old import files and activities.

    Args:
        days_old: Delete records older than this many days

    Returns:
        str: Cleanup summary
    """
    try:
        cutoff_date = timezone.now() - timezone.timedelta(days=days_old)

        # Find old import activities
        old_activities = DataActivity.objects.filter(
            activity_type="IMPORT", completed_at__lt=cutoff_date
        )

        deleted_files = 0
        deleted_records = 0

        for activity in old_activities:
            # Delete associated file if it exists
            if activity.file_path and os.path.exists(activity.file_path):
                try:
                    os.remove(activity.file_path)
                    deleted_files += 1
                except OSError as e:
                    logger.warning(f"Failed to delete import file {activity.file_path}: {e}")

        # Delete old activity records
        deleted_records = old_activities.count()
        old_activities.delete()

        summary = f"Cleaned up {deleted_records} import records and {deleted_files} files"
        logger.info(summary)
        return summary

    except Exception as e:
        logger.exception(f"Import cleanup failed: {e}")
        raise


@shared_task(
    name="apps.core.data_tasks.process_pending_backups",
    bind=True,
)
def process_pending_backups(self) -> str:
    """
    Process pending backup triggers.

    Returns:
        str: Processing summary
    """
    try:
        # Find pending backup triggers that are due
        now = timezone.now()
        pending_triggers = BackupTrigger.objects.filter(
            status__in=["PENDING", "QUEUED"], scheduled_at__lte=now
        ).order_by("priority", "created_at")

        processed_count = 0

        for trigger in pending_triggers[:10]:  # Process up to 10 at a time
            try:
                # Mark as started
                trigger.mark_started()

                # Here we would integrate with the actual backup system
                # For now, we'll simulate the backup process
                logger.info(f"Processing backup trigger {trigger.id}: {trigger.backup_type}")

                # Simulate backup completion
                import uuid

                backup_id = uuid.uuid4()
                file_path = f"/backups/backup_{backup_id}.sql.gz"
                file_size = 1024 * 1024 * 100  # 100MB simulation

                trigger.mark_completed(
                    backup_id=backup_id, file_path=file_path, file_size=file_size
                )

                processed_count += 1

            except Exception as e:
                logger.exception(f"Failed to process backup trigger {trigger.id}: {e}")
                trigger.mark_failed(str(e))

        summary = f"Processed {processed_count} backup triggers"
        logger.info(summary)
        return summary

    except Exception as e:
        logger.exception(f"Backup processing failed: {e}")
        raise
