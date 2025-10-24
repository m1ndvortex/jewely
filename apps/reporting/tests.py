"""
Tests for the reporting system.

Tests the core functionality of report builder infrastructure.
"""

import json
import os
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.reporting.models import Report, ReportCategory
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

    def test_predefined_report_execution(self):
        """Test execution of predefined reports."""
        from apps.reporting.models import Report
        from apps.reporting.services import ReportQueryEngine

        mock_tenant = MagicMock()
        mock_tenant.id = "test-tenant-id"

        engine = ReportQueryEngine(mock_tenant)

        # Test sales summary report structure
        report = Report(report_type="PREDEFINED", query_config={"report_name": "sales_summary"})

        # This would normally execute against the database
        # For testing, we just verify the method exists and handles the report type
        try:
            # This will fail due to database access, but we can catch and verify the error type
            engine.execute_query(report, {})
        except Exception as e:
            # Should fail with database error, not ValueError for unknown report
            self.assertNotIsInstance(e, ValueError)

    def test_unknown_predefined_report(self):
        """Test handling of unknown predefined report."""
        from apps.reporting.models import Report
        from apps.reporting.services import ReportQueryEngine

        mock_tenant = MagicMock()
        engine = ReportQueryEngine(mock_tenant)

        report = Report(report_type="PREDEFINED", query_config={"report_name": "unknown_report"})

        with self.assertRaises(ValueError) as context:
            engine.execute_query(report, {})

        self.assertIn("Unknown predefined report", str(context.exception))


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


class PrebuiltReportServiceTests(TestCase):
    """Test pre-built report service functionality."""

    def test_get_prebuilt_reports(self):
        """Test getting all pre-built reports."""
        from apps.reporting.services import PrebuiltReportService

        reports = PrebuiltReportService.get_prebuilt_reports()

        self.assertIsInstance(reports, list)
        self.assertGreater(len(reports), 0)

        # Check that all required fields are present
        for report in reports:
            self.assertIn("id", report)
            self.assertIn("name", report)
            self.assertIn("description", report)
            self.assertIn("category", report)
            self.assertIn("parameters", report)
            self.assertIn("output_formats", report)

    def test_get_prebuilt_report_by_id(self):
        """Test getting a specific pre-built report."""
        from apps.reporting.services import PrebuiltReportService

        # Test valid report ID
        report = PrebuiltReportService.get_prebuilt_report("sales_summary")
        self.assertEqual(report["id"], "sales_summary")
        self.assertEqual(report["name"], "Daily Sales Summary")
        self.assertEqual(report["category"], "SALES")

        # Test invalid report ID
        with self.assertRaises(ValueError):
            PrebuiltReportService.get_prebuilt_report("nonexistent_report")

    def test_get_reports_by_category(self):
        """Test filtering reports by category."""
        from apps.reporting.services import PrebuiltReportService

        sales_reports = PrebuiltReportService.get_reports_by_category("SALES")
        self.assertIsInstance(sales_reports, list)

        # All reports should be sales reports
        for report in sales_reports:
            self.assertEqual(report["category"], "SALES")

        # Test empty category
        empty_reports = PrebuiltReportService.get_reports_by_category("NONEXISTENT")
        self.assertEqual(len(empty_reports), 0)

    def test_report_categories_coverage(self):
        """Test that all expected categories are covered."""
        from apps.reporting.services import PrebuiltReportService

        reports = PrebuiltReportService.get_prebuilt_reports()
        categories = set(report["category"] for report in reports)

        expected_categories = {"SALES", "INVENTORY", "FINANCIAL", "CUSTOMER"}
        self.assertTrue(expected_categories.issubset(categories))

    def test_report_parameter_structure(self):
        """Test that report parameters have correct structure."""
        from apps.reporting.services import PrebuiltReportService

        reports = PrebuiltReportService.get_prebuilt_reports()

        for report in reports:
            for param in report["parameters"]:
                self.assertIn("name", param)
                self.assertIn("type", param)
                self.assertIn("required", param)

                # Check valid parameter types
                valid_types = ["TEXT", "NUMBER", "DATE", "DATERANGE", "SELECT", "BRANCH"]
                self.assertIn(param["type"], valid_types)


class ReportSchedulingTests(TestCase):
    """Test report scheduling functionality."""

    def setUp(self):
        """Set up test data."""
        import uuid

        from django.contrib.auth import get_user_model

        from apps.core.models import Tenant
        from apps.core.tenant_context import bypass_rls, tenant_context

        User = get_user_model()

        # Create test tenant and user using RLS bypass
        unique_id = str(uuid.uuid4())[:8]

        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop", slug=f"test-shop-{unique_id}", status="ACTIVE"
            )

            self.user = User.objects.create_user(
                username=f"testuser-{unique_id}",
                email=f"test-{unique_id}@example.com",
                tenant=self.tenant,
                role="TENANT_OWNER",
            )

        # Create test report category and report within tenant context
        from apps.reporting.models import Report

        with tenant_context(self.tenant.id):
            self.category = ReportCategory.objects.create(
                name="Test Reports", category_type="SALES"
            )

            self.report = Report.objects.create(
                tenant=self.tenant,
                name="Test Sales Report",
                description="Test report for scheduling",
                category=self.category,
                report_type="PREDEFINED",
                query_config={"report_name": "sales_summary"},
                created_by=self.user,
                is_public=True,
            )

    def test_report_schedule_creation(self):
        """Test creating a report schedule."""
        from apps.core.tenant_context import tenant_context
        from apps.reporting.models import ReportSchedule

        with tenant_context(self.tenant.id):
            schedule = ReportSchedule.objects.create(
                report=self.report,
                name="Daily Sales Report",
                frequency="DAILY",
                start_date=timezone.now(),
                parameters={"date_range_start": "2024-01-01", "date_range_end": "2024-01-31"},
                output_format="PDF",
                email_recipients=["manager@testshop.com"],
                email_subject="Daily Sales Report",
                created_by=self.user,
            )

        self.assertEqual(schedule.name, "Daily Sales Report")
        self.assertEqual(schedule.frequency, "DAILY")
        self.assertEqual(schedule.status, "ACTIVE")
        self.assertEqual(len(schedule.email_recipients), 1)

    def test_schedule_next_run_calculation(self):
        """Test next run time calculation for different frequencies."""
        from apps.reporting.models import ReportSchedule

        base_time = timezone.now()

        # Test daily schedule
        daily_schedule = ReportSchedule.objects.create(
            report=self.report,
            name="Daily Report",
            frequency="DAILY",
            start_date=base_time,
            email_recipients=["test@example.com"],
            created_by=self.user,
        )

        next_run = daily_schedule.calculate_next_run()
        self.assertIsNotNone(next_run)

        # Should be approximately 24 hours from start time
        expected_time = base_time + timedelta(days=1)
        time_diff = abs((next_run - expected_time).total_seconds())
        self.assertLess(time_diff, 60)  # Within 1 minute

    def test_schedule_validation(self):
        """Test schedule validation rules."""
        from django.core.exceptions import ValidationError

        from apps.reporting.models import ReportSchedule

        # Test missing email recipients
        schedule = ReportSchedule(
            report=self.report,
            name="Invalid Schedule",
            frequency="DAILY",
            start_date=timezone.now(),
            email_recipients=[],  # Empty recipients
            created_by=self.user,
        )

        with self.assertRaises(ValidationError):
            schedule.full_clean()

    def test_scheduled_report_execution_task(self):
        """Test scheduled report execution via Celery task."""
        from unittest.mock import MagicMock, patch

        from apps.core.tenant_context import tenant_context
        from apps.reporting.models import ReportSchedule
        from apps.reporting.tasks import execute_scheduled_report

        with tenant_context(self.tenant.id):
            # Create a schedule
            schedule = ReportSchedule.objects.create(
                report=self.report,
                name="Test Scheduled Report",
                frequency="DAILY",
                start_date=timezone.now() - timedelta(hours=1),  # Due for execution
                next_run_at=timezone.now() - timedelta(minutes=30),  # Past due
                parameters={"date_range_start": "2024-01-01"},
                output_format="CSV",
                email_recipients=["test@example.com"],
                created_by=self.user,
            )

            # Mock the report execution service to avoid database queries
            with patch("apps.reporting.tasks.ReportExecutionService") as mock_service:
                mock_execution = MagicMock()
                mock_execution.row_count = 10
                mock_service.return_value.execute_report.return_value = mock_execution

                # Execute the task
                result = execute_scheduled_report(str(schedule.id))

                # Verify task completed
                self.assertIsNotNone(result)
                self.assertIn("Executed report", result)

                # Verify schedule was updated
                schedule.refresh_from_db()
                self.assertIsNotNone(schedule.last_run_at)
                self.assertEqual(schedule.run_count, 1)


class ReportDashboardDataTests(TestCase):
    """Test dashboard data accuracy."""

    def setUp(self):
        """Set up test data."""
        import uuid

        from django.contrib.auth import get_user_model

        from apps.core.models import Tenant
        from apps.core.tenant_context import bypass_rls, tenant_context

        User = get_user_model()

        # Create test tenant and user using RLS bypass
        unique_id = str(uuid.uuid4())[:8]

        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Dashboard Test Shop",
                slug=f"dashboard-test-{unique_id}",
                status="ACTIVE",
            )

            self.user = User.objects.create_user(
                username=f"dashuser-{unique_id}",
                email=f"dash-{unique_id}@example.com",
                tenant=self.tenant,
                role="TENANT_OWNER",
            )

        # Create test report category within tenant context
        with tenant_context(self.tenant.id):
            self.category = ReportCategory.objects.create(
                name="Dashboard Reports", category_type="SALES"
            )

    def test_dashboard_statistics_calculation(self):
        """Test dashboard statistics are calculated correctly."""
        from apps.core.tenant_context import tenant_context
        from apps.reporting.models import Report, ReportExecution, ReportSchedule

        with tenant_context(self.tenant.id):
            # Create test reports
            report1 = Report.objects.create(
                tenant=self.tenant,
                name="Sales Report 1",
                category=self.category,
                created_by=self.user,
            )

            report2 = Report.objects.create(
                tenant=self.tenant,
                name="Sales Report 2",
                category=self.category,
                created_by=self.user,
            )

            # Create test schedules
            ReportSchedule.objects.create(
                report=report1,
                name="Schedule 1",
                frequency="DAILY",
                status="ACTIVE",
                email_recipients=["test@example.com"],
                created_by=self.user,
            )

            ReportSchedule.objects.create(
                report=report2,
                name="Schedule 2",
                frequency="WEEKLY",
                status="PAUSED",
                email_recipients=["test@example.com"],
                created_by=self.user,
            )

            # Create test executions
            ReportExecution.objects.create(
                report=report1,
                trigger_type="MANUAL",
                output_format="PDF",
                status="COMPLETED",
                row_count=100,
                executed_by=self.user,
            )

            ReportExecution.objects.create(
                report=report2,
                trigger_type="SCHEDULED",
                output_format="EXCEL",
                status="FAILED",
                executed_by=self.user,
            )

        # Test dashboard calculations
        total_reports = Report.objects.filter(tenant=self.tenant).count()
        self.assertEqual(total_reports, 2)

        active_schedules = ReportSchedule.objects.filter(
            report__tenant=self.tenant, status="ACTIVE"
        ).count()
        self.assertEqual(active_schedules, 1)

        total_executions = ReportExecution.objects.filter(report__tenant=self.tenant).count()
        self.assertEqual(total_executions, 2)

        successful_executions = ReportExecution.objects.filter(
            report__tenant=self.tenant, status="COMPLETED"
        ).count()
        self.assertEqual(successful_executions, 1)

        failed_executions = ReportExecution.objects.filter(
            report__tenant=self.tenant, status="FAILED"
        ).count()
        self.assertEqual(failed_executions, 1)

    def test_popular_reports_calculation(self):
        """Test popular reports calculation for dashboard."""
        from django.db.models import Count

        from apps.reporting.models import Report, ReportExecution

        # Create test reports
        popular_report = Report.objects.create(
            tenant=self.tenant, name="Popular Report", category=self.category, created_by=self.user
        )

        unpopular_report = Report.objects.create(
            tenant=self.tenant,
            name="Unpopular Report",
            category=self.category,
            created_by=self.user,
        )

        # Create multiple executions for popular report
        for i in range(5):
            ReportExecution.objects.create(
                report=popular_report,
                trigger_type="MANUAL",
                output_format="PDF",
                status="COMPLETED",
                executed_by=self.user,
            )

        # Create single execution for unpopular report
        ReportExecution.objects.create(
            report=unpopular_report,
            trigger_type="MANUAL",
            output_format="PDF",
            status="COMPLETED",
            executed_by=self.user,
        )

        # Test popular reports query
        popular_reports = (
            Report.objects.filter(tenant=self.tenant)
            .annotate(execution_count=Count("executions"))
            .order_by("-execution_count")
        )

        self.assertEqual(popular_reports[0].name, "Popular Report")
        self.assertEqual(popular_reports[0].execution_count, 5)
        self.assertEqual(popular_reports[1].name, "Unpopular Report")
        self.assertEqual(popular_reports[1].execution_count, 1)


class ReportGenerationIntegrationTests(TestCase):
    """Integration tests for complete report generation workflow."""

    def setUp(self):
        """Set up test data."""
        import uuid

        from django.contrib.auth import get_user_model

        from apps.core.models import Tenant
        from apps.core.tenant_context import bypass_rls, tenant_context

        User = get_user_model()

        # Create test tenant and user using RLS bypass
        unique_id = str(uuid.uuid4())[:8]

        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Integration Test Shop",
                slug=f"integration-test-{unique_id}",
                status="ACTIVE",
            )

            self.user = User.objects.create_user(
                username=f"integuser-{unique_id}",
                email=f"integ-{unique_id}@example.com",
                tenant=self.tenant,
                role="TENANT_OWNER",
            )

        # Create test report category within tenant context
        with tenant_context(self.tenant.id):
            self.category = ReportCategory.objects.create(
                name="Integration Reports", category_type="SALES"
            )

    def test_complete_report_execution_workflow(self):
        """Test complete report execution from creation to export."""
        from unittest.mock import patch

        from apps.reporting.models import Report
        from apps.reporting.services import ReportExecutionService

        # Create test report
        report = Report.objects.create(
            tenant=self.tenant,
            name="Integration Test Report",
            description="Test complete workflow",
            category=self.category,
            report_type="PREDEFINED",
            query_config={"report_name": "sales_summary"},
            parameters={
                "parameters": [{"name": "date_range", "type": "DATERANGE", "required": True}]
            },
            output_formats=["PDF", "CSV"],
            created_by=self.user,
            is_public=True,
        )

        # Mock the query engine to return test data
        test_data = [
            {"date": "2024-01-01", "sales": 1000, "transactions": 10},
            {"date": "2024-01-02", "sales": 1500, "transactions": 15},
        ]

        with patch("apps.reporting.services.ReportQueryEngine.execute_query") as mock_query:
            mock_query.return_value = test_data

            # Execute report
            execution_service = ReportExecutionService(self.tenant)

            execution = execution_service.execute_report(
                report=report,
                parameters={"date_range_start": "2024-01-01", "date_range_end": "2024-01-02"},
                output_format="CSV",
                user=self.user,
                email_recipients=["test@example.com"],
                trigger_type="MANUAL",
            )

            # Verify execution was created
            self.assertIsNotNone(execution)
            self.assertEqual(execution.status, "COMPLETED")
            self.assertEqual(execution.row_count, 2)
            self.assertEqual(execution.trigger_type, "MANUAL")
            self.assertEqual(execution.output_format, "CSV")
            self.assertTrue(execution.result_file_path.endswith(".csv"))

            # Verify report statistics were updated
            report.refresh_from_db()
            self.assertEqual(report.run_count, 1)
            self.assertIsNotNone(report.last_run_at)

    def test_report_parameter_validation_workflow(self):
        """Test parameter validation in complete workflow."""
        from apps.reporting.models import Report, ReportParameter
        from apps.reporting.services import ReportExecutionService

        # Create test report with parameters
        report = Report.objects.create(
            tenant=self.tenant,
            name="Parameter Test Report",
            category=self.category,
            report_type="CUSTOM",
            query_config={"sql": "SELECT * FROM test_table WHERE date >= %(start_date)s"},
            created_by=self.user,
        )

        # Create parameter definition
        ReportParameter.objects.create(
            report=report,
            name="start_date",
            label="Start Date",
            parameter_type="DATE",
            is_required=True,
        )

        execution_service = ReportExecutionService(self.tenant)

        # Test with missing required parameter
        with self.assertRaises(ValueError) as context:
            execution_service.execute_report(
                report=report,
                parameters={},  # Missing required parameter
                output_format="CSV",
                user=self.user,
            )

        self.assertIn("Parameter validation failed", str(context.exception))
        self.assertIn("Required parameter", str(context.exception))

    def test_export_format_handling(self):
        """Test different export formats in workflow."""
        from apps.reporting.services import ReportExportService

        export_service = ReportExportService(self.tenant)

        test_data = [
            {"product": "Gold Ring", "quantity": 5, "revenue": 2500.00},
            {"product": "Silver Chain", "quantity": 3, "revenue": 450.00},
        ]

        # Test all supported formats
        formats_to_test = ["CSV", "EXCEL", "PDF", "JSON"]

        for format_type in formats_to_test:
            with self.subTest(format_type=format_type):
                filename = f"test_report.{format_type.lower()}"

                try:
                    filepath = export_service.export_data(
                        data=test_data,
                        format_type=format_type,
                        filename=filename,
                        report_name="Test Export Report",
                    )

                    # Verify file was created
                    self.assertTrue(os.path.exists(filepath))
                    self.assertGreater(os.path.getsize(filepath), 0)

                    # Verify correct file extension
                    expected_extension = export_service.get_format_extension(format_type)
                    self.assertTrue(filepath.endswith(expected_extension))

                except Exception as e:
                    self.fail(f"Export failed for format {format_type}: {e}")


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

    def test_prebuilt_report_data_structure(self):
        """Test that pre-built reports return expected data structure."""
        from apps.reporting.services import PrebuiltReportService

        # Test all pre-built reports have consistent structure
        reports = PrebuiltReportService.get_prebuilt_reports()

        required_fields = [
            "id",
            "name",
            "description",
            "category",
            "icon",
            "parameters",
            "output_formats",
        ]

        for report in reports:
            for field in required_fields:
                self.assertIn(
                    field, report, f"Report {report.get('id', 'unknown')} missing field: {field}"
                )

            # Test output formats are valid
            valid_formats = ["PDF", "EXCEL", "CSV", "JSON"]
            for format_type in report["output_formats"]:
                self.assertIn(format_type, valid_formats)

            # Test parameters structure
            for param in report["parameters"]:
                self.assertIn("name", param)
                self.assertIn("type", param)
                self.assertIn("required", param)


class ReportEmailDeliveryTests(TestCase):
    """Test report email delivery functionality."""

    def setUp(self):
        """Set up test data."""
        import uuid

        from django.contrib.auth import get_user_model

        from apps.core.models import Tenant
        from apps.core.tenant_context import bypass_rls, tenant_context

        User = get_user_model()

        # Create test tenant and user using RLS bypass
        unique_id = str(uuid.uuid4())[:8]

        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Email Test Shop", slug=f"email-test-{unique_id}", status="ACTIVE"
            )

            self.user = User.objects.create_user(
                username=f"emailuser-{unique_id}",
                email=f"email-{unique_id}@example.com",
                tenant=self.tenant,
                role="TENANT_OWNER",
            )

        # Create test report category and report within tenant context
        with tenant_context(self.tenant.id):
            self.category = ReportCategory.objects.create(
                name="Email Reports", category_type="SALES"
            )

            self.report = Report.objects.create(
                tenant=self.tenant,
                name="Email Test Report",
                category=self.category,
                created_by=self.user,
            )

    def test_email_service_initialization(self):
        """Test email service initialization."""
        from apps.reporting.services import ReportEmailService

        email_service = ReportEmailService(self.tenant)
        self.assertEqual(email_service.tenant, self.tenant)

    def test_email_content_generation(self):
        """Test email content generation."""
        from apps.reporting.models import ReportExecution
        from apps.reporting.services import ReportEmailService

        # Create test execution
        execution = ReportExecution.objects.create(
            report=self.report,
            trigger_type="MANUAL",
            output_format="PDF",
            status="COMPLETED",
            row_count=25,
            duration_seconds=120,
            executed_by=self.user,
        )

        email_service = ReportEmailService(self.tenant)

        # Test email body generation
        body = email_service._generate_email_body(execution)

        self.assertIn(self.tenant.company_name, body)
        self.assertIn(self.report.name, body)
        self.assertIn("25", body)  # Row count
        self.assertIn("2m 0s", body)  # Duration

    def test_content_type_detection(self):
        """Test MIME content type detection."""
        from apps.reporting.services import ReportEmailService

        email_service = ReportEmailService(self.tenant)

        # Test different file extensions
        self.assertEqual(email_service._get_content_type("report.pdf"), "application/pdf")
        self.assertEqual(
            email_service._get_content_type("report.xlsx"),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertEqual(email_service._get_content_type("report.csv"), "text/csv")
        self.assertEqual(email_service._get_content_type("report.json"), "application/json")
        self.assertEqual(
            email_service._get_content_type("report.unknown"), "application/octet-stream"
        )

    @patch("apps.reporting.services.EmailMessage")
    def test_email_sending_success(self, mock_email_class):
        """Test successful email sending."""
        import os
        import tempfile

        from apps.reporting.models import ReportExecution
        from apps.reporting.services import ReportEmailService

        # Create test execution
        execution = ReportExecution.objects.create(
            report=self.report,
            trigger_type="MANUAL",
            output_format="PDF",
            status="COMPLETED",
            executed_by=self.user,
        )

        # Create temporary test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pdf", delete=False) as f:
            f.write("Test PDF content")
            test_file_path = f.name

        try:
            # Mock email sending
            mock_email_instance = MagicMock()
            mock_email_class.return_value = mock_email_instance
            mock_email_instance.send.return_value = True

            email_service = ReportEmailService(self.tenant)

            # Test email sending
            result = email_service.send_report_email(
                execution=execution,
                file_path=test_file_path,
                recipients=["test@example.com", "manager@example.com"],
                subject="Test Report",
                body="Test email body",
            )

            # Verify email was sent
            self.assertTrue(result)
            mock_email_instance.send.assert_called_once()
            mock_email_instance.attach.assert_called_once()

            # Verify execution was updated
            execution.refresh_from_db()
            self.assertTrue(execution.email_sent)
            self.assertEqual(len(execution.email_recipients), 2)

        finally:
            # Clean up test file
            if os.path.exists(test_file_path):
                os.unlink(test_file_path)

    @patch("apps.reporting.services.EmailMessage")
    def test_email_sending_failure(self, mock_email_class):
        """Test email sending failure handling."""
        from apps.reporting.models import ReportExecution
        from apps.reporting.services import ReportEmailService

        # Create test execution
        execution = ReportExecution.objects.create(
            report=self.report,
            trigger_type="MANUAL",
            output_format="PDF",
            status="COMPLETED",
            executed_by=self.user,
        )

        # Mock email sending failure
        mock_email_instance = MagicMock()
        mock_email_class.return_value = mock_email_instance
        mock_email_instance.send.side_effect = Exception("SMTP Error")

        email_service = ReportEmailService(self.tenant)

        # Test email sending failure
        result = email_service.send_report_email(
            execution=execution, file_path="nonexistent.pdf", recipients=["test@example.com"]
        )

        # Verify failure was handled
        self.assertFalse(result)

        # Verify execution was not marked as sent
        execution.refresh_from_db()
        self.assertFalse(execution.email_sent)


class ReportCleanupTaskTests(TestCase):
    """Test report cleanup tasks."""

    def setUp(self):
        """Set up test data."""
        import uuid

        from django.contrib.auth import get_user_model

        from apps.core.models import Tenant
        from apps.core.tenant_context import bypass_rls, tenant_context

        User = get_user_model()

        # Create test tenant and user using RLS bypass
        unique_id = str(uuid.uuid4())[:8]

        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Cleanup Test Shop", slug=f"cleanup-test-{unique_id}", status="ACTIVE"
            )

            self.user = User.objects.create_user(
                username=f"cleanupuser-{unique_id}",
                email=f"cleanup-{unique_id}@example.com",
                tenant=self.tenant,
                role="TENANT_OWNER",
            )

        # Create test report category and report within tenant context
        with tenant_context(self.tenant.id):
            self.category = ReportCategory.objects.create(
                name="Cleanup Reports", category_type="SALES"
            )

            self.report = Report.objects.create(
                tenant=self.tenant,
                name="Cleanup Test Report",
                category=self.category,
                created_by=self.user,
            )

    def test_old_execution_cleanup(self):
        """Test cleanup of old execution records."""
        from apps.reporting.models import ReportExecution
        from apps.reporting.tasks import cleanup_old_executions

        # Create old executions (older than 90 days)
        old_date = timezone.now() - timedelta(days=95)

        old_successful = ReportExecution.objects.create(
            report=self.report,
            trigger_type="MANUAL",
            output_format="PDF",
            status="COMPLETED",
            completed_at=old_date,
            executed_by=self.user,
        )

        old_failed = ReportExecution.objects.create(
            report=self.report,
            trigger_type="MANUAL",
            output_format="PDF",
            status="FAILED",
            completed_at=old_date,
            executed_by=self.user,
        )

        # Create recent execution (should not be deleted)
        recent_execution = ReportExecution.objects.create(
            report=self.report,
            trigger_type="MANUAL",
            output_format="PDF",
            status="COMPLETED",
            completed_at=timezone.now() - timedelta(days=30),
            executed_by=self.user,
        )

        # Run cleanup task
        result = cleanup_old_executions(days_to_keep=90)

        # Verify old executions were deleted
        self.assertFalse(ReportExecution.objects.filter(id=old_successful.id).exists())
        self.assertFalse(ReportExecution.objects.filter(id=old_failed.id).exists())

        # Verify recent execution was kept
        self.assertTrue(ReportExecution.objects.filter(id=recent_execution.id).exists())

        # Verify result message
        self.assertIn("Deleted", result)
        self.assertIn("old execution records", result)

    def test_file_cleanup_task(self):
        """Test cleanup of old report files."""
        import os
        import tempfile

        from apps.reporting.models import ReportExecution
        from apps.reporting.tasks import cleanup_old_report_files

        # Create temporary test files
        old_file = tempfile.NamedTemporaryFile(mode="w", suffix=".pdf", delete=False)
        old_file.write("Old report content")
        old_file.close()

        recent_file = tempfile.NamedTemporaryFile(mode="w", suffix=".pdf", delete=False)
        recent_file.write("Recent report content")
        recent_file.close()

        try:
            # Create old execution with file (older than 30 days)
            old_execution = ReportExecution.objects.create(
                report=self.report,
                trigger_type="MANUAL",
                output_format="PDF",
                status="COMPLETED",
                completed_at=timezone.now() - timedelta(days=35),
                result_file_path=old_file.name,
                executed_by=self.user,
            )

            # Create recent execution with file (should not be deleted)
            ReportExecution.objects.create(
                report=self.report,
                trigger_type="MANUAL",
                output_format="PDF",
                status="COMPLETED",
                completed_at=timezone.now() - timedelta(days=15),
                result_file_path=recent_file.name,
                executed_by=self.user,
            )

            # Verify files exist before cleanup
            self.assertTrue(os.path.exists(old_file.name))
            self.assertTrue(os.path.exists(recent_file.name))

            # Run cleanup task
            result = cleanup_old_report_files(days_to_keep=30)

            # Verify old file was deleted
            self.assertFalse(os.path.exists(old_file.name))

            # Verify recent file was kept
            self.assertTrue(os.path.exists(recent_file.name))

            # Verify execution record was updated
            old_execution.refresh_from_db()
            self.assertEqual(old_execution.result_file_path, "")

            # Verify result message
            self.assertIn("Deleted", result)
            self.assertIn("old report files", result)

        finally:
            # Clean up remaining files
            for file_path in [old_file.name, recent_file.name]:
                if os.path.exists(file_path):
                    os.unlink(file_path)

    def test_schedule_next_run_update_task(self):
        """Test schedule next run update task."""
        from apps.reporting.models import ReportSchedule
        from apps.reporting.tasks import update_schedule_next_runs

        # Create test schedule
        schedule = ReportSchedule.objects.create(
            report=self.report,
            name="Test Schedule",
            frequency="DAILY",
            start_date=timezone.now() - timedelta(days=1),
            next_run_at=None,  # No next run set
            email_recipients=["test@example.com"],
            created_by=self.user,
        )

        # Run update task
        result = update_schedule_next_runs()

        # Verify schedule was updated
        schedule.refresh_from_db()
        self.assertIsNotNone(schedule.next_run_at)

        # Verify result message
        self.assertIn("Updated next run times", result)


class ReportUsageStatsTests(TestCase):
    """Test report usage statistics generation."""

    def setUp(self):
        """Set up test data."""
        import uuid

        from django.contrib.auth import get_user_model

        from apps.core.models import Tenant
        from apps.core.tenant_context import bypass_rls, tenant_context

        User = get_user_model()

        # Create test tenant and user using RLS bypass
        unique_id = str(uuid.uuid4())[:8]

        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Stats Test Shop", slug=f"stats-test-{unique_id}", status="ACTIVE"
            )

            self.user = User.objects.create_user(
                username=f"statsuser-{unique_id}",
                email=f"stats-{unique_id}@example.com",
                tenant=self.tenant,
                role="TENANT_OWNER",
            )

        # Create test report category within tenant context
        with tenant_context(self.tenant.id):
            self.category = ReportCategory.objects.create(
                name="Stats Reports", category_type="SALES"
            )

    def test_usage_stats_generation(self):
        """Test usage statistics generation task."""
        from apps.reporting.models import Report, ReportExecution
        from apps.reporting.tasks import generate_report_usage_stats

        # Create test reports
        popular_report = Report.objects.create(
            tenant=self.tenant, name="Popular Report", category=self.category, created_by=self.user
        )

        unpopular_report = Report.objects.create(
            tenant=self.tenant,
            name="Unpopular Report",
            category=self.category,
            created_by=self.user,
        )

        # Create executions for the last week
        week_ago = timezone.now() - timedelta(days=7)

        # Popular report executions
        for i in range(5):
            ReportExecution.objects.create(
                report=popular_report,
                trigger_type="MANUAL",
                output_format="PDF",
                status="COMPLETED",
                started_at=week_ago + timedelta(days=i),
                row_count=100 + i,
                executed_by=self.user,
            )

        # Unpopular report execution
        ReportExecution.objects.create(
            report=unpopular_report,
            trigger_type="MANUAL",
            output_format="PDF",
            status="COMPLETED",
            started_at=week_ago + timedelta(days=1),
            row_count=50,
            executed_by=self.user,
        )

        # Create old execution (should not be included)
        ReportExecution.objects.create(
            report=popular_report,
            trigger_type="MANUAL",
            output_format="PDF",
            status="COMPLETED",
            started_at=timezone.now() - timedelta(days=10),
            executed_by=self.user,
        )

        # Run stats generation task
        result = generate_report_usage_stats()

        # Verify result message
        self.assertIn("Generated usage stats", result)
        self.assertIn("6 executions", result)  # 5 + 1 from last week


class ReportViewIntegrationTests(TestCase):
    """Integration tests for report views."""

    def setUp(self):
        """Set up test data."""
        import uuid

        from django.contrib.auth import get_user_model

        from apps.core.models import Tenant
        from apps.core.tenant_context import bypass_rls, tenant_context

        User = get_user_model()

        # Create test tenant and user using RLS bypass
        unique_id = str(uuid.uuid4())[:8]

        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="View Test Shop", slug=f"view-test-{unique_id}", status="ACTIVE"
            )

            self.user = User.objects.create_user(
                username=f"viewuser-{unique_id}",
                email=f"view-{unique_id}@example.com",
                tenant=self.tenant,
                role="TENANT_OWNER",
            )

        # Create test report category and report within tenant context
        with tenant_context(self.tenant.id):
            self.category = ReportCategory.objects.create(
                name="View Reports", category_type="SALES"
            )

            self.report = Report.objects.create(
                tenant=self.tenant,
                name="View Test Report",
                category=self.category,
                report_type="PREDEFINED",
                query_config={"report_name": "sales_summary"},
                created_by=self.user,
                is_public=True,
            )

    def test_report_list_view_context(self):
        """Test report list view context data."""
        from django.test import RequestFactory

        from apps.reporting.views import ReportListView

        factory = RequestFactory()
        request = factory.get("/reports/")
        request.user = self.user

        view = ReportListView()
        view.request = request

        # Test queryset
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().name, "View Test Report")

        # Test context data
        context = view.get_context_data()
        self.assertIn("categories", context)

    def test_prebuilt_reports_view_context(self):
        """Test prebuilt reports view context data."""
        from django.test import RequestFactory

        from apps.reporting.views import PrebuiltReportsView

        factory = RequestFactory()
        request = factory.get("/reports/prebuilt/")
        request.user = self.user

        view = PrebuiltReportsView()
        view.request = request

        # Test context data
        context = view.get_context_data()
        self.assertIn("categories", context)

        # Verify categories contain expected reports
        categories = context["categories"]
        self.assertIn("SALES", categories)
        self.assertIn("INVENTORY", categories)
        self.assertIn("FINANCIAL", categories)
        self.assertIn("CUSTOMER", categories)

        # Verify each category has reports
        for category_name, reports in categories.items():
            self.assertGreater(len(reports), 0)
            for report in reports:
                self.assertIn("id", report)
                self.assertIn("name", report)
                self.assertIn("description", report)

    def test_report_dashboard_view_statistics(self):
        """Test report dashboard view statistics calculation."""
        from django.test import RequestFactory

        from apps.reporting.models import ReportExecution, ReportSchedule
        from apps.reporting.views import ReportDashboardView

        # Create additional test data
        ReportSchedule.objects.create(
            report=self.report,
            name="Test Schedule",
            frequency="DAILY",
            status="ACTIVE",
            email_recipients=["test@example.com"],
            created_by=self.user,
        )

        execution = ReportExecution.objects.create(
            report=self.report,
            trigger_type="MANUAL",
            output_format="PDF",
            status="COMPLETED",
            row_count=100,
            executed_by=self.user,
        )

        factory = RequestFactory()
        request = factory.get("/reports/dashboard/")
        request.user = self.user

        view = ReportDashboardView()
        view.request = request

        # Test context data
        context = view.get_context_data()

        # Verify statistics
        self.assertEqual(context["total_reports"], 1)
        self.assertEqual(context["active_schedules"], 1)
        self.assertEqual(context["executions_last_30_days"], 1)
        self.assertEqual(context["successful_executions"], 1)
        self.assertEqual(context["failed_executions"], 0)

        # Verify recent executions
        self.assertEqual(len(context["recent_executions"]), 1)
        self.assertEqual(context["recent_executions"][0].id, execution.id)

        # Verify popular reports
        self.assertEqual(len(context["popular_reports"]), 1)

        # Verify prebuilt categories
        self.assertIn("prebuilt_categories", context)
        prebuilt_categories = context["prebuilt_categories"]
        self.assertIn("SALES", prebuilt_categories)
        self.assertIn("INVENTORY", prebuilt_categories)
        self.assertIn("FINANCIAL", prebuilt_categories)
        self.assertIn("CUSTOMER", prebuilt_categories)
