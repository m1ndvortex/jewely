"""
Integration tests for security monitoring functionality.

These tests verify the complete security monitoring system works end-to-end
with real database, cache, and authentication - NO MOCKS.

Tests verify Requirement 8 acceptance criteria:
1. Log all administrative actions ✓ (covered by existing audit tests)
2. Track user logins, logouts, failed login attempts ✓
3. Log all data modifications ✓ (covered by existing audit tests)
4. Log all API requests ✓ (covered by existing audit tests)
5. Advanced search and filtering ✓ (covered by existing audit tests)
6. Export audit logs ✓ (covered by existing audit tests)
7. Detect and flag suspicious activity ✓ (THIS FILE)
8. Implement brute force protection ✓ (THIS FILE)
9. Retain audit logs ✓ (covered by existing audit tests)
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.test import Client, RequestFactory
from django.urls import reverse
from django.utils import timezone

import pytest

from apps.core.audit_models import APIRequestLog, AuditLog, LoginAttempt
from apps.core.models import Tenant
from apps.core.security_monitoring import (
    BruteForceProtection,
    IPTracker,
    SessionMonitor,
    SuspiciousActivityDetector,
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
def platform_admin():
    """Create a platform admin user."""
    return User.objects.create_user(
        username="admin",
        email="admin@example.com",
        password="admin123!@#",
        role=User.PLATFORM_ADMIN,
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def tenant_user(tenant):
    """Create a tenant user."""
    return User.objects.create_user(
        username="shopowner",
        email="owner@shop.com",
        password="shop123!@#",
        tenant=tenant,
        role=User.TENANT_OWNER,
    )


@pytest.fixture
def client():
    """Create a test client."""
    return Client()


@pytest.fixture
def request_factory():
    """Create a request factory."""
    return RequestFactory()


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before and after each test."""
    cache.clear()
    yield
    cache.clear()


# ============================================================================
# Requirement 8.7: Detect and flag suspicious activity
# ============================================================================


@pytest.mark.django_db
class TestSuspiciousActivityDetection:
    """
    Integration tests for suspicious activity detection.

    Verifies Requirement 8.7: Detect and flag suspicious activity including
    multiple failed logins and access from new locations.
    """

    def test_multiple_failed_logins_detection_real_flow(self, tenant_user, client):
        """
        Test that multiple failed login attempts are detected and logged.

        This is a real end-to-end test with actual login attempts.
        """
        # Attempt to login with wrong password 6 times
        for i in range(6):
            response = client.post(
                reverse("account_login"),
                {
                    "login": tenant_user.username,
                    "password": "wrongpassword",
                },
            )
            # Should fail
            assert response.status_code in [200, 302]  # 200 = form error, 302 = redirect

        # Verify LoginAttempt records were created
        failed_attempts = LoginAttempt.objects.filter(
            user=tenant_user,
            result__in=[
                LoginAttempt.RESULT_FAILED_PASSWORD,
                LoginAttempt.RESULT_FAILED_USER_NOT_FOUND,
            ],
        )
        assert failed_attempts.count() >= 5

        # Run suspicious activity detection
        result = SuspiciousActivityDetector.detect_multiple_failed_logins(tenant_user)

        # Should be flagged as suspicious
        assert result["is_suspicious"] is True
        assert result["failed_attempts"] >= 5

        # Verify security event was logged
        security_logs = AuditLog.objects.filter(
            user=tenant_user,
            category=AuditLog.CATEGORY_SECURITY,
            action=AuditLog.ACTION_SECURITY_SUSPICIOUS_ACTIVITY,
        )
        assert security_logs.exists()

    def test_new_location_login_detection_real_flow(self, tenant_user):
        """
        Test that logins from new locations are detected.

        This tests the real detection logic with actual LoginAttempt records.
        """
        # Create successful login from known IP
        LoginAttempt.objects.create(
            user=tenant_user,
            username=tenant_user.username,
            result=LoginAttempt.RESULT_SUCCESS,
            ip_address="192.168.1.100",
            timestamp=timezone.now() - timedelta(days=5),
        )

        # Simulate login from new IP
        new_ip = "203.0.113.50"
        result = SuspiciousActivityDetector.detect_new_location_login(
            tenant_user, new_ip, country="US"
        )

        # Should be detected as new location
        assert result["is_new_location"] is True
        assert result["ip_address"] == new_ip
        assert result["previous_ip_count"] == 1

        # Verify security event was logged
        security_logs = AuditLog.objects.filter(
            user=tenant_user,
            category=AuditLog.CATEGORY_SECURITY,
            action=AuditLog.ACTION_SECURITY_SUSPICIOUS_ACTIVITY,
            description__icontains="new location",
        )
        assert security_logs.exists()

    def test_bulk_export_detection_real_flow(self, tenant_user):
        """
        Test that bulk data exports are detected.

        This tests the real detection logic.
        """
        # Simulate 15 exports (above threshold of 10)
        export_count = 15

        result = SuspiciousActivityDetector.detect_bulk_export(
            tenant_user, export_count=export_count
        )

        # Should be flagged as suspicious
        assert result["is_suspicious"] is True
        assert result["export_count"] == export_count

        # Verify security event was logged
        security_logs = AuditLog.objects.filter(
            user=tenant_user,
            category=AuditLog.CATEGORY_SECURITY,
            action=AuditLog.ACTION_SECURITY_SUSPICIOUS_ACTIVITY,
            description__icontains="bulk",
        )
        assert security_logs.exists()

    def test_unusual_api_activity_detection_real_flow(self, tenant_user, tenant):
        """
        Test that unusual API activity is detected with real API request logs.
        """
        # Create 1500 API requests (above threshold of 1000)
        api_requests = []
        for i in range(1500):
            api_requests.append(
                APIRequestLog(
                    user=tenant_user,
                    tenant=tenant,
                    method="GET",
                    path=f"/api/inventory/{i}/",
                    status_code=200 if i < 1000 else 500,  # 500 failures
                    response_time_ms=100,
                    ip_address="192.168.1.100",
                )
            )

        # Bulk create for performance
        APIRequestLog.objects.bulk_create(api_requests)

        # Run detection
        result = SuspiciousActivityDetector.detect_unusual_api_activity(tenant_user)

        # Should be flagged as suspicious
        assert result["is_suspicious"] is True
        assert result["api_requests"] == 1500
        assert result["is_high_volume"] is True

        # Verify security event was logged
        security_logs = AuditLog.objects.filter(
            user=tenant_user,
            category=AuditLog.CATEGORY_SECURITY,
            action=AuditLog.ACTION_SECURITY_SUSPICIOUS_ACTIVITY,
            description__icontains="API activity",
        )
        assert security_logs.exists()


# ============================================================================
# Requirement 8.8: Implement brute force protection
# ============================================================================


@pytest.mark.django_db
class TestBruteForceProtectionIntegration:
    """
    Integration tests for brute force protection.

    Verifies Requirement 8.8: Implement brute force protection by detecting
    and blocking repeated login attempts.
    """

    def test_brute_force_protection_blocks_after_threshold(self, tenant_user, client):
        """
        Test that brute force protection blocks login attempts after threshold.

        This is a real end-to-end test with actual failed login attempts.
        """
        ip_address = "192.168.1.100"

        # Create 5 failed login attempts (at threshold)
        for i in range(5):
            LoginAttempt.objects.create(
                user=tenant_user,
                username=tenant_user.username,
                result=LoginAttempt.RESULT_FAILED_PASSWORD,
                ip_address=ip_address,
            )

        # Track the login attempt
        result = IPTracker.track_login_attempt(ip_address, tenant_user.username, success=False)

        # Should be blocked
        assert result["should_block"] is True
        assert "Brute force detected" in result["block_reason"]

        # Verify IP is flagged
        assert IPTracker.is_ip_flagged(ip_address) is True

        # Verify security event was logged
        security_logs = AuditLog.objects.filter(
            category=AuditLog.CATEGORY_SECURITY,
            action=AuditLog.ACTION_SECURITY_SUSPICIOUS_ACTIVITY,
            description__icontains="blocked",
        )
        assert security_logs.exists()

    def test_brute_force_protection_rate_limiting(self, tenant_user):
        """
        Test that rate limiting works correctly.
        """
        identifier = tenant_user.username

        # Make 5 attempts (at threshold)
        for i in range(5):
            result = BruteForceProtection.check_and_increment(identifier)
            if i < 4:
                assert result["allowed"] is True
            else:
                # 5th attempt should still be allowed, 6th will be blocked
                assert result["allowed"] is True

        # 6th attempt should be blocked
        result = BruteForceProtection.check_and_increment(identifier)
        assert result["allowed"] is False
        assert "Too many failed login attempts" in result["reason"]

        # Verify lockout status
        assert BruteForceProtection.is_locked_out(identifier) is True

        # Get lockout info
        lockout_info = BruteForceProtection.get_lockout_info(identifier)
        assert lockout_info is not None
        assert lockout_info["is_locked_out"] is True

    def test_brute_force_protection_reset_on_success(self, tenant_user):
        """
        Test that successful login resets the attempt counter.
        """
        identifier = tenant_user.username

        # Make 3 failed attempts
        for i in range(3):
            BruteForceProtection.check_and_increment(identifier)

        # Reset (simulating successful login)
        BruteForceProtection.reset_attempts(identifier)

        # Next attempt should start from 1
        result = BruteForceProtection.check_and_increment(identifier)
        assert result["attempts"] == 1
        assert result["allowed"] is True

    def test_account_lockout_and_unlock(self, tenant_user):
        """
        Test manual account lock and unlock functionality.
        """
        # Lock the account
        BruteForceProtection.lock_account(tenant_user, duration_minutes=30)

        # Verify account is locked
        assert BruteForceProtection.is_account_locked(tenant_user) is True

        # Verify security event was logged
        security_logs = AuditLog.objects.filter(
            user=tenant_user,
            category=AuditLog.CATEGORY_SECURITY,
            action=AuditLog.ACTION_SECURITY_SUSPICIOUS_ACTIVITY,
            description__icontains="locked",
        )
        assert security_logs.exists()

        # Unlock the account
        BruteForceProtection.unlock_account(tenant_user)

        # Verify account is unlocked
        assert BruteForceProtection.is_account_locked(tenant_user) is False


# ============================================================================
# Session Monitoring Integration Tests
# ============================================================================


@pytest.mark.django_db
class TestSessionMonitoringIntegration:
    """
    Integration tests for session monitoring.

    Tests session tracking and force logout capabilities.
    """

    def test_session_monitoring_tracks_active_sessions(self, tenant_user):
        """
        Test that active sessions are tracked correctly.
        """
        # Create 3 active sessions for the user
        sessions = []
        for i in range(3):
            session = Session.objects.create(
                session_key=f"test_session_{i}",
                session_data=Session.objects.encode({"_auth_user_id": str(tenant_user.id)}),
                expire_date=timezone.now() + timedelta(days=1),
            )
            sessions.append(session)

        # Get active sessions
        active_sessions = SessionMonitor.get_active_sessions(tenant_user)

        # Should have 3 active sessions
        assert len(active_sessions) == 3

        # Verify session keys
        session_keys = [s["session_key"] for s in active_sessions]
        for session in sessions:
            assert session.session_key in session_keys

    def test_force_logout_terminates_sessions(self, tenant_user):
        """
        Test that force logout terminates user sessions.
        """
        # Create 3 active sessions
        for i in range(3):
            Session.objects.create(
                session_key=f"test_session_{i}",
                session_data=Session.objects.encode({"_auth_user_id": str(tenant_user.id)}),
                expire_date=timezone.now() + timedelta(days=1),
            )

        # Force logout all sessions
        count = SessionMonitor.force_logout(tenant_user)

        # Should have terminated 3 sessions
        assert count == 3

        # Verify no active sessions remain
        active_sessions = SessionMonitor.get_active_sessions(tenant_user)
        assert len(active_sessions) == 0

        # Verify security event was logged
        security_logs = AuditLog.objects.filter(
            user=tenant_user,
            category=AuditLog.CATEGORY_SECURITY,
            action=AuditLog.ACTION_SECURITY_SUSPICIOUS_ACTIVITY,
            description__icontains="Forced logout",
        )
        assert security_logs.exists()

    def test_force_logout_specific_session(self, tenant_user):
        """
        Test that force logout can target a specific session.
        """
        # Create 3 sessions
        sessions = []
        for i in range(3):
            session = Session.objects.create(
                session_key=f"test_session_{i}",
                session_data=Session.objects.encode({"_auth_user_id": str(tenant_user.id)}),
                expire_date=timezone.now() + timedelta(days=1),
            )
            sessions.append(session)

        # Force logout specific session
        target_session = sessions[1]
        count = SessionMonitor.force_logout(tenant_user, session_key=target_session.session_key)

        # Should have terminated 1 session
        assert count == 1

        # Verify target session is deleted
        assert not Session.objects.filter(session_key=target_session.session_key).exists()

        # Verify other sessions still exist
        assert Session.objects.filter(session_key=sessions[0].session_key).exists()
        assert Session.objects.filter(session_key=sessions[2].session_key).exists()


# ============================================================================
# IP Tracking Integration Tests
# ============================================================================


@pytest.mark.django_db
class TestIPTrackingIntegration:
    """
    Integration tests for IP tracking and flagging.

    Tests IP-based security monitoring.
    """

    def test_ip_tracking_with_real_login_attempts(self, tenant_user):
        """
        Test IP tracking with real LoginAttempt records.
        """
        ip_address = "192.168.1.100"

        # Create 10 failed login attempts from this IP
        for i in range(10):
            LoginAttempt.objects.create(
                user=tenant_user,
                username=tenant_user.username,
                result=LoginAttempt.RESULT_FAILED_PASSWORD,
                ip_address=ip_address,
            )

        # Track the login attempt
        result = IPTracker.track_login_attempt(ip_address, tenant_user.username, success=False)

        # Should be blocked due to high failure count
        assert result["should_block"] is True
        assert result["recent_failures_hour"] >= 10

        # Verify IP is flagged
        assert IPTracker.is_ip_flagged(ip_address) is True

    def test_ip_flagging_and_unflagging(self):
        """
        Test manual IP flagging and unflagging.
        """
        ip_address = "203.0.113.100"
        reason = "Manual flag for testing"

        # Flag the IP
        IPTracker.flag_ip(ip_address, reason, duration_minutes=60)

        # Verify IP is flagged
        assert IPTracker.is_ip_flagged(ip_address) is True

        # Get metadata
        metadata = IPTracker.get_ip_metadata(ip_address)
        assert metadata is not None
        assert metadata["reason"] == reason

        # Unflag the IP
        IPTracker.unflag_ip(ip_address)

        # Verify IP is no longer flagged
        assert IPTracker.is_ip_flagged(ip_address) is False

    def test_get_all_flagged_ips(self):
        """
        Test retrieving all flagged IPs.
        """
        # Flag multiple IPs
        ips = ["192.168.1.100", "192.168.1.101", "192.168.1.102"]
        for ip in ips:
            IPTracker.flag_ip(ip, f"Test flag for {ip}", duration_minutes=60)

        # Get all flagged IPs
        flagged_ips = IPTracker.get_all_flagged_ips()

        # Should have all 3 IPs
        assert len(flagged_ips) >= 3

        # Verify all IPs are in the list
        flagged_ip_addresses = [ip_data["ip_address"] for ip_data in flagged_ips]
        for ip in ips:
            assert ip in flagged_ip_addresses


# ============================================================================
# End-to-End Security Monitoring Test
# ============================================================================


@pytest.mark.django_db
class TestSecurityMonitoringEndToEnd:
    """
    End-to-end integration test for the complete security monitoring system.

    This test simulates a real attack scenario and verifies all security
    measures work together correctly.
    """

    def test_complete_brute_force_attack_scenario(self, tenant_user, client):
        """
        Simulate a complete brute force attack and verify all security measures activate.

        This test verifies:
        1. Failed login attempts are logged
        2. IP tracking detects the attack
        3. Brute force protection blocks further attempts
        4. Security events are logged
        5. IP is flagged
        """
        attacker_ip = "203.0.113.50"

        # Simulate 10 failed login attempts from attacker IP
        for i in range(10):
            LoginAttempt.objects.create(
                user=tenant_user,
                username=tenant_user.username,
                result=LoginAttempt.RESULT_FAILED_PASSWORD,
                ip_address=attacker_ip,
            )

        # Track the attack
        result = IPTracker.track_login_attempt(attacker_ip, tenant_user.username, success=False)

        # Verify attack was detected and blocked
        assert result["should_block"] is True
        assert result["recent_failures_hour"] >= 10

        # Verify IP is flagged
        assert IPTracker.is_ip_flagged(attacker_ip) is True

        # Verify security events were logged
        security_logs = AuditLog.objects.filter(
            category=AuditLog.CATEGORY_SECURITY,
            action=AuditLog.ACTION_SECURITY_SUSPICIOUS_ACTIVITY,
        )
        # Should have at least one security log entry
        assert security_logs.count() >= 1

        # Verify LoginAttempt records exist
        login_attempts = LoginAttempt.objects.filter(
            ip_address=attacker_ip,
            result=LoginAttempt.RESULT_FAILED_PASSWORD,
        )
        assert login_attempts.count() >= 10

        # Verify brute force protection would block if we check it
        # (Note: IPTracker and BruteForceProtection are separate systems)
        # IPTracker flags IPs, BruteForceProtection tracks login attempts per user
        # In a real scenario, both would be checked by the middleware/login view
        for i in range(6):
            BruteForceProtection.check_and_increment(tenant_user.username)

        assert BruteForceProtection.is_locked_out(tenant_user.username) is True

        # Verify suspicious activity detection
        detection_result = SuspiciousActivityDetector.detect_multiple_failed_logins(tenant_user)
        assert detection_result["is_suspicious"] is True
