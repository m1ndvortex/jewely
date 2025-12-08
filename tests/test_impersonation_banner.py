"""
Tests for impersonation banner template.

Verifies that the impersonation banner is displayed correctly when a platform
administrator is impersonating a tenant user.

Requirements: 12.3
"""

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

import pytest

from apps.core.models import Tenant, TenantSettings
from apps.core.services.impersonation_service import ImpersonationService

User = get_user_model()


@pytest.mark.django_db
class TestImpersonationBanner:
    """Test suite for impersonation banner display."""

    def test_banner_not_displayed_when_not_impersonating(self):
        """
        Test that the banner is not displayed when not impersonating.

        Requirement 12.3: Banner should only be visible during impersonation.
        """
        # Create platform admin
        admin = User.objects.create_user(
            username="admin_banner_test_1",
            email="admin1@example.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Login as admin
        client = Client()
        client.force_login(admin)

        # Access admin dashboard
        response = client.get(reverse("core:admin_dashboard"))

        # Verify banner is not displayed
        assert response.status_code == 200
        assert "Impersonation Mode" not in response.content.decode()
        assert "End Impersonation" not in response.content.decode()

    def test_banner_displayed_during_impersonation(self):
        """
        Test that the banner is displayed when impersonating a user.

        Requirement 12.3: Display visible banner during impersonation.
        """
        # Create tenant and tenant user
        tenant = Tenant.objects.create(
            company_name="Test Jewelry",
            slug="test-jewelry-2",
            status="active",
        )
        TenantSettings.objects.create(tenant=tenant)

        tenant_user = User.objects.create_user(
            username="tenant_user_2",
            email="user2@test.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_OWNER,
        )

        # Create platform admin
        admin = User.objects.create_user(
            username="admin_banner_test_2",
            email="admin2@example.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Start impersonation
        client = Client()
        client.force_login(admin)

        impersonation_service = ImpersonationService()
        request = client.get(reverse("core:admin_dashboard")).wsgi_request
        request.user = admin

        success, message = impersonation_service.start_impersonation(
            request=request,
            target_user=tenant_user,
            admin_user=admin,
        )

        assert success is True

        # Update session
        client.session.update(request.session)
        client.session.save()

        # Access tenant dashboard (now as impersonated user)
        response = client.get(reverse("core:tenant_dashboard"))

        # Verify banner is displayed
        assert response.status_code == 200
        content = response.content.decode()
        assert "Impersonation Mode" in content
        assert "End Impersonation" in content

    def test_banner_shows_impersonated_user_info(self):
        """
        Test that the banner shows the impersonated user's information.

        Requirement 12.3: Show impersonated user info.
        """
        # Create tenant and tenant user
        tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-jewelry-3",
            status="active",
        )
        TenantSettings.objects.create(tenant=tenant)

        tenant_user = User.objects.create_user(
            username="john_doe_3",
            email="john3@testjewelry.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_OWNER,
        )

        # Create platform admin
        admin = User.objects.create_user(
            username="admin_banner_test_3",
            email="admin3@example.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Start impersonation
        client = Client()
        client.force_login(admin)

        impersonation_service = ImpersonationService()
        request = client.get(reverse("core:admin_dashboard")).wsgi_request
        request.user = admin

        success, message = impersonation_service.start_impersonation(
            request=request,
            target_user=tenant_user,
            admin_user=admin,
        )

        assert success is True

        # Update session
        client.session.update(request.session)
        client.session.save()

        # Access tenant dashboard
        response = client.get(reverse("core:tenant_dashboard"))

        # Verify user info is displayed
        assert response.status_code == 200
        content = response.content.decode()
        assert "john_doe_3" in content  # Username
        assert "john3@testjewelry.com" in content  # Email
        assert "Test Jewelry Shop" in content  # Tenant name

    def test_banner_has_end_impersonation_button(self):
        """
        Test that the banner has an "End Impersonation" button.

        Requirement 12.3: Add "End Impersonation" button.
        """
        # Create tenant and tenant user
        tenant = Tenant.objects.create(
            company_name="Test Jewelry",
            slug="test-jewelry-4",
            status="active",
        )
        TenantSettings.objects.create(tenant=tenant)

        tenant_user = User.objects.create_user(
            username="tenant_user_4",
            email="user4@test.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_OWNER,
        )

        # Create platform admin
        admin = User.objects.create_user(
            username="admin_banner_test_4",
            email="admin4@example.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Start impersonation
        client = Client()
        client.force_login(admin)

        impersonation_service = ImpersonationService()
        request = client.get(reverse("core:admin_dashboard")).wsgi_request
        request.user = admin

        success, message = impersonation_service.start_impersonation(
            request=request,
            target_user=tenant_user,
            admin_user=admin,
        )

        assert success is True

        # Update session
        client.session.update(request.session)
        client.session.save()

        # Access tenant dashboard
        response = client.get(reverse("core:tenant_dashboard"))

        # Verify button is present with correct action
        assert response.status_code == 200
        content = response.content.decode()
        assert "End Impersonation" in content
        assert reverse("core:admin_end_impersonation") in content
        assert 'method="post"' in content  # Form should use POST

    def test_banner_is_visually_prominent(self):
        """
        Test that the banner has prominent styling.

        Requirement 12.3: Display visible banner (should be prominent).
        """
        # Create tenant and tenant user
        tenant = Tenant.objects.create(
            company_name="Test Jewelry",
            slug="test-jewelry-5",
            status="active",
        )
        TenantSettings.objects.create(tenant=tenant)

        tenant_user = User.objects.create_user(
            username="tenant_user_5",
            email="user5@test.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_OWNER,
        )

        # Create platform admin
        admin = User.objects.create_user(
            username="admin_banner_test_5",
            email="admin5@example.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Start impersonation
        client = Client()
        client.force_login(admin)

        impersonation_service = ImpersonationService()
        request = client.get(reverse("core:admin_dashboard")).wsgi_request
        request.user = admin

        success, message = impersonation_service.start_impersonation(
            request=request,
            target_user=tenant_user,
            admin_user=admin,
        )

        assert success is True

        # Update session
        client.session.update(request.session)
        client.session.save()

        # Access tenant dashboard
        response = client.get(reverse("core:tenant_dashboard"))

        # Verify prominent styling classes are present
        assert response.status_code == 200
        content = response.content.decode()

        # Check for fixed positioning (stays at top)
        assert "fixed" in content
        assert "top-0" in content

        # Check for high z-index (appears above other content)
        assert "z-[9999]" in content or "z-50" in content

        # Check for warning colors (orange/red)
        assert "orange" in content or "red" in content

        # Check for shadow (makes it stand out)
        assert "shadow" in content

    def test_banner_shows_audit_warning(self):
        """
        Test that the banner shows a warning that actions are logged.

        Requirement 12.3: Banner should indicate that actions are audited.
        """
        # Create tenant and tenant user
        tenant = Tenant.objects.create(
            company_name="Test Jewelry",
            slug="test-jewelry-6",
            status="active",
        )
        TenantSettings.objects.create(tenant=tenant)

        tenant_user = User.objects.create_user(
            username="tenant_user_6",
            email="user6@test.com",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_OWNER,
        )

        # Create platform admin
        admin = User.objects.create_user(
            username="admin_banner_test_6",
            email="admin6@example.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

        # Start impersonation
        client = Client()
        client.force_login(admin)

        impersonation_service = ImpersonationService()
        request = client.get(reverse("core:admin_dashboard")).wsgi_request
        request.user = admin

        success, message = impersonation_service.start_impersonation(
            request=request,
            target_user=tenant_user,
            admin_user=admin,
        )

        assert success is True

        # Update session
        client.session.update(request.session)
        client.session.save()

        # Access tenant dashboard
        response = client.get(reverse("core:tenant_dashboard"))

        # Verify audit warning is displayed
        assert response.status_code == 200
        content = response.content.decode()
        assert "logged" in content.lower() or "audit" in content.lower()
