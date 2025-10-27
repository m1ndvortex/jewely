"""
Security middleware for IP blocking and brute force protection.

This middleware checks incoming requests against flagged IPs and
enforces brute force protection before allowing access to login endpoints.
"""

import logging

from django.http import HttpResponseForbidden, JsonResponse
from django.urls import resolve

from apps.core.audit import get_client_ip
from apps.core.security_monitoring import BruteForceProtection, IPTracker

logger = logging.getLogger(__name__)


class SecurityMiddleware:
    """
    Middleware to enforce security policies.

    - Blocks requests from flagged IP addresses
    - Enforces brute force protection on login endpoints
    """

    # Login endpoints to protect
    LOGIN_ENDPOINTS = [
        "token_obtain_pair",
        "login",
        "account_login",
        "api_auth_login",
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Get client IP
        ip_address = get_client_ip(request)

        # Check if IP is flagged
        blocked_response = self._check_flagged_ip(request, ip_address)
        if blocked_response:
            return blocked_response

        # Check brute force protection for login endpoints
        blocked_response = self._check_brute_force_protection(request, ip_address)
        if blocked_response:
            return blocked_response

        response = self.get_response(request)
        return response

    def _check_flagged_ip(self, request, ip_address):
        """Check if IP is flagged and return blocked response if needed."""
        if not ip_address or not IPTracker.is_ip_flagged(ip_address):
            return None

        metadata = IPTracker.get_ip_metadata(ip_address)
        reason = (
            metadata.get("reason", "IP address has been flagged")
            if metadata
            else "IP address has been flagged"
        )

        logger.warning(f"Blocked request from flagged IP {ip_address}: {reason}")

        # Return 403 Forbidden
        if request.path.startswith("/api/"):
            return JsonResponse(
                {
                    "error": "Access Denied",
                    "message": "Your IP address has been temporarily blocked due to suspicious activity.",
                    "reason": reason,
                },
                status=403,
            )
        else:
            return HttpResponseForbidden(
                f"<h1>Access Denied</h1><p>Your IP address has been temporarily blocked due to suspicious activity.</p><p>Reason: {reason}</p>"
            )

    def _check_brute_force_protection(self, request, ip_address):
        """Check brute force protection for login endpoints."""
        try:
            resolved = resolve(request.path)
            if resolved.url_name not in self.LOGIN_ENDPOINTS:
                return None

            # Check username-based lockout
            username = request.POST.get("username") or request.POST.get("email")
            if username and BruteForceProtection.is_locked_out(username):
                return self._create_lockout_response(
                    request, username, ip_address, is_user=True
                )

            # Check IP-based lockout
            if ip_address and BruteForceProtection.is_locked_out(ip_address):
                return self._create_lockout_response(
                    request, ip_address, ip_address, is_user=False
                )

        except Exception as e:
            # Don't let middleware errors break the application
            logger.debug(f"Error in security middleware: {e}")

        return None

    def _create_lockout_response(self, request, identifier, ip_address, is_user=True):
        """Create a lockout response."""
        lockout_info = BruteForceProtection.get_lockout_info(identifier)

        if is_user:
            logger.warning(
                f"Blocked login attempt for locked out user {identifier} from IP {ip_address}"
            )
            error_msg = "Account Locked"
            user_msg = "Too many failed login attempts. Please try again later."
            html_msg = "<h1>Account Temporarily Locked</h1><p>Too many failed login attempts. Please try again later.</p>"
        else:
            logger.warning(f"Blocked login attempt from locked out IP {ip_address}")
            error_msg = "Too Many Attempts"
            user_msg = "Too many failed login attempts from your IP address. Please try again later."
            html_msg = "<h1>Too Many Attempts</h1><p>Too many failed login attempts from your IP address. Please try again later.</p>"

        if request.path.startswith("/api/"):
            return JsonResponse(
                {
                    "error": error_msg,
                    "message": user_msg,
                    "lockout_info": lockout_info,
                },
                status=429,
            )
        else:
            return HttpResponseForbidden(html_msg)
