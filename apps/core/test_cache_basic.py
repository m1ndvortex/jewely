"""
Basic cache functionality tests without database dependencies.

Tests core caching utilities to verify Redis integration works.
"""

from django.core.cache import caches

import pytest

from apps.core.cache_utils import get_cache_key, get_tenant_cache_key


@pytest.mark.django_db
class TestBasicCacheFunctionality:
    """Test basic cache operations."""

    def test_cache_backends_configured(self):
        """Test that all cache backends are configured."""
        assert "default" in caches
        assert "query" in caches
        assert "template" in caches
        assert "api" in caches

    def test_cache_set_and_get(self):
        """Test basic cache set and get operations."""
        cache = caches["default"]
        cache.clear()

        # Set a value
        cache.set("test_key", "test_value", timeout=300)

        # Get the value
        result = cache.get("test_key")
        assert result == "test_value"

    def test_cache_key_generation(self):
        """Test cache key generation."""
        key1 = get_cache_key("test", "arg1", "arg2")
        key2 = get_cache_key("test", "arg1", "arg2")

        # Same arguments should generate same key
        assert key1 == key2

        # Different arguments should generate different key
        key3 = get_cache_key("test", "arg1", "arg3")
        assert key1 != key3

    def test_tenant_cache_key_generation(self):
        """Test tenant-specific cache key generation."""
        key1 = get_tenant_cache_key(123, "inventory")
        key2 = get_tenant_cache_key(123, "inventory")

        # Same tenant and prefix should generate same key
        assert key1 == key2

        # Different tenant should generate different key
        key3 = get_tenant_cache_key(456, "inventory")
        assert key1 != key3

    def test_cache_isolation_between_backends(self):
        """Test that cache backends are isolated."""
        # Set same key in different backends
        caches["default"].set("test_key", "default_value")
        caches["query"].set("test_key", "query_value")

        # Each backend should have its own value
        assert caches["default"].get("test_key") == "default_value"
        assert caches["query"].get("test_key") == "query_value"

    def test_cache_expiration(self):
        """Test that cache respects timeout."""
        cache = caches["default"]
        cache.clear()

        # Set with very short timeout
        cache.set("test_key", "test_value", timeout=1)

        # Should be available immediately
        assert cache.get("test_key") == "test_value"

        # After timeout, should be None
        import time

        time.sleep(2)
        assert cache.get("test_key") is None

    def test_cache_delete(self):
        """Test cache deletion."""
        cache = caches["default"]
        cache.clear()

        # Set a value
        cache.set("test_key", "test_value")
        assert cache.get("test_key") == "test_value"

        # Delete it
        cache.delete("test_key")
        assert cache.get("test_key") is None

    def test_cache_clear(self):
        """Test clearing entire cache."""
        cache = caches["default"]

        # Set multiple values
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        # Clear cache
        cache.clear()

        # All values should be gone
        assert cache.get("key1") is None
        assert cache.get("key2") is None
