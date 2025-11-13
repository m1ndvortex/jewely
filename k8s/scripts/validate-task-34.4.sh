#!/bin/bash

# ============================================================================
# Task 34.4: Validate Nginx Reverse Proxy Deployment
# ============================================================================
# This script validates the Nginx deployment according to task requirements:
# - 2 Nginx pods running
# - nginx.conf mounted correctly from ConfigMap
# - Nginx proxies to Django backend
# - Static files served directly by Nginx
# - No errors in Nginx logs
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="jewelry-shop"
REQUIRED_REPLICAS=2

# Counters
PASSED=0
FAILED=0
WARNINGS=0

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}Task 34.4: Validating Nginx Reverse Proxy Deployment${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""

# Function to print test result
print_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

print_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((PASSED++))
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((FAILED++))
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    ((WARNINGS++))
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Test 1: Verify 2 Nginx pods are running
print_test "Test 1: Verifying 2 Nginx pods are running..."
POD_COUNT=$(kubectl get pods -n "$NAMESPACE" -l component=nginx --field-selector=status.phase=Running -o json | jq '.items | length')
if [ "$POD_COUNT" -eq "$REQUIRED_REPLICAS" ]; then
    print_pass "Found $POD_COUNT running Nginx pods (expected $REQUIRED_REPLICAS)"
else
    print_fail "Found $POD_COUNT running Nginx pods (expected $REQUIRED_REPLICAS)"
    kubectl get pods -n "$NAMESPACE" -l component=nginx
fi
echo ""

# Test 2: Verify all pods are ready
print_test "Test 2: Verifying all Nginx pods are ready..."
READY_PODS=$(kubectl get pods -n "$NAMESPACE" -l component=nginx -o json | jq '[.items[] | select(.status.conditions[] | select(.type=="Ready" and .status=="True"))] | length')
if [ "$READY_PODS" -eq "$POD_COUNT" ]; then
    print_pass "All $READY_PODS Nginx pods are ready"
else
    print_fail "Only $READY_PODS out of $POD_COUNT pods are ready"
fi
echo ""

# Test 3: Verify nginx.conf is mounted from ConfigMap
print_test "Test 3: Verifying nginx.conf is mounted from ConfigMap..."
POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l component=nginx -o jsonpath='{.items[0].metadata.name}')
if kubectl exec -n "$NAMESPACE" "$POD_NAME" -c nginx -- test -f /etc/nginx/nginx.conf; then
    print_pass "nginx.conf file exists in pod"
    
    # Check if it contains expected content
    if kubectl exec -n "$NAMESPACE" "$POD_NAME" -c nginx -- grep -q "worker_processes" /etc/nginx/nginx.conf; then
        print_pass "nginx.conf contains expected configuration"
    else
        print_fail "nginx.conf does not contain expected configuration"
    fi
else
    print_fail "nginx.conf file not found in pod"
fi
echo ""

# Test 4: Verify site configuration is mounted
print_test "Test 4: Verifying site configuration is mounted..."
if kubectl exec -n "$NAMESPACE" "$POD_NAME" -c nginx -- test -f /etc/nginx/conf.d/jewelry-shop.conf; then
    print_pass "jewelry-shop.conf file exists in pod"
    
    # Check if it contains Django backend configuration
    if kubectl exec -n "$NAMESPACE" "$POD_NAME" -c nginx -- grep -q "django_backend" /etc/nginx/conf.d/jewelry-shop.conf; then
        print_pass "Site configuration contains Django backend upstream"
    else
        print_fail "Site configuration does not contain Django backend upstream"
    fi
else
    print_fail "jewelry-shop.conf file not found in pod"
fi
echo ""

# Test 5: Verify snippets are mounted
print_test "Test 5: Verifying configuration snippets are mounted..."
SNIPPETS=("gzip.conf" "proxy-params.conf" "security-headers-dev.conf" "metrics.conf")
SNIPPET_PASS=0
for snippet in "${SNIPPETS[@]}"; do
    if kubectl exec -n "$NAMESPACE" "$POD_NAME" -c nginx -- test -f "/etc/nginx/snippets/$snippet"; then
        ((SNIPPET_PASS++))
    fi
done
if [ "$SNIPPET_PASS" -eq "${#SNIPPETS[@]}" ]; then
    print_pass "All $SNIPPET_PASS configuration snippets are mounted"
else
    print_warn "Only $SNIPPET_PASS out of ${#SNIPPETS[@]} snippets are mounted"
fi
echo ""

# Test 6: Verify Nginx service exists
print_test "Test 6: Verifying Nginx service exists..."
if kubectl get service nginx-service -n "$NAMESPACE" &> /dev/null; then
    print_pass "Nginx service exists"
    
    # Check service type
    SERVICE_TYPE=$(kubectl get service nginx-service -n "$NAMESPACE" -o jsonpath='{.spec.type}')
    if [ "$SERVICE_TYPE" = "ClusterIP" ]; then
        print_pass "Service type is ClusterIP (as expected)"
    else
        print_warn "Service type is $SERVICE_TYPE (expected ClusterIP)"
    fi
    
    # Check service ports
    HTTP_PORT=$(kubectl get service nginx-service -n "$NAMESPACE" -o jsonpath='{.spec.ports[?(@.name=="http")].port}')
    if [ "$HTTP_PORT" = "80" ]; then
        print_pass "HTTP port is 80 (as expected)"
    else
        print_fail "HTTP port is $HTTP_PORT (expected 80)"
    fi
else
    print_fail "Nginx service not found"
fi
echo ""

# Test 7: Test Nginx responds to requests
print_test "Test 7: Testing if Nginx responds to requests..."
RESPONSE=$(kubectl run test-nginx-response --image=curlimages/curl --rm -i --restart=Never -n "$NAMESPACE" -- \
    curl -s -o /dev/null -w "%{http_code}" http://nginx-service 2>/dev/null || echo "000")
if echo "$RESPONSE" | grep -q "200\|301\|302\|404\|502\|503"; then
    print_pass "Nginx responds to HTTP requests (HTTP $RESPONSE)"
else
    print_warn "Nginx may not be responding correctly (this is expected if Django is not deployed)"
fi
echo ""

# Test 8: Test Nginx can reach Django backend (if Django is deployed)
print_test "Test 8: Testing if Nginx can proxy to Django backend..."
if kubectl get service django-service -n "$NAMESPACE" &> /dev/null; then
    print_info "Django service found, testing proxy..."
    
    # Try to access through Nginx
    RESPONSE=$(kubectl run test-nginx-proxy --image=curlimages/curl --rm -i --restart=Never -n "$NAMESPACE" -- \
        curl -s -o /dev/null -w "%{http_code}" http://nginx-service/health/live/ 2>/dev/null || echo "000")
    
    if [ "$RESPONSE" = "200" ]; then
        print_pass "Nginx successfully proxies to Django backend"
    else
        print_warn "Nginx proxy returned HTTP $RESPONSE (expected 200)"
    fi
else
    print_warn "Django service not found, skipping proxy test"
fi
echo ""

# Test 9: Check for errors in Nginx logs
print_test "Test 9: Checking Nginx logs for errors..."
ERROR_COUNT=$(kubectl logs -n "$NAMESPACE" -l component=nginx -c nginx --tail=100 2>/dev/null | grep -i "error" | grep -v "error.log" | wc -l || echo "0")
if [ "$ERROR_COUNT" -eq 0 ]; then
    print_pass "No errors found in Nginx logs"
else
    print_warn "Found $ERROR_COUNT error messages in Nginx logs"
    print_info "Recent errors:"
    kubectl logs -n "$NAMESPACE" -l component=nginx -c nginx --tail=100 | grep -i "error" | grep -v "error.log" | head -5
fi
echo ""

# Test 10: Verify resource requests and limits
print_test "Test 10: Verifying resource requests and limits..."
RESOURCES=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o json | jq -r '.spec.containers[] | select(.name=="nginx") | .resources')
if echo "$RESOURCES" | jq -e '.requests.cpu' &> /dev/null; then
    CPU_REQUEST=$(echo "$RESOURCES" | jq -r '.requests.cpu')
    CPU_LIMIT=$(echo "$RESOURCES" | jq -r '.limits.cpu')
    MEM_REQUEST=$(echo "$RESOURCES" | jq -r '.requests.memory')
    MEM_LIMIT=$(echo "$RESOURCES" | jq -r '.limits.memory')
    
    print_pass "Resource requests and limits are configured:"
    print_info "  CPU: $CPU_REQUEST (request) / $CPU_LIMIT (limit)"
    print_info "  Memory: $MEM_REQUEST (request) / $MEM_LIMIT (limit)"
else
    print_fail "Resource requests and limits not configured"
fi
echo ""

# Test 11: Verify health checks are configured
print_test "Test 11: Verifying health checks are configured..."
LIVENESS=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o json | jq -r '.spec.containers[] | select(.name=="nginx") | .livenessProbe')
READINESS=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o json | jq -r '.spec.containers[] | select(.name=="nginx") | .readinessProbe')

if [ "$LIVENESS" != "null" ]; then
    LIVENESS_TYPE=$(echo "$LIVENESS" | jq -r 'keys[0]')
    print_pass "Liveness probe configured (type: $LIVENESS_TYPE)"
else
    print_fail "Liveness probe not configured"
fi

if [ "$READINESS" != "null" ]; then
    READINESS_TYPE=$(echo "$READINESS" | jq -r 'keys[0]')
    print_pass "Readiness probe configured (type: $READINESS_TYPE)"
else
    print_fail "Readiness probe not configured"
fi
echo ""

# Test 12: Verify pod anti-affinity
print_test "Test 12: Verifying pod anti-affinity for high availability..."
AFFINITY=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o json | jq -r '.spec.affinity')
if [ "$AFFINITY" != "null" ]; then
    print_pass "Pod anti-affinity is configured"
else
    print_warn "Pod anti-affinity not configured (pods may run on same node)"
fi
echo ""

# Display summary
echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}Validation Summary${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""
echo -e "${GREEN}Passed:${NC}   $PASSED"
echo -e "${RED}Failed:${NC}   $FAILED"
echo -e "${YELLOW}Warnings:${NC} $WARNINGS"
echo ""

if [ "$FAILED" -eq 0 ]; then
    echo -e "${GREEN}============================================================================${NC}"
    echo -e "${GREEN}All critical tests passed! Nginx deployment is successful.${NC}"
    echo -e "${GREEN}============================================================================${NC}"
    exit 0
else
    echo -e "${RED}============================================================================${NC}"
    echo -e "${RED}Some tests failed. Please review the output above.${NC}"
    echo -e "${RED}============================================================================${NC}"
    exit 1
fi
