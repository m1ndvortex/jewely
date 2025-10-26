"""
Tests for backup management interface (Task 18.10).

This module tests:
- Backup dashboard
- Manual backup trigger form
- 4-step restore wizard
- Backup history table with filters
- DR runbook execution interface
"""

import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

import pytest

from apps.backups.models import Backup, BackupAlert
from apps.core.models import Tenant

User = get_user_model()


@pytest.mark.django_db
class TestBackupDashboard(TestCase):
    """Test backup dashboard view."""

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
            status="ACTIVE",
        )

        # Create test backups
        self.backup1 = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename="backup_full_20251026.dump.gz.enc",
            size_bytes=1024 * 1024 * 100,  # 100 MB
            checksum="abc123",
            r2_path="r2://backups/backup_full_20251026.dump.gz.enc",
            b2_path="b2://backups/backup_full_20251026.dump.gz.enc",
            status=Backup.COMPLETED,
        )

        self.backup2 = Backup.objects.create(
            backup_type=Backup.TENANT_BACKUP,
            tenant=self.tenant,
            filename="backup_tenant_test_20251026.dump.gz.enc",
            size_bytes=1024 * 1024 * 50,  # 50 MB
            checksum="def456",
            r2_path="r2://backups/backup_tenant_test_20251026.dump.gz.enc",
            b2_path="b2://backups/backup_tenant_test_20251026.dump.gz.enc",
            status=Backup.COMPLETED,
        )

        # Create test alert
        self.alert = BackupAlert.objects.create(
            alert_type=BackupAlert.BACKUP_FAILURE,
            severity=BackupAlert.CRITICAL,
            backup=self.backup1,
            message="Backup failed due to network error",
            status=BackupAlert.ACTIVE,
        )

        self.client = Client()

    def test_dashboard_requires_authentication(self):
        """Test that dashboard requires authentication."""
        response = self.client.get(reverse("backups:dashboard"))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_dashboard_requires_platform_admin(self):
        """Test that dashboard requires platform admin role."""
        # Create non-admin user
        User.objects.create_user(
            username="regular",
            email="regular@example.com",
            password="testpass123",
            role="TENANT_OWNER",
            tenant=self.tenant,
        )

        self.client.login(username="regular", password="testpass123")
        response = self.client.get(reverse("backups:dashboard"))
        self.assertEqual(response.status_code, 302)  # Redirect (access denied)

    def test_dashboard_displays_statistics(self):
        """Test that dashboard displays backup statistics."""
        self.client.login(username="admin", password="testpass123")
        response = self.client.get(reverse("backups:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("stats", response.context)
        self.assertIn("recent_backups", response.context)
        self.assertIn("active_alerts", response.context)
        self.assertIn("health_score", response.context)

    def test_dashboard_shows_recent_backups(self):
        """Test that dashboard shows recent backups."""
        self.client.login(username="admin", password="testpass123")
        response = self.client.get(reverse("backups:dashboard"))

        recent_backups = response.context["recent_backups"]
        self.assertGreaterEqual(len(recent_backups), 2)

    def test_dashboard_shows_active_alerts(self):
        """Test that dashboard shows active alerts."""
        self.client.login(username="admin", password="testpass123")
        response = self.client.get(reverse("backups:dashboard"))

        active_alerts = response.context["active_alerts"]
        self.assertEqual(len(active_alerts), 1)
        self.assertEqual(active_alerts[0].id, self.alert.id)


@pytest.mark.django_db
class TestBackupList(TestCase):
    """Test backup list view with filters."""

    def setUp(self):
        """Set up test data."""
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop",
            status="ACTIVE",
        )

        # Create multiple backups
        for i in range(30):
            Backup.objects.create(
                backup_type=Backup.FULL_DATABASE if i % 2 == 0 else Backup.TENANT_BACKUP,
                tenant=self.tenant if i % 2 == 1 else None,
                filename=f"backup_{i}.dump.gz.enc",
                size_bytes=1024 * 1024 * (i + 1),
                checksum=f"checksum_{i}",
                r2_path=f"r2://backups/backup_{i}.dump.gz.enc",
                b2_path=f"b2://backups/backup_{i}.dump.gz.enc",
                status=Backup.COMPLETED if i % 3 != 0 else Backup.FAILED,
            )

        self.client = Client()
        self.client.login(username="admin", password="testpass123")

    def test_backup_list_displays_backups(self):
        """Test that backup list displays backups."""
        response = self.client.get(reverse("backups:backup_list"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("backups", response.context)
        self.assertIn("page_obj", response.context)

    def test_backup_list_pagination(self):
        """Test that backup list has pagination."""
        response = self.client.get(reverse("backups:backup_list"))

        page_obj = response.context["page_obj"]
        self.assertTrue(page_obj.has_other_pages())
        self.assertEqual(len(page_obj.object_list), 25)  # 25 per page

    def test_backup_list_filter_by_type(self):
        """Test filtering backups by type."""
        response = self.client.get(
            reverse("backups:backup_list"), {"backup_type": Backup.FULL_DATABASE}
        )

        backups = response.context["backups"]
        for backup in backups:
            self.assertEqual(backup.backup_type, Backup.FULL_DATABASE)

    def test_backup_list_filter_by_status(self):
        """Test filtering backups by status."""
        response = self.client.get(reverse("backups:backup_list"), {"status": Backup.FAILED})

        backups = response.context["backups"]
        for backup in backups:
            self.assertEqual(backup.status, Backup.FAILED)

    def test_backup_list_filter_by_tenant(self):
        """Test filtering backups by tenant."""
        response = self.client.get(reverse("backups:backup_list"), {"tenant": str(self.tenant.id)})

        backups = response.context["backups"]
        for backup in backups:
            if backup.tenant:
                self.assertEqual(backup.tenant.id, self.tenant.id)


@pytest.mark.django_db
class TestBackupDetail(TestCase):
    """Test backup detail view."""

    def setUp(self):
        """Set up test data."""
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        self.backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename="backup_full_20251026.dump.gz.enc",
            size_bytes=1024 * 1024 * 100,
            checksum="abc123",
            r2_path="r2://backups/backup_full_20251026.dump.gz.enc",
            b2_path="b2://backups/backup_full_20251026.dump.gz.enc",
            status=Backup.COMPLETED,
            backup_duration_seconds=300,
            compression_ratio=0.7,
        )

        self.client = Client()
        self.client.login(username="admin", password="testpass123")

    def test_backup_detail_displays_information(self):
        """Test that backup detail displays all information."""
        response = self.client.get(reverse("backups:backup_detail", args=[self.backup.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["backup"].id, self.backup.id)
        self.assertContains(response, self.backup.filename)
        self.assertContains(response, "100")  # Size in MB


@pytest.mark.django_db
class TestManualBackup(TestCase):
    """Test manual backup trigger form."""

    def setUp(self):
        """Set up test data."""
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop",
            status="ACTIVE",
        )

        self.client = Client()
        self.client.login(username="admin", password="testpass123")

    def test_manual_backup_form_displays(self):
        """Test that manual backup form displays."""
        response = self.client.get(reverse("backups:manual_backup"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertContains(response, "Backup Scope")
        self.assertContains(response, "Execution Timing")

    @patch("apps.backups.views.BackupService.trigger_manual_backup")
    def test_manual_backup_submission(self, mock_trigger):
        """Test manual backup form submission."""
        mock_trigger.return_value = {
            "success": True,
            "backup_jobs": [{"job_id": "test-job-1"}],
        }

        response = self.client.post(
            reverse("backups:manual_backup"),
            {
                "backup_scope": "all",
                "execution_timing": "immediate",
                "include_configuration": True,
                "notes": "Test backup",
            },
        )

        self.assertEqual(response.status_code, 302)  # Redirect after success
        mock_trigger.assert_called_once()


@pytest.mark.django_db
class TestRestoreWizard(TestCase):
    """Test 4-step restore wizard."""

    def setUp(self):
        """Set up test data."""
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        self.backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename="backup_full_20251026.dump.gz.enc",
            size_bytes=1024 * 1024 * 100,
            checksum="abc123",
            r2_path="r2://backups/backup_full_20251026.dump.gz.enc",
            b2_path="b2://backups/backup_full_20251026.dump.gz.enc",
            status=Backup.COMPLETED,
        )

        self.client = Client()
        self.client.login(username="admin", password="testpass123")

    def test_restore_wizard_displays(self):
        """Test that restore wizard displays."""
        response = self.client.get(reverse("backups:restore_backup"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertContains(response, "Restore Wizard")
        self.assertContains(response, "4-step process")

    def test_restore_wizard_with_backup_id(self):
        """Test restore wizard with pre-selected backup."""
        response = self.client.get(reverse("backups:restore_backup_with_id", args=[self.backup.id]))

        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)

    @patch("apps.backups.views.BackupService.trigger_restore")
    def test_restore_wizard_submission(self, mock_trigger):
        """Test restore wizard form submission."""
        mock_trigger.return_value = {
            "success": True,
            "restore_log_id": str(uuid.uuid4()),
        }

        response = self.client.post(
            reverse("backups:restore_backup"),
            {
                "backup": str(self.backup.id),
                "restore_mode": "FULL",
                "selective_restore": False,
                "reason": "Test restore",
            },
        )

        self.assertEqual(response.status_code, 302)  # Redirect after success
        mock_trigger.assert_called_once()


@pytest.mark.django_db
class TestDisasterRecoveryRunbook(TestCase):
    """Test DR runbook execution interface."""

    def setUp(self):
        """Set up test data."""
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        self.backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename="backup_full_20251026.dump.gz.enc",
            size_bytes=1024 * 1024 * 100,
            checksum="abc123",
            r2_path="r2://backups/backup_full_20251026.dump.gz.enc",
            b2_path="b2://backups/backup_full_20251026.dump.gz.enc",
            status=Backup.COMPLETED,
        )

        self.client = Client()
        self.client.login(username="admin", password="testpass123")

    def test_dr_runbook_displays(self):
        """Test that DR runbook interface displays."""
        response = self.client.get(reverse("backups:disaster_recovery_runbook"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("latest_backup", response.context)
        self.assertIn("available_backups", response.context)
        self.assertContains(response, "Disaster Recovery")

    @patch("apps.backups.views.BackupService.execute_disaster_recovery")
    def test_dr_runbook_execution(self, mock_execute):
        """Test DR runbook execution."""
        mock_execute.return_value = {
            "success": True,
            "task_id": "test-task-id",
        }

        response = self.client.post(
            reverse("backups:disaster_recovery_runbook"),
            {
                "backup_id": str(self.backup.id),
                "reason": "Testing disaster recovery",
            },
        )

        self.assertEqual(response.status_code, 302)  # Redirect after success
        mock_execute.assert_called_once()


@pytest.mark.django_db
class TestAlertManagement(TestCase):
    """Test alert list and management."""

    def setUp(self):
        """Set up test data."""
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        self.backup = Backup.objects.create(
            backup_type=Backup.FULL_DATABASE,
            filename="backup_full_20251026.dump.gz.enc",
            size_bytes=1024 * 1024 * 100,
            checksum="abc123",
            r2_path="r2://backups/backup_full_20251026.dump.gz.enc",
            b2_path="b2://backups/backup_full_20251026.dump.gz.enc",
            status=Backup.FAILED,
        )

        self.alert = BackupAlert.objects.create(
            alert_type=BackupAlert.BACKUP_FAILURE,
            severity=BackupAlert.CRITICAL,
            backup=self.backup,
            message="Backup failed due to network error",
            status=BackupAlert.ACTIVE,
        )

        self.client = Client()
        self.client.login(username="admin", password="testpass123")

    def test_alert_list_displays(self):
        """Test that alert list displays."""
        response = self.client.get(reverse("backups:alert_list"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("alerts", response.context)
        self.assertContains(response, "Backup failed")

    def test_acknowledge_alert(self):
        """Test acknowledging an alert."""
        response = self.client.post(reverse("backups:acknowledge_alert", args=[self.alert.id]))

        self.assertEqual(response.status_code, 302)  # Redirect after success

        # Verify alert was acknowledged
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, BackupAlert.ACKNOWLEDGED)
        self.assertIsNotNone(self.alert.acknowledged_at)
        self.assertEqual(self.alert.acknowledged_by, self.admin_user)

    def test_resolve_alert(self):
        """Test resolving an alert."""
        response = self.client.post(
            reverse("backups:resolve_alert", args=[self.alert.id]),
            {"resolution_notes": "Fixed network issue"},
        )

        self.assertEqual(response.status_code, 302)  # Redirect after success

        # Verify alert was resolved
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, BackupAlert.RESOLVED)
        self.assertIsNotNone(self.alert.resolved_at)
        self.assertEqual(self.alert.resolved_by, self.admin_user)
        self.assertEqual(self.alert.resolution_notes, "Fixed network issue")
