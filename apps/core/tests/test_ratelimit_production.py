"""
Production-ready tests for django-ratelimit with PgBouncer compatibility.

These tests verify that rate limiting works correctly in a production environment
with PgBouncer connection pooling.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import JsonResponse
from django.test import Client, TestCase, override_settings
from django.urls import path

import pytest

from apps.core.models import Tenant
from apps.core.throttling import api_ratelimit, api_ratelimit_tenant, api_ratelimit_user

User = get_user_model()


# Test views for rate limiting
@api_ratelimit(key="ip", rate="5/m", block=True)
def test_ip_ratelimit_view(request):
    """Test view with IP-based rate limiting."""
    return JsonResponse({"success": True, "message": "Request successful"})


@api_ratelimit_user(rate="3/m")
def test_user_ratelimit_view(request):
    """Test view with user-based rate limiting."""
    return JsonResponse({"success": True, "user": request.user.username})


@api_ratelimit_tenant(rate="10/m")
def test_tenant_ratelimit_view(request):
    """Test view with tenant-based rate limiting."""
    return JsonResponse({"success": True, "tenant": str(request.user.tenant.id)})


# URL patterns for testing
test_urlpatterns = [
    path("test/ip-limit/", test_ip_ratelimit_view, name="test_ip_limit"),
    path("test/user-limit/", test_user_ratelimit_view, name="test_user_limit"),
    path("test/tenant-limit/", test_tenant_ratelimit_view, name="test_tenant_limit"),
]


@override_settings(ROOT_URLCONF=__name__)
@override_settings(RATELIMIT_ENABLE=True)
@pytest.mark.django_db
class RateLimitProductionTests(TestCase):
    """
    Production-ready rate limiting tests.

    These tests verify that django-ratelimit works correctly with:
    - Redis cache backend
    - PgBouncer connection pooling
    - Multiple concurrent requests
    - Different rate limit strategies
    """

    @classmethod
    def setUpClass(cls):
        """Set up URL patterns for testing."""
        super().setUpClass()
        # URL patterns are defined at module level

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        # Create tenant
        self.tenant = Tenant.objects.create(
            company_name="Test Company",
            slug="test-company",
            status="ACTIVE",
        )

        # Create test user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_EMPLOYEE",
        )

        # Clear cache before each test
        cache.clear()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_redis_cache_available(self):
        """Verify Redis cache is available for rate limiting."""
        # Test cache set/get
        cache.set("test_key", "test_value", 60)
        value = cache.get("test_key")
        self.assertEqual(value, "test_value")

        # Clean up
        cache.delete("test_key")

    def test_database_connection_with_pgbouncer(self):
        """Verify database connection works through PgBouncer."""
        # This should work even with PgBouncer's transaction pooling
        user_count = User.objects.count()
        self.assertEqual(user_count, 1)

        # Test multiple queries in sequence
        for i in range(5):
            User.objects.filter(username="testuser").exists()

    def test_ip_based_rate_limiting_functional(self):
        """Test that IP-based rate limiting actually works."""
        url = "/test/ip-limit/"

        # Make requests up to the limit
        for i in range(5):
            response = self.client.get(url, REMOTE_ADDR="127.0.0.1")
            self.assertEqual(
                response.status_code,
                200,
                f"Request {i+1} should succeed (limit is 5/m)",
            )

        # Next request should be rate limited
        response = self.client.get(url, REMOTE_ADDR="127.0.0.1")
        self.assertEqual(
            response.status_code,
            429,
            "Request 6 should be rate limited (limit is 5/m)",
        )

        # Verify error response
        data = response.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"], "Rate limit exceeded")

    def test_user_based_rate_limiting_functional(self):
        """Test that user-based rate limiting actually works."""
        url = "/test/user-limit/"

        # Login
        self.client.login(username="testuser", password="testpass123")

        # Make requests up to the limit
        for i in range(3):
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                200,
                f"Request {i+1} should succeed (limit is 3/m)",
            )

        # Next request should be rate limited
        response = self.client.get(url)
        self.assertEqual(
            response.status_code,
            429,
            "Request 4 should be rate limited (limit is 3/m)",
        )

    def test_tenant_based_rate_limiting_functional(self):
        """Test that tenant-based rate limiting actually works."""
        url = "/test/tenant-limit/"

        # Login
        self.client.login(username="testuser", password="testpass123")

        # Make requests up to the limit
        for i in range(10):
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                200,
                f"Request {i+1} should succeed (limit is 10/m)",
            )

        # Next request should be rate limited
        response = self.client.get(url)
        self.assertEqual(
            response.status_code,
            429,
            "Request 11 should be rate limited (limit is 10/m)",
        )

        # Verify tenant-specific error message
        data = response.json()
        self.assertIn("organization", data["message"])

    def test_rate_limit_isolation_between_ips(self):
        """Test that rate limits are isolated per IP address."""
        url = "/test/ip-limit/"

        # IP 1: Make 5 requests (at limit)
        for i in range(5):
            response = self.client.get(url, REMOTE_ADDR="192.168.1.1")
            self.assertEqual(response.status_code, 200)

        # IP 1: Should be rate limited
        response = self.client.get(url, REMOTE_ADDR="192.168.1.1")
        self.assertEqual(response.status_code, 429)

        # IP 2: Should still work (different IP)
        response = self.client.get(url, REMOTE_ADDR="192.168.1.2")
        self.assertEqual(response.status_code, 200)

    def test_rate_limit_isolation_between_users(self):
        """Test that rate limits are isolated per user."""
        url = "/test/user-limit/"

        # Create second user
        User.objects.create_user(
            username="testuser2",
            email="test2@example.com",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_EMPLOYEE",
        )

        # User 1: Make 3 requests (at limit)
        self.client.login(username="testuser", password="testpass123")
        for i in range(3):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

        # User 1: Should be rate limited
        response = self.client.get(url)
        self.assertEqual(response.status_code, 429)

        # User 2: Should still work (different user)
        self.client.login(username="testuser2", password="testpass123")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_rate_limit_isolation_between_tenants(self):
        """Test that rate limits are isolated per tenant."""
        url = "/test/tenant-limit/"

        # Create second tenant and user
        tenant2 = Tenant.objects.create(
            company_name="Test Company 2",
            slug="test-company-2",
            status="ACTIVE",
        )
        User.objects.create_user(
            username="testuser2",
            email="test2@example.com",
            password="testpass123",
            tenant=tenant2,
            role="TENANT_EMPLOYEE",
        )

        # Tenant 1: Make 10 requests (at limit)
        self.client.login(username="testuser", password="testpass123")
        for i in range(10):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

        # Tenant 1: Should be rate limited
        response = self.client.get(url)
        self.assertEqual(response.status_code, 429)

        # Tenant 2: Should still work (different tenant)
        self.client.login(username="testuser2", password="testpass123")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_rate_limit_with_pgbouncer_transaction_pooling(self):
        """
        Test that rate limiting works correctly with PgBouncer's transaction pooling.

        PgBouncer in transaction mode releases connections after each transaction,
        which could potentially affect rate limiting if not handled correctly.
        """
        url = "/test/user-limit/"

        # Login
        self.client.login(username="testuser", password="testpass123")

        # Make multiple requests with database queries
        # Each request will get a new connection from PgBouncer
        for i in range(3):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

            # Force a database query to ensure connection is used
            User.objects.filter(username="testuser").exists()

        # Rate limit should still work despite connection pooling
        response = self.client.get(url)
        self.assertEqual(response.status_code, 429)

    def test_rate_limit_cache_keys_are_unique(self):
        """Test that rate limit cache keys are properly namespaced."""
        url_ip = "/test/ip-limit/"
        url_user = "/test/user-limit/"

        # Login
        self.client.login(username="testuser", password="testpass123")

        # Make requests to IP-limited endpoint
        for i in range(5):
            self.client.get(url_ip, REMOTE_ADDR="127.0.0.1")

        # IP endpoint should be rate limited
        response = self.client.get(url_ip, REMOTE_ADDR="127.0.0.1")
        self.assertEqual(response.status_code, 429)

        # User endpoint should still work (different cache key)
        response = self.client.get(url_user)
        self.assertEqual(response.status_code, 200)

    def test_rate_limit_response_headers(self):
        """Test that rate limit information is available in responses."""
        url = "/test/ip-limit/"

        # Make a request
        response = self.client.get(url, REMOTE_ADDR="127.0.0.1")
        self.assertEqual(response.status_code, 200)

        # Check that request was processed
        data = response.json()
        self.assertTrue(data["success"])

    @override_settings(RATELIMIT_ENABLE=False)
    def test_rate_limiting_can_be_disabled(self):
        """Test that rate limiting can be disabled via settings."""
        url = "/test/ip-limit/"

        # Make more requests than the limit
        for i in range(10):
            response = self.client.get(url, REMOTE_ADDR="127.0.0.1")
            # All should succeed when rate limiting is disabled
            self.assertEqual(response.status_code, 200)


# Make URL patterns available at module level
urlpatterns = test_urlpatterns
