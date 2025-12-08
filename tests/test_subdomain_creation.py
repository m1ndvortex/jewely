"""
Test subdomain auto-creation during tenant creation.

This test verifies that when a tenant is created, a subdomain is automatically
generated and created as a TenantDomain record with the correct properties.

Per Requirement 9.1: Auto-generate subdomain from slug.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

import pytest

from apps.core.models import Tenant, TenantDomain, TenantSettings
from apps.core.services.tenant_service import TenantService

User = get_user_model()


@pytest.mark.django_db
class TestSubdomainCreation(TestCase):
    """Test subdomain auto-creation during tenant creation."""

    def setUp(self):
        """Set up test data."""
        # Create a platform admin user for creating tenants
        self.admin_user = User.objects.create_user(
            username="platform_admin",
            email="admin@platform.com",
            password="admin123",
            role=User.PLATFORM_ADMIN,
        )

    def test_subdomain_created_on_tenant_creation(self):
        """
        Test that a subdomain is automatically created when a tenant is created.

        Verifies:
        - Subdomain is generated from slug
        - TenantDomain record is created with type=SUBDOMAIN
        - is_primary is set to True
        - verification_status is VERIFIED
        - verified_at is set

        Per Requirement 9.1.
        """
        # Arrange
        tenant_data = {
            "company_name": "Test Jewelry Shop",
            "slug": "test-shop",
            "status": Tenant.ACTIVE,
        }
        settings_data = {
            "business_name": "Test Shop Inc",
            "email": "contact@testshop.com",
            "timezone": "UTC",
            "currency": TenantSettings.CURRENCY_USD,
            "date_format": TenantSettings.DATE_FORMAT_MDY,
        }
        owner_data = {
            "username": "shop_owner",
            "email": "owner@testshop.com",
            "password": "SecurePass123!",
        }
        domain_data = {}

        # Act
        service = TenantService()
        tenant, owner, password = service.create_tenant_with_owner(
            tenant_data=tenant_data,
            settings_data=settings_data,
            owner_data=owner_data,
            domain_data=domain_data,
            created_by=self.admin_user,
        )

        # Assert
        # Check that tenant was created
        self.assertIsNotNone(tenant)
        self.assertEqual(tenant.company_name, "Test Jewelry Shop")
        self.assertEqual(tenant.slug, "test-shop")

        # Check that subdomain was created
        subdomains = TenantDomain.objects.filter(
            tenant=tenant,
            domain_type=TenantDomain.DOMAIN_TYPE_SUBDOMAIN,
        )
        self.assertEqual(subdomains.count(), 1, "Exactly one subdomain should be created")

        subdomain = subdomains.first()

        # Verify subdomain properties
        self.assertEqual(
            subdomain.domain,
            "test-shop.jewelry-shop.local",
            "Subdomain should follow format {slug}.{BASE_DOMAIN}",
        )
        self.assertTrue(
            subdomain.is_primary,
            "Subdomain should be set as primary domain",
        )
        self.assertEqual(
            subdomain.verification_status,
            TenantDomain.VERIFICATION_VERIFIED,
            "Subdomain should be auto-verified",
        )
        self.assertIsNotNone(
            subdomain.verified_at,
            "verified_at should be set for auto-verified subdomain",
        )

    def test_subdomain_format_consistency(self):
        """
        Test that subdomain format is consistent across different slugs.

        Per Requirement 9.1 for subdomain generation consistency.
        """
        # Test with different slug formats
        test_cases = [
            ("simple", "simple.jewelry-shop.local"),
            ("with-hyphens", "with-hyphens.jewelry-shop.local"),
            ("with_underscores", "with_underscores.jewelry-shop.local"),
            ("mixed-format_123", "mixed-format_123.jewelry-shop.local"),
        ]

        service = TenantService()

        for slug, expected_subdomain in test_cases:
            with self.subTest(slug=slug):
                # Create tenant
                tenant_data = {
                    "company_name": f"Test Shop {slug}",
                    "slug": slug,
                    "status": Tenant.ACTIVE,
                }
                settings_data = {
                    "email": f"contact@{slug}.com",
                    "timezone": "UTC",
                    "currency": TenantSettings.CURRENCY_USD,
                    "date_format": TenantSettings.DATE_FORMAT_MDY,
                }
                owner_data = {
                    "username": f"owner_{slug}",
                    "email": f"owner@{slug}.com",
                    "password": "SecurePass123!",
                }
                domain_data = {}

                tenant, owner, password = service.create_tenant_with_owner(
                    tenant_data=tenant_data,
                    settings_data=settings_data,
                    owner_data=owner_data,
                    domain_data=domain_data,
                    created_by=self.admin_user,
                )

                # Check subdomain
                subdomain = TenantDomain.objects.get(
                    tenant=tenant,
                    domain_type=TenantDomain.DOMAIN_TYPE_SUBDOMAIN,
                )
                self.assertEqual(
                    subdomain.domain,
                    expected_subdomain,
                    f"Subdomain for slug '{slug}' should be '{expected_subdomain}'",
                )

    def test_subdomain_uniqueness(self):
        """
        Test that subdomain is unique across all tenants.

        Per Requirement 9.1 for subdomain uniqueness.
        """
        # Create first tenant
        service = TenantService()
        tenant_data_1 = {
            "company_name": "First Shop",
            "slug": "unique-shop",
            "status": Tenant.ACTIVE,
        }
        settings_data = {
            "email": "contact@shop1.com",
            "timezone": "UTC",
            "currency": TenantSettings.CURRENCY_USD,
            "date_format": TenantSettings.DATE_FORMAT_MDY,
        }
        owner_data_1 = {
            "username": "owner1",
            "email": "owner1@shop.com",
            "password": "SecurePass123!",
        }
        domain_data = {}

        tenant1, owner1, password1 = service.create_tenant_with_owner(
            tenant_data=tenant_data_1,
            settings_data=settings_data,
            owner_data=owner_data_1,
            domain_data=domain_data,
            created_by=self.admin_user,
        )

        # Try to create second tenant with same slug (should fail)
        tenant_data_2 = {
            "company_name": "Second Shop",
            "slug": "unique-shop",  # Same slug
            "status": Tenant.ACTIVE,
        }
        owner_data_2 = {
            "username": "owner2",
            "email": "owner2@shop.com",
            "password": "SecurePass123!",
        }

        # This should raise an IntegrityError due to unique constraint on domain
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            tenant2, owner2, password2 = service.create_tenant_with_owner(
                tenant_data=tenant_data_2,
                settings_data=settings_data,
                owner_data=owner_data_2,
                domain_data=domain_data,
                created_by=self.admin_user,
            )

    def test_subdomain_with_custom_domain(self):
        """
        Test that subdomain is created even when custom domain is provided.

        Per Requirement 9.1 for subdomain auto-generation.
        """
        # Create tenant with custom domain
        service = TenantService()
        tenant_data = {
            "company_name": "Shop with Custom Domain",
            "slug": "custom-shop",
            "status": Tenant.ACTIVE,
        }
        settings_data = {
            "email": "contact@customshop.com",
            "timezone": "UTC",
            "currency": TenantSettings.CURRENCY_USD,
            "date_format": TenantSettings.DATE_FORMAT_MDY,
        }
        owner_data = {
            "username": "custom_owner",
            "email": "owner@customshop.com",
            "password": "SecurePass123!",
        }
        domain_data = {
            "custom_domain": "shop.example.com",
        }

        tenant, owner, password = service.create_tenant_with_owner(
            tenant_data=tenant_data,
            settings_data=settings_data,
            owner_data=owner_data,
            domain_data=domain_data,
            created_by=self.admin_user,
        )

        # Check that both subdomain and custom domain were created
        domains = TenantDomain.objects.filter(tenant=tenant)
        self.assertEqual(domains.count(), 2, "Both subdomain and custom domain should be created")

        # Check subdomain
        subdomain = domains.get(domain_type=TenantDomain.DOMAIN_TYPE_SUBDOMAIN)
        self.assertEqual(subdomain.domain, "custom-shop.jewelry-shop.local")
        self.assertTrue(subdomain.is_primary, "Subdomain should be primary")
        self.assertEqual(subdomain.verification_status, TenantDomain.VERIFICATION_VERIFIED)

        # Check custom domain
        custom = domains.get(domain_type=TenantDomain.DOMAIN_TYPE_CUSTOM)
        self.assertEqual(custom.domain, "shop.example.com")
        self.assertFalse(custom.is_primary, "Custom domain should not be primary initially")
        self.assertEqual(
            custom.verification_status,
            TenantDomain.VERIFICATION_PENDING,
            "Custom domain should be pending verification",
        )
