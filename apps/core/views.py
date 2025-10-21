from django.http import JsonResponse
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET"])
def health_check(request):
    """
    Health check endpoint for Docker and Kubernetes.
    Returns 200 OK if the application is running.
    """
    return JsonResponse({"status": "healthy", "service": "jewelry-shop-saas"})


@require_http_methods(["GET"])
def home(request):
    """
    Home page view.
    """
    return JsonResponse({"message": "Welcome to Jewelry Shop SaaS Platform", "version": "1.0.0"})
