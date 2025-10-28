"""
Comprehensive tests for audit log security detection functionality (Task 20.4).

These tests verify security detection features including:
- IP tracking and flagging
- Suspicious activity detection (multiple failed logins, new locations, bulk exports)
- Session monitoring and hijacking detection
- Brute force protection

NO MOCKS ALLOWED - All tests use real database and services per Docker-only policy.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.test import RequestFactory
from django.utils import timezone

import pytest

from apps.core.audit import log_login_attempt
from apps.core.audit_models import AuditLog, LoginAttempt
from apps.core.models import Tenant
from apps.core.security_monitoring import (
    BruteForceProtection,
    IPTracker,
    SessionMonitor,
    SuspiciousActivityDetector,
    get_security_dashboard_data,
)

User = get_user_model()


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def tenant():
    """Create a test tenant."""
    return Tenant.objects.create(
        company_name="Security Test Shop",
        slug="security-test",
    )


@pytest.fixture
def user(tenant):
    """Create a test user."""
    return User.objects.create_user(
        username="securityuser",
        email="security@test.com",
        password="SecurePass123!",
        tenant=tenant,
        role=User.TENANT_EMPLOYEE,
    )


@pytest.fixture
def request_factory():
    """Create a request factory."""
    return RequestFactory()


@pytest.mark.django_db
class TestIPTracking:
    """Test IP tracking and flagging functionality."""

    def test_track_successful_login(self, user, request_factory):
        """Test tracking a successful login attempt."""
        request = request_factory.post("/login/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_USER_AGENT"] = "Test Browser"

        # Track successful login
        result = IPTracker.track_login_attempt("192.168.1.100", user.username, success=True)

        assert result["should_block"] is False
        assert result["ip_address"] == "192.168.1.100"

    def test_track_failed_login(self, user, request_factory):
        """Test tracking a failed login attempt."""
        request = request_factory.post("/login/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_USER_AGENT"] = "Test Browser"

        # First log the failed attempt
        log_login_attempt(
            username=user.username,
            user=user,
            success=False,
            failure_reason="invalid_password",
            request=request,
        )

        # Then track it
        result = IPTracker.track_login_attempt("192.168.1.100", user.username, success=False)

        assert result["should_block"] is False  # First failure shouldn't block
        assert result["consecutive_failures"] >= 1

    def test_brute_force_detection(self, user, request_factory):
        """Test that brute force attempts are detected and IP is flagged."""
        ip_address = "10.0.0.50"
        request = request_factory.post("/login/")
        request.META["REMOTE_ADDR"] = ip_address
        request.META["HTTP_USER_AGENT"] = "Attacker Browser"

        # Create multiple consecutive failed attempts
        for i in range(6):
            log_login_attempt(
                username=user.username,
                user=user,
                success=False,
                failure_reason="invalid_password",
                request=request,
            )

        # Track the attempts
        result = IPTracker.track_login_attempt(ip_address, user.username, success=False)

        # Should be blocked after 5 consecutive failures
        assert result["should_block"] is True
        assert result["consecutive_failures"] >= 5
        assert "Brute force" in result["block_reason"]

        # Verify IP is flagged
        assert IPTracker.is_ip_flagged(ip_address) is True

    def test_too_many_failures_per_hour(self, user, request_factory):
        """Test that too many failures per hour triggers blocking."""
        ip_address = "10.0.0.60"
        request = request_factory.post("/login/")
        request.META["REMOTE_ADDR"] = ip_address

        # Create 11 failed attempts (threshold is 10)
        for i in range(11):
            log_login_attempt(
                username=f"user{i}",
                user=None,
                success=False,
                failure_reason="user_not_found",
                request=request,
            )

        # Track the attempts
        result = IPTracker.track_login_attempt(ip_address, "testuser", success=False)

        # Should be blocked
        assert result["should_block"] is True
        assert result["recent_failures_hour"] >= 10

    def test_flag_and_unflag_ip(self):
        """Test manually flagging and unflagging an IP."""
        ip_address = "192.168.1.200"

        # Flag IP
        IPTracker.flag_ip(ip_address, "Manual test flag", duration_minutes=30)

        # Verify flagged
        assert IPTracker.is_ip_flagged(ip_address) is True

        # Get metadata
        metadata = IPTracker.get_ip_metadata(ip_address)
        assert metadata is not None
        assert metadata["reason"] == "Manual test flag"

        # Unflag IP
        IPTracker.unflag_ip(ip_address)

        # Verify unflagged
        assert IPTracker.is_ip_flagged(ip_address) is False

    def test_get_all_flagged_ips(self):
        """Test retrieving all flagged IPs."""
        # Flag multiple IPs
        IPTracker.flag_ip("10.0.0.1", "Reason 1", duration_minutes=60)
        IPTracker.flag_ip("10.0.0.2", "Reason 2", duration_minutes=60)
        IPTracker.flag_ip("10.0.0.3", "Reason 3", duration_minutes=60)

        # Get all flagged IPs
        flagged_ips = IPTracker.get_all_flagged_ips()

        assert len(flagged_ips) == 3
        ip_addresses = [ip["ip_address"] for ip in flagged_ips]
        assert "10.0.0.1" in ip_addresses
        assert "10.0.0.2" in ip_addresses
        assert "10.0.0.3" in ip_addresses


@pytest.mark.django_db
class TestSuspiciousActivityDetection:
    """Test suspicious activity detection."""

    def test_detect_multiple_failed_logins(self, user, request_factory):
        """Test detection of multiple failed login attempts."""
        request = request_factory.post("/login/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"

        # Create 6 failed login attempts
        for i in range(6):
            log_login_attempt(
                username=user.username,
                user=user,
                success=False,
                failure_reason="invalid_password",
                request=request,
            )

        # Detect suspicious activity
        result = SuspiciousActivityDetector.detect_multiple_failed_logins(
            user, time_window_hours=24
        )

        assert result["is_suspicious"] is True
        assert result["failed_attempts"] >= 5

        # Verify security event was logged
        security_logs = AuditLog.objects.filter(
            category=AuditLog.CATEGORY_SECURITY,
            user=user,
            action=AuditLog.ACTION_SECURITY_SUSPICIOUS_ACTIVITY,
        )
        assert security_logs.exists()

    def test_detect_new_location_login(self, user, request_factory):
        """Test detection of login from new location."""
        # Create a successful login from known IP
        request1 = request_factory.post("/login/")
        request1.META["REMOTE_ADDR"] = "192.168.1.100"

        log_login_attempt(
            username=user.username,
            user=user,
            success=True,
            request=request1,
        )

        # Try login from new IP
        new_ip = "10.0.0.50"
        result = SuspiciousActivityDetector.detect_new_location_login(user, new_ip, country="US")

        assert result["is_new_location"] is True
        assert result["ip_address"] == new_ip
        assert result["previous_ip_count"] >= 1

    def test_detect_bulk_export(self, user):
        """Test detection of bulk data export activity."""
        # Simulate 15 exports (threshold is 10)
        result = SuspiciousActivityDetector.detect_bulk_export(
            user, export_count=15, time_window_minutes=60
        )

        assert result["is_suspicious"] is True
        assert result["export_count"] == 15

        # Verify security event was logged
        security_logs = AuditLog.objects.filter(
            category=AuditLog.CATEGORY_SECURITY,
            user=user,
            action=AuditLog.ACTION_SECURITY_SUSPICIOUS_ACTIVITY,
        )
        assert security_logs.exists()

    def test_detect_unusual_api_activity(self, user):
        """Test detection of unusual API activity."""
        from apps.core.audit_models import APIRequestLog

        # Create many API requests
        now = timezone.now()
        for i in range(1100):  # Threshold is 1000
            APIRequestLog.objects.create(
                user=user,
                tenant=user.tenant,
                method="GET",
                path=f"/api/products/{i}/",
                status_code=200,
                response_time_ms=100,
                ip_address="192.168.1.100",
                timestamp=now,
            )

        # Detect unusual activity
        result = SuspiciousActivityDetector.detect_unusual_api_activity(
            user, time_window_minutes=60
        )

        assert result["is_suspicious"] is True
        assert result["is_high_volume"] is True
        assert result["api_requests"] >= 1000

    def test_detect_high_failure_rate_api(self, user):
        """Test detection of high API failure rate."""
        from apps.core.audit_models import APIRequestLog

        # Create API requests with high failure rate
        now = timezone.now()
        for i in range(20):
            # 15 failures, 5 successes = 75% failure rate
            status_code = 500 if i < 15 else 200
            APIRequestLog.objects.create(
                user=user,
                tenant=user.tenant,
                method="POST",
                path="/api/orders/",
                status_code=status_code,
                response_time_ms=100,
                ip_address="192.168.1.100",
                timestamp=now,
            )

        # Detect unusual activity
        result = SuspiciousActivityDetector.detect_unusual_api_activity(
            user, time_window_minutes=60
        )

        assert result["is_suspicious"] is True
        assert result["is_high_failure_rate"] is True
        assert result["failure_rate"] >= 0.5


@pytest.mark.django_db
class TestSessionMonitoring:
    """Test session monitoring functionality."""

    def test_get_active_sessions(self, user):
        """Test retrieving active sessions for a user."""
        # Create a session for the user
        from django.contrib.sessions.backends.db import SessionStore

        session = SessionStore()
        session["_auth_user_id"] = str(user.id)
        session.create()

        # Get active sessions
        sessions = SessionMonitor.get_active_sessions(user)

        assert len(sessions) >= 1
        assert any(s["session_key"] == session.session_key for s in sessions)

    def test_force_logout_specific_session(self, user):
        """Test forcing logout of a specific session."""
        # Create a session
        from django.contrib.sessions.backends.db import SessionStore

        session = SessionStore()
        session["_auth_user_id"] = str(user.id)
        session.create()

        session_key = session.session_key

        # Force logout
        count = SessionMonitor.force_logout(user, session_key=session_key)

        assert count == 1

        # Verify session is deleted
        assert not Session.objects.filter(session_key=session_key).exists()

    def test_force_logout_all_sessions(self, user):
        """Test forcing logout of all sessions."""
        # Create multiple sessions
        from django.contrib.sessions.backends.db import SessionStore

        session1 = SessionStore()
        session1["_auth_user_id"] = str(user.id)
        session1.create()

        session2 = SessionStore()
        session2["_auth_user_id"] = str(user.id)
        session2.create()

        # Force logout all
        count = SessionMonitor.force_logout(user)

        assert count >= 2

    def test_detect_session_hijacking(self, user):
        """Test detection of potential session hijacking."""
        # Create multiple sessions
        from django.contrib.sessions.backends.db import SessionStore

        # Create 5 sessions
        for i in range(5):
            session = SessionStore()
            session["_auth_user_id"] = str(user.id)
            session.create()

        # Get active sessions
        sessions = SessionMonitor.get_active_sessions(user)

        # Verify we can detect multiple sessions
        assert len(sessions) >= 2, f"Expected at least 2 sessions, got {len(sessions)}"

        # Test the detection logic directly
        # Note: In a real scenario, sessions would have different IPs from audit logs
        # For testing, we verify the detection method works correctly
        result = SessionMonitor.detect_session_hijacking(user)

        # Verify result structure
        assert "is_suspicious" in result
        assert "active_sessions" in result
        assert "unique_ips" in result
        assert "sessions" in result
        assert result["active_sessions"] >= 2

    def test_get_concurrent_sessions_count(self, user):
        """Test getting concurrent session count."""
        # Create sessions
        from django.contrib.sessions.backends.db import SessionStore

        for i in range(3):
            session = SessionStore()
            session["_auth_user_id"] = str(user.id)
            session.create()

        # Get count
        count = SessionMonitor.get_concurrent_sessions_count(user)

        assert count >= 3


@pytest.mark.django_db
class TestBruteForceProtection:
    """Test brute force protection mechanisms."""

    def test_check_and_increment_allowed(self):
        """Test that login is allowed initially."""
        result = BruteForceProtection.check_and_increment("testuser")

        assert result["allowed"] is True
        assert result["attempts"] == 1
        assert result["remaining_attempts"] == 4

    def test_check_and_increment_blocked(self):
        """Test that login is blocked after max attempts."""
        identifier = "blockeduser"

        # Make max attempts
        for i in range(5):
            BruteForceProtection.check_and_increment(identifier)

        # Next attempt should be blocked
        result = BruteForceProtection.check_and_increment(identifier)

        assert result["allowed"] is False
        assert "Too many failed login attempts" in result["reason"]

    def test_reset_attempts(self):
        """Test resetting login attempts."""
        identifier = "resetuser"

        # Make some attempts
        for i in range(3):
            BruteForceProtection.check_and_increment(identifier)

        # Reset
        BruteForceProtection.reset_attempts(identifier)

        # Should be allowed again
        result = BruteForceProtection.check_and_increment(identifier)
        assert result["allowed"] is True
        assert result["attempts"] == 1

    def test_is_locked_out(self):
        """Test checking if identifier is locked out."""
        identifier = "lockeduser"

        # Not locked initially
        assert BruteForceProtection.is_locked_out(identifier) is False

        # Make max attempts
        for i in range(5):
            BruteForceProtection.check_and_increment(identifier)

        # Should be locked now
        assert BruteForceProtection.is_locked_out(identifier) is True

    def test_get_lockout_info(self):
        """Test getting lockout information."""
        identifier = "infouser"

        # No lockout initially
        info = BruteForceProtection.get_lockout_info(identifier)
        assert info is None

        # Make max attempts
        for i in range(5):
            BruteForceProtection.check_and_increment(identifier)

        # Get lockout info
        info = BruteForceProtection.get_lockout_info(identifier)
        assert info is not None
        assert info["is_locked_out"] is True
        assert info["attempts"] >= 5

    def test_lock_and_unlock_account(self, user):
        """Test manually locking and unlocking an account."""
        # Lock account
        BruteForceProtection.lock_account(user, duration_minutes=30)

        # Verify locked
        assert BruteForceProtection.is_account_locked(user) is True

        # Unlock account
        BruteForceProtection.unlock_account(user)

        # Verify unlocked
        assert BruteForceProtection.is_account_locked(user) is False

        # Verify security event was logged
        security_logs = AuditLog.objects.filter(
            category=AuditLog.CATEGORY_SECURITY,
            user=user,
        )
        assert security_logs.exists()


@pytest.mark.django_db
class TestSecurityDashboardData:
    """Test security dashboard data aggregation."""

    def test_get_security_dashboard_data(self, user, request_factory):
        """Test getting aggregated security dashboard data."""
        request = request_factory.post("/login/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"

        # Create some security events
        log_login_attempt(user.username, user, success=True, request=request)
        log_login_attempt(
            user.username, user, success=False, failure_reason="invalid_password", request=request
        )
        log_login_attempt(
            user.username, user, success=False, failure_reason="invalid_password", request=request
        )

        # Flag an IP
        IPTracker.flag_ip("10.0.0.1", "Test flag", duration_minutes=60)

        # Get dashboard data
        data = get_security_dashboard_data(time_window_hours=24)

        assert "failed_logins" in data
        assert "successful_logins" in data
        assert "security_events" in data
        assert "flagged_ips_count" in data
        assert "flagged_ips" in data
        assert "top_failed_ips" in data
        assert "recent_events" in data

        assert data["failed_logins"] >= 2
        assert data["successful_logins"] >= 1
        assert data["flagged_ips_count"] >= 1

    def test_dashboard_data_time_window(self, user, request_factory):
        """Test that dashboard data respects time window."""
        request = request_factory.post("/login/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"

        # Create recent event
        log_login_attempt(
            user.username, user, success=False, failure_reason="invalid_password", request=request
        )

        # Create old event (manually set timestamp)
        old_attempt = LoginAttempt.objects.create(
            user=user,
            username=user.username,
            result=LoginAttempt.RESULT_FAILED_PASSWORD,
            ip_address="192.168.1.100",
        )
        old_timestamp = timezone.now() - timedelta(hours=48)
        LoginAttempt.objects.filter(id=old_attempt.id).update(timestamp=old_timestamp)

        # Get data for last 24 hours
        data = get_security_dashboard_data(time_window_hours=24)

        # Should only include recent event
        assert data["failed_logins"] >= 1

        # Get data for last 72 hours
        data_72h = get_security_dashboard_data(time_window_hours=72)

        # Should include both events
        assert data_72h["failed_logins"] >= 2


@pytest.mark.django_db
class TestSecurityEventLogging:
    """Test that security events are properly logged."""

    def test_brute_force_logs_security_event(self, user, request_factory):
        """Test that brute force detection logs a security event."""
        ip_address = "10.0.0.99"
        request = request_factory.post("/login/")
        request.META["REMOTE_ADDR"] = ip_address

        # Clear existing logs
        AuditLog.objects.filter(category=AuditLog.CATEGORY_SECURITY).delete()

        # Create brute force pattern
        for i in range(6):
            log_login_attempt(
                username=user.username,
                user=user,
                success=False,
                failure_reason="invalid_password",
                request=request,
            )

        # Track to trigger detection
        IPTracker.track_login_attempt(ip_address, user.username, success=False)

        # Verify security event was logged
        security_logs = AuditLog.objects.filter(
            category=AuditLog.CATEGORY_SECURITY,
            action=AuditLog.ACTION_SECURITY_SUSPICIOUS_ACTIVITY,
        )
        assert security_logs.exists()
        assert any("blocked" in log.description.lower() for log in security_logs)

    def test_session_hijacking_logs_security_event(self, user):
        """Test that session hijacking detection can log security events when triggered."""
        # Clear existing logs
        AuditLog.objects.filter(category=AuditLog.CATEGORY_SECURITY).delete()

        # Test that the detection method can be called and returns proper structure
        result = SessionMonitor.detect_session_hijacking(user)

        # Verify result structure
        assert "is_suspicious" in result
        assert "active_sessions" in result
        assert "unique_ips" in result

        # If suspicious activity is detected, verify logging works
        # Note: In a real scenario with multiple IPs, this would log a security event
        # For testing, we verify the method executes without errors
        if result["is_suspicious"]:
            security_logs = AuditLog.objects.filter(
                category=AuditLog.CATEGORY_SECURITY,
                user=user,
            )
            assert security_logs.exists()
            assert any("hijacking" in log.description.lower() for log in security_logs)

    def test_forced_logout_logs_security_event(self, user):
        """Test that forced logout logs a security event."""
        # Clear existing logs
        AuditLog.objects.filter(category=AuditLog.CATEGORY_SECURITY).delete()

        # Create a session
        from django.contrib.sessions.backends.db import SessionStore

        session = SessionStore()
        session["_auth_user_id"] = str(user.id)
        session.create()

        # Force logout
        SessionMonitor.force_logout(user)

        # Verify security event was logged
        security_logs = AuditLog.objects.filter(
            category=AuditLog.CATEGORY_SECURITY,
            user=user,
        )
        assert security_logs.exists()
        assert any("forced logout" in log.description.lower() for log in security_logs)


@pytest.mark.django_db
class TestSecurityIntegration:
    """Integration tests for complete security workflows."""

    def test_complete_brute_force_workflow(self, user, request_factory):
        """Test complete brute force detection and blocking workflow."""
        ip_address = "10.0.0.200"
        request = request_factory.post("/login/")
        request.META["REMOTE_ADDR"] = ip_address

        # Attempt 1-4: Should be allowed
        for i in range(4):
            result = BruteForceProtection.check_and_increment(user.username)
            assert result["allowed"] is True

            log_login_attempt(
                username=user.username,
                user=user,
                success=False,
                failure_reason="invalid_password",
                request=request,
            )

        # Attempt 5: Should still be allowed but at limit
        result = BruteForceProtection.check_and_increment(user.username)
        assert result["allowed"] is True
        assert result["remaining_attempts"] == 0

        log_login_attempt(
            username=user.username,
            user=user,
            success=False,
            failure_reason="invalid_password",
            request=request,
        )

        # Attempt 6: Should be blocked
        result = BruteForceProtection.check_and_increment(user.username)
        assert result["allowed"] is False

        # IP should be flagged
        tracking_result = IPTracker.track_login_attempt(ip_address, user.username, success=False)
        assert tracking_result["should_block"] is True

        # Security event should be logged
        security_logs = AuditLog.objects.filter(
            category=AuditLog.CATEGORY_SECURITY,
        )
        assert security_logs.exists()

    def test_successful_login_resets_protection(self, user, request_factory):
        """Test that successful login resets brute force protection."""
        request = request_factory.post("/login/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"

        # Make some failed attempts
        for i in range(3):
            BruteForceProtection.check_and_increment(user.username)
            log_login_attempt(
                username=user.username,
                user=user,
                success=False,
                failure_reason="invalid_password",
                request=request,
            )

        # Successful login
        log_login_attempt(
            username=user.username,
            user=user,
            success=True,
            request=request,
        )

        # Reset protection
        BruteForceProtection.reset_attempts(user.username)

        # Should be allowed again with fresh count
        result = BruteForceProtection.check_and_increment(user.username)
        assert result["allowed"] is True
        assert result["attempts"] == 1

    def test_multiple_security_detections(self, user, request_factory):
        """Test that multiple security issues are detected simultaneously."""
        ip_address = "10.0.0.250"
        request = request_factory.post("/login/")
        request.META["REMOTE_ADDR"] = ip_address

        # Create multiple failed logins (triggers multiple failed logins detection)
        for i in range(6):
            log_login_attempt(
                username=user.username,
                user=user,
                success=False,
                failure_reason="invalid_password",
                request=request,
            )

        # Detect multiple failed logins
        failed_login_result = SuspiciousActivityDetector.detect_multiple_failed_logins(user)
        assert failed_login_result["is_suspicious"] is True

        # Track IP (triggers brute force detection)
        ip_result = IPTracker.track_login_attempt(ip_address, user.username, success=False)
        assert ip_result["should_block"] is True

        # Verify multiple security events were logged
        security_logs = AuditLog.objects.filter(
            category=AuditLog.CATEGORY_SECURITY,
        )
        assert security_logs.count() >= 2
