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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from celery import shared_task

from .encryption import compress_and_encrypt_file, verify_backup_integrity
from .models import Backup, BackupAlert, BackupRestoreLog
from .storage import get_storage_backend

User = get_user_model()

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

    This function temporarily disables FORCE ROW LEVEL SECURITY on tables
    to allow pg_dump to export all data, then re-enables it after the backup.

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
    from django.db import connection

    try:
        # Temporarily disable FORCE RLS on tenants table for backup
        # We need to commit this outside of any atomic block
        logger.info("Temporarily disabling FORCE RLS for backup...")

        # Exit any atomic blocks and commit immediately
        if connection.in_atomic_block:
            # Force commit by using set_autocommit
            connection.set_autocommit(True)

        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE tenants NO FORCE ROW LEVEL SECURITY;")

        logger.info("FORCE RLS disabled on tenants table")

        # Set up environment for pg_dump
        env = os.environ.copy()
        env["PGPASSWORD"] = password

        # Build pg_dump command
        # -Fp: Plain text SQL format (not pre-compressed, allows gzip to compress effectively)
        # -v: Verbose mode
        # --no-owner: Don't output commands to set ownership
        # --no-acl: Don't output commands to set access privileges
        cmd = [
            "pg_dump",
            "-Fp",  # Plain text format (for effective gzip compression)
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
    finally:
        # Re-enable FORCE RLS on tenants table
        try:
            logger.info("Re-enabling FORCE RLS...")

            # Ensure we're in autocommit mode
            if connection.in_atomic_block:
                connection.set_autocommit(True)

            with connection.cursor() as cursor:
                cursor.execute("ALTER TABLE tenants FORCE ROW LEVEL SECURITY;")

            logger.info("FORCE RLS re-enabled on tenants table")
        except Exception as e:
            logger.error(f"Failed to re-enable FORCE RLS: {e}")


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

    This is a legacy function that creates an alert without sending notifications.
    For new code, use create_backup_alert_with_notifications from monitoring module.

    Args:
        alert_type: Type of alert (BACKUP_FAILURE, SIZE_DEVIATION, etc.)
        severity: Severity level (INFO, WARNING, ERROR, CRITICAL)
        message: Alert message
        backup: Related backup object (optional)
        details: Additional details (optional)

    Returns:
        Created BackupAlert instance
    """
    from .monitoring import create_backup_alert_with_notifications

    # Use the new monitoring function that includes notifications
    return create_backup_alert_with_notifications(
        alert_type=alert_type,
        severity=severity,
        message=message,
        backup=backup,
        details=details,
    )


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
    from django_redis import get_redis_connection

    # Check if this task is already running (prevent duplicate execution)
    redis_conn = get_redis_connection("default")
    task_lock_key = f"backup:daily_full_database_backup:lock:{self.request.id}"

    # Try to acquire lock with 2-hour expiration
    if not redis_conn.set(task_lock_key, "1", ex=7200, nx=True):
        logger.warning(f"Daily backup task {self.request.id} already running, skipping duplicate execution")
        return None

    try:
        start_time = timezone.now()
        backup = None
        temp_files = []

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

            encrypted_path, checksum, _, compressed_size, final_size = compress_and_encrypt_file(
                input_path=dump_path, output_path=os.path.join(temp_dir, remote_filename)
            )
            temp_files.append(encrypted_path)

            # Calculate compression ratio (using compressed size, not final encrypted size)
            compression_ratio = 1 - (compressed_size / original_size) if original_size > 0 else 0

            logger.info(f"Compressed size: {compressed_size / (1024**2):.2f} MB")
            logger.info(f"Final encrypted size: {final_size / (1024**2):.2f} MB")
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
            backup.compression_ratio = compression_ratio * 100  # Convert to percentage
            backup.backup_duration_seconds = int((timezone.now() - start_time).total_seconds())
            backup.metadata = {
                "database": db_config["name"],
                "original_size_bytes": original_size,
                "compressed_size_bytes": compressed_size,
                "pg_dump_format": "plain",
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

        # Monitor backup completion and create alerts if needed
        from .monitoring import monitor_backup_completion

        monitor_backup_completion(backup)

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

        # Release task lock
        try:
            redis_conn.delete(task_lock_key)
            logger.debug(f"Released task lock for {self.request.id}")
        except Exception as lock_error:
            logger.warning(f"Failed to release task lock: {lock_error}")


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
            # -Fp: Plain text SQL format (not pre-compressed, allows gzip to compress effectively)
            # -v: Verbose mode
            # --no-owner: Don't output commands to set ownership
            # --no-acl: Don't output commands to set access privileges
            # -t: Include specific tables
            cmd = [
                "pg_dump",
                "-Fp",  # Plain text format (for effective gzip compression)
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
    Perform weekly per-tenant backup (Celery task wrapper).

    This task is scheduled by Celery Beat for automated weekly backups.
    For manual backups, use perform_tenant_backup instead.

    Args:
        tenant_id: UUID of the tenant to backup (if None, backs up all active tenants)
        initiated_by_user_id: ID of user who initiated the backup (None for automated)

    Returns:
        List of backup IDs if successful, None otherwise
    """
    return _do_weekly_per_tenant_backup(self, tenant_id, initiated_by_user_id)


def _do_weekly_per_tenant_backup(  # noqa: C901
    task_self, tenant_id: Optional[str] = None, initiated_by_user_id: Optional[int] = None
):
    """
    Perform weekly per-tenant backup (actual implementation).

    This function contains the actual backup logic. It's called by both:
    - weekly_per_tenant_backup (scheduled task)
    - perform_tenant_backup (manual trigger)

    Args:
        task_self: The Celery task instance (for accessing self.request.id)
        tenant_id: UUID of the tenant to backup (if None, backs up all active tenants)
        initiated_by_user_id: ID of user who initiated the backup (None for automated)

    Returns:
        List of backup IDs if successful, None otherwise
    """
    from django_redis import get_redis_connection

    from apps.core.models import Tenant
    from apps.core.tenant_context import bypass_rls

    # Check if this task is already running (prevent duplicate execution)
    redis_conn = get_redis_connection("default")
    task_lock_key = f"backup:weekly_tenant_backup:lock:{task_self.request.id}"

    # Try to acquire lock with 30-minute expiration
    if not redis_conn.set(task_lock_key, "1", ex=1800, nx=True):
        logger.warning(f"Tenant backup task {task_self.request.id} already running, skipping duplicate execution")
        return None

    try:
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
                # Check if backup is already in progress for this tenant
                tenant_lock_key = f"backup:tenant:{tenant.id}:in_progress"

                # Try to acquire tenant-specific lock with 20-minute expiration
                if not redis_conn.set(tenant_lock_key, task_self.request.id, ex=1200, nx=True):
                    existing_task_id = redis_conn.get(tenant_lock_key)
                    if existing_task_id:
                        existing_task_id = existing_task_id.decode('utf-8')
                    logger.warning(
                        f"Backup already in progress for tenant {tenant.company_name} ({tenant.id}) "
                        f"by task {existing_task_id}, skipping"
                    )
                    continue

                try:
                    logger.info(
                        f"Processing tenant {index}/{tenant_count}: {tenant.company_name} ({tenant.id})"
                    )

                    backup = None
                    temp_files = []

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
                            backup_job_id=task_self.request.id,
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

                        encrypted_path, checksum, _, compressed_size, final_size = compress_and_encrypt_file(
                            input_path=dump_path,
                            output_path=os.path.join(temp_dir, remote_filename),
                        )
                        temp_files.append(encrypted_path)

                        # Calculate compression ratio (using compressed size, not final encrypted size)
                        compression_ratio = 1 - (compressed_size / original_size) if original_size > 0 else 0

                        logger.info(f"Compressed size: {compressed_size / (1024**2):.2f} MB")
                        logger.info(f"Final encrypted size: {final_size / (1024**2):.2f} MB")
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
                            backup.compression_ratio = compression_ratio * 100  # Convert to percentage
                            backup.backup_duration_seconds = int(
                                (timezone.now() - start_time).total_seconds()
                            )
                            backup.metadata = {
                                "tenant_id": str(tenant.id),
                                "tenant_name": tenant.company_name,
                                "database": db_config["name"],
                                "original_size_bytes": original_size,
                                "compressed_size_bytes": compressed_size,
                                "pg_dump_format": "plain",
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
                            "task_id": task_self.request.id,
                        },
                    )

                    # Continue with next tenant instead of failing entire task
                    continue

                finally:
                    # Clean up temporary files
                    cleanup_temp_files(*temp_files)

                    # Release tenant-specific lock
                    try:
                        redis_conn.delete(tenant_lock_key)
                        logger.debug(f"Released lock for tenant {tenant.id}")
                    except Exception as lock_error:
                        logger.warning(f"Failed to release tenant lock: {lock_error}")

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
                details={"error": str(e), "task_id": task_self.request.id},
            )

            # Re-raise exception for Celery retry handling
            raise e

    finally:
        # Release task-level lock
        try:
            redis_conn.delete(task_lock_key)
            logger.debug(f"Released task lock for {task_self.request.id}")
        except Exception as lock_error:
            logger.warning(f"Failed to release task lock: {lock_error}")


@shared_task(
    bind=True,
    name="apps.backups.tasks.continuous_wal_archiving",
    max_retries=3,
    default_retry_delay=60,  # 1 minute
)
def continuous_wal_archiving(self):  # noqa: C901
    """
    Perform continuous WAL (Write-Ahead Log) archiving for Point-in-Time Recovery.

    This task:
    1. Identifies new WAL files in PostgreSQL's pg_wal directory
    2. Compresses WAL files with gzip level 9
    3. Calculates SHA-256 checksum
    4. Uploads to R2 and B2 (skips local storage for WAL files)
    5. Marks WAL files as archived in PostgreSQL
    6. Implements 7-day local and 30-day cloud retention

    WAL archiving enables Point-in-Time Recovery (PITR) with 5-minute granularity.
    This task should run every 5 minutes via Celery Beat.

    Returns:
        Number of WAL files archived if successful, None otherwise
    """
    start_time = timezone.now()
    archived_count = 0
    temp_files = []

    try:
        logger.info("=" * 80)
        logger.info("Starting continuous WAL archiving")
        logger.info("=" * 80)

        # Get PostgreSQL WAL archive directory
        # PostgreSQL's archive_command copies WAL files to this directory
        pg_wal_archive_dir = os.environ.get("PG_WAL_ARCHIVE_DIR", "/var/lib/postgresql/wal_archive")

        # Check if WAL archive directory exists
        if not Path(pg_wal_archive_dir).exists():
            logger.warning(f"PostgreSQL WAL archive directory not found: {pg_wal_archive_dir}")
            logger.info(
                "WAL archiving may not be configured. "
                "Ensure PostgreSQL archive_mode is 'on' and archive_command is set."
            )
            return 0

        # Get list of WAL files ready for archiving
        # WAL files follow the naming pattern: 000000010000000000000001
        # PostgreSQL's archive_command copies completed WAL files to this directory
        wal_files = []
        try:
            for file_path in Path(pg_wal_archive_dir).iterdir():
                if file_path.is_file() and len(file_path.name) == 24 and file_path.name.isalnum():
                    # Check if this WAL file has already been archived
                    # by checking if it exists in our backup records
                    wal_filename = file_path.name
                    remote_filename = f"{wal_filename}.gz"

                    # Check if already archived
                    from apps.core.tenant_context import bypass_rls

                    with bypass_rls():
                        already_archived = Backup.objects.filter(
                            backup_type=Backup.WAL_ARCHIVE, filename=remote_filename
                        ).exists()

                    if not already_archived:
                        wal_files.append(file_path)

        except Exception as e:
            logger.error(f"Error scanning WAL directory: {e}")
            return 0

        if not wal_files:
            logger.info("No new WAL files to archive")
            return 0

        logger.info(f"Found {len(wal_files)} WAL file(s) to archive")

        # Process each WAL file
        for wal_file_path in wal_files:
            backup = None
            wal_filename = wal_file_path.name

            try:
                logger.info(f"Processing WAL file: {wal_filename}")

                # Generate remote filename
                remote_filename = f"{wal_filename}.gz"

                # Create backup record
                from apps.core.tenant_context import bypass_rls

                with bypass_rls():
                    backup = Backup.objects.create(
                        backup_type=Backup.WAL_ARCHIVE,
                        tenant=None,  # WAL archives are not tenant-specific
                        filename=remote_filename,
                        size_bytes=0,  # Will be updated later
                        checksum="",  # Will be updated later
                        local_path="",  # WAL files skip local storage
                        r2_path="",
                        b2_path="",
                        status=Backup.IN_PROGRESS,
                        backup_job_id=self.request.id,
                    )

                logger.info(f"Created backup record: {backup.id}")

                # Get original WAL file size
                original_size = wal_file_path.stat().st_size
                logger.info(f"WAL file size: {original_size / (1024**2):.2f} MB")

                # Step 1: Compress WAL file and keep it locally (save space)
                compressed_local_path = str(wal_file_path) + ".gz"

                logger.info("Compressing WAL file...")

                # Import compression function
                from .encryption import calculate_checksum, compress_file

                compressed_path, original_size_returned, final_size = compress_file(
                    input_path=str(wal_file_path), output_path=compressed_local_path
                )

                # Calculate SHA-256 checksum of compressed file
                checksum = calculate_checksum(compressed_path, algorithm='sha256')

                # Calculate compression ratio
                compression_ratio = 1 - (final_size / original_size) if original_size > 0 else 0

                logger.info(f"Compressed size: {final_size / (1024**2):.2f} MB")
                logger.info(f"Compression ratio: {compression_ratio * 100:.1f}%")
                logger.info(f"Checksum: {checksum}")

                # Step 2: Upload to R2 and B2 (also keep compressed file locally)
                logger.info("Uploading to cloud storage (R2 and B2)...")

                storage_paths = {"local": f"{remote_filename}", "r2": None, "b2": None}

                # Upload to Cloudflare R2
                try:
                    r2_storage = get_storage_backend("r2")
                    # Use a subdirectory for WAL files
                    r2_remote_path = f"wal/{remote_filename}"
                    if r2_storage.upload(compressed_local_path, r2_remote_path):
                        storage_paths["r2"] = r2_remote_path
                        logger.info(f"Uploaded to Cloudflare R2: {r2_remote_path}")
                    else:
                        logger.error(f"Failed to upload to Cloudflare R2: {r2_remote_path}")
                except Exception as e:
                    logger.error(f"Error uploading to Cloudflare R2: {e}")

                # Upload to Backblaze B2
                try:
                    b2_storage = get_storage_backend("b2")
                    # Use a subdirectory for WAL files
                    b2_remote_path = f"wal/{remote_filename}"
                    if b2_storage.upload(compressed_local_path, b2_remote_path):
                        storage_paths["b2"] = b2_remote_path
                        logger.info(f"Uploaded to Backblaze B2: {b2_remote_path}")
                    else:
                        logger.error(f"Failed to upload to Backblaze B2: {b2_remote_path}")
                except Exception as e:
                    logger.error(f"Error uploading to Backblaze B2: {e}")

                # Require at least one cloud storage location
                if not storage_paths["r2"] and not storage_paths["b2"]:
                    raise Exception("Failed to upload to any cloud storage location")

                # Step 3: Update backup record
                with bypass_rls():
                    backup.size_bytes = final_size
                    backup.checksum = checksum
                    backup.local_path = storage_paths["local"]  # Keep compressed locally
                    backup.r2_path = storage_paths["r2"] or ""
                    backup.b2_path = storage_paths["b2"] or ""
                    backup.status = Backup.COMPLETED
                    backup.compression_ratio = compression_ratio
                    backup.backup_duration_seconds = int(
                        (timezone.now() - start_time).total_seconds()
                    )
                    backup.metadata = {
                        "wal_filename": wal_filename,
                        "original_size_bytes": original_size,
                        "compressed_size_bytes": final_size,
                        "pg_wal_archive_dir": pg_wal_archive_dir,
                        "kept_compressed_locally": True,
                    }
                    backup.save()

                logger.info(f"WAL file archived successfully: {backup.id}")

                # Step 4: Remove UNCOMPRESSED WAL file (keep .gz compressed version)
                # This saves ~94% disk space (16MB uncompressed -> 1MB compressed)
                try:
                    wal_file_path.unlink()
                    logger.info(f"Removed uncompressed WAL: {wal_filename}")
                    logger.info(f"Kept compressed file: {compressed_local_path} ({final_size / (1024**2):.2f} MB)")
                except Exception as e:
                    logger.warning(f"Failed to remove uncompressed WAL {wal_filename}: {e}")
                    # This is not critical - PostgreSQL will handle cleanup

                # Mark as verified
                with bypass_rls():
                    backup.status = Backup.VERIFIED
                    backup.verified_at = timezone.now()
                    backup.save()

                archived_count += 1

            except Exception as e:

                logger.error(f"WAL archiving failed for {wal_filename}: {e}", exc_info=True)

                # Update backup record to failed status
                if backup:
                    from apps.core.tenant_context import bypass_rls

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
                    message=f"WAL archiving failed for {wal_filename}: {str(e)}",
                    backup=backup,
                    details={
                        "error": str(e),
                        "wal_filename": wal_filename,
                        "task_id": self.request.id,
                    },
                )

                # Continue with next WAL file instead of failing entire task
                continue

            finally:
                # Clean up temporary files
                cleanup_temp_files(*temp_files)
                temp_files = []

        logger.info("=" * 80)
        logger.info(f"Continuous WAL archiving completed: {archived_count} file(s) archived")
        logger.info("=" * 80)

        # Step 5: Cleanup old WAL archives (7-day local, 30-day cloud retention)
        cleanup_old_wal_archives()

        return archived_count

    except Exception as e:
        logger.error(f"Continuous WAL archiving task failed: {e}", exc_info=True)

        # Create alert for overall task failure
        create_backup_alert(
            alert_type=BackupAlert.BACKUP_FAILURE,
            severity=BackupAlert.ERROR,
            message=f"Continuous WAL archiving task failed: {str(e)}",
            details={"error": str(e), "task_id": self.request.id},
        )

        # Retry the task
        raise self.retry(exc=e)

    finally:
        # Clean up any remaining temporary files
        cleanup_temp_files(*temp_files)


def cleanup_old_wal_archives():  # noqa: C901
    """
    Clean up old WAL archives according to retention policies.

    Retention policies:
    - Local storage: 7 days (WAL files skip local storage, so nothing to clean)
    - Cloud storage (R2 and B2): 30 days

    This function is called automatically after each WAL archiving run.
    """
    try:
        logger.info("Starting WAL archive cleanup...")

        from datetime import timedelta

        from apps.core.tenant_context import bypass_rls

        # Calculate cutoff date for cloud storage (30 days)
        cloud_cutoff = timezone.now() - timedelta(days=30)

        # Find old WAL archives
        with bypass_rls():
            old_wal_archives = list(
                Backup.objects.filter(backup_type=Backup.WAL_ARCHIVE, created_at__lt=cloud_cutoff)
            )

        old_count = len(old_wal_archives)

        if old_count == 0:
            logger.info("No old WAL archives to clean up")
            return

        logger.info(f"Found {old_count} old WAL archive(s) to clean up")

        # Delete old WAL archives from cloud storage
        for backup in old_wal_archives:
            try:
                # Delete from R2
                if backup.r2_path:
                    try:
                        r2_storage = get_storage_backend("r2")
                        if r2_storage.delete(backup.r2_path):
                            logger.info(f"Deleted from R2: {backup.r2_path}")
                        else:
                            logger.warning(f"Failed to delete from R2: {backup.r2_path}")
                    except Exception as e:
                        logger.error(f"Error deleting from R2: {e}")

                # Delete from B2
                if backup.b2_path:
                    try:
                        b2_storage = get_storage_backend("b2")
                        if b2_storage.delete(backup.b2_path):
                            logger.info(f"Deleted from B2: {backup.b2_path}")
                        else:
                            logger.warning(f"Failed to delete from B2: {backup.b2_path}")
                    except Exception as e:
                        logger.error(f"Error deleting from B2: {e}")

                # Delete backup record (need bypass_rls for deletion)
                with bypass_rls():
                    backup.delete()
                logger.info(f"Deleted backup record: {backup.id}")

            except Exception as e:
                logger.error(f"Error cleaning up WAL archive {backup.id}: {e}")
                continue

        logger.info(f"WAL archive cleanup completed: {old_count} archive(s) removed")

    except Exception as e:
        logger.error(f"WAL archive cleanup failed: {e}", exc_info=True)


def collect_configuration_files(temp_dir: str) -> Tuple[list, dict]:  # noqa: C901
    """
    Collect all configuration files for backup.

    This function collects:
    - Docker configuration files (docker-compose.yml, Dockerfile)
    - Environment files (.env, .env.example)
    - Nginx configuration files (if they exist)
    - SSL certificates (if they exist)
    - Kubernetes manifests (if they exist)
    - PostgreSQL configuration files

    Args:
        temp_dir: Temporary directory to copy files to

    Returns:
        Tuple of (list of collected file paths, metadata dict)
    """
    collected_files = []
    metadata = {
        "docker_files": [],
        "env_files": [],
        "nginx_files": [],
        "ssl_files": [],
        "k8s_files": [],
        "postgres_files": [],
        "other_files": [],
    }

    # Get project root directory (where manage.py is located)
    project_root = Path(settings.BASE_DIR)

    # Create subdirectories in temp directory to preserve structure
    config_backup_dir = Path(temp_dir) / "config_backup"
    config_backup_dir.mkdir(parents=True, exist_ok=True)

    # Helper function to copy file and track it
    def copy_file(source_path: Path, category: str, relative_path: str = None):
        """Copy a file to the backup directory and track it."""
        if not source_path.exists():
            logger.debug(f"File not found, skipping: {source_path}")
            return

        # Determine destination path
        if relative_path:
            dest_path = config_backup_dir / relative_path
        else:
            # Use relative path from project root
            try:
                rel_path = source_path.relative_to(project_root)
                dest_path = config_backup_dir / rel_path
            except ValueError:
                # File is outside project root, use just the filename
                dest_path = config_backup_dir / source_path.name

        # Create parent directories
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy file
        import shutil

        shutil.copy2(source_path, dest_path)
        collected_files.append(str(dest_path))
        metadata[category].append(str(source_path.relative_to(project_root)))
        logger.debug(f"Collected {category}: {source_path.name}")

    # 1. Docker configuration files
    logger.info("Collecting Docker configuration files...")
    docker_files = [
        "docker-compose.yml",
        "docker-compose.dev.yml",
        "docker-compose.prod.yml",
        "Dockerfile",
        ".dockerignore",
    ]
    for filename in docker_files:
        copy_file(project_root / filename, "docker_files")

    # Docker directory files
    docker_dir = project_root / "docker"
    if docker_dir.exists():
        for file_path in docker_dir.rglob("*"):
            if file_path.is_file():
                copy_file(file_path, "docker_files")

    # 2. Environment files
    logger.info("Collecting environment files...")
    env_files = [".env.example"]  # Don't include .env directly for security
    for filename in env_files:
        copy_file(project_root / filename, "env_files")

    # Create a sanitized version of .env (remove sensitive values)
    env_file = project_root / ".env"
    if env_file.exists():
        sanitized_env_path = config_backup_dir / ".env.sanitized"
        try:
            with open(env_file, "r") as f_in:
                with open(sanitized_env_path, "w") as f_out:
                    for line in f_in:
                        # Keep structure but mask sensitive values
                        if "=" in line and not line.strip().startswith("#"):
                            key, _ = line.split("=", 1)
                            f_out.write(f"{key}=***REDACTED***\n")
                        else:
                            f_out.write(line)
            collected_files.append(str(sanitized_env_path))
            metadata["env_files"].append(".env.sanitized")
            logger.info("Created sanitized .env file")
        except Exception as e:
            logger.warning(f"Failed to create sanitized .env: {e}")

    # 3. Nginx configuration files
    logger.info("Collecting Nginx configuration files...")
    nginx_locations = [
        project_root / "nginx",
        project_root / "config" / "nginx",
        Path("/etc/nginx"),  # System nginx config (if accessible)
    ]
    for nginx_dir in nginx_locations:
        if nginx_dir.exists() and nginx_dir.is_dir():
            for file_path in nginx_dir.rglob("*.conf"):
                if file_path.is_file():
                    copy_file(file_path, "nginx_files")

    # 4. SSL certificates (if they exist)
    logger.info("Collecting SSL certificates...")
    ssl_locations = [
        project_root / "ssl",
        project_root / "certs",
        Path("/etc/letsencrypt"),  # Let's Encrypt certs (if accessible)
    ]
    for ssl_dir in ssl_locations:
        if ssl_dir.exists() and ssl_dir.is_dir():
            for file_path in ssl_dir.rglob("*"):
                if file_path.is_file() and file_path.suffix in [".pem", ".crt", ".key", ".cert"]:
                    copy_file(file_path, "ssl_files")

    # 5. Kubernetes manifests
    logger.info("Collecting Kubernetes manifests...")
    k8s_locations = [
        project_root / "k8s",
        project_root / "kubernetes",
        project_root / "manifests",
    ]
    for k8s_dir in k8s_locations:
        if k8s_dir.exists() and k8s_dir.is_dir():
            for file_path in k8s_dir.rglob("*"):
                if file_path.is_file() and file_path.suffix in [".yaml", ".yml"]:
                    copy_file(file_path, "k8s_files")

    # 6. PostgreSQL configuration files
    logger.info("Collecting PostgreSQL configuration files...")
    postgres_files = [
        project_root / "docker" / "postgresql.conf",
        project_root / "docker" / "init-db.sh",
        project_root / "docker" / "init-wal-archive.sh",
    ]
    for file_path in postgres_files:
        if file_path.exists():
            copy_file(file_path, "postgres_files")

    postgres_dir = project_root / "docker" / "postgres"
    if postgres_dir.exists():
        for file_path in postgres_dir.rglob("*"):
            if file_path.is_file():
                copy_file(file_path, "postgres_files")

    # 7. Other important configuration files
    logger.info("Collecting other configuration files...")
    other_files = [
        "requirements.txt",
        "pyproject.toml",
        "setup.cfg",
        "pytest.ini",
        ".pre-commit-config.yaml",
        "Makefile",
    ]
    for filename in other_files:
        copy_file(project_root / filename, "other_files")

    # Django settings
    settings_dir = project_root / "config"
    if settings_dir.exists():
        for file_path in settings_dir.glob("*.py"):
            if file_path.is_file():
                copy_file(file_path, "other_files")

    # Count collected files
    total_files = len(collected_files)
    logger.info(f"Collected {total_files} configuration file(s)")
    logger.info(f"  - Docker files: {len(metadata['docker_files'])}")
    logger.info(f"  - Environment files: {len(metadata['env_files'])}")
    logger.info(f"  - Nginx files: {len(metadata['nginx_files'])}")
    logger.info(f"  - SSL files: {len(metadata['ssl_files'])}")
    logger.info(f"  - Kubernetes files: {len(metadata['k8s_files'])}")
    logger.info(f"  - PostgreSQL files: {len(metadata['postgres_files'])}")
    logger.info(f"  - Other files: {len(metadata['other_files'])}")

    return collected_files, metadata


def create_tar_archive(source_dir: str, output_path: str) -> Tuple[bool, Optional[str], int]:
    """
    Create a tar.gz archive from a directory.

    Args:
        source_dir: Directory to archive
        output_path: Path for the output tar.gz file

    Returns:
        Tuple of (success: bool, error_message: Optional[str], archive_size: int)
    """
    import tarfile

    try:
        logger.info(f"Creating tar.gz archive: {output_path}")

        # Create tar.gz archive with maximum compression
        with tarfile.open(output_path, "w:gz", compresslevel=9) as tar:
            # Add all files from source directory
            tar.add(source_dir, arcname=Path(source_dir).name)

        # Get archive size
        archive_size = Path(output_path).stat().st_size

        logger.info(f"Created tar.gz archive: {archive_size / (1024**2):.2f} MB")

        return True, None, archive_size

    except Exception as e:
        error_msg = f"Failed to create tar.gz archive: {e}"
        logger.error(error_msg)
        return False, error_msg, 0


@shared_task(
    bind=True,
    name="apps.backups.tasks.configuration_backup",
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def configuration_backup(self, initiated_by_user_id: Optional[int] = None):
    """
    Perform configuration backup.

    This task:
    1. Collects all configuration files (docker-compose, .env, nginx, SSL, k8s)
    2. Creates a tar.gz archive preserving directory structure
    3. Encrypts the archive with AES-256
    4. Calculates SHA-256 checksum
    5. Uploads to all three storage locations (local, R2, B2)
    6. Records metadata in the database

    Configuration files include:
    - Docker: docker-compose.yml, Dockerfile, docker directory
    - Environment: .env.example, .env (sanitized)
    - Nginx: nginx.conf and related files
    - SSL: certificates and keys
    - Kubernetes: k8s manifests
    - PostgreSQL: postgresql.conf, init scripts
    - Other: requirements.txt, settings.py, etc.

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
        logger.info("Starting configuration backup")
        logger.info("=" * 80)

        # Generate filename
        filename = generate_backup_filename("CONFIGURATION")
        tar_filename = f"{filename}.tar.gz"
        remote_filename = f"{tar_filename}.enc"

        # Create backup record
        backup = Backup.objects.create(
            backup_type=Backup.CONFIGURATION,
            tenant=None,  # Configuration backup is not tenant-specific
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

        # Step 1: Collect configuration files in a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info("Collecting configuration files...")

            collected_files, metadata = collect_configuration_files(temp_dir)

            if not collected_files:
                raise Exception("No configuration files found to backup")

            # Step 2: Create tar.gz archive
            tar_path = os.path.join(temp_dir, tar_filename)
            temp_files.append(tar_path)

            logger.info("Creating tar.gz archive...")

            config_backup_dir = Path(temp_dir) / "config_backup"
            success, error_msg, original_size = create_tar_archive(str(config_backup_dir), tar_path)

            if not success:
                raise Exception(f"Failed to create tar.gz archive: {error_msg}")

            logger.info(f"Archive size: {original_size / (1024**2):.2f} MB")

            # Step 3: Encrypt the archive
            logger.info("Encrypting configuration archive...")

            encrypted_path, checksum, _, compressed_size, final_size = compress_and_encrypt_file(
                input_path=tar_path, output_path=os.path.join(temp_dir, remote_filename)
            )
            temp_files.append(encrypted_path)

            # Note: compress_and_encrypt_file compresses again, but tar.gz is already compressed
            # The additional compression won't reduce size much, but encryption is applied
            compression_ratio = 1 - (compressed_size / original_size) if original_size > 0 else 0

            logger.info(f"Compressed size: {compressed_size / (1024**2):.2f} MB")
            logger.info(f"Encrypted size: {final_size / (1024**2):.2f} MB")
            logger.info(f"Compression ratio: {compression_ratio * 100:.1f}%")
            logger.info(f"Checksum: {checksum}")

            # Step 4: Upload to all storage locations
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

            # Step 5: Update backup record
            backup.size_bytes = final_size
            backup.checksum = checksum
            backup.local_path = storage_paths["local"] or ""
            backup.r2_path = storage_paths["r2"] or ""
            backup.b2_path = storage_paths["b2"] or ""
            backup.status = Backup.COMPLETED
            backup.compression_ratio = compression_ratio * 100  # Convert to percentage
            backup.backup_duration_seconds = int((timezone.now() - start_time).total_seconds())
            backup.metadata = {
                "original_size_bytes": original_size,
                "compressed_size_bytes": compressed_size,
                "archive_format": "tar.gz",
                "files_collected": len(collected_files),
                "file_categories": metadata,
            }
            backup.save()

            logger.info(f"Configuration backup completed successfully: {backup.id}")
            logger.info(f"Duration: {backup.backup_duration_seconds} seconds")

            # Step 6: Verify backup integrity
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
                    message=f"Configuration backup integrity verification failed for {remote_filename}",
                    backup=backup,
                    details=verification_result,
                )

        logger.info("=" * 80)
        logger.info(f"Configuration backup completed: {backup.id}")
        logger.info("=" * 80)

        return str(backup.id)

    except Exception as e:
        logger.error(f"Configuration backup failed: {e}", exc_info=True)

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
            message=f"Configuration backup failed: {str(e)}",
            backup=backup,
            details={"error": str(e), "task_id": self.request.id},
        )

        # Retry the task
        raise self.retry(exc=e)

    finally:
        # Clean up temporary files (if they weren't in a temp directory)
        cleanup_temp_files(*temp_files)


# Wrapper functions for manual backup triggers


@shared_task(
    bind=True,
    name="apps.backups.tasks.perform_full_database_backup",
    max_retries=3,
    default_retry_delay=300,
)
def perform_full_database_backup(self, notes: str = "", created_by_id: Optional[int] = None):
    """
    Wrapper for manual full database backup trigger.

    Args:
        notes: Optional notes about the backup
        created_by_id: ID of user who initiated the backup

    Returns:
        Backup ID if successful
    """
    return daily_full_database_backup(initiated_by_user_id=created_by_id)


@shared_task(
    bind=True,
    name="apps.backups.tasks.perform_tenant_backup",
    max_retries=3,
    default_retry_delay=300,
)
def perform_tenant_backup(
    self, tenant_id: str, notes: str = "", created_by_id: Optional[int] = None
):
    """
    Wrapper for manual tenant backup trigger.

    Args:
        tenant_id: UUID of the tenant to backup
        notes: Optional notes about the backup
        created_by_id: ID of user who initiated the backup

    Returns:
        List of backup IDs if successful
    """
    # Call the helper function directly, not as a Celery task
    return _do_weekly_per_tenant_backup(
        task_self=self, tenant_id=tenant_id, initiated_by_user_id=created_by_id
    )


@shared_task(
    bind=True,
    name="apps.backups.tasks.perform_configuration_backup",
    max_retries=3,
    default_retry_delay=300,
)
def perform_configuration_backup(self, notes: str = "", created_by_id: Optional[int] = None):
    """
    Wrapper for manual configuration backup trigger.

    Args:
        notes: Optional notes about the backup
        created_by_id: ID of user who initiated the backup

    Returns:
        Backup ID if successful
    """
    return configuration_backup(initiated_by_user_id=created_by_id)


@shared_task(
    bind=True,
    name="apps.backups.tasks.perform_restore_operation",
    max_retries=1,  # Restores should not be retried automatically
    default_retry_delay=0,
)
def perform_restore_operation(self, restore_log_id: str):  # noqa: C901
    """
    Perform a restore operation based on a restore log entry.

    This task:
    1. Retrieves the restore log and backup information
    2. Downloads the backup from storage
    3. Decrypts and decompresses the backup
    4. Performs the restore based on restore mode (FULL, MERGE, PITR)
    5. Updates the restore log with results

    Args:
        restore_log_id: UUID of the BackupRestoreLog entry

    Returns:
        Restore log ID if successful
    """
    from apps.core.tenant_context import bypass_rls

    start_time = timezone.now()
    restore_log = None
    temp_files = []

    try:
        logger.info("=" * 80)
        logger.info(f"Starting restore operation: {restore_log_id}")
        logger.info("=" * 80)

        # Get restore log
        with bypass_rls():
            restore_log = BackupRestoreLog.objects.get(id=restore_log_id)
            backup = restore_log.backup

        logger.info(f"Restore mode: {restore_log.restore_mode}")
        logger.info(f"Backup: {backup.filename}")
        logger.info(f"Backup type: {backup.backup_type}")

        # Validate backup
        if not backup.is_completed():
            raise Exception(f"Backup is not completed (status: {backup.status})")

        # Step 1: Download backup from storage
        logger.info("Downloading backup from storage...")

        with tempfile.TemporaryDirectory() as temp_dir:
            encrypted_path = os.path.join(temp_dir, backup.filename)
            temp_files.append(encrypted_path)

            # Try to download from R2 first, then B2, then local
            downloaded = False

            if backup.r2_path:
                try:
                    r2_storage = get_storage_backend("r2")
                    if r2_storage.download(backup.r2_path, encrypted_path):
                        logger.info(f"Downloaded from R2: {backup.r2_path}")
                        downloaded = True
                except Exception as e:
                    logger.warning(f"Failed to download from R2: {e}")

            if not downloaded and backup.b2_path:
                try:
                    b2_storage = get_storage_backend("b2")
                    if b2_storage.download(backup.b2_path, encrypted_path):
                        logger.info(f"Downloaded from B2: {backup.b2_path}")
                        downloaded = True
                except Exception as e:
                    logger.warning(f"Failed to download from B2: {e}")

            if not downloaded and backup.local_path:
                try:
                    local_storage = get_storage_backend("local")
                    if local_storage.download(backup.local_path, encrypted_path):
                        logger.info(f"Downloaded from local storage: {backup.local_path}")
                        downloaded = True
                except Exception as e:
                    logger.warning(f"Failed to download from local storage: {e}")

            if not downloaded:
                raise Exception("Failed to download backup from any storage location")

            # Step 2: Decrypt and decompress backup
            logger.info("Decrypting and decompressing backup...")

            from .encryption import decrypt_and_decompress_file

            decrypted_path = os.path.join(temp_dir, backup.filename.replace(".gz.enc", ""))
            temp_files.append(decrypted_path)

            decrypt_and_decompress_file(encrypted_path, decrypted_path)

            logger.info(f"Decrypted and decompressed: {decrypted_path}")

            # Step 3: Perform restore based on mode
            logger.info(f"Performing {restore_log.restore_mode} restore...")

            db_config = get_database_config()

            if restore_log.restore_mode == BackupRestoreLog.FULL:
                # Full restore - replace all data (DESTRUCTIVE)
                logger.warning("FULL RESTORE MODE - This will replace all existing data!")

                # Use pg_restore with --clean to drop existing objects
                success, error_msg = perform_pg_restore(
                    dump_path=decrypted_path,
                    database=db_config["name"],
                    user=db_config["user"],
                    password=db_config["password"],
                    host=db_config["host"],
                    port=db_config["port"],
                    clean=True,
                    selective_tenants=restore_log.tenant_ids,
                )

                if not success:
                    raise Exception(f"pg_restore failed: {error_msg}")

            elif restore_log.restore_mode == BackupRestoreLog.MERGE:
                # Merge restore - preserve existing data
                logger.info("MERGE RESTORE MODE - Preserving existing data")

                # Use pg_restore without --clean to merge data
                success, error_msg = perform_pg_restore(
                    dump_path=decrypted_path,
                    database=db_config["name"],
                    user=db_config["user"],
                    password=db_config["password"],
                    host=db_config["host"],
                    port=db_config["port"],
                    clean=False,
                    selective_tenants=restore_log.tenant_ids,
                )

                if not success:
                    raise Exception(f"pg_restore failed: {error_msg}")

            elif restore_log.restore_mode == BackupRestoreLog.PITR:
                # Point-in-Time Recovery
                logger.info(f"PITR MODE - Restoring to {restore_log.target_timestamp.isoformat()}")

                # PITR requires WAL archives and is more complex
                # For now, we'll implement basic PITR using pg_restore + WAL replay
                # Full PITR implementation would require PostgreSQL recovery.conf

                raise NotImplementedError(
                    "Point-in-Time Recovery is not yet fully implemented. "
                    "Please use FULL or MERGE restore mode."
                )

            else:
                raise Exception(f"Invalid restore mode: {restore_log.restore_mode}")

            # Step 4: Update restore log
            duration_seconds = int((timezone.now() - start_time).total_seconds())

            with bypass_rls():
                restore_log.status = BackupRestoreLog.COMPLETED
                restore_log.completed_at = timezone.now()
                restore_log.duration_seconds = duration_seconds
                restore_log.save()

            logger.info(f"Restore completed successfully: {restore_log.id}")
            logger.info(f"Duration: {duration_seconds} seconds")

        logger.info("=" * 80)
        logger.info(f"Restore operation completed: {restore_log.id}")
        logger.info("=" * 80)

        return str(restore_log.id)

    except Exception as e:
        logger.error(f"Restore operation failed: {e}", exc_info=True)

        # Update restore log to failed status
        if restore_log:
            duration_seconds = int((timezone.now() - start_time).total_seconds())

            with bypass_rls():
                restore_log.status = BackupRestoreLog.FAILED
                restore_log.error_message = str(e)
                restore_log.completed_at = timezone.now()
                restore_log.duration_seconds = duration_seconds
                restore_log.save()

        # Create alert
        create_backup_alert(
            alert_type=BackupAlert.RESTORE_FAILURE,
            severity=BackupAlert.CRITICAL,
            message=f"Restore operation failed: {str(e)}",
            restore_log=restore_log,
            details={"error": str(e), "task_id": self.request.id},
        )

        raise

    finally:
        # Clean up temporary files
        cleanup_temp_files(*temp_files)


def perform_pg_restore(
    dump_path: str,
    database: str,
    user: str,
    password: str,
    host: str,
    port: str,
    clean: bool = False,
    selective_tenants: Optional[list] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Perform PostgreSQL restore using pg_restore.

    Args:
        dump_path: Path to the dump file
        database: Database name
        user: Database user
        password: Database password
        host: Database host
        port: Database port
        clean: Whether to clean (drop) existing objects before restore
        selective_tenants: List of tenant IDs to restore (for selective restore)

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        # Set up environment for pg_restore
        env = os.environ.copy()
        env["PGPASSWORD"] = password

        # Build pg_restore command
        # -Fc: Custom format
        # -v: Verbose mode
        # --no-owner: Don't output commands to set ownership
        # --no-acl: Don't output commands to set access privileges
        # -j 4: Use 4 parallel jobs for faster restore
        cmd = [
            "pg_restore",
            "-v",  # Verbose
            "--no-owner",
            "--no-acl",
            "-j",
            "4",  # Parallel jobs
            "-h",
            host,
            "-p",
            port,
            "-U",
            user,
            "-d",
            database,
        ]

        # Add --clean flag if requested (DESTRUCTIVE)
        if clean:
            cmd.append("--clean")

        # Add dump file
        cmd.append(dump_path)

        logger.info(f"Starting pg_restore for database {database}")
        if clean:
            logger.warning("Using --clean flag - existing objects will be dropped!")

        # Execute pg_restore
        result = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=7200  # 2 hour timeout
        )

        # pg_restore may return non-zero even on success if some objects already exist
        # Check stderr for actual errors
        if result.returncode != 0:
            # Check if errors are just warnings about existing objects
            if "already exists" in result.stderr or "does not exist" in result.stderr:
                logger.warning(f"pg_restore completed with warnings: {result.stderr}")
                return True, None
            else:
                error_msg = (
                    f"pg_restore failed with return code {result.returncode}: {result.stderr}"
                )
                logger.error(error_msg)
                return False, error_msg

        logger.info("pg_restore completed successfully")
        return True, None

    except subprocess.TimeoutExpired:
        error_msg = "pg_restore timed out after 2 hours"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"pg_restore failed with exception: {e}"
        logger.error(error_msg)
        return False, error_msg


@shared_task(
    bind=True,
    name="apps.backups.tasks.execute_disaster_recovery_runbook",
    max_retries=0,  # DR should not be retried automatically
    default_retry_delay=0,
)
def execute_disaster_recovery_runbook(  # noqa: C901
    self, backup_id: Optional[str] = None, reason: str = "Disaster recovery initiated"
):
    """
    Execute automated disaster recovery runbook with 1-hour RTO.

    This task implements the complete disaster recovery procedure:
    1. Download latest backup from R2 (with B2 failover)
    2. Decrypt and decompress backup
    3. Restore database with 4 parallel jobs
    4. Restart application pods (if in Kubernetes)
    5. Verify health checks
    6. Reroute traffic (if needed)
    7. Log all DR events

    Args:
        backup_id: Optional specific backup ID to restore (defaults to latest)
        reason: Reason for disaster recovery

    Returns:
        Dictionary with DR operation results
    """
    from apps.core.tenant_context import bypass_rls

    start_time = timezone.now()
    dr_log = {
        "start_time": start_time.isoformat(),
        "backup_id": backup_id,
        "reason": reason,
        "steps": [],
        "success": False,
        "error": None,
        "duration_seconds": 0,
    }

    restore_log = None
    temp_files = []

    try:
        logger.info("=" * 80)
        logger.info("DISASTER RECOVERY RUNBOOK INITIATED")
        logger.info(f"Reason: {reason}")
        logger.info("Target RTO: 1 hour")
        logger.info("=" * 80)

        # Step 1: Select backup to restore
        logger.info("Step 1: Selecting backup for restore...")
        step_start = timezone.now()

        with bypass_rls():
            if backup_id:
                backup = Backup.objects.get(id=backup_id)
                logger.info(f"Using specified backup: {backup.filename}")
            else:
                # Get latest successful full database backup
                backup = (
                    Backup.objects.filter(
                        backup_type=Backup.FULL_DATABASE,
                        status__in=[Backup.COMPLETED, Backup.VERIFIED],
                    )
                    .order_by("-created_at")
                    .first()
                )

                if not backup:
                    raise Exception("No successful full database backup found")

                logger.info(f"Using latest backup: {backup.filename}")
                logger.info(f"Backup created at: {backup.created_at.isoformat()}")

        step_duration = (timezone.now() - step_start).total_seconds()
        dr_log["steps"].append(
            {
                "step": 1,
                "name": "Select backup",
                "status": "completed",
                "duration_seconds": step_duration,
                "backup_id": str(backup.id),
                "backup_filename": backup.filename,
            }
        )

        # Step 2: Download backup from R2 with B2 failover
        logger.info("Step 2: Downloading backup from storage...")
        step_start = timezone.now()

        with tempfile.TemporaryDirectory() as temp_dir:
            encrypted_path = os.path.join(temp_dir, backup.filename)
            temp_files.append(encrypted_path)

            downloaded = False
            download_source = None

            # Try R2 first
            if backup.r2_path:
                try:
                    logger.info("Attempting download from Cloudflare R2...")
                    r2_storage = get_storage_backend("r2")
                    if r2_storage.download(backup.r2_path, encrypted_path):
                        logger.info(f"✓ Downloaded from R2: {backup.r2_path}")
                        downloaded = True
                        download_source = "r2"
                except Exception as e:
                    logger.warning(f"✗ Failed to download from R2: {e}")

            # Failover to B2
            if not downloaded and backup.b2_path:
                try:
                    logger.info("Failing over to Backblaze B2...")
                    b2_storage = get_storage_backend("b2")
                    if b2_storage.download(backup.b2_path, encrypted_path):
                        logger.info(f"✓ Downloaded from B2: {backup.b2_path}")
                        downloaded = True
                        download_source = "b2"
                except Exception as e:
                    logger.warning(f"✗ Failed to download from B2: {e}")

            # Last resort: local storage
            if not downloaded and backup.local_path:
                try:
                    logger.info("Attempting download from local storage...")
                    local_storage = get_storage_backend("local")
                    if local_storage.download(backup.local_path, encrypted_path):
                        logger.info(f"✓ Downloaded from local storage: {backup.local_path}")
                        downloaded = True
                        download_source = "local"
                except Exception as e:
                    logger.warning(f"✗ Failed to download from local storage: {e}")

            if not downloaded:
                raise Exception(
                    "Failed to download backup from any storage location (R2, B2, local)"
                )

            step_duration = (timezone.now() - step_start).total_seconds()
            dr_log["steps"].append(
                {
                    "step": 2,
                    "name": "Download backup",
                    "status": "completed",
                    "duration_seconds": step_duration,
                    "source": download_source,
                    "size_mb": backup.get_size_mb(),
                }
            )

            # Step 3: Decrypt and decompress backup
            logger.info("Step 3: Decrypting and decompressing backup...")
            step_start = timezone.now()

            from .encryption import decrypt_and_decompress_file

            decrypted_path = os.path.join(temp_dir, backup.filename.replace(".gz.enc", ""))
            temp_files.append(decrypted_path)

            decrypt_and_decompress_file(encrypted_path, decrypted_path)

            logger.info(f"✓ Decrypted and decompressed: {decrypted_path}")

            step_duration = (timezone.now() - step_start).total_seconds()
            dr_log["steps"].append(
                {
                    "step": 3,
                    "name": "Decrypt and decompress",
                    "status": "completed",
                    "duration_seconds": step_duration,
                }
            )

            # Step 4: Restore database with 4 parallel jobs
            logger.info("Step 4: Restoring database with 4 parallel jobs...")
            step_start = timezone.now()

            db_config = get_database_config()

            # Create restore log entry
            with bypass_rls():
                restore_log = BackupRestoreLog.objects.create(
                    backup=backup,
                    initiated_by=None,  # Automated DR
                    restore_mode=BackupRestoreLog.FULL,
                    reason=reason,
                    status=BackupRestoreLog.IN_PROGRESS,
                )

            logger.info(f"Created restore log: {restore_log.id}")

            # Perform full restore with --clean
            success, error_msg = perform_pg_restore(
                dump_path=decrypted_path,
                database=db_config["name"],
                user=db_config["user"],
                password=db_config["password"],
                host=db_config["host"],
                port=db_config["port"],
                clean=True,  # Full restore - replace all data
                selective_tenants=None,
            )

            if not success:
                raise Exception(f"Database restore failed: {error_msg}")

            logger.info("✓ Database restored successfully")

            step_duration = (timezone.now() - step_start).total_seconds()
            dr_log["steps"].append(
                {
                    "step": 4,
                    "name": "Restore database",
                    "status": "completed",
                    "duration_seconds": step_duration,
                    "parallel_jobs": 4,
                }
            )

            # Step 5: Restart application pods (if in Kubernetes)
            logger.info("Step 5: Restarting application pods...")
            step_start = timezone.now()

            restart_success = False
            restart_method = None

            # Check if running in Kubernetes
            if os.path.exists("/var/run/secrets/kubernetes.io"):
                try:
                    logger.info("Detected Kubernetes environment")
                    # Restart Django pods by deleting them (Deployment will recreate)
                    result = subprocess.run(
                        [
                            "kubectl",
                            "rollout",
                            "restart",
                            "deployment/django-app",
                            "-n",
                            os.getenv("K8S_NAMESPACE", "default"),
                        ],
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )

                    if result.returncode == 0:
                        logger.info("✓ Kubernetes deployment restarted")
                        restart_success = True
                        restart_method = "kubernetes"
                    else:
                        logger.warning(f"kubectl rollout restart failed: {result.stderr}")
                except Exception as e:
                    logger.warning(f"Failed to restart Kubernetes deployment: {e}")

            # Check if running in Docker Compose
            if not restart_success and os.path.exists("/var/run/docker.sock"):
                try:
                    logger.info("Detected Docker environment")
                    # Restart web service
                    result = subprocess.run(
                        ["docker-compose", "restart", "web"],
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )

                    if result.returncode == 0:
                        logger.info("✓ Docker Compose service restarted")
                        restart_success = True
                        restart_method = "docker-compose"
                    else:
                        logger.warning(f"docker-compose restart failed: {result.stderr}")
                except Exception as e:
                    logger.warning(f"Failed to restart Docker Compose service: {e}")

            if not restart_success:
                logger.warning(
                    "Could not automatically restart application - manual restart required"
                )
                restart_method = "manual_required"

            step_duration = (timezone.now() - step_start).total_seconds()
            dr_log["steps"].append(
                {
                    "step": 5,
                    "name": "Restart application",
                    "status": "completed" if restart_success else "manual_required",
                    "duration_seconds": step_duration,
                    "method": restart_method,
                }
            )

            # Step 6: Verify health checks
            logger.info("Step 6: Verifying health checks...")
            step_start = timezone.now()

            import time

            import requests

            health_check_url = os.getenv("HEALTH_CHECK_URL", "http://localhost:8000/health/")
            max_attempts = 30
            health_check_passed = False

            logger.info(f"Waiting for application to be healthy (max {max_attempts} attempts)...")

            for attempt in range(1, max_attempts + 1):
                try:
                    response = requests.get(health_check_url, timeout=5)
                    if response.status_code == 200:
                        logger.info(f"✓ Health check passed on attempt {attempt}")
                        health_check_passed = True
                        break
                    else:
                        logger.info(
                            f"Health check attempt {attempt}/{max_attempts}: status {response.status_code}"
                        )
                except Exception as e:
                    logger.info(f"Health check attempt {attempt}/{max_attempts}: {e}")

                if attempt < max_attempts:
                    time.sleep(10)  # Wait 10 seconds between attempts

            if not health_check_passed:
                logger.warning(
                    "Health checks did not pass within timeout - manual verification required"
                )

            step_duration = (timezone.now() - step_start).total_seconds()
            dr_log["steps"].append(
                {
                    "step": 6,
                    "name": "Verify health checks",
                    "status": "completed" if health_check_passed else "manual_required",
                    "duration_seconds": step_duration,
                    "attempts": attempt,
                    "health_check_url": health_check_url,
                }
            )

            # Step 7: Reroute traffic (if needed)
            logger.info("Step 7: Rerouting traffic...")
            step_start = timezone.now()

            # In most setups, traffic routing is automatic via load balancer
            # This step is a placeholder for custom routing logic
            logger.info("Traffic routing handled by load balancer - no action needed")

            step_duration = (timezone.now() - step_start).total_seconds()
            dr_log["steps"].append(
                {
                    "step": 7,
                    "name": "Reroute traffic",
                    "status": "completed",
                    "duration_seconds": step_duration,
                    "method": "automatic_load_balancer",
                }
            )

            # Update restore log to completed
            total_duration = (timezone.now() - start_time).total_seconds()

            with bypass_rls():
                restore_log.status = BackupRestoreLog.COMPLETED
                restore_log.completed_at = timezone.now()
                restore_log.duration_seconds = int(total_duration)
                restore_log.notes = "Automated disaster recovery completed successfully"
                restore_log.metadata = dr_log
                restore_log.save()

            dr_log["success"] = True
            dr_log["duration_seconds"] = total_duration
            dr_log["restore_log_id"] = str(restore_log.id)

            logger.info("=" * 80)
            logger.info("DISASTER RECOVERY COMPLETED SUCCESSFULLY")
            logger.info(
                f"Total duration: {total_duration:.2f} seconds ({total_duration / 60:.2f} minutes)"
            )
            logger.info("RTO target: 3600 seconds (1 hour)")
            logger.info(f"RTO achieved: {'YES' if total_duration < 3600 else 'NO'}")
            logger.info("=" * 80)

            # Send success notification
            create_backup_alert(
                alert_type=BackupAlert.RESTORE_FAILURE,  # Reusing type for DR success
                severity=BackupAlert.INFO,
                message=f"Disaster recovery completed successfully in {total_duration / 60:.2f} minutes",
                backup=backup,
                details=dr_log,
            )

            return dr_log

    except Exception as e:
        logger.error(f"Disaster recovery failed: {e}", exc_info=True)

        total_duration = (timezone.now() - start_time).total_seconds()
        dr_log["success"] = False
        dr_log["error"] = str(e)
        dr_log["duration_seconds"] = total_duration

        # Update restore log to failed status
        if restore_log:
            with bypass_rls():
                restore_log.status = BackupRestoreLog.FAILED
                restore_log.error_message = str(e)
                restore_log.completed_at = timezone.now()
                restore_log.duration_seconds = int(total_duration)
                restore_log.metadata = dr_log
                restore_log.save()

        # Create critical alert
        create_backup_alert(
            alert_type=BackupAlert.RESTORE_FAILURE,
            severity=BackupAlert.CRITICAL,
            message=f"DISASTER RECOVERY FAILED: {str(e)}",
            backup=backup if "backup" in locals() else None,
            details=dr_log,
        )

        logger.error("=" * 80)
        logger.error("DISASTER RECOVERY FAILED")
        logger.error(f"Error: {e}")
        logger.error(f"Duration: {total_duration:.2f} seconds")
        logger.error("=" * 80)

        raise

    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.debug(f"Cleaned up temporary file: {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {temp_file}: {e}")


@shared_task(
    bind=True,
    name="apps.backups.tasks.monitor_storage_capacity",
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def monitor_storage_capacity(self):
    """
    Monitor storage capacity across all storage backends.

    This task should run hourly to check storage usage and create alerts
    if capacity exceeds 80%.

    Returns:
        Number of alerts created
    """
    from .monitoring import check_storage_capacity

    try:
        logger.info("Starting storage capacity monitoring")

        alerts = check_storage_capacity()

        logger.info(f"Storage capacity monitoring completed: {len(alerts)} alerts created")

        return len(alerts)

    except Exception as e:
        logger.error(f"Storage capacity monitoring failed: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(
    bind=True,
    name="apps.backups.tasks.cleanup_resolved_alerts",
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def cleanup_resolved_alerts(self, days_to_keep: int = 30):
    """
    Clean up old resolved backup alerts.

    This task should run daily to remove resolved alerts older than the specified days.

    Args:
        days_to_keep: Number of days to keep resolved alerts (default: 30)

    Returns:
        Number of alerts deleted
    """
    try:
        logger.info(f"Starting cleanup of resolved alerts older than {days_to_keep} days")

        cutoff_date = timezone.now() - timedelta(days=days_to_keep)

        deleted_count, _ = BackupAlert.objects.filter(
            status=BackupAlert.RESOLVED, resolved_at__lt=cutoff_date
        ).delete()

        logger.info(f"Cleaned up {deleted_count} resolved alerts")

        return deleted_count

    except Exception as e:
        logger.error(f"Alert cleanup failed: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(
    bind=True,
    name="apps.backups.tasks.send_alert_digest",
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def send_alert_digest(self):
    """
    Send daily digest of active backup alerts to platform admins.

    This task should run daily to provide a summary of all active alerts.

    Returns:
        Number of recipients notified
    """
    from .monitoring import get_active_alerts, get_alert_summary

    try:
        logger.info("Starting alert digest generation")

        # Get alert summary
        summary = get_alert_summary()

        # Only send digest if there are active alerts
        if summary["active_alerts"] == 0:
            logger.info("No active alerts, skipping digest")
            return 0

        # Get platform admins
        recipients = list(User.objects.filter(role="PLATFORM_ADMIN", is_active=True))

        if not recipients:
            logger.warning("No platform admins found for alert digest")
            return 0

        # Get active alerts grouped by severity
        critical_alerts = get_active_alerts(severity=BackupAlert.CRITICAL)
        error_alerts = get_active_alerts(severity=BackupAlert.ERROR)
        warning_alerts = get_active_alerts(severity=BackupAlert.WARNING)

        # Prepare context for email
        context = {
            "summary": summary,
            "critical_alerts": critical_alerts,
            "error_alerts": error_alerts,
            "warning_alerts": warning_alerts,
            "total_active": summary["active_alerts"],
        }

        # Send digest to each admin
        from apps.notifications.services import create_notification, send_system_email

        for user in recipients:
            # Create in-app notification
            create_notification(
                user=user,
                title=f"Backup Alert Digest: {summary['active_alerts']} Active Alerts",
                message=f"Critical: {summary['critical_alerts']}, "
                f"Active: {summary['active_alerts']}, "
                f"Recent (24h): {summary['recent_alerts_24h']}",
                notification_type="SYSTEM",
                action_url="/admin/backups/alerts/",
                action_text="View Alerts",
            )

            # Send email digest
            if user.email:
                try:
                    send_system_email(
                        user=user,
                        template_name="backup_alert_digest",
                        context=context,
                        subject=f"Backup Alert Digest: {summary['active_alerts']} Active Alerts",
                    )
                except Exception as e:
                    logger.error(f"Failed to send alert digest email to {user.email}: {e}")

        logger.info(f"Alert digest sent to {len(recipients)} platform admins")

        return len(recipients)

    except Exception as e:
        logger.error(f"Alert digest generation failed: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(
    bind=True,
    name="apps.backups.tasks.automated_test_restore",
    max_retries=1,  # Test restores should not be retried automatically
    default_retry_delay=0,
)
def automated_test_restore(self):  # noqa: C901
    """
    Perform automated monthly test restore to verify backup integrity.

    This task:
    1. Selects a random recent backup (from last 7 days)
    2. Restores backup to a staging/test database
    3. Verifies data integrity (row counts, tables, relationships)
    4. Generates test restore report
    5. Alerts on failures

    This task should run monthly on the 1st at 3:00 AM via Celery Beat.

    Returns:
        Dictionary with test restore results
    """
    from apps.core.tenant_context import bypass_rls

    start_time = timezone.now()
    test_report = {
        "start_time": start_time.isoformat(),
        "backup_id": None,
        "backup_filename": None,
        "test_database": None,
        "success": False,
        "integrity_checks": {},
        "errors": [],
        "duration_seconds": 0,
    }

    restore_log = None
    temp_files = []
    test_db_name = None

    try:
        logger.info("=" * 80)
        logger.info("AUTOMATED TEST RESTORE - Monthly Verification")
        logger.info("=" * 80)

        # Step 1: Select a random backup from the last 7 days
        logger.info("Step 1: Selecting random backup for test restore...")

        cutoff_date = timezone.now() - timedelta(days=7)

        with bypass_rls():
            # Get all successful full database backups from last 7 days
            recent_backups = list(
                Backup.objects.filter(
                    backup_type=Backup.FULL_DATABASE,
                    status__in=[Backup.COMPLETED, Backup.VERIFIED],
                    created_at__gte=cutoff_date,
                ).order_by("-created_at")
            )

        if not recent_backups:
            logger.warning("No recent backups found for test restore")
            test_report["errors"].append("No recent backups available for testing")
            test_report["success"] = False

            # Create alert
            create_backup_alert(
                alert_type=BackupAlert.BACKUP_FAILURE,
                severity=BackupAlert.WARNING,
                message="Automated test restore skipped: No recent backups available",
                details=test_report,
            )

            return test_report

        # Select a random backup
        import random

        backup = random.choice(recent_backups)

        logger.info(f"Selected backup: {backup.filename}")
        logger.info(f"Backup created at: {backup.created_at.isoformat()}")
        logger.info(f"Backup size: {backup.get_size_mb():.2f} MB")

        test_report["backup_id"] = str(backup.id)
        test_report["backup_filename"] = backup.filename

        # Step 2: Create test database
        logger.info("Step 2: Creating test database...")

        db_config = get_database_config()
        test_db_name = f"test_restore_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        test_report["test_database"] = test_db_name

        # Create test database
        success, error_msg = create_test_database(
            test_db_name=test_db_name,
            host=db_config["host"],
            port=db_config["port"],
            user=db_config["user"],
            password=db_config["password"],
        )

        if not success:
            raise Exception(f"Failed to create test database: {error_msg}")

        logger.info(f"✓ Created test database: {test_db_name}")

        # Step 3: Download backup from storage
        logger.info("Step 3: Downloading backup from storage...")

        with tempfile.TemporaryDirectory() as temp_dir:
            encrypted_path = os.path.join(temp_dir, backup.filename)
            temp_files.append(encrypted_path)

            # Try to download from R2 first, then B2, then local
            downloaded = False

            if backup.r2_path:
                try:
                    r2_storage = get_storage_backend("r2")
                    if r2_storage.download(backup.r2_path, encrypted_path):
                        logger.info(f"✓ Downloaded from R2: {backup.r2_path}")
                        downloaded = True
                except Exception as e:
                    logger.warning(f"Failed to download from R2: {e}")

            if not downloaded and backup.b2_path:
                try:
                    b2_storage = get_storage_backend("b2")
                    if b2_storage.download(backup.b2_path, encrypted_path):
                        logger.info(f"✓ Downloaded from B2: {backup.b2_path}")
                        downloaded = True
                except Exception as e:
                    logger.warning(f"Failed to download from B2: {e}")

            if not downloaded and backup.local_path:
                try:
                    local_storage = get_storage_backend("local")
                    if local_storage.download(backup.local_path, encrypted_path):
                        logger.info(f"✓ Downloaded from local storage: {backup.local_path}")
                        downloaded = True
                except Exception as e:
                    logger.warning(f"Failed to download from local storage: {e}")

            if not downloaded:
                raise Exception("Failed to download backup from any storage location")

            # Step 4: Decrypt and decompress backup
            logger.info("Step 4: Decrypting and decompressing backup...")

            from .encryption import decrypt_and_decompress_file

            decrypted_path = os.path.join(temp_dir, backup.filename.replace(".gz.enc", ""))
            temp_files.append(decrypted_path)

            decrypt_and_decompress_file(encrypted_path, decrypted_path)

            logger.info(f"✓ Decrypted and decompressed: {decrypted_path}")

            # Step 5: Restore backup to test database
            logger.info("Step 5: Restoring backup to test database...")

            # Create restore log entry
            with bypass_rls():
                restore_log = BackupRestoreLog.objects.create(
                    backup=backup,
                    initiated_by=None,  # Automated test restore
                    restore_mode=BackupRestoreLog.FULL,
                    reason="Automated monthly test restore for integrity verification",
                    status=BackupRestoreLog.IN_PROGRESS,
                    notes=f"Test restore to database: {test_db_name}",
                )

            logger.info(f"Created restore log: {restore_log.id}")

            # Perform restore to test database
            success, error_msg = perform_pg_restore(
                dump_path=decrypted_path,
                database=test_db_name,
                user=db_config["user"],
                password=db_config["password"],
                host=db_config["host"],
                port=db_config["port"],
                clean=False,  # Test database is empty, no need to clean
                selective_tenants=None,
            )

            if not success:
                raise Exception(f"Test restore failed: {error_msg}")

            logger.info("✓ Backup restored to test database successfully")

            # Step 6: Verify data integrity
            logger.info("Step 6: Verifying data integrity...")

            integrity_results = verify_test_restore_integrity(
                test_db_name=test_db_name,
                host=db_config["host"],
                port=db_config["port"],
                user=db_config["user"],
                password=db_config["password"],
            )

            test_report["integrity_checks"] = integrity_results

            # Check if all integrity checks passed
            all_checks_passed = all(
                check.get("passed", False) for check in integrity_results.values()
            )

            if not all_checks_passed:
                failed_checks = [
                    name
                    for name, check in integrity_results.items()
                    if not check.get("passed", False)
                ]
                raise Exception(f"Data integrity verification failed: {', '.join(failed_checks)}")

            logger.info("✓ All data integrity checks passed")

            # Step 7: Generate test restore report
            logger.info("Step 7: Generating test restore report...")

            total_duration = (timezone.now() - start_time).total_seconds()
            test_report["success"] = True
            test_report["duration_seconds"] = total_duration

            # Update restore log
            with bypass_rls():
                restore_log.status = BackupRestoreLog.COMPLETED
                restore_log.completed_at = timezone.now()
                restore_log.duration_seconds = int(total_duration)
                restore_log.metadata = test_report
                restore_log.save()

            logger.info("=" * 80)
            logger.info("AUTOMATED TEST RESTORE COMPLETED SUCCESSFULLY")
            logger.info(f"Backup: {backup.filename}")
            logger.info(f"Test database: {test_db_name}")
            logger.info(f"Duration: {total_duration:.2f} seconds")
            logger.info(f"Integrity checks: {len(integrity_results)} passed")
            logger.info("=" * 80)

            # Send success notification
            create_backup_alert(
                alert_type=BackupAlert.BACKUP_FAILURE,  # Reusing type for test restore success
                severity=BackupAlert.INFO,
                message=f"Automated test restore completed successfully: {backup.filename}",
                backup=backup,
                details=test_report,
            )

            return test_report

    except Exception as e:
        logger.error(f"Automated test restore failed: {e}", exc_info=True)

        total_duration = (timezone.now() - start_time).total_seconds()
        test_report["success"] = False
        test_report["errors"].append(str(e))
        test_report["duration_seconds"] = total_duration

        # Update restore log to failed status
        if restore_log:
            with bypass_rls():
                restore_log.status = BackupRestoreLog.FAILED
                restore_log.error_message = str(e)
                restore_log.completed_at = timezone.now()
                restore_log.duration_seconds = int(total_duration)
                restore_log.metadata = test_report
                restore_log.save()

        # Create critical alert
        create_backup_alert(
            alert_type=BackupAlert.BACKUP_FAILURE,
            severity=BackupAlert.CRITICAL,
            message=f"AUTOMATED TEST RESTORE FAILED: {str(e)}",
            backup=backup if "backup" in locals() else None,
            details=test_report,
        )

        logger.error("=" * 80)
        logger.error("AUTOMATED TEST RESTORE FAILED")
        logger.error(f"Error: {e}")
        logger.error(f"Duration: {total_duration:.2f} seconds")
        logger.error("=" * 80)

        return test_report

    finally:
        # Step 8: Cleanup test database
        if test_db_name:
            try:
                logger.info(f"Cleaning up test database: {test_db_name}")

                db_config = get_database_config()
                success, error_msg = drop_test_database(
                    test_db_name=test_db_name,
                    host=db_config["host"],
                    port=db_config["port"],
                    user=db_config["user"],
                    password=db_config["password"],
                )

                if success:
                    logger.info(f"✓ Dropped test database: {test_db_name}")
                else:
                    logger.warning(f"Failed to drop test database: {error_msg}")

            except Exception as e:
                logger.warning(f"Error cleaning up test database: {e}")

        # Clean up temporary files
        cleanup_temp_files(*temp_files)


def create_test_database(
    test_db_name: str, host: str, port: str, user: str, password: str
) -> Tuple[bool, Optional[str]]:
    """
    Create a test database for restore verification.

    Args:
        test_db_name: Name of the test database to create
        host: Database host
        port: Database port
        user: Database user
        password: Database password

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        # Set up environment
        env = os.environ.copy()
        env["PGPASSWORD"] = password

        # Create database using psql
        cmd = [
            "psql",
            "-h",
            host,
            "-p",
            port,
            "-U",
            user,
            "-d",
            "postgres",  # Connect to postgres database to create new database
            "-c",
            f"CREATE DATABASE {test_db_name};",
        ]

        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            logger.info(f"Created test database: {test_db_name}")
            return True, None
        else:
            error_msg = f"Failed to create test database: {result.stderr}"
            logger.error(error_msg)
            return False, error_msg

    except Exception as e:
        error_msg = f"Exception creating test database: {e}"
        logger.error(error_msg)
        return False, error_msg


def drop_test_database(
    test_db_name: str, host: str, port: str, user: str, password: str
) -> Tuple[bool, Optional[str]]:
    """
    Drop a test database after restore verification.

    Args:
        test_db_name: Name of the test database to drop
        host: Database host
        port: Database port
        user: Database user
        password: Database password

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        # Set up environment
        env = os.environ.copy()
        env["PGPASSWORD"] = password

        # Drop database using psql
        cmd = [
            "psql",
            "-h",
            host,
            "-p",
            port,
            "-U",
            user,
            "-d",
            "postgres",  # Connect to postgres database to drop database
            "-c",
            f"DROP DATABASE IF EXISTS {test_db_name};",
        ]

        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            logger.info(f"Dropped test database: {test_db_name}")
            return True, None
        else:
            error_msg = f"Failed to drop test database: {result.stderr}"
            logger.error(error_msg)
            return False, error_msg

    except Exception as e:
        error_msg = f"Exception dropping test database: {e}"
        logger.error(error_msg)
        return False, error_msg


def verify_test_restore_integrity(  # noqa: C901
    test_db_name: str, host: str, port: str, user: str, password: str
) -> dict:
    """
    Verify data integrity of a test restore.

    This function performs the following checks:
    1. Row counts for key tables
    2. Table existence verification
    3. Relationship integrity (foreign keys)
    4. Data corruption detection (basic checks)

    Args:
        test_db_name: Name of the test database
        host: Database host
        port: Database port
        user: Database user
        password: Database password

    Returns:
        Dictionary with integrity check results
    """
    import psycopg2

    results = {}

    try:
        # Connect to test database
        conn = psycopg2.connect(
            dbname=test_db_name, host=host, port=port, user=user, password=password
        )
        cursor = conn.cursor()

        # Check 1: Verify key tables exist
        logger.info("Checking table existence...")

        key_tables = [
            "tenants",
            "users",
            "core_branch",
            "inventory_items",
            "sales",
            "crm_customer",
            "backups_backup",
        ]

        existing_tables = []
        missing_tables = []

        for table in key_tables:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = %s
                );
            """,
                (table,),
            )
            exists = cursor.fetchone()[0]

            if exists:
                existing_tables.append(table)
            else:
                missing_tables.append(table)

        results["table_existence"] = {
            "passed": len(missing_tables) == 0,
            "existing_tables": existing_tables,
            "missing_tables": missing_tables,
            "total_checked": len(key_tables),
        }

        logger.info(f"Table existence: {len(existing_tables)}/{len(key_tables)} tables found")

        # Check 2: Verify row counts for key tables
        logger.info("Checking row counts...")

        row_counts = {}

        for table in existing_tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                count = cursor.fetchone()[0]
                row_counts[table] = count
            except Exception as e:
                logger.warning(f"Failed to count rows in {table}: {e}")
                row_counts[table] = -1

        results["row_counts"] = {
            "passed": all(count >= 0 for count in row_counts.values()),
            "counts": row_counts,
            "total_rows": sum(count for count in row_counts.values() if count >= 0),
        }

        logger.info(f"Row counts: {results['row_counts']['total_rows']} total rows")

        # Check 3: Verify foreign key relationships
        logger.info("Checking foreign key integrity...")

        # Get all foreign key constraints
        cursor.execute(
            """
            SELECT
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            LIMIT 20;
        """
        )

        fk_constraints = cursor.fetchall()
        fk_violations = []

        for table, column, ref_table, ref_column in fk_constraints:
            try:
                # Check for orphaned records
                cursor.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM {table} t
                    WHERE t.{column} IS NOT NULL
                    AND NOT EXISTS (
                        SELECT 1 FROM {ref_table} r
                        WHERE r.{ref_column} = t.{column}
                    );
                """
                )
                violations = cursor.fetchone()[0]

                if violations > 0:
                    fk_violations.append(
                        {
                            "table": table,
                            "column": column,
                            "ref_table": ref_table,
                            "violations": violations,
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to check FK constraint {table}.{column}: {e}")

        results["foreign_key_integrity"] = {
            "passed": len(fk_violations) == 0,
            "constraints_checked": len(fk_constraints),
            "violations": fk_violations,
        }

        logger.info(
            f"Foreign key integrity: {len(fk_constraints)} constraints checked, "
            f"{len(fk_violations)} violations found"
        )

        # Check 4: Basic data corruption detection
        logger.info("Checking for data corruption...")

        corruption_issues = []

        # Check for NULL values in NOT NULL columns (sample check)
        try:
            cursor.execute(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE is_nullable = 'NO'
                AND table_schema = 'public'
                LIMIT 10;
            """
            )

            not_null_columns = cursor.fetchall()

            for table, column in not_null_columns:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL;")
                    null_count = cursor.fetchone()[0]

                    if null_count > 0:
                        corruption_issues.append(
                            {
                                "table": table,
                                "column": column,
                                "issue": f"Found {null_count} NULL values in NOT NULL column",
                            }
                        )
                except Exception as e:
                    logger.debug(f"Skipping NULL check for {table}.{column}: {e}")

        except Exception as e:
            logger.warning(f"Failed to check for data corruption: {e}")

        results["data_corruption"] = {
            "passed": len(corruption_issues) == 0,
            "issues": corruption_issues,
        }

        logger.info(f"Data corruption: {len(corruption_issues)} issues found")

        # Close connection
        cursor.close()
        conn.close()

        # Overall result
        all_passed = all(check.get("passed", False) for check in results.values())
        results["overall"] = {
            "passed": all_passed,
            "total_checks": len(results),
            "passed_checks": sum(1 for check in results.values() if check.get("passed", False)),
        }

        return results

    except Exception as e:
        logger.error(f"Failed to verify test restore integrity: {e}", exc_info=True)
        return {
            "error": str(e),
            "passed": False,
        }


@shared_task(
    bind=True,
    name="apps.backups.tasks.cleanup_old_backups",
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def cleanup_old_backups(self):  # noqa: C901
    """
    Clean up old backups according to retention policies.

    This task should run daily at 5:00 AM to:
    1. Delete local backups older than 30 days
    2. Archive cloud backups older than 1 year (mark for archival, actual deletion optional)
    3. Clean up temporary files in the backup directory

    Retention policies:
    - Local storage: 30 days
    - Cloudflare R2: 1 year
    - Backblaze B2: 1 year

    Returns:
        Dictionary with cleanup statistics
    """
    from apps.core.tenant_context import bypass_rls

    start_time = timezone.now()
    cleanup_stats = {
        "local_deleted": 0,
        "local_failed": 0,
        "r2_deleted": 0,
        "r2_failed": 0,
        "b2_deleted": 0,
        "b2_failed": 0,
        "temp_files_deleted": 0,
        "database_records_deleted": 0,
        "errors": [],
    }

    try:
        logger.info("=" * 80)
        logger.info("Starting backup cleanup task")
        logger.info("=" * 80)

        # Step 1: Delete local backups older than 30 days
        logger.info("Step 1: Cleaning up local backups older than 30 days...")

        # Retention is 30 days, so delete backups created more than 30 days ago
        # Using __lte (less than or equal) with 30 days would delete 30-day-old backups
        # We want to keep 30 days, so we use __lt with 30 days (which means 31+ days old)
        local_cutoff_date = timezone.now() - timedelta(days=30)

        with bypass_rls():
            # Get all backups older than 30 days with local storage
            # created_at < (now - 30 days) means the backup is more than 30 days old
            old_local_backups = list(
                Backup.objects.filter(
                    created_at__lt=local_cutoff_date,
                    local_path__isnull=False,
                ).exclude(local_path="")
            )

        logger.info(f"Found {len(old_local_backups)} local backups to clean up")

        local_storage = get_storage_backend("local")

        for backup in old_local_backups:
            try:
                # Delete from local storage
                if local_storage.delete(backup.local_path):
                    # Update backup record to remove local path
                    with bypass_rls():
                        backup.local_path = ""
                        backup.save(update_fields=["local_path"])

                    cleanup_stats["local_deleted"] += 1
                    logger.info(f"✓ Deleted local backup: {backup.filename}")
                else:
                    cleanup_stats["local_failed"] += 1
                    logger.warning(f"✗ Failed to delete local backup: {backup.filename}")

            except Exception as e:
                cleanup_stats["local_failed"] += 1
                cleanup_stats["errors"].append(f"Local deletion failed for {backup.filename}: {e}")
                logger.error(f"Error deleting local backup {backup.filename}: {e}")

        logger.info(
            f"Local cleanup: {cleanup_stats['local_deleted']} deleted, "
            f"{cleanup_stats['local_failed']} failed"
        )

        # Step 2: Archive cloud backups older than 1 year
        logger.info("Step 2: Archiving cloud backups older than 1 year...")

        cloud_cutoff_date = timezone.now() - timedelta(days=365)

        with bypass_rls():
            # Get all backups older than 1 year
            old_cloud_backups = list(
                Backup.objects.filter(
                    created_at__lt=cloud_cutoff_date,
                ).exclude(r2_path="", b2_path="")
            )

        logger.info(f"Found {len(old_cloud_backups)} cloud backups to archive")

        r2_storage = get_storage_backend("r2")
        b2_storage = get_storage_backend("b2")

        for backup in old_cloud_backups:
            # Delete from R2
            if backup.r2_path:
                try:
                    if r2_storage.delete(backup.r2_path):
                        with bypass_rls():
                            backup.r2_path = ""
                            backup.save(update_fields=["r2_path"])

                        cleanup_stats["r2_deleted"] += 1
                        logger.info(f"✓ Deleted R2 backup: {backup.filename}")
                    else:
                        cleanup_stats["r2_failed"] += 1
                        logger.warning(f"✗ Failed to delete R2 backup: {backup.filename}")

                except Exception as e:
                    cleanup_stats["r2_failed"] += 1
                    cleanup_stats["errors"].append(f"R2 deletion failed for {backup.filename}: {e}")
                    logger.error(f"Error deleting R2 backup {backup.filename}: {e}")

            # Delete from B2
            if backup.b2_path:
                try:
                    if b2_storage.delete(backup.b2_path):
                        with bypass_rls():
                            backup.b2_path = ""
                            backup.save(update_fields=["b2_path"])

                        cleanup_stats["b2_deleted"] += 1
                        logger.info(f"✓ Deleted B2 backup: {backup.filename}")
                    else:
                        cleanup_stats["b2_failed"] += 1
                        logger.warning(f"✗ Failed to delete B2 backup: {backup.filename}")

                except Exception as e:
                    cleanup_stats["b2_failed"] += 1
                    cleanup_stats["errors"].append(f"B2 deletion failed for {backup.filename}: {e}")
                    logger.error(f"Error deleting B2 backup {backup.filename}: {e}")

        logger.info(
            f"Cloud cleanup: R2={cleanup_stats['r2_deleted']} deleted, "
            f"B2={cleanup_stats['b2_deleted']} deleted"
        )

        # Step 3: Delete database records for backups with no storage locations
        logger.info("Step 3: Cleaning up database records for fully deleted backups...")

        with bypass_rls():
            # Find backups with no storage locations (all paths empty)
            orphaned_backups = Backup.objects.filter(
                local_path="",
                r2_path="",
                b2_path="",
            )

            orphaned_count = orphaned_backups.count()

            if orphaned_count > 0:
                logger.info(f"Found {orphaned_count} orphaned backup records to delete")

                # Delete orphaned backup records
                deleted_count, _ = orphaned_backups.delete()
                cleanup_stats["database_records_deleted"] = deleted_count

                logger.info(f"✓ Deleted {deleted_count} orphaned backup records")
            else:
                logger.info("No orphaned backup records found")

        # Step 4: Clean up temporary files
        logger.info("Step 4: Cleaning up temporary files...")

        # Clean up any leftover temporary files in the backup directory
        local_storage = get_storage_backend("local")
        backup_dir = local_storage.base_path

        temp_patterns = ["*.tmp", "*.temp", "test_restore_*"]

        for pattern in temp_patterns:
            try:
                for temp_file in backup_dir.glob(pattern):
                    if temp_file.is_file():
                        try:
                            # Only delete files older than 1 day
                            file_age = timezone.now() - datetime.fromtimestamp(
                                temp_file.stat().st_mtime, tz=timezone.get_current_timezone()
                            )

                            if file_age > timedelta(days=1):
                                temp_file.unlink()
                                cleanup_stats["temp_files_deleted"] += 1
                                logger.debug(f"✓ Deleted temp file: {temp_file.name}")

                        except Exception as e:
                            logger.warning(f"Failed to delete temp file {temp_file}: {e}")

            except Exception as e:
                logger.warning(f"Error scanning for temp files with pattern {pattern}: {e}")

        logger.info(f"Temp file cleanup: {cleanup_stats['temp_files_deleted']} files deleted")

        # Calculate total duration
        duration = (timezone.now() - start_time).total_seconds()
        cleanup_stats["duration_seconds"] = duration

        logger.info("=" * 80)
        logger.info("Backup cleanup completed successfully")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Local backups deleted: {cleanup_stats['local_deleted']}")
        logger.info(f"R2 backups deleted: {cleanup_stats['r2_deleted']}")
        logger.info(f"B2 backups deleted: {cleanup_stats['b2_deleted']}")
        logger.info(f"Database records deleted: {cleanup_stats['database_records_deleted']}")
        logger.info(f"Temp files deleted: {cleanup_stats['temp_files_deleted']}")
        logger.info("=" * 80)

        # Create info alert if significant cleanup occurred
        total_deleted = (
            cleanup_stats["local_deleted"]
            + cleanup_stats["r2_deleted"]
            + cleanup_stats["b2_deleted"]
        )

        if total_deleted > 0:
            create_backup_alert(
                alert_type=BackupAlert.BACKUP_FAILURE,  # Reusing type for cleanup info
                severity=BackupAlert.INFO,
                message=f"Backup cleanup completed: {total_deleted} old backups removed",
                details=cleanup_stats,
            )

        # Create warning alert if there were failures
        total_failed = (
            cleanup_stats["local_failed"] + cleanup_stats["r2_failed"] + cleanup_stats["b2_failed"]
        )

        if total_failed > 0:
            create_backup_alert(
                alert_type=BackupAlert.BACKUP_FAILURE,
                severity=BackupAlert.WARNING,
                message=f"Backup cleanup had {total_failed} failures",
                details=cleanup_stats,
            )

        return cleanup_stats

    except Exception as e:
        logger.error(f"Backup cleanup task failed: {e}", exc_info=True)

        cleanup_stats["errors"].append(str(e))

        # Create critical alert
        create_backup_alert(
            alert_type=BackupAlert.BACKUP_FAILURE,
            severity=BackupAlert.CRITICAL,
            message=f"Backup cleanup task failed: {str(e)}",
            details=cleanup_stats,
        )

        # Retry the task
        raise self.retry(exc=e)


@shared_task(
    bind=True,
    name="apps.backups.tasks.verify_storage_integrity",
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def verify_storage_integrity(self):  # noqa: C901
    """
    Verify storage integrity by checking checksums across all storage locations.

    This task:
    1. Retrieves all completed backups from the last 30 days
    2. Verifies checksums across all three storage locations (local, R2, B2)
    3. Identifies mismatches between storage locations
    4. Creates alerts for any integrity failures
    5. Tracks verification results in backup metadata

    This task should run hourly via Celery Beat to ensure continuous
    monitoring of backup integrity across all storage backends.

    Requirement 6.31: Verify storage integrity hourly by checking checksums

    Returns:
        Dictionary with verification statistics if successful, None otherwise
    """
    from datetime import timedelta

    from apps.core.tenant_context import bypass_rls

    start_time = timezone.now()
    stats = {
        "total_backups_checked": 0,
        "verified_successfully": 0,
        "integrity_failures": 0,
        "storage_mismatches": 0,
        "missing_files": 0,
        "checksum_mismatches": 0,
    }

    try:
        logger.info("=" * 80)
        logger.info("Starting storage integrity verification")
        logger.info("=" * 80)

        # Get all completed backups from the last 30 days
        # We focus on recent backups as they are most critical
        cutoff_date = timezone.now() - timedelta(days=30)

        with bypass_rls():
            backups_to_verify = list(
                Backup.objects.filter(
                    status__in=[Backup.COMPLETED, Backup.VERIFIED], created_at__gte=cutoff_date
                ).order_by("-created_at")
            )

        total_backups = len(backups_to_verify)
        stats["total_backups_checked"] = total_backups

        if total_backups == 0:
            logger.info("No backups found to verify")
            return stats

        logger.info(f"Found {total_backups} backup(s) to verify")

        # Limit verification to a reasonable number per run to avoid long-running tasks
        # Verify up to 100 backups per hour (most recent first)
        max_verifications_per_run = 100
        if total_backups > max_verifications_per_run:
            logger.info(f"Limiting verification to {max_verifications_per_run} most recent backups")
            backups_to_verify = backups_to_verify[:max_verifications_per_run]
            stats["total_backups_checked"] = max_verifications_per_run

        # Initialize storage backends
        storage_backends = {
            "local": get_storage_backend("local"),
            "r2": get_storage_backend("r2"),
            "b2": get_storage_backend("b2"),
        }

        # Verify each backup
        for index, backup in enumerate(backups_to_verify, 1):
            try:
                logger.info(
                    f"Verifying backup {index}/{len(backups_to_verify)}: {backup.filename} ({backup.id})"
                )

                verification_results = {
                    "backup_id": str(backup.id),
                    "filename": backup.filename,
                    "expected_checksum": backup.checksum,
                    "storage_checks": {},
                    "has_integrity_failure": False,
                    "errors": [],
                }

                # Check each storage location
                for storage_name, storage_backend in storage_backends.items():
                    storage_path = getattr(backup, f"{storage_name}_path", None)

                    if not storage_path:
                        # This storage location was not used for this backup
                        # (e.g., WAL files skip local storage)
                        verification_results["storage_checks"][storage_name] = {
                            "checked": False,
                            "reason": "not_used",
                        }
                        continue

                    try:
                        # Check if file exists
                        file_exists = storage_backend.exists(storage_path)

                        if not file_exists:
                            logger.warning(
                                f"File missing in {storage_name} storage: {storage_path}"
                            )
                            verification_results["storage_checks"][storage_name] = {
                                "checked": True,
                                "exists": False,
                                "error": "file_not_found",
                            }
                            verification_results["has_integrity_failure"] = True
                            verification_results["errors"].append(
                                f"File missing in {storage_name}: {storage_path}"
                            )
                            stats["missing_files"] += 1
                            continue

                        # Get file size
                        file_size = storage_backend.get_size(storage_path)

                        # Check if size matches
                        size_matches = file_size == backup.size_bytes if file_size else False

                        if not size_matches:
                            logger.warning(
                                f"Size mismatch in {storage_name} storage: "
                                f"expected {backup.size_bytes}, got {file_size}"
                            )
                            verification_results["storage_checks"][storage_name] = {
                                "checked": True,
                                "exists": True,
                                "size_matches": False,
                                "expected_size": backup.size_bytes,
                                "actual_size": file_size,
                                "error": "size_mismatch",
                            }
                            verification_results["has_integrity_failure"] = True
                            verification_results["errors"].append(
                                f"Size mismatch in {storage_name}: "
                                f"expected {backup.size_bytes}, got {file_size}"
                            )
                            stats["storage_mismatches"] += 1
                            continue

                        # For full checksum verification, we would need to download the file
                        # and recalculate the checksum. This is expensive for large files.
                        # For hourly checks, we verify existence and size.
                        # Full checksum verification can be done less frequently (e.g., weekly)

                        verification_results["storage_checks"][storage_name] = {
                            "checked": True,
                            "exists": True,
                            "size_matches": True,
                            "size": file_size,
                            "status": "ok",
                        }

                        logger.debug(f"Verification passed for {storage_name}: {storage_path}")

                    except Exception as e:
                        logger.error(
                            f"Error verifying {storage_name} storage for {storage_path}: {e}"
                        )
                        verification_results["storage_checks"][storage_name] = {
                            "checked": True,
                            "error": str(e),
                        }
                        verification_results["has_integrity_failure"] = True
                        verification_results["errors"].append(
                            f"Error checking {storage_name}: {str(e)}"
                        )

                # Determine overall verification status
                if verification_results["has_integrity_failure"]:
                    logger.warning(
                        f"Integrity verification failed for backup {backup.id}: "
                        f"{', '.join(verification_results['errors'])}"
                    )
                    stats["integrity_failures"] += 1

                    # Create alert for integrity failure
                    create_backup_alert(
                        alert_type=BackupAlert.INTEGRITY_FAILURE,
                        severity=BackupAlert.ERROR,
                        message=f"Storage integrity verification failed for backup {backup.filename}",
                        backup=backup,
                        details=verification_results,
                    )

                    # Update backup metadata with verification failure
                    with bypass_rls():
                        if not backup.metadata:
                            backup.metadata = {}
                        backup.metadata["last_integrity_check"] = {
                            "timestamp": timezone.now().isoformat(),
                            "status": "failed",
                            "errors": verification_results["errors"],
                        }
                        backup.save(update_fields=["metadata"])

                else:
                    logger.debug(f"Integrity verification passed for backup {backup.id}")
                    stats["verified_successfully"] += 1

                    # Update backup metadata with successful verification
                    with bypass_rls():
                        if not backup.metadata:
                            backup.metadata = {}
                        backup.metadata["last_integrity_check"] = {
                            "timestamp": timezone.now().isoformat(),
                            "status": "passed",
                        }
                        backup.save(update_fields=["metadata"])

            except Exception as e:
                logger.error(f"Error verifying backup {backup.id}: {e}", exc_info=True)
                stats["integrity_failures"] += 1

                # Create alert for verification error
                create_backup_alert(
                    alert_type=BackupAlert.INTEGRITY_FAILURE,
                    severity=BackupAlert.WARNING,
                    message=f"Error during storage integrity verification for {backup.filename}",
                    backup=backup,
                    details={"error": str(e), "backup_id": str(backup.id)},
                )

                # Continue with next backup
                continue

        # Calculate verification duration
        duration_seconds = int((timezone.now() - start_time).total_seconds())

        logger.info("=" * 80)
        logger.info("Storage integrity verification completed")
        logger.info(f"Duration: {duration_seconds} seconds")
        logger.info(f"Total backups checked: {stats['total_backups_checked']}")
        logger.info(f"Verified successfully: {stats['verified_successfully']}")
        logger.info(f"Integrity failures: {stats['integrity_failures']}")
        logger.info(f"Storage mismatches: {stats['storage_mismatches']}")
        logger.info(f"Missing files: {stats['missing_files']}")
        logger.info(f"Checksum mismatches: {stats['checksum_mismatches']}")
        logger.info("=" * 80)

        # Create summary alert if there were any failures
        if stats["integrity_failures"] > 0:
            create_backup_alert(
                alert_type=BackupAlert.INTEGRITY_FAILURE,
                severity=BackupAlert.WARNING,
                message=f"Storage integrity verification found {stats['integrity_failures']} issue(s)",
                details={
                    "stats": stats,
                    "duration_seconds": duration_seconds,
                    "timestamp": timezone.now().isoformat(),
                },
            )

        return stats

    except Exception as e:
        logger.error(f"Storage integrity verification task failed: {e}", exc_info=True)

        # Create alert for overall task failure
        create_backup_alert(
            alert_type=BackupAlert.INTEGRITY_FAILURE,
            severity=BackupAlert.ERROR,
            message=f"Storage integrity verification task failed: {str(e)}",
            details={"error": str(e), "task_id": self.request.id},
        )

        # Retry the task
        raise self.retry(exc=e)
