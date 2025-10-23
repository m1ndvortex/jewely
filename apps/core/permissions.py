"""
Permission mixins and classes for tenant-based access control.
"""

from django.core.exceptions import PermissionDenied

from rest_framework import permissions


class HasTenantAccess(permissions.BasePermission):
    """
    Permission class to ensure users can only access resources from their own tenant.
    """

    def has_permission(self, request, view):
        # Check if user is authenticated and has a tenant
        return request.user.is_authenticated and request.user.tenant is not None

    def has_object_permission(self, request, view, obj):
        # Check if the object belongs to the user's tenant
        if hasattr(obj, "tenant"):
            return obj.tenant == request.user.tenant
        return True


class TenantPermissionMixin:
    """
    Mixin to ensure users can only access resources from their own tenant.
    """

    def dispatch(self, request, *args, **kwargs):
        # Check if user has a tenant (not platform admin)
        if not request.user.tenant:
            raise PermissionDenied("Access denied. User must belong to a tenant.")

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        """Override to filter by tenant."""
        queryset = super().get_queryset()
        if hasattr(queryset.model, "tenant"):
            return queryset.filter(tenant=self.request.user.tenant)
        return queryset


class TenantOwnerPermissionMixin(TenantPermissionMixin):
    """
    Mixin to ensure only tenant owners can access certain resources.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_tenant_owner():
            raise PermissionDenied("Access denied. Only tenant owners can perform this action.")

        return super().dispatch(request, *args, **kwargs)


class TenantManagerPermissionMixin(TenantPermissionMixin):
    """
    Mixin to ensure only tenant owners and managers can access certain resources.
    """

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_tenant_owner() or request.user.is_tenant_manager()):
            raise PermissionDenied(
                "Access denied. Only tenant owners and managers can perform this action."
            )

        return super().dispatch(request, *args, **kwargs)
