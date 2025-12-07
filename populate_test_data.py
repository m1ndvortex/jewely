#!/usr/bin/env python
"""
Populate test data for jewelry shop system.
Creates realistic data for categories, items, customers, sales, etc.
"""

import os
import random
import sys
from datetime import datetime, timedelta
from decimal import Decimal

import django

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from faker import Faker

from apps.core.models import Branch, Tenant
from apps.crm.models import Customer, LoyaltyTier
from apps.inventory.models import InventoryItem, ProductCategory

User = get_user_model()
fake = Faker()


class DataPopulator:
    """Populates test data for the jewelry shop."""

    def __init__(self, tenant_slug="test"):
        """Initialize with tenant."""
        try:
            self.tenant = Tenant.objects.get(slug=tenant_slug)
            print(f"✅ Using tenant: {self.tenant.company_name} ({tenant_slug})")
        except Tenant.DoesNotExist:
            print(f"❌ Tenant not found with slug: {tenant_slug}")
            sys.exit(1)

        # Get or create main branch
        self.branch = Branch.objects.filter(tenant=self.tenant).first()
        if not self.branch:
            print("❌ No branch found for this tenant")
            sys.exit(1)
        print(f"✅ Using branch: {self.branch.name}")

    def create_categories(self):
        """Create product categories."""
        print("\n📁 Creating product categories...")

        categories_data = [
            {
                "name": "Rings",
                "description": "Gold and diamond rings",
                "subcategories": [
                    "Engagement Rings",
                    "Wedding Bands",
                    "Fashion Rings",
                    "Statement Rings",
                ],
            },
            {
                "name": "Necklaces",
                "description": "Gold chains and pendant necklaces",
                "subcategories": [
                    "Gold Chains",
                    "Pendant Necklaces",
                    "Chokers",
                    "Statement Necklaces",
                ],
            },
            {
                "name": "Bracelets",
                "description": "Gold and diamond bracelets",
                "subcategories": [
                    "Bangles",
                    "Chain Bracelets",
                    "Charm Bracelets",
                    "Tennis Bracelets",
                ],
            },
            {
                "name": "Earrings",
                "description": "Various styles of earrings",
                "subcategories": ["Studs", "Hoops", "Drop Earrings", "Chandelier Earrings"],
            },
            {
                "name": "Watches",
                "description": "Luxury and designer watches",
                "subcategories": ["Men's Watches", "Women's Watches", "Unisex Watches"],
            },
            {
                "name": "Gemstones",
                "description": "Loose gemstones",
                "subcategories": ["Diamonds", "Rubies", "Sapphires", "Emeralds", "Semi-Precious"],
            },
        ]

        created_categories = {}

        for cat_data in categories_data:
            # Create parent category
            parent_cat, created = ProductCategory.objects.get_or_create(
                tenant=self.tenant,
                name=cat_data["name"],
                defaults={
                    "description": cat_data["description"],
                    "is_active": True,
                    "display_order": len(created_categories),
                },
            )
            created_categories[cat_data["name"]] = parent_cat

            if created:
                print(f"  ✓ Created category: {cat_data['name']}")

            # Create subcategories
            for idx, subcat_name in enumerate(cat_data.get("subcategories", [])):
                subcat, created = ProductCategory.objects.get_or_create(
                    tenant=self.tenant,
                    name=subcat_name,
                    parent=parent_cat,
                    defaults={
                        "is_active": True,
                        "display_order": idx,
                    },
                )
                created_categories[subcat_name] = subcat

                if created:
                    print(f"    ✓ Created subcategory: {subcat_name}")

        return created_categories

    def create_inventory_items(self, categories, count=50):
        """Create inventory items."""
        print(f"\n💍 Creating {count} inventory items...")

        items_data = {
            "Engagement Rings": [
                ("Solitaire Diamond Ring", 18, "1.5", "HANDMADE", 15000, 25000),
                ("Halo Diamond Ring", 18, "2.2", "HANDMADE", 20000, 35000),
                ("Three Stone Diamond Ring", 18, "2.8", "HANDMADE", 25000, 42000),
            ],
            "Wedding Bands": [
                ("Classic Gold Band", 22, "3.5", "MACHINE_MADE", 3500, 5500),
                ("Diamond Eternity Band", 18, "2.1", "SEMI_HANDMADE", 12000, 18000),
                ("Engraved Wedding Band", 22, "4.2", "HANDMADE", 4500, 7000),
            ],
            "Gold Chains": [
                ("Rope Chain Necklace", 22, "15.5", "MACHINE_MADE", 12000, 18000),
                ("Box Chain Necklace", 18, "8.3", "MACHINE_MADE", 6500, 10000),
                ("Figaro Chain", 22, "12.8", "MACHINE_MADE", 10000, 15000),
            ],
            "Pendant Necklaces": [
                ("Diamond Pendant", 18, "5.2", "HANDMADE", 8000, 14000),
                ("Heart Pendant", 22, "3.8", "SEMI_HANDMADE", 3500, 6000),
                ("Cross Pendant", 18, "4.5", "HANDMADE", 5000, 8500),
            ],
            "Bangles": [
                ("Plain Gold Bangle", 22, "25.0", "MACHINE_MADE", 20000, 30000),
                ("Diamond Bangle", 18, "18.5", "HANDMADE", 35000, 55000),
                ("Carved Gold Bangle", 22, "22.0", "SEMI_HANDMADE", 18000, 28000),
            ],
            "Studs": [
                ("Diamond Studs 0.5ct", 18, "1.2", "MACHINE_MADE", 8000, 13000),
                ("Diamond Studs 1ct", 18, "1.8", "MACHINE_MADE", 15000, 24000),
                ("Gold Ball Studs", 22, "2.5", "MACHINE_MADE", 2000, 3500),
            ],
            "Hoops": [
                ("Small Gold Hoops", 22, "3.2", "MACHINE_MADE", 2500, 4000),
                ("Large Gold Hoops", 22, "5.5", "MACHINE_MADE", 4500, 7000),
                ("Diamond Hoops", 18, "4.8", "SEMI_HANDMADE", 12000, 19000),
            ],
        }

        created_items = []
        sku_counter = 1000

        for category_name, items in items_data.items():
            if category_name not in categories:
                continue

            category = categories[category_name]

            for name, karat, weight, craftsmanship, cost, price in items:
                # Create multiple quantities
                for i in range(random.randint(2, 5)):
                    sku = f"JWL-{sku_counter:05d}"
                    sku_counter += 1

                    item = InventoryItem.objects.create(
                        tenant=self.tenant,
                        branch=self.branch,
                        sku=sku,
                        name=name,
                        category=category,
                        description=f"Beautiful {name.lower()} crafted with precision",
                        karat=karat,
                        weight_grams=Decimal(weight),
                        craftsmanship_level=craftsmanship,
                        cost_price=Decimal(cost),
                        selling_price=Decimal(price),
                        markup_percentage=Decimal((price - cost) / cost * 100),
                        quantity=random.randint(1, 10),
                        min_quantity=2,
                        is_active=True,
                    )
                    created_items.append(item)

        print(f"  ✓ Created {len(created_items)} inventory items")
        return created_items

    def create_loyalty_tiers(self):
        """Create loyalty tiers."""
        print("\n🏆 Creating loyalty tiers...")

        tiers_data = [
            {
                "name": "Bronze",
                "min_spending": Decimal("0.00"),
                "discount_percentage": Decimal("2.0"),
                "points_multiplier": Decimal("1.0"),
                "order": 0,
            },
            {
                "name": "Silver",
                "min_spending": Decimal("50000.00"),
                "discount_percentage": Decimal("5.0"),
                "points_multiplier": Decimal("1.25"),
                "order": 1,
            },
            {
                "name": "Gold",
                "min_spending": Decimal("150000.00"),
                "discount_percentage": Decimal("10.0"),
                "points_multiplier": Decimal("1.5"),
                "order": 2,
            },
            {
                "name": "Platinum",
                "min_spending": Decimal("300000.00"),
                "discount_percentage": Decimal("15.0"),
                "points_multiplier": Decimal("2.0"),
                "order": 3,
            },
        ]

        created_tiers = {}

        for tier_data in tiers_data:
            tier, created = LoyaltyTier.objects.get_or_create(
                tenant=self.tenant,
                name=tier_data["name"],
                defaults={
                    "min_spending": tier_data["min_spending"],
                    "discount_percentage": tier_data["discount_percentage"],
                    "points_multiplier": tier_data["points_multiplier"],
                    "order": tier_data["order"],
                    "validity_months": 12,
                    "is_active": True,
                },
            )
            created_tiers[tier_data["name"]] = tier

            if created:
                print(f"  ✓ Created tier: {tier_data['name']}")

        return created_tiers

    def create_customers(self, loyalty_tiers, count=30):
        """Create customers."""
        print(f"\n👥 Creating {count} customers...")

        created_customers = []
        customer_counter = 1001

        for i in range(count):
            customer_number = f"CUST-{customer_counter:05d}"
            customer_counter += 1

            # Random tier assignment
            tier_choice = random.choices(
                [None, "Bronze", "Silver", "Gold", "Platinum"],
                weights=[20, 40, 25, 10, 5],
                k=1,
            )[0]

            tier = loyalty_tiers.get(tier_choice) if tier_choice else None
            points = 0
            if tier:
                if tier.name == "Bronze":
                    points = random.randint(0, 999)
                elif tier.name == "Silver":
                    points = random.randint(1000, 4999)
                elif tier.name == "Gold":
                    points = random.randint(5000, 9999)
                elif tier.name == "Platinum":
                    points = random.randint(10000, 50000)

            customer = Customer.objects.create(
                tenant=self.tenant,
                customer_number=customer_number,
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                email=fake.email() if random.random() > 0.3 else None,
                phone=fake.phone_number()[:20],
                date_of_birth=(
                    fake.date_of_birth(minimum_age=18, maximum_age=80)
                    if random.random() > 0.4
                    else None
                ),
                gender=random.choice([c[0] for c in Customer.GENDER_CHOICES]),
                address_line_1=fake.street_address() if random.random() > 0.3 else "",
                city=fake.city() if random.random() > 0.3 else "",
                state=fake.state() if random.random() > 0.3 else "",
                postal_code=fake.postcode() if random.random() > 0.3 else "",
                country=fake.country() if random.random() > 0.3 else "",
                loyalty_tier=tier,
                loyalty_points=points,
                tier_achieved_at=(
                    timezone.now() - timedelta(days=random.randint(1, 365)) if tier else None
                ),
                total_purchases=Decimal(random.uniform(1000, 50000)),
                preferred_communication=random.choice(
                    [c[0] for c in Customer.COMMUNICATION_CHOICES]
                ),
                marketing_opt_in=random.choice([True, False]),
            )
            created_customers.append(customer)

        print(f"  ✓ Created {len(created_customers)} customers")
        return created_customers

    def run(self):
        """Run all data population."""
        print("=" * 60)
        print("🚀 Starting test data population")
        print("=" * 60)

        with transaction.atomic():
            # Create data
            categories = self.create_categories()
            items = self.create_inventory_items(categories, count=50)
            loyalty_tiers = self.create_loyalty_tiers()
            customers = self.create_customers(loyalty_tiers, count=30)

            print("\n" + "=" * 60)
            print("✅ Test data population complete!")
            print("=" * 60)
            print(f"\n📊 Summary:")
            print(f"  • Categories: {len(categories)}")
            print(f"  • Inventory Items: {len(items)}")
            print(f"  • Loyalty Tiers: {len(loyalty_tiers)}")
            print(f"  • Customers: {len(customers)}")
            print("\n🎉 Your jewelry shop is ready for testing!")


if __name__ == "__main__":
    populator = DataPopulator()
    populator.run()
