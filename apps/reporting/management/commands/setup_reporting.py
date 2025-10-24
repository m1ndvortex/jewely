"""
Management command to set up initial reporting data.

Creates default report categories and sample reports.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.reporting.models import ReportCategory


class Command(BaseCommand):
    help = "Set up initial reporting data including categories and sample reports"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-reports",
            action="store_true",
            help="Skip creating sample reports, only create categories",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Setting up reporting system..."))

        with transaction.atomic():
            # Create report categories
            self.create_categories()

            if not options["skip_reports"]:
                self.create_sample_reports()

        self.stdout.write(self.style.SUCCESS("Reporting setup completed successfully!"))

    def create_categories(self):
        """Create default report categories."""
        categories = [
            {
                "name": "Sales Reports",
                "category_type": "SALES",
                "description": "Reports related to sales transactions, revenue, and performance",
                "icon": "fas fa-chart-line",
                "sort_order": 1,
            },
            {
                "name": "Inventory Reports",
                "category_type": "INVENTORY",
                "description": "Reports for inventory valuation, stock levels, and movement",
                "icon": "fas fa-boxes",
                "sort_order": 2,
            },
            {
                "name": "Financial Reports",
                "category_type": "FINANCIAL",
                "description": "Financial statements, profit & loss, and accounting reports",
                "icon": "fas fa-calculator",
                "sort_order": 3,
            },
            {
                "name": "Customer Reports",
                "category_type": "CUSTOMER",
                "description": "Customer analysis, loyalty, and relationship reports",
                "icon": "fas fa-users",
                "sort_order": 4,
            },
            {
                "name": "Employee Reports",
                "category_type": "EMPLOYEE",
                "description": "Staff performance, sales by employee, and HR reports",
                "icon": "fas fa-user-tie",
                "sort_order": 5,
            },
            {
                "name": "Custom Reports",
                "category_type": "CUSTOM",
                "description": "User-defined custom reports and analytics",
                "icon": "fas fa-cogs",
                "sort_order": 6,
            },
        ]

        for category_data in categories:
            category, created = ReportCategory.objects.get_or_create(
                category_type=category_data["category_type"], defaults=category_data
            )

            if created:
                self.stdout.write(f"Created category: {category.name}")
            else:
                self.stdout.write(f"Category already exists: {category.name}")

    def create_sample_reports(self):
        """Create sample predefined reports."""
        # Get categories
        sales_category = ReportCategory.objects.get(category_type="SALES")
        inventory_category = ReportCategory.objects.get(category_type="INVENTORY")
        financial_category = ReportCategory.objects.get(category_type="FINANCIAL")
        customer_category = ReportCategory.objects.get(category_type="CUSTOMER")

        sample_reports = [
            {
                "name": "Daily Sales Summary",
                "description": "Summary of daily sales including total revenue, number of transactions, and average sale amount",
                "category": sales_category,
                "report_type": "PREDEFINED",
                "query_config": {"report_name": "sales_summary"},
                "parameters": {
                    "date_range": {
                        "type": "DATERANGE",
                        "label": "Date Range",
                        "required": True,
                        "default": "last_30_days",
                    },
                    "branch_id": {"type": "BRANCH", "label": "Branch", "required": False},
                },
                "default_parameters": {"date_range": "last_30_days"},
                "output_formats": ["PDF", "EXCEL", "CSV"],
                "is_public": True,
                "allowed_roles": ["TENANT_OWNER", "TENANT_MANAGER"],
            },
            {
                "name": "Inventory Valuation Report",
                "description": "Current inventory valuation by category, branch, and product",
                "category": inventory_category,
                "report_type": "PREDEFINED",
                "query_config": {"report_name": "inventory_valuation"},
                "parameters": {
                    "branch_id": {"type": "BRANCH", "label": "Branch", "required": False},
                    "category_id": {
                        "type": "SELECT",
                        "label": "Product Category",
                        "required": False,
                    },
                },
                "output_formats": ["PDF", "EXCEL", "CSV"],
                "is_public": True,
                "allowed_roles": ["TENANT_OWNER", "TENANT_MANAGER"],
            },
            {
                "name": "Customer Analysis Report",
                "description": "Customer purchase behavior, loyalty tier analysis, and top customers",
                "category": customer_category,
                "report_type": "PREDEFINED",
                "query_config": {"report_name": "customer_analysis"},
                "parameters": {
                    "date_range": {
                        "type": "DATERANGE",
                        "label": "Analysis Period",
                        "required": True,
                        "default": "last_90_days",
                    }
                },
                "default_parameters": {"date_range": "last_90_days"},
                "output_formats": ["PDF", "EXCEL", "CSV"],
                "is_public": True,
                "allowed_roles": ["TENANT_OWNER", "TENANT_MANAGER"],
            },
            {
                "name": "Financial Summary",
                "description": "Revenue, expenses, and profit summary for the specified period",
                "category": financial_category,
                "report_type": "PREDEFINED",
                "query_config": {"report_name": "financial_summary"},
                "parameters": {
                    "date_range": {
                        "type": "DATERANGE",
                        "label": "Financial Period",
                        "required": True,
                        "default": "current_month",
                    }
                },
                "default_parameters": {"date_range": "current_month"},
                "output_formats": ["PDF", "EXCEL"],
                "is_public": True,
                "allowed_roles": ["TENANT_OWNER", "TENANT_MANAGER"],
            },
        ]

        self.stdout.write("Note: Sample reports are templates and need to be created per tenant.")
        self.stdout.write("Use the admin interface or API to create actual report instances.")

        for report_data in sample_reports:
            self.stdout.write(f'Sample report template: {report_data["name"]}')
