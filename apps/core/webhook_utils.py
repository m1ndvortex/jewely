"""
Utility functions for triggering webhook events.

This module provides helper functions to trigger webhooks from various
parts of the application when events occur.

Per Requirement 32 - Webhook and Integration Management
"""

import logging
from typing import Any, Dict
from uuid import UUID

from django.utils import timezone

from .webhook_models import Webhook, WebhookDelivery
from .webhook_tasks import deliver_webhook

logger = logging.getLogger(__name__)


def trigger_webhook_event(
    event_type: str,
    event_id: UUID,
    payload_data: Dict[str, Any],
    tenant,
    async_delivery: bool = True,
) -> int:
    """
    Trigger a webhook event for all subscribed webhooks.

    This function should be called from other parts of the application
    when events occur (e.g., sale created, inventory updated).

    Args:
        event_type: Type of event (e.g., 'sale.created')
        event_id: UUID of the event object
        payload_data: Dict containing event data
        tenant: Tenant instance
        async_delivery: If True, deliver asynchronously via Celery (default: True)

    Returns:
        int: Number of webhooks triggered

    Example:
        >>> from apps.core.webhook_utils import trigger_webhook_event
        >>> trigger_webhook_event(
        ...     event_type='sale.created',
        ...     event_id=sale.id,
        ...     payload_data={
        ...         'sale_number': sale.sale_number,
        ...         'total': str(sale.total),
        ...         'customer_id': str(sale.customer_id) if sale.customer else None,
        ...     },
        ...     tenant=sale.tenant,
        ... )
    """
    # Find all active webhooks subscribed to this event
    webhooks = Webhook.objects.filter(
        tenant=tenant,
        is_active=True,
        events__contains=[event_type],
    )

    triggered_count = 0

    for webhook in webhooks:
        # Enrich payload with metadata
        enriched_payload = {
            "event": event_type,
            "event_id": str(event_id),
            "timestamp": timezone.now().isoformat(),
            "tenant_id": str(tenant.id),
            "data": payload_data,
        }

        # Create delivery record
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=event_type,
            event_id=event_id,
            payload=enriched_payload,
            signature="",  # Will be generated during delivery
            status=WebhookDelivery.PENDING,
        )

        # Schedule delivery task
        if async_delivery:
            deliver_webhook.delay(str(delivery.id))
        else:
            # Synchronous delivery (useful for testing)
            deliver_webhook(str(delivery.id))

        triggered_count += 1

        logger.info(
            f"Triggered webhook {webhook.name} for event {event_type} " f"(delivery {delivery.id})"
        )

    return triggered_count


def trigger_sale_created(sale):
    """
    Trigger webhook for sale.created event.

    Args:
        sale: Sale instance

    Returns:
        int: Number of webhooks triggered
    """
    payload = {
        "sale_number": sale.sale_number,
        "total": str(sale.total),
        "subtotal": str(sale.subtotal),
        "tax": str(sale.tax),
        "discount": str(sale.discount),
        "payment_method": sale.payment_method,
        "status": sale.status,
        "customer_id": str(sale.customer_id) if sale.customer_id else None,
        "branch_id": str(sale.branch_id),
        "employee_id": str(sale.employee_id),
        "created_at": sale.created_at.isoformat(),
    }

    return trigger_webhook_event(
        event_type=Webhook.EVENT_SALE_CREATED,
        event_id=sale.id,
        payload_data=payload,
        tenant=sale.tenant,
    )


def trigger_sale_updated(sale):
    """
    Trigger webhook for sale.updated event.

    Args:
        sale: Sale instance

    Returns:
        int: Number of webhooks triggered
    """
    payload = {
        "sale_number": sale.sale_number,
        "total": str(sale.total),
        "status": sale.status,
        "updated_at": sale.created_at.isoformat(),  # Assuming there's an updated_at field
    }

    return trigger_webhook_event(
        event_type=Webhook.EVENT_SALE_UPDATED,
        event_id=sale.id,
        payload_data=payload,
        tenant=sale.tenant,
    )


def trigger_sale_refunded(sale):
    """
    Trigger webhook for sale.refunded event.

    Args:
        sale: Sale instance

    Returns:
        int: Number of webhooks triggered
    """
    payload = {
        "sale_number": sale.sale_number,
        "total": str(sale.total),
        "refunded_at": timezone.now().isoformat(),
    }

    return trigger_webhook_event(
        event_type=Webhook.EVENT_SALE_REFUNDED,
        event_id=sale.id,
        payload_data=payload,
        tenant=sale.tenant,
    )


def trigger_inventory_created(inventory_item):
    """
    Trigger webhook for inventory.created event.

    Args:
        inventory_item: InventoryItem instance

    Returns:
        int: Number of webhooks triggered
    """
    payload = {
        "sku": inventory_item.sku,
        "name": inventory_item.name,
        "quantity": inventory_item.quantity,
        "cost_price": str(inventory_item.cost_price),
        "selling_price": str(inventory_item.selling_price),
        "branch_id": str(inventory_item.branch_id),
        "created_at": inventory_item.created_at.isoformat(),
    }

    return trigger_webhook_event(
        event_type=Webhook.EVENT_INVENTORY_CREATED,
        event_id=inventory_item.id,
        payload_data=payload,
        tenant=inventory_item.tenant,
    )


def trigger_inventory_updated(inventory_item):
    """
    Trigger webhook for inventory.updated event.

    Args:
        inventory_item: InventoryItem instance

    Returns:
        int: Number of webhooks triggered
    """
    payload = {
        "sku": inventory_item.sku,
        "name": inventory_item.name,
        "quantity": inventory_item.quantity,
        "selling_price": str(inventory_item.selling_price),
        "updated_at": inventory_item.updated_at.isoformat(),
    }

    return trigger_webhook_event(
        event_type=Webhook.EVENT_INVENTORY_UPDATED,
        event_id=inventory_item.id,
        payload_data=payload,
        tenant=inventory_item.tenant,
    )


def trigger_inventory_low_stock(inventory_item, threshold: int):
    """
    Trigger webhook for inventory.low_stock event.

    Args:
        inventory_item: InventoryItem instance
        threshold: Low stock threshold that was crossed

    Returns:
        int: Number of webhooks triggered
    """
    payload = {
        "sku": inventory_item.sku,
        "name": inventory_item.name,
        "quantity": inventory_item.quantity,
        "threshold": threshold,
        "branch_id": str(inventory_item.branch_id),
    }

    return trigger_webhook_event(
        event_type=Webhook.EVENT_INVENTORY_LOW_STOCK,
        event_id=inventory_item.id,
        payload_data=payload,
        tenant=inventory_item.tenant,
    )


def trigger_customer_created(customer):
    """
    Trigger webhook for customer.created event.

    Args:
        customer: Customer instance

    Returns:
        int: Number of webhooks triggered
    """
    payload = {
        "customer_number": customer.customer_number,
        "first_name": customer.first_name,
        "last_name": customer.last_name,
        "email": customer.email,
        "phone": customer.phone,
        "loyalty_tier": customer.loyalty_tier,
        "created_at": customer.created_at.isoformat(),
    }

    return trigger_webhook_event(
        event_type=Webhook.EVENT_CUSTOMER_CREATED,
        event_id=customer.id,
        payload_data=payload,
        tenant=customer.tenant,
    )


def trigger_customer_updated(customer):
    """
    Trigger webhook for customer.updated event.

    Args:
        customer: Customer instance

    Returns:
        int: Number of webhooks triggered
    """
    payload = {
        "customer_number": customer.customer_number,
        "first_name": customer.first_name,
        "last_name": customer.last_name,
        "email": customer.email,
        "phone": customer.phone,
        "loyalty_tier": customer.loyalty_tier,
        "updated_at": customer.updated_at.isoformat(),
    }

    return trigger_webhook_event(
        event_type=Webhook.EVENT_CUSTOMER_UPDATED,
        event_id=customer.id,
        payload_data=payload,
        tenant=customer.tenant,
    )


def trigger_repair_order_created(repair_order):
    """
    Trigger webhook for repair_order.created event.

    Args:
        repair_order: RepairOrder instance

    Returns:
        int: Number of webhooks triggered
    """
    payload = {
        "order_number": repair_order.order_number,
        "customer_id": str(repair_order.customer_id),
        "service_type": repair_order.service_type,
        "status": repair_order.status,
        "cost_estimate": str(repair_order.cost_estimate),
        "estimated_completion": (
            repair_order.estimated_completion.isoformat()
            if repair_order.estimated_completion
            else None
        ),
        "created_at": repair_order.created_at.isoformat(),
    }

    return trigger_webhook_event(
        event_type=Webhook.EVENT_REPAIR_ORDER_CREATED,
        event_id=repair_order.id,
        payload_data=payload,
        tenant=repair_order.tenant,
    )


def trigger_repair_order_status_changed(repair_order, old_status: str, new_status: str):
    """
    Trigger webhook for repair_order.status_changed event.

    Args:
        repair_order: RepairOrder instance
        old_status: Previous status
        new_status: New status

    Returns:
        int: Number of webhooks triggered
    """
    payload = {
        "order_number": repair_order.order_number,
        "customer_id": str(repair_order.customer_id),
        "old_status": old_status,
        "new_status": new_status,
        "changed_at": timezone.now().isoformat(),
    }

    return trigger_webhook_event(
        event_type=Webhook.EVENT_REPAIR_ORDER_STATUS_CHANGED,
        event_id=repair_order.id,
        payload_data=payload,
        tenant=repair_order.tenant,
    )


def trigger_purchase_order_created(purchase_order):
    """
    Trigger webhook for purchase_order.created event.

    Args:
        purchase_order: PurchaseOrder instance

    Returns:
        int: Number of webhooks triggered
    """
    payload = {
        "po_number": purchase_order.po_number,
        "supplier_id": str(purchase_order.supplier_id),
        "total_amount": str(purchase_order.total_amount),
        "status": purchase_order.status,
        "expected_delivery": (
            purchase_order.expected_delivery.isoformat()
            if purchase_order.expected_delivery
            else None
        ),
        "created_at": purchase_order.created_at.isoformat(),
    }

    return trigger_webhook_event(
        event_type=Webhook.EVENT_PURCHASE_ORDER_CREATED,
        event_id=purchase_order.id,
        payload_data=payload,
        tenant=purchase_order.tenant,
    )


def trigger_purchase_order_received(purchase_order):
    """
    Trigger webhook for purchase_order.received event.

    Args:
        purchase_order: PurchaseOrder instance

    Returns:
        int: Number of webhooks triggered
    """
    payload = {
        "po_number": purchase_order.po_number,
        "supplier_id": str(purchase_order.supplier_id),
        "total_amount": str(purchase_order.total_amount),
        "received_at": timezone.now().isoformat(),
    }

    return trigger_webhook_event(
        event_type=Webhook.EVENT_PURCHASE_ORDER_RECEIVED,
        event_id=purchase_order.id,
        payload_data=payload,
        tenant=purchase_order.tenant,
    )
