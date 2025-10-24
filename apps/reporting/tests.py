"""
Tests for the reporting system.

Tests the core functionality of report builder infrastructure.
"""

import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.reporting.models import ReportCategory
from apps.reporting.services import ReportExportService

User = get_user_model()


class ReportCategoryTests(TestCase):
    """Test report category functionality."""

    def test_category_creation(self):
        """Test creating a report category."""
        category = ReportCategory.objects.create(
            name="Test Category",
            category_type="SALES",
            description="Test sales category",
            icon="fas fa-chart-line",
            sort_order=1,
        )

        self.assertEqual(category.name, "Test Category")
        self.assertEqual(category.category_type, "SALES")
        self.assertTrue(category.is_active)


class ReportExportServiceTests(TestCase):
    """Test report export functionality without tenant dependency."""

    def setUp(self):
        """Set up test data."""
        # Create a mock tenant object for the export service
        self.mock_tenant = MagicMock()
        self.mock_tenant.company_name = "Test Shop"

        self.export_service = ReportExportService(self.mock_tenant)

        self.sample_data = [
            {"name": "Gold Ring", "price": "299.99", "quantity": "5"},
            {"name": "Silver Necklace", "price": "149.99", "quantity": "3"},
            {"name": "Diamond Earrings", "price": "899.99", "quantity": "2"},
        ]

    def test_csv_export(self):
        """Test CSV export."""
        filepath = self.export_service.export_to_csv(self.sample_data, "test_report.csv")

        self.assertTrue(filepath.endswith("test_report.csv"))

        # Read and verify content
        with open(filepath, "r") as f:
            content = f.read()
            self.assertIn("Gold Ring", content)
            self.assertIn("299.99", content)

    def test_json_export(self):
        """Test JSON export."""
        filepath = self.export_service.export_to_json(self.sample_data, "test_report.json")

        self.assertTrue(filepath.endswith("test_report.json"))

        # Read and verify content
        with open(filepath, "r") as f:
            data = json.load(f)
            self.assertEqual(data["row_count"], 3)
            self.assertEqual(len(data["data"]), 3)
            self.assertEqual(data["tenant"], "Test Shop")

    def test_excel_export(self):
        """Test Excel export."""
        filepath = self.export_service.export_to_excel(
            self.sample_data, "test_report.xlsx", "Test Report"
        )

        self.assertTrue(filepath.endswith("test_report.xlsx"))

        # Verify file exists and has content
        import os

        self.assertTrue(os.path.exists(filepath))
        self.assertGreater(os.path.getsize(filepath), 0)


class ReportModelTests(TestCase):
    """Test report model functionality."""

    def test_report_parameter_validation(self):
        """Test report parameter validation."""
        from apps.reporting.models import ReportParameter

        # Test date parameter validation
        param = ReportParameter(name="test_date", parameter_type="DATE", is_required=True)

        # Test valid date
        self.assertTrue(param.validate_value("2024-01-01"))

        # Test invalid date format
        self.assertFalse(param.validate_value("invalid-date"))

        # Test required parameter with None
        self.assertFalse(param.validate_value(None))

        # Test optional parameter with None
        param.is_required = False
        self.assertTrue(param.validate_value(None))

    def test_report_schedule_calculation(self):
        """Test report schedule next run calculations."""
        from apps.reporting.models import ReportSchedule

        # Test daily schedule
        schedule = ReportSchedule(frequency="DAILY", start_date=timezone.now(), status="ACTIVE")

        next_run = schedule.calculate_next_run()
        self.assertIsNotNone(next_run)

        # Should be approximately 24 hours from now
        expected_time = timezone.now() + timedelta(days=1)
        time_diff = abs((next_run - expected_time).total_seconds())
        self.assertLess(time_diff, 60)  # Within 1 minute

    def test_report_execution_status(self):
        """Test report execution status management."""
        from apps.reporting.models import ReportExecution

        # Test pending execution
        execution = ReportExecution(status="PENDING")
        self.assertTrue(execution.is_running)
        self.assertFalse(execution.is_completed)

        # Test completed execution
        execution.status = "COMPLETED"
        self.assertFalse(execution.is_running)
        self.assertTrue(execution.is_completed)

    def test_duration_display(self):
        """Test duration display formatting."""
        from apps.reporting.models import ReportExecution

        execution = ReportExecution()

        # Test no duration
        self.assertEqual(execution.duration_display, "N/A")

        # Test seconds
        execution.duration_seconds = 45
        self.assertEqual(execution.duration_display, "45s")

        # Test minutes and seconds
        execution.duration_seconds = 125  # 2m 5s
        self.assertEqual(execution.duration_display, "2m 5s")


class ReportParameterProcessorTests(TestCase):
    """Test report parameter processing."""

    def test_parameter_validation_logic(self):
        """Test parameter validation without database dependencies."""
        from apps.reporting.models import ReportParameter
        from apps.reporting.services import ReportParameterProcessor

        # Create mock report and parameters
        mock_report = MagicMock()
        mock_param = ReportParameter(name="test_param", parameter_type="TEXT", is_required=True)

        # Mock the parameter definitions
        processor = ReportParameterProcessor(mock_report)
        processor.parameter_definitions = {"test_param": mock_param}

        # Test missing required parameter
        is_valid, errors = processor.validate_parameters({})
        self.assertFalse(is_valid)
        self.assertTrue(len(errors) > 0)

        # Test valid parameter
        is_valid, errors = processor.validate_parameters({"test_param": "value"})
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)


class ReportEmailServiceTests(TestCase):
    """Test report email service."""

    def test_content_type_detection(self):
        """Test MIME content type detection."""
        from apps.reporting.services import ReportEmailService

        mock_tenant = MagicMock()
        service = ReportEmailService(mock_tenant)

        # Test different file extensions
        self.assertEqual(service._get_content_type("report.pdf"), "application/pdf")
        self.assertEqual(
            service._get_content_type("report.xlsx"),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertEqual(service._get_content_type("report.csv"), "text/csv")
        self.assertEqual(service._get_content_type("report.json"), "application/json")
        self.assertEqual(service._get_content_type("report.unknown"), "application/octet-stream")


class ReportQueryEngineTests(TestCase):
    """Test report query engine."""

    def test_predefined_report_types(self):
        """Test predefined report type handling."""
        from apps.reporting.models import Report
        from apps.reporting.services import ReportQueryEngine

        mock_tenant = MagicMock()
        engine = ReportQueryEngine(mock_tenant)

        # Test unsupported report type
        report = Report(report_type="UNSUPPORTED")

        with self.assertRaises(ValueError):
            engine.execute_query(report, {})


class CeleryTaskTests(TestCase):
    """Test Celery task functionality."""

    @patch("apps.reporting.tasks.ReportSchedule")
    def test_scheduled_report_task_logic(self, mock_schedule_model):
        """Test scheduled report task logic."""
        from apps.reporting.tasks import execute_scheduled_reports

        # Mock no due schedules
        mock_schedule_model.objects.filter.return_value.select_related.return_value = []

        # This should not raise an error
        result = execute_scheduled_reports()
        self.assertIn("Queued 0 scheduled reports", result)


class ReportIntegrationTests(TestCase):
    """Integration tests for the reporting system."""

    def test_export_service_error_handling(self):
        """Test export service error handling."""
        mock_tenant = MagicMock()
        mock_tenant.company_name = "Test Shop"

        export_service = ReportExportService(mock_tenant)

        # Test empty data export
        with self.assertRaises(ValueError):
            export_service.export_to_csv([], "empty.csv")

        with self.assertRaises(ValueError):
            export_service.export_to_json([], "empty.json")

        with self.assertRaises(ValueError):
            export_service.export_to_excel([], "empty.xlsx")

        with self.assertRaises(ValueError):
            export_service.export_to_pdf([], "empty.pdf")

    def test_pdf_export_functionality(self):
        """Test PDF export functionality."""
        mock_tenant = MagicMock()
        mock_tenant.company_name = "Test Shop"

        export_service = ReportExportService(mock_tenant)

        sample_data = [
            {"product": "Gold Ring", "sales": "10", "revenue": "2999.90"},
            {"product": "Silver Chain", "sales": "5", "revenue": "749.95"},
        ]

        filepath = export_service.export_to_pdf(sample_data, "test_report.pdf", "Sales Report")

        self.assertTrue(filepath.endswith("test_report.pdf"))

        # Verify file exists and has content
        import os

        self.assertTrue(os.path.exists(filepath))
        self.assertGreater(os.path.getsize(filepath), 0)
