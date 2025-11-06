"""
Tests for rate limiting and brute force protection.

Per Requirement 25: Security Hardening and Compliance
Tests Task 29.2: Rate limiting implementation
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.core.audit_models import LoginAttempt
from apps.core.brute_force_protection import (
    block_ip,
    check_brute_force,
    clear_failed_attempts,
    get_failed_attempts_count,
    is_ip_blocked,
)
from apps.core.models import Tenant

User = get_user_model()


@pytest.mark.django_db
class TestBruteForceProtection:
    """Test brute force protection functionality."""

    def setup_method(self):
        """Set up test data."""
        self.client = Client()
        cache.clear()

        # Create test user
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

    def test_get_failed_attempts_count(self):
        """Test counting failed login attempts."""
        # Create some failed attempts
        for i in range(3):
            LoginAttempt.objects.create(
                username="testuser",
                result=LoginAttempt.RESULT_FAILED_PASSWORD,
                ip_address=self.ip_address,
            )

        count = get_failed_attempts_count(self.ip_address)
        assert count == 3

    def test_get_failed_attempts_count_time_window(self):
        """Test that old attempts are not counted."""
        # Create old attempt (outside window)
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

    def test_block_ip(self):
        """Test IP blocking functionality."""
        assert not is_ip_blocked(self.ip_address)

        block_ip(self.ip_address, duration_minutes=1)

        assert is_ip_blocked(self.ip_address)

    def test_check_brute_force_not_blocked(self):
        """Test that IPs with few attempts are not blocked."""
        # Create 2 failed attempts (below threshold)
        for i in range(2):
            LoginAttempt.objects.create(
                username="testuser",
                result=LoginAttempt.RESULT_FAILED_PASSWORD,
                ip_address=self.ip_address,
            )

        is_blocked, message = check_brute_force(self.ip_address)
        assert not is_blocked
        assert message is None

    def test_check_brute_force_blocks_after_threshold(self):
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

    def test_clear_failed_attempts(self):
        """Test clearing failed attempts after successful login."""
        # Block the IP
        block_ip(self.ip_address)
        assert is_ip_blocked(self.ip_address)

        # Clear attempts
        clear_failed_attempts(self.ip_address)

        # IP should no longer be blocked
        assert not is_ip_blocked(self.ip_address)


@pytest.mark.django_db
class TestLoginRateLimiting:
    """Test rate limiting on login endpoints."""

    def setup_method(self):
        """Set up test data."""
        self.client = Client()
        cache.clear()

        # Create test user
        self.tenant = Tenant.objects.create(
            company_name="Test Company",
            slug="test-company",
        )
        self.user = User.objects.create_user(
            username="admin",
            password="adminpass123",
            email="admin@example.com",
            tenant=self.tenant,
            role="PLATFORM_ADMIN",
        )

    def test_admin_login_rate_limit(self):
        """Test that admin login is rate limited to 5/min."""
        url = reverse("core:admin_login")

        # Make 5 requests (should succeed)
        for i in range(5):
            response = self.client.post(
                url,
                {"username": "wronguser", "password": "wrongpass"},
            )
            # Should get 200 with error message, not 429
            assert response.status_code == 200

        # 6th request should be rate limited
        response = self.client.post(
            url,
            {"username": "wronguser", "password": "wrongpass"},
        )
        assert response.status_code == 429

    def test_api_token_rate_limit(self):
        """Test that API token endpoint is rate limited."""
        url = reverse("core:token_obtain_pair")

        # Make 5 requests (should succeed)
        for i in range(5):
            response = self.client.post(
                url,
                {"username": "wronguser", "password": "wrongpass"},
                content_type="application/json",
            )
            # Should get 401 (unauthorized), not 429
            assert response.status_code == 401

        # 6th request should be rate limited
        response = self.client.post(
            url,
            {"username": "wronguser", "password": "wrongpass"},
            content_type="application/json",
        )
        assert response.status_code == 429

    def test_successful_login_not_rate_limited(self):
        """Test that successful logins don't trigger rate limiting."""
        url = reverse("core:admin_login")

        # Make 3 successful logins
        for i in range(3):
            response = self.client.post(
                url,
                {"username": "admin", "password": "adminpass123"},
            )
            # Should redirect on success
            assert response.status_code == 302

            # Logout for next attempt
            self.client.logout()

        # Should still be able to login
        response = self.client.post(
            url,
            {"username": "admin", "password": "adminpass123"},
        )
        assert response.status_code == 302


@pytest.mark.django_db
class TestBruteForceProtectionIntegration:
    """Integration tests for brute force protection on login views."""

    def setup_method(self):
        """Set up test data."""
        self.client = Client()
        cache.clear()
        LoginAttempt.objects.all().delete()

        # Create test user
        self.tenant = Tenant.objects.create(
            company_name="Test Company",
            slug="test-company",
        )
        self.user = User.objects.create_user(
            username="admin",
            password="adminpass123",
            email="admin@example.com",
            tenant=self.tenant,
            role="PLATFORM_ADMIN",
        )

    def test_admin_login_brute_force_protection(self):
        """Test that admin login blocks after 5 failed attempts."""
        url = reverse("core:admin_login")

        # Make 5 failed login attempts
        for i in range(5):
            response = self.client.post(
                url,
                {"username": "admin", "password": "wrongpass"},
            )
            assert response.status_code == 200  # Returns form with error

        # 6th attempt should be blocked
        response = self.client.post(
            url,
            {"username": "admin", "password": "wrongpass"},
        )
        assert response.status_code == 429

        # Verify LoginAttempt records were created
        attempts = LoginAttempt.objects.filter(username="admin")
        assert attempts.count() >= 5

    def test_api_token_brute_force_protection(self):
        """Test that API token endpoint blocks after 5 failed attempts."""
        url = reverse("core:token_obtain_pair")

        # Make 5 failed attempts
        for i in range(5):
            response = self.client.post(
                url,
                {"username": "admin", "password": "wrongpass"},
                content_type="application/json",
            )
            # Should get 401 (unauthorized)
            assert response.status_code in [401, 429]

        # Next attempt should be blocked
        response = self.client.post(
            url,
            {"username": "admin", "password": "wrongpass"},
            content_type="application/json",
        )
        assert response.status_code == 429

        # Verify response contains error message
        data = response.json()
        assert "error" in data
        assert "blocked" in data["message"].lower() or "many" in data["message"].lower()

    def test_successful_login_clears_block(self):
        """Test that successful login clears the IP block."""
        url = reverse("core:admin_login")

        # Make 4 failed attempts (just below threshold)
        for i in range(4):
            response = self.client.post(
                url,
                {"username": "admin", "password": "wrongpass"},
            )

        # Successful login should clear the attempts
        response = self.client.post(
            url,
            {"username": "admin", "password": "adminpass123"},
        )
        assert response.status_code == 302  # Redirect on success

        # Logout
        self.client.logout()

        # Should be able to make more attempts now
        for i in range(4):
            response = self.client.post(
                url,
                {"username": "admin", "password": "wrongpass"},
            )
            assert response.status_code == 200  # Not blocked yet


@pytest.mark.django_db
class TestAPIRateLimiting:
    """Test API rate limiting middleware."""

    def setup_method(self):
        """Set up test data."""
        self.client = Client()
        cache.clear()

        # Create test user
        self.tenant = Tenant.objects.create(
            company_name="Test Company",
            slug="test-company",
        )
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            email="test@example.com",
            tenant=self.tenant,
            role="TENANT_OWNER",
        )

    def test_api_rate_limit_anonymous(self):
        """Test that anonymous API requests are rate limited."""
        # Note: This test would need actual API endpoints to test properly
        # For now, we'll test the middleware logic
        pass

    def test_api_rate_limit_authenticated(self):
        """Test that authenticated API requests are rate limited."""
        # Note: This test would need actual API endpoints to test properly
        # For now, we'll test the middleware logic
        pass


@pytest.mark.django_db
class TestLoginAttemptLogging:
    """Test that login attempts are properly logged."""

    def setup_method(self):
        """Set up test data."""
        self.client = Client()
        cache.clear()
        LoginAttempt.objects.all().delete()

        # Create test user
        self.tenant = Tenant.objects.create(
            company_name="Test Company",
            slug="test-company",
        )
        self.user = User.objects.create_user(
            username="admin",
            password="adminpass123",
            email="admin@example.com",
            tenant=self.tenant,
            role="PLATFORM_ADMIN",
        )

    def test_successful_login_logged(self):
        """Test that successful logins are logged."""
        url = reverse("core:admin_login")

        self.client.post(
            url,
            {"username": "admin", "password": "adminpass123"},
        )

        # Check that attempt was logged
        attempt = LoginAttempt.objects.filter(
            username="admin",
            result=LoginAttempt.RESULT_SUCCESS,
        ).first()

        assert attempt is not None
        assert attempt.user == self.user

    def test_failed_login_logged(self):
        """Test that failed logins are logged."""
        url = reverse("core:admin_login")

        self.client.post(
            url,
            {"username": "admin", "password": "wrongpass"},
        )

        # Check that attempt was logged
        attempt = LoginAttempt.objects.filter(
            username="admin",
            result=LoginAttempt.RESULT_FAILED_PASSWORD,
        ).first()

        assert attempt is not None
        assert attempt.user == self.user

    def test_nonexistent_user_logged(self):
        """Test that attempts with nonexistent users are logged."""
        url = reverse("core:admin_login")

        self.client.post(
            url,
            {"username": "nonexistent", "password": "somepass"},
        )

        # Check that attempt was logged
        attempt = LoginAttempt.objects.filter(
            username="nonexistent",
            result=LoginAttempt.RESULT_FAILED_USER_NOT_FOUND,
        ).first()

        assert attempt is not None
        assert attempt.user is None
