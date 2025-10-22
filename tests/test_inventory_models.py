"""
Tests for inventory models.

Tests Requirement 9: Advanced Inventory Management
- Serialized inventory tracking
- Lot-tracked inventory
- Tracking by karat, weight, product type
- Real-time inventory levels
- Inventory movements and valuation
- RLS policy enforcement
"""

from decimal import Decimal

import pytest

from apps.core.models import Branch, Tenant
from apps.inventory.models import InventoryItem, ProductCategory


@pytest.mark.django_db
class TestProductCategory:
    """Test ProductCategory model functionality."""

    def test_create_category(self):
        """Test creating a product category."""
        from apps.core.tenant_context import bypass_rls, tenant_context

        with bypass_rls():
            tenant = Tenant.objects.create(company_name="Test Jewelry Shop", slug="test-shop")

        with tenant_context(tenant.id):
            category = ProductCategory.objects.create(
                tenant=tenant,
                name="Rings",
                description="Gold and diamond rings",
            )

            assert category.id is not None
            assert category.name == "Rings"
            assert category.tenant == tenant
            assert category.is_active is True
            assert str(category) == "Rings"

    def test_hierarchical_categories(self):
        """Test parent-child category relationships."""
        from apps.core.tenant_context import bypass_rls, tenant_context

        with bypass_rls():
            tenant = Tenant.objects.create(company_name="Test Jewelry Shop", slug="test-shop")

        with tenant_context(tenant.id):
            parent = ProductCategory.objects.create(tenant=tenant, name="Jewelry")
            child = ProductCategory.objects.create(tenant=tenant, name="Rings", parent=parent)

            assert child.parent == parent
            assert child in parent.subcategories.all()
            assert str(child) == "Jewelry > Rings"

    def test_get_full_path(self):
        """Test getting full category path."""
        from apps.core.tenant_context import bypass_rls, tenant_context

        with bypass_rls():
            tenant = Tenant.objects.create(company_name="Test Jewelry Shop", slug="test-shop")

        with tenant_context(tenant.id):
            level1 = ProductCategory.objects.create(tenant=tenant, name="Jewelry")
            level2 = ProductCategory.objects.create(tenant=tenant, name="Rings", parent=level1)
            level3 = ProductCategory.objects.create(tenant=tenant, name="Gold Rings", parent=level2)

            assert level3.get_full_path() == "Jewelry > Rings > Gold Rings"

    def test_unique_constraint(self):
        """Test that category names can be reused with different parents."""
        from apps.core.tenant_context import bypass_rls, tenant_context

        with bypass_rls():
            tenant = Tenant.objects.create(company_name="Test Jewelry Shop", slug="test-shop")

        with tenant_context(tenant.id):
            parent1 = ProductCategory.objects.create(tenant=tenant, name="Jewelry")
            parent2 = ProductCategory.objects.create(tenant=tenant, name="Accessories")

            # Same name "Rings" can exist under different parents
            rings1 = ProductCategory.objects.create(tenant=tenant, name="Rings", parent=parent1)
            rings2 = ProductCategory.objects.create(tenant=tenant, name="Rings", parent=parent2)

            assert rings1.parent == parent1
            assert rings2.parent == parent2
            assert rings1.name == rings2.name


@pytest.mark.django_db
class TestInventoryItem:
    """Test InventoryItem model functionality."""

    @pytest.fixture
    def setup_data(self):
        """Set up test data."""
        from apps.core.tenant_context import bypass_rls, tenant_context

        with bypass_rls():
            tenant = Tenant.objects.create(company_name="Test Jewelry Shop", slug="test-shop")

        with tenant_context(tenant.id):
            branch = Branch.objects.create(tenant=tenant, name="Main Branch")
            category = ProductCategory.objects.create(tenant=tenant, name="Rings")

        return {
            "tenant": tenant,
            "branch": branch,
            "category": category,
        }

    def test_create_inventory_item(self, setup_data):
        """Test creating an inventory item."""
        item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=5,
            branch=setup_data["branch"],
        )

        assert item.id is not None
        assert item.sku == "GR-001"
        assert item.name == "24K Gold Ring"
        assert item.karat == 24
        assert item.weight_grams == Decimal("10.500")
        assert item.quantity == 5
        assert str(item) == "GR-001 - 24K Gold Ring"

    def test_markup_percentage_calculation(self, setup_data):
        """Test automatic markup percentage calculation."""
        item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=5,
            branch=setup_data["branch"],
        )

        # Markup should be calculated as (1200 - 1000) / 1000 * 100 = 20%
        assert item.markup_percentage == Decimal("20.00")

    def test_serialized_item(self, setup_data):
        """Test serialized inventory tracking."""
        item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=1,
            branch=setup_data["branch"],
            serial_number="SN-12345",
        )

        assert item.is_serialized() is True
        assert item.is_lot_tracked() is False
        assert item.serial_number == "SN-12345"

    def test_lot_tracked_item(self, setup_data):
        """Test lot-tracked inventory."""
        item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GEM-001",
            name="Diamond Batch",
            category=setup_data["category"],
            karat=0,
            weight_grams=Decimal("50.000"),
            cost_price=Decimal("5000.00"),
            selling_price=Decimal("6000.00"),
            quantity=100,
            branch=setup_data["branch"],
            lot_number="LOT-2024-001",
        )

        assert item.is_lot_tracked() is True
        assert item.is_serialized() is False
        assert item.lot_number == "LOT-2024-001"

    def test_low_stock_detection(self, setup_data):
        """Test low stock alert detection."""
        item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=3,
            min_quantity=5,
            branch=setup_data["branch"],
        )

        assert item.is_low_stock() is True
        assert item.is_out_of_stock() is False

    def test_out_of_stock_detection(self, setup_data):
        """Test out of stock detection."""
        item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=0,
            branch=setup_data["branch"],
        )

        assert item.is_out_of_stock() is True
        assert item.is_low_stock() is True

    def test_inventory_valuation(self, setup_data):
        """Test inventory value calculations."""
        item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=5,
            branch=setup_data["branch"],
        )

        assert item.calculate_total_value() == Decimal("5000.00")
        assert item.calculate_total_selling_value() == Decimal("6000.00")
        assert item.calculate_profit_margin() == Decimal("20.00")

    def test_deduct_quantity_success(self, setup_data):
        """Test successful quantity deduction."""
        item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=10,
            branch=setup_data["branch"],
        )

        initial_quantity = item.quantity
        item.deduct_quantity(3, reason="Sale")

        assert item.quantity == initial_quantity - 3
        assert item.can_deduct_quantity(7) is True

    def test_deduct_quantity_insufficient(self, setup_data):
        """Test quantity deduction with insufficient stock."""
        item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=5,
            branch=setup_data["branch"],
        )

        with pytest.raises(ValueError, match="Insufficient inventory"):
            item.deduct_quantity(10, reason="Sale")

    def test_add_quantity(self, setup_data):
        """Test adding quantity to inventory."""
        item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=5,
            branch=setup_data["branch"],
        )

        initial_quantity = item.quantity
        item.add_quantity(10, reason="Purchase")

        assert item.quantity == initial_quantity + 10

    def test_unique_sku_per_tenant(self, setup_data):
        """Test that SKU must be unique within tenant."""
        InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=5,
            branch=setup_data["branch"],
        )

        # Should raise error for duplicate SKU within same tenant
        with pytest.raises(Exception):
            InventoryItem.objects.create(
                tenant=setup_data["tenant"],
                sku="GR-001",
                name="Another Ring",
                category=setup_data["category"],
                karat=22,
                weight_grams=Decimal("8.000"),
                cost_price=Decimal("800.00"),
                selling_price=Decimal("1000.00"),
                quantity=3,
                branch=setup_data["branch"],
            )

    def test_barcode_uniqueness(self, setup_data):
        """Test that barcode must be globally unique."""
        from django.db import IntegrityError, transaction

        from apps.core.tenant_context import bypass_rls, tenant_context

        with tenant_context(setup_data["tenant"].id):
            InventoryItem.objects.create(
                tenant=setup_data["tenant"],
                sku="GR-001",
                name="24K Gold Ring",
                category=setup_data["category"],
                karat=24,
                weight_grams=Decimal("10.500"),
                cost_price=Decimal("1000.00"),
                selling_price=Decimal("1200.00"),
                quantity=5,
                branch=setup_data["branch"],
                barcode="123456789",
            )

        # Create another tenant
        with bypass_rls():
            tenant2 = Tenant.objects.create(company_name="Another Shop", slug="another-shop")

        # Should raise error for duplicate barcode even across tenants
        with tenant_context(tenant2.id):
            branch2 = Branch.objects.create(tenant=tenant2, name="Branch 2")
            category2 = ProductCategory.objects.create(tenant=tenant2, name="Rings")

            with pytest.raises(IntegrityError):
                with transaction.atomic():
                    InventoryItem.objects.create(
                        tenant=tenant2,
                        sku="GR-002",
                        name="Another Ring",
                        category=category2,
                        karat=22,
                        weight_grams=Decimal("8.000"),
                        cost_price=Decimal("800.00"),
                        selling_price=Decimal("1000.00"),
                        quantity=3,
                        branch=branch2,
                        barcode="123456789",
                    )
