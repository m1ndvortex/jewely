"""
Reporting services for the jewelry shop SaaS platform.

Implements Requirement 15: Advanced Reporting and Analytics
- Report execution engine
- Parameter validation and processing
- Data export services
- Email delivery services
"""

import csv
import json
import logging
import os
import tempfile
from datetime import timedelta
from typing import Any, Dict, List, Tuple

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import connection
from django.template.loader import render_to_string
from django.utils import timezone

import openpyxl
from openpyxl.styles import Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.core.models import Tenant
from apps.reporting.models import Report, ReportExecution

logger = logging.getLogger(__name__)


class ReportParameterProcessor:
    """
    Process and validate report parameters.
    """

    def __init__(self, report: Report):
        self.report = report
        self.parameter_definitions = {
            param.name: param for param in report.parameter_definitions.all()
        }

    def validate_parameters(self, parameters: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate report parameters against their definitions.

        Args:
            parameters: Dictionary of parameter values

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Check required parameters
        for param_name, param_def in self.parameter_definitions.items():
            if param_def.is_required and param_name not in parameters:
                errors.append(f"Required parameter '{param_def.label}' is missing")
                continue

            if param_name in parameters:
                value = parameters[param_name]
                if not param_def.validate_value(value):
                    errors.append(f"Invalid value for parameter '{param_def.label}'")

        return len(errors) == 0, errors

    def process_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process parameters and apply defaults.

        Args:
            parameters: Raw parameter values

        Returns:
            Processed parameters with defaults applied
        """
        processed = parameters.copy()

        # Apply default values for missing parameters
        for param_name, param_def in self.parameter_definitions.items():
            if param_name not in processed and param_def.default_value is not None:
                processed[param_name] = param_def.default_value

        # Process date ranges
        for param_name, param_def in self.parameter_definitions.items():
            if param_def.parameter_type == "DATERANGE" and param_name in processed:
                date_range = processed[param_name]
                if isinstance(date_range, dict):
                    # Convert to proper date objects
                    if "start_date" in date_range:
                        processed[f"{param_name}_start"] = date_range["start_date"]
                    if "end_date" in date_range:
                        processed[f"{param_name}_end"] = date_range["end_date"]

        return processed


class ReportQueryEngine:
    """
    Execute report queries and return data.
    """

    def __init__(self, tenant: Tenant):
        self.tenant = tenant

    def execute_query(self, report: Report, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute a report query with parameters.

        Args:
            report: Report instance
            parameters: Processed parameters

        Returns:
            List of result rows as dictionaries
        """
        query_config = report.query_config

        if report.report_type == "PREDEFINED":
            return self._execute_predefined_report(report, parameters)
        elif report.report_type == "CUSTOM":
            return self._execute_custom_query(query_config, parameters)
        else:
            raise ValueError(f"Unsupported report type: {report.report_type}")

    def _execute_predefined_report(
        self, report: Report, parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Execute a predefined report."""
        report_name = report.query_config.get("report_name")

        if report_name == "sales_summary":
            return self._get_sales_summary(parameters)
        elif report_name == "inventory_valuation":
            return self._get_inventory_valuation(parameters)
        elif report_name == "customer_analysis":
            return self._get_customer_analysis(parameters)
        elif report_name == "financial_summary":
            return self._get_financial_summary(parameters)
        else:
            raise ValueError(f"Unknown predefined report: {report_name}")

    def _execute_custom_query(
        self, query_config: Dict[str, Any], parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Execute a custom SQL query."""
        sql_query = query_config.get("sql")
        if not sql_query:
            raise ValueError("Custom report must have SQL query")

        # Set tenant context for RLS
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('app.current_tenant', %s, false)", [str(self.tenant.id)]
            )

            # Execute the main query
            cursor.execute(sql_query, parameters)
            columns = [col[0] for col in cursor.description]
            results = []

            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))

            return results

    def _get_sales_summary(self, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get sales summary report data."""
        start_date = parameters.get("date_range_start", timezone.now() - timedelta(days=30))
        end_date = parameters.get("date_range_end", timezone.now())
        branch_id = parameters.get("branch_id")

        sql = """
        SELECT
            DATE(s.created_at) as sale_date,
            b.name as branch_name,
            COUNT(s.id) as total_sales,
            SUM(s.total) as total_amount,
            AVG(s.total) as average_sale,
            SUM(s.tax) as total_tax
        FROM sales s
        JOIN core_branches b ON s.branch_id = b.id
        WHERE s.created_at >= %s AND s.created_at <= %s
        """

        params = [start_date, end_date]

        if branch_id:
            sql += " AND s.branch_id = %s"
            params.append(branch_id)

        sql += " GROUP BY DATE(s.created_at), b.name ORDER BY sale_date DESC"

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('app.current_tenant', %s, false)", [str(self.tenant.id)]
            )
            cursor.execute(sql, params)
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def _get_inventory_valuation(self, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get inventory valuation report data."""
        branch_id = parameters.get("branch_id")
        category_id = parameters.get("category_id")

        sql = """
        SELECT
            i.sku,
            i.name,
            pc.name as category_name,
            b.name as branch_name,
            i.quantity,
            i.cost_price,
            i.selling_price,
            (i.quantity * i.cost_price) as total_cost_value,
            (i.quantity * i.selling_price) as total_selling_value,
            i.karat,
            i.weight_grams
        FROM inventory_items i
        JOIN inventory_categories pc ON i.category_id = pc.id
        JOIN core_branches b ON i.branch_id = b.id
        WHERE i.is_active = true
        """

        params = []

        if branch_id:
            sql += " AND i.branch_id = %s"
            params.append(branch_id)

        if category_id:
            sql += " AND i.category_id = %s"
            params.append(category_id)

        sql += " ORDER BY total_selling_value DESC"

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('app.current_tenant', %s, false)", [str(self.tenant.id)]
            )
            cursor.execute(sql, params)
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def _get_customer_analysis(self, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get customer analysis report data."""
        start_date = parameters.get("date_range_start", timezone.now() - timedelta(days=90))
        end_date = parameters.get("date_range_end", timezone.now())

        sql = """
        SELECT
            c.customer_number,
            c.first_name,
            c.last_name,
            c.email,
            c.phone,
            c.loyalty_tier,
            c.loyalty_points,
            c.store_credit,
            c.total_purchases,
            COUNT(s.id) as total_orders,
            COALESCE(SUM(s.total), 0) as period_spending,
            MAX(s.created_at) as last_purchase_date
        FROM crm_customers c
        LEFT JOIN sales s ON c.id = s.customer_id
            AND s.created_at >= %s AND s.created_at <= %s
        GROUP BY c.id, c.customer_number, c.first_name, c.last_name,
                 c.email, c.phone, c.loyalty_tier, c.loyalty_points,
                 c.store_credit, c.total_purchases
        ORDER BY period_spending DESC
        """

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('app.current_tenant', %s, false)", [str(self.tenant.id)]
            )
            cursor.execute(sql, [start_date, end_date])
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def _get_financial_summary(self, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get financial summary report data."""
        start_date = parameters.get("date_range_start", timezone.now() - timedelta(days=30))
        end_date = parameters.get("date_range_end", timezone.now())

        sql = """
        SELECT
            'Sales Revenue' as category,
            SUM(total - tax) as amount,
            'REVENUE' as type
        FROM sales
        WHERE created_at >= %s AND created_at <= %s
        UNION ALL
        SELECT
            'Tax Collected' as category,
            SUM(tax) as amount,
            'REVENUE' as type
        FROM sales
        WHERE created_at >= %s AND created_at <= %s
        UNION ALL
        SELECT
            'Inventory Purchases' as category,
            SUM(total_amount) as amount,
            'EXPENSE' as type
        FROM procurement_purchaseorders
        WHERE status = 'COMPLETED' AND created_at >= %s AND created_at <= %s
        ORDER BY type, amount DESC
        """

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('app.current_tenant', %s, false)", [str(self.tenant.id)]
            )
            cursor.execute(sql, [start_date, end_date, start_date, end_date, start_date, end_date])
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]


class ReportExportService:
    """
    Export report data to various formats.
    """

    def __init__(self, tenant: Tenant):
        self.tenant = tenant

    def export_to_csv(self, data: List[Dict[str, Any]], filename: str) -> str:
        """
        Export data to CSV format.

        Args:
            data: Report data
            filename: Output filename

        Returns:
            Path to the generated file
        """
        if not data:
            raise ValueError("No data to export")

        filepath = os.path.join(tempfile.gettempdir(), filename)

        with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = data[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

        return filepath

    def export_to_excel(  # noqa: C901
        self, data: List[Dict[str, Any]], filename: str, report_name: str = ""
    ) -> str:
        """
        Export data to Excel format with formatting.

        Args:
            data: Report data
            filename: Output filename
            report_name: Report name for the title

        Returns:
            Path to the generated file
        """
        if not data:
            raise ValueError("No data to export")

        filepath = os.path.join(tempfile.gettempdir(), filename)

        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = "Report Data"

        # Add title
        if report_name:
            worksheet["A1"] = report_name
            worksheet["A1"].font = Font(size=16, bold=True)
            worksheet["A2"] = f"Generated on: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
            start_row = 4
        else:
            start_row = 1

        # Add headers
        headers = list(data[0].keys())
        for col, header in enumerate(headers, 1):
            cell = worksheet.cell(row=start_row, column=col, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")

        # Add data
        for row_idx, row_data in enumerate(data, start_row + 1):
            for col_idx, header in enumerate(headers, 1):
                value = row_data.get(header, "")
                worksheet.cell(row=row_idx, column=col_idx, value=value)

        # Auto-adjust column widths
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except (TypeError, AttributeError):
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width

        workbook.save(filepath)
        return filepath

    def export_to_pdf(
        self, data: List[Dict[str, Any]], filename: str, report_name: str = ""
    ) -> str:
        """
        Export data to PDF format.

        Args:
            data: Report data
            filename: Output filename
            report_name: Report name for the title

        Returns:
            Path to the generated file
        """
        if not data:
            raise ValueError("No data to export")

        filepath = os.path.join(tempfile.gettempdir(), filename)

        doc = SimpleDocTemplate(filepath, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Add title
        if report_name:
            title = Paragraph(report_name, styles["Title"])
            story.append(title)
            story.append(Spacer(1, 12))

            subtitle = Paragraph(
                f"Generated on: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]
            )
            story.append(subtitle)
            story.append(Spacer(1, 12))

        # Prepare table data
        headers = list(data[0].keys())
        table_data = [headers]

        for row in data:
            table_data.append([str(row.get(header, "")) for header in headers])

        # Create table
        table = Table(table_data)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )

        story.append(table)
        doc.build(story)

        return filepath

    def export_to_json(self, data: List[Dict[str, Any]], filename: str) -> str:
        """
        Export data to JSON format.

        Args:
            data: Report data
            filename: Output filename

        Returns:
            Path to the generated file
        """
        if not data:
            raise ValueError("No data to export")

        filepath = os.path.join(tempfile.gettempdir(), filename)

        export_data = {
            "generated_at": timezone.now().isoformat(),
            "tenant": self.tenant.company_name,
            "row_count": len(data),
            "data": data,
        }

        with open(filepath, "w", encoding="utf-8") as jsonfile:
            json.dump(export_data, jsonfile, indent=2, default=str)

        return filepath


class ReportEmailService:
    """
    Handle email delivery of reports.
    """

    def __init__(self, tenant: Tenant):
        self.tenant = tenant

    def send_report_email(
        self,
        execution: ReportExecution,
        file_path: str,
        recipients: List[str],
        subject: str = "",
        body: str = "",
    ) -> bool:
        """
        Send report via email.

        Args:
            execution: Report execution instance
            file_path: Path to the report file
            recipients: List of email addresses
            subject: Email subject (optional)
            body: Email body (optional)

        Returns:
            True if email sent successfully
        """
        try:
            # Generate default subject and body if not provided
            if not subject:
                subject = f"Report: {execution.report.name} - {timezone.now().strftime('%Y-%m-%d')}"

            if not body:
                body = self._generate_email_body(execution)

            # Create email
            email = EmailMessage(
                subject=subject, body=body, from_email=settings.DEFAULT_FROM_EMAIL, to=recipients
            )

            # Attach report file
            if file_path and os.path.exists(file_path):
                filename = os.path.basename(file_path)
                with open(file_path, "rb") as f:
                    email.attach(filename, f.read(), self._get_content_type(filename))

            # Send email
            email.send()

            # Update execution record
            execution.email_sent = True
            execution.email_recipients = recipients
            execution.save(update_fields=["email_sent", "email_recipients"])

            logger.info(f"Report email sent successfully to {len(recipients)} recipients")
            return True

        except Exception as e:
            logger.error(f"Failed to send report email: {e}")
            return False

    def _generate_email_body(self, execution: ReportExecution) -> str:
        """Generate default email body."""
        context = {
            "tenant_name": self.tenant.company_name,
            "report_name": execution.report.name,
            "execution_date": execution.started_at.strftime("%Y-%m-%d %H:%M:%S"),
            "row_count": execution.row_count,
            "duration": execution.duration_display,
        }

        return render_to_string("reporting/email/report_delivery.txt", context)

    def _get_content_type(self, filename: str) -> str:
        """Get MIME content type for file."""
        extension = filename.lower().split(".")[-1]

        content_types = {
            "pdf": "application/pdf",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "csv": "text/csv",
            "json": "application/json",
        }

        return content_types.get(extension, "application/octet-stream")


class ReportExecutionService:
    """
    Main service for executing reports.
    """

    def __init__(self, tenant: Tenant):
        self.tenant = tenant
        self.parameter_processor = None
        self.query_engine = ReportQueryEngine(tenant)
        self.export_service = ReportExportService(tenant)
        self.email_service = ReportEmailService(tenant)

    def execute_report(
        self,
        report: Report,
        parameters: Dict[str, Any],
        output_format: str,
        user,
        email_recipients: List[str] = None,
        trigger_type: str = "MANUAL",
    ) -> ReportExecution:
        """
        Execute a report with given parameters.

        Args:
            report: Report to execute
            parameters: Report parameters
            output_format: Output format (PDF, EXCEL, CSV, JSON)
            user: User executing the report
            email_recipients: Optional email recipients
            trigger_type: How the report was triggered

        Returns:
            ReportExecution instance
        """
        # Create execution record
        execution = ReportExecution.objects.create(
            report=report,
            trigger_type=trigger_type,
            parameters=parameters,
            output_format=output_format,
            executed_by=user,
            email_recipients=email_recipients or [],
        )

        try:
            # Update status to running
            execution.status = "RUNNING"
            execution.save(update_fields=["status"])

            # Validate parameters
            self.parameter_processor = ReportParameterProcessor(report)
            is_valid, errors = self.parameter_processor.validate_parameters(parameters)

            if not is_valid:
                raise ValueError(f"Parameter validation failed: {', '.join(errors)}")

            # Process parameters
            processed_params = self.parameter_processor.process_parameters(parameters)

            # Execute query
            data = self.query_engine.execute_query(report, processed_params)

            if not data:
                logger.warning(f"Report {report.name} returned no data")

            # Generate filename
            timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{report.name.replace(' ', '_')}_{timestamp}.{output_format.lower()}"

            # Export data
            file_path = self._export_data(data, output_format, filename, report.name)

            # Get file size
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

            # Mark as completed
            execution.mark_completed(file_path, len(data))
            execution.result_file_size = file_size
            execution.save(update_fields=["result_file_size"])

            # Send email if recipients provided
            if email_recipients:
                self.email_service.send_report_email(execution, file_path, email_recipients)

            # Update report statistics
            report.increment_run_count()

            logger.info(f"Report {report.name} executed successfully: {len(data)} rows")

            return execution

        except Exception as e:
            logger.error(f"Report execution failed: {e}")
            execution.mark_failed(str(e))
            raise

    def _export_data(
        self, data: List[Dict[str, Any]], format_type: str, filename: str, report_name: str
    ) -> str:
        """Export data to the specified format."""
        if format_type == "CSV":
            return self.export_service.export_to_csv(data, filename)
        elif format_type == "EXCEL":
            return self.export_service.export_to_excel(data, filename, report_name)
        elif format_type == "PDF":
            return self.export_service.export_to_pdf(data, filename, report_name)
        elif format_type == "JSON":
            return self.export_service.export_to_json(data, filename)
        else:
            raise ValueError(f"Unsupported export format: {format_type}")
