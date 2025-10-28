"""
Tests for direct messaging and bulk communication functionality.

Per Requirement 31 - Communication and Announcement System

IMPORTANT: These are REAL integration tests with NO MOCKS.
All tests use real database, real services, and real functionality.
"""

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

import pytest

from apps.core.announcement_models import CommunicationLog, CommunicationTemplate, DirectMessage
from apps.core.communication_service import BulkCommunicationService, CommunicationService
from apps.core.models import SubscriptionPlan, Tenant, TenantSubscription
from apps.notifications.models import Notification

User = get_user_model()


@pytest.mark.django_db
class TestDirectMessaging(TestCase):
    """
    Test direct messaging functionality.

    Requirement 31.8: Send direct messages to specific tenants.
    Requirement 31.10: Log all platform-to-tenant communications.
    """

    def setUp(self):
        """Set up test data."""
        # Create platform admin
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        # Create subscription plan
        self.plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            price=99.00,
            billing_cycle="MONTHLY",
            user_limit=10,
            inventory_limit=1000,
            branch_limit=3,
            status=SubscriptionPlan.STATUS_ACTIVE,
        )

        # Create test tenants
        self.tenant1 = Tenant.objects.create(
            company_name="Test Jewelry Shop 1",
            slug="test-shop-1",
            status=Tenant.ACTIVE,
        )

        self.tenant2 = Tenant.objects.create(
            company_name="Test Jewelry Shop 2",
            slug="test-shop-2",
            status=Tenant.ACTIVE,
        )

        # Create subscriptions
        TenantSubscription.objects.create(
            tenant=self.tenant1,
            plan=self.plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        TenantSubscription.objects.create(
            tenant=self.tenant2,
            plan=self.plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        # Create tenant owners
        self.tenant1_owner = User.objects.create_user(
            username="owner1",
            email="owner1@example.com",
            password="testpass123",
            role="TENANT_OWNER",
            tenant=self.tenant1,
        )

        self.tenant2_owner = User.objects.create_user(
            username="owner2",
            email="owner2@example.com",
            password="testpass123",
            role="TENANT_OWNER",
            tenant=self.tenant2,
        )

    def test_create_direct_message(self):
        """Test creating a direct message."""
        message = DirectMessage.objects.create(
            tenant=self.tenant1,
            subject="Test Message",
            message="This is a test message.",
            channels=["email"],
            created_by=self.admin,
        )

        assert message.status == DirectMessage.DRAFT
        assert message.tenant == self.tenant1
        assert message.subject == "Test Message"
        assert "email" in message.channels

    def test_send_direct_message(self):
        """Test sending a direct message via communication service."""
        message = DirectMessage.objects.create(
            tenant=self.tenant1,
            subject="Test Message",
            message="This is a test message.",
            channels=["email", "in_app"],
            created_by=self.admin,
        )

        # Send the message
        delivery_status = CommunicationService.send_direct_message(
            message=message,
            created_by=self.admin,
        )

        # Verify delivery status
        assert "email" in delivery_status
        assert "in_app" in delivery_status

        # Verify message status updated
        message.refresh_from_db()
        assert message.status == DirectMessage.SENT
        assert message.sent_at is not None

    def test_communication_logging(self):
        """Test that communications are logged."""
        message = DirectMessage.objects.create(
            tenant=self.tenant1,
            subject="Test Message",
            message="This is a test message.",
            channels=["email"],
            created_by=self.admin,
        )

        # Send the message
        CommunicationService.send_direct_message(
            message=message,
            created_by=self.admin,
        )

        # Verify communication log was created
        logs = CommunicationLog.objects.filter(
            direct_message=message,
            tenant=self.tenant1,
        )

        assert logs.count() == 1
        log = logs.first()
        assert log.communication_type == CommunicationLog.DIRECT_MESSAGE
        assert log.subject == "Test Message"
        assert "email" in log.channels_used

    def test_bulk_message_to_all_tenants(self):
        """Test sending bulk message to all active tenants."""
        results = BulkCommunicationService.send_to_all_active(
            subject="Bulk Test Message",
            message="This is a bulk test message.",
            channels=["email"],
            created_by=self.admin,
        )

        # Verify results
        assert results["total"] == 2  # Two active tenants
        assert results["success"] >= 0
        assert results["failed"] >= 0

        # Verify direct messages were created
        messages = DirectMessage.objects.filter(subject="Bulk Test Message")
        assert messages.count() == 2

        # Verify communication logs were created
        logs = CommunicationLog.objects.filter(subject="Bulk Test Message")
        assert logs.count() == 2

    def test_bulk_message_to_specific_tenants(self):
        """Test sending bulk message to specific tenants."""
        tenant_ids = [str(self.tenant1.id)]

        results = BulkCommunicationService.send_bulk_message(
            tenant_ids=tenant_ids,
            subject="Specific Bulk Message",
            message="This is a message to specific tenants.",
            channels=["email", "in_app"],
            created_by=self.admin,
        )

        # Verify results
        assert results["total"] == 1
        assert results["success"] >= 0

        # Verify only one message was created
        messages = DirectMessage.objects.filter(subject="Specific Bulk Message")
        assert messages.count() == 1
        assert messages.first().tenant == self.tenant1

    def test_bulk_message_to_plan(self):
        """Test sending bulk message to tenants on specific plan."""
        results = BulkCommunicationService.send_to_plan(
            plan_name="Basic Plan",
            subject="Plan-Specific Message",
            message="This is a message to all Basic Plan tenants.",
            channels=["email"],
            created_by=self.admin,
        )

        # Verify results
        assert results["total"] == 2  # Both tenants are on Basic Plan

        # Verify messages were created
        messages = DirectMessage.objects.filter(subject="Plan-Specific Message")
        assert messages.count() == 2


@pytest.mark.django_db
class TestCommunicationTemplates(TestCase):
    """
    Test communication template functionality.

    Requirement 31.9: Provide communication templates for common messages.
    """

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

    def test_create_template(self):
        """Test creating a communication template."""
        template = CommunicationTemplate.objects.create(
            name="Maintenance Notice",
            template_type=CommunicationTemplate.MAINTENANCE,
            subject="Scheduled Maintenance on {{date}}",
            message="We will be performing maintenance on {{date}} at {{time}}.",
            default_severity="WARNING",
            default_channels=["email", "in_app"],
            created_by=self.admin,
        )

        assert template.name == "Maintenance Notice"
        assert template.template_type == CommunicationTemplate.MAINTENANCE
        assert "{{date}}" in template.subject
        assert "{{time}}" in template.message

    def test_template_rendering(self):
        """Test rendering a template with context variables."""
        template = CommunicationTemplate.objects.create(
            name="Test Template",
            template_type=CommunicationTemplate.CUSTOM,
            subject="Hello {{tenant_name}}",
            message="Your account status: {{status}}",
            created_by=self.admin,
        )

        context = {
            "tenant_name": "Test Shop",
            "status": "Active",
        }

        subject, message = template.render(context)

        assert subject == "Hello Test Shop"
        assert message == "Your account status: Active"

    def test_template_usage_counter(self):
        """Test that template usage is tracked."""
        template = CommunicationTemplate.objects.create(
            name="Test Template",
            template_type=CommunicationTemplate.CUSTOM,
            subject="Test",
            message="Test message",
            created_by=self.admin,
        )

        assert template.usage_count == 0

        # Increment usage
        template.increment_usage()
        template.refresh_from_db()

        assert template.usage_count == 1

        # Increment again
        template.increment_usage()
        template.refresh_from_db()

        assert template.usage_count == 2


@pytest.mark.django_db
class TestDirectMessageViews(TestCase):
    """
    Test direct message views.

    Requirement 31.8: Send direct messages to specific tenants.
    """

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        self.plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            price=99.00,
            billing_cycle="MONTHLY",
            user_limit=10,
            inventory_limit=1000,
            branch_limit=3,
            status=SubscriptionPlan.STATUS_ACTIVE,
        )

        self.tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        self.client.force_login(self.admin)

    def test_direct_message_list_view(self):
        """Test direct message list view."""
        url = reverse("core:direct_message_list")
        response = self.client.get(url)

        assert response.status_code == 200
        assert "messages" in response.context

    def test_direct_message_create_view(self):
        """Test direct message create view."""
        url = reverse("core:direct_message_create")
        response = self.client.get(url)

        assert response.status_code == 200

    def test_bulk_message_create_view(self):
        """Test bulk message create view."""
        url = reverse("core:bulk_message_create")
        response = self.client.get(url)

        assert response.status_code == 200
        assert "tenants" in response.context
        assert "plans" in response.context
        assert "templates" in response.context


@pytest.mark.django_db
class TestRealEmailDelivery(TransactionTestCase):
    """
    Test real email delivery without mocks.

    Requirement 31.8: Send direct messages to specific tenants.
    Requirement 31.10: Log all platform-to-tenant communications.
    """

    def setUp(self):
        """Set up test data."""
        # Create platform admin
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        # Create subscription plan
        self.plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            price=99.00,
            billing_cycle="MONTHLY",
            user_limit=10,
            inventory_limit=1000,
            branch_limit=3,
            status=SubscriptionPlan.STATUS_ACTIVE,
        )

        # Create test tenant
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        # Create subscription
        TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        # Create tenant owner with email
        self.tenant_owner = User.objects.create_user(
            username="owner",
            email="owner@testshop.com",
            password="testpass123",
            role="TENANT_OWNER",
            tenant=self.tenant,
        )

    def test_real_email_sent_to_outbox(self):
        """Test that email is actually sent to Django's outbox."""
        # Clear mail outbox
        mail.outbox = []

        # Create and send direct message
        message = DirectMessage.objects.create(
            tenant=self.tenant,
            subject="Test Email Message",
            message="This is a real test email message.",
            channels=["email"],
            created_by=self.admin,
        )

        # Send the message
        delivery_status = CommunicationService.send_direct_message(
            message=message,
            created_by=self.admin,
        )

        # Verify email was sent
        assert delivery_status["email"] is True
        assert len(mail.outbox) == 1

        # Verify email content
        sent_email = mail.outbox[0]
        assert sent_email.subject == "Test Email Message"
        assert "This is a real test email message." in sent_email.body
        assert self.tenant_owner.email in sent_email.to

        # Verify message status updated
        message.refresh_from_db()
        assert message.status == DirectMessage.SENT
        assert message.email_sent is True

    def test_real_bulk_email_delivery(self):
        """Test real bulk email delivery to multiple tenants."""
        # Create additional tenants
        tenant2 = Tenant.objects.create(
            company_name="Second Shop",
            slug="second-shop",
            status=Tenant.ACTIVE,
        )

        TenantSubscription.objects.create(
            tenant=tenant2,
            plan=self.plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        owner2 = User.objects.create_user(
            username="owner2",
            email="owner2@secondshop.com",
            password="testpass123",
            role="TENANT_OWNER",
            tenant=tenant2,
        )

        # Clear mail outbox
        mail.outbox = []

        # Send bulk email
        results = BulkCommunicationService.send_to_all_active(
            subject="Bulk Email Test",
            message="This is a bulk email test.",
            channels=["email"],
            created_by=self.admin,
        )

        # Verify results
        assert results["total"] == 2
        assert results["success"] == 2
        assert results["failed"] == 0

        # Verify emails were sent
        assert len(mail.outbox) == 2

        # Verify email recipients
        recipients = [email.to[0] for email in mail.outbox]
        assert self.tenant_owner.email in recipients
        assert owner2.email in recipients

        # Verify direct messages were created
        messages = DirectMessage.objects.filter(subject="Bulk Email Test")
        assert messages.count() == 2

        # Verify all messages are sent
        for msg in messages:
            assert msg.status == DirectMessage.SENT
            assert msg.email_sent is True


@pytest.mark.django_db
class TestRealInAppNotifications(TransactionTestCase):
    """
    Test real in-app notification creation without mocks.

    Requirement 31.8: Send direct messages to specific tenants.
    """

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        self.plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            price=99.00,
            billing_cycle="MONTHLY",
            user_limit=10,
            inventory_limit=1000,
            branch_limit=3,
            status=SubscriptionPlan.STATUS_ACTIVE,
        )

        self.tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        # Create multiple tenant users
        self.user1 = User.objects.create_user(
            username="user1",
            email="user1@testshop.com",
            password="testpass123",
            role="TENANT_OWNER",
            tenant=self.tenant,
        )

        self.user2 = User.objects.create_user(
            username="user2",
            email="user2@testshop.com",
            password="testpass123",
            role="TENANT_STAFF",
            tenant=self.tenant,
        )

    def test_real_in_app_notification_creation(self):
        """Test that in-app notifications are actually created in database."""
        # Clear existing notifications
        Notification.objects.all().delete()

        # Create and send direct message with in-app channel
        message = DirectMessage.objects.create(
            tenant=self.tenant,
            subject="In-App Test",
            message="This is an in-app notification test.",
            channels=["in_app"],
            created_by=self.admin,
        )

        # Send the message
        delivery_status = CommunicationService.send_direct_message(
            message=message,
            created_by=self.admin,
        )

        # Verify in-app delivery succeeded
        assert delivery_status["in_app"] is True

        # Verify notifications were created for all tenant users
        notifications = Notification.objects.filter(
            user__tenant=self.tenant,
            title="In-App Test",
        )

        assert notifications.count() == 2  # Two tenant users

        # Verify notification content
        for notif in notifications:
            assert notif.title == "In-App Test"
            assert notif.message == "This is an in-app notification test."
            assert notif.notification_type == "SYSTEM"
            assert notif.is_read is False

        # Verify message status
        message.refresh_from_db()
        assert message.in_app_sent is True

    def test_real_multi_channel_delivery(self):
        """Test real delivery via multiple channels simultaneously."""
        # Clear mail and notifications
        mail.outbox = []
        Notification.objects.all().delete()

        # Create message with multiple channels
        message = DirectMessage.objects.create(
            tenant=self.tenant,
            subject="Multi-Channel Test",
            message="Testing multiple delivery channels.",
            channels=["email", "in_app"],
            created_by=self.admin,
        )

        # Send the message
        delivery_status = CommunicationService.send_direct_message(
            message=message,
            created_by=self.admin,
        )

        # Verify both channels succeeded
        assert delivery_status["email"] is True
        assert delivery_status["in_app"] is True

        # Verify email was sent
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "Multi-Channel Test"

        # Verify in-app notifications were created
        notifications = Notification.objects.filter(title="Multi-Channel Test")
        assert notifications.count() == 2  # Two tenant users

        # Verify message status
        message.refresh_from_db()
        assert message.email_sent is True
        assert message.in_app_sent is True


@pytest.mark.django_db
class TestRealCommunicationLogging(TransactionTestCase):
    """
    Test real communication logging without mocks.

    Requirement 31.10: Log all platform-to-tenant communications.
    """

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        self.plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            price=99.00,
            billing_cycle="MONTHLY",
            user_limit=10,
            inventory_limit=1000,
            branch_limit=3,
            status=SubscriptionPlan.STATUS_ACTIVE,
        )

        self.tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        self.tenant_owner = User.objects.create_user(
            username="owner",
            email="owner@testshop.com",
            password="testpass123",
            role="TENANT_OWNER",
            tenant=self.tenant,
        )

    def test_real_communication_log_creation(self):
        """Test that communication logs are actually created in database."""
        # Clear existing logs
        CommunicationLog.objects.all().delete()

        # Create and send message
        message = DirectMessage.objects.create(
            tenant=self.tenant,
            subject="Logging Test",
            message="Testing communication logging.",
            channels=["email"],
            created_by=self.admin,
        )

        # Send the message
        CommunicationService.send_direct_message(
            message=message,
            created_by=self.admin,
        )

        # Verify log was created
        logs = CommunicationLog.objects.filter(
            direct_message=message,
            tenant=self.tenant,
        )

        assert logs.count() == 1

        # Verify log content
        log = logs.first()
        assert log.communication_type == CommunicationLog.DIRECT_MESSAGE
        assert log.subject == "Logging Test"
        assert "Testing communication logging." in log.message_preview
        assert "email" in log.channels_used
        assert log.sent_by == self.admin

        # Verify delivery status is logged
        assert "email" in log.delivery_status
        assert log.delivery_status["email"] is True

    def test_real_bulk_communication_logging(self):
        """Test that bulk communications are logged for each tenant."""
        # Create additional tenant
        tenant2 = Tenant.objects.create(
            company_name="Second Shop",
            slug="second-shop",
            status=Tenant.ACTIVE,
        )

        TenantSubscription.objects.create(
            tenant=tenant2,
            plan=self.plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        User.objects.create_user(
            username="owner2",
            email="owner2@secondshop.com",
            password="testpass123",
            role="TENANT_OWNER",
            tenant=tenant2,
        )

        # Clear existing logs
        CommunicationLog.objects.all().delete()

        # Send bulk message
        BulkCommunicationService.send_to_all_active(
            subject="Bulk Logging Test",
            message="Testing bulk communication logging.",
            channels=["email"],
            created_by=self.admin,
        )

        # Verify logs were created for each tenant
        logs = CommunicationLog.objects.filter(subject="Bulk Logging Test")
        assert logs.count() == 2

        # Verify each tenant has a log
        tenant_ids = [log.tenant.id for log in logs]
        assert self.tenant.id in tenant_ids
        assert tenant2.id in tenant_ids

        # Verify all logs have correct data
        for log in logs:
            assert log.communication_type == CommunicationLog.DIRECT_MESSAGE
            assert "email" in log.channels_used
            assert log.sent_by == self.admin


@pytest.mark.django_db
class TestRealTemplateRendering(TestCase):
    """
    Test real template rendering without mocks.

    Requirement 31.9: Provide communication templates for common messages.
    """

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

    def test_real_template_variable_substitution(self):
        """Test that template variables are actually substituted."""
        template = CommunicationTemplate.objects.create(
            name="Test Template",
            template_type=CommunicationTemplate.MAINTENANCE,
            subject="Maintenance on {{date}} at {{time}}",
            message="Dear {{tenant_name}}, we will perform maintenance on {{date}} at {{time}}. Expected duration: {{duration}}.",
            created_by=self.admin,
        )

        # Render with real context
        context = {
            "date": "2025-10-30",
            "time": "02:00 AM",
            "tenant_name": "Test Shop",
            "duration": "2 hours",
        }

        subject, message = template.render(context)

        # Verify substitution actually happened
        assert subject == "Maintenance on 2025-10-30 at 02:00 AM"
        assert "Dear Test Shop" in message
        assert "2025-10-30" in message
        assert "02:00 AM" in message
        assert "2 hours" in message
        assert "{{" not in subject  # No unsubstituted variables
        assert "{{" not in message

    def test_real_template_usage_tracking(self):
        """Test that template usage is actually tracked in database."""
        template = CommunicationTemplate.objects.create(
            name="Usage Test Template",
            template_type=CommunicationTemplate.CUSTOM,
            subject="Test",
            message="Test message",
            created_by=self.admin,
        )

        # Verify initial usage count
        assert template.usage_count == 0

        # Increment usage multiple times
        template.increment_usage()
        template.refresh_from_db()
        assert template.usage_count == 1

        template.increment_usage()
        template.refresh_from_db()
        assert template.usage_count == 2

        template.increment_usage()
        template.refresh_from_db()
        assert template.usage_count == 3


@pytest.mark.django_db
class TestRealEndToEndFlow(TransactionTestCase):
    """
    Test complete end-to-end flow without mocks.

    Tests the entire flow from message creation to delivery and logging.
    """

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        self.plan = SubscriptionPlan.objects.create(
            name="Premium Plan",
            price=199.00,
            billing_cycle="MONTHLY",
            user_limit=20,
            inventory_limit=5000,
            branch_limit=10,
            status=SubscriptionPlan.STATUS_ACTIVE,
        )

        self.tenant = Tenant.objects.create(
            company_name="Premium Jewelry",
            slug="premium-jewelry",
            status=Tenant.ACTIVE,
        )

        TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        self.owner = User.objects.create_user(
            username="premium_owner",
            email="owner@premiumjewelry.com",
            password="testpass123",
            role="TENANT_OWNER",
            tenant=self.tenant,
        )

        self.staff = User.objects.create_user(
            username="premium_staff",
            email="staff@premiumjewelry.com",
            password="testpass123",
            role="TENANT_STAFF",
            tenant=self.tenant,
        )

    def test_complete_direct_message_flow(self):
        """Test complete flow: create -> send -> verify delivery -> verify logging."""
        # Clear everything
        mail.outbox = []
        Notification.objects.all().delete()
        CommunicationLog.objects.all().delete()

        # Step 1: Create direct message
        message = DirectMessage.objects.create(
            tenant=self.tenant,
            subject="Important Update",
            message="We have an important update for your account.",
            channels=["email", "in_app"],
            created_by=self.admin,
        )

        # Verify initial state
        assert message.status == DirectMessage.DRAFT
        assert message.email_sent is False
        assert message.in_app_sent is False

        # Step 2: Send message
        delivery_status = CommunicationService.send_direct_message(
            message=message,
            created_by=self.admin,
        )

        # Step 3: Verify delivery status
        assert delivery_status["email"] is True
        assert delivery_status["in_app"] is True

        # Step 4: Verify email delivery
        assert len(mail.outbox) == 1
        sent_email = mail.outbox[0]
        assert sent_email.subject == "Important Update"
        assert self.owner.email in sent_email.to

        # Step 5: Verify in-app notifications
        notifications = Notification.objects.filter(
            user__tenant=self.tenant,
            title="Important Update",
        )
        assert notifications.count() == 2  # Owner and staff

        # Step 6: Verify message status updated
        message.refresh_from_db()
        assert message.status == DirectMessage.SENT
        assert message.sent_at is not None
        assert message.email_sent is True
        assert message.in_app_sent is True

        # Step 7: Verify communication log
        logs = CommunicationLog.objects.filter(
            direct_message=message,
            tenant=self.tenant,
        )
        assert logs.count() == 1

        log = logs.first()
        assert log.communication_type == CommunicationLog.DIRECT_MESSAGE
        assert log.subject == "Important Update"
        assert log.sent_by == self.admin
        assert "email" in log.channels_used
        assert "in_app" in log.channels_used
        assert log.delivery_status["email"] is True
        assert log.delivery_status["in_app"] is True

    def test_complete_bulk_message_flow_by_plan(self):
        """Test complete bulk messaging flow targeting specific plan."""
        # Create another tenant on different plan
        basic_plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            price=99.00,
            billing_cycle="MONTHLY",
            user_limit=10,
            inventory_limit=1000,
            branch_limit=3,
            status=SubscriptionPlan.STATUS_ACTIVE,
        )

        basic_tenant = Tenant.objects.create(
            company_name="Basic Shop",
            slug="basic-shop",
            status=Tenant.ACTIVE,
        )

        TenantSubscription.objects.create(
            tenant=basic_tenant,
            plan=basic_plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        User.objects.create_user(
            username="basic_owner",
            email="owner@basicshop.com",
            password="testpass123",
            role="TENANT_OWNER",
            tenant=basic_tenant,
        )

        # Clear everything
        mail.outbox = []
        CommunicationLog.objects.all().delete()

        # Send bulk message to Premium Plan only
        results = BulkCommunicationService.send_to_plan(
            plan_name="Premium Plan",
            subject="Premium Feature Announcement",
            message="New premium features are now available!",
            channels=["email"],
            created_by=self.admin,
        )

        # Verify only Premium tenant received message
        assert results["total"] == 1
        assert results["success"] == 1

        # Verify email sent only to Premium tenant
        assert len(mail.outbox) == 1
        assert self.owner.email in mail.outbox[0].to

        # Verify direct message created only for Premium tenant
        messages = DirectMessage.objects.filter(subject="Premium Feature Announcement")
        assert messages.count() == 1
        assert messages.first().tenant == self.tenant

        # Verify communication log
        logs = CommunicationLog.objects.filter(subject="Premium Feature Announcement")
        assert logs.count() == 1
        assert logs.first().tenant == self.tenant
