"""
Security monitoring services for detecting and preventing security threats.

This module implements:
- Suspicious activity detection (multiple failed logins, new locations, bulk exports)
- IP tracking and flagging
- Session monitoring with force logout capability
- Brute force protection

Per Requirement 8 - Audit Logs and Security Monitoring.
"""

import logging
from datetime import timedelta
from typing import Dict, List, Optional

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone

from apps.core.audit import log_security_event
from apps.core.audit_models import AuditLog, LoginAttempt

logger = logging.getLogger(__name__)

User = get_user_model()


# ============================================================================
# IP Tracking and Flagging
# ============================================================================


class IPTracker:
    """Track and flag suspicious IP addresses."""

    # Cache keys
    FLAGGED_IPS_KEY = "security:flagged_ips"
    IP_METADATA_KEY = "security:ip:{ip}:metadata"
    IP_LOGIN_ATTEMPTS_KEY = "security:ip:{ip}:login_attempts"

    # Thresholds
    MAX_FAILED_LOGINS_PER_IP = 10  # per hour
    MAX_FAILED_LOGINS_PER_IP_PER_DAY = 50
    BRUTE_FORCE_THRESHOLD = 5  # consecutive failures
    BRUTE_FORCE_LOCKOUT_MINUTES = 15

    @classmethod
    def track_login_attempt(cls, ip_address: str, username: str, success: bool) -> Dict:
        """
        Track a login attempt from an IP address.

        Args:
            ip_address: IP address of the attempt
            username: Username attempted
            success: Whether the login was successful

        Returns:
            Dictionary with tracking info and whether IP should be blocked
        """
        now = timezone.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        # Count recent failed attempts from this IP
        recent_failures_hour = LoginAttempt.objects.filter(
            ip_address=ip_address,
            result__in=[
                LoginAttempt.RESULT_FAILED_PASSWORD,
                LoginAttempt.RESULT_FAILED_USER_NOT_FOUND,
            ],
            timestamp__gte=hour_ago,
        ).count()

        recent_failures_day = LoginAttempt.objects.filter(
            ip_address=ip_address,
            result__in=[
                LoginAttempt.RESULT_FAILED_PASSWORD,
                LoginAttempt.RESULT_FAILED_USER_NOT_FOUND,
            ],
            timestamp__gte=day_ago,
        ).count()

        # Check for brute force pattern (consecutive failures)
        consecutive_failures = cls._count_consecutive_failures(ip_address)

        # Determine if IP should be blocked
        should_block = False
        block_reason = None

        if consecutive_failures >= cls.BRUTE_FORCE_THRESHOLD:
            should_block = True
            block_reason = f"Brute force detected: {consecutive_failures} consecutive failures"
            cls.flag_ip(ip_address, block_reason, duration_minutes=cls.BRUTE_FORCE_LOCKOUT_MINUTES)

        elif recent_failures_hour >= cls.MAX_FAILED_LOGINS_PER_IP:
            should_block = True
            block_reason = f"Too many failed logins: {recent_failures_hour} in last hour"
            cls.flag_ip(ip_address, block_reason, duration_minutes=60)

        elif recent_failures_day >= cls.MAX_FAILED_LOGINS_PER_IP_PER_DAY:
            should_block = True
            block_reason = f"Too many failed logins: {recent_failures_day} in last 24 hours"
            cls.flag_ip(ip_address, block_reason, duration_minutes=1440)  # 24 hours

        # Log suspicious activity if threshold exceeded
        if should_block:
            log_security_event(
                event_type="suspicious_activity",
                description=f"IP {ip_address} blocked: {block_reason}",
                severity="WARNING",
                metadata={
                    "ip_address": ip_address,
                    "username": username,
                    "consecutive_failures": consecutive_failures,
                    "recent_failures_hour": recent_failures_hour,
                    "recent_failures_day": recent_failures_day,
                },
            )

        return {
            "ip_address": ip_address,
            "should_block": should_block,
            "block_reason": block_reason,
            "consecutive_failures": consecutive_failures,
            "recent_failures_hour": recent_failures_hour,
            "recent_failures_day": recent_failures_day,
        }

    @classmethod
    def _count_consecutive_failures(cls, ip_address: str) -> int:
        """Count consecutive failed login attempts from an IP."""
        # Get last 20 attempts from this IP
        attempts = LoginAttempt.objects.filter(ip_address=ip_address).order_by("-timestamp")[:20]

        consecutive = 0
        for attempt in attempts:
            if attempt.is_failed():
                consecutive += 1
            else:
                # Stop counting at first success
                break

        return consecutive

    @classmethod
    def is_ip_flagged(cls, ip_address: str) -> bool:
        """Check if an IP address is currently flagged."""
        flagged_ips = cache.get(cls.FLAGGED_IPS_KEY, set())
        return ip_address in flagged_ips

    @classmethod
    def flag_ip(cls, ip_address: str, reason: str, duration_minutes: int = 60):
        """
        Flag an IP address as suspicious.

        Args:
            ip_address: IP address to flag
            reason: Reason for flagging
            duration_minutes: How long to keep the flag (default: 60 minutes)
        """
        # Add to flagged IPs set
        flagged_ips = cache.get(cls.FLAGGED_IPS_KEY, set())
        flagged_ips.add(ip_address)
        cache.set(cls.FLAGGED_IPS_KEY, flagged_ips, timeout=duration_minutes * 60)

        # Store metadata about the flag
        metadata = {
            "reason": reason,
            "flagged_at": timezone.now().isoformat(),
            "expires_at": (timezone.now() + timedelta(minutes=duration_minutes)).isoformat(),
        }
        cache.set(
            cls.IP_METADATA_KEY.format(ip=ip_address), metadata, timeout=duration_minutes * 60
        )

        logger.warning(f"IP {ip_address} flagged: {reason} (duration: {duration_minutes} minutes)")

    @classmethod
    def unflag_ip(cls, ip_address: str):
        """Remove flag from an IP address."""
        flagged_ips = cache.get(cls.FLAGGED_IPS_KEY, set())
        if ip_address in flagged_ips:
            flagged_ips.remove(ip_address)
            cache.set(cls.FLAGGED_IPS_KEY, flagged_ips)

        cache.delete(cls.IP_METADATA_KEY.format(ip=ip_address))
        logger.info(f"IP {ip_address} unflagged")

    @classmethod
    def get_ip_metadata(cls, ip_address: str) -> Optional[Dict]:
        """Get metadata about a flagged IP."""
        return cache.get(cls.IP_METADATA_KEY.format(ip=ip_address))

    @classmethod
    def get_all_flagged_ips(cls) -> List[Dict]:
        """Get all currently flagged IPs with their metadata."""
        flagged_ips = cache.get(cls.FLAGGED_IPS_KEY, set())
        result = []

        for ip in flagged_ips:
            metadata = cls.get_ip_metadata(ip)
            if metadata:
                result.append({"ip_address": ip, **metadata})

        return result


# ============================================================================
# Suspicious Activity Detection
# ============================================================================


class SuspiciousActivityDetector:
    """Detect suspicious user activity patterns."""

    @classmethod
    def detect_multiple_failed_logins(cls, user: User, time_window_hours: int = 24) -> Dict:
        """
        Detect multiple failed login attempts for a user.

        Args:
            user: User to check
            time_window_hours: Time window to check (default: 24 hours)

        Returns:
            Dictionary with detection results
        """
        since = timezone.now() - timedelta(hours=time_window_hours)

        failed_attempts = LoginAttempt.objects.filter(
            user=user,
            result__in=[
                LoginAttempt.RESULT_FAILED_PASSWORD,
                LoginAttempt.RESULT_FAILED_MFA,
            ],
            timestamp__gte=since,
        ).count()

        is_suspicious = failed_attempts >= 5

        if is_suspicious:
            log_security_event(
                event_type="suspicious_activity",
                description=f"Multiple failed login attempts detected for user {user.username}: {failed_attempts} in last {time_window_hours} hours",
                user=user,
                severity="WARNING",
                metadata={
                    "failed_attempts": failed_attempts,
                    "time_window_hours": time_window_hours,
                },
            )

        return {
            "is_suspicious": is_suspicious,
            "failed_attempts": failed_attempts,
            "time_window_hours": time_window_hours,
        }

    @classmethod
    def detect_new_location_login(cls, user: User, ip_address: str, country: str = None) -> Dict:
        """
        Detect login from a new location.

        Args:
            user: User logging in
            ip_address: IP address of login
            country: Country of IP address (optional)

        Returns:
            Dictionary with detection results
        """
        # Get user's previous login locations (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)

        previous_ips = set(
            LoginAttempt.objects.filter(
                user=user, result=LoginAttempt.RESULT_SUCCESS, timestamp__gte=thirty_days_ago
            )
            .values_list("ip_address", flat=True)
            .distinct()
        )

        is_new_location = ip_address not in previous_ips

        if is_new_location and len(previous_ips) > 0:
            # User has logged in before, but from different IPs
            log_security_event(
                event_type="suspicious_activity",
                description=f"Login from new location detected for user {user.username}: IP {ip_address}",
                user=user,
                severity="INFO",
                metadata={
                    "ip_address": ip_address,
                    "country": country,
                    "previous_ip_count": len(previous_ips),
                },
            )

        return {
            "is_new_location": is_new_location,
            "ip_address": ip_address,
            "country": country,
            "previous_ip_count": len(previous_ips),
        }

    @classmethod
    def detect_bulk_export(
        cls, user: User, export_count: int, time_window_minutes: int = 60
    ) -> Dict:
        """
        Detect suspicious bulk data export activity.

        Args:
            user: User performing exports
            export_count: Number of exports in the time window
            time_window_minutes: Time window to check (default: 60 minutes)

        Returns:
            Dictionary with detection results
        """
        # Threshold for suspicious bulk exports
        BULK_EXPORT_THRESHOLD = 10

        is_suspicious = export_count >= BULK_EXPORT_THRESHOLD

        if is_suspicious:
            log_security_event(
                event_type="suspicious_activity",
                description=f"Bulk data export detected for user {user.username}: {export_count} exports in {time_window_minutes} minutes",
                user=user,
                severity="WARNING",
                metadata={
                    "export_count": export_count,
                    "time_window_minutes": time_window_minutes,
                    "threshold": BULK_EXPORT_THRESHOLD,
                },
            )

        return {
            "is_suspicious": is_suspicious,
            "export_count": export_count,
            "time_window_minutes": time_window_minutes,
            "threshold": BULK_EXPORT_THRESHOLD,
        }

    @classmethod
    def detect_unusual_api_activity(cls, user: User, time_window_minutes: int = 60) -> Dict:
        """
        Detect unusual API activity patterns.

        Args:
            user: User to check
            time_window_minutes: Time window to check (default: 60 minutes)

        Returns:
            Dictionary with detection results
        """
        from apps.core.audit_models import APIRequestLog

        since = timezone.now() - timedelta(minutes=time_window_minutes)

        # Count API requests in time window
        api_requests = APIRequestLog.objects.filter(user=user, timestamp__gte=since).count()

        # Count failed requests (4xx, 5xx)
        failed_requests = APIRequestLog.objects.filter(
            user=user, timestamp__gte=since, status_code__gte=400
        ).count()

        # Thresholds
        HIGH_VOLUME_THRESHOLD = 1000  # requests per hour
        HIGH_FAILURE_RATE = 0.5  # 50% failure rate

        is_high_volume = api_requests >= HIGH_VOLUME_THRESHOLD
        failure_rate = failed_requests / api_requests if api_requests > 0 else 0
        is_high_failure_rate = failure_rate >= HIGH_FAILURE_RATE and api_requests >= 10

        is_suspicious = is_high_volume or is_high_failure_rate

        if is_suspicious:
            log_security_event(
                event_type="suspicious_activity",
                description=f"Unusual API activity detected for user {user.username}: {api_requests} requests ({failed_requests} failed) in {time_window_minutes} minutes",
                user=user,
                severity="WARNING",
                metadata={
                    "api_requests": api_requests,
                    "failed_requests": failed_requests,
                    "failure_rate": failure_rate,
                    "time_window_minutes": time_window_minutes,
                },
            )

        return {
            "is_suspicious": is_suspicious,
            "api_requests": api_requests,
            "failed_requests": failed_requests,
            "failure_rate": failure_rate,
            "is_high_volume": is_high_volume,
            "is_high_failure_rate": is_high_failure_rate,
        }


# ============================================================================
# Session Monitoring
# ============================================================================


class SessionMonitor:
    """Monitor and manage user sessions."""

    @classmethod
    def get_active_sessions(cls, user: User) -> List[Dict]:
        """
        Get all active sessions for a user.

        Args:
            user: User to get sessions for

        Returns:
            List of session dictionaries with metadata
        """
        sessions = []

        # Get all sessions
        for session in Session.objects.filter(expire_date__gte=timezone.now()):
            session_data = session.get_decoded()
            session_user_id = session_data.get("_auth_user_id")

            if session_user_id and int(session_user_id) == user.id:
                # Get last activity from audit logs
                last_activity = (
                    AuditLog.objects.filter(
                        user=user,
                        timestamp__gte=session.expire_date - timedelta(days=14),  # Django default
                    )
                    .order_by("-timestamp")
                    .first()
                )

                sessions.append(
                    {
                        "session_key": session.session_key,
                        "expire_date": session.expire_date,
                        "last_activity": last_activity.timestamp if last_activity else None,
                        "ip_address": last_activity.ip_address if last_activity else None,
                        "user_agent": last_activity.user_agent if last_activity else None,
                    }
                )

        return sessions

    @classmethod
    def force_logout(cls, user: User, session_key: Optional[str] = None) -> int:
        """
        Force logout a user by deleting their session(s).

        Args:
            user: User to logout
            session_key: Specific session to logout (optional, if None logs out all sessions)

        Returns:
            Number of sessions deleted
        """
        if session_key:
            # Delete specific session
            try:
                session = Session.objects.get(session_key=session_key)
                session_data = session.get_decoded()
                session_user_id = session_data.get("_auth_user_id")

                if session_user_id and int(session_user_id) == user.id:
                    session.delete()
                    count = 1
                else:
                    count = 0
            except Session.DoesNotExist:
                count = 0
        else:
            # Delete all sessions for user
            count = 0
            for session in Session.objects.filter(expire_date__gte=timezone.now()):
                session_data = session.get_decoded()
                session_user_id = session_data.get("_auth_user_id")

                if session_user_id and int(session_user_id) == user.id:
                    session.delete()
                    count += 1

        # Log the forced logout
        log_security_event(
            event_type="suspicious_activity",
            description=f"Forced logout for user {user.username}: {count} session(s) terminated",
            user=user,
            severity="WARNING",
            metadata={
                "sessions_terminated": count,
                "session_key": session_key,
            },
        )

        logger.warning(f"Forced logout for user {user.username}: {count} session(s) terminated")

        return count

    @classmethod
    def get_concurrent_sessions_count(cls, user: User) -> int:
        """Get the number of concurrent active sessions for a user."""
        return len(cls.get_active_sessions(user))

    @classmethod
    def detect_session_hijacking(cls, user: User) -> Dict:
        """
        Detect potential session hijacking by analyzing session patterns.

        Args:
            user: User to check

        Returns:
            Dictionary with detection results
        """
        sessions = cls.get_active_sessions(user)

        # Check for multiple concurrent sessions from different IPs
        unique_ips = set()
        for session in sessions:
            if session.get("ip_address"):
                unique_ips.add(session["ip_address"])

        # Suspicious if more than 3 different IPs with active sessions
        is_suspicious = len(unique_ips) > 3 and len(sessions) > 1

        if is_suspicious:
            log_security_event(
                event_type="suspicious_activity",
                description=f"Potential session hijacking detected for user {user.username}: {len(sessions)} active sessions from {len(unique_ips)} different IPs",
                user=user,
                severity="WARNING",
                metadata={
                    "active_sessions": len(sessions),
                    "unique_ips": len(unique_ips),
                    "ip_addresses": list(unique_ips),
                },
            )

        return {
            "is_suspicious": is_suspicious,
            "active_sessions": len(sessions),
            "unique_ips": len(unique_ips),
            "sessions": sessions,
        }


# ============================================================================
# Brute Force Protection
# ============================================================================


class BruteForceProtection:
    """Implement brute force protection mechanisms."""

    # Cache keys
    LOGIN_ATTEMPTS_KEY = "security:login_attempts:{identifier}"
    ACCOUNT_LOCKOUT_KEY = "security:account_lockout:{user_id}"

    # Configuration
    MAX_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15
    ATTEMPT_WINDOW_MINUTES = 15

    @classmethod
    def check_and_increment(cls, identifier: str) -> Dict:
        """
        Check if login should be allowed and increment attempt counter.

        Args:
            identifier: Unique identifier (username, email, or IP address)

        Returns:
            Dictionary with check results
        """
        cache_key = cls.LOGIN_ATTEMPTS_KEY.format(identifier=identifier)

        # Get current attempt count
        attempts = cache.get(cache_key, 0)

        # Check if locked out
        if attempts >= cls.MAX_ATTEMPTS:
            return {
                "allowed": False,
                "attempts": attempts,
                "max_attempts": cls.MAX_ATTEMPTS,
                "lockout_duration_minutes": cls.LOCKOUT_DURATION_MINUTES,
                "reason": "Too many failed login attempts. Account temporarily locked.",
            }

        # Increment attempt counter
        attempts += 1
        cache.set(cache_key, attempts, timeout=cls.ATTEMPT_WINDOW_MINUTES * 60)

        return {
            "allowed": True,
            "attempts": attempts,
            "max_attempts": cls.MAX_ATTEMPTS,
            "remaining_attempts": cls.MAX_ATTEMPTS - attempts,
        }

    @classmethod
    def reset_attempts(cls, identifier: str):
        """Reset login attempt counter for an identifier."""
        cache_key = cls.LOGIN_ATTEMPTS_KEY.format(identifier=identifier)
        cache.delete(cache_key)

    @classmethod
    def is_locked_out(cls, identifier: str) -> bool:
        """Check if an identifier is currently locked out."""
        cache_key = cls.LOGIN_ATTEMPTS_KEY.format(identifier=identifier)
        attempts = cache.get(cache_key, 0)
        return attempts >= cls.MAX_ATTEMPTS

    @classmethod
    def get_lockout_info(cls, identifier: str) -> Optional[Dict]:
        """Get lockout information for an identifier."""
        cache_key = cls.LOGIN_ATTEMPTS_KEY.format(identifier=identifier)
        attempts = cache.get(cache_key, 0)

        if attempts >= cls.MAX_ATTEMPTS:
            # Get TTL from cache
            ttl = cache.ttl(cache_key)
            if ttl is None:
                ttl = 0

            return {
                "is_locked_out": True,
                "attempts": attempts,
                "max_attempts": cls.MAX_ATTEMPTS,
                "lockout_duration_minutes": cls.LOCKOUT_DURATION_MINUTES,
                "time_remaining_seconds": ttl,
            }

        return None

    @classmethod
    def lock_account(cls, user: User, duration_minutes: Optional[int] = None):
        """
        Manually lock a user account.

        Args:
            user: User to lock
            duration_minutes: Lock duration (default: LOCKOUT_DURATION_MINUTES)
        """
        if duration_minutes is None:
            duration_minutes = cls.LOCKOUT_DURATION_MINUTES

        cache_key = cls.ACCOUNT_LOCKOUT_KEY.format(user_id=user.id)
        cache.set(cache_key, True, timeout=duration_minutes * 60)

        log_security_event(
            event_type="suspicious_activity",
            description=f"Account locked for user {user.username} for {duration_minutes} minutes",
            user=user,
            severity="WARNING",
            metadata={
                "duration_minutes": duration_minutes,
            },
        )

        logger.warning(f"Account locked for user {user.username} for {duration_minutes} minutes")

    @classmethod
    def unlock_account(cls, user: User):
        """Manually unlock a user account."""
        cache_key = cls.ACCOUNT_LOCKOUT_KEY.format(user_id=user.id)
        cache.delete(cache_key)

        # Also reset login attempts
        cls.reset_attempts(user.username)
        if user.email:
            cls.reset_attempts(user.email)

        logger.info(f"Account unlocked for user {user.username}")

    @classmethod
    def is_account_locked(cls, user: User) -> bool:
        """Check if a user account is manually locked."""
        cache_key = cls.ACCOUNT_LOCKOUT_KEY.format(user_id=user.id)
        return cache.get(cache_key, False)


# ============================================================================
# Security Dashboard Data
# ============================================================================


def get_security_dashboard_data(time_window_hours: int = 24) -> Dict:
    """
    Get aggregated security monitoring data for dashboard.

    Args:
        time_window_hours: Time window for statistics (default: 24 hours)

    Returns:
        Dictionary with security statistics
    """
    since = timezone.now() - timedelta(hours=time_window_hours)

    # Failed login attempts
    failed_logins = LoginAttempt.objects.filter(
        timestamp__gte=since,
        result__in=[
            LoginAttempt.RESULT_FAILED_PASSWORD,
            LoginAttempt.RESULT_FAILED_USER_NOT_FOUND,
        ],
    ).count()

    # Successful logins
    successful_logins = LoginAttempt.objects.filter(
        timestamp__gte=since, result=LoginAttempt.RESULT_SUCCESS
    ).count()

    # Security events
    security_events = AuditLog.objects.filter(
        timestamp__gte=since, category=AuditLog.CATEGORY_SECURITY
    ).count()

    # Flagged IPs
    flagged_ips = IPTracker.get_all_flagged_ips()

    # Top failed login IPs
    top_failed_ips = (
        LoginAttempt.objects.filter(
            timestamp__gte=since,
            result__in=[
                LoginAttempt.RESULT_FAILED_PASSWORD,
                LoginAttempt.RESULT_FAILED_USER_NOT_FOUND,
            ],
        )
        .values("ip_address")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    # Recent security events
    recent_events = AuditLog.objects.filter(
        timestamp__gte=since, category=AuditLog.CATEGORY_SECURITY
    ).order_by("-timestamp")[:20]

    return {
        "time_window_hours": time_window_hours,
        "failed_logins": failed_logins,
        "successful_logins": successful_logins,
        "security_events": security_events,
        "flagged_ips_count": len(flagged_ips),
        "flagged_ips": flagged_ips,
        "top_failed_ips": list(top_failed_ips),
        "recent_events": [
            {
                "id": str(event.id),
                "action": event.action,
                "description": event.description,
                "severity": event.severity,
                "timestamp": event.timestamp.isoformat(),
                "user": event.user.username if event.user else None,
                "ip_address": event.ip_address,
            }
            for event in recent_events
        ],
    }
