#!/usr/bin/env python
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

from apps.core.models import Tenant  # noqa: E402

User = get_user_model()

admin = User.objects.filter(username="admin").first()
print(f"Admin user: {admin.username}")
print(f"Admin tenant: {admin.tenant}")
print(f"Admin tenant ID: {admin.tenant.id if admin.tenant else None}")

print("\nAll tenants:")
for tenant in Tenant.objects.all():
    print(f"  - {tenant.company_name} (ID: {tenant.id})")
    users = User.objects.filter(tenant=tenant)
    print(f"    Users: {[u.username for u in users]}")
