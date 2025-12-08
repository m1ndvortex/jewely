"""
Tests for DNS verification instructions display.

This test verifies that DNS verification instructions are properly displayed
for custom domains in the tenant detail view.

Requirements: 9.4, 9.5
"""

from django.test import Client, TestCase
from django.urls import reverse

import pytest

from apps.core.models import Tenant, TenantDomain, TenantSettings, User


@pytest.mark.django_db
class TestDNSVerificationDisplay(TestCase):
    """Test DNS verification instructions display in tenant detail view."""

    def setUp(self):
        """Set up test data."""
        # Create platform admin user with unique username
        import uuid

        unique_id = str(uuid.uuid4())[:8]
        self.admin_user = User.objects.create_user(
            username=f"admin_{unique_id}",
            email=f"admin_{unique_id}@example.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
            is_staff=True,
            is_superuser=True,
        )

        # Create test tenant
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

        # Create tenant settings
        TenantSettings.objects.create(tenant=self.tenant)

        # Create subdomain (auto-verified)
        self.subdomain = TenantDomain.objects.create(
            tenant=self.tenant,
            domain_type=TenantDomain.DOMAIN_TYPE_SUBDOMAIN,
            domain="test-shop.jewelry-shop.local",
            is_primary=True,
            verification_status=TenantDomain.VERIFICATION_VERIFIED,
        )

        # Create custom domain (pending verification)
        self.custom_domain = TenantDomain.objects.create(
            tenant=self.tenant,
            domain_type=TenantDomain.DOMAIN_TYPE_CUSTOM,
            domain="shop.example.com",
            is_primary=False,
            verification_status=TenantDomain.VERIFICATION_PENDING,
            verification_token="test-token-123",
        )

        self.client = Client()
        self.client.force_login(self.admin_user)

    def test_dns_verification_instructions_displayed(self):
        """
        Test that DNS verification instructions are displayed for pending custom domains.

        Requirements: 9.4, 9.5
        """
        url = reverse("core:admin_tenant_detail", kwargs={"pk": self.tenant.id})
        response = self.client.get(url + "?tab=info")

        self.assertEqual(response.status_code, 200)

        # Check that custom domain is displayed
        self.assertContains(response, "shop.example.com")

        # Check that verification status is shown
        self.assertContains(response, "Pending Verification")

        # Check that DNS configuration section is present
        self.assertContains(response, "DNS Configuration Required")

        # Check that CNAME record instructions are present
        self.assertContains(response, "CNAME Record")
        self.assertContains(response, "CNAME")

        # Check that TXT record instructions are present
        self.assertContains(response, "TXT Verification Record")
        self.assertContains(response, "TXT")

        # Check that verification token is displayed
        self.assertContains(response, "jewelry-verify=")

        # Check that help text is present
        self.assertContains(response, "DNS changes may take up to 48 hours")

    def test_dns_instructions_not_shown_for_verified_domains(self):
        """
        Test that DNS instructions are not shown for verified domains.

        Requirements: 9.5
        """
        # Mark custom domain as verified
        self.custom_domain.verification_status = TenantDomain.VERIFICATION_VERIFIED
        self.custom_domain.save()

        url = reverse("core:admin_tenant_detail", kwargs={"pk": self.tenant.id})
        response = self.client.get(url + "?tab=info")

        self.assertEqual(response.status_code, 200)

        # Check that custom domain is displayed
        self.assertContains(response, "shop.example.com")

        # Check that verification status shows verified
        self.assertContains(response, "Verified")

        # Check that DNS configuration section is NOT present
        self.assertNotContains(response, "DNS Configuration Required")

    def test_dns_records_in_context(self):
        """
        Test that DNS records are properly included in the view context.

        Requirements: 9.4
        """
        url = reverse("core:admin_tenant_detail", kwargs={"pk": self.tenant.id})
        response = self.client.get(url + "?tab=info")

        self.assertEqual(response.status_code, 200)

        # Check that custom_domains_with_dns is in context
        self.assertIn("custom_domains_with_dns", response.context)

        custom_domains_with_dns = response.context["custom_domains_with_dns"]
        self.assertEqual(len(custom_domains_with_dns), 1)

        # Check DNS records structure
        domain_data = custom_domains_with_dns[0]
        self.assertIn("domain", domain_data)
        self.assertIn("dns_records", domain_data)

        dns_records = domain_data["dns_records"]
        self.assertIn("cname", dns_records)
        self.assertIn("txt", dns_records)

        # Verify CNAME record structure
        cname = dns_records["cname"]
        self.assertIn("name", cname)
        self.assertIn("type", cname)
        self.assertIn("value", cname)
        self.assertIn("description", cname)
        self.assertIn("full_record", cname)
        self.assertEqual(cname["type"], "CNAME")

        # Verify TXT record structure
        txt = dns_records["txt"]
        self.assertIn("name", txt)
        self.assertIn("type", txt)
        self.assertIn("value", txt)
        self.assertIn("description", txt)
        self.assertIn("full_record", txt)
        self.assertEqual(txt["type"], "TXT")
        self.assertIn("jewelry-verify=", txt["value"])

    def test_subdomain_no_dns_instructions(self):
        """
        Test that subdomains don't show DNS instructions (auto-verified).

        Requirements: 9.1
        """
        url = reverse("core:admin_tenant_detail", kwargs={"pk": self.tenant.id})
        response = self.client.get(url + "?tab=info")

        self.assertEqual(response.status_code, 200)

        # Check that subdomain is displayed
        self.assertContains(response, "test-shop.jewelry-shop.local")

        # Check that subdomain shows as verified
        self.assertContains(response, "Verified")

        # Subdomain should not have DNS configuration section
        # (only custom domains with pending status show DNS instructions)

    def test_verify_now_button_displayed(self):
        """
        Test that 'Verify Now' button is displayed for pending domains.

        Requirements: 9.3
        """
        url = reverse("core:admin_tenant_detail", kwargs={"pk": self.tenant.id})
        response = self.client.get(url + "?tab=info")

        self.assertEqual(response.status_code, 200)

        # Check that Verify Now button is present
        self.assertContains(response, "Verify Now")
        self.assertContains(response, f"verifyDomain('{self.custom_domain.id}')")

    def test_copy_buttons_present(self):
        """
        Test that copy buttons are present for DNS records.

        Requirements: 9.4
        """
        url = reverse("core:admin_tenant_detail", kwargs={"pk": self.tenant.id})
        response = self.client.get(url + "?tab=info")

        self.assertEqual(response.status_code, 200)

        # Check that copy buttons are present
        self.assertContains(response, "copyToClipboard")

        # Should have copy buttons for:
        # 1. Domain URL
        # 2. CNAME record
        # 3. TXT record
        copy_count = response.content.decode().count("copyToClipboard")
        self.assertGreaterEqual(copy_count, 3)
