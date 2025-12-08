"""
Property-based tests for TenantDomain model and subdomain generation.

**Feature: advanced-tenant-management, Property 2: Subdomain Generation Consistency**
**Validates: Requirements 1.5, 9.1**

Property 2: Subdomain Generation Consistency
*For any* tenant slug, the generated subdomain SHALL follow the format
`{slug}.{BASE_DOMAIN}` and be unique across all tenants.
"""

import re
import uuid

from django.conf import settings

import pytest
from hypothesis import assume, given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from apps.core.models import Tenant, TenantDomain
from apps.core.services.domain_service import DomainService
from apps.core.tenant_context import bypass_rls

# Default base domain for testing (can be overridden in settings)
DEFAULT_BASE_DOMAIN = "jewelry-shop.local"


def get_base_domain():
    """Get the base domain from settings or use default."""
    return getattr(settings, "TENANT_BASE_DOMAIN", DEFAULT_BASE_DOMAIN)


def is_valid_slug(slug: str) -> bool:
    """
    Check if a string is a valid Django slug.
    Valid slugs contain only letters, numbers, underscores, and hyphens.
    """
    if not slug:
        return False
    # Django slug pattern: letters, numbers, underscores, hyphens
    return bool(re.match(r"^[a-zA-Z0-9_-]+$", slug))


# Strategy for generating valid slugs
# Django slugs: letters, numbers, underscores, hyphens
# Min length 1, max length 50 (reasonable for subdomain)
valid_slug_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789-_"),
    min_size=1,
    max_size=50,
).filter(lambda s: s and not s.startswith("-") and not s.endswith("-"))


@pytest.mark.django_db
class TestSubdomainGenerationConsistency:
    """
    **Feature: advanced-tenant-management, Property 2: Subdomain Generation Consistency**
    **Validates: Requirements 1.5, 9.1**

    Property tests for subdomain generation using DomainService ensuring:
    1. Format follows {slug}.{BASE_DOMAIN}
    2. Same slug always produces same subdomain (deterministic)
    3. Different slugs produce different subdomains (uniqueness)
    """

    @given(slug=valid_slug_strategy)
    @hypothesis_settings(max_examples=100)
    def test_subdomain_format_consistency(self, slug):
        """
        **Feature: advanced-tenant-management, Property 2: Subdomain Generation Consistency**
        **Validates: Requirements 1.5, 9.1**

        For any valid slug, the DomainService.generate_subdomain() SHALL produce
        a subdomain following the format {slug}.{BASE_DOMAIN}.
        """
        service = DomainService()
        subdomain = service.generate_subdomain(slug)
        base_domain = service.base_domain

        # Property: subdomain must follow format {slug}.{base_domain}
        expected_format = f"{slug}.{base_domain}"
        assert (
            subdomain == expected_format
        ), f"Subdomain format mismatch: expected '{expected_format}', got '{subdomain}'"

        # Property: subdomain must contain exactly one occurrence of base_domain
        assert (
            subdomain.count(base_domain) == 1
        ), f"Subdomain should contain base domain exactly once"

        # Property: subdomain must start with the slug
        assert subdomain.startswith(slug), f"Subdomain should start with slug '{slug}'"

        # Property: subdomain must end with base_domain
        assert subdomain.endswith(
            base_domain
        ), f"Subdomain should end with base domain '{base_domain}'"

    @given(slug=valid_slug_strategy)
    @hypothesis_settings(max_examples=100)
    def test_subdomain_generation_deterministic(self, slug):
        """
        **Feature: advanced-tenant-management, Property 2: Subdomain Generation Consistency**
        **Validates: Requirements 1.5, 9.1**

        For any slug, calling DomainService.generate_subdomain() multiple times
        SHALL produce the same result (deterministic).
        """
        service = DomainService()
        subdomain1 = service.generate_subdomain(slug)
        subdomain2 = service.generate_subdomain(slug)
        subdomain3 = service.generate_subdomain(slug)

        assert (
            subdomain1 == subdomain2 == subdomain3
        ), f"Subdomain generation is not deterministic for slug '{slug}'"

    @given(slug1=valid_slug_strategy, slug2=valid_slug_strategy)
    @hypothesis_settings(max_examples=100)
    def test_different_slugs_produce_different_subdomains(self, slug1, slug2):
        """
        **Feature: advanced-tenant-management, Property 2: Subdomain Generation Consistency**
        **Validates: Requirements 1.5, 9.1**

        For any two different slugs, the generated subdomains SHALL be different
        (uniqueness property).
        """
        # Use assume to skip when slugs are the same
        assume(slug1 != slug2)

        service = DomainService()
        subdomain1 = service.generate_subdomain(slug1)
        subdomain2 = service.generate_subdomain(slug2)

        assert (
            subdomain1 != subdomain2
        ), f"Different slugs '{slug1}' and '{slug2}' produced same subdomain"

    @given(slug=valid_slug_strategy)
    @hypothesis_settings(max_examples=100)
    def test_subdomain_contains_separator(self, slug):
        """
        **Feature: advanced-tenant-management, Property 2: Subdomain Generation Consistency**
        **Validates: Requirements 1.5, 9.1**

        For any valid slug, the generated subdomain SHALL contain exactly one
        dot separator between slug and base domain.
        """
        service = DomainService()
        subdomain = service.generate_subdomain(slug)
        base_domain = service.base_domain

        # The subdomain should be slug + "." + base_domain
        # So total dots = dots in base_domain + 1 (the separator)
        base_domain_dots = base_domain.count(".")
        expected_dots = base_domain_dots + 1

        assert (
            subdomain.count(".") == expected_dots
        ), f"Subdomain should have {expected_dots} dots, got {subdomain.count('.')}"

    @given(slug=valid_slug_strategy)
    @hypothesis_settings(max_examples=100)
    def test_subdomain_preserves_slug_case(self, slug):
        """
        **Feature: advanced-tenant-management, Property 2: Subdomain Generation Consistency**
        **Validates: Requirements 1.5, 9.1**

        For any valid slug, the generated subdomain SHALL preserve the original
        slug casing (no transformation applied).
        """
        service = DomainService()
        subdomain = service.generate_subdomain(slug)

        # Extract the slug portion from the subdomain
        base_domain = service.base_domain
        extracted_slug = subdomain.replace(f".{base_domain}", "")

        assert (
            extracted_slug == slug
        ), f"Slug was transformed: expected '{slug}', got '{extracted_slug}'"


@pytest.mark.django_db
class TestTenantDomainUniqueness:
    """
    **Feature: advanced-tenant-management, Property 2: Subdomain Generation Consistency**
    **Validates: Requirements 1.5, 9.1**

    Property tests for TenantDomain model uniqueness constraint.
    Tests that subdomains generated by DomainService are unique across tenants.
    """

    @given(slug=valid_slug_strategy)
    @hypothesis_settings(max_examples=50, deadline=None)
    def test_tenant_domain_uniqueness_enforced(self, slug):
        """
        **Feature: advanced-tenant-management, Property 2: Subdomain Generation Consistency**
        **Validates: Requirements 1.5, 9.1**

        For any subdomain generated by DomainService, the TenantDomain model
        SHALL enforce uniqueness at the database level.
        """
        from django.db import IntegrityError, transaction

        service = DomainService()
        subdomain = service.generate_subdomain(slug)
        unique_id = str(uuid.uuid4())[:8]

        with bypass_rls():
            # Create first tenant
            tenant1 = Tenant.objects.create(
                company_name=f"Test Shop 1 {unique_id}",
                slug=f"{slug}-{unique_id}-1",
                status="ACTIVE",
            )

            # Create domain for first tenant using generated subdomain
            domain1 = TenantDomain.objects.create(
                tenant=tenant1,
                domain_type=TenantDomain.DOMAIN_TYPE_SUBDOMAIN,
                domain=f"{subdomain}-{unique_id}",
                is_primary=True,
            )

            # Create second tenant
            tenant2 = Tenant.objects.create(
                company_name=f"Test Shop 2 {unique_id}",
                slug=f"{slug}-{unique_id}-2",
                status="ACTIVE",
            )

            # Attempting to create domain with same domain name should fail
            try:
                with transaction.atomic():
                    TenantDomain.objects.create(
                        tenant=tenant2,
                        domain_type=TenantDomain.DOMAIN_TYPE_SUBDOMAIN,
                        domain=f"{subdomain}-{unique_id}",  # Same domain
                        is_primary=True,
                    )
                # If we get here, uniqueness was not enforced
                assert False, "Expected IntegrityError for duplicate domain"
            except IntegrityError:
                # This is expected - uniqueness constraint is working
                pass

            # Cleanup
            domain1.delete()
            tenant2.delete()
            tenant1.delete()

    @given(slug=valid_slug_strategy)
    @hypothesis_settings(max_examples=50, deadline=None)
    def test_subdomain_stored_correctly_in_model(self, slug):
        """
        **Feature: advanced-tenant-management, Property 2: Subdomain Generation Consistency**
        **Validates: Requirements 1.5, 9.1**

        For any valid slug, when a TenantDomain is created with the subdomain
        generated by DomainService, it SHALL be stored and retrieved correctly.
        """
        service = DomainService()
        subdomain = service.generate_subdomain(slug)
        unique_id = str(uuid.uuid4())[:8]
        unique_subdomain = f"{subdomain}-{unique_id}"

        with bypass_rls():
            # Create tenant
            tenant = Tenant.objects.create(
                company_name=f"Test Shop {unique_id}",
                slug=f"{slug}-{unique_id}",
                status="ACTIVE",
            )

            # Create domain using DomainService-generated subdomain
            domain = TenantDomain.objects.create(
                tenant=tenant,
                domain_type=TenantDomain.DOMAIN_TYPE_SUBDOMAIN,
                domain=unique_subdomain,
                is_primary=True,
            )

            # Retrieve and verify
            retrieved = TenantDomain.objects.get(id=domain.id)
            assert retrieved.domain == unique_subdomain, (
                f"Domain not stored correctly: expected '{unique_subdomain}', "
                f"got '{retrieved.domain}'"
            )
            assert retrieved.domain_type == TenantDomain.DOMAIN_TYPE_SUBDOMAIN
            assert retrieved.is_primary is True
            assert retrieved.tenant_id == tenant.id

            # Cleanup
            domain.delete()
            tenant.delete()

    @given(slug=valid_slug_strategy)
    @hypothesis_settings(max_examples=50, deadline=None)
    def test_create_subdomain_for_tenant_integration(self, slug):
        """
        **Feature: advanced-tenant-management, Property 2: Subdomain Generation Consistency**
        **Validates: Requirements 1.5, 9.1**

        For any valid slug, DomainService.create_subdomain_for_tenant() SHALL
        create a TenantDomain with the correctly formatted subdomain.
        """
        service = DomainService()
        unique_id = str(uuid.uuid4())[:8]
        tenant_slug = f"{slug}-{unique_id}"

        with bypass_rls():
            # Create tenant
            tenant = Tenant.objects.create(
                company_name=f"Test Shop {unique_id}",
                slug=tenant_slug,
                status="ACTIVE",
            )

            # Use service to create subdomain
            domain = service.create_subdomain_for_tenant(tenant, set_as_primary=True)

            # Verify the subdomain follows the expected format
            expected_subdomain = service.generate_subdomain(tenant_slug)
            assert domain.domain == expected_subdomain, (
                f"Subdomain mismatch: expected '{expected_subdomain}', " f"got '{domain.domain}'"
            )
            assert domain.domain_type == TenantDomain.DOMAIN_TYPE_SUBDOMAIN
            assert domain.is_primary is True
            assert domain.tenant_id == tenant.id
            assert domain.verification_status == TenantDomain.VERIFICATION_VERIFIED

            # Cleanup
            domain.delete()
            tenant.delete()
