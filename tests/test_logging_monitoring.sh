#!/bin/bash
# Test script for Nginx logging and monitoring
# Task 31.5: Configure logging and monitoring
# Tests runtime behavior of logging and metrics

set -e

echo "=========================================="
echo "Testing Nginx Logging and Monitoring"
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

# Function to check if service is running
check_service() {
    docker compose ps | grep -q "$1.*Up"
    return $?
}

echo "1. Checking if required services are running..."
echo "----------------------------------------------"

check_service "nginx"
print_result $? "Nginx service is running"

check_service "nginx_exporter"
print_result $? "nginx_exporter service is running"

check_service "prometheus"
print_result $? "Prometheus service is running"

echo ""
echo "2. Testing Nginx configuration..."
echo "----------------------------------------------"

# Test nginx configuration syntax
docker compose exec -T nginx nginx -t > /dev/null 2>&1
print_result $? "Nginx configuration syntax is valid"

# Check if logging snippet is loaded
docker compose exec -T nginx cat /etc/nginx/snippets/logging.conf > /dev/null 2>&1
print_result $? "Logging snippet is accessible"

# Check if metrics snippet is loaded
docker compose exec -T nginx cat /etc/nginx/snippets/metrics.conf > /dev/null 2>&1
print_result $? "Metrics snippet is accessible"

echo ""
echo "3. Testing access logs..."
echo "----------------------------------------------"

# Make a test request to generate log entry
echo "Making test request to generate access log..."
curl -s http://localhost/health/ > /dev/null 2>&1
sleep 2

# Check if access log exists and has entries
docker compose exec -T nginx test -f /var/log/nginx/access.log
print_result $? "Access log file exists"

# Check if access log contains response time metrics
docker compose exec -T nginx tail -n 5 /var/log/nginx/access.log | grep -q "rt="
print_result $? "Access log contains request time (rt=)"

docker compose exec -T nginx tail -n 5 /var/log/nginx/access.log | grep -q "uct="
print_result $? "Access log contains upstream connect time (uct=)"

docker compose exec -T nginx tail -n 5 /var/log/nginx/access.log | grep -q "urt="
print_result $? "Access log contains upstream response time (urt=)"

echo ""
echo "4. Testing error logs..."
echo "----------------------------------------------"

# Check if error log exists
docker compose exec -T nginx test -f /var/log/nginx/error.log
print_result $? "Error log file exists"

# Check if critical error log exists
docker compose exec -T nginx test -f /var/log/nginx/error-critical.log
print_result $? "Critical error log file exists"

echo ""
echo "5. Testing Nginx metrics endpoint..."
echo "----------------------------------------------"

# Test nginx_status endpoint (should be accessible from Docker network)
NGINX_STATUS=$(docker compose exec -T nginx wget -q -O - http://localhost/nginx_status 2>/dev/null || echo "")

if echo "$NGINX_STATUS" | grep -q "Active connections"; then
    print_result 0 "nginx_status endpoint is accessible"
else
    print_result 1 "nginx_status endpoint is not accessible"
fi

if echo "$NGINX_STATUS" | grep -q "server accepts handled requests"; then
    print_result 0 "nginx_status shows connection metrics"
else
    print_result 1 "nginx_status doesn't show connection metrics"
fi

if echo "$NGINX_STATUS" | grep -q "Reading.*Writing.*Waiting"; then
    print_result 0 "nginx_status shows state metrics"
else
    print_result 1 "nginx_status doesn't show state metrics"
fi

echo ""
echo "6. Testing nginx-prometheus-exporter..."
echo "----------------------------------------------"

# Check if nginx_exporter is exposing metrics
EXPORTER_METRICS=$(curl -s http://localhost:9113/metrics 2>/dev/null || echo "")

if echo "$EXPORTER_METRICS" | grep -q "nginx_"; then
    print_result 0 "nginx_exporter is exposing metrics"
else
    print_result 1 "nginx_exporter is not exposing metrics"
fi

if echo "$EXPORTER_METRICS" | grep -q "nginx_connections_active"; then
    print_result 0 "nginx_exporter exposes active connections metric"
else
    print_result 1 "nginx_exporter doesn't expose active connections metric"
fi

if echo "$EXPORTER_METRICS" | grep -q "nginx_http_requests_total"; then
    print_result 0 "nginx_exporter exposes total requests metric"
else
    print_result 1 "nginx_exporter doesn't expose total requests metric"
fi

echo ""
echo "7. Testing Prometheus integration..."
echo "----------------------------------------------"

# Check if Prometheus is scraping nginx_exporter
sleep 5  # Wait for Prometheus to scrape

PROM_TARGETS=$(curl -s http://localhost:9090/api/v1/targets 2>/dev/null || echo "")

if echo "$PROM_TARGETS" | grep -q "nginx"; then
    print_result 0 "Prometheus has nginx job configured"
else
    print_result 1 "Prometheus doesn't have nginx job configured"
fi

# Query Prometheus for nginx metrics
PROM_QUERY=$(curl -s "http://localhost:9090/api/v1/query?query=nginx_connections_active" 2>/dev/null || echo "")

if echo "$PROM_QUERY" | grep -q "nginx_connections_active"; then
    print_result 0 "Prometheus is collecting nginx metrics"
else
    print_result 1 "Prometheus is not collecting nginx metrics"
fi

echo ""
echo "8. Testing log rotation readiness..."
echo "----------------------------------------------"

# Check if log directory is writable
docker compose exec -T nginx test -w /var/log/nginx
print_result $? "Nginx log directory is writable"

# Check if logs are being written
ACCESS_LOG_SIZE=$(docker compose exec -T nginx stat -c%s /var/log/nginx/access.log 2>/dev/null || echo "0")
if [ "$ACCESS_LOG_SIZE" -gt 0 ]; then
    print_result 0 "Access log is being written (size: $ACCESS_LOG_SIZE bytes)"
else
    print_result 1 "Access log is not being written"
fi

echo ""
echo "9. Testing metrics endpoint security..."
echo "----------------------------------------------"

# Test that nginx_status is not publicly accessible (should fail from outside)
# This test assumes we're running from host, not inside Docker network
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/nginx_status 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "403" ] || [ "$HTTP_CODE" = "000" ]; then
    print_result 0 "nginx_status endpoint is properly restricted (HTTP $HTTP_CODE)"
else
    print_result 1 "nginx_status endpoint may be publicly accessible (HTTP $HTTP_CODE)"
fi

echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
fi
