"""
Views for security monitoring and management.

Provides interfaces for:
- Security dashboard
- IP management (flagging/unflagging)
- Session monitoring and force logout
- Brute force protection management
"""

import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.core.decorators import platform_admin_required
from apps.core.security_monitoring import (
    BruteForceProtection,
    IPTracker,
    SessionMonitor,
    SuspiciousActivityDetector,
    get_security_dashboard_data,
)

logger = logging.getLogger(__name__)

User = get_user_model()


# ============================================================================
# Security Dashboard
# ============================================================================


@login_required
@platform_admin_required
def security_dashboard(request):
    """
    Security monitoring dashboard.

    Shows:
    - Failed login statistics
    - Flagged IPs
    - Recent security events
    - Top suspicious IPs
    """
    # Get time window from query params (default: 24 hours)
    time_window = int(request.GET.get("time_window", 24))

    # Get dashboard data
    dashboard_data = get_security_dashboard_data(time_window_hours=time_window)

    context = {
        "dashboard_data": dashboard_data,
        "time_window": time_window,
        "page_title": "Security Monitoring Dashboard",
    }

    return render(request, "core/security/dashboard.html", context)


# ============================================================================
# IP Management
# ============================================================================


@login_required
@platform_admin_required
def flagged_ips_list(request):
    """List all flagged IP addresses."""
    flagged_ips = IPTracker.get_all_flagged_ips()

    context = {
        "flagged_ips": flagged_ips,
        "page_title": "Flagged IP Addresses",
    }

    return render(request, "core/security/flagged_ips.html", context)


@login_required
@platform_admin_required
@require_POST
def flag_ip(request):
    """Manually flag an IP address."""
    ip_address = request.POST.get("ip_address")
    reason = request.POST.get("reason", "Manually flagged by administrator")
    duration_minutes = int(request.POST.get("duration_minutes", 60))

    if not ip_address:
        messages.error(request, "IP address is required")
        return redirect("core:flagged_ips_list")

    IPTracker.flag_ip(ip_address, reason, duration_minutes)
    messages.success(request, f"IP {ip_address} has been flagged for {duration_minutes} minutes")

    return redirect("core:flagged_ips_list")


@login_required
@platform_admin_required
@require_POST
def unflag_ip(request):
    """Manually unflag an IP address."""
    ip_address = request.POST.get("ip_address")

    if not ip_address:
        messages.error(request, "IP address is required")
        return redirect("core:flagged_ips_list")

    IPTracker.unflag_ip(ip_address)
    messages.success(request, f"IP {ip_address} has been unflagged")

    return redirect("core:flagged_ips_list")


# ============================================================================
# Session Monitoring
# ============================================================================


@login_required
@platform_admin_required
def user_sessions(request, user_id):
    """View active sessions for a specific user."""
    user = get_object_or_404(User, id=user_id)

    # Get active sessions
    sessions = SessionMonitor.get_active_sessions(user)

    # Check for session hijacking
    hijacking_detection = SessionMonitor.detect_session_hijacking(user)

    context = {
        "target_user": user,
        "sessions": sessions,
        "session_count": len(sessions),
        "hijacking_detection": hijacking_detection,
        "page_title": f"Active Sessions - {user.username}",
    }

    return render(request, "core/security/user_sessions.html", context)


@login_required
@platform_admin_required
@require_POST
def force_logout_user(request, user_id):
    """Force logout a user (all sessions or specific session)."""
    user = get_object_or_404(User, id=user_id)
    session_key = request.POST.get("session_key")

    count = SessionMonitor.force_logout(user, session_key)

    if count > 0:
        messages.success(request, f"Successfully terminated {count} session(s) for {user.username}")
    else:
        messages.warning(request, f"No active sessions found for {user.username}")

    return redirect("core:user_sessions", user_id=user_id)


# ============================================================================
# Brute Force Protection Management
# ============================================================================


@login_required
@platform_admin_required
def brute_force_status(request):
    """View brute force protection status and locked accounts."""
    # This would require tracking locked accounts in the database
    # For now, we'll show a simple status page

    context = {
        "max_attempts": BruteForceProtection.MAX_ATTEMPTS,
        "lockout_duration": BruteForceProtection.LOCKOUT_DURATION_MINUTES,
        "attempt_window": BruteForceProtection.ATTEMPT_WINDOW_MINUTES,
        "page_title": "Brute Force Protection Status",
    }

    return render(request, "core/security/brute_force_status.html", context)


@login_required
@platform_admin_required
@require_POST
def unlock_account(request, user_id):
    """Manually unlock a user account."""
    user = get_object_or_404(User, id=user_id)

    BruteForceProtection.unlock_account(user)
    messages.success(request, f"Account unlocked for {user.username}")

    return redirect("core:user_detail", user_id=user_id)


@login_required
@platform_admin_required
@require_POST
def lock_account(request, user_id):
    """Manually lock a user account."""
    user = get_object_or_404(User, id=user_id)
    duration_minutes = int(request.POST.get("duration_minutes", 15))

    BruteForceProtection.lock_account(user, duration_minutes)
    messages.success(request, f"Account locked for {user.username} for {duration_minutes} minutes")

    return redirect("core:user_detail", user_id=user_id)


# ============================================================================
# Suspicious Activity Detection
# ============================================================================


@login_required
@platform_admin_required
def suspicious_activity_report(request):
    """Generate a report of suspicious activity."""
    # Get time window from query params (default: 24 hours)
    time_window = int(request.GET.get("time_window", 24))

    # Get users with multiple failed logins
    from datetime import timedelta

    from django.db.models import Count
    from django.utils import timezone

    from apps.core.audit_models import LoginAttempt

    since = timezone.now() - timedelta(hours=time_window)

    # Users with multiple failed logins
    users_with_failures = (
        LoginAttempt.objects.filter(
            timestamp__gte=since,
            result__in=[
                LoginAttempt.RESULT_FAILED_PASSWORD,
                LoginAttempt.RESULT_FAILED_MFA,
            ],
            user__isnull=False,
        )
        .values("user__id", "user__username")
        .annotate(failure_count=Count("id"))
        .filter(failure_count__gte=5)
        .order_by("-failure_count")
    )

    # IPs with multiple failed logins
    ips_with_failures = (
        LoginAttempt.objects.filter(
            timestamp__gte=since,
            result__in=[
                LoginAttempt.RESULT_FAILED_PASSWORD,
                LoginAttempt.RESULT_FAILED_USER_NOT_FOUND,
            ],
        )
        .values("ip_address")
        .annotate(failure_count=Count("id"))
        .filter(failure_count__gte=10)
        .order_by("-failure_count")
    )

    context = {
        "time_window": time_window,
        "users_with_failures": users_with_failures,
        "ips_with_failures": ips_with_failures,
        "page_title": "Suspicious Activity Report",
    }

    return render(request, "core/security/suspicious_activity_report.html", context)


# ============================================================================
# API Endpoints (JSON responses)
# ============================================================================


@login_required
@platform_admin_required
@require_http_methods(["GET"])
def api_security_stats(request):
    """API endpoint for security statistics (for HTMX updates)."""
    time_window = int(request.GET.get("time_window", 24))
    dashboard_data = get_security_dashboard_data(time_window_hours=time_window)

    return JsonResponse(dashboard_data)


@login_required
@platform_admin_required
@require_http_methods(["GET"])
def api_check_ip(request, ip_address):
    """API endpoint to check if an IP is flagged."""
    is_flagged = IPTracker.is_ip_flagged(ip_address)
    metadata = IPTracker.get_ip_metadata(ip_address) if is_flagged else None

    return JsonResponse(
        {
            "ip_address": ip_address,
            "is_flagged": is_flagged,
            "metadata": metadata,
        }
    )


@login_required
@platform_admin_required
@require_http_methods(["GET"])
def api_user_sessions(request, user_id):
    """API endpoint to get user sessions."""
    user = get_object_or_404(User, id=user_id)
    sessions = SessionMonitor.get_active_sessions(user)

    return JsonResponse(
        {
            "user_id": user_id,
            "username": user.username,
            "session_count": len(sessions),
            "sessions": sessions,
        }
    )


@login_required
@platform_admin_required
@require_http_methods(["POST"])
def api_detect_suspicious_activity(request, user_id):
    """API endpoint to run suspicious activity detection for a user."""
    user = get_object_or_404(User, id=user_id)

    # Run all detection methods
    failed_logins = SuspiciousActivityDetector.detect_multiple_failed_logins(user)
    api_activity = SuspiciousActivityDetector.detect_unusual_api_activity(user)
    session_hijacking = SessionMonitor.detect_session_hijacking(user)

    return JsonResponse(
        {
            "user_id": user_id,
            "username": user.username,
            "failed_logins": failed_logins,
            "api_activity": api_activity,
            "session_hijacking": session_hijacking,
        }
    )
