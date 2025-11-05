"""
Cache utilities for the jewelry shop platform.

This module provides decorators, utilities, and helper functions for caching
query results, API responses, and template fragments with smart invalidation.
"""

import functools
import hashlib
from typing import Any, Callable, Optional, Union

from django.core.cache import caches
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.db.models import Model, QuerySet
from django.http import HttpRequest
from django.utils.encoding import force_bytes


def get_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Generate a cache key from prefix and arguments.

    Args:
        prefix: Cache key prefix
        *args: Positional arguments to include in key
        **kwargs: Keyword arguments to include in key

    Returns:
        str: Generated cache key
    """
    key_parts = [prefix]

    # Add positional arguments
    for arg in args:
        if isinstance(arg, (QuerySet, Model)):
            # For Django models/querysets, use their string representation
            key_parts.append(str(arg))
        else:
            key_parts.append(str(arg))

    # Add keyword arguments (sorted for consistency)
    for key, value in sorted(kwargs.items()):
        key_parts.append(f"{key}={value}")

    # Create hash of the key parts
    key_string = ":".join(key_parts)
    key_hash = hashlib.md5(force_bytes(key_string)).hexdigest()

    return f"{prefix}:{key_hash}"


def get_tenant_cache_key(tenant_id: Union[str, int], prefix: str, *args, **kwargs) -> str:
    """
    Generate a tenant-specific cache key.

    Args:
        tenant_id: Tenant identifier
        prefix: Cache key prefix
        *args: Positional arguments to include in key
        **kwargs: Keyword arguments to include in key

    Returns:
        str: Generated tenant-specific cache key
    """
    return get_cache_key(f"tenant:{tenant_id}:{prefix}", *args, **kwargs)


def cache_query_result(
    timeout: int = DEFAULT_TIMEOUT,
    cache_alias: str = "query",
    key_prefix: str = "query",
):
    """
    Decorator to cache expensive query results.

    Usage:
        @cache_query_result(timeout=900, key_prefix="inventory_list")
        def get_inventory_items(tenant_id, branch_id=None):
            return InventoryItem.objects.filter(tenant_id=tenant_id)

    Args:
        timeout: Cache timeout in seconds
        cache_alias: Cache backend to use
        key_prefix: Prefix for cache key

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = get_cache_key(key_prefix, *args, **kwargs)

            # Try to get from cache
            cache = caches[cache_alias]
            result = cache.get(cache_key)

            if result is not None:
                return result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)

            return result

        return wrapper

    return decorator


def cache_tenant_query(
    timeout: int = DEFAULT_TIMEOUT,
    cache_alias: str = "query",
    key_prefix: str = "tenant_query",
):
    """
    Decorator to cache tenant-specific query results.

    The first argument must be tenant_id.

    Usage:
        @cache_tenant_query(timeout=900, key_prefix="sales_summary")
        def get_sales_summary(tenant_id, start_date, end_date):
            return Sale.objects.filter(tenant_id=tenant_id, ...)

    Args:
        timeout: Cache timeout in seconds
        cache_alias: Cache backend to use
        key_prefix: Prefix for cache key

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(tenant_id, *args, **kwargs):
            # Generate tenant-specific cache key
            cache_key = get_tenant_cache_key(tenant_id, key_prefix, *args, **kwargs)

            # Try to get from cache
            cache = caches[cache_alias]
            result = cache.get(cache_key)

            if result is not None:
                return result

            # Execute function and cache result
            result = func(tenant_id, *args, **kwargs)
            cache.set(cache_key, result, timeout)

            return result

        return wrapper

    return decorator


def cache_api_response(
    timeout: int = 180,
    cache_alias: str = "api",
    key_prefix: str = "api",
    vary_on_user: bool = True,
):
    """
    Decorator to cache API responses.

    Usage:
        @cache_api_response(timeout=300, key_prefix="product_list")
        def list_products(request):
            # ... return response

    Args:
        timeout: Cache timeout in seconds
        cache_alias: Cache backend to use
        key_prefix: Prefix for cache key
        vary_on_user: Include user ID in cache key

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            # Build cache key components
            key_parts = [key_prefix, request.path]

            # Add query parameters
            if request.GET:
                query_string = request.GET.urlencode()
                key_parts.append(query_string)

            # Add user ID if requested
            if vary_on_user and request.user.is_authenticated:
                key_parts.append(f"user:{request.user.id}")

            # Add tenant ID if available
            if hasattr(request, "tenant") and request.tenant:
                key_parts.append(f"tenant:{request.tenant.id}")

            # Generate cache key
            cache_key = get_cache_key(*key_parts)

            # Try to get from cache
            cache = caches[cache_alias]
            result = cache.get(cache_key)

            if result is not None:
                return result

            # Execute function and cache result
            result = func(request, *args, **kwargs)
            cache.set(cache_key, result, timeout)

            return result

        return wrapper

    return decorator


def invalidate_cache(
    key_pattern: str,
    cache_alias: str = "default",
):
    """
    Invalidate cache keys matching a pattern.

    Usage:
        invalidate_cache("inventory:*")
        invalidate_cache("tenant:123:*")

    Args:
        key_pattern: Pattern to match (supports wildcards)
        cache_alias: Cache backend to use
    """
    cache = caches[cache_alias]

    # django-redis supports delete_pattern
    if hasattr(cache, "delete_pattern"):
        cache.delete_pattern(key_pattern)
    else:
        # Fallback: clear entire cache
        cache.clear()


def invalidate_tenant_cache(
    tenant_id: Union[str, int],
    prefix: Optional[str] = None,
    cache_alias: str = "default",
):
    """
    Invalidate all cache entries for a specific tenant.

    Usage:
        invalidate_tenant_cache(tenant_id)
        invalidate_tenant_cache(tenant_id, prefix="inventory")

    Args:
        tenant_id: Tenant identifier
        prefix: Optional prefix to limit invalidation
        cache_alias: Cache backend to use
    """
    if prefix:
        pattern = f"*tenant:{tenant_id}:{prefix}*"
    else:
        pattern = f"*tenant:{tenant_id}*"

    invalidate_cache(pattern, cache_alias)


def invalidate_model_cache(
    model_name: str,
    tenant_id: Optional[Union[str, int]] = None,
):
    """
    Invalidate cache for a specific model.

    Usage:
        invalidate_model_cache("InventoryItem", tenant_id=123)
        invalidate_model_cache("Sale")

    Args:
        model_name: Name of the model
        tenant_id: Optional tenant ID to limit invalidation
    """
    if tenant_id:
        pattern = f"*tenant:{tenant_id}*{model_name.lower()}*"
    else:
        pattern = f"*{model_name.lower()}*"

    # Invalidate in all cache backends
    for cache_alias in ["default", "query", "template", "api"]:
        invalidate_cache(pattern, cache_alias)


def get_or_set_cache(
    key: str,
    default_func: Callable,
    timeout: int = DEFAULT_TIMEOUT,
    cache_alias: str = "default",
) -> Any:
    """
    Get value from cache or set it using the default function.

    Usage:
        result = get_or_set_cache(
            "expensive_calculation",
            lambda: expensive_function(),
            timeout=900
        )

    Args:
        key: Cache key
        default_func: Function to call if cache miss
        timeout: Cache timeout in seconds
        cache_alias: Cache backend to use

    Returns:
        Cached or computed value
    """
    cache = caches[cache_alias]
    result = cache.get(key)

    if result is None:
        result = default_func()
        cache.set(key, result, timeout)

    return result


class CacheManager:
    """
    Context manager for temporary cache operations.

    Usage:
        with CacheManager("query") as cache:
            cache.set("key", "value", 300)
            value = cache.get("key")
    """

    def __init__(self, cache_alias: str = "default"):
        self.cache_alias = cache_alias
        self.cache = None

    def __enter__(self):
        self.cache = caches[self.cache_alias]
        return self.cache

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Clean up if needed
        pass


# Convenience functions for common cache operations


def cache_dashboard_data(tenant_id: Union[str, int], data: dict, timeout: int = 300):
    """Cache dashboard data for a tenant."""
    cache_key = get_tenant_cache_key(tenant_id, "dashboard")
    caches["default"].set(cache_key, data, timeout)


def get_cached_dashboard_data(tenant_id: Union[str, int]) -> Optional[dict]:
    """Get cached dashboard data for a tenant."""
    cache_key = get_tenant_cache_key(tenant_id, "dashboard")
    return caches["default"].get(cache_key)


def cache_report_result(
    tenant_id: Union[str, int],
    report_type: str,
    params: dict,
    result: Any,
    timeout: int = 900,
):
    """Cache report generation result."""
    cache_key = get_tenant_cache_key(tenant_id, f"report:{report_type}", **params)
    caches["query"].set(cache_key, result, timeout)


def get_cached_report_result(
    tenant_id: Union[str, int],
    report_type: str,
    params: dict,
) -> Optional[Any]:
    """Get cached report result."""
    cache_key = get_tenant_cache_key(tenant_id, f"report:{report_type}", **params)
    return caches["query"].get(cache_key)


def cache_gold_rate(rate_data: dict, timeout: int = 300):
    """Cache current gold rate."""
    caches["default"].set("gold_rate:current", rate_data, timeout)


def get_cached_gold_rate() -> Optional[dict]:
    """Get cached gold rate."""
    return caches["default"].get("gold_rate:current")
