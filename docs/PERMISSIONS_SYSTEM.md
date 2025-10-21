# Role-Based Permissions System

## Overview

The jewelry shop SaaS platform implements a comprehensive role-based access control (RBAC) system with object-level permissions using django-guardian. This document explains how to use the permissions system.

## User Roles

The system defines four primary roles:

1. **PLATFORM_ADMIN** - Platform administrators who manage the entire SaaS platform
2. **TENANT_OWNER** - Jewelry shop owners who have full control over their shop
3. **TENANT_MANAGER** - Shop managers with elevated permissions
4. **TENANT_EMPLOYEE** - Shop employees with basic access

## Permission Groups

Permission groups are automatically created by running:

```bash
docker compose exec web python manage.py setup_permissions
```

This creates:
- **Platform Administrators** - Full access to tenants, users, and branches
- **Tenant Owners** - Can manage users and branches within their tenant
- **Tenant Managers** - Limited user and branch management
- **Tenant Employees** - View-only access

## Using Decorators

### Function-Based Views

```python
from apps.core.decorators import (
    role_required,
    platform_admin_required,
    tenant_owner_required,
    tenant_manager_or_owner_required,
    tenant_access_required,
)

# Require specific role(s)
@role_required('TENANT_OWNER', 'TENANT_MANAGER')
def manage_inventory(request):
    # Only owners and managers can access
    pass

# Require platform admin
@platform_admin_required
def admin_dashboard(request):
    # Only platform admins can access
    pass

# Require tenant access
@tenant_access_required
def process_sale(request):
    # All tenant users can access
    pass
```

### Class-Based Views

```python
from apps.core.decorators import (
    role_required_for_class_view,
    platform_admin_required_for_class_view,
)

class InventoryView(APIView):
    @role_required_for_class_view('TENANT_OWNER', 'TENANT_MANAGER')
    def post(self, request):
        # Only owners and managers can create inventory
        pass
```

## Using Permission Classes

### DRF Views

```python
from rest_framework.views import APIView
from apps.core.permissions import (
    IsPlatformAdmin,
    IsTenantOwner,
    IsTenantManager,
    IsTenantManagerOrOwner,
    HasTenantAccess,
    CanManageUsers,
    CanManageInventory,
    CanProcessSales,
)

class UserManagementView(APIView):
    permission_classes = [CanManageUsers]
    
    def get(self, request):
        # Only users who can manage users can access
        pass

class InventoryView(APIView):
    permission_classes = [CanManageInventory]
    
    def post(self, request):
        # Only users who can manage inventory can create items
        pass
```

## Object-Level Permissions

### Checking Tenant Access

```python
from apps.core.permissions import IsSameTenant

class BranchDetailView(APIView):
    permission_classes = [IsSameTenant]
    
    def get_object(self):
        obj = Branch.objects.get(pk=self.kwargs['pk'])
        # IsSameTenant ensures user can only access their tenant's branches
        self.check_object_permissions(self.request, obj)
        return obj
```

### Checking Branch Access

```python
from apps.core.permissions import IsSameBranch

class InventoryDetailView(APIView):
    permission_classes = [IsSameBranch]
    
    def get_object(self):
        obj = InventoryItem.objects.get(pk=self.kwargs['pk'])
        # IsSameBranch ensures user can only access their assigned branch's items
        self.check_object_permissions(self.request, obj)
        return obj
```

### Using django-guardian

```python
from guardian.shortcuts import assign_perm, get_objects_for_user

# Assign object-level permission
assign_perm('view_branch', user, branch)

# Check object-level permission
if user.has_perm('core.view_branch', branch):
    # User has permission for this specific branch
    pass

# Get all objects user has permission for
branches = get_objects_for_user(user, 'core.view_branch', Branch)
```

## Using Mixins

### Role-Based Mixin

```python
from apps.core.permissions import RoleRequiredMixin

class OwnerOnlyView(RoleRequiredMixin, APIView):
    required_roles = ['TENANT_OWNER']
    
    def get(self, request):
        # Only tenant owners can access
        pass
```

### Tenant Filter Mixin

```python
from apps.core.permissions import TenantFilterMixin
from rest_framework.generics import ListAPIView

class BranchListView(TenantFilterMixin, ListAPIView):
    queryset = Branch.objects.all()
    # Automatically filters to show only user's tenant branches
    # Platform admins see all branches
```

### Guardian Permission Mixin

```python
from apps.core.permissions import GuardianPermissionMixin
from rest_framework.generics import ListAPIView

class BranchListView(GuardianPermissionMixin, ListAPIView):
    queryset = Branch.objects.all()
    guardian_permission = 'view_branch'
    # Only shows branches user has explicit permission for
```

### Branch Filter Mixin

```python
from apps.core.permissions import BranchFilterMixin
from rest_framework.generics import ListAPIView

class InventoryListView(BranchFilterMixin, ListAPIView):
    queryset = InventoryItem.objects.all()
    # Automatically filters to show only user's assigned branch items
    # Tenant owners and platform admins see all branches
```

## Utility Functions

```python
from apps.core.permissions import check_role_permission, check_tenant_access, check_branch_access

# Check if user has specific role
if check_role_permission(request.user, 'TENANT_OWNER', 'TENANT_MANAGER'):
    # User is owner or manager
    pass

# Check if user can access an object based on tenant
if check_tenant_access(request.user, inventory_item):
    # User can access this item
    pass

# Check if user can access an object based on branch assignment
if check_branch_access(request.user, inventory_item):
    # User can access this item from their branch
    pass
```

## Audit Logging

All permission changes are automatically logged for compliance and security auditing per Requirement 18.9.

### Logging Permission Changes

```python
from apps.core.audit import (
    log_role_change,
    log_permission_grant,
    log_permission_revoke,
    log_group_assignment,
    log_branch_assignment,
)

# Log role change
log_role_change(
    actor=request.user,
    target_user=employee,
    old_role='TENANT_EMPLOYEE',
    new_role='TENANT_MANAGER',
    request=request  # Optional, captures IP and user agent
)

# Log permission grant
log_permission_grant(
    actor=request.user,
    target_user=employee,
    permission='view_inventory',
    obj=inventory_item,  # Optional
    request=request
)

# Log permission revocation
log_permission_revoke(
    actor=request.user,
    target_user=employee,
    permission='delete_inventory',
    request=request
)

# Log group assignment
log_group_assignment(
    actor=request.user,
    target_user=employee,
    group=managers_group,
    added=True,  # False for removal
    request=request
)

# Log branch assignment
log_branch_assignment(
    actor=request.user,
    target_user=employee,
    branch=main_branch,
    assigned=True,  # False for unassignment
    request=request
)
```

### Viewing Audit Logs

```python
from apps.core.models import PermissionAuditLog

# Get all permission changes for a user
logs = PermissionAuditLog.objects.filter(target_user=user)

# Get recent role changes
role_changes = PermissionAuditLog.objects.filter(
    action=PermissionAuditLog.ROLE_CHANGED
).order_by('-timestamp')[:10]

# Get all actions performed by an admin
admin_actions = PermissionAuditLog.objects.filter(actor=admin_user)
```

## Model Methods

The User model includes convenience methods:

```python
user = request.user

# Check roles
user.is_platform_admin()
user.is_tenant_owner()
user.is_tenant_manager()
user.is_tenant_employee()

# Check capabilities
user.has_tenant_access()
user.can_manage_users()
user.can_manage_inventory()
user.can_process_sales()
user.requires_mfa()  # True for platform admins
```

## Testing

Run permission tests:

```bash
docker compose exec web pytest tests/test_permissions.py -v
```

## Best Practices

1. **Use the most specific permission check** - Prefer `CanManageInventory` over generic role checks
2. **Combine permissions when needed** - Use multiple permission classes for complex requirements
3. **Always check object-level permissions** - Use `IsSameTenant` for tenant-scoped objects
4. **Platform admins bypass tenant checks** - They can access all tenants' data
5. **Test permissions thoroughly** - Write tests for all permission scenarios

## Configuration

Guardian is configured in `config/settings.py`:

```python
INSTALLED_APPS = [
    ...
    'guardian',
    ...
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
    'guardian.backends.ObjectPermissionBackend',
]

ANONYMOUS_USER_NAME = None
GUARDIAN_RAISE_403 = True
```

## Migration Notes

When adding new models that need tenant isolation:

1. Add a `tenant` ForeignKey to the model
2. Use `IsSameTenant` permission class in views
3. Use `TenantFilterMixin` for list views
4. Add appropriate tests

## Related Requirements

This implementation satisfies **Requirement 18**: User Management and Permissions from the requirements document:

- ✅ 18.1: Allow shop owners to create, edit, and deactivate staff user accounts
- ✅ 18.2: Support role-based access control with predefined roles (Owner, Manager, Salesperson, Cashier)
- ✅ 18.3: Allow custom permission assignment for granular access control (via django-guardian)
- ✅ 18.4: Assign users to specific branches with location-based restrictions (IsSameBranch, BranchFilterMixin)
- ✅ 18.5: Track user activity including login times and actions performed (handled by other modules)
- ✅ 18.6: Enforce password complexity requirements (already implemented)
- ✅ 18.7: Support multi-factor authentication (already implemented)
- ✅ 18.8: Allow users to configure language and theme preferences (already implemented)
- ✅ 18.9: Log all permission changes for audit purposes (PermissionAuditLog model)
