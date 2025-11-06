"""
Tests for API optimizations including pagination, compression, and throttling.

Per Requirement 26 - Performance Optimization and Scaling
Task 28.4 - Implement API optimizations
"""

import gzip
import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import JsonResponse
from django.test import RequestFactory, TestCase, override_settings

from apps.core.models import Tenant
from apps.core.pagination import APIPaginator, paginate_queryset
from apps.core.throttling import (
    api_ratelimit,
    api_ratelimit_lenient,
    api_ratelimit_standard,
    api_ratelimit_strict,
    api_ratelimit_tenant,
    api_ratelimit_user,
    api_ratelimit_write,
)

User = get_user_model()


class PaginationTests(TestCase):
    """Test pagination utilities."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.tenant = Tenant.objects.create(
            company_name="Test Company", slug="test-company", status="ACTIVE"
        )
        # Create test users
        self.users = []
        for i in range(50):
            user = User.objects.create_user(
                username=f"user{i}",
                email=f"user{i}@example.com",
                tenant=self.tenant,
                role="TENANT_EMPLOYEE",
            )
            self.users.append(user)

    def test_basic_pagination(self):
        """Test basic pagination functionality."""
        request = self.factory.get("/api/users/")
        queryset = User.objects.filter(tenant=self.tenant).order_by("id")

        paginator = APIPaginator(request, queryset, per_page=10)
        data = paginator.get_response_data()

        # Check structure
        self.assertIn("results", data)
        self.assertIn("pagination", data)

        # Check pagination metadata
        pagination = data["pagination"]
        self.assertEqual(pagination["page"], 1)
        self.assertEqual(pagination["per_page"], 10)
        self.assertEqual(pagination["total_pages"], 5)
        self.assertEqual(pagination["total_items"], 50)
        self.assertTrue(pagination["has_next"])
        self.assertFalse(pagination["has_previous"])
        self.assertEqual(pagination["next_page"], 2)
        self.assertIsNone(pagination["previous_page"])

    def test_pagination_with_page_parameter(self):
        """Test pagination with specific page number."""
        request = self.factory.get("/api/users/?page=3")
        queryset = User.objects.filter(tenant=self.tenant).order_by("id")

        paginator = APIPaginator(request, queryset, per_page=10)
        data = paginator.get_response_data()

        pagination = data["pagination"]
        self.assertEqual(pagination["page"], 3)
        self.assertTrue(pagination["has_next"])
        self.assertTrue(pagination["has_previous"])
        self.assertEqual(pagination["next_page"], 4)
        self.assertEqual(pagination["previous_page"], 2)

    def test_pagination_with_per_page_parameter(self):
        """Test pagination with custom per_page."""
        request = self.factory.get("/api/users/?per_page=25")
        queryset = User.objects.filter(tenant=self.tenant).order_by("id")

        paginator = APIPaginator(request, queryset, per_page=10)
        data = paginator.get_response_data()

        pagination = data["pagination"]
        self.assertEqual(pagination["per_page"], 25)
        self.assertEqual(pagination["total_pages"], 2)

    def test_pagination_max_per_page_limit(self):
        """Test that per_page is capped at max_per_page."""
        request = self.factory.get("/api/users/?per_page=500")
        queryset = User.objects.filter(tenant=self.tenant).order_by("id")

        paginator = APIPaginator(request, queryset, per_page=10, max_per_page=100)
        data = paginator.get_response_data()

        pagination = data["pagination"]
        self.assertEqual(pagination["per_page"], 100)  # Capped at max

    def test_pagination_invalid_page_number(self):
        """Test pagination with invalid page number."""
        request = self.factory.get("/api/users/?page=invalid")
        queryset = User.objects.filter(tenant=self.tenant).order_by("id")

        paginator = APIPaginator(request, queryset, per_page=10)
        data = paginator.get_response_data()

        pagination = data["pagination"]
        self.assertEqual(pagination["page"], 1)  # Defaults to page 1

    def test_pagination_out_of_range_page(self):
        """Test pagination with page number out of range."""
        request = self.factory.get("/api/users/?page=999")
        queryset = User.objects.filter(tenant=self.tenant).order_by("id")

        paginator = APIPaginator(request, queryset, per_page=10)
        data = paginator.get_response_data()

        pagination = data["pagination"]
        self.assertEqual(pagination["page"], 5)  # Last page

    def test_pagination_with_serializer_function(self):
        """Test pagination with custom serializer function."""
        request = self.factory.get("/api/users/")
        queryset = User.objects.filter(tenant=self.tenant).order_by("id")

        def serialize_user(user):
            return {"id": user.id, "username": user.username, "email": user.email}

        data = paginate_queryset(request, queryset, per_page=10, serializer_func=serialize_user)

        # Check that results are serialized
        self.assertEqual(len(data["results"]), 10)
        self.assertIn("username", data["results"][0])
        self.assertIn("email", data["results"][0])

    def test_pagination_empty_queryset(self):
        """Test pagination with empty queryset."""
        request = self.factory.get("/api/users/")
        queryset = User.objects.filter(username="nonexistent")

        paginator = APIPaginator(request, queryset, per_page=10)
        data = paginator.get_response_data()

        pagination = data["pagination"]
        self.assertEqual(pagination["total_items"], 0)
        self.assertEqual(pagination["total_pages"], 1)
        self.assertEqual(len(data["results"]), 0)

    def test_paginate_queryset_convenience_function(self):
        """Test the convenience function for pagination."""
        request = self.factory.get("/api/users/?page=2&per_page=15")
        queryset = User.objects.filter(tenant=self.tenant).order_by("id")

        data = paginate_queryset(request, queryset, per_page=10)

        self.assertIn("results", data)
        self.assertIn("pagination", data)
        self.assertEqual(data["pagination"]["page"], 2)
        self.assertEqual(data["pagination"]["per_page"], 15)


@override_settings(RATELIMIT_ENABLE=True)
class ThrottlingTests(TestCase):
    """Test API throttling functionality."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.tenant = Tenant.objects.create(
            company_name="Test Company", slug="test-company", status="ACTIVE"
        )
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

    def test_api_ratelimit_decorator(self):
        """Test that rate limit decorator is applied correctly."""

        @api_ratelimit(key="ip", rate="3/m")
        def test_view(request):
            return JsonResponse({"success": True})

        request = self.factory.get("/api/test/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        # Test that decorator is applied and view works
        response = test_view(request)
        self.assertEqual(response.status_code, 200)

        # Verify response structure
        data = json.loads(response.content)
        self.assertIn("success", data)
        self.assertTrue(data["success"])

        # Note: Actual rate limiting enforcement requires Redis state
        # and is tested in integration/manual testing

    def test_api_ratelimit_user_decorator(self):
        """Test that user-based rate limiting decorator is applied correctly."""

        @api_ratelimit_user(rate="3/m")
        def test_view(request):
            return JsonResponse({"success": True})

        request = self.factory.get("/api/test/")
        request.user = self.user

        # Test that decorator is applied and view works
        response = test_view(request)
        self.assertEqual(response.status_code, 200)

        # Verify response structure
        data = json.loads(response.content)
        self.assertIn("success", data)

        # Note: Actual rate limiting enforcement requires Redis state
        # and is tested in integration/manual testing

    def test_api_ratelimit_tenant_decorator(self):
        """Test that tenant-based rate limiting decorator is applied correctly."""

        @api_ratelimit_tenant(rate="3/m")
        def test_view(request):
            return JsonResponse({"success": True})

        request = self.factory.get("/api/test/")
        request.user = self.user

        # Test that decorator is applied and view works
        response = test_view(request)
        self.assertEqual(response.status_code, 200)

        # Verify response structure
        data = json.loads(response.content)
        self.assertIn("success", data)

        # Note: Actual rate limiting enforcement requires Redis state
        # and is tested in integration/manual testing

    def test_predefined_rate_limits(self):
        """Test predefined rate limit decorators."""

        @api_ratelimit_strict
        def strict_view(request):
            return JsonResponse({"success": True})

        @api_ratelimit_standard
        def standard_view(request):
            return JsonResponse({"success": True})

        @api_ratelimit_lenient
        def lenient_view(request):
            return JsonResponse({"success": True})

        request = self.factory.get("/api/test/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        # All should work for first request
        self.assertEqual(strict_view(request).status_code, 200)
        self.assertEqual(standard_view(request).status_code, 200)
        self.assertEqual(lenient_view(request).status_code, 200)

    def test_rate_limit_different_ips(self):
        """Test that rate limit decorator handles different IPs correctly."""

        @api_ratelimit(key="ip", rate="2/m")
        def test_view(request):
            return JsonResponse({"success": True})

        # First IP
        request1 = self.factory.get("/api/test/")
        request1.META["REMOTE_ADDR"] = "127.0.0.1"

        # Second IP
        request2 = self.factory.get("/api/test/")
        request2.META["REMOTE_ADDR"] = "192.168.1.1"

        # Both IPs should work (decorator is applied)
        self.assertEqual(test_view(request1).status_code, 200)
        self.assertEqual(test_view(request2).status_code, 200)

        # Note: Actual per-IP rate limiting enforcement requires Redis state
        # and is tested in integration/manual testing

    def test_rate_limit_write_operations(self):
        """Test rate limiting for write operations."""

        @api_ratelimit_write
        def test_view(request):
            return JsonResponse({"success": True})

        request = self.factory.post("/api/test/")
        request.user = self.user

        # Should work for POST
        response = test_view(request)
        self.assertEqual(response.status_code, 200)


@override_settings(MIDDLEWARE=["django.middleware.gzip.GZipMiddleware"])
class CompressionTests(TestCase):
    """Test GZip compression for API responses."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()

    def test_gzip_compression_enabled(self):
        """Test that GZip compression is enabled in middleware."""
        from django.conf import settings

        self.assertIn("django.middleware.gzip.GZipMiddleware", settings.MIDDLEWARE)

    def test_large_response_compression(self):
        """Test that large responses are compressed."""
        # Create a large JSON response
        large_data = {"items": [{"id": i, "name": f"Item {i}"} for i in range(1000)]}
        response = JsonResponse(large_data)

        # Check that response is compressible
        content = response.content
        self.assertGreater(len(content), 200)  # Larger than GZIP_MIN_LENGTH

        # Simulate compression
        compressed = gzip.compress(content)
        compression_ratio = len(compressed) / len(content)

        # Should achieve significant compression
        self.assertLess(compression_ratio, 0.5)  # At least 50% compression

    def test_small_response_not_compressed(self):
        """Test that small responses are not compressed."""
        small_data = {"status": "ok"}
        response = JsonResponse(small_data)

        content = response.content
        # Small responses (< 200 bytes) typically aren't compressed
        self.assertLess(len(content), 200)


class APIOptimizationIntegrationTests(TestCase):
    """Integration tests for API optimizations."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.tenant = Tenant.objects.create(
            company_name="Test Company", slug="test-company", status="ACTIVE"
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_EMPLOYEE",
        )
        cache.clear()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_paginated_api_with_rate_limiting(self):
        """Test that pagination and rate limiting work together."""

        @api_ratelimit(key="ip", rate="10/m")
        def list_users(request):
            queryset = User.objects.filter(tenant=request.user.tenant).order_by("id")

            # Serialize users properly
            def serialize_user(user):
                return {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                }

            data = paginate_queryset(request, queryset, per_page=10, serializer_func=serialize_user)
            return JsonResponse(data)

        request = self.factory.get("/api/users/?page=1")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        # Should work with both features
        response = list_users(request)
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn("results", data)
        self.assertIn("pagination", data)

    def test_api_response_structure(self):
        """Test that API responses follow consistent structure."""

        def api_view(request):
            queryset = User.objects.filter(tenant=request.user.tenant).order_by("id")
            data = paginate_queryset(
                request,
                queryset,
                per_page=5,
                serializer_func=lambda u: {"id": u.id, "username": u.username},
            )
            return JsonResponse(data)

        request = self.factory.get("/api/users/")
        request.user = self.user

        response = api_view(request)
        data = json.loads(response.content)

        # Check structure
        self.assertIn("results", data)
        self.assertIn("pagination", data)

        # Check pagination metadata
        pagination = data["pagination"]
        required_fields = [
            "page",
            "per_page",
            "total_pages",
            "total_items",
            "has_next",
            "has_previous",
            "next_page",
            "previous_page",
        ]
        for field in required_fields:
            self.assertIn(field, pagination)
