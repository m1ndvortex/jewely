"""
Custom decorators for authentication and authorization.

This module provides decorators and mixins for enforcing role-based
and object-level permissions throughout the application.
"""

from functools import wraps

from django.http import JsonResponse

from rest_framework import status


def mfa_required(view_func):
    """
    Decorator to enforce MFA for platform administrators.

    Per Requirement 25.7: "THE System SHALL require multi-factor authentication for admin users"

    This decorator checks if the user is a platform admin and has MFA enabled.
    If not, it returns a 403 Forbidden response.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user

        # Check if user is authenticated
        if not user or not user.is_authenticated:
            return JsonResponse(
                {"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED
            )

        # Check if user is platform admin and requires MFA
        if hasattr(user, "requires_mfa") and user.requires_mfa():
            if not user.is_mfa_enabled:
                return JsonResponse(
                    {
                        "error": "Multi-factor authentication is required for platform administrators.",
                        "mfa_required": True,
                        "message": "Please enable MFA on your account to access this resource.",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        return view_func(request, *args, **kwargs)

    return wrapper


def mfa_required_for_class_view(method):
    """
    Decorator to enforce MFA for class-based views.

    Usage:
        class MyView(APIView):
            @mfa_required_for_class_view
            def post(self, request):
                ...
    """

    @wraps(method)
    def wrapper(self, request, *args, **kwargs):
        user = request.user

        # Check if user is authenticated
        if not user or not user.is_authenticated:
            from rest_framework.response import Response

            return Response(
                {"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED
            )

        # Check if user is platform admin and requires MFA
        if hasattr(user, "requires_mfa") and user.requires_mfa():
            if not user.is_mfa_enabled:
                from rest_framework.response import Response

                return Response(
                    {
                        "error": "Multi-factor authentication is required for platform administrators.",
                        "mfa_required": True,
                        "message": "Please enable MFA on your account to access this resource.",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        return method(self, request, *args, **kwargs)

    return wrapper


# Role-based permission decorators


def role_required(*allowed_roles):
    """
    Decorator to enforce role-based access control.

    Usage:
        @role_required('PLATFORM_ADMIN', 'TENANT_OWNER')
        def my_view(request):
            ...

    Args:
        *allowed_roles: Variable number of role strings that are allowed to access the view

    Returns:
        Decorated function that checks user role before executing
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user

            # Check if user is authenticated
            if not user or not user.is_authenticated:
                return JsonResponse(
                    {"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED
                )

            # Check if user has one of the allowed roles
            if not hasattr(user, "role") or user.role not in allowed_roles:
                return JsonResponse(
                    {
                        "error": "Permission denied.",
                        "detail": f"This action requires one of the following roles: {', '.join(allowed_roles)}",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def platform_admin_required(view_func):
    """
    Decorator to restrict access to platform administrators only.

    Usage:
        @platform_admin_required
        def admin_view(request):
            ...
    """
    return role_required("PLATFORM_ADMIN")(view_func)


def tenant_owner_required(view_func):
    """
    Decorator to restrict access to tenant owners only.

    Usage:
        @tenant_owner_required
        def owner_view(request):
            ...
    """
    return role_required("TENANT_OWNER")(view_func)


def tenant_manager_or_owner_required(view_func):
    """
    Decorator to restrict access to tenant managers and owners.

    Usage:
        @tenant_manager_or_owner_required
        def management_view(request):
            ...
    """
    return role_required("TENANT_OWNER", "TENANT_MANAGER")(view_func)


def tenant_access_required(view_func):
    """
    Decorator to ensure user has access to tenant features.

    Usage:
        @tenant_access_required
        def tenant_view(request):
            ...
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user

        # Check if user is authenticated
        if not user or not user.is_authenticated:
            return JsonResponse(
                {"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED
            )

        # Check if user has tenant access
        if not hasattr(user, "has_tenant_access") or not user.has_tenant_access():
            return JsonResponse(
                {
                    "error": "Permission denied.",
                    "detail": "This action requires tenant access.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return view_func(request, *args, **kwargs)

    return wrapper


# Class-based view decorators


def role_required_for_class_view(*allowed_roles):
    """
    Decorator to enforce role-based access control for class-based views.

    Usage:
        class MyView(APIView):
            @role_required_for_class_view('PLATFORM_ADMIN', 'TENANT_OWNER')
            def post(self, request):
                ...
    """

    def decorator(method):
        @wraps(method)
        def wrapper(self, request, *args, **kwargs):
            user = request.user

            # Check if user is authenticated
            if not user or not user.is_authenticated:
                from rest_framework.response import Response

                return Response(
                    {"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED
                )

            # Check if user has one of the allowed roles
            if not hasattr(user, "role") or user.role not in allowed_roles:
                from rest_framework.response import Response

                return Response(
                    {
                        "error": "Permission denied.",
                        "detail": f"This action requires one of the following roles: {', '.join(allowed_roles)}",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            return method(self, request, *args, **kwargs)

        return wrapper

    return decorator


def platform_admin_required_for_class_view(method):
    """
    Decorator to restrict class-based view methods to platform administrators.

    Usage:
        class AdminView(APIView):
            @platform_admin_required_for_class_view
            def post(self, request):
                ...
    """
    return role_required_for_class_view("PLATFORM_ADMIN")(method)


def tenant_owner_required_for_class_view(method):
    """
    Decorator to restrict class-based view methods to tenant owners.

    Usage:
        class OwnerView(APIView):
            @tenant_owner_required_for_class_view
            def post(self, request):
                ...
    """
    return role_required_for_class_view("TENANT_OWNER")(method)


def tenant_manager_or_owner_required_for_class_view(method):
    """
    Decorator to restrict class-based view methods to tenant managers and owners.

    Usage:
        class ManagementView(APIView):
            @tenant_manager_or_owner_required_for_class_view
            def post(self, request):
                ...
    """
    return role_required_for_class_view("TENANT_OWNER", "TENANT_MANAGER")(method)
