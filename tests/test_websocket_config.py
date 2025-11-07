"""
Test WebSocket Proxying Configuration

This test verifies that Nginx is properly configured to handle WebSocket connections
with appropriate headers and timeouts.
"""

import os
import re
import pytest


class TestWebSocketConfiguration:
    """Test WebSocket proxying configuration in Nginx"""
    
    @pytest.fixture
    def websocket_snippet_path(self):
        """Path to websocket.conf snippet"""
        return "docker/nginx/snippets/websocket.conf"
    
    @pytest.fixture
    def nginx_conf_path(self):
        """Path to main Nginx configuration"""
        return "docker/nginx/conf.d/jewelry-shop.conf"
    
    @pytest.fixture
    def websocket_snippet_content(self, websocket_snippet_path):
        """Read websocket.conf content"""
        with open(websocket_snippet_path, 'r') as f:
            return f.read()
    
    @pytest.fixture
    def nginx_conf_content(self, nginx_conf_path):
        """Read jewelry-shop.conf content"""
        with open(nginx_conf_path, 'r') as f:
            return f.read()
    
    def test_websocket_snippet_exists(self, websocket_snippet_path):
        """Test that websocket.conf snippet file exists"""
        assert os.path.exists(websocket_snippet_path), \
            "websocket.conf snippet file should exist"
    
    def test_websocket_http_version(self, websocket_snippet_content):
        """Test that HTTP/1.1 is configured for WebSocket"""
        assert "proxy_http_version 1.1" in websocket_snippet_content, \
            "WebSocket configuration should use HTTP/1.1"
    
    def test_websocket_upgrade_header(self, websocket_snippet_content):
        """Test that Upgrade header is configured"""
        assert re.search(r'proxy_set_header\s+Upgrade\s+\$http_upgrade', websocket_snippet_content), \
            "WebSocket configuration should set Upgrade header"
    
    def test_websocket_connection_header(self, websocket_snippet_content):
        """Test that Connection header is configured"""
        assert re.search(r'proxy_set_header\s+Connection\s+"upgrade"', websocket_snippet_content), \
            "WebSocket configuration should set Connection header to 'upgrade'"
    
    def test_websocket_connect_timeout(self, websocket_snippet_content):
        """Test that connect timeout is configured"""
        assert "proxy_connect_timeout" in websocket_snippet_content, \
            "WebSocket configuration should have connect timeout"
        
        # Verify timeout is reasonable (not 7 days)
        match = re.search(r'proxy_connect_timeout\s+(\d+[hmd])', websocket_snippet_content)
        assert match, "Connect timeout should be specified"
        timeout = match.group(1)
        assert timeout == "24h", f"Connect timeout should be 24h, got {timeout}"
    
    def test_websocket_send_timeout(self, websocket_snippet_content):
        """Test that send timeout is configured"""
        assert "proxy_send_timeout" in websocket_snippet_content, \
            "WebSocket configuration should have send timeout"
        
        match = re.search(r'proxy_send_timeout\s+(\d+[hmd])', websocket_snippet_content)
        assert match, "Send timeout should be specified"
        timeout = match.group(1)
        assert timeout == "24h", f"Send timeout should be 24h, got {timeout}"
    
    def test_websocket_read_timeout(self, websocket_snippet_content):
        """Test that read timeout is configured"""
        assert "proxy_read_timeout" in websocket_snippet_content, \
            "WebSocket configuration should have read timeout"
        
        match = re.search(r'proxy_read_timeout\s+(\d+[hmd])', websocket_snippet_content)
        assert match, "Read timeout should be specified"
        timeout = match.group(1)
        assert timeout == "24h", f"Read timeout should be 24h, got {timeout}"
    
    def test_websocket_buffering_disabled(self, websocket_snippet_content):
        """Test that proxy buffering is disabled for WebSocket"""
        assert "proxy_buffering off" in websocket_snippet_content, \
            "WebSocket configuration should disable proxy buffering"
    
    def test_websocket_tcp_nodelay(self, websocket_snippet_content):
        """Test that tcp_nodelay is enabled"""
        assert "tcp_nodelay on" in websocket_snippet_content, \
            "WebSocket configuration should enable tcp_nodelay"
    
    def test_websocket_location_in_http_block(self, nginx_conf_content):
        """Test that /ws/ location exists in HTTP server block"""
        # Find the HTTP server block (listen 80)
        http_block_match = re.search(
            r'server\s*{[^}]*listen\s+80;.*?location\s+/ws/\s*{.*?}',
            nginx_conf_content,
            re.DOTALL
        )
        assert http_block_match, "/ws/ location should exist in HTTP server block"
    
    def test_websocket_snippet_included_in_http(self, nginx_conf_content):
        """Test that websocket.conf is included in HTTP /ws/ location"""
        # Find the /ws/ location in HTTP block
        ws_location_match = re.search(
            r'location\s+/ws/\s*{(.*?)}',
            nginx_conf_content,
            re.DOTALL
        )
        assert ws_location_match, "/ws/ location should exist"
        
        ws_location_content = ws_location_match.group(1)
        assert "include /etc/nginx/snippets/websocket.conf" in ws_location_content, \
            "HTTP /ws/ location should include websocket.conf snippet"
    
    def test_websocket_snippet_included_in_https(self, nginx_conf_content):
        """Test that websocket.conf is included in HTTPS /ws/ location (commented)"""
        # Find the commented /ws/ location in HTTPS block
        assert "#         include /etc/nginx/snippets/websocket.conf" in nginx_conf_content, \
            "HTTPS /ws/ location should include websocket.conf snippet (commented)"
    
    def test_websocket_rate_limiting(self, nginx_conf_content):
        """Test that WebSocket location has rate limiting"""
        # Find the /ws/ location
        ws_location_match = re.search(
            r'location\s+/ws/\s*{(.*?)}',
            nginx_conf_content,
            re.DOTALL
        )
        assert ws_location_match, "/ws/ location should exist"
        
        ws_location_content = ws_location_match.group(1)
        assert "limit_req" in ws_location_content, \
            "/ws/ location should have rate limiting configured"
        assert "limit_conn" in ws_location_content, \
            "/ws/ location should have connection limiting configured"
    
    def test_websocket_proxy_pass(self, nginx_conf_content):
        """Test that WebSocket location proxies to Django backend"""
        ws_location_match = re.search(
            r'location\s+/ws/\s*{(.*?)}',
            nginx_conf_content,
            re.DOTALL
        )
        assert ws_location_match, "/ws/ location should exist"
        
        ws_location_content = ws_location_match.group(1)
        assert "proxy_pass http://django_backend" in ws_location_content, \
            "/ws/ location should proxy to django_backend"
    
    def test_websocket_proxy_params_included(self, nginx_conf_content):
        """Test that proxy-params.conf is included in WebSocket location"""
        ws_location_match = re.search(
            r'location\s+/ws/\s*{(.*?)}',
            nginx_conf_content,
            re.DOTALL
        )
        assert ws_location_match, "/ws/ location should exist"
        
        ws_location_content = ws_location_match.group(1)
        assert "include /etc/nginx/snippets/proxy-params.conf" in ws_location_content, \
            "/ws/ location should include proxy-params.conf"
    
    def test_no_excessive_timeouts(self, websocket_snippet_content):
        """Test that timeouts are not excessively long (like 7 days)"""
        # Check that we don't have 7d timeouts
        assert "7d" not in websocket_snippet_content, \
            "WebSocket timeouts should not be 7 days (too long)"
        
        # Verify we have reasonable timeouts (24h)
        assert "24h" in websocket_snippet_content, \
            "WebSocket timeouts should be set to 24 hours"


class TestWebSocketDocumentation:
    """Test that WebSocket configuration is documented"""
    
    def test_nginx_documentation_exists(self):
        """Test that Nginx documentation exists"""
        doc_path = "docs/NGINX_CONFIGURATION.md"
        assert os.path.exists(doc_path), \
            "Nginx configuration documentation should exist"
    
    def test_websocket_documented(self):
        """Test that WebSocket configuration is documented"""
        doc_path = "docs/NGINX_CONFIGURATION.md"
        with open(doc_path, 'r') as f:
            content = f.read()
        
        # Check for WebSocket-related documentation
        assert "websocket" in content.lower() or "ws/" in content, \
            "Documentation should mention WebSocket configuration"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
