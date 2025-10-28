"""
Tests for webhook delivery tasks.

This module tests webhook delivery, retry logic, HMAC signing, and failure alerting
per Requirement 32 - Webhook and Integration Management.
"""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

import pytest
import requests
import responses

from apps.core.models import Tenant, User
from apps.core.webhook_models import Webhook, WebhookDelivery
from apps.core.webhook_tasks import (
    calculate_retry_delay,
    cleanup_old_deliveries,
    deliver_webhook,
    generate_hmac_signature,
    retry_failed_webhooks,
    send_webhook_failure_alert,
)
from apps.core.webhook_utils import trigger_webhook_event
from apps.notifications.models import Notification


@pytest.mark.django_db
class WebhookDeliveryTestCase(TestCase):
    """
    Test webhook delivery functionality.

    Tests Requirement 32.3: Sign webhook payloads with HMAC.
    Tests Requirement 32.4: Retry failed webhook deliveries with exponential backoff.
    Tests Requirement 32.5: Track webhook delivery status.
    Tests Requirement 32.6: Log request/response data.
    Tests Requirement 32.7: Alert on consistent failures.
    """

    def setUp(self):
        """Set up test data."""
        # Create tenant
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        # Create user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            role=User.TENANT_OWNER,
        )

        # Create webhook
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            secret="test-secret-key",
            created_by=self.user,
        )

        # Create delivery
        self.delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id="12345678-1234-1234-1234-123456789012",
            payload={
                "event": "sale.created",
                "data": {"sale_number": "SALE-001", "total": "299.99"},
            },
        )

    def test_generate_hmac_signature(self):
        """Test HMAC signature generation (Requirement 32.3)."""
        secret = "test-secret"
        payload = b'{"test": "data"}'

        signature = generate_hmac_signature(secret, payload)

        # Signature should be hex string
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)  # SHA256 produces 64 hex chars
        self.assertTrue(all(c in "0123456789abcdef" for c in signature))

        # Same input should produce same signature
        signature2 = generate_hmac_signature(secret, payload)
        self.assertEqual(signature, signature2)

        # Different secret should produce different signature
        signature3 = generate_hmac_signature("different-secret", payload)
        self.assertNotEqual(signature, signature3)

    @responses.activate
    def test_successful_webhook_delivery(self):
        """Test successful webhook delivery (Requirement 32.5, 32.6)."""
        # Mock successful HTTP response
        responses.add(
            responses.POST,
            self.webhook.url,
            json={"status": "received"},
            status=200,
        )

        # Deliver webhook
        result = deliver_webhook(str(self.delivery.id))

        # Check result
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["status_code"], 200)
        self.assertIn("duration_ms", result)

        # Refresh delivery from database
        self.delivery.refresh_from_db()

        # Check delivery status
        self.assertEqual(self.delivery.status, WebhookDelivery.SUCCESS)
        self.assertEqual(self.delivery.response_status_code, 200)
        self.assertIn("received", self.delivery.response_body)
        self.assertIsNotNone(self.delivery.sent_at)
        self.assertIsNotNone(self.delivery.completed_at)
        self.assertIsNotNone(self.delivery.duration_ms)

        # Check webhook success tracking
        self.webhook.refresh_from_db()
        self.assertEqual(self.webhook.consecutive_failures, 0)
        self.assertIsNotNone(self.webhook.last_success_at)

    @responses.activate
    def test_failed_webhook_delivery_with_retry(self):
        """Test failed webhook delivery schedules retry (Requirement 32.4)."""
        # Mock failed HTTP response
        responses.add(
            responses.POST,
            self.webhook.url,
            json={"error": "Internal server error"},
            status=500,
        )

        # Deliver webhook
        result = deliver_webhook(str(self.delivery.id))

        # Check result
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["status_code"], 500)
        self.assertTrue(result["can_retry"])

        # Refresh delivery from database
        self.delivery.refresh_from_db()

        # Check delivery status
        self.assertEqual(self.delivery.status, WebhookDelivery.RETRYING)
        self.assertEqual(self.delivery.response_status_code, 500)
        self.assertEqual(self.delivery.attempt_count, 1)
        self.assertIsNotNone(self.delivery.next_retry_at)
        self.assertIn("HTTP 500", self.delivery.error_message)

        # Check webhook failure tracking
        self.webhook.refresh_from_db()
        self.assertEqual(self.webhook.consecutive_failures, 1)
        self.assertIsNotNone(self.webhook.last_failure_at)

    def test_webhook_delivery_timeout(self):
        """Test webhook delivery timeout handling."""
        # Deliver webhook with timeout
        with patch("requests.post") as mock_post:
            mock_post.side_effect = requests.Timeout("Request timed out")
            result = deliver_webhook(str(self.delivery.id))

        # Check result
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["can_retry"])

        # Refresh delivery
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, WebhookDelivery.RETRYING)
        self.assertIn("timed out", self.delivery.error_message)

    def test_webhook_delivery_inactive_webhook(self):
        """Test delivery skips inactive webhooks."""
        # Deactivate webhook
        self.webhook.is_active = False
        self.webhook.save()

        # Deliver webhook
        result = deliver_webhook(str(self.delivery.id))

        # Check result
        self.assertEqual(result["status"], "skipped")

        # Refresh delivery
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, WebhookDelivery.FAILED)
        self.assertIn("inactive", self.delivery.error_message)

    def test_calculate_retry_delay(self):
        """Test exponential backoff calculation (Requirement 32.4)."""
        # Test backoff schedule
        self.assertEqual(calculate_retry_delay(0), 60)  # 1 minute
        self.assertEqual(calculate_retry_delay(1), 300)  # 5 minutes
        self.assertEqual(calculate_retry_delay(2), 900)  # 15 minutes
        self.assertEqual(calculate_retry_delay(3), 3600)  # 1 hour
        self.assertEqual(calculate_retry_delay(4), 14400)  # 4 hours
        self.assertEqual(calculate_retry_delay(5), 14400)  # Max at 4 hours

    def test_delivery_max_retries(self):
        """Test delivery stops after max retries."""
        # Set delivery to max attempts
        self.delivery.attempt_count = 5
        self.delivery.status = WebhookDelivery.RETRYING
        self.delivery.save()

        # Try to mark as failed
        self.delivery.mark_as_failed("Final failure")

        # Should be marked as permanently failed
        self.assertEqual(self.delivery.status, WebhookDelivery.FAILED)
        self.assertIsNone(self.delivery.next_retry_at)
        self.assertIsNotNone(self.delivery.completed_at)

    def test_send_webhook_failure_alert(self):
        """Test failure alert creation (Requirement 32.7)."""
        # Set webhook to 3 consecutive failures (alert threshold)
        self.webhook.consecutive_failures = 3
        self.webhook.last_failure_at = timezone.now()
        self.webhook.save()

        # Set delivery error message
        self.delivery.error_message = "Connection refused"
        self.delivery.save()

        # Send alert
        send_webhook_failure_alert(self.webhook.id, self.delivery.id)

        # Check notification was created
        notifications = Notification.objects.filter(
            user=self.user,
            notification_type="ERROR",
        )
        self.assertEqual(notifications.count(), 1)

        notification = notifications.first()
        self.assertIn("Test Webhook", notification.title)
        self.assertIn("3 times", notification.message)
        self.assertIn("Connection refused", notification.message)

    def test_webhook_auto_disable_after_10_failures(self):
        """Test webhook auto-disables after 10 consecutive failures."""
        # Set to 9 failures
        self.webhook.consecutive_failures = 9
        self.webhook.save()

        # Record one more failure
        self.webhook.record_failure()

        # Should be disabled
        self.webhook.refresh_from_db()
        self.assertFalse(self.webhook.is_active)
        self.assertEqual(self.webhook.consecutive_failures, 10)

    def test_retry_failed_webhooks_task(self):
        """Test periodic retry task."""
        # Create multiple deliveries ready for retry
        delivery1 = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id="11111111-1111-1111-1111-111111111111",
            payload={"test": "data1"},
            status=WebhookDelivery.RETRYING,
            next_retry_at=timezone.now() - timedelta(minutes=1),  # Past due
            attempt_count=1,
        )

        WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id="22222222-2222-2222-2222-222222222222",
            payload={"test": "data2"},
            status=WebhookDelivery.RETRYING,
            next_retry_at=timezone.now() + timedelta(minutes=5),  # Not yet due
            attempt_count=1,
        )

        # Mock the deliver_webhook task
        with patch("apps.core.webhook_tasks.deliver_webhook.delay") as mock_deliver:
            result = retry_failed_webhooks()

        # Should have scheduled retry for delivery1 only
        self.assertEqual(result["retries_scheduled"], 1)
        mock_deliver.assert_called_once_with(str(delivery1.id))

    def test_cleanup_old_deliveries(self):
        """Test cleanup of old delivery records."""
        # Create old successful delivery
        old_success = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id="33333333-3333-3333-3333-333333333333",
            payload={"test": "old"},
            status=WebhookDelivery.SUCCESS,
            completed_at=timezone.now() - timedelta(days=100),
        )

        # Create old failed delivery
        old_failed = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id="44444444-4444-4444-4444-444444444444",
            payload={"test": "old_failed"},
            status=WebhookDelivery.FAILED,
            completed_at=timezone.now() - timedelta(days=130),
        )

        # Create recent delivery
        recent = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id="55555555-5555-5555-5555-555555555555",
            payload={"test": "recent"},
            status=WebhookDelivery.SUCCESS,
            completed_at=timezone.now() - timedelta(days=10),
        )

        # Run cleanup
        cleanup_old_deliveries(days=90)

        # Old successful should be deleted
        self.assertFalse(WebhookDelivery.objects.filter(id=old_success.id).exists())

        # Old failed should be deleted (120 days cutoff)
        self.assertFalse(WebhookDelivery.objects.filter(id=old_failed.id).exists())

        # Recent should still exist
        self.assertTrue(WebhookDelivery.objects.filter(id=recent.id).exists())

    def test_trigger_webhook_event(self):
        """Test triggering webhook event."""
        event_id = "66666666-6666-6666-6666-666666666666"
        payload_data = {
            "sale_number": "SALE-002",
            "total": "499.99",
        }

        # Mock the deliver_webhook task
        with patch("apps.core.webhook_tasks.deliver_webhook.delay") as mock_deliver:
            count = trigger_webhook_event(
                event_type=Webhook.EVENT_SALE_CREATED,
                event_id=event_id,
                payload_data=payload_data,
                tenant=self.tenant,
            )

        # Should have triggered 1 webhook
        self.assertEqual(count, 1)

        # Should have created delivery record
        delivery = WebhookDelivery.objects.filter(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
        ).first()

        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.status, WebhookDelivery.PENDING)
        self.assertIn("sale_number", delivery.payload["data"])
        self.assertEqual(delivery.payload["data"]["sale_number"], "SALE-002")

        # Should have scheduled delivery
        mock_deliver.assert_called_once()

    def test_webhook_delivery_includes_signature_header(self):
        """Test that delivery includes HMAC signature in headers."""
        # Mock successful HTTP response
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                self.webhook.url,
                json={"status": "received"},
                status=200,
            )

            # Deliver webhook
            deliver_webhook(str(self.delivery.id))

            # Check request was made with signature header
            self.assertEqual(len(rsps.calls), 1)
            request = rsps.calls[0].request

            # Should have signature header
            self.assertIn("X-Webhook-Signature", request.headers)
            self.assertIn("X-Webhook-Event", request.headers)
            self.assertIn("X-Webhook-Delivery", request.headers)
            self.assertIn("X-Webhook-Timestamp", request.headers)

            # Signature should be valid
            signature = request.headers["X-Webhook-Signature"]
            self.assertEqual(len(signature), 64)  # SHA256 hex

    def test_webhook_should_alert_on_failure(self):
        """Test alert threshold logic."""
        # No alert on 1st or 2nd failure
        self.webhook.consecutive_failures = 1
        self.assertFalse(self.webhook.should_alert_on_failure())

        self.webhook.consecutive_failures = 2
        self.assertFalse(self.webhook.should_alert_on_failure())

        # Alert on 3rd failure
        self.webhook.consecutive_failures = 3
        self.assertTrue(self.webhook.should_alert_on_failure())

        # No alert on 4th
        self.webhook.consecutive_failures = 4
        self.assertFalse(self.webhook.should_alert_on_failure())

        # Alert on 5th
        self.webhook.consecutive_failures = 5
        self.assertTrue(self.webhook.should_alert_on_failure())

        # Alert on 10th (auto-disable)
        self.webhook.consecutive_failures = 10
        self.assertTrue(self.webhook.should_alert_on_failure())

    def test_delivery_get_retry_info(self):
        """Test getting retry information."""
        # Delivery that can retry
        self.delivery.attempt_count = 2
        self.delivery.next_retry_at = timezone.now() + timedelta(minutes=15)
        self.delivery.status = WebhookDelivery.RETRYING

        info = self.delivery.get_retry_info()

        self.assertTrue(info["can_retry"])
        self.assertEqual(info["attempt"], 3)
        self.assertEqual(info["max_attempts"], 5)
        self.assertIn("minutes_until_retry", info)

        # Delivery at max attempts
        self.delivery.attempt_count = 5
        info = self.delivery.get_retry_info()

        self.assertFalse(info["can_retry"])
        self.assertIn("Maximum retry attempts reached", info["message"])
