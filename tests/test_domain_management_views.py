"""
Tests for domain management views.

Tests the TenantDomainCreateView, TenantDomainDeleteView, and TenantDomainVerifyView
to ensure they work correctly per Requirements 9.2, 9.3, 9.4.
"""

import json
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

import pytest

from apps.core.models import Tenant, TenantDomain

User = get_user_model()


@pytest.fixture
def platform_admin(db):
    """Create a platform admin user."""
    import uuid

    unique_id = str(uuid.uuid4())[:8]
    return User.objects.create_user(
        username=f"admin_{unique_id}",
        email=f"admin_{unique_id}@example.com",
        password="testpass123",
        role=User.PLATFORM_ADMIN,
    )


@pytest.fixture
def tenant(db):
    """Create a test tenant."""
    return Tenant.objects.create(
        company_name="Test Jewelry Shop",
        slug="test-shop",
        status=Tenant.ACTIVE,
    )


@pytest.fixture
def authenticated_client(platform_admin):
    """Create an authenticated client with platform admin."""
    client = Client()
    client.force_login(platform_admin)
    return client


@pytest.mark.django_db
class TestTenantDomainCreateView:
    """Test the TenantDomainCreateView."""

    def test_create_custom_domain_success(self, authenticated_client, tenant):
        """Test successfully creating a custom domain."""
        url = reverse("core:admin_tenant_domain_create", kwargs={"pk": tenant.pk})
        data = {"domain": "shop.example.com"}

        response = authenticated_client.post(
            url,
            data=json.dumps(data),
            content_type="application/json",
        )

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "shop.example.com" in result["message"]
        assert result["domain"]["domain"] == "shop.example.com"
        assert result["domain"]["domain_type"] == TenantDomain.DOMAIN_TYPE_CUSTOM
        assert result["domain"]["verification_status"] == TenantDomain.VERIFICATION_PENDING

        # Verify domain was created in database
        domain = TenantDomain.objects.get(domain="shop.example.com")
        assert domain.tenant == tenant
        assert domain.domain_type == TenantDomain.DOMAIN_TYPE_CUSTOM
        assert domain.verification_token != ""

    def test_create_domain_empty_domain(self, authenticated_client, tenant):
        """Test creating domain with empty domain name."""
        url = reverse("core:admin_tenant_domain_create", kwargs={"pk": tenant.pk})
        data = {"domain": ""}

        response = authenticated_client.post(
            url,
            data=json.dumps(data),
            content_type="application/json",
        )

        assert response.status_code == 400
        result = response.json()
        assert result["success"] is False
        assert "required" in result["error"].lower()

    def test_create_domain_invalid_format(self, authenticated_client, tenant):
        """Test creating domain with invalid format."""
        url = reverse("core:admin_tenant_domain_create", kwargs={"pk": tenant.pk})
        data = {"domain": "invalid domain with spaces"}

        response = authenticated_client.post(
            url,
            data=json.dumps(data),
            content_type="application/json",
        )

        assert response.status_code == 400
        result = response.json()
        assert result["success"] is False
        assert "validation failed" in result["error"].lower()

    def test_create_domain_duplicate(self, authenticated_client, tenant):
        """Test creating a domain that already exists."""
        # Create first domain
        TenantDomain.objects.create(
            tenant=tenant,
            domain="shop.example.com",
            domain_type=TenantDomain.DOMAIN_TYPE_CUSTOM,
            verification_token="test-token",
        )

        # Try to create duplicate
        url = reverse("core:admin_tenant_domain_create", kwargs={"pk": tenant.pk})
        data = {"domain": "shop.example.com"}

        response = authenticated_client.post(
            url,
            data=json.dumps(data),
            content_type="application/json",
        )

        assert response.status_code == 400
        result = response.json()
        assert result["success"] is False
        assert "already registered" in result["error"].lower()

    def test_create_domain_requires_authentication(self, tenant):
        """Test that domain creation requires authentication."""
        client = Client()
        url = reverse("core:admin_tenant_domain_create", kwargs={"pk": tenant.pk})
        data = {"domain": "shop.example.com"}

        response = client.post(
            url,
            data=json.dumps(data),
            content_type="application/json",
        )

        # Should redirect to login
        assert response.status_code == 302


@pytest.mark.django_db
class TestTenantDomainDeleteView:
    """Test the TenantDomainDeleteView."""

    def test_delete_custom_domain_success(self, authenticated_client, tenant):
        """Test successfully deleting a custom domain."""
        # Create a custom domain
        domain = TenantDomain.objects.create(
            tenant=tenant,
            domain="shop.example.com",
            domain_type=TenantDomain.DOMAIN_TYPE_CUSTOM,
            is_primary=False,
            verification_token="test-token",
        )

        url = reverse(
            "core:admin_tenant_domain_delete",
            kwargs={"pk": tenant.pk, "domain_pk": domain.pk},
        )

        response = authenticated_client.post(url)

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "deleted successfully" in result["message"].lower()

        # Verify domain was deleted from database
        assert not TenantDomain.objects.filter(pk=domain.pk).exists()

    def test_delete_primary_subdomain_fails(self, authenticated_client, tenant):
        """Test that deleting primary subdomain is prevented."""
        # Create a primary subdomain
        domain = TenantDomain.objects.create(
            tenant=tenant,
            domain="test-shop.jewelry-shop.local",
            domain_type=TenantDomain.DOMAIN_TYPE_SUBDOMAIN,
            is_primary=True,
            verification_status=TenantDomain.VERIFICATION_VERIFIED,
        )

        url = reverse(
            "core:admin_tenant_domain_delete",
            kwargs={"pk": tenant.pk, "domain_pk": domain.pk},
        )

        response = authenticated_client.post(url)

        assert response.status_code == 400
        result = response.json()
        assert result["success"] is False
        assert "cannot delete" in result["error"].lower()
        assert "primary subdomain" in result["error"].lower()

        # Verify domain still exists
        assert TenantDomain.objects.filter(pk=domain.pk).exists()

    def test_delete_domain_not_found(self, authenticated_client, tenant):
        """Test deleting a non-existent domain."""
        fake_domain_id = uuid.uuid4()
        url = reverse(
            "core:admin_tenant_domain_delete",
            kwargs={"pk": tenant.pk, "domain_pk": fake_domain_id},
        )

        response = authenticated_client.post(url)

        assert response.status_code == 404


@pytest.mark.django_db
class TestTenantDomainVerifyView:
    """Test the TenantDomainVerifyView."""

    def test_verify_custom_domain_success(self, authenticated_client, tenant):
        """Test successfully verifying a custom domain."""
        # Create a custom domain
        domain = TenantDomain.objects.create(
            tenant=tenant,
            domain="shop.example.com",
            domain_type=TenantDomain.DOMAIN_TYPE_CUSTOM,
            verification_status=TenantDomain.VERIFICATION_PENDING,
            verification_token="test-token-123",
        )

        url = reverse(
            "core:admin_tenant_domain_verify",
            kwargs={"pk": tenant.pk, "domain_pk": domain.pk},
        )

        # Mock the domain service to return verified status
        with patch(
            "apps.core.services.domain_service.DomainService.check_domain_verification"
        ) as mock_verify:
            mock_verify.return_value = TenantDomain.VERIFICATION_VERIFIED

            response = authenticated_client.post(url)

            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            assert "verified successfully" in result["message"].lower()

    def test_verify_subdomain_fails(self, authenticated_client, tenant):
        """Test that verifying a subdomain is not allowed."""
        # Create a subdomain
        domain = TenantDomain.objects.create(
            tenant=tenant,
            domain="test-shop.jewelry-shop.local",
            domain_type=TenantDomain.DOMAIN_TYPE_SUBDOMAIN,
            is_primary=True,
            verification_status=TenantDomain.VERIFICATION_VERIFIED,
        )

        url = reverse(
            "core:admin_tenant_domain_verify",
            kwargs={"pk": tenant.pk, "domain_pk": domain.pk},
        )

        response = authenticated_client.post(url)

        assert response.status_code == 400
        result = response.json()
        assert result["success"] is False
        assert "only custom domains" in result["error"].lower()

    def test_verify_domain_pending(self, authenticated_client, tenant):
        """Test verifying a domain that remains pending."""
        # Create a custom domain
        domain = TenantDomain.objects.create(
            tenant=tenant,
            domain="shop.example.com",
            domain_type=TenantDomain.DOMAIN_TYPE_CUSTOM,
            verification_status=TenantDomain.VERIFICATION_PENDING,
            verification_token="test-token-123",
        )

        url = reverse(
            "core:admin_tenant_domain_verify",
            kwargs={"pk": tenant.pk, "domain_pk": domain.pk},
        )

        # Mock the domain service to return pending status
        with patch(
            "apps.core.services.domain_service.DomainService.check_domain_verification"
        ) as mock_verify:
            mock_verify.return_value = TenantDomain.VERIFICATION_PENDING

            response = authenticated_client.post(url)

            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            assert "pending" in result["message"].lower()
            assert result["domain"]["verification_status"] == TenantDomain.VERIFICATION_PENDING
