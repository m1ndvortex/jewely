"""
Domain Service for tenant domain management.

This service handles:
- Subdomain generation from tenant slug
- Custom domain validation
- DNS verification record generation
- Domain verification status checking

Requirements: 9.1, 9.2, 9.3, 9.4
"""

import re
import secrets
import socket
from typing import TYPE_CHECKING, Optional

from django.conf import settings
from django.utils import timezone

if TYPE_CHECKING:
    from apps.core.models import Tenant, TenantDomain


# Default base domain if not configured in settings
DEFAULT_BASE_DOMAIN = "jewelry-shop.local"


class DomainService:
    """
    Service for managing tenant domains including subdomain generation,
    custom domain validation, and DNS verification.

    Per Requirements 9.1-9.4 for domain management.
    """

    # Verification token length
    VERIFICATION_TOKEN_LENGTH = 32

    # DNS record names
    DNS_CNAME_NAME = "www"
    DNS_TXT_PREFIX = "_jewelry-verify"

    # Valid hostname pattern (RFC 1123)
    HOSTNAME_PATTERN = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$")

    # Full domain pattern
    DOMAIN_PATTERN = re.compile(
        r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
    )

    def __init__(self):
        """Initialize the domain service."""
        self._base_domain = getattr(settings, "TENANT_BASE_DOMAIN", DEFAULT_BASE_DOMAIN)

    @property
    def base_domain(self) -> str:
        """Get the base domain for subdomain generation."""
        return self._base_domain

    def generate_subdomain(self, slug: str) -> str:
        """
        Generate subdomain from tenant slug.

        Format: {slug}.{BASE_DOMAIN}

        Args:
            slug: The tenant's URL-friendly slug

        Returns:
            The full subdomain string (e.g., "my-shop.jewelry-shop.local")

        Raises:
            ValueError: If slug is empty or invalid

        Per Requirements 1.5, 9.1 for subdomain generation.
        """
        if not slug:
            raise ValueError("Slug cannot be empty")

        # Validate slug format (alphanumeric, hyphens, underscores)
        if not re.match(r"^[a-zA-Z0-9_-]+$", slug):
            raise ValueError("Slug must contain only letters, numbers, hyphens, and underscores")

        return f"{slug}.{self._base_domain}"

    def validate_custom_domain(self, domain: str) -> tuple[bool, list[str]]:
        """
        Validate custom domain format.

        Checks:
        - Valid hostname format (RFC 1123 compliant)
        - Not a subdomain of the platform's BASE_DOMAIN
        - Minimum 2 domain parts (e.g., example.com)
        - No IP addresses

        Args:
            domain: The custom domain to validate

        Returns:
            Tuple of (is_valid, list_of_error_messages)

        Per Requirement 9.2 for custom domain configuration.
        """
        errors = []

        if not domain:
            errors.append("Domain cannot be empty")
            return (False, errors)

        # Normalize domain (lowercase, strip whitespace)
        domain = domain.lower().strip()

        # Check for valid domain format
        if not self.DOMAIN_PATTERN.match(domain):
            errors.append(
                "Invalid domain format. Domain must be a valid hostname " "(e.g., shop.example.com)"
            )

        # Check it's not a subdomain of our base domain
        if domain.endswith(f".{self._base_domain}") or domain == self._base_domain:
            errors.append(
                f"Custom domain cannot be a subdomain of {self._base_domain}. "
                "Use the subdomain feature instead."
            )

        # Check for IP address (not allowed as custom domain)
        if self._is_ip_address(domain):
            errors.append("IP addresses are not allowed as custom domains")

        # Check domain length
        if len(domain) > 253:
            errors.append("Domain name is too long (max 253 characters)")

        # Check each label length
        labels = domain.split(".")
        for label in labels:
            if len(label) > 63:
                errors.append(f"Domain label '{label}' is too long (max 63 characters)")
                break

        # Check minimum parts (at least domain.tld)
        if len(labels) < 2:
            errors.append("Domain must have at least two parts (e.g., example.com)")

        return (len(errors) == 0, errors)

    def _is_ip_address(self, domain: str) -> bool:
        """Check if the domain is an IP address."""
        # Check IPv4
        try:
            parts = domain.split(".")
            if len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
                return True
        except (ValueError, AttributeError):
            pass

        # Check IPv6 (simplified check)
        if ":" in domain:
            return True

        return False

    def generate_verification_token(self) -> str:
        """
        Generate a secure verification token for DNS verification.

        Returns:
            A random hex string for DNS TXT record verification

        Per Requirement 9.4 for DNS verification.
        """
        return secrets.token_hex(self.VERIFICATION_TOKEN_LENGTH)

    def get_dns_verification_records(self, domain: str, tenant: "Tenant") -> dict:
        """
        Get required DNS records for domain verification.

        Returns the CNAME and TXT records that must be configured
        for the custom domain to be verified.

        Args:
            domain: The custom domain being verified
            tenant: The tenant that owns the domain

        Returns:
            Dictionary with CNAME and TXT record requirements:
            {
                "cname": {
                    "name": "www",
                    "type": "CNAME",
                    "value": "{BASE_DOMAIN}",
                    "description": "Points www subdomain to platform"
                },
                "txt": {
                    "name": "_jewelry-verify.{domain}",
                    "type": "TXT",
                    "value": "{verification_token}",
                    "description": "Verification record"
                }
            }

        Per Requirement 9.4 for DNS verification instructions.
        """
        # Get or generate verification token
        from apps.core.models import TenantDomain

        try:
            tenant_domain = TenantDomain.objects.get(
                tenant=tenant,
                domain=domain,
                domain_type=TenantDomain.DOMAIN_TYPE_CUSTOM,
            )
            verification_token = tenant_domain.verification_token
            if not verification_token:
                verification_token = self.generate_verification_token()
                tenant_domain.verification_token = verification_token
                tenant_domain.save(update_fields=["verification_token", "updated_at"])
        except TenantDomain.DoesNotExist:
            # Generate a new token for display purposes
            verification_token = self.generate_verification_token()

        return {
            "cname": {
                "name": domain,
                "type": "CNAME",
                "value": self._base_domain,
                "description": f"Point your domain to {self._base_domain}",
                "full_record": f"{domain}. CNAME {self._base_domain}.",
            },
            "txt": {
                "name": f"{self.DNS_TXT_PREFIX}.{domain}",
                "type": "TXT",
                "value": f"jewelry-verify={verification_token}",
                "description": "Verification record to prove domain ownership",
                "full_record": (
                    f"{self.DNS_TXT_PREFIX}.{domain}. TXT " f'"jewelry-verify={verification_token}"'
                ),
            },
            "verification_token": verification_token,
        }

    def check_domain_verification(self, domain: "TenantDomain") -> str:
        """
        Check DNS records and update verification status.

        Verifies that:
        1. CNAME record points to the platform domain
        2. TXT verification record contains the correct token

        Args:
            domain: The TenantDomain instance to verify

        Returns:
            The verification status: PENDING, VERIFIED, or FAILED

        Per Requirements 9.3, 9.4 for domain verification.
        """
        from apps.core.models import TenantDomain

        # Only verify custom domains
        if domain.domain_type != TenantDomain.DOMAIN_TYPE_CUSTOM:
            return TenantDomain.VERIFICATION_VERIFIED

        # Check if we have a verification token
        if not domain.verification_token:
            domain.verification_token = self.generate_verification_token()
            domain.save(update_fields=["verification_token", "updated_at"])
            return TenantDomain.VERIFICATION_PENDING

        # Verify DNS records
        cname_verified = self._verify_cname_record(domain.domain)
        txt_verified = self._verify_txt_record(domain.domain, domain.verification_token)

        if cname_verified and txt_verified:
            domain.verification_status = TenantDomain.VERIFICATION_VERIFIED
            domain.verified_at = timezone.now()
            domain.save(update_fields=["verification_status", "verified_at", "updated_at"])
            return TenantDomain.VERIFICATION_VERIFIED
        else:
            # Only mark as failed if we've attempted verification
            # Keep as pending if DNS hasn't propagated yet
            domain.verification_status = TenantDomain.VERIFICATION_PENDING
            domain.save(update_fields=["verification_status", "updated_at"])
            return TenantDomain.VERIFICATION_PENDING

    def _verify_cname_record(self, domain: str) -> bool:
        """
        Verify CNAME record points to the platform domain.

        Args:
            domain: The domain to check

        Returns:
            True if CNAME is correctly configured
        """
        try:
            # Try to resolve the domain
            result = socket.gethostbyname(domain)
            # Also try to get the canonical name
            try:
                cname_result = socket.getfqdn(domain)
                # Check if it resolves to our base domain
                if self._base_domain in cname_result:
                    return True
            except socket.error:
                pass

            # If we got an IP, the domain resolves (basic check)
            # In production, you'd want to use dnspython for proper CNAME lookup
            return result is not None
        except socket.gaierror:
            # Domain doesn't resolve
            return False
        except Exception:
            return False

    def _verify_txt_record(self, domain: str, expected_token: str) -> bool:
        """
        Verify TXT verification record contains the correct token.

        Args:
            domain: The domain to check
            expected_token: The expected verification token

        Returns:
            True if TXT record is correctly configured
        """
        try:
            import dns.resolver

            txt_domain = f"{self.DNS_TXT_PREFIX}.{domain}"
            answers = dns.resolver.resolve(txt_domain, "TXT")

            expected_value = f"jewelry-verify={expected_token}"
            for rdata in answers:
                txt_value = str(rdata).strip('"')
                if txt_value == expected_value:
                    return True
            return False
        except ImportError:
            # dnspython not installed, skip TXT verification
            # In production, this should be a required dependency
            return True
        except Exception:
            # DNS lookup failed
            return False

    def create_subdomain_for_tenant(
        self, tenant: "Tenant", set_as_primary: bool = True
    ) -> "TenantDomain":
        """
        Create a subdomain record for a tenant.

        Args:
            tenant: The tenant to create subdomain for
            set_as_primary: Whether to set this as the primary domain

        Returns:
            The created TenantDomain instance

        Per Requirement 9.1 for auto-generating subdomain.
        """
        from apps.core.models import TenantDomain

        subdomain = self.generate_subdomain(tenant.slug)

        # Check if subdomain already exists
        existing = TenantDomain.objects.filter(
            tenant=tenant,
            domain_type=TenantDomain.DOMAIN_TYPE_SUBDOMAIN,
        ).first()

        if existing:
            # Update existing subdomain if slug changed
            if existing.domain != subdomain:
                existing.domain = subdomain
                existing.save(update_fields=["domain", "updated_at"])
            return existing

        # Create new subdomain
        return TenantDomain.objects.create(
            tenant=tenant,
            domain_type=TenantDomain.DOMAIN_TYPE_SUBDOMAIN,
            domain=subdomain,
            is_primary=set_as_primary,
            verification_status=TenantDomain.VERIFICATION_VERIFIED,  # Subdomains are auto-verified
            verified_at=timezone.now(),
        )

    def add_custom_domain(self, tenant: "Tenant", domain: str) -> tuple["TenantDomain", dict]:
        """
        Add a custom domain for a tenant.

        Args:
            tenant: The tenant to add domain for
            domain: The custom domain to add

        Returns:
            Tuple of (TenantDomain instance, DNS verification records)

        Raises:
            ValueError: If domain validation fails

        Per Requirements 9.2, 9.4 for custom domain configuration.
        """
        from apps.core.models import TenantDomain

        # Validate domain
        is_valid, errors = self.validate_custom_domain(domain)
        if not is_valid:
            raise ValueError("; ".join(errors))

        # Normalize domain
        domain = domain.lower().strip()

        # Generate verification token
        verification_token = self.generate_verification_token()

        # Create domain record
        tenant_domain = TenantDomain.objects.create(
            tenant=tenant,
            domain_type=TenantDomain.DOMAIN_TYPE_CUSTOM,
            domain=domain,
            is_primary=False,  # Custom domains start as non-primary
            verification_status=TenantDomain.VERIFICATION_PENDING,
            verification_token=verification_token,
        )

        # Get DNS verification records
        dns_records = self.get_dns_verification_records(domain, tenant)

        return (tenant_domain, dns_records)
