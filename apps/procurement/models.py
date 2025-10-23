"""
Procurement models for supplier and purchase order management.

This module contains models for managing suppliers, purchase orders,
purchase order items, and goods receipts with proper tenant isolation
using Row-Level Security (RLS).
"""

import uuid
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from django_fsm import FSMField, transition

from apps.core.models import Branch, Tenant, User


class Supplier(models.Model):
    """
    Supplier model for managing vendor relationships.

    Tracks supplier information, contact details, and performance ratings
    with proper tenant isolation.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="suppliers",
        help_text="Tenant that owns this supplier",
    )

    # Basic Information
    name = models.CharField(max_length=255, help_text="Supplier company name")
    contact_person = models.CharField(
        max_length=255, blank=True, help_text="Primary contact person name"
    )

    # Contact Information
    email = models.EmailField(blank=True, help_text="Primary email address")
    phone = models.CharField(max_length=20, blank=True, help_text="Primary phone number")
    address = models.TextField(blank=True, help_text="Complete address")

    # Business Information
    tax_id = models.CharField(max_length=50, blank=True, help_text="Tax identification number")
    payment_terms = models.CharField(
        max_length=100, blank=True, help_text="Payment terms (e.g., Net 30, COD)"
    )

    # Performance Tracking
    rating = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        help_text="Supplier rating from 0-5 stars",
    )

    # Status and Metadata
    is_active = models.BooleanField(default=True, help_text="Whether supplier is active")
    notes = models.TextField(blank=True, help_text="Internal notes about supplier")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="created_suppliers")

    class Meta:
        db_table = "procurement_suppliers"
        unique_together = [["tenant", "name"]]
        indexes = [
            models.Index(fields=["tenant", "is_active"]),
            models.Index(fields=["tenant", "rating"]),
            models.Index(fields=["name"]),
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}"

    def get_total_orders(self):
        """Get total number of purchase orders for this supplier."""
        return self.purchase_orders.count()

    def get_total_order_value(self):
        """Get total value of all purchase orders for this supplier."""
        return self.purchase_orders.aggregate(total=models.Sum("total_amount"))["total"] or Decimal(
            "0.00"
        )

    def get_average_delivery_time(self):
        """Calculate average delivery time in days."""
        completed_orders = self.purchase_orders.filter(status="COMPLETED")
        if not completed_orders.exists():
            return None

        total_days = 0
        count = 0
        for order in completed_orders:
            if order.expected_delivery and order.completed_at:
                delivery_days = (order.completed_at.date() - order.expected_delivery).days
                total_days += delivery_days
                count += 1

        return total_days / count if count > 0 else None


class PurchaseOrder(models.Model):
    """
    Purchase Order model with Finite State Machine for workflow management.

    Manages the complete purchase order lifecycle from draft to completion
    with proper state transitions and audit trail.
    """

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("APPROVED", "Approved"),
        ("SENT", "Sent to Supplier"),
        ("PARTIALLY_RECEIVED", "Partially Received"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    ]

    PRIORITY_CHOICES = [
        ("LOW", "Low"),
        ("NORMAL", "Normal"),
        ("HIGH", "High"),
        ("URGENT", "Urgent"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="purchase_orders",
        help_text="Tenant that owns this purchase order",
    )

    # Order Information
    po_number = models.CharField(max_length=50, help_text="Unique purchase order number")
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="purchase_orders",
        help_text="Supplier for this purchase order",
    )

    # Financial Information
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Subtotal before tax",
    )
    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Tax amount",
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Total amount including tax",
    )

    # Workflow and Status
    status = FSMField(
        default="DRAFT", choices=STATUS_CHOICES, help_text="Current status of the purchase order"
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default="NORMAL",
        help_text="Priority level of this order",
    )

    # Dates
    order_date = models.DateField(default=timezone.now, help_text="Date when order was created")
    expected_delivery = models.DateField(null=True, blank=True, help_text="Expected delivery date")

    # Branch and User Information
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Branch that will receive the goods",
    )

    # Audit Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="created_purchase_orders"
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approved_purchase_orders",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Additional Information
    notes = models.TextField(blank=True, help_text="Internal notes about this purchase order")
    supplier_reference = models.CharField(
        max_length=100, blank=True, help_text="Supplier's reference number for this order"
    )

    class Meta:
        db_table = "procurement_purchase_orders"
        unique_together = [["tenant", "po_number"]]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "supplier"]),
            models.Index(fields=["tenant", "order_date"]),
            models.Index(fields=["status", "expected_delivery"]),
        ]
        ordering = ["-order_date", "-created_at"]

    def __str__(self):
        return f"PO {self.po_number} - {self.supplier.name}"

    # FSM Transitions
    @transition(field=status, source="DRAFT", target="APPROVED")
    def approve(self, user):
        """Approve the purchase order."""
        self.approved_by = user
        self.approved_at = timezone.now()

    @transition(field=status, source="APPROVED", target="SENT")
    def send_to_supplier(self):
        """Mark order as sent to supplier."""
        self.sent_at = timezone.now()

    @transition(field=status, source="SENT", target="PARTIALLY_RECEIVED")
    def mark_partially_received(self):
        """Mark order as partially received."""
        pass

    @transition(field=status, source=["SENT", "PARTIALLY_RECEIVED"], target="COMPLETED")
    def mark_completed(self):
        """Mark order as completed."""
        self.completed_at = timezone.now()

    @transition(field=status, source=["DRAFT", "APPROVED"], target="CANCELLED")
    def cancel(self):
        """Cancel the purchase order."""
        pass

    def calculate_totals(self):
        """Calculate subtotal, tax, and total from line items."""
        items = self.items.all()
        self.subtotal = sum(item.total_price for item in items)
        # Tax calculation can be customized based on business rules
        self.tax_amount = self.subtotal * Decimal("0.00")  # No tax by default
        self.total_amount = self.subtotal + self.tax_amount
        self.save(update_fields=["subtotal", "tax_amount", "total_amount"])

    def get_received_percentage(self):
        """Calculate percentage of items received."""
        total_items = self.items.count()
        if total_items == 0:
            return 0

        received_items = sum(
            1 for item in self.items.all() if item.received_quantity >= item.quantity
        )
        return (received_items / total_items) * 100


class PurchaseOrderItem(models.Model):
    """
    Line items for purchase orders.

    Tracks individual products/items within a purchase order
    with quantities, prices, and receiving status.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="items",
        help_text="Purchase order this item belongs to",
    )

    # Product Information
    product_name = models.CharField(max_length=255, help_text="Name/description of the product")
    product_sku = models.CharField(
        max_length=100, blank=True, help_text="Product SKU or supplier part number"
    )

    # Quantities
    quantity = models.IntegerField(validators=[MinValueValidator(1)], help_text="Ordered quantity")
    received_quantity = models.IntegerField(
        default=0, validators=[MinValueValidator(0)], help_text="Quantity received so far"
    )

    # Pricing
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Price per unit",
    )
    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Total price for this line item",
    )

    # Additional Information
    notes = models.TextField(blank=True, help_text="Notes about this item")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "procurement_purchase_order_items"
        indexes = [
            models.Index(fields=["purchase_order"]),
            models.Index(fields=["product_sku"]),
        ]
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.product_name} - {self.quantity} units"

    def save(self, *args, **kwargs):
        """Auto-calculate total price on save."""
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    @property
    def remaining_quantity(self):
        """Calculate remaining quantity to be received."""
        return self.quantity - self.received_quantity

    @property
    def is_fully_received(self):
        """Check if item is fully received."""
        return self.received_quantity >= self.quantity

    def receive_quantity(self, quantity):
        """Receive a specific quantity of this item."""
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        if self.received_quantity + quantity > self.quantity:
            raise ValueError("Cannot receive more than ordered quantity")

        self.received_quantity += quantity
        self.save(update_fields=["received_quantity"])


class GoodsReceipt(models.Model):
    """
    Goods Receipt model for tracking received shipments.

    Records when goods are received from suppliers, including
    quality checks and discrepancy tracking.
    """

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("IN_PROGRESS", "In Progress"),
        ("COMPLETED", "Completed"),
        ("DISCREPANCY", "Has Discrepancy"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="goods_receipts",
        help_text="Tenant that owns this goods receipt",
    )

    # Receipt Information
    receipt_number = models.CharField(max_length=50, help_text="Unique goods receipt number")
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.PROTECT,
        related_name="goods_receipts",
        help_text="Related purchase order",
    )

    # Shipment Information
    supplier_invoice_number = models.CharField(
        max_length=100, blank=True, help_text="Supplier's invoice number"
    )
    tracking_number = models.CharField(
        max_length=100, blank=True, help_text="Shipment tracking number"
    )

    # Status and Dates
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
        help_text="Current status of goods receipt",
    )
    received_date = models.DateField(
        default=timezone.now, help_text="Date when goods were received"
    )

    # Quality and Inspection
    quality_check_passed = models.BooleanField(
        null=True, blank=True, help_text="Whether quality check passed"
    )
    inspection_notes = models.TextField(blank=True, help_text="Notes from quality inspection")

    # Discrepancy Tracking
    has_discrepancy = models.BooleanField(
        default=False, help_text="Whether there are discrepancies in this receipt"
    )
    discrepancy_notes = models.TextField(blank=True, help_text="Notes about any discrepancies")

    # Audit Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    received_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="received_goods_receipts",
        help_text="User who received the goods",
    )
    inspected_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inspected_goods_receipts",
        help_text="User who performed quality inspection",
    )

    class Meta:
        db_table = "procurement_goods_receipts"
        unique_together = [["tenant", "receipt_number"]]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "purchase_order"]),
            models.Index(fields=["received_date"]),
            models.Index(fields=["has_discrepancy"]),
        ]
        ordering = ["-received_date", "-created_at"]

    def __str__(self):
        return f"GR {self.receipt_number} - PO {self.purchase_order.po_number}"

    def mark_completed(self):
        """Mark goods receipt as completed."""
        self.status = "COMPLETED"
        self.save(update_fields=["status"])

        # Update purchase order status if all items received
        if self.purchase_order.get_received_percentage() == 100:
            if self.purchase_order.status in ["SENT", "PARTIALLY_RECEIVED"]:
                self.purchase_order.mark_completed()
        elif self.purchase_order.status == "SENT":
            self.purchase_order.mark_partially_received()

    def add_discrepancy(self, notes):
        """Add discrepancy to this goods receipt."""
        self.has_discrepancy = True
        self.status = "DISCREPANCY"
        self.discrepancy_notes = notes
        self.save(update_fields=["has_discrepancy", "status", "discrepancy_notes"])


class SupplierCommunication(models.Model):
    """
    Track communication history with suppliers.

    Records all interactions including emails, calls, meetings,
    and negotiations with suppliers for audit and reference.
    """

    COMMUNICATION_TYPES = [
        ("EMAIL", "Email"),
        ("PHONE", "Phone Call"),
        ("MEETING", "In-Person Meeting"),
        ("VIDEO_CALL", "Video Call"),
        ("SMS", "SMS/Text Message"),
        ("LETTER", "Letter/Mail"),
        ("OTHER", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name="communications",
        help_text="Supplier this communication is with",
    )

    # Communication Details
    communication_type = models.CharField(
        max_length=20, choices=COMMUNICATION_TYPES, help_text="Type of communication"
    )
    subject = models.CharField(max_length=255, help_text="Subject or topic of communication")
    content = models.TextField(help_text="Content or summary of the communication")

    # Participants
    contact_person = models.CharField(
        max_length=255, blank=True, help_text="Supplier contact person involved"
    )
    internal_participants = models.ManyToManyField(
        User,
        blank=True,
        related_name="supplier_communications",
        help_text="Internal team members involved",
    )

    # Status and Follow-up
    requires_followup = models.BooleanField(
        default=False, help_text="Whether this communication requires follow-up"
    )
    followup_date = models.DateField(
        null=True, blank=True, help_text="Date when follow-up is needed"
    )
    is_completed = models.BooleanField(
        default=True, help_text="Whether this communication is completed"
    )

    # Metadata
    communication_date = models.DateTimeField(
        default=timezone.now, help_text="Date and time of communication"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="created_supplier_communications"
    )

    class Meta:
        db_table = "procurement_supplier_communications"
        indexes = [
            models.Index(fields=["supplier", "-communication_date"]),
            models.Index(fields=["communication_type"]),
            models.Index(fields=["requires_followup", "followup_date"]),
            models.Index(fields=["is_completed"]),
        ]
        ordering = ["-communication_date"]

    def __str__(self):
        return f"{self.supplier.name} - {self.subject} ({self.communication_date.date()})"


class SupplierDocument(models.Model):
    """
    Store supplier certifications and documents.

    Manages important supplier documents including certifications,
    contracts, insurance papers, and other business documents.
    """

    DOCUMENT_TYPES = [
        ("CERTIFICATION", "Certification"),
        ("CONTRACT", "Contract"),
        ("INSURANCE", "Insurance Document"),
        ("TAX_DOCUMENT", "Tax Document"),
        ("BUSINESS_LICENSE", "Business License"),
        ("QUALITY_CERTIFICATE", "Quality Certificate"),
        ("COMPLIANCE_DOCUMENT", "Compliance Document"),
        ("INVOICE", "Invoice"),
        ("RECEIPT", "Receipt"),
        ("OTHER", "Other Document"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name="documents",
        help_text="Supplier this document belongs to",
    )

    # Document Information
    document_type = models.CharField(
        max_length=30, choices=DOCUMENT_TYPES, help_text="Type of document"
    )
    title = models.CharField(max_length=255, help_text="Document title or name")
    description = models.TextField(blank=True, help_text="Document description")

    # File Information
    file = models.FileField(upload_to="supplier_documents/%Y/%m/", help_text="Document file")
    file_size = models.BigIntegerField(null=True, blank=True, help_text="File size in bytes")
    mime_type = models.CharField(max_length=100, blank=True, help_text="MIME type of the file")

    # Validity and Status
    issue_date = models.DateField(null=True, blank=True, help_text="Date when document was issued")
    expiry_date = models.DateField(null=True, blank=True, help_text="Date when document expires")
    is_active = models.BooleanField(default=True, help_text="Whether document is currently active")

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="uploaded_supplier_documents"
    )

    class Meta:
        db_table = "procurement_supplier_documents"
        indexes = [
            models.Index(fields=["supplier", "document_type"]),
            models.Index(fields=["document_type"]),
            models.Index(fields=["expiry_date"]),
            models.Index(fields=["is_active"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.supplier.name} - {self.title}"

    def save(self, *args, **kwargs):
        """Auto-populate file metadata on save."""
        if self.file:
            self.file_size = self.file.size
            # You could add MIME type detection here if needed
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """Check if document is expired."""
        if not self.expiry_date:
            return False
        return timezone.now().date() > self.expiry_date

    @property
    def expires_soon(self):
        """Check if document expires within 30 days."""
        if not self.expiry_date:
            return False
        days_until_expiry = (self.expiry_date - timezone.now().date()).days
        return 0 <= days_until_expiry <= 30
