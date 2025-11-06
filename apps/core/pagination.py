"""
Pagination utilities for API endpoints.

Provides consistent pagination across all list endpoints to improve
performance and user experience.
"""

from typing import Any, Dict, List, Optional

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import QuerySet
from django.http import HttpRequest


class APIPaginator:
    """
    Paginator for API endpoints that returns JSON-friendly data.

    Usage:
        queryset = MyModel.objects.all()
        paginator = APIPaginator(request, queryset, per_page=20)
        return JsonResponse(paginator.get_response_data())
    """

    def __init__(
        self,
        request: HttpRequest,
        queryset: QuerySet,
        per_page: int = 20,
        max_per_page: int = 100,
    ):
        """
        Initialize the paginator.

        Args:
            request: The HTTP request object
            queryset: The queryset to paginate
            per_page: Default number of items per page
            max_per_page: Maximum allowed items per page
        """
        self.request = request
        self.queryset = queryset
        self.per_page = per_page
        self.max_per_page = max_per_page

        # Get page number from request
        self.page_number = self._get_page_number()

        # Get per_page from request, with validation
        self.requested_per_page = self._get_per_page()

        # Create Django paginator
        self.paginator = Paginator(queryset, self.requested_per_page)

        # Get the page
        try:
            self.page = self.paginator.page(self.page_number)
        except PageNotAnInteger:
            self.page = self.paginator.page(1)
        except EmptyPage:
            self.page = self.paginator.page(self.paginator.num_pages)

    def _get_page_number(self) -> int:
        """Get page number from request parameters."""
        try:
            page = int(self.request.GET.get("page", 1))
            return max(1, page)  # Ensure page is at least 1
        except (ValueError, TypeError):
            return 1

    def _get_per_page(self) -> int:
        """Get per_page from request parameters with validation."""
        try:
            per_page = int(self.request.GET.get("per_page", self.per_page))
            # Ensure per_page is within valid range
            return max(1, min(per_page, self.max_per_page))
        except (ValueError, TypeError):
            return self.per_page

    def get_page_data(self) -> List[Any]:
        """Get the items for the current page."""
        return list(self.page.object_list)

    def get_pagination_metadata(self) -> Dict[str, Any]:
        """
        Get pagination metadata.

        Returns:
            Dictionary with pagination information
        """
        return {
            "page": self.page.number,
            "per_page": self.requested_per_page,
            "total_pages": self.paginator.num_pages,
            "total_items": self.paginator.count,
            "has_next": self.page.has_next(),
            "has_previous": self.page.has_previous(),
            "next_page": self.page.next_page_number() if self.page.has_next() else None,
            "previous_page": self.page.previous_page_number() if self.page.has_previous() else None,
        }

    def get_response_data(
        self,
        data: Optional[List[Dict[str, Any]]] = None,
        serializer_func: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Get complete response data with pagination metadata.

        Args:
            data: Pre-serialized data (if None, returns raw queryset items)
            serializer_func: Function to serialize each item (if data is None)

        Returns:
            Dictionary with 'results' and 'pagination' keys
        """
        if data is None:
            items = self.get_page_data()
            if serializer_func:
                data = [serializer_func(item) for item in items]
            else:
                # Return model instances as-is (caller should serialize)
                data = items

        return {
            "results": data,
            "pagination": self.get_pagination_metadata(),
        }


def paginate_queryset(
    request: HttpRequest,
    queryset: QuerySet,
    per_page: int = 20,
    max_per_page: int = 100,
    serializer_func: Optional[callable] = None,
) -> Dict[str, Any]:
    """
    Convenience function to paginate a queryset and return response data.

    Args:
        request: The HTTP request object
        queryset: The queryset to paginate
        per_page: Default number of items per page
        max_per_page: Maximum allowed items per page
        serializer_func: Optional function to serialize each item

    Returns:
        Dictionary with 'results' and 'pagination' keys

    Example:
        def my_api_view(request):
            queryset = MyModel.objects.all()
            data = paginate_queryset(
                request,
                queryset,
                per_page=25,
                serializer_func=lambda obj: {
                    'id': obj.id,
                    'name': obj.name,
                }
            )
            return JsonResponse(data)
    """
    paginator = APIPaginator(request, queryset, per_page, max_per_page)
    return paginator.get_response_data(serializer_func=serializer_func)
