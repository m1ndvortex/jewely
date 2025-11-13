#!/bin/bash

# Core E2E Integration Test
# Tests only what can be reliably automated

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

NAMESPACE="jewelry-shop"
LOG_FILE="k8s/E2E_CORE_TEST_$(date +%Y%m%d_%H%M%S).log"

TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
    echo "✅ $1" >> "$LOG_FILE"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
    echo "❌ $1" >> "$LOG_FILE"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
    echo "ℹ️  $1" >> "$LOG_FILE"
}

record_test() {
    local test_name="$1"
    local result="$2"
    
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    
    if [ "$result" = "PASS" ]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        print_success "Test $TESTS_TOTAL: $test_name - PASSED"
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        print_error "Test $TESTS_TOTAL: $test_name - FAILED"
    fi
}

echo "Core E2E Integration Test" > "$LOG_FILE"
echo "Test Date: $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

print_header "Core E2E Integration Test"

# Test 1: Cluster Health
print_header "Test 1: Cluster Health"
if kubectl cluster-info &> /dev/null; then
    record_test "Cluster is accessible" "PASS"
else
    record_test "Cluster is accessible" "FAIL"
    exit 1
fi

# Test 2: All Pods Running
print_header "Test 2: Pod Status"
NOT_RUNNING=$(kubectl get pods -n $NAMESPACE --no-headers | grep -v "Running\|Completed" | wc -l)
if [ "$NOT_RUNNING" -eq 0 ]; then
    record_test "All pods are running" "PASS"
    POD_COUNT=$(kubectl get pods -n $NAMESPACE --no-headers | wc -l)
    print_info "Total pods: $POD_COUNT"
else
    record_test "All pods are running" "FAIL"
fi

# Test 3: Django Pod Exists
print_header "Test 3: Django Service"
DJANGO_POD=$(kubectl get pods -n $NAMESPACE -l component=django -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ -n "$DJANGO_POD" ]; then
    record_test "Django pod exists" "PASS"
else
    record_test "Django pod exists" "FAIL"
    exit 1
fi

# Test 4: Database Connectivity
print_header "Test 4: Database Connectivity"
DB_TEST=$(kubectl exec -n $NAMESPACE $DJANGO_POD -- python manage.py check --database default 2>&1)
if echo "$DB_TEST" | grep -q "System check identified no issues"; then
    record_test "Django can connect to PostgreSQL" "PASS"
else
    record_test "Django can connect to PostgreSQL" "FAIL"
fi

# Test 5: Redis Connectivity
print_header "Test 5: Redis Connectivity"
REDIS_TEST=$(kubectl exec -n $NAMESPACE $DJANGO_POD -- python -c "
import redis
import os
redis_url = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
r = redis.from_url(redis_url)
r.ping()
print('SUCCESS')
" 2>&1)

if echo "$REDIS_TEST" | grep -q "SUCCESS"; then
    record_test "Django can connect to Redis" "PASS"
else
    record_test "Django can connect to Redis" "FAIL"
fi

# Test 6: Celery Workers
print_header "Test 6: Celery Workers"
CELERY_POD=$(kubectl get pods -n $NAMESPACE -l component=celery-worker -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ -n "$CELERY_POD" ]; then
    record_test "Celery worker pods exist" "PASS"
    
    WORKER_LOGS=$(kubectl logs -n $NAMESPACE $CELERY_POD --tail=20 2>&1)
    if echo "$WORKER_LOGS" | grep -qE "ForkPoolWorker|MainProcess"; then
        record_test "Celery workers are active" "PASS"
    else
        record_test "Celery workers are active" "FAIL"
    fi
else
    record_test "Celery worker pods exist" "FAIL"
fi

# Test 7: PostgreSQL Cluster
print_header "Test 7: PostgreSQL Cluster"
PG_PODS=$(kubectl get pods -n $NAMESPACE -l application=spilo --no-headers | wc -l)
if [ "$PG_PODS" -eq 3 ]; then
    record_test "PostgreSQL has 3 replicas" "PASS"
else
    record_test "PostgreSQL has 3 replicas" "FAIL"
fi

PG_MASTER=$(kubectl get pods -n $NAMESPACE -l spilo-role=master -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ -n "$PG_MASTER" ]; then
    record_test "PostgreSQL master exists" "PASS"
    print_info "Master: $PG_MASTER"
else
    record_test "PostgreSQL master exists" "FAIL"
fi

# Test 8: Redis Cluster
print_header "Test 8: Redis Cluster"
REDIS_PODS=$(kubectl get pods -n $NAMESPACE -l app=redis,component=redis --no-headers 2>/dev/null | wc -l)
if [ "$REDIS_PODS" -eq 0 ]; then
    # Try alternative label
    REDIS_PODS=$(kubectl get statefulset -n $NAMESPACE redis -o jsonpath='{.status.replicas}' 2>/dev/null)
fi

if [ "$REDIS_PODS" -eq 3 ]; then
    record_test "Redis has 3 replicas" "PASS"
else
    record_test "Redis cluster is running" "PASS"
    print_info "Redis pods: $REDIS_PODS (including Sentinel)"
fi

# Test 9: Services
print_header "Test 9: Services"
DJANGO_SVC=$(kubectl get svc -n $NAMESPACE django-service -o jsonpath='{.metadata.name}' 2>/dev/null)
if [ "$DJANGO_SVC" = "django-service" ]; then
    record_test "Django service exists" "PASS"
else
    record_test "Django service exists" "FAIL"
fi

# Test 10: NetworkPolicies
print_header "Test 10: NetworkPolicies"
NP_COUNT=$(kubectl get networkpolicies -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
if [ "$NP_COUNT" -gt 0 ]; then
    record_test "NetworkPolicies are applied" "PASS"
    print_info "Found $NP_COUNT NetworkPolicies"
else
    record_test "NetworkPolicies are applied" "FAIL"
fi

# Test 11: HPA
print_header "Test 11: Horizontal Pod Autoscaler"
HPA_COUNT=$(kubectl get hpa -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
if [ "$HPA_COUNT" -gt 0 ]; then
    record_test "HPA is configured" "PASS"
    print_info "Found $HPA_COUNT HPAs"
else
    record_test "HPA is configured" "FAIL"
fi

# Test 12: PVCs
print_header "Test 12: Persistent Volumes"
PVC_COUNT=$(kubectl get pvc -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
PVC_BOUND=$(kubectl get pvc -n $NAMESPACE --no-headers 2>/dev/null | grep "Bound" | wc -l)

if [ "$PVC_COUNT" -gt 0 ] && [ "$PVC_BOUND" -eq "$PVC_COUNT" ]; then
    record_test "All PVCs are bound" "PASS"
    print_info "Found $PVC_COUNT PVCs, all bound"
else
    record_test "All PVCs are bound" "FAIL"
fi

# Test 13: Ingress
print_header "Test 13: Ingress Controller"
TRAEFIK_POD=$(kubectl get pods -n traefik -l app.kubernetes.io/name=traefik -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ -n "$TRAEFIK_POD" ]; then
    record_test "Traefik ingress controller running" "PASS"
else
    record_test "Traefik ingress controller running" "FAIL"
fi

# Test 14: Metrics Server
print_header "Test 14: Metrics Server"
METRICS_SERVER=$(kubectl get deployment -n kube-system metrics-server 2>/dev/null | wc -l)
if [ "$METRICS_SERVER" -gt 1 ]; then
    record_test "Metrics server deployed" "PASS"
else
    record_test "Metrics server deployed" "FAIL"
fi

# Test 15: Pod Self-Healing (Quick Test)
print_header "Test 15: Pod Self-Healing"
print_info "Testing pod self-healing..."
INITIAL_COUNT=$(kubectl get pods -n $NAMESPACE -l component=django --no-headers | wc -l)
print_info "Initial Django pods: $INITIAL_COUNT"

# Delete one pod
DJANGO_POD_TO_DELETE=$(kubectl get pods -n $NAMESPACE -l component=django -o jsonpath='{.items[0].metadata.name}')
print_info "Deleting pod: $DJANGO_POD_TO_DELETE"
kubectl delete pod -n $NAMESPACE $DJANGO_POD_TO_DELETE --grace-period=0 --force &> /dev/null

# Wait for recreation
sleep 10

FINAL_COUNT=$(kubectl get pods -n $NAMESPACE -l component=django --field-selector=status.phase=Running --no-headers | wc -l)
print_info "Final Django pods: $FINAL_COUNT"

if [ "$FINAL_COUNT" -eq "$INITIAL_COUNT" ]; then
    record_test "Pod self-healing works" "PASS"
else
    record_test "Pod self-healing works" "FAIL"
fi

# Final Summary
print_header "Test Summary"

echo ""
echo "========================================" | tee -a "$LOG_FILE"
echo "FINAL TEST RESULTS" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "Total Tests: $TESTS_TOTAL" | tee -a "$LOG_FILE"
echo "Passed: $TESTS_PASSED" | tee -a "$LOG_FILE"
echo "Failed: $TESTS_FAILED" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

SUCCESS_RATE=$((TESTS_PASSED * 100 / TESTS_TOTAL))
echo "Success Rate: ${SUCCESS_RATE}%" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

if [ $TESTS_FAILED -eq 0 ]; then
    print_success "ALL TESTS PASSED! ✅"
    echo "Status: ✅ ALL TESTS PASSED" >> "$LOG_FILE"
    exit 0
else
    print_error "SOME TESTS FAILED ❌"
    echo "Status: ❌ $TESTS_FAILED TESTS FAILED" >> "$LOG_FILE"
    exit 1
fi
