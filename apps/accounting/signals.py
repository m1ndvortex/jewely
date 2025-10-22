"""
Accounting signals for automatic journal entry creation.

This module contains Django signals that automatically create journal entries
when business transactions occur (sales, purchases, payments, expenses).
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.sales.models import Sale

from .models import AccountingConfiguration
from .services import AccountingService
from .transaction_models import Expense, Payment, PurchaseOrder

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Sale)
def create_sale_journal_entry(sender, instance, created, **kwargs):
    """
    Automatically create journal entry when a sale is completed.

    This signal is triggered when a Sale is saved. It creates the appropriate
    double-entry bookkeeping entries for the sale transaction.
    """
    # Create journal entry for completed sales (both new and updated)
    if instance.status == Sale.COMPLETED:
        try:
            # Check if tenant has accounting set up
            if not hasattr(instance.tenant, "accounting_entity"):
                logger.warning(
                    f"No accounting entity found for tenant {instance.tenant.company_name}"
                )
                return

            # Check if automatic journal entries are enabled
            try:
                config = AccountingConfiguration.objects.get(tenant=instance.tenant)
                if not config.use_automatic_journal_entries:
                    logger.info(
                        f"Automatic journal entries disabled for tenant {instance.tenant.company_name}"
                    )
                    return
            except AccountingConfiguration.DoesNotExist:
                logger.warning(
                    f"No accounting configuration found for tenant {instance.tenant.company_name}"
                )
                return

            # Create the journal entry
            journal_entry = AccountingService.create_sale_journal_entry(
                sale=instance, user=instance.employee
            )

            if journal_entry:
                logger.info(
                    f"Journal entry {journal_entry.uuid} created for sale {instance.sale_number}"
                )
            else:
                logger.warning(f"Failed to create journal entry for sale {instance.sale_number}")

        except Exception as e:
            logger.error(f"Error creating journal entry for sale {instance.sale_number}: {str(e)}")


@receiver(post_save, sender=PurchaseOrder)
def create_purchase_journal_entry(sender, instance, created, **kwargs):
    """
    Automatically create journal entry when a purchase order is completed.
    """
    if instance.status == "COMPLETED":
        try:
            # Check if tenant has accounting set up
            if not hasattr(instance.tenant, "accounting_entity"):
                logger.warning(
                    f"No accounting entity found for tenant {instance.tenant.company_name}"
                )
                return

            # Check if automatic journal entries are enabled
            try:
                config = AccountingConfiguration.objects.get(tenant=instance.tenant)
                if not config.use_automatic_journal_entries:
                    logger.info(
                        f"Automatic journal entries disabled for tenant {instance.tenant.company_name}"
                    )
                    return
            except AccountingConfiguration.DoesNotExist:
                logger.warning(
                    f"No accounting configuration found for tenant {instance.tenant.company_name}"
                )
                return

            # Create the journal entry
            journal_entry = AccountingService.create_purchase_journal_entry(
                purchase_order=instance, user=instance.created_by
            )

            if journal_entry:
                logger.info(
                    f"Journal entry {journal_entry.uuid} created for purchase order {instance.po_number}"
                )
            else:
                logger.warning(
                    f"Failed to create journal entry for purchase order {instance.po_number}"
                )

        except Exception as e:
            logger.error(
                f"Error creating journal entry for purchase order {instance.po_number}: {str(e)}"
            )


@receiver(post_save, sender=Payment)
def create_payment_journal_entry(sender, instance, created, **kwargs):
    """
    Automatically create journal entry when a payment is created.
    """
    if created:  # Only for new payments
        try:
            # Check if tenant has accounting set up
            if not hasattr(instance.tenant, "accounting_entity"):
                logger.warning(
                    f"No accounting entity found for tenant {instance.tenant.company_name}"
                )
                return

            # Check if automatic journal entries are enabled
            try:
                config = AccountingConfiguration.objects.get(tenant=instance.tenant)
                if not config.use_automatic_journal_entries:
                    logger.info(
                        f"Automatic journal entries disabled for tenant {instance.tenant.company_name}"
                    )
                    return
            except AccountingConfiguration.DoesNotExist:
                logger.warning(
                    f"No accounting configuration found for tenant {instance.tenant.company_name}"
                )
                return

            # Create the journal entry
            journal_entry = AccountingService.create_payment_journal_entry(
                payment=instance, user=instance.created_by
            )

            if journal_entry:
                logger.info(
                    f"Journal entry {journal_entry.uuid} created for payment {instance.payment_number}"
                )
            else:
                logger.warning(
                    f"Failed to create journal entry for payment {instance.payment_number}"
                )

        except Exception as e:
            logger.error(
                f"Error creating journal entry for payment {instance.payment_number}: {str(e)}"
            )


@receiver(post_save, sender=Expense)
def create_expense_journal_entry(sender, instance, created, **kwargs):
    """
    Automatically create journal entry when an expense is created.
    """
    if created:  # Only for new expenses
        try:
            # Check if tenant has accounting set up
            if not hasattr(instance.tenant, "accounting_entity"):
                logger.warning(
                    f"No accounting entity found for tenant {instance.tenant.company_name}"
                )
                return

            # Check if automatic journal entries are enabled
            try:
                config = AccountingConfiguration.objects.get(tenant=instance.tenant)
                if not config.use_automatic_journal_entries:
                    logger.info(
                        f"Automatic journal entries disabled for tenant {instance.tenant.company_name}"
                    )
                    return
            except AccountingConfiguration.DoesNotExist:
                logger.warning(
                    f"No accounting configuration found for tenant {instance.tenant.company_name}"
                )
                return

            # Create the journal entry
            journal_entry = AccountingService.create_expense_journal_entry(
                expense=instance, user=instance.created_by
            )

            if journal_entry:
                logger.info(
                    f"Journal entry {journal_entry.uuid} created for expense {instance.description}"
                )
            else:
                logger.warning(f"Failed to create journal entry for expense {instance.description}")

        except Exception as e:
            logger.error(
                f"Error creating journal entry for expense {instance.description}: {str(e)}"
            )
