"""
Integration tests for webhook delivery system.

These tests use REAL HTTP servers and REAL database operations to verify
the complete webhook delivery flow end-to-end.

Per Requirement 32 - Webhook and Integration Management
"""

import hashlib
import hmac
import json
import threading
import time
import uuid
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

from django.test import TestCase
from django.utils import timezone

import pytest

from apps.core.models import Tenant, User
from apps.core.webhook_models import Webhook, WebhookDelivery
from apps.core.webhook_tasks import (
    cleanup_old_deliveries,
    deliver_webhook,
    retry_failed_webhooks,
    send_webhook_failure_alert,
)
from apps.core.webhook_utils import trigger_webhook_event
from apps.notifications.models import Notification


# Test HTTP Server for receiving webhooks
class WebhookTestHandler(BaseHTTPRequestHandler):
    """HTTP handler for testing webhook delivery."""

    # Class variables to store received requests
    received_requests = []
    response_status = 200
    response_body = {"status": "received"}
    should_timeout = False

    def do_POST(self):
        """Handle POST requests."""
        # Simulate timeout if requested
        if self.should_timeout:
            time.sleep(35)  # Longer than webhook timeout
            return

        # Read request body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # Store request details
        request_data = {
            "path": self.path,
            "headers": dict(self.headers),
            "body": body.decode("utf-8"),
            "timestamp": time.time(),
        }
        WebhookTestHandler.received_requests.append(request_data)

        # Send response
        self.send_response(self.response_status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(self.response_body).encode("utf-8"))

    def log_message(self, format, *args):
        """Suppress log messages."""
        pass


def start_test_server(port=8765):
    """Start a test HTTP server in a background thread."""
    server = HTTPServer(("127.0.0.1", port), WebhookTestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.5)  # Give server time to start
    return server


@pytest.mark.django_db
class WebhookDeliveryIntegrationTestCase(TestCase):
    """
    Integration tests for webhook delivery with REAL HTTP requests.

    Tests all requirements without mocking:
    - Requirement 32.1: Register webhook URLs
    - Requirement 32.2: Select events
    - Requirement 32.3: HMAC signing
    - Requirement 32.4: Retry with exponential backoff
    - Requirement 32.5: Track delivery status
    - Requirement 32.6: Log request/response data
    - Requirement 32.7: Alert on failures
    """

    @classmethod
    def setUpClass(cls):
        """Set up test HTTP server."""
        super().setUpClass()
        cls.test_server = start_test_server(port=8765)
        cls.webhook_url = "http://127.0.0.1:8765/webhook"

    @classmethod
    def tearDownClass(cls):
        """Shut down test HTTP server."""
        cls.test_server.shutdown()
        super().tearDownClass()

    def setUp(self):
        """Set up test data."""
        # Clear received requests
        WebhookTestHandler.received_requests = []
        WebhookTestHandler.response_status = 200
        WebhookTestHandler.response_body = {"status": "received"}
        WebhookTestHandler.should_timeout = False

        # Create tenant
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop-integration",
            status=Tenant.ACTIVE,
        )

        # Create user
        self.user = User.objects.create_user(
            username="testuser_integration",
            email="test_integration@example.com",
            password="testpass123",
            tenant=self.tenant,
            role=User.TENANT_OWNER,
        )

        # Create webhook pointing to real test server
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Integration Test Webhook",
            url=self.webhook_url,
            events=[
                Webhook.EVENT_SALE_CREATED,
                Webhook.EVENT_INVENTORY_CREATED,
                Webhook.EVENT_CUSTOMER_CREATED,
            ],
            secret="integration-test-secret-key",
            created_by=self.user,
        )

    def test_successful_webhook_delivery_real_http(self):
        """
        Test successful webhook delivery with REAL HTTP request.

        Tests Requirement 32.3: HMAC signing
        Tests Requirement 32.5: Track delivery status
        Tests Requirement 32.6: Log request/response data
        """
        # Create delivery
        event_id = uuid.uuid4()
        payload = {
            "event": "sale.created",
            "event_id": str(event_id),
            "timestamp": timezone.now().isoformat(),
            "data": {"sale_number": "SALE-001", "total": "299.99"},
        }

        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=event_id,
            payload=payload,
        )

        # Deliver webhook (REAL HTTP request)
        result = deliver_webhook(str(delivery.id))

        # Verify result
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["status_code"], 200)
        self.assertGreater(result["duration_ms"], 0)

        # Verify delivery was updated in database
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.SUCCESS)
        self.assertEqual(delivery.response_status_code, 200)
        self.assertIn("received", delivery.response_body)
        self.assertIsNotNone(delivery.sent_at)
        self.assertIsNotNone(delivery.completed_at)
        self.assertGreater(delivery.duration_ms, 0)

        # Verify webhook success tracking
        self.webhook.refresh_from_db()
        self.assertEqual(self.webhook.consecutive_failures, 0)
        self.assertIsNotNone(self.webhook.last_success_at)

        # Verify REAL HTTP request was received
        self.assertEqual(len(WebhookTestHandler.received_requests), 1)
        request = WebhookTestHandler.received_requests[0]

        # Verify headers
        self.assertIn("X-Webhook-Signature", request["headers"])
        self.assertIn("X-Webhook-Event", request["headers"])
        self.assertIn("X-Webhook-Delivery", request["headers"])
        self.assertIn("X-Webhook-Timestamp", request["headers"])

        # Verify HMAC signature is valid
        received_signature = request["headers"]["X-Webhook-Signature"]
        payload_bytes = request["body"].encode("utf-8")
        expected_signature = hmac.new(
            self.webhook.secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(received_signature, expected_signature)

        # Verify payload
        received_payload = json.loads(request["body"])
        self.assertEqual(received_payload["event"], "sale.created")
        self.assertEqual(received_payload["data"]["sale_number"], "SALE-001")

    def test_failed_webhook_delivery_with_retry_real_http(self):
        """
        Test failed webhook delivery with REAL HTTP 500 error.

        Tests Requirement 32.4: Retry with exponential backoff
        Tests Requirement 32.5: Track delivery status
        """
        # Configure server to return 500 error
        WebhookTestHandler.response_status = 500
        WebhookTestHandler.response_body = {"error": "Internal server error"}

        # Create delivery
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"event": "sale.created", "data": {"sale_number": "SALE-002"}},
        )

        # Deliver webhook (REAL HTTP request)
        result = deliver_webhook(str(delivery.id))

        # Verify result
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["status_code"], 500)
        self.assertTrue(result["can_retry"])

        # Verify delivery status
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.RETRYING)
        self.assertEqual(delivery.response_status_code, 500)
        self.assertEqual(delivery.attempt_count, 1)
        self.assertIsNotNone(delivery.next_retry_at)
        self.assertIn("HTTP 500", delivery.error_message)

        # Verify webhook failure tracking
        self.webhook.refresh_from_db()
        self.assertEqual(self.webhook.consecutive_failures, 1)
        self.assertIsNotNone(self.webhook.last_failure_at)

        # Verify REAL HTTP request was received
        self.assertEqual(len(WebhookTestHandler.received_requests), 1)

    def test_webhook_timeout_real_http(self):
        """
        Test webhook timeout with REAL slow server.

        Tests Requirement 32.4: Retry logic
        Tests Requirement 32.6: Log errors
        """
        # Configure server to timeout
        WebhookTestHandler.should_timeout = True

        # Create delivery
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"event": "sale.created", "data": {}},
        )

        # Deliver webhook (REAL HTTP request that will timeout)
        start_time = time.time()
        result = deliver_webhook(str(delivery.id))
        duration = time.time() - start_time

        # Verify timeout occurred (should be around 30 seconds)
        self.assertGreater(duration, 29)
        self.assertLess(duration, 35)

        # Verify result
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["can_retry"])

        # Verify delivery status
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.RETRYING)
        self.assertIn("timed out", delivery.error_message)

    def test_trigger_webhook_event_integration(self):
        """
        Test triggering webhook event creates delivery and sends request.

        Tests Requirement 32.1: Register webhooks
        Tests Requirement 32.2: Select events
        """
        # Trigger webhook event
        event_id = uuid.uuid4()
        count = trigger_webhook_event(
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=event_id,
            payload_data={"sale_number": "SALE-003", "total": "599.99"},
            tenant=self.tenant,
            async_delivery=False,  # Synchronous for testing
        )

        # Verify webhook was triggered
        self.assertEqual(count, 1)

        # Verify delivery was created
        delivery = WebhookDelivery.objects.filter(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
        ).first()
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.status, WebhookDelivery.SUCCESS)

        # Verify REAL HTTP request was received
        self.assertEqual(len(WebhookTestHandler.received_requests), 1)
        request = WebhookTestHandler.received_requests[0]
        payload = json.loads(request["body"])
        self.assertEqual(payload["data"]["sale_number"], "SALE-003")

    def test_multiple_webhooks_same_event(self):
        """
        Test multiple webhooks subscribed to same event.

        Tests Requirement 32.2: Event selection
        """
        # Create second webhook
        Webhook.objects.create(
            tenant=self.tenant,
            name="Second Webhook",
            url=self.webhook_url,
            events=[Webhook.EVENT_SALE_CREATED],
            secret="second-secret",
            created_by=self.user,
        )

        # Trigger event
        event_id = uuid.uuid4()
        count = trigger_webhook_event(
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=event_id,
            payload_data={"sale_number": "SALE-MULTI"},
            tenant=self.tenant,
            async_delivery=False,
        )

        # Both webhooks should be triggered
        self.assertEqual(count, 2)

        # Verify both deliveries
        deliveries = WebhookDelivery.objects.filter(event_id=event_id)
        self.assertEqual(deliveries.count(), 2)

        # Verify both HTTP requests received
        self.assertEqual(len(WebhookTestHandler.received_requests), 2)

    def test_webhook_failure_alert_integration(self):
        """
        Test failure alert creation with REAL database operations.

        Tests Requirement 32.7: Alert on consistent failures
        """
        # Set webhook to 3 consecutive failures
        self.webhook.consecutive_failures = 3
        self.webhook.last_failure_at = timezone.now()
        self.webhook.save()

        # Create failed delivery
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"test": "data"},
            status=WebhookDelivery.FAILED,
            error_message="Connection refused",
        )

        # Send alert (REAL database operation)
        send_webhook_failure_alert(self.webhook.id, delivery.id)

        # Verify notification was created in REAL database
        notifications = Notification.objects.filter(
            user=self.user,
            notification_type="ERROR",
        )
        self.assertEqual(notifications.count(), 1)

        notification = notifications.first()
        self.assertIn("Integration Test Webhook", notification.title)
        self.assertIn("3 times", notification.message)
        self.assertIn("Connection refused", notification.message)

    def test_retry_failed_webhooks_integration(self):
        """
        Test periodic retry task with REAL database queries.

        Tests Requirement 32.4: Automatic retry
        """
        # Create delivery ready for retry
        WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"test": "retry"},
            status=WebhookDelivery.RETRYING,
            next_retry_at=timezone.now() - timedelta(minutes=1),  # Past due
            attempt_count=1,
        )

        # Run retry task (REAL database query and task scheduling)
        result = retry_failed_webhooks()

        # Verify retry was scheduled
        self.assertEqual(result["retries_scheduled"], 1)

        # Note: We can't easily test the actual retry execution here
        # because it's scheduled asynchronously, but we verified the
        # retry task finds and schedules the right deliveries

    def test_cleanup_old_deliveries_integration(self):
        """
        Test cleanup task with REAL database operations.

        Tests Requirement 32.6: Delivery logging and cleanup
        """
        # Create old successful delivery
        old_success = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"test": "old"},
            status=WebhookDelivery.SUCCESS,
            completed_at=timezone.now() - timedelta(days=100),
        )

        # Create old failed delivery
        old_failed = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"test": "old_failed"},
            status=WebhookDelivery.FAILED,
            completed_at=timezone.now() - timedelta(days=130),
        )

        # Create recent delivery
        recent = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"test": "recent"},
            status=WebhookDelivery.SUCCESS,
            completed_at=timezone.now() - timedelta(days=10),
        )

        # Run cleanup (REAL database delete operations)
        result = cleanup_old_deliveries(days=90)

        # Verify cleanup results
        self.assertGreater(result["deleted_success"], 0)
        self.assertGreater(result["deleted_failed"], 0)

        # Verify old deliveries deleted from REAL database
        self.assertFalse(WebhookDelivery.objects.filter(id=old_success.id).exists())
        self.assertFalse(WebhookDelivery.objects.filter(id=old_failed.id).exists())

        # Verify recent delivery still exists
        self.assertTrue(WebhookDelivery.objects.filter(id=recent.id).exists())

    def test_webhook_auto_disable_after_failures_integration(self):
        """
        Test webhook auto-disable after 10 failures with REAL database.

        Tests Requirement 32.7: Alert and disable on consistent failures
        """
        # Set to 9 failures
        self.webhook.consecutive_failures = 9
        self.webhook.save()

        # Record one more failure (REAL database operation)
        self.webhook.record_failure()

        # Verify webhook disabled in REAL database
        self.webhook.refresh_from_db()
        self.assertFalse(self.webhook.is_active)
        self.assertEqual(self.webhook.consecutive_failures, 10)

    def test_hmac_signature_verification_integration(self):
        """
        Test HMAC signature can be verified by receiver.

        Tests Requirement 32.3: HMAC payload signing
        """
        # Create delivery
        payload = {"event": "test", "data": {"test": "value"}}
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload=payload,
        )

        # Deliver webhook
        deliver_webhook(str(delivery.id))

        # Get received request
        self.assertEqual(len(WebhookTestHandler.received_requests), 1)
        request = WebhookTestHandler.received_requests[0]

        # Verify signature
        received_signature = request["headers"]["X-Webhook-Signature"]
        payload_bytes = request["body"].encode("utf-8")

        # Receiver would verify like this:
        expected_signature = hmac.new(
            self.webhook.secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        self.assertEqual(received_signature, expected_signature)

    def test_exponential_backoff_timing_integration(self):
        """
        Test exponential backoff timing with REAL database.

        Tests Requirement 32.4: Exponential backoff
        """
        # Configure server to fail
        WebhookTestHandler.response_status = 500

        # Create delivery
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"test": "backoff"},
        )

        # First attempt
        deliver_webhook(str(delivery.id))
        delivery.refresh_from_db()
        self.assertEqual(delivery.attempt_count, 1)
        first_retry = delivery.next_retry_at

        # Verify retry scheduled for ~1 minute from now
        time_until_retry = (first_retry - timezone.now()).total_seconds()
        self.assertGreater(time_until_retry, 50)  # At least 50 seconds
        self.assertLess(time_until_retry, 70)  # At most 70 seconds

        # Simulate second attempt
        delivery.sent_at = timezone.now()
        delivery.save()
        deliver_webhook(str(delivery.id))
        delivery.refresh_from_db()
        self.assertEqual(delivery.attempt_count, 2)
        second_retry = delivery.next_retry_at

        # Verify retry scheduled for ~5 minutes from now
        time_until_retry = (second_retry - timezone.now()).total_seconds()
        self.assertGreater(time_until_retry, 290)  # At least 4:50
        self.assertLess(time_until_retry, 310)  # At most 5:10
