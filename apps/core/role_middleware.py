"""
Role-based access control middleware.

This middleware ensures that:
1. Platform admins can only access /platform/* URLs
2. Tenant users can only access tenant-specific URLs
3. Users are redirected to appropriate dashboards
"""

from django.shortcuts import redirect
from django.urls import resolve


class RoleBasedAccessMiddleware:
    """
    Middleware to enforce role-based access control.

    Platform admins should only access /platform/* URLs.
    Tenant users should not access /platform/* URLs.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # URLs that don't require role checking
        self.exempt_urls = [
            "accounts",  # allauth URLs
            "hijack",  # impersonation
            "admin",  # Django admin
            "health",  # health check
            "metrics",  # Prometheus metrics
            "static",  # static files
            "media",  # media files
            "api/auth",  # authentication API
        ]

    def __call__(self, request):
        # Skip middleware for unauthenticated users
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Skip middleware for exempt URLs
        path = request.path
        if any(
            path.startswith(f"/{exempt}/") or path == f"/{exempt}" for exempt in self.exempt_urls
        ):
            return self.get_response(request)

        # Skip for root path
        if path == "/":
            return self.get_response(request)

        # Get the resolved URL
        try:
            resolved = resolve(path)
        except Exception:
            return self.get_response(request)

        # Check if user is accessing platform admin area
        is_platform_url = path.startswith("/platform/")

        # Platform admin trying to access tenant area
        if request.user.is_platform_admin() and not is_platform_url:
            # Allow access to logout and profile
            if resolved.url_name in [
                "account_logout",
                "user_profile",
                "language_switch",
                "theme_switch",
            ]:
                return self.get_response(request)
            # Redirect to platform dashboard
            return redirect("core:admin_dashboard")

        # Tenant user trying to access platform admin area
        if not request.user.is_platform_admin() and is_platform_url:
            # Redirect to tenant dashboard
            return redirect("core:tenant_dashboard")

        # Tenant user without tenant access
        if not request.user.is_platform_admin() and not request.user.has_tenant_access():
            # User has no tenant - should not happen, but handle gracefully
            return redirect("account_logout")

        return self.get_response(request)
