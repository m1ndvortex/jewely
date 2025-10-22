"""
Transaction models for accounting journal entries.

These are placeholder models for purchase orders, payments, and expenses
that will be used for journal entry creation. These models will be moved
to their appropriate apps when those modules are implemented.
"""

import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import Tenant, User


class PurchaseOrder(models.Model):
    """
    Placeholder model for purchase orders.
    This will be moved to a procurement app when implemented.
    """

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("APPROVED", "Approved"),
        ("SENT", "Sent"),
        ("RECEIVED", "Received"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="purchase_orders")
    po_number = models.CharField(max_length=50, help_text="Purchase order number")
    supplier_name = models.CharField(max_length=255, help_text="Supplier name")
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Total purchase amount",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)

    class Meta:
        db_table = "accounting_purchase_orders"
        unique_together = [["tenant", "po_number"]]

    def __str__(self):
        return f"PO {self.po_number} - {self.supplier_name}"


class Payment(models.Model):
    """
    Placeholder model for supplier payments.
    This will be moved to a procurement app when implemented.
    """

    PAYMENT_METHOD_CHOICES = [
        ("CASH", "Cash"),
        ("CHECK", "Check"),
        ("BANK_TRANSFER", "Bank Transfer"),
        ("CARD", "Credit Card"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="payments")
    payment_number = models.CharField(max_length=50, help_text="Payment reference number")
    supplier_name = models.CharField(max_length=255, help_text="Supplier name")
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Payment amount",
    )
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_date = models.DateField(default=timezone.now)
    description = models.TextField(blank=True, help_text="Payment description")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)

    class Meta:
        db_table = "accounting_payments"
        unique_together = [["tenant", "payment_number"]]

    def __str__(self):
        return f"Payment {self.payment_number} - {self.supplier_name}"

    @property
    def supplier(self):
        """Mock supplier property for compatibility with journal entry service."""

        class MockSupplier:
            def __init__(self, name):
                self.name = name

        return MockSupplier(self.supplier_name)


class Expense(models.Model):
    """
    Placeholder model for business expenses.
    This will be moved to an expenses app when implemented.
    """

    CATEGORY_CHOICES = [
        ("RENT", "Rent"),
        ("UTILITIES", "Utilities"),
        ("INSURANCE", "Insurance"),
        ("MARKETING", "Marketing"),
        ("WAGES", "Wages"),
        ("PROFESSIONAL", "Professional Fees"),
        ("BANK_FEES", "Bank Fees"),
        ("OFFICE", "Office Expenses"),
        ("TRAVEL", "Travel"),
        ("SUPPLIES", "Supplies"),
        ("EQUIPMENT", "Equipment"),
        ("OTHER", "Other"),
    ]

    PAYMENT_METHOD_CHOICES = [
        ("CASH", "Cash"),
        ("CHECK", "Check"),
        ("BANK_TRANSFER", "Bank Transfer"),
        ("CARD", "Credit Card"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="expenses")
    description = models.CharField(max_length=255, help_text="Expense description")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Expense amount",
    )
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    expense_date = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True, help_text="Additional notes")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)

    class Meta:
        db_table = "accounting_expenses"
        ordering = ["-expense_date"]

    def __str__(self):
        return f"{self.category}: {self.description} - ${self.amount}"
