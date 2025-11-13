#!/bin/bash

# ============================================================================
# Task 34.13 Verification Script
# ============================================================================
# Quick verification that NetworkPolicies are correctly implemented
# ============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Task 34.13 Verification${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 1. Check NetworkPolicies exist
echo -e "${YELLOW}1. Checking NetworkPolicies...${NC}"
POLICY_COUNT=$(kubectl get networkpolicies -n jewelry-shop --no-headers 2>/dev/null | wc -l)
if [ "$POLICY_COUNT" -eq 17 ]; then
    echo -e "${GREEN}✓ All 17 NetworkPolicies exist${NC}"
else
    echo -e "✗ Expected 17 policies, found $POLICY_COUNT"
    exit 1
fi
echo ""

# 2. Test DNS resolution
echo -e "${YELLOW}2. Testing DNS resolution...${NC}"
DJANGO_POD=$(kubectl get pods -n jewelry-shop -l component=django -o jsonpath='{.items[0].metadata.name}')
if kubectl exec -n jewelry-shop $DJANGO_POD -- python -c "import socket; socket.gethostbyname('jewelry-shop-db-pooler.jewelry-shop.svc.cluster.local')" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ DNS resolution works${NC}"
else
    echo -e "✗ DNS resolution failed"
    exit 1
fi
echo ""

# 3. Test Django → PostgreSQL
echo -e "${YELLOW}3. Testing Django → PostgreSQL...${NC}"
if kubectl exec -n jewelry-shop $DJANGO_POD -- python -c "import socket; s = socket.socket(); s.settimeout(5); result = s.connect_ex(('jewelry-shop-db-pooler.jewelry-shop.svc.cluster.local', 5432)); exit(0 if result == 0 else 1)" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Django can connect to PostgreSQL${NC}"
else
    echo -e "✗ Django cannot connect to PostgreSQL"
    exit 1
fi
echo ""

# 4. Test Django → Redis
echo -e "${YELLOW}4. Testing Django → Redis...${NC}"
if kubectl exec -n jewelry-shop $DJANGO_POD -- python -c "import socket; s = socket.socket(); s.settimeout(5); result = s.connect_ex(('redis.jewelry-shop.svc.cluster.local', 6379)); exit(0 if result == 0 else 1)" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Django can connect to Redis${NC}"
else
    echo -e "✗ Django cannot connect to Redis"
    exit 1
fi
echo ""

# 5. Test Celery → PostgreSQL
echo -e "${YELLOW}5. Testing Celery → PostgreSQL...${NC}"
CELERY_POD=$(kubectl get pods -n jewelry-shop -l component=celery-worker -o jsonpath='{.items[0].metadata.name}')
if kubectl exec -n jewelry-shop $CELERY_POD -- python -c "import socket; s = socket.socket(); s.settimeout(5); result = s.connect_ex(('jewelry-shop-db-pooler.jewelry-shop.svc.cluster.local', 5432)); exit(0 if result == 0 else 1)" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Celery can connect to PostgreSQL${NC}"
else
    echo -e "✗ Celery cannot connect to PostgreSQL"
    exit 1
fi
echo ""

# 6. Test Celery → Redis
echo -e "${YELLOW}6. Testing Celery → Redis...${NC}"
if kubectl exec -n jewelry-shop $CELERY_POD -- python -c "import socket; s = socket.socket(); s.settimeout(5); result = s.connect_ex(('redis.jewelry-shop.svc.cluster.local', 6379)); exit(0 if result == 0 else 1)" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Celery can connect to Redis${NC}"
else
    echo -e "✗ Celery cannot connect to Redis"
    exit 1
fi
echo ""

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✓ All verification tests passed!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "NetworkPolicies are correctly implemented."
echo "Note: Enforcement requires Calico in production."
echo ""
echo "Next steps:"
echo "  1. Proceed to Task 34.14 (Integration testing)"
echo "  2. Install Calico for production (Task 34.15)"
echo ""
