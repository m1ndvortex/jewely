"""
Comprehensive integration tests for announcement and communication system.
Per Requirement 31 - Communication and Announcement System

Tests all 10 acceptance criteria:
1. Create platform-wide announcements
2. Schedule announcements for future delivery
3. Target specific tenant segments
4. Deliver via multiple channels
5. Display as dismissible banners
6. Track read/unread status
7. Require acknowledgment for critical announcements
8. Send direct messages to specific tenants
9. Provide communication templates
10. Log all communications

NO MOCKS - All tests use real database and services.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

import pytest

from apps.core.announcement_models import (
    Announcement,
    AnnouncementRead,
    CommunicationLog,
    CommunicationTemplate,
    DirectMessage,
)
from apps.core.models import SubscriptionPlan, Tenant, TenantSubscription

User = get_user_model()


@pytest.mark.django_db
class AnnouncementCreationTestCase(TestCase):
    """
    Test Requirement 31.1: Create platform-wide announcements.
    """

    def setUp(self):
        """Set up test data."""
        # Create platform admin
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            role="PLATFORM_ADMIN",
        )

    def test_create_maintenance_announcement(self):
        """Test creating a maintenance announcement."""
        announcement = Announcement.objects.create(
            title="Scheduled Maintenance",
            message="We will be performing system maintenance on Nov 1, 2025.",
            severity=Announcement.MAINTENANCE,
            target_all_tenants=True,
            channels=["in_app", "email"],
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        assert announcement.title == "Scheduled Maintenance"
        assert announcement.severity == Announcement.MAINTENANCE
        assert announcement.target_all_tenants is True
        assert "in_app" in announcement.channels
        assert "email" in announcement.channels
        assert announcement.created_by == self.admin

    def test_create_new_feature_announcement(self):
        """Test creating a new feature announcement."""
        announcement = Announcement.objects.create(
            title="New Feature: Advanced Reporting",
            message="We're excited to announce advanced reporting features!",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app", "email", "sms"],
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        assert announcement.title == "New Feature: Advanced Reporting"
        assert announcement.severity == Announcement.INFO
        assert len(announcement.channels) == 3

    def test_create_critical_announcement(self):
        """Test creating a critical announcement requiring acknowledgment."""
        announcement = Announcement.objects.create(
            title="Critical Security Update",
            message="Please update your password immediately.",
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


@pytest.mark.django_db
class AnnouncementSchedulingTestCase(TestCase):
    """
    Test Requirement 31.2: Schedule announcements for future delivery.
    """

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            role="PLATFORM_ADMIN",
        )

    def test_schedule_future_announcement(self):
        """Test scheduling an announcement for future delivery."""
        future_time = timezone.now() + timezone.timedelta(days=7)

        announcement = Announcement.objects.create(
            title="Upcoming Feature Release",
            message="New features coming next week!",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app", "email"],
            scheduled_at=future_time,
            status=Announcement.SCHEDULED,
            created_by=self.admin,
        )

        assert announcement.scheduled_at == future_time
        assert announcement.status == Announcement.SCHEDULED
        assert announcement.sent_at is None

    def test_should_send_scheduled_announcement(self):
        """Test should_send method for scheduled announcements."""
        # Past scheduled time - should send
        past_time = timezone.now() - timezone.timedelta(hours=1)
        announcement_past = Announcement.objects.create(
            title="Past Announcement",
            message="This should be sent.",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            scheduled_at=past_time,
            status=Announcement.SCHEDULED,
            created_by=self.admin,
        )

        assert announcement_past.should_send() is True

        # Future scheduled time - should not send
        future_time = timezone.now() + timezone.timedelta(hours=1)
        announcement_future = Announcement.objects.create(
            title="Future Announcement",
            message="This should not be sent yet.",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            scheduled_at=future_time,
            status=Announcement.SCHEDULED,
            created_by=self.admin,
        )

        assert announcement_future.should_send() is False

    def test_mark_announcement_as_sent(self):
        """Test marking announcement as sent."""
        announcement = Announcement.objects.create(
            title="Test Announcement",
            message="Test message",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            status=Announcement.SCHEDULED,
            created_by=self.admin,
        )

        assert announcement.sent_at is None
        assert announcement.status == Announcement.SCHEDULED

        announcement.mark_as_sent()

        assert announcement.sent_at is not None
        assert announcement.status == Announcement.SENT

    def test_cancel_scheduled_announcement(self):
        """Test canceling a scheduled announcement."""
        future_time = timezone.now() + timezone.timedelta(days=1)
        announcement = Announcement.objects.create(
            title="Cancelable Announcement",
            message="This will be canceled.",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            scheduled_at=future_time,
            status=Announcement.SCHEDULED,
            created_by=self.admin,
        )

        announcement.cancel()

        assert announcement.status == Announcement.CANCELLED


@pytest.mark.django_db
class TenantTargetingTestCase(TestCase):
    """
    Test Requirement 31.3: Target specific tenant segments.
    """

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            role="PLATFORM_ADMIN",
        )

        # Create subscription plans
        self.basic_plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            price=Decimal("29.99"),
            billing_cycle="MONTHLY",
        )

        self.premium_plan = SubscriptionPlan.objects.create(
            name="Premium Plan",
            price=Decimal("99.99"),
            billing_cycle="MONTHLY",
        )
        # Create tenants with different plans
        self.tenant1 = Tenant.objects.create(
            company_name="Gold Shop 1",
            slug="gold-shop-1",
            status=Tenant.ACTIVE,
        )
        TenantSubscription.objects.create(
            tenant=self.tenant1,
            plan=self.basic_plan,
            status="active",
        )

        self.tenant2 = Tenant.objects.create(
            company_name="Gold Shop 2",
            slug="gold-shop-2",
            status=Tenant.ACTIVE,
        )
        TenantSubscription.objects.create(
            tenant=self.tenant2,
            plan=self.premium_plan,
            status="active",
        )

        self.tenant3 = Tenant.objects.create(
            company_name="Gold Shop 3",
            slug="gold-shop-3",
            status=Tenant.SUSPENDED,
        )

    def test_target_all_tenants(self):
        """Test targeting all active tenants."""
        announcement = Announcement.objects.create(
            title="All Tenants Announcement",
            message="This goes to everyone.",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        target_tenants = announcement.get_target_tenants()

        # Should include active tenants only
        assert self.tenant1 in target_tenants
        assert self.tenant2 in target_tenants
        assert self.tenant3 not in target_tenants  # Suspended

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
        assert self.tenant1 not in target_tenants  # Basic plan
        assert self.tenant2 in target_tenants  # Premium plan

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
        assert self.tenant1 not in target_tenants
        assert self.tenant2 not in target_tenants
        assert self.tenant3 in target_tenants


@pytest.mark.django_db
class MultiChannelDeliveryTestCase(TestCase):
    """
    Test Requirement 31.4: Deliver via multiple channels.
    """

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            role="PLATFORM_ADMIN",
        )

    def test_in_app_channel(self):
        """Test in-app channel configuration."""
        announcement = Announcement.objects.create(
            title="In-App Announcement",
            message="This appears in the app.",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        assert "in_app" in announcement.channels
        assert len(announcement.channels) == 1

    def test_email_channel(self):
        """Test email channel configuration."""
        announcement = Announcement.objects.create(
            title="Email Announcement",
            message="This is sent via email.",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["email"],
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        assert "email" in announcement.channels

    def test_sms_channel(self):
        """Test SMS channel configuration."""
        announcement = Announcement.objects.create(
            title="SMS Announcement",
            message="This is sent via SMS.",
            severity=Announcement.CRITICAL,
            target_all_tenants=True,
            channels=["sms"],
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        assert "sms" in announcement.channels

    def test_all_channels(self):
        """Test using all delivery channels."""
        announcement = Announcement.objects.create(
            title="Multi-Channel Announcement",
            message="This goes everywhere!",
            severity=Announcement.WARNING,
            target_all_tenants=True,
            channels=["in_app", "email", "sms"],
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        assert "in_app" in announcement.channels
        assert "email" in announcement.channels
        assert "sms" in announcement.channels
        assert len(announcement.channels) == 3


@pytest.mark.django_db
class DismissibleBannerTestCase(TestCase):
    """
    Test Requirement 31.5: Display as dismissible banners.
    """

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            role="PLATFORM_ADMIN",
        )

        self.tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

    def test_dismissible_banner(self):
        """Test creating a dismissible banner."""
        announcement = Announcement.objects.create(
            title="Dismissible Notice",
            message="You can dismiss this.",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            is_dismissible=True,
            status=Announcement.SENT,
            sent_at=timezone.now(),
            created_by=self.admin,
        )

        assert announcement.is_dismissible is True

    def test_non_dismissible_banner(self):
        """Test creating a non-dismissible banner."""
        announcement = Announcement.objects.create(
            title="Critical Notice",
            message="You cannot dismiss this.",
            severity=Announcement.CRITICAL,
            target_all_tenants=True,
            channels=["in_app"],
            is_dismissible=False,
            requires_acknowledgment=True,
            status=Announcement.SENT,
            sent_at=timezone.now(),
            created_by=self.admin,
        )

        assert announcement.is_dismissible is False
        assert announcement.requires_acknowledgment is True

    def test_banner_with_display_until(self):
        """Test banner with expiration time."""
        future_time = timezone.now() + timezone.timedelta(days=7)

        announcement = Announcement.objects.create(
            title="Time-Limited Notice",
            message="This expires in 7 days.",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            display_until=future_time,
            status=Announcement.SENT,
            sent_at=timezone.now(),
            created_by=self.admin,
        )

        assert announcement.display_until == future_time
        assert announcement.is_active() is True

    def test_expired_banner(self):
        """Test that expired banners are not active."""
        past_time = timezone.now() - timezone.timedelta(days=1)

        announcement = Announcement.objects.create(
            title="Expired Notice",
            message="This has expired.",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            display_until=past_time,
            status=Announcement.SENT,
            sent_at=timezone.now() - timezone.timedelta(days=2),
            created_by=self.admin,
        )

        assert announcement.is_active() is False


@pytest.mark.django_db
class ReadTrackingTestCase(TestCase):
    """
    Test Requirement 31.6: Track read/unread status.
    """

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            role="PLATFORM_ADMIN",
        )
        self.tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        self.user = User.objects.create_user(
            username="tenant_user",
            email="user@testshop.com",
            password="userpass123",
            tenant=self.tenant,
            role="TENANT_OWNER",
        )

        self.announcement = Announcement.objects.create(
            title="Test Announcement",
            message="Test message",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            status=Announcement.SENT,
            sent_at=timezone.now(),
            created_by=self.admin,
        )

    def test_track_announcement_read(self):
        """Test tracking when a tenant reads an announcement."""
        read_record = AnnouncementRead.objects.create(
            announcement=self.announcement,
            tenant=self.tenant,
            user=self.user,
        )

        assert read_record.announcement == self.announcement
        assert read_record.tenant == self.tenant
        assert read_record.user == self.user
        assert read_record.read_at is not None
        assert read_record.acknowledged is False

    def test_unique_read_per_tenant(self):
        """Test that each tenant can only have one read record per announcement."""
        AnnouncementRead.objects.create(
            announcement=self.announcement,
            tenant=self.tenant,
            user=self.user,
        )

        # Attempting to create duplicate should raise error
        with pytest.raises(Exception):  # IntegrityError
            AnnouncementRead.objects.create(
                announcement=self.announcement,
                tenant=self.tenant,
                user=self.user,
            )

    def test_check_unread_announcements(self):
        """Test checking for unread announcements."""
        # Create another announcement (unread)
        Announcement.objects.create(
            title="Unread Announcement",
            message="This is unread",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            status=Announcement.SENT,
            sent_at=timezone.now(),
            created_by=self.admin,
        )

        # Mark first announcement as read
        AnnouncementRead.objects.create(
            announcement=self.announcement,
            tenant=self.tenant,
            user=self.user,
        )

        # Check read status
        read_announcements = AnnouncementRead.objects.filter(tenant=self.tenant)
        assert read_announcements.count() == 1
        assert read_announcements.first().announcement == self.announcement


@pytest.mark.django_db
class AcknowledgmentTestCase(TestCase):
    """
    Test Requirement 31.7: Require acknowledgment for critical announcements.
    """

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            role="PLATFORM_ADMIN",
        )

        self.tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        self.user = User.objects.create_user(
            username="tenant_user",
            email="user@testshop.com",
            password="userpass123",
            tenant=self.tenant,
            role="TENANT_OWNER",
        )

        self.critical_announcement = Announcement.objects.create(
            title="Critical Security Update",
            message="Action required immediately.",
            severity=Announcement.CRITICAL,
            target_all_tenants=True,
            channels=["in_app", "email"],
            requires_acknowledgment=True,
            is_dismissible=False,
            status=Announcement.SENT,
            sent_at=timezone.now(),
            created_by=self.admin,
        )

    def test_acknowledgment_required(self):
        """Test that critical announcements require acknowledgment."""
        assert self.critical_announcement.requires_acknowledgment is True
        assert self.critical_announcement.is_dismissible is False

    def test_acknowledge_announcement(self):
        """Test acknowledging a critical announcement."""
        read_record = AnnouncementRead.objects.create(
            announcement=self.critical_announcement,
            tenant=self.tenant,
            user=self.user,
        )

        assert read_record.acknowledged is False
        assert read_record.acknowledged_at is None

        # Acknowledge the announcement
        read_record.acknowledge(self.user)

        assert read_record.acknowledged is True
        assert read_record.acknowledged_at is not None
        assert read_record.acknowledged_by == self.user

    def test_find_unacknowledged_critical_announcements(self):
        """Test finding unacknowledged critical announcements."""
        # Create read record without acknowledgment
        read_record = AnnouncementRead.objects.create(
            announcement=self.critical_announcement,
            tenant=self.tenant,
            user=self.user,
        )

        # Find unacknowledged
        unacknowledged = AnnouncementRead.objects.filter(
            tenant=self.tenant, acknowledged=False, announcement__requires_acknowledgment=True
        )

        assert unacknowledged.count() == 1
        assert unacknowledged.first() == read_record


@pytest.mark.django_db
class DirectMessageTestCase(TestCase):
    """
    Test Requirement 31.8: Send direct messages to specific tenants.
    """

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            role="PLATFORM_ADMIN",
        )

        self.tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

    def test_create_direct_message(self):
        """Test creating a direct message to a specific tenant."""
        message = DirectMessage.objects.create(
            tenant=self.tenant,
            subject="Account Issue",
            message="We noticed an issue with your account.",
            channels=["email", "in_app"],
            status=DirectMessage.DRAFT,
            created_by=self.admin,
        )

        assert message.tenant == self.tenant
        assert message.subject == "Account Issue"
        assert "email" in message.channels
        assert "in_app" in message.channels
        assert message.created_by == self.admin

    def test_mark_direct_message_as_sent(self):
        """Test marking a direct message as sent."""
        message = DirectMessage.objects.create(
            tenant=self.tenant,
            subject="Test Message",
            message="Test content",
            channels=["email"],
            status=DirectMessage.DRAFT,
            created_by=self.admin,
        )

        assert message.sent_at is None
        assert message.status == DirectMessage.DRAFT

        message.mark_as_sent()

        assert message.sent_at is not None
        assert message.status == DirectMessage.SENT

    def test_track_message_read_status(self):
        """Test tracking when a message is read."""
        message = DirectMessage.objects.create(
            tenant=self.tenant,
            subject="Test Message",
            message="Test content",
            channels=["in_app"],
            status=DirectMessage.SENT,
            created_by=self.admin,
        )

        assert message.read_at is None

        message.mark_as_read()

        assert message.read_at is not None

    def test_track_delivery_channels(self):
        """Test tracking delivery status for each channel."""
        message = DirectMessage.objects.create(
            tenant=self.tenant,
            subject="Multi-Channel Message",
            message="Test content",
            channels=["email", "sms", "in_app"],
            status=DirectMessage.SENT,
            created_by=self.admin,
        )

        # Initially all false
        assert message.email_sent is False
        assert message.sms_sent is False
        assert message.in_app_sent is False

        # Simulate delivery
        message.email_sent = True
        message.in_app_sent = True
        message.save()

        assert message.email_sent is True
        assert message.sms_sent is False
        assert message.in_app_sent is True


@pytest.mark.django_db
class CommunicationTemplateTestCase(TestCase):
    """
    Test Requirement 31.9: Provide communication templates.
    """

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            role="PLATFORM_ADMIN",
        )

    def test_create_maintenance_template(self):
        """Test creating a maintenance notice template."""
        template = CommunicationTemplate.objects.create(
            name="Maintenance Notice",
            template_type=CommunicationTemplate.MAINTENANCE,
            subject="Scheduled Maintenance: {{date}}",
            message="Dear {{tenant_name}}, we will perform maintenance on {{date}} at {{time}}.",
            default_severity=Announcement.MAINTENANCE,
            default_channels=["in_app", "email"],
            created_by=self.admin,
        )

        assert template.name == "Maintenance Notice"
        assert template.template_type == CommunicationTemplate.MAINTENANCE
        assert "{{date}}" in template.subject
        assert "{{tenant_name}}" in template.message

    def test_render_template_with_variables(self):
        """Test rendering a template with variable substitution."""
        template = CommunicationTemplate.objects.create(
            name="Welcome Message",
            template_type=CommunicationTemplate.CUSTOM,
            subject="Welcome to {{platform_name}}!",
            message="Hello {{tenant_name}}, welcome to {{platform_name}}. Your account is ready!",
            default_severity=Announcement.INFO,
            default_channels=["email"],
            created_by=self.admin,
        )

        context = {"platform_name": "Jewelry SaaS", "tenant_name": "Gold Shop"}

        subject, message = template.render(context)

        assert subject == "Welcome to Jewelry SaaS!"
        assert "Hello Gold Shop" in message
        assert "welcome to Jewelry SaaS" in message

    def test_template_usage_tracking(self):
        """Test tracking template usage count."""
        template = CommunicationTemplate.objects.create(
            name="Test Template",
            template_type=CommunicationTemplate.CUSTOM,
            subject="Test",
            message="Test message",
            default_severity=Announcement.INFO,
            default_channels=["in_app"],
            created_by=self.admin,
        )

        assert template.usage_count == 0

        template.increment_usage()
        assert template.usage_count == 1

        template.increment_usage()
        assert template.usage_count == 2

    def test_template_types(self):
        """Test all template types."""
        template_types = [
            CommunicationTemplate.MAINTENANCE,
            CommunicationTemplate.NEW_FEATURE,
            CommunicationTemplate.POLICY_CHANGE,
            CommunicationTemplate.BILLING,
            CommunicationTemplate.SUPPORT,
            CommunicationTemplate.CUSTOM,
        ]

        for template_type in template_types:
            template = CommunicationTemplate.objects.create(
                name=f"Template {template_type}",
                template_type=template_type,
                subject="Test Subject",
                message="Test Message",
                default_severity=Announcement.INFO,
                default_channels=["in_app"],
                created_by=self.admin,
            )
            assert template.template_type == template_type


@pytest.mark.django_db
class CommunicationLogTestCase(TestCase):
    """
    Test Requirement 31.10: Log all communications.
    """

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            role="PLATFORM_ADMIN",
        )

        self.tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        self.announcement = Announcement.objects.create(
            title="Test Announcement",
            message="Test message",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app", "email"],
            status=Announcement.SENT,
            sent_at=timezone.now(),
            created_by=self.admin,
        )

    def test_log_announcement_communication(self):
        """Test logging an announcement communication."""
        log = CommunicationLog.objects.create(
            communication_type=CommunicationLog.ANNOUNCEMENT,
            announcement=self.announcement,
            tenant=self.tenant,
            subject=self.announcement.title,
            message_preview=self.announcement.message[:100],
            channels_used=["in_app", "email"],
            delivery_status={"in_app": "sent", "email": "sent"},
            sent_by=self.admin,
        )

        assert log.communication_type == CommunicationLog.ANNOUNCEMENT
        assert log.announcement == self.announcement
        assert log.tenant == self.tenant
        assert log.sent_by == self.admin
        assert "in_app" in log.channels_used
        assert "email" in log.channels_used

    def test_log_direct_message_communication(self):
        """Test logging a direct message communication."""
        direct_message = DirectMessage.objects.create(
            tenant=self.tenant,
            subject="Direct Message",
            message="This is a direct message.",
            channels=["email"],
            status=DirectMessage.SENT,
            created_by=self.admin,
        )

        log = CommunicationLog.objects.create(
            communication_type=CommunicationLog.DIRECT_MESSAGE,
            direct_message=direct_message,
            tenant=self.tenant,
            subject=direct_message.subject,
            message_preview=direct_message.message[:100],
            channels_used=["email"],
            delivery_status={"email": "sent"},
            sent_by=self.admin,
        )

        assert log.communication_type == CommunicationLog.DIRECT_MESSAGE
        assert log.direct_message == direct_message
        assert log.tenant == self.tenant

    def test_query_tenant_communication_history(self):
        """Test querying all communications for a tenant."""
        # Create multiple communications
        for i in range(3):
            CommunicationLog.objects.create(
                communication_type=CommunicationLog.ANNOUNCEMENT,
                announcement=self.announcement,
                tenant=self.tenant,
                subject=f"Announcement {i}",
                message_preview=f"Message {i}",
                channels_used=["in_app"],
                delivery_status={"in_app": "sent"},
                sent_by=self.admin,
            )

        logs = CommunicationLog.objects.filter(tenant=self.tenant)
        assert logs.count() == 3

    def test_communication_log_ordering(self):
        """Test that communication logs are ordered by sent_at descending."""
        # Create logs with slight time differences
        import time

        log1 = CommunicationLog.objects.create(
            communication_type=CommunicationLog.ANNOUNCEMENT,
            tenant=self.tenant,
            subject="First",
            message_preview="First message",
            channels_used=["in_app"],
            delivery_status={},
            sent_by=self.admin,
        )

        time.sleep(0.01)

        log2 = CommunicationLog.objects.create(
            communication_type=CommunicationLog.ANNOUNCEMENT,
            tenant=self.tenant,
            subject="Second",
            message_preview="Second message",
            channels_used=["in_app"],
            delivery_status={},
            sent_by=self.admin,
        )

        logs = CommunicationLog.objects.filter(tenant=self.tenant)
        assert logs.first() == log2  # Most recent first
        assert logs.last() == log1


@pytest.mark.django_db
class AnnouncementIntegrationTestCase(TestCase):
    """
    Comprehensive integration test covering complete announcement workflow.
    """

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            role="PLATFORM_ADMIN",
        )

        # Create multiple tenants
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

        self.user1 = User.objects.create_user(
            username="user1",
            email="user1@goldshop1.com",
            password="pass123",
            tenant=self.tenant1,
            role="TENANT_OWNER",
        )

        self.user2 = User.objects.create_user(
            username="user2",
            email="user2@goldshop2.com",
            password="pass123",
            tenant=self.tenant2,
            role="TENANT_OWNER",
        )

    def test_complete_announcement_workflow(self):
        """Test complete workflow from creation to acknowledgment."""
        # Step 1: Admin creates announcement
        announcement = Announcement.objects.create(
            title="System Upgrade",
            message="We will upgrade the system on Nov 1, 2025.",
            severity=Announcement.MAINTENANCE,
            target_all_tenants=True,
            channels=["in_app", "email"],
            requires_acknowledgment=True,
            is_dismissible=False,
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        assert announcement.status == Announcement.DRAFT

        # Step 2: Schedule announcement
        future_time = timezone.now() + timezone.timedelta(hours=1)
        announcement.scheduled_at = future_time
        announcement.status = Announcement.SCHEDULED
        announcement.save()

        assert announcement.should_send() is False

        # Step 3: Time passes, announcement should be sent
        announcement.scheduled_at = timezone.now() - timezone.timedelta(minutes=1)
        announcement.save()

        assert announcement.should_send() is True

        # Step 4: Mark as sent
        announcement.mark_as_sent()

        assert announcement.status == Announcement.SENT
        assert announcement.sent_at is not None
        assert announcement.is_active() is True

        # Step 5: Tenants read the announcement
        read1 = AnnouncementRead.objects.create(
            announcement=announcement,
            tenant=self.tenant1,
            user=self.user1,
        )

        read2 = AnnouncementRead.objects.create(
            announcement=announcement,
            tenant=self.tenant2,
            user=self.user2,
        )

        assert AnnouncementRead.objects.filter(announcement=announcement).count() == 2

        # Step 6: Tenants acknowledge
        read1.acknowledge(self.user1)
        read2.acknowledge(self.user2)

        assert read1.acknowledged is True
        assert read2.acknowledged is True

        # Step 7: Log communications
        for tenant, user in [(self.tenant1, self.user1), (self.tenant2, self.user2)]:
            CommunicationLog.objects.create(
                communication_type=CommunicationLog.ANNOUNCEMENT,
                announcement=announcement,
                tenant=tenant,
                subject=announcement.title,
                message_preview=announcement.message[:100],
                channels_used=announcement.channels,
                delivery_status={"in_app": "sent", "email": "sent"},
                sent_by=self.admin,
            )

        assert CommunicationLog.objects.filter(announcement=announcement).count() == 2

    def test_template_based_announcement_workflow(self):
        """Test creating announcement from template."""
        # Step 1: Create template
        template = CommunicationTemplate.objects.create(
            name="Maintenance Template",
            template_type=CommunicationTemplate.MAINTENANCE,
            subject="Maintenance on {{date}}",
            message="Dear {{tenant_name}}, maintenance scheduled for {{date}}.",
            default_severity=Announcement.MAINTENANCE,
            default_channels=["in_app", "email"],
            created_by=self.admin,
        )

        # Step 2: Render template for tenant
        context = {"date": "Nov 1, 2025", "tenant_name": self.tenant1.company_name}

        subject, message = template.render(context)

        assert "Nov 1, 2025" in subject
        assert self.tenant1.company_name in message

        # Step 3: Create announcement from template
        announcement = Announcement.objects.create(
            title=subject,
            message=message,
            severity=template.default_severity,
            target_all_tenants=False,
            target_filter={},
            channels=template.default_channels,
            status=Announcement.SENT,
            sent_at=timezone.now(),
            created_by=self.admin,
        )

        # Step 4: Track template usage
        template.increment_usage()

        assert template.usage_count == 1
        assert announcement.title == subject
        assert announcement.message == message
