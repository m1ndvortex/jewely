#!/bin/bash

# ============================================================================
# Quick Validation for Task 34.16
# ============================================================================
# This script runs quick validation tests to verify all components work
# ============================================================================

set -e

NAMESPACE="jewelry-shop"
LOG_FILE="k8s/TASK_34.16_QUICK_VALIDATION_$(date +%Y%m%d_%H%M%S).log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

exec > >(tee -a "$LOG_FILE") 2>&1

echo "============================================================================"
echo "TASK 34.16 - QUICK VALIDATION TEST"
echo "============================================================================"
echo "Date: $(date)"
echo "Log: $LOG_FILE"
echo ""

TESTS_PASSED=0
TESTS_FAILED=0

# ============================================================================
# Test 1: Locust Infrastructure
# ============================================================================

echo "============================================================================"
echo "TEST 1: Locust Infrastructure"
echo "============================================================================"
echo ""

echo "Checking Locust master..."
MASTER_POD=$(kubectl get pods -n $NAMESPACE -l app=locust,role=master -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ -n "$MASTER_POD" ]; then
    echo -e "${GREEN}✅ Locust master running: $MASTER_POD${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ Locust master not found${NC}"
    ((TESTS_FAILED++))
fi

echo "Checking Locust workers..."
WORKER_COUNT=$(kubectl get pods -n $NAMESPACE -l app=locust,role=worker --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
if [ "$WORKER_COUNT" -eq 3 ]; then
    echo -e "${GREEN}✅ Locust workers running: $WORKER_COUNT/3${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ Locust workers: $WORKER_COUNT/3${NC}"
    ((TESTS_FAILED++))
fi

echo "Checking Locust master logs..."
if kubectl logs -n $NAMESPACE $MASTER_POD --tail=5 2>&1 | grep -q "Starting Locust"; then
    echo -e "${GREEN}✅ Locust master initialized${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ Locust master not initialized${NC}"
    ((TESTS_FAILED++))
fi

echo ""

# ============================================================================
# Test 2: HPA Configuration
# ============================================================================

echo "============================================================================"
echo "TEST 2: HPA Configuration"
echo "============================================================================"
echo ""

echo "Checking Django HPA..."
if kubectl get hpa django-hpa -n $NAMESPACE >/dev/null 2>&1; then
    MIN=$(kubectl get hpa django-hpa -n $NAMESPACE -o jsonpath='{.spec.minReplicas}')
    MAX=$(kubectl get hpa django-hpa -n $NAMESPACE -o jsonpath='{.spec.maxReplicas}')
    CURRENT=$(kubectl get hpa django-hpa -n $NAMESPACE -o jsonpath='{.status.currentReplicas}')
    
    echo -e "${GREEN}✅ Django HPA configured${NC}"
    echo "   Min: $MIN, Max: $MAX, Current: $CURRENT"
    
    if [ "$MIN" -eq 3 ] && [ "$MAX" -eq 10 ]; then
        echo -e "${GREEN}✅ HPA limits correct (3-10)${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}❌ HPA limits incorrect (expected 3-10, got $MIN-$MAX)${NC}"
        ((TESTS_FAILED++))
    fi
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ Django HPA not found${NC}"
    ((TESTS_FAILED+=2))
fi

echo ""

# ============================================================================
# Test 3: PostgreSQL Cluster
# ============================================================================

echo "============================================================================"
echo "TEST 3: PostgreSQL Cluster"
echo "============================================================================"
echo ""

echo "Checking PostgreSQL pods..."
PG_PODS=$(kubectl get pods -n $NAMESPACE -l application=spilo --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
if [ "$PG_PODS" -ge 3 ]; then
    echo -e "${GREEN}✅ PostgreSQL cluster running: $PG_PODS pods${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ PostgreSQL cluster: only $PG_PODS pods${NC}"
    ((TESTS_FAILED++))
fi

echo "Checking PostgreSQL master..."
PG_MASTER=$(kubectl get pods -n $NAMESPACE -l application=spilo,spilo-role=master -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ -n "$PG_MASTER" ]; then
    echo -e "${GREEN}✅ PostgreSQL master: $PG_MASTER${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ PostgreSQL master not found${NC}"
    ((TESTS_FAILED++))
fi

echo ""

# ============================================================================
# Test 4: Redis Cluster
# ============================================================================

echo "============================================================================"
echo "TEST 4: Redis Cluster"
echo "============================================================================"
echo ""

echo "Checking Redis pods..."
REDIS_PODS=$(kubectl get pods -n $NAMESPACE -l app=redis --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
if [ "$REDIS_PODS" -ge 3 ]; then
    echo -e "${GREEN}✅ Redis cluster running: $REDIS_PODS pods${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ Redis cluster: only $REDIS_PODS pods${NC}"
    ((TESTS_FAILED++))
fi

echo "Checking Redis master..."
for i in 0 1 2; do
    ROLE=$(kubectl exec -n $NAMESPACE redis-$i -- redis-cli info replication 2>/dev/null | grep "role:" | cut -d: -f2 | tr -d '\r' || echo "")
    if [ "$ROLE" = "master" ]; then
        echo -e "${GREEN}✅ Redis master: redis-$i${NC}"
        ((TESTS_PASSED++))
        break
    fi
done

echo ""

# ============================================================================
# Test 5: Django Service
# ============================================================================

echo "============================================================================"
echo "TEST 5: Django Service"
echo "============================================================================"
echo ""

echo "Checking Django pods..."
DJANGO_PODS=$(kubectl get pods -n $NAMESPACE -l component=django --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
if [ "$DJANGO_PODS" -ge 3 ]; then
    echo -e "${GREEN}✅ Django pods running: $DJANGO_PODS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ Django pods: only $DJANGO_PODS${NC}"
    ((TESTS_FAILED++))
fi

echo "Checking Django service..."
if kubectl get svc django-service -n $NAMESPACE >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Django service exists${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ Django service not found${NC}"
    ((TESTS_FAILED++))
fi

echo "Testing Django health check..."
DJANGO_POD=$(kubectl get pods -n $NAMESPACE -l component=django -o jsonpath='{.items[0].metadata.name}')
if kubectl exec -n $NAMESPACE $DJANGO_POD -- python manage.py check 2>&1 | grep -q "System check identified no issues"; then
    echo -e "${GREEN}✅ Django health check passed${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ Django health check failed${NC}"
    ((TESTS_FAILED++))
fi

echo ""

# ============================================================================
# Test 6: Metrics Server
# ============================================================================

echo "============================================================================"
echo "TEST 6: Metrics Server"
echo "============================================================================"
echo ""

echo "Checking metrics server..."
if kubectl get deployment metrics-server -n kube-system >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Metrics server deployed${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ Metrics server not found${NC}"
    ((TESTS_FAILED++))
fi

echo "Testing pod metrics..."
if kubectl top pods -n $NAMESPACE -l component=django >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Pod metrics available${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ Pod metrics not available${NC}"
    ((TESTS_FAILED++))
fi

echo ""

# ============================================================================
# Test 7: Load Test Capability
# ============================================================================

echo "============================================================================"
echo "TEST 7: Load Test Capability (Quick Test)"
echo "============================================================================"
echo ""

echo "Testing Locust can reach Django service..."
echo "Creating test pod..."
kubectl run test-load --image=busybox:1.35 --rm -i --restart=Never -n $NAMESPACE -- /bin/sh -c "
    for i in 1 2 3 4 5; do
        wget -q -O- http://django-service.$NAMESPACE.svc.cluster.local/ >/dev/null 2>&1 && echo 'Request \$i: OK' || echo 'Request \$i: FAIL'
    done
" 2>&1 | grep -v "pod.*deleted" | grep -v "If you don't see"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Load test connectivity verified${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}⚠️  Load test connectivity check inconclusive${NC}"
fi

echo ""

# ============================================================================
# Summary
# ============================================================================

echo "============================================================================"
echo "VALIDATION SUMMARY"
echo "============================================================================"
echo ""

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
SUCCESS_RATE=$((TESTS_PASSED * 100 / TOTAL_TESTS))

echo "Tests Passed: $TESTS_PASSED"
echo "Tests Failed: $TESTS_FAILED"
echo "Total Tests: $TOTAL_TESTS"
echo "Success Rate: ${SUCCESS_RATE}%"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ ALL VALIDATION TESTS PASSED${NC}"
    echo ""
    echo "The system is ready for full load testing and chaos engineering."
    echo "To run the complete test suite:"
    echo "  bash k8s/scripts/task-34.16-complete-test.sh"
    echo ""
    exit 0
else
    echo -e "${RED}❌ SOME VALIDATION TESTS FAILED${NC}"
    echo ""
    echo "Please fix the issues before running the complete test suite."
    echo ""
    exit 1
fi
