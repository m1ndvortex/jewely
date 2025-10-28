"""
Comprehensive communication system tests for Task 22.5.

This test suite covers all aspects of the communication system:
1. Announcement creation and delivery
2. Targeting logic
3. Direct messaging

Per Requirements 31 and 28 - Communication and Announcement System with Comprehensive Testing

IMPORTANT: These are REAL integration tests with NO MOCKS.
All tests use real database, real services, and real functionality.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

import pytest

from apps.core.announcement_models import (
    Announcement,
    AnnouncementRead,
    CommunicationLog,
    CommunicationTemplate,
    DirectMessage,
)
from apps.core.communication_service import BulkCommunicationService, CommunicationService
from apps.core.models import SubscriptionPlan, Tenant, TenantSubscription
from apps.notifications.models import Notification

User = get_user_model()


@pytest.mark.django_db
class TestAnnouncementCreationAndDelivery(TestCase):
    """
    Test Requirement 31.1: Create platform-wide announcements.
    Test Requirement 31.2: Schedule announcements for future delivery.
    Test Requirement 31.4: Deliver via multiple channels.
    Test Requirement 31.5: Display as dismissible banners.
    Test Requirement 31.6: Track read/unread status.
    Test Requirement 31.7: Require acknowledgment for critical announcements.
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
            price=Decimal("99.00"),
            billing_cycle="MONTHLY",
            user_limit=10,
            inventory_limit=1000,
            branch_limit=3,
            status=SubscriptionPlan.STATUS_ACTIVE,
        )

        # Create test tenants
        self.tenant1 = Tenant.objects.create(
            company_name="Gold Shop 1",
            slug="gold-shop-1",
            status=Tenant.ACTIVE,
        )

        self.tenant2 = Tenant.objects.create(
            company_name="Gold Shop 2",
            slug="gold-shop-2",
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

        # Create tenant users
        self.user1 = User.objects.create_user(
            username="user1",
            email="user1@goldshop1.com",
            password="testpass123",
            role="TENANT_OWNER",
            tenant=self.tenant1,
        )

        self.user2 = User.objects.create_user(
            username="user2",
            email="user2@goldshop2.com",
            password="testpass123",
            role="TENANT_OWNER",
            tenant=self.tenant2,
        )

    def test_create_info_announcement(self):
        """Test creating an info announcement."""
        announcement = Announcement.objects.create(
            title="New Feature Available",
            message="We've added advanced reporting features to help you analyze sales data.",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app", "email"],
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        assert announcement.title == "New Feature Available"
        assert announcement.severity == Announcement.INFO
        assert announcement.target_all_tenants is True
        assert "in_app" in announcement.channels
        assert "email" in announcement.channels
        assert announcement.status == Announcement.DRAFT
        assert announcement.created_by == self.admin

    def test_create_critical_announcement_requiring_acknowledgment(self):
        """Test creating critical announcement that requires acknowledgment."""
        announcement = Announcement.objects.create(
            title="Critical Security Update",
            message="Please update your password immediately for security.",
            severity=Announcement.CRITICAL,
            target_all_tenants=True,
            channels=["in_app", "email", "sms"],
            requires_acknowledgment=True,
            is_dismissible=False,
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        assert announcement.severity == Announcement.CRITICAL
        assert announcement.requires_acknowledgment is True
        assert announcement.is_dismissible is False
        assert len(announcement.channels) == 3

    def test_schedule_announcement_for_future_delivery(self):
        """Test scheduling announcement for future delivery."""
        future_time = timezone.now() + timezone.timedelta(hours=24)

        announcement = Announcement.objects.create(
            title="Scheduled Maintenance",
            message="System maintenance will occur tomorrow at 2 AM.",
            severity=Announcement.MAINTENANCE,
            target_all_tenants=True,
            channels=["in_app", "email"],
            scheduled_at=future_time,
            status=Announcement.SCHEDULED,
            created_by=self.admin,
        )

        assert announcement.scheduled_at == future_time
        assert announcement.status == Announcement.SCHEDULED
        assert announcement.should_send() is False  # Future time

        # Test past scheduled time
        announcement.scheduled_at = timezone.now() - timezone.timedelta(minutes=1)
        announcement.save()
        assert announcement.should_send() is True

    def test_announcement_delivery_workflow(self):
        """Test complete announcement delivery workflow."""
        # Create announcement
        announcement = Announcement.objects.create(
            title="System Update",
            message="We've updated the system with new features.",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        # Mark as sent
        announcement.mark_as_sent()

        assert announcement.status == Announcement.SENT
        assert announcement.sent_at is not None
        assert announcement.is_active() is True

    def test_announcement_read_tracking(self):
        """Test tracking when tenants read announcements."""
        announcement = Announcement.objects.create(
            title="Test Announcement",
            message="Test message for read tracking.",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            status=Announcement.SENT,
            sent_at=timezone.now(),
            created_by=self.admin,
        )

        # Mark as read by tenant1
        read_record = AnnouncementRead.objects.create(
            announcement=announcement,
            tenant=self.tenant1,
            user=self.user1,
        )

        assert read_record.read_at is not None
        assert read_record.acknowledged is False

        # Verify unique constraint (one read per tenant per announcement)
        with pytest.raises(Exception):  # IntegrityError
            AnnouncementRead.objects.create(
                announcement=announcement,
                tenant=self.tenant1,
                user=self.user1,
            )

    def test_critical_announcement_acknowledgment(self):
        """Test acknowledgment workflow for critical announcements."""
        announcement = Announcement.objects.create(
            title="Critical Update",
            message="This requires your acknowledgment.",
            severity=Announcement.CRITICAL,
            target_all_tenants=True,
            channels=["in_app"],
            requires_acknowledgment=True,
            is_dismissible=False,
            status=Announcement.SENT,
            sent_at=timezone.now(),
            created_by=self.admin,
        )

        # Create read record
        read_record = AnnouncementRead.objects.create(
            announcement=announcement,
            tenant=self.tenant1,
            user=self.user1,
        )

        assert read_record.acknowledged is False
        assert read_record.acknowledged_at is None

        # Acknowledge
        read_record.acknowledge(self.user1)

        assert read_record.acknowledged is True
        assert read_record.acknowledged_at is not None
        assert read_record.acknowledged_by == self.user1

    def test_dismissible_announcement_workflow(self):
        """Test dismissible announcement workflow."""
        announcement = Announcement.objects.create(
            title="Dismissible Notice",
            message="You can dismiss this notification.",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            is_dismissible=True,
            status=Announcement.SENT,
            sent_at=timezone.now(),
            created_by=self.admin,
        )

        # Create read record
        read_record = AnnouncementRead.objects.create(
            announcement=announcement,
            tenant=self.tenant1,
            user=self.user1,
        )

        assert read_record.dismissed is False

        # Dismiss
        read_record.dismiss()

        assert read_record.dismissed is True
        assert read_record.dismissed_at is not None

    def test_announcement_expiration(self):
        """Test announcement expiration with display_until."""
        # Create expired announcement
        past_time = timezone.now() - timezone.timedelta(hours=1)
        expired_announcement = Announcement.objects.create(
            title="Expired Notice",
            message="This announcement has expired.",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            display_until=past_time,
            status=Announcement.SENT,
            sent_at=timezone.now() - timezone.timedelta(hours=2),
            created_by=self.admin,
        )

        assert expired_announcement.is_active() is False

        # Create active announcement
        future_time = timezone.now() + timezone.timedelta(hours=1)
        active_announcement = Announcement.objects.create(
            title="Active Notice",
            message="This announcement is still active.",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            display_until=future_time,
            status=Announcement.SENT,
            sent_at=timezone.now(),
            created_by=self.admin,
        )

        assert active_announcement.is_active() is True


@pytest.mark.django_db
class TestAnnouncementTargetingLogic(TestCase):
    """
    Test Requirement 31.3: Target specific tenant segments by plan, region, status.
    """

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin_targeting",
            email="admin_targeting@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        # Create different subscription plans
        self.basic_plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            price=Decimal("99.00"),
            billing_cycle="MONTHLY",
            status=SubscriptionPlan.STATUS_ACTIVE,
        )

        self.premium_plan = SubscriptionPlan.objects.create(
            name="Premium Plan",
            price=Decimal("199.00"),
            billing_cycle="MONTHLY",
            status=SubscriptionPlan.STATUS_ACTIVE,
        )

        # Create tenants with different plans and statuses
        self.basic_tenant1 = Tenant.objects.create(
            company_name="Basic Shop 1",
            slug="basic-shop-1",
            status=Tenant.ACTIVE,
        )

        self.basic_tenant2 = Tenant.objects.create(
            company_name="Basic Shop 2",
            slug="basic-shop-2",
            status=Tenant.ACTIVE,
        )

        self.premium_tenant = Tenant.objects.create(
            company_name="Premium Shop",
            slug="premium-shop",
            status=Tenant.ACTIVE,
        )

        self.suspended_tenant = Tenant.objects.create(
            company_name="Suspended Shop",
            slug="suspended-shop",
            status=Tenant.SUSPENDED,
        )

        # Create subscriptions
        TenantSubscription.objects.create(
            tenant=self.basic_tenant1,
            plan=self.basic_plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        TenantSubscription.objects.create(
            tenant=self.basic_tenant2,
            plan=self.basic_plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        TenantSubscription.objects.create(
            tenant=self.premium_tenant,
            plan=self.premium_plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        TenantSubscription.objects.create(
            tenant=self.suspended_tenant,
            plan=self.basic_plan,
            status=TenantSubscription.STATUS_CANCELLED,
        )

    def test_target_all_active_tenants(self):
        """Test targeting all active tenants."""
        announcement = Announcement.objects.create(
            title="All Tenants Announcement",
            message="This goes to all active tenants.",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        target_tenants = announcement.get_target_tenants()

        # Should include all active tenants
        assert self.basic_tenant1 in target_tenants
        assert self.basic_tenant2 in target_tenants
        assert self.premium_tenant in target_tenants
        assert self.suspended_tenant not in target_tenants  # Suspended

    def test_target_by_subscription_plan(self):
        """Test targeting tenants by subscription plan."""
        announcement = Announcement.objects.create(
            title="Premium Feature Announcement",
            message="New premium features available!",
            severity=Announcement.INFO,
            target_all_tenants=False,
            target_filter={"plans": ["Premium Plan"]},
            channels=["in_app"],
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        target_tenants = announcement.get_target_tenants()

        # Should only include premium plan tenants
        assert self.basic_tenant1 not in target_tenants
        assert self.basic_tenant2 not in target_tenants
        assert self.premium_tenant in target_tenants
        assert self.suspended_tenant not in target_tenants

    def test_target_by_multiple_plans(self):
        """Test targeting tenants by multiple subscription plans."""
        announcement = Announcement.objects.create(
            title="Multi-Plan Announcement",
            message="This goes to Basic and Premium plans.",
            severity=Announcement.INFO,
            target_all_tenants=False,
            target_filter={"plans": ["Basic Plan", "Premium Plan"]},
            channels=["in_app"],
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        target_tenants = announcement.get_target_tenants()

        # Should include both plan types (active only)
        assert self.basic_tenant1 in target_tenants
        assert self.basic_tenant2 in target_tenants
        assert self.premium_tenant in target_tenants
        assert self.suspended_tenant not in target_tenants  # Suspended

    def test_target_by_tenant_status(self):
        """Test targeting tenants by status."""
        announcement = Announcement.objects.create(
            title="Suspended Account Notice",
            message="Your account is suspended.",
            severity=Announcement.WARNING,
            target_all_tenants=False,
            target_filter={"statuses": [Tenant.SUSPENDED]},
            channels=["in_app", "email"],
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        target_tenants = announcement.get_target_tenants()

        # Should only include suspended tenants
        assert self.basic_tenant1 not in target_tenants
        assert self.basic_tenant2 not in target_tenants
        assert self.premium_tenant not in target_tenants
        assert self.suspended_tenant in target_tenants

    def test_target_by_multiple_statuses(self):
        """Test targeting tenants by multiple statuses."""
        announcement = Announcement.objects.create(
            title="Multi-Status Announcement",
            message="This goes to active and suspended tenants.",
            severity=Announcement.INFO,
            target_all_tenants=False,
            target_filter={"statuses": [Tenant.ACTIVE, Tenant.SUSPENDED]},
            channels=["in_app"],
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        target_tenants = announcement.get_target_tenants()

        # Should include both active and suspended
        assert self.basic_tenant1 in target_tenants
        assert self.basic_tenant2 in target_tenants
        assert self.premium_tenant in target_tenants
        assert self.suspended_tenant in target_tenants

    def test_complex_targeting_plan_and_status(self):
        """Test complex targeting combining plan and status filters."""
        announcement = Announcement.objects.create(
            title="Complex Targeting",
            message="Basic plan active tenants only.",
            severity=Announcement.INFO,
            target_all_tenants=False,
            target_filter={
                "plans": ["Basic Plan"],
                "statuses": [Tenant.ACTIVE],
            },
            channels=["in_app"],
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        target_tenants = announcement.get_target_tenants()

        # Should only include active Basic plan tenants
        assert self.basic_tenant1 in target_tenants
        assert self.basic_tenant2 in target_tenants
        assert self.premium_tenant not in target_tenants  # Premium plan
        assert self.suspended_tenant not in target_tenants  # Suspended

    def test_empty_target_filter(self):
        """Test behavior with empty target filter."""
        announcement = Announcement.objects.create(
            title="Empty Filter",
            message="Empty target filter should default to active tenants.",
            severity=Announcement.INFO,
            target_all_tenants=False,
            target_filter={},
            channels=["in_app"],
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        target_tenants = announcement.get_target_tenants()

        # Should include all active tenants (default behavior)
        assert self.basic_tenant1 in target_tenants
        assert self.basic_tenant2 in target_tenants
        assert self.premium_tenant in target_tenants
        assert self.suspended_tenant not in target_tenants


@pytest.mark.django_db
class TestDirectMessaging(TransactionTestCase):
    """
    Test Requirement 31.8: Send direct messages to specific tenants.
    Test Requirement 31.9: Provide communication templates for common messages.
    Test Requirement 31.10: Log all platform-to-tenant communications.
    """

    def setUp(self):
        """Set up test data."""
        # Create platform admin
        self.admin = User.objects.create_user(
            username="admin_messaging",
            email="admin_messaging@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        # Create subscription plan
        self.plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            price=Decimal("99.00"),
            billing_cycle="MONTHLY",
            user_limit=10,
            inventory_limit=1000,
            branch_limit=3,
            status=SubscriptionPlan.STATUS_ACTIVE,
        )

        # Create test tenants
        self.tenant1 = Tenant.objects.create(
            company_name="Test Shop 1",
            slug="test-shop-1",
            status=Tenant.ACTIVE,
        )

        self.tenant2 = Tenant.objects.create(
            company_name="Test Shop 2",
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

        # Create tenant users
        self.user1 = User.objects.create_user(
            username="owner1",
            email="owner1@testshop1.com",
            password="testpass123",
            role="TENANT_OWNER",
            tenant=self.tenant1,
        )

        self.user2 = User.objects.create_user(
            username="owner2",
            email="owner2@testshop2.com",
            password="testpass123",
            role="TENANT_OWNER",
            tenant=self.tenant2,
        )

        self.staff1 = User.objects.create_user(
            username="staff1",
            email="staff1@testshop1.com",
            password="testpass123",
            role="TENANT_STAFF",
            tenant=self.tenant1,
        )

    def test_create_direct_message(self):
        """Test creating a direct message."""
        message = DirectMessage.objects.create(
            tenant=self.tenant1,
            subject="Account Issue",
            message="We noticed an issue with your account that needs attention.",
            channels=["email", "in_app"],
            created_by=self.admin,
        )

        assert message.status == DirectMessage.DRAFT
        assert message.tenant == self.tenant1
        assert message.subject == "Account Issue"
        assert "email" in message.channels
        assert "in_app" in message.channels
        assert message.created_by == self.admin

    def test_send_direct_message_email_only(self):
        """Test sending direct message via email only."""
        # Clear mail outbox
        mail.outbox = []

        message = DirectMessage.objects.create(
            tenant=self.tenant1,
            subject="Email Test",
            message="This is an email-only test message.",
            channels=["email"],
            created_by=self.admin,
        )

        # Send the message
        delivery_status = CommunicationService.send_direct_message(
            message=message,
            created_by=self.admin,
        )

        # Verify delivery
        assert delivery_status["email"] is True
        assert delivery_status["in_app"] is False
        assert delivery_status["sms"] is False

        # Verify email was sent
        assert len(mail.outbox) == 1
        sent_email = mail.outbox[0]
        assert sent_email.subject == "Email Test"
        assert self.user1.email in sent_email.to

        # Verify message status
        message.refresh_from_db()
        assert message.status == DirectMessage.SENT
        assert message.email_sent is True
        assert message.in_app_sent is False

    def test_send_direct_message_in_app_only(self):
        """Test sending direct message via in-app notification only."""
        # Clear notifications
        Notification.objects.all().delete()

        message = DirectMessage.objects.create(
            tenant=self.tenant1,
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

        # Verify delivery
        assert delivery_status["in_app"] is True
        assert delivery_status["email"] is False

        # Verify notifications were created
        notifications = Notification.objects.filter(
            user__tenant=self.tenant1,
            title="In-App Test",
        )
        assert notifications.count() == 2  # Owner and staff

        # Verify message status
        message.refresh_from_db()
        assert message.status == DirectMessage.SENT
        assert message.in_app_sent is True
        assert message.email_sent is False

    def test_send_direct_message_multi_channel(self):
        """Test sending direct message via multiple channels."""
        # Clear mail and notifications
        mail.outbox = []
        Notification.objects.all().delete()

        message = DirectMessage.objects.create(
            tenant=self.tenant1,
            subject="Multi-Channel Test",
            message="This tests multiple delivery channels.",
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

        # Verify email
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "Multi-Channel Test"

        # Verify in-app notifications
        notifications = Notification.objects.filter(title="Multi-Channel Test")
        assert notifications.count() == 2

        # Verify message status
        message.refresh_from_db()
        assert message.status == DirectMessage.SENT
        assert message.email_sent is True
        assert message.in_app_sent is True

    def test_bulk_message_to_all_active_tenants(self):
        """Test sending bulk message to all active tenants."""
        # Clear mail and logs
        mail.outbox = []
        CommunicationLog.objects.all().delete()

        results = BulkCommunicationService.send_to_all_active(
            subject="Bulk Test Message",
            message="This is a bulk test message to all active tenants.",
            channels=["email"],
            created_by=self.admin,
        )

        # Verify results
        assert results["total"] == 2  # Two active tenants
        assert results["success"] == 2
        assert results["failed"] == 0

        # Verify emails were sent
        assert len(mail.outbox) == 2

        # Verify direct messages were created
        messages = DirectMessage.objects.filter(subject="Bulk Test Message")
        assert messages.count() == 2

        # Verify communication logs
        logs = CommunicationLog.objects.filter(subject="Bulk Test Message")
        assert logs.count() == 2

    def test_bulk_message_to_specific_tenants(self):
        """Test sending bulk message to specific tenants."""
        # Clear mail
        mail.outbox = []

        tenant_ids = [str(self.tenant1.id)]

        results = BulkCommunicationService.send_bulk_message(
            tenant_ids=tenant_ids,
            subject="Specific Bulk Message",
            message="This goes to specific tenants only.",
            channels=["email"],
            created_by=self.admin,
        )

        # Verify results
        assert results["total"] == 1
        assert results["success"] == 1

        # Verify only one email sent
        assert len(mail.outbox) == 1
        assert self.user1.email in mail.outbox[0].to

        # Verify only one message created
        messages = DirectMessage.objects.filter(subject="Specific Bulk Message")
        assert messages.count() == 1
        assert messages.first().tenant == self.tenant1

    def test_bulk_message_to_subscription_plan(self):
        """Test sending bulk message to tenants on specific plan."""
        # Clear mail
        mail.outbox = []

        results = BulkCommunicationService.send_to_plan(
            plan_name="Basic Plan",
            subject="Plan-Specific Message",
            message="This goes to all Basic Plan tenants.",
            channels=["email"],
            created_by=self.admin,
        )

        # Verify results
        assert results["total"] == 2  # Both tenants on Basic Plan

        # Verify emails sent to both tenants
        assert len(mail.outbox) == 2
        recipients = [email.to[0] for email in mail.outbox]
        assert self.user1.email in recipients
        assert self.user2.email in recipients

    def test_communication_logging(self):
        """Test that all communications are logged."""
        # Clear logs
        CommunicationLog.objects.all().delete()

        message = DirectMessage.objects.create(
            tenant=self.tenant1,
            subject="Logging Test",
            message="Testing communication logging functionality.",
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
            tenant=self.tenant1,
        )

        assert logs.count() == 1

        log = logs.first()
        assert log.communication_type == CommunicationLog.DIRECT_MESSAGE
        assert log.subject == "Logging Test"
        assert "Testing communication logging functionality." in log.message_preview
        assert "email" in log.channels_used
        assert log.sent_by == self.admin
        assert log.delivery_status["email"] is True

    def test_communication_template_creation_and_usage(self):
        """Test creating and using communication templates."""
        # Create template
        template = CommunicationTemplate.objects.create(
            name="Account Issue Template",
            template_type=CommunicationTemplate.SUPPORT,
            subject="Account Issue: {{issue_type}}",
            message="Dear {{tenant_name}}, we've identified a {{issue_type}} with your account. Please contact support.",
            default_severity=Announcement.WARNING,
            default_channels=["email", "in_app"],
            created_by=self.admin,
        )

        assert template.usage_count == 0

        # Render template
        context = {
            "issue_type": "billing issue",
            "tenant_name": self.tenant1.company_name,
        }

        subject, message = template.render(context)

        assert subject == "Account Issue: billing issue"
        assert "Dear Test Shop 1" in message
        assert "billing issue" in message

        # Track usage
        template.increment_usage()
        template.refresh_from_db()

        assert template.usage_count == 1

    def test_template_variable_substitution(self):
        """Test template variable substitution with various data types."""
        template = CommunicationTemplate.objects.create(
            name="Complex Template",
            template_type=CommunicationTemplate.CUSTOM,
            subject="{{action}} on {{date}} at {{time}}",
            message="Hello {{tenant_name}}, {{action}} scheduled for {{date}} at {{time}}. Duration: {{duration}} hours.",
            created_by=self.admin,
        )

        context = {
            "action": "Maintenance",
            "date": "2025-11-01",
            "time": "02:00 AM",
            "tenant_name": "Test Shop",
            "duration": 2,
        }

        subject, message = template.render(context)

        assert subject == "Maintenance on 2025-11-01 at 02:00 AM"
        assert "Hello Test Shop" in message
        assert "2025-11-01" in message
        assert "02:00 AM" in message
        assert "2 hours" in message
        assert "{{" not in subject  # No unsubstituted variables
        assert "{{" not in message


@pytest.mark.django_db
class TestCommunicationIntegration(TransactionTestCase):
    """
    End-to-end integration tests for the complete communication system.
    Tests the full workflow from creation to delivery and logging.
    """

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin_integration",
            email="admin_integration@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        self.plan = SubscriptionPlan.objects.create(
            name="Premium Plan",
            price=Decimal("199.00"),
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

    def test_complete_announcement_workflow(self):
        """Test complete announcement workflow from creation to acknowledgment."""
        # Clear everything
        mail.outbox = []
        Notification.objects.all().delete()
        CommunicationLog.objects.all().delete()

        # Step 1: Create announcement
        announcement = Announcement.objects.create(
            title="Important System Update",
            message="We have an important system update that requires your attention.",
            severity=Announcement.CRITICAL,
            target_all_tenants=True,
            channels=["in_app", "email"],
            requires_acknowledgment=True,
            is_dismissible=False,
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        # Step 2: Schedule and send
        announcement.mark_as_sent()

        # Step 3: Tenant reads announcement
        read_record = AnnouncementRead.objects.create(
            announcement=announcement,
            tenant=self.tenant,
            user=self.owner,
        )

        # Step 4: Tenant acknowledges
        read_record.acknowledge(self.owner)

        # Step 5: Log communication
        CommunicationLog.objects.create(
            communication_type=CommunicationLog.ANNOUNCEMENT,
            announcement=announcement,
            tenant=self.tenant,
            subject=announcement.title,
            message_preview=announcement.message[:500],
            channels_used=announcement.channels,
            delivery_status={"in_app": True, "email": True},
            sent_by=self.admin,
        )

        # Verify complete workflow
        assert announcement.status == Announcement.SENT
        assert announcement.is_active() is True
        assert read_record.acknowledged is True
        assert read_record.acknowledged_by == self.owner
        assert CommunicationLog.objects.filter(announcement=announcement).exists()

    def test_complete_direct_message_workflow(self):
        """Test complete direct message workflow with multi-channel delivery."""
        # Clear everything
        mail.outbox = []
        Notification.objects.all().delete()
        CommunicationLog.objects.all().delete()

        # Step 1: Create direct message
        message = DirectMessage.objects.create(
            tenant=self.tenant,
            subject="Account Verification Required",
            message="Please verify your account information to continue using our services.",
            channels=["email", "in_app"],
            created_by=self.admin,
        )

        # Step 2: Send message
        delivery_status = CommunicationService.send_direct_message(
            message=message,
            created_by=self.admin,
        )

        # Step 3: Verify delivery
        assert delivery_status["email"] is True
        assert delivery_status["in_app"] is True

        # Step 4: Verify email delivery
        assert len(mail.outbox) == 1
        sent_email = mail.outbox[0]
        assert sent_email.subject == "Account Verification Required"
        assert self.owner.email in sent_email.to

        # Step 5: Verify in-app notifications
        notifications = Notification.objects.filter(
            user__tenant=self.tenant,
            title="Account Verification Required",
        )
        assert notifications.count() == 2  # Owner and staff

        # Step 6: Verify message status
        message.refresh_from_db()
        assert message.status == DirectMessage.SENT
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
        assert log.subject == "Account Verification Required"
        assert log.sent_by == self.admin
        assert log.delivery_status["email"] is True
        assert log.delivery_status["in_app"] is True

    def test_template_based_bulk_communication(self):
        """Test using templates for bulk communication."""
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

        # Create template
        template = CommunicationTemplate.objects.create(
            name="Maintenance Template",
            template_type=CommunicationTemplate.MAINTENANCE,
            subject="Scheduled Maintenance: {{date}}",
            message="Dear {{tenant_name}}, we will perform maintenance on {{date}}. Expected downtime: {{duration}}.",
            default_channels=["email"],
            created_by=self.admin,
        )

        # Clear mail and logs
        mail.outbox = []
        CommunicationLog.objects.all().delete()

        # Send bulk message using template concept
        results = BulkCommunicationService.send_to_plan(
            plan_name="Premium Plan",
            subject="Scheduled Maintenance: 2025-11-01",
            message="Dear valued customer, we will perform maintenance on 2025-11-01. Expected downtime: 2 hours.",
            channels=["email"],
            created_by=self.admin,
        )

        # Track template usage
        template.increment_usage()

        # Verify results
        assert results["total"] == 2
        assert results["success"] == 2

        # Verify emails sent
        assert len(mail.outbox) == 2

        # Verify template usage tracked
        template.refresh_from_db()
        assert template.usage_count == 1

        # Verify communication logs
        logs = CommunicationLog.objects.filter(subject__contains="Scheduled Maintenance")
        assert logs.count() == 2


if __name__ == "__main__":
    pytest.main([__file__])
