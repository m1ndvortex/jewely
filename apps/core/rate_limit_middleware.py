"""
Rate limiting middleware for API endpoints.

Applies rate limiting to all API endpoints based on user authentication status.

Per Requirement 25: Security Hardening and Compliance
"""

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from django_ratelimit.core import is_ratelimited


class APIRateLimitMiddleware(MiddlewareMixin):
    """
    Middleware to apply rate limiting to API endpoints.

    - Authenticated users: 100 requests per hour
    - Anonymous users: 20 requests per hour (per IP)

    Only applies to paths starting with /api/
    """

    def process_request(self, request):
        """Check rate limit before processing the request."""
        # Only apply to API endpoints
        if not request.path.startswith("/api/"):
            return None

        # Skip rate limiting for certain endpoints (health checks, etc.)
        exempt_paths = [
            "/api/health/",
            "/api/metrics/",
        ]

        if any(request.path.startswith(path) for path in exempt_paths):
            return None

        # Determine rate limit based on authentication
        # Check if user attribute exists (may not be set yet in middleware chain)
        if hasattr(request, "user") and request.user.is_authenticated:
            # Authenticated users: 100/hour per user
            rate = "100/h"
            key = f"user:{request.user.id}"
        else:
            # Anonymous users: 20/hour per IP
            rate = "20/h"
            key = request.META.get("REMOTE_ADDR", "unknown")

        # Check if rate limited
        is_limited = is_ratelimited(
            request=request,
            group="api",
            key=lambda g, r: key,
            rate=rate,
            method=request.method,
            increment=True,
        )

        if is_limited:
            return JsonResponse(
                {
                    "error": "Rate limit exceeded",
                    "message": "You have exceeded the API rate limit. Please try again later.",
                    "rate_limit": rate,
                },
                status=429,
            )

        return None
