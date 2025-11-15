#!/bin/bash

# Comprehensive Alertmanager Testing Script
# Per Requirement 24 - Test alert rules and routing

set -e

echo "========================================="
echo "Alertmanager Comprehensive Testing"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

FAILED=0
PASSED=0

# Function to check status
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        ((FAILED++))
        return 1
    fi
}

# Get pod names
PROMETHEUS_POD=$(kubectl get pods -n jewelry-shop -l app=prometheus -o jsonpath='{.items[0].metadata.name}')
ALERTMANAGER_POD=$(kubectl get pods -n jewelry-shop -l app=alertmanager -o jsonpath='{.items[0].metadata.name}')

if [ -z "$PROMETHEUS_POD" ]; then
    echo -e "${RED}Error: Prometheus pod not found${NC}"
    exit 1
fi

if [ -z "$ALERTMANAGER_POD" ]; then
    echo -e "${RED}Error: Alertmanager pod not found${NC}"
    exit 1
fi

echo "Using Prometheus pod: $PROMETHEUS_POD"
echo "Using Alertmanager pod: $ALERTMANAGER_POD"
echo ""

# Test 1: Verify Alertmanager is registered in Prometheus
echo "Test 1: Verifying Alertmanager registration in Prometheus..."
kubectl exec -n jewelry-shop $PROMETHEUS_POD -- wget -q -O- http://localhost:9090/api/v1/alertmanagers | grep -q "alertmanager"
check_status
echo ""

# Test 2: Check alert rules are loaded
echo "Test 2: Checking if alert rules are loaded..."
RULES_OUTPUT=$(kubectl exec -n jewelry-shop $PROMETHEUS_POD -- wget -q -O- http://localhost:9090/api/v1/rules)
echo "$RULES_OUTPUT" | grep -q '"groups"'
check_status

if [ $? -eq 0 ]; then
    echo "Alert rule groups found:"
    echo "$RULES_OUTPUT" | grep -o '"name":"[^"]*"' | head -10
fi
echo ""

# Test 3: Check specific alert rules exist
echo "Test 3: Verifying specific alert rules..."
echo "  - Checking for infrastructure alerts..."
echo "$RULES_OUTPUT" | grep -q '"name":"infrastructure"'
check_status

echo "  - Checking for database alerts..."
echo "$RULES_OUTPUT" | grep -q '"name":"database"'
check_status

echo "  - Checking for application alerts..."
echo "$RULES_OUTPUT" | grep -q '"name":"application"'
check_status
echo ""

# Test 4: Check Alertmanager configuration
echo "Test 4: Checking Alertmanager configuration..."
ALERTMANAGER_CONFIG=$(kubectl exec -n jewelry-shop $ALERTMANAGER_POD -- wget -q -O- http://localhost:9093/api/v2/status)
echo "$ALERTMANAGER_CONFIG" | grep -q "config"
check_status
echo ""

# Test 5: Check alert receivers are configured
echo "Test 5: Verifying alert receivers..."
kubectl get configmap -n jewelry-shop alertmanager-config -o yaml | grep -q "critical-alerts"
check_status

kubectl get configmap -n jewelry-shop alertmanager-config -o yaml | grep -q "database-team"
check_status

kubectl get configmap -n jewelry-shop alertmanager-config -o yaml | grep -q "infrastructure-team"
check_status
echo ""

# Test 6: Check inhibition rules
echo "Test 6: Checking inhibition rules..."
kubectl get configmap -n jewelry-shop alertmanager-config -o yaml | grep -q "inhibit_rules"
check_status
echo ""

# Test 7: Verify Alertmanager cluster mode
echo "Test 7: Verifying Alertmanager cluster configuration..."
kubectl exec -n jewelry-shop $ALERTMANAGER_POD -- wget -q -O- http://localhost:9093/api/v2/status | grep -q "cluster"
check_status
echo ""

# Test 8: Check if secrets are mounted
echo "Test 8: Checking if secrets are properly mounted..."
kubectl exec -n jewelry-shop $ALERTMANAGER_POD -- env | grep -q "SMTP_PASSWORD"
check_status

kubectl exec -n jewelry-shop $ALERTMANAGER_POD -- env | grep -q "SLACK_WEBHOOK_URL"
check_status

kubectl exec -n jewelry-shop $ALERTMANAGER_POD -- env | grep -q "PAGERDUTY_SERVICE_KEY"
check_status
echo ""

# Test 9: Trigger a test alert
echo "Test 9: Triggering a test alert..."
echo "Creating a test alert rule..."

# Create a temporary alert rule that will fire immediately
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-test-alert
  namespace: jewelry-shop
data:
  test-alert.yml: |
    groups:
      - name: test
        interval: 10s
        rules:
          - alert: TestAlert
            expr: vector(1)
            for: 0s
            labels:
              severity: warning
              component: test
              service: test
            annotations:
              summary: "This is a test alert"
              description: "This alert is used for testing Alertmanager integration"
EOF

echo "Waiting for alert to fire (30 seconds)..."
sleep 30

# Check if alert is firing
ALERTS=$(kubectl exec -n jewelry-shop $PROMETHEUS_POD -- wget -q -O- http://localhost:9090/api/v1/alerts)
echo "$ALERTS" | grep -q "TestAlert"
check_status

if [ $? -eq 0 ]; then
    echo "Test alert is firing in Prometheus"
fi
echo ""

# Test 10: Check if alert reached Alertmanager
echo "Test 10: Checking if alert reached Alertmanager..."
sleep 10
ALERTMANAGER_ALERTS=$(kubectl exec -n jewelry-shop $ALERTMANAGER_POD -- wget -q -O- http://localhost:9093/api/v2/alerts)
echo "$ALERTMANAGER_ALERTS" | grep -q "TestAlert"
check_status

if [ $? -eq 0 ]; then
    echo "Test alert received by Alertmanager"
fi
echo ""

# Test 11: Check alert routing
echo "Test 11: Verifying alert routing configuration..."
kubectl get configmap -n jewelry-shop alertmanager-config -o yaml | grep -q "route:"
check_status

kubectl get configmap -n jewelry-shop alertmanager-config -o yaml | grep -q "group_by:"
check_status
echo ""

# Test 12: Verify email configuration
echo "Test 12: Checking email notification configuration..."
kubectl get configmap -n jewelry-shop alertmanager-config -o yaml | grep -q "email_configs:"
check_status

kubectl get configmap -n jewelry-shop alertmanager-config -o yaml | grep -q "smtp_smarthost:"
check_status
echo ""

# Test 13: Verify Slack configuration
echo "Test 13: Checking Slack notification configuration..."
kubectl get configmap -n jewelry-shop alertmanager-config -o yaml | grep -q "slack_configs:"
check_status

kubectl get configmap -n jewelry-shop alertmanager-config -o yaml | grep -q "slack_api_url:"
check_status
echo ""

# Test 14: Verify PagerDuty configuration
echo "Test 14: Checking PagerDuty notification configuration..."
kubectl get configmap -n jewelry-shop alertmanager-config -o yaml | grep -q "pagerduty_configs:"
check_status

kubectl get configmap -n jewelry-shop alertmanager-config -o yaml | grep -q "pagerduty_url:"
check_status
echo ""

# Test 15: Check webhook configuration for SMS
echo "Test 15: Checking webhook configuration for SMS..."
kubectl get configmap -n jewelry-shop alertmanager-config -o yaml | grep -q "webhook_configs:"
check_status
echo ""

# Cleanup test alert
echo "Cleaning up test alert..."
kubectl delete configmap prometheus-test-alert -n jewelry-shop --ignore-not-found=true
echo ""

# Display detailed status
echo "========================================="
echo "Detailed Status"
echo "========================================="
echo ""

echo -e "${BLUE}Alertmanager Pods:${NC}"
kubectl get pods -n jewelry-shop -l app=alertmanager -o wide
echo ""

echo -e "${BLUE}Alertmanager Services:${NC}"
kubectl get svc -n jewelry-shop -l app=alertmanager
echo ""

echo -e "${BLUE}Active Alerts in Prometheus:${NC}"
kubectl exec -n jewelry-shop $PROMETHEUS_POD -- wget -q -O- http://localhost:9090/api/v1/alerts | grep -o '"alertname":"[^"]*"' | sort | uniq
echo ""

echo -e "${BLUE}Alerts in Alertmanager:${NC}"
kubectl exec -n jewelry-shop $ALERTMANAGER_POD -- wget -q -O- http://localhost:9093/api/v2/alerts | grep -o '"name":"[^"]*"' | sort | uniq
echo ""

echo -e "${BLUE}Alert Rule Groups:${NC}"
kubectl exec -n jewelry-shop $PROMETHEUS_POD -- wget -q -O- http://localhost:9090/api/v1/rules | grep -o '"name":"[^"]*"' | sort | uniq
echo ""

# Display summary
echo "========================================="
echo "Test Summary"
echo "========================================="
echo ""
echo -e "Tests Passed: ${GREEN}$PASSED${NC}"
echo -e "Tests Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed successfully!${NC}"
    echo ""
    echo "Alertmanager is properly configured and working."
    echo ""
    echo "Access UIs:"
    echo "  Alertmanager: kubectl port-forward -n jewelry-shop svc/alertmanager 9093:9093"
    echo "  Prometheus:   kubectl port-forward -n jewelry-shop svc/prometheus 9090:9090"
    echo ""
    echo "View alerts:"
    echo "  Prometheus alerts: http://localhost:9090/alerts"
    echo "  Alertmanager UI:   http://localhost:9093"
    echo ""
    exit 0
else
    echo -e "${RED}Some tests failed. Please review the output above.${NC}"
    echo ""
    echo "Check logs:"
    echo "  kubectl logs -n jewelry-shop -l app=alertmanager"
    echo "  kubectl logs -n jewelry-shop -l app=prometheus"
    echo ""
    exit 1
fi
