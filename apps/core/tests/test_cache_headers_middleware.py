"""
Tests for Cache Headers Middleware (Task 28.3)
"""

import pytest
from django.test import RequestFactory, TestCase
from django.http import HttpResponse

from apps.core.cache_headers_middleware import CacheHeadersMiddleware


class TestCacheHeadersMiddleware(TestCase):
    """Test cache headers middleware functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()
        self.get_response = lambda request: HttpResponse("Test response")
        self.middleware = CacheHeadersMiddleware(self.get_response)
    
    def test_static_asset_caching(self):
        """Test that static assets get long cache times"""
        request = self.factory.get("/static/css/theme.css")
        response = self.middleware(request)
        
        # Check Cache-Control header
        self.assertIn("Cache-Control", response)
        cache_control = response["Cache-Control"]
        self.assertIn("public", cache_control)
        self.assertIn("max-age=31536000", cache_control)  # 1 year
        self.assertIn("immutable", cache_control)
        
        # Check Vary header
        self.assertIn("Vary", response)
        self.assertIn("Accept-Encoding", response["Vary"])
    
    def test_media_file_caching(self):
        """Test that media files get medium cache times"""
        request = self.factory.get("/media/uploads/image.jpg")
        response = self.middleware(request)
        
        # Check Cache-Control header
        self.assertIn("Cache-Control", response)
        cache_control = response["Cache-Control"]
        self.assertIn("public", cache_control)
        self.assertIn("max-age=604800", cache_control)  # 1 week
    
    def test_html_page_caching(self):
        """Test that HTML pages get short cache times"""
        request = self.factory.get("/dashboard/")
        response = HttpResponse("HTML content", content_type="text/html")
        
        # Manually call middleware
        middleware = CacheHeadersMiddleware(lambda r: response)
        response = middleware(request)
        
        # Check Cache-Control header
        self.assertIn("Cache-Control", response)
        cache_control = response["Cache-Control"]
        self.assertIn("private", cache_control)
        self.assertIn("max-age=300", cache_control)  # 5 minutes
        self.assertIn("must-revalidate", cache_control)
        
        # Check Vary header
        self.assertIn("Vary", response)
        self.assertIn("Accept-Language", response["Vary"])
        self.assertIn("Cookie", response["Vary"])
    
    def test_api_endpoint_no_cache(self):
        """Test that API endpoints don't get cached"""
        request = self.factory.get("/api/inventory/")
        response = self.middleware(request)
        
        # Check Cache-Control header
        self.assertIn("Cache-Control", response)
        cache_control = response["Cache-Control"]
        self.assertIn("private", cache_control)
        self.assertIn("no-cache", cache_control)
        self.assertIn("no-store", cache_control)
        self.assertIn("must-revalidate", cache_control)
    
    def test_existing_cache_control_preserved(self):
        """Test that existing Cache-Control headers are preserved"""
        request = self.factory.get("/custom/")
        response = HttpResponse("Custom response")
        response["Cache-Control"] = "public, max-age=3600"
        
        # Manually call middleware
        middleware = CacheHeadersMiddleware(lambda r: response)
        response = middleware(request)
        
        # Original Cache-Control should be preserved
        self.assertEqual(response["Cache-Control"], "public, max-age=3600")
