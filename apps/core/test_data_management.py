"""
Tests for data management functionality.

Implements Requirement 20: Settings and Configuration
- Test data export functionality
- Test data import functionality
- Test backup trigger interface
"""

import os
import tempfile
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.data_models import BackupTrigger, DataActivity
from apps.core.data_services import BackupTriggerService, DataExportService, DataImportService
from apps.core.models import Branch, Tenant
from apps.core.tenant_context import bypass_rls, tenant_context

User = get_user_model()


class DataExportServiceTests(TestCase):
    """Test data export service functionality."""

    def setUp(self):
        """Set up test data."""
        with bypass_rls():
            self.tenant = Tenant.objects.create(company_name="Test Jewelry Shop", slug="test-shop")

            self.user = User.objects.create_user(
                username="testuser", password="testpass", tenant=self.tenant, role=User.TENANT_OWNER
            )

            # Create a branch
            self.branch = Branch.objects.create(tenant=self.tenant, name="Main Branch")

        self.export_service = DataExportService(self.tenant)

    def test_export_inventory_data(self):
        """Test exporting inventory data."""
        # Create test inventory item
        from apps.inventory.models import InventoryItem, ProductCategory

        with tenant_context(self.tenant.id):
            category = ProductCategory.objects.create(tenant=self.tenant, name="Rings")

            InventoryItem.objects.create(
                tenant=self.tenant,
                sku="RING-001",
                name="Gold Ring",
                category=category,
                karat=24,
                weight_grams=Decimal("10.5"),
                cost_price=Decimal("1000.00"),
                selling_price=Decimal("1200.00"),
                quantity=5,
                branch=self.branch,
            )

            # Test export
            data = self.export_service._get_inventory_data()

            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["SKU"], "RING-001")
            self.assertEqual(data[0]["Name"], "Gold Ring")
            self.assertEqual(data[0]["Karat"], 24)

    def test_export_to_csv(self):
        """Test CSV export functionality."""
        test_data = {
            "inventory": [
                {"SKU": "TEST-001", "Name": "Test Item", "Price": 100.00},
                {"SKU": "TEST-002", "Name": "Test Item 2", "Price": 200.00},
            ]
        }

        file_path = self.export_service._export_to_csv(test_data, ["inventory"])

        # Verify file was created
        self.assertTrue(os.path.exists(file_path))

        # Verify file content
        with open(file_path, "r") as f:
            content = f.read()
            self.assertIn("SKU,Name,Price", content)
            self.assertIn("TEST-001,Test Item,100.0", content)

        # Clean up
        os.remove(file_path)

    def test_export_to_excel(self):
        """Test Excel export functionality."""
        test_data = {"inventory": [{"SKU": "TEST-001", "Name": "Test Item", "Price": 100.00}]}

        file_path = self.export_service._export_to_excel(test_data, ["inventory"])

        # Verify file was created
        self.assertTrue(os.path.exists(file_path))
        self.assertTrue(file_path.endswith(".xlsx"))

        # Clean up
        os.remove(file_path)


class DataImportServiceTests(TestCase):
    """Test data import service functionality."""

    def setUp(self):
        """Set up test data."""
        with bypass_rls():
            self.tenant = Tenant.objects.create(company_name="Test Jewelry Shop", slug="test-shop")

            self.user = User.objects.create_user(
                username="testuser", password="testpass", tenant=self.tenant, role=User.TENANT_OWNER
            )

            # Create a branch
            self.branch = Branch.objects.create(tenant=self.tenant, name="Main Branch")

        self.import_service = DataImportService(self.tenant)

    def test_parse_csv_file(self):
        """Test CSV file parsing."""
        # Create temporary CSV file
        csv_content = """SKU,Name,Karat,Weight (grams),Cost Price,Selling Price,Quantity
RING-001,Gold Ring,24,10.5,1000.00,1200.00,5
RING-002,Silver Ring,18,8.0,800.00,1000.00,3"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_file = f.name

        try:
            data = self.import_service._parse_csv_file(temp_file)

            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]["SKU"], "RING-001")
            self.assertEqual(data[0]["Name"], "Gold Ring")
            self.assertEqual(data[1]["SKU"], "RING-002")
        finally:
            os.unlink(temp_file)

    def test_validate_inventory_data(self):
        """Test inventory data validation."""
        # Valid data
        valid_data = [
            {
                "SKU": "RING-001",
                "Name": "Gold Ring",
                "Karat": "24",
                "Weight (grams)": "10.5",
                "Cost Price": "1000.00",
                "Selling Price": "1200.00",
                "Quantity": "5",
            }
        ]

        errors = self.import_service._validate_import_data("inventory", valid_data)
        self.assertEqual(len(errors), 0)

        # Invalid data - missing required field
        invalid_data = [
            {
                "Name": "Gold Ring",
                "Karat": "24",
                # Missing SKU and other required fields
            }
        ]

        errors = self.import_service._validate_import_data("inventory", invalid_data)
        self.assertGreater(len(errors), 0)
        self.assertIn("Missing required fields", errors[0])


class BackupTriggerServiceTests(TestCase):
    """Test backup trigger service functionality."""

    def setUp(self):
        """Set up test data."""
        with bypass_rls():
            self.tenant = Tenant.objects.create(company_name="Test Jewelry Shop", slug="test-shop")

            self.user = User.objects.create_user(
                username="testuser", password="testpass", tenant=self.tenant, role=User.TENANT_OWNER
            )

        self.backup_service = BackupTriggerService(self.tenant)

    def test_trigger_backup(self):
        """Test backup trigger creation."""
        trigger = self.backup_service.trigger_backup(
            backup_type="TENANT", user=self.user, reason="Test backup"
        )

        self.assertIsInstance(trigger, BackupTrigger)
        self.assertEqual(trigger.backup_type, "TENANT")
        self.assertEqual(trigger.tenant, self.tenant)
        self.assertEqual(trigger.initiated_by, self.user)
        self.assertEqual(trigger.reason, "Test backup")
        self.assertEqual(trigger.status, "QUEUED")

    def test_get_backup_status(self):
        """Test backup status retrieval."""
        trigger = BackupTrigger.objects.create(
            tenant=self.tenant, backup_type="TENANT", initiated_by=self.user, status="COMPLETED"
        )

        status = self.backup_service.get_backup_status(str(trigger.id))

        self.assertEqual(status["id"], str(trigger.id))
        self.assertEqual(status["status"], "COMPLETED")
        self.assertEqual(status["backup_type"], "TENANT")


class DataManagementViewTests(TestCase):
    """Test data management views."""

    def setUp(self):
        """Set up test data."""
        with bypass_rls():
            self.tenant = Tenant.objects.create(company_name="Test Jewelry Shop", slug="test-shop")

            self.user = User.objects.create_user(
                username="testuser", password="testpass", tenant=self.tenant, role=User.TENANT_OWNER
            )

        self.client.force_login(self.user)

    def test_data_management_view_get(self):
        """Test data management view GET request."""
        url = reverse("core:settings_data_management")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Data Management")
        self.assertContains(response, "Data Export")
        self.assertContains(response, "Data Import")

    @patch("apps.core.settings_views.export_data_async.delay")
    def test_data_export_request(self, mock_export_task):
        """Test data export request."""
        mock_export_task.return_value = MagicMock()

        url = reverse("core:settings_data_management")
        data = {
            "action": "export",
            "export_types": ["inventory", "customers"],
            "export_format": "csv",
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)  # Redirect after success
        mock_export_task.assert_called_once()

    @patch("apps.core.settings_views.import_data_async.delay")
    def test_data_import_request(self, mock_import_task):
        """Test data import request."""
        mock_import_task.return_value = MagicMock()

        # Create a test CSV file
        csv_content = "SKU,Name,Karat\nTEST-001,Test Item,24"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_file = f.name

        try:
            url = reverse("core:settings_data_management")

            with open(temp_file, "rb") as upload_file:
                data = {
                    "action": "import",
                    "import_type": "inventory",
                    "import_file": upload_file,
                    "update_existing": "on",
                }

                response = self.client.post(url, data)

            self.assertEqual(response.status_code, 302)  # Redirect after success
            mock_import_task.assert_called_once()
        finally:
            os.unlink(temp_file)

    def test_backup_management_view_get(self):
        """Test backup management view GET request."""
        url = reverse("core:settings_backup_management")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Backup Management")
        self.assertContains(response, "Trigger Manual Backup")

    @patch("apps.core.settings_views.trigger_backup_async.delay")
    def test_backup_trigger_request(self, mock_backup_task):
        """Test backup trigger request."""
        mock_backup_task.return_value = MagicMock()

        url = reverse("core:settings_backup_management")
        data = {
            "backup_type": "TENANT",
            "priority": "NORMAL",
            "reason": "Test backup",
            "include_media": "on",
            "compress_backup": "on",
            "encrypt_backup": "on",
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)  # Redirect after success
        mock_backup_task.assert_called_once()


class DataActivityModelTests(TestCase):
    """Test DataActivity model functionality."""

    def setUp(self):
        """Set up test data."""
        with bypass_rls():
            self.tenant = Tenant.objects.create(company_name="Test Jewelry Shop", slug="test-shop")

            self.user = User.objects.create_user(
                username="testuser", password="testpass", tenant=self.tenant, role=User.TENANT_OWNER
            )

    def test_create_data_activity(self):
        """Test creating a data activity record."""
        with tenant_context(self.tenant.id):
            activity = DataActivity.objects.create(
                tenant=self.tenant,
                activity_type="EXPORT",
                data_type="inventory",
                format="csv",
                initiated_by=self.user,
            )

            self.assertEqual(activity.tenant, self.tenant)
            self.assertEqual(activity.activity_type, "EXPORT")
            self.assertEqual(activity.data_type, "inventory")
            self.assertEqual(activity.format, "csv")
            self.assertEqual(activity.status, "PENDING")

    def test_activity_status_transitions(self):
        """Test activity status transitions."""
        activity = DataActivity.objects.create(
            tenant=self.tenant,
            activity_type="EXPORT",
            data_type="inventory",
            format="csv",
            initiated_by=self.user,
        )

        # Test mark_started
        activity.mark_started()
        activity.refresh_from_db()
        self.assertEqual(activity.status, "IN_PROGRESS")
        self.assertIsNotNone(activity.started_at)

        # Test mark_completed
        activity.mark_completed(records_processed=100, records_successful=95, records_failed=5)
        activity.refresh_from_db()
        self.assertEqual(activity.status, "COMPLETED")
        self.assertIsNotNone(activity.completed_at)
        self.assertEqual(activity.records_processed, 100)
        self.assertEqual(activity.records_successful, 95)
        self.assertEqual(activity.records_failed, 5)

    def test_activity_success_rate(self):
        """Test activity success rate calculation."""
        activity = DataActivity.objects.create(
            tenant=self.tenant,
            activity_type="IMPORT",
            data_type="customers",
            format="csv",
            initiated_by=self.user,
            records_processed=100,
            records_successful=95,
            records_failed=5,
        )

        self.assertEqual(activity.success_rate, 95.0)


class BackupTriggerModelTests(TestCase):
    """Test BackupTrigger model functionality."""

    def setUp(self):
        """Set up test data."""
        with bypass_rls():
            self.tenant = Tenant.objects.create(company_name="Test Jewelry Shop", slug="test-shop")

            self.user = User.objects.create_user(
                username="testuser", password="testpass", tenant=self.tenant, role=User.TENANT_OWNER
            )

    def test_create_backup_trigger(self):
        """Test creating a backup trigger record."""
        trigger = BackupTrigger.objects.create(
            tenant=self.tenant,
            backup_type="TENANT",
            priority="HIGH",
            initiated_by=self.user,
            reason="Test backup",
        )

        self.assertEqual(trigger.tenant, self.tenant)
        self.assertEqual(trigger.backup_type, "TENANT")
        self.assertEqual(trigger.priority, "HIGH")
        self.assertEqual(trigger.status, "PENDING")
        self.assertEqual(trigger.reason, "Test backup")

    def test_backup_status_transitions(self):
        """Test backup status transitions."""
        trigger = BackupTrigger.objects.create(
            tenant=self.tenant, backup_type="TENANT", initiated_by=self.user
        )

        # Test mark_queued
        trigger.mark_queued()
        trigger.refresh_from_db()
        self.assertEqual(trigger.status, "QUEUED")

        # Test mark_started
        trigger.mark_started()
        trigger.refresh_from_db()
        self.assertEqual(trigger.status, "IN_PROGRESS")
        self.assertIsNotNone(trigger.started_at)

        # Test mark_completed
        import uuid

        backup_id = uuid.uuid4()
        trigger.mark_completed(backup_id=backup_id, file_path="/path/to/backup.sql", file_size=1024)
        trigger.refresh_from_db()
        self.assertEqual(trigger.status, "COMPLETED")
        self.assertIsNotNone(trigger.completed_at)
        self.assertEqual(trigger.backup_id, backup_id)
        self.assertEqual(trigger.file_path, "/path/to/backup.sql")
        self.assertEqual(trigger.file_size, 1024)
