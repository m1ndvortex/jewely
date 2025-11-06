"""
Script to generate test data for performance testing.

This script creates sample data to ensure meaningful performance tests:
- Test users and tenants
- Inventory items
- Customers
- Sales transactions
- Accounting entries

Run with: docker compose exec web python tests/performance/test_data_setup.py
"""

import os
import random
import sys
from datetime import datetime, timedelta
from decimal import Decimal

import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

from apps.core.models import Branch, Tenant  # noqa: E402
from apps.crm.models import Customer, LoyaltyTier  # noqa: E402
from apps.inventory.models import InventoryItem, ProductCategory  # noqa: E402
from apps.sales.models import Sale, SaleItem, Terminal  # noqa: E402

User = get_user_model()


def create_test_tenant():
    """Create or get test tenant."""
    tenant, created = Tenant.objects.get_or_create(
        slug="test-performance",
        defaults={"company_name": "Performance Test Jewelry Shop", "status": "ACTIVE"},
    )
    if created:
        print(f"✓ Created test tenant: {tenant.company_name}")
    else:
        print(f"✓ Using existing tenant: {tenant.company_name}")
    return tenant


def create_test_user(tenant):
    """Create or get test user."""
    user, created = User.objects.get_or_create(
        username="testuser@example.com",
        email="testuser@example.com",
        defaults={"tenant": tenant, "role": "TENANT_OWNER", "language": "en", "theme": "light"},
    )
    if created:
        user.set_password("TestPassword123!")
        user.save()
        print(f"✓ Created test user: {user.username}")
    else:
        print(f"✓ Using existing user: {user.username}")
    return user


def create_test_branch(tenant):
    """Create or get test branch."""
    branch, created = Branch.objects.get_or_create(
        tenant=tenant,
        name="Main Branch",
        defaults={
            "address": "123 Test Street",
            "phone": "+1234567890",
            "is_active": True,
            "opening_hours": {
                "monday": "09:00-18:00",
                "tuesday": "09:00-18:00",
                "wednesday": "09:00-18:00",
                "thursday": "09:00-18:00",
                "friday": "09:00-18:00",
                "saturday": "10:00-16:00",
                "sunday": "closed",
            },
        },
    )
    if created:
        print(f"✓ Created test branch: {branch.name}")
    else:
        print(f"✓ Using existing branch: {branch.name}")
    return branch


def create_test_terminal(branch):
    """Create or get test terminal."""
    terminal, created = Terminal.objects.get_or_create(
        branch=branch, terminal_id="POS-001", defaults={"is_active": True}
    )
    if created:
        print(f"✓ Created test terminal: {terminal.terminal_id}")
    else:
        print(f"✓ Using existing terminal: {terminal.terminal_id}")
    return terminal


def create_product_categories(tenant):
    """Create product categories."""
    categories = [
        "Rings",
        "Necklaces",
        "Bracelets",
        "Earrings",
        "Pendants",
        "Chains",
        "Bangles",
        "Anklets",
    ]

    created_categories = []
    for cat_name in categories:
        category, created = ProductCategory.objects.get_or_create(tenant=tenant, name=cat_name)
        created_categories.append(category)

    print(f"✓ Created/verified {len(created_categories)} product categories")
    return created_categories


def create_inventory_items(tenant, branch, categories, count=500):
    """Create inventory items."""
    existing_count = InventoryItem.objects.filter(tenant=tenant).count()

    if existing_count >= count:
        print(f"✓ Already have {existing_count} inventory items")
        return

    items_to_create = count - existing_count
    karats = [10, 14, 18, 22, 24]

    for i in range(items_to_create):
        category = random.choice(categories)
        karat = random.choice(karats)
        weight = Decimal(random.uniform(1.0, 50.0)).quantize(Decimal("0.001"))
        cost = Decimal(random.uniform(100, 5000)).quantize(Decimal("0.01"))
        markup = Decimal(random.uniform(1.2, 2.0))

        InventoryItem.objects.create(
            tenant=tenant,
            sku=f"SKU-{existing_count + i + 1:06d}",
            name=f"{category.name} {karat}K Gold",
            category=category,
            karat=karat,
            weight_grams=weight,
            cost_price=cost,
            selling_price=cost * markup,
            quantity=random.randint(1, 20),
            branch=branch,
            is_active=True,
        )

    print(f"✓ Created {items_to_create} inventory items (total: {count})")


def create_loyalty_tiers(tenant):
    """Create loyalty tiers."""
    tiers = [("Bronze", 0, 5), ("Silver", 1000, 10), ("Gold", 5000, 15), ("Platinum", 10000, 20)]

    for name, min_spending, discount in tiers:
        LoyaltyTier.objects.get_or_create(
            tenant=tenant,
            name=name,
            defaults={
                "min_spending": Decimal(min_spending),
                "discount_percentage": Decimal(discount),
                "points_multiplier": Decimal("1.0"),
            },
        )

    print(f"✓ Created/verified {len(tiers)} loyalty tiers")


def create_customers(tenant, count=200):
    """Create customer records."""
    existing_count = Customer.objects.filter(tenant=tenant).count()

    if existing_count >= count:
        print(f"✓ Already have {existing_count} customers")
        return

    items_to_create = count - existing_count
    # Get actual LoyaltyTier instances
    tiers = list(LoyaltyTier.objects.filter(tenant=tenant))

    if not tiers:
        print("⚠ No loyalty tiers found, creating customers without tiers")
        tiers = [None]

    for i in range(items_to_create):
        Customer.objects.create(
            tenant=tenant,
            customer_number=f"CUST-{existing_count + i + 1:06d}",
            first_name=f"Customer{existing_count + i + 1}",
            last_name="Test",
            email=f"customer{existing_count + i + 1}@test.com",
            phone=f"+1234567{existing_count + i + 1:04d}",
            loyalty_tier=random.choice(tiers),
            loyalty_points=random.randint(0, 1000),
            store_credit=Decimal(random.uniform(0, 500)).quantize(Decimal("0.01")),
            total_purchases=Decimal(random.uniform(0, 10000)).quantize(Decimal("0.01")),
        )

    print(f"✓ Created {items_to_create} customers (total: {count})")


def create_sales(tenant, branch, terminal, user, count=100):
    """Create sales transactions."""
    existing_count = Sale.objects.filter(tenant=tenant).count()

    if existing_count >= count:
        print(f"✓ Already have {existing_count} sales")
        return

    items_to_create = count - existing_count
    customers = list(Customer.objects.filter(tenant=tenant)[:50])
    inventory_items = list(InventoryItem.objects.filter(tenant=tenant, quantity__gt=0)[:100])

    if not customers or not inventory_items:
        print("⚠ Need customers and inventory items to create sales")
        return

    for i in range(items_to_create):
        customer = random.choice(customers) if random.random() > 0.3 else None

        # Create sale
        sale = Sale.objects.create(
            tenant=tenant,
            sale_number=f"SALE-{existing_count + i + 1:08d}",
            customer=customer,
            branch=branch,
            terminal=terminal,
            employee=user,
            subtotal=Decimal("0"),
            tax=Decimal("0"),
            discount=Decimal("0"),
            total=Decimal("0"),
            payment_method=random.choice(["CASH", "CARD", "SPLIT"]),
            status="COMPLETED",
            created_at=datetime.now() - timedelta(days=random.randint(0, 90)),
        )

        # Add 1-3 items to sale
        num_items = random.randint(1, 3)
        subtotal = Decimal("0")

        for _ in range(num_items):
            item = random.choice(inventory_items)
            quantity = 1
            unit_price = item.selling_price
            item_subtotal = unit_price * quantity

            SaleItem.objects.create(
                sale=sale,
                inventory_item=item,
                quantity=quantity,
                unit_price=unit_price,
                subtotal=item_subtotal,
            )

            subtotal += item_subtotal

        # Update sale totals
        tax = subtotal * Decimal("0.1")  # 10% tax
        total = subtotal + tax

        sale.subtotal = subtotal
        sale.tax = tax
        sale.total = total
        sale.save()

    print(f"✓ Created {items_to_create} sales (total: {count})")


def main():
    """Main setup function."""
    print("\n" + "=" * 60)
    print("Performance Test Data Setup")
    print("=" * 60 + "\n")

    # Create test data
    tenant = create_test_tenant()
    user = create_test_user(tenant)
    branch = create_test_branch(tenant)
    terminal = create_test_terminal(branch)
    categories = create_product_categories(tenant)
    create_inventory_items(tenant, branch, categories, count=500)
    create_loyalty_tiers(tenant)
    create_customers(tenant, count=200)
    create_sales(tenant, branch, terminal, user, count=100)

    print("\n" + "=" * 60)
    print("✓ Test data setup complete!")
    print("=" * 60 + "\n")

    print("You can now run performance tests with:")
    print("  docker compose exec web locust -f tests/performance/locustfile.py")
    print("\nOr with web UI:")
    print(
        "  docker compose exec web locust -f tests/performance/locustfile.py --host=http://localhost:8000"
    )
    print()


if __name__ == "__main__":
    main()
