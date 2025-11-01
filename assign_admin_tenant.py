#!/usr/bin/env python
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

from apps.core.models import Tenant  # noqa: E402

User = get_user_model()

admin = User.objects.filter(username="admin").first()
tenant = Tenant.objects.first()  # Test Company

admin.tenant = tenant
admin.save()

# Refresh from database
admin.refresh_from_db()

print(f"✅ Assigned admin user to tenant: {tenant.company_name}")
print(f"Admin tenant: {admin.tenant}")
if admin.tenant:
    print(f"Admin tenant ID: {admin.tenant.id}")
else:
    print("ERROR: Tenant assignment failed!")
