"""
Impersonation Service for platform administrators.

This service handles:
- Starting impersonation sessions (switching to target user context)
- Ending impersonation sessions (restoring admin context)
- Tracking impersonation state
- Audit logging of impersonation events
- Cross-portal session transfer via secure tokens

Requirements: 12.1, 12.3, 12.5
"""

import secrets
from typing import Optional, Tuple

from django.contrib.auth import get_user_model, login
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.http import HttpRequest
from django.utils import timezone

from apps.core.audit_models import AuditLog

User = get_user_model()


class ImpersonationService:
    """
    Service for managing user impersonation by platform administrators.

    Allows platform admins to temporarily assume the identity of tenant users
    for support and troubleshooting purposes. All impersonation sessions are
    fully audited.

    Per Requirements 12.1, 12.3, 12.5 for impersonation functionality.
    """

    # Session keys for storing impersonation state
    SESSION_KEY_ORIGINAL_USER_ID = "_impersonate_original_user_id"
    SESSION_KEY_IMPERSONATION_START = "_impersonate_start_time"
    SESSION_KEY_TARGET_USER_ID = "_impersonate_target_user_id"

    # Cache key prefix for impersonation tokens (for cross-portal transfer)
    IMPERSONATION_TOKEN_PREFIX = "impersonation_token_"
    IMPERSONATION_TOKEN_EXPIRY = 60  # Token valid for 60 seconds

    def generate_impersonation_token(
        self,
        admin_user: User,
        target_user: User,
    ) -> str:
        """
        Generate a one-time secure token for cross-portal impersonation transfer.

        This is needed because the multi-portal session middleware uses different
        session cookies for /platform/ and /dashboard/ paths. The token allows
        secure transfer of impersonation state between portals.

        Args:
            admin_user: The platform admin initiating impersonation
            target_user: The user to be impersonated

        Returns:
            str: A secure token that can be used to complete impersonation
        """
        token = secrets.token_urlsafe(32)
        cache_key = f"{self.IMPERSONATION_TOKEN_PREFIX}{token}"

        # Store impersonation details in cache
        cache.set(
            cache_key,
            {
                "admin_user_id": admin_user.id,
                "target_user_id": target_user.id,
                "created_at": timezone.now().isoformat(),
            },
            timeout=self.IMPERSONATION_TOKEN_EXPIRY,
        )

        return token

    def complete_impersonation_transfer(
        self,
        request: HttpRequest,
        token: str,
    ) -> Tuple[bool, str, Optional[User]]:
        """
        Complete impersonation by validating token and logging in as target user.

        This method is called from the tenant portal endpoint to complete the
        impersonation that was initiated from the platform portal.

        Args:
            request: The HTTP request in the tenant portal context
            token: The one-time impersonation token

        Returns:
            Tuple of (success, message, target_user or None)
        """
        cache_key = f"{self.IMPERSONATION_TOKEN_PREFIX}{token}"
        impersonation_data = cache.get(cache_key)

        if not impersonation_data:
            return (False, "Invalid or expired impersonation token.", None)

        # Delete the token immediately (one-time use)
        cache.delete(cache_key)

        try:
            admin_user = User.objects.get(id=impersonation_data["admin_user_id"])
            target_user = User.objects.get(id=impersonation_data["target_user_id"])
        except User.DoesNotExist:
            return (False, "User not found.", None)

        # Validate target user has a tenant
        if not target_user.tenant:
            return (False, "Cannot impersonate platform administrators.", None)

        # Check if already impersonating
        if self.is_impersonating(request):
            return (False, "Already impersonating a user.", None)

        # Store impersonation state in tenant session
        request.session[self.SESSION_KEY_ORIGINAL_USER_ID] = admin_user.id
        request.session[self.SESSION_KEY_TARGET_USER_ID] = target_user.id
        request.session[self.SESSION_KEY_IMPERSONATION_START] = timezone.now().isoformat()

        # Log in as target user
        target_user.backend = "django.contrib.auth.backends.ModelBackend"
        login(request, target_user)

        # Save the session
        request.session.save()

        # Create audit log entry
        self._log_impersonation_start(
            admin_user=admin_user,
            target_user=target_user,
            request=request,
        )

        return (
            True,
            f"Now impersonating {target_user.username}. Click 'End Impersonation' to return to your admin session.",
            target_user,
        )

    def start_impersonation(
        self,
        request: HttpRequest,
        target_user: User,
        admin_user: User,
    ) -> Tuple[bool, str]:
        """
        Start an impersonation session.

        Stores the original admin user ID in the session, then logs in as the
        target user. Creates an audit log entry for the impersonation start.

        Args:
            request: The HTTP request object
            target_user: The user to impersonate
            admin_user: The platform admin starting the impersonation

        Returns:
            Tuple of (success, message)

        Raises:
            ValueError: If already impersonating or if target is a platform admin

        Per Requirements 12.1, 12.2 for starting impersonation.
        """
        # Validate we're not already impersonating
        if self.is_impersonating(request):
            return (
                False,
                "Already impersonating a user. End current impersonation first.",
            )

        # Validate target user is not a platform admin
        if not target_user.tenant:
            return (
                False,
                "Cannot impersonate platform administrators.",
            )

        # Validate admin user has permission (should be platform admin)
        if admin_user.tenant is not None:
            return (
                False,
                "Only platform administrators can impersonate users.",
            )

        # Store original admin user ID in session
        request.session[self.SESSION_KEY_ORIGINAL_USER_ID] = admin_user.id
        request.session[self.SESSION_KEY_TARGET_USER_ID] = target_user.id
        request.session[self.SESSION_KEY_IMPERSONATION_START] = timezone.now().isoformat()

        # Switch to target user (login as target user)
        # We need to set the backend attribute for login to work
        target_user.backend = "django.contrib.auth.backends.ModelBackend"
        login(request, target_user)

        # Ensure the session is saved with impersonation data
        request.session.save()

        # Create audit log entry
        self._log_impersonation_start(
            admin_user=admin_user,
            target_user=target_user,
            request=request,
        )

        return (
            True,
            f"Now impersonating {target_user.username}. Click 'End Impersonation' to return to your admin session.",
        )

    def end_impersonation(
        self,
        request: HttpRequest,
    ) -> Tuple[bool, str]:
        """
        End an impersonation session.

        Retrieves the original admin user from the session and logs back in as
        that user. Creates an audit log entry for the impersonation end.

        Args:
            request: The HTTP request object

        Returns:
            Tuple of (success, message)

        Raises:
            ValueError: If not currently impersonating

        Per Requirements 12.3, 12.4 for ending impersonation.
        """
        # Validate we're currently impersonating
        if not self.is_impersonating(request):
            return (False, "Not currently impersonating any user.")

        # Get the original admin user ID
        original_user_id = request.session.get(self.SESSION_KEY_ORIGINAL_USER_ID)
        target_user_id = request.session.get(self.SESSION_KEY_TARGET_USER_ID)

        if not original_user_id:
            return (False, "Cannot restore admin session: original user not found.")

        # Get the users
        try:
            original_user = User.objects.get(id=original_user_id)
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return (False, "Cannot restore admin session: user not found.")

        # Create audit log entry BEFORE switching back
        # (so we capture the impersonated user's context)
        self._log_impersonation_end(
            admin_user=original_user,
            target_user=target_user,
            request=request,
        )

        # Clear impersonation session data
        del request.session[self.SESSION_KEY_ORIGINAL_USER_ID]
        del request.session[self.SESSION_KEY_TARGET_USER_ID]
        del request.session[self.SESSION_KEY_IMPERSONATION_START]

        # Switch back to original admin user
        original_user.backend = "django.contrib.auth.backends.ModelBackend"
        login(request, original_user)

        return (
            True,
            f"Impersonation ended. You are now logged in as {original_user.username}.",
        )

    def is_impersonating(self, request: HttpRequest) -> bool:
        """
        Check if the current session is in impersonation mode.

        Args:
            request: The HTTP request object

        Returns:
            True if currently impersonating, False otherwise

        Per Requirement 12.3 for impersonation state tracking.
        """
        return self.SESSION_KEY_ORIGINAL_USER_ID in request.session

    def get_original_user(self, request: HttpRequest) -> Optional[User]:
        """
        Get the original admin user who started the impersonation.

        Args:
            request: The HTTP request object

        Returns:
            The original admin User object, or None if not impersonating

        Per Requirement 12.5 for accessing original admin session data.
        """
        if not self.is_impersonating(request):
            return None

        original_user_id = request.session.get(self.SESSION_KEY_ORIGINAL_USER_ID)
        if not original_user_id:
            return None

        try:
            return User.objects.get(id=original_user_id)
        except User.DoesNotExist:
            return None

    def get_target_user(self, request: HttpRequest) -> Optional[User]:
        """
        Get the target user being impersonated.

        Args:
            request: The HTTP request object

        Returns:
            The target User object, or None if not impersonating
        """
        if not self.is_impersonating(request):
            return None

        target_user_id = request.session.get(self.SESSION_KEY_TARGET_USER_ID)
        if not target_user_id:
            return None

        try:
            return User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return None

    def get_impersonation_start_time(self, request: HttpRequest) -> Optional[str]:
        """
        Get the timestamp when impersonation started.

        Args:
            request: The HTTP request object

        Returns:
            ISO format timestamp string, or None if not impersonating
        """
        if not self.is_impersonating(request):
            return None

        return request.session.get(self.SESSION_KEY_IMPERSONATION_START)

    def _log_impersonation_start(
        self,
        admin_user: User,
        target_user: User,
        request: HttpRequest,
    ) -> None:
        """
        Create an audit log entry for impersonation start.

        Args:
            admin_user: The platform admin starting impersonation
            target_user: The user being impersonated
            request: The HTTP request object

        Per Requirement 12.2 for audit logging.
        """
        # Get IP address from request
        ip_address = self._get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        # Get content type for User model
        user_content_type = ContentType.objects.get_for_model(User)

        AuditLog.objects.create(
            tenant=target_user.tenant,  # Log to target user's tenant
            user=admin_user,  # The admin who initiated impersonation
            category=AuditLog.CATEGORY_SECURITY,
            action=AuditLog.ACTION_IMPERSONATION_START,
            severity=AuditLog.SEVERITY_WARNING,
            description=f"Platform admin {admin_user.username} started impersonating user {target_user.username}",
            content_type=user_content_type,
            object_id=str(target_user.id),
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={
                "admin_user_id": admin_user.id,
                "admin_username": admin_user.username,
                "target_user_id": target_user.id,
                "target_username": target_user.username,
                "target_tenant_id": str(target_user.tenant.id) if target_user.tenant else None,
                "target_tenant_name": (
                    target_user.tenant.company_name if target_user.tenant else None
                ),
            },
        )

    def _log_impersonation_end(
        self,
        admin_user: User,
        target_user: User,
        request: HttpRequest,
    ) -> None:
        """
        Create an audit log entry for impersonation end.

        Args:
            admin_user: The platform admin ending impersonation
            target_user: The user who was impersonated
            request: The HTTP request object

        Per Requirement 12.4 for audit logging.
        """
        # Get IP address from request
        ip_address = self._get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        # Get impersonation duration
        start_time_str = self.get_impersonation_start_time(request)
        duration_seconds = None
        if start_time_str:
            from datetime import datetime

            start_time = datetime.fromisoformat(start_time_str)
            duration_seconds = (timezone.now() - start_time).total_seconds()

        # Get content type for User model
        user_content_type = ContentType.objects.get_for_model(User)

        AuditLog.objects.create(
            tenant=target_user.tenant,  # Log to target user's tenant
            user=admin_user,  # The admin who initiated impersonation
            category=AuditLog.CATEGORY_SECURITY,
            action=AuditLog.ACTION_IMPERSONATION_END,
            severity=AuditLog.SEVERITY_INFO,
            description=f"Platform admin {admin_user.username} ended impersonation of user {target_user.username}",
            content_type=user_content_type,
            object_id=str(target_user.id),
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={
                "admin_user_id": admin_user.id,
                "admin_username": admin_user.username,
                "target_user_id": target_user.id,
                "target_username": target_user.username,
                "target_tenant_id": str(target_user.tenant.id) if target_user.tenant else None,
                "target_tenant_name": (
                    target_user.tenant.company_name if target_user.tenant else None
                ),
                "duration_seconds": duration_seconds,
            },
        )

    def _get_client_ip(self, request: HttpRequest) -> Optional[str]:
        """
        Extract the client IP address from the request.

        Handles X-Forwarded-For header for proxied requests.

        Args:
            request: The HTTP request object

        Returns:
            The client IP address as a string, or None if not available
        """
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            # Take the first IP in the chain
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")

        return ip
