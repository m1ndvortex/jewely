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

    # FSM Transitions for Custom Orders
    @transition(field=status, source="quote_requested", target="quote_provided")
    def provide_quote(self):
        """Provide quote to customer."""
        pass

    @transition(field=status, source="quote_provided", target="approved")
    def approve_quote(self):
        """Customer approves the quote."""
        pass

    @transition(field=status, source="approved", target="in_design")
    def start_design(self):
        """Start the design process."""
        pass

    @transition(field=status, source="in_design", target="design_approved")
    def approve_design(self):
        """Customer approves the design."""
        pass

    @transition(field=status, source="design_approved", target="in_production")
    def start_production(self):
        """Start production of the custom piece."""
        pass

    @transition(field=status, source="in_production", target="quality_check")
    def submit_for_quality_check(self):
        """Submit for quality check."""
        pass

    @transition(field=status, source="quality_check", target="completed")
    def complete_order(self):
        """Mark custom order as completed."""
        self.actual_completion = timezone.now()
        self.save()

    @transition(field=status, source="completed", target="delivered")
    def deliver_to_customer(self):
        """Mark as delivered to customer."""
        self.delivered_date = timezone.now()
        self.save()

    @transition(
        field=status, source=["quote_requested", "quote_provided", "approved"], target="cancelled"
    )
    def cancel_order(self):
        """Cancel the custom order."""
        pass
