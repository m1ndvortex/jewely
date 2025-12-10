"""
Payment app signals.

This module contains signal handlers for payment-related events.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.payments.models import SubscriptionPurchase


@receiver(post_save, sender=SubscriptionPurchase)
def handle_purchase_status_change(sender, instance, created, **kwargs):
    """
    Handle purchase status changes.

    When a purchase is completed, this signal can trigger:
    - Subscription activation
    - Email notifications
    - Audit logging
    """
    if not created and instance.payment_status == SubscriptionPurchase.PAYMENT_STATUS_COMPLETED:
        # Payment completed - subscription activation is handled by the service
        pass
