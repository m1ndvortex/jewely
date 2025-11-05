"""
Tests for caching utilities and functionality.

This module tests the caching strategy implementation including
cache decorators, invalidation, and helper functions.
"""

import time
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.core.cache import caches
from django.test import TestCase

from apps.core.cache_utils import (
    cache_api_response,
    cache_dashboard_data,
    cache_query_result,
    cache_tenant_query,
    get_cache_key,
    get_cached_dashboard_data,
    get_or_set_cache,
    get_tenant_cache_key,
    invalidate_cache,
    invalidate_model_cache,
    invalidate_tenant_cache,
)

User = get_user_model()


class CacheKeyGenerationTest(TestCase):
    """Test cache key generation functions."""

    def test_get_cache_key_basic(self):
        """Test basic cache key generation."""
        key = get_cache_key("test", "arg1", "arg2")
        self.assertIn("test:", key)
        self.assertEqual(len(key.split(":")), 2)  # prefix:hash

    def test_get_cache_key_with_kwargs(self):
        """Test cache key generation with keyword arguments."""
        key1 = get_cache_key("test", param1="value1", param2="value2")
        key2 = get_cache_key("test", param2="value2", param1="value1")
        # Keys should be the same regardless of kwarg order
        self.assertEqual(key1, key2)

    def test_get_tenant_cache_key(self):
        """Test tenant-specific cache key generation."""
        key = get_tenant_cache_key(123, "inventory", branch_id=456)
        self.assertIn("tenant:123:inventory", key)


class CacheDecoratorTest(TestCase):
    """Test cache decorators."""

    def setUp(self):
        """Clear cache before each test."""
        for cache_alias in ["default", "query", "template", "api"]:
            caches[cache_alias].clear()

    def test_cache_query_result_decorator(self):
        """Test query result caching decorator."""
        call_count = 0

        @cache_query_result(timeout=300, key_prefix="test_query")
        def expensive_query(param):
            nonlocal call_count
            call_count += 1
            return f"result_{param}"

        # First call - cache miss
        result1 = expensive_query("test")
        self.assertEqual(result1, "result_test")
        self.assertEqual(call_count, 1)

        # Second call - cache hit
        result2 = expensive_query("test")
        self.assertEqual(result2, "result_test")
        self.assertEqual(call_count, 1)  # Function not called again

        # Different parameter - cache miss
        result3 = expensive_query("other")
        self.assertEqual(result3, "result_other")
        self.assertEqual(call_count, 2)

    def test_cache_tenant_query_decorator(self):
        """Test tenant query caching decorator."""
        call_count = 0

        @cache_tenant_query(timeout=300, key_prefix="tenant_query")
        def get_tenant_data(tenant_id, param):
            nonlocal call_count
            call_count += 1
            return f"tenant_{tenant_id}_{param}"

        # First call - cache miss
        result1 = get_tenant_data(123, "data")
        self.assertEqual(result1, "tenant_123_data")
        self.assertEqual(call_count, 1)

        # Second call - cache hit
        result2 = get_tenant_data(123, "data")
        self.assertEqual(result2, "tenant_123_data")
        self.assertEqual(call_count, 1)

        # Different tenant - cache miss
        result3 = get_tenant_data(456, "data")
        self.assertEqual(result3, "tenant_456_data")
        self.assertEqual(call_count, 2)


class CacheInvalidationTest(TestCase):
    """Test cache invalidation functions."""

    def setUp(self):
        """Clear cache before each test."""
        for cache_alias in ["default", "query", "template", "api"]:
            caches[cache_alias].clear()

    def test_invalidate_cache_pattern(self):
        """Test cache invalidation by pattern."""
        cache = caches["default"]

        # Set some cache values
        cache.set("test:key1", "value1")
        cache.set("test:key2", "value2")
        cache.set("other:key3", "value3")

        # Invalidate test:* pattern
        invalidate_cache("test:*", cache_alias="default")

        # test:* keys should be gone
        self.assertIsNone(cache.get("test:key1"))
        self.assertIsNone(cache.get("test:key2"))

    def test_invalidate_tenant_cache(self):
        """Test tenant-specific cache invalidation."""
        cache = caches["default"]

        # Set tenant-specific cache
        tenant_key = get_tenant_cache_key(123, "inventory")
        cache.set(tenant_key, "inventory_data")

        # Invalidate tenant cache
        invalidate_tenant_cache(123, prefix="inventory")

        # Cache should be invalidated
        self.assertIsNone(cache.get(tenant_key))

    def test_invalidate_model_cache(self):
        """Test model-specific cache invalidation."""
        # Set cache in multiple backends
        for cache_alias in ["default", "query"]:
            cache = caches[cache_alias]
            cache.set("tenant:123:inventoryitem:list", "data")

        # Invalidate model cache
        invalidate_model_cache("InventoryItem", tenant_id=123)

        # Cache should be invalidated in all backends
        for cache_alias in ["default", "query"]:
            cache = caches[cache_alias]
            self.assertIsNone(cache.get("tenant:123:inventoryitem:list"))


class CacheHelperFunctionsTest(TestCase):
    """Test cache helper functions."""

    def setUp(self):
        """Clear cache before each test."""
        caches["default"].clear()

    def test_get_or_set_cache(self):
        """Test get_or_set_cache helper."""
        call_count = 0

        def compute_value():
            nonlocal call_count
            call_count += 1
            return "computed_value"

        # First call - cache miss
        result1 = get_or_set_cache("test_key", compute_value, timeout=300)
        self.assertEqual(result1, "computed_value")
        self.assertEqual(call_count, 1)

        # Second call - cache hit
        result2 = get_or_set_cache("test_key", compute_value, timeout=300)
        self.assertEqual(result2, "computed_value")
        self.assertEqual(call_count, 1)  # Function not called again

    def test_dashboard_caching(self):
        """Test dashboard data caching helpers."""
        tenant_id = 123
        dashboard_data = {"sales": 1000, "inventory_value": 50000, "alerts": 5}

        # Cache dashboard data
        cache_dashboard_data(tenant_id, dashboard_data, timeout=300)

        # Retrieve cached data
        cached_data = get_cached_dashboard_data(tenant_id)
        self.assertEqual(cached_data, dashboard_data)

        # Different tenant should have no cache
        other_cached = get_cached_dashboard_data(456)
        self.assertIsNone(other_cached)


class CacheTimeoutTest(TestCase):
    """Test cache timeout behavior."""

    def setUp(self):
        """Clear cache before each test."""
        caches["default"].clear()

    def test_cache_expiration(self):
        """Test that cache expires after timeout."""
        cache = caches["default"]

        # Set cache with 1 second timeout
        cache.set("test_key", "test_value", timeout=1)

        # Should be available immediately
        self.assertEqual(cache.get("test_key"), "test_value")

        # Wait for expiration
        time.sleep(2)

        # Should be expired
        self.assertIsNone(cache.get("test_key"))


class CacheBackendTest(TestCase):
    """Test different cache backends."""

    def test_multiple_cache_backends(self):
        """Test that different cache backends are isolated."""
        # Set same key in different backends
        caches["default"].set("test_key", "default_value")
        caches["query"].set("test_key", "query_value")
        caches["template"].set("test_key", "template_value")
        caches["api"].set("test_key", "api_value")

        # Each backend should have its own value
        self.assertEqual(caches["default"].get("test_key"), "default_value")
        self.assertEqual(caches["query"].get("test_key"), "query_value")
        self.assertEqual(caches["template"].get("test_key"), "template_value")
        self.assertEqual(caches["api"].get("test_key"), "api_value")

        # Clear one backend shouldn't affect others
        caches["default"].clear()
        self.assertIsNone(caches["default"].get("test_key"))
        self.assertEqual(caches["query"].get("test_key"), "query_value")


class CacheAPIResponseTest(TestCase):
    """Test API response caching."""

    def setUp(self):
        """Clear cache and create test user."""
        caches["api"].clear()
        self.user = User.objects.create_user(username="testuser", password="testpass123")

    def test_cache_api_response_decorator(self):
        """Test API response caching decorator."""
        call_count = 0

        @cache_api_response(timeout=300, key_prefix="test_api")
        def api_view(request):
            nonlocal call_count
            call_count += 1
            return {"data": "response"}

        # Create mock request
        request = Mock()
        request.path = "/api/test/"
        request.GET = Mock()
        request.GET.urlencode.return_value = ""
        request.user = self.user
        request.tenant = None

        # First call - cache miss
        result1 = api_view(request)
        self.assertEqual(result1, {"data": "response"})
        self.assertEqual(call_count, 1)

        # Second call - cache hit
        result2 = api_view(request)
        self.assertEqual(result2, {"data": "response"})
        self.assertEqual(call_count, 1)
