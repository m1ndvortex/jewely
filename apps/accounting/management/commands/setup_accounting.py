"""
Management command to set up accounting for existing tenants.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.accounting.services import AccountingService
from apps.core.models import Tenant

User = get_user_model()


class Command(BaseCommand):
    help = "Set up accounting for existing tenants"

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-id",
            type=str,
            help="Set up accounting for specific tenant ID",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Set up accounting for all tenants without accounting",
        )

    def handle(self, *args, **options):
        if options["tenant_id"]:
            try:
                tenant = Tenant.objects.get(id=options["tenant_id"])
                self.setup_tenant_accounting(tenant)
            except Tenant.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Tenant with ID {options["tenant_id"]} not found')
                )
        elif options["all"]:
            # Find tenants without accounting setup
            tenants_without_accounting = Tenant.objects.filter(accounting_entity__isnull=True)

            if not tenants_without_accounting.exists():
                self.stdout.write(self.style.SUCCESS("All tenants already have accounting set up"))
                return

            for tenant in tenants_without_accounting:
                self.setup_tenant_accounting(tenant)
        else:
            self.stdout.write(self.style.ERROR("Please specify --tenant-id or --all"))

    def setup_tenant_accounting(self, tenant):
        """Set up accounting for a single tenant."""
        try:
            # Get tenant owner as admin user
            admin_user = User.objects.filter(tenant=tenant, role="TENANT_OWNER").first()

            if not admin_user:
                # Fallback to any user in the tenant
                admin_user = User.objects.filter(tenant=tenant).first()

            if not admin_user:
                self.stdout.write(
                    self.style.ERROR(f"No users found for tenant {tenant.company_name}")
                )
                return

            # Set up accounting
            AccountingService.setup_tenant_accounting(tenant, admin_user)

            self.stdout.write(
                self.style.SUCCESS(f"Successfully set up accounting for {tenant.company_name}")
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Failed to set up accounting for {tenant.company_name}: {str(e)}")
            )
