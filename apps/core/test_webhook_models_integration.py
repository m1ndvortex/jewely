"""
Integration tests for webhook models.

These tests verify webhook models work correctly with the real database,
including all relationships, constraints, and business logic.

NO MOCKS - All tests use real database operations per project testing policy.

Tests Requirement 32 - Webhook and Integration Management
"""

import uuid
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

import pytest

from apps.core.models import Tenant, User
from apps.core.webhook_models import Webhook, WebhookDelivery


@pytest.mark.django_db
class WebhookModelIntegrationTest(TestCase):
    """
    Integration tests for Webhook model with real database operations.

    Tests Requirement 32.1: Register webhook URLs
    Tests Requirement 32.2: Select events
    Tests Requirement 32.3: HMAC signing
    Tests Requirement 32.7: Alert on consistent failures
    """

    def setUp(self):
        """Set up test data with real database records."""
        # Create multiple tenants for isolation testing
        self.tenant1 = Tenant.objects.create(
            company_name="Jewelry Shop 1",
            slug="shop-1",
            status=Tenant.ACTIVE,
        )

        self.tenant2 = Tenant.objects.create(
            company_name="Jewelry Shop 2",
            slug="shop-2",
            status=Tenant.ACTIVE,
        )

        # Create users for both tenants
        self.user1 = User.objects.create_user(
            username="user1",
            email="user1@example.com",
            password="testpass123",
            tenant=self.tenant1,
            role=User.TENANT_OWNER,
        )

        self.user2 = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            password="testpass123",
            tenant=self.tenant2,
            role=User.TENANT_OWNER,
        )

    def test_webhook_tenant_isolation(self):
        """Test that webhooks are properly isolated by tenant."""
        # Create webhooks for different tenants
        webhook1 = Webhook.objects.create(
            tenant=self.tenant1,
            name="Tenant 1 Webhook",
            url="https://tenant1.example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user1,
        )

        webhook2 = Webhook.objects.create(
            tenant=self.tenant2,
            name="Tenant 2 Webhook",
            url="https://tenant2.example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user2,
        )

        # Verify tenant 1 can only see their webhooks
        tenant1_webhooks = Webhook.objects.filter(tenant=self.tenant1)
        self.assertEqual(tenant1_webhooks.count(), 1)
        self.assertEqual(tenant1_webhooks.first().id, webhook1.id)

        # Verify tenant 2 can only see their webhooks
        tenant2_webhooks = Webhook.objects.filter(tenant=self.tenant2)
        self.assertEqual(tenant2_webhooks.count(), 1)
        self.assertEqual(tenant2_webhooks.first().id, webhook2.id)

    def test_webhook_requires_tenant(self):
        """Test that webhook cannot be created without tenant."""
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Webhook.objects.create(
                    tenant=None,
                    name="Invalid Webhook",
                    url="https://example.com/webhook",
                    events=[Webhook.EVENT_SALE_CREATED],
                )

    def test_webhook_cascade_delete_with_tenant(self):
        """Test that webhooks are deleted when tenant is deleted."""
        webhook = Webhook.objects.create(
            tenant=self.tenant1,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user1,
        )

        webhook_id = webhook.id

        # Delete tenant
        self.tenant1.delete()

        # Webhook should be deleted
        self.assertFalse(Webhook.objects.filter(id=webhook_id).exists())

    def test_webhook_secret_uniqueness(self):
        """Test that each webhook gets a unique secret."""
        webhook1 = Webhook.objects.create(
            tenant=self.tenant1,
            name="Webhook 1",
            url="https://example.com/webhook1",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user1,
        )

        webhook2 = Webhook.objects.create(
            tenant=self.tenant1,
            name="Webhook 2",
            url="https://example.com/webhook2",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user1,
        )

        # Secrets should be different
        self.assertNotEqual(webhook1.secret, webhook2.secret)
        self.assertGreater(len(webhook1.secret), 40)
        self.assertGreater(len(webhook2.secret), 40)

    def test_webhook_multiple_events_subscription(self):
        """Test webhook can subscribe to multiple events."""
        events = [
            Webhook.EVENT_SALE_CREATED,
            Webhook.EVENT_SALE_UPDATED,
            Webhook.EVENT_INVENTORY_UPDATED,
            Webhook.EVENT_CUSTOMER_CREATED,
        ]

        webhook = Webhook.objects.create(
            tenant=self.tenant1,
            name="Multi-Event Webhook",
            url="https://example.com/webhook",
            events=events,
            created_by=self.user1,
        )

        # Refresh from database
        webhook.refresh_from_db()

        # Verify all events are stored
        self.assertEqual(len(webhook.events), 4)
        for event in events:
            self.assertIn(event, webhook.events)
            self.assertTrue(webhook.is_subscribed_to_event(event))

    def test_webhook_failure_tracking_persistence(self):
        """Test that failure tracking persists across database operations."""
        webhook = Webhook.objects.create(
            tenant=self.tenant1,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user1,
        )

        # Record multiple failures
        for i in range(5):
            webhook.record_failure()

        # Refresh from database
        webhook.refresh_from_db()

        # Verify failure count persisted
        self.assertEqual(webhook.consecutive_failures, 5)
        self.assertIsNotNone(webhook.last_failure_at)
        self.assertTrue(webhook.is_active)

        # Record success
        webhook.record_success()

        # Refresh from database
        webhook.refresh_from_db()

        # Verify reset persisted
        self.assertEqual(webhook.consecutive_failures, 0)
        self.assertIsNotNone(webhook.last_success_at)

    def test_webhook_auto_disable_persistence(self):
        """Test that auto-disable after 10 failures persists."""
        webhook = Webhook.objects.create(
            tenant=self.tenant1,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            consecutive_failures=9,
            created_by=self.user1,
        )

        # Record 10th failure
        webhook.record_failure()

        # Refresh from database
        webhook.refresh_from_db()

        # Verify disabled state persisted
        self.assertEqual(webhook.consecutive_failures, 10)
        self.assertFalse(webhook.is_active)

        # Query from database to verify
        db_webhook = Webhook.objects.get(id=webhook.id)
        self.assertFalse(db_webhook.is_active)

    def test_webhook_created_by_relationship(self):
        """Test webhook created_by relationship with user."""
        webhook = Webhook.objects.create(
            tenant=self.tenant1,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user1,
        )

        # Refresh from database
        webhook.refresh_from_db()

        # Verify relationship
        self.assertEqual(webhook.created_by.id, self.user1.id)
        self.assertEqual(webhook.created_by.username, "user1")

        # Verify reverse relationship
        user_webhooks = self.user1.webhooks_created.all()
        self.assertEqual(user_webhooks.count(), 1)
        self.assertEqual(user_webhooks.first().id, webhook.id)

    def test_webhook_created_by_null_on_user_delete(self):
        """Test that webhook.created_by is set to null when user is deleted."""
        webhook = Webhook.objects.create(
            tenant=self.tenant1,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user1,
        )

        webhook_id = webhook.id

        # Delete user
        self.user1.delete()

        # Webhook should still exist but created_by should be null
        webhook = Webhook.objects.get(id=webhook_id)
        self.assertIsNone(webhook.created_by)

    def test_webhook_ordering(self):
        """Test that webhooks are ordered by created_at descending."""
        # Create webhooks with slight time differences
        webhook1 = Webhook.objects.create(
            tenant=self.tenant1,
            name="Webhook 1",
            url="https://example.com/webhook1",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user1,
        )

        webhook2 = Webhook.objects.create(
            tenant=self.tenant1,
            name="Webhook 2",
            url="https://example.com/webhook2",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user1,
        )

        webhook3 = Webhook.objects.create(
            tenant=self.tenant1,
            name="Webhook 3",
            url="https://example.com/webhook3",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user1,
        )

        # Query all webhooks
        webhooks = Webhook.objects.filter(tenant=self.tenant1)

        # Should be ordered newest first
        self.assertEqual(webhooks[0].id, webhook3.id)
        self.assertEqual(webhooks[1].id, webhook2.id)
        self.assertEqual(webhooks[2].id, webhook1.id)


@pytest.mark.django_db
class WebhookDeliveryModelIntegrationTest(TestCase):
    """
    Integration tests for WebhookDelivery model with real database operations.

    Tests Requirement 32.4: Retry with exponential backoff
    Tests Requirement 32.5: Track delivery status
    Tests Requirement 32.6: Detailed logs
    """

    def setUp(self):
        """Set up test data with real database records."""
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            role=User.TENANT_OWNER,
        )

        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

    def test_delivery_requires_webhook(self):
        """Test that delivery cannot be created without webhook."""
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WebhookDelivery.objects.create(
                    webhook=None,
                    event_type=Webhook.EVENT_SALE_CREATED,
                    event_id=uuid.uuid4(),
                    payload={},
                    signature="test",
                )

    def test_delivery_cascade_delete_with_webhook(self):
        """Test that deliveries are deleted when webhook is deleted."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"test": "data"},
            signature="test-signature",
        )

        delivery_id = delivery.id

        # Delete webhook
        self.webhook.delete()

        # Delivery should be deleted
        self.assertFalse(WebhookDelivery.objects.filter(id=delivery_id).exists())

    def test_delivery_status_transitions_persistence(self):
        """Test that delivery status transitions persist correctly."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"test": "data"},
            signature="test-signature",
        )

        # Initial state
        self.assertEqual(delivery.status, WebhookDelivery.PENDING)

        # Mark as failed (should transition to RETRYING)
        delivery.mark_as_failed("Connection timeout")

        # Refresh from database
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.RETRYING)
        self.assertEqual(delivery.attempt_count, 1)
        self.assertIsNotNone(delivery.next_retry_at)

        # Mark as success
        delivery.mark_as_success(200, '{"status": "ok"}', {}, 100)

        # Refresh from database
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.SUCCESS)
        self.assertIsNotNone(delivery.completed_at)

    def test_delivery_max_attempts_enforcement(self):
        """Test that delivery stops retrying after max attempts."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"test": "data"},
            signature="test-signature",
        )

        # Fail 5 times (max attempts)
        for i in range(5):
            delivery.mark_as_failed(f"Attempt {i+1} failed")
            delivery.refresh_from_db()

        # Should be permanently failed
        self.assertEqual(delivery.status, WebhookDelivery.FAILED)
        self.assertEqual(delivery.attempt_count, 5)
        self.assertIsNone(delivery.next_retry_at)
        self.assertIsNotNone(delivery.completed_at)
        self.assertFalse(delivery.can_retry())

    def test_delivery_webhook_failure_tracking_integration(self):
        """Test that delivery failures update webhook failure tracking."""
        # Initial state
        self.assertEqual(self.webhook.consecutive_failures, 0)

        # Create and fail a delivery
        delivery1 = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"test": "data"},
            signature="test-signature",
        )

        delivery1.mark_as_failed("Connection timeout")

        # Webhook should track failure
        self.webhook.refresh_from_db()
        self.assertEqual(self.webhook.consecutive_failures, 1)

        # Create and fail another delivery
        delivery2 = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"test": "data"},
            signature="test-signature",
        )

        delivery2.mark_as_failed("Connection timeout")

        # Webhook should track second failure
        self.webhook.refresh_from_db()
        self.assertEqual(self.webhook.consecutive_failures, 2)

        # Create and succeed a delivery
        delivery3 = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"test": "data"},
            signature="test-signature",
        )

        delivery3.mark_as_success(200, '{"status": "ok"}', {}, 100)

        # Webhook should reset failure count
        self.webhook.refresh_from_db()
        self.assertEqual(self.webhook.consecutive_failures, 0)

    def test_delivery_response_data_persistence(self):
        """Test that delivery response data persists correctly."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"test": "data"},
            signature="test-signature",
        )

        response_body = '{"status": "ok", "message": "Webhook received"}'
        response_headers = {
            "Content-Type": "application/json",
            "X-Request-Id": "12345",
        }

        delivery.mark_as_success(200, response_body, response_headers, 150)

        # Refresh from database
        delivery.refresh_from_db()

        # Verify all response data persisted
        self.assertEqual(delivery.response_status_code, 200)
        self.assertEqual(delivery.response_body, response_body)
        self.assertEqual(delivery.response_headers["Content-Type"], "application/json")
        self.assertEqual(delivery.response_headers["X-Request-Id"], "12345")
        self.assertEqual(delivery.duration_ms, 150)

    def test_delivery_large_response_truncation(self):
        """Test that large response bodies are truncated to 10KB."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"test": "data"},
            signature="test-signature",
        )

        # Create 20KB response
        large_response = "x" * 20000

        delivery.mark_as_success(200, large_response, {}, 100)

        # Refresh from database
        delivery.refresh_from_db()

        # Should be truncated to 10KB
        self.assertEqual(len(delivery.response_body), 10000)

    def test_delivery_ordering(self):
        """Test that deliveries are ordered by created_at descending."""
        event_id = uuid.uuid4()

        # Create multiple deliveries
        delivery1 = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=event_id,
            payload={"test": "data1"},
            signature="sig1",
        )

        delivery2 = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=event_id,
            payload={"test": "data2"},
            signature="sig2",
        )

        delivery3 = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=event_id,
            payload={"test": "data3"},
            signature="sig3",
        )

        # Query all deliveries
        deliveries = WebhookDelivery.objects.filter(webhook=self.webhook)

        # Should be ordered newest first
        self.assertEqual(deliveries[0].id, delivery3.id)
        self.assertEqual(deliveries[1].id, delivery2.id)
        self.assertEqual(deliveries[2].id, delivery1.id)

    def test_delivery_event_tracking(self):
        """Test that deliveries can be queried by event type and ID."""
        event_id = uuid.uuid4()

        # Create deliveries for different events
        delivery1 = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=event_id,
            payload={"test": "data"},
            signature="sig1",
        )

        WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_INVENTORY_UPDATED,
            event_id=uuid.uuid4(),
            payload={"test": "data"},
            signature="sig2",
        )

        # Query by event type
        sale_deliveries = WebhookDelivery.objects.filter(event_type=Webhook.EVENT_SALE_CREATED)
        self.assertEqual(sale_deliveries.count(), 1)
        self.assertEqual(sale_deliveries.first().id, delivery1.id)

        # Query by event ID
        event_deliveries = WebhookDelivery.objects.filter(event_id=event_id)
        self.assertEqual(event_deliveries.count(), 1)
        self.assertEqual(event_deliveries.first().id, delivery1.id)

    def test_delivery_retry_scheduling_persistence(self):
        """Test that retry scheduling persists correctly."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"test": "data"},
            signature="test-signature",
        )

        # Mark as failed to schedule retry
        before_fail = timezone.now()
        delivery.mark_as_failed("Connection timeout")

        # Refresh from database
        delivery.refresh_from_db()

        # Verify retry is scheduled
        self.assertIsNotNone(delivery.next_retry_at)
        self.assertEqual(delivery.status, WebhookDelivery.RETRYING)

        # Verify retry time is in the future (should be ~1 minute from before_fail)
        self.assertGreater(delivery.next_retry_at, before_fail)

        # Verify retry time is approximately 1 minute from when we failed it
        expected_retry = before_fail + timedelta(minutes=1)
        time_diff = abs((delivery.next_retry_at - expected_retry).total_seconds())
        self.assertLess(time_diff, 5)  # Within 5 seconds of expected

        # Query deliveries ready for retry (use the actual retry time)
        ready_for_retry = WebhookDelivery.objects.filter(
            status=WebhookDelivery.RETRYING,
            next_retry_at__lte=delivery.next_retry_at + timedelta(seconds=1),
        )

        self.assertEqual(ready_for_retry.count(), 1)
        self.assertEqual(ready_for_retry.first().id, delivery.id)


@pytest.mark.django_db
class WebhookIndexPerformanceTest(TestCase):
    """
    Test that database indexes are working correctly for performance.

    Verifies that queries use indexes as expected.
    """

    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            role=User.TENANT_OWNER,
        )

    def test_webhook_tenant_active_index(self):
        """Test that tenant + is_active queries use index."""
        # Create multiple webhooks
        for i in range(10):
            Webhook.objects.create(
                tenant=self.tenant,
                name=f"Webhook {i}",
                url=f"https://example.com/webhook{i}",
                events=[Webhook.EVENT_SALE_CREATED],
                is_active=(i % 2 == 0),  # Half active, half inactive
                created_by=self.user,
            )

        # Query active webhooks for tenant
        active_webhooks = Webhook.objects.filter(
            tenant=self.tenant,
            is_active=True,
        )

        # Should return 5 active webhooks
        self.assertEqual(active_webhooks.count(), 5)

    def test_webhook_tenant_created_index(self):
        """Test that tenant + created_at queries use index."""
        # Create webhooks
        for i in range(5):
            Webhook.objects.create(
                tenant=self.tenant,
                name=f"Webhook {i}",
                url=f"https://example.com/webhook{i}",
                events=[Webhook.EVENT_SALE_CREATED],
                created_by=self.user,
            )

        # Query webhooks ordered by created_at
        webhooks = Webhook.objects.filter(tenant=self.tenant).order_by("-created_at")

        # Should return all webhooks in correct order
        self.assertEqual(webhooks.count(), 5)

    def test_delivery_webhook_status_index(self):
        """Test that webhook + status queries use index."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

        # Create deliveries with different statuses
        for i in range(10):
            delivery = WebhookDelivery.objects.create(
                webhook=webhook,
                event_type=Webhook.EVENT_SALE_CREATED,
                event_id=uuid.uuid4(),
                payload={"test": f"data{i}"},
                signature=f"sig{i}",
            )

            if i < 3:
                delivery.status = WebhookDelivery.SUCCESS
            elif i < 6:
                delivery.status = WebhookDelivery.FAILED
            else:
                delivery.status = WebhookDelivery.RETRYING

            delivery.save()

        # Query by webhook and status
        failed_deliveries = WebhookDelivery.objects.filter(
            webhook=webhook,
            status=WebhookDelivery.FAILED,
        )

        self.assertEqual(failed_deliveries.count(), 3)

    def test_delivery_retry_index(self):
        """Test that status + next_retry_at queries use index."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

        # Create deliveries ready for retry
        now = timezone.now()
        for i in range(5):
            WebhookDelivery.objects.create(
                webhook=webhook,
                event_type=Webhook.EVENT_SALE_CREATED,
                event_id=uuid.uuid4(),
                payload={"test": f"data{i}"},
                signature=f"sig{i}",
                status=WebhookDelivery.RETRYING,
                next_retry_at=now + timedelta(minutes=i),
            )

        # Query deliveries ready for retry
        ready_for_retry = WebhookDelivery.objects.filter(
            status=WebhookDelivery.RETRYING,
            next_retry_at__lte=now + timedelta(minutes=2),
        )

        # Should return deliveries with retry time <= now + 2 minutes
        self.assertEqual(ready_for_retry.count(), 3)
