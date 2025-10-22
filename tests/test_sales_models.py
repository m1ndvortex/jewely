"""
Tests for sales models.

Tests the sales data models including Terminal, Customer, Sale, and SaleItem.
Verifies model creation, relationships, and business logic.
"""

from decimal import Decimal

import pytest

from apps.core.models import Branch
from apps.core.tenant_context import tenant_context
from apps.inventory.models import InventoryItem, ProductCategory
from apps.sales.models import Customer, Sale, SaleItem, Terminal


@pytest.mark.django_db
class TestTerminalModel:
    """Test Terminal model functionality."""

    def test_create_terminal(self, tenant):
        """Test creating a terminal."""
        with tenant_context(tenant.id):
            branch = Branch.objects.create(
                tenant=tenant,
                name="Main Branch",
                address="123 Main St",
            )

            terminal = Terminal.objects.create(
                branch=branch,
                terminal_id="POS-01",
                description="Main counter terminal",
                is_active=True,
            )

            assert terminal.id is not None
            assert terminal.terminal_id == "POS-01"
            assert terminal.branch == branch
            assert terminal.is_active is True
            assert str(terminal) == "POS-01 (Main Branch)"

    def test_terminal_mark_as_used(self, tenant):
        """Test marking terminal as used."""
        with tenant_context(tenant.id):
            branch = Branch.objects.create(
                tenant=tenant,
                name="Main Branch",
            )
            terminal = Terminal.objects.create(
                branch=branch,
                terminal_id="POS-01",
            )

            assert terminal.last_used_at is None
            terminal.mark_as_used()
            terminal.refresh_from_db()
            assert terminal.last_used_at is not None


@pytest.mark.django_db
class TestCustomerModel:
    """Test Customer model functionality."""

    def test_create_customer(self, tenant):
        """Test creating a customer."""
        with tenant_context(tenant.id):
            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-001",
                first_name="John",
                last_name="Doe",
                email="john@example.com",
                phone="+1234567890",
                loyalty_tier=Customer.BRONZE,
            )

            assert customer.id is not None
            assert customer.customer_number == "CUST-001"
            assert customer.get_full_name() == "John Doe"
            assert customer.loyalty_points == 0
            assert customer.store_credit == Decimal("0.00")
            assert str(customer) == "CUST-001 - John Doe"


@pytest.mark.django_db
class TestSaleModel:
    """Test Sale model functionality."""

    def test_create_sale(self, tenant, tenant_user):
        """Test creating a sale."""
        with tenant_context(tenant.id):
            branch = Branch.objects.create(
                tenant=tenant,
                name="Main Branch",
            )
            terminal = Terminal.objects.create(
                branch=branch,
                terminal_id="POS-01",
            )
            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-001",
                first_name="John",
                last_name="Doe",
                phone="+1234567890",
            )

            sale = Sale.objects.create(
                tenant=tenant,
                sale_number="SALE-2024-00001",
                customer=customer,
                branch=branch,
                terminal=terminal,
                employee=tenant_user,
                subtotal=Decimal("1000.00"),
                tax=Decimal("100.00"),
                discount=Decimal("50.00"),
                total=Decimal("1050.00"),
                payment_method=Sale.CASH,
                status=Sale.COMPLETED,
            )

            assert sale.id is not None
            assert sale.sale_number == "SALE-2024-00001"
            assert sale.customer == customer
            assert sale.total == Decimal("1050.00")
            assert sale.status == Sale.COMPLETED
            assert str(sale) == "SALE-2024-00001 - 1050.00"

    def test_sale_mark_as_completed(self, tenant, tenant_user):
        """Test marking sale as completed."""
        with tenant_context(tenant.id):
            branch = Branch.objects.create(
                tenant=tenant,
                name="Main Branch",
            )
            terminal = Terminal.objects.create(
                branch=branch,
                terminal_id="POS-01",
            )

            sale = Sale.objects.create(
                tenant=tenant,
                sale_number="SALE-2024-00001",
                branch=branch,
                terminal=terminal,
                employee=tenant_user,
                subtotal=Decimal("1000.00"),
                tax=Decimal("0.00"),
                discount=Decimal("0.00"),
                total=Decimal("1000.00"),
                payment_method=Sale.CASH,
                status=Sale.ON_HOLD,
            )

            assert sale.completed_at is None
            sale.mark_as_completed()
            sale.refresh_from_db()
            assert sale.status == Sale.COMPLETED
            assert sale.completed_at is not None

    def test_sale_can_be_refunded(self, tenant, tenant_user):
        """Test checking if sale can be refunded."""
        with tenant_context(tenant.id):
            branch = Branch.objects.create(
                tenant=tenant,
                name="Main Branch",
            )
            terminal = Terminal.objects.create(
                branch=branch,
                terminal_id="POS-01",
            )

            sale = Sale.objects.create(
                tenant=tenant,
                sale_number="SALE-2024-00001",
                branch=branch,
                terminal=terminal,
                employee=tenant_user,
                subtotal=Decimal("1000.00"),
                tax=Decimal("0.00"),
                discount=Decimal("0.00"),
                total=Decimal("1000.00"),
                payment_method=Sale.CASH,
                status=Sale.COMPLETED,
            )

            assert sale.can_be_refunded() is True

            sale.status = Sale.REFUNDED
            sale.save()
            assert sale.can_be_refunded() is False


@pytest.mark.django_db
class TestSaleItemModel:
    """Test SaleItem model functionality."""

    def test_create_sale_item(self, tenant, tenant_user):
        """Test creating a sale item."""
        with tenant_context(tenant.id):
            branch = Branch.objects.create(
                tenant=tenant,
                name="Main Branch",
            )
            terminal = Terminal.objects.create(
                branch=branch,
                terminal_id="POS-01",
            )
            category = ProductCategory.objects.create(
                tenant=tenant,
                name="Rings",
            )
            inventory_item = InventoryItem.objects.create(
                tenant=tenant,
                sku="RING-001",
                name="Gold Ring",
                category=category,
                karat=18,
                weight_grams=Decimal("5.5"),
                cost_price=Decimal("500.00"),
                selling_price=Decimal("800.00"),
                quantity=10,
                branch=branch,
            )
            sale = Sale.objects.create(
                tenant=tenant,
                sale_number="SALE-2024-00001",
                branch=branch,
                terminal=terminal,
                employee=tenant_user,
                subtotal=Decimal("0.00"),
                tax=Decimal("0.00"),
                discount=Decimal("0.00"),
                total=Decimal("0.00"),
                payment_method=Sale.CASH,
            )

            sale_item = SaleItem.objects.create(
                sale=sale,
                inventory_item=inventory_item,
                quantity=2,
                unit_price=Decimal("800.00"),
                discount=Decimal("0.00"),
            )

            assert sale_item.id is not None
            assert sale_item.quantity == 2
            assert sale_item.unit_price == Decimal("800.00")
            assert sale_item.subtotal == Decimal("1600.00")
            assert str(sale_item) == "Gold Ring x 2"

    def test_sale_item_calculate_subtotal(self, tenant, tenant_user):
        """Test calculating sale item subtotal."""
        with tenant_context(tenant.id):
            branch = Branch.objects.create(
                tenant=tenant,
                name="Main Branch",
            )
            terminal = Terminal.objects.create(
                branch=branch,
                terminal_id="POS-01",
            )
            category = ProductCategory.objects.create(
                tenant=tenant,
                name="Rings",
            )
            inventory_item = InventoryItem.objects.create(
                tenant=tenant,
                sku="RING-001",
                name="Gold Ring",
                category=category,
                karat=18,
                weight_grams=Decimal("5.5"),
                cost_price=Decimal("500.00"),
                selling_price=Decimal("800.00"),
                quantity=10,
                branch=branch,
            )
            sale = Sale.objects.create(
                tenant=tenant,
                sale_number="SALE-2024-00001",
                branch=branch,
                terminal=terminal,
                employee=tenant_user,
                subtotal=Decimal("0.00"),
                tax=Decimal("0.00"),
                discount=Decimal("0.00"),
                total=Decimal("0.00"),
                payment_method=Sale.CASH,
            )

            sale_item = SaleItem.objects.create(
                sale=sale,
                inventory_item=inventory_item,
                quantity=3,
                unit_price=Decimal("800.00"),
                discount=Decimal("100.00"),
            )

            calculated_subtotal = sale_item.calculate_subtotal()
            assert calculated_subtotal == Decimal("2300.00")  # (800 * 3) - 100

    def test_sale_calculate_totals(self, tenant, tenant_user):
        """Test calculating sale totals from items."""
        with tenant_context(tenant.id):
            branch = Branch.objects.create(
                tenant=tenant,
                name="Main Branch",
            )
            terminal = Terminal.objects.create(
                branch=branch,
                terminal_id="POS-01",
            )
            category = ProductCategory.objects.create(
                tenant=tenant,
                name="Rings",
            )
            inventory_item = InventoryItem.objects.create(
                tenant=tenant,
                sku="RING-001",
                name="Gold Ring",
                category=category,
                karat=18,
                weight_grams=Decimal("5.5"),
                cost_price=Decimal("500.00"),
                selling_price=Decimal("800.00"),
                quantity=10,
                branch=branch,
            )
            sale = Sale.objects.create(
                tenant=tenant,
                sale_number="SALE-2024-00001",
                branch=branch,
                terminal=terminal,
                employee=tenant_user,
                subtotal=Decimal("0.00"),
                tax=Decimal("0.00"),
                discount=Decimal("0.00"),
                total=Decimal("0.00"),
                payment_method=Sale.CASH,
            )

            # Create multiple sale items
            SaleItem.objects.create(
                sale=sale,
                inventory_item=inventory_item,
                quantity=2,
                unit_price=Decimal("800.00"),
            )
            SaleItem.objects.create(
                sale=sale,
                inventory_item=inventory_item,
                quantity=1,
                unit_price=Decimal("800.00"),
            )

            sale.calculate_totals()
            sale.refresh_from_db()

            assert sale.subtotal == Decimal("2400.00")  # 1600 + 800
            assert sale.total == Decimal("2400.00")  # subtotal + 0 tax - 0 discount
