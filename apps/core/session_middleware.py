"""
Multi-portal session middleware for independent authentication across portals.

This middleware provides session isolation between:
- Django Admin Portal (/admin/) - uses 'sessionid' cookie
- Platform Admin Portal (/platform/) - uses 'platform_sessionid' cookie
- Tenant/Client Portal (/accounts/, /dashboard/) - uses 'tenant_sessionid' cookie

This allows users to be logged into multiple portals simultaneously in the same browser
without session conflicts, similar to how enterprise platforms like AWS, Azure, and GCP
handle multiple admin interfaces.
"""

import logging
from importlib import import_module

from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.utils.cache import patch_vary_headers
from django.utils.http import http_date

logger = logging.getLogger(__name__)


class MultiPortalSessionMiddleware(SessionMiddleware):
    """
    Custom session middleware that uses different session cookies for different portals.

    Portal Types:
    - ADMIN: Django admin interface (/admin/)
    - PLATFORM: Platform admin dashboard (/platform/)
    - TENANT: Client/tenant portal (/accounts/, /dashboard/, and other tenant-facing URLs)

    Each portal type gets its own session cookie, allowing independent authentication.
    """

    # Session cookie names for each portal type
    COOKIE_NAMES = {
        "admin": "sessionid",  # Django admin - keep default for compatibility
        "platform": "platform_sessionid",  # Platform admin portal
        "tenant": "tenant_sessionid",  # Tenant/client portal
    }

    # URL prefixes that determine portal type
    ADMIN_PREFIXES = ["/admin/"]
    PLATFORM_PREFIXES = ["/platform/"]
    # Everything else is tenant portal (including /accounts/, /dashboard/, etc.)

    def get_portal_type(self, path):
        """
        Determine portal type from request path.

        Args:
            path: Request path

        Returns:
            str: 'admin', 'platform', or 'tenant'
        """
        if any(path.startswith(prefix) for prefix in self.ADMIN_PREFIXES):
            return "admin"
        elif any(path.startswith(prefix) for prefix in self.PLATFORM_PREFIXES):
            return "platform"
        else:
            return "tenant"

    def get_session_cookie_name(self, request):
        """
        Get the appropriate session cookie name for this request.

        Args:
            request: HttpRequest object

        Returns:
            str: Cookie name for this portal type
        """
        portal_type = self.get_portal_type(request.path)
        cookie_name = self.COOKIE_NAMES[portal_type]
        logger.debug(f"Portal: {portal_type}, Cookie: {cookie_name}, Path: {request.path}")
        return cookie_name

    def process_request(self, request):
        """
        Process incoming request and load the appropriate session.

        Overrides SessionMiddleware.process_request to use portal-specific cookie name.
        """
        # Determine which session cookie to use
        session_cookie_name = self.get_session_cookie_name(request)
        session_key = request.COOKIES.get(session_cookie_name)

        # Store portal info on request for later use
        portal_type = self.get_portal_type(request.path)
        request.portal_type = portal_type
        request.session_cookie_name = session_cookie_name

        # Load session using the portal-specific session key
        engine = import_module(settings.SESSION_ENGINE)
        request.session = engine.SessionStore(session_key)

        logger.debug(
            f"Loaded session for {portal_type} portal: "
            f"cookie={session_cookie_name}, "
            f"key={session_key[:8] if session_key else None}..."
        )

    def process_response(self, request, response):
        """
        Save session and set the appropriate session cookie.

        Overrides SessionMiddleware.process_response to use portal-specific cookie name.
        """
        try:
            accessed = request.session.accessed
            modified = request.session.modified
            empty = request.session.is_empty()
        except AttributeError:
            return response

        # Get the portal-specific cookie name
        session_cookie_name = getattr(request, "session_cookie_name", settings.SESSION_COOKIE_NAME)

        # If the session is being used, set appropriate Vary headers
        if accessed:
            patch_vary_headers(response, ("Cookie",))

        # If session was modified or new, save it
        if modified or settings.SESSION_SAVE_EVERY_REQUEST:
            if request.session.get_expire_at_browser_close():
                max_age = None
                expires = None
            else:
                max_age = request.session.get_expiry_age()
                expires_time = request.session.get_expiry_date()
                expires = http_date(expires_time.timestamp())

            # Save the session data
            if not empty:
                try:
                    request.session.save()
                except Exception as e:
                    logger.error(f"Error saving session: {e}")
                    return response

                # Set the session cookie with portal-specific name
                response.set_cookie(
                    session_cookie_name,
                    request.session.session_key,
                    max_age=max_age,
                    expires=expires,
                    domain=settings.SESSION_COOKIE_DOMAIN,
                    path=settings.SESSION_COOKIE_PATH,
                    secure=settings.SESSION_COOKIE_SECURE,
                    httponly=settings.SESSION_COOKIE_HTTPONLY,
                    samesite=settings.SESSION_COOKIE_SAMESITE,
                )

                logger.debug(
                    f"Set session cookie: {session_cookie_name}="
                    f"{request.session.session_key[:8]}... for {request.portal_type} portal"
                )
            else:
                # Session is empty, delete the cookie if it exists
                if session_cookie_name in request.COOKIES:
                    response.delete_cookie(
                        session_cookie_name,
                        path=settings.SESSION_COOKIE_PATH,
                        domain=settings.SESSION_COOKIE_DOMAIN,
                        samesite=settings.SESSION_COOKIE_SAMESITE,
                    )
                    logger.debug(f"Deleted empty session cookie: {session_cookie_name}")

        return response

    def clear_session_cookie(self, request, response, portal_type=None):
        """
        Clear the session cookie for a specific portal type.

        This is a helper method that can be called from logout views.

        Args:
            request: HttpRequest object
            response: HttpResponse object
            portal_type: 'admin', 'platform', or 'tenant' (auto-detected if None)
        """
        if portal_type is None:
            portal_type = self.get_portal_type(request.path)

        cookie_name = self.COOKIE_NAMES[portal_type]

        response.delete_cookie(
            cookie_name,
            path=settings.SESSION_COOKIE_PATH,
            domain=settings.SESSION_COOKIE_DOMAIN,
            samesite=settings.SESSION_COOKIE_SAMESITE,
        )

        logger.info(f"Cleared {portal_type} portal session cookie: {cookie_name}")
        return response
