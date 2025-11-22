#!/usr/bin/env python
"""Create test tenant and user for development"""

import os
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from apps.core.models import Tenant, User
from django.contrib.auth.hashers import make_password

# Create or get test tenant
tenant, created = Tenant.objects.get_or_create(
    slug="test", defaults={"company_name": "Test Shop", "status": "active"}
)

if created:
    print(f"Created tenant: {tenant.company_name}")
else:
    print(f"Using existing tenant: {tenant.company_name}")

# Create or update admin user
user, created = User.objects.update_or_create(
    username="admin",
    defaults={
        "email": "admin@test.com",
        "password": make_password("admin123"),
        "is_staff": True,
        "is_superuser": True,
        "role": "PLATFORM_ADMIN",
        "tenant": tenant,
    },
)

if created:
    print(f"Created user: {user.username} / password: admin123")
else:
    print(f"Updated user: {user.username} / password: admin123")

print("\n✓ Setup complete!")
print(f"Login at: http://localhost:8000/accounts/login/")
print(f"Username: admin")
print(f"Password: admin123")
