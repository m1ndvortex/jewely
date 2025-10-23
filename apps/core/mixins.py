"""
Mixins for class-based views.

This module provides mixins for enforcing tenant access and other
common functionality in class-based views.
"""

from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden


class TenantRequiredMixin:
    """
    Mixin to ensure user belongs to a tenant.

    Usage:
        class MyView(TenantRequiredMixin, ListView):
            ...
    """

    def dispatch(self, request, *args, **kwargs):
        """Check if user has a tenant before dispatching."""
        user = request.user

        # Check if user is authenticated (should be handled by LoginRequiredMixin)
        if not user or not user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        # Check if user has a tenant
        if not hasattr(user, "tenant") or not user.tenant:
            return HttpResponseForbidden("Access denied. User must belong to a tenant.")

        return super().dispatch(request, *args, **kwargs)


class RoleRequiredMixin:
    """
    Mixin to enforce role-based access control.

    Usage:
        class MyView(RoleRequiredMixin, ListView):
            allowed_roles = ['TENANT_OWNER', 'TENANT_MANAGER']
    """

    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        """Check if user has required role before dispatching."""
        user = request.user

        # Check if user is authenticated (should be handled by LoginRequiredMixin)
        if not user or not user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        # Check if user has one of the allowed roles
        if self.allowed_roles and (
            not hasattr(user, "role") or user.role not in self.allowed_roles
        ):
            raise PermissionDenied(
                f"This action requires one of the following roles: {', '.join(self.allowed_roles)}"
            )

        return super().dispatch(request, *args, **kwargs)


class PlatformAdminRequiredMixin(RoleRequiredMixin):
    """
    Mixin to restrict access to platform administrators only.

    Usage:
        class AdminView(PlatformAdminRequiredMixin, ListView):
            ...
    """

    allowed_roles = ["PLATFORM_ADMIN"]


class TenantOwnerRequiredMixin(RoleRequiredMixin):
    """
    Mixin to restrict access to tenant owners only.

    Usage:
        class OwnerView(TenantOwnerRequiredMixin, ListView):
            ...
    """

    allowed_roles = ["TENANT_OWNER"]


class TenantManagerOrOwnerRequiredMixin(RoleRequiredMixin):
    """
    Mixin to restrict access to tenant managers and owners.

    Usage:
        class ManagementView(TenantManagerOrOwnerRequiredMixin, ListView):
            ...
    """

    allowed_roles = ["TENANT_OWNER", "TENANT_MANAGER"]


class TenantAccessRequiredMixin(RoleRequiredMixin):
    """
    Mixin to ensure user has access to tenant features.

    Usage:
        class TenantView(TenantAccessRequiredMixin, ListView):
            ...
    """

    allowed_roles = ["TENANT_OWNER", "TENANT_MANAGER", "TENANT_EMPLOYEE"]


class TenantMixin(TenantRequiredMixin, TenantAccessRequiredMixin):
    """
    Combined mixin for tenant-scoped views.

    Ensures user belongs to a tenant and has appropriate role.

    Usage:
        class MyTenantView(TenantMixin, ListView):
            ...
    """

    pass
