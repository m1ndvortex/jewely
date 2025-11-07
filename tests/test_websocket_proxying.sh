#!/bin/bash

# Test WebSocket Proxying Configuration
# This script verifies that Nginx is properly configured for WebSocket connections

set -e

echo "=========================================="
echo "Testing WebSocket Proxying Configuration"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Function to print test result
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ PASS${NC}: $2"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC}: $2"
        ((TESTS_FAILED++))
    fi
}

# Test 1: Check if websocket.conf snippet exists
echo "Test 1: Checking if websocket.conf snippet exists..."
if [ -f "docker/nginx/snippets/websocket.conf" ]; then
    print_result 0 "websocket.conf snippet file exists"
else
    print_result 1 "websocket.conf snippet file not found"
fi
echo ""

# Test 2: Verify websocket.conf contains required directives
echo "Test 2: Verifying websocket.conf contains required directives..."
REQUIRED_DIRECTIVES=(
    "proxy_http_version 1.1"
    "proxy_set_header Upgrade"
    "proxy_set_header Connection"
    "proxy_connect_timeout"
    "proxy_send_timeout"
    "proxy_read_timeout"
)

for directive in "${REQUIRED_DIRECTIVES[@]}"; do
    if grep -q "$directive" docker/nginx/snippets/websocket.conf 2>/dev/null; then
        print_result 0 "websocket.conf contains '$directive'"
    else
        print_result 1 "websocket.conf missing '$directive'"
    fi
done
echo ""

# Test 3: Check if jewelry-shop.conf includes WebSocket location in HTTP block
echo "Test 3: Checking WebSocket location in HTTP server block..."
if grep -A 10 "location /ws/" docker/nginx/conf.d/jewelry-shop.conf | grep -q "include /etc/nginx/snippets/websocket.conf"; then
    print_result 0 "HTTP server block includes WebSocket configuration"
else
    print_result 1 "HTTP server block missing WebSocket configuration"
fi
echo ""

# Test 4: Check if jewelry-shop.conf includes WebSocket location in HTTPS block (commented)
echo "Test 4: Checking WebSocket location in HTTPS server block..."
if grep -A 10 "#     location /ws/" docker/nginx/conf.d/jewelry-shop.conf | grep -q "#         include /etc/nginx/snippets/websocket.conf"; then
    print_result 0 "HTTPS server block includes WebSocket configuration"
else
    print_result 1 "HTTPS server block missing WebSocket configuration"
fi
echo ""

# Test 5: Verify timeout values are reasonable (not 7 days)
echo "Test 5: Verifying WebSocket timeout values are reasonable..."
if grep -q "proxy_connect_timeout 24h" docker/nginx/snippets/websocket.conf; then
    print_result 0 "WebSocket timeouts set to reasonable values (24h)"
else
    print_result 1 "WebSocket timeouts not set to 24h"
fi
echo ""

# Test 6: Check if WebSocket location has rate limiting
echo "Test 6: Checking if WebSocket location has rate limiting..."
if grep -B 5 "location /ws/" docker/nginx/conf.d/jewelry-shop.conf | grep -q "limit_req"; then
    print_result 0 "WebSocket location has rate limiting configured"
else
    print_result 1 "WebSocket location missing rate limiting"
fi
echo ""

# Test 7: Verify Nginx configuration syntax
echo "Test 7: Testing Nginx configuration syntax..."
if docker compose exec -T nginx nginx -t 2>&1 | grep -q "syntax is ok"; then
    print_result 0 "Nginx configuration syntax is valid"
else
    print_result 1 "Nginx configuration syntax has errors"
fi
echo ""

# Test 8: Check if proxy_buffering is disabled for WebSocket
echo "Test 8: Checking if proxy_buffering is disabled..."
if grep -q "proxy_buffering off" docker/nginx/snippets/websocket.conf; then
    print_result 0 "proxy_buffering is disabled for WebSocket"
else
    print_result 1 "proxy_buffering not disabled for WebSocket"
fi
echo ""

# Test 9: Verify tcp_nodelay is enabled
echo "Test 9: Checking if tcp_nodelay is enabled..."
if grep -q "tcp_nodelay on" docker/nginx/snippets/websocket.conf; then
    print_result 0 "tcp_nodelay is enabled for WebSocket"
else
    print_result 1 "tcp_nodelay not enabled for WebSocket"
fi
echo ""

# Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo -e "Tests Passed: ${GREEN}${TESTS_PASSED}${NC}"
echo -e "Tests Failed: ${RED}${TESTS_FAILED}${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Please review the configuration.${NC}"
    exit 1
fi
