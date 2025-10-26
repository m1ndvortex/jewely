"""
Service layer for backup operations.

This module provides high-level functions for:
- Triggering manual backups
- Scheduling backups
- Restoring backups
- Managing backup lifecycle
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import models

from apps.core.models import Tenant

from .models import Backup, BackupRestoreLog
from .tasks import (
    execute_disaster_recovery_runbook,
    perform_configuration_backup,
    perform_restore_operation,
    perform_tenant_backup,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class BackupService:
    """Service for managing backup operations."""

    @staticmethod
    def trigger_manual_backup(  # noqa: C901
        backup_scope: str,
        tenants: Optional[List[Tenant]] = None,
        execution_timing: str = "immediate",
        scheduled_time: Optional[datetime] = None,
        include_configuration: bool = False,
        notes: str = "",
        user: Optional[User] = None,
    ) -> dict:
        """
        Trigger a manual backup with flexible options.

        Args:
            backup_scope: Scope of backup ("all", "specific", "multiple")
            tenants: List of tenants to backup (for specific/multiple scope)
            execution_timing: When to execute ("immediate" or "scheduled")
            scheduled_time: Scheduled execution time (for scheduled timing)
            include_configuration: Whether to include configuration files
            notes: Optional notes about the backup
            user: User who triggered the backup

        Returns:
            Dictionary with backup job information
        """
        logger.info(
            f"Manual backup triggered by {user.username if user else 'system'}: "
            f"scope={backup_scope}, timing={execution_timing}"
        )

        results = {
            "success": True,
            "backup_jobs": [],
            "scheduled_jobs": [],
            "errors": [],
        }

        # Determine which tenants to backup
        if backup_scope == "all":
            target_tenants = list(Tenant.objects.filter(status=Tenant.ACTIVE))
            logger.info(f"Backing up all {len(target_tenants)} active tenants")
        elif backup_scope in ["specific", "multiple"]:
            target_tenants = list(tenants) if tenants else []
            logger.info(f"Backing up {len(target_tenants)} selected tenants")
        else:
            results["success"] = False
            results["errors"].append(f"Invalid backup scope: {backup_scope}")
            return results

        # Execute or schedule backups
        if execution_timing == "immediate":
            # Execute immediately
            for tenant in target_tenants:
                try:
                    # Trigger tenant backup task
                    task = perform_tenant_backup.delay(
                        tenant_id=str(tenant.id),
                        notes=notes,
                        created_by_id=user.id if user else None,
                    )

                    results["backup_jobs"].append(
                        {
                            "tenant_id": str(tenant.id),
                            "tenant_name": tenant.company_name,
                            "task_id": task.id,
                            "status": "queued",
                        }
                    )

                    logger.info(f"Queued backup for tenant {tenant.company_name} (task: {task.id})")

                except Exception as e:
                    logger.error(f"Failed to queue backup for tenant {tenant.company_name}: {e}")
                    results["errors"].append(
                        {
                            "tenant_id": str(tenant.id),
                            "tenant_name": tenant.company_name,
                            "error": str(e),
                        }
                    )

            # Include configuration backup if requested
            if include_configuration:
                try:
                    task = perform_configuration_backup.delay(
                        notes=notes,
                        created_by_id=user.id if user else None,
                    )

                    results["backup_jobs"].append(
                        {
                            "backup_type": "configuration",
                            "task_id": task.id,
                            "status": "queued",
                        }
                    )

                    logger.info(f"Queued configuration backup (task: {task.id})")

                except Exception as e:
                    logger.error(f"Failed to queue configuration backup: {e}")
                    results["errors"].append(
                        {
                            "backup_type": "configuration",
                            "error": str(e),
                        }
                    )

        elif execution_timing == "scheduled":
            # Schedule for later execution
            if not scheduled_time:
                results["success"] = False
                results["errors"].append("Scheduled time is required for scheduled execution")
                return results

            for tenant in target_tenants:
                try:
                    # Schedule tenant backup task
                    task = perform_tenant_backup.apply_async(
                        kwargs={
                            "tenant_id": str(tenant.id),
                            "notes": notes,
                            "created_by_id": user.id if user else None,
                        },
                        eta=scheduled_time,
                    )

                    results["scheduled_jobs"].append(
                        {
                            "tenant_id": str(tenant.id),
                            "tenant_name": tenant.company_name,
                            "task_id": task.id,
                            "scheduled_time": scheduled_time.isoformat(),
                            "status": "scheduled",
                        }
                    )

                    logger.info(
                        f"Scheduled backup for tenant {tenant.company_name} at {scheduled_time} (task: {task.id})"
                    )

                except Exception as e:
                    logger.error(f"Failed to schedule backup for tenant {tenant.company_name}: {e}")
                    results["errors"].append(
                        {
                            "tenant_id": str(tenant.id),
                            "tenant_name": tenant.company_name,
                            "error": str(e),
                        }
                    )

            # Include configuration backup if requested
            if include_configuration:
                try:
                    task = perform_configuration_backup.apply_async(
                        kwargs={
                            "notes": notes,
                            "created_by_id": user.id if user else None,
                        },
                        eta=scheduled_time,
                    )

                    results["scheduled_jobs"].append(
                        {
                            "backup_type": "configuration",
                            "task_id": task.id,
                            "scheduled_time": scheduled_time.isoformat(),
                            "status": "scheduled",
                        }
                    )

                    logger.info(
                        f"Scheduled configuration backup at {scheduled_time} (task: {task.id})"
                    )

                except Exception as e:
                    logger.error(f"Failed to schedule configuration backup: {e}")
                    results["errors"].append(
                        {
                            "backup_type": "configuration",
                            "error": str(e),
                        }
                    )

        else:
            results["success"] = False
            results["errors"].append(f"Invalid execution timing: {execution_timing}")

        # Set success to False if there were any errors
        if results["errors"]:
            results["success"] = False

        return results

    @staticmethod
    def trigger_restore(
        backup_id: UUID,
        restore_mode: str,
        selective_restore: bool = False,
        tenant_ids: Optional[List[str]] = None,
        target_timestamp: Optional[datetime] = None,
        reason: str = "",
        user: Optional[User] = None,
    ) -> dict:
        """
        Trigger a restore operation with flexible options.

        Args:
            backup_id: ID of the backup to restore
            restore_mode: Restore mode (FULL, MERGE, PITR)
            selective_restore: Whether to restore only specific tenants
            tenant_ids: List of tenant IDs to restore (for selective restore)
            target_timestamp: Target timestamp for PITR
            reason: Reason for the restore operation
            user: User who triggered the restore

        Returns:
            Dictionary with restore job information
        """
        logger.info(
            f"Restore triggered by {user.username if user else 'system'}: "
            f"backup={backup_id}, mode={restore_mode}"
        )

        try:
            # Get the backup
            backup = Backup.objects.get(id=backup_id)

            # Validate backup status
            if not backup.is_completed():
                return {
                    "success": False,
                    "error": f"Backup is not completed (status: {backup.status})",
                }

            # Create restore log entry
            restore_log = BackupRestoreLog.objects.create(
                backup=backup,
                initiated_by=user,
                tenant_ids=tenant_ids if selective_restore else None,
                restore_mode=restore_mode,
                target_timestamp=target_timestamp,
                reason=reason,
                status=BackupRestoreLog.IN_PROGRESS,
            )

            # Trigger restore task
            task = perform_restore_operation.delay(
                restore_log_id=str(restore_log.id),
            )

            logger.info(f"Queued restore operation (task: {task.id}, log: {restore_log.id})")

            return {
                "success": True,
                "restore_log_id": str(restore_log.id),
                "task_id": task.id,
                "status": "queued",
            }

        except Backup.DoesNotExist:
            logger.error(f"Backup not found: {backup_id}")
            return {
                "success": False,
                "error": f"Backup not found: {backup_id}",
            }

        except Exception as e:
            logger.error(f"Failed to trigger restore: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    @staticmethod
    def execute_disaster_recovery(
        backup_id: Optional[UUID] = None,
        reason: str = "Disaster recovery initiated",
        user: Optional[User] = None,
    ) -> dict:
        """
        Execute automated disaster recovery runbook.

        This triggers the complete DR procedure with 1-hour RTO:
        1. Download latest backup from R2 (with B2 failover)
        2. Decrypt and decompress
        3. Restore database with 4 parallel jobs
        4. Restart application pods
        5. Verify health checks
        6. Reroute traffic
        7. Log all DR events

        Args:
            backup_id: Optional specific backup ID to restore (defaults to latest)
            reason: Reason for disaster recovery
            user: User who initiated DR (None for automated)

        Returns:
            Dictionary with DR job information
        """
        logger.info(
            f"Disaster recovery initiated by {user.username if user else 'system'}: "
            f"backup={backup_id}, reason={reason}"
        )

        try:
            # Trigger DR runbook task
            task = execute_disaster_recovery_runbook.delay(
                backup_id=str(backup_id) if backup_id else None,
                reason=reason,
            )

            logger.info(f"Queued disaster recovery runbook (task: {task.id})")

            return {
                "success": True,
                "task_id": task.id,
                "status": "queued",
                "message": "Disaster recovery runbook initiated",
            }

        except Exception as e:
            logger.error(f"Failed to initiate disaster recovery: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    @staticmethod
    def get_backup_statistics() -> dict:
        """
        Get backup system statistics.

        Returns:
            Dictionary with backup statistics
        """
        total_backups = Backup.objects.count()
        completed_backups = Backup.objects.filter(
            status__in=[Backup.COMPLETED, Backup.VERIFIED]
        ).count()
        failed_backups = Backup.objects.filter(status=Backup.FAILED).count()
        in_progress_backups = Backup.objects.filter(status=Backup.IN_PROGRESS).count()

        # Calculate total storage used
        total_storage_bytes = (
            Backup.objects.filter(status__in=[Backup.COMPLETED, Backup.VERIFIED]).aggregate(
                total=models.Sum("size_bytes")
            )["total"]
            or 0
        )

        # Get latest backup
        latest_backup = Backup.objects.filter(
            status__in=[Backup.COMPLETED, Backup.VERIFIED]
        ).first()

        # Get backup counts by type
        backup_counts_by_type = {}
        for backup_type, _ in Backup.BACKUP_TYPE_CHOICES:
            count = Backup.objects.filter(backup_type=backup_type).count()
            backup_counts_by_type[backup_type] = count

        return {
            "total_backups": total_backups,
            "completed_backups": completed_backups,
            "failed_backups": failed_backups,
            "in_progress_backups": in_progress_backups,
            "total_storage_bytes": total_storage_bytes,
            "total_storage_gb": round(total_storage_bytes / (1024**3), 2),
            "latest_backup": (
                {
                    "id": str(latest_backup.id) if latest_backup else None,
                    "type": latest_backup.backup_type if latest_backup else None,
                    "created_at": latest_backup.created_at.isoformat() if latest_backup else None,
                }
                if latest_backup
                else None
            ),
            "backup_counts_by_type": backup_counts_by_type,
        }
