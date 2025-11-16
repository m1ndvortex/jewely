import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jewelry_shop.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.core.models import Tenant
from django.db import transaction

User = get_user_model()

with transaction.atomic():
    # Create or get tenant
    tenant, created = Tenant.objects.get_or_create(
        subdomain='test-tenant',
        defaults={
            'name': 'Test Tenant',
            'owner_email': 'tenant@example.com',
            'is_active': True
        }
    )
    
    # Create tenant user
    if not User.objects.filter(username='tenant_user').exists():
        tenant_user = User.objects.create_user(
            username='tenant_user',
            email='tenant@example.com',
            password='TenantPassword123!',
            is_active=True,
            tenant=tenant
        )
        print(f"✓ Created tenant user: tenant_user")
    else:
        print(f"✓ Tenant user already exists")
    
    # Create platform admin
    if not User.objects.filter(username='admin').exists():
        admin = User.objects.create_superuser(
            username='admin',
            email='admin@jewelry-shop.com',
            password='AdminPassword123!',
            is_active=True
        )
        print(f"✓ Created platform admin: admin")
    else:
        print(f"✓ Platform admin already exists")

print("\nTest users created successfully!")
