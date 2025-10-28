"""
Comprehensive webhook tests covering all requirements for Task 23.5.

This module tests:
- Webhook registration (Requirement 32.1, 32.2)
- Webhook delivery and retries (Requirement 32.4, 32.5)
- HMAC signing (Requirement 32.3)
- OAuth integration (Requirement 32.10)

Per Task 23.5 - Write webhook tests
"""

import hashlib
import hmac
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

import pytest
import responses

from apps.core.integration_models import ExternalService, OAuth2Token
from apps.core.models import Tenant, User
from apps.core.webhook_models import Webhook, WebhookDelivery
from apps.core.webhook_tasks import deliver_webhook, generate_hmac_signature, retry_failed_webhooks
from apps.core.webhook_utils import trigger_webhook_event


@pytest.mark.django_db
class TestWebhookRegistration(TestCase):
    """
    Test webhook registration functionality.

    Tests Requirement 32.1: Allow tenants to register webhook URLs
    Tests Requirement 32.2: Allow tenants to select which events trigger webhooks
    """

    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop-registration",
            status=Tenant.ACTIVE,
        )

        self.user = User.objects.create_user(
            username="testuser_registration",
            email="test_registration@example.com",
            password="testpass123",
            tenant=self.tenant,
            role=User.TENANT_OWNER,
        )

    def test_register_webhook_with_single_event(self):
        """Test registering a webhook for a single event type."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Sales Webhook",
            url="https://example.com/webhooks/sales",
            description="Webhook for sales events",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

        self.assertIsNotNone(webhook.id)
        self.assertEqual(webhook.name, "Sales Webhook")
        self.assertEqual(webhook.url, "https://example.com/webhooks/sales")
        self.assertEqual(len(webhook.events), 1)
        self.assertIn(Webhook.EVENT_SALE_CREATED, webhook.events)
        self.assertTrue(webhook.is_active)

    def test_register_webhook_with_multiple_events(self):
        """Test registering a webhook for multiple event types."""
        events = [
            Webhook.EVENT_SALE_CREATED,
            Webhook.EVENT_SALE_UPDATED,
            Webhook.EVENT_INVENTORY_CREATED,
            Webhook.EVENT_CUSTOMER_CREATED,
        ]

        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Multi-Event Webhook",
            url="https://example.com/webhooks/all",
            events=events,
            created_by=self.user,
        )

        self.assertEqual(len(webhook.events), 4)
        for event in events:
            self.assertIn(event, webhook.events)
            self.assertTrue(webhook.is_subscribed_to_event(event))

    def test_register_webhook_with_all_available_events(self):
        """Test registering a webhook for all available event types."""
        all_events = [choice[0] for choice in Webhook.EVENT_CHOICES]

        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="All Events Webhook",
            url="https://example.com/webhooks/all-events",
            events=all_events,
            created_by=self.user,
        )

        self.assertEqual(len(webhook.events), len(Webhook.EVENT_CHOICES))
        for event in all_events:
            self.assertTrue(webhook.is_subscribed_to_event(event))

    def test_webhook_event_subscription_check(self):
        """Test checking if webhook is subscribed to specific events."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Selective Webhook",
            url="https://example.com/webhooks/selective",
            events=[
                Webhook.EVENT_SALE_CREATED,
                Webhook.EVENT_INVENTORY_UPDATED,
            ],
            created_by=self.user,
        )

        # Should be subscribed
        self.assertTrue(webhook.is_subscribed_to_event(Webhook.EVENT_SALE_CREATED))
        self.assertTrue(webhook.is_subscribed_to_event(Webhook.EVENT_INVENTORY_UPDATED))

        # Should not be subscribed
        self.assertFalse(webhook.is_subscribed_to_event(Webhook.EVENT_CUSTOMER_CREATED))
        self.assertFalse(webhook.is_subscribed_to_event(Webhook.EVENT_REPAIR_ORDER_CREATED))

    def test_multiple_webhooks_same_tenant(self):
        """Test that a tenant can register multiple webhooks."""
        webhook1 = Webhook.objects.create(
            tenant=self.tenant,
            name="Webhook 1",
            url="https://example.com/webhook1",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

        webhook2 = Webhook.objects.create(
            tenant=self.tenant,
            name="Webhook 2",
            url="https://example.com/webhook2",
            events=[Webhook.EVENT_INVENTORY_CREATED],
            created_by=self.user,
        )

        webhooks = Webhook.objects.filter(tenant=self.tenant)
        self.assertEqual(webhooks.count(), 2)
        self.assertIn(webhook1, webhooks)
        self.assertIn(webhook2, webhooks)

    def test_webhook_url_validation(self):
        """Test that webhook URL must be valid."""
        # Valid URLs should work
        valid_urls = [
            "https://example.com/webhook",
            "http://localhost:8000/webhook",
            "https://api.example.com/v1/webhooks/receive",
        ]

        for url in valid_urls:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name=f"Webhook for {url}",
                url=url,
                events=[Webhook.EVENT_SALE_CREATED],
                created_by=self.user,
            )
            self.assertEqual(webhook.url, url)

    def test_webhook_get_event_display_names(self):
        """Test getting human-readable event names."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Display Names Test",
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


@pytest.mark.django_db
class TestWebhookDeliveryAndRetries(TestCase):
    """
    Test webhook delivery and retry functionality.

    Tests Requirement 32.4: Retry failed deliveries with exponential backoff
    Tests Requirement 32.5: Track delivery status
    Tests Requirement 32.6: Log request/response data
    """

    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop-delivery",
            status=Tenant.ACTIVE,
        )

        self.user = User.objects.create_user(
            username="testuser_delivery",
            email="test_delivery@example.com",
            password="testpass123",
            tenant=self.tenant,
            role=User.TENANT_OWNER,
        )

        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            secret="test-secret-key",
            created_by=self.user,
        )

    @responses.activate
    def test_successful_delivery_tracking(self):
        """Test that successful deliveries are properly tracked."""
        # Create delivery
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"event": "sale.created", "data": {"sale_number": "SALE-001"}},
        )

        # Mock successful response
        responses.add(
            responses.POST,
            self.webhook.url,
            json={"status": "received"},
            status=200,
        )

        # Deliver webhook
        result = deliver_webhook(str(delivery.id))

        # Verify result
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["status_code"], 200)

        # Verify delivery tracking
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.SUCCESS)
        self.assertEqual(delivery.response_status_code, 200)
        self.assertIn("received", delivery.response_body)
        self.assertIsNotNone(delivery.sent_at)
        self.assertIsNotNone(delivery.completed_at)
        self.assertIsNotNone(delivery.duration_ms)
        self.assertGreater(delivery.duration_ms, 0)

    @responses.activate
    def test_failed_delivery_with_retry_schedule(self):
        """Test that failed deliveries schedule retries with exponential backoff."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"event": "sale.created", "data": {}},
        )

        # Mock failed response
        responses.add(
            responses.POST,
            self.webhook.url,
            json={"error": "Internal server error"},
            status=500,
        )

        # Deliver webhook
        result = deliver_webhook(str(delivery.id))

        # Verify result
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["status_code"], 500)
        self.assertTrue(result["can_retry"])

        # Verify retry scheduling
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.RETRYING)
        self.assertEqual(delivery.attempt_count, 1)
        self.assertIsNotNone(delivery.next_retry_at)

        # Verify exponential backoff (1st retry should be ~1 minute)
        time_until_retry = (delivery.next_retry_at - timezone.now()).total_seconds()
        self.assertGreater(time_until_retry, 50)
        self.assertLess(time_until_retry, 70)

    @responses.activate
    def test_exponential_backoff_progression(self):
        """Test that retry delays follow exponential backoff schedule."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"test": "data"},
        )

        # Mock failed response
        responses.add(
            responses.POST,
            self.webhook.url,
            status=500,
        )

        # Test backoff schedule
        expected_delays = [60, 300, 900, 3600, 14400]  # seconds

        for attempt, expected_delay in enumerate(expected_delays):
            # Reset delivery for next attempt
            delivery.sent_at = timezone.now()
            delivery.save()

            # Deliver webhook
            deliver_webhook(str(delivery.id))

            # Verify retry delay
            delivery.refresh_from_db()
            if delivery.can_retry():
                time_until_retry = (delivery.next_retry_at - timezone.now()).total_seconds()
                # Allow 10 second tolerance
                self.assertAlmostEqual(time_until_retry, expected_delay, delta=10)

    @responses.activate
    def test_max_retries_reached(self):
        """Test that delivery stops after max retries."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"test": "data"},
            attempt_count=4,  # Already at 4 attempts
        )

        # Mock failed response
        responses.add(
            responses.POST,
            self.webhook.url,
            status=500,
        )

        # Deliver webhook (5th attempt)
        result = deliver_webhook(str(delivery.id))

        # Verify result
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["can_retry"])

        # Verify delivery is permanently failed
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.FAILED)
        self.assertEqual(delivery.attempt_count, 5)
        self.assertIsNone(delivery.next_retry_at)
        self.assertIsNotNone(delivery.completed_at)

    @responses.activate
    def test_request_response_logging(self):
        """Test that request and response data are logged."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"event": "sale.created", "data": {"sale_number": "SALE-LOG-001"}},
        )

        # Mock response with headers
        responses.add(
            responses.POST,
            self.webhook.url,
            json={"status": "received", "id": "12345"},
            status=200,
            headers={"X-Request-ID": "req-12345", "Content-Type": "application/json"},
        )

        # Deliver webhook
        deliver_webhook(str(delivery.id))

        # Verify response logging
        delivery.refresh_from_db()
        self.assertEqual(delivery.response_status_code, 200)
        self.assertIn("received", delivery.response_body)
        self.assertIn("12345", delivery.response_body)
        self.assertIn("X-Request-ID", delivery.response_headers)
        self.assertEqual(delivery.response_headers["X-Request-ID"], "req-12345")

    def test_retry_failed_webhooks_task(self):
        """Test periodic retry task finds and retries deliveries."""
        # Create delivery ready for retry
        delivery1 = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"test": "retry1"},
            status=WebhookDelivery.RETRYING,
            next_retry_at=timezone.now() - timedelta(minutes=1),  # Past due
            attempt_count=1,
        )

        # Create delivery not yet due for retry
        WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"test": "retry2"},
            status=WebhookDelivery.RETRYING,
            next_retry_at=timezone.now() + timedelta(minutes=5),  # Future
            attempt_count=1,
        )

        # Mock the deliver_webhook task
        with patch("apps.core.webhook_tasks.deliver_webhook.delay") as mock_deliver:
            result = retry_failed_webhooks()

        # Verify only past-due delivery was scheduled
        self.assertEqual(result["retries_scheduled"], 1)
        mock_deliver.assert_called_once_with(str(delivery1.id))


@pytest.mark.django_db
class TestHMACSigningVerification(TestCase):
    """
    Test HMAC signing and verification.

    Tests Requirement 32.3: Sign webhook payloads with HMAC
    """

    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop-hmac",
            status=Tenant.ACTIVE,
        )

        self.user = User.objects.create_user(
            username="testuser_hmac",
            email="test_hmac@example.com",
            password="testpass123",
            tenant=self.tenant,
            role=User.TENANT_OWNER,
        )

        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="HMAC Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            secret="test-hmac-secret-key",
            created_by=self.user,
        )

    def test_hmac_signature_generation(self):
        """Test HMAC signature generation."""
        secret = "test-secret"
        payload = b'{"test": "data"}'

        signature = generate_hmac_signature(secret, payload)

        # Verify signature format
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)  # SHA256 produces 64 hex chars
        self.assertTrue(all(c in "0123456789abcdef" for c in signature))

    def test_hmac_signature_consistency(self):
        """Test that same input produces same signature."""
        secret = "test-secret"
        payload = b'{"test": "data"}'

        signature1 = generate_hmac_signature(secret, payload)
        signature2 = generate_hmac_signature(secret, payload)

        self.assertEqual(signature1, signature2)

    def test_hmac_signature_different_secrets(self):
        """Test that different secrets produce different signatures."""
        payload = b'{"test": "data"}'

        signature1 = generate_hmac_signature("secret1", payload)
        signature2 = generate_hmac_signature("secret2", payload)

        self.assertNotEqual(signature1, signature2)

    def test_hmac_signature_different_payloads(self):
        """Test that different payloads produce different signatures."""
        secret = "test-secret"

        signature1 = generate_hmac_signature(secret, b'{"test": "data1"}')
        signature2 = generate_hmac_signature(secret, b'{"test": "data2"}')

        self.assertNotEqual(signature1, signature2)

    @responses.activate
    def test_webhook_includes_hmac_signature_header(self):
        """Test that webhook delivery includes HMAC signature in headers."""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"event": "sale.created", "data": {"test": "hmac"}},
        )

        # Mock response
        responses.add(
            responses.POST,
            self.webhook.url,
            json={"status": "received"},
            status=200,
        )

        # Deliver webhook
        deliver_webhook(str(delivery.id))

        # Verify request was made with signature header
        self.assertEqual(len(responses.calls), 1)
        request = responses.calls[0].request

        # Verify signature header exists
        self.assertIn("X-Webhook-Signature", request.headers)

        # Verify signature is valid
        signature = request.headers["X-Webhook-Signature"]
        self.assertEqual(len(signature), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in signature))

    @responses.activate
    def test_hmac_signature_verification(self):
        """Test that receiver can verify HMAC signature."""
        payload_data = {"event": "sale.created", "data": {"sale_number": "SALE-VERIFY"}}

        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload=payload_data,
        )

        # Mock response
        responses.add(
            responses.POST,
            self.webhook.url,
            json={"status": "received"},
            status=200,
        )

        # Deliver webhook
        deliver_webhook(str(delivery.id))

        # Get the request
        request = responses.calls[0].request
        received_signature = request.headers["X-Webhook-Signature"]
        payload_bytes = request.body

        # Receiver would verify signature like this:
        expected_signature = hmac.new(
            self.webhook.secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        # Verify signatures match
        self.assertEqual(received_signature, expected_signature)

    @responses.activate
    def test_webhook_includes_metadata_headers(self):
        """Test that webhook includes metadata headers."""
        event_id = uuid.uuid4()
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=event_id,
            payload={"event": "sale.created", "data": {}},
        )

        # Mock response
        responses.add(
            responses.POST,
            self.webhook.url,
            json={"status": "received"},
            status=200,
        )

        # Deliver webhook
        deliver_webhook(str(delivery.id))

        # Verify headers
        request = responses.calls[0].request
        self.assertIn("X-Webhook-Signature", request.headers)
        self.assertIn("X-Webhook-Event", request.headers)
        self.assertIn("X-Webhook-Delivery", request.headers)
        self.assertIn("X-Webhook-Timestamp", request.headers)

        # Verify header values
        self.assertEqual(request.headers["X-Webhook-Event"], Webhook.EVENT_SALE_CREATED)
        self.assertEqual(request.headers["X-Webhook-Delivery"], str(delivery.id))

    def test_webhook_auto_generates_secret(self):
        """Test that webhook automatically generates HMAC secret."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Auto Secret Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

        # Secret should be auto-generated
        self.assertIsNotNone(webhook.secret)
        self.assertGreater(len(webhook.secret), 32)

    def test_webhook_custom_secret(self):
        """Test creating webhook with custom secret."""
        custom_secret = "my-custom-hmac-secret-key-12345"

        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Custom Secret Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            secret=custom_secret,
            created_by=self.user,
        )

        self.assertEqual(webhook.secret, custom_secret)


@pytest.mark.django_db
class TestOAuthIntegration(TestCase):
    """
    Test OAuth2 integration functionality.

    Tests Requirement 32.10: Support OAuth2 for third-party service connections
    """

    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop-oauth",
            status=Tenant.ACTIVE,
        )

        self.user = User.objects.create_user(
            username="testuser_oauth",
            email="test_oauth@example.com",
            password="testpass123",
            tenant=self.tenant,
            role=User.TENANT_OWNER,
        )

    def test_create_oauth2_service(self):
        """Test creating an external service with OAuth2 authentication."""
        service = ExternalService.objects.create(
            tenant=self.tenant,
            name="OAuth2 Service",
            description="Test OAuth2 service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_OAUTH2,
            api_key="client_id_12345",
            api_secret="client_secret_67890",
            config={
                "oauth2_auth_endpoint": "https://provider.com/oauth/authorize",
                "oauth2_token_endpoint": "https://provider.com/oauth/token",
                "oauth2_default_scope": "read write",
            },
        )

        self.assertIsNotNone(service.id)
        self.assertEqual(service.auth_type, ExternalService.AUTH_OAUTH2)
        self.assertEqual(service.api_key, "client_id_12345")
        self.assertEqual(service.api_secret, "client_secret_67890")
        self.assertIn("oauth2_auth_endpoint", service.config)
        self.assertIn("oauth2_token_endpoint", service.config)

    def test_create_oauth2_token(self):
        """Test creating an OAuth2 token for a service."""
        service = ExternalService.objects.create(
            tenant=self.tenant,
            name="OAuth2 Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_OAUTH2,
        )

        expires_at = timezone.now() + timedelta(hours=1)

        token = OAuth2Token.objects.create(
            service=service,
            access_token="access_token_abc123",
            refresh_token="refresh_token_xyz789",
            token_type="Bearer",
            expires_at=expires_at,
            scope="read write",
        )

        self.assertIsNotNone(token.id)
        self.assertEqual(token.service, service)
        self.assertEqual(token.access_token, "access_token_abc123")
        self.assertEqual(token.refresh_token, "refresh_token_xyz789")
        self.assertEqual(token.token_type, "Bearer")
        self.assertFalse(token.is_expired())

    def test_oauth2_token_expiration(self):
        """Test OAuth2 token expiration detection."""
        service = ExternalService.objects.create(
            tenant=self.tenant,
            name="OAuth2 Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_OAUTH2,
        )

        # Create expired token
        expires_at = timezone.now() - timedelta(hours=1)

        token = OAuth2Token.objects.create(
            service=service,
            access_token="expired_token",
            expires_at=expires_at,
        )

        self.assertTrue(token.is_expired())

    def test_oauth2_token_refresh_needed(self):
        """Test OAuth2 token refresh detection."""
        service = ExternalService.objects.create(
            tenant=self.tenant,
            name="OAuth2 Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_OAUTH2,
        )

        # Create token expiring soon (within 5 minutes)
        expires_at = timezone.now() + timedelta(minutes=3)

        token = OAuth2Token.objects.create(
            service=service,
            access_token="soon_to_expire_token",
            refresh_token="refresh_token",
            expires_at=expires_at,
        )

        self.assertFalse(token.is_expired())
        self.assertTrue(token.needs_refresh())

    def test_oauth2_service_token_relationship(self):
        """Test relationship between OAuth2 service and token."""
        service = ExternalService.objects.create(
            tenant=self.tenant,
            name="OAuth2 Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_OAUTH2,
        )

        token = OAuth2Token.objects.create(
            service=service,
            access_token="test_token",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        # Verify relationship
        self.assertEqual(service.oauth2_token, token)
        self.assertEqual(token.service, service)
        self.assertFalse(token.is_expired())
        self.assertFalse(token.needs_refresh())

    def test_multiple_oauth2_services(self):
        """Test that tenant can have multiple OAuth2 services."""
        service1 = ExternalService.objects.create(
            tenant=self.tenant,
            name="OAuth2 Service 1",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_OAUTH2,
        )

        service2 = ExternalService.objects.create(
            tenant=self.tenant,
            name="OAuth2 Service 2",
            service_type=ExternalService.SERVICE_PAYMENT_GATEWAY,
            auth_type=ExternalService.AUTH_OAUTH2,
        )

        services = ExternalService.objects.filter(
            tenant=self.tenant,
            auth_type=ExternalService.AUTH_OAUTH2,
        )

        self.assertEqual(services.count(), 2)
        self.assertIn(service1, services)
        self.assertIn(service2, services)

    def test_oauth2_token_update(self):
        """Test updating OAuth2 token after refresh."""
        service = ExternalService.objects.create(
            tenant=self.tenant,
            name="OAuth2 Service",
            service_type=ExternalService.SERVICE_CUSTOM,
            auth_type=ExternalService.AUTH_OAUTH2,
        )

        # Create initial token
        token = OAuth2Token.objects.create(
            service=service,
            access_token="old_token",
            refresh_token="old_refresh",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        # Update token (simulating refresh)
        new_expires_at = timezone.now() + timedelta(hours=2)
        token.access_token = "new_token"
        token.refresh_token = "new_refresh"
        token.expires_at = new_expires_at
        token.save()

        # Verify update
        token.refresh_from_db()
        self.assertEqual(token.access_token, "new_token")
        self.assertEqual(token.refresh_token, "new_refresh")
        self.assertFalse(token.is_expired())


@pytest.mark.django_db
class TestWebhookEventTriggering(TestCase):
    """
    Test webhook event triggering from application events.

    Tests integration of webhook system with application events.
    """

    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop-trigger",
            status=Tenant.ACTIVE,
        )

        self.user = User.objects.create_user(
            username="testuser_trigger",
            email="test_trigger@example.com",
            password="testpass123",
            tenant=self.tenant,
            role=User.TENANT_OWNER,
        )

    def test_trigger_webhook_event_creates_delivery(self):
        """Test that triggering an event creates delivery records."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

        event_id = uuid.uuid4()

        # Mock the deliver_webhook task
        with patch("apps.core.webhook_tasks.deliver_webhook.delay") as mock_deliver:
            count = trigger_webhook_event(
                event_type=Webhook.EVENT_SALE_CREATED,
                event_id=event_id,
                payload_data={"sale_number": "SALE-001"},
                tenant=self.tenant,
            )

        # Verify webhook was triggered
        self.assertEqual(count, 1)

        # Verify delivery was created
        delivery = WebhookDelivery.objects.filter(
            webhook=webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
        ).first()

        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.status, WebhookDelivery.PENDING)
        self.assertIn("sale_number", delivery.payload["data"])

        # Verify delivery was scheduled
        mock_deliver.assert_called_once()

    def test_trigger_multiple_webhooks_same_event(self):
        """Test that multiple webhooks receive the same event."""
        Webhook.objects.create(
            tenant=self.tenant,
            name="Webhook 1",
            url="https://example.com/webhook1",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

        Webhook.objects.create(
            tenant=self.tenant,
            name="Webhook 2",
            url="https://example.com/webhook2",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

        event_id = uuid.uuid4()

        # Mock the deliver_webhook task
        with patch("apps.core.webhook_tasks.deliver_webhook.delay"):
            count = trigger_webhook_event(
                event_type=Webhook.EVENT_SALE_CREATED,
                event_id=event_id,
                payload_data={"sale_number": "SALE-MULTI"},
                tenant=self.tenant,
            )

        # Both webhooks should be triggered
        self.assertEqual(count, 2)

        # Verify both deliveries were created
        deliveries = WebhookDelivery.objects.filter(event_id=event_id)
        self.assertEqual(deliveries.count(), 2)

    def test_trigger_only_subscribed_webhooks(self):
        """Test that only webhooks subscribed to event are triggered."""
        # Webhook subscribed to sale events
        webhook1 = Webhook.objects.create(
            tenant=self.tenant,
            name="Sales Webhook",
            url="https://example.com/webhook1",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

        # Webhook subscribed to inventory events
        Webhook.objects.create(
            tenant=self.tenant,
            name="Inventory Webhook",
            url="https://example.com/webhook2",
            events=[Webhook.EVENT_INVENTORY_CREATED],
            created_by=self.user,
        )

        event_id = uuid.uuid4()

        # Trigger sale event
        with patch("apps.core.webhook_tasks.deliver_webhook.delay"):
            count = trigger_webhook_event(
                event_type=Webhook.EVENT_SALE_CREATED,
                event_id=event_id,
                payload_data={"sale_number": "SALE-001"},
                tenant=self.tenant,
            )

        # Only sales webhook should be triggered
        self.assertEqual(count, 1)

        # Verify only one delivery was created
        deliveries = WebhookDelivery.objects.filter(event_id=event_id)
        self.assertEqual(deliveries.count(), 1)
        self.assertEqual(deliveries.first().webhook, webhook1)

    def test_inactive_webhooks_not_triggered(self):
        """Test that inactive webhooks are not triggered."""
        # Active webhook
        Webhook.objects.create(
            tenant=self.tenant,
            name="Active Webhook",
            url="https://example.com/webhook1",
            events=[Webhook.EVENT_SALE_CREATED],
            is_active=True,
            created_by=self.user,
        )

        # Inactive webhook
        Webhook.objects.create(
            tenant=self.tenant,
            name="Inactive Webhook",
            url="https://example.com/webhook2",
            events=[Webhook.EVENT_SALE_CREATED],
            is_active=False,
            created_by=self.user,
        )

        event_id = uuid.uuid4()

        # Trigger event
        with patch("apps.core.webhook_tasks.deliver_webhook.delay"):
            count = trigger_webhook_event(
                event_type=Webhook.EVENT_SALE_CREATED,
                event_id=event_id,
                payload_data={"sale_number": "SALE-001"},
                tenant=self.tenant,
            )

        # Only active webhook should be triggered
        self.assertEqual(count, 1)
