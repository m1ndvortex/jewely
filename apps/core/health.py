"""
Health check views and URLs for monitoring and deployment verification.

This module provides health check endpoints used by:
- Load balancers for health checks
- Kubernetes liveness and readiness probes
- CI/CD pipeline for deployment verification
- Monitoring systems for uptime checks
"""

import logging

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.urls import path
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@never_cache
@require_GET
def health_check(request) -> JsonResponse:
    """
    Basic health check endpoint.

    Returns 200 OK if the application is running.
    Used for simple uptime monitoring.

    Returns:
        JsonResponse: {"status": "ok", "version": "1.0.0"}
    """
    return JsonResponse(
        {
            "status": "ok",
            "version": getattr(settings, "VERSION", "1.0.0"),
            "environment": getattr(settings, "ENVIRONMENT", "unknown"),
        }
    )


@never_cache
@require_GET
def health_check_detailed(request) -> JsonResponse:
    """
    Detailed health check endpoint with dependency checks.

    Checks:
    - Database connectivity
    - Redis cache connectivity
    - Celery worker availability (if configured)

    Returns 200 if all checks pass, 503 if any check fails.
    Used by Kubernetes readiness probes and deployment verification.

    Returns:
        JsonResponse: Detailed health status of all components
    """
    health_status = {
        "status": "healthy",
        "version": getattr(settings, "VERSION", "1.0.0"),
        "environment": getattr(settings, "ENVIRONMENT", "unknown"),
        "checks": {},
    }

    all_healthy = True

    # Check database connectivity
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        health_status["checks"]["database"] = {
            "status": "healthy",
            "message": "Database connection successful",
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}",
        }
        all_healthy = False

    # Check Redis cache connectivity
    try:
        cache_key = "health_check_test"
        cache_value = "ok"
        cache.set(cache_key, cache_value, timeout=10)
        retrieved_value = cache.get(cache_key)

        if retrieved_value == cache_value:
            health_status["checks"]["cache"] = {
                "status": "healthy",
                "message": "Redis cache connection successful",
            }
        else:
            raise Exception("Cache value mismatch")
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        health_status["checks"]["cache"] = {
            "status": "unhealthy",
            "message": f"Redis cache connection failed: {str(e)}",
        }
        all_healthy = False

    # Check Celery workers (optional - only if Celery is configured)
    try:
        from celery import current_app

        # Get active workers
        inspect = current_app.control.inspect()
        active_workers = inspect.active()

        if active_workers:
            worker_count = len(active_workers)
            health_status["checks"]["celery"] = {
                "status": "healthy",
                "message": f"{worker_count} Celery worker(s) active",
                "workers": list(active_workers.keys()),
            }
        else:
            health_status["checks"]["celery"] = {
                "status": "warning",
                "message": "No active Celery workers found",
            }
            # Don't mark as unhealthy - Celery might not be required for basic operation
    except Exception as e:
        logger.warning(f"Celery health check failed: {e}")
        health_status["checks"]["celery"] = {
            "status": "warning",
            "message": f"Celery check failed: {str(e)}",
        }
        # Don't mark as unhealthy - Celery might not be configured

    # Set overall status
    if not all_healthy:
        health_status["status"] = "unhealthy"
        status_code = 503
    else:
        status_code = 200

    return JsonResponse(health_status, status=status_code)


@never_cache
@require_GET
def liveness_probe(request) -> JsonResponse:
    """
    Kubernetes liveness probe endpoint.

    Returns 200 if the application process is alive.
    If this fails, Kubernetes will restart the pod.

    This is a simple check - just verifies the process is running.

    Returns:
        JsonResponse: {"status": "alive"}
    """
    return JsonResponse({"status": "alive"})


@never_cache
@require_GET
def readiness_probe(request) -> JsonResponse:
    """
    Kubernetes readiness probe endpoint.

    Returns 200 if the application is ready to serve traffic.
    If this fails, Kubernetes will stop routing traffic to this pod.

    Checks database connectivity to ensure the app is ready.

    Returns:
        JsonResponse: {"status": "ready"} or 503 if not ready
    """
    try:
        # Check database connectivity
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

        return JsonResponse({"status": "ready"})
    except Exception as e:
        logger.error(f"Readiness probe failed: {e}")
        return JsonResponse({"status": "not_ready", "reason": str(e)}, status=503)


@never_cache
@require_GET
def startup_probe(request) -> JsonResponse:
    """
    Kubernetes startup probe endpoint.

    Returns 200 if the application has completed initialization.
    If this fails, Kubernetes will restart the pod.

    This probe allows more time for slow-starting containers.
    Once this succeeds, liveness and readiness probes take over.

    Checks:
    - Database connectivity (critical for startup)
    - Cache connectivity (critical for startup)

    Returns:
        JsonResponse: {"status": "started"} or 503 if not started
    """
    try:
        # Check database connectivity
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

        # Check cache connectivity
        cache_key = "startup_check"
        cache.set(cache_key, "ok", timeout=10)
        cache.get(cache_key)

        return JsonResponse({"status": "started"})
    except Exception as e:
        logger.error(f"Startup probe failed: {e}")
        return JsonResponse({"status": "not_started", "reason": str(e)}, status=503)


# URL patterns for health check endpoints
urlpatterns = [
    path("", health_check, name="health"),
    path("detailed/", health_check_detailed, name="health_detailed"),
    path("live/", liveness_probe, name="liveness"),
    path("ready/", readiness_probe, name="readiness"),
    path("startup/", startup_probe, name="startup"),
]
