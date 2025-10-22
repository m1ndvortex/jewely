"""
Signal handlers for CRM app.

Implements Requirement 36: Enhanced Loyalty Program
- Automatic points accrual on purchases
- Automatic tier upgrades based on spending
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.sales.models import Sale


@receiver(post_save, sender=Sale)
def award_loyalty_points_on_sale(sender, instance, created, **kwargs):
    """
    Award loyalty points to customer when a sale is completed.

    Implements Requirement 36: Enhanced Loyalty Program
    - Implement point accrual rules based on purchase amount
    - Apply point multipliers during special events or for specific products
    - Automatically upgrade customers based on spending thresholds

    Points calculation:
    - Base points: 1 point per dollar spent (configurable)
    - Tier multiplier: Applied based on customer's loyalty tier
    - Example: $100 purchase with 1.5x multiplier = 150 points

    Note: This works with the sales.Customer model, not crm.Customer.
    The sales.Customer is a simplified model for POS operations.
    """
    # Only process completed sales with a customer
    if not instance.customer or instance.status != Sale.COMPLETED:
        return

    # Check if we've already awarded points for this sale
    # (to avoid duplicate awards on subsequent saves)
    from apps.crm.models import Customer as CRMCustomer
    from apps.crm.models import LoyaltyTransaction

    # Try to find matching CRM customer by customer_number
    try:
        crm_customer = CRMCustomer.objects.get(
            tenant=instance.tenant, customer_number=instance.customer.customer_number
        )
    except CRMCustomer.DoesNotExist:
        # No matching CRM customer, skip loyalty points
        return

    # Check if we've already awarded points for this sale
    existing_transaction = LoyaltyTransaction.objects.filter(
        customer=crm_customer, sale=instance, transaction_type=LoyaltyTransaction.EARNED
    ).exists()

    if existing_transaction:
        return

    # Calculate base points (1 point per dollar by default)
    # This can be made configurable per tenant in the future
    base_points = int(instance.total)

    if base_points <= 0:
        return

    # Award points to CRM customer (tier multiplier is applied in add_loyalty_points method)
    crm_customer.add_loyalty_points(
        base_points, description=f"Purchase: {instance.sale_number} (${instance.total})"
    )

    # Update customer's total purchases and last purchase date
    crm_customer.total_purchases += instance.total
    crm_customer.last_purchase_at = instance.completed_at or instance.created_at
    crm_customer.save(update_fields=["total_purchases", "last_purchase_at"])

    # Check for tier upgrade
    crm_customer.update_loyalty_tier()


@receiver(post_save, sender=Sale)
def apply_tier_discount_on_sale(sender, instance, created, **kwargs):
    """
    Apply tier-specific discount to sale if customer has a loyalty tier.

    Implements Requirement 36: Enhanced Loyalty Program
    - Calculate tier-specific discounts

    This is informational - the actual discount should be applied
    during sale creation in the POS system.
    """
    # This is handled in the POS views during sale creation
    # This signal is here for documentation and future enhancements
    pass
