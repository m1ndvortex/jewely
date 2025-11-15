#!/bin/bash

# Comprehensive Grafana Testing Script
# Task: 35.2 - Deploy Grafana
# Requirement: 24 - Monitoring and Observability

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

NAMESPACE="jewelry-shop"
TEST_FAILED=0
TEST_PASSED=0
TEST_TOTAL=0

# Logging
LOG_FILE="TASK_35.2_TEST_RESULTS_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE")
exec 2>&1

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Grafana Comprehensive Testing${NC}"
echo -e "${BLUE}Task: 35.2 - Deploy Grafana${NC}"
echo -e "${BLUE}Requirement: 24 - Monitoring and Observability${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Test started at: $(date)"
echo "Log file: $LOG_FILE"
echo ""

# Test function
run_test() {
    local test_name=$1
    local test_command=$2
    
    TEST_TOTAL=$((TEST_TOTAL + 1))
    echo -e "${YELLOW}[TEST $TEST_TOTAL] $test_name${NC}"
    
    if eval "$test_command"; then
        echo -e "${GREEN}✓ PASS${NC}"
        TEST_PASSED=$((TEST_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        TEST_FAILED=$((TEST_FAILED + 1))
        return 1
    fi
    echo ""
}

echo -e "${BLUE}=== Phase 1: Pre-Installation Checks ===${NC}"
echo ""

# Check namespace exists
run_test "Namespace 'jewelry-shop' exists" \
    "kubectl get namespace $NAMESPACE &>/dev/null"

# Check if Prometheus is running (recommended)
if kubectl get deployment prometheus -n "$NAMESPACE" &>/dev/null; then
    run_test "Prometheus deployment exists" "true"
else
    echo -e "${YELLOW}⚠ Warning: Prometheus not found (recommended but not required)${NC}"
fi

echo -e "${BLUE}=== Phase 2: Installation ===${NC}"
echo ""

# Install Grafana
run_test "Install Grafana using script" \
    "bash k8s/grafana/install-grafana.sh"

echo -e "${BLUE}=== Phase 3: Resource Verification ===${NC}"
echo ""

# Check deployment
run_test "Grafana deployment exists" \
    "kubectl get deployment grafana -n $NAMESPACE &>/dev/null"

# Check service
run_test "Grafana service exists" \
    "kubectl get svc grafana -n $NAMESPACE &>/dev/null"

# Check PVC
run_test "Grafana PVC exists and is Bound" \
    "[[ \$(kubectl get pvc grafana-storage -n $NAMESPACE -o jsonpath='{.status.phase}' 2>/dev/null) == 'Bound' ]]"

# Check secrets
run_test "Grafana secrets exist" \
    "kubectl get secret grafana-secrets -n $NAMESPACE &>/dev/null"

# Check ConfigMaps
run_test "Grafana config ConfigMap exists" \
    "kubectl get configmap grafana-config -n $NAMESPACE &>/dev/null"

run_test "Grafana datasources ConfigMap exists" \
    "kubectl get configmap grafana-datasources -n $NAMESPACE &>/dev/null"

run_test "Grafana dashboards config ConfigMap exists" \
    "kubectl get configmap grafana-dashboards-config -n $NAMESPACE &>/dev/null"

# Check dashboard ConfigMaps
run_test "System Overview dashboard ConfigMap exists" \
    "kubectl get configmap grafana-dashboard-system-overview -n $NAMESPACE &>/dev/null"

run_test "Application Performance dashboard ConfigMap exists" \
    "kubectl get configmap grafana-dashboard-application-performance -n $NAMESPACE &>/dev/null"

run_test "Database Performance dashboard ConfigMap exists" \
    "kubectl get configmap grafana-dashboard-database-performance -n $NAMESPACE &>/dev/null"

run_test "Infrastructure Health dashboard ConfigMap exists" \
    "kubectl get configmap grafana-dashboard-infrastructure-health -n $NAMESPACE &>/dev/null"

echo -e "${BLUE}=== Phase 4: Pod Health Checks ===${NC}"
echo ""

# Wait for pod to be ready
echo "Waiting for Grafana pod to be ready (timeout: 300s)..."
if kubectl wait --for=condition=ready pod -l app=grafana -n "$NAMESPACE" --timeout=300s; then
    run_test "Grafana pod is Ready" "true"
else
    run_test "Grafana pod is Ready" "false"
fi

# Get pod name
POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l app=grafana -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [ -n "$POD_NAME" ]; then
    # Check pod status
    run_test "Grafana pod is Running" \
        "[[ \$(kubectl get pod $POD_NAME -n $NAMESPACE -o jsonpath='{.status.phase}') == 'Running' ]]"
    
    # Check container status
    run_test "Grafana container is ready" \
        "[[ \$(kubectl get pod $POD_NAME -n $NAMESPACE -o jsonpath='{.status.containerStatuses[0].ready}') == 'true' ]]"
    
    # Check restart count
    RESTART_COUNT=$(kubectl get pod $POD_NAME -n $NAMESPACE -o jsonpath='{.status.containerStatuses[0].restartCount}')
    run_test "Grafana container has not restarted (count: $RESTART_COUNT)" \
        "[[ $RESTART_COUNT -eq 0 ]]"
fi

echo -e "${BLUE}=== Phase 5: HTTP Health Checks ===${NC}"
echo ""

if [ -n "$POD_NAME" ]; then
    # Test health endpoint
    run_test "Grafana /api/health endpoint responds" \
        "kubectl exec -n $NAMESPACE $POD_NAME -- wget -q -O - http://localhost:3000/api/health &>/dev/null"
    
    # Test health endpoint returns 200
    HTTP_CODE=$(kubectl exec -n $NAMESPACE $POD_NAME -- wget -q -O /dev/null -S http://localhost:3000/api/health 2>&1 | grep "HTTP/" | awk '{print $2}' || echo "000")
    run_test "Grafana health endpoint returns HTTP 200 (got: $HTTP_CODE)" \
        "[[ $HTTP_CODE == '200' ]]"
    
    # Test main page
    run_test "Grafana main page is accessible" \
        "kubectl exec -n $NAMESPACE $POD_NAME -- wget -q -O /dev/null http://localhost:3000/ &>/dev/null"
fi

echo -e "${BLUE}=== Phase 6: Prometheus Data Source Verification ===${NC}"
echo ""

if [ -n "$POD_NAME" ]; then
    # Wait for Grafana to initialize
    echo "Waiting 10 seconds for Grafana to fully initialize..."
    sleep 10
    
    # Check if Prometheus data source exists
    run_test "Prometheus data source is configured" \
        "kubectl exec -n $NAMESPACE $POD_NAME -- wget -q -O - http://localhost:3000/api/datasources 2>/dev/null | grep -q 'Prometheus'"
    
    # Check if Prometheus service exists
    if kubectl get svc prometheus -n "$NAMESPACE" &>/dev/null; then
        run_test "Prometheus service exists" "true"
        
        # Test connectivity from Grafana to Prometheus
        run_test "Grafana can reach Prometheus service" \
            "kubectl exec -n $NAMESPACE $POD_NAME -- wget -q -O /dev/null -T 5 http://prometheus:9090/-/healthy 2>/dev/null"
    else
        echo -e "${YELLOW}⚠ Prometheus service not found (expected if not deployed)${NC}"
    fi
fi

echo -e "${BLUE}=== Phase 7: Dashboard Verification ===${NC}"
echo ""

if [ -n "$POD_NAME" ]; then
    # Check if dashboard files are mounted
    run_test "Dashboard directory exists" \
        "kubectl exec -n $NAMESPACE $POD_NAME -- test -d /var/lib/grafana/dashboards/jewelry-shop"
    
    # Count dashboard files
    DASHBOARD_COUNT=$(kubectl exec -n $NAMESPACE $POD_NAME -- sh -c "ls -1 /var/lib/grafana/dashboards/jewelry-shop/*.json 2>/dev/null | wc -l" || echo "0")
    run_test "All 4 dashboard files are present (found: $DASHBOARD_COUNT)" \
        "[[ $DASHBOARD_COUNT -ge 4 ]]"
    
    # List dashboard files
    echo "Dashboard files found:"
    kubectl exec -n $NAMESPACE $POD_NAME -- ls -lh /var/lib/grafana/dashboards/jewelry-shop/ 2>/dev/null || echo "  (none)"
    echo ""
fi

echo -e "${BLUE}=== Phase 8: Storage Verification ===${NC}"
echo ""

# Check PVC capacity
PVC_CAPACITY=$(kubectl get pvc grafana-storage -n $NAMESPACE -o jsonpath='{.status.capacity.storage}' 2>/dev/null || echo "unknown")
run_test "PVC has correct capacity (expected: 10Gi, got: $PVC_CAPACITY)" \
    "[[ $PVC_CAPACITY == '10Gi' ]]"

# Check PVC access mode
PVC_ACCESS=$(kubectl get pvc grafana-storage -n $NAMESPACE -o jsonpath='{.status.accessModes[0]}' 2>/dev/null || echo "unknown")
run_test "PVC has ReadWriteOnce access mode (got: $PVC_ACCESS)" \
    "[[ $PVC_ACCESS == 'ReadWriteOnce' ]]"

echo -e "${BLUE}=== Phase 9: Resource Limits Verification ===${NC}"
echo ""

# Check CPU requests
CPU_REQUEST=$(kubectl get deployment grafana -n $NAMESPACE -o jsonpath='{.spec.template.spec.containers[0].resources.requests.cpu}' 2>/dev/null || echo "unknown")
run_test "CPU request is set (got: $CPU_REQUEST)" \
    "[[ $CPU_REQUEST == '250m' ]]"

# Check CPU limits
CPU_LIMIT=$(kubectl get deployment grafana -n $NAMESPACE -o jsonpath='{.spec.template.spec.containers[0].resources.limits.cpu}' 2>/dev/null || echo "unknown")
run_test "CPU limit is set (got: $CPU_LIMIT)" \
    "[[ $CPU_LIMIT == '1000m' || $CPU_LIMIT == '1' ]]"

# Check memory requests
MEM_REQUEST=$(kubectl get deployment grafana -n $NAMESPACE -o jsonpath='{.spec.template.spec.containers[0].resources.requests.memory}' 2>/dev/null || echo "unknown")
run_test "Memory request is set (got: $MEM_REQUEST)" \
    "[[ $MEM_REQUEST == '512Mi' ]]"

# Check memory limits
MEM_LIMIT=$(kubectl get deployment grafana -n $NAMESPACE -o jsonpath='{.spec.template.spec.containers[0].resources.limits.memory}' 2>/dev/null || echo "unknown")
run_test "Memory limit is set (got: $MEM_LIMIT)" \
    "[[ $MEM_LIMIT == '2Gi' ]]"

echo -e "${BLUE}=== Phase 10: Security Verification ===${NC}"
echo ""

# Check security context
RUN_AS_USER=$(kubectl get deployment grafana -n $NAMESPACE -o jsonpath='{.spec.template.spec.securityContext.runAsUser}' 2>/dev/null || echo "unknown")
run_test "Pod runs as non-root user (UID: $RUN_AS_USER)" \
    "[[ $RUN_AS_USER == '472' ]]"

# Check if secrets are properly mounted
if [ -n "$POD_NAME" ]; then
    run_test "Admin password secret is mounted" \
        "kubectl exec -n $NAMESPACE $POD_NAME -- env | grep -q 'GF_SECURITY_ADMIN_PASSWORD'"
fi

echo -e "${BLUE}=== Phase 11: Log Analysis ===${NC}"
echo ""

if [ -n "$POD_NAME" ]; then
    # Check for errors in logs
    ERROR_COUNT=$(kubectl logs $POD_NAME -n $NAMESPACE --tail=200 2>/dev/null | grep -i "error\|fatal\|panic" | grep -v "level=info" | wc -l || echo "0")
    run_test "No critical errors in logs (found: $ERROR_COUNT)" \
        "[[ $ERROR_COUNT -eq 0 ]]"
    
    if [ $ERROR_COUNT -gt 0 ]; then
        echo "Recent errors found:"
        kubectl logs $POD_NAME -n $NAMESPACE --tail=200 | grep -i "error\|fatal\|panic" | grep -v "level=info" | tail -10
        echo ""
    fi
fi

echo -e "${BLUE}=== Phase 12: Service Connectivity ===${NC}"
echo ""

# Check service type
SVC_TYPE=$(kubectl get svc grafana -n $NAMESPACE -o jsonpath='{.spec.type}' 2>/dev/null || echo "unknown")
run_test "Service type is ClusterIP (got: $SVC_TYPE)" \
    "[[ $SVC_TYPE == 'ClusterIP' ]]"

# Check service port
SVC_PORT=$(kubectl get svc grafana -n $NAMESPACE -o jsonpath='{.spec.ports[0].port}' 2>/dev/null || echo "unknown")
run_test "Service port is 3000 (got: $SVC_PORT)" \
    "[[ $SVC_PORT == '3000' ]]"

# Check service has endpoints
ENDPOINTS=$(kubectl get endpoints grafana -n $NAMESPACE -o jsonpath='{.subsets[0].addresses[0].ip}' 2>/dev/null || echo "")
run_test "Service has endpoints" \
    "[[ -n $ENDPOINTS ]]"

echo -e "${BLUE}=== Phase 13: Requirement 24 Verification ===${NC}"
echo ""

echo "Verifying Requirement 24 Acceptance Criteria:"
echo ""

# Criterion 6: Provide Grafana dashboards
echo "Criterion 6: THE System SHALL provide Grafana dashboards for:"
run_test "  - System overview dashboard" \
    "kubectl get configmap grafana-dashboard-system-overview -n $NAMESPACE &>/dev/null"

run_test "  - Application performance dashboard" \
    "kubectl get configmap grafana-dashboard-application-performance -n $NAMESPACE &>/dev/null"

run_test "  - Database performance dashboard" \
    "kubectl get configmap grafana-dashboard-database-performance -n $NAMESPACE &>/dev/null"

run_test "  - Infrastructure health dashboard" \
    "kubectl get configmap grafana-dashboard-infrastructure-health -n $NAMESPACE &>/dev/null"

echo -e "${BLUE}=== Phase 14: Integration Testing ===${NC}"
echo ""

if [ -n "$POD_NAME" ]; then
    # Test port-forward capability
    echo "Testing port-forward capability..."
    kubectl port-forward -n $NAMESPACE svc/grafana 13000:3000 &
    PF_PID=$!
    sleep 5
    
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:13000/api/health | grep -q "200"; then
        run_test "Port-forward to Grafana works" "true"
    else
        run_test "Port-forward to Grafana works" "false"
    fi
    
    kill $PF_PID 2>/dev/null || true
    sleep 2
fi

echo -e "${BLUE}=== Phase 15: Performance Check ===${NC}"
echo ""

if command -v kubectl &>/dev/null && kubectl top pod $POD_NAME -n $NAMESPACE &>/dev/null 2>&1; then
    echo "Current resource usage:"
    kubectl top pod $POD_NAME -n $NAMESPACE
    echo ""
    
    # Check if CPU usage is reasonable
    CPU_USAGE=$(kubectl top pod $POD_NAME -n $NAMESPACE --no-headers | awk '{print $2}' | sed 's/m//')
    if [ -n "$CPU_USAGE" ] && [ "$CPU_USAGE" -lt 1000 ]; then
        run_test "CPU usage is within limits (<1000m, current: ${CPU_USAGE}m)" "true"
    else
        echo -e "${YELLOW}⚠ Metrics server not available or CPU usage high${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Metrics server not available (kubectl top not working)${NC}"
fi

echo -e "${BLUE}=== Test Summary ===${NC}"
echo ""
echo "Total Tests: $TEST_TOTAL"
echo -e "${GREEN}Passed: $TEST_PASSED${NC}"
echo -e "${RED}Failed: $TEST_FAILED${NC}"
echo ""

if [ $TEST_FAILED -eq 0 ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ ALL TESTS PASSED!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Grafana is successfully deployed and operational!"
    echo ""
    echo "Access Grafana:"
    echo "  kubectl port-forward -n $NAMESPACE svc/grafana 3000:3000"
    echo "  Open: http://localhost:3000"
    echo "  Username: admin"
    echo "  Password: admin123!@#"
    echo ""
    exit 0
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}✗ SOME TESTS FAILED${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo "Please review the failures above and check:"
    echo "  - Pod logs: kubectl logs -n $NAMESPACE -l app=grafana"
    echo "  - Pod events: kubectl describe pod -n $NAMESPACE -l app=grafana"
    echo "  - Service status: kubectl get svc grafana -n $NAMESPACE"
    echo ""
    exit 1
fi
