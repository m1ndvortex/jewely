"""
Cache invalidation signals for smart cache management.

This module provides signal handlers to automatically invalidate cache
when models are created, updated, or deleted.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.core.cache_utils import invalidate_tenant_cache

# Inventory cache invalidation


@receiver(post_save, sender="inventory.InventoryItem")
@receiver(post_delete, sender="inventory.InventoryItem")
def invalidate_inventory_cache(sender, instance, **kwargs):
    """Invalidate inventory-related cache when items change."""
    if hasattr(instance, "tenant_id"):
        # Invalidate tenant-specific inventory cache
        invalidate_tenant_cache(instance.tenant_id, prefix="inventory")
        invalidate_tenant_cache(instance.tenant_id, prefix="dashboard")

        # Invalidate branch-specific cache if applicable
        if hasattr(instance, "branch_id") and instance.branch_id:
            invalidate_tenant_cache(
                instance.tenant_id, prefix=f"inventory:branch:{instance.branch_id}"
            )


@receiver(post_save, sender="inventory.ProductCategory")
@receiver(post_delete, sender="inventory.ProductCategory")
def invalidate_category_cache(sender, instance, **kwargs):
    """Invalidate category cache when categories change."""
    if hasattr(instance, "tenant_id"):
        invalidate_tenant_cache(instance.tenant_id, prefix="category")
        invalidate_tenant_cache(instance.tenant_id, prefix="inventory")


# Sales cache invalidation


@receiver(post_save, sender="sales.Sale")
@receiver(post_delete, sender="sales.Sale")
def invalidate_sales_cache(sender, instance, **kwargs):
    """Invalidate sales-related cache when sales change."""
    if hasattr(instance, "tenant_id"):
        # Invalidate tenant-specific sales cache
        invalidate_tenant_cache(instance.tenant_id, prefix="sales")
        invalidate_tenant_cache(instance.tenant_id, prefix="dashboard")
        invalidate_tenant_cache(instance.tenant_id, prefix="report")

        # Invalidate branch-specific cache
        if hasattr(instance, "branch_id") and instance.branch_id:
            invalidate_tenant_cache(instance.tenant_id, prefix=f"sales:branch:{instance.branch_id}")

        # Invalidate customer-specific cache
        if hasattr(instance, "customer_id") and instance.customer_id:
            invalidate_tenant_cache(instance.tenant_id, prefix=f"customer:{instance.customer_id}")


# Customer cache invalidation


@receiver(post_save, sender="crm.Customer")
@receiver(post_delete, sender="crm.Customer")
def invalidate_customer_cache(sender, instance, **kwargs):
    """Invalidate customer-related cache when customers change."""
    if hasattr(instance, "tenant_id"):
        invalidate_tenant_cache(instance.tenant_id, prefix="customer")
        invalidate_tenant_cache(instance.tenant_id, prefix="crm")

        # Invalidate specific customer cache
        if instance.id:
            invalidate_tenant_cache(instance.tenant_id, prefix=f"customer:{instance.id}")


@receiver(post_save, sender="crm.LoyaltyTransaction")
@receiver(post_delete, sender="crm.LoyaltyTransaction")
def invalidate_loyalty_cache(sender, instance, **kwargs):
    """Invalidate loyalty cache when transactions change."""
    if hasattr(instance, "customer") and instance.customer:
        customer = instance.customer
        if hasattr(customer, "tenant_id"):
            invalidate_tenant_cache(customer.tenant_id, prefix=f"customer:{customer.id}:loyalty")


# Accounting cache invalidation


@receiver(post_save, sender="accounting.Expense")
@receiver(post_delete, sender="accounting.Expense")
def invalidate_accounting_cache(sender, instance, **kwargs):
    """Invalidate accounting cache when journal entries change."""
    if hasattr(instance, "tenant_id"):
        invalidate_tenant_cache(instance.tenant_id, prefix="accounting")
        invalidate_tenant_cache(instance.tenant_id, prefix="financial_report")
        invalidate_tenant_cache(instance.tenant_id, prefix="dashboard")


@receiver(post_save, sender="accounting.Bill")
@receiver(post_delete, sender="accounting.Bill")
def invalidate_bill_cache(sender, instance, **kwargs):
    """Invalidate bill cache when bills change."""
    if hasattr(instance, "tenant_id"):
        invalidate_tenant_cache(instance.tenant_id, prefix="bill")
        invalidate_tenant_cache(instance.tenant_id, prefix="accounting")
        invalidate_tenant_cache(instance.tenant_id, prefix="payable")


@receiver(post_save, sender="accounting.Invoice")
@receiver(post_delete, sender="accounting.Invoice")
def invalidate_invoice_cache(sender, instance, **kwargs):
    """Invalidate invoice cache when invoices change."""
    if hasattr(instance, "tenant_id"):
        invalidate_tenant_cache(instance.tenant_id, prefix="invoice")
        invalidate_tenant_cache(instance.tenant_id, prefix="accounting")
        invalidate_tenant_cache(instance.tenant_id, prefix="receivable")


# Repair order cache invalidation


@receiver(post_save, sender="repair.RepairOrder")
@receiver(post_delete, sender="repair.RepairOrder")
def invalidate_repair_cache(sender, instance, **kwargs):
    """Invalidate repair order cache when orders change."""
    if hasattr(instance, "tenant_id"):
        invalidate_tenant_cache(instance.tenant_id, prefix="repair")
        invalidate_tenant_cache(instance.tenant_id, prefix="dashboard")


# Procurement cache invalidation


@receiver(post_save, sender="procurement.PurchaseOrder")
@receiver(post_delete, sender="procurement.PurchaseOrder")
def invalidate_purchase_order_cache(sender, instance, **kwargs):
    """Invalidate purchase order cache when POs change."""
    if hasattr(instance, "tenant_id"):
        invalidate_tenant_cache(instance.tenant_id, prefix="purchase_order")
        invalidate_tenant_cache(instance.tenant_id, prefix="procurement")
        invalidate_tenant_cache(instance.tenant_id, prefix="dashboard")


@receiver(post_save, sender="procurement.Supplier")
@receiver(post_delete, sender="procurement.Supplier")
def invalidate_supplier_cache(sender, instance, **kwargs):
    """Invalidate supplier cache when suppliers change."""
    if hasattr(instance, "tenant_id"):
        invalidate_tenant_cache(instance.tenant_id, prefix="supplier")
        invalidate_tenant_cache(instance.tenant_id, prefix="procurement")


# Pricing cache invalidation


@receiver(post_save, sender="pricing.GoldRate")
def invalidate_gold_rate_cache(sender, instance, **kwargs):
    """Invalidate gold rate cache when rates change."""
    from apps.core.cache_utils import invalidate_cache

    # Invalidate global gold rate cache
    invalidate_cache("gold_rate:*")

    # Invalidate all tenant pricing caches
    invalidate_cache("*pricing*")
    invalidate_cache("*inventory*")  # Prices may have changed


@receiver(post_save, sender="pricing.PricingRule")
@receiver(post_delete, sender="pricing.PricingRule")
def invalidate_pricing_rule_cache(sender, instance, **kwargs):
    """Invalidate pricing rule cache when rules change."""
    if hasattr(instance, "tenant_id"):
        invalidate_tenant_cache(instance.tenant_id, prefix="pricing")
        invalidate_tenant_cache(instance.tenant_id, prefix="inventory")


# Branch cache invalidation


@receiver(post_save, sender="core.Branch")
@receiver(post_delete, sender="core.Branch")
def invalidate_branch_cache(sender, instance, **kwargs):
    """Invalidate branch cache when branches change."""
    if hasattr(instance, "tenant_id"):
        invalidate_tenant_cache(instance.tenant_id, prefix="branch")
        invalidate_tenant_cache(instance.tenant_id, prefix="dashboard")


# User cache invalidation


@receiver(post_save, sender="auth.User")
@receiver(post_delete, sender="auth.User")
def invalidate_user_cache(sender, instance, **kwargs):
    """Invalidate user cache when users change."""
    if hasattr(instance, "tenant_id") and instance.tenant_id:
        invalidate_tenant_cache(instance.tenant_id, prefix="user")
        invalidate_tenant_cache(instance.tenant_id, prefix="staff")


# Settings cache invalidation


@receiver(post_save, sender="core.TenantSettings")
def invalidate_settings_cache(sender, instance, **kwargs):
    """Invalidate settings cache when tenant settings change."""
    if hasattr(instance, "tenant_id"):
        invalidate_tenant_cache(instance.tenant_id, prefix="settings")
        invalidate_tenant_cache(instance.tenant_id, prefix="config")


# Notification cache invalidation


@receiver(post_save, sender="notifications.Notification")
def invalidate_notification_cache(sender, instance, **kwargs):
    """Invalidate notification cache when notifications are created."""
    if hasattr(instance, "user") and instance.user:
        user = instance.user
        if hasattr(user, "tenant_id") and user.tenant_id:
            invalidate_tenant_cache(user.tenant_id, prefix=f"user:{user.id}:notifications")


def register_cache_invalidation_signals():
    """
    Register all cache invalidation signals.

    Call this function in apps.py ready() method to ensure
    all signals are connected.
    """
    # Signals are automatically connected via @receiver decorator
    # This function is here for explicit registration if needed
    pass
