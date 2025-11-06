"""
Example API views demonstrating pagination, compression, and throttling.

This module provides examples of how to use the API optimization utilities
implemented in Task 28.4.

Per Requirement 26 - Performance Optimization and Scaling
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.core.pagination import paginate_queryset
from apps.core.throttling import (
    api_ratelimit,
    api_ratelimit_lenient,
    api_ratelimit_standard,
    api_ratelimit_strict,
    api_ratelimit_tenant,
    api_ratelimit_user,
    api_ratelimit_write,
)

User = get_user_model()


# Example 1: Simple paginated list endpoint with rate limiting
@require_http_methods(["GET"])
@login_required
@api_ratelimit_lenient  # 500 requests per hour for read operations
def list_users_api(request):
    """
    List users with pagination and rate limiting.

    Query Parameters:
        - page: Page number (default: 1)
        - per_page: Items per page (default: 20, max: 100)

    Response:
        {
            "results": [
                {"id": 1, "username": "user1", "email": "user1@example.com"},
                ...
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
    """
    # Get queryset filtered by tenant
    queryset = User.objects.filter(tenant=request.user.tenant).order_by("id")

    # Serialize function
    def serialize_user(user):
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
        }

    # Paginate and return
    data = paginate_queryset(
        request, queryset, per_page=20, max_per_page=100, serializer_func=serialize_user
    )

    return JsonResponse(data)


# Example 2: Tenant-based rate limiting for multi-tenant isolation
@require_http_methods(["GET"])
@login_required
@api_ratelimit_tenant(rate="1000/h")  # 1000 requests per hour per tenant
def tenant_stats_api(request):
    """
    Get tenant statistics with tenant-based rate limiting.

    This ensures fair resource usage across all tenants.
    """
    tenant = request.user.tenant

    stats = {
        "tenant_id": str(tenant.id),
        "company_name": tenant.company_name,
        "total_users": User.objects.filter(tenant=tenant).count(),
        "active_users": User.objects.filter(tenant=tenant, is_active=True).count(),
    }

    return JsonResponse({"success": True, "data": stats})


# Example 3: User-based rate limiting for write operations
@require_http_methods(["POST"])
@login_required
@api_ratelimit_user(rate="50/h")  # 50 requests per hour per user
def create_resource_api(request):
    """
    Create a resource with user-based rate limiting.

    Write operations typically have stricter rate limits.
    """
    # Parse request data
    try:
        data = request.POST
        name = data.get("name")

        if not name:
            return JsonResponse({"success": False, "error": "Name is required"}, status=400)

        # Create resource logic here
        # ...

        return JsonResponse(
            {"success": True, "message": "Resource created", "data": {"name": name}}
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


# Example 4: Standard rate limiting for general API endpoints
@require_http_methods(["GET"])
@login_required
@api_ratelimit_standard  # 100 requests per hour
def general_api_endpoint(request):
    """
    General API endpoint with standard rate limiting.
    """
    return JsonResponse({"success": True, "message": "This is a general API endpoint"})


# Example 5: Combining pagination with custom serialization
@require_http_methods(["GET"])
@login_required
@api_ratelimit_tenant(rate="500/h")
def list_users_detailed_api(request):
    """
    List users with detailed information, pagination, and rate limiting.

    Demonstrates custom serialization with related data.
    """
    queryset = (
        User.objects.filter(tenant=request.user.tenant)
        .select_related("branch")
        .order_by("-date_joined")
    )

    def serialize_user_detailed(user):
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.get_full_name(),
            "role": user.role,
            "branch": {"id": user.branch.id, "name": user.branch.name} if user.branch else None,
            "is_active": user.is_active,
            "date_joined": user.date_joined.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
        }

    data = paginate_queryset(
        request, queryset, per_page=25, max_per_page=100, serializer_func=serialize_user_detailed
    )

    return JsonResponse(data)


# Example 6: Search endpoint with pagination
@require_http_methods(["GET"])
@login_required
@api_ratelimit_standard
def search_users_api(request):
    """
    Search users with pagination.

    Query Parameters:
        - q: Search query
        - page: Page number
        - per_page: Items per page
    """
    search_query = request.GET.get("q", "").strip()

    if not search_query:
        return JsonResponse({"success": False, "error": "Search query is required"}, status=400)

    # Search in username, email, first_name, last_name
    queryset = (
        User.objects.filter(tenant=request.user.tenant)
        .filter(
            Q(username__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
        )
        .order_by("username")
    )

    def serialize_user(user):
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.get_full_name(),
        }

    data = paginate_queryset(request, queryset, per_page=20, serializer_func=serialize_user)

    # Add search query to response
    data["search_query"] = search_query

    return JsonResponse(data)


# Example 7: Strict rate limiting for expensive operations
@require_http_methods(["POST"])
@login_required
@api_ratelimit_strict  # 10 requests per minute
def expensive_operation_api(request):
    """
    Expensive operation with strict rate limiting.

    Use strict rate limits for operations that are:
    - Computationally expensive
    - Generate large reports
    - Trigger background jobs
    - Access external APIs
    """
    # Simulate expensive operation
    # ...

    return JsonResponse(
        {
            "success": True,
            "message": "Expensive operation queued",
            "note": "This endpoint is strictly rate limited to 10 requests per minute",
        }
    )


# Example 8: Write operation with specific rate limit
@require_http_methods(["POST", "PUT", "PATCH"])
@login_required
@api_ratelimit_write  # 50 requests per hour for write operations
def update_resource_api(request, resource_id):
    """
    Update a resource with write operation rate limiting.
    """
    try:
        # Update logic here
        # ...

        return JsonResponse(
            {
                "success": True,
                "message": f"Resource {resource_id} updated",
                "resource_id": resource_id,
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


# Example 9: Public API endpoint with IP-based rate limiting
@require_http_methods(["GET"])
@api_ratelimit(key="ip", rate="20/h")  # 20 requests per hour per IP
def public_api_endpoint(request):
    """
    Public API endpoint with IP-based rate limiting.

    No authentication required, but rate limited by IP address.
    """
    return JsonResponse(
        {
            "success": True,
            "message": "This is a public API endpoint",
            "note": "Rate limited to 20 requests per hour per IP address",
        }
    )


# Example 10: Combining multiple optimizations
@require_http_methods(["GET"])
@login_required
@api_ratelimit_tenant(rate="1000/h")
def optimized_list_api(request):
    """
    Fully optimized list endpoint demonstrating all optimizations:
    - Pagination for large datasets
    - GZip compression (automatic via middleware)
    - Rate limiting by tenant
    - Efficient database queries with select_related
    """
    # Efficient query with select_related to prevent N+1
    queryset = (
        User.objects.filter(tenant=request.user.tenant)
        .select_related("branch", "tenant")
        .only(
            "id", "username", "email", "role", "is_active", "branch__name", "tenant__company_name"
        )
        .order_by("-date_joined")
    )

    def serialize_user(user):
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "branch_name": user.branch.name if user.branch else None,
        }

    # Paginate with reasonable defaults
    data = paginate_queryset(
        request, queryset, per_page=50, max_per_page=200, serializer_func=serialize_user
    )

    # Add metadata
    data["meta"] = {
        "tenant": request.user.tenant.company_name,
        "optimizations": ["pagination", "gzip_compression", "rate_limiting", "query_optimization"],
    }

    # Response will be automatically compressed by GZipMiddleware if large enough
    return JsonResponse(data)
