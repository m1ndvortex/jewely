# Tenant Context Middleware Implementation

## Overview

The `TenantContextMiddleware` automatically sets the PostgreSQL session variable for Row-Level Security (RLS) on every request, ensuring proper tenant data isolation throughout the application.

## Key Features

### 1. Tenant Extraction
The middleware extracts tenant ID from multiple sources (in priority order):
- **JWT Token**: From `Authorization: Bearer <token>` header (when JWT auth is implemented)
- **Session**: From `request.session['tenant_id']`
- **User Model**: From `request.user.tenant_id` or `request.user.tenant`

### 2. Tenant Validation
After extracting the tenant ID, the middleware:
- Sets the tenant context in PostgreSQL
- Queries the tenant to validate it exists (RLS allows this since context is set)
- Checks tenant status (ACTIVE, SUSPENDED, PENDING_DELETION)
- Returns appropriate error responses for invalid states

### 3. Security Features
- **Suspended Tenants**: Returns 403 with clear error message
- **Pending Deletion**: Returns 403 with deletion notice
- **Non-existent Tenants**: Returns 404 error
- **Platform Admin Bypass**: Enables RLS bypass for superusers on admin paths
- **Context Cleanup**: Clears tenant context after each request to prevent leakage

### 4. Exempt Paths
The following paths don't require tenant context:
- `/admin/` - Django admin (platform admin area)
- `/api/auth/login/` - Authentication endpoints
- `/api/auth/register/` - Registration endpoints
- `/api/auth/refresh/` - Token refresh
- `/health/` - Health checks
- `/metrics/` - Monitoring metrics
- `/static/` - Static files
- `/media/` - Media files

## Usage

### Configuration

The middleware is already configured in `config/settings.py`:

```python
MIDDLEWARE = [
    # ... other middleware ...
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.TenantContextMiddleware",  # After auth middleware
]
```

### Accessing Tenant in Views

The middleware adds tenant information to the request object:

```python
def my_view(request):
    # Access tenant object
    tenant = request.tenant
    tenant_id = request.tenant_id
    
    # All ORM queries are automatically scoped to this tenant
    products = Product.objects.all()  # Only this tenant's products
```

### Session-Based Authentication

For session-based auth, set the tenant_id in the session after login:

```python
def login_view(request):
    # After successful authentication
    user = authenticate(username=username, password=password)
    if user:
        login(request, user)
        # Set tenant context in session
        request.session['tenant_id'] = str(user.tenant_id)
```

### JWT Authentication (Future)

When JWT is implemented, include tenant_id in the token payload:

```python
from rest_framework_simplejwt.tokens import RefreshToken

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    # Add tenant_id to token payload
    refresh['tenant_id'] = str(user.tenant_id)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }
```

## Security Considerations

### 1. No RLS Bypass in Production Code
The middleware **never** bypasses RLS when validating tenants. It:
1. Sets the tenant context first
2. Then queries the tenant (RLS allows access since context matches)
3. This ensures proper security even for tenant validation

### 2. Context Isolation
- Tenant context is cleared at the start of each request
- Context is cleared after response is sent
- Context is cleared even if an exception occurs
- This prevents context leakage between requests

### 3. Platform Admin Access
- Only superusers get RLS bypass
- Bypass only enabled on `/admin/` paths
- All bypass operations are logged

### 4. Error Handling
- Database errors return 500 with generic message
- Invalid tenant IDs are logged but don't expose system details
- All security events are logged for audit

## Testing

Comprehensive tests cover:
- ✅ Tenant extraction from session
- ✅ Tenant extraction from user model
- ✅ Suspended tenant handling
- ✅ Pending deletion tenant handling
- ✅ Non-existent tenant handling
- ✅ Exempt paths
- ✅ Platform admin RLS bypass
- ✅ Context cleanup after requests
- ✅ Context cleanup on exceptions
- ✅ No context leakage between requests
- ✅ Edge cases and error handling

Test coverage: 84% for middleware module

## Requirements Satisfied

This implementation satisfies **Requirement 1** from the requirements document:
- Multi-tenant architecture with data isolation
- Automatic tenant context management
- Secure tenant validation
- Proper error handling for invalid tenant states

## Future Enhancements

1. **JWT Authentication**: Full JWT token support (currently has placeholder code)
2. **Rate Limiting**: Per-tenant rate limiting
3. **Metrics**: Track tenant context set/clear operations
4. **Caching**: Cache tenant status to reduce database queries
5. **Audit Logging**: Enhanced audit trail for tenant access

## Related Files

- `apps/core/middleware.py` - Middleware implementation
- `apps/core/tenant_context.py` - Tenant context utilities
- `apps/core/models.py` - Tenant model
- `tests/test_tenant_middleware.py` - Comprehensive test suite
- `config/settings.py` - Middleware configuration
