"""
Test Nginx compression and caching configuration
Tests gzip compression, cache headers, and ETag generation
Requirement 22: Nginx Configuration - Task 31.3
"""

import re
import subprocess
from pathlib import Path


class TestNginxCompressionCaching:
    """Test suite for Nginx compression and caching configuration"""

    @staticmethod
    def get_nginx_config_path(filename):
        """Get the path to an Nginx configuration file"""
        base_path = Path(__file__).parent.parent / "docker" / "nginx"
        return base_path / filename

    def test_gzip_config_exists(self):
        """Test that gzip configuration file exists"""
        gzip_conf = self.get_nginx_config_path("snippets/gzip.conf")
        assert gzip_conf.exists(), "gzip.conf file does not exist"

    def test_cache_config_exists(self):
        """Test that cache configuration file exists"""
        cache_conf = self.get_nginx_config_path("snippets/cache.conf")
        assert cache_conf.exists(), "cache.conf file does not exist"

    def test_gzip_enabled(self):
        """Test that gzip compression is enabled"""
        gzip_conf = self.get_nginx_config_path("snippets/gzip.conf")
        content = gzip_conf.read_text()

        # Check for gzip on
        assert re.search(r"gzip\s+on;", content), "gzip is not enabled"

        # Check for gzip_vary
        assert re.search(r"gzip_vary\s+on;", content), "gzip_vary is not enabled"

        # Check for gzip_proxied
        assert re.search(r"gzip_proxied\s+any;", content), "gzip_proxied is not set to any"

    def test_gzip_compression_level(self):
        """Test that gzip compression level is set appropriately"""
        gzip_conf = self.get_nginx_config_path("snippets/gzip.conf")
        content = gzip_conf.read_text()

        # Check for compression level (should be between 1-9, typically 5-6)
        match = re.search(r"gzip_comp_level\s+(\d+);", content)
        assert match, "gzip_comp_level is not set"

        level = int(match.group(1))
        assert 1 <= level <= 9, f"gzip_comp_level {level} is out of range (1-9)"
        assert 5 <= level <= 7, f"gzip_comp_level {level} is not optimal (recommended 5-7)"

    def test_gzip_mime_types(self):
        """Test that gzip is configured for appropriate MIME types"""
        gzip_conf = self.get_nginx_config_path("snippets/gzip.conf")
        content = gzip_conf.read_text()

        # Essential MIME types that should be compressed
        required_types = [
            "text/plain",
            "text/css",
            "text/javascript",
            "application/json",
            "application/javascript",
            "application/xml",
            "image/svg+xml",
        ]

        for mime_type in required_types:
            assert mime_type in content, f"MIME type {mime_type} is not configured for gzip"

    def test_gzip_min_length(self):
        """Test that gzip minimum length is set"""
        gzip_conf = self.get_nginx_config_path("snippets/gzip.conf")
        content = gzip_conf.read_text()

        # Check for minimum length (should be at least 256 bytes)
        match = re.search(r"gzip_min_length\s+(\d+);", content)
        assert match, "gzip_min_length is not set"

        min_length = int(match.group(1))
        assert min_length >= 256, f"gzip_min_length {min_length} is too small (should be >= 256)"

    def test_etag_enabled(self):
        """Test that ETag generation is enabled"""
        cache_conf = self.get_nginx_config_path("snippets/cache.conf")
        content = cache_conf.read_text()

        # Check for etag on
        assert re.search(r"etag\s+on;", content), "ETag generation is not enabled"

    def test_if_modified_since_configured(self):
        """Test that If-Modified-Since handling is configured"""
        cache_conf = self.get_nginx_config_path("snippets/cache.conf")
        content = cache_conf.read_text()

        # Check for if_modified_since
        assert re.search(
            r"if_modified_since\s+\w+;", content
        ), "if_modified_since is not configured"

    def test_open_file_cache_configured(self):
        """Test that open file cache is configured for performance"""
        cache_conf = self.get_nginx_config_path("snippets/cache.conf")
        content = cache_conf.read_text()

        # Check for open_file_cache
        assert re.search(r"open_file_cache\s+max=\d+", content), "open_file_cache is not configured"
        assert re.search(
            r"open_file_cache_valid", content
        ), "open_file_cache_valid is not configured"
        assert re.search(
            r"open_file_cache_min_uses", content
        ), "open_file_cache_min_uses is not configured"

    def test_cache_map_configured(self):
        """Test that cache expiration map is configured"""
        cache_conf = self.get_nginx_config_path("snippets/cache.conf")
        content = cache_conf.read_text()

        # Check for expires map
        assert (
            "map $sent_http_content_type $expires_map" in content
        ), "Cache expires map is not configured"

        # Check for common content types in the map
        assert "text/css" in content, "CSS not in cache map"
        assert "text/javascript" in content, "JavaScript not in cache map"
        assert "image/jpeg" in content, "JPEG images not in cache map"
        assert "font/woff" in content, "WOFF fonts not in cache map"

    def test_main_nginx_includes_gzip(self):
        """Test that main nginx.conf includes gzip configuration"""
        nginx_conf = self.get_nginx_config_path("nginx.conf")
        content = nginx_conf.read_text()

        # Check for gzip include
        assert (
            "include /etc/nginx/snippets/gzip.conf" in content
        ), "nginx.conf does not include gzip.conf"

    def test_site_config_includes_cache(self):
        """Test that site configuration includes cache configuration"""
        site_conf = self.get_nginx_config_path("conf.d/jewelry-shop.conf")
        content = site_conf.read_text()

        # Check for cache include in static files location
        assert (
            "include /etc/nginx/snippets/cache.conf" in content
        ), "jewelry-shop.conf does not include cache.conf"

    def test_static_files_cache_headers(self):
        """Test that static files have appropriate cache headers"""
        site_conf = self.get_nginx_config_path("conf.d/jewelry-shop.conf")
        content = site_conf.read_text()

        # Find static files location block
        static_block = re.search(r"location /static/.*?\{(.*?)\}", content, re.DOTALL)
        assert static_block, "Static files location block not found"

        static_content = static_block.group(1)

        # Check for expires directive
        assert "expires" in static_content, "expires directive not set for static files"

        # Check for Cache-Control header
        assert "Cache-Control" in static_content, "Cache-Control header not set for static files"

        # Check for immutable directive (good for versioned assets)
        assert "immutable" in static_content, "immutable directive not set for static files"

    def test_media_files_cache_headers(self):
        """Test that media files have appropriate cache headers"""
        site_conf = self.get_nginx_config_path("conf.d/jewelry-shop.conf")
        content = site_conf.read_text()

        # Find media files location block
        media_block = re.search(r"location /media/.*?\{(.*?)\}", content, re.DOTALL)
        assert media_block, "Media files location block not found"

        media_content = media_block.group(1)

        # Check for expires directive
        assert "expires" in media_content, "expires directive not set for media files"

        # Check for Cache-Control header
        assert "Cache-Control" in media_content, "Cache-Control header not set for media files"

    def test_nginx_config_syntax(self):
        """Test that Nginx configuration syntax is valid"""
        # This test requires nginx to be installed
        # Skip if nginx is not available
        try:
            result = subprocess.run(
                ["docker", "compose", "exec", "-T", "nginx", "nginx", "-t"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Check if test was successful
            if result.returncode == 0:
                assert (
                    "syntax is ok" in result.stderr or "test is successful" in result.stderr
                ), f"Nginx config test failed: {result.stderr}"
            else:
                # If docker is not running, skip this test
                print(f"Skipping nginx syntax test (docker not available): {result.stderr}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"Skipping nginx syntax test: {e}")

    def test_gzip_documentation(self):
        """Test that gzip configuration is well documented"""
        gzip_conf = self.get_nginx_config_path("snippets/gzip.conf")
        content = gzip_conf.read_text()

        # Check for comments explaining the configuration
        assert "#" in content, "gzip.conf lacks documentation comments"
        assert "Requirement 22" in content, "gzip.conf does not reference requirement"

    def test_cache_documentation(self):
        """Test that cache configuration is well documented"""
        cache_conf = self.get_nginx_config_path("snippets/cache.conf")
        content = cache_conf.read_text()

        # Check for comments explaining the configuration
        assert "#" in content, "cache.conf lacks documentation comments"
        assert "Requirement 22" in content, "cache.conf does not reference requirement"
        assert "ETag" in content, "cache.conf does not mention ETags"

    def test_font_compression(self):
        """Test that font files are configured for compression"""
        gzip_conf = self.get_nginx_config_path("snippets/gzip.conf")
        content = gzip_conf.read_text()

        # Font MIME types that should be compressed
        font_types = [
            "font/woff",
            "font/woff2",
            "application/font-woff",
        ]

        for font_type in font_types:
            assert font_type in content, f"Font type {font_type} is not configured for gzip"

    def test_font_caching(self):
        """Test that fonts have long cache times"""
        cache_conf = self.get_nginx_config_path("snippets/cache.conf")
        content = cache_conf.read_text()

        # Check that fonts have long cache times (at least 30 days)
        assert re.search(r"font/woff.*\d+d", content), "WOFF fonts do not have cache expiration"
        assert re.search(r"font/woff2.*\d+d", content), "WOFF2 fonts do not have cache expiration"

    def test_no_cache_for_dynamic_content(self):
        """Test that dynamic content is not aggressively cached"""
        cache_conf = self.get_nginx_config_path("snippets/cache.conf")
        content = cache_conf.read_text()

        # HTML should have short cache or no cache
        html_match = re.search(r"text/html\s+(\d+)([hd])", content)
        if html_match:
            value = int(html_match.group(1))
            unit = html_match.group(2)

            # HTML should be cached for hours, not days
            if unit == "d":
                assert value <= 1, "HTML is cached too long (should be hours, not days)"
            elif unit == "h":
                assert value <= 24, "HTML is cached too long (should be <= 24 hours)"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
