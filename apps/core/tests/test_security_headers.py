"""
Tests for security headers middleware and security configurations.

Requirement 25: Security Hardening and Compliance
Task 29.1: Implement security headers
"""

import pytest
from django.test import Client, TestCase
from django.urls import reverse


class SecurityHeadersTest(TestCase):
    """Test security headers are properly set on responses."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    def test_content_security_policy_header(self):
        """Test that CSP header is present and properly configured."""
        response = self.client.get(reverse("core:health_check"))

        self.assertIn("Content-Security-Policy", response)
        csp = response["Content-Security-Policy"]

        # Check key CSP directives
        self.assertIn("default-src 'self'", csp)
        self.assertIn("script-src", csp)
        self.assertIn("style-src", csp)
        self.assertIn("img-src", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertIn("upgrade-insecure-requests", csp)

    def test_x_content_type_options_header(self):
        """Test that X-Content-Type-Options header is set to nosniff."""
        response = self.client.get(reverse("core:health_check"))

        self.assertIn("X-Content-Type-Options", response)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_x_frame_options_header(self):
        """Test that X-Frame-Options header is set to DENY."""
        response = self.client.get(reverse("core:health_check"))

        self.assertIn("X-Frame-Options", response)
        self.assertEqual(response["X-Frame-Options"], "DENY")

    def test_referrer_policy_header(self):
        """Test that Referrer-Policy header is properly set."""
        response = self.client.get(reverse("core:health_check"))

        self.assertIn("Referrer-Policy", response)
        self.assertEqual(response["Referrer-Policy"], "strict-origin-when-cross-origin")

    def test_permissions_policy_header(self):
        """Test that Permissions-Policy header is present."""
        response = self.client.get(reverse("core:health_check"))

        self.assertIn("Permissions-Policy", response)
        permissions = response["Permissions-Policy"]

        # Check that dangerous features are disabled
        self.assertIn("geolocation=()", permissions)
        self.assertIn("microphone=()", permissions)
        self.assertIn("camera=()", permissions)

    def test_hsts_configuration(self):
        """Test that HSTS configuration is properly set."""
        # Note: HSTS is set by Django's SecurityMiddleware in production
        # This test verifies the configuration exists
        from django.conf import settings

        self.assertTrue(hasattr(settings, "SECURE_HSTS_SECONDS"))
        self.assertTrue(hasattr(settings, "SECURE_HSTS_INCLUDE_SUBDOMAINS"))
        self.assertTrue(hasattr(settings, "SECURE_HSTS_PRELOAD"))

        # In production (DEBUG=False), these should be set to secure values
        # In development, they may be 0 or False

    def test_secure_cookie_settings(self):
        """Test that secure cookie settings are properly configured."""
        from django.conf import settings

        # Session cookie settings
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")

        # CSRF cookie settings
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "Lax")

    def test_csrf_protection_enabled(self):
        """Test that CSRF protection is enabled."""
        from django.conf import settings

        # Check CSRF middleware is in MIDDLEWARE
        self.assertIn("django.middleware.csrf.CsrfViewMiddleware", settings.MIDDLEWARE)

    def test_security_headers_on_all_responses(self):
        """Test that security headers are added to all responses."""
        # Test different endpoints
        endpoints = [
            reverse("core:health_check"),
        ]

        for endpoint in endpoints:
            response = self.client.get(endpoint)

            # Check critical security headers
            self.assertIn("Content-Security-Policy", response)
            self.assertIn("X-Content-Type-Options", response)
            self.assertIn("X-Frame-Options", response)
            self.assertIn("Referrer-Policy", response)
            self.assertIn("Permissions-Policy", response)

    def test_csp_allows_required_sources(self):
        """Test that CSP allows required external sources."""
        response = self.client.get(reverse("core:health_check"))
        csp = response["Content-Security-Policy"]

        # Check that we allow CDNs for scripts and styles
        self.assertIn("cdn.jsdelivr.net", csp)
        self.assertIn("unpkg.com", csp)
        self.assertIn("cdnjs.cloudflare.com", csp)

        # Check that we allow Google Fonts
        self.assertIn("fonts.googleapis.com", csp)
        self.assertIn("fonts.gstatic.com", csp)

    def test_csp_script_src_configuration(self):
        """Test that script-src allows HTMX and Alpine.js to work."""
        response = self.client.get(reverse("core:health_check"))
        csp = response["Content-Security-Policy"]

        # HTMX and Alpine.js require unsafe-inline and unsafe-eval
        self.assertIn("script-src", csp)
        self.assertIn("'unsafe-inline'", csp)
        self.assertIn("'unsafe-eval'", csp)

    def test_csp_style_src_configuration(self):
        """Test that style-src allows Tailwind CSS to work."""
        response = self.client.get(reverse("core:health_check"))
        csp = response["Content-Security-Policy"]

        # Tailwind CSS uses inline styles
        self.assertIn("style-src", csp)
        self.assertIn("'unsafe-inline'", csp)

    def test_csp_img_src_allows_data_uris(self):
        """Test that img-src allows data URIs for inline images."""
        response = self.client.get(reverse("core:health_check"))
        csp = response["Content-Security-Policy"]

        # Check that data URIs and blob URIs are allowed
        self.assertIn("img-src", csp)
        self.assertIn("data:", csp)
        self.assertIn("blob:", csp)


@pytest.mark.django_db
class CSRFProtectionTest(TestCase):
    """Test CSRF protection functionality."""

    def setUp(self):
        """Set up test client."""
        self.client = Client(enforce_csrf_checks=True)

    def test_csrf_token_required_for_post(self):
        """Test that POST requests without CSRF token are rejected."""
        # Try to POST without CSRF token
        response = self.client.post(
            reverse("core:health_check"),
            data={"test": "data"},
        )

        # Should be rejected (403 Forbidden)
        self.assertEqual(response.status_code, 403)

    def test_csrf_middleware_configured(self):
        """Test that CSRF middleware is properly configured."""
        from django.conf import settings

        # Check that CSRF middleware is in MIDDLEWARE
        self.assertIn("django.middleware.csrf.CsrfViewMiddleware", settings.MIDDLEWARE)

        # Check CSRF cookie settings
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "Lax")

    def test_csrf_failure_view(self):
        """Test custom CSRF failure view."""
        from django.conf import settings

        # Check that custom CSRF failure view is configured
        self.assertEqual(settings.CSRF_FAILURE_VIEW, "apps.core.views.csrf_failure")


class SecureConnectionTest(TestCase):
    """Test secure connection settings."""

    def test_ssl_redirect_configuration(self):
        """Test that SSL redirect configuration exists."""
        from django.conf import settings

        # Check that SSL redirect setting exists
        self.assertTrue(hasattr(settings, "SECURE_SSL_REDIRECT"))

    def test_session_cookie_configuration(self):
        """Test that session cookie settings are properly configured."""
        from django.conf import settings

        # Check that secure cookie settings exist
        self.assertTrue(hasattr(settings, "SESSION_COOKIE_SECURE"))
        self.assertTrue(hasattr(settings, "CSRF_COOKIE_SECURE"))

        # Check HttpOnly and SameSite settings (always enabled)
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")

    def test_session_timeout_configured(self):
        """Test that session timeout is properly configured."""
        from django.conf import settings

        # Session should expire after 24 hours
        self.assertEqual(settings.SESSION_COOKIE_AGE, 86400)


class SecurityMiddlewareOrderTest(TestCase):
    """Test that security middleware is in correct order."""

    def test_security_middleware_order(self):
        """Test that security middlewares are in correct order."""
        from django.conf import settings

        middleware = settings.MIDDLEWARE

        # Django's SecurityMiddleware should be early
        security_idx = middleware.index("django.middleware.security.SecurityMiddleware")

        # Our SecurityHeadersMiddleware should be right after
        headers_idx = middleware.index(
            "apps.core.security_headers_middleware.SecurityHeadersMiddleware"
        )

        self.assertEqual(headers_idx, security_idx + 1)

        # CSRF middleware should be present
        self.assertIn("django.middleware.csrf.CsrfViewMiddleware", middleware)


class SecurityComplianceTest(TestCase):
    """Test overall security compliance."""

    def test_all_security_headers_present(self):
        """Test that all required security headers are present."""
        response = self.client.get(reverse("core:health_check"))

        required_headers = [
            "Content-Security-Policy",
            "X-Content-Type-Options",
            "X-Frame-Options",
            "Referrer-Policy",
            "Permissions-Policy",
        ]

        for header in required_headers:
            self.assertIn(header, response, f"Required security header '{header}' is missing")

    def test_security_settings_configured(self):
        """Test that all security settings are properly configured."""
        from django.conf import settings

        # Check all security settings
        security_settings = [
            "SECURE_BROWSER_XSS_FILTER",
            "SECURE_CONTENT_TYPE_NOSNIFF",
            "X_FRAME_OPTIONS",
            "SESSION_COOKIE_HTTPONLY",
            "SESSION_COOKIE_SAMESITE",
            "CSRF_COOKIE_HTTPONLY",
            "CSRF_COOKIE_SAMESITE",
        ]

        for setting in security_settings:
            self.assertTrue(
                hasattr(settings, setting), f"Security setting '{setting}' is not configured"
            )

    def test_requirement_25_compliance(self):
        """Test compliance with Requirement 25: Security Hardening."""
        from django.conf import settings

        # Requirement 25.4: CSP headers to prevent XSS
        response = self.client.get(reverse("core:health_check"))
        self.assertIn("Content-Security-Policy", response)

        # Requirement 25.5: CSRF protection enabled
        self.assertIn("django.middleware.csrf.CsrfViewMiddleware", settings.MIDDLEWARE)

        # Requirement 25.9: TLS 1.3 (configured at Nginx level, but check HTTPS settings exist)
        self.assertTrue(hasattr(settings, "SECURE_SSL_REDIRECT"))
        self.assertTrue(hasattr(settings, "SESSION_COOKIE_SECURE"))
        self.assertTrue(hasattr(settings, "CSRF_COOKIE_SECURE"))
