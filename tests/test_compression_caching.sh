#!/bin/bash
# Test script for Nginx compression and caching configuration
# Tests gzip compression, cache headers, and ETag generation
# Requirement 22: Nginx Configuration - Task 31.3

set -e

echo "=========================================="
echo "Testing Nginx Compression and Caching"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test configuration
NGINX_URL="${NGINX_URL:-http://localhost}"
TEST_PASSED=0
TEST_FAILED=0

# Function to print test result
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ PASS${NC}: $2"
        ((TEST_PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC}: $2"
        ((TEST_FAILED++))
    fi
}

# Function to test gzip compression
test_gzip_compression() {
    echo "Testing Gzip Compression..."
    echo "----------------------------"
    
    # Test 1: Check if gzip is enabled for HTML
    echo "Test 1: HTML compression"
    RESPONSE=$(curl -s -I -H "Accept-Encoding: gzip" "${NGINX_URL}/" 2>/dev/null || echo "")
    if echo "$RESPONSE" | grep -qi "Content-Encoding: gzip"; then
        print_result 0 "HTML content is gzip compressed"
    else
        print_result 1 "HTML content is NOT gzip compressed"
    fi
    
    # Test 2: Check if gzip is enabled for CSS
    echo "Test 2: CSS compression"
    RESPONSE=$(curl -s -I -H "Accept-Encoding: gzip" "${NGINX_URL}/static/css/style.css" 2>/dev/null || echo "")
    if echo "$RESPONSE" | grep -qi "Content-Encoding: gzip"; then
        print_result 0 "CSS content is gzip compressed"
    else
        # CSS file might not exist, check if gzip would be applied
        if echo "$RESPONSE" | grep -qi "404"; then
            echo -e "${YELLOW}⚠ SKIP${NC}: CSS file not found (expected in development)"
        else
            print_result 1 "CSS content is NOT gzip compressed"
        fi
    fi
    
    # Test 3: Check if gzip is enabled for JavaScript
    echo "Test 3: JavaScript compression"
    RESPONSE=$(curl -s -I -H "Accept-Encoding: gzip" "${NGINX_URL}/static/js/main.js" 2>/dev/null || echo "")
    if echo "$RESPONSE" | grep -qi "Content-Encoding: gzip"; then
        print_result 0 "JavaScript content is gzip compressed"
    else
        if echo "$RESPONSE" | grep -qi "404"; then
            echo -e "${YELLOW}⚠ SKIP${NC}: JavaScript file not found (expected in development)"
        else
            print_result 1 "JavaScript content is NOT gzip compressed"
        fi
    fi
    
    # Test 4: Check if gzip is enabled for JSON
    echo "Test 4: JSON compression"
    RESPONSE=$(curl -s -I -H "Accept-Encoding: gzip" -H "Accept: application/json" "${NGINX_URL}/api/" 2>/dev/null || echo "")
    if echo "$RESPONSE" | grep -qi "Content-Encoding: gzip"; then
        print_result 0 "JSON content is gzip compressed"
    else
        if echo "$RESPONSE" | grep -qi "404"; then
            echo -e "${YELLOW}⚠ SKIP${NC}: API endpoint not found (expected in development)"
        else
            print_result 1 "JSON content is NOT gzip compressed"
        fi
    fi
    
    # Test 5: Check Vary header
    echo "Test 5: Vary: Accept-Encoding header"
    RESPONSE=$(curl -s -I "${NGINX_URL}/" 2>/dev/null || echo "")
    if echo "$RESPONSE" | grep -qi "Vary:.*Accept-Encoding"; then
        print_result 0 "Vary: Accept-Encoding header is present"
    else
        print_result 1 "Vary: Accept-Encoding header is missing"
    fi
    
    echo ""
}

# Function to test cache headers
test_cache_headers() {
    echo "Testing Cache Headers..."
    echo "------------------------"
    
    # Test 6: Check Cache-Control for static files
    echo "Test 6: Cache-Control header for static files"
    RESPONSE=$(curl -s -I "${NGINX_URL}/static/css/style.css" 2>/dev/null || echo "")
    if echo "$RESPONSE" | grep -qi "Cache-Control:.*public"; then
        print_result 0 "Cache-Control header is present for static files"
    else
        if echo "$RESPONSE" | grep -qi "404"; then
            echo -e "${YELLOW}⚠ SKIP${NC}: Static file not found (expected in development)"
        else
            print_result 1 "Cache-Control header is missing for static files"
        fi
    fi
    
    # Test 7: Check Expires header
    echo "Test 7: Expires header for static files"
    RESPONSE=$(curl -s -I "${NGINX_URL}/static/css/style.css" 2>/dev/null || echo "")
    if echo "$RESPONSE" | grep -qi "Expires:"; then
        print_result 0 "Expires header is present for static files"
    else
        if echo "$RESPONSE" | grep -qi "404"; then
            echo -e "${YELLOW}⚠ SKIP${NC}: Static file not found (expected in development)"
        else
            print_result 1 "Expires header is missing for static files"
        fi
    fi
    
    # Test 8: Check Cache-Control for media files
    echo "Test 8: Cache-Control header for media files"
    RESPONSE=$(curl -s -I "${NGINX_URL}/media/test.jpg" 2>/dev/null || echo "")
    if echo "$RESPONSE" | grep -qi "Cache-Control:.*public"; then
        print_result 0 "Cache-Control header is present for media files"
    else
        if echo "$RESPONSE" | grep -qi "404"; then
            echo -e "${YELLOW}⚠ SKIP${NC}: Media file not found (expected in development)"
        else
            print_result 1 "Cache-Control header is missing for media files"
        fi
    fi
    
    echo ""
}

# Function to test ETag generation
test_etag_generation() {
    echo "Testing ETag Generation..."
    echo "--------------------------"
    
    # Test 9: Check if ETag is generated for static files
    echo "Test 9: ETag header for static files"
    RESPONSE=$(curl -s -I "${NGINX_URL}/static/css/style.css" 2>/dev/null || echo "")
    if echo "$RESPONSE" | grep -qi "ETag:"; then
        print_result 0 "ETag header is generated for static files"
    else
        if echo "$RESPONSE" | grep -qi "404"; then
            echo -e "${YELLOW}⚠ SKIP${NC}: Static file not found (expected in development)"
        else
            print_result 1 "ETag header is missing for static files"
        fi
    fi
    
    # Test 10: Check if ETag is generated for media files
    echo "Test 10: ETag header for media files"
    RESPONSE=$(curl -s -I "${NGINX_URL}/media/test.jpg" 2>/dev/null || echo "")
    if echo "$RESPONSE" | grep -qi "ETag:"; then
        print_result 0 "ETag header is generated for media files"
    else
        if echo "$RESPONSE" | grep -qi "404"; then
            echo -e "${YELLOW}⚠ SKIP${NC}: Media file not found (expected in development)"
        else
            print_result 1 "ETag header is missing for media files"
        fi
    fi
    
    # Test 11: Check Last-Modified header
    echo "Test 11: Last-Modified header"
    RESPONSE=$(curl -s -I "${NGINX_URL}/static/css/style.css" 2>/dev/null || echo "")
    if echo "$RESPONSE" | grep -qi "Last-Modified:"; then
        print_result 0 "Last-Modified header is present"
    else
        if echo "$RESPONSE" | grep -qi "404"; then
            echo -e "${YELLOW}⚠ SKIP${NC}: Static file not found (expected in development)"
        else
            print_result 1 "Last-Modified header is missing"
        fi
    fi
    
    # Test 12: Test conditional request with If-None-Match
    echo "Test 12: Conditional request with If-None-Match"
    # First, get the ETag
    ETAG=$(curl -s -I "${NGINX_URL}/static/css/style.css" 2>/dev/null | grep -i "ETag:" | cut -d' ' -f2 | tr -d '\r\n' || echo "")
    if [ -n "$ETAG" ]; then
        # Make conditional request
        STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "If-None-Match: $ETAG" "${NGINX_URL}/static/css/style.css" 2>/dev/null || echo "")
        if [ "$STATUS" = "304" ]; then
            print_result 0 "Conditional request returns 304 Not Modified"
        else
            print_result 1 "Conditional request does not return 304 (got $STATUS)"
        fi
    else
        echo -e "${YELLOW}⚠ SKIP${NC}: Could not get ETag for conditional request test"
    fi
    
    echo ""
}

# Function to test compression effectiveness
test_compression_effectiveness() {
    echo "Testing Compression Effectiveness..."
    echo "------------------------------------"
    
    # Test 13: Compare compressed vs uncompressed size
    echo "Test 13: Compression ratio"
    
    # Get uncompressed size
    UNCOMPRESSED=$(curl -s -w "%{size_download}" -o /dev/null "${NGINX_URL}/" 2>/dev/null || echo "0")
    
    # Get compressed size
    COMPRESSED=$(curl -s -H "Accept-Encoding: gzip" -w "%{size_download}" -o /dev/null "${NGINX_URL}/" 2>/dev/null || echo "0")
    
    if [ "$UNCOMPRESSED" -gt 0 ] && [ "$COMPRESSED" -gt 0 ]; then
        RATIO=$(echo "scale=2; (1 - $COMPRESSED / $UNCOMPRESSED) * 100" | bc)
        echo "  Uncompressed: ${UNCOMPRESSED} bytes"
        echo "  Compressed: ${COMPRESSED} bytes"
        echo "  Compression ratio: ${RATIO}%"
        
        # Check if compression is effective (at least 20% reduction)
        if (( $(echo "$RATIO > 20" | bc -l) )); then
            print_result 0 "Compression is effective (${RATIO}% reduction)"
        else
            print_result 1 "Compression is not effective enough (only ${RATIO}% reduction)"
        fi
    else
        echo -e "${YELLOW}⚠ SKIP${NC}: Could not measure compression effectiveness"
    fi
    
    echo ""
}

# Run all tests
test_gzip_compression
test_cache_headers
test_etag_generation
test_compression_effectiveness

# Print summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo -e "${GREEN}Passed: ${TEST_PASSED}${NC}"
echo -e "${RED}Failed: ${TEST_FAILED}${NC}"
echo ""

if [ $TEST_FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
fi
