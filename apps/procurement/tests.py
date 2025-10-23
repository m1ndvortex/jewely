"""
Tests for procurement models.

Tests cover model functionality, FSM transitions, RLS policies,
and business logic for supplier and purchase order management.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError

import pytest

from apps.core.tenant_context import bypass_rls, tenant_context

from .models import GoodsReceipt, PurchaseOrder, PurchaseOrderItem, Supplier


@pytest.mark.django_db
class TestSupplierModel:
    """Test Supplier model functionality."""

    def test_create_supplier(self, tenant, tenant_user):
        """Test creating a supplier."""
        with tenant_context(tenant.id):
            supplier = Supplier.objects.create(
                tenant=tenant,
                name="Gold Supplier Inc",
                contact_person="John Doe",
                email="john@goldsupplier.com",
                phone="+1234567890",
                rating=4,
                created_by=tenant_user,
            )

            assert supplier.name == "Gold Supplier Inc"
            assert supplier.contact_person == "John Doe"
            assert supplier.rating == 4
            assert supplier.is_active is True
            assert str(supplier) == "Gold Supplier Inc"

    def test_supplier_rating_validation(self, tenant, tenant_user):
        """Test supplier rating validation."""
        with tenant_context(tenant.id):
            # Valid rating
            supplier = Supplier.objects.create(
                tenant=tenant, name="Test Supplier", rating=5, created_by=tenant_user
            )
            assert supplier.rating == 5

            # Invalid rating should be caught by model validation
            with pytest.raises(ValidationError):
                supplier = Supplier(
                    tenant=tenant,
                    name="Invalid Supplier",
                    rating=6,  # Invalid: > 5
                    created_by=tenant_user,
                )
                supplier.full_clean()

    def test_supplier_methods(self, tenant, tenant_user):
        """Test supplier helper methods."""
        with tenant_context(tenant.id):
            supplier = Supplier.objects.create(
                tenant=tenant, name="Test Supplier", created_by=tenant_user
            )

            # Test methods with no orders
            assert supplier.get_total_orders() == 0
            assert supplier.get_total_order_value() == Decimal("0.00")
            assert supplier.get_average_delivery_time() is None


@pytest.mark.django_db
class TestPurchaseOrderModel:
    """Test PurchaseOrder model functionality."""

    @pytest.fixture
    def supplier(self, tenant, tenant_user):
        """Create a test supplier."""
        with tenant_context(tenant.id):
            return Supplier.objects.create(
                tenant=tenant, name="Test Supplier", created_by=tenant_user
            )

    def test_create_purchase_order(self, tenant, tenant_user, supplier):
        """Test creating a purchase order."""
        with tenant_context(tenant.id):
            po = PurchaseOrder.objects.create(
                tenant=tenant,
                po_number="PO-2025-001",
                supplier=supplier,
                total_amount=Decimal("1000.00"),
                created_by=tenant_user,
            )

            assert po.po_number == "PO-2025-001"
            assert po.supplier == supplier
            assert po.status == "DRAFT"
            assert po.priority == "NORMAL"
            assert po.total_amount == Decimal("1000.00")
            assert str(po) == "PO PO-2025-001 - Test Supplier"

    def test_purchase_order_fsm_transitions(self, tenant, tenant_user, supplier):
        """Test FSM state transitions."""
        with tenant_context(tenant.id):
            po = PurchaseOrder.objects.create(
                tenant=tenant, po_number="PO-2025-002", supplier=supplier, created_by=tenant_user
            )

            # Test approve transition
            assert po.status == "DRAFT"
            po.approve(tenant_user)
            po.save()
            assert po.status == "APPROVED"
            assert po.approved_by == tenant_user
            assert po.approved_at is not None

            # Test send to supplier transition
            po.send_to_supplier()
            po.save()
            assert po.status == "SENT"
            assert po.sent_at is not None

            # Test mark completed transition
            po.mark_completed()
            po.save()
            assert po.status == "COMPLETED"
            assert po.completed_at is not None


@pytest.mark.django_db
class TestPurchaseOrderItemModel:
    """Test PurchaseOrderItem model functionality."""

    @pytest.fixture
    def supplier(self, tenant, tenant_user):
        """Create a test supplier."""
        with tenant_context(tenant.id):
            return Supplier.objects.create(
                tenant=tenant, name="Test Supplier", created_by=tenant_user
            )

    @pytest.fixture
    def purchase_order(self, tenant, tenant_user, supplier):
        """Create a test purchase order."""
        with tenant_context(tenant.id):
            return PurchaseOrder.objects.create(
                tenant=tenant, po_number="PO-2025-001", supplier=supplier, created_by=tenant_user
            )

    def test_create_purchase_order_item(self, purchase_order):
        """Test creating a purchase order item."""
        with tenant_context(purchase_order.tenant.id):
            item = PurchaseOrderItem.objects.create(
                purchase_order=purchase_order,
                product_name="Gold Ring",
                product_sku="GR-001",
                quantity=5,
                unit_price=Decimal("100.00"),
            )

            assert item.product_name == "Gold Ring"
            assert item.quantity == 5
            assert item.unit_price == Decimal("100.00")
            assert item.total_price == Decimal("500.00")  # Auto-calculated
            assert item.received_quantity == 0
            assert str(item) == "Gold Ring - 5 units"

    def test_receive_quantity_method(self, purchase_order):
        """Test receive quantity method."""
        with tenant_context(purchase_order.tenant.id):
            item = PurchaseOrderItem.objects.create(
                purchase_order=purchase_order,
                product_name="Test Item",
                quantity=10,
                unit_price=Decimal("100.00"),
            )

            # Receive valid quantity
            item.receive_quantity(3)
            assert item.received_quantity == 3

            # Receive more
            item.receive_quantity(2)
            assert item.received_quantity == 5

            # Try to receive more than remaining
            with pytest.raises(ValueError, match="Cannot receive more than ordered quantity"):
                item.receive_quantity(6)  # Would make total 11, but only ordered 10


@pytest.mark.django_db
class TestGoodsReceiptModel:
    """Test GoodsReceipt model functionality."""

    @pytest.fixture
    def supplier(self, tenant, tenant_user):
        """Create a test supplier."""
        with tenant_context(tenant.id):
            return Supplier.objects.create(
                tenant=tenant, name="Test Supplier", created_by=tenant_user
            )

    @pytest.fixture
    def purchase_order(self, tenant, tenant_user, supplier):
        """Create a test purchase order."""
        with tenant_context(tenant.id):
            return PurchaseOrder.objects.create(
                tenant=tenant,
                po_number="PO-2025-001",
                supplier=supplier,
                status="SENT",
                created_by=tenant_user,
            )

    def test_create_goods_receipt(self, tenant, tenant_user, purchase_order):
        """Test creating a goods receipt."""
        with tenant_context(tenant.id):
            receipt = GoodsReceipt.objects.create(
                tenant=tenant,
                receipt_number="GR-2025-001",
                purchase_order=purchase_order,
                received_by=tenant_user,
            )

            assert receipt.receipt_number == "GR-2025-001"
            assert receipt.purchase_order == purchase_order
            assert receipt.status == "PENDING"
            assert receipt.has_discrepancy is False
            assert str(receipt) == "GR GR-2025-001 - PO PO-2025-001"

    def test_mark_completed(self, tenant, tenant_user, purchase_order):
        """Test marking goods receipt as completed."""
        with tenant_context(tenant.id):
            receipt = GoodsReceipt.objects.create(
                tenant=tenant,
                receipt_number="GR-2025-002",
                purchase_order=purchase_order,
                received_by=tenant_user,
            )

            receipt.mark_completed()
            assert receipt.status == "COMPLETED"


@pytest.mark.django_db
class TestRLSPolicies:
    """Test Row-Level Security policies for procurement models."""

    def test_supplier_rls_isolation(self, tenant, tenant_user):
        """Test that suppliers are isolated by tenant."""
        # Create tenant2 with bypass_rls
        with bypass_rls():
            from django.contrib.auth import get_user_model

            from apps.core.models import Tenant

            User = get_user_model()

            tenant2 = Tenant.objects.create(
                company_name="Tenant 2", slug="tenant-2-test", status="ACTIVE"
            )
            user2 = User.objects.create_user(
                username="user2-test", password="testpass", tenant=tenant2, role="TENANT_OWNER"
            )

        # Create suppliers for each tenant
        with tenant_context(tenant.id):
            supplier1 = Supplier.objects.create(
                tenant=tenant, name="Tenant 1 Supplier", created_by=tenant_user
            )

        with tenant_context(tenant2.id):
            supplier2 = Supplier.objects.create(
                tenant=tenant2, name="Tenant 2 Supplier", created_by=user2
            )

        # Test tenant1 context - should only see tenant1's supplier
        with tenant_context(tenant.id):
            suppliers = Supplier.objects.all()
            assert supplier1 in suppliers
            assert supplier2 not in suppliers
            assert suppliers.count() == 1

        # Test tenant2 context - should only see tenant2's supplier
        with tenant_context(tenant2.id):
            suppliers = Supplier.objects.all()
            assert supplier1 not in suppliers
            assert supplier2 in suppliers
            assert suppliers.count() == 1
