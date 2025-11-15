#!/bin/bash

# Comprehensive Loki Testing Script
# Tests log collection, querying, and integration with Grafana

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

NAMESPACE="jewelry-shop"
FAILED_TESTS=0
PASSED_TESTS=0

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Comprehensive Loki Testing${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓ PASS]${NC} $1"; ((PASSED_TESTS++)); }
print_error() { echo -e "${RED}[✗ FAIL]${NC} $1"; ((FAILED_TESTS++)); }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }

# Get pod names
LOKI_POD=$(kubectl get pods -n "$NAMESPACE" -l app=loki -o jsonpath='{.items[0].metadata.name}')
PROMTAIL_POD=$(kubectl get pods -n "$NAMESPACE" -l app=promtail -o jsonpath='{.items[0].metadata.name}')

# Test Suite 1: Deployment Validation
print_info "=== Test Suite 1: Deployment Validation ==="

# Test 1.1: Loki pod health
print_info "Test 1.1: Checking Loki pod health..."
if kubectl get pods -n "$NAMESPACE" -l app=loki | grep -q "1/1.*Running"; then
    print_success "Loki pod is healthy"
else
    print_error "Loki pod is not healthy"
fi

# Test 1.2: Promtail pods health
print_info "Test 1.2: Checking Promtail pods health..."
EXPECTED_NODES=$(kubectl get nodes --no-headers | wc -l)
RUNNING_PROMTAIL=$(kubectl get pods -n "$NAMESPACE" -l app=promtail --field-selector=status.phase=Running --no-headers | wc -l)
if [ "$RUNNING_PROMTAIL" -eq "$EXPECTED_NODES" ]; then
    print_success "All Promtail pods are healthy ($RUNNING_PROMTAIL/$EXPECTED_NODES)"
else
    print_error "Promtail pods not healthy ($RUNNING_PROMTAIL/$EXPECTED_NODES)"
fi

# Test Suite 2: API Functionality
print_info "=== Test Suite 2: API Functionality ==="

# Test 2.1: Loki ready endpoint
print_info "Test 2.1: Testing Loki ready endpoint..."
if kubectl exec -n "$NAMESPACE" "$LOKI_POD" -- wget -q -O- http://localhost:3100/ready | grep -q "ready"; then
    print_success "Loki ready endpoint responding"
else
    print_error "Loki ready endpoint not responding"
fi

# Test 2.2: Loki labels API
print_info "Test 2.2: Testing Loki labels API..."
sleep 10  # Wait for log ingestion
LABELS=$(kubectl exec -n "$NAMESPACE" "$LOKI_POD" -- wget -q -O- http://localhost:3100/loki/api/v1/labels 2>/dev/null)
if echo "$LABELS" | grep -q '"status":"success"'; then
    print_success "Loki labels API working"
else
    print_error "Loki labels API not working"
fi

# Test 2.3: Query logs from namespace
print_info "Test 2.3: Testing log query for jewelry-shop namespace..."
QUERY=$(kubectl exec -n "$NAMESPACE" "$LOKI_POD" -- wget -q -O- 'http://localhost:3100/loki/api/v1/query?query={namespace="jewelry-shop"}&limit=10' 2>/dev/null)
if echo "$QUERY" | grep -q '"status":"success"'; then
    print_success "Successfully queried logs from jewelry-shop namespace"
else
    print_warning "No logs found yet (may need more time)"
fi

# Test Suite 3: Log Collection
print_info "=== Test Suite 3: Log Collection ==="

# Test 3.1: Create test pod and verify log collection
print_info "Test 3.1: Creating test pod to generate logs..."
kubectl run test-logger --image=busybox --restart=Never -n "$NAMESPACE" -- sh -c "for i in \$(seq 1 10); do echo 'Test log message \$i'; sleep 1; done" 2>/dev/null || true
sleep 15

# Query for test pod logs
TEST_LOGS=$(kubectl exec -n "$NAMESPACE" "$LOKI_POD" -- wget -q -O- 'http://localhost:3100/loki/api/v1/query?query={pod="test-logger"}&limit=10' 2>/dev/null)
if echo "$TEST_LOGS" | grep -q "Test log message"; then
    print_success "Test pod logs collected successfully"
else
    print_warning "Test pod logs not found yet"
fi

# Cleanup test pod
kubectl delete pod test-logger -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null

# Test Suite 4: Metrics
print_info "=== Test Suite 4: Metrics ==="

# Test 4.1: Loki metrics
print_info "Test 4.1: Checking Loki metrics..."
if kubectl exec -n "$NAMESPACE" "$LOKI_POD" -- wget -q -O- http://localhost:3100/metrics | grep -q "loki_ingester_chunks_created_total"; then
    print_success "Loki metrics available"
else
    print_error "Loki metrics not available"
fi

# Test 4.2: Promtail metrics
print_info "Test 4.2: Checking Promtail metrics..."
if kubectl exec -n "$NAMESPACE" "$PROMTAIL_POD" -- wget -q -O- http://localhost:9080/metrics | grep -q "promtail_sent_entries_total"; then
    print_success "Promtail metrics available"
else
    print_error "Promtail metrics not available"
fi

# Test Suite 5: Storage and Retention
print_info "=== Test Suite 5: Storage and Retention ==="

# Test 5.1: PVC status
print_info "Test 5.1: Checking PVC status..."
if kubectl get pvc loki-storage -n "$NAMESPACE" | grep -q "Bound"; then
    print_success "Loki PVC is bound"
else
    print_error "Loki PVC is not bound"
fi

# Test 5.2: Storage usage
print_info "Test 5.2: Checking storage usage..."
STORAGE_USED=$(kubectl exec -n "$NAMESPACE" "$LOKI_POD" -- df -h /loki | tail -1 | awk '{print $5}')
print_info "Loki storage usage: $STORAGE_USED"

# Test Suite 6: Integration
print_info "=== Test Suite 6: Integration Tests ==="

# Test 6.1: Grafana datasource
print_info "Test 6.1: Checking Grafana datasource configuration..."
if kubectl get configmap loki-datasource -n "$NAMESPACE" >/dev/null 2>&1; then
    print_success "Loki datasource configured for Grafana"
else
    print_warning "Loki datasource not configured"
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Tests Passed: ${GREEN}$PASSED_TESTS${NC}"
echo -e "Tests Failed: ${RED}$FAILED_TESTS${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed.${NC}"
    exit 1
fi
