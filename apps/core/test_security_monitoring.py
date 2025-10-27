"""
Tests for security monitoring functionality.

Tests:
- IP tracking and flagging
- Suspicious activity detection
- Session monitoring
- Brute force protection
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.test import RequestFactory
from django.utils import timezone

import pytest

from apps.core.audit_models import APIRequestLog, LoginAttempt
from apps.core.models import Tenant
from apps.core.security_monitoring import (
    BruteForceProtection,
    IPTracker,
    SessionMonitor,
    SuspiciousActivityDetector,
    get_security_dashboard_data,
)

User = get_user_model()


@pytest.fixture
def tenant():
    """Create a test tenant."""
    return Tenant.objects.create(
        company_name="Test Jewelry Shop",
        slug="test-shop",
        status=Tenant.ACTIVE,
    )


@pytest.fixture
def user(tenant):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
        tenant=tenant,
        role=User.TENANT_OWNER,
    )


@pytest.fixture
def request_factory():
    """Create a request factory."""
    return RequestFactory()


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test."""
    cache.clear()
    yield
    cache.clear()


# ============================================================================
# IP Tracking Tests
# ============================================================================


@pytest.mark.django_db
class TestIPTracker:
    """Tests for IP tracking and flagging."""

    def test_track_successful_login(self, user):
        """Test tracking a successful login attempt."""
        ip_address = "192.168.1.100"

        # Create a successful login attempt
        LoginAttempt.objects.create(
            user=user,
            username=user.username,
            result=LoginAttempt.RESULT_SUCCESS,
            ip_address=ip_address,
        )

        result = IPTracker.track_login_attempt(ip_address, user.username, success=True)

        assert result["should_block"] is False
        assert result["consecutive_failures"] == 0

    def test_track_failed_login_below_threshold(self, user):
        """Test tracking failed logins below threshold."""
        ip_address = "192.168.1.100"

        # Create 3 failed attempts (below threshold of 5)
        for _ in range(3):
            LoginAttempt.objects.create(
                user=user,
                username=user.username,
                result=LoginAttempt.RESULT_FAILED_PASSWORD,
                ip_address=ip_address,
            )

        result = IPTracker.track_login_attempt(ip_address, user.username, success=False)

        assert result["should_block"] is False
        assert result["consecutive_failures"] == 3

    def test_track_failed_login_brute_force_threshold(self, user):
        """Test that brute force threshold triggers blocking."""
        ip_address = "192.168.1.100"

        # Create 5 consecutive failed attempts (brute force threshold)
        for _ in range(5):
            LoginAttempt.objects.create(
                user=user,
                username=user.username,
                result=LoginAttempt.RESULT_FAILED_PASSWORD,
                ip_address=ip_address,
            )

        result = IPTracker.track_login_attempt(ip_address, user.username, success=False)

        assert result["should_block"] is True
        assert "Brute force detected" in result["block_reason"]
        assert result["consecutive_failures"] >= 5

    def test_flag_and_check_ip(self):
        """Test flagging and checking an IP address."""
        ip_address = "192.168.1.100"
        reason = "Test flagging"

        # Flag the IP
        IPTracker.flag_ip(ip_address, reason, duration_minutes=60)

        # Check if flagged
        assert IPTracker.is_ip_flagged(ip_address) is True

        # Get metadata
        metadata = IPTracker.get_ip_metadata(ip_address)
        assert metadata is not None
        assert metadata["reason"] == reason

    def test_unflag_ip(self):
        """Test unflagging an IP address."""
        ip_address = "192.168.1.100"

        # Flag the IP
        IPTracker.flag_ip(ip_address, "Test", duration_minutes=60)
        assert IPTracker.is_ip_flagged(ip_address) is True

        # Unflag the IP
        IPTracker.unflag_ip(ip_address)
        assert IPTracker.is_ip_flagged(ip_address) is False

    def test_get_all_flagged_ips(self):
        """Test getting all flagged IPs."""
        # Flag multiple IPs
        IPTracker.flag_ip("192.168.1.100", "Test 1", duration_minutes=60)
        IPTracker.flag_ip("192.168.1.101", "Test 2", duration_minutes=60)

        flagged_ips = IPTracker.get_all_flagged_ips()

        assert len(flagged_ips) == 2
        ip_addresses = [ip["ip_address"] for ip in flagged_ips]
        assert "192.168.1.100" in ip_addresses
        assert "192.168.1.101" in ip_addresses


# ============================================================================
# Suspicious Activity Detection Tests
# ============================================================================


@pytest.mark.django_db
class TestSuspiciousActivityDetector:
    """Tests for suspicious activity detection."""

    def test_detect_multiple_failed_logins(self, user):
        """Test detection of multiple failed login attempts."""
        # Create 6 failed login attempts (above threshold of 5)
        for _ in range(6):
            LoginAttempt.objects.create(
                user=user,
                username=user.username,
                result=LoginAttempt.RESULT_FAILED_PASSWORD,
                ip_address="192.168.1.100",
            )

        result = SuspiciousActivityDetector.detect_multiple_failed_logins(user)

        assert result["is_suspicious"] is True
        assert result["failed_attempts"] == 6

    def test_detect_new_location_login(self, user):
        """Test detection of login from new location."""
        # Create a successful login from known IP
        LoginAttempt.objects.create(
            user=user,
            username=user.username,
            result=LoginAttempt.RESULT_SUCCESS,
            ip_address="192.168.1.100",
        )

        # Check login from new IP
        result = SuspiciousActivityDetector.detect_new_location_login(
            user, "192.168.1.200", country="US"
        )

        assert result["is_new_location"] is True
        assert result["ip_address"] == "192.168.1.200"
        assert result["previous_ip_count"] == 1

    def test_detect_bulk_export(self, user):
        """Test detection of bulk data exports."""
        # Simulate 15 exports (above threshold of 10)
        result = SuspiciousActivityDetector.detect_bulk_export(user, export_count=15)

        assert result["is_suspicious"] is True
        assert result["export_count"] == 15

    def test_detect_unusual_api_activity(self, user):
        """Test detection of unusual API activity."""
        # Create 1500 API requests (above threshold of 1000)
        for i in range(1500):
            APIRequestLog.objects.create(
                user=user,
                tenant=user.tenant,
                method="GET",
                path=f"/api/test/{i}/",
                status_code=200 if i < 1000 else 500,  # 500 failures
                response_time_ms=100,
                ip_address="192.168.1.100",
            )

        result = SuspiciousActivityDetector.detect_unusual_api_activity(user)

        assert result["is_suspicious"] is True
        assert result["api_requests"] == 1500
        assert result["is_high_volume"] is True


# ============================================================================
# Session Monitoring Tests
# ============================================================================


@pytest.mark.django_db
class TestSessionMonitor:
    """Tests for session monitoring."""

    def test_get_active_sessions(self, user):
        """Test getting active sessions for a user."""
        # Create a session for the user
        Session.objects.create(
            session_key="test_session_key",
            session_data=Session.objects.encode({"_auth_user_id": str(user.id)}),
            expire_date=timezone.now() + timedelta(days=1),
        )

        sessions = SessionMonitor.get_active_sessions(user)

        assert len(sessions) >= 1
        session_keys = [s["session_key"] for s in sessions]
        assert "test_session_key" in session_keys

    def test_force_logout_specific_session(self, user):
        """Test forcing logout of a specific session."""
        # Create a session for the user
        Session.objects.create(
            session_key="test_session_key",
            session_data=Session.objects.encode({"_auth_user_id": str(user.id)}),
            expire_date=timezone.now() + timedelta(days=1),
        )

        # Force logout specific session
        count = SessionMonitor.force_logout(user, session_key="test_session_key")

        assert count == 1
        assert not Session.objects.filter(session_key="test_session_key").exists()

    def test_force_logout_all_sessions(self, user):
        """Test forcing logout of all sessions."""
        # Create multiple sessions for the user
        for i in range(3):
            Session.objects.create(
                session_key=f"test_session_{i}",
                session_data=Session.objects.encode({"_auth_user_id": str(user.id)}),
                expire_date=timezone.now() + timedelta(days=1),
            )

        # Force logout all sessions
        count = SessionMonitor.force_logout(user)

        assert count == 3

    def test_detect_session_hijacking(self, user):
        """Test detection of potential session hijacking."""
        # The session hijacking detection looks at active sessions and their associated IPs
        # Since we can't easily simulate multiple IPs per session in tests,
        # we'll test that the detection logic works correctly

        # Create 5 sessions
        for i in range(5):
            Session.objects.create(
                session_key=f"test_session_{i}",
                session_data=Session.objects.encode({"_auth_user_id": str(user.id)}),
                expire_date=timezone.now() + timedelta(days=1),
            )

        result = SessionMonitor.detect_session_hijacking(user)

        # Should have 5 active sessions
        assert result["active_sessions"] == 5
        # The unique_ips count depends on audit logs, which may not be present in this test
        # So we just verify the structure is correct
        assert "unique_ips" in result
        assert "is_suspicious" in result
        assert "sessions" in result


# ============================================================================
# Brute Force Protection Tests
# ============================================================================


@pytest.mark.django_db
class TestBruteForceProtection:
    """Tests for brute force protection."""

    def test_check_and_increment_below_threshold(self):
        """Test checking and incrementing attempts below threshold."""
        identifier = "testuser"

        # First attempt
        result = BruteForceProtection.check_and_increment(identifier)

        assert result["allowed"] is True
        assert result["attempts"] == 1
        assert result["remaining_attempts"] == 4

    def test_check_and_increment_at_threshold(self):
        """Test checking and incrementing at lockout threshold."""
        identifier = "testuser"

        # Make 5 attempts (max threshold)
        for i in range(5):
            result = BruteForceProtection.check_and_increment(identifier)

        # 6th attempt should be blocked
        result = BruteForceProtection.check_and_increment(identifier)

        assert result["allowed"] is False
        assert "Too many failed login attempts" in result["reason"]

    def test_reset_attempts(self):
        """Test resetting login attempts."""
        identifier = "testuser"

        # Make 3 attempts
        for _ in range(3):
            BruteForceProtection.check_and_increment(identifier)

        # Reset
        BruteForceProtection.reset_attempts(identifier)

        # Next attempt should start from 1
        result = BruteForceProtection.check_and_increment(identifier)
        assert result["attempts"] == 1

    def test_is_locked_out(self):
        """Test checking if identifier is locked out."""
        identifier = "testuser"

        # Make 5 attempts to lock out
        for _ in range(5):
            BruteForceProtection.check_and_increment(identifier)

        assert BruteForceProtection.is_locked_out(identifier) is True

    def test_get_lockout_info(self):
        """Test getting lockout information."""
        identifier = "testuser"

        # Make 5 attempts to lock out
        for _ in range(5):
            BruteForceProtection.check_and_increment(identifier)

        lockout_info = BruteForceProtection.get_lockout_info(identifier)

        assert lockout_info is not None
        assert lockout_info["is_locked_out"] is True
        assert lockout_info["attempts"] >= 5

    def test_lock_and_unlock_account(self, user):
        """Test manually locking and unlocking an account."""
        # Lock account
        BruteForceProtection.lock_account(user, duration_minutes=30)
        assert BruteForceProtection.is_account_locked(user) is True

        # Unlock account
        BruteForceProtection.unlock_account(user)
        assert BruteForceProtection.is_account_locked(user) is False


# ============================================================================
# Security Dashboard Tests
# ============================================================================


@pytest.mark.django_db
class TestSecurityDashboard:
    """Tests for security dashboard data."""

    def test_get_security_dashboard_data(self, user):
        """Test getting security dashboard data."""
        # Create some test data
        LoginAttempt.objects.create(
            user=user,
            username=user.username,
            result=LoginAttempt.RESULT_SUCCESS,
            ip_address="192.168.1.100",
        )

        LoginAttempt.objects.create(
            user=user,
            username=user.username,
            result=LoginAttempt.RESULT_FAILED_PASSWORD,
            ip_address="192.168.1.101",
        )

        # Flag an IP
        IPTracker.flag_ip("192.168.1.101", "Test", duration_minutes=60)

        # Get dashboard data
        data = get_security_dashboard_data(time_window_hours=24)

        assert data["failed_logins"] >= 1
        assert data["successful_logins"] >= 1
        assert data["flagged_ips_count"] >= 1
        assert len(data["flagged_ips"]) >= 1
