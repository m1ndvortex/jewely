"""
Brute force protection for login endpoints.

Implements rate limiting and IP blocking to prevent brute force attacks
on authentication endpoints.

Per Requirement 25: Security Hardening and Compliance
"""

from datetime import timedelta
from functools import wraps
from typing import Callable, Optional

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext as _

from .audit_models import LoginAttempt

# Configuration
MAX_FAILED_ATTEMPTS = getattr(settings, "BRUTE_FORCE_MAX_ATTEMPTS", 5)
LOCKOUT_DURATION_MINUTES = getattr(settings, "BRUTE_FORCE_LOCKOUT_MINUTES", 15)
ATTEMPT_WINDOW_MINUTES = getattr(settings, "BRUTE_FORCE_WINDOW_MINUTES", 5)


def get_client_ip(request: HttpRequest) -> str:
    """
    Extract client IP address from request.

    Handles X-Forwarded-For header for proxied requests.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        # Take the first IP in the chain
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "unknown")
    return ip


def is_ip_blocked(ip_address: str) -> bool:
    """
    Check if an IP address is currently blocked due to brute force attempts.

    Args:
        ip_address: IP address to check

    Returns:
        True if IP is blocked, False otherwise
    """
    cache_key = f"brute_force_block:{ip_address}"
    return cache.get(cache_key, False)


def block_ip(ip_address: str, duration_minutes: int = LOCKOUT_DURATION_MINUTES) -> None:
    """
    Block an IP address for a specified duration.

    Args:
        ip_address: IP address to block
        duration_minutes: How long to block the IP (default: 15 minutes)
    """
    cache_key = f"brute_force_block:{ip_address}"
    cache.set(cache_key, True, duration_minutes * 60)


def get_failed_attempts_count(ip_address: str, window_minutes: int = ATTEMPT_WINDOW_MINUTES) -> int:
    """
    Count failed login attempts from an IP within the time window.

    Args:
        ip_address: IP address to check
        window_minutes: Time window in minutes (default: 5 minutes)

    Returns:
        Number of failed attempts
    """
    cutoff_time = timezone.now() - timedelta(minutes=window_minutes)

    failed_attempts = LoginAttempt.objects.filter(
        ip_address=ip_address,
        timestamp__gte=cutoff_time,
        result__in=[
            LoginAttempt.RESULT_FAILED_PASSWORD,
            LoginAttempt.RESULT_FAILED_USER_NOT_FOUND,
            LoginAttempt.RESULT_FAILED_MFA,
        ],
    ).count()

    return failed_attempts


def check_brute_force(ip_address: str) -> tuple[bool, Optional[str]]:
    """
    Check if an IP should be blocked due to brute force attempts.

    Args:
        ip_address: IP address to check

    Returns:
        Tuple of (is_blocked, error_message)
    """
    # Check if IP is already blocked
    if is_ip_blocked(ip_address):
        return True, _(
            "Too many failed login attempts. Your IP has been temporarily blocked. "
            "Please try again in {} minutes."
        ).format(LOCKOUT_DURATION_MINUTES)

    # Check recent failed attempts
    failed_count = get_failed_attempts_count(ip_address)

    if failed_count >= MAX_FAILED_ATTEMPTS:
        # Block the IP
        block_ip(ip_address)

        # Log the block event
        LoginAttempt.objects.create(
            username="[BLOCKED]",
            result=LoginAttempt.RESULT_FAILED_RATE_LIMIT,
            ip_address=ip_address,
            user_agent="",
        )

        return True, _(
            "Too many failed login attempts. Your IP has been temporarily blocked. "
            "Please try again in {} minutes."
        ).format(LOCKOUT_DURATION_MINUTES)

    return False, None


def record_login_attempt(
    request: HttpRequest,
    username: str,
    result: str,
    user=None,
) -> None:
    """
    Record a login attempt in the database.

    Args:
        request: HTTP request object
        username: Username that was attempted
        result: Result of the attempt (use LoginAttempt.RESULT_* constants)
        user: User object if found (optional)
    """
    ip_address = get_client_ip(request)
    user_agent = request.META.get("HTTP_USER_AGENT", "")

    LoginAttempt.objects.create(
        user=user,
        username=username,
        result=result,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def brute_force_protected(view_func: Callable) -> Callable:
    """
    Decorator to protect login views from brute force attacks.

    Checks if the IP is blocked before allowing the view to execute.
    Should be applied to login POST handlers.

    Example:
        @brute_force_protected
        def post(self, request):
            # Login logic here
            pass
    """

    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        ip_address = get_client_ip(request)

        # Check for brute force
        is_blocked, error_message = check_brute_force(ip_address)

        if is_blocked:
            # Return appropriate response based on request type
            if request.path.startswith("/api/"):
                # API endpoint - return JSON
                return JsonResponse(
                    {
                        "error": "Too many failed attempts",
                        "message": error_message,
                        "retry_after": LOCKOUT_DURATION_MINUTES * 60,
                    },
                    status=429,
                )
            else:
                # Web endpoint - render template with error
                from django.contrib import messages

                messages.error(request, error_message)

                # Try to render the same template
                if hasattr(view_func, "__self__"):
                    # Class-based view
                    view_instance = view_func.__self__
                    if hasattr(view_instance, "template_name"):
                        return render(request, view_instance.template_name)

                # Fallback to generic error
                return render(
                    request,
                    "errors/429.html",
                    {"error_message": error_message},
                    status=429,
                )

        # Not blocked, proceed with the view
        return view_func(request, *args, **kwargs)

    return wrapped_view


def clear_failed_attempts(ip_address: str) -> None:
    """
    Clear failed login attempts for an IP (called after successful login).

    Args:
        ip_address: IP address to clear
    """
    # We don't actually delete the records (for audit purposes),
    # but we can clear any temporary blocks
    cache_key = f"brute_force_block:{ip_address}"
    cache.delete(cache_key)
