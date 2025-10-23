"""
Comprehensive tests for procurement functionality.

This module implements task 10.5: Write procurement tests
- Test supplier CRUD operations
- Test PO workflow and approvals
- Test goods receiving
- Test three-way matching
- Test inventory updates
- Requirements: 16, 28
"""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from apps.core.models import Branch, Tenant
from apps.core.tenant_context import bypass_rls, tenant_context
from apps.procurement.models import (
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseOrder,
    PurchaseOrderApprovalThreshold,
    PurchaseOrderItem,
    Supplier,
    SupplierCommunication,
    SupplierDocument,
)

User = get_user_model()


class ProcurementTestCase(TestCase):
    """Base test case for procurement tests with common setup."""

    def setUp(self):
        """Set up test data."""
        # Create tenant with bypass_rls and unique slug
        import uuid

        unique_slug = f"test-shop-{uuid.uuid4().hex[:8]}"
        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop", slug=unique_slug, status="ACTIVE"
            )
            self.user = User.objects.create_user(
                username="testuser",
                password="testpass",
                tenant=self.tenant,
                role="TENANT_OWNER",
                email="test@example.com",
            )
            self.manager = User.objects.create_user(
                username="manager",
                password="testpass",
                tenant=self.tenant,
                role="TENANT_MANAGER",
                email="manager@example.com",
            )
            self.employee = User.objects.create_user(
                username="employee",
                password="testpass",
                tenant=self.tenant,
                role="TENANT_EMPLOYEE",
                email="employee@example.com",
            )

            # Create a branch
            self.branch = Branch.objects.create(
                tenant=self.tenant,
                name="Main Branch",
                address="123 Main St",
                phone="555-0123",
                manager=self.manager,
            )


class TestSupplierCRUD(ProcurementTestCase):
    """Test supplier CRUD operations."""

    def test_create_supplier(self):
        """Test creating a supplier with all fields."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant,
                name="Gold Supplier Inc",
                contact_person="John Doe",
                email="john@goldsupplier.com",
                phone="+1234567890",
                address="123 Gold Street, Jewelry City",
                tax_id="TAX123456",
                payment_terms="Net 30",
                rating=4,
                notes="Reliable gold supplier",
                created_by=self.user,
            )

            # Verify all fields
            assert supplier.name == "Gold Supplier Inc"
            assert supplier.contact_person == "John Doe"
            assert supplier.email == "john@goldsupplier.com"
            assert supplier.phone == "+1234567890"
            assert supplier.address == "123 Gold Street, Jewelry City"
            assert supplier.tax_id == "TAX123456"
            assert supplier.payment_terms == "Net 30"
            assert supplier.rating == 4
            assert supplier.notes == "Reliable gold supplier"
            assert supplier.is_active is True
            assert supplier.tenant == self.tenant
            assert supplier.created_by == self.user
            assert str(supplier) == "Gold Supplier Inc"

    def test_supplier_rating_validation(self):
        """Test supplier rating validation (0-5)."""
        with tenant_context(self.tenant.id):
            # Valid ratings
            for rating in [0, 1, 2, 3, 4, 5]:
                supplier = Supplier.objects.create(
                    tenant=self.tenant,
                    name=f"Supplier {rating}",
                    rating=rating,
                    created_by=self.user,
                )
                assert supplier.rating == rating

            # Invalid rating should be caught by model validation
            with self.assertRaises(ValidationError):
                supplier = Supplier(
                    tenant=self.tenant,
                    name="Invalid Supplier",
                    rating=6,  # Invalid: > 5
                    created_by=self.user,
                )
                supplier.full_clean()

    def test_supplier_statistics_methods(self):
        """Test supplier statistics calculation methods."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            # Test initial statistics (no orders)
            assert supplier.get_total_orders() == 0
            assert supplier.get_total_order_value() == Decimal("0.00")
            assert supplier.get_average_delivery_time() is None

            # Create purchase orders
            PurchaseOrder.objects.create(
                tenant=self.tenant,
                supplier=supplier,
                total_amount=Decimal("1000.00"),
                created_by=self.user,
            )
            PurchaseOrder.objects.create(
                tenant=self.tenant,
                supplier=supplier,
                total_amount=Decimal("500.00"),
                created_by=self.user,
            )

            # Test statistics with orders
            assert supplier.get_total_orders() == 2
            assert supplier.get_total_order_value() == Decimal("1500.00")

    def test_supplier_update(self):
        """Test updating supplier information."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant,
                name="Original Name",
                rating=3,
                created_by=self.user,
            )

            # Update supplier
            supplier.name = "Updated Name"
            supplier.rating = 5
            supplier.is_active = False
            supplier.save()

            # Verify updates
            supplier.refresh_from_db()
            assert supplier.name == "Updated Name"
            assert supplier.rating == 5
            assert supplier.is_active is False

    def test_supplier_delete(self):
        """Test deleting a supplier."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )
            supplier_id = supplier.id

            # Delete supplier
            supplier.delete()

            # Verify deletion
            with self.assertRaises(Supplier.DoesNotExist):
                Supplier.objects.get(id=supplier_id)


class TestSupplierCommunication(ProcurementTestCase):
    """Test supplier communication functionality."""

    def test_create_communication(self):
        """Test creating communication records."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            comm = SupplierCommunication.objects.create(
                supplier=supplier,
                communication_type="EMAIL",
                subject="Test Communication",
                content="This is a test communication record.",
                contact_person="John Doe",
                requires_followup=True,
                created_by=self.user,
            )

            assert comm.supplier == supplier
            assert comm.communication_type == "EMAIL"
            assert comm.subject == "Test Communication"
            assert comm.content == "This is a test communication record."
            assert comm.contact_person == "John Doe"
            assert comm.requires_followup is True
            assert comm.is_completed is True  # Default
            assert comm.created_by == self.user

    def test_communication_followup_tracking(self):
        """Test follow-up tracking functionality."""
        from datetime import date, timedelta

        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            comm = SupplierCommunication.objects.create(
                supplier=supplier,
                communication_type="PHONE",
                subject="Follow-up Required",
                content="Need to follow up on pricing",
                requires_followup=True,
                followup_date=date.today() + timedelta(days=7),
                is_completed=False,
                created_by=self.user,
            )

            assert comm.requires_followup is True
            assert comm.is_completed is False
            assert comm.followup_date is not None


class TestSupplierDocument(ProcurementTestCase):
    """Test supplier document functionality."""

    def test_create_document(self):
        """Test creating document records."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            doc = SupplierDocument.objects.create(
                supplier=supplier,
                document_type="CERTIFICATION",
                title="Quality Certificate",
                description="ISO 9001 certification",
                uploaded_by=self.user,
            )

            assert doc.supplier == supplier
            assert doc.document_type == "CERTIFICATION"
            assert doc.title == "Quality Certificate"
            assert doc.description == "ISO 9001 certification"
            assert doc.is_active is True
            assert doc.uploaded_by == self.user

    def test_document_expiry_properties(self):
        """Test document expiry checking properties."""
        from datetime import date, timedelta

        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            # Test expired document
            expired_doc = SupplierDocument.objects.create(
                supplier=supplier,
                document_type="CERTIFICATION",
                title="Expired Certificate",
                expiry_date=date.today() - timedelta(days=1),
                uploaded_by=self.user,
            )

            assert expired_doc.is_expired is True
            assert expired_doc.expires_soon is False

            # Test document expiring soon
            expiring_doc = SupplierDocument.objects.create(
                supplier=supplier,
                document_type="INSURANCE",
                title="Expiring Insurance",
                expiry_date=date.today() + timedelta(days=15),
                uploaded_by=self.user,
            )

            assert expiring_doc.is_expired is False
            assert expiring_doc.expires_soon is True

            # Test valid document
            valid_doc = SupplierDocument.objects.create(
                supplier=supplier,
                document_type="CONTRACT",
                title="Valid Contract",
                expiry_date=date.today() + timedelta(days=365),
                uploaded_by=self.user,
            )

            assert valid_doc.is_expired is False
            assert valid_doc.expires_soon is False


class TestPurchaseOrderWorkflow(ProcurementTestCase):
    """Test purchase order workflow and approvals."""

    def test_create_purchase_order(self):
        """Test creating a purchase order."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant,
                supplier=supplier,
                priority="HIGH",
                total_amount=Decimal("1500.00"),
                branch=self.branch,
                notes="Urgent order for holiday season",
                created_by=self.user,
            )

            assert po.tenant == self.tenant
            assert po.supplier == supplier
            assert po.status == "DRAFT"
            assert po.priority == "HIGH"
            assert po.total_amount == Decimal("1500.00")
            assert po.branch == self.branch
            assert po.notes == "Urgent order for holiday season"
            assert po.created_by == self.user
            assert po.po_number is not None  # Auto-generated
            assert po.po_number.startswith("PO-")

    def test_purchase_order_number_generation(self):
        """Test automatic PO number generation."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            # Create multiple POs
            po1 = PurchaseOrder.objects.create(
                tenant=self.tenant, supplier=supplier, created_by=self.user
            )
            po2 = PurchaseOrder.objects.create(
                tenant=self.tenant, supplier=supplier, created_by=self.user
            )

            assert po1.po_number is not None
            assert po2.po_number is not None
            assert po1.po_number != po2.po_number
            assert po1.po_number.startswith("PO-")
            assert po2.po_number.startswith("PO-")

    def test_purchase_order_fsm_transitions(self):
        """Test FSM state transitions."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant, supplier=supplier, created_by=self.user
            )

            # Initial state
            assert po.status == "DRAFT"

            # Test approve transition
            po.approve(self.user)
            po.save()
            assert po.status == "APPROVED"
            assert po.approved_by == self.user
            assert po.approved_at is not None

            # Test send transition
            po.send_to_supplier()
            po.save()
            assert po.status == "SENT"
            assert po.sent_at is not None

            # Test partial receive transition
            po.mark_partially_received()
            assert po.status == "PARTIALLY_RECEIVED"

            # Test completion transition
            po.mark_completed()
            assert po.status == "COMPLETED"
            assert po.completed_at is not None

    def test_purchase_order_cancellation(self):
        """Test purchase order cancellation."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            # Test cancelling draft order
            po_draft = PurchaseOrder.objects.create(
                tenant=self.tenant, supplier=supplier, created_by=self.user
            )
            po_draft.cancel()
            po_draft.save()
            assert po_draft.status == "CANCELLED"

            # Test cancelling approved order
            po_approved = PurchaseOrder.objects.create(
                tenant=self.tenant, supplier=supplier, created_by=self.user
            )
            po_approved.approve(self.user)
            po_approved.save()
            po_approved.cancel()
            po_approved.save()
            assert po_approved.status == "CANCELLED"


class TestPurchaseOrderApproval(ProcurementTestCase):
    """Test purchase order approval workflow."""

    def test_approval_thresholds(self):
        """Test approval threshold configuration and logic."""
        with tenant_context(self.tenant.id):
            # Create approval thresholds
            threshold1 = PurchaseOrderApprovalThreshold.objects.create(
                tenant=self.tenant,
                min_amount=Decimal("0.00"),
                max_amount=Decimal("1000.00"),
                required_role="TENANT_MANAGER",
                created_by=self.user,
            )

            threshold2 = PurchaseOrderApprovalThreshold.objects.create(
                tenant=self.tenant,
                min_amount=Decimal("1000.01"),
                max_amount=None,  # No limit
                required_role="TENANT_OWNER",
                created_by=self.user,
            )

            # Test threshold validation
            threshold1.clean()  # Should not raise
            threshold2.clean()  # Should not raise

            # Test string representation
            assert "$0.00 - $1,000.00" in str(threshold1)
            assert "$1,000.01 - No Limit" in str(threshold2)

    def test_approval_role_determination(self):
        """Test determining required approver role."""
        with tenant_context(self.tenant.id):
            # Create approval thresholds
            PurchaseOrderApprovalThreshold.objects.create(
                tenant=self.tenant,
                min_amount=Decimal("0.00"),
                max_amount=Decimal("1000.00"),
                required_role="TENANT_MANAGER",
                created_by=self.user,
            )

            PurchaseOrderApprovalThreshold.objects.create(
                tenant=self.tenant,
                min_amount=Decimal("1000.01"),
                max_amount=None,
                required_role="TENANT_OWNER",
                created_by=self.user,
            )

            # Test small amount (should require manager)
            required_role = PurchaseOrderApprovalThreshold.get_required_approver_role(
                self.tenant, Decimal("500.00")
            )
            assert required_role == "TENANT_MANAGER"

            # Test large amount (should require owner)
            required_role = PurchaseOrderApprovalThreshold.get_required_approver_role(
                self.tenant, Decimal("2000.00")
            )
            assert required_role == "TENANT_OWNER"

    def test_user_approval_capability(self):
        """Test checking if user can approve orders."""
        with tenant_context(self.tenant.id):
            # Create approval threshold
            PurchaseOrderApprovalThreshold.objects.create(
                tenant=self.tenant,
                min_amount=Decimal("0.00"),
                max_amount=Decimal("1000.00"),
                required_role="TENANT_MANAGER",
                created_by=self.user,
            )

            # Test manager can approve small amounts
            assert (
                PurchaseOrderApprovalThreshold.can_user_approve(self.manager, Decimal("500.00"))
                is True
            )

            # Test employee cannot approve
            assert (
                PurchaseOrderApprovalThreshold.can_user_approve(self.employee, Decimal("500.00"))
                is False
            )

            # Test owner can approve anything
            assert (
                PurchaseOrderApprovalThreshold.can_user_approve(self.user, Decimal("500.00"))
                is True
            )

    def test_purchase_order_approval_check(self):
        """Test purchase order approval capability check."""
        with tenant_context(self.tenant.id):
            # Create approval threshold
            PurchaseOrderApprovalThreshold.objects.create(
                tenant=self.tenant,
                min_amount=Decimal("0.00"),
                max_amount=Decimal("1000.00"),
                required_role="TENANT_MANAGER",
                created_by=self.user,
            )

            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant,
                supplier=supplier,
                total_amount=Decimal("500.00"),
                created_by=self.user,
            )

            # Test approval capability
            assert po.can_be_approved_by(self.manager) is True
            assert po.can_be_approved_by(self.employee) is False
            assert po.can_be_approved_by(self.user) is True

            # Test after approval (should not be approvable again)
            po.approve(self.manager)
            po.save()
            assert po.can_be_approved_by(self.manager) is False


class TestPurchaseOrderItems(ProcurementTestCase):
    """Test purchase order line items."""

    def test_create_purchase_order_item(self):
        """Test creating purchase order items."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant, supplier=supplier, created_by=self.user
            )

            item = PurchaseOrderItem.objects.create(
                purchase_order=po,
                product_name="Gold Ring 18K",
                product_sku="GR18K-001",
                quantity=10,
                unit_price=Decimal("150.00"),
                notes="Premium quality gold rings",
            )

            assert item.purchase_order == po
            assert item.product_name == "Gold Ring 18K"
            assert item.product_sku == "GR18K-001"
            assert item.quantity == 10
            assert item.unit_price == Decimal("150.00")
            assert item.total_price == Decimal("1500.00")  # Auto-calculated
            assert item.received_quantity == 0
            assert item.notes == "Premium quality gold rings"
            assert str(item) == "Gold Ring 18K - 10 units"

    def test_item_total_calculation(self):
        """Test automatic total price calculation."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant, supplier=supplier, created_by=self.user
            )

            item = PurchaseOrderItem.objects.create(
                purchase_order=po,
                product_name="Test Product",
                quantity=7,
                unit_price=Decimal("25.50"),
            )

            # Total should be automatically calculated
            assert item.total_price == Decimal("178.50")

    def test_item_receiving_functionality(self):
        """Test item receiving functionality."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant, supplier=supplier, created_by=self.user
            )

            item = PurchaseOrderItem.objects.create(
                purchase_order=po,
                product_name="Test Product",
                quantity=10,
                unit_price=Decimal("25.50"),
            )

            # Initial state
            assert item.received_quantity == 0
            assert item.remaining_quantity == 10
            assert item.is_fully_received is False

            # Receive partial quantity
            item.receive_quantity(4)
            assert item.received_quantity == 4
            assert item.remaining_quantity == 6
            assert item.is_fully_received is False

            # Receive remaining quantity
            item.receive_quantity(6)
            assert item.received_quantity == 10
            assert item.remaining_quantity == 0
            assert item.is_fully_received is True

            # Test over-receiving (should raise error)
            with self.assertRaises(ValueError):
                item.receive_quantity(1)

    def test_purchase_order_total_calculation(self):
        """Test purchase order total calculation from items."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant, supplier=supplier, created_by=self.user
            )

            # Add multiple items
            PurchaseOrderItem.objects.create(
                purchase_order=po,
                product_name="Item 1",
                quantity=5,
                unit_price=Decimal("100.00"),
            )

            PurchaseOrderItem.objects.create(
                purchase_order=po,
                product_name="Item 2",
                quantity=3,
                unit_price=Decimal("200.00"),
            )

            # Calculate totals
            po.calculate_totals()

            assert po.subtotal == Decimal("1100.00")  # 500 + 600
            assert po.tax_amount == Decimal("0.00")  # No tax by default
            assert po.total_amount == Decimal("1100.00")


class TestGoodsReceiving(ProcurementTestCase):
    """Test goods receiving functionality."""

    def test_create_goods_receipt(self):
        """Test creating a goods receipt."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant,
                supplier=supplier,
                status="SENT",
                created_by=self.user,
            )

            receipt = GoodsReceipt.objects.create(
                tenant=self.tenant,
                purchase_order=po,
                supplier_invoice_number="INV-2025-001",
                tracking_number="TRACK123456",
                inspection_notes="All items in good condition",
                received_by=self.user,
            )

            assert receipt.tenant == self.tenant
            assert receipt.purchase_order == po
            assert receipt.supplier_invoice_number == "INV-2025-001"
            assert receipt.tracking_number == "TRACK123456"
            assert receipt.status == "PENDING"
            assert receipt.has_discrepancy is False
            assert receipt.inspection_notes == "All items in good condition"
            assert receipt.received_by == self.user
            assert receipt.receipt_number is not None  # Auto-generated
            assert receipt.receipt_number.startswith("GR-")

    def test_goods_receipt_number_generation(self):
        """Test automatic receipt number generation."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant,
                supplier=supplier,
                status="SENT",
                created_by=self.user,
            )

            # Create multiple receipts
            receipt1 = GoodsReceipt.objects.create(
                tenant=self.tenant, purchase_order=po, received_by=self.user
            )
            receipt2 = GoodsReceipt.objects.create(
                tenant=self.tenant, purchase_order=po, received_by=self.user
            )

            assert receipt1.receipt_number is not None
            assert receipt2.receipt_number is not None
            assert receipt1.receipt_number != receipt2.receipt_number
            assert receipt1.receipt_number.startswith("GR-")
            assert receipt2.receipt_number.startswith("GR-")

    def test_goods_receipt_completion(self):
        """Test marking goods receipt as completed."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant,
                supplier=supplier,
                status="SENT",
                created_by=self.user,
            )

            receipt = GoodsReceipt.objects.create(
                tenant=self.tenant, purchase_order=po, received_by=self.user
            )

            # Mark as completed
            receipt.mark_completed()
            assert receipt.status == "COMPLETED"

    def test_goods_receipt_discrepancy_handling(self):
        """Test discrepancy handling in goods receipts."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant,
                supplier=supplier,
                status="SENT",
                created_by=self.user,
            )

            receipt = GoodsReceipt.objects.create(
                tenant=self.tenant, purchase_order=po, received_by=self.user
            )

            # Add discrepancy
            discrepancy_notes = "Received damaged items"
            receipt.add_discrepancy(discrepancy_notes)

            assert receipt.has_discrepancy is True
            assert receipt.status == "DISCREPANCY"
            assert receipt.discrepancy_notes == discrepancy_notes


class TestGoodsReceiptItems(ProcurementTestCase):
    """Test goods receipt line items."""

    def test_create_goods_receipt_item(self):
        """Test creating goods receipt items."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant,
                supplier=supplier,
                status="SENT",
                created_by=self.user,
            )

            po_item = PurchaseOrderItem.objects.create(
                purchase_order=po,
                product_name="Gold Ring",
                quantity=10,
                unit_price=Decimal("100.00"),
            )

            receipt = GoodsReceipt.objects.create(
                tenant=self.tenant, purchase_order=po, received_by=self.user
            )

            receipt_item = GoodsReceiptItem.objects.create(
                goods_receipt=receipt,
                purchase_order_item=po_item,
                quantity_received=8,
                quantity_rejected=1,
                quality_check_passed=True,
                quality_notes="Minor scratches on one item",
                discrepancy_reason="One item damaged in shipping",
            )

            assert receipt_item.goods_receipt == receipt
            assert receipt_item.purchase_order_item == po_item
            assert receipt_item.quantity_received == 8
            assert receipt_item.quantity_rejected == 1
            assert receipt_item.quantity_accepted == 7  # Auto-calculated
            assert receipt_item.quality_check_passed is True
            assert receipt_item.quality_notes == "Minor scratches on one item"
            assert receipt_item.discrepancy_reason == "One item damaged in shipping"

    def test_receipt_item_quality_issues(self):
        """Test quality issue detection."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant,
                supplier=supplier,
                status="SENT",
                created_by=self.user,
            )

            po_item = PurchaseOrderItem.objects.create(
                purchase_order=po,
                product_name="Test Item",
                quantity=10,
                unit_price=Decimal("100.00"),
            )

            receipt = GoodsReceipt.objects.create(
                tenant=self.tenant, purchase_order=po, received_by=self.user
            )

            # Item with rejected quantity
            receipt_item1 = GoodsReceiptItem.objects.create(
                goods_receipt=receipt,
                purchase_order_item=po_item,
                quantity_received=10,
                quantity_rejected=2,
            )

            assert receipt_item1.has_quality_issues is True

            # Item with failed quality check
            receipt_item2 = GoodsReceiptItem.objects.create(
                goods_receipt=receipt,
                purchase_order_item=po_item,
                quantity_received=10,
                quantity_rejected=0,
                quality_check_passed=False,
            )

            assert receipt_item2.has_quality_issues is True

            # Item with no issues
            receipt_item3 = GoodsReceiptItem.objects.create(
                goods_receipt=receipt,
                purchase_order_item=po_item,
                quantity_received=10,
                quantity_rejected=0,
                quality_check_passed=True,
            )

            assert receipt_item3.has_quality_issues is False


class TestThreeWayMatching(ProcurementTestCase):
    """Test three-way matching functionality."""

    def test_three_way_matching_success(self):
        """Test successful three-way matching."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant,
                supplier=supplier,
                status="SENT",
                created_by=self.user,
            )

            # Add PO items
            po_item1 = PurchaseOrderItem.objects.create(
                purchase_order=po,
                product_name="Item 1",
                quantity=5,
                unit_price=Decimal("100.00"),
            )

            po_item2 = PurchaseOrderItem.objects.create(
                purchase_order=po,
                product_name="Item 2",
                quantity=3,
                unit_price=Decimal("200.00"),
            )

            receipt = GoodsReceipt.objects.create(
                tenant=self.tenant, purchase_order=po, received_by=self.user
            )

            # Add receipt items that match PO exactly
            GoodsReceiptItem.objects.create(
                goods_receipt=receipt,
                purchase_order_item=po_item1,
                quantity_received=5,
                quantity_accepted=5,
            )

            GoodsReceiptItem.objects.create(
                goods_receipt=receipt,
                purchase_order_item=po_item2,
                quantity_received=3,
                quantity_accepted=3,
            )

            # Three-way matching should succeed
            assert receipt.perform_three_way_matching() is True

    def test_three_way_matching_failure(self):
        """Test three-way matching failure due to quantity mismatch."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant,
                supplier=supplier,
                status="SENT",
                created_by=self.user,
            )

            po_item = PurchaseOrderItem.objects.create(
                purchase_order=po,
                product_name="Test Item",
                quantity=10,
                unit_price=Decimal("100.00"),
            )

            receipt = GoodsReceipt.objects.create(
                tenant=self.tenant, purchase_order=po, received_by=self.user
            )

            # Receive less than ordered
            GoodsReceiptItem.objects.create(
                goods_receipt=receipt,
                purchase_order_item=po_item,
                quantity_received=8,
                quantity_accepted=8,
            )

            # Three-way matching should fail
            assert receipt.perform_three_way_matching() is False


class TestInventoryUpdates(ProcurementTestCase):
    """Test inventory updates from goods receiving."""

    @patch("apps.procurement.views._create_or_update_inventory_item")
    def test_inventory_update_on_receipt_completion(self, mock_update_inventory):
        """Test that inventory is updated when goods receipt is completed."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant,
                supplier=supplier,
                status="SENT",
                created_by=self.user,
            )

            po_item = PurchaseOrderItem.objects.create(
                purchase_order=po,
                product_name="Gold Ring",
                quantity=10,
                unit_price=Decimal("100.00"),
            )

            receipt = GoodsReceipt.objects.create(
                tenant=self.tenant, purchase_order=po, received_by=self.user
            )

            receipt_item = GoodsReceiptItem.objects.create(
                goods_receipt=receipt,
                purchase_order_item=po_item,
                quantity_received=10,
                quantity_accepted=10,
            )

            # Update inventory (this would normally be called in the view)
            receipt_item.update_inventory()

            # Verify PO item received quantity was updated
            po_item.refresh_from_db()
            assert po_item.received_quantity == 10

    def test_purchase_order_status_update_on_completion(self):
        """Test that PO status is updated when all items are received."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant,
                supplier=supplier,
                status="SENT",
                created_by=self.user,
            )

            po_item = PurchaseOrderItem.objects.create(
                purchase_order=po,
                product_name="Test Item",
                quantity=10,
                unit_price=Decimal("100.00"),
            )

            receipt = GoodsReceipt.objects.create(
                tenant=self.tenant, purchase_order=po, received_by=self.user
            )

            receipt_item = GoodsReceiptItem.objects.create(
                goods_receipt=receipt,
                purchase_order_item=po_item,
                quantity_received=10,
                quantity_accepted=10,
            )

            # Update inventory to trigger PO item update
            receipt_item.update_inventory()

            # Mark receipt as completed (this should update PO status)
            receipt.mark_completed()

            # Verify PO status was updated to completed
            po.refresh_from_db()
            assert po.status == "COMPLETED"

    def test_partial_receipt_status_update(self):
        """Test PO status update for partial receipts."""
        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant,
                supplier=supplier,
                status="SENT",
                created_by=self.user,
            )

            po_item = PurchaseOrderItem.objects.create(
                purchase_order=po,
                product_name="Test Item",
                quantity=10,
                unit_price=Decimal("100.00"),
            )

            receipt = GoodsReceipt.objects.create(
                tenant=self.tenant, purchase_order=po, received_by=self.user
            )

            receipt_item = GoodsReceiptItem.objects.create(
                goods_receipt=receipt,
                purchase_order_item=po_item,
                quantity_received=5,  # Partial receipt
                quantity_accepted=5,
            )

            # Update inventory
            receipt_item.update_inventory()

            # Mark receipt as completed
            receipt.mark_completed()

            # Verify PO status was updated to partially received
            po.refresh_from_db()
            assert po.status == "PARTIALLY_RECEIVED"


class TestProcurementViews(ProcurementTestCase):
    """Test procurement views and web interface."""

    def test_supplier_list_view(self):
        """Test supplier list view."""
        self.client.force_login(self.user)

        with tenant_context(self.tenant.id):
            Supplier.objects.create(
                tenant=self.tenant,
                name="Test Supplier 1",
                email="supplier1@test.com",
                created_by=self.user,
            )
            Supplier.objects.create(
                tenant=self.tenant,
                name="Test Supplier 2",
                email="supplier2@test.com",
                created_by=self.user,
            )

        url = reverse("procurement:supplier_list")
        response = self.client.get(url)

        assert response.status_code == 200
        content = response.content.decode()
        assert "Test Supplier 1" in content
        assert "Test Supplier 2" in content

    def test_purchase_order_list_view(self):
        """Test purchase order list view."""
        self.client.force_login(self.user)

        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant,
                supplier=supplier,
                total_amount=Decimal("1000.00"),
                created_by=self.user,
            )

        url = reverse("procurement:purchase_order_list")
        response = self.client.get(url)

        assert response.status_code == 200
        content = response.content.decode()
        assert po.po_number in content
        assert "Test Supplier" in content

    def test_goods_receipt_list_view(self):
        """Test goods receipt list view."""
        self.client.force_login(self.user)

        with tenant_context(self.tenant.id):
            supplier = Supplier.objects.create(
                tenant=self.tenant, name="Test Supplier", created_by=self.user
            )

            po = PurchaseOrder.objects.create(
                tenant=self.tenant,
                supplier=supplier,
                status="SENT",
                created_by=self.user,
            )

            receipt = GoodsReceipt.objects.create(
                tenant=self.tenant, purchase_order=po, received_by=self.user
            )

        url = reverse("procurement:goods_receipt_list")
        response = self.client.get(url)

        assert response.status_code == 200
        content = response.content.decode()
        assert receipt.receipt_number in content


class TestProcurementIntegration(TransactionTestCase):
    """Integration tests for complete procurement workflows."""

    def setUp(self):
        """Set up test data."""
        # Create tenant with bypass_rls and unique slug
        import uuid

        unique_slug = f"test-shop-{uuid.uuid4().hex[:8]}"
        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop", slug=unique_slug, status="ACTIVE"
            )
            self.user = User.objects.create_user(
                username="testuser",
                password="testpass",
                tenant=self.tenant,
                role="TENANT_OWNER",
            )

    def test_complete_procurement_workflow(self):
        """Test complete procurement workflow from supplier to inventory."""
        with tenant_context(self.tenant.id):
            # 1. Create supplier
            supplier = Supplier.objects.create(
                tenant=self.tenant,
                name="Gold Supplier Inc",
                email="supplier@gold.com",
                created_by=self.user,
            )

            # 2. Create purchase order
            po = PurchaseOrder.objects.create(
                tenant=self.tenant,
                supplier=supplier,
                created_by=self.user,
            )

            # 3. Add line items
            po_item1 = PurchaseOrderItem.objects.create(
                purchase_order=po,
                product_name="Gold Ring 18K",
                product_sku="GR18K-001",
                quantity=5,
                unit_price=Decimal("200.00"),
            )

            po_item2 = PurchaseOrderItem.objects.create(
                purchase_order=po,
                product_name="Gold Necklace 14K",
                product_sku="GN14K-001",
                quantity=3,
                unit_price=Decimal("300.00"),
            )

            # 4. Calculate totals
            po.calculate_totals()
            assert po.total_amount == Decimal("1900.00")

            # 5. Approve purchase order
            po.approve(self.user)
            po.save()
            assert po.status == "APPROVED"

            # 6. Send to supplier
            po.send_to_supplier()
            po.save()
            assert po.status == "SENT"

            # 7. Create goods receipt
            receipt = GoodsReceipt.objects.create(
                tenant=self.tenant,
                purchase_order=po,
                supplier_invoice_number="INV-001",
                received_by=self.user,
            )

            # 8. Add receipt items
            receipt_item1 = GoodsReceiptItem.objects.create(
                goods_receipt=receipt,
                purchase_order_item=po_item1,
                quantity_received=5,
                quantity_accepted=5,
                quality_check_passed=True,
            )

            receipt_item2 = GoodsReceiptItem.objects.create(
                goods_receipt=receipt,
                purchase_order_item=po_item2,
                quantity_received=3,
                quantity_accepted=3,
                quality_check_passed=True,
            )

            # 9. Update inventory
            receipt_item1.update_inventory()
            receipt_item2.update_inventory()

            # 10. Complete receipt
            receipt.mark_completed()

            # 11. Verify final state
            po.refresh_from_db()
            assert po.status == "COMPLETED"
            assert receipt.status == "COMPLETED"
            assert receipt.perform_three_way_matching() is True

            # Verify PO items were updated
            po_item1.refresh_from_db()
            po_item2.refresh_from_db()
            assert po_item1.received_quantity == 5
            assert po_item2.received_quantity == 3
            assert po_item1.is_fully_received is True
            assert po_item2.is_fully_received is True
