"""
Tests for purchase order workflow functionality.

This module tests the purchase order creation, approval workflow,
and sending functionality implemented in task 10.3.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse

import pytest

from apps.core.tenant_context import tenant_context
from apps.procurement.models import (
    PurchaseOrder,
    PurchaseOrderApprovalThreshold,
    PurchaseOrderItem,
    Supplier,
)

User = get_user_model()


@pytest.mark.django_db
class TestPurchaseOrderWorkflow:
    """Test purchase order workflow functionality."""

    def test_purchase_order_creation(self, tenant_user, client):
        """Test purchase order creation through the web interface."""
        # Login as tenant user
        client.force_login(tenant_user)

        # Create a supplier
        with tenant_context(tenant_user.tenant.id):
            supplier = Supplier.objects.create(
                tenant=tenant_user.tenant,
                name="Test Supplier",
                email="supplier@test.com",
                created_by=tenant_user,
            )

        # Access create form
        url = reverse("procurement:purchase_order_create")
        response = client.get(url)
        assert response.status_code == 200

        # Submit form with line items
        from datetime import date, timedelta
        future_date = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        data = {
            "supplier": supplier.id,
            "priority": "NORMAL",
            "expected_delivery": future_date,
            "notes": "Test purchase order",
            # Management form data for formset
            "items-TOTAL_FORMS": "2",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            # First item
            "items-0-product_name": "Gold Ring",
            "items-0-product_sku": "GR-001",
            "items-0-quantity": "10",
            "items-0-unit_price": "100.00",
            "items-0-notes": "24K gold rings",
            # Second item
            "items-1-product_name": "Silver Necklace",
            "items-1-product_sku": "SN-001",
            "items-1-quantity": "5",
            "items-1-unit_price": "50.00",
            "items-1-notes": "Sterling silver",
        }
        response = client.post(url, data)

        # Debug form errors if not redirecting
        if response.status_code != 302:
            print("Form errors:", response.context.get('form', {}).errors if response.context else "No context")
            print("Formset errors:", response.context.get('formset', {}).errors if response.context else "No formset")
            print("Response content:", response.content.decode()[:500])

        # Should redirect to detail page
        assert response.status_code == 302

        # Verify purchase order was created
        with tenant_context(tenant_user.tenant.id):
            po = PurchaseOrder.objects.get(supplier=supplier)
            assert po.tenant == tenant_user.tenant
            assert po.created_by == tenant_user
            assert po.status == "DRAFT"
            assert po.priority == "NORMAL"
            assert po.notes == "Test purchase order"

            # Verify line items
            items = po.items.all()
            assert items.count() == 2

            item1 = items.get(product_name="Gold Ring")
            assert item1.product_sku == "GR-001"
            assert item1.quantity == 10
            assert item1.unit_price == Decimal("100.00")
            assert item1.total_price == Decimal("1000.00")

            item2 = items.get(product_name="Silver Necklace")
            assert item2.quantity == 5
            assert item2.unit_price == Decimal("50.00")
            assert item2.total_price == Decimal("250.00")

            # Verify totals were calculated
            assert po.subtotal == Decimal("1250.00")
            assert po.total_amount == Decimal("1250.00")

    def test_purchase_order_approval_workflow(self, tenant_user):
        """Test purchase order approval workflow."""
        with tenant_context(tenant_user.tenant.id):
            # Create approval threshold
            PurchaseOrderApprovalThreshold.objects.create(
                tenant=tenant_user.tenant,
                min_amount=Decimal("0.00"),
                max_amount=Decimal("1000.00"),
                required_role="TENANT_MANAGER",
                created_by=tenant_user,
            )

            # Create supplier and purchase order
            supplier = Supplier.objects.create(
                tenant=tenant_user.tenant, name="Test Supplier", created_by=tenant_user
            )

            po = PurchaseOrder.objects.create(
                tenant=tenant_user.tenant,
                supplier=supplier,
                total_amount=Decimal("500.00"),
                created_by=tenant_user,
            )

            # Test approval check for manager
            tenant_user.role = "TENANT_MANAGER"
            tenant_user.save()
            assert po.can_be_approved_by(tenant_user) is True

            # Test approval check for employee (should fail)
            tenant_user.role = "TENANT_EMPLOYEE"
            tenant_user.save()
            assert po.can_be_approved_by(tenant_user) is False

            # Approve as manager
            tenant_user.role = "TENANT_MANAGER"
            tenant_user.save()
            po.approve(tenant_user)
            po.save()

            assert po.status == "APPROVED"
            assert po.approved_by == tenant_user
            assert po.approved_at is not None

    def test_purchase_order_approval_thresholds(self, tenant_user):
        """Test approval threshold logic."""
        with tenant_context(tenant_user.tenant.id):
            # Create multiple approval thresholds
            PurchaseOrderApprovalThreshold.objects.create(
                tenant=tenant_user.tenant,
                min_amount=Decimal("0.00"),
                max_amount=Decimal("1000.00"),
                required_role="TENANT_MANAGER",
                created_by=tenant_user,
            )

            PurchaseOrderApprovalThreshold.objects.create(
                tenant=tenant_user.tenant,
                min_amount=Decimal("1000.01"),
                max_amount=None,  # No limit
                required_role="TENANT_OWNER",
                created_by=tenant_user,
            )

            # Test small amount (should require manager)
            required_role = PurchaseOrderApprovalThreshold.get_required_approver_role(
                tenant_user.tenant, Decimal("500.00")
            )
            assert required_role == "TENANT_MANAGER"

            # Test large amount (should require owner)
            required_role = PurchaseOrderApprovalThreshold.get_required_approver_role(
                tenant_user.tenant, Decimal("2000.00")
            )
            assert required_role == "TENANT_OWNER"

            # Test user approval capability
            tenant_user.role = "TENANT_MANAGER"
            tenant_user.save()
            assert (
                PurchaseOrderApprovalThreshold.can_user_approve(
                    tenant_user, Decimal("500.00")
                )
                is True
            )
            assert (
                PurchaseOrderApprovalThreshold.can_user_approve(
                    tenant_user, Decimal("2000.00")
                )
                is False
            )

            tenant_user.role = "TENANT_OWNER"
            tenant_user.save()
            assert (
                PurchaseOrderApprovalThreshold.can_user_approve(
                    tenant_user, Decimal("2000.00")
                )
                is True
            )

    def test_purchase_order_number_generation(self, tenant_user):
        """Test automatic PO number generation."""
        with tenant_context(tenant_user.tenant.id):
            supplier = Supplier.objects.create(
                tenant=tenant_user.tenant, name="Test Supplier", created_by=tenant_user
            )

            # Create first PO
            po1 = PurchaseOrder.objects.create(
                tenant=tenant_user.tenant, supplier=supplier, created_by=tenant_user
            )

            assert po1.po_number is not None
            assert po1.po_number.startswith("PO-")

            # Create second PO
            po2 = PurchaseOrder.objects.create(
                tenant=tenant_user.tenant, supplier=supplier, created_by=tenant_user
            )

            assert po2.po_number is not None
            assert po2.po_number != po1.po_number
            assert po2.po_number.startswith("PO-")

    def test_purchase_order_state_transitions(self, tenant_user):
        """Test FSM state transitions."""
        with tenant_context(tenant_user.tenant.id):
            supplier = Supplier.objects.create(
                tenant=tenant_user.tenant, name="Test Supplier", created_by=tenant_user
            )

            po = PurchaseOrder.objects.create(
                tenant=tenant_user.tenant, supplier=supplier, created_by=tenant_user
            )

            # Initial state should be DRAFT
            assert po.status == "DRAFT"

            # Test approval transition
            po.approve(tenant_user)
            po.save()
            assert po.status == "APPROVED"

            # Test send transition
            po.send_to_supplier()
            po.save()
            assert po.status == "SENT"
            assert po.sent_at is not None

            # Test completion transition
            po.mark_completed()
            po.save()
            assert po.status == "COMPLETED"
            assert po.completed_at is not None

    def test_purchase_order_list_view(self, tenant_user, client):
        """Test purchase order list view."""
        # Login as tenant user
        client.force_login(tenant_user)

        # Create supplier and purchase orders
        with tenant_context(tenant_user.tenant.id):
            supplier = Supplier.objects.create(
                tenant=tenant_user.tenant, name="Test Supplier", created_by=tenant_user
            )

            po1 = PurchaseOrder.objects.create(
                tenant=tenant_user.tenant,
                supplier=supplier,
                priority="HIGH",
                total_amount=Decimal("1000.00"),
                created_by=tenant_user,
            )

            po2 = PurchaseOrder.objects.create(
                tenant=tenant_user.tenant,
                supplier=supplier,
                priority="NORMAL",
                total_amount=Decimal("500.00"),
                created_by=tenant_user,
            )

        # Access list view
        url = reverse("procurement:purchase_order_list")
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()
        assert po1.po_number in content
        assert po2.po_number in content
        assert "Test Supplier" in content

    def test_purchase_order_detail_view(self, tenant_user, client):
        """Test purchase order detail view."""
        # Login as tenant user
        client.force_login(tenant_user)

        # Create supplier and purchase order
        with tenant_context(tenant_user.tenant.id):
            supplier = Supplier.objects.create(
                tenant=tenant_user.tenant,
                name="Test Supplier",
                email="supplier@test.com",
                created_by=tenant_user,
            )

            po = PurchaseOrder.objects.create(
                tenant=tenant_user.tenant,
                supplier=supplier,
                notes="Test notes",
                created_by=tenant_user,
            )

            # Add line item
            PurchaseOrderItem.objects.create(
                purchase_order=po,
                product_name="Test Product",
                quantity=5,
                unit_price=Decimal("100.00"),
            )

        # Access detail view
        url = reverse("procurement:purchase_order_detail", kwargs={"pk": po.pk})
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()
        assert po.po_number in content
        assert "Test Supplier" in content
        assert "Test Product" in content
        assert "Test notes" in content

    def test_purchase_order_approval_view(self, tenant_user, client):
        """Test purchase order approval view."""
        # Set user as manager
        tenant_user.role = "TENANT_MANAGER"
        tenant_user.save()
        client.force_login(tenant_user)

        # Create approval threshold
        with tenant_context(tenant_user.tenant.id):
            PurchaseOrderApprovalThreshold.objects.create(
                tenant=tenant_user.tenant,
                min_amount=Decimal("0.00"),
                max_amount=Decimal("1000.00"),
                required_role="TENANT_MANAGER",
                created_by=tenant_user,
            )

            supplier = Supplier.objects.create(
                tenant=tenant_user.tenant, name="Test Supplier", created_by=tenant_user
            )

            po = PurchaseOrder.objects.create(
                tenant=tenant_user.tenant,
                supplier=supplier,
                total_amount=Decimal("500.00"),
                created_by=tenant_user,
            )

        # Access approval view
        url = reverse("procurement:purchase_order_approve", kwargs={"pk": po.pk})
        response = client.get(url)
        assert response.status_code == 200

        # Submit approval
        data = {"approval_notes": "Approved for testing"}
        response = client.post(url, data)
        assert response.status_code == 302

        # Verify approval
        po.refresh_from_db()
        assert po.status == "APPROVED"
        assert po.approved_by == tenant_user

    def test_purchase_order_send_view(self, tenant_user, client):
        """Test purchase order send view."""
        # Set user as manager
        tenant_user.role = "TENANT_MANAGER"
        tenant_user.save()
        client.force_login(tenant_user)

        # Create approved purchase order
        with tenant_context(tenant_user.tenant.id):
            supplier = Supplier.objects.create(
                tenant=tenant_user.tenant,
                name="Test Supplier",
                email="supplier@test.com",
                created_by=tenant_user,
            )

            po = PurchaseOrder.objects.create(
                tenant=tenant_user.tenant,
                supplier=supplier,
                status="APPROVED",
                total_amount=Decimal("500.00"),
                created_by=tenant_user,
            )

        # Access send view
        url = reverse("procurement:purchase_order_send", kwargs={"pk": po.pk})
        response = client.get(url)
        assert response.status_code == 200

        # Test form display
        content = response.content.decode()
        assert "Send Purchase Order" in content
        assert supplier.email in content


@pytest.mark.django_db
class TestPurchaseOrderItem:
    """Test purchase order item functionality."""

    def test_item_total_calculation(self, tenant_user):
        """Test automatic total price calculation."""
        with tenant_context(tenant_user.tenant.id):
            supplier = Supplier.objects.create(
                tenant=tenant_user.tenant, name="Test Supplier", created_by=tenant_user
            )

            po = PurchaseOrder.objects.create(
                tenant=tenant_user.tenant, supplier=supplier, created_by=tenant_user
            )

            item = PurchaseOrderItem.objects.create(
                purchase_order=po,
                product_name="Test Product",
                quantity=10,
                unit_price=Decimal("25.50"),
            )

            # Total should be automatically calculated
            assert item.total_price == Decimal("255.00")

    def test_item_receiving_functionality(self, tenant_user):
        """Test item receiving functionality."""
        with tenant_context(tenant_user.tenant.id):
            supplier = Supplier.objects.create(
                tenant=tenant_user.tenant, name="Test Supplier", created_by=tenant_user
            )

            po = PurchaseOrder.objects.create(
                tenant=tenant_user.tenant, supplier=supplier, created_by=tenant_user
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
            item.receive_quantity(5)
            assert item.received_quantity == 5
            assert item.remaining_quantity == 5
            assert item.is_fully_received is False

            # Receive remaining quantity
            item.receive_quantity(5)
            assert item.received_quantity == 10
            assert item.remaining_quantity == 0
            assert item.is_fully_received is True

            # Test over-receiving (should raise error)
            with pytest.raises(ValueError):
                item.receive_quantity(1)


@pytest.mark.django_db
class TestApprovalThreshold:
    """Test approval threshold functionality."""

    def test_threshold_validation(self, tenant_user):
        """Test threshold validation logic."""
        with tenant_context(tenant_user.tenant.id):
            # Test valid threshold
            threshold = PurchaseOrderApprovalThreshold(
                tenant=tenant_user.tenant,
                min_amount=Decimal("100.00"),
                max_amount=Decimal("1000.00"),
                required_role="TENANT_MANAGER",
                created_by=tenant_user,
            )
            threshold.clean()  # Should not raise

            # Test invalid threshold (min >= max)
            invalid_threshold = PurchaseOrderApprovalThreshold(
                tenant=tenant_user.tenant,
                min_amount=Decimal("1000.00"),
                max_amount=Decimal("500.00"),
                required_role="TENANT_MANAGER",
                created_by=tenant_user,
            )

            with pytest.raises(Exception):  # ValidationError
                invalid_threshold.clean()

    def test_threshold_string_representation(self, tenant_user):
        """Test threshold string representation."""
        with tenant_context(tenant_user.tenant.id):
            # Threshold with max amount
            threshold1 = PurchaseOrderApprovalThreshold.objects.create(
                tenant=tenant_user.tenant,
                min_amount=Decimal("100.00"),
                max_amount=Decimal("1000.00"),
                required_role="TENANT_MANAGER",
                created_by=tenant_user,
            )

            assert "$100.00 - $1,000.00" in str(threshold1)
            assert "Manager" in str(threshold1)

            # Threshold without max amount (unlimited)
            threshold2 = PurchaseOrderApprovalThreshold.objects.create(
                tenant=tenant_user.tenant,
                min_amount=Decimal("1000.01"),
                max_amount=None,
                required_role="TENANT_OWNER",
                created_by=tenant_user,
            )

            assert "$1,000.01 - No Limit" in str(threshold2)
            assert "Owner" in str(threshold2)