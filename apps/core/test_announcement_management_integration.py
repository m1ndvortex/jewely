"""
Integration tests for announcement management interface.

Tests the complete announcement management workflow including:
- Creating announcements via forms
- Scheduling announcements
- Targeting tenants
- Sending announcements
- Managing direct messages
- Using templates

NO MOCKS - All tests use real database and services.
Per Requirement 31 - Communication and Announcement System
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

import pytest

from apps.core.announcement_models import (
    Announcement,
    AnnouncementRead,
    CommunicationTemplate,
    DirectMessage,
)
from apps.core.models import SubscriptionPlan, Tenant, TenantSubscription

User = get_user_model()


@pytest.mark.django_db
class AnnouncementManagementIntegrationTest(TestCase):
    """
    Integration tests for announcement management interface.
    Tests actual HTTP requests and form submissions.
    """

    def setUp(self):
        """Set up test data."""
        # Create platform admin
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            role="PLATFORM_ADMIN",
            is_staff=True,
        )

        # Create subscription plans
        self.basic_plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            price=Decimal("29.99"),
            billing_cycle="monthly",
            status=SubscriptionPlan.STATUS_ACTIVE,
        )

        self.premium_plan = SubscriptionPlan.objects.create(
            name="Premium Plan",
            price=Decimal("99.99"),
            billing_cycle="monthly",
            status=SubscriptionPlan.STATUS_ACTIVE,
        )

        # Create tenants
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

        # Create client and login
        self.client = Client()
        self.client.login(username="admin", password="adminpass123")

    def test_announcement_list_view(self):
        """Test accessing announcement list view."""
        # Create some announcements
        Announcement.objects.create(
            title="Test Announcement 1",
            message="Message 1",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        Announcement.objects.create(
            title="Test Announcement 2",
            message="Message 2",
            severity=Announcement.CRITICAL,
            target_all_tenants=True,
            channels=["in_app", "email"],
            status=Announcement.SENT,
            sent_at=timezone.now(),
            created_by=self.admin,
        )

        # Access list view
        response = self.client.get(reverse("core:announcement_list"))

        assert response.status_code == 200
        assert "Test Announcement 1" in str(response.content)
        assert "Test Announcement 2" in str(response.content)

    def test_create_announcement_with_all_tenants(self):
        """Test creating announcement targeting all tenants."""
        data = {
            "title": "System Maintenance",
            "message": "We will perform maintenance on Nov 1, 2025.",
            "severity": Announcement.MAINTENANCE,
            "target_all_tenants": True,
            "channel_in_app": True,
            "channel_email": True,
            "requires_acknowledgment": False,
            "is_dismissible": True,
        }

        response = self.client.post(reverse("core:announcement_create"), data)

        # Should redirect on success
        assert response.status_code == 302

        # Verify announcement was created
        announcement = Announcement.objects.get(title="System Maintenance")
        assert announcement.message == "We will perform maintenance on Nov 1, 2025."
        assert announcement.severity == Announcement.MAINTENANCE
        assert announcement.target_all_tenants is True
        assert "in_app" in announcement.channels
        assert "email" in announcement.channels
        assert announcement.status == Announcement.DRAFT
        assert announcement.created_by == self.admin

    def test_create_announcement_with_plan_targeting(self):
        """Test creating announcement targeting specific subscription plans."""
        data = {
            "title": "Premium Feature Announcement",
            "message": "New premium features available!",
            "severity": Announcement.INFO,
            "target_all_tenants": False,
            "target_plans": [self.premium_plan.id],
            "channel_in_app": True,
            "requires_acknowledgment": False,
            "is_dismissible": True,
        }

        response = self.client.post(reverse("core:announcement_create"), data)

        assert response.status_code == 302

        announcement = Announcement.objects.get(title="Premium Feature Announcement")
        assert announcement.target_all_tenants is False
        assert "plans" in announcement.target_filter
        assert "Premium Plan" in announcement.target_filter["plans"]

        # Verify targeting works
        target_tenants = announcement.get_target_tenants()
        assert self.tenant2 in target_tenants  # Premium plan
        assert self.tenant1 not in target_tenants  # Basic plan

    def test_create_announcement_with_status_targeting(self):
        """Test creating announcement targeting specific tenant statuses."""
        data = {
            "title": "Suspended Account Notice",
            "message": "Your account is suspended.",
            "severity": Announcement.WARNING,
            "target_all_tenants": False,
            "target_statuses": [Tenant.SUSPENDED],
            "channel_in_app": True,
            "channel_email": True,
            "requires_acknowledgment": False,
            "is_dismissible": True,
        }

        response = self.client.post(reverse("core:announcement_create"), data)

        assert response.status_code == 302

        announcement = Announcement.objects.get(title="Suspended Account Notice")
        assert "statuses" in announcement.target_filter
        assert Tenant.SUSPENDED in announcement.target_filter["statuses"]

        # Verify targeting works
        target_tenants = announcement.get_target_tenants()
        assert self.tenant3 in target_tenants  # Suspended
        assert self.tenant1 not in target_tenants  # Active
        assert self.tenant2 not in target_tenants  # Active

    def test_create_scheduled_announcement(self):
        """Test creating a scheduled announcement."""
        future_time = timezone.now() + timezone.timedelta(days=7)

        data = {
            "title": "Upcoming Feature Release",
            "message": "New features coming next week!",
            "severity": Announcement.INFO,
            "target_all_tenants": True,
            "channel_in_app": True,
            "schedule_for_later": True,
            "scheduled_at": future_time.strftime("%Y-%m-%dT%H:%M"),
            "requires_acknowledgment": False,
            "is_dismissible": True,
        }

        response = self.client.post(reverse("core:announcement_create"), data)

        assert response.status_code == 302

        announcement = Announcement.objects.get(title="Upcoming Feature Release")
        assert announcement.status == Announcement.SCHEDULED
        assert announcement.scheduled_at is not None
        assert announcement.sent_at is None

    def test_create_critical_announcement_requiring_acknowledgment(self):
        """Test creating critical announcement that requires acknowledgment."""
        data = {
            "title": "Critical Security Update",
            "message": "Please update your password immediately.",
            "severity": Announcement.CRITICAL,
            "target_all_tenants": True,
            "channel_in_app": True,
            "channel_email": True,
            "channel_sms": True,
            "requires_acknowledgment": True,
            "is_dismissible": False,
        }

        response = self.client.post(reverse("core:announcement_create"), data)

        assert response.status_code == 302

        announcement = Announcement.objects.get(title="Critical Security Update")
        assert announcement.severity == Announcement.CRITICAL
        assert announcement.requires_acknowledgment is True
        assert announcement.is_dismissible is False
        assert len(announcement.channels) == 3

    def test_edit_draft_announcement(self):
        """Test editing a draft announcement."""
        announcement = Announcement.objects.create(
            title="Draft Announcement",
            message="Original message",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        data = {
            "title": "Updated Draft Announcement",
            "message": "Updated message",
            "severity": Announcement.WARNING,
            "target_all_tenants": True,
            "channel_in_app": True,
            "channel_email": True,
            "requires_acknowledgment": False,
            "is_dismissible": True,
        }

        response = self.client.post(
            reverse("core:announcement_update", kwargs={"pk": announcement.pk}), data
        )

        assert response.status_code == 302

        announcement.refresh_from_db()
        assert announcement.title == "Updated Draft Announcement"
        assert announcement.message == "Updated message"
        assert announcement.severity == Announcement.WARNING
        assert "email" in announcement.channels

    def test_send_announcement_immediately(self):
        """Test sending an announcement immediately."""
        announcement = Announcement.objects.create(
            title="Immediate Announcement",
            message="Send this now",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        response = self.client.post(
            reverse("core:announcement_send", kwargs={"pk": announcement.pk})
        )

        assert response.status_code == 302

        announcement.refresh_from_db()
        assert announcement.status == Announcement.SENT
        assert announcement.sent_at is not None

    def test_cancel_scheduled_announcement(self):
        """Test canceling a scheduled announcement."""
        future_time = timezone.now() + timezone.timedelta(days=1)
        announcement = Announcement.objects.create(
            title="Scheduled Announcement",
            message="This will be canceled",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            scheduled_at=future_time,
            status=Announcement.SCHEDULED,
            created_by=self.admin,
        )

        response = self.client.post(
            reverse("core:announcement_cancel", kwargs={"pk": announcement.pk})
        )

        assert response.status_code == 302

        announcement.refresh_from_db()
        assert announcement.status == Announcement.CANCELLED

    def test_announcement_detail_view_with_statistics(self):
        """Test viewing announcement details with read statistics."""
        announcement = Announcement.objects.create(
            title="Test Announcement",
            message="Test message",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            status=Announcement.SENT,
            sent_at=timezone.now(),
            created_by=self.admin,
        )

        # Create some read records
        AnnouncementRead.objects.create(
            announcement=announcement,
            tenant=self.tenant1,
        )

        response = self.client.get(
            reverse("core:announcement_detail", kwargs={"pk": announcement.pk})
        )

        assert response.status_code == 200
        assert "Test Announcement" in str(response.content)
        # Should show read statistics
        assert response.context["read_count"] == 1

    def test_form_validation_requires_channel(self):
        """Test that form validation requires at least one channel."""
        data = {
            "title": "No Channel Announcement",
            "message": "This should fail",
            "severity": Announcement.INFO,
            "target_all_tenants": True,
            "channel_in_app": False,
            "channel_email": False,
            "channel_sms": False,
            "requires_acknowledgment": False,
            "is_dismissible": True,
        }

        response = self.client.post(reverse("core:announcement_create"), data)

        # Should not redirect (form error)
        assert response.status_code == 200
        assert "Please select at least one delivery channel" in str(response.content)

    def test_form_validation_scheduled_time_in_future(self):
        """Test that scheduled time must be in the future."""
        past_time = timezone.now() - timezone.timedelta(hours=1)

        data = {
            "title": "Past Scheduled Announcement",
            "message": "This should fail",
            "severity": Announcement.INFO,
            "target_all_tenants": True,
            "channel_in_app": True,
            "schedule_for_later": True,
            "scheduled_at": past_time.strftime("%Y-%m-%dT%H:%M"),
            "requires_acknowledgment": False,
            "is_dismissible": True,
        }

        response = self.client.post(reverse("core:announcement_create"), data)

        # Should not redirect (form error)
        assert response.status_code == 200
        assert "Scheduled time must be in the future" in str(response.content)


@pytest.mark.django_db
class DirectMessageManagementIntegrationTest(TestCase):
    """Integration tests for direct message management."""

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            role="PLATFORM_ADMIN",
            is_staff=True,
        )

        self.tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        self.client = Client()
        self.client.login(username="admin", password="adminpass123")

    def test_direct_message_list_view(self):
        """Test accessing direct message list view."""
        DirectMessage.objects.create(
            tenant=self.tenant,
            subject="Test Message",
            message="Test content",
            channels=["email"],
            status=DirectMessage.DRAFT,
            created_by=self.admin,
        )

        response = self.client.get(reverse("core:direct_message_list"))

        assert response.status_code == 200
        assert "Test Message" in str(response.content)

    def test_create_direct_message(self):
        """Test creating a direct message."""
        data = {
            "tenant": self.tenant.id,
            "subject": "Account Issue",
            "message": "We noticed an issue with your account.",
            "channel_email": True,
            "channel_in_app": True,
        }

        response = self.client.post(reverse("core:direct_message_create"), data)

        assert response.status_code == 302

        message = DirectMessage.objects.get(subject="Account Issue")
        assert message.tenant == self.tenant
        assert message.message == "We noticed an issue with your account."
        assert "email" in message.channels
        assert "in_app" in message.channels
        assert message.status == DirectMessage.DRAFT
        assert message.created_by == self.admin

    def test_send_direct_message(self):
        """Test sending a direct message."""
        message = DirectMessage.objects.create(
            tenant=self.tenant,
            subject="Test Message",
            message="Test content",
            channels=["email"],
            status=DirectMessage.DRAFT,
            created_by=self.admin,
        )

        response = self.client.post(reverse("core:direct_message_send", kwargs={"pk": message.pk}))

        assert response.status_code == 302

        message.refresh_from_db()
        assert message.status == DirectMessage.SENT
        assert message.sent_at is not None

    def test_direct_message_detail_view(self):
        """Test viewing direct message details."""
        message = DirectMessage.objects.create(
            tenant=self.tenant,
            subject="Test Message",
            message="Test content",
            channels=["email"],
            status=DirectMessage.SENT,
            created_by=self.admin,
        )

        response = self.client.get(reverse("core:direct_message_detail", kwargs={"pk": message.pk}))

        assert response.status_code == 200
        assert "Test Message" in str(response.content)


@pytest.mark.django_db
class CommunicationTemplateManagementIntegrationTest(TestCase):
    """Integration tests for communication template management."""

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            role="PLATFORM_ADMIN",
            is_staff=True,
        )

        self.client = Client()
        self.client.login(username="admin", password="adminpass123")

    def test_template_list_view(self):
        """Test accessing template list view."""
        CommunicationTemplate.objects.create(
            name="Maintenance Template",
            template_type=CommunicationTemplate.MAINTENANCE,
            subject="Maintenance on {{date}}",
            message="Maintenance scheduled for {{date}}.",
            default_severity=Announcement.MAINTENANCE,
            default_channels=["in_app", "email"],
            created_by=self.admin,
        )

        response = self.client.get(reverse("core:template_list"))

        assert response.status_code == 200
        assert "Maintenance Template" in str(response.content)

    def test_create_template(self):
        """Test creating a communication template."""
        data = {
            "name": "Welcome Template",
            "template_type": CommunicationTemplate.CUSTOM,
            "subject": "Welcome to {{platform_name}}",
            "message": "Hello {{tenant_name}}, welcome!",
            "default_severity": Announcement.INFO,
            "default_channel_in_app": True,
            "default_channel_email": True,
            "is_active": True,
        }

        response = self.client.post(reverse("core:template_create"), data)

        assert response.status_code == 302

        template = CommunicationTemplate.objects.get(name="Welcome Template")
        assert template.template_type == CommunicationTemplate.CUSTOM
        assert "{{platform_name}}" in template.subject
        assert "{{tenant_name}}" in template.message
        assert "in_app" in template.default_channels
        assert "email" in template.default_channels
        assert template.is_active is True
        assert template.created_by == self.admin

    def test_edit_template(self):
        """Test editing a template."""
        template = CommunicationTemplate.objects.create(
            name="Original Template",
            template_type=CommunicationTemplate.CUSTOM,
            subject="Original Subject",
            message="Original Message",
            default_severity=Announcement.INFO,
            default_channels=["in_app"],
            created_by=self.admin,
        )

        data = {
            "name": "Updated Template",
            "template_type": CommunicationTemplate.CUSTOM,
            "subject": "Updated Subject",
            "message": "Updated Message",
            "default_severity": Announcement.WARNING,
            "default_channel_in_app": True,
            "default_channel_email": True,
            "is_active": True,
        }

        response = self.client.post(
            reverse("core:template_update", kwargs={"pk": template.pk}), data
        )

        assert response.status_code == 302

        template.refresh_from_db()
        assert template.name == "Updated Template"
        assert template.subject == "Updated Subject"
        assert template.message == "Updated Message"
        assert template.default_severity == Announcement.WARNING
        assert "email" in template.default_channels

    def test_use_template_to_create_announcement(self):
        """Test using a template to create an announcement."""
        template = CommunicationTemplate.objects.create(
            name="Maintenance Template",
            template_type=CommunicationTemplate.MAINTENANCE,
            subject="Maintenance on {{date}}",
            message="Dear {{tenant_name}}, maintenance scheduled for {{date}}.",
            default_severity=Announcement.MAINTENANCE,
            default_channels=["in_app", "email"],
            created_by=self.admin,
        )

        response = self.client.get(reverse("core:template_use", kwargs={"pk": template.pk}))

        assert response.status_code == 200
        # Should show announcement form pre-filled with template data
        assert "Maintenance on {{date}}" in str(response.content)

        # Verify usage counter incremented
        template.refresh_from_db()
        assert template.usage_count == 1

    def test_template_detail_view(self):
        """Test viewing template details."""
        template = CommunicationTemplate.objects.create(
            name="Test Template",
            template_type=CommunicationTemplate.CUSTOM,
            subject="Test Subject",
            message="Test Message",
            default_severity=Announcement.INFO,
            default_channels=["in_app"],
            created_by=self.admin,
        )

        response = self.client.get(reverse("core:template_detail", kwargs={"pk": template.pk}))

        assert response.status_code == 200
        assert "Test Template" in str(response.content)


@pytest.mark.django_db
class AnnouncementFilteringIntegrationTest(TestCase):
    """Integration tests for announcement filtering."""

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            role="PLATFORM_ADMIN",
            is_staff=True,
        )

        # Create announcements with different attributes
        Announcement.objects.create(
            title="Draft Info",
            message="Message",
            severity=Announcement.INFO,
            target_all_tenants=True,
            channels=["in_app"],
            status=Announcement.DRAFT,
            created_by=self.admin,
        )

        Announcement.objects.create(
            title="Sent Critical",
            message="Message",
            severity=Announcement.CRITICAL,
            target_all_tenants=True,
            channels=["in_app"],
            status=Announcement.SENT,
            sent_at=timezone.now(),
            created_by=self.admin,
        )

        Announcement.objects.create(
            title="Scheduled Maintenance",
            message="Message",
            severity=Announcement.MAINTENANCE,
            target_all_tenants=True,
            channels=["in_app"],
            status=Announcement.SCHEDULED,
            scheduled_at=timezone.now() + timezone.timedelta(days=1),
            created_by=self.admin,
        )

        self.client = Client()
        self.client.login(username="admin", password="adminpass123")

    def test_filter_by_status(self):
        """Test filtering announcements by status."""
        response = self.client.get(
            reverse("core:announcement_list"), {"status": Announcement.DRAFT}
        )

        assert response.status_code == 200
        assert "Draft Info" in str(response.content)
        assert "Sent Critical" not in str(response.content)

    def test_filter_by_severity(self):
        """Test filtering announcements by severity."""
        response = self.client.get(
            reverse("core:announcement_list"), {"severity": Announcement.CRITICAL}
        )

        assert response.status_code == 200
        assert "Sent Critical" in str(response.content)
        assert "Draft Info" not in str(response.content)

    def test_search_by_title(self):
        """Test searching announcements by title."""
        response = self.client.get(reverse("core:announcement_list"), {"search": "Critical"})

        assert response.status_code == 200
        assert "Sent Critical" in str(response.content)
        assert "Draft Info" not in str(response.content)


@pytest.mark.django_db
class PermissionIntegrationTest(TestCase):
    """Integration tests for permission enforcement."""

    def setUp(self):
        """Set up test data."""
        # Create tenant for regular user
        self.tenant = Tenant.objects.create(
            company_name="Regular Shop",
            slug="regular-shop",
            status=Tenant.ACTIVE,
        )

        # Create non-admin user
        self.regular_user = User.objects.create_user(
            username="regular",
            email="regular@example.com",
            password="pass123",
            role="TENANT_OWNER",
            tenant=self.tenant,
        )

        self.client = Client()

    def test_non_admin_cannot_access_announcement_list(self):
        """Test that non-admin users cannot access announcement management."""
        self.client.login(username="regular", password="pass123")

        response = self.client.get(reverse("core:announcement_list"))

        # Should redirect or show error
        assert response.status_code in [302, 403]

    def test_non_admin_cannot_create_announcement(self):
        """Test that non-admin users cannot create announcements."""
        self.client.login(username="regular", password="pass123")

        data = {
            "title": "Unauthorized",
            "message": "Should not work",
            "severity": Announcement.INFO,
            "target_all_tenants": True,
            "channel_in_app": True,
        }

        response = self.client.post(reverse("core:announcement_create"), data)

        # Should redirect or show error
        assert response.status_code in [302, 403]

        # Verify announcement was not created
        assert not Announcement.objects.filter(title="Unauthorized").exists()

    def test_unauthenticated_cannot_access(self):
        """Test that unauthenticated users cannot access announcement management."""
        # Don't login

        response = self.client.get(reverse("core:announcement_list"))

        # Should redirect to login
        assert response.status_code == 302
        assert "/admin/login/" in response.url or "login" in response.url
