"""
Tenant context middleware for multi-tenant data isolation.

This middleware extracts the tenant ID from the request (JWT token or session)
and sets the PostgreSQL session variable for Row-Level Security (RLS) enforcement.
"""

import logging
from typing import Optional
from uuid import UUID

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.deprecation import MiddlewareMixin

from apps.core.models import Tenant
from apps.core.tenant_context import clear_tenant_context, enable_rls_bypass, set_tenant_context

logger = logging.getLogger(__name__)


class TenantContextMiddleware(MiddlewareMixin):
    """
    Middleware to set tenant context for each request.

    This middleware:
    1. Extracts tenant_id from JWT token or session
    2. Sets PostgreSQL session variable for RLS
    3. Handles tenant not found and suspended tenant cases
    4. Enables RLS bypass for platform admins

    Requirements: Requirement 1 - Multi-Tenant Architecture with Data Isolation
    """

    # Paths that don't require tenant context
    EXEMPT_PATHS = [
        "/admin/",  # Django admin (platform admin)
        "/platform/",  # Platform admin dashboard
        "/api/auth/login/",
        "/api/auth/register/",
        "/api/auth/refresh/",
        "/health/",
        "/metrics/",
        "/static/",
        "/media/",
    ]

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Process incoming request and set tenant context.

        Args:
            request: The incoming HTTP request

        Returns:
            None if processing should continue, HttpResponse if request should be rejected
        """
        # Clear any existing tenant context from previous requests
        clear_tenant_context()

        # Check if path is exempt from tenant context
        if self._is_exempt_path(request.path):
            # For admin and platform paths, enable RLS bypass if user is platform admin
            if (
                request.path.startswith("/admin/") or request.path.startswith("/platform/")
            ) and self._is_platform_admin(request.user):
                enable_rls_bypass()
                logger.debug(f"RLS bypass enabled for platform admin: {request.user}")
            return None

        # Extract tenant ID from request
        tenant_id = self._extract_tenant_id(request)

        if not tenant_id:
            # No tenant context available
            if request.user and not isinstance(request.user, AnonymousUser):
                logger.warning(f"No tenant context for authenticated user: {request.user.username}")
                return JsonResponse(
                    {"error": "Tenant context not found. Please contact support."},
                    status=403,
                )
            # Anonymous users without tenant context are allowed (for login, etc.)
            return None

        # Set tenant context first, then validate
        set_tenant_context(tenant_id)
        logger.debug(f"Tenant context set for request: {tenant_id}")

        # Now query the tenant - RLS will allow access since context is set
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            logger.error(f"Tenant not found: {tenant_id}")
            clear_tenant_context()
            return JsonResponse(
                {"error": "Tenant not found. Please contact support."},
                status=404,
            )
        except Exception as e:
            logger.error(f"Error querying tenant {tenant_id}: {e}")
            clear_tenant_context()
            return JsonResponse(
                {"error": "An error occurred. Please try again later."},
                status=500,
            )

        # Check tenant status
        if tenant.status == Tenant.SUSPENDED:
            logger.warning(f"Access attempt to suspended tenant: {tenant_id}")
            clear_tenant_context()
            return JsonResponse(
                {
                    "error": "Your account has been suspended. Please contact support.",
                    "tenant_status": "suspended",
                },
                status=403,
            )

        if tenant.status == Tenant.PENDING_DELETION:
            logger.warning(f"Access attempt to tenant pending deletion: {tenant_id}")
            clear_tenant_context()
            return JsonResponse(
                {
                    "error": "Your account is scheduled for deletion. Please contact support.",
                    "tenant_status": "pending_deletion",
                },
                status=403,
            )

        # Store tenant in request for easy access
        request.tenant = tenant
        request.tenant_id = tenant_id

        return None

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """
        Clean up tenant context after request processing.

        Args:
            request: The HTTP request
            response: The HTTP response

        Returns:
            The HTTP response
        """
        # Clear tenant context to prevent leakage between requests
        try:
            clear_tenant_context()
        except Exception as e:
            logger.error(f"Error clearing tenant context: {e}")

        return response

    def process_exception(
        self, request: HttpRequest, exception: Exception
    ) -> Optional[HttpResponse]:
        """
        Clean up tenant context if an exception occurs.

        Args:
            request: The HTTP request
            exception: The exception that occurred

        Returns:
            None to allow normal exception handling
        """
        try:
            clear_tenant_context()
        except Exception as e:
            logger.error(f"Error clearing tenant context during exception handling: {e}")

        return None

    def _is_exempt_path(self, path: str) -> bool:
        """
        Check if the request path is exempt from tenant context.

        Args:
            path: The request path

        Returns:
            True if path is exempt, False otherwise
        """
        return any(path.startswith(exempt_path) for exempt_path in self.EXEMPT_PATHS)

    def _is_platform_admin(self, user) -> bool:
        """
        Check if user is a platform administrator.

        Args:
            user: The user object

        Returns:
            True if user is platform admin, False otherwise
        """
        if not user or isinstance(user, AnonymousUser):
            return False

        # Check if user is superuser (Django admin)
        if user.is_superuser:
            return True

        # Check if user has PLATFORM_ADMIN role (if User model is extended)
        if hasattr(user, "role"):
            return user.role == "PLATFORM_ADMIN"

        return False

    def _extract_tenant_id(self, request: HttpRequest) -> Optional[UUID]:
        """
        Extract tenant ID from JWT token or session.

        Priority:
        1. JWT token (Authorization header)
        2. Session
        3. User model (if authenticated)

        Args:
            request: The HTTP request

        Returns:
            UUID of the tenant, or None if not found
        """
        # Try to extract from JWT token
        tenant_id = self._extract_from_jwt(request)
        if tenant_id:
            return tenant_id

        # Try to extract from session
        tenant_id = self._extract_from_session(request)
        if tenant_id:
            return tenant_id

        # Try to extract from user model
        tenant_id = self._extract_from_user(request)
        if tenant_id:
            return tenant_id

        return None

    def _extract_from_jwt(self, request: HttpRequest) -> Optional[UUID]:
        """
        Extract tenant ID from JWT token in Authorization header.

        Args:
            request: The HTTP request

        Returns:
            UUID of the tenant, or None if not found
        """
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return None

        try:
            # Import here to avoid circular imports
            from rest_framework_simplejwt.tokens import AccessToken

            token = auth_header.split(" ")[1]
            access_token = AccessToken(token)

            # Extract tenant_id from token payload
            tenant_id_str = access_token.get("tenant_id")
            if tenant_id_str:
                return UUID(tenant_id_str)

        except ImportError:
            # JWT library not installed yet, skip JWT extraction
            logger.debug("JWT library not available, skipping JWT extraction")
        except Exception as e:
            logger.warning(f"Error extracting tenant from JWT: {e}")

        return None

    def _extract_from_session(self, request: HttpRequest) -> Optional[UUID]:
        """
        Extract tenant ID from session.

        Args:
            request: The HTTP request

        Returns:
            UUID of the tenant, or None if not found
        """
        # Check if session exists
        if not hasattr(request, "session"):
            return None

        tenant_id_str = request.session.get("tenant_id")
        if tenant_id_str:
            try:
                return UUID(tenant_id_str)
            except (ValueError, AttributeError) as e:
                logger.warning(f"Invalid tenant_id in session: {tenant_id_str}, error: {e}")

        return None

    def _extract_from_user(self, request: HttpRequest) -> Optional[UUID]:
        """
        Extract tenant ID from authenticated user model.

        Args:
            request: The HTTP request

        Returns:
            UUID of the tenant, or None if not found
        """
        if not request.user or isinstance(request.user, AnonymousUser):
            return None

        # Check if user has tenant_id attribute first (doesn't trigger DB query)
        if hasattr(request.user, "tenant_id") and request.user.tenant_id:
            tenant_id = request.user.tenant_id
            if isinstance(tenant_id, UUID):
                return tenant_id
            try:
                return UUID(str(tenant_id))
            except (ValueError, AttributeError) as e:
                logger.warning(f"Invalid tenant_id on user: {tenant_id}, error: {e}")

        # Check if user has tenant attribute (extended User model)
        # Wrap in try-except to handle cases where tenant is not accessible due to RLS
        try:
            if hasattr(request.user, "tenant") and request.user.tenant:
                tenant = request.user.tenant
                if hasattr(tenant, "id"):
                    return tenant.id
                return tenant  # In case it's already a UUID
        except Tenant.DoesNotExist:
            # Tenant not accessible (possibly due to RLS), fall through to return None
            logger.debug(f"Tenant not accessible for user {request.user.username}")
            pass

        return None
