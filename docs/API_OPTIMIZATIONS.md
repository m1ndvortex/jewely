# API Optimizations Guide

This document describes the API optimization features implemented in Task 28.4, including pagination, response compression, and API throttling.

## Overview

Per Requirement 26 (Performance Optimization and Scaling), the following optimizations have been implemented:

1. **Pagination** - Efficient handling of large datasets
2. **GZip Compression** - Automatic response compression
3. **API Throttling** - Rate limiting to prevent abuse

## 1. Pagination

### Purpose

Pagination improves API performance by:
- Reducing response payload size
- Decreasing database query time
- Improving client-side rendering performance
- Reducing memory usage

### Usage

#### Basic Pagination

```python
from django.http import JsonResponse
from apps.core.pagination import paginate_queryset

def list_items_api(request):
    queryset = MyModel.objects.filter(tenant=request.user.tenant).order_by('id')
    
    data = paginate_queryset(request, queryset, per_page=20)
    return JsonResponse(data)
```

#### With Custom Serialization

```python
def list_items_api(request):
    queryset = MyModel.objects.filter(tenant=request.user.tenant).order_by('id')
    
    def serialize_item(item):
        return {
            'id': item.id,
            'name': item.name,
            'created_at': item.created_at.isoformat(),
        }
    
    data = paginate_queryset(
        request,
        queryset,
        per_page=25,
        max_per_page=100,
        serializer_func=serialize_item
    )
    return JsonResponse(data)
```

#### Using APIPaginator Class

```python
from apps.core.pagination import APIPaginator

def list_items_api(request):
    queryset = MyModel.objects.filter(tenant=request.user.tenant).order_by('id')
    
    paginator = APIPaginator(request, queryset, per_page=20, max_per_page=100)
    
    # Get serialized data
    items = paginator.get_page_data()
    serialized_items = [serialize_item(item) for item in items]
    
    # Get response with pagination metadata
    data = paginator.get_response_data(data=serialized_items)
    return JsonResponse(data)
```

### Query Parameters

- `page` - Page number (default: 1)
- `per_page` - Items per page (default: 20, max: 100)

### Response Format

```json
{
    "results": [
        {"id": 1, "name": "Item 1"},
        {"id": 2, "name": "Item 2"}
    ],
    "pagination": {
        "page": 1,
        "per_page": 20,
        "total_pages": 5,
        "total_items": 100,
        "has_next": true,
        "has_previous": false,
        "next_page": 2,
        "previous_page": null
    }
}
```

### Best Practices

1. **Always order querysets** - Use `.order_by()` for consistent pagination
2. **Use select_related/prefetch_related** - Prevent N+1 queries
3. **Set reasonable defaults** - 20-50 items per page is typical
4. **Enforce max limits** - Prevent clients from requesting too many items
5. **Cache expensive queries** - Use Redis for frequently accessed data

## 2. GZip Compression

### Purpose

GZip compression reduces bandwidth usage by:
- Compressing JSON responses (typically 70-90% reduction)
- Reducing transfer time for large payloads
- Improving API response times
- Reducing hosting costs

### Configuration

GZip compression is enabled via `GZipMiddleware` in `settings.py`:

```python
MIDDLEWARE = [
    # ...
    "django.middleware.gzip.GZipMiddleware",  # Early in middleware stack
    # ...
]

# Minimum response size to compress (bytes)
GZIP_MIN_LENGTH = 200
```

### How It Works

1. Client sends request with `Accept-Encoding: gzip` header
2. Django processes request and generates response
3. GZipMiddleware compresses response if:
   - Response size > `GZIP_MIN_LENGTH` (200 bytes)
   - Client supports gzip encoding
   - Response is compressible (JSON, HTML, CSS, JS)
4. Compressed response sent with `Content-Encoding: gzip` header

### Automatic Compression

Compression is **automatic** - no code changes needed. The middleware handles:
- Checking client support
- Compressing eligible responses
- Setting appropriate headers
- Skipping already-compressed content

### Compression Ratios

Typical compression ratios for API responses:

- JSON data: 70-90% reduction
- HTML pages: 60-80% reduction
- CSS/JavaScript: 70-85% reduction

Example:
- Original JSON: 50 KB
- Compressed: 8 KB (84% reduction)

### Testing Compression

```bash
# Test with curl
curl -H "Accept-Encoding: gzip" http://localhost:8000/api/users/ --compressed -v

# Check response headers
# Should see: Content-Encoding: gzip
```

## 3. API Throttling (Rate Limiting)

### Purpose

Rate limiting prevents API abuse by:
- Protecting against DDoS attacks
- Ensuring fair resource usage across tenants
- Preventing accidental infinite loops
- Maintaining system stability

### Configuration

Rate limiting is configured in `settings.py`:

```python
# Enable/disable rate limiting
RATELIMIT_ENABLE = True

# Use Redis for rate limit tracking
RATELIMIT_USE_CACHE = 'default'

# Default rate limits
RATELIMIT_DEFAULT_RATE = '100/h'      # 100 requests per hour
RATELIMIT_STRICT_RATE = '10/m'        # 10 requests per minute
RATELIMIT_LENIENT_RATE = '500/h'      # 500 requests per hour
RATELIMIT_TENANT_RATE = '1000/h'      # 1000 requests per hour per tenant
RATELIMIT_USER_RATE = '100/h'         # 100 requests per hour per user
```

### Usage

#### IP-Based Rate Limiting

```python
from apps.core.throttling import api_ratelimit

@api_ratelimit(key='ip', rate='100/h')
def my_api_view(request):
    return JsonResponse({'data': 'value'})
```

#### User-Based Rate Limiting

```python
from apps.core.throttling import api_ratelimit_user

@api_ratelimit_user(rate='50/h')
def user_api_view(request):
    return JsonResponse({'data': 'value'})
```

#### Tenant-Based Rate Limiting

```python
from apps.core.throttling import api_ratelimit_tenant

@api_ratelimit_tenant(rate='1000/h')
def tenant_api_view(request):
    return JsonResponse({'data': 'value'})
```

#### Predefined Rate Limits

```python
from apps.core.throttling import (
    api_ratelimit_strict,    # 10/m - expensive operations
    api_ratelimit_standard,  # 100/h - general endpoints
    api_ratelimit_lenient,   # 500/h - read-only operations
    api_ratelimit_write,     # 50/h - write operations
)

@api_ratelimit_strict
def expensive_operation(request):
    # Generate report, trigger background job, etc.
    pass

@api_ratelimit_lenient
def read_only_endpoint(request):
    # List, search, retrieve operations
    pass

@api_ratelimit_write
def create_or_update(request):
    # POST, PUT, PATCH operations
    pass
```

### Rate Limit Formats

- `10/s` - 10 requests per second
- `100/m` - 100 requests per minute
- `1000/h` - 1000 requests per hour
- `10000/d` - 10000 requests per day

### Rate Limit Keys

- `ip` - Limit by IP address
- `user` - Limit by authenticated user
- `header:x-api-key` - Limit by custom header
- Custom function - Limit by tenant, organization, etc.

### Rate Limit Response

When rate limit is exceeded, API returns:

```json
{
    "error": "Rate limit exceeded",
    "message": "Too many requests. Please try again later.",
    "rate_limit": "100/h"
}
```

HTTP Status: `429 Too Many Requests`

### Best Practices

1. **Use appropriate limits** - Balance security and usability
2. **Different limits for different operations**:
   - Read operations: More lenient (500/h)
   - Write operations: Stricter (50/h)
   - Expensive operations: Very strict (10/m)
3. **Tenant-based limits** - Ensure fair usage in multi-tenant systems
4. **Monitor rate limit hits** - Track which endpoints are being limited
5. **Communicate limits** - Document rate limits in API documentation

## Complete Example

Here's a complete example combining all optimizations:

```python
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.core.pagination import paginate_queryset
from apps.core.throttling import api_ratelimit_tenant

@require_http_methods(['GET'])
@login_required
@api_ratelimit_tenant(rate='1000/h')
def list_products_api(request):
    """
    List products with full optimizations:
    - Pagination for large datasets
    - GZip compression (automatic)
    - Rate limiting by tenant
    - Efficient database queries
    """
    # Efficient query
    queryset = (
        Product.objects
        .filter(tenant=request.user.tenant)
        .select_related('category', 'branch')
        .only('id', 'name', 'sku', 'price', 'category__name', 'branch__name')
        .order_by('-created_at')
    )
    
    # Serializer
    def serialize_product(product):
        return {
            'id': product.id,
            'name': product.name,
            'sku': product.sku,
            'price': str(product.price),
            'category': product.category.name,
            'branch': product.branch.name,
        }
    
    # Paginate
    data = paginate_queryset(
        request,
        queryset,
        per_page=50,
        max_per_page=200,
        serializer_func=serialize_product
    )
    
    # Response will be automatically compressed if large enough
    return JsonResponse(data)
```

## Performance Metrics

### Expected Improvements

With these optimizations, you should see:

1. **Response Time**:
   - Without pagination: 2-5 seconds for 1000 items
   - With pagination: 200-500ms for 50 items
   - Target: <500ms for 95th percentile (Requirement 26.2)

2. **Bandwidth Usage**:
   - Without compression: 50 KB JSON response
   - With compression: 8 KB (84% reduction)
   - Savings: ~40 KB per request

3. **Server Load**:
   - Rate limiting prevents abuse
   - Pagination reduces database load
   - Compression reduces network I/O

### Monitoring

Monitor these metrics:

- API response times (p50, p95, p99)
- Rate limit hit rate
- Compression ratios
- Database query times
- Cache hit rates

Use Prometheus and Grafana dashboards to track these metrics.

## Testing

Run tests to verify optimizations:

```bash
# Run all API optimization tests
docker compose exec web pytest apps/core/tests/test_api_optimizations.py -v

# Run specific test categories
docker compose exec web pytest apps/core/tests/test_api_optimizations.py::PaginationTests -v
docker compose exec web pytest apps/core/tests/test_api_optimizations.py::ThrottlingTests -v
docker compose exec web pytest apps/core/tests/test_api_optimizations.py::CompressionTests -v
```

## Troubleshooting

### Pagination Issues

**Problem**: Inconsistent results across pages
**Solution**: Always use `.order_by()` on querysets

**Problem**: Slow pagination on large datasets
**Solution**: Add database indexes on ordering fields

### Compression Issues

**Problem**: Responses not being compressed
**Solution**: Check client sends `Accept-Encoding: gzip` header

**Problem**: Already compressed content being re-compressed
**Solution**: GZipMiddleware automatically skips compressed content

### Rate Limiting Issues

**Problem**: Rate limits not working
**Solution**: Ensure Redis is running and `RATELIMIT_ENABLE=True`

**Problem**: Rate limits too strict/lenient
**Solution**: Adjust rates in settings or per-endpoint decorators

## References

- Django Pagination: https://docs.djangoproject.com/en/4.2/topics/pagination/
- GZip Middleware: https://docs.djangoproject.com/en/4.2/ref/middleware/#django.middleware.gzip.GZipMiddleware
- django-ratelimit: https://django-ratelimit.readthedocs.io/
- Requirement 26: Performance Optimization and Scaling
