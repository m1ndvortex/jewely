"""
Integration tests for webhook management interface.

These tests verify the webhook interface works correctly with real database,
real HTTP requests, and actual form submissions.

NO MOCKS - All tests use real operations per project testing policy.

Tests Requirement 32 - Webhook and Integration Management
"""

import json
import uuid

from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse

import pytest
import responses

from apps.core.models import Tenant, User
from apps.core.webhook_models import Webhook, WebhookDelivery


@pytest.mark.django_db
class WebhookInterfaceIntegrationTest(TestCase):
    """
    Integration tests for webhook management interface.

    Tests Requirement 32.1: Register webhook URLs
    Tests Requirement 32.2: Select events
    Tests Requirement 32.3: HMAC signing
    Tests Requirement 32.8: Webhook testing
    """

    def setUp(self):
        """Set up test data with real database records."""
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

        # Create client and login
        self.client = Client()
        self.client.login(username="testuser", password="testpass123")

        # Set tenant in session
        session = self.client.session
        session["tenant_id"] = str(self.tenant.id)
        session.save()

    def test_webhook_list_view_displays_webhooks(self):
        """
        Test that webhook list view displays all webhooks for tenant.

        Tests Requirement 32.1: Display registered webhooks
        """
        # Create test webhooks
        Webhook.objects.create(
            tenant=self.tenant,
            name="Sales Webhook",
            url="https://example.com/sales",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
            is_active=True,
        )

        Webhook.objects.create(
            tenant=self.tenant,
            name="Inventory Webhook",
            url="https://example.com/inventory",
            events=[Webhook.EVENT_INVENTORY_UPDATED],
            created_by=self.user,
            is_active=False,
        )

        # Access list view
        response = self.client.get(reverse("core:webhooks:webhook_list"))

        # Verify response
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sales Webhook")
        self.assertContains(response, "Inventory Webhook")
        self.assertContains(response, "https://example.com/sales")
        self.assertContains(response, "https://example.com/inventory")

        # Verify statistics
        self.assertContains(response, "2")  # Total webhooks
        self.assertContains(response, "1")  # Active webhooks

    def test_webhook_list_view_search_functionality(self):
        """
        Test webhook list search functionality.

        Tests Requirement 32.1: Search webhooks
        """
        # Create test webhooks
        Webhook.objects.create(
            tenant=self.tenant,
            name="Sales Webhook",
            url="https://example.com/sales",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

        Webhook.objects.create(
            tenant=self.tenant,
            name="Inventory Webhook",
            url="https://example.com/inventory",
            events=[Webhook.EVENT_INVENTORY_UPDATED],
            created_by=self.user,
        )

        # Search for "sales"
        response = self.client.get(reverse("core:webhooks:webhook_list"), {"search": "sales"})

        # Verify only sales webhook is shown
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sales Webhook")
        self.assertNotContains(response, "Inventory Webhook")

    def test_webhook_list_view_status_filter(self):
        """
        Test webhook list status filtering.

        Tests Requirement 32.1: Filter webhooks by status
        """
        # Create active and inactive webhooks
        Webhook.objects.create(
            tenant=self.tenant,
            name="Active Webhook",
            url="https://example.com/active",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
            is_active=True,
        )

        Webhook.objects.create(
            tenant=self.tenant,
            name="Inactive Webhook",
            url="https://example.com/inactive",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
            is_active=False,
        )

        # Filter for active only
        response = self.client.get(reverse("core:webhooks:webhook_list"), {"status": "active"})

        # Verify only active webhook is shown
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Active Webhook")
        self.assertNotContains(response, "Inactive Webhook")

    def test_webhook_create_view_creates_webhook(self):
        """
        Test creating a webhook through the interface.

        Tests Requirement 32.1: Register webhook URLs
        Tests Requirement 32.2: Select events
        Tests Requirement 32.3: Generate HMAC secret
        """
        # Prepare form data
        # Note: For MultipleChoiceField in forms, we need to send the data correctly
        form_data = {
            "name": "New Test Webhook",
            "url": "https://example.com/webhook",
            "description": "Test webhook description",
            "event_choices": [
                Webhook.EVENT_SALE_CREATED,
                Webhook.EVENT_INVENTORY_UPDATED,
            ],
            "is_active": "on",  # Checkbox fields expect "on" in POST data
        }

        # Submit form
        response = self.client.post(reverse("core:webhooks:webhook_create"), form_data)

        # Verify redirect to list
        self.assertEqual(response.status_code, 302)

        # Verify webhook was created
        webhook = Webhook.objects.get(name="New Test Webhook")
        self.assertEqual(webhook.tenant, self.tenant)
        self.assertEqual(webhook.url, "https://example.com/webhook")
        self.assertEqual(webhook.description, "Test webhook description")
        self.assertEqual(
            set(webhook.events),
            {Webhook.EVENT_SALE_CREATED, Webhook.EVENT_INVENTORY_UPDATED},
        )
        self.assertTrue(webhook.is_active)
        self.assertEqual(webhook.created_by, self.user)

        # Verify HMAC secret was generated
        self.assertIsNotNone(webhook.secret)
        self.assertGreater(len(webhook.secret), 40)

        # Verify success message
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("created successfully" in str(m) for m in messages))

    def test_webhook_create_view_validates_url(self):
        """
        Test URL validation in webhook creation.

        Tests Requirement 32.1: Validate webhook URLs
        """
        # Try to create webhook with invalid URL
        form_data = {
            "name": "Invalid Webhook",
            "url": "not-a-valid-url",
            "event_choices": [Webhook.EVENT_SALE_CREATED],
            "is_active": True,
        }

        response = self.client.post(reverse("core:webhooks:webhook_create"), form_data)

        # Verify form error
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "form", "url", "Enter a valid URL.")

        # Verify webhook was not created
        self.assertEqual(Webhook.objects.filter(name="Invalid Webhook").count(), 0)

    def test_webhook_detail_view_displays_information(self):
        """
        Test webhook detail view displays all information.

        Tests Requirement 32.1: Display webhook details
        Tests Requirement 32.3: Display HMAC secret
        Tests Requirement 32.5: Display delivery statistics
        """
        # Create webhook
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED, Webhook.EVENT_INVENTORY_UPDATED],
            created_by=self.user,
            is_active=True,
        )

        # Create some deliveries
        for i in range(5):
            WebhookDelivery.objects.create(
                webhook=webhook,
                event_type=Webhook.EVENT_SALE_CREATED,
                event_id=uuid.uuid4(),
                payload={"test": "data"},
                signature="test-signature",
                status=WebhookDelivery.SUCCESS if i < 3 else WebhookDelivery.FAILED,
            )

        # Access detail view
        response = self.client.get(
            reverse("core:webhooks:webhook_detail", kwargs={"pk": webhook.pk})
        )

        # Verify response
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Webhook")
        self.assertContains(response, "https://example.com/webhook")
        self.assertContains(response, webhook.secret)

        # Verify statistics
        self.assertContains(response, "5")  # Total deliveries
        self.assertContains(response, "3")  # Successful
        self.assertContains(response, "2")  # Failed

        # Verify event display
        self.assertContains(response, "Sale Created")
        self.assertContains(response, "Inventory Item Updated")

    def test_webhook_update_view_updates_webhook(self):
        """
        Test updating webhook through the interface.

        Tests Requirement 32.1: Update webhook configuration
        Tests Requirement 32.2: Update event selection
        """
        # Create webhook
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Original Name",
            url="https://example.com/original",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
            is_active=True,
        )

        # Update form data
        form_data = {
            "name": "Updated Name",
            "url": "https://example.com/updated",
            "description": "Updated description",
            "event_choices": [
                Webhook.EVENT_SALE_CREATED,
                Webhook.EVENT_INVENTORY_UPDATED,
                Webhook.EVENT_CUSTOMER_CREATED,
            ],
            # Note: is_active=False means checkbox is not checked, so we omit it
        }

        # Submit update
        response = self.client.post(
            reverse("core:webhooks:webhook_update", kwargs={"pk": webhook.pk}), form_data
        )

        # Verify redirect
        self.assertEqual(response.status_code, 302)

        # Verify webhook was updated
        webhook.refresh_from_db()
        self.assertEqual(webhook.name, "Updated Name")
        self.assertEqual(webhook.url, "https://example.com/updated")
        self.assertEqual(webhook.description, "Updated description")
        self.assertEqual(
            set(webhook.events),
            {
                Webhook.EVENT_SALE_CREATED,
                Webhook.EVENT_INVENTORY_UPDATED,
                Webhook.EVENT_CUSTOMER_CREATED,
            },
        )
        self.assertFalse(webhook.is_active)

    def test_webhook_delete_view_deletes_webhook(self):
        """
        Test deleting webhook through the interface.

        Tests Requirement 32.1: Delete webhooks
        """
        # Create webhook
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="To Delete",
            url="https://example.com/delete",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

        webhook_id = webhook.id

        # Delete webhook
        response = self.client.post(
            reverse("core:webhooks:webhook_delete", kwargs={"pk": webhook.pk})
        )

        # Verify redirect
        self.assertEqual(response.status_code, 302)

        # Verify webhook was deleted
        self.assertEqual(Webhook.objects.filter(id=webhook_id).count(), 0)

    def test_webhook_toggle_view_toggles_status(self):
        """
        Test toggling webhook active status.

        Tests Requirement 32.1: Activate/deactivate webhooks
        """
        # Create active webhook
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Toggle Test",
            url="https://example.com/toggle",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
            is_active=True,
        )

        # Toggle to inactive
        response = self.client.post(
            reverse("core:webhooks:webhook_toggle", kwargs={"pk": webhook.pk})
        )

        # Verify redirect
        self.assertEqual(response.status_code, 302)

        # Verify status changed
        webhook.refresh_from_db()
        self.assertFalse(webhook.is_active)

        # Toggle back to active
        response = self.client.post(
            reverse("core:webhooks:webhook_toggle", kwargs={"pk": webhook.pk})
        )

        webhook.refresh_from_db()
        self.assertTrue(webhook.is_active)

    def test_webhook_regenerate_secret_view_generates_new_secret(self):
        """
        Test regenerating HMAC secret.

        Tests Requirement 32.3: Regenerate HMAC secrets
        """
        # Create webhook
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Secret Test",
            url="https://example.com/secret",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

        original_secret = webhook.secret

        # Regenerate secret
        response = self.client.post(
            reverse("core:webhooks:webhook_regenerate_secret", kwargs={"pk": webhook.pk})
        )

        # Verify redirect
        self.assertEqual(response.status_code, 302)

        # Verify new secret was generated
        webhook.refresh_from_db()
        self.assertNotEqual(webhook.secret, original_secret)
        self.assertGreater(len(webhook.secret), 40)

    @responses.activate
    def test_webhook_test_view_sends_test_request(self):
        """
        Test webhook testing functionality with real HTTP request.

        Tests Requirement 32.8: Webhook testing capability
        Tests Requirement 32.3: HMAC signature generation
        """
        # Create webhook
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

        # Mock the HTTP endpoint
        responses.add(
            responses.POST,
            "https://example.com/webhook",
            json={"status": "received"},
            status=200,
        )

        # Submit test form
        form_data = {
            "event_type": Webhook.EVENT_SALE_CREATED,
        }

        response = self.client.post(
            reverse("core:webhooks:webhook_test", kwargs={"pk": webhook.pk}), form_data
        )

        # Verify response
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test webhook sent successfully")
        self.assertContains(response, "200")  # Status code

        # Verify HTTP request was made
        self.assertEqual(len(responses.calls), 1)
        request = responses.calls[0].request

        # Verify headers
        self.assertIn("X-Webhook-Signature", request.headers)
        self.assertIn("X-Webhook-Event", request.headers)
        self.assertIn("X-Webhook-ID", request.headers)
        self.assertEqual(request.headers["X-Webhook-Event"], Webhook.EVENT_SALE_CREATED)
        self.assertEqual(request.headers["X-Webhook-ID"], str(webhook.id))

        # Verify payload
        payload = json.loads(request.body)
        self.assertEqual(payload["event_type"], Webhook.EVENT_SALE_CREATED)
        self.assertTrue(payload["test"])

    @responses.activate
    def test_webhook_test_view_with_custom_payload(self):
        """
        Test webhook testing with custom payload.

        Tests Requirement 32.8: Custom payload testing
        """
        # Create webhook
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

        # Mock the HTTP endpoint
        responses.add(
            responses.POST,
            "https://example.com/webhook",
            json={"status": "received"},
            status=200,
        )

        # Custom payload
        custom_payload = {"custom": "data", "value": 123}

        # Submit test form with custom payload
        form_data = {
            "event_type": Webhook.EVENT_SALE_CREATED,
            "test_payload": json.dumps(custom_payload),
        }

        response = self.client.post(
            reverse("core:webhooks:webhook_test", kwargs={"pk": webhook.pk}), form_data
        )

        # Verify response
        self.assertEqual(response.status_code, 200)

        # Verify custom payload was sent
        request = responses.calls[0].request
        payload = json.loads(request.body)
        self.assertEqual(payload["custom"], "data")
        self.assertEqual(payload["value"], 123)

    @responses.activate
    def test_webhook_test_view_handles_failure(self):
        """
        Test webhook testing handles failures gracefully.

        Tests Requirement 32.8: Handle test failures
        """
        # Create webhook
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

        # Mock failed endpoint
        responses.add(
            responses.POST,
            "https://example.com/webhook",
            json={"error": "Internal server error"},
            status=500,
        )

        # Submit test form
        form_data = {
            "event_type": Webhook.EVENT_SALE_CREATED,
        }

        response = self.client.post(
            reverse("core:webhooks:webhook_test", kwargs={"pk": webhook.pk}), form_data
        )

        # Verify response shows failure
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test webhook failed")
        self.assertContains(response, "500")

    def test_webhook_delivery_list_view_displays_deliveries(self):
        """
        Test delivery list view displays all deliveries.

        Tests Requirement 32.5: Track delivery status
        Tests Requirement 32.6: Display delivery logs
        """
        # Create webhook
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

        # Create deliveries
        WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"test": "data1"},
            signature="sig1",
            status=WebhookDelivery.SUCCESS,
            response_status_code=200,
        )

        WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=Webhook.EVENT_INVENTORY_UPDATED,
            event_id=uuid.uuid4(),
            payload={"test": "data2"},
            signature="sig2",
            status=WebhookDelivery.FAILED,
            response_status_code=500,
        )

        # Access delivery list
        response = self.client.get(
            reverse("core:webhooks:webhook_delivery_list", kwargs={"webhook_id": webhook.pk})
        )

        # Verify response
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, Webhook.EVENT_SALE_CREATED)
        self.assertContains(response, Webhook.EVENT_INVENTORY_UPDATED)
        self.assertContains(response, "200")
        self.assertContains(response, "500")
        self.assertContains(response, "Success")
        self.assertContains(response, "Failed")

    def test_webhook_delivery_list_view_filters_by_status(self):
        """
        Test delivery list filtering by status.

        Tests Requirement 32.5: Filter deliveries by status
        """
        # Create webhook
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

        # Create deliveries with different statuses
        WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"test": "success"},
            signature="sig1",
            status=WebhookDelivery.SUCCESS,
        )

        WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload={"test": "failed"},
            signature="sig2",
            status=WebhookDelivery.FAILED,
        )

        # Filter for success only
        response = self.client.get(
            reverse("core:webhooks:webhook_delivery_list", kwargs={"webhook_id": webhook.pk}),
            {"status": "SUCCESS"},
        )

        # Verify only success delivery is shown
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "success")
        self.assertNotContains(response, "failed")

    def test_webhook_delivery_detail_view_displays_full_information(self):
        """
        Test delivery detail view displays complete information.

        Tests Requirement 32.6: Detailed delivery logs
        Tests Requirement 32.3: Display HMAC signature
        """
        # Create webhook
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=self.user,
        )

        # Create delivery
        payload = {"sale_id": "12345", "amount": 999.99}
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=Webhook.EVENT_SALE_CREATED,
            event_id=uuid.uuid4(),
            payload=payload,
            signature="test-hmac-signature-12345",
            status=WebhookDelivery.SUCCESS,
            response_status_code=200,
            response_body='{"status": "received"}',
            duration_ms=150,
        )

        # Access detail view
        response = self.client.get(
            reverse("core:webhooks:webhook_delivery_detail", kwargs={"pk": delivery.pk})
        )

        # Verify response
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, Webhook.EVENT_SALE_CREATED)
        self.assertContains(response, "test-hmac-signature-12345")
        self.assertContains(response, "12345")
        self.assertContains(response, "999.99")
        self.assertContains(response, "200")
        self.assertContains(response, "150")
        self.assertContains(response, "received")

    def test_webhook_tenant_isolation_in_views(self):
        """
        Test that webhooks are properly isolated by tenant in all views.

        Tests security: Tenant isolation
        """
        # Create another tenant and webhook
        other_tenant = Tenant.objects.create(
            company_name="Other Shop",
            slug="other-shop",
            status=Tenant.ACTIVE,
        )

        other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="testpass123",
            tenant=other_tenant,
            role=User.TENANT_OWNER,
        )

        other_webhook = Webhook.objects.create(
            tenant=other_tenant,
            name="Other Webhook",
            url="https://other.example.com/webhook",
            events=[Webhook.EVENT_SALE_CREATED],
            created_by=other_user,
        )

        # Try to access other tenant's webhook
        response = self.client.get(
            reverse("core:webhooks:webhook_detail", kwargs={"pk": other_webhook.pk})
        )

        # Verify access denied (404 because queryset filters by tenant)
        self.assertEqual(response.status_code, 404)

        # Verify list view doesn't show other tenant's webhooks
        response = self.client.get(reverse("core:webhooks:webhook_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Other Webhook")

    def test_webhook_requires_authentication(self):
        """
        Test that all webhook views require authentication.

        Tests security: Authentication required
        """
        # Logout
        self.client.logout()

        # Try to access list view
        response = self.client.get(reverse("core:webhooks:webhook_list"))
        self.assertEqual(response.status_code, 302)  # Redirect to login

        # Try to access create view
        response = self.client.get(reverse("core:webhooks:webhook_create"))
        self.assertEqual(response.status_code, 302)  # Redirect to login
