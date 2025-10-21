# PostgreSQL Row-Level Security (RLS) Implementation

## Overview

This document describes the PostgreSQL Row-Level Security (RLS) implementation for multi-tenant data isolation in the jewelry shop SaaS platform.

## Architecture

### Database-Level Isolation

RLS provides database-level tenant isolation, which means:
- Data filtering happens at the PostgreSQL level, not in application code
- Cannot be bypassed by ORM queries or raw SQL (unless explicitly allowed)
- Provides defense-in-depth security
- Automatic enforcement for all database operations

### Key Components

1. **PostgreSQL Functions**:
   - `set_tenant_context(tenant_uuid)`: Sets the current tenant context
   - `get_current_tenant()`: Returns the current tenant UUID
   - `is_rls_bypassed()`: Checks if RLS bypass is enabled

2. **Session Variables**:
   - `app.current_tenant`: Stores the current tenant UUID
   - `app.bypass_rls`: Controls whether RLS is bypassed (for platform admins)

3. **RLS Policies**:
   - SELECT: Users can only see their own tenant's data
   - INSERT: Only platform admins can create tenants
   - UPDATE: Users can update their own tenant, admins can update any
   - DELETE: Only platform admins can delete tenants

## Usage

### Setting Tenant Context

```python
from apps.core.tenant_context import set_tenant_context
from uuid import UUID

# Set tenant context for all subsequent queries
tenant_id = UUID('123e4567-e89b-12d3-a456-426614174000')
set_tenant_context(tenant_id)

# Now all queries are automatically scoped to this tenant
tenants = Tenant.objects.all()  # Returns only this tenant's data
```

### Using Context Manager

```python
from apps.core.tenant_context import tenant_context

# Temporarily switch tenant context
with tenant_context(tenant_id):
    # All queries here are scoped to tenant_id
    products = Product.objects.all()
# Original context is restored here
```

### Platform Admin Operations

```python
from apps.core.tenant_context import bypass_rls

# Bypass RLS for admin operations
with bypass_rls():
    # Can access all tenant data
    all_tenants = Tenant.objects.all()
# RLS is restored here
```

### Clearing Context

```python
from apps.core.tenant_context import clear_tenant_context

# Clear tenant context and disable RLS bypass
clear_tenant_context()
```

## Implementation Details

### FORCE ROW LEVEL SECURITY

The migration includes `ALTER TABLE tenants FORCE ROW LEVEL SECURITY` which is critical because:
- Django typically connects to PostgreSQL as a superuser
- By default, RLS policies don't apply to table owners/superusers
- FORCE ROW LEVEL SECURITY ensures policies apply even to superusers
- This provides true isolation even for privileged database connections

### Policy Logic

```sql
-- SELECT Policy
USING (
    id::text = current_setting('app.current_tenant', true)
    OR
    current_setting('app.bypass_rls', true) = 'true'
)
```

This means:
- If `app.current_tenant` matches the row's tenant_id, allow access
- If `app.bypass_rls` is 'true', allow access (admin mode)
- Otherwise, deny access

## Middleware Integration

In production, you'll need middleware to automatically set tenant context:

```python
# apps/core/middleware.py
from apps.core.tenant_context import set_tenant_context, enable_rls_bypass
from django.utils.deprecation import MiddlewareMixin

class TenantContextMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.user.is_authenticated:
            if request.user.role == 'PLATFORM_ADMIN':
                # Platform admins can see all tenants
                enable_rls_bypass()
            elif request.user.tenant:
                # Regular users are scoped to their tenant
                set_tenant_context(request.user.tenant_id)
```

## Testing

### Test Setup

When writing tests, you need to manage RLS context carefully:

```python
def setUp(self):
    # Enable bypass to create test data
    enable_rls_bypass()
    self.tenant = Tenant.objects.create(...)
    disable_rls_bypass()  # Important!

def test_tenant_isolation(self):
    # Set tenant context for the test
    set_tenant_context(self.tenant.id)
    
    # Now queries are scoped to this tenant
    tenants = Tenant.objects.all()
    assert tenants.count() == 1
```

### Common Pitfalls

1. **Forgetting to disable bypass after setUp**: Session variables persist across queries
2. **Not setting tenant context**: Queries will return no results
3. **Testing with superuser**: Even with RLS, need FORCE ROW LEVEL SECURITY

## Security Considerations

1. **Defense in Depth**: RLS is a database-level control, but should be combined with application-level checks
2. **Audit Logging**: All RLS bypass operations should be logged
3. **Principle of Least Privilege**: Only platform admins should have bypass capability
4. **Session Management**: Ensure tenant context is set correctly for each request

## Performance

RLS policies use PostgreSQL indexes efficiently:
- The `tenant_status_idx` index helps filter by status
- The `tenant_slug_idx` index helps with slug lookups
- RLS policies can use these indexes for fast filtering

## Future Tenant-Scoped Tables

When adding new tenant-scoped tables:

1. Add `tenant` foreign key to the model
2. Create migration to enable RLS:
   ```python
   migrations.RunSQL(
       sql="ALTER TABLE my_table ENABLE ROW LEVEL SECURITY;",
       reverse_sql="ALTER TABLE my_table DISABLE ROW LEVEL SECURITY;"
   )
   ```
3. Create RLS policy:
   ```python
   migrations.RunSQL(
       sql="""
       CREATE POLICY tenant_isolation_policy ON my_table
           FOR ALL
           USING (
               tenant_id::text = current_setting('app.current_tenant', true)
               OR current_setting('app.bypass_rls', true) = 'true'
           );
       """,
       reverse_sql="DROP POLICY IF EXISTS tenant_isolation_policy ON my_table;"
   )
   ```

## References

- [PostgreSQL RLS Documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- Requirement 1: Multi-Tenant Architecture with Data Isolation
- Task 2.2: Implement PostgreSQL Row-Level Security policies
