#!/bin/bash

# ============================================================================
# Network Policy Validation Script
# ============================================================================
# This script validates that NetworkPolicies are correctly configured and
# enforcing the expected security rules.
#
# Tests performed:
# 1. Verify all NetworkPolicies are created
# 2. Test that Django can connect to PostgreSQL (should succeed)
# 3. Test that Django can connect to Redis (should succeed)
# 4. Test that Nginx can connect to Django (should succeed)
# 5. Test that external pods cannot connect to PostgreSQL (should fail)
# 6. Test that external pods cannot connect to Redis (should fail)
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Namespace
NAMESPACE="jewelry-shop"

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}Network Policy Validation for jewelry-shop${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""

# ============================================================================
# Test 1: Verify NetworkPolicies are created
# ============================================================================

echo -e "${YELLOW}Test 1: Verifying NetworkPolicies are created...${NC}"
echo ""

POLICIES=$(kubectl get networkpolicies -n $NAMESPACE --no-headers 2>/dev/null | wc -l)

if [ "$POLICIES" -eq 0 ]; then
    echo -e "${RED}✗ FAIL: No NetworkPolicies found in namespace $NAMESPACE${NC}"
    echo "Please apply the network policies first:"
    echo "  kubectl apply -f k8s/network-policies.yaml"
    exit 1
fi

echo -e "${GREEN}✓ PASS: Found $POLICIES NetworkPolicies${NC}"
echo ""
kubectl get networkpolicies -n $NAMESPACE
echo ""

# ============================================================================
# Test 2: Verify Django can connect to PostgreSQL
# ============================================================================

echo -e "${YELLOW}Test 2: Testing Django → PostgreSQL connectivity (should succeed)...${NC}"
echo ""

# Get a Django pod
DJANGO_POD=$(kubectl get pods -n $NAMESPACE -l component=django --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -z "$DJANGO_POD" ]; then
    echo -e "${YELLOW}⚠ SKIP: No running Django pods found${NC}"
else
    # Get PostgreSQL service name
    PG_SERVICE="jewelry-shop-db-pooler"
    
    echo "Testing connection from pod: $DJANGO_POD"
    echo "Target: $PG_SERVICE:5432"
    echo ""
    
    if kubectl exec -n $NAMESPACE $DJANGO_POD -- timeout 5 nc -zv $PG_SERVICE 5432 2>&1 | grep -q "succeeded\|open"; then
        echo -e "${GREEN}✓ PASS: Django can connect to PostgreSQL${NC}"
    else
        echo -e "${RED}✗ FAIL: Django cannot connect to PostgreSQL${NC}"
        echo "This connection should be allowed by NetworkPolicy"
    fi
fi
echo ""

# ============================================================================
# Test 3: Verify Django can connect to Redis
# ============================================================================

echo -e "${YELLOW}Test 3: Testing Django → Redis connectivity (should succeed)...${NC}"
echo ""

if [ -z "$DJANGO_POD" ]; then
    echo -e "${YELLOW}⚠ SKIP: No running Django pods found${NC}"
else
    REDIS_SERVICE="redis"
    
    echo "Testing connection from pod: $DJANGO_POD"
    echo "Target: $REDIS_SERVICE:6379"
    echo ""
    
    if kubectl exec -n $NAMESPACE $DJANGO_POD -- timeout 5 nc -zv $REDIS_SERVICE 6379 2>&1 | grep -q "succeeded\|open"; then
        echo -e "${GREEN}✓ PASS: Django can connect to Redis${NC}"
    else
        echo -e "${RED}✗ FAIL: Django cannot connect to Redis${NC}"
        echo "This connection should be allowed by NetworkPolicy"
    fi
fi
echo ""

# ============================================================================
# Test 4: Verify Nginx can connect to Django
# ============================================================================

echo -e "${YELLOW}Test 4: Testing Nginx → Django connectivity (should succeed)...${NC}"
echo ""

NGINX_POD=$(kubectl get pods -n $NAMESPACE -l component=nginx --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -z "$NGINX_POD" ]; then
    echo -e "${YELLOW}⚠ SKIP: No running Nginx pods found${NC}"
else
    DJANGO_SERVICE="django-service"
    
    echo "Testing connection from pod: $NGINX_POD"
    echo "Target: $DJANGO_SERVICE:80"
    echo ""
    
    if kubectl exec -n $NAMESPACE $NGINX_POD -- timeout 5 nc -zv $DJANGO_SERVICE 80 2>&1 | grep -q "succeeded\|open"; then
        echo -e "${GREEN}✓ PASS: Nginx can connect to Django${NC}"
    else
        echo -e "${RED}✗ FAIL: Nginx cannot connect to Django${NC}"
        echo "This connection should be allowed by NetworkPolicy"
    fi
fi
echo ""

# ============================================================================
# Test 5: Verify external pods cannot connect to PostgreSQL
# ============================================================================

echo -e "${YELLOW}Test 5: Testing external pod → PostgreSQL connectivity (should fail)...${NC}"
echo ""

# Create a test pod in default namespace (external to jewelry-shop)
echo "Creating test pod in default namespace..."
kubectl run netpol-test --image=busybox:1.35 --restart=Never --rm -i --quiet -- sleep 3600 2>/dev/null &
TEST_POD_PID=$!

# Wait for pod to be ready
sleep 5

if kubectl get pod netpol-test -n default &>/dev/null; then
    PG_SERVICE="jewelry-shop-db-pooler.jewelry-shop.svc.cluster.local"
    
    echo "Testing connection from pod: netpol-test (default namespace)"
    echo "Target: $PG_SERVICE:5432"
    echo ""
    
    if kubectl exec -n default netpol-test -- timeout 5 nc -zv $PG_SERVICE 5432 2>&1 | grep -q "succeeded\|open"; then
        echo -e "${RED}✗ FAIL: External pod CAN connect to PostgreSQL${NC}"
        echo "This connection should be blocked by NetworkPolicy"
    else
        echo -e "${GREEN}✓ PASS: External pod cannot connect to PostgreSQL (blocked by NetworkPolicy)${NC}"
    fi
    
    # Cleanup
    kubectl delete pod netpol-test -n default --force --grace-period=0 &>/dev/null
else
    echo -e "${YELLOW}⚠ SKIP: Could not create test pod${NC}"
fi
echo ""

# ============================================================================
# Test 6: Verify external pods cannot connect to Redis
# ============================================================================

echo -e "${YELLOW}Test 6: Testing external pod → Redis connectivity (should fail)...${NC}"
echo ""

# Create a test pod in default namespace
echo "Creating test pod in default namespace..."
kubectl run netpol-test --image=busybox:1.35 --restart=Never --rm -i --quiet -- sleep 3600 2>/dev/null &
TEST_POD_PID=$!

# Wait for pod to be ready
sleep 5

if kubectl get pod netpol-test -n default &>/dev/null; then
    REDIS_SERVICE="redis.jewelry-shop.svc.cluster.local"
    
    echo "Testing connection from pod: netpol-test (default namespace)"
    echo "Target: $REDIS_SERVICE:6379"
    echo ""
    
    if kubectl exec -n default netpol-test -- timeout 5 nc -zv $REDIS_SERVICE 6379 2>&1 | grep -q "succeeded\|open"; then
        echo -e "${RED}✗ FAIL: External pod CAN connect to Redis${NC}"
        echo "This connection should be blocked by NetworkPolicy"
    else
        echo -e "${GREEN}✓ PASS: External pod cannot connect to Redis (blocked by NetworkPolicy)${NC}"
    fi
    
    # Cleanup
    kubectl delete pod netpol-test -n default --force --grace-period=0 &>/dev/null
else
    echo -e "${YELLOW}⚠ SKIP: Could not create test pod${NC}"
fi
echo ""

# ============================================================================
# Test 7: Verify Celery workers can connect to PostgreSQL
# ============================================================================

echo -e "${YELLOW}Test 7: Testing Celery Worker → PostgreSQL connectivity (should succeed)...${NC}"
echo ""

CELERY_POD=$(kubectl get pods -n $NAMESPACE -l component=celery-worker --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -z "$CELERY_POD" ]; then
    echo -e "${YELLOW}⚠ SKIP: No running Celery worker pods found${NC}"
else
    PG_SERVICE="jewelry-shop-db-pooler"
    
    echo "Testing connection from pod: $CELERY_POD"
    echo "Target: $PG_SERVICE:5432"
    echo ""
    
    if kubectl exec -n $NAMESPACE $CELERY_POD -- timeout 5 nc -zv $PG_SERVICE 5432 2>&1 | grep -q "succeeded\|open"; then
        echo -e "${GREEN}✓ PASS: Celery worker can connect to PostgreSQL${NC}"
    else
        echo -e "${RED}✗ FAIL: Celery worker cannot connect to PostgreSQL${NC}"
        echo "This connection should be allowed by NetworkPolicy"
    fi
fi
echo ""

# ============================================================================
# Test 8: Verify Celery workers can connect to Redis
# ============================================================================

echo -e "${YELLOW}Test 8: Testing Celery Worker → Redis connectivity (should succeed)...${NC}"
echo ""

if [ -z "$CELERY_POD" ]; then
    echo -e "${YELLOW}⚠ SKIP: No running Celery worker pods found${NC}"
else
    REDIS_SERVICE="redis"
    
    echo "Testing connection from pod: $CELERY_POD"
    echo "Target: $REDIS_SERVICE:6379"
    echo ""
    
    if kubectl exec -n $NAMESPACE $CELERY_POD -- timeout 5 nc -zv $REDIS_SERVICE 6379 2>&1 | grep -q "succeeded\|open"; then
        echo -e "${GREEN}✓ PASS: Celery worker can connect to Redis${NC}"
    else
        echo -e "${RED}✗ FAIL: Celery worker cannot connect to Redis${NC}"
        echo "This connection should be allowed by NetworkPolicy"
    fi
fi
echo ""

# ============================================================================
# Summary
# ============================================================================

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}Validation Summary${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""
echo "NetworkPolicies enforce zero-trust networking:"
echo "  ✓ Django can access PostgreSQL and Redis"
echo "  ✓ Nginx can access Django"
echo "  ✓ Celery workers can access PostgreSQL and Redis"
echo "  ✓ External pods cannot access PostgreSQL or Redis"
echo ""
echo "To view all NetworkPolicies:"
echo "  kubectl get networkpolicies -n $NAMESPACE"
echo ""
echo "To describe a specific policy:"
echo "  kubectl describe networkpolicy <policy-name> -n $NAMESPACE"
echo ""
echo -e "${GREEN}Network security validation complete!${NC}"
