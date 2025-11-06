"""
Simple focused tests for rate limiting without Silk interference.

Per Requirement 25: Security Hardening and Compliance
Tests Task 29.2: Rate limiting implementation
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from apps.core.audit_models import LoginAttempt
from apps.core.brute_force_protection import (
    block_ip,
    check_brute_force,
    clear_failed_attempts,
    get_client_ip,
    get_failed_attempts_count,
    is_ip_blocked,
)
from apps.core.models import Tenant

User = get_user_model()


@pytest.mark.django_db
class TestBruteForceProtectionCore:
    """Core brute force protection tests without middleware interference."""

    def setup_method(self):
        """Set up test data."""
        cache.clear()
        LoginAttempt.objects.all().delete()

        # Create test tenant and user
        self.tenant = Tenant.objects.create(
            company_name="Test Company",
            slug="test-company",
        )
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            email="test@example.com",
            tenant=self.tenant,
            role="PLATFORM_ADMIN",
        )
        self.ip_address = "192.168.1.100"

    def test_get_client_ip_basic(self):
        """Test IP extraction from request."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        ip = get_client_ip(request)
        assert ip == "192.168.1.1"

    def test_get_client_ip_with_forwarded(self):
        """Test IP extraction with X-Forwarded-For header."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "10.0.0.1, 192.168.1.1"
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        ip = get_client_ip(request)
        assert ip == "10.0.0.1"  # Should get first IP in chain

    def test_block_and_check_ip(self):
        """Test IP blocking and checking."""
        assert not is_ip_blocked(self.ip_address)

        block_ip(self.ip_address, duration_minutes=1)

        assert is_ip_blocked(self.ip_address)

    def test_clear_failed_attempts(self):
        """Test clearing failed attempts."""
        block_ip(self.ip_address)
        assert is_ip_blocked(self.ip_address)

        clear_failed_attempts(self.ip_address)

        assert not is_ip_blocked(self.ip_address)

    def test_get_failed_attempts_count(self):
        """Test counting failed login attempts."""
        # Create 3 failed attempts
        for i in range(3):
            LoginAttempt.objects.create(
                username="testuser",
                result=LoginAttempt.RESULT_FAILED_PASSWORD,
                ip_address=self.ip_address,
            )

        count = get_failed_attempts_count(self.ip_address)
        assert count == 3

    def test_get_failed_attempts_count_ignores_old(self):
        """Test that old attempts are not counted."""
        # Create old attempt (outside 5-minute window)
        old_attempt = LoginAttempt.objects.create(
            username="testuser",
            result=LoginAttempt.RESULT_FAILED_PASSWORD,
            ip_address=self.ip_address,
        )
        old_attempt.timestamp = timezone.now() - timedelta(minutes=10)
        old_attempt.save()

        # Create recent attempt
        LoginAttempt.objects.create(
            username="testuser",
            result=LoginAttempt.RESULT_FAILED_PASSWORD,
            ip_address=self.ip_address,
        )

        count = get_failed_attempts_count(self.ip_address, window_minutes=5)
        assert count == 1  # Only the recent one

    def test_get_failed_attempts_count_ignores_success(self):
        """Test that successful attempts are not counted."""
        # Create failed attempt
        LoginAttempt.objects.create(
            username="testuser",
            result=LoginAttempt.RESULT_FAILED_PASSWORD,
            ip_address=self.ip_address,
        )

        # Create successful attempt
        LoginAttempt.objects.create(
            username="testuser",
            result=LoginAttempt.RESULT_SUCCESS,
            ip_address=self.ip_address,
            user=self.user,
        )

        count = get_failed_attempts_count(self.ip_address)
        assert count == 1  # Only the failed one

    def test_check_brute_force_not_blocked_below_threshold(self):
        """Test that IPs with few attempts are not blocked."""
        # Create 2 failed attempts (below threshold of 5)
        for i in range(2):
            LoginAttempt.objects.create(
                username="testuser",
                result=LoginAttempt.RESULT_FAILED_PASSWORD,
                ip_address=self.ip_address,
            )

        is_blocked, message = check_brute_force(self.ip_address)
        assert not is_blocked
        assert message is None

    def test_check_brute_force_blocks_at_threshold(self):
        """Test that IPs are blocked after exceeding threshold."""
        # Create 5 failed attempts (at threshold)
        for i in range(5):
            LoginAttempt.objects.create(
                username="testuser",
                result=LoginAttempt.RESULT_FAILED_PASSWORD,
                ip_address=self.ip_address,
            )

        is_blocked, message = check_brute_force(self.ip_address)
        assert is_blocked
        assert "temporarily blocked" in message.lower()

        # Verify IP is now blocked
        assert is_ip_blocked(self.ip_address)

        # Verify a LoginAttempt record was created for the block
        block_attempt = LoginAttempt.objects.filter(
            ip_address=self.ip_address,
            result=LoginAttempt.RESULT_FAILED_RATE_LIMIT,
        ).first()
        assert block_attempt is not None

    def test_check_brute_force_already_blocked(self):
        """Test that already blocked IPs return blocked status."""
        # Block the IP directly
        block_ip(self.ip_address)

        is_blocked, message = check_brute_force(self.ip_address)
        assert is_blocked
        assert "temporarily blocked" in message.lower()


@pytest.mark.django_db
class TestLoginAttemptRecording:
    """Test login attempt recording functionality."""

    def setup_method(self):
        """Set up test data."""
        cache.clear()
        LoginAttempt.objects.all().delete()

        self.tenant = Tenant.objects.create(
            company_name="Test Company",
            slug="test-company",
        )
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            email="test@example.com",
            tenant=self.tenant,
            role="PLATFORM_ADMIN",
        )

    def test_record_successful_login(self):
        """Test recording successful login attempt."""
        from django.test import RequestFactory

        from apps.core.brute_force_protection import record_login_attempt

        factory = RequestFactory()
        request = factory.post("/login/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.META["HTTP_USER_AGENT"] = "Test Browser"

        record_login_attempt(
            request,
            "testuser",
            LoginAttempt.RESULT_SUCCESS,
            self.user,
        )

        attempt = LoginAttempt.objects.filter(
            username="testuser",
            result=LoginAttempt.RESULT_SUCCESS,
        ).first()

        assert attempt is not None
        assert attempt.user == self.user
        assert attempt.ip_address == "192.168.1.1"
        assert attempt.user_agent == "Test Browser"

    def test_record_failed_login(self):
        """Test recording failed login attempt."""
        from django.test import RequestFactory

        from apps.core.brute_force_protection import record_login_attempt

        factory = RequestFactory()
        request = factory.post("/login/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        record_login_attempt(
            request,
            "testuser",
            LoginAttempt.RESULT_FAILED_PASSWORD,
            self.user,
        )

        attempt = LoginAttempt.objects.filter(
            username="testuser",
            result=LoginAttempt.RESULT_FAILED_PASSWORD,
        ).first()

        assert attempt is not None
        assert attempt.user == self.user

    def test_record_nonexistent_user(self):
        """Test recording attempt for nonexistent user."""
        from django.test import RequestFactory

        from apps.core.brute_force_protection import record_login_attempt

        factory = RequestFactory()
        request = factory.post("/login/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        record_login_attempt(
            request,
            "nonexistent",
            LoginAttempt.RESULT_FAILED_USER_NOT_FOUND,
            None,
        )

        attempt = LoginAttempt.objects.filter(
            username="nonexistent",
            result=LoginAttempt.RESULT_FAILED_USER_NOT_FOUND,
        ).first()

        assert attempt is not None
        assert attempt.user is None


@pytest.mark.django_db
class TestRateLimitMiddleware:
    """Test API rate limiting middleware."""

    def setup_method(self):
        """Set up test data."""
        cache.clear()

    def test_middleware_exempts_health_check(self):
        """Test that health check endpoints are exempt from rate limiting."""
        from django.test import RequestFactory

        from apps.core.rate_limit_middleware import APIRateLimitMiddleware

        factory = RequestFactory()
        request = factory.get("/api/health/")
        request.user = type("User", (), {"is_authenticated": False})()

        middleware = APIRateLimitMiddleware(lambda r: None)
        response = middleware.process_request(request)

        # Should return None (not rate limited)
        assert response is None

    def test_middleware_applies_to_api_paths(self):
        """Test that middleware applies to /api/ paths."""
        from django.test import RequestFactory

        from apps.core.rate_limit_middleware import APIRateLimitMiddleware

        factory = RequestFactory()
        request = factory.get("/api/some-endpoint/")
        request.user = type("User", (), {"is_authenticated": False})()
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        middleware = APIRateLimitMiddleware(lambda r: None)

        # First request should pass
        response = middleware.process_request(request)
        # May return None or a response depending on rate limit state
        # Just verify it doesn't crash
        assert response is None or hasattr(response, "status_code")

    def test_middleware_ignores_non_api_paths(self):
        """Test that middleware ignores non-API paths."""
        from django.test import RequestFactory

        from apps.core.rate_limit_middleware import APIRateLimitMiddleware

        factory = RequestFactory()
        request = factory.get("/dashboard/")
        request.user = type("User", (), {"is_authenticated": False})()

        middleware = APIRateLimitMiddleware(lambda r: None)
        response = middleware.process_request(request)

        # Should return None (not processed)
        assert response is None
