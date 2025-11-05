#!/usr/bin/env python
"""
Create test users for multi-portal authentication testing.
Run this inside Docker: docker compose exec web python create_test_auth_users.py
"""
import os
import django
from django.contrib.auth import get_user_model
from apps.core.models import Tenant

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

User = get_user_model()

print("=" * 80)
print("CREATING TEST USERS FOR MULTI-PORTAL AUTHENTICATION")
print("=" * 80)
print()

# Create or get platform admin
admin, created = User.objects.get_or_create(
    username="admin",
    defaults={
        "email": "admin@platform.com",
        "role": User.PLATFORM_ADMIN,
        "is_staff": True,
        "is_superuser": True,
    },
)

if created:
    admin.set_password("AdminPassword123!")
    admin.save()
    print(f"✅ Created platform admin: {admin.username}")
else:
    # Update existing admin
    admin.role = User.PLATFORM_ADMIN
    admin.is_staff = True
    admin.is_superuser = True
    admin.set_password("AdminPassword123!")
    admin.save()
    print(f"✅ Updated existing admin: {admin.username}")

print(f"   Email: {admin.email}")
print(f"   Role: {admin.role}")
print(f"   Is Platform Admin: {admin.is_platform_admin()}")
print()

# Create or get test tenant
tenant, created = Tenant.objects.get_or_create(
    slug="test-tenant",
    defaults={
        "company_name": "Test Tenant Company",
        "status": Tenant.ACTIVE,
    },
)

if created:
    print(f"✅ Created test tenant: {tenant.company_name}")
else:
    print(f"✅ Using existing tenant: {tenant.company_name}")

print(f"   Slug: {tenant.slug}")
print(f"   Status: {tenant.status}")
print()

# Create or get tenant owner
tenant_owner, created = User.objects.get_or_create(
    username="tenant_user",
    defaults={
        "email": "tenant@example.com",
        "role": User.TENANT_OWNER,
        "tenant": tenant,
    },
)

if created:
    tenant_owner.set_password("TenantPassword123!")
    tenant_owner.save()
    print(f"✅ Created tenant owner: {tenant_owner.username}")
else:
    # Update existing tenant user
    tenant_owner.role = User.TENANT_OWNER
    tenant_owner.tenant = tenant
    tenant_owner.set_password("TenantPassword123!")
    tenant_owner.save()
    print(f"✅ Updated existing tenant user: {tenant_owner.username}")

print(f"   Email: {tenant_owner.email}")
print(f"   Role: {tenant_owner.role}")
print(f"   Tenant: {tenant_owner.tenant}")
print()

print("=" * 80)
print("TEST USER CREDENTIALS")
print("=" * 80)
print()
print("Platform Admin Portal (http://localhost:8000/platform/login/)")
print("  Username: admin")
print("  Password: AdminPassword123!")
print()
print("Tenant Portal (http://localhost:8000/accounts/login/)")
print("  Username: tenant_user")
print("  Password: TenantPassword123!")
print()
print("Django Admin (http://localhost:8000/admin/)")
print("  Username: admin")
print("  Password: AdminPassword123!")
print()
print("=" * 80)
