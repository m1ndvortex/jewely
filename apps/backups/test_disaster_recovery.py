"""
Tests for disaster recovery runbook.

This module tests the automated disaster recovery functionality including:
- DR runbook execution
- Backup download with failover
- Database restore
- Application restart
- Health check verification
"""

from unittest.mock import Mock, patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.utils import timezone

import pytest

from apps.core.models import Tenant

from .models import Backup, BackupRestoreLog
from .services import BackupService
from .tasks import execute_disaster_recovery_runbook

User = get_user_model()


@pytest.mark.django_db
class TestDisasterRecoveryRunbook(TransactionTestCase):
    """Test disaster recovery runbook execution."""

    def setUp(self):
        """Set up test data."""
        # Create platform admin user
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        # Create test tenant
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        # Create test backup
        self.backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename="backup_full_database_20250126_120000.dump.gz.enc",
            size_bytes=1024 * 1024 * 100,  # 100 MB
            checksum="a" * 64,
            local_path="/backups/local/backup_full_database_20250126_120000.dump.gz.enc",
            r2_path="backups/backup_full_database_20250126_120000.dump.gz.enc",
            b2_path="backups/backup_full_database_20250126_120000.dump.gz.enc",
            status=Backup.COMPLETED,
            compression_ratio=0.3,
            backup_duration_seconds=300,
        )

    @patch("apps.backups.tasks.get_storage_backend")
    @patch("apps.backups.tasks.decrypt_and_decompress_file")
    @patch("apps.backups.tasks.perform_pg_restore")
    @patch("apps.backups.tasks.subprocess.run")
    @patch("apps.backups.tasks.requests.get")
    def test_dr_runbook_success_with_r2(
        self,
        mock_requests_get,
        mock_subprocess_run,
        mock_pg_restore,
        mock_decrypt,
        mock_storage_backend,
    ):
        """Test successful DR runbook execution with R2 download."""
        # Mock storage backend download
        mock_r2_storage = Mock()
        mock_r2_storage.download.return_value = True
        mock_storage_backend.return_value = mock_r2_storage

        # Mock pg_restore success
        mock_pg_restore.return_value = (True, None)

        # Mock subprocess (kubectl/docker-compose)
        mock_subprocess_run.return_value = Mock(returncode=0, stderr="")

        # Mock health check
        mock_response = Mock()
        mock_response.status_code = 200
        mock_requests_get.return_value = mock_response

        # Execute DR runbook
        result = execute_disaster_recovery_runbook(
            backup_id=str(self.backup.id),
            reason="Test disaster recovery",
        )

        # Verify result
        assert result["success"] is True
        assert result["duration_seconds"] > 0
        assert len(result["steps"]) == 7

        # Verify all steps completed
        for step in result["steps"]:
            assert step["status"] in ["completed", "manual_required"]

        # Verify download was from R2
        download_step = result["steps"][1]
        assert download_step["source"] == "r2"

        # Verify restore log was created
        restore_log = BackupRestoreLog.objects.get(id=result["restore_log_id"])
        assert restore_log.status == BackupRestoreLog.COMPLETED
        assert restore_log.backup == self.backup
        assert restore_log.restore_mode == BackupRestoreLog.FULL

    @patch("apps.backups.tasks.get_storage_backend")
    @patch("apps.backups.tasks.decrypt_and_decompress_file")
    @patch("apps.backups.tasks.perform_pg_restore")
    @patch("apps.backups.tasks.subprocess.run")
    @patch("apps.backups.tasks.requests.get")
    def test_dr_runbook_failover_to_b2(
        self,
        mock_requests_get,
        mock_subprocess_run,
        mock_pg_restore,
        mock_decrypt,
        mock_storage_backend,
    ):
        """Test DR runbook with R2 failure and B2 failover."""

        def storage_backend_side_effect(backend_type):
            if backend_type == "r2":
                # R2 fails
                mock_r2 = Mock()
                mock_r2.download.side_effect = Exception("R2 connection failed")
                return mock_r2
            elif backend_type == "b2":
                # B2 succeeds
                mock_b2 = Mock()
                mock_b2.download.return_value = True
                return mock_b2
            return Mock()

        mock_storage_backend.side_effect = storage_backend_side_effect

        # Mock pg_restore success
        mock_pg_restore.return_value = (True, None)

        # Mock subprocess
        mock_subprocess_run.return_value = Mock(returncode=0, stderr="")

        # Mock health check
        mock_response = Mock()
        mock_response.status_code = 200
        mock_requests_get.return_value = mock_response

        # Execute DR runbook
        result = execute_disaster_recovery_runbook(
            backup_id=str(self.backup.id),
            reason="Test B2 failover",
        )

        # Verify result
        assert result["success"] is True

        # Verify download was from B2 (failover)
        download_step = result["steps"][1]
        assert download_step["source"] == "b2"

    @patch("apps.backups.tasks.get_storage_backend")
    def test_dr_runbook_all_storage_failed(self, mock_storage_backend):
        """Test DR runbook when all storage backends fail."""
        # Mock all storage backends to fail
        mock_storage = Mock()
        mock_storage.download.side_effect = Exception("Storage unavailable")
        mock_storage_backend.return_value = mock_storage

        # Execute DR runbook - should fail
        with pytest.raises(Exception) as exc_info:
            execute_disaster_recovery_runbook(
                backup_id=str(self.backup.id),
                reason="Test storage failure",
            )

        assert "Failed to download backup from any storage location" in str(exc_info.value)

        # Verify restore log was created and marked as failed
        restore_log = BackupRestoreLog.objects.filter(backup=self.backup).first()
        assert restore_log is not None
        assert restore_log.status == BackupRestoreLog.FAILED

    @patch("apps.backups.tasks.get_storage_backend")
    @patch("apps.backups.tasks.decrypt_and_decompress_file")
    @patch("apps.backups.tasks.perform_pg_restore")
    def test_dr_runbook_restore_failure(self, mock_pg_restore, mock_decrypt, mock_storage_backend):
        """Test DR runbook when database restore fails."""
        # Mock storage backend download
        mock_storage = Mock()
        mock_storage.download.return_value = True
        mock_storage_backend.return_value = mock_storage

        # Mock pg_restore failure
        mock_pg_restore.return_value = (False, "Database restore failed: connection error")

        # Execute DR runbook - should fail
        with pytest.raises(Exception) as exc_info:
            execute_disaster_recovery_runbook(
                backup_id=str(self.backup.id),
                reason="Test restore failure",
            )

        assert "Database restore failed" in str(exc_info.value)

    def test_dr_runbook_uses_latest_backup(self):
        """Test DR runbook uses latest backup when no backup_id specified."""
        # Create multiple backups
        Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename="backup_old.dump.gz.enc",
            size_bytes=1024 * 1024 * 50,
            checksum="b" * 64,
            r2_path="backups/backup_old.dump.gz.enc",
            b2_path="backups/backup_old.dump.gz.enc",
            status=Backup.COMPLETED,
            created_at=timezone.now() - timezone.timedelta(days=1),
        )

        with (
            patch("apps.backups.tasks.get_storage_backend"),
            patch("apps.backups.tasks.decrypt_and_decompress_file"),
            patch("apps.backups.tasks.perform_pg_restore") as mock_pg_restore,
            patch("apps.backups.tasks.subprocess.run"),
            patch("apps.backups.tasks.requests.get") as mock_requests_get,
        ):

            mock_pg_restore.return_value = (True, None)
            mock_response = Mock()
            mock_response.status_code = 200
            mock_requests_get.return_value = mock_response

            # Execute DR runbook without backup_id
            result = execute_disaster_recovery_runbook(
                backup_id=None,  # Should use latest
                reason="Test latest backup selection",
            )

            # Verify it used the latest backup (self.backup, not older_backup)
            restore_log = BackupRestoreLog.objects.get(id=result["restore_log_id"])
            assert restore_log.backup == self.backup

    def test_dr_service_method(self):
        """Test BackupService.execute_disaster_recovery method."""
        with patch("apps.backups.services.execute_disaster_recovery_runbook") as mock_task:
            mock_task.delay.return_value = Mock(id="test-task-id")

            result = BackupService.execute_disaster_recovery(
                backup_id=self.backup.id,
                reason="Test service method",
                user=self.admin_user,
            )

            assert result["success"] is True
            assert result["task_id"] == "test-task-id"
            assert result["status"] == "queued"

            # Verify task was called with correct arguments
            mock_task.delay.assert_called_once_with(
                backup_id=str(self.backup.id),
                reason="Test service method",
            )

    @patch("apps.backups.tasks.get_storage_backend")
    @patch("apps.backups.tasks.decrypt_and_decompress_file")
    @patch("apps.backups.tasks.perform_pg_restore")
    @patch("apps.backups.tasks.subprocess.run")
    @patch("apps.backups.tasks.requests.get")
    def test_dr_runbook_rto_tracking(
        self,
        mock_requests_get,
        mock_subprocess_run,
        mock_pg_restore,
        mock_decrypt,
        mock_storage_backend,
    ):
        """Test that DR runbook tracks RTO (Recovery Time Objective)."""
        # Mock all dependencies
        mock_storage = Mock()
        mock_storage.download.return_value = True
        mock_storage_backend.return_value = mock_storage
        mock_pg_restore.return_value = (True, None)
        mock_subprocess_run.return_value = Mock(returncode=0, stderr="")
        mock_response = Mock()
        mock_response.status_code = 200
        mock_requests_get.return_value = mock_response

        # Execute DR runbook
        result = execute_disaster_recovery_runbook(
            backup_id=str(self.backup.id),
            reason="Test RTO tracking",
        )

        # Verify RTO tracking
        assert "duration_seconds" in result
        assert result["duration_seconds"] > 0

        # Verify each step has duration tracking
        for step in result["steps"]:
            assert "duration_seconds" in step
            assert step["duration_seconds"] >= 0

        # Verify total duration is sum of steps (approximately)
        total_step_duration = sum(step["duration_seconds"] for step in result["steps"])
        assert abs(result["duration_seconds"] - total_step_duration) < 5  # Allow 5 second variance

    def test_dr_runbook_invalid_backup(self):
        """Test DR runbook with invalid backup ID."""
        with pytest.raises(Exception) as exc_info:
            execute_disaster_recovery_runbook(
                backup_id=str(uuid4()),  # Non-existent backup
                reason="Test invalid backup",
            )

        # Should fail during backup selection
        assert "does not exist" in str(exc_info.value).lower()
