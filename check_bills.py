#!/usr/bin/env python
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.accounting.bill_models import Bill  # noqa: E402

bills = Bill.objects.all()
print(f"Total bills: {bills.count()}")
for bill in bills:
    print(
        f"  - {bill.bill_number}: Status={bill.status}, Tenant={bill.tenant.company_name}, Amount Due=${bill.amount_due}"
    )
