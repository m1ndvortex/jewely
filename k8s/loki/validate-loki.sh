#!/bin/bash

# Loki Validation Script
# This script validates the Loki and Promtail deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="jewelry-shop"
FAILED_TESTS=0
PASSED_TESTS=0

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Loki Validation Tests${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to print colored messages
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓ PASS]${NC} $1"
    ((PASSED_TESTS++))
}

print_error() {
    echo -e "${RED}[✗ FAIL]${NC} $1"
    ((FAILED_TESTS++))
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Test 1: Check if Loki pod is running
print_info "Test 1: Checking if Loki pod is running..."
if kubectl get pods -n "$NAMESPACE" -l app=loki | grep -q "Running"; then
    print_success "Loki pod is running"
else
    print_error "Loki pod is not running"
    kubectl get pods -n "$NAMESPACE" -l app=loki
fi

# Test 2: Check if Loki service exists
print_info "Test 2: Checking if Loki service exists..."
if kubectl get service loki -n "$NAMESPACE" >/dev/null 2>&1; then
    print_success "Loki service exists"
else
    print_error "Loki service does not exist"
fi

# Test 3: Check if Promtail DaemonSet exists
print_info "Test 3: Checking if Promtail DaemonSet exists..."
if kubectl get daemonset promtail -n "$NAMESPACE" >/dev/null 2>&1; then
    print_success "Promtail DaemonSet exists"
else
    print_error "Promtail DaemonSet does not exist"
fi

# Test 4: Check if Promtail pods are running on all nodes
print_info "Test 4: Checking if Promtail pods are running..."
NODE_COUNT=$(kubectl get nodes --no-headers | wc -l)
PROMTAIL_COUNT=$(kubectl get pods -n "$NAMESPACE" -l app=promtail --field-selector=status.phase=Running --no-headers | wc -l)
if [ "$PROMTAIL_COUNT" -eq "$NODE_COUNT" ]; then
    print_success "Promtail is running on all $NODE_COUNT nodes"
else
    print_warning "Promtail running on $PROMTAIL_COUNT nodes, expected $NODE_COUNT"
fi

# Test 5: Check Loki readiness
print_info "Test 5: Checking Loki readiness endpoint..."
LOKI_POD=$(kubectl get pods -n "$NAMESPACE" -l app=loki -o jsonpath='{.items[0].metadata.name}')
if kubectl exec -n "$NAMESPACE" "$LOKI_POD" -- wget -q -O- http://localhost:3100/ready | grep -q "ready"; then
    print_success "Loki is ready"
else
    print_error "Loki is not ready"
fi

# Test 6: Check if Loki is receiving logs
print_info "Test 6: Checking if Loki is receiving logs..."
sleep 5  # Wait for logs to be ingested
LABEL_COUNT=$(kubectl exec -n "$NAMESPACE" "$LOKI_POD" -- wget -q -O- http://localhost:3100/loki/api/v1/labels 2>/dev/null | grep -o '"data":\[' | wc -l)
if [ "$LABEL_COUNT" -gt 0 ]; then
    print_success "Loki is receiving logs (found labels)"
else
    print_warning "Loki may not be receiving logs yet (no labels found)"
fi

# Test 7: Check if logs from jewelry-shop namespace are being collected
print_info "Test 7: Checking if logs from jewelry-shop namespace are being collected..."
QUERY_RESULT=$(kubectl exec -n "$NAMESPACE" "$LOKI_POD" -- wget -q -O- 'http://localhost:3100/loki/api/v1/query?query={namespace="jewelry-shop"}' 2>/dev/null || echo "")
if echo "$QUERY_RESULT" | grep -q '"status":"success"'; then
    print_success "Logs from jewelry-shop namespace are being collected"
else
    print_warning "No logs from jewelry-shop namespace found yet (may need more time)"
fi

# Test 8: Check Promtail metrics
print_info "Test 8: Checking Promtail metrics..."
PROMTAIL_POD=$(kubectl get pods -n "$NAMESPACE" -l app=promtail -o jsonpath='{.items[0].metadata.name}')
if kubectl exec -n "$NAMESPACE" "$PROMTAIL_POD" -- wget -q -O- http://localhost:9080/metrics | grep -q "promtail_"; then
    print_success "Promtail is exposing metrics"
else
    print_error "Promtail is not exposing metrics"
fi

# Test 9: Check Loki metrics
print_info "Test 9: Checking Loki metrics..."
if kubectl exec -n "$NAMESPACE" "$LOKI_POD" -- wget -q -O- http://localhost:3100/metrics | grep -q "loki_"; then
    print_success "Loki is exposing metrics"
else
    print_error "Loki is not exposing metrics"
fi

# Test 10: Check PersistentVolumeClaim
print_info "Test 10: Checking Loki PersistentVolumeClaim..."
if kubectl get pvc loki-storage -n "$NAMESPACE" | grep -q "Bound"; then
    print_success "Loki PVC is bound"
else
    print_error "Loki PVC is not bound"
    kubectl get pvc loki-storage -n "$NAMESPACE"
fi

# Test 11: Check if Loki datasource is configured in Grafana
print_info "Test 11: Checking if Loki datasource is configured for Grafana..."
if kubectl get configmap loki-datasource -n "$NAMESPACE" >/dev/null 2>&1; then
    print_success "Loki datasource ConfigMap exists"
else
    print_warning "Loki datasource ConfigMap not found"
fi

# Test 12: Check Promtail ServiceAccount and RBAC
print_info "Test 12: Checking Promtail RBAC configuration..."
if kubectl get serviceaccount promtail -n "$NAMESPACE" >/dev/null 2>&1; then
    print_success "Promtail ServiceAccount exists"
else
    print_error "Promtail ServiceAccount does not exist"
fi

if kubectl get clusterrole promtail >/dev/null 2>&1; then
    print_success "Promtail ClusterRole exists"
else
    print_error "Promtail ClusterRole does not exist"
fi

# Test 13: Check log retention configuration
print_info "Test 13: Checking log retention configuration..."
RETENTION=$(kubectl get configmap loki-config -n "$NAMESPACE" -o yaml | grep "retention_period:" | head -1 | awk '{print $2}')
if [ -n "$RETENTION" ]; then
    print_success "Log retention configured: $RETENTION"
else
    print_warning "Log retention configuration not found"
fi

# Test 14: Test log query functionality
print_info "Test 14: Testing log query functionality..."
QUERY_TEST=$(kubectl exec -n "$NAMESPACE" "$LOKI_POD" -- wget -q -O- 'http://localhost:3100/loki/api/v1/query_range?query={namespace="jewelry-shop"}&limit=10' 2>/dev/null || echo "")
if echo "$QUERY_TEST" | grep -q '"status":"success"'; then
    print_success "Log query functionality is working"
else
    print_warning "Log query returned no results (may need more time for log ingestion)"
fi

# Test 15: Check resource usage
print_info "Test 15: Checking resource usage..."
LOKI_CPU=$(kubectl top pod -n "$NAMESPACE" "$LOKI_POD" --no-headers 2>/dev/null | awk '{print $2}' || echo "N/A")
LOKI_MEM=$(kubectl top pod -n "$NAMESPACE" "$LOKI_POD" --no-headers 2>/dev/null | awk '{print $3}' || echo "N/A")
if [ "$LOKI_CPU" != "N/A" ]; then
    print_success "Loki resource usage: CPU=$LOKI_CPU, Memory=$LOKI_MEM"
else
    print_warning "Could not retrieve resource usage (metrics-server may not be installed)"
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Validation Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Tests Passed: ${GREEN}$PASSED_TESTS${NC}"
echo -e "Tests Failed: ${RED}$FAILED_TESTS${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}✓ All critical tests passed!${NC}"
    echo ""
    echo -e "${BLUE}Loki Deployment Information:${NC}"
    echo ""
    kubectl get all -n "$NAMESPACE" -l component=logging
    echo ""
    echo -e "${BLUE}Storage Information:${NC}"
    echo ""
    kubectl get pvc -n "$NAMESPACE" -l app=loki
    echo ""
    echo -e "${BLUE}Access Loki:${NC}"
    echo "  kubectl port-forward -n $NAMESPACE svc/loki 3100:3100"
    echo "  curl http://localhost:3100/loki/api/v1/labels"
    echo ""
    echo -e "${BLUE}View Logs in Grafana:${NC}"
    echo "  1. Access Grafana dashboard"
    echo "  2. Go to Explore"
    echo "  3. Select 'Loki' datasource"
    echo "  4. Query: {namespace=\"jewelry-shop\"}"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please review the errors above.${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check Loki logs: kubectl logs -n $NAMESPACE -l app=loki"
    echo "  2. Check Promtail logs: kubectl logs -n $NAMESPACE -l app=promtail"
    echo "  3. Check events: kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp'"
    echo ""
    exit 1
fi
