"""
Cache Headers Middleware for Frontend Asset Optimization (Task 28.3)

This middleware sets appropriate cache headers for static assets and HTML pages
to improve performance and reduce server load.
"""

from django.utils.cache import patch_cache_control, patch_vary_headers


class CacheHeadersMiddleware:
    """
    Middleware to set cache headers for different types of responses.
    
    - Static assets (CSS, JS, images): Long cache times with immutable flag
    - HTML pages: Short cache times with revalidation
    - API responses: No cache or short cache depending on endpoint
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Get the request path
        path = request.path
        
        # Set cache headers based on content type and path
        if self._is_static_asset(path, response):
            # Static assets: Cache for 1 year (immutable)
            patch_cache_control(
                response,
                public=True,
                max_age=31536000,  # 1 year
                immutable=True,
            )
            # Add Vary header for proper caching
            patch_vary_headers(response, ["Accept-Encoding"])
            
        elif self._is_media_file(path):
            # Media files: Cache for 1 week
            patch_cache_control(
                response,
                public=True,
                max_age=604800,  # 1 week
            )
            patch_vary_headers(response, ["Accept-Encoding"])
            
        elif self._is_api_endpoint(path):
            # API endpoints: No cache by default (can be overridden per view)
            if not response.has_header("Cache-Control"):
                patch_cache_control(
                    response,
                    private=True,
                    no_cache=True,
                    no_store=True,
                    must_revalidate=True,
                )
                
        elif response.get("Content-Type", "").startswith("text/html"):
            # HTML pages: Short cache with revalidation
            if not response.has_header("Cache-Control"):
                patch_cache_control(
                    response,
                    private=True,
                    max_age=300,  # 5 minutes
                    must_revalidate=True,
                )
                # Vary on Accept-Language for i18n support
                patch_vary_headers(response, ["Accept-Language", "Cookie"])
        
        return response
    
    def _is_static_asset(self, path, response):
        """Check if the response is a static asset (CSS, JS, fonts, etc.)"""
        # Check path
        if path.startswith("/static/") or path.startswith("/staticfiles/"):
            return True
        
        # Check content type
        content_type = response.get("Content-Type", "")
        static_types = [
            "text/css",
            "application/javascript",
            "application/x-javascript",
            "text/javascript",
            "font/",
            "application/font",
        ]
        return any(content_type.startswith(t) for t in static_types)
    
    def _is_media_file(self, path):
        """Check if the path is a media file"""
        return path.startswith("/media/")
    
    def _is_api_endpoint(self, path):
        """Check if the path is an API endpoint"""
        return path.startswith("/api/")
