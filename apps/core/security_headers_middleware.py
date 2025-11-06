"""
Security Headers Middleware for comprehensive security header management.

This middleware adds Content Security Policy (CSP) and other security headers
to all responses to protect against XSS, clickjacking, and other attacks.

Requirement 25: Security Hardening and Compliance
"""

import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware:
    """
    Middleware to add comprehensive security headers to all responses.

    Headers added:
    - Content-Security-Policy: Prevents XSS and other injection attacks
    - Referrer-Policy: Controls referrer information
    - Permissions-Policy: Controls browser features

    Note: Other security headers (HSTS, X-Frame-Options, X-Content-Type-Options)
    are handled by Django's SecurityMiddleware and settings.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Add Content Security Policy
        response = self._add_csp_header(response)

        # Add Referrer Policy
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Add Permissions Policy (formerly Feature-Policy)
        response["Permissions-Policy"] = self._get_permissions_policy()

        return response

    def _add_csp_header(self, response):
        """
        Add Content Security Policy header.

        CSP is configured to work with our tech stack:
        - HTMX: Requires 'unsafe-inline' for inline event handlers
        - Alpine.js: Requires 'unsafe-eval' for reactive expressions
        - Chart.js: Loaded from CDN
        - Tailwind CSS: Inline styles need 'unsafe-inline'

        In production, consider using nonces or hashes instead of 'unsafe-inline'.
        """
        csp_directives = [
            "default-src 'self'",
            # Scripts: Allow self, CDNs, and inline scripts (for HTMX/Alpine.js)
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://unpkg.com https://cdnjs.cloudflare.com",
            # Styles: Allow self, CDNs, and inline styles (for Tailwind)
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com https://cdnjs.cloudflare.com https://fonts.googleapis.com",
            # Fonts: Allow self and Google Fonts
            "font-src 'self' https://fonts.gstatic.com data:",
            # Images: Allow self, data URIs, and blob URIs (for charts/uploads)
            "img-src 'self' data: blob: https:",
            # Connect: Allow self and API endpoints
            "connect-src 'self'",
            # Media: Allow self
            "media-src 'self'",
            # Objects: Disallow plugins
            "object-src 'none'",
            # Base URI: Restrict to self
            "base-uri 'self'",
            # Forms: Allow self
            "form-action 'self'",
            # Frame ancestors: Deny (prevent clickjacking)
            "frame-ancestors 'none'",
            # Upgrade insecure requests in production
            "upgrade-insecure-requests",
        ]

        response["Content-Security-Policy"] = "; ".join(csp_directives)
        return response

    def _get_permissions_policy(self):
        """
        Get Permissions Policy header value.

        This controls which browser features can be used.
        We disable most features except what we need.
        """
        policies = [
            "geolocation=()",  # Disable geolocation
            "microphone=()",  # Disable microphone
            "camera=()",  # Disable camera
            "payment=(self)",  # Allow payment APIs on same origin
            "usb=()",  # Disable USB
            "magnetometer=()",  # Disable magnetometer
            "gyroscope=()",  # Disable gyroscope
            "accelerometer=()",  # Disable accelerometer
        ]

        return ", ".join(policies)
