"""
Audit logging middleware for automatic request/response logging.

This middleware automatically logs API requests and responses per Requirement 8.4.
"""

import logging
import time

from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

from apps.core.audit import log_api_request

logger = logging.getLogger(__name__)


class AuditLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to automatically log API requests and responses.

    This middleware:
    1. Tracks request timing
    2. Logs all API requests with details
    3. Captures request/response metadata

    Per Requirement 8.4 - Log all API requests with details.
    """

    # Paths to exclude from API logging (to reduce noise)
    EXCLUDED_PATHS = [
        "/static/",
        "/media/",
        "/metrics/",  # Prometheus metrics
        "/health/",  # Health check endpoint
        "/__debug__/",  # Django Debug Toolbar
    ]

    def process_request(self, request: HttpRequest):
        """
        Store request start time.

        Args:
            request: The incoming HTTP request
        """
        request._audit_start_time = time.time()
        return None

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """
        Log the request/response after processing.

        Args:
            request: The HTTP request
            response: The HTTP response

        Returns:
            The HTTP response
        """
        # Skip excluded paths
        if self._should_exclude(request.path):
            return response

        # Calculate response time
        if hasattr(request, "_audit_start_time"):
            response_time_ms = int((time.time() - request._audit_start_time) * 1000)
        else:
            response_time_ms = 0

        # Log the API request asynchronously to avoid blocking
        try:
            # Only log API endpoints (paths starting with /api/)
            if request.path.startswith("/api/"):
                log_api_request(request, response, response_time_ms)
        except Exception as e:
            # Don't let audit logging failures break the request
            logger.error(f"Error logging API request: {e}", exc_info=True)

        return response

    def _should_exclude(self, path: str) -> bool:
        """
        Check if the request path should be excluded from logging.

        Args:
            path: The request path

        Returns:
            True if path should be excluded, False otherwise
        """
        return any(path.startswith(excluded) for excluded in self.EXCLUDED_PATHS)
