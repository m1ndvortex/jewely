"""
API throttling utilities using django-ratelimit.

Provides rate limiting decorators to prevent API abuse and ensure
fair resource usage across tenants.
"""

from functools import wraps
from typing import Callable

from django.http import JsonResponse

from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited


def api_ratelimit(
    key: str = "ip",
    rate: str = "100/h",
    method: str = "ALL",
    block: bool = True,
) -> Callable:
    """
    Rate limit decorator for API endpoints.

    Args:
        key: What to rate limit on ('ip', 'user', 'header:x-api-key', etc.)
        rate: Rate limit (e.g., '100/h', '10/m', '1000/d')
        method: HTTP methods to rate limit ('GET', 'POST', 'ALL', etc.)
        block: Whether to block requests that exceed the limit

    Returns:
        Decorator function

    Example:
        @api_ratelimit(key='user', rate='50/h')
        def my_api_view(request):
            return JsonResponse({'data': 'value'})
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        @ratelimit(key=key, rate=rate, method=method, block=block)
        def wrapped_view(request, *args, **kwargs):
            # Check if request was rate limited
            if getattr(request, "limited", False):
                return JsonResponse(
                    {
                        "error": "Rate limit exceeded",
                        "message": "Too many requests. Please try again later.",
                        "rate_limit": rate,
                    },
                    status=429,
                )

            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator


def api_ratelimit_tenant(rate: str = "1000/h", method: str = "ALL") -> Callable:
    """
    Rate limit by tenant for multi-tenant applications.

    Args:
        rate: Rate limit per tenant
        method: HTTP methods to rate limit

    Returns:
        Decorator function

    Example:
        @api_ratelimit_tenant(rate='500/h')
        def tenant_api_view(request):
            return JsonResponse({'data': 'value'})
    """

    def get_tenant_key(group, request):
        """Extract tenant ID from request for rate limiting."""
        if hasattr(request.user, "tenant_id"):
            return f"tenant:{request.user.tenant_id}"
        elif hasattr(request.user, "tenant") and request.user.tenant:
            return f"tenant:{request.user.tenant.id}"
        # Fallback to IP if no tenant
        return request.META.get("REMOTE_ADDR", "unknown")

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        @ratelimit(key=get_tenant_key, rate=rate, method=method, block=True)
        def wrapped_view(request, *args, **kwargs):
            if getattr(request, "limited", False):
                return JsonResponse(
                    {
                        "error": "Rate limit exceeded",
                        "message": "Your organization has exceeded the API rate limit. Please try again later.",
                        "rate_limit": rate,
                    },
                    status=429,
                )

            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator


def api_ratelimit_user(rate: str = "100/h", method: str = "ALL") -> Callable:
    """
    Rate limit by authenticated user.

    Args:
        rate: Rate limit per user
        method: HTTP methods to rate limit

    Returns:
        Decorator function

    Example:
        @api_ratelimit_user(rate='50/h')
        def user_api_view(request):
            return JsonResponse({'data': 'value'})
    """

    def get_user_key(group, request):
        """Extract user ID from request for rate limiting."""
        if request.user.is_authenticated:
            return f"user:{request.user.id}"
        # Fallback to IP for anonymous users
        return request.META.get("REMOTE_ADDR", "unknown")

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        @ratelimit(key=get_user_key, rate=rate, method=method, block=True)
        def wrapped_view(request, *args, **kwargs):
            if getattr(request, "limited", False):
                return JsonResponse(
                    {
                        "error": "Rate limit exceeded",
                        "message": "You have exceeded the API rate limit. Please try again later.",
                        "rate_limit": rate,
                    },
                    status=429,
                )

            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator


# Predefined rate limit decorators for common use cases

# Strict rate limit for expensive operations
api_ratelimit_strict = api_ratelimit(key="ip", rate="10/m", method="ALL")

# Standard rate limit for general API endpoints
api_ratelimit_standard = api_ratelimit(key="ip", rate="100/h", method="ALL")

# Lenient rate limit for read-only operations
api_ratelimit_lenient = api_ratelimit(key="ip", rate="500/h", method="GET")

# Write operation rate limit
api_ratelimit_write = api_ratelimit(key="user", rate="50/h", method="POST")


def handle_ratelimit_exception(view_func: Callable) -> Callable:
    """
    Decorator to handle Ratelimited exceptions and return JSON response.

    This is useful when using ratelimit without the block parameter.

    Example:
        @handle_ratelimit_exception
        @ratelimit(key='ip', rate='10/m', block=False)
        def my_view(request):
            if getattr(request, 'limited', False):
                # Custom handling
                pass
            return JsonResponse({'data': 'value'})
    """

    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Ratelimited:
            return JsonResponse(
                {
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                },
                status=429,
            )

    return wrapped_view
