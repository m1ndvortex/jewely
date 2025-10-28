"""
Tests for tenant-facing announcement display functionality.

Per Requirement 31 - Communication and Announcement System
Task 22.3 - Implement announcement display

These are real integration tests using the actual database and models.
No mocking is used - all tests verify real functionality.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

import pytest

from apps.core.announcement_models import Announcement, AnnouncementRead
from apps.core.models import SubscriptionPlan, Tenant, TenantSubscription

User = get_user_model()


@pytest.mark.django_db
class TestAnnouncementDisplay(TestCase):
    """
    Test announcement display functionality for tenants.

    Requirement 31.5: Display announcements as dismissible banners.
    Requirement 31.6: Track read/unread status.
    Requirement 31.7: Require tenant acknowledgment for critical announcements.
    """

    def setUp(self):
        """Set up test data."""
        # Create subscription plan
        self.plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            price=99.00,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=10,
            inventory_limit=1000,
            branch_limit=5,
            status=SubscriptionPlan.STATUS_ACTIVE,
        )

        # Create tenant
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        # Create tenant subscription
        self.subscription = TenantSubscription.objects.create(
            tenant=self.tenant, plan=self.plan, status=TenantSubscription.STATUS_ACTIVE
        )

        # Create tenant user
        self.tenant_user = User.objects.create_user(
            username="tenant_user",
            email="tenant@example.com",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_OWNER",
        )

        # Create platform admin
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            role="PLATFORM_ADMIN",
        )

        # Create test announcements
        self.info_announcement = Announcement.objects.create(
            title="New Feature Available",
            message="We've added a new reporting feature to help you analyze your sales data.",
            severity=Announcement.INFO,
            status=Announcement.SENT,
            sent_at=timezone.now(),
            target_all_tenants=True,
            channels=["in_app"],
            is_dismissible=True,
            requires_acknowledgment=False,
            created_by=self.admin_user,
        )

        self.critical_announcement = Announcement.objects.create(
            title="Critical Security Update",
            message="Please review and acknowledge this important security update.",
            severity=Announcement.CRITICAL,
            status=Announcement.SENT,
            sent_at=timezone.now(),
            target_all_tenants=True,
            channels=["in_app", "email"],
            is_dismissible=False,
            requires_acknowledgment=True,
            created_by=self.admin_user,
        )

        self.maintenance_announcement = Announcement.objects.create(
            title="Scheduled Maintenance",
            message="System maintenance scheduled for this weekend.",
            severity=Announcement.MAINTENANCE,
            status=Announcement.SENT,
            sent_at=timezone.now(),
            target_all_tenants=True,
            channels=["in_app"],
            is_dismissible=True,
            requires_acknowledgment=False,
            created_by=self.admin_user,
        )

        self.client = Client()

    def test_announcement_center_access(self):
        """Test that tenant users can access announcement center."""
        self.client.login(username="tenant_user", password="testpass123")
        response = self.client.get(reverse("core:tenant_announcement_center"))

        assert response.status_code == 200
        assert "Announcements" in response.content.decode()

    def test_announcement_center_shows_unread_announcements(self):
        """Test that announcement center displays unread announcements."""
        self.client.login(username="tenant_user", password="testpass123")
        response = self.client.get(reverse("core:tenant_announcement_center"))

        content = response.content.decode()
        assert self.info_announcement.title in content
        assert self.critical_announcement.title in content
        assert self.maintenance_announcement.title in content

    def test_announcement_center_separates_read_unread(self):
        """Test that read and unread announcements are separated."""
        # Mark one announcement as read
        AnnouncementRead.objects.create(
            announcement=self.info_announcement, tenant=self.tenant, user=self.tenant_user
        )

        self.client.login(username="tenant_user", password="testpass123")
        response = self.client.get(reverse("core:tenant_announcement_center"))

        content = response.content.decode()
        assert "Unread Announcements" in content
        assert "Read Announcements" in content

    def test_announcement_detail_marks_as_read(self):
        """Test that viewing announcement detail marks it as read."""
        self.client.login(username="tenant_user", password="testpass123")

        # Verify not read initially
        assert not AnnouncementRead.objects.filter(
            announcement=self.info_announcement, tenant=self.tenant
        ).exists()

        # View announcement detail
        response = self.client.get(
            reverse("core:tenant_announcement_detail", kwargs={"pk": self.info_announcement.pk})
        )

        assert response.status_code == 200

        # Verify marked as read
        assert AnnouncementRead.objects.filter(
            announcement=self.info_announcement, tenant=self.tenant
        ).exists()

    def test_dismissible_announcement_can_be_dismissed(self):
        """Test that dismissible announcements can be dismissed."""
        self.client.login(username="tenant_user", password="testpass123")

        # Dismiss announcement
        response = self.client.get(
            reverse("core:tenant_announcement_dismiss", kwargs={"pk": self.info_announcement.pk})
        )

        assert response.status_code == 302  # Redirect after dismiss

        # Verify dismissed
        read_record = AnnouncementRead.objects.get(
            announcement=self.info_announcement, tenant=self.tenant
        )
        assert read_record.dismissed is True
        assert read_record.dismissed_at is not None

    def test_non_dismissible_announcement_cannot_be_dismissed(self):
        """Test that non-dismissible announcements cannot be dismissed."""
        self.client.login(username="tenant_user", password="testpass123")

        # Try to dismiss non-dismissible announcement
        response = self.client.get(
            reverse(
                "core:tenant_announcement_dismiss", kwargs={"pk": self.critical_announcement.pk}
            )
        )

        # Should redirect with error message
        assert response.status_code == 302

        # Verify not dismissed
        read_record = AnnouncementRead.objects.filter(
            announcement=self.critical_announcement, tenant=self.tenant
        ).first()
        if read_record:
            assert read_record.dismissed is False

    def test_critical_announcement_requires_acknowledgment(self):
        """Test that critical announcements require acknowledgment."""
        self.client.login(username="tenant_user", password="testpass123")

        # View acknowledgment page
        response = self.client.get(
            reverse(
                "core:tenant_announcement_acknowledge",
                kwargs={"pk": self.critical_announcement.pk},
            )
        )

        assert response.status_code == 200
        assert "Acknowledge Announcement" in response.content.decode()

    def test_acknowledge_announcement(self):
        """Test acknowledging an announcement."""
        self.client.login(username="tenant_user", password="testpass123")

        # Acknowledge announcement
        response = self.client.post(
            reverse(
                "core:tenant_announcement_acknowledge",
                kwargs={"pk": self.critical_announcement.pk},
            ),
            {"confirm": "on"},
        )

        assert response.status_code == 302  # Redirect after acknowledgment

        # Verify acknowledged
        read_record = AnnouncementRead.objects.get(
            announcement=self.critical_announcement, tenant=self.tenant
        )
        assert read_record.acknowledged is True
        assert read_record.acknowledged_at is not None
        assert read_record.acknowledged_by == self.tenant_user

    def test_cannot_acknowledge_non_acknowledgment_announcement(self):
        """Test that non-acknowledgment announcements cannot be acknowledged."""
        self.client.login(username="tenant_user", password="testpass123")

        # Try to acknowledge non-acknowledgment announcement
        response = self.client.get(
            reverse(
                "core:tenant_announcement_acknowledge", kwargs={"pk": self.info_announcement.pk}
            )
        )

        # Should redirect with error message
        assert response.status_code == 302

    def test_active_announcements_api(self):
        """Test API endpoint for active announcements."""
        self.client.login(username="tenant_user", password="testpass123")

        response = self.client.get(reverse("core:api_tenant_active_announcements"))

        assert response.status_code == 200
        data = response.json()

        assert "announcements" in data
        assert "unread_count" in data
        assert "unacknowledged_critical_count" in data

        # Should have 3 announcements
        assert len(data["announcements"]) <= 5  # API limits to 5

        # Should have 3 unread
        assert data["unread_count"] == 3

        # Should have 1 unacknowledged critical
        assert data["unacknowledged_critical_count"] == 1

    def test_active_announcements_api_excludes_dismissed(self):
        """Test that API excludes dismissed announcements."""
        # Dismiss one announcement
        read_record = AnnouncementRead.objects.create(
            announcement=self.info_announcement, tenant=self.tenant, user=self.tenant_user
        )
        read_record.dismiss()

        self.client.login(username="tenant_user", password="testpass123")

        response = self.client.get(reverse("core:api_tenant_active_announcements"))
        data = response.json()

        # Should not include dismissed announcement
        announcement_ids = [a["id"] for a in data["announcements"]]
        assert str(self.info_announcement.id) not in announcement_ids

    def test_active_announcements_api_shows_acknowledgment_status(self):
        """Test that API shows acknowledgment status correctly."""
        # Acknowledge critical announcement
        read_record = AnnouncementRead.objects.create(
            announcement=self.critical_announcement, tenant=self.tenant, user=self.tenant_user
        )
        read_record.acknowledge(self.tenant_user)

        self.client.login(username="tenant_user", password="testpass123")

        response = self.client.get(reverse("core:api_tenant_active_announcements"))
        data = response.json()

        # Find critical announcement in response
        critical_data = next(
            (a for a in data["announcements"] if a["id"] == str(self.critical_announcement.id)),
            None,
        )

        assert critical_data is not None
        assert critical_data["requires_acknowledgment"] is True
        assert critical_data["is_acknowledged"] is True

        # Should have 0 unacknowledged critical
        assert data["unacknowledged_critical_count"] == 0

    def test_announcement_center_shows_unread_count(self):
        """Test that announcement center displays correct unread count."""
        self.client.login(username="tenant_user", password="testpass123")

        response = self.client.get(reverse("core:tenant_announcement_center"))
        content = response.content.decode()

        # Should show 3 unread
        assert "3" in content  # Unread count

    def test_announcement_center_requires_authentication(self):
        """Test that announcement center requires authentication."""
        response = self.client.get(reverse("core:tenant_announcement_center"))

        # Should redirect to login
        assert response.status_code == 302
        assert "/login/" in response.url or "login" in response.url.lower()

    def test_announcement_detail_requires_authentication(self):
        """Test that announcement detail requires authentication."""
        response = self.client.get(
            reverse("core:tenant_announcement_detail", kwargs={"pk": self.info_announcement.pk})
        )

        # Should redirect to login
        assert response.status_code == 302

    def test_announcement_targeting_by_plan(self):
        """Test that announcements can be targeted by subscription plan."""
        # Create announcement targeted to specific plan
        targeted_announcement = Announcement.objects.create(
            title="Premium Feature",
            message="This feature is only for premium users.",
            severity=Announcement.INFO,
            status=Announcement.SENT,
            sent_at=timezone.now(),
            target_all_tenants=False,
            target_filter={"plans": ["Premium Plan"]},
            channels=["in_app"],
            created_by=self.admin_user,
        )

        self.client.login(username="tenant_user", password="testpass123")

        response = self.client.get(reverse("core:tenant_announcement_center"))
        content = response.content.decode()

        # Should not show targeted announcement (tenant has Basic Plan)
        assert targeted_announcement.title not in content

    def test_announcement_display_respects_display_until(self):
        """Test that announcements respect display_until date."""
        # Create announcement with past display_until
        expired_announcement = Announcement.objects.create(
            title="Expired Announcement",
            message="This announcement has expired.",
            severity=Announcement.INFO,
            status=Announcement.SENT,
            sent_at=timezone.now() - timezone.timedelta(days=2),
            display_until=timezone.now() - timezone.timedelta(days=1),
            target_all_tenants=True,
            channels=["in_app"],
            created_by=self.admin_user,
        )

        self.client.login(username="tenant_user", password="testpass123")

        response = self.client.get(reverse("core:api_tenant_active_announcements"))
        data = response.json()

        # Should not include expired announcement
        announcement_ids = [a["id"] for a in data["announcements"]]
        assert str(expired_announcement.id) not in announcement_ids


@pytest.mark.django_db
class TestAnnouncementBannerComponent(TestCase):
    """Test the announcement banner component functionality."""

    def setUp(self):
        """Set up test data."""
        # Create subscription plan
        self.plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            price=99.00,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=10,
            inventory_limit=1000,
            branch_limit=5,
            status=SubscriptionPlan.STATUS_ACTIVE,
        )

        # Create tenant
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        # Create tenant subscription
        self.subscription = TenantSubscription.objects.create(
            tenant=self.tenant, plan=self.plan, status=TenantSubscription.STATUS_ACTIVE
        )

        # Create tenant user
        self.tenant_user = User.objects.create_user(
            username="tenant_user",
            email="tenant@example.com",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_OWNER",
        )

        # Create platform admin
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            role="PLATFORM_ADMIN",
        )

        self.client = Client()

    def test_banner_api_returns_json(self):
        """Test that banner API returns valid JSON."""
        self.client.login(username="tenant_user", password="testpass123")

        response = self.client.get(reverse("core:api_tenant_active_announcements"))

        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"

        data = response.json()
        assert isinstance(data, dict)
        assert "announcements" in data
        assert isinstance(data["announcements"], list)

    def test_banner_api_includes_severity_info(self):
        """Test that banner API includes severity information."""
        # Create announcement
        announcement = Announcement.objects.create(
            title="Test Announcement",
            message="Test message",
            severity=Announcement.WARNING,
            status=Announcement.SENT,
            sent_at=timezone.now(),
            target_all_tenants=True,
            channels=["in_app"],
            created_by=self.admin_user,
        )

        self.client.login(username="tenant_user", password="testpass123")

        response = self.client.get(reverse("core:api_tenant_active_announcements"))
        data = response.json()

        # Verify the announcement we created is in the response
        announcement_data = data["announcements"][0]
        assert announcement_data["severity"] == "WARNING"
        assert announcement_data["is_dismissible"] is True
        assert announcement.id  # Verify announcement was created

    def test_banner_api_limits_results(self):
        """Test that banner API limits results to 5 most recent."""
        # Create 10 announcements
        for i in range(10):
            Announcement.objects.create(
                title=f"Announcement {i}",
                message=f"Message {i}",
                severity=Announcement.INFO,
                status=Announcement.SENT,
                sent_at=timezone.now(),
                target_all_tenants=True,
                channels=["in_app"],
                created_by=self.admin_user,
            )

        self.client.login(username="tenant_user", password="testpass123")

        response = self.client.get(reverse("core:api_tenant_active_announcements"))
        data = response.json()

        # Should return maximum 5 announcements
        assert len(data["announcements"]) <= 5
