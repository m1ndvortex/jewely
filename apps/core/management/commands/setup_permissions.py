"""
Management command to set up permission groups for the application.

This command creates the standard permission groups for the jewelry shop SaaS platform:
- Platform Administrators
- Tenant Owners
- Tenant Managers
- Tenant Employees

Usage:
    docker-compose exec web python manage.py setup_permissions
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from apps.core.models import Branch, Tenant, User


class Command(BaseCommand):
    """
    Management command to create permission groups.
    """

    help = "Set up permission groups for role-based access control"

    def handle(self, *args, **options):
        """Execute the command."""
        self.stdout.write("Setting up permission groups...")

        # Get content types
        tenant_ct = ContentType.objects.get_for_model(Tenant)
        user_ct = ContentType.objects.get_for_model(User)
        branch_ct = ContentType.objects.get_for_model(Branch)

        # Create Platform Administrator group
        self.stdout.write("Creating Platform Administrator group...")
        platform_admin_group, created = Group.objects.get_or_create(name="Platform Administrators")

        if created:
            # Platform admins have full access to tenants and users
            platform_admin_permissions = Permission.objects.filter(
                content_type__in=[tenant_ct, user_ct, branch_ct]
            )
            platform_admin_group.permissions.set(platform_admin_permissions)
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Created Platform Administrator group with {platform_admin_permissions.count()} permissions"
                )
            )
        else:
            self.stdout.write(self.style.WARNING("Platform Administrator group already exists"))

        # Create Tenant Owner group
        self.stdout.write("Creating Tenant Owner group...")
        tenant_owner_group, created = Group.objects.get_or_create(name="Tenant Owners")

        if created:
            # Tenant owners can manage users and branches within their tenant
            tenant_owner_permissions = Permission.objects.filter(
                content_type__in=[user_ct, branch_ct],
                codename__in=[
                    "add_user",
                    "change_user",
                    "delete_user",
                    "view_user",
                    "add_branch",
                    "change_branch",
                    "delete_branch",
                    "view_branch",
                ],
            )
            tenant_owner_group.permissions.set(tenant_owner_permissions)
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Created Tenant Owner group with {tenant_owner_permissions.count()} permissions"
                )
            )
        else:
            self.stdout.write(self.style.WARNING("Tenant Owner group already exists"))

        # Create Tenant Manager group
        self.stdout.write("Creating Tenant Manager group...")
        tenant_manager_group, created = Group.objects.get_or_create(name="Tenant Managers")

        if created:
            # Tenant managers can view and change users, manage branches
            tenant_manager_permissions = Permission.objects.filter(
                content_type__in=[user_ct, branch_ct],
                codename__in=[
                    "change_user",
                    "view_user",
                    "add_branch",
                    "change_branch",
                    "view_branch",
                ],
            )
            tenant_manager_group.permissions.set(tenant_manager_permissions)
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Created Tenant Manager group with {tenant_manager_permissions.count()} permissions"
                )
            )
        else:
            self.stdout.write(self.style.WARNING("Tenant Manager group already exists"))

        # Create Tenant Employee group
        self.stdout.write("Creating Tenant Employee group...")
        tenant_employee_group, created = Group.objects.get_or_create(name="Tenant Employees")

        if created:
            # Tenant employees have view-only access to users and branches
            tenant_employee_permissions = Permission.objects.filter(
                content_type__in=[user_ct, branch_ct],
                codename__in=[
                    "view_user",
                    "view_branch",
                ],
            )
            tenant_employee_group.permissions.set(tenant_employee_permissions)
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Created Tenant Employee group with {tenant_employee_permissions.count()} permissions"
                )
            )
        else:
            self.stdout.write(self.style.WARNING("Tenant Employee group already exists"))

        self.stdout.write(self.style.SUCCESS("\n✓ Permission groups setup complete!"))
        self.stdout.write("\nCreated groups:")
        self.stdout.write("  - Platform Administrators (full access)")
        self.stdout.write("  - Tenant Owners (manage users and branches)")
        self.stdout.write("  - Tenant Managers (limited user and branch management)")
        self.stdout.write("  - Tenant Employees (view-only access)")
