"""
Tests for impersonation views.

Tests the TenantUserImpersonateView and EndImpersonationView to ensure
they properly start and end impersonation sessions with audit logging.

Requirements: 12.2, 12.4
"""

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

import pytest

from apps.core.audit_models import AuditLog
from apps.core.models import Tenant

User = get_user_model()


@pytest.mark.django_db
class TestImpersonationViews:
    """Test impersonation view functionality."""

    def test_impersonate_view_starts_impersonation(self):
        """
        Test that TenantUserImpersonateView starts impersonation and logs it.

        Validates Requirement 12.2: Audit logging of impersonation start.
        """
        # Create platform admin
        admin = User.objects.create_user(
            username="admin_impersonate_test",
            email="admin_impersonate@platform.com",
            password="testpass123",
            tenant=None,  # Platform admin has no tenant
            role=User.PLATFORM_ADMIN,
        )

        # Create tenant and tenant user
        tenant = Tenant.objects.create(
            company_name="Test Tenant",
            slug="test-tenant",
            status=Tenant.ACTIVE,
        )

        tenant_user = User.objects.create_user(
            username="tenant_user",
            email="user@tenant.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Login as admin
        client = Client()
        client.force_login(admin)

        # Start impersonation
        url = reverse(
            "core:admin_tenant_user_impersonate",
            kwargs={
                "tenant_pk": tenant.id,
                "user_pk": tenant_user.id,
            },
        )

        response = client.post(url)

        # Should redirect to tenant dashboard
        assert response.status_code == 302

        # Check audit log was created
        audit_logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_IMPERSONATION_START,
            tenant=tenant,
        )
        assert audit_logs.count() == 1

        audit_log = audit_logs.first()
        assert audit_log.user == admin
        assert audit_log.category == AuditLog.CATEGORY_SECURITY
        assert audit_log.metadata["target_user_id"] == tenant_user.id
        assert audit_log.metadata["target_username"] == tenant_user.username

    def test_end_impersonation_view_ends_impersonation(self):
        """
        Test that EndImpersonationView ends impersonation and logs it.

        Validates Requirement 12.4: Audit logging of impersonation end.
        """
        # Create platform admin
        admin = User.objects.create_user(
            username="admin_end_test",
            email="admin_end@platform.com",
            password="testpass123",
            tenant=None,
            role=User.PLATFORM_ADMIN,
        )

        # Create tenant and tenant user
        tenant = Tenant.objects.create(
            company_name="Test Tenant",
            slug="test-tenant",
            status=Tenant.ACTIVE,
        )

        tenant_user = User.objects.create_user(
            username="tenant_user",
            email="user@tenant.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        # Login as admin and start impersonation
        client = Client()
        client.force_login(admin)

        start_url = reverse(
            "core:admin_tenant_user_impersonate",
            kwargs={
                "tenant_pk": tenant.id,
                "user_pk": tenant_user.id,
            },
        )
        client.post(start_url)

        # Clear the start audit log for cleaner testing
        AuditLog.objects.filter(action=AuditLog.ACTION_IMPERSONATION_START).delete()

        # End impersonation
        end_url = reverse("core:admin_end_impersonation")
        response = client.post(end_url)

        # Should redirect to tenant detail or dashboard
        assert response.status_code == 302

        # Check audit log was created
        audit_logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_IMPERSONATION_END,
            tenant=tenant,
        )
        assert audit_logs.count() == 1

        audit_log = audit_logs.first()
        assert audit_log.user == admin
        assert audit_log.category == AuditLog.CATEGORY_SECURITY
        assert audit_log.metadata["target_user_id"] == tenant_user.id
        assert audit_log.metadata["target_username"] == tenant_user.username

    def test_impersonate_view_rejects_platform_admin(self):
        """
        Test that impersonation of platform admins is rejected.

        Validates security requirement that platform admins cannot be impersonated.
        """
        # Create two platform admins
        admin1 = User.objects.create_user(
            username="admin1",
            email="admin1@platform.com",
            password="testpass123",
            tenant=None,
            role=User.PLATFORM_ADMIN,
        )

        admin2 = User.objects.create_user(
            username="admin2",
            email="admin2@platform.com",
            password="testpass123",
            tenant=None,
            role=User.PLATFORM_ADMIN,
        )

        # Login as admin1
        client = Client()
        client.force_login(admin1)

        # Try to impersonate admin2 (should fail at service level)
        # Note: This would normally fail at the view level because admin2 has no tenant
        # But we test the service validation
        from django.test import RequestFactory

        from apps.core.services.impersonation_service import ImpersonationService

        factory = RequestFactory()
        request = factory.post("/")
        request.user = admin1
        request.session = client.session

        service = ImpersonationService()
        success, message = service.start_impersonation(request, admin2, admin1)

        assert not success
        assert "Cannot impersonate platform administrators" in message
