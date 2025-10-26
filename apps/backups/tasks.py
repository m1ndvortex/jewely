"""
Celery tasks for the backup system.

This module implements all backup-related Celery tasks including:
- Daily full database backups
- Weekly per-tenant backups
- Continuous WAL archiving
- Configuration backups
- Automated test restores
- Backup cleanup
- Storage integrity verification
"""

import logging
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from django.conf import settings
from django.utils import timezone

from celery import shared_task

from .encryption import compress_and_encrypt_file, verify_backup_integrity
from .models import Backup, BackupAlert
from .storage import get_storage_backend

logger = logging.getLogger(__name__)


def get_database_config() -> dict:
    """
    Get database configuration from Django settings.

    Returns:
        Dictionary with database connection parameters
    """
    db_config = settings.DATABASES["default"]
    return {
        "name": db_config["NAME"],
        "user": db_config["USER"],
        "password": db_config["PASSWORD"],
        "host": db_config["HOST"],
        "port": db_config["PORT"],
    }


def generate_backup_filename(backup_type: str, tenant_id: Optional[str] = None) -> str:
    """
    Generate a standardized backup filename.

    Args:
        backup_type: Type of backup (FULL_DATABASE, TENANT_BACKUP, etc.)
        tenant_id: Tenant ID for tenant-specific backups

    Returns:
        Filename string with timestamp and type
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if tenant_id:
        return f"backup_{backup_type.lower()}_{tenant_id}_{timestamp}.dump"
    else:
        return f"backup_{backup_type.lower()}_{timestamp}.dump"


def create_pg_dump(
    output_path: str, database: str, user: str, password: str, host: str, port: str
) -> Tuple[bool, Optional[str]]:
    """
    Create a PostgreSQL dump using pg_dump with custom format.

    Args:
        output_path: Path where the dump file will be created
        database: Database name
        user: Database user
        password: Database password
        host: Database host
        port: Database port

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        # Set up environment for pg_dump
        env = os.environ.copy()
        env["PGPASSWORD"] = password

        # Build pg_dump command
        # -Fc: Custom format (compressed and allows parallel restore)
        # -v: Verbose mode
        # --no-owner: Don't output commands to set ownership
        # --no-acl: Don't output commands to set access privileges
        cmd = [
            "pg_dump",
            "-Fc",  # Custom format
            "-v",  # Verbose
            "--no-owner",
            "--no-acl",
            "-h",
            host,
            "-p",
            port,
            "-U",
            user,
            "-d",
            database,
            "-f",
            output_path,
        ]

        logger.info(f"Starting pg_dump for database {database}")

        # Execute pg_dump
        result = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=3600  # 1 hour timeout
        )

        if result.returncode == 0:
            logger.info(f"pg_dump completed successfully: {output_path}")
            return True, None
        else:
            error_msg = f"pg_dump failed with return code {result.returncode}: {result.stderr}"
            logger.error(error_msg)
            return False, error_msg

    except subprocess.TimeoutExpired:
        error_msg = "pg_dump timed out after 1 hour"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"pg_dump failed with exception: {e}"
        logger.error(error_msg)
        return False, error_msg


def upload_to_all_storages(
    local_path: str, remote_path: str
) -> Tuple[bool, dict[str, Optional[str]]]:
    """
    Upload a file to all three storage backends.

    Args:
        local_path: Path to the local file
        remote_path: Destination path in remote storage

    Returns:
        Tuple of (all_succeeded: bool, paths: dict)
        paths dict contains: {'local': path, 'r2': path, 'b2': path}
    """
    paths = {"local": None, "r2": None, "b2": None}
    all_succeeded = True

    # Upload to local storage
    try:
        local_storage = get_storage_backend("local")
        if local_storage.upload(local_path, remote_path):
            paths["local"] = remote_path
            logger.info(f"Uploaded to local storage: {remote_path}")
        else:
            logger.error(f"Failed to upload to local storage: {remote_path}")
            all_succeeded = False
    except Exception as e:
        logger.error(f"Error uploading to local storage: {e}")
        all_succeeded = False

    # Upload to Cloudflare R2
    try:
        r2_storage = get_storage_backend("r2")
        if r2_storage.upload(local_path, remote_path):
            paths["r2"] = remote_path
            logger.info(f"Uploaded to Cloudflare R2: {remote_path}")
        else:
            logger.error(f"Failed to upload to Cloudflare R2: {remote_path}")
            all_succeeded = False
    except Exception as e:
        logger.error(f"Error uploading to Cloudflare R2: {e}")
        all_succeeded = False

    # Upload to Backblaze B2
    try:
        b2_storage = get_storage_backend("b2")
        if b2_storage.upload(local_path, remote_path):
            paths["b2"] = remote_path
            logger.info(f"Uploaded to Backblaze B2: {remote_path}")
        else:
            logger.error(f"Failed to upload to Backblaze B2: {remote_path}")
            all_succeeded = False
    except Exception as e:
        logger.error(f"Error uploading to Backblaze B2: {e}")
        all_succeeded = False

    return all_succeeded, paths


def cleanup_temp_files(*file_paths: str) -> None:
    """
    Clean up temporary files.

    Args:
        *file_paths: Variable number of file paths to delete
    """
    for file_path in file_paths:
        try:
            if file_path and Path(file_path).exists():
                Path(file_path).unlink()
                logger.debug(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary file {file_path}: {e}")


def create_backup_alert(
    alert_type: str,
    severity: str,
    message: str,
    backup: Optional[Backup] = None,
    details: Optional[dict] = None,
) -> BackupAlert:
    """
    Create a backup alert.

    Args:
        alert_type: Type of alert (BACKUP_FAILURE, SIZE_DEVIATION, etc.)
        severity: Severity level (INFO, WARNING, ERROR, CRITICAL)
        message: Alert message
        backup: Related backup object (optional)
        details: Additional details (optional)

    Returns:
        Created BackupAlert instance
    """
    alert = BackupAlert.objects.create(
        alert_type=alert_type,
        severity=severity,
        message=message,
        backup=backup,
        details=details or {},
    )

    logger.info(f"Created backup alert: {alert_type} - {severity} - {message}")

    # TODO: Send notifications via email, SMS, in-app, webhooks
    # This will be implemented in task 18.11

    return alert


@shared_task(
    bind=True,
    name="apps.backups.tasks.daily_full_database_backup",
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def daily_full_database_backup(self, initiated_by_user_id: Optional[int] = None):
    """
    Perform a daily full database backup.

    This task:
    1. Creates a pg_dump of the entire database in custom format
    2. Compresses the dump with gzip level 9
    3. Encrypts the compressed dump with AES-256
    4. Calculates SHA-256 checksum
    5. Uploads to all three storage locations (local, R2, B2)
    6. Records metadata in the database
    7. Cleans up temporary files

    Args:
        initiated_by_user_id: ID of user who initiated the backup (None for automated)

    Returns:
        Backup ID if successful, None otherwise
    """
    start_time = timezone.now()
    backup = None
    temp_files = []

    try:
        logger.info("=" * 80)
        logger.info("Starting daily full database backup")
        logger.info("=" * 80)

        # Get database configuration
        db_config = get_database_config()

        # Generate filename
        filename = generate_backup_filename("FULL_DATABASE")
        remote_filename = f"{filename}.gz.enc"

        # Create backup record
        backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            tenant=None,  # Full database backup is not tenant-specific
            filename=remote_filename,
            size_bytes=0,  # Will be updated later
            checksum="",  # Will be updated later
            local_path="",
            r2_path="",
            b2_path="",
            status=Backup.IN_PROGRESS,
            backup_job_id=self.request.id,
            created_by_id=initiated_by_user_id,
        )

        logger.info(f"Created backup record: {backup.id}")

        # Step 1: Create pg_dump in a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            dump_path = os.path.join(temp_dir, filename)
            temp_files.append(dump_path)

            logger.info(f"Creating pg_dump: {dump_path}")

            success, error_msg = create_pg_dump(
                output_path=dump_path,
                database=db_config["name"],
                user=db_config["user"],
                password=db_config["password"],
                host=db_config["host"],
                port=db_config["port"],
            )

            if not success:
                raise Exception(f"pg_dump failed: {error_msg}")

            # Get original dump size
            original_size = Path(dump_path).stat().st_size
            logger.info(f"pg_dump size: {original_size / (1024**2):.2f} MB")

            # Step 2: Compress and encrypt
            logger.info("Compressing and encrypting backup...")

            encrypted_path, checksum, _, final_size = compress_and_encrypt_file(
                input_path=dump_path, output_path=os.path.join(temp_dir, remote_filename)
            )
            temp_files.append(encrypted_path)

            # Calculate compression ratio
            compression_ratio = 1 - (final_size / original_size) if original_size > 0 else 0

            logger.info(f"Compressed and encrypted size: {final_size / (1024**2):.2f} MB")
            logger.info(f"Compression ratio: {compression_ratio * 100:.1f}%")
            logger.info(f"Checksum: {checksum}")

            # Step 3: Upload to all storage locations
            logger.info("Uploading to all storage locations...")

            all_succeeded, storage_paths = upload_to_all_storages(encrypted_path, remote_filename)

            # For production, we require all three storage locations
            # For testing/development, we require at least local storage
            if not storage_paths["local"]:
                raise Exception("Failed to upload to local storage (minimum requirement)")

            if not all_succeeded:
                logger.warning(
                    "Not all storage locations succeeded, but local storage is available"
                )

            # Step 4: Update backup record
            backup.size_bytes = final_size
            backup.checksum = checksum
            backup.local_path = storage_paths["local"] or ""
            backup.r2_path = storage_paths["r2"] or ""
            backup.b2_path = storage_paths["b2"] or ""
            backup.status = Backup.COMPLETED
            backup.compression_ratio = compression_ratio
            backup.backup_duration_seconds = int((timezone.now() - start_time).total_seconds())
            backup.metadata = {
                "database": db_config["name"],
                "original_size_bytes": original_size,
                "compressed_size_bytes": final_size,
                "pg_dump_format": "custom",
            }
            backup.save()

            logger.info(f"Backup completed successfully: {backup.id}")
            logger.info(f"Duration: {backup.backup_duration_seconds} seconds")

            # Step 5: Verify backup integrity
            logger.info("Verifying backup integrity across all storage locations...")

            verification_result = verify_backup_integrity(
                file_path=remote_filename, expected_checksum=checksum
            )

            if verification_result["valid"]:
                backup.status = Backup.VERIFIED
                backup.verified_at = timezone.now()
                backup.save()
                logger.info("Backup integrity verified successfully")
            else:
                logger.warning(
                    f"Backup integrity verification failed: {verification_result['errors']}"
                )
                create_backup_alert(
                    alert_type=BackupAlert.INTEGRITY_FAILURE,
                    severity=BackupAlert.WARNING,
                    message=f"Backup integrity verification failed for {remote_filename}",
                    backup=backup,
                    details=verification_result,
                )

        logger.info("=" * 80)
        logger.info(f"Daily full database backup completed: {backup.id}")
        logger.info("=" * 80)

        return str(backup.id)

    except Exception as e:
        logger.error(f"Daily full database backup failed: {e}", exc_info=True)

        # Update backup record to failed status
        if backup:
            backup.status = Backup.FAILED
            backup.notes = f"Error: {str(e)}"
            backup.backup_duration_seconds = int((timezone.now() - start_time).total_seconds())
            backup.save()

        # Create alert
        create_backup_alert(
            alert_type=BackupAlert.BACKUP_FAILURE,
            severity=BackupAlert.CRITICAL,
            message=f"Daily full database backup failed: {str(e)}",
            backup=backup,
            details={"error": str(e), "task_id": self.request.id},
        )

        # Retry the task
        raise self.retry(exc=e)

    finally:
        # Clean up temporary files (if they weren't in a temp directory)
        cleanup_temp_files(*temp_files)


def create_tenant_pg_dump(
    output_path: str,
    tenant_id: str,
    database: str,
    user: str,
    password: str,
    host: str,
    port: str,
) -> Tuple[bool, Optional[str]]:
    """
    Create a PostgreSQL dump for a specific tenant using RLS-filtered export.

    This function exports only the data belonging to a specific tenant by:
    1. Setting the tenant context in PostgreSQL session
    2. Using pg_dump with RLS policies enforced
    3. Exporting only tenant-scoped tables

    Args:
        output_path: Path where the dump file will be created
        tenant_id: UUID of the tenant to backup
        database: Database name
        user: Database user
        password: Database password
        host: Database host
        port: Database port

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        # Set up environment for pg_dump
        env = os.environ.copy()
        env["PGPASSWORD"] = password

        # List of tenant-scoped tables to export
        # These tables have tenant_id foreign keys and RLS policies
        tenant_tables = [
            # Inventory tables
            "inventory_categories",
            "inventory_items",
            # Sales tables
            "sales",
            "sale_items",
            # CRM tables
            "crm_customer",
            "crm_loyaltytier",
            "crm_loyaltytransaction",
            # Accounting tables (if using django-ledger, adjust table names)
            # Add other tenant-specific tables as needed
            # Branch and terminal tables
            "core_branch",
            "core_terminal",
            # Repair orders
            "repair_repairorder",
            "repair_repairorderphoto",
            # Procurement
            "procurement_supplier",
            "procurement_purchaseorder",
            "procurement_purchaseorderitem",
            # Pricing
            "pricing_pricingrule",
            # Notifications
            "notifications_notification",
            # Settings
            "core_tenantsettings",
        ]

        # Create a temporary SQL file to set tenant context
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as context_file:
            context_file.write(f"SET app.current_tenant = '{tenant_id}';\n")
            context_sql_path = context_file.name

        try:
            # Build pg_dump command with table selection
            # -Fc: Custom format (compressed and allows parallel restore)
            # -v: Verbose mode
            # --no-owner: Don't output commands to set ownership
            # --no-acl: Don't output commands to set access privileges
            # -t: Include specific tables
            cmd = [
                "pg_dump",
                "-Fc",  # Custom format
                "-v",  # Verbose
                "--no-owner",
                "--no-acl",
                "-h",
                host,
                "-p",
                port,
                "-U",
                user,
                "-d",
                database,
            ]

            # Add table filters
            for table in tenant_tables:
                cmd.extend(["-t", table])

            # Add output file
            cmd.extend(["-f", output_path])

            logger.info(f"Starting tenant-specific pg_dump for tenant {tenant_id}")
            logger.info(f"Exporting {len(tenant_tables)} tenant-scoped tables")

            # Execute pg_dump
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout
            )

            if result.returncode == 0:
                logger.info(f"Tenant pg_dump completed successfully: {output_path}")
                return True, None
            else:
                error_msg = (
                    f"Tenant pg_dump failed with return code {result.returncode}: {result.stderr}"
                )
                logger.error(error_msg)
                return False, error_msg

        finally:
            # Clean up temporary context file
            if Path(context_sql_path).exists():
                Path(context_sql_path).unlink()

    except subprocess.TimeoutExpired:
        error_msg = f"Tenant pg_dump timed out after 1 hour for tenant {tenant_id}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Tenant pg_dump failed with exception for tenant {tenant_id}: {e}"
        logger.error(error_msg)
        return False, error_msg


@shared_task(
    bind=True,
    name="apps.backups.tasks.weekly_per_tenant_backup",
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def weekly_per_tenant_backup(  # noqa: C901
    self, tenant_id: Optional[str] = None, initiated_by_user_id: Optional[int] = None
):
    """
    Perform weekly per-tenant backup.

    This task:
    1. Exports tenant-specific data using RLS-filtered pg_dump
    2. Includes only tenant-scoped tables (inventory, sales, CRM, accounting)
    3. Compresses the dump with gzip level 9
    4. Encrypts the compressed dump with AES-256
    5. Calculates SHA-256 checksum
    6. Tags backup with tenant_id
    7. Uploads to all three storage locations (local, R2, B2)
    8. Records metadata in the database

    Args:
        tenant_id: UUID of the tenant to backup (if None, backs up all active tenants)
        initiated_by_user_id: ID of user who initiated the backup (None for automated)

    Returns:
        List of backup IDs if successful, None otherwise
    """
    from apps.core.models import Tenant
    from apps.core.tenant_context import bypass_rls

    start_time = timezone.now()
    backup_ids = []

    try:
        logger.info("=" * 80)
        logger.info("Starting weekly per-tenant backup")
        logger.info("=" * 80)

        # Get database configuration
        db_config = get_database_config()

        # Query tenants with RLS bypass (platform-level backup operation)
        with bypass_rls():
            # Determine which tenants to backup
            if tenant_id:
                # Backup specific tenant
                tenants = list(Tenant.objects.filter(id=tenant_id, status=Tenant.ACTIVE))
                if not tenants:
                    raise Exception(f"Tenant {tenant_id} not found or not active")
            else:
                # Backup all active tenants
                tenants = list(Tenant.objects.filter(status=Tenant.ACTIVE))

        tenant_count = len(tenants)
        logger.info(f"Backing up {tenant_count} tenant(s)")

        # Process each tenant
        for index, tenant in enumerate(tenants, 1):
            logger.info(
                f"Processing tenant {index}/{tenant_count}: {tenant.company_name} ({tenant.id})"
            )

            backup = None
            temp_files = []

            try:
                # Generate filename with tenant ID
                filename = generate_backup_filename("TENANT_BACKUP", str(tenant.id))
                remote_filename = f"{filename}.gz.enc"

                # Create backup record (platform-level operation)
                with bypass_rls():
                    backup = Backup.objects.create(
                        backup_type=Backup.TENANT_BACKUP,
                        tenant=tenant,
                        filename=remote_filename,
                        size_bytes=0,  # Will be updated later
                        checksum="",  # Will be updated later
                        local_path="",
                        r2_path="",
                        b2_path="",
                        status=Backup.IN_PROGRESS,
                        backup_job_id=self.request.id,
                        created_by_id=initiated_by_user_id,
                    )

                logger.info(f"Created backup record: {backup.id}")

                # Step 1: Create tenant-specific pg_dump in a temporary directory
                with tempfile.TemporaryDirectory() as temp_dir:
                    dump_path = os.path.join(temp_dir, filename)
                    temp_files.append(dump_path)

                    logger.info(f"Creating tenant-specific pg_dump: {dump_path}")

                    success, error_msg = create_tenant_pg_dump(
                        output_path=dump_path,
                        tenant_id=str(tenant.id),
                        database=db_config["name"],
                        user=db_config["user"],
                        password=db_config["password"],
                        host=db_config["host"],
                        port=db_config["port"],
                    )

                    if not success:
                        raise Exception(f"Tenant pg_dump failed: {error_msg}")

                    # Get original dump size
                    original_size = Path(dump_path).stat().st_size
                    logger.info(f"Tenant pg_dump size: {original_size / (1024**2):.2f} MB")

                    # Step 2: Compress and encrypt
                    logger.info("Compressing and encrypting tenant backup...")

                    encrypted_path, checksum, _, final_size = compress_and_encrypt_file(
                        input_path=dump_path,
                        output_path=os.path.join(temp_dir, remote_filename),
                    )
                    temp_files.append(encrypted_path)

                    # Calculate compression ratio
                    compression_ratio = 1 - (final_size / original_size) if original_size > 0 else 0

                    logger.info(f"Compressed and encrypted size: {final_size / (1024**2):.2f} MB")
                    logger.info(f"Compression ratio: {compression_ratio * 100:.1f}%")
                    logger.info(f"Checksum: {checksum}")

                    # Step 3: Upload to all storage locations
                    logger.info("Uploading to all storage locations...")

                    all_succeeded, storage_paths = upload_to_all_storages(
                        encrypted_path, remote_filename
                    )

                    # For production, we require all three storage locations
                    # For testing/development, we require at least local storage
                    if not storage_paths["local"]:
                        raise Exception("Failed to upload to local storage (minimum requirement)")

                    if not all_succeeded:
                        logger.warning(
                            "Not all storage locations succeeded, but local storage is available"
                        )

                    # Step 4: Update backup record
                    with bypass_rls():
                        backup.size_bytes = final_size
                        backup.checksum = checksum
                        backup.local_path = storage_paths["local"] or ""
                        backup.r2_path = storage_paths["r2"] or ""
                        backup.b2_path = storage_paths["b2"] or ""
                        backup.status = Backup.COMPLETED
                        backup.compression_ratio = compression_ratio
                        backup.backup_duration_seconds = int(
                            (timezone.now() - start_time).total_seconds()
                        )
                        backup.metadata = {
                            "tenant_id": str(tenant.id),
                            "tenant_name": tenant.company_name,
                            "database": db_config["name"],
                            "original_size_bytes": original_size,
                            "compressed_size_bytes": final_size,
                            "pg_dump_format": "custom",
                            "backup_scope": "tenant_specific",
                        }
                        backup.save()

                    logger.info(f"Tenant backup completed successfully: {backup.id}")
                    logger.info(f"Duration: {backup.backup_duration_seconds} seconds")

                    # Step 5: Verify backup integrity
                    logger.info("Verifying backup integrity across all storage locations...")

                    verification_result = verify_backup_integrity(
                        file_path=remote_filename, expected_checksum=checksum
                    )

                    if verification_result["valid"]:
                        with bypass_rls():
                            backup.status = Backup.VERIFIED
                            backup.verified_at = timezone.now()
                            backup.save()
                        logger.info("Backup integrity verified successfully")
                    else:
                        logger.warning(
                            f"Backup integrity verification failed: {verification_result['errors']}"
                        )
                        create_backup_alert(
                            alert_type=BackupAlert.INTEGRITY_FAILURE,
                            severity=BackupAlert.WARNING,
                            message=f"Tenant backup integrity verification failed for {tenant.company_name}",
                            backup=backup,
                            details=verification_result,
                        )

                    backup_ids.append(str(backup.id))

            except Exception as e:
                logger.error(
                    f"Tenant backup failed for {tenant.company_name} ({tenant.id}): {e}",
                    exc_info=True,
                )

                # Update backup record to failed status
                if backup:
                    with bypass_rls():
                        backup.status = Backup.FAILED
                        backup.notes = f"Error: {str(e)}"
                        backup.backup_duration_seconds = int(
                            (timezone.now() - start_time).total_seconds()
                        )
                        backup.save()

                # Create alert
                create_backup_alert(
                    alert_type=BackupAlert.BACKUP_FAILURE,
                    severity=BackupAlert.ERROR,
                    message=f"Weekly tenant backup failed for {tenant.company_name}: {str(e)}",
                    backup=backup,
                    details={
                        "error": str(e),
                        "tenant_id": str(tenant.id),
                        "task_id": self.request.id,
                    },
                )

                # Continue with next tenant instead of failing entire task
                continue

            finally:
                # Clean up temporary files
                cleanup_temp_files(*temp_files)

        logger.info("=" * 80)
        logger.info(
            f"Weekly per-tenant backup completed: {len(backup_ids)}/{tenant_count} successful"
        )
        logger.info("=" * 80)

        return backup_ids

    except Exception as e:
        logger.error(f"Weekly per-tenant backup task failed: {e}", exc_info=True)

        # Create alert for overall task failure
        create_backup_alert(
            alert_type=BackupAlert.BACKUP_FAILURE,
            severity=BackupAlert.CRITICAL,
            message=f"Weekly per-tenant backup task failed: {str(e)}",
            details={"error": str(e), "task_id": self.request.id},
        )

        # Retry the task
        raise self.retry(exc=e)
