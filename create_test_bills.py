#!/usr/bin/env python
"""Create test bills for aged payables report testing."""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model

from apps.accounting.bill_models import Bill
from apps.core.models import Tenant
from apps.procurement.models import Supplier

User = get_user_model()

# Get tenant and user
tenant = Tenant.objects.first()
user = User.objects.first()  # Get any user
supplier = Supplier.objects.first()  # Get any supplier

if not tenant or not user or not supplier:
    print("Error: Missing tenant, user, or supplier")
    print(f"Tenant: {tenant}")
    print(f"User: {user}")
    print(f"Supplier: {supplier}")
    exit(1)

print(f"Using tenant: {tenant.company_name}")
print(f"Using user: {user.username}")
print(f"Using supplier: {supplier.name}")

# Create bills with different due dates for aging buckets
today = date.today()

# Bill 1: 45 days overdue (31-60 days bucket)
bill1 = Bill.objects.create(
    tenant=tenant,
    supplier=supplier,
    bill_number="TEST-001",
    bill_date=today - timedelta(days=60),
    due_date=today - timedelta(days=45),
    subtotal=Decimal("500.00"),
    tax=Decimal("50.00"),
    total=Decimal("550.00"),
    amount_paid=Decimal("0.00"),
    status="APPROVED",
    created_by=user,
)

# Bill 2: 75 days overdue (61-90 days bucket)
bill2 = Bill.objects.create(
    tenant=tenant,
    supplier=supplier,
    bill_number="TEST-002",
    bill_date=today - timedelta(days=90),
    due_date=today - timedelta(days=75),
    subtotal=Decimal("1000.00"),
    tax=Decimal("100.00"),
    total=Decimal("1100.00"),
    amount_paid=Decimal("0.00"),
    status="APPROVED",
    created_by=user,
)

# Bill 3: 120 days overdue (90+ days bucket)
bill3 = Bill.objects.create(
    tenant=tenant,
    supplier=supplier,
    bill_number="TEST-003",
    bill_date=today - timedelta(days=135),
    due_date=today - timedelta(days=120),
    subtotal=Decimal("750.00"),
    tax=Decimal("75.00"),
    total=Decimal("825.00"),
    amount_paid=Decimal("0.00"),
    status="APPROVED",
    created_by=user,
)

# Bill 4: 15 days overdue (1-30 days bucket)
bill4 = Bill.objects.create(
    tenant=tenant,
    supplier=supplier,
    bill_number="TEST-004",
    bill_date=today - timedelta(days=30),
    due_date=today - timedelta(days=15),
    subtotal=Decimal("300.00"),
    tax=Decimal("30.00"),
    total=Decimal("330.00"),
    amount_paid=Decimal("0.00"),
    status="APPROVED",
    created_by=user,
)

# Bill 5: Not overdue yet (Current bucket)
bill5 = Bill.objects.create(
    tenant=tenant,
    supplier=supplier,
    bill_number="TEST-005",
    bill_date=today - timedelta(days=5),
    due_date=today + timedelta(days=10),
    subtotal=Decimal("200.00"),
    tax=Decimal("20.00"),
    total=Decimal("220.00"),
    amount_paid=Decimal("0.00"),
    status="APPROVED",
    created_by=user,
)

print("✅ Created 5 test bills:")
print(
    "Bill 1: {} - Due {} - ${} - {} days overdue".format(
        bill1.bill_number, bill1.due_date, bill1.total, bill1.days_overdue
    )
)
print(
    f"Bill 2: {bill2.bill_number} - Due {bill2.due_date} - ${bill2.total} - {bill2.days_overdue} days overdue"
)
print(
    f"Bill 3: {bill3.bill_number} - Due {bill3.due_date} - ${bill3.total} - {bill3.days_overdue} days overdue"
)
print(
    f"Bill 4: {bill4.bill_number} - Due {bill4.due_date} - ${bill4.total} - {bill4.days_overdue} days overdue"
)
print(
    f"Bill 5: {bill5.bill_number} - Due {bill5.due_date} - ${bill5.total} - {bill5.days_overdue} days overdue"
)
