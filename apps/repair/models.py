"""
Repair and Custom Order models for jewelry shop management.

This module contains models for tracking repair orders and custom jewelry orders
with finite state machine (FSM) for status management.
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from django_fsm import FSMField, transition


class RepairOrder(models.Model):
    """
    Model for tracking repair orders with FSM state management.

    Tracks repair orders from receipt through completion and delivery,
    with automatic state transitions and business logic enforcement.
    """

    # Service type choices
    SERVICE_TYPE_CHOICES = [
        ("CLEANING", "Cleaning"),
        ("POLISHING", "Polishing"),
        ("RESIZING", "Resizing"),
        ("STONE_SETTING", "Stone Setting"),
        ("CHAIN_REPAIR", "Chain Repair"),
        ("CLASP_REPAIR", "Clasp Repair"),
        ("PRONG_REPAIR", "Prong Repair"),
        ("ENGRAVING", "Engraving"),
        ("RHODIUM_PLATING", "Rhodium Plating"),
        ("CUSTOM_WORK", "Custom Work"),
        ("OTHER", "Other"),
    ]

    # Status choices for FSM
    STATUS_CHOICES = [
        ("received", "Received"),
        ("in_progress", "In Progress"),
        ("quality_check", "Quality Check"),
        ("completed", "Completed"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]

    # Priority choices
    PRIORITY_CHOICES = [
        ("LOW", "Low"),
        ("NORMAL", "Normal"),
        ("HIGH", "High"),
        ("URGENT", "Urgent"),
    ]

    # Core fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="repair_orders"
    )
    order_number = models.CharField(max_length=50, help_text="Unique order number for tracking")
    customer = models.ForeignKey(
        "crm.Customer", on_delete=models.PROTECT, related_name="repair_orders"
    )

    # Item details
    item_description = models.TextField(help_text="Detailed description of the item to be repaired")
    service_type = models.CharField(
        max_length=20, choices=SERVICE_TYPE_CHOICES, help_text="Type of service/repair needed"
    )
    service_notes = models.TextField(
        blank=True, help_text="Additional notes about the service required"
    )

    # Status and workflow
    status = FSMField(
        default="received", choices=STATUS_CHOICES, help_text="Current status of the repair order"
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default="NORMAL",
        help_text="Priority level of the repair",
    )

    # Dates
    received_date = models.DateTimeField(
        default=timezone.now, help_text="Date and time when the item was received"
    )
    estimated_completion = models.DateField(help_text="Estimated completion date")
    actual_completion = models.DateTimeField(
        null=True, blank=True, help_text="Actual completion date and time"
    )
    delivered_date = models.DateTimeField(
        null=True, blank=True, help_text="Date and time when item was delivered to customer"
    )

    # Pricing
    cost_estimate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Estimated cost for the repair",
    )
    final_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Final cost charged to customer",
    )

    # Staff assignment
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_repairs",
        help_text="Staff member assigned to this repair",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_repairs"
    )

    class Meta:
        db_table = "repair_orders"
        unique_together = [["tenant", "order_number"]]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "customer"]),
            models.Index(fields=["tenant", "estimated_completion"]),
            models.Index(fields=["tenant", "priority", "status"]),
            models.Index(fields=["assigned_to", "status"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.order_number} - {self.customer} ({self.get_status_display()})"

    @property
    def is_overdue(self):
        """Check if the repair is overdue based on estimated completion date."""
        if self.status in ["completed", "delivered", "cancelled"]:
            return False
        return timezone.now().date() > self.estimated_completion

    @property
    def days_until_due(self):
        """Calculate days until due date (negative if overdue)."""
        if self.status in ["completed", "delivered", "cancelled"]:
            return None
        delta = self.estimated_completion - timezone.now().date()
        return delta.days

    # FSM Transitions
    @transition(field=status, source="received", target="in_progress")
    def start_work(self, user=None):
        """Start work on the repair order."""
        if user and not self.assigned_to:
            self.assigned_to = user
        self.save()

    @transition(field=status, source="in_progress", target="quality_check")
    def submit_for_quality_check(self):
        """Submit repair for quality check."""
        pass

    @transition(field=status, source="quality_check", target="in_progress")
    def return_to_work(self):
        """Return repair to work (failed quality check)."""
        pass

    @transition(field=status, source="quality_check", target="completed")
    def complete_work(self):
        """Mark repair as completed."""
        self.actual_completion = timezone.now()
        self.save()

    @transition(field=status, source="completed", target="delivered")
    def deliver_to_customer(self):
        """Mark repair as delivered to customer."""
        self.delivered_date = timezone.now()
        self.save()

    @transition(field=status, source=["received", "in_progress"], target="cancelled")
    def cancel_order(self):
        """Cancel the repair order."""
        pass

    def can_start_work(self):
        """Check if work can be started on this order."""
        return self.status == "received"

    def can_complete(self):
        """Check if order can be marked as completed."""
        return self.status == "quality_check"

    def can_deliver(self):
        """Check if order can be delivered."""
        return self.status == "completed"


class RepairOrderPhoto(models.Model):
    """
    Model for storing photos of repair items for documentation.

    Stores before/after photos and condition documentation for repair orders.
    """

    PHOTO_TYPE_CHOICES = [
        ("BEFORE", "Before Repair"),
        ("DURING", "During Repair"),
        ("AFTER", "After Repair"),
        ("DAMAGE", "Damage Documentation"),
        ("REFERENCE", "Reference Photo"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repair_order = models.ForeignKey(RepairOrder, on_delete=models.CASCADE, related_name="photos")
    photo = models.ImageField(
        upload_to="repair_photos/%Y/%m/%d/", help_text="Photo of the repair item"
    )
    photo_type = models.CharField(
        max_length=10, choices=PHOTO_TYPE_CHOICES, help_text="Type/purpose of the photo"
    )
    description = models.TextField(blank=True, help_text="Description or notes about the photo")
    taken_at = models.DateTimeField(default=timezone.now, help_text="When the photo was taken")
    taken_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        help_text="Staff member who took the photo",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "repair_order_photos"
        indexes = [
            models.Index(fields=["repair_order", "photo_type"]),
            models.Index(fields=["repair_order", "taken_at"]),
        ]
        ordering = ["taken_at"]

    def __str__(self):
        return f"{self.repair_order.order_number} - {self.get_photo_type_display()}"


class CustomOrder(models.Model):
    """
    Model for tracking custom jewelry orders.

    Handles custom design requests with material specifications and pricing.
    """

    STATUS_CHOICES = [
        ("quote_requested", "Quote Requested"),
        ("quote_provided", "Quote Provided"),
        ("approved", "Approved"),
        ("in_design", "In Design"),
        ("design_approved", "Design Approved"),
        ("in_production", "In Production"),
        ("quality_check", "Quality Check"),
        ("completed", "Completed"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]

    COMPLEXITY_CHOICES = [
        ("SIMPLE", "Simple"),
        ("MODERATE", "Moderate"),
        ("COMPLEX", "Complex"),
        ("VERY_COMPLEX", "Very Complex"),
    ]

    # Core fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="custom_orders"
    )
    order_number = models.CharField(max_length=50, help_text="Unique order number for tracking")
    customer = models.ForeignKey(
        "crm.Customer", on_delete=models.PROTECT, related_name="custom_orders"
    )

    # Design details
    design_description = models.TextField(help_text="Detailed description of the custom design")
    design_specifications = models.JSONField(
        default=dict, help_text="Technical specifications (dimensions, materials, etc.)"
    )
    complexity = models.CharField(
        max_length=15,
        choices=COMPLEXITY_CHOICES,
        default="MODERATE",
        help_text="Complexity level of the custom work",
    )

    # Status and workflow
    status = FSMField(
        default="quote_requested",
        choices=STATUS_CHOICES,
        help_text="Current status of the custom order",
    )

    # Dates
    requested_date = models.DateTimeField(
        default=timezone.now, help_text="Date when custom order was requested"
    )
    estimated_completion = models.DateField(
        null=True, blank=True, help_text="Estimated completion date"
    )
    actual_completion = models.DateTimeField(
        null=True, blank=True, help_text="Actual completion date and time"
    )
    delivered_date = models.DateTimeField(
        null=True, blank=True, help_text="Date when item was delivered to customer"
    )

    # Pricing
    quoted_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Quoted price for the custom work",
    )
    final_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Final price charged to customer",
    )
    deposit_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Deposit amount paid by customer",
    )

    # Material and labor costs (for pricing calculation)
    material_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Total cost of materials required",
    )
    labor_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Estimated labor cost",
    )
    overhead_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("20.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Overhead percentage to add to costs",
    )
    profit_margin_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("30.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Profit margin percentage",
    )

    # Link to inventory when completed
    created_inventory_item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_custom_order",
        help_text="Inventory item created from this custom order when completed",
    )

    # Staff assignment
    designer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="designed_orders",
        help_text="Designer assigned to this custom order",
    )
    craftsman = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="crafted_orders",
        help_text="Craftsman assigned to create the piece",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_custom_orders"
    )

    class Meta:
        db_table = "custom_orders"
        unique_together = [["tenant", "order_number"]]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "customer"]),
            models.Index(fields=["tenant", "estimated_completion"]),
            models.Index(fields=["designer", "status"]),
            models.Index(fields=["craftsman", "status"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.order_number} - {self.customer} ({self.get_status_display()})"

    @property
    def is_overdue(self):
        """Check if the custom order is overdue."""
        if not self.estimated_completion or self.status in ["completed", "delivered", "cancelled"]:
            return False
        return timezone.now().date() > self.estimated_completion

    @property
    def remaining_balance(self):
        """Calculate remaining balance after deposit."""
        if self.final_price:
            return self.final_price - self.deposit_amount
        elif self.quoted_price:
            return self.quoted_price - self.deposit_amount
        return Decimal("0.00")

    @property
    def total_material_cost(self):
        """Calculate total cost of all required materials."""
        return sum(req.total_cost for req in self.material_requirements.all())

    def calculate_pricing(self):
        """
        Calculate pricing for the custom order based on materials, labor, overhead, and profit margin.

        Returns:
            dict: Dictionary containing pricing breakdown
        """
        # Get total material cost from requirements
        material_cost = self.total_material_cost

        # Use stored labor cost or calculate based on complexity
        labor_cost = self.labor_cost
        if labor_cost == 0:
            # Default labor cost based on complexity
            complexity_multipliers = {
                "SIMPLE": Decimal("50.00"),
                "MODERATE": Decimal("100.00"),
                "COMPLEX": Decimal("200.00"),
                "VERY_COMPLEX": Decimal("400.00"),
            }
            labor_cost = complexity_multipliers.get(self.complexity, Decimal("100.00"))

        # Calculate base cost
        base_cost = material_cost + labor_cost

        # Add overhead
        overhead_amount = base_cost * (self.overhead_percentage / 100)
        cost_with_overhead = base_cost + overhead_amount

        # Add profit margin
        profit_amount = cost_with_overhead * (self.profit_margin_percentage / 100)
        final_price = cost_with_overhead + profit_amount

        return {
            "material_cost": material_cost,
            "labor_cost": labor_cost,
            "base_cost": base_cost,
            "overhead_percentage": self.overhead_percentage,
            "overhead_amount": overhead_amount,
            "cost_with_overhead": cost_with_overhead,
            "profit_margin_percentage": self.profit_margin_percentage,
            "profit_amount": profit_amount,
            "final_price": final_price,
        }

    def update_pricing(self):
        """Update the quoted price based on current material requirements and settings."""
        pricing = self.calculate_pricing()
        self.material_cost = pricing["material_cost"]
        self.labor_cost = pricing["labor_cost"]
        self.quoted_price = pricing["final_price"]
        self.save(update_fields=["material_cost", "labor_cost", "quoted_price", "updated_at"])
        return pricing

    def create_inventory_item(self, branch, sku=None):
        """
        Create an inventory item from this completed custom order.

        Args:
            branch: Branch where the item will be stored
            sku: Optional SKU, will be auto-generated if not provided

        Returns:
            InventoryItem: The created inventory item

        Raises:
            ValueError: If order is not completed or inventory item already exists
        """
        from apps.inventory.models import InventoryItem, ProductCategory

        if self.status != "completed":
            raise ValueError("Can only create inventory from completed custom orders")

        if self.created_inventory_item:
            raise ValueError("Inventory item already created for this custom order")

        # Generate SKU if not provided
        if not sku:
            sku = f"CUSTOM-{self.order_number}"

        # Get or create a "Custom Orders" category
        category, _ = ProductCategory.objects.get_or_create(
            tenant=self.tenant,
            name="Custom Orders",
            defaults={
                "description": "Items created from custom orders",
                "is_active": True,
            },
        )

        # Extract specifications for inventory item
        specs = self.design_specifications or {}
        karat = specs.get("karat", 18)  # Default to 18K
        weight = specs.get("weight_grams", Decimal("10.0"))  # Default weight

        # Create inventory item
        inventory_item = InventoryItem.objects.create(
            tenant=self.tenant,
            sku=sku,
            name=f"Custom: {self.design_description[:100]}",
            category=category,
            description=f"Custom order {self.order_number}: {self.design_description}",
            karat=karat,
            weight_grams=weight,
            craftsmanship_level="HANDMADE",  # Custom orders are typically handmade
            cost_price=self.material_cost + self.labor_cost,
            selling_price=self.final_price or self.quoted_price,
            quantity=1,  # Custom orders typically produce one item
            branch=branch,
            serial_number=f"CUSTOM-{self.order_number}",
            notes=f"Created from custom order {self.order_number}",
            is_active=True,
        )

        # Link the inventory item to this custom order
        self.created_inventory_item = inventory_item
        self.save(update_fields=["created_inventory_item", "updated_at"])

        return inventory_item

    def generate_work_order(self, craftsman=None, notes=None):
        """
        Generate a work order for this custom order.

        Args:
            craftsman: User instance to assign as craftsman
            notes: Optional additional notes

        Returns:
            dict: Work order details
        """
        from .services import WorkOrderGenerator

        work_order = WorkOrderGenerator.generate_work_order(self, craftsman, notes)

        # Send work order to craftsman if assigned
        if self.craftsman:
            WorkOrderGenerator.send_work_order_to_craftsman(work_order, self)

        return work_order

    # FSM Transitions for Custom Orders
    @transition(field=status, source="quote_requested", target="quote_provided")
    def provide_quote(self):
        """Provide quote to customer."""
        from .services import send_custom_order_status_notification

        send_custom_order_status_notification(self)

    @transition(field=status, source="quote_provided", target="approved")
    def approve_quote(self):
        """Customer approves the quote."""
        from .services import send_custom_order_status_notification

        send_custom_order_status_notification(self)

    @transition(field=status, source="approved", target="in_design")
    def start_design(self):
        """Start the design process."""
        from .services import send_custom_order_status_notification

        send_custom_order_status_notification(self)

    @transition(field=status, source="in_design", target="design_approved")
    def approve_design(self):
        """Customer approves the design."""
        from .services import send_custom_order_status_notification

        send_custom_order_status_notification(self)

    @transition(field=status, source="design_approved", target="in_production")
    def start_production(self):
        """Start production of the custom piece."""
        from .services import send_custom_order_status_notification

        send_custom_order_status_notification(self)

    @transition(field=status, source="in_production", target="quality_check")
    def submit_for_quality_check(self):
        """Submit for quality check."""
        from .services import send_custom_order_status_notification

        send_custom_order_status_notification(self)

    @transition(field=status, source="quality_check", target="completed")
    def complete_order(self):
        """Mark custom order as completed."""
        self.actual_completion = timezone.now()
        self.save()

        # Send notification to customer
        from .services import send_custom_order_status_notification

        send_custom_order_status_notification(self)

    @transition(field=status, source="completed", target="delivered")
    def deliver_to_customer(self):
        """Mark as delivered to customer."""
        self.delivered_date = timezone.now()
        self.save()

        # Send notification to customer
        from .services import send_custom_order_status_notification

        send_custom_order_status_notification(self)

    @transition(
        field=status, source=["quote_requested", "quote_provided", "approved"], target="cancelled"
    )
    def cancel_order(self):
        """Cancel the custom order."""
        pass


class MaterialRequirement(models.Model):
    """
    Model for tracking material requirements for custom orders.

    Tracks what materials are needed, quantities, costs, and sourcing information.
    This model matches the existing database structure.
    """

    MATERIAL_TYPE_CHOICES = [
        ("GOLD", "Gold"),
        ("SILVER", "Silver"),
        ("PLATINUM", "Platinum"),
        ("DIAMOND", "Diamond"),
        ("GEMSTONE", "Gemstone"),
        ("PEARL", "Pearl"),
        ("CHAIN", "Chain"),
        ("FINDING", "Finding/Component"),
        ("TOOL", "Tool/Equipment"),
        ("OTHER", "Other"),
    ]

    UNIT_CHOICES = [
        ("GRAMS", "Grams"),
        ("PIECES", "Pieces"),
        ("CARATS", "Carats"),
        ("METERS", "Meters"),
        ("SETS", "Sets"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    custom_order = models.ForeignKey(
        CustomOrder,
        on_delete=models.CASCADE,
        related_name="material_requirements",
        help_text="Custom order this material is required for",
    )

    # Material details (matching existing structure)
    material_type = models.CharField(
        max_length=20,
        choices=MATERIAL_TYPE_CHOICES,
        help_text="Type of material",
    )
    material_name = models.CharField(
        max_length=255,
        help_text="Name/description of the material",
    )
    specifications = models.JSONField(
        default=dict,
        help_text="Detailed specifications (purity, color, grade, etc.)",
    )

    # Quantity and units (matching existing structure)
    quantity_required = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
        help_text="Quantity required",
    )
    unit = models.CharField(
        max_length=15,  # Matching existing structure
        choices=UNIT_CHOICES,
        help_text="Unit of measurement",
    )

    # Pricing (matching existing structure)
    estimated_cost_per_unit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Estimated cost per unit",
    )
    actual_cost_per_unit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Actual cost per unit",
    )

    # Sourcing (matching existing structure)
    supplier_info = models.CharField(
        max_length=255,
        default="",
        help_text="Supplier information",
    )

    # Notes (matching existing structure)
    notes = models.TextField(
        default="",
        help_text="Additional notes about this material requirement",
    )

    # Status tracking (matching existing structure)
    is_acquired = models.BooleanField(
        default=False,
        help_text="Whether this material has been acquired",
    )
    acquired_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date when material was acquired",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "material_requirements"
        indexes = [
            models.Index(
                fields=["custom_order", "is_acquired"], name="material_re_custom__0fb28b_idx"
            ),
            models.Index(
                fields=["custom_order", "material_type"], name="material_re_custom__508f24_idx"
            ),
        ]
        ordering = ["material_type", "material_name"]

    def __str__(self):
        return f"{self.material_name} ({self.quantity_required} {self.unit}) for {self.custom_order.order_number}"

    @property
    def total_estimated_cost(self):
        """Calculate total estimated cost for this material requirement."""
        return self.quantity_required * self.estimated_cost_per_unit

    @property
    def total_actual_cost(self):
        """Calculate total actual cost for this material requirement."""
        if self.actual_cost_per_unit:
            return self.quantity_required * self.actual_cost_per_unit
        return self.total_estimated_cost

    @property
    def unit_cost(self):
        """Get the unit cost (actual if available, otherwise estimated)."""
        return self.actual_cost_per_unit or self.estimated_cost_per_unit

    @property
    def total_cost(self):
        """Get the total cost (actual if available, otherwise estimated)."""
        return self.total_actual_cost

    def mark_as_acquired(self, actual_cost_per_unit=None):
        """
        Mark this material requirement as acquired.

        Args:
            actual_cost_per_unit: Optional actual cost per unit
        """
        self.is_acquired = True
        self.acquired_date = timezone.now()
        if actual_cost_per_unit is not None:
            self.actual_cost_per_unit = actual_cost_per_unit
        self.save(
            update_fields=["is_acquired", "acquired_date", "actual_cost_per_unit", "updated_at"]
        )

    def can_source_from_inventory(self, inventory_item):
        """Check if this requirement can be sourced from existing inventory."""
        return inventory_item.can_deduct_quantity(int(self.quantity_required))

    def source_from_inventory(self, inventory_item):
        """
        Source this material requirement from existing inventory.

        Args:
            inventory_item: InventoryItem to source from

        Raises:
            ValueError: If insufficient inventory or already acquired
        """
        if self.is_acquired:
            raise ValueError("Material requirement is already acquired")

        if not inventory_item.can_deduct_quantity(int(self.quantity_required)):
            raise ValueError(
                f"Insufficient inventory. Available: {inventory_item.quantity}, Required: {self.quantity_required}"
            )

        # Deduct from inventory
        inventory_item.deduct_quantity(
            int(self.quantity_required),
            reason=f"Used for custom order {self.custom_order.order_number}",
        )

        # Mark as acquired with inventory cost
        self.mark_as_acquired(actual_cost_per_unit=inventory_item.cost_price)
        self.supplier_info = f"Internal inventory: {inventory_item.sku}"
        self.save(update_fields=["supplier_info", "updated_at"])
