"""
Stripe webhook handlers for subscription lifecycle management.

This module processes Stripe webhook events to automatically manage
subscription lifecycle, payment status, and billing events per Requirement 5.7.
"""

import logging
from typing import Any, Dict

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

import stripe

from apps.core.models import Tenant, TenantSubscription

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    Handle incoming Stripe webhook events.

    This endpoint receives and processes webhook events from Stripe
    to keep subscription status in sync with payment events.
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        # Invalid payload
        logger.error("Invalid Stripe webhook payload")
        return HttpResponseBadRequest("Invalid payload")
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        logger.error("Invalid Stripe webhook signature")
        return HttpResponseBadRequest("Invalid signature")

    # Handle the event
    event_type = event["type"]
    event_data = event["data"]["object"]

    logger.info(f"Received Stripe webhook event: {event_type}")

    # Route to appropriate handler
    handlers = {
        "customer.subscription.created": handle_subscription_created,
        "customer.subscription.updated": handle_subscription_updated,
        "customer.subscription.deleted": handle_subscription_deleted,
        "customer.subscription.trial_will_end": handle_trial_will_end,
        "invoice.payment_succeeded": handle_payment_succeeded,
        "invoice.payment_failed": handle_payment_failed,
        "invoice.upcoming": handle_invoice_upcoming,
        "customer.created": handle_customer_created,
        "customer.updated": handle_customer_updated,
        "customer.deleted": handle_customer_deleted,
    }

    handler = handlers.get(event_type)
    if handler:
        try:
            handler(event_data)
        except Exception as e:
            logger.error(
                f"Error handling Stripe webhook {event_type}: {str(e)}",
                exc_info=True,
            )
            return HttpResponse(status=500)
    else:
        logger.info(f"Unhandled Stripe webhook event type: {event_type}")

    return HttpResponse(status=200)


def handle_subscription_created(subscription_data: Dict[str, Any]):
    """
    Handle subscription.created event.

    Called when a new subscription is created in Stripe.
    """
    from apps.core.tenant_context import bypass_rls

    subscription_id = subscription_data["id"]
    status = subscription_data["status"]

    logger.info(f"Subscription created: {subscription_id}")

    try:
        with bypass_rls():
            # Find tenant subscription by Stripe subscription ID
            tenant_subscription = TenantSubscription.objects.get(
                stripe_subscription_id=subscription_id
            )

            # Update status
            tenant_subscription.status = _map_stripe_status(status)
            tenant_subscription.current_period_start = timezone.datetime.fromtimestamp(
                subscription_data["current_period_start"], tz=timezone.utc
            )
            tenant_subscription.current_period_end = timezone.datetime.fromtimestamp(
                subscription_data["current_period_end"], tz=timezone.utc
            )
            tenant_subscription.save(
                update_fields=[
                    "status",
                    "current_period_start",
                    "current_period_end",
                    "updated_at",
                ]
            )

            logger.info(
                f"Updated tenant subscription {tenant_subscription.id} "
                f"with status {tenant_subscription.status}"
            )

    except TenantSubscription.DoesNotExist:
        logger.warning(f"Tenant subscription not found for Stripe subscription {subscription_id}")


def handle_subscription_updated(subscription_data: Dict[str, Any]):
    """
    Handle subscription.updated event.

    Called when a subscription is updated in Stripe (plan change, status change, etc.).
    """
    from apps.core.tenant_context import bypass_rls

    subscription_id = subscription_data["id"]
    status = subscription_data["status"]
    cancel_at_period_end = subscription_data.get("cancel_at_period_end", False)

    logger.info(f"Subscription updated: {subscription_id}")

    try:
        with bypass_rls():
            tenant_subscription = TenantSubscription.objects.get(
                stripe_subscription_id=subscription_id
            )

            # Update status
            tenant_subscription.status = _map_stripe_status(status)
            tenant_subscription.current_period_start = timezone.datetime.fromtimestamp(
                subscription_data["current_period_start"], tz=timezone.utc
            )
            tenant_subscription.current_period_end = timezone.datetime.fromtimestamp(
                subscription_data["current_period_end"], tz=timezone.utc
            )

            # Handle cancellation
            if cancel_at_period_end and not tenant_subscription.cancelled_at:
                tenant_subscription.cancelled_at = timezone.now()
            elif not cancel_at_period_end and tenant_subscription.cancelled_at:
                tenant_subscription.cancelled_at = None

            tenant_subscription.save(
                update_fields=[
                    "status",
                    "current_period_start",
                    "current_period_end",
                    "cancelled_at",
                    "updated_at",
                ]
            )

            logger.info(
                f"Updated tenant subscription {tenant_subscription.id} "
                f"with status {tenant_subscription.status}"
            )

    except TenantSubscription.DoesNotExist:
        logger.warning(f"Tenant subscription not found for Stripe subscription {subscription_id}")


def handle_subscription_deleted(subscription_data: Dict[str, Any]):
    """
    Handle subscription.deleted event.

    Called when a subscription is cancelled and deleted in Stripe.
    """
    from apps.core.tenant_context import bypass_rls

    subscription_id = subscription_data["id"]

    logger.info(f"Subscription deleted: {subscription_id}")

    try:
        with bypass_rls():
            tenant_subscription = TenantSubscription.objects.get(
                stripe_subscription_id=subscription_id
            )

            # Mark as cancelled
            tenant_subscription.status = TenantSubscription.STATUS_CANCELLED
            tenant_subscription.cancelled_at = timezone.now()
            tenant_subscription.save(update_fields=["status", "cancelled_at", "updated_at"])

            # Optionally suspend the tenant
            tenant = tenant_subscription.tenant
            if tenant.status == Tenant.ACTIVE:
                tenant.status = Tenant.SUSPENDED
                tenant.save(update_fields=["status", "updated_at"])
                logger.info(f"Suspended tenant {tenant.id} due to subscription cancellation")

            logger.info(f"Marked tenant subscription {tenant_subscription.id} as cancelled")

    except TenantSubscription.DoesNotExist:
        logger.warning(f"Tenant subscription not found for Stripe subscription {subscription_id}")


def handle_trial_will_end(subscription_data: Dict[str, Any]):
    """
    Handle subscription.trial_will_end event.

    Called 3 days before a trial period ends. Can be used to send
    reminder emails to tenants.
    """
    subscription_id = subscription_data["id"]

    logger.info(f"Trial will end for subscription: {subscription_id}")

    try:
        tenant_subscription = TenantSubscription.objects.get(stripe_subscription_id=subscription_id)

        # TODO: Send trial ending notification email
        # This can be implemented using the notification system

        logger.info(f"Trial ending soon for tenant {tenant_subscription.tenant.company_name}")

    except TenantSubscription.DoesNotExist:
        logger.warning(f"Tenant subscription not found for Stripe subscription {subscription_id}")


def handle_payment_succeeded(invoice_data: Dict[str, Any]):
    """
    Handle invoice.payment_succeeded event.

    Called when a payment is successfully processed.
    """
    from apps.core.tenant_context import bypass_rls

    subscription_id = invoice_data.get("subscription")
    amount_paid = invoice_data.get("amount_paid", 0) / 100  # Convert from cents

    if not subscription_id:
        logger.info("Payment succeeded for non-subscription invoice")
        return

    logger.info(f"Payment succeeded for subscription: {subscription_id}")

    try:
        with bypass_rls():
            tenant_subscription = TenantSubscription.objects.get(
                stripe_subscription_id=subscription_id
            )

            # Ensure subscription is active
            if tenant_subscription.status != TenantSubscription.STATUS_ACTIVE:
                tenant_subscription.status = TenantSubscription.STATUS_ACTIVE
                tenant_subscription.save(update_fields=["status", "updated_at"])

            # Ensure tenant is active
            tenant = tenant_subscription.tenant
            if tenant.status == Tenant.SUSPENDED:
                tenant.status = Tenant.ACTIVE
                tenant.save(update_fields=["status", "updated_at"])
                logger.info(f"Reactivated tenant {tenant.id} after successful payment")

            # TODO: Send payment receipt email

            logger.info(
                f"Payment of ${amount_paid} succeeded for tenant "
                f"{tenant_subscription.tenant.company_name}"
            )

    except TenantSubscription.DoesNotExist:
        logger.warning(f"Tenant subscription not found for Stripe subscription {subscription_id}")


def handle_payment_failed(invoice_data: Dict[str, Any]):
    """
    Handle invoice.payment_failed event.

    Called when a payment attempt fails.
    """
    from apps.core.tenant_context import bypass_rls

    subscription_id = invoice_data.get("subscription")
    attempt_count = invoice_data.get("attempt_count", 0)

    if not subscription_id:
        logger.info("Payment failed for non-subscription invoice")
        return

    logger.info(f"Payment failed for subscription: {subscription_id}")

    try:
        with bypass_rls():
            tenant_subscription = TenantSubscription.objects.get(
                stripe_subscription_id=subscription_id
            )

            # Mark as past due
            tenant_subscription.status = TenantSubscription.STATUS_PAST_DUE
            tenant_subscription.save(update_fields=["status", "updated_at"])

            # TODO: Send payment failed notification email

            # Suspend tenant after multiple failed attempts
            if attempt_count >= 3:
                tenant = tenant_subscription.tenant
                if tenant.status == Tenant.ACTIVE:
                    tenant.status = Tenant.SUSPENDED
                    tenant.save(update_fields=["status", "updated_at"])
                    logger.info(
                        f"Suspended tenant {tenant.id} after {attempt_count} "
                        f"failed payment attempts"
                    )

            logger.info(
                f"Payment failed (attempt {attempt_count}) for tenant "
                f"{tenant_subscription.tenant.company_name}"
            )

    except TenantSubscription.DoesNotExist:
        logger.warning(f"Tenant subscription not found for Stripe subscription {subscription_id}")


def handle_invoice_upcoming(invoice_data: Dict[str, Any]):
    """
    Handle invoice.upcoming event.

    Called a few days before an invoice is due. Can be used to send
    reminder emails to tenants.
    """
    subscription_id = invoice_data.get("subscription")
    amount_due = invoice_data.get("amount_due", 0) / 100  # Convert from cents

    if not subscription_id:
        return

    logger.info(f"Upcoming invoice for subscription: {subscription_id}")

    try:
        tenant_subscription = TenantSubscription.objects.get(stripe_subscription_id=subscription_id)

        # TODO: Send upcoming invoice notification email

        logger.info(
            f"Upcoming invoice of ${amount_due} for tenant "
            f"{tenant_subscription.tenant.company_name}"
        )

    except TenantSubscription.DoesNotExist:
        logger.warning(f"Tenant subscription not found for Stripe subscription {subscription_id}")


def handle_customer_created(customer_data: Dict[str, Any]):
    """
    Handle customer.created event.

    Called when a new customer is created in Stripe.
    """
    customer_id = customer_data["id"]
    email = customer_data.get("email")

    logger.info(f"Customer created: {customer_id} ({email})")


def handle_customer_updated(customer_data: Dict[str, Any]):
    """
    Handle customer.updated event.

    Called when a customer is updated in Stripe.
    """
    customer_id = customer_data["id"]

    logger.info(f"Customer updated: {customer_id}")


def handle_customer_deleted(customer_data: Dict[str, Any]):
    """
    Handle customer.deleted event.

    Called when a customer is deleted in Stripe.
    """
    customer_id = customer_data["id"]

    logger.info(f"Customer deleted: {customer_id}")

    try:
        # Find and update tenant subscription
        tenant_subscription = TenantSubscription.objects.get(stripe_customer_id=customer_id)
        tenant_subscription.stripe_customer_id = ""
        tenant_subscription.save(update_fields=["stripe_customer_id", "updated_at"])

        logger.info(
            f"Cleared Stripe customer ID for tenant subscription " f"{tenant_subscription.id}"
        )

    except TenantSubscription.DoesNotExist:
        logger.warning(f"Tenant subscription not found for Stripe customer {customer_id}")


def _map_stripe_status(stripe_status: str) -> str:
    """
    Map Stripe subscription status to TenantSubscription status.

    Args:
        stripe_status: Stripe subscription status

    Returns:
        TenantSubscription status constant
    """
    status_map = {
        "active": TenantSubscription.STATUS_ACTIVE,
        "trialing": TenantSubscription.STATUS_TRIAL,
        "past_due": TenantSubscription.STATUS_PAST_DUE,
        "canceled": TenantSubscription.STATUS_CANCELLED,
        "unpaid": TenantSubscription.STATUS_PAST_DUE,
        "incomplete": TenantSubscription.STATUS_PAST_DUE,
        "incomplete_expired": TenantSubscription.STATUS_EXPIRED,
    }

    return status_map.get(stripe_status, TenantSubscription.STATUS_ACTIVE)
