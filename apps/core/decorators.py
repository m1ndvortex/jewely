"""
Custom decorators for authentication and authorization.
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
