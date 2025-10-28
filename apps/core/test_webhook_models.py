"""
Tests for webhook models.

This module tests webhook registration, delivery tracking, and related functionality
per Requirement 32 - Webhook and Integration Management.
"""

import uuid
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

import pytest

from apps.core.models import Tenant, User
from apps.core.webhook_models import Webhook, WebhookDelivery


@pytest.mark.django_db
class WebhookModelTestCase(TestCase):
    """
    Test Webhook model functionality.

    Tests Requirement 32.1: Allow tenants to register webhook URLs.
    Tests Requirement 32.2: Allow tenants to select which events trigger webhooks.
    Tests Requirement 32.3: Sign webhook payloads with HMAC.
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

    def test_webhook_creation(self):
        """Test creating a webhook with basic fields."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            description="Test webhook for sales events",
            events=[Webhook.EVENT_SALE_CREATED, Webhook.EVENT_SALE_UPDATED],
            created_by=self.user,
        )

        self.assertIsNotNone(webhook.id)
        self.assertEqual(webhook.name, "Test Webhook")
        self.assertEqual(webhook.url, "https://example.com/webhook")
        self.assertEqual(webhook.tenant, self.tenant)
        self.assertTrue(webhook.is_active)
        self.assertEqual(webhook.consecutive_failures, 0)
        self.assertIsNone(webhook.last_success_at)
        self.assertIsNone(webhook.last_failure_at)

    def test_webhook_auto_generates_secret(self):
        """Test that webhook automatically generates HMAC secret."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

        # Secret should be auto-generated
        self.assertIsNotNone(webhook.secret)
        self.assertGreater(len(webhook.secret), 0)

        # Secret should be URL-safe base64
        self.assertTrue(all(c.isalnum() or c in "-_" for c in webhook.secret))

    def test_webhook_custom_secret(self):
        """Test creating webhook with custom secret."""
        custom_secret = "my-custom-secret-key"
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            secret=custom_secret,
            created_by=self.user,
        )

        self.assertEqual(webhook.secret, custom_secret)

    def test_is_subscribed_to_event(self):
        """Test checking if webhook is subscribed to specific events."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[
                Webhook.EVENT_SALE_CREATED,
                Webhook.EVENT_INVENTORY_UPDATED,
            ],
            created_by=self.user,
        )

        # Should be subscribed to these events
        self.assertTrue(webhook.is_subscribed_to_event(Webhook.EVENT_SALE_CREATED))
        self.assertTrue(webhook.is_subscribed_to_event(Webhook.EVENT_INVENTORY_UPDATED))

        # Should not be subscribed to these events
        self.assertFalse(webhook.is_subscribed_to_event(Webhook.EVENT_CUSTOMER_CREATED))
        self.assertFalse(webhook.is_subscribed_to_event(Webhook.EVENT_REPAIR_ORDER_CREATED))

    def test_record_success(self):
        """Test recording successful webhook delivery."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            consecutive_failures=3,
            created_by=self.user,
        )

        # Record success
        webhook.record_success()

        # Refresh from database
        webhook.refresh_from_db()

        # Consecutive failures should be reset
        self.assertEqual(webhook.consecutive_failures, 0)
        self.assertIsNotNone(webhook.last_success_at)

    def test_record_failure(self):
        """Test recording failed webhook delivery."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

        # Record failure
        webhook.record_failure()

        # Refresh from database
        webhook.refresh_from_db()

        # Consecutive failures should increment
        self.assertEqual(webhook.consecutive_failures, 1)
        self.assertIsNotNone(webhook.last_failure_at)
        self.assertTrue(webhook.is_active)

    def test_auto_disable_after_failures(self):
        """Test webhook auto-disables after 10 consecutive failures."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            consecutive_failures=9,
            created_by=self.user,
        )

        # Record 10th failure
        webhook.record_failure()

        # Refresh from database
        webhook.refresh_from_db()

        # Should be disabled
        self.assertEqual(webhook.consecutive_failures, 10)
        self.assertFalse(webhook.is_active)

    def test_should_alert_on_failure(self):
        """Test alert triggering on specific failure counts."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

        # Should not alert on 1st or 2nd failure
        webhook.consecutive_failures = 1
        self.assertFalse(webhook.should_alert_on_failure())

        webhook.consecutive_failures = 2
        self.assertFalse(webhook.should_alert_on_failure())

        # Should alert on 3rd, 5th, and 10th failure
        webhook.consecutive_failures = 3
        self.assertTrue(webhook.should_alert_on_failure())

        webhook.consecutive_failures = 5
        self.assertTrue(webhook.should_alert_on_failure())

        webhook.consecutive_failures = 10
        self.assertTrue(webhook.should_alert_on_failure())

        # Should not alert on other counts
        webhook.consecutive_failures = 4
        self.assertFalse(webhook.should_alert_on_failure())

        webhook.consecutive_failures = 7
        self.assertFalse(webhook.should_alert_on_failure())

    def test_get_event_display_names(self):
        """Test getting human-readable event names."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[
                Webhook.EVENT_SALE_CREATED,
                Webhook.EVENT_INVENTORY_UPDATED,
                Webhook.EVENT_CUSTOMER_CREATED,
            ],
            created_by=self.user,
        )

        display_names = webhook.get_event_display_names()

        self.assertEqual(len(display_names), 3)
        self.assertIn("Sale Created", display_names)
        self.assertIn("Inventory Item Updated", display_names)
        self.assertIn("Customer Created", display_names)

    def test_webhook_str_representation(self):
        """Test webhook string representation."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

        expected = f"Test Webhook ({self.tenant.company_name})"
        self.assertEqual(str(webhook), expected)


@pytest.mark.django_db
class WebhookDeliveryModelTestCase(TestCase):
    """
    Test WebhookDelivery model functionality.

    Tests Requirement 32.4: Retry failed deliveries with exponential backoff.
    Tests Requirement 32.5: Track delivery status.
    Tests Requirement 32.6: Log all webhook attempts.
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
            created_by=self.user,
        )

    def test_delivery_creation(self):
        """Test creating a webhook delivery."""
        event_id = uuid.uuid4()
        payload = {"event": "sale.created", "data": {"id": str(event_id)}}

        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=event_id,
            payload=payload,
            signature="test-signature",
        )

        self.assertIsNotNone(delivery.id)
        self.assertEqual(delivery.webhook, self.webhook)
        self.assertEqual(delivery.event_type, Webhook.EVENT_SALE_CREATED)
        self.assertEqual(delivery.event_id, event_id)
        self.assertEqual(delivery.status, WebhookDelivery.PENDING)
        self.assertEqual(delivery.attempt_count, 0)
        self.assertEqual(delivery.max_attempts, 5)

    def test_status_check_methods(self):
        """Test delivery status check methods."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={},
            signature="test-signature",
        )

        # Test pending status
        self.assertTrue(delivery.is_pending())
        self.assertFalse(delivery.is_success())
        self.assertFalse(delivery.is_failed())
        self.assertFalse(delivery.is_retrying())

        # Test success status
        delivery.status = WebhookDelivery.SUCCESS
        delivery.save()
        self.assertFalse(delivery.is_pending())
        self.assertTrue(delivery.is_success())
        self.assertFalse(delivery.is_failed())

        # Test failed status
        delivery.status = WebhookDelivery.FAILED
        delivery.save()
        self.assertFalse(delivery.is_pending())
        self.assertFalse(delivery.is_success())
        self.assertTrue(delivery.is_failed())

        # Test retrying status
        delivery.status = WebhookDelivery.RETRYING
        delivery.save()
        self.assertFalse(delivery.is_pending())
        self.assertFalse(delivery.is_success())
        self.assertFalse(delivery.is_failed())
        self.assertTrue(delivery.is_retrying())

    def test_can_retry(self):
        """Test checking if delivery can be retried."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={},
            signature="test-signature",
        )

        # Should be able to retry initially
        self.assertTrue(delivery.can_retry())

        # Should be able to retry after failures
        delivery.attempt_count = 3
        delivery.save()
        self.assertTrue(delivery.can_retry())

        # Should not be able to retry after max attempts
        delivery.attempt_count = 5
        delivery.save()
        self.assertFalse(delivery.can_retry())

    def test_calculate_next_retry(self):
        """Test exponential backoff calculation."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={},
            signature="test-signature",
        )

        now = timezone.now()

        # After 1st failure (attempt_count=1): 1 minute
        delivery.attempt_count = 1
        next_retry = delivery.calculate_next_retry()
        delta = (next_retry - now).total_seconds()
        self.assertAlmostEqual(delta, 60, delta=5)

        # After 2nd failure (attempt_count=2): 5 minutes
        delivery.attempt_count = 2
        next_retry = delivery.calculate_next_retry()
        delta = (next_retry - now).total_seconds()
        self.assertAlmostEqual(delta, 300, delta=5)

        # After 3rd failure (attempt_count=3): 15 minutes
        delivery.attempt_count = 3
        next_retry = delivery.calculate_next_retry()
        delta = (next_retry - now).total_seconds()
        self.assertAlmostEqual(delta, 900, delta=5)

        # After 4th failure (attempt_count=4): 1 hour
        delivery.attempt_count = 4
        next_retry = delivery.calculate_next_retry()
        delta = (next_retry - now).total_seconds()
        self.assertAlmostEqual(delta, 3600, delta=5)

        # After 5th+ failure (attempt_count=5): 4 hours
        delivery.attempt_count = 5
        next_retry = delivery.calculate_next_retry()
        delta = (next_retry - now).total_seconds()
        self.assertAlmostEqual(delta, 14400, delta=5)

    def test_mark_as_success(self):
        """Test marking delivery as successful."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={},
            signature="test-signature",
        )

        # Mark as success
        delivery.mark_as_success(
            status_code=200,
            response_body='{"status": "ok"}',
            response_headers={"Content-Type": "application/json"},
            duration_ms=150,
        )

        # Refresh from database
        delivery.refresh_from_db()

        self.assertEqual(delivery.status, WebhookDelivery.SUCCESS)
        self.assertEqual(delivery.response_status_code, 200)
        self.assertEqual(delivery.response_body, '{"status": "ok"}')
        self.assertEqual(delivery.duration_ms, 150)
        self.assertIsNotNone(delivery.completed_at)

        # Webhook should have success recorded
        self.webhook.refresh_from_db()
        self.assertEqual(self.webhook.consecutive_failures, 0)
        self.assertIsNotNone(self.webhook.last_success_at)

    def test_mark_as_failed_with_retry(self):
        """Test marking delivery as failed with retry scheduled."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={},
            signature="test-signature",
        )

        # Mark as failed
        delivery.mark_as_failed(
            error_message="Connection timeout",
            status_code=None,
            response_body="",
            duration_ms=5000,
        )

        # Refresh from database
        delivery.refresh_from_db()

        self.assertEqual(delivery.status, WebhookDelivery.RETRYING)
        self.assertEqual(delivery.attempt_count, 1)
        self.assertEqual(delivery.error_message, "Connection timeout")
        self.assertIsNotNone(delivery.next_retry_at)
        self.assertIsNone(delivery.completed_at)

        # Webhook should have failure recorded
        self.webhook.refresh_from_db()
        self.assertEqual(self.webhook.consecutive_failures, 1)
        self.assertIsNotNone(self.webhook.last_failure_at)

    def test_mark_as_failed_no_retry(self):
        """Test marking delivery as failed after max attempts."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={},
            signature="test-signature",
            attempt_count=4,  # Already at 4 attempts
        )

        # Mark as failed (5th attempt)
        delivery.mark_as_failed(
            error_message="Connection timeout",
            status_code=None,
        )

        # Refresh from database
        delivery.refresh_from_db()

        self.assertEqual(delivery.status, WebhookDelivery.FAILED)
        self.assertEqual(delivery.attempt_count, 5)
        self.assertIsNone(delivery.next_retry_at)
        self.assertIsNotNone(delivery.completed_at)

    def test_get_retry_info(self):
        """Test getting retry information."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={},
            signature="test-signature",
        )

        # Can retry
        info = delivery.get_retry_info()
        self.assertTrue(info["can_retry"])
        self.assertEqual(info["attempt"], 1)
        self.assertEqual(info["max_attempts"], 5)

        # Schedule retry
        delivery.next_retry_at = timezone.now() + timedelta(minutes=5)
        delivery.save()

        info = delivery.get_retry_info()
        self.assertTrue(info["can_retry"])
        self.assertIn("next_retry_at", info)
        self.assertIn("minutes_until_retry", info)

        # Cannot retry after max attempts
        delivery.attempt_count = 5
        delivery.save()

        info = delivery.get_retry_info()
        self.assertFalse(info["can_retry"])
        self.assertIn("Maximum retry attempts reached", info["message"])

    def test_response_body_truncation(self):
        """Test that response body is truncated to 10KB."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={},
            signature="test-signature",
        )

        # Create a large response body (20KB)
        large_response = "x" * 20000

        delivery.mark_as_success(
            status_code=200,
            response_body=large_response,
            response_headers={},
            duration_ms=100,
        )

        # Refresh from database
        delivery.refresh_from_db()

        # Should be truncated to 10KB
        self.assertEqual(len(delivery.response_body), 10000)

    def test_delivery_str_representation(self):
        """Test delivery string representation."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={},
            signature="test-signature",
        )

        expected = f"{self.webhook.name} - {Webhook.EVENT_SALE_CREATED} (PENDING)"
        self.assertEqual(str(delivery), expected)
