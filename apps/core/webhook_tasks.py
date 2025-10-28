"""
Celery tasks for webhook delivery.

This module provides:
- Webhook delivery with HMAC signing
- Retry logic with exponential backoff
- Delivery status tracking
- Request/response logging
- Failure alerting

Per Requirement 32 - Webhook and Integration Management
"""

import hashlib
import hmac
import json
import logging
import time
from datetime import timedelta

from django.utils import timezone

import requests
from celery import shared_task

from .webhook_models import Webhook, WebhookDelivery

logger = logging.getLogger(__name__)


@shared_task(
    name="apps.core.webhook_tasks.deliver_webhook",
    bind=True,
    max_retries=5,
    default_retry_delay=60,  # 1 minute base delay
    autoretry_for=(requests.RequestException,),
    retry_backoff=True,
    retry_backoff_max=14400,  # 4 hours max
    retry_jitter=True,
)
def deliver_webhook(self, delivery_id):  # noqa: C901
    """
    Deliver a webhook to its target URL.

    This task handles:
    - HMAC payload signing (Requirement 32.3)
    - HTTP delivery with timeout
    - Response tracking
    - Retry logic with exponential backoff (Requirement 32.4)
    - Status tracking (Requirement 32.5)
    - Request/response logging (Requirement 32.6)

    Args:
        delivery_id: UUID of the WebhookDelivery to send

    Returns:
        dict: Delivery result with status and details
    """
    try:
        # Get the delivery record
        delivery = WebhookDelivery.objects.select_related("webhook").get(id=delivery_id)
    except WebhookDelivery.DoesNotExist:
        logger.error(f"WebhookDelivery {delivery_id} not found")
        return {"status": "error", "message": "Delivery not found"}

    webhook = delivery.webhook

    # Check if webhook is still active
    if not webhook.is_active:
        logger.info(f"Webhook {webhook.id} is inactive, skipping delivery {delivery_id}")
        # Mark as failed without retry since webhook is inactive
        delivery.error_message = "Webhook is inactive"
        delivery.attempt_count = delivery.max_attempts  # Set to max to prevent retries
        delivery.status = WebhookDelivery.FAILED
        delivery.completed_at = timezone.now()
        delivery.save(
            update_fields=[
                "error_message",
                "attempt_count",
                "status",
                "completed_at",
                "updated_at",
            ]
        )
        return {"status": "skipped", "message": "Webhook is inactive"}

    # Prepare the payload
    payload_json = json.dumps(delivery.payload, separators=(",", ":"))
    payload_bytes = payload_json.encode("utf-8")

    # Generate HMAC signature (Requirement 32.3)
    signature = generate_hmac_signature(webhook.secret, payload_bytes)

    # Prepare headers
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "JewelryShop-Webhook/1.0",
        "X-Webhook-Signature": signature,
        "X-Webhook-Event": delivery.event_type,
        "X-Webhook-Delivery": str(delivery.id),
        "X-Webhook-Timestamp": str(int(time.time())),
    }

    # Record the attempt
    delivery.sent_at = timezone.now()
    delivery.save(update_fields=["sent_at", "updated_at"])

    # Make the HTTP request
    start_time = time.time()
    response_status_code = None
    response_body = ""
    response_headers = {}
    error_message = ""

    try:
        # Send the webhook with timeout
        response = requests.post(
            webhook.url,
            data=payload_bytes,
            headers=headers,
            timeout=30,  # 30 second timeout
            allow_redirects=False,  # Don't follow redirects
        )

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Get response details
        response_status_code = response.status_code
        response_body = response.text[:10000]  # Truncate to 10KB
        response_headers = dict(response.headers)

        # Check if successful (2xx status codes)
        if 200 <= response_status_code < 300:
            # Mark as successful
            delivery.mark_as_success(
                status_code=response_status_code,
                response_body=response_body,
                response_headers=response_headers,
                duration_ms=duration_ms,
            )

            logger.info(
                f"Webhook delivery {delivery_id} successful: "
                f"{response_status_code} in {duration_ms}ms"
            )

            return {
                "status": "success",
                "delivery_id": str(delivery_id),
                "status_code": response_status_code,
                "duration_ms": duration_ms,
            }
        else:
            # Non-2xx status code is a failure
            error_message = f"HTTP {response_status_code}: {response_body[:200]}"

            # Mark as failed and schedule retry if possible
            delivery.mark_as_failed(
                error_message=error_message,
                status_code=response_status_code,
                response_body=response_body,
                duration_ms=duration_ms,
            )

            logger.warning(
                f"Webhook delivery {delivery_id} failed with status {response_status_code}: "
                f"{error_message}"
            )

            # Check if we should alert on this failure
            if webhook.should_alert_on_failure():
                send_webhook_failure_alert.delay(webhook.id, delivery.id)

            # Schedule retry if possible
            if delivery.can_retry():
                # Calculate retry delay based on attempt count
                retry_delay = calculate_retry_delay(delivery.attempt_count)
                logger.info(
                    f"Scheduling retry for delivery {delivery_id} "
                    f"in {retry_delay} seconds (attempt {delivery.attempt_count + 1})"
                )
                # Schedule the retry
                deliver_webhook.apply_async(
                    args=[str(delivery_id)],
                    countdown=retry_delay,
                )

            return {
                "status": "failed",
                "delivery_id": str(delivery_id),
                "status_code": response_status_code,
                "error": error_message,
                "can_retry": delivery.can_retry(),
            }

    except requests.Timeout:
        # Request timed out
        duration_ms = int((time.time() - start_time) * 1000)
        error_message = "Request timed out after 30 seconds"

        delivery.mark_as_failed(
            error_message=error_message,
            status_code=None,
            response_body="",
            duration_ms=duration_ms,
        )

        logger.warning(f"Webhook delivery {delivery_id} timed out")

        # Check if we should alert
        if webhook.should_alert_on_failure():
            send_webhook_failure_alert.delay(webhook.id, delivery.id)

        # Schedule retry if possible
        if delivery.can_retry():
            retry_delay = calculate_retry_delay(delivery.attempt_count)
            deliver_webhook.apply_async(
                args=[str(delivery_id)],
                countdown=retry_delay,
            )

        return {
            "status": "failed",
            "delivery_id": str(delivery_id),
            "error": error_message,
            "can_retry": delivery.can_retry(),
        }

    except requests.RequestException as e:
        # Network error or other request exception
        duration_ms = int((time.time() - start_time) * 1000)
        error_message = f"Request failed: {str(e)}"

        delivery.mark_as_failed(
            error_message=error_message,
            status_code=None,
            response_body="",
            duration_ms=duration_ms,
        )

        logger.error(f"Webhook delivery {delivery_id} failed with exception: {e}")

        # Check if we should alert
        if webhook.should_alert_on_failure():
            send_webhook_failure_alert.delay(webhook.id, delivery.id)

        # Schedule retry if possible
        if delivery.can_retry():
            retry_delay = calculate_retry_delay(delivery.attempt_count)
            deliver_webhook.apply_async(
                args=[str(delivery_id)],
                countdown=retry_delay,
            )

        return {
            "status": "failed",
            "delivery_id": str(delivery_id),
            "error": error_message,
            "can_retry": delivery.can_retry(),
        }

    except Exception as e:
        # Unexpected error
        logger.exception(f"Unexpected error delivering webhook {delivery_id}: {e}")

        delivery.mark_as_failed(
            error_message=f"Unexpected error: {str(e)}",
            status_code=None,
            response_body="",
            duration_ms=0,
        )

        return {
            "status": "error",
            "delivery_id": str(delivery_id),
            "error": str(e),
        }


@shared_task(name="apps.core.webhook_tasks.send_webhook_failure_alert")
def send_webhook_failure_alert(webhook_id, delivery_id):
    """
    Send alert to tenant about webhook failures.

    This task handles:
    - Alert on consistent failures (Requirement 32.7)
    - Notification via in-app, email, or SMS

    Args:
        webhook_id: UUID of the Webhook
        delivery_id: UUID of the failed WebhookDelivery
    """
    try:
        webhook = Webhook.objects.select_related("tenant", "created_by").get(id=webhook_id)
        delivery = WebhookDelivery.objects.get(id=delivery_id)
    except (Webhook.DoesNotExist, WebhookDelivery.DoesNotExist):
        logger.error(f"Webhook {webhook_id} or Delivery {delivery_id} not found for alert")
        return

    # Determine alert message based on consecutive failures
    if webhook.consecutive_failures >= 10:
        message = (
            f"Webhook '{webhook.name}' has been automatically disabled after "
            f"10 consecutive failures. Please check the webhook URL and configuration."
        )
    elif webhook.consecutive_failures >= 5:
        message = (
            f"Webhook '{webhook.name}' has failed {webhook.consecutive_failures} times "
            f"consecutively. It will be disabled after 10 failures."
        )
    else:
        message = (
            f"Webhook '{webhook.name}' has failed {webhook.consecutive_failures} times "
            f"consecutively. Please check the webhook endpoint."
        )

    # Create in-app notification
    from apps.notifications.models import Notification

    # Build detailed message with error info
    detailed_message = (
        f"{message}\n\n"
        f"Error: {delivery.error_message}\n"
        f"Last failure: {webhook.last_failure_at.strftime('%Y-%m-%d %H:%M:%S') if webhook.last_failure_at else 'N/A'}"
    )

    # Notify the webhook creator
    if webhook.created_by:
        Notification.objects.create(
            user=webhook.created_by,
            title=f"Webhook Failure Alert: {webhook.name}",
            message=detailed_message,
            notification_type="ERROR",
        )

    # Also notify tenant owner
    tenant_owner = webhook.tenant.users.filter(role="TENANT_OWNER").first()
    if tenant_owner and tenant_owner != webhook.created_by:
        Notification.objects.create(
            user=tenant_owner,
            title=f"Webhook Failure Alert: {webhook.name}",
            message=detailed_message,
            notification_type="ERROR",
        )

    logger.info(
        f"Sent webhook failure alert for {webhook.name} "
        f"({webhook.consecutive_failures} consecutive failures)"
    )


@shared_task(name="apps.core.webhook_tasks.retry_failed_webhooks")
def retry_failed_webhooks():
    """
    Periodic task to retry failed webhook deliveries.

    This task:
    - Finds deliveries that are ready for retry
    - Schedules delivery tasks for them
    - Implements exponential backoff (Requirement 32.4)

    This should be run periodically (e.g., every minute) via Celery Beat.
    """
    now = timezone.now()

    # Find deliveries that are ready for retry
    deliveries_to_retry = WebhookDelivery.objects.filter(
        status=WebhookDelivery.RETRYING,
        next_retry_at__lte=now,
    ).select_related("webhook")

    retry_count = 0

    for delivery in deliveries_to_retry:
        # Check if webhook is still active
        if not delivery.webhook.is_active:
            logger.info(
                f"Skipping retry for delivery {delivery.id} - webhook {delivery.webhook.id} is inactive"
            )
            delivery.mark_as_failed(
                error_message="Webhook was deactivated",
                status_code=None,
                response_body="",
                duration_ms=0,
            )
            continue

        # Schedule the delivery
        deliver_webhook.delay(str(delivery.id))
        retry_count += 1

        logger.info(
            f"Scheduled retry for delivery {delivery.id} "
            f"(attempt {delivery.attempt_count + 1}/{delivery.max_attempts})"
        )

    if retry_count > 0:
        logger.info(f"Scheduled {retry_count} webhook delivery retries")

    return {"retries_scheduled": retry_count}


@shared_task(name="apps.core.webhook_tasks.cleanup_old_deliveries")
def cleanup_old_deliveries(days=90):
    """
    Clean up old webhook delivery records.

    Args:
        days: Number of days to keep delivery records (default: 90)

    Returns:
        dict: Cleanup statistics
    """
    cutoff_date = timezone.now() - timedelta(days=days)

    # Delete old successful deliveries
    deleted_success = WebhookDelivery.objects.filter(
        status=WebhookDelivery.SUCCESS,
        completed_at__lt=cutoff_date,
    ).delete()

    # Delete old failed deliveries (keep failed ones a bit longer for debugging)
    deleted_failed = WebhookDelivery.objects.filter(
        status=WebhookDelivery.FAILED,
        completed_at__lt=cutoff_date - timedelta(days=30),  # Keep failed for 120 days total
    ).delete()

    logger.info(
        f"Cleaned up {deleted_success[0]} successful and {deleted_failed[0]} failed "
        f"webhook deliveries older than {days} days"
    )

    return {
        "deleted_success": deleted_success[0],
        "deleted_failed": deleted_failed[0],
        "cutoff_date": cutoff_date.isoformat(),
    }


# Helper functions


def generate_hmac_signature(secret, payload_bytes):
    """
    Generate HMAC-SHA256 signature for webhook payload.

    Requirement 32.3: Sign webhook payloads with HMAC for verification.

    Args:
        secret: Webhook secret key
        payload_bytes: Payload as bytes

    Returns:
        str: Hex-encoded HMAC signature
    """
    signature = hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    return signature


def calculate_retry_delay(attempt_count):
    """
    Calculate retry delay in seconds using exponential backoff.

    Backoff schedule:
    - After 1st failure: 1 minute (60 seconds)
    - After 2nd failure: 5 minutes (300 seconds)
    - After 3rd failure: 15 minutes (900 seconds)
    - After 4th failure: 1 hour (3600 seconds)
    - After 5th+ failure: 4 hours (14400 seconds)

    Args:
        attempt_count: Number of attempts already made

    Returns:
        int: Delay in seconds
    """
    backoff_seconds = [60, 300, 900, 3600, 14400]
    attempt_index = min(attempt_count, len(backoff_seconds) - 1)
    return backoff_seconds[attempt_index]


def trigger_webhook_event(event_type, event_id, payload_data, tenant):
    """
    Trigger a webhook event for all subscribed webhooks.

    This is a helper function that should be called from other parts of the application
    when events occur (e.g., sale created, inventory updated).

    Args:
        event_type: Type of event (e.g., 'sale.created')
        event_id: UUID of the event object
        payload_data: Dict containing event data
        tenant: Tenant instance

    Returns:
        int: Number of webhooks triggered
    """
    # Find all active webhooks subscribed to this event
    webhooks = Webhook.objects.filter(
        tenant=tenant,
        is_active=True,
        events__contains=[event_type],
    )

    triggered_count = 0

    for webhook in webhooks:
        # Create delivery record
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=event_type,
            event_id=event_id,
            payload=payload_data,
            signature="",  # Will be generated during delivery
            status=WebhookDelivery.PENDING,
        )

        # Schedule delivery task
        deliver_webhook.delay(str(delivery.id))
        triggered_count += 1

        logger.info(
            f"Triggered webhook {webhook.name} for event {event_type} " f"(delivery {delivery.id})"
        )

    return triggered_count
