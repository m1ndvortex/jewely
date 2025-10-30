# Role-Based Navigation and Access Control Fix

## Problem Identified

Both Platform Admin and Tenant users were seeing the same navigation menu and could access each other's areas. The system wasn't properly separating:

1. **Platform Admin Features** (tenant management, subscriptions, monitoring, etc.)
2. **Tenant Features** (inventory, sales, customers, accounting, etc.)

## Solution Implemented

### 1. Updated Navigation Bar (`templates/base.html`)

**Platform Admin Navigation:**
- Dashboard → `/platform/dashboard/`
- Tenants → `/platform/tenants/`
- Subscriptions → `/platform/subscription-plans/`
- Monitoring → `/platform/monitoring/`
- Audit Logs → `/platform/audit-logs/`
- More dropdown:
  - Backups
  - Security
  - Feature Flags
  - Announcements
  - Webhooks
  - Jobs
  - Documentation

**Tenant User Navigation:**
- Dashboard → `/dashboard/`
- Inventory → `/inventory/`
- Sales → `/sales/pos/`
- Customers → `/customers/`
- More dropdown:
  - Accounting
  - Repairs
  - Procurement
  - Branches
  - Reports
  - Settings

### 2. Created Role-Based Access Middleware (`apps/core/role_middleware.py`)

This middleware enforces:
- Platform admins can ONLY access `/platform/*` URLs
- Tenant users CANNOT access `/platform/*` URLs
- Automatic redirects to appropriate dashboards if users try to access unauthorized areas
- Exemptions for common URLs (auth, static files, health checks, etc.)

### 3. Updated Home View (`apps/core/views.py`)

The root URL (`/`) now intelligently redirects:
- Platform admins → `/platform/dashboard/`
- Tenant users → `/dashboard/`
- Unauthenticated users → `/accounts/login/`

### 4. Existing Login Redirect Logic

The system already had proper redirect logic in `apps/core/adapters.py`:
- `get_login_redirect_url()` method redirects based on user role after login

## User Roles

The system supports these roles (defined in `apps/core/models.py`):

1. **PLATFORM_ADMIN** - Full platform access, manages all tenants
2. **TENANT_OWNER** - Tenant administrator, full access to their tenant
3. **TENANT_MANAGER** - Tenant manager, most tenant features
4. **TENANT_EMPLOYEE** - Basic tenant user, limited access

## Testing

To test the fix:

1. **Login as Platform Admin:**
   ```
   URL: http://localhost:8000/platform/login/
   Username: admin
   Password: AdminPassword123!
   ```
   - Should see Platform Admin navigation
   - Should be redirected to `/platform/dashboard/`
   - Should NOT be able to access `/dashboard/` or tenant features

2. **Login as Tenant User:**
   ```
   URL: http://localhost:8000/accounts/login/
   Username: tenant_user
   Password: TenantPassword123!
   ```
   - Should see Tenant navigation
   - Should be redirected to `/dashboard/`
   - Should NOT be able to access `/platform/*` URLs

## Files Modified

1. `templates/base.html` - Updated navigation to be role-specific
2. `apps/core/role_middleware.py` - NEW: Enforces role-based access control
3. `config/settings.py` - Added RoleBasedAccessMiddleware to MIDDLEWARE
4. `apps/core/views.py` - Updated home view to redirect based on role

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User Authentication                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              RoleBasedAccessMiddleware                       │
│  - Checks user role                                          │
│  - Enforces URL access rules                                 │
│  - Redirects unauthorized access                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────┴─────────┐
                    ↓                   ↓
        ┌───────────────────┐  ┌───────────────────┐
        │  Platform Admin   │  │   Tenant User     │
        │   /platform/*     │  │   /dashboard/     │
        │                   │  │   /inventory/     │
        │ - Tenants         │  │   /sales/         │
        │ - Subscriptions   │  │   /customers/     │
        │ - Monitoring      │  │   /accounting/    │
        │ - Audit Logs      │  │   /repair/        │
        │ - Backups         │  │   /procurement/   │
        │ - Security        │  │   /reports/       │
        │ - Feature Flags   │  │   /settings/      │
        │ - Announcements   │  │   /branches/      │
        │ - Webhooks        │  │                   │
        │ - Jobs            │  │                   │
        │ - Documentation   │  │                   │
        └───────────────────┘  └───────────────────┘
```

## Security Benefits

1. **Clear Separation of Concerns** - Admin and tenant features are completely separated
2. **Automatic Enforcement** - Middleware prevents unauthorized access at the request level
3. **User-Friendly** - Automatic redirects instead of error pages
4. **Audit Trail** - All access attempts are logged by existing audit middleware
5. **Impersonation Support** - Works seamlessly with django-hijack for admin impersonation

## Next Steps

If you want to further enhance this:

1. **Add permission decorators** to individual views for fine-grained control
2. **Create custom 403 pages** for better UX when access is denied
3. **Add role-based template tags** for conditional rendering in templates
4. **Implement feature flags** per tenant for gradual rollout
5. **Add API endpoint protection** with DRF permission classes

## Verification Commands

```bash
# Check for any Django issues
docker compose exec web python manage.py check

# Run tests
docker compose exec web pytest

# Check middleware order
docker compose exec web python manage.py diffsettings | grep MIDDLEWARE
```
