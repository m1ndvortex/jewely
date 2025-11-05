# Caching Strategy Documentation

## Overview

This document describes the comprehensive caching strategy implemented for the jewelry shop SaaS platform. The caching system uses Redis with django-redis and provides multiple cache backends for different use cases.

## Architecture

### Cache Backends

The system uses four separate Redis databases for different caching purposes:

1. **default** (DB 0) - General purpose caching
   - Timeout: 5 minutes (300 seconds)
   - Use for: Session data, temporary data, general caching

2. **query** (DB 1) - Query result caching
   - Timeout: 15 minutes (900 seconds)
   - Use for: Expensive database queries, report results, aggregations

3. **template** (DB 2) - Template fragment caching
   - Timeout: 10 minutes (600 seconds)
   - Use for: Rendered template fragments, navigation menus, static content

4. **api** (DB 3) - API response caching
   - Timeout: 3 minutes (180 seconds)
   - Use for: API endpoint responses, frequently accessed data

### Configuration

Cache configuration is in `config/settings.py`:

```python
CACHES = {
    "default": {
        "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
        "LOCATION": "redis://redis:6379/0",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "MAX_CONNECTIONS": 50,
        },
        "KEY_PREFIX": "jewelry_shop",
        "TIMEOUT": 300,
    },
    "query": {
        "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
        "LOCATION": "redis://redis:6379/1",
        "KEY_PREFIX": "jewelry_shop_query",
        "TIMEOUT": 900,
    },
    # ... other backends
}
```

## Cache Utilities

### Decorators

#### `@cache_query_result`

Cache expensive query results:

```python
from apps.core.cache_utils import cache_query_result

@cache_query_result(timeout=900, key_prefix="inventory_list")
def get_inventory_items(tenant_id, branch_id=None):
    return InventoryItem.objects.filter(tenant_id=tenant_id)
```

#### `@cache_tenant_query`

Cache tenant-specific query results (first argument must be tenant_id):

```python
from apps.core.cache_utils import cache_tenant_query

@cache_tenant_query(timeout=900, key_prefix="sales_summary")
def get_sales_summary(tenant_id, start_date, end_date):
    return Sale.objects.filter(
        tenant_id=tenant_id,
        created_at__date__range=[start_date, end_date]
    ).aggregate(total=Sum('total'))
```

#### `@cache_api_response`

Cache API responses:

```python
from apps.core.cache_utils import cache_api_response

@cache_api_response(timeout=300, key_prefix="product_list")
def list_products(request):
    products = Product.objects.filter(tenant=request.user.tenant)
    return JsonResponse({'products': list(products.values())})
```

### Helper Functions

#### `get_cache_key()`

Generate consistent cache keys:

```python
from apps.core.cache_utils import get_cache_key

cache_key = get_cache_key("inventory", tenant_id, branch_id)
```

#### `get_tenant_cache_key()`

Generate tenant-specific cache keys:

```python
from apps.core.cache_utils import get_tenant_cache_key

cache_key = get_tenant_cache_key(tenant_id, "sales", year=2024)
```

#### `get_or_set_cache()`

Get from cache or compute and cache:

```python
from apps.core.cache_utils import get_or_set_cache

result = get_or_set_cache(
    "expensive_calculation",
    lambda: expensive_function(),
    timeout=900
)
```

### Convenience Functions

#### Dashboard Caching

```python
from apps.core.cache_utils import (
    cache_dashboard_data,
    get_cached_dashboard_data
)

# Cache dashboard data
cache_dashboard_data(tenant_id, data, timeout=300)

# Retrieve cached dashboard data
data = get_cached_dashboard_data(tenant_id)
```

#### Report Caching

```python
from apps.core.cache_utils import (
    cache_report_result,
    get_cached_report_result
)

# Cache report result
cache_report_result(
    tenant_id,
    "sales_report",
    {"start_date": "2024-01-01", "end_date": "2024-12-31"},
    report_data,
    timeout=900
)

# Retrieve cached report
report = get_cached_report_result(
    tenant_id,
    "sales_report",
    {"start_date": "2024-01-01", "end_date": "2024-12-31"}
)
```

#### Gold Rate Caching

```python
from apps.core.cache_utils import (
    cache_gold_rate,
    get_cached_gold_rate
)

# Cache current gold rate
cache_gold_rate(rate_data, timeout=300)

# Get cached gold rate
rate = get_cached_gold_rate()
```

## Cache Invalidation

### Automatic Invalidation

The system automatically invalidates cache when models change using Django signals. Signal handlers are in `apps/core/cache_invalidation.py`.

Example: When an inventory item is saved or deleted, the following caches are invalidated:
- Tenant-specific inventory cache
- Dashboard cache
- Branch-specific inventory cache

### Manual Invalidation

#### Invalidate by Pattern

```python
from apps.core.cache_utils import invalidate_cache

# Invalidate all inventory-related cache
invalidate_cache("inventory:*")

# Invalidate tenant-specific cache
invalidate_cache("tenant:123:*")
```

#### Invalidate Tenant Cache

```python
from apps.core.cache_utils import invalidate_tenant_cache

# Invalidate all cache for a tenant
invalidate_tenant_cache(tenant_id)

# Invalidate specific prefix for a tenant
invalidate_tenant_cache(tenant_id, prefix="inventory")
```

#### Invalidate Model Cache

```python
from apps.core.cache_utils import invalidate_model_cache

# Invalidate cache for a model
invalidate_model_cache("InventoryItem", tenant_id=123)

# Invalidate across all tenants
invalidate_model_cache("Sale")
```

## Template Fragment Caching

### Basic Usage

```django
{% load cache %}

{% cache 600 sidebar request.user.tenant.id %}
    <!-- Expensive sidebar rendering -->
    <div class="sidebar">
        {% for item in menu_items %}
            <a href="{{ item.url }}">{{ item.name }}</a>
        {% endfor %}
    </div>
{% endcache %}
```

### Cache Key Variations

Cache keys can vary on multiple variables:

```django
{# Vary by tenant and language #}
{% cache 3600 navigation request.user.tenant.id LANGUAGE_CODE %}
    <!-- Navigation menu -->
{% endcache %}

{# Vary by user role #}
{% cache 1800 dashboard_widgets request.user.tenant.id request.user.role %}
    <!-- Role-specific widgets -->
{% endcache %}

{# Vary by date #}
{% cache 300 daily_stats request.user.tenant.id today %}
    <!-- Today's statistics -->
{% endcache %}
```

### Using Different Cache Backends

```django
{# Use the 'template' cache backend #}
{% cache 600 product_list request.user.tenant.id using="template" %}
    <!-- Product list -->
{% endcache %}
```

## Best Practices

### 1. Choose Appropriate Timeouts

- **Short (1-5 minutes)**: Frequently changing data (sales, inventory levels)
- **Medium (10-30 minutes)**: Moderately changing data (product lists, categories)
- **Long (1+ hours)**: Rarely changing data (navigation menus, settings)

### 2. Use Tenant-Specific Keys

Always include tenant_id in cache keys for multi-tenant data:

```python
cache_key = get_tenant_cache_key(tenant_id, "prefix", other_params)
```

### 3. Cache at the Right Level

- **Query level**: Cache expensive database queries
- **View level**: Cache entire view responses
- **Template level**: Cache template fragments
- **API level**: Cache API responses

### 4. Invalidate Smartly

- Use signals for automatic invalidation
- Invalidate related caches together
- Use patterns for bulk invalidation

### 5. Monitor Cache Performance

Use Prometheus metrics to monitor:
- Cache hit/miss ratios
- Cache memory usage
- Cache operation latency

### 6. Handle Cache Failures Gracefully

Always have fallback logic:

```python
result = cache.get(cache_key)
if result is None:
    result = expensive_operation()
    cache.set(cache_key, result, timeout)
return result
```

### 7. Avoid Caching User-Specific Data

Don't cache data that varies by user unless the cache key includes user_id:

```python
# Bad - will return same data for all users
@cache_query_result(key_prefix="user_orders")
def get_user_orders(user_id):
    return Order.objects.filter(user_id=user_id)

# Good - cache key includes user_id
@cache_tenant_query(key_prefix="user_orders")
def get_user_orders(tenant_id, user_id):
    return Order.objects.filter(tenant_id=tenant_id, user_id=user_id)
```

## Performance Targets

Based on Requirement 26:

- **Page load times**: < 2 seconds (initial load)
- **API response times**: < 500ms (95th percentile)
- **Database query times**: < 100ms (95th percentile)

Caching helps achieve these targets by:
- Reducing database queries
- Avoiding expensive computations
- Serving pre-rendered content

## Testing Cache

### Unit Tests

```python
from django.core.cache import caches
from django.test import TestCase

class CacheTest(TestCase):
    def test_query_caching(self):
        cache = caches['query']
        
        # First call - cache miss
        result1 = get_expensive_query(tenant_id=1)
        
        # Second call - cache hit
        result2 = get_expensive_query(tenant_id=1)
        
        self.assertEqual(result1, result2)
```

### Integration Tests

```python
def test_cache_invalidation(self):
    # Create item
    item = InventoryItem.objects.create(...)
    
    # Cache should be invalidated
    cached_data = get_cached_inventory(tenant_id)
    self.assertIsNone(cached_data)
```

## Monitoring

### Redis Monitoring

Check Redis stats:

```bash
docker compose exec redis redis-cli INFO stats
docker compose exec redis redis-cli INFO memory
```

### Cache Metrics

View cache metrics in Prometheus:
- `django_cache_get_total` - Total cache get operations
- `django_cache_hits_total` - Total cache hits
- `django_cache_misses_total` - Total cache misses

### Grafana Dashboards

View cache performance in Grafana:
- Cache hit/miss ratio
- Cache memory usage
- Cache operation latency

## Troubleshooting

### Cache Not Working

1. Check Redis is running:
   ```bash
   docker compose ps redis
   ```

2. Check Redis connectivity:
   ```bash
   docker compose exec web python manage.py shell
   >>> from django.core.cache import caches
   >>> caches['default'].set('test', 'value')
   >>> caches['default'].get('test')
   ```

3. Check cache configuration in settings.py

### Cache Not Invalidating

1. Verify signals are connected:
   ```python
   # In apps/core/apps.py ready() method
   import apps.core.cache_invalidation
   ```

2. Check signal handlers are being called

3. Verify cache key patterns match

### High Memory Usage

1. Check cache sizes:
   ```bash
   docker compose exec redis redis-cli INFO memory
   ```

2. Reduce cache timeouts

3. Implement cache eviction policies

4. Use separate Redis instances for different cache backends

## Examples

See the following files for complete examples:

- `apps/core/cache_utils.py` - Cache utility functions
- `apps/core/cache_invalidation.py` - Cache invalidation signals
- `apps/core/cached_dashboard_views.py` - Cached view examples
- `apps/core/templates/core/cached_dashboard_example.html` - Template caching examples

## References

- [Django Cache Framework](https://docs.djangoproject.com/en/4.2/topics/cache/)
- [django-redis Documentation](https://github.com/jazzband/django-redis)
- [Redis Documentation](https://redis.io/documentation)
- [Prometheus Django Metrics](https://github.com/korfuri/django-prometheus)
