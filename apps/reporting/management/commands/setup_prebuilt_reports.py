"""
Management command to set up pre-built reports.

This command creates the necessary report categories and can optionally
create report instances for all tenants.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import Tenant
from apps.reporting.models import ReportCategory
from apps.reporting.services import PrebuiltReportService


class Command(BaseCommand):
    help = "Set up pre-built reports and categories"

    def add_arguments(self, parser):
        parser.add_argument(
            "--create-instances",
            action="store_true",
            help="Create report instances for all tenants",
        )
        parser.add_argument(
            "--tenant-id",
            type=str,
            help="Create report instances for specific tenant only",
        )

    def handle(self, *args, **options):
        self.stdout.write("Setting up pre-built reports...")

        with transaction.atomic():
            # Create report categories
            self.create_categories()

            # Create report instances if requested
            if options["create_instances"]:
                if options["tenant_id"]:
                    try:
                        tenant = Tenant.objects.get(id=options["tenant_id"])
                        self.create_report_instances_for_tenant(tenant)
                    except Tenant.DoesNotExist:
                        self.stdout.write(
                            self.style.ERROR(f"Tenant {options['tenant_id']} not found")
                        )
                        return
                else:
                    self.create_report_instances_for_all_tenants()

        self.stdout.write(self.style.SUCCESS("Pre-built reports setup completed"))

    def create_categories(self):
        """Create report categories."""
        categories = [
            {
                "name": "Sales Reports",
                "category_type": "SALES",
                "description": "Sales performance and analysis reports",
                "icon": "fas fa-chart-line",
                "sort_order": 1,
            },
            {
                "name": "Inventory Reports",
                "category_type": "INVENTORY",
                "description": "Inventory valuation and movement reports",
                "icon": "fas fa-warehouse",
                "sort_order": 2,
            },
            {
                "name": "Financial Reports",
                "category_type": "FINANCIAL",
                "description": "Financial performance and accounting reports",
                "icon": "fas fa-dollar-sign",
                "sort_order": 3,
            },
            {
                "name": "Customer Reports",
                "category_type": "CUSTOMER",
                "description": "Customer analysis and loyalty reports",
                "icon": "fas fa-users",
                "sort_order": 4,
            },
            {
                "name": "Employee Reports",
                "category_type": "EMPLOYEE",
                "description": "Employee performance and activity reports",
                "icon": "fas fa-user-tie",
                "sort_order": 5,
            },
            {
                "name": "Custom Reports",
                "category_type": "CUSTOM",
                "description": "User-defined custom reports",
                "icon": "fas fa-cogs",
                "sort_order": 6,
            },
        ]

        created_count = 0
        updated_count = 0

        for category_data in categories:
            # First, try to get the preferred category (by name and type)
            try:
                category = ReportCategory.objects.get(
                    name=category_data["name"], category_type=category_data["category_type"]
                )
                # Update existing category with new data
                for key, value in category_data.items():
                    setattr(category, key, value)
                category.save()
                updated_count += 1
                self.stdout.write(f"Updated category: {category.name}")

            except ReportCategory.DoesNotExist:
                # Check if there's any category with this type
                existing = ReportCategory.objects.filter(
                    category_type=category_data["category_type"]
                ).first()

                if existing:
                    # Update the existing one
                    for key, value in category_data.items():
                        setattr(existing, key, value)
                    existing.save()
                    updated_count += 1
                    self.stdout.write(f"Updated existing category: {existing.name}")
                else:
                    # Create new category
                    category = ReportCategory.objects.create(**category_data)
                    created_count += 1
                    self.stdout.write(f"Created category: {category.name}")

            except ReportCategory.MultipleObjectsReturned:
                # Handle multiple categories of same type - keep the first, update it
                categories_qs = ReportCategory.objects.filter(
                    category_type=category_data["category_type"]
                ).order_by("id")

                # Keep the first one, delete the rest
                first_category = categories_qs.first()
                categories_qs.exclude(id=first_category.id).delete()

                # Update the kept category
                for key, value in category_data.items():
                    setattr(first_category, key, value)
                first_category.save()
                updated_count += 1
                self.stdout.write(f"Cleaned up and updated category: {first_category.name}")

        self.stdout.write(
            f"Created {created_count} new categories, updated {updated_count} existing categories"
        )

    def create_report_instances_for_all_tenants(self):
        """Create report instances for all tenants."""
        tenants = Tenant.objects.filter(status="ACTIVE")
        self.stdout.write(f"Creating report instances for {tenants.count()} tenants...")

        for tenant in tenants:
            self.create_report_instances_for_tenant(tenant)

    def create_report_instances_for_tenant(self, tenant):
        """Create report instances for a specific tenant."""
        self.stdout.write(f"Creating reports for tenant: {tenant.company_name}")

        reports = PrebuiltReportService.get_prebuilt_reports()
        created_count = 0

        # Get the first admin user for this tenant as the creator
        admin_user = tenant.users.filter(role__in=["TENANT_OWNER", "TENANT_MANAGER"]).first()
        if not admin_user:
            self.stdout.write(
                self.style.WARNING(
                    f"No admin user found for tenant {tenant.company_name}, skipping"
                )
            )
            return

        for report_def in reports:
            try:
                report = PrebuiltReportService.create_prebuilt_report_instance(
                    tenant, report_def["id"], admin_user
                )
                created_count += 1
                self.stdout.write(f"  Created report: {report.name}")
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f"  Failed to create report {report_def['name']}: {str(e)}")
                )

        self.stdout.write(f"Created {created_count} reports for {tenant.company_name}")
