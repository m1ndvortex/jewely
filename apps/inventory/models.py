"""
Inventory models for jewelry shop management.

Implements Requirement 9: Advanced Inventory Management
- Serialized inventory tracking with unique serial numbers
- Lot-tracked inventory for bulk items
- Tracking by karat, weight, product type, and craftsmanship level
- Real-time inventory levels across all branches
- Inventory movements and valuation
"""

import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from django_fsm import FSMField, transition

from apps.core.models import Branch, Tenant, User


class ProductCategory(models.Model):
    """
    Product categories for organizing inventory items.

    Supports hierarchical categories with self-referential parent relationship.
    Each category is tenant-scoped for data isolation.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the category",
    )

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="product_categories",
        help_text="Tenant that owns this category",
    )

    name = models.CharField(
        max_length=100,
        help_text="Category name (e.g., Rings, Necklaces, Bracelets)",
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subcategories",
        help_text="Parent category for hierarchical organization",
    )

    description = models.TextField(
        blank=True,
        help_text="Optional description of the category",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this category is active",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "inventory_categories"
        ordering = ["name"]
        verbose_name = "Product Category"
        verbose_name_plural = "Product Categories"
        unique_together = [["tenant", "name", "parent"]]
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="cat_tenant_active_idx"),
            models.Index(fields=["tenant", "parent"], name="cat_tenant_parent_idx"),
        ]

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name

    def get_full_path(self):
        """Get the full category path (e.g., 'Jewelry > Rings > Gold Rings')."""
        path = [self.name]
        parent = self.parent
        while parent:
            path.insert(0, parent.name)
            parent = parent.parent
        return " > ".join(path)


class InventoryItem(models.Model):
    """
    Main inventory tracking model for jewelry items.

    Supports both serialized tracking (unique serial numbers for high-value items)
    and lot tracking (bulk items like gemstones) per Requirement 9.

    Implements comprehensive tracking including:
    - SKU, name, category
    - Karat, weight, craftsmanship level
    - Cost and selling prices
    - Quantity tracking
    - Branch assignment
    - Serial/lot numbers for traceability
    - Barcode/QR code support
    """

    # Craftsmanship level choices
    HANDMADE = "HANDMADE"
    MACHINE_MADE = "MACHINE_MADE"
    SEMI_HANDMADE = "SEMI_HANDMADE"

    CRAFTSMANSHIP_CHOICES = [
        (HANDMADE, "Handmade"),
        (MACHINE_MADE, "Machine Made"),
        (SEMI_HANDMADE, "Semi-Handmade"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the inventory item",
    )

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="inventory_items",
        help_text="Tenant that owns this inventory item",
    )

    # Basic information
    sku = models.CharField(
        max_length=100,
        help_text="Stock Keeping Unit - unique identifier within tenant",
    )

    name = models.CharField(
        max_length=255,
        help_text="Product name (e.g., '24K Gold Ring with Diamond')",
    )

    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.PROTECT,
        related_name="items",
        help_text="Product category",
    )

    description = models.TextField(
        blank=True,
        help_text="Detailed description of the item",
    )

    # Jewelry-specific attributes
    karat = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Gold karat (e.g., 18, 22, 24)",
    )

    weight_grams = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
        help_text="Weight in grams",
    )

    craftsmanship_level = models.CharField(
        max_length=20,
        choices=CRAFTSMANSHIP_CHOICES,
        default=MACHINE_MADE,
        help_text="Level of craftsmanship",
    )

    # Pricing
    cost_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Cost price (what we paid)",
    )

    selling_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Selling price (what we charge)",
    )

    markup_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Markup percentage over cost price",
    )

    # Inventory tracking
    quantity = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Current quantity in stock",
    )

    min_quantity = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Minimum quantity threshold for low stock alerts",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="inventory_items",
        help_text="Branch where this item is located",
    )

    # Traceability - Serialized or Lot tracking
    serial_number = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Unique serial number for high-value items (serialized tracking)",
    )

    lot_number = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Lot number for bulk items like gemstones (lot tracking)",
    )

    # Barcode/QR code support
    barcode = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        unique=True,
        help_text="Barcode for quick scanning",
    )

    qr_code = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="QR code data",
    )

    # Additional metadata
    supplier_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Supplier name",
    )

    supplier_sku = models.CharField(
        max_length=100,
        blank=True,
        help_text="Supplier's SKU/reference number",
    )

    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the item",
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this item is active in inventory",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the item was added to inventory",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the item was last updated",
    )

    class Meta:
        db_table = "inventory_items"
        ordering = ["-created_at"]
        verbose_name = "Inventory Item"
        verbose_name_plural = "Inventory Items"
        unique_together = [["tenant", "sku"]]
        indexes = [
            # Common query patterns
            models.Index(fields=["tenant", "branch"], name="inv_tenant_branch_idx"),
            models.Index(fields=["tenant", "category"], name="inv_tenant_category_idx"),
            models.Index(fields=["tenant", "is_active"], name="inv_tenant_active_idx"),
            models.Index(fields=["tenant", "karat"], name="inv_tenant_karat_idx"),
            # Search and lookup
            models.Index(fields=["sku"], name="inv_sku_idx"),
            models.Index(fields=["barcode"], name="inv_barcode_idx"),
            models.Index(fields=["serial_number"], name="inv_serial_idx"),
            models.Index(fields=["lot_number"], name="inv_lot_idx"),
            # Low stock alerts
            models.Index(
                fields=["tenant", "quantity", "min_quantity"],
                name="inv_low_stock_idx",
            ),
        ]

    def __str__(self):
        return f"{self.sku} - {self.name}"

    def save(self, *args, **kwargs):
        """
        Override save to calculate markup percentage if not provided.
        """
        if self.markup_percentage is None and self.cost_price > 0:
            self.markup_percentage = (self.selling_price - self.cost_price) / self.cost_price * 100
        super().save(*args, **kwargs)

    def is_low_stock(self):
        """Check if item is below minimum quantity threshold."""
        return self.quantity <= self.min_quantity

    def is_out_of_stock(self):
        """Check if item is out of stock."""
        return self.quantity == 0

    def is_serialized(self):
        """Check if this is a serialized item (has serial number)."""
        return bool(self.serial_number)

    def is_lot_tracked(self):
        """Check if this is a lot-tracked item (has lot number)."""
        return bool(self.lot_number)

    def calculate_total_value(self):
        """Calculate total inventory value (cost price * quantity)."""
        return self.cost_price * self.quantity

    def calculate_total_selling_value(self):
        """Calculate total selling value (selling price * quantity)."""
        return self.selling_price * self.quantity

    def calculate_profit_margin(self):
        """Calculate profit margin percentage."""
        if self.cost_price == 0:
            return Decimal("0.00")
        return ((self.selling_price - self.cost_price) / self.cost_price) * 100

    def can_deduct_quantity(self, quantity):
        """Check if we can deduct the specified quantity."""
        return self.quantity >= quantity

    def deduct_quantity(self, quantity, reason=""):
        """
        Deduct quantity from inventory.

        Args:
            quantity: Amount to deduct
            reason: Reason for deduction (for audit trail)

        Raises:
            ValueError: If insufficient quantity
        """
        if not self.can_deduct_quantity(quantity):
            raise ValueError(
                f"Insufficient inventory for {self.name}. "
                f"Available: {self.quantity}, Requested: {quantity}"
            )
        self.quantity -= quantity
        self.save(update_fields=["quantity", "updated_at"])

    def add_quantity(self, quantity, reason=""):
        """
        Add quantity to inventory.

        Args:
            quantity: Amount to add
            reason: Reason for addition (for audit trail)
        """
        self.quantity += quantity
        self.save(update_fields=["quantity", "updated_at"])


class InventoryTransfer(models.Model):
    """
    Inter-branch inventory transfer model with FSM workflow.

    Implements Requirement 14: Multi-Branch Management
    - Inter-branch inventory transfers with in-transit tracking
    - Approval workflow for high-value transfers
    - Complete audit trail of all inter-branch movements

    State transitions:
    pending → approved → in_transit → received
    pending → rejected (terminal state)
    """

    # Status choices for FSM
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_TRANSIT = "in_transit"
    RECEIVED = "received"
    CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (PENDING, "Pending Approval"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
        (IN_TRANSIT, "In Transit"),
        (RECEIVED, "Received"),
        (CANCELLED, "Cancelled"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the transfer",
    )

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="inventory_transfers",
        help_text="Tenant that owns this transfer",
    )

    transfer_number = models.CharField(
        max_length=50,
        help_text="Unique transfer number (e.g., TRF-20231015-001)",
    )

    from_branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="transfers_out",
        help_text="Source branch sending the inventory",
    )

    to_branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="transfers_in",
        help_text="Destination branch receiving the inventory",
    )

    # FSM status field
    status = FSMField(
        default=PENDING,
        choices=STATUS_CHOICES,
        protected=True,
        help_text="Current status of the transfer",
    )

    # Workflow tracking
    requested_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="transfers_requested",
        help_text="User who requested the transfer",
    )

    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfers_approved",
        help_text="User who approved the transfer",
    )

    rejected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfers_rejected",
        help_text="User who rejected the transfer",
    )

    shipped_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfers_shipped",
        help_text="User who marked the transfer as shipped",
    )

    received_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfers_received",
        help_text="User who received the transfer",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the transfer was requested",
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the transfer was approved",
    )

    rejected_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the transfer was rejected",
    )

    shipped_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the transfer was shipped",
    )

    received_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the transfer was received",
    )

    # Additional information
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the transfer",
    )

    rejection_reason = models.TextField(
        blank=True,
        help_text="Reason for rejection",
    )

    # High-value transfer flag (requires approval)
    requires_approval = models.BooleanField(
        default=False,
        help_text="Whether this transfer requires approval (high-value items)",
    )

    total_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total value of items being transferred",
    )

    class Meta:
        db_table = "inventory_transfers"
        ordering = ["-created_at"]
        verbose_name = "Inventory Transfer"
        verbose_name_plural = "Inventory Transfers"
        unique_together = [["tenant", "transfer_number"]]
        indexes = [
            models.Index(fields=["tenant", "status"], name="transfer_tenant_status_idx"),
            models.Index(fields=["tenant", "from_branch"], name="transfer_from_branch_idx"),
            models.Index(fields=["tenant", "to_branch"], name="transfer_to_branch_idx"),
            models.Index(fields=["tenant", "-created_at"], name="transfer_created_idx"),
            models.Index(fields=["status", "-created_at"], name="transfer_status_created_idx"),
        ]

    def __str__(self):
        return f"{self.transfer_number} ({self.from_branch.name} → {self.to_branch.name})"

    def save(self, *args, **kwargs):
        """Generate transfer number if not provided."""
        if not self.transfer_number:
            from django.utils import timezone

            date_str = timezone.now().strftime("%Y%m%d")
            # Get count of transfers today for this tenant
            today_count = (
                InventoryTransfer.objects.filter(
                    tenant=self.tenant, transfer_number__startswith=f"TRF-{date_str}"
                ).count()
                + 1
            )
            self.transfer_number = f"TRF-{date_str}-{today_count:04d}"

        super().save(*args, **kwargs)

    @transition(field=status, source=PENDING, target=APPROVED)
    def approve(self, user):
        """
        Approve the transfer request.

        Args:
            user: User approving the transfer
        """
        from django.utils import timezone

        self.approved_by = user
        self.approved_at = timezone.now()

    @transition(field=status, source=PENDING, target=REJECTED)
    def reject(self, user, reason=""):
        """
        Reject the transfer request.

        Args:
            user: User rejecting the transfer
            reason: Reason for rejection
        """
        from django.utils import timezone

        self.rejected_by = user
        self.rejected_at = timezone.now()
        self.rejection_reason = reason

    @transition(field=status, source=APPROVED, target=IN_TRANSIT)
    def mark_shipped(self, user):
        """
        Mark the transfer as shipped/in transit.

        Args:
            user: User marking the transfer as shipped
        """
        from django.utils import timezone

        self.shipped_by = user
        self.shipped_at = timezone.now()

        # Deduct inventory from source branch
        for item in self.items.all():
            item.inventory_item.deduct_quantity(
                item.quantity, reason=f"Transfer {self.transfer_number} to {self.to_branch.name}"
            )

    @transition(field=status, source=IN_TRANSIT, target=RECEIVED)
    def mark_received(self, user, discrepancies=None):
        """
        Mark the transfer as received at destination.

        Args:
            user: User receiving the transfer
            discrepancies: Dict of item_id -> actual_quantity for items with discrepancies
        """
        from django.utils import timezone

        self.received_by = user
        self.received_at = timezone.now()

        # Process each item
        for item in self.items.all():
            actual_quantity = item.quantity
            if discrepancies and str(item.id) in discrepancies:
                actual_quantity = discrepancies[str(item.id)]
                # Log discrepancy
                item.received_quantity = actual_quantity
                item.has_discrepancy = True
                item.discrepancy_notes = (
                    f"Expected: {item.quantity}, Received: {actual_quantity}, "
                    f"Difference: {actual_quantity - item.quantity}"
                )
                item.save()

            # Add inventory to destination branch
            # Note: In a real system, we might need to create new inventory items
            # or update existing ones at the destination branch
            # For now, we'll assume the inventory item exists at destination
            item.inventory_item.add_quantity(
                actual_quantity,
                reason=f"Transfer {self.transfer_number} from {self.from_branch.name}",
            )

    @transition(field=status, source=[PENDING, APPROVED], target=CANCELLED)
    def cancel(self, user, reason=""):
        """
        Cancel the transfer.

        Args:
            user: User cancelling the transfer
            reason: Reason for cancellation
        """
        self.notes = f"{self.notes}\n\nCancelled by {user.username}: {reason}".strip()

    def calculate_total_value(self):
        """Calculate total value of all items in the transfer."""
        total = sum(item.calculate_value() for item in self.items.all())
        return total

    def is_high_value(self, threshold=Decimal("10000.00")):
        """
        Check if this is a high-value transfer requiring approval.

        Args:
            threshold: Value threshold for requiring approval (default: 10,000)

        Returns:
            bool: True if total value exceeds threshold
        """
        return self.calculate_total_value() >= threshold

    def can_approve(self, user):
        """Check if user can approve this transfer."""
        # User must be a manager or owner, and not the requester
        return (
            user.can_manage_inventory()
            and user != self.requested_by
            and user.tenant_id == self.tenant_id
        )

    def can_ship(self, user):
        """Check if user can mark this transfer as shipped."""
        # User must be from the source branch
        return user.branch_id == self.from_branch_id and user.tenant_id == self.tenant_id

    def can_receive(self, user):
        """Check if user can receive this transfer."""
        # User must be from the destination branch
        return user.branch_id == self.to_branch_id and user.tenant_id == self.tenant_id


class InventoryTransferItem(models.Model):
    """
    Individual items in an inventory transfer.

    Tracks each inventory item being transferred with quantity and discrepancy logging.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the transfer item",
    )

    transfer = models.ForeignKey(
        InventoryTransfer,
        on_delete=models.CASCADE,
        related_name="items",
        help_text="Transfer this item belongs to",
    )

    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name="transfer_items",
        help_text="Inventory item being transferred",
    )

    quantity = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Quantity to transfer",
    )

    # Receiving information
    received_quantity = models.IntegerField(
        null=True,
        blank=True,
        help_text="Actual quantity received (may differ from requested)",
    )

    has_discrepancy = models.BooleanField(
        default=False,
        help_text="Whether there was a discrepancy between sent and received quantities",
    )

    discrepancy_notes = models.TextField(
        blank=True,
        help_text="Notes about any discrepancies",
    )

    # Value tracking
    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Cost per unit at time of transfer",
    )

    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this item",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "inventory_transfer_items"
        ordering = ["created_at"]
        verbose_name = "Inventory Transfer Item"
        verbose_name_plural = "Inventory Transfer Items"
        indexes = [
            models.Index(fields=["transfer", "inventory_item"], name="transfer_item_idx"),
        ]

    def __str__(self):
        return f"{self.inventory_item.name} x{self.quantity} ({self.transfer.transfer_number})"

    def save(self, *args, **kwargs):
        """Capture unit cost from inventory item if not provided."""
        if not self.unit_cost:
            self.unit_cost = self.inventory_item.cost_price
        super().save(*args, **kwargs)

    def calculate_value(self):
        """Calculate total value of this transfer item."""
        return self.unit_cost * self.quantity

    def get_discrepancy_quantity(self):
        """Get the quantity discrepancy (received - expected)."""
        if self.received_quantity is not None:
            return self.received_quantity - self.quantity
        return 0
