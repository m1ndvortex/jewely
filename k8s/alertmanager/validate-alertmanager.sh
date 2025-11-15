#!/bin/bash

# Alertmanager Validation Script for Jewelry SaaS Platform
# Per Requirement 24 - Validate alerting configuration

set -e

echo "========================================="
echo "Alertmanager Validation"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FAILED=0
PASSED=0

# Function to check status
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC}"
        ((FAILED++))
    fi
}

# Test 1: Check if Alertmanager pods are running
echo "Test 1: Checking Alertmanager pods..."
kubectl get pods -n jewelry-shop -l app=alertmanager | grep -q "Running"
check_status
echo ""

# Test 2: Check if Alertmanager service exists
echo "Test 2: Checking Alertmanager service..."
kubectl get svc -n jewelry-shop alertmanager &> /dev/null
check_status
echo ""

# Test 3: Check if ConfigMap exists
echo "Test 3: Checking Alertmanager ConfigMap..."
kubectl get configmap -n jewelry-shop alertmanager-config &> /dev/null
check_status
echo ""

# Test 4: Check if secrets exist
echo "Test 4: Checking Alertmanager secrets..."
kubectl get secret -n jewelry-shop alertmanager-secrets &> /dev/null
check_status
echo ""

# Test 5: Check if alert rules ConfigMap exists
echo "Test 5: Checking Prometheus alert rules..."
kubectl get configmap -n jewelry-shop prometheus-alert-rules &> /dev/null
check_status
echo ""

# Test 6: Check Alertmanager health endpoint
echo "Test 6: Checking Alertmanager health..."
ALERTMANAGER_POD=$(kubectl get pods -n jewelry-shop -l app=alertmanager -o jsonpath='{.items[0].metadata.name}')
if [ -n "$ALERTMANAGER_POD" ]; then
    kubectl exec -n jewelry-shop $ALERTMANAGER_POD -- wget -q -O- http://localhost:9093/-/healthy | grep -q "Healthy"
    check_status
else
    echo -e "${RED}✗ FAIL - No Alertmanager pod found${NC}"
    ((FAILED++))
fi
echo ""

# Test 7: Check if Prometheus can reach Alertmanager
echo "Test 7: Checking Prometheus to Alertmanager connectivity..."
PROMETHEUS_POD=$(kubectl get pods -n jewelry-shop -l app=prometheus -o jsonpath='{.items[0].metadata.name}')
if [ -n "$PROMETHEUS_POD" ]; then
    kubectl exec -n jewelry-shop $PROMETHEUS_POD -- wget -q -O- http://alertmanager.jewelry-shop.svc.cluster.local:9093/-/healthy | grep -q "Healthy"
    check_status
else
    echo -e "${RED}✗ FAIL - No Prometheus pod found${NC}"
    ((FAILED++))
fi
echo ""

# Test 8: Check if alert rules are loaded in Prometheus
echo "Test 8: Checking if alert rules are loaded..."
if [ -n "$PROMETHEUS_POD" ]; then
    RULES_COUNT=$(kubectl exec -n jewelry-shop $PROMETHEUS_POD -- wget -q -O- http://localhost:9090/api/v1/rules | grep -o '"groups":\[' | wc -l)
    if [ "$RULES_COUNT" -gt 0 ]; then
        echo -e "${GREEN}✓ PASS - Found alert rule groups${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAIL - No alert rules loaded${NC}"
        ((FAILED++))
    fi
else
    echo -e "${RED}✗ FAIL - No Prometheus pod found${NC}"
    ((FAILED++))
fi
echo ""

# Test 9: Check Alertmanager cluster status
echo "Test 9: Checking Alertmanager cluster status..."
if [ -n "$ALERTMANAGER_POD" ]; then
    kubectl exec -n jewelry-shop $ALERTMANAGER_POD -- wget -q -O- http://localhost:9093/api/v2/status | grep -q "cluster"
    check_status
else
    echo -e "${RED}✗ FAIL - No Alertmanager pod found${NC}"
    ((FAILED++))
fi
echo ""

# Test 10: Check if Alertmanager configuration is valid
echo "Test 10: Checking Alertmanager configuration validity..."
if [ -n "$ALERTMANAGER_POD" ]; then
    kubectl logs -n jewelry-shop $ALERTMANAGER_POD --tail=50 | grep -q "Completed loading of configuration file"
    check_status
else
    echo -e "${RED}✗ FAIL - No Alertmanager pod found${NC}"
    ((FAILED++))
fi
echo ""

# Display detailed information
echo "========================================="
echo "Detailed Information"
echo "========================================="
echo ""

echo "Alertmanager Pods:"
kubectl get pods -n jewelry-shop -l app=alertmanager -o wide
echo ""

echo "Alertmanager Services:"
kubectl get svc -n jewelry-shop -l app=alertmanager
echo ""

echo "Alert Rules Summary:"
if [ -n "$PROMETHEUS_POD" ]; then
    kubectl exec -n jewelry-shop $PROMETHEUS_POD -- wget -q -O- http://localhost:9090/api/v1/rules | grep -o '"name":"[^"]*"' | head -10
fi
echo ""

echo "Active Alerts:"
if [ -n "$PROMETHEUS_POD" ]; then
    kubectl exec -n jewelry-shop $PROMETHEUS_POD -- wget -q -O- http://localhost:9090/api/v1/alerts | grep -o '"alertname":"[^"]*"' | head -10
fi
echo ""

# Display summary
echo "========================================="
echo "Validation Summary"
echo "========================================="
echo ""
echo -e "Tests Passed: ${GREEN}$PASSED${NC}"
echo -e "Tests Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All validation tests passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Access Alertmanager UI:"
    echo "   kubectl port-forward -n jewelry-shop svc/alertmanager 9093:9093"
    echo "   Open http://localhost:9093"
    echo ""
    echo "2. View alerts in Prometheus:"
    echo "   kubectl port-forward -n jewelry-shop svc/prometheus 9090:9090"
    echo "   Open http://localhost:9090/alerts"
    echo ""
    echo "3. Test alert by triggering a test alert:"
    echo "   Run: ./test-alertmanager-comprehensive.sh"
    echo ""
    exit 0
else
    echo -e "${RED}Some validation tests failed. Please check the logs:${NC}"
    echo "  kubectl logs -n jewelry-shop -l app=alertmanager"
    echo "  kubectl logs -n jewelry-shop -l app=prometheus"
    echo ""
    exit 1
fi
