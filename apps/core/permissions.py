"""
Permission classes and mixins for role-based and object-level access control.

This module provides Django REST Framework permission classes and mixins
for enforcing role-based permissions and object-level permissions using django-guardian.
"""

from django.core.exceptions import PermissionDenied

from guardian.shortcuts import get_objects_for_user
from rest_framework import permissions

# Role-based permission classes


class IsPlatformAdmin(permissions.BasePermission):
    """
    Permission class that allows access only to platform administrators.

    Usage:
        class MyView(APIView):
            permission_classes = [IsPlatformAdmin]
    """

    message = "Only platform administrators can perform this action."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, "is_platform_admin")
            and request.user.is_platform_admin()
        )


class IsTenantOwner(permissions.BasePermission):
    """
    Permission class that allows access only to tenant owners.

    Usage:
        class MyView(APIView):
            permission_classes = [IsTenantOwner]
    """

    message = "Only tenant owners can perform this action."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, "is_tenant_owner")
            and request.user.is_tenant_owner()
        )


class IsTenantManager(permissions.BasePermission):
    """
    Permission class that allows access only to tenant managers.

    Usage:
        class MyView(APIView):
            permission_classes = [IsTenantManager]
    """

    message = "Only tenant managers can perform this action."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, "is_tenant_manager")
            and request.user.is_tenant_manager()
        )


class IsTenantManagerOrOwner(permissions.BasePermission):
    """
    Permission class that allows access to tenant managers and owners.

    Usage:
        class MyView(APIView):
            permission_classes = [IsTenantManagerOrOwner]
    """

    message = "Only tenant managers or owners can perform this action."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, "role")
            and request.user.role
            in [
                request.user.TENANT_OWNER,
                request.user.TENANT_MANAGER,
            ]
        )


class HasTenantAccess(permissions.BasePermission):
    """
    Permission class that ensures user has access to tenant features.

    Usage:
        class MyView(APIView):
            permission_classes = [HasTenantAccess]
    """

    message = "This action requires tenant access."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, "has_tenant_access")
            and request.user.has_tenant_access()
        )


class CanManageUsers(permissions.BasePermission):
    """
    Permission class for user management operations.

    Allows platform admins, tenant owners, and tenant managers.

    Usage:
        class UserManagementView(APIView):
            permission_classes = [CanManageUsers]
    """

    message = "You do not have permission to manage users."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, "can_manage_users")
            and request.user.can_manage_users()
        )


class CanManageInventory(permissions.BasePermission):
    """
    Permission class for inventory management operations.

    Allows tenant owners and tenant managers.

    Usage:
        class InventoryView(APIView):
            permission_classes = [CanManageInventory]
    """

    message = "You do not have permission to manage inventory."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, "can_manage_inventory")
            and request.user.can_manage_inventory()
        )


class CanProcessSales(permissions.BasePermission):
    """
    Permission class for sales processing operations.

    Allows all tenant users (owners, managers, employees).

    Usage:
        class SalesView(APIView):
            permission_classes = [CanProcessSales]
    """

    message = "You do not have permission to process sales."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, "can_process_sales")
            and request.user.can_process_sales()
        )


# Object-level permission classes


class IsSameTenant(permissions.BasePermission):
    """
    Object-level permission to only allow users to access objects from their own tenant.

    The object must have a 'tenant' attribute.

    Usage:
        class MyView(APIView):
            permission_classes = [IsSameTenant]
    """

    message = "You can only access objects from your own tenant."

    def has_object_permission(self, request, view, obj):
        # Platform admins can access all objects
        if hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin():
            return True

        # Check if object has tenant attribute
        if not hasattr(obj, "tenant"):
            return False

        # Check if user's tenant matches object's tenant
        return (
            request.user.tenant is not None
            and obj.tenant is not None
            and request.user.tenant.id == obj.tenant.id
        )


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object to edit it.
    Read-only access is allowed for all authenticated users.

    The object must have an 'owner' or 'user' attribute.

    Usage:
        class MyView(APIView):
            permission_classes = [IsOwnerOrReadOnly]
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed for any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return True

        # Platform admins can edit all objects
        if hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin():
            return True

        # Write permissions are only allowed to the owner
        owner = getattr(obj, "owner", None) or getattr(obj, "user", None)
        return owner == request.user


# Mixins for views


class RoleRequiredMixin:
    """
    Mixin to enforce role-based access control in class-based views.

    Usage:
        class MyView(RoleRequiredMixin, APIView):
            required_roles = ['PLATFORM_ADMIN', 'TENANT_OWNER']
    """

    required_roles = []

    def check_permissions(self, request):
        """Override to add role checking."""
        super().check_permissions(request)

        if not self.required_roles:
            return

        user = request.user
        if not user or not user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        if not hasattr(user, "role") or user.role not in self.required_roles:
            raise PermissionDenied(
                f"This action requires one of the following roles: {', '.join(self.required_roles)}"
            )


class TenantFilterMixin:
    """
    Mixin to automatically filter querysets by the user's tenant.

    Usage:
        class MyView(TenantFilterMixin, ListAPIView):
            queryset = MyModel.objects.all()
    """

    def get_queryset(self):
        """Filter queryset by user's tenant."""
        queryset = super().get_queryset()

        # Platform admins see all objects
        if (
            hasattr(self.request.user, "is_platform_admin")
            and self.request.user.is_platform_admin()
        ):
            return queryset

        # Tenant users see only their tenant's objects
        if hasattr(self.request.user, "tenant") and self.request.user.tenant:
            # Check if queryset model has tenant field
            if hasattr(queryset.model, "tenant"):
                return queryset.filter(tenant=self.request.user.tenant)

        return queryset


class GuardianPermissionMixin:
    """
    Mixin to integrate django-guardian object-level permissions.

    Usage:
        class MyView(GuardianPermissionMixin, ListAPIView):
            queryset = MyModel.objects.all()
            guardian_permission = 'view_mymodel'
    """

    guardian_permission = None

    def get_queryset(self):
        """Filter queryset by object-level permissions."""
        queryset = super().get_queryset()

        # Platform admins see all objects
        if (
            hasattr(self.request.user, "is_platform_admin")
            and self.request.user.is_platform_admin()
        ):
            return queryset

        # Filter by guardian permissions if specified
        if self.guardian_permission:
            return get_objects_for_user(
                self.request.user,
                self.guardian_permission,
                queryset,
                accept_global_perms=False,
            )

        return queryset


# Utility functions


def check_role_permission(user, *allowed_roles):
    """
    Check if user has one of the allowed roles.

    Args:
        user: User instance
        *allowed_roles: Variable number of role strings

    Returns:
        bool: True if user has one of the allowed roles

    Usage:
        if check_role_permission(request.user, 'PLATFORM_ADMIN', 'TENANT_OWNER'):
            # Allow action
    """
    if not user or not user.is_authenticated:
        return False

    if not hasattr(user, "role"):
        return False

    return user.role in allowed_roles


def check_tenant_access(user, obj):
    """
    Check if user has access to an object based on tenant.

    Args:
        user: User instance
        obj: Object to check access for (must have 'tenant' attribute)

    Returns:
        bool: True if user can access the object

    Usage:
        if check_tenant_access(request.user, inventory_item):
            # Allow access
    """
    # Platform admins can access all objects
    if hasattr(user, "is_platform_admin") and user.is_platform_admin():
        return True

    # Check if object has tenant attribute
    if not hasattr(obj, "tenant"):
        return False

    # Check if user's tenant matches object's tenant
    return user.tenant is not None and obj.tenant is not None and user.tenant.id == obj.tenant.id


class IsSameBranch(permissions.BasePermission):
    """
    Object-level permission to only allow users to access objects from their assigned branch.

    The object must have a 'branch' attribute.
    Platform admins and users without branch assignment can access all branches.

    Usage:
        class MyView(APIView):
            permission_classes = [IsSameBranch]
    """

    message = "You can only access objects from your assigned branch."

    def has_object_permission(self, request, view, obj):
        # Platform admins can access all objects
        if hasattr(request.user, "is_platform_admin") and request.user.is_platform_admin():
            return True

        # Tenant owners can access all branches in their tenant
        if hasattr(request.user, "is_tenant_owner") and request.user.is_tenant_owner():
            return True

        # Check if object has branch attribute
        if not hasattr(obj, "branch"):
            return False

        # Users without branch assignment can access all branches in their tenant
        if not request.user.branch:
            return True

        # Check if user's branch matches object's branch
        return (
            request.user.branch is not None
            and obj.branch is not None
            and request.user.branch.id == obj.branch.id
        )


class BranchFilterMixin:
    """
    Mixin to automatically filter querysets by the user's assigned branch.

    Usage:
        class MyView(BranchFilterMixin, ListAPIView):
            queryset = MyModel.objects.all()
    """

    def get_queryset(self):
        """Filter queryset by user's branch."""
        queryset = super().get_queryset()

        # Platform admins see all objects
        if (
            hasattr(self.request.user, "is_platform_admin")
            and self.request.user.is_platform_admin()
        ):
            return queryset

        # Tenant owners see all objects in their tenant
        if hasattr(self.request.user, "is_tenant_owner") and self.request.user.is_tenant_owner():
            return queryset

        # Users with branch assignment see only their branch's objects
        if hasattr(self.request.user, "branch") and self.request.user.branch:
            # Check if queryset model has branch field
            if hasattr(queryset.model, "branch"):
                return queryset.filter(branch=self.request.user.branch)

        return queryset


def check_branch_access(user, obj):
    """
    Check if user has access to an object based on branch assignment.

    Args:
        user: User instance
        obj: Object to check access for (must have 'branch' attribute)

    Returns:
        bool: True if user can access the object

    Usage:
        if check_branch_access(request.user, inventory_item):
            # Allow access
    """
    # Platform admins can access all objects
    if hasattr(user, "is_platform_admin") and user.is_platform_admin():
        return True

    # Tenant owners can access all branches in their tenant
    if hasattr(user, "is_tenant_owner") and user.is_tenant_owner():
        return True

    # Check if object has branch attribute
    if not hasattr(obj, "branch"):
        return False

    # Users without branch assignment can access all branches in their tenant
    if not user.branch:
        return True

    # Check if user's branch matches object's branch
    return user.branch is not None and obj.branch is not None and user.branch.id == obj.branch.id
