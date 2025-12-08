"""
Property-based tests for DNS record generation.

**Feature: advanced-tenant-management, Property 15: DNS Record Generation**
**Validates: Requirements 9.4**

Property 15: DNS Record Generation
*For any* custom domain, the system SHALL generate correct CNAME and TXT
verification records that, when configured, would allow verification.
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

# Default base domain for testing
DEFAULT_BASE_DOMAIN = "jewelry-shop.local"


def get_base_domain():
    """Get the base domain from settings or use default."""
    return getattr(settings, "TENANT_BASE_DOMAIN", DEFAULT_BASE_DOMAIN)


def is_valid_hex_token(token: str, expected_length: int = 64) -> bool:
    """
    Check if a string is a valid hexadecimal token.

    Args:
        token: The token to validate
        expected_length: Expected length (default 64 for 32-byte token_hex)

    Returns:
        True if token is valid hex of expected length
    """
    if not token or len(token) != expected_length:
        return False
    return bool(re.match(r"^[0-9a-f]+$", token))


# Strategy for generating valid domain names (not subdomains of BASE_DOMAIN)
# Format: [subdomain.]domain.tld
def valid_custom_domain_strategy():
    """Generate valid custom domains that are not subdomains of BASE_DOMAIN."""
    base_domain = get_base_domain()

    # Domain name part (e.g., "example", "myshop")
    domain_part = st.text(
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789-"),
        min_size=3,
        max_size=20,
    ).filter(lambda s: s and not s.startswith("-") and not s.endswith("-"))

    # TLD part (e.g., "com", "net", "org")
    tld_part = st.sampled_from(["com", "net", "org", "io", "co", "shop", "store"])

    # Optional subdomain part (e.g., "shop", "www")
    subdomain_part = st.one_of(
        st.none(),
        st.text(
            alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789-"),
            min_size=2,
            max_size=15,
        ).filter(lambda s: s and not s.startswith("-") and not s.endswith("-")),
    )

    @st.composite
    def domain_strategy(draw):
        domain = draw(domain_part)
        tld = draw(tld_part)
        subdomain = draw(subdomain_part)

        if subdomain:
            full_domain = f"{subdomain}.{domain}.{tld}"
        else:
            full_domain = f"{domain}.{tld}"

        # Ensure it's not a subdomain of BASE_DOMAIN
        assume(not full_domain.endswith(f".{base_domain}"))
        assume(full_domain != base_domain)

        return full_domain

    return domain_strategy()


# Strategy for generating valid slugs
valid_slug_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789-_"),
    min_size=1,
    max_size=50,
).filter(lambda s: s and not s.startswith("-") and not s.endswith("-"))


@pytest.mark.django_db
class TestDNSRecordGeneration:
    """
    **Feature: advanced-tenant-management, Property 15: DNS Record Generation**
    **Validates: Requirements 9.4**

    Property tests for DNS record generation ensuring:
    1. CNAME and TXT records are generated for any custom domain
    2. Records have correct structure and required fields
    3. CNAME points to BASE_DOMAIN
    4. TXT record contains valid verification token
    5. Records are consistent and properly formatted
    """

    @given(
        domain=valid_custom_domain_strategy(),
        slug=valid_slug_strategy,
    )
    @hypothesis_settings(max_examples=100)
    def test_dns_records_structure_completeness(self, domain, slug):
        """
        **Feature: advanced-tenant-management, Property 15: DNS Record Generation**
        **Validates: Requirements 9.4**

        For any custom domain, get_dns_verification_records() SHALL return
        a dictionary containing both 'cname' and 'txt' records with all
        required fields.
        """
        service = DomainService()

        # Create a test tenant
        with bypass_rls():
            tenant = Tenant.objects.create(
                id=uuid.uuid4(),
                company_name=f"Test Company {slug}",
                slug=slug,
                status=Tenant.ACTIVE,
            )

        try:
            # Get DNS verification records
            dns_records = service.get_dns_verification_records(domain, tenant)

            # Property: Response must be a dictionary
            assert isinstance(dns_records, dict), "DNS records must be returned as a dictionary"

            # Property: Must contain 'cname' key
            assert "cname" in dns_records, "DNS records must contain 'cname' key"

            # Property: Must contain 'txt' key
            assert "txt" in dns_records, "DNS records must contain 'txt' key"

            # Property: Must contain 'verification_token' key
            assert (
                "verification_token" in dns_records
            ), "DNS records must contain 'verification_token' key"

            # Property: CNAME record must have required fields
            cname = dns_records["cname"]
            assert isinstance(cname, dict), "CNAME record must be a dictionary"
            required_cname_fields = ["name", "type", "value", "description", "full_record"]
            for field in required_cname_fields:
                assert field in cname, f"CNAME record must contain '{field}' field"

            # Property: TXT record must have required fields
            txt = dns_records["txt"]
            assert isinstance(txt, dict), "TXT record must be a dictionary"
            required_txt_fields = ["name", "type", "value", "description", "full_record"]
            for field in required_txt_fields:
                assert field in txt, f"TXT record must contain '{field}' field"

            # Property: Record types must be correct
            assert cname["type"] == "CNAME", "CNAME record type must be 'CNAME'"
            assert txt["type"] == "TXT", "TXT record type must be 'TXT'"

        finally:
            # Cleanup
            with bypass_rls():
                tenant.delete()

    @given(
        domain=valid_custom_domain_strategy(),
        slug=valid_slug_strategy,
    )
    @hypothesis_settings(max_examples=100)
    def test_cname_record_correctness(self, domain, slug):
        """
        **Feature: advanced-tenant-management, Property 15: DNS Record Generation**
        **Validates: Requirements 9.4**

        For any custom domain, the CNAME record SHALL point to the platform's
        BASE_DOMAIN.
        """
        service = DomainService()
        base_domain = service.base_domain

        # Create a test tenant
        with bypass_rls():
            tenant = Tenant.objects.create(
                id=uuid.uuid4(),
                company_name=f"Test Company {slug}",
                slug=slug,
                status=Tenant.ACTIVE,
            )

        try:
            # Get DNS verification records
            dns_records = service.get_dns_verification_records(domain, tenant)
            cname = dns_records["cname"]

            # Property: CNAME name must be the custom domain
            assert cname["name"] == domain, f"CNAME name must be the custom domain '{domain}'"

            # Property: CNAME value must be BASE_DOMAIN
            assert (
                cname["value"] == base_domain
            ), f"CNAME value must point to BASE_DOMAIN '{base_domain}'"

            # Property: CNAME full_record must contain both domain and BASE_DOMAIN
            full_record = cname["full_record"]
            assert domain in full_record, f"CNAME full_record must contain domain '{domain}'"
            assert (
                base_domain in full_record
            ), f"CNAME full_record must contain BASE_DOMAIN '{base_domain}'"
            assert "CNAME" in full_record, "CNAME full_record must contain 'CNAME' keyword"

        finally:
            # Cleanup
            with bypass_rls():
                tenant.delete()

    @given(
        domain=valid_custom_domain_strategy(),
        slug=valid_slug_strategy,
    )
    @hypothesis_settings(max_examples=100)
    def test_txt_record_format(self, domain, slug):
        """
        **Feature: advanced-tenant-management, Property 15: DNS Record Generation**
        **Validates: Requirements 9.4**

        For any custom domain, the TXT record SHALL have the correct format
        with verification prefix and contain a valid verification token.
        """
        service = DomainService()

        # Create a test tenant
        with bypass_rls():
            tenant = Tenant.objects.create(
                id=uuid.uuid4(),
                company_name=f"Test Company {slug}",
                slug=slug,
                status=Tenant.ACTIVE,
            )

        try:
            # Get DNS verification records
            dns_records = service.get_dns_verification_records(domain, tenant)
            txt = dns_records["txt"]
            verification_token = dns_records["verification_token"]

            # Property: TXT name must start with verification prefix
            expected_txt_name = f"{service.DNS_TXT_PREFIX}.{domain}"
            assert txt["name"] == expected_txt_name, f"TXT name must be '{expected_txt_name}'"

            # Property: TXT value must contain verification token
            expected_txt_value = f"jewelry-verify={verification_token}"
            assert (
                txt["value"] == expected_txt_value
            ), f"TXT value must be 'jewelry-verify={{token}}'"

            # Property: TXT value must start with 'jewelry-verify='
            assert txt["value"].startswith(
                "jewelry-verify="
            ), "TXT value must start with 'jewelry-verify='"

            # Property: TXT full_record must contain all components
            full_record = txt["full_record"]
            assert (
                service.DNS_TXT_PREFIX in full_record
            ), f"TXT full_record must contain prefix '{service.DNS_TXT_PREFIX}'"
            assert domain in full_record, f"TXT full_record must contain domain '{domain}'"
            assert "TXT" in full_record, "TXT full_record must contain 'TXT' keyword"
            assert (
                verification_token in full_record
            ), "TXT full_record must contain verification token"

        finally:
            # Cleanup
            with bypass_rls():
                tenant.delete()

    @given(
        domain=valid_custom_domain_strategy(),
        slug=valid_slug_strategy,
    )
    @hypothesis_settings(max_examples=100)
    def test_verification_token_validity(self, domain, slug):
        """
        **Feature: advanced-tenant-management, Property 15: DNS Record Generation**
        **Validates: Requirements 9.4**

        For any custom domain, the verification token SHALL be a valid
        hexadecimal string of the expected length (64 characters for 32-byte token).
        """
        service = DomainService()

        # Create a test tenant
        with bypass_rls():
            tenant = Tenant.objects.create(
                id=uuid.uuid4(),
                company_name=f"Test Company {slug}",
                slug=slug,
                status=Tenant.ACTIVE,
            )

        try:
            # Get DNS verification records
            dns_records = service.get_dns_verification_records(domain, tenant)
            verification_token = dns_records["verification_token"]

            # Property: Token must be a string
            assert isinstance(verification_token, str), "Verification token must be a string"

            # Property: Token must be non-empty
            assert len(verification_token) > 0, "Verification token must not be empty"

            # Property: Token must be valid hexadecimal
            # token_hex(32) produces 64 hex characters
            expected_length = service.VERIFICATION_TOKEN_LENGTH * 2
            assert is_valid_hex_token(
                verification_token, expected_length
            ), f"Verification token must be a valid hex string of length {expected_length}"

            # Property: Token must only contain hex characters (0-9, a-f)
            assert re.match(
                r"^[0-9a-f]+$", verification_token
            ), "Verification token must only contain hexadecimal characters"

        finally:
            # Cleanup
            with bypass_rls():
                tenant.delete()

    @given(
        domain=valid_custom_domain_strategy(),
        slug=valid_slug_strategy,
    )
    @hypothesis_settings(max_examples=50, deadline=None)
    def test_dns_records_consistency_with_tenant_domain(self, domain, slug):
        """
        **Feature: advanced-tenant-management, Property 15: DNS Record Generation**
        **Validates: Requirements 9.4**

        For any custom domain with an existing TenantDomain record, calling
        get_dns_verification_records() multiple times SHALL return the same
        verification token (consistency).
        """
        service = DomainService()

        # Create a test tenant
        with bypass_rls():
            tenant = Tenant.objects.create(
                id=uuid.uuid4(),
                company_name=f"Test Company {slug}",
                slug=slug,
                status=Tenant.ACTIVE,
            )

        try:
            # Create a TenantDomain record with a verification token
            initial_token = service.generate_verification_token()
            with bypass_rls():
                tenant_domain = TenantDomain.objects.create(
                    tenant=tenant,
                    domain_type=TenantDomain.DOMAIN_TYPE_CUSTOM,
                    domain=domain,
                    is_primary=False,
                    verification_status=TenantDomain.VERIFICATION_PENDING,
                    verification_token=initial_token,
                )

            # Get DNS records first time
            dns_records_1 = service.get_dns_verification_records(domain, tenant)
            token_1 = dns_records_1["verification_token"]

            # Get DNS records second time
            dns_records_2 = service.get_dns_verification_records(domain, tenant)
            token_2 = dns_records_2["verification_token"]

            # Property: Token must be consistent across calls
            assert token_1 == token_2, "Verification token must be consistent across multiple calls"

            # Property: Token must match the stored token
            assert (
                token_1 == initial_token
            ), "Verification token must match the stored TenantDomain token"

            # Property: CNAME records must be identical
            assert (
                dns_records_1["cname"] == dns_records_2["cname"]
            ), "CNAME records must be identical across calls"

            # Property: TXT records must be identical
            assert (
                dns_records_1["txt"] == dns_records_2["txt"]
            ), "TXT records must be identical across calls"

        finally:
            # Cleanup
            with bypass_rls():
                TenantDomain.objects.filter(tenant=tenant).delete()
                tenant.delete()

    @given(
        domain1=valid_custom_domain_strategy(),
        domain2=valid_custom_domain_strategy(),
        slug=valid_slug_strategy,
    )
    @hypothesis_settings(max_examples=50, deadline=None)
    def test_different_domains_produce_different_records(self, domain1, domain2, slug):
        """
        **Feature: advanced-tenant-management, Property 15: DNS Record Generation**
        **Validates: Requirements 9.4**

        For any two different custom domains, the DNS records SHALL be different
        (different TXT names, different verification tokens).
        """
        # Skip if domains are the same
        assume(domain1 != domain2)

        service = DomainService()

        # Create a test tenant
        with bypass_rls():
            tenant = Tenant.objects.create(
                id=uuid.uuid4(),
                company_name=f"Test Company {slug}",
                slug=slug,
                status=Tenant.ACTIVE,
            )

        try:
            # Get DNS records for first domain
            dns_records_1 = service.get_dns_verification_records(domain1, tenant)

            # Get DNS records for second domain
            dns_records_2 = service.get_dns_verification_records(domain2, tenant)

            # Property: CNAME names must be different
            assert (
                dns_records_1["cname"]["name"] != dns_records_2["cname"]["name"]
            ), "Different domains must have different CNAME names"

            # Property: TXT names must be different
            assert (
                dns_records_1["txt"]["name"] != dns_records_2["txt"]["name"]
            ), "Different domains must have different TXT names"

            # Property: Verification tokens must be different
            # (unless they happen to collide, which is astronomically unlikely)
            assert (
                dns_records_1["verification_token"] != dns_records_2["verification_token"]
            ), "Different domains should have different verification tokens"

            # Property: TXT values must be different (different tokens)
            assert (
                dns_records_1["txt"]["value"] != dns_records_2["txt"]["value"]
            ), "Different domains must have different TXT values"

        finally:
            # Cleanup
            with bypass_rls():
                tenant.delete()

    @given(
        domain=valid_custom_domain_strategy(),
        slug=valid_slug_strategy,
    )
    @hypothesis_settings(max_examples=100)
    def test_dns_records_enable_verification(self, domain, slug):
        """
        **Feature: advanced-tenant-management, Property 15: DNS Record Generation**
        **Validates: Requirements 9.4**

        For any custom domain, the generated DNS records SHALL contain all
        information necessary to configure DNS and enable verification.
        """
        service = DomainService()

        # Create a test tenant
        with bypass_rls():
            tenant = Tenant.objects.create(
                id=uuid.uuid4(),
                company_name=f"Test Company {slug}",
                slug=slug,
                status=Tenant.ACTIVE,
            )

        try:
            # Get DNS verification records
            dns_records = service.get_dns_verification_records(domain, tenant)

            # Property: CNAME record must have description
            assert (
                len(dns_records["cname"]["description"]) > 0
            ), "CNAME record must have a non-empty description"

            # Property: TXT record must have description
            assert (
                len(dns_records["txt"]["description"]) > 0
            ), "TXT record must have a non-empty description"

            # Property: CNAME full_record must be a complete DNS record
            cname_full = dns_records["cname"]["full_record"]
            assert "." in cname_full, "CNAME full_record must be a complete DNS record with dots"

            # Property: TXT full_record must be a complete DNS record
            txt_full = dns_records["txt"]["full_record"]
            assert "." in txt_full, "TXT full_record must be a complete DNS record with dots"

            # Property: Records must contain all components needed for DNS configuration
            # CNAME: domain -> BASE_DOMAIN
            assert domain in cname_full, "CNAME full_record must contain the domain"
            assert service.base_domain in cname_full, "CNAME full_record must contain BASE_DOMAIN"

            # TXT: _jewelry-verify.domain -> "jewelry-verify={token}"
            assert (
                service.DNS_TXT_PREFIX in txt_full
            ), "TXT full_record must contain verification prefix"
            assert domain in txt_full, "TXT full_record must contain the domain"
            assert (
                dns_records["verification_token"] in txt_full
            ), "TXT full_record must contain the verification token"

        finally:
            # Cleanup
            with bypass_rls():
                tenant.delete()
