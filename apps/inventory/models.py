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

from apps.core.models import Branch, Tenant


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
