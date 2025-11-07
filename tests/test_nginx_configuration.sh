#!/bin/bash
# Test script for Nginx Configuration (Task 31.1)
# Tests all 10 acceptance criteria from Requirement 22

# Don't exit on error, we want to count failures
set +e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0

echo -e "${GREEN}=== Testing Nginx Configuration (Requirement 22) ===${NC}"
echo ""

# Helper function to test
test_requirement() {
    local test_name="$1"
    local test_command="$2"
    
    echo -n "Testing: $test_name... "
    
    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASSED${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}"
        ((FAILED++))
        return 1
    fi
}

# 1. Test reverse proxy to Django backend
test_requirement "1. Reverse proxy to Django backend" \
    "curl -s http://localhost/health/ | grep -q 'healthy'"

# 2. Test static file serving
test_requirement "2. Static file serving" \
    "curl -I http://localhost/static/admin/css/base.css 2>&1 | grep -q '200 OK'"

# 3. Test SSL/TLS configuration (check if certbot is running)
test_requirement "3. SSL/TLS with Let's Encrypt (certbot running)" \
    "docker compose ps certbot | grep -q 'Up'"

# 4. Test HTTP/2 support (configuration check)
test_requirement "4. HTTP/2 configuration present" \
    "docker compose exec nginx grep -q 'http2' /etc/nginx/conf.d/jewelry-shop.conf"

# 5. Test security headers (HSTS, CSP, etc.)
test_requirement "5. Security headers configured" \
    "docker compose exec nginx grep -q 'Strict-Transport-Security' /etc/nginx/snippets/security-headers.conf"

# 6. Test rate limiting configuration
test_requirement "6. Rate limiting configured" \
    "docker compose exec nginx grep -q 'limit_req_zone' /etc/nginx/nginx.conf"

# 7. Test gzip compression
test_requirement "7. Gzip compression enabled" \
    "docker compose exec nginx grep -q 'gzip on' /etc/nginx/snippets/gzip.conf"

# 8. Test WebSocket proxy configuration
test_requirement "8. WebSocket proxy configured" \
    "docker compose exec nginx grep -q 'Upgrade' /etc/nginx/snippets/proxy-params.conf"

# 9. Test request logging with response times
test_requirement "9. Request logging with response times" \
    "docker compose exec nginx grep -q 'request_time' /etc/nginx/nginx.conf"

# 10. Test Prometheus metrics export
test_requirement "10. Prometheus metrics export" \
    "curl -s http://localhost:9113/metrics | grep -q 'nginx_up 1'"

echo ""
echo -e "${GREEN}=== Additional Tests ===${NC}"
echo ""

# Test nginx configuration syntax
test_requirement "Nginx configuration syntax valid" \
    "docker compose exec nginx nginx -t"

# Test nginx is healthy
test_requirement "Nginx container healthy" \
    "docker compose ps nginx | grep -q 'healthy'"

# Test nginx_exporter is running
test_requirement "Nginx exporter running" \
    "docker compose ps nginx_exporter | grep -q 'Up'"

# Test static file caching headers
test_requirement "Static file caching headers" \
    "curl -I http://localhost/static/admin/css/base.css 2>&1 | grep -q 'Cache-Control'"

# Test media file serving
test_requirement "Media file directory accessible" \
    "docker compose exec nginx test -d /app/media"

# Test SSL directory exists
test_requirement "SSL directory exists" \
    "docker compose exec nginx test -d /etc/nginx/ssl"

echo ""
echo -e "${GREEN}=== Test Summary ===${NC}"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed!${NC}"
    exit 1
fi
