"""
Webhook and integration models for external system integration.

This module provides webhook management for:
- Webhook registration with event selection
- HMAC payload signing for security
- Webhook delivery tracking with retry logic
- Delivery status monitoring (success, failed, pending)
- Request/response logging
- Failure alerting
- API key management for external services
- OAuth2 support for third-party integrations

Per Requirement 32 - Webhook and Integration Management
"""

import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Webhook(models.Model):
    """
    Webhook registration for tenant event notifications.

    Requirement 32.1: Allow tenants to register webhook URLs for event notifications.
    Requirement 32.2: Allow tenants to select which events trigger webhooks.
    Requirement 32.3: Sign webhook payloads with HMAC for verification.
    """

    # Event type choices
    EVENT_SALE_CREATED = "sale.created"
    EVENT_SALE_UPDATED = "sale.updated"
    EVENT_SALE_REFUNDED = "sale.refunded"
    EVENT_INVENTORY_CREATED = "inventory.created"
    EVENT_INVENTORY_UPDATED = "inventory.updated"
    EVENT_INVENTORY_LOW_STOCK = "inventory.low_stock"
    EVENT_CUSTOMER_CREATED = "customer.created"
    EVENT_CUSTOMER_UPDATED = "customer.updated"
    EVENT_REPAIR_ORDER_CREATED = "repair_order.created"
    EVENT_REPAIR_ORDER_STATUS_CHANGED = "repair_order.status_changed"
    EVENT_PURCHASE_ORDER_CREATED = "purchase_order.created"
    EVENT_PURCHASE_ORDER_RECEIVED = "purchase_order.received"

    EVENT_CHOICES = [
        (EVENT_SALE_CREATED, "Sale Created"),
        (EVENT_SALE_UPDATED, "Sale Updated"),
        (EVENT_SALE_REFUNDED, "Sale Refunded"),
        (EVENT_INVENTORY_CREATED, "Inventory Item Created"),
        (EVENT_INVENTORY_UPDATED, "Inventory Item Updated"),
        (EVENT_INVENTORY_LOW_STOCK, "Inventory Low Stock Alert"),
        (EVENT_CUSTOMER_CREATED, "Customer Created"),
        (EVENT_CUSTOMER_UPDATED, "Customer Updated"),
        (EVENT_REPAIR_ORDER_CREATED, "Repair Order Created"),
        (EVENT_REPAIR_ORDER_STATUS_CHANGED, "Repair Order Status Changed"),
        (EVENT_PURCHASE_ORDER_CREATED, "Purchase Order Created"),
        (EVENT_PURCHASE_ORDER_RECEIVED, "Purchase Order Received"),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the webhook",
    )

    # Tenant association
    tenant = models.ForeignKey(
        "Tenant",
        on_delete=models.CASCADE,
        related_name="webhooks",
        help_text="Tenant that owns this webhook",
    )

    # Webhook configuration
    name = models.CharField(
        max_length=255,
        help_text="Descriptive name for the webhook",
    )

    url = models.URLField(
        max_length=500,
        help_text="Target URL for webhook delivery",
    )

    description = models.TextField(
        blank=True,
        help_text="Optional description of webhook purpose",
    )

    # Event subscription
    events = models.JSONField(
        default=list,
        help_text="List of event types this webhook subscribes to",
    )

    # Security
    secret = models.CharField(
        max_length=255,
        help_text="HMAC secret for payload signing (auto-generated)",
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the webhook is active and should receive events",
    )

    # Failure tracking
    consecutive_failures = models.IntegerField(
        default=0,
        help_text="Number of consecutive delivery failures",
    )

    last_failure_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last delivery failure",
    )

    last_success_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last successful delivery",
    )

    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="webhooks_created",
        help_text="User who created this webhook",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the webhook was created",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the webhook was last updated",
    )

    class Meta:
        db_table = "webhooks"
        ordering = ["-created_at"]
        verbose_name = "Webhook"
        verbose_name_plural = "Webhooks"
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="webhook_tenant_active_idx"),
            models.Index(fields=["tenant", "-created_at"], name="webhook_tenant_created_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.tenant.company_name})"

    def save(self, *args, **kwargs):
        """
        Override save to auto-generate HMAC secret if not provided.
        """
        if not self.secret:
            # Generate a secure random secret (64 characters)
            self.secret = secrets.token_urlsafe(48)
        super().save(*args, **kwargs)

    def is_subscribed_to_event(self, event_type):
        """
        Check if webhook is subscribed to a specific event type.

        Args:
            event_type: Event type string (e.g., 'sale.created')

        Returns:
            bool: True if subscribed, False otherwise
        """
        return event_type in self.events

    def record_success(self):
        """
        Record a successful webhook delivery.
        Resets consecutive failures counter.
        """
        self.consecutive_failures = 0
        self.last_success_at = timezone.now()
        self.save(update_fields=["consecutive_failures", "last_success_at", "updated_at"])

    def record_failure(self):
        """
        Record a failed webhook delivery.
        Increments consecutive failures counter.
        """
        self.consecutive_failures += 1
        self.last_failure_at = timezone.now()

        # Auto-disable webhook after 10 consecutive failures
        if self.consecutive_failures >= 10:
            self.is_active = False

        self.save(
            update_fields=[
                "consecutive_failures",
                "last_failure_at",
                "is_active",
                "updated_at",
            ]
        )

    def should_alert_on_failure(self):
        """
        Determine if tenant should be alerted about webhook failures.

        Alert on 3rd, 5th, and 10th consecutive failure.

        Returns:
            bool: True if alert should be sent
        """
        return self.consecutive_failures in [3, 5, 10]

    def get_event_display_names(self):
        """
        Get human-readable names for subscribed events.

        Returns:
            list: List of event display names
        """
        event_dict = dict(self.EVENT_CHOICES)
        return [event_dict.get(event, event) for event in self.events]


class WebhookDelivery(models.Model):
    """
    Track individual webhook delivery attempts.

    Requirement 32.4: Automatically retry failed webhook deliveries with exponential backoff.
    Requirement 32.5: Track webhook delivery status (success, failed, pending).
    Requirement 32.6: Provide detailed logs of all webhook attempts.
    """

    # Status choices
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRYING = "RETRYING"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (SUCCESS, "Success"),
        (FAILED, "Failed"),
        (RETRYING, "Retrying"),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the delivery",
    )

    # Webhook reference
    webhook = models.ForeignKey(
        Webhook,
        on_delete=models.CASCADE,
        related_name="deliveries",
        help_text="Webhook that this delivery belongs to",
    )

    # Event information
    event_type = models.CharField(
        max_length=100,
        help_text="Type of event that triggered this delivery",
    )

    event_id = models.UUIDField(
        help_text="ID of the event object (e.g., sale ID, inventory ID)",
    )

    # Delivery details
    payload = models.JSONField(
        help_text="JSON payload sent to webhook URL",
    )

    signature = models.CharField(
        max_length=255,
        help_text="HMAC signature of the payload",
    )

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PENDING,
        help_text="Current delivery status",
    )

    # Retry tracking
    attempt_count = models.IntegerField(
        default=0,
        help_text="Number of delivery attempts made",
    )

    max_attempts = models.IntegerField(
        default=5,
        help_text="Maximum number of delivery attempts",
    )

    next_retry_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Scheduled time for next retry attempt",
    )

    # Response tracking
    response_status_code = models.IntegerField(
        null=True,
        blank=True,
        help_text="HTTP status code from webhook endpoint",
    )

    response_body = models.TextField(
        blank=True,
        help_text="Response body from webhook endpoint (truncated to 10KB)",
    )

    response_headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="Response headers from webhook endpoint",
    )

    # Error tracking
    error_message = models.TextField(
        blank=True,
        help_text="Error message if delivery failed",
    )

    # Timing
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the delivery was sent",
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the delivery was completed (success or final failure)",
    )

    duration_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Delivery duration in milliseconds",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the delivery was created",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the delivery was last updated",
    )

    class Meta:
        db_table = "webhook_deliveries"
        ordering = ["-created_at"]
        verbose_name = "Webhook Delivery"
        verbose_name_plural = "Webhook Deliveries"
        indexes = [
            models.Index(fields=["webhook", "-created_at"], name="delivery_webhook_created_idx"),
            models.Index(fields=["webhook", "status"], name="delivery_webhook_status_idx"),
            models.Index(fields=["status", "next_retry_at"], name="delivery_retry_idx"),
            models.Index(fields=["event_type", "event_id"], name="delivery_event_idx"),
        ]

    def __str__(self):
        return f"{self.webhook.name} - {self.event_type} ({self.status})"

    def is_pending(self):
        """Check if delivery is pending."""
        return self.status == self.PENDING

    def is_success(self):
        """Check if delivery was successful."""
        return self.status == self.SUCCESS

    def is_failed(self):
        """Check if delivery failed permanently."""
        return self.status == self.FAILED

    def is_retrying(self):
        """Check if delivery is in retry state."""
        return self.status == self.RETRYING

    def can_retry(self):
        """
        Check if delivery can be retried.

        Returns:
            bool: True if retry is possible
        """
        return (
            self.status in [self.PENDING, self.RETRYING, self.FAILED]
            and self.attempt_count < self.max_attempts
        )

    def calculate_next_retry(self):
        """
        Calculate next retry time using exponential backoff.

        Backoff schedule (based on number of failures):
        - After 1st failure: 1 minute
        - After 2nd failure: 5 minutes
        - After 3rd failure: 15 minutes
        - After 4th failure: 1 hour
        - After 5th+ failure: 4 hours

        Returns:
            datetime: Next retry time
        """
        from datetime import timedelta

        backoff_minutes = [1, 5, 15, 60, 240]
        # Use attempt_count - 1 because attempt_count has already been incremented
        # when this is called from mark_as_failed
        attempt_index = min(self.attempt_count - 1, len(backoff_minutes) - 1)
        attempt_index = max(0, attempt_index)  # Ensure non-negative
        delay_minutes = backoff_minutes[attempt_index]

        return timezone.now() + timedelta(minutes=delay_minutes)

    def mark_as_success(self, status_code, response_body, response_headers, duration_ms):
        """
        Mark delivery as successful.

        Args:
            status_code: HTTP status code
            response_body: Response body (will be truncated)
            response_headers: Response headers dict
            duration_ms: Request duration in milliseconds
        """
        self.status = self.SUCCESS
        self.response_status_code = status_code
        self.response_body = response_body[:10000]  # Truncate to 10KB
        self.response_headers = response_headers
        self.duration_ms = duration_ms
        self.completed_at = timezone.now()
        self.save(
            update_fields=[
                "status",
                "response_status_code",
                "response_body",
                "response_headers",
                "duration_ms",
                "completed_at",
                "updated_at",
            ]
        )

        # Update webhook success tracking
        self.webhook.record_success()

    def mark_as_failed(self, error_message, status_code=None, response_body="", duration_ms=None):
        """
        Mark delivery as failed and schedule retry if possible.

        Args:
            error_message: Error message describing the failure
            status_code: HTTP status code (if available)
            response_body: Response body (if available)
            duration_ms: Request duration in milliseconds (if available)
        """
        self.error_message = error_message
        self.response_status_code = status_code
        self.response_body = response_body[:10000] if response_body else ""
        self.duration_ms = duration_ms

        # Increment attempt count first
        self.attempt_count += 1

        # Check if we can still retry after this attempt
        if self.attempt_count < self.max_attempts:
            # Calculate retry time based on current attempt_count (after increment)
            # But we want backoff based on attempt number, so subtract 1
            self.next_retry_at = self.calculate_next_retry()
            self.status = self.RETRYING
        else:
            self.status = self.FAILED
            self.completed_at = timezone.now()
            self.next_retry_at = None

        self.save(
            update_fields=[
                "status",
                "attempt_count",
                "error_message",
                "response_status_code",
                "response_body",
                "duration_ms",
                "next_retry_at",
                "completed_at",
                "updated_at",
            ]
        )

        # Update webhook failure tracking
        self.webhook.record_failure()

    def get_retry_info(self):
        """
        Get human-readable retry information.

        Returns:
            dict: Retry information
        """
        if not self.can_retry():
            return {
                "can_retry": False,
                "message": "Maximum retry attempts reached",
            }

        if self.next_retry_at:
            time_until_retry = self.next_retry_at - timezone.now()
            minutes = int(time_until_retry.total_seconds() / 60)

            return {
                "can_retry": True,
                "next_retry_at": self.next_retry_at,
                "minutes_until_retry": minutes,
                "attempt": self.attempt_count + 1,
                "max_attempts": self.max_attempts,
            }

        return {
            "can_retry": True,
            "message": "Ready for retry",
            "attempt": self.attempt_count + 1,
            "max_attempts": self.max_attempts,
        }
