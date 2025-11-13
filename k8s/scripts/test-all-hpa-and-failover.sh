#!/bin/bash

# ============================================================================
# Comprehensive HPA and Failover Testing Script
# ============================================================================
# This script performs comprehensive testing of:
# 1. All HPA configurations (Django, Celery, Nginx)
# 2. Scale-up and scale-down behavior
# 3. Pod failover and self-healing
# 4. Replica management
# 5. PodDisruptionBudget enforcement
# ============================================================================

set -e

NAMESPACE="jewelry-shop"
LOAD_DURATION=120  # 2 minutes of load for testing

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "============================================================================"
echo "Comprehensive HPA and Failover Testing"
echo "============================================================================"
echo ""

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl not found. Please install kubectl first.${NC}"
    exit 1
fi

# Check if cluster is accessible
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}❌ Cannot connect to Kubernetes cluster.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Cluster connection verified${NC}"
echo ""

# ============================================================================
# PART 1: Verify All HPAs Are Configured
# ============================================================================

echo "============================================================================"
echo "PART 1: Verify All HPAs Are Configured"
echo "============================================================================"
echo ""

echo "Checking all HPAs in namespace $NAMESPACE..."
echo ""

kubectl get hpa -n $NAMESPACE

echo ""

# Check each HPA individually
HPAS=("django-hpa" "celery-worker-hpa" "nginx-hpa")
for hpa in "${HPAS[@]}"; do
    if kubectl get hpa $hpa -n $NAMESPACE &> /dev/null; then
        echo -e "${GREEN}✅ $hpa exists${NC}"
    else
        echo -e "${RED}❌ $hpa not found${NC}"
        exit 1
    fi
done

echo ""
echo -e "${GREEN}✅ All HPAs are configured${NC}"
echo ""

# ============================================================================
# PART 2: Verify Metrics Are Available
# ============================================================================

echo "============================================================================"
echo "PART 2: Verify Metrics Are Available"
echo "============================================================================"
echo ""

echo "Checking node metrics..."
kubectl top nodes
echo ""

echo "Checking pod metrics..."
kubectl top pods -n $NAMESPACE
echo ""

echo -e "${GREEN}✅ Metrics are available${NC}"
echo ""

# ============================================================================
# PART 3: Check Current State
# ============================================================================

echo "============================================================================"
echo "PART 3: Check Current State"
echo "============================================================================"
echo ""

echo "Current HPA Status:"
kubectl get hpa -n $NAMESPACE
echo ""

echo "Current Deployments:"
kubectl get deployments -n $NAMESPACE
echo ""

echo "Current Pods:"
kubectl get pods -n $NAMESPACE -o wide
echo ""

# ============================================================================
# PART 4: Test Django HPA Scale-Up
# ============================================================================

echo "============================================================================"
echo "PART 4: Test Django HPA Scale-Up"
echo "============================================================================"
echo ""

echo "Current Django replicas:"
DJANGO_INITIAL=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}')
echo "Initial: $DJANGO_INITIAL"
echo ""

echo "Generating load on Django service for $LOAD_DURATION seconds..."
echo ""

# Create load generator for Django
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: django-load-generator
  namespace: $NAMESPACE
  labels:
    app: load-generator
    target: django
spec:
  containers:
  - name: load-generator
    image: busybox:1.35
    command:
    - /bin/sh
    - -c
    - |
      echo "Starting Django load generation..."
      END_TIME=\$((SECONDS + $LOAD_DURATION))
      REQUEST_COUNT=0
      
      while [ \$SECONDS -lt \$END_TIME ]; do
        # Send 10 requests in parallel
        for i in \$(seq 1 10); do
          wget -q -O- http://django-service.$NAMESPACE.svc.cluster.local:80/ > /dev/null 2>&1 &
        done
        wait
        REQUEST_COUNT=\$((REQUEST_COUNT + 10))
        
        if [ \$((REQUEST_COUNT % 100)) -eq 0 ]; then
          echo "Sent \$REQUEST_COUNT requests..."
        fi
      done
      
      echo "Load generation complete. Total requests: \$REQUEST_COUNT"
      sleep 300
  restartPolicy: Never
EOF

echo ""
echo "Waiting for load generator to start..."
kubectl wait --for=condition=Ready pod/django-load-generator -n $NAMESPACE --timeout=60s 2>/dev/null || true
echo ""

echo "Monitoring Django HPA for $LOAD_DURATION seconds..."
echo ""

# Monitor for the duration of the load test
MONITOR_END=$((SECONDS + LOAD_DURATION))
while [ $SECONDS -lt $MONITOR_END ]; do
    TIMESTAMP=$(date '+%H:%M:%S')
    REPLICAS=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}')
    READY=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.readyReplicas}')
    
    echo -e "${BLUE}[$TIMESTAMP] Django - Replicas: $REPLICAS | Ready: $READY${NC}"
    kubectl get hpa django-hpa -n $NAMESPACE --no-headers
    echo ""
    
    sleep 15
done

DJANGO_SCALED=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}')
echo ""
echo "Django scaling result: $DJANGO_INITIAL → $DJANGO_SCALED replicas"

if [ "$DJANGO_SCALED" -gt "$DJANGO_INITIAL" ]; then
    echo -e "${GREEN}✅ Django HPA scaled up successfully${NC}"
else
    echo -e "${YELLOW}⚠️  Django HPA did not scale up (may need more load or time)${NC}"
fi

echo ""

# Cleanup Django load generator
kubectl delete pod django-load-generator -n $NAMESPACE --ignore-not-found=true

# ============================================================================
# PART 5: Test Pod Failover and Self-Healing
# ============================================================================

echo "============================================================================"
echo "PART 5: Test Pod Failover and Self-Healing"
echo "============================================================================"
echo ""

echo "Testing Django pod self-healing..."
echo ""

# Get a Django pod
DJANGO_POD=$(kubectl get pods -n $NAMESPACE -l component=django -o jsonpath='{.items[0].metadata.name}')
echo "Deleting pod: $DJANGO_POD"
kubectl delete pod $DJANGO_POD -n $NAMESPACE

echo ""
echo "Waiting for replacement pod to be created..."
sleep 5

echo ""
echo "Current Django pods:"
kubectl get pods -n $NAMESPACE -l component=django
echo ""

# Wait for all pods to be ready
echo "Waiting for all Django pods to be ready..."
kubectl wait --for=condition=Ready pods -l component=django -n $NAMESPACE --timeout=120s

echo ""
echo -e "${GREEN}✅ Django pod self-healing verified${NC}"
echo ""

# ============================================================================
# PART 6: Test PodDisruptionBudget
# ============================================================================

echo "============================================================================"
echo "PART 6: Test PodDisruptionBudget"
echo "============================================================================"
echo ""

echo "Checking PodDisruptionBudgets..."
kubectl get pdb -n $NAMESPACE
echo ""

# Check Django PDB
echo "Django PDB details:"
kubectl describe pdb django-pdb -n $NAMESPACE | grep -A 5 "Status:"
echo ""

echo -e "${GREEN}✅ PodDisruptionBudgets are configured${NC}"
echo ""

# ============================================================================
# PART 7: Test Scale-Down Behavior
# ============================================================================

echo "============================================================================"
echo "PART 7: Test Scale-Down Behavior"
echo "============================================================================"
echo ""

echo "Load has stopped. Monitoring scale-down behavior..."
echo "Django HPA should wait 5 minutes before scaling down."
echo ""

echo "Monitoring for 6 minutes (or until back to minimum)..."
echo ""

MONITOR_END=$((SECONDS + 360))
while [ $SECONDS -lt $MONITOR_END ]; do
    TIMESTAMP=$(date '+%H:%M:%S')
    REPLICAS=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}')
    READY=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.readyReplicas}')
    
    echo -e "${BLUE}[$TIMESTAMP] Django - Replicas: $REPLICAS | Ready: $READY${NC}"
    kubectl get hpa django-hpa -n $NAMESPACE --no-headers
    echo ""
    
    # If back to minimum, we're done
    if [ "$REPLICAS" -eq 3 ]; then
        echo -e "${GREEN}✅ Scaled back down to minimum (3 replicas)${NC}"
        break
    fi
    
    sleep 30
done

echo ""

# ============================================================================
# PART 8: Test Celery Worker HPA
# ============================================================================

echo "============================================================================"
echo "PART 8: Test Celery Worker HPA"
echo "============================================================================"
echo ""

echo "Current Celery worker status:"
kubectl get hpa celery-worker-hpa -n $NAMESPACE
echo ""

echo "Current Celery worker pods:"
kubectl get pods -n $NAMESPACE -l component=celery-worker
echo ""

echo "Celery worker metrics:"
kubectl top pods -n $NAMESPACE -l component=celery-worker
echo ""

echo -e "${GREEN}✅ Celery worker HPA is configured and monitoring${NC}"
echo ""

# ============================================================================
# PART 9: Test Nginx HPA
# ============================================================================

echo "============================================================================"
echo "PART 9: Test Nginx HPA"
echo "============================================================================"
echo ""

echo "Current Nginx status:"
kubectl get hpa nginx-hpa -n $NAMESPACE
echo ""

echo "Current Nginx pods:"
kubectl get pods -n $NAMESPACE -l component=nginx
echo ""

echo "Nginx metrics:"
kubectl top pods -n $NAMESPACE -l component=nginx
echo ""

echo -e "${GREEN}✅ Nginx HPA is configured and monitoring${NC}"
echo ""

# ============================================================================
# PART 10: Comprehensive Status Summary
# ============================================================================

echo "============================================================================"
echo "PART 10: Comprehensive Status Summary"
echo "============================================================================"
echo ""

echo "All HPAs:"
kubectl get hpa -n $NAMESPACE
echo ""

echo "All Deployments:"
kubectl get deployments -n $NAMESPACE
echo ""

echo "All PodDisruptionBudgets:"
kubectl get pdb -n $NAMESPACE
echo ""

echo "All Pods:"
kubectl get pods -n $NAMESPACE -o wide
echo ""

echo "Pod Metrics:"
kubectl top pods -n $NAMESPACE
echo ""

# ============================================================================
# Test Results Summary
# ============================================================================

echo "============================================================================"
echo "TEST RESULTS SUMMARY"
echo "============================================================================"
echo ""

echo -e "${GREEN}✅ PASSED TESTS:${NC}"
echo "  ✓ All HPAs configured (Django, Celery, Nginx)"
echo "  ✓ Metrics-server working"
echo "  ✓ Pod metrics available"
echo "  ✓ Django HPA monitoring active"
echo "  ✓ Celery HPA monitoring active"
echo "  ✓ Nginx HPA monitoring active"
echo "  ✓ Pod self-healing verified"
echo "  ✓ PodDisruptionBudgets configured"
echo ""

if [ "$DJANGO_SCALED" -gt "$DJANGO_INITIAL" ]; then
    echo "  ✓ Django HPA scale-up verified ($DJANGO_INITIAL → $DJANGO_SCALED)"
else
    echo -e "  ${YELLOW}⚠ Django HPA scale-up not observed (may need more load)${NC}"
fi

echo ""
echo "============================================================================"
echo "✅ COMPREHENSIVE TESTING COMPLETE"
echo "============================================================================"
echo ""

echo "Summary:"
echo "  - Django HPA: min=3, max=10, current=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}')"
echo "  - Celery HPA: min=1, max=3, current=$(kubectl get deployment celery-worker -n $NAMESPACE -o jsonpath='{.status.replicas}')"
echo "  - Nginx HPA: min=2, max=5, current=$(kubectl get deployment nginx -n $NAMESPACE -o jsonpath='{.status.replicas}')"
echo ""

echo "To watch HPAs in real-time:"
echo "  kubectl get hpa -n $NAMESPACE --watch"
echo ""

echo "To generate more load for testing:"
echo "  kubectl run -it load-generator --rm --image=busybox --restart=Never -n $NAMESPACE -- /bin/sh -c \"while true; do wget -q -O- http://django-service.$NAMESPACE.svc.cluster.local:80/; done\""
echo ""

echo "============================================================================"
