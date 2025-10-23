"""
Simple Django tests for procurement models to verify basic functionality.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.models import Tenant
from apps.core.tenant_context import bypass_rls, tenant_context

from .models import GoodsReceipt, PurchaseOrder, PurchaseOrderItem, Supplier

User = get_user_model()


class TestProcurementModels(TestCase):
    """Test procurement models basic functionality."""

    def setUp(self):
        """Set up test data."""
        # Create tenant with bypass_rls
        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop", slug="test-shop", status="ACTIVE"
            )
            self.user = User.objects.create_user(
                username="testuser", password="testpass", tenant=self.tenant, role="TENANT_OWNER"
            )

    def test_create_supplier(self):
        """Test creating a supplier."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant,
                name="Gold Supplier Inc",
                contact_person="John Doe",
                email="john@goldsupplier.com",
                phone="+1234567890",
                rating=4,
                created_by=self.user,
            )

            self.assertEqual(supplier.name, "Gold Supplier Inc")
            self.assertEqual(supplier.contact_person, "John Doe")
            self.assertEqual(supplier.rating, 4)
            self.assertTrue(supplier.is_active)
            self.assertEqual(str(supplier), "Gold Supplier Inc")

    def test_create_purchase_order(self):
        """Test creating a purchase order."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant,
                po_number="PO-2025-001",
                supplier=supplier,
                total_amount=Decimal("1000.00"),
                created_by=self.user,
            )

            self.assertEqual(po.po_number, "PO-2025-001")
            self.assertEqual(po.supplier, supplier)
            self.assertEqual(po.status, "DRAFT")
            self.assertEqual(po.priority, "NORMAL")
            self.assertEqual(po.total_amount, Decimal("1000.00"))
            self.assertEqual(str(po), "PO PO-2025-001 - Test Supplier")

    def test_purchase_order_fsm_transitions(self):
        """Test FSM state transitions."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant, po_number="PO-2025-002", supplier=supplier, created_by=self.user
            )

            # Test approve transition
            self.assertEqual(po.status, "DRAFT")
            po.approve(self.user)
            po.save()
            self.assertEqual(po.status, "APPROVED")
            self.assertEqual(po.approved_by, self.user)
            self.assertIsNotNone(po.approved_at)

            # Test send to supplier transition
            po.send_to_supplier()
            po.save()
            self.assertEqual(po.status, "SENT")
            self.assertIsNotNone(po.sent_at)

            # Test mark completed transition
            po.mark_completed()
            po.save()
            self.assertEqual(po.status, "COMPLETED")
            self.assertIsNotNone(po.completed_at)

    def test_create_purchase_order_item(self):
        """Test creating a purchase order item."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant, po_number="PO-2025-001", supplier=supplier, created_by=self.user
            )

            item = PurchaseOrderItem.objects.create(
                purchase_order=po,
                product_name="Gold Ring",
                product_sku="GR-001",
                quantity=5,
                unit_price=Decimal("100.00"),
            )

            self.assertEqual(item.product_name, "Gold Ring")
            self.assertEqual(item.quantity, 5)
            self.assertEqual(item.unit_price, Decimal("100.00"))
            self.assertEqual(item.total_price, Decimal("500.00"))  # Auto-calculated
            self.assertEqual(item.received_quantity, 0)
            self.assertEqual(str(item), "Gold Ring - 5 units")

    def test_create_goods_receipt(self):
        """Test creating a goods receipt."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant,
                po_number="PO-2025-001",
                supplier=supplier,
                status="SENT",
                created_by=self.user,
            )

            receipt = GoodsReceipt.objects.create(
                tenant=self.tenant,
                receipt_number="GR-2025-001",
                purchase_order=po,
                received_by=self.user,
            )

            self.assertEqual(receipt.receipt_number, "GR-2025-001")
            self.assertEqual(receipt.purchase_order, po)
            self.assertEqual(receipt.status, "PENDING")
            self.assertFalse(receipt.has_discrepancy)
            self.assertEqual(str(receipt), "GR GR-2025-001 - PO PO-2025-001")
