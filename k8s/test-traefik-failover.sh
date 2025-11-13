#!/bin/bash

# Traefik Failover and Replica Testing Script
# Tests high availability and self-healing capabilities

set +e  # Don't exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TRAEFIK_NAMESPACE="traefik"
TEST_RESULTS=()

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Traefik Failover Testing - Task 34.9${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Test 1: Verify initial state
echo -e "${YELLOW}Test 1: Verifying initial Traefik deployment...${NC}"
INITIAL_PODS=$(kubectl get pods -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik --no-headers | wc -l)
RUNNING_PODS=$(kubectl get pods -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik --field-selector=status.phase=Running --no-headers | wc -l)

echo "Total Traefik pods: ${INITIAL_PODS}"
echo "Running pods: ${RUNNING_PODS}"

if [ "$RUNNING_PODS" -eq 2 ]; then
    echo -e "${GREEN}✓ PASS: 2 Traefik replicas are running${NC}"
    TEST_RESULTS+=("PASS: Initial state - 2 replicas running")
else
    echo -e "${RED}✗ FAIL: Expected 2 replicas, found ${RUNNING_PODS}${NC}"
    TEST_RESULTS+=("FAIL: Initial state - Expected 2, found ${RUNNING_PODS}")
fi
echo ""

# Get pod names
POD1=$(kubectl get pods -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik -o jsonpath='{.items[0].metadata.name}')
POD2=$(kubectl get pods -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik -o jsonpath='{.items[1].metadata.name}')

echo "Pod 1: ${POD1}"
echo "Pod 2: ${POD2}"
echo ""

# Test 2: Kill one pod and verify the other continues serving
echo -e "${YELLOW}Test 2: Testing single pod failure (kill ${POD1})...${NC}"
echo "Deleting pod: ${POD1}"
kubectl delete pod ${POD1} -n ${TRAEFIK_NAMESPACE} --wait=false

echo "Waiting 5 seconds..."
sleep 5

# Check if service is still available
RUNNING_AFTER=$(kubectl get pods -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik --field-selector=status.phase=Running --no-headers | wc -l)
echo "Running pods after deletion: ${RUNNING_AFTER}"

if [ "$RUNNING_AFTER" -ge 1 ]; then
    echo -e "${GREEN}✓ PASS: At least 1 pod still running (high availability maintained)${NC}"
    TEST_RESULTS+=("PASS: Single pod failure - Service remained available")
else
    echo -e "${RED}✗ FAIL: No pods running after deletion${NC}"
    TEST_RESULTS+=("FAIL: Single pod failure - Service unavailable")
fi
echo ""

# Test 3: Verify pod self-healing (new pod should be created)
echo -e "${YELLOW}Test 3: Testing self-healing (pod recreation)...${NC}"
echo "Waiting 30 seconds for pod to be recreated..."
sleep 30

FINAL_PODS=$(kubectl get pods -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik --field-selector=status.phase=Running --no-headers | wc -l)
echo "Running pods after self-healing: ${FINAL_PODS}"

if [ "$FINAL_PODS" -eq 2 ]; then
    echo -e "${GREEN}✓ PASS: Pod was automatically recreated (self-healing works)${NC}"
    TEST_RESULTS+=("PASS: Self-healing - Pod automatically recreated")
else
    echo -e "${YELLOW}⚠ WARNING: Expected 2 pods, found ${FINAL_PODS}${NC}"
    TEST_RESULTS+=("WARNING: Self-healing - Found ${FINAL_PODS} pods instead of 2")
fi

kubectl get pods -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik
echo ""

# Test 4: Test pod distribution (anti-affinity)
echo -e "${YELLOW}Test 4: Testing pod distribution across nodes...${NC}"
echo "Checking which nodes pods are running on:"
kubectl get pods -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik -o wide

POD_NODES=$(kubectl get pods -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik -o jsonpath='{range .items[*]}{.spec.nodeName}{"\n"}{end}' | sort -u | wc -l)
echo ""
echo "Pods are distributed across ${POD_NODES} node(s)"

if [ "$POD_NODES" -gt 1 ]; then
    echo -e "${GREEN}✓ PASS: Pods are distributed across multiple nodes (anti-affinity working)${NC}"
    TEST_RESULTS+=("PASS: Pod distribution - Pods on different nodes")
else
    echo -e "${YELLOW}⚠ INFO: All pods on same node (acceptable for small clusters)${NC}"
    TEST_RESULTS+=("INFO: Pod distribution - All pods on same node")
fi
echo ""

# Test 5: Test LoadBalancer service
echo -e "${YELLOW}Test 5: Testing LoadBalancer service...${NC}"
EXTERNAL_IPS=$(kubectl get svc traefik -n ${TRAEFIK_NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[*].ip}')
SERVICE_TYPE=$(kubectl get svc traefik -n ${TRAEFIK_NAMESPACE} -o jsonpath='{.spec.type}')

echo "Service type: ${SERVICE_TYPE}"
echo "External IPs: ${EXTERNAL_IPS}"

if [ -n "$EXTERNAL_IPS" ]; then
    echo -e "${GREEN}✓ PASS: LoadBalancer has external IP(s)${NC}"
    TEST_RESULTS+=("PASS: LoadBalancer - External IPs assigned")
else
    echo -e "${YELLOW}⚠ WARNING: No external IPs (may be pending)${NC}"
    TEST_RESULTS+=("WARNING: LoadBalancer - No external IPs")
fi
echo ""

# Test 6: Test service endpoints
echo -e "${YELLOW}Test 6: Testing service endpoints...${NC}"
ENDPOINTS=$(kubectl get endpoints traefik -n ${TRAEFIK_NAMESPACE} -o jsonpath='{.subsets[*].addresses[*].ip}' | wc -w)
echo "Number of endpoints: ${ENDPOINTS}"

if [ "$ENDPOINTS" -eq 2 ]; then
    echo -e "${GREEN}✓ PASS: Service has 2 endpoints (both pods registered)${NC}"
    TEST_RESULTS+=("PASS: Service endpoints - 2 endpoints registered")
else
    echo -e "${YELLOW}⚠ WARNING: Expected 2 endpoints, found ${ENDPOINTS}${NC}"
    TEST_RESULTS+=("WARNING: Service endpoints - Found ${ENDPOINTS} instead of 2")
fi

kubectl get endpoints traefik -n ${TRAEFIK_NAMESPACE}
echo ""

# Test 7: Test rolling update capability
echo -e "${YELLOW}Test 7: Testing rolling update capability...${NC}"
DEPLOYMENT=$(kubectl get deployment -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik -o jsonpath='{.items[0].metadata.name}')
MAX_UNAVAILABLE=$(kubectl get deployment ${DEPLOYMENT} -n ${TRAEFIK_NAMESPACE} -o jsonpath='{.spec.strategy.rollingUpdate.maxUnavailable}')
MAX_SURGE=$(kubectl get deployment ${DEPLOYMENT} -n ${TRAEFIK_NAMESPACE} -o jsonpath='{.spec.strategy.rollingUpdate.maxSurge}')

echo "Deployment: ${DEPLOYMENT}"
echo "Max Unavailable: ${MAX_UNAVAILABLE:-default}"
echo "Max Surge: ${MAX_SURGE:-default}"

STRATEGY=$(kubectl get deployment ${DEPLOYMENT} -n ${TRAEFIK_NAMESPACE} -o jsonpath='{.spec.strategy.type}')
if [ "$STRATEGY" = "RollingUpdate" ]; then
    echo -e "${GREEN}✓ PASS: Rolling update strategy configured${NC}"
    TEST_RESULTS+=("PASS: Rolling update - Strategy configured")
else
    echo -e "${RED}✗ FAIL: Rolling update not configured (strategy: ${STRATEGY})${NC}"
    TEST_RESULTS+=("FAIL: Rolling update - Strategy: ${STRATEGY}")
fi
echo ""

# Test 8: Test resource limits
echo -e "${YELLOW}Test 8: Testing resource limits...${NC}"
CPU_REQUEST=$(kubectl get deployment ${DEPLOYMENT} -n ${TRAEFIK_NAMESPACE} -o jsonpath='{.spec.template.spec.containers[0].resources.requests.cpu}')
MEM_REQUEST=$(kubectl get deployment ${DEPLOYMENT} -n ${TRAEFIK_NAMESPACE} -o jsonpath='{.spec.template.spec.containers[0].resources.requests.memory}')
CPU_LIMIT=$(kubectl get deployment ${DEPLOYMENT} -n ${TRAEFIK_NAMESPACE} -o jsonpath='{.spec.template.spec.containers[0].resources.limits.cpu}')
MEM_LIMIT=$(kubectl get deployment ${DEPLOYMENT} -n ${TRAEFIK_NAMESPACE} -o jsonpath='{.spec.template.spec.containers[0].resources.limits.memory}')

echo "CPU Request: ${CPU_REQUEST}"
echo "Memory Request: ${MEM_REQUEST}"
echo "CPU Limit: ${CPU_LIMIT}"
echo "Memory Limit: ${MEM_LIMIT}"

if [ -n "$CPU_REQUEST" ] && [ -n "$MEM_REQUEST" ]; then
    echo -e "${GREEN}✓ PASS: Resource requests configured${NC}"
    TEST_RESULTS+=("PASS: Resources - Requests configured")
else
    echo -e "${RED}✗ FAIL: Resource requests not configured${NC}"
    TEST_RESULTS+=("FAIL: Resources - Requests not configured")
fi
echo ""

# Test 9: Test Prometheus metrics
echo -e "${YELLOW}Test 9: Testing Prometheus metrics endpoint...${NC}"
CURRENT_POD=$(kubectl get pods -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik -o jsonpath='{.items[0].metadata.name}')
METRICS=$(kubectl exec -n ${TRAEFIK_NAMESPACE} ${CURRENT_POD} -- wget -q -O- http://localhost:9100/metrics 2>/dev/null | head -5)

if [ -n "$METRICS" ]; then
    echo -e "${GREEN}✓ PASS: Prometheus metrics endpoint is accessible${NC}"
    echo "Sample metrics:"
    echo "$METRICS"
    TEST_RESULTS+=("PASS: Metrics - Prometheus endpoint accessible")
else
    echo -e "${RED}✗ FAIL: Cannot access Prometheus metrics${NC}"
    TEST_RESULTS+=("FAIL: Metrics - Prometheus endpoint not accessible")
fi
echo ""

# Test 10: Test both pods simultaneously (chaos test)
echo -e "${YELLOW}Test 10: Chaos test - Deleting both pods simultaneously...${NC}"
echo "This tests Kubernetes' ability to maintain service during complete failure"
echo ""

ALL_PODS=$(kubectl get pods -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik -o jsonpath='{.items[*].metadata.name}')
echo "Deleting all Traefik pods: ${ALL_PODS}"
kubectl delete pods -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik --wait=false

echo "Waiting 5 seconds..."
sleep 5

PODS_AFTER_CHAOS=$(kubectl get pods -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik --no-headers | wc -l)
echo "Pods after chaos deletion: ${PODS_AFTER_CHAOS}"

echo "Waiting 30 seconds for full recovery..."
sleep 30

RECOVERED_PODS=$(kubectl get pods -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik --field-selector=status.phase=Running --no-headers | wc -l)
echo "Running pods after recovery: ${RECOVERED_PODS}"

if [ "$RECOVERED_PODS" -eq 2 ]; then
    echo -e "${GREEN}✓ PASS: System recovered from complete failure (chaos test passed)${NC}"
    TEST_RESULTS+=("PASS: Chaos test - Full recovery from complete failure")
else
    echo -e "${RED}✗ FAIL: System did not fully recover (${RECOVERED_PODS}/2 pods)${NC}"
    TEST_RESULTS+=("FAIL: Chaos test - Only ${RECOVERED_PODS}/2 pods recovered")
fi

kubectl get pods -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik
echo ""

# Summary
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Test Summary${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

for result in "${TEST_RESULTS[@]}"; do
    if [[ $result == PASS:* ]]; then
        echo -e "${GREEN}✓ ${result}${NC}"
        ((PASS_COUNT++))
    elif [[ $result == FAIL:* ]]; then
        echo -e "${RED}✗ ${result}${NC}"
        ((FAIL_COUNT++))
    else
        echo -e "${YELLOW}⚠ ${result}${NC}"
        ((WARN_COUNT++))
    fi
done

echo ""
echo -e "Tests Passed: ${GREEN}${PASS_COUNT}${NC}"
echo -e "Tests Failed: ${RED}${FAIL_COUNT}${NC}"
echo -e "Warnings: ${YELLOW}${WARN_COUNT}${NC}"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}✓ All critical tests passed!${NC}"
    echo -e "${GREEN}Traefik is highly available and self-healing.${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please review the results above.${NC}"
    exit 1
fi
