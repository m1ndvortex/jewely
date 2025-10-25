"""
Tests for tenant impersonation functionality.

Tests the django-hijack integration for secure tenant user impersonation
by platform administrators per Requirement 4.5 and Requirement 8.1.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

import pytest

from apps.core.models import PermissionAuditLog, Tenant
from apps.core.permissions import can_hijack_user

User = get_user_model()


class TestImpersonationPermissions(TestCase):
    """Test permission checks for impersonation."""

    def setUp(self):
        """Set up test data."""
        # Create platform admin
        self.platform_admin = User.objects.create_user(
            username="test_admin",
            email="testadmin@platform.com",
            password="admin123",
            role=User.PLATFORM_ADMIN,
            is_staff=True,
            is_superuser=True,
        )

        # Create tenant with users
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop-impersonate",
            status=Tenant.ACTIVE,
        )

        self.owner = User.objects.create_user(
            username="test_shop_owner",
            email="owner@testshop.com",
            password="owner123",
            role=User.TENANT_OWNER,
            tenant=self.tenant,
        )

        self.employee = User.objects.create_user(
            username="test_shop_employee",
            email="employee@testshop.com",
            password="employee123",
            role=User.TENANT_EMPLOYEE,
            tenant=self.tenant,
        )

    def test_platform_admin_can_hijack_tenant_user(self):
        """Platform admins should be able to hijack tenant users."""
        assert can_hijack_user(self.platform_admin, self.owner) is True

    def test_platform_admin_cannot_hijack_another_admin(self):
        """Platform admins should not be able to hijack other platform admins."""
        another_admin = User.objects.create_user(
            username="admin2",
            email="admin2@platform.com",
            password="admin123",
            role=User.PLATFORM_ADMIN,
        )
        assert can_hijack_user(self.platform_admin, another_admin) is False

    def test_platform_admin_cannot_hijack_self(self):
        """Platform admins should not be able to hijack themselves."""
        assert can_hijack_user(self.platform_admin, self.platform_admin) is False

    def test_tenant_user_cannot_hijack(self):
        """Tenant users should not be able to hijack anyone."""
        assert can_hijack_user(self.owner, self.employee) is False

    def test_tenant_owner_cannot_hijack_employee(self):
        """Tenant owners should not be able to hijack their employees."""
        assert can_hijack_user(self.owner, self.employee) is False


class TestImpersonationFlow(TestCase):
    """Test the complete impersonation flow."""

    def setUp(self):
        """Set up test data."""
        # Create platform admin
        self.platform_admin = User.objects.create_user(
            username="test_admin",
            email="testadmin@platform.com",
            password="admin123",
            role=User.PLATFORM_ADMIN,
            is_staff=True,
            is_superuser=True,
        )

        # Create tenant with users
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop-impersonate",
            status=Tenant.ACTIVE,
        )

        self.owner = User.objects.create_user(
            username="test_shop_owner",
            email="owner@testshop.com",
            password="owner123",
            role=User.TENANT_OWNER,
            tenant=self.tenant,
        )

        self.employee = User.objects.create_user(
            username="test_shop_employee",
            email="employee@testshop.com",
            password="employee123",
            role=User.TENANT_EMPLOYEE,
            tenant=self.tenant,
        )

    def test_impersonation_requires_authentication(self):
        """Impersonation should require authentication."""
        client = Client()

        # Try to hijack without authentication
        response = client.post(f"/hijack/{self.owner.id}/")

        # Should redirect to login or return 403
        assert response.status_code in [302, 403]

    def test_impersonation_requires_platform_admin(self):
        """Impersonation should require platform admin role."""
        client = Client()

        # Login as tenant owner
        client.login(username="test_shop_owner", password="owner123")

        # Try to hijack employee
        response = client.post(f"/hijack/{self.employee.id}/")

        # Should be denied (403 or redirect)
        assert response.status_code in [302, 403]

    def test_successful_impersonation_by_admin(self):
        """Platform admin should be able to successfully impersonate tenant user."""
        client = Client()

        # Login as platform admin
        client.login(username="test_admin", password="admin123")

        # Hijack tenant user
        response = client.post(f"/hijack/{self.owner.id}/", follow=True)

        # Should redirect to tenant dashboard
        assert response.status_code == 200

        # Check that we're now impersonating
        # The session should have hijack information
        assert "_hijack" in client.session or "hijack_history" in client.session

    def test_impersonation_creates_audit_log(self):
        """Impersonation should create audit log entries."""
        client = Client()

        # Clear existing audit logs
        PermissionAuditLog.objects.all().delete()

        # Login as platform admin
        client.login(username="test_admin", password="admin123")

        # Hijack tenant user
        client.post(f"/hijack/{self.owner.id}/", follow=True)

        # Check that audit log was created
        audit_logs = PermissionAuditLog.objects.filter(
            actor=self.platform_admin, target_user=self.owner
        )

        assert audit_logs.exists()
        assert audit_logs.filter(action="IMPERSONATION_STARTED").exists()

    def test_release_impersonation_creates_audit_log(self):
        """Releasing impersonation should create audit log entry."""
        client = Client()

        # Clear existing audit logs
        PermissionAuditLog.objects.all().delete()

        # Login as platform admin
        client.login(username="test_admin", password="admin123")

        # Hijack tenant user
        client.post(f"/hijack/{self.owner.id}/", follow=True)

        # Release hijack
        response = client.post("/hijack/release-hijack/", follow=True)

        # Should redirect back to admin dashboard
        assert response.status_code == 200

        # Check that both start and end audit logs were created
        audit_logs = PermissionAuditLog.objects.filter(
            actor=self.platform_admin, target_user=self.owner
        )

        assert audit_logs.filter(action="IMPERSONATION_STARTED").exists()
        assert audit_logs.filter(action="IMPERSONATION_ENDED").exists()


@pytest.mark.django_db
class TestImpersonationUI:
    """Test impersonation UI elements."""

    def test_impersonate_button_visible_for_active_tenant(self, platform_admin, tenant_with_users):
        """Impersonate button should be visible for active tenants with users."""
        client = Client()
        tenant = tenant_with_users["tenant"]

        # Login as platform admin
        client.login(username="test_admin", password="admin123")

        # Visit tenant detail page
        response = client.get(f"/platform/tenants/{tenant.id}/")

        assert response.status_code == 200
        assert b"Impersonate User" in response.content

    def test_impersonate_button_hidden_for_suspended_tenant(self, platform_admin, bypass_rls):
        """Impersonate button should be hidden for suspended tenants."""
        client = Client()

        # Create suspended tenant
        tenant = Tenant.objects.create(
            company_name="Suspended Shop",
            slug="suspended-shop-test",
            status=Tenant.SUSPENDED,
        )

        User.objects.create_user(
            username="suspended_user_test",
            email="user@suspended.com",
            password="user123",
            role=User.TENANT_OWNER,
            tenant=tenant,
        )

        # Login as platform admin
        client.login(username="test_admin", password="admin123")

        # Visit tenant detail page
        response = client.get(f"/platform/tenants/{tenant.id}/")

        assert response.status_code == 200
        # Button should not be visible for suspended tenants
        assert b"Impersonate User" not in response.content

    def test_impersonate_button_hidden_for_tenant_without_users(self, platform_admin, bypass_rls):
        """Impersonate button should be hidden for tenants without users."""
        client = Client()

        # Create tenant without users
        tenant = Tenant.objects.create(
            company_name="Empty Shop",
            slug="empty-shop-test",
            status=Tenant.ACTIVE,
        )

        # Login as platform admin
        client.login(username="test_admin", password="admin123")

        # Visit tenant detail page
        response = client.get(f"/platform/tenants/{tenant.id}/")

        assert response.status_code == 200
        # Button should not be visible for tenants without users
        assert b"Impersonate User" not in response.content


@pytest.mark.django_db
class TestImpersonationBanner:
    """Test impersonation banner display."""

    def test_banner_displayed_during_impersonation(self, platform_admin, tenant_with_users):
        """Impersonation banner should be displayed when impersonating."""
        client = Client()
        tenant_user = tenant_with_users["owner"]

        # Login as platform admin
        client.login(username="test_admin", password="admin123")

        # Hijack tenant user
        client.post(f"/hijack/{tenant_user.id}/", follow=True)

        # Visit dashboard
        response = client.get("/dashboard/")

        # Banner should be visible
        assert b"Impersonating:" in response.content or b"impersonating" in response.content.lower()
        assert b"Stop Impersonating" in response.content

    def test_banner_not_displayed_for_normal_users(self, tenant_with_users):
        """Impersonation banner should not be displayed for normal users."""
        client = Client()

        # Login as normal tenant user
        client.login(username="test_shop_owner", password="owner123")

        # Visit dashboard
        response = client.get("/dashboard/")

        # Banner should not be visible
        assert b"Stop Impersonating" not in response.content


@pytest.mark.django_db
class TestImpersonationSecurity:
    """Test security aspects of impersonation."""

    def test_cannot_impersonate_with_get_request(self, platform_admin, tenant_with_users):
        """Impersonation should not work with GET requests (security)."""
        client = Client()
        tenant_user = tenant_with_users["owner"]

        # Login as platform admin
        client.login(username="test_admin", password="admin123")

        # Try to hijack with GET request
        response = client.get(f"/hijack/{tenant_user.id}/")

        # Should not allow GET requests (per HIJACK_ALLOW_GET_REQUESTS = False)
        assert response.status_code in [405, 403]  # Method not allowed or forbidden

    def test_audit_log_includes_ip_address(self, platform_admin, tenant_with_users):
        """Audit log should include IP address of the hijacker."""
        client = Client()
        tenant_user = tenant_with_users["owner"]

        # Clear existing audit logs
        PermissionAuditLog.objects.all().delete()

        # Login as platform admin
        client.login(username="test_admin", password="admin123")

        # Hijack tenant user
        client.post(f"/hijack/{tenant_user.id}/", REMOTE_ADDR="192.168.1.100", follow=True)

        # Check audit log
        audit_log = PermissionAuditLog.objects.filter(
            actor=platform_admin, target_user=tenant_user, action="IMPERSONATION_STARTED"
        ).first()

        assert audit_log is not None
        # IP address should be recorded (may be 127.0.0.1 in tests)
        assert audit_log.ip_address is not None

    def test_audit_log_includes_user_agent(self, platform_admin, tenant_with_users):
        """Audit log should include user agent of the hijacker."""
        client = Client()
        tenant_user = tenant_with_users["owner"]

        # Clear existing audit logs
        PermissionAuditLog.objects.all().delete()

        # Login as platform admin
        client.login(username="test_admin", password="admin123")

        # Hijack tenant user with custom user agent
        client.post(
            f"/hijack/{tenant_user.id}/",
            HTTP_USER_AGENT="Mozilla/5.0 Test Browser",
            follow=True,
        )

        # Check audit log
        audit_log = PermissionAuditLog.objects.filter(
            actor=platform_admin, target_user=tenant_user, action="IMPERSONATION_STARTED"
        ).first()

        assert audit_log is not None
        assert audit_log.user_agent is not None
        assert "Mozilla" in audit_log.user_agent or audit_log.user_agent != ""
