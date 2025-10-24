"""
Management command to create test data for dashboard testing.
"""

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import Branch, Tenant, User
from apps.crm.models import Customer, LoyaltyTier
from apps.inventory.models import InventoryItem, ProductCategory
from apps.repair.models import RepairOrder
from apps.sales.models import Sale, SaleItem, Terminal


class Command(BaseCommand):
    help = "Create test data for dashboard functionality"

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-name", type=str, default="Test Jewelry Shop", help="Name of the test tenant"
        )

    def handle(self, *args, **options):
        from apps.core.tenant_context import bypass_rls

        tenant_name = options["tenant_name"]

        # Create or get tenant (bypass RLS for management command)
        with bypass_rls():
            tenant = self._create_tenant(tenant_name)
            branch = self._create_branch(tenant)
            terminal = self._create_terminal(branch)
            user = self._create_user(tenant, branch)
            categories = self._create_categories(tenant)
            inventory_items = self._create_inventory_items(tenant, branch, categories)
            customers = self._create_customers(tenant)
            sales_created = self._create_sales(tenant, branch, terminal, user, inventory_items)
            repair_orders_created = self._create_repair_orders(tenant, customers)

        self._print_summary(
            tenant,
            branch,
            categories,
            inventory_items,
            customers,
            sales_created,
            repair_orders_created,
        )

    def _create_tenant(self, tenant_name):
        """Create or get tenant."""
        tenant, created = Tenant.objects.get_or_create(
            company_name=tenant_name,
            defaults={"slug": tenant_name.lower().replace(" ", "-"), "status": "ACTIVE"},
        )

        if created:
            self.stdout.write(f"Created tenant: {tenant.company_name}")
        else:
            self.stdout.write(f"Using existing tenant: {tenant.company_name}")

        return tenant

    def _create_branch(self, tenant):
        """Create branch."""
        branch, created = Branch.objects.get_or_create(
            tenant=tenant,
            name="Main Branch",
            defaults={
                "address": "123 Main St, City, State 12345",
                "phone": "+1-555-0123",
                "opening_hours": {
                    "monday": {"open": "09:00", "close": "18:00"},
                    "tuesday": {"open": "09:00", "close": "18:00"},
                    "wednesday": {"open": "09:00", "close": "18:00"},
                    "thursday": {"open": "09:00", "close": "18:00"},
                    "friday": {"open": "09:00", "close": "18:00"},
                    "saturday": {"open": "10:00", "close": "16:00"},
                    "sunday": {"closed": True},
                },
            },
        )
        return branch

    def _create_terminal(self, branch):
        """Create terminal."""
        terminal, created = Terminal.objects.get_or_create(
            branch=branch, terminal_id="POS-001", defaults={"is_active": True}
        )
        return terminal

    def _create_user(self, tenant, branch):
        """Create user."""
        user, created = User.objects.get_or_create(
            username="testowner",
            defaults={
                "email": "owner@testshop.com",
                "first_name": "Test",
                "last_name": "Owner",
                "tenant": tenant,
                "branch": branch,
                "role": "TENANT_OWNER",
            },
        )
        if created:
            user.set_password("testpass123")
            user.save()
        return user

    def _create_categories(self, tenant):
        """Create product categories."""
        categories = ["Rings", "Necklaces", "Bracelets", "Earrings", "Watches"]
        category_objects = []
        for cat_name in categories:
            category, created = ProductCategory.objects.get_or_create(tenant=tenant, name=cat_name)
            category_objects.append(category)
        return category_objects

    def _create_inventory_items(self, tenant, branch, categories):
        """Create inventory items."""
        inventory_items = []
        for i, category in enumerate(categories):
            for j in range(5):  # 5 items per category
                item, created = InventoryItem.objects.get_or_create(
                    tenant=tenant,
                    sku=f"{category.name.upper()}-{j+1:03d}",
                    defaults={
                        "name": f"{category.name[:-1]} #{j+1}",
                        "category": category,
                        "karat": 18 if i % 2 == 0 else 24,
                        "weight_grams": Decimal(f"{5 + j}.{i}"),
                        "cost_price": Decimal(f"{100 + i*50 + j*10}"),
                        "selling_price": Decimal(f"{150 + i*75 + j*15}"),
                        "quantity": 10 - j,
                        "min_quantity": 2,
                        "branch": branch,
                    },
                )
                if created:
                    inventory_items.append(item)
        return inventory_items

    def _create_customers(self, tenant):
        """Create customers."""
        # Create loyalty tier first
        bronze_tier, created = LoyaltyTier.objects.get_or_create(
            tenant=tenant,
            name="Bronze",
            defaults={
                "min_spending": Decimal("0"),
                "discount_percentage": Decimal("0"),
                "points_multiplier": Decimal("1.0"),
            },
        )

        customers = []
        customer_names = [("John", "Doe"), ("Jane", "Smith"), ("Bob", "Johnson")]

        for first_name, last_name in customer_names:
            customer, created = Customer.objects.get_or_create(
                tenant=tenant,
                email=f"{first_name.lower()}.{last_name.lower()}@example.com",
                defaults={
                    "customer_number": f"CUST-{len(customers)+1:04d}",
                    "first_name": first_name,
                    "last_name": last_name,
                    "phone": f"+1-555-{1000 + len(customers):04d}",
                    "loyalty_tier": bronze_tier,
                    "loyalty_points": 100 * (len(customers) + 1),
                },
            )
            if created:
                customers.append(customer)
        return customers

    def _create_sales(self, tenant, branch, terminal, user, inventory_items):
        """Create sales for the last 30 days."""
        sales_created = 0
        for days_ago in range(30):
            date = timezone.now() - timedelta(days=days_ago)
            num_sales = max(1, 5 - (days_ago // 10))

            for sale_num in range(num_sales):
                sale_number = f"SALE-{date.strftime('%Y%m%d')}-{sale_num+1:03d}"

                if Sale.objects.filter(tenant=tenant, sale_number=sale_number).exists():
                    continue

                sale = Sale.objects.create(
                    tenant=tenant,
                    sale_number=sale_number,
                    customer=None,
                    branch=branch,
                    terminal=terminal,
                    employee=user,
                    subtotal=Decimal("0"),
                    tax=Decimal("0"),
                    discount=Decimal("0"),
                    total=Decimal("0"),
                    payment_method="cash" if sale_num % 2 == 0 else "card",
                    status=Sale.COMPLETED,
                    created_at=date,
                )

                # Add items to sale
                if inventory_items:
                    item = inventory_items[sale_num % len(inventory_items)]
                    unit_price = item.selling_price
                    subtotal = unit_price

                    SaleItem.objects.create(
                        sale=sale,
                        inventory_item=item,
                        quantity=1,
                        unit_price=unit_price,
                        subtotal=subtotal,
                    )

                    sale.subtotal = subtotal
                    sale.tax = subtotal * Decimal("0.08")
                    sale.total = sale.subtotal + sale.tax
                    sale.save()

                    sales_created += 1

        return sales_created

    def _create_repair_orders(self, tenant, customers):
        """Create repair orders."""
        repair_orders_created = 0
        for i in range(5):
            if customers:
                customer = customers[i % len(customers)]

                RepairOrder.objects.get_or_create(
                    tenant=tenant,
                    order_number=f"REP-{timezone.now().strftime('%Y%m%d')}-{i+1:03d}",
                    defaults={
                        "customer": customer,
                        "item_description": f"Gold ring repair #{i+1}",
                        "service_type": "REPAIR",
                        "status": ["received", "in_progress", "quality_check"][i % 3],
                        "estimated_completion": timezone.now().date() + timedelta(days=7),
                        "cost_estimate": Decimal(f"{50 + i*10}"),
                    },
                )
                repair_orders_created += 1

        return repair_orders_created

    def _print_summary(
        self,
        tenant,
        branch,
        categories,
        inventory_items,
        customers,
        sales_created,
        repair_orders_created,
    ):
        """Print summary of created data."""
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created test data:\n"
                f"- Tenant: {tenant.company_name}\n"
                f"- Branch: {branch.name}\n"
                f"- Categories: {len(categories)}\n"
                f"- Inventory Items: {len(inventory_items)}\n"
                f"- Customers: {len(customers)}\n"
                f"- Sales: {sales_created}\n"
                f"- Repair Orders: {repair_orders_created}"
            )
        )
