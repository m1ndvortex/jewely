"""
Tests for inventory transfer functionality.

Tests Requirement 14: Multi-Branch Management
- Inter-branch inventory transfers with in-transit tracking
- Approval workflow for high-value transfers
- Receiving confirmation interface with discrepancy logging
- Update inventory levels on transfer completion
- Complete audit trail of all inter-branch movements
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.models import Branch, Tenant
from apps.core.tenant_context import bypass_rls, tenant_context
from apps.inventory.models import (
    InventoryItem,
    InventoryTransfer,
    InventoryTransferItem,
    ProductCategory,
)

User = get_user_model()


class InventoryTransferModelTestCase(TestCase):
    """Test case for InventoryTransfer model functionality."""

    def setUp(self):
        """Set up test data."""
        # Create tenant using RLS bypass
        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop Transfer",
                slug="test-shop-transfer",
                status=Tenant.ACTIVE,
            )

            # Create users
            self.owner = User.objects.create_user(
                username="owner",
                email="owner@test.com",
                password="testpass123",
                tenant=self.tenant,
                role=User.TENANT_OWNER,
            )

            self.manager = User.objects.create_user(
                username="manager",
                email="manager@test.com",
                password="testpass123",
                tenant=self.tenant,
                role=User.TENANT_MANAGER,
            )

            self.employee1 = User.objects.create_user(
                username="employee1",
                email="employee1@test.com",
                password="testpass123",
                tenant=self.tenant,
                role=User.TENANT_EMPLOYEE,
            )

            self.employee2 = User.objects.create_user(
                username="employee2",
                email="employee2@test.com",
                password="testpass123",
                tenant=self.tenant,
                role=User.TENANT_EMPLOYEE,
            )

        # Create branches and inventory within tenant context
        with tenant_context(self.tenant.id):
            self.branch_a = Branch.objects.create(
                tenant=self.tenant,
                name="Branch A",
                address="123 Main St",
                phone="+1-555-123-4567",
                is_active=True,
            )

            self.branch_b = Branch.objects.create(
                tenant=self.tenant,
                name="Branch B",
                address="456 Mall Ave",
                phone="+1-555-987-6543",
                is_active=True,
            )

            # Assign employees to branches
            self.employee1.branch = self.branch_a
            self.employee1.save()

            self.employee2.branch = self.branch_b
            self.employee2.save()

            # Create product category
            self.category = ProductCategory.objects.create(
                tenant=self.tenant,
                name="Rings",
                is_active=True,
            )

            # Create inventory items in Branch A
            self.item1 = InventoryItem.objects.create(
                tenant=self.tenant,
                sku="RING-001",
                name="Gold Ring 18K",
                category=self.category,
                karat=18,
                weight_grams=Decimal("5.5"),
                cost_price=Decimal("500.00"),
                selling_price=Decimal("750.00"),
                quantity=10,
                min_quantity=2,
                branch=self.branch_a,
            )

            self.item2 = InventoryItem.objects.create(
                tenant=self.tenant,
                sku="RING-002",
                name="Gold Ring 22K",
                category=self.category,
                karat=22,
                weight_grams=Decimal("6.0"),
                cost_price=Decimal("800.00"),
                selling_price=Decimal("1200.00"),
                quantity=5,
                min_quantity=1,
                branch=self.branch_a,
            )

    def test_create_transfer(self):
        """Test creating an inventory transfer."""
        with tenant_context(self.tenant.id):
            transfer = InventoryTransfer.objects.create(
                tenant=self.tenant,
                from_branch=self.branch_a,
                to_branch=self.branch_b,
                requested_by=self.employee1,
            )

            self.assertIsNotNone(transfer.id)
            self.assertIsNotNone(transfer.transfer_number)
            self.assertTrue(transfer.transfer_number.startswith("TRF-"))
            self.assertEqual(transfer.status, InventoryTransfer.PENDING)
            self.assertEqual(transfer.from_branch, self.branch_a)
            self.assertEqual(transfer.to_branch, self.branch_b)
            self.assertEqual(transfer.requested_by, self.employee1)

    def test_transfer_number_generation(self):
        """Test automatic transfer number generation."""
        with tenant_context(self.tenant.id):
            transfer1 = InventoryTransfer.objects.create(
                tenant=self.tenant,
                from_branch=self.branch_a,
                to_branch=self.branch_b,
                requested_by=self.employee1,
            )

            transfer2 = InventoryTransfer.objects.create(
                tenant=self.tenant,
                from_branch=self.branch_a,
                to_branch=self.branch_b,
                requested_by=self.employee1,
            )

            # Both should have transfer numbers
            self.assertIsNotNone(transfer1.transfer_number)
            self.assertIsNotNone(transfer2.transfer_number)

            # Transfer numbers should be different
            self.assertNotEqual(transfer1.transfer_number, transfer2.transfer_number)

    def test_add_transfer_items(self):
        """Test adding items to a transfer."""
        with tenant_context(self.tenant.id):
            transfer = InventoryTransfer.objects.create(
                tenant=self.tenant,
                from_branch=self.branch_a,
                to_branch=self.branch_b,
                requested_by=self.employee1,
            )

            # Add items
            item1 = InventoryTransferItem.objects.create(
                transfer=transfer,
                inventory_item=self.item1,
                quantity=3,
            )

            item2 = InventoryTransferItem.objects.create(
                transfer=transfer,
                inventory_item=self.item2,
                quantity=2,
            )

            # Verify items were added
            self.assertEqual(transfer.items.count(), 2)
            self.assertEqual(item1.unit_cost, self.item1.cost_price)
            self.assertEqual(item2.unit_cost, self.item2.cost_price)

    def test_calculate_total_value(self):
        """Test calculating total transfer value."""
        with tenant_context(self.tenant.id):
            transfer = InventoryTransfer.objects.create(
                tenant=self.tenant,
                from_branch=self.branch_a,
                to_branch=self.branch_b,
                requested_by=self.employee1,
            )

            # Add items
            InventoryTransferItem.objects.create(
                transfer=transfer,
                inventory_item=self.item1,
                quantity=3,
                unit_cost=self.item1.cost_price,
            )

            InventoryTransferItem.objects.create(
                transfer=transfer,
                inventory_item=self.item2,
                quantity=2,
                unit_cost=self.item2.cost_price,
            )

            # Calculate total value
            total = transfer.calculate_total_value()
            expected = (Decimal("500.00") * 3) + (Decimal("800.00") * 2)
            self.assertEqual(total, expected)

    def test_approve_transfer(self):
        """Test approving a transfer."""
        with tenant_context(self.tenant.id):
            transfer = InventoryTransfer.objects.create(
                tenant=self.tenant,
                from_branch=self.branch_a,
                to_branch=self.branch_b,
                requested_by=self.employee1,
                status=InventoryTransfer.PENDING,
            )

            # Approve transfer
            transfer.approve(self.manager)
            transfer.save()

            # Verify status changed
            self.assertEqual(transfer.status, InventoryTransfer.APPROVED)
            self.assertEqual(transfer.approved_by, self.manager)
            self.assertIsNotNone(transfer.approved_at)

    def test_reject_transfer(self):
        """Test rejecting a transfer."""
        with tenant_context(self.tenant.id):
            transfer = InventoryTransfer.objects.create(
                tenant=self.tenant,
                from_branch=self.branch_a,
                to_branch=self.branch_b,
                requested_by=self.employee1,
                status=InventoryTransfer.PENDING,
            )

            # Reject transfer
            reason = "Insufficient stock at destination"
            transfer.reject(self.manager, reason)
            transfer.save()

            # Verify status changed
            self.assertEqual(transfer.status, InventoryTransfer.REJECTED)
            self.assertEqual(transfer.rejected_by, self.manager)
            self.assertEqual(transfer.rejection_reason, reason)
            self.assertIsNotNone(transfer.rejected_at)

    def test_ship_transfer_deducts_inventory(self):
        """Test that shipping a transfer deducts inventory from source branch."""
        with tenant_context(self.tenant.id):
            transfer = InventoryTransfer.objects.create(
                tenant=self.tenant,
                from_branch=self.branch_a,
                to_branch=self.branch_b,
                requested_by=self.employee1,
                status=InventoryTransfer.APPROVED,
            )

            # Add items
            InventoryTransferItem.objects.create(
                transfer=transfer,
                inventory_item=self.item1,
                quantity=3,
            )

            # Record initial quantity
            initial_quantity = self.item1.quantity

            # Ship transfer
            transfer.mark_shipped(self.employee1)
            transfer.save()

            # Verify status changed
            self.assertEqual(transfer.status, InventoryTransfer.IN_TRANSIT)
            self.assertEqual(transfer.shipped_by, self.employee1)
            self.assertIsNotNone(transfer.shipped_at)

            # Verify inventory was deducted
            self.item1.refresh_from_db()
            self.assertEqual(self.item1.quantity, initial_quantity - 3)

    def test_receive_transfer_adds_inventory(self):
        """Test that receiving a transfer adds inventory to destination branch."""
        with tenant_context(self.tenant.id):
            transfer = InventoryTransfer.objects.create(
                tenant=self.tenant,
                from_branch=self.branch_a,
                to_branch=self.branch_b,
                requested_by=self.employee1,
                status=InventoryTransfer.IN_TRANSIT,
            )

            # Add items
            InventoryTransferItem.objects.create(
                transfer=transfer,
                inventory_item=self.item1,
                quantity=3,
            )

            # Record initial quantity
            initial_quantity = self.item1.quantity

            # Receive transfer
            transfer.mark_received(self.employee2)
            transfer.save()

            # Verify status changed
            self.assertEqual(transfer.status, InventoryTransfer.RECEIVED)
            self.assertEqual(transfer.received_by, self.employee2)
            self.assertIsNotNone(transfer.received_at)

            # Verify inventory was added
            self.item1.refresh_from_db()
            self.assertEqual(self.item1.quantity, initial_quantity + 3)

    def test_receive_transfer_with_discrepancies(self):
        """Test receiving a transfer with quantity discrepancies."""
        with tenant_context(self.tenant.id):
            transfer = InventoryTransfer.objects.create(
                tenant=self.tenant,
                from_branch=self.branch_a,
                to_branch=self.branch_b,
                requested_by=self.employee1,
                status=InventoryTransfer.IN_TRANSIT,
            )

            # Add items
            transfer_item = InventoryTransferItem.objects.create(
                transfer=transfer,
                inventory_item=self.item1,
                quantity=5,  # Expected 5
            )

            # Record initial quantity
            initial_quantity = self.item1.quantity

            # Receive with discrepancy (only 4 received)
            discrepancies = {str(transfer_item.id): 4}
            transfer.mark_received(self.employee2, discrepancies)
            transfer.save()

            # Verify status changed
            self.assertEqual(transfer.status, InventoryTransfer.RECEIVED)

            # Verify discrepancy was logged
            transfer_item.refresh_from_db()
            self.assertTrue(transfer_item.has_discrepancy)
            self.assertEqual(transfer_item.received_quantity, 4)
            self.assertIn("Expected: 5", transfer_item.discrepancy_notes)
            self.assertIn("Received: 4", transfer_item.discrepancy_notes)

            # Verify only actual received quantity was added
            self.item1.refresh_from_db()
            self.assertEqual(self.item1.quantity, initial_quantity + 4)

    def test_cancel_transfer(self):
        """Test cancelling a transfer."""
        with tenant_context(self.tenant.id):
            transfer = InventoryTransfer.objects.create(
                tenant=self.tenant,
                from_branch=self.branch_a,
                to_branch=self.branch_b,
                requested_by=self.employee1,
                status=InventoryTransfer.PENDING,
            )

            # Cancel transfer
            reason = "No longer needed"
            transfer.cancel(self.manager, reason)
            transfer.save()

            # Verify status changed
            self.assertEqual(transfer.status, InventoryTransfer.CANCELLED)
            self.assertIn(reason, transfer.notes)

    def test_can_approve_permissions(self):
        """Test can_approve permission checks."""
        with tenant_context(self.tenant.id):
            transfer = InventoryTransfer.objects.create(
                tenant=self.tenant,
                from_branch=self.branch_a,
                to_branch=self.branch_b,
                requested_by=self.employee1,
            )

            # Manager can approve
            self.assertTrue(transfer.can_approve(self.manager))

            # Owner can approve
            self.assertTrue(transfer.can_approve(self.owner))

            # Requester cannot approve their own request
            self.assertFalse(transfer.can_approve(self.employee1))

            # Regular employee cannot approve
            self.assertFalse(transfer.can_approve(self.employee2))

    def test_can_ship_permissions(self):
        """Test can_ship permission checks."""
        with tenant_context(self.tenant.id):
            transfer = InventoryTransfer.objects.create(
                tenant=self.tenant,
                from_branch=self.branch_a,
                to_branch=self.branch_b,
                requested_by=self.employee1,
            )

            # Employee from source branch can ship
            self.assertTrue(transfer.can_ship(self.employee1))

            # Employee from destination branch cannot ship
            self.assertFalse(transfer.can_ship(self.employee2))

    def test_can_receive_permissions(self):
        """Test can_receive permission checks."""
        with tenant_context(self.tenant.id):
            transfer = InventoryTransfer.objects.create(
                tenant=self.tenant,
                from_branch=self.branch_a,
                to_branch=self.branch_b,
                requested_by=self.employee1,
            )

            # Employee from destination branch can receive
            self.assertTrue(transfer.can_receive(self.employee2))

            # Employee from source branch cannot receive
            self.assertFalse(transfer.can_receive(self.employee1))

    def test_high_value_transfer_requires_approval(self):
        """Test that high-value transfers are flagged for approval."""
        with tenant_context(self.tenant.id):
            transfer = InventoryTransfer.objects.create(
                tenant=self.tenant,
                from_branch=self.branch_a,
                to_branch=self.branch_b,
                requested_by=self.employee1,
            )

            # Add high-value items
            InventoryTransferItem.objects.create(
                transfer=transfer,
                inventory_item=self.item1,
                quantity=10,
                unit_cost=Decimal("1500.00"),  # High value
            )

            # Check if flagged as high value
            self.assertTrue(transfer.is_high_value(threshold=Decimal("10000.00")))

    def test_complete_transfer_workflow(self):
        """Test complete transfer workflow from creation to receipt."""
        with tenant_context(self.tenant.id):
            # 1. Create transfer
            transfer = InventoryTransfer.objects.create(
                tenant=self.tenant,
                from_branch=self.branch_a,
                to_branch=self.branch_b,
                requested_by=self.employee1,
            )

            # Add items
            InventoryTransferItem.objects.create(
                transfer=transfer,
                inventory_item=self.item1,
                quantity=3,
            )

            # Record initial quantities
            initial_qty_a = self.item1.quantity

            # 2. Approve transfer
            transfer.approve(self.manager)
            transfer.save()
            self.assertEqual(transfer.status, InventoryTransfer.APPROVED)

            # 3. Ship transfer (deducts from source)
            transfer.mark_shipped(self.employee1)
            transfer.save()
            self.assertEqual(transfer.status, InventoryTransfer.IN_TRANSIT)

            self.item1.refresh_from_db()
            self.assertEqual(self.item1.quantity, initial_qty_a - 3)

            # 4. Receive transfer (adds to destination)
            transfer.mark_received(self.employee2)
            transfer.save()
            self.assertEqual(transfer.status, InventoryTransfer.RECEIVED)

            self.item1.refresh_from_db()
            # Net effect: quantity should be back to initial (deducted then added)
            self.assertEqual(self.item1.quantity, initial_qty_a)


class InventoryTransferAPITestCase(TestCase):
    """Test case for inventory transfer API endpoints."""

    def setUp(self):
        """Set up test data."""
        # Create tenant using RLS bypass
        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop Transfer API",
                slug="test-shop-transfer-api",
                status=Tenant.ACTIVE,
            )

            # Create users
            self.manager = User.objects.create_user(
                username="manager",
                email="manager@test.com",
                password="testpass123",
                tenant=self.tenant,
                role=User.TENANT_MANAGER,
            )

        # Create branches and inventory within tenant context
        with tenant_context(self.tenant.id):
            self.branch_a = Branch.objects.create(
                tenant=self.tenant,
                name="Branch A",
                is_active=True,
            )

            self.branch_b = Branch.objects.create(
                tenant=self.tenant,
                name="Branch B",
                is_active=True,
            )

            self.category = ProductCategory.objects.create(
                tenant=self.tenant,
                name="Rings",
                is_active=True,
            )

            self.item1 = InventoryItem.objects.create(
                tenant=self.tenant,
                sku="RING-001",
                name="Gold Ring 18K",
                category=self.category,
                karat=18,
                weight_grams=Decimal("5.5"),
                cost_price=Decimal("500.00"),
                selling_price=Decimal("750.00"),
                quantity=10,
                branch=self.branch_a,
            )

    def test_transfer_str_representation(self):
        """Test string representation of transfer."""
        with tenant_context(self.tenant.id):
            transfer = InventoryTransfer.objects.create(
                tenant=self.tenant,
                from_branch=self.branch_a,
                to_branch=self.branch_b,
                requested_by=self.manager,
            )

            str_repr = str(transfer)
            self.assertIn(transfer.transfer_number, str_repr)
            self.assertIn(self.branch_a.name, str_repr)
            self.assertIn(self.branch_b.name, str_repr)

    def test_transfer_item_str_representation(self):
        """Test string representation of transfer item."""
        with tenant_context(self.tenant.id):
            transfer = InventoryTransfer.objects.create(
                tenant=self.tenant,
                from_branch=self.branch_a,
                to_branch=self.branch_b,
                requested_by=self.manager,
            )

            transfer_item = InventoryTransferItem.objects.create(
                transfer=transfer,
                inventory_item=self.item1,
                quantity=3,
            )

            str_repr = str(transfer_item)
            self.assertIn(self.item1.name, str_repr)
            self.assertIn("x3", str_repr)
            self.assertIn(transfer.transfer_number, str_repr)
