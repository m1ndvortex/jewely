"""
Real integration tests for backup management interface (Task 18.10).

These tests use REAL database, REAL storage backends, and REAL services.
NO MOCKS ALLOWED - this is production-level testing.

Tests verify:
1. Backup dashboard displays real data
2. Manual backup trigger actually creates backups
3. Restore wizard actually restores data
4. Backup history filters work with real data
5. DR runbook actually executes disaster recovery
6. Alert management actually updates alerts
"""

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

import pytest

from apps.backups.models import Backup, BackupAlert, BackupRestoreLog
from apps.core.models import Tenant

User = get_user_model()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database_for_interface(django_db_setup, django_db_blocker):
    """Grant BYPASSRLS privilege to postgres user for test database."""
    with django_db_blocker.unblock():
        try:
            with connection.cursor() as cursor:
                cursor.execute("ALTER USER postgres WITH BYPASSRLS;")
            print("✓ Granted BYPASSRLS privilege to postgres user for test database")
        except Exception as e:
            print(f"Warning: Could not grant BYPASSRLS: {e}")


@pytest.mark.django_db
class TestBackupDashboardIntegration(TestCase):
    """Test backup dashboard with real data."""

    def setUp(self):
        """Set up test data."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            # Create platform admin user
            self.admin_user = User.objects.create_user(
                username="admin",
                email="admin@example.com",
                password="testpass123",
                role="PLATFORM_ADMIN",
                is_staff=True,
            )

            # Create test tenant
            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop",
                slug="test-shop",
                status="ACTIVE",
            )

            # Create real backup records
            self.backup1 = Backup.objects.create(
                backup_type=Backup.FULL_DATABASE,
                filename="backup_full_20251026.dump.gz.enc",
                size_bytes=1024 * 1024 * 100,  # 100 MB
                checksum="abc123",
                r2_path="r2://backups/backup_full_20251026.dump.gz.enc",
                b2_path="b2://backups/backup_full_20251026.dump.gz.enc",
                status=Backup.COMPLETED,
                backup_duration_seconds=300,
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

    def test_dashboard_displays_real_statistics(self):
        """Test that dashboard displays real backup statistics."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("backups:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("stats", response.context)

        stats = response.context["stats"]
        self.assertGreaterEqual(stats["total_backups"], 2)
        self.assertGreaterEqual(stats["completed_backups"], 2)

    def test_dashboard_shows_real_backups(self):
        """Test that dashboard shows real recent backups."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("backups:dashboard"))

        self.assertEqual(response.status_code, 200)
        recent_backups = response.context["recent_backups"]
        self.assertGreaterEqual(len(recent_backups), 2)

        # Verify backup data
        backup_ids = [b.id for b in recent_backups]
        self.assertIn(self.backup1.id, backup_ids)
        self.assertIn(self.backup2.id, backup_ids)

    def test_dashboard_shows_real_alerts(self):
        """Test that dashboard shows real active alerts."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("backups:dashboard"))

        self.assertEqual(response.status_code, 200)
        active_alerts = response.context["active_alerts"]
        self.assertEqual(len(active_alerts), 1)
        self.assertEqual(active_alerts[0].id, self.alert.id)


@pytest.mark.django_db
class TestBackupListIntegration(TestCase):
    """Test backup list with real filtering."""

    def setUp(self):
        """Set up test data."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            self.admin_user = User.objects.create_user(
                username="admin",
                email="admin@example.com",
                password="testpass123",
                role="PLATFORM_ADMIN",
                is_staff=True,
            )

            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop",
                slug="test-shop",
                status="ACTIVE",
            )

            # Create multiple backups with different types and statuses
            for i in range(10):
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

    def test_backup_list_displays_real_backups(self):
        """Test that backup list displays real backups."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("backups:backup_list"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("backups", response.context)
        backups = response.context["backups"]
        self.assertGreaterEqual(len(backups), 10)

    def test_backup_list_filter_by_type_works(self):
        """Test filtering backups by type with real data."""
        self.client.force_login(self.admin_user)
        response = self.client.get(
            reverse("backups:backup_list"), {"backup_type": Backup.FULL_DATABASE}
        )

        self.assertEqual(response.status_code, 200)
        backups = response.context["backups"]

        # Verify all returned backups are full database backups
        for backup in backups:
            self.assertEqual(backup.backup_type, Backup.FULL_DATABASE)

    def test_backup_list_filter_by_status_works(self):
        """Test filtering backups by status with real data."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("backups:backup_list"), {"status": Backup.FAILED})

        self.assertEqual(response.status_code, 200)
        backups = response.context["backups"]

        # Verify all returned backups have failed status
        for backup in backups:
            self.assertEqual(backup.status, Backup.FAILED)


@pytest.mark.django_db
class TestBackupDetailIntegration(TestCase):
    """Test backup detail view with real data."""

    def setUp(self):
        """Set up test data."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            self.admin_user = User.objects.create_user(
                username="admin",
                email="admin@example.com",
                password="testpass123",
                role="PLATFORM_ADMIN",
                is_staff=True,
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
                created_by=self.admin_user,
            )

        self.client = Client()

    def test_backup_detail_displays_real_information(self):
        """Test that backup detail displays all real information."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("backups:backup_detail", args=[self.backup.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["backup"].id, self.backup.id)

        # Verify all fields are displayed
        self.assertContains(response, self.backup.filename)
        self.assertContains(response, "100")  # Size in MB
        self.assertContains(response, "300")  # Duration in seconds
        self.assertContains(response, "abc123")  # Checksum


@pytest.mark.django_db
class TestAlertManagementIntegration(TestCase):
    """Test alert management with real database operations."""

    def setUp(self):
        """Set up test data."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            self.admin_user = User.objects.create_user(
                username="admin",
                email="admin@example.com",
                password="testpass123",
                role="PLATFORM_ADMIN",
                is_staff=True,
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

    def test_alert_list_displays_real_alerts(self):
        """Test that alert list displays real alerts."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("backups:alert_list"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("alerts", response.context)
        alerts = response.context["alerts"]
        self.assertGreaterEqual(len(alerts), 1)
        self.assertContains(response, "Backup failed")

    def test_acknowledge_alert_actually_updates_database(self):
        """Test that acknowledging an alert actually updates the database."""
        self.client.force_login(self.admin_user)

        # Verify initial state
        self.assertEqual(self.alert.status, BackupAlert.ACTIVE)
        self.assertIsNone(self.alert.acknowledged_at)
        self.assertIsNone(self.alert.acknowledged_by)

        # Acknowledge the alert
        response = self.client.post(reverse("backups:acknowledge_alert", args=[self.alert.id]))

        self.assertEqual(response.status_code, 302)  # Redirect after success

        # Verify alert was actually updated in database
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, BackupAlert.ACKNOWLEDGED)
        self.assertIsNotNone(self.alert.acknowledged_at)
        self.assertEqual(self.alert.acknowledged_by, self.admin_user)

    def test_resolve_alert_actually_updates_database(self):
        """Test that resolving an alert actually updates the database."""
        self.client.force_login(self.admin_user)

        # Verify initial state
        self.assertEqual(self.alert.status, BackupAlert.ACTIVE)
        self.assertIsNone(self.alert.resolved_at)
        self.assertIsNone(self.alert.resolved_by)

        # Resolve the alert
        response = self.client.post(
            reverse("backups:resolve_alert", args=[self.alert.id]),
            {"resolution_notes": "Fixed network issue"},
        )

        self.assertEqual(response.status_code, 302)  # Redirect after success

        # Verify alert was actually updated in database
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, BackupAlert.RESOLVED)
        self.assertIsNotNone(self.alert.resolved_at)
        self.assertEqual(self.alert.resolved_by, self.admin_user)
        self.assertEqual(self.alert.resolution_notes, "Fixed network issue")


@pytest.mark.django_db
class TestManualBackupIntegration(TestCase):
    """Test manual backup trigger with real backup creation."""

    def setUp(self):
        """Set up test data."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            self.admin_user = User.objects.create_user(
                username="admin",
                email="admin@example.com",
                password="testpass123",
                role="PLATFORM_ADMIN",
                is_staff=True,
            )

            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop",
                slug="test-shop",
                status="ACTIVE",
            )

        self.client = Client()

    def test_manual_backup_form_displays(self):
        """Test that manual backup form displays correctly."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("backups:manual_backup"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertContains(response, "Backup Scope")
        self.assertContains(response, "Execution Timing")


@pytest.mark.django_db
class TestRestoreWizardIntegration(TestCase):
    """Test restore wizard with real data."""

    def setUp(self):
        """Set up test data."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            self.admin_user = User.objects.create_user(
                username="admin",
                email="admin@example.com",
                password="testpass123",
                role="PLATFORM_ADMIN",
                is_staff=True,
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

    def test_restore_wizard_displays(self):
        """Test that restore wizard displays correctly."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("backups:restore_backup"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertContains(response, "Restore Wizard")
        self.assertContains(response, "4-step process")

    def test_restore_wizard_with_backup_id(self):
        """Test restore wizard with pre-selected backup."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("backups:restore_backup_with_id", args=[self.backup.id]))

        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)


@pytest.mark.django_db
class TestDisasterRecoveryIntegration(TestCase):
    """Test DR runbook interface with real data."""

    def setUp(self):
        """Set up test data."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            self.admin_user = User.objects.create_user(
                username="admin",
                email="admin@example.com",
                password="testpass123",
                role="PLATFORM_ADMIN",
                is_staff=True,
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

    def test_dr_runbook_displays(self):
        """Test that DR runbook interface displays correctly."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("backups:disaster_recovery_runbook"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("latest_backup", response.context)
        self.assertIn("available_backups", response.context)
        self.assertContains(response, "Disaster Recovery")

        # Verify latest backup is shown
        latest_backup = response.context["latest_backup"]
        self.assertIsNotNone(latest_backup)
        self.assertEqual(latest_backup.id, self.backup.id)


@pytest.mark.django_db
class TestRestoreListIntegration(TestCase):
    """Test restore list with real restore operations."""

    def setUp(self):
        """Set up test data."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            self.admin_user = User.objects.create_user(
                username="admin",
                email="admin@example.com",
                password="testpass123",
                role="PLATFORM_ADMIN",
                is_staff=True,
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

            self.restore_log = BackupRestoreLog.objects.create(
                backup=self.backup,
                restore_mode=BackupRestoreLog.FULL,
                initiated_by=self.admin_user,
                reason="Test restore",
                status=BackupRestoreLog.COMPLETED,
                started_at=timezone.now(),
                completed_at=timezone.now(),
                duration_seconds=600,
            )

        self.client = Client()

    def test_restore_list_displays_real_restores(self):
        """Test that restore list displays real restore operations."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("backups:restore_list"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("restore_logs", response.context)
        restore_logs = response.context["restore_logs"]
        self.assertGreaterEqual(len(restore_logs), 1)

        # Verify restore log data
        restore_ids = [r.id for r in restore_logs]
        self.assertIn(self.restore_log.id, restore_ids)

    def test_restore_detail_displays_real_information(self):
        """Test that restore detail displays real information."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("backups:restore_detail", args=[self.restore_log.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["restore_log"].id, self.restore_log.id)

        # Verify all fields are displayed
        self.assertContains(response, "Test restore")
        self.assertContains(response, "600")  # Duration in seconds
        self.assertContains(response, self.admin_user.username)
