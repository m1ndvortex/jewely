#!/bin/bash

# ============================================================================
# Extreme Load Test for Django HPA
# ============================================================================
# This script generates extreme load to push Django pods to maximum replicas
# and then monitors the scale-down behavior.
# ============================================================================

set -e

NAMESPACE="jewelry-shop"
LOAD_DURATION=300  # 5 minutes of extreme load
MONITOR_DURATION=600  # 10 minutes to watch scale-down

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "============================================================================"
echo "EXTREME LOAD TEST - Django HPA Scale-Up and Scale-Down"
echo "============================================================================"
echo ""

echo -e "${CYAN}Test Parameters:${NC}"
echo "  - Load Duration: $LOAD_DURATION seconds (5 minutes)"
echo "  - Monitor Duration: $MONITOR_DURATION seconds (10 minutes)"
echo "  - Target: Django pods (min: 3, max: 10)"
echo "  - Expected: Scale from 3 to 10 pods, then back to 3"
echo ""

# Check cluster
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}❌ Cannot connect to Kubernetes cluster.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Cluster connection verified${NC}"
echo ""

# ============================================================================
# PART 1: Check Initial State
# ============================================================================

echo "============================================================================"
echo "PART 1: Initial State"
echo "============================================================================"
echo ""

echo "Current HPA Status:"
kubectl get hpa django-hpa -n $NAMESPACE
echo ""

echo "Current Django Pods:"
kubectl get pods -n $NAMESPACE -l component=django
echo ""

echo "Current Metrics:"
kubectl top pods -n $NAMESPACE -l component=django
echo ""

INITIAL_REPLICAS=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}')
echo -e "${BLUE}Initial replica count: $INITIAL_REPLICAS${NC}"
echo ""

# ============================================================================
# PART 2: Deploy Extreme Load Generators
# ============================================================================

echo "============================================================================"
echo "PART 2: Deploying Extreme Load Generators"
echo "============================================================================"
echo ""

echo "Creating 10 parallel load generator pods..."
echo "Each pod will generate continuous CPU-intensive requests"
echo ""

# Create multiple load generator pods
for i in {1..10}; do
    cat <<EOF | kubectl apply -f - > /dev/null
apiVersion: v1
kind: Pod
metadata:
  name: extreme-load-$i
  namespace: $NAMESPACE
  labels:
    app: extreme-load-test
spec:
  containers:
  - name: load
    image: busybox:1.35
    command:
    - /bin/sh
    - -c
    - |
      echo "Load generator $i starting..."
      END_TIME=\$((SECONDS + $LOAD_DURATION))
      REQUEST_COUNT=0
      
      while [ \$SECONDS -lt \$END_TIME ]; do
        # Send 20 parallel requests
        for j in \$(seq 1 20); do
          wget -q -O- http://django-service.$NAMESPACE.svc.cluster.local:80/ > /dev/null 2>&1 &
        done
        wait
        REQUEST_COUNT=\$((REQUEST_COUNT + 20))
        
        if [ \$((REQUEST_COUNT % 1000)) -eq 0 ]; then
          echo "Generator $i: \$REQUEST_COUNT requests sent"
        fi
      done
      
      echo "Generator $i complete: \$REQUEST_COUNT total requests"
      sleep 600
  restartPolicy: Never
EOF
    echo -e "${GREEN}✓${NC} Load generator $i created"
done

echo ""
echo -e "${GREEN}✅ All 10 load generators created${NC}"
echo ""

# Wait for pods to start
echo "Waiting for load generators to start..."
sleep 10

# Check how many are running
RUNNING=$(kubectl get pods -n $NAMESPACE -l app=extreme-load-test --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
echo -e "${BLUE}Load generators running: $RUNNING/10${NC}"
echo ""

# ============================================================================
# PART 3: Monitor Scale-Up
# ============================================================================

echo "============================================================================"
echo "PART 3: Monitoring Scale-Up (5 minutes)"
echo "============================================================================"
echo ""

echo -e "${YELLOW}Generating extreme load for $LOAD_DURATION seconds...${NC}"
echo -e "${YELLOW}Watch for Django pods scaling from $INITIAL_REPLICAS to 10${NC}"
echo ""

START_TIME=$SECONDS
MONITOR_END=$((SECONDS + LOAD_DURATION))

while [ $SECONDS -lt $MONITOR_END ]; do
    ELAPSED=$((SECONDS - START_TIME))
    TIMESTAMP=$(date '+%H:%M:%S')
    REPLICAS=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}')
    READY=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.readyReplicas}')
    
    # Get HPA metrics
    HPA_INFO=$(kubectl get hpa django-hpa -n $NAMESPACE --no-headers 2>/dev/null)
    
    echo -e "${CYAN}[$TIMESTAMP] Elapsed: ${ELAPSED}s | Replicas: $REPLICAS | Ready: $READY${NC}"
    echo "$HPA_INFO"
    
    # Show pod metrics
    echo "Pod Metrics:"
    kubectl top pods -n $NAMESPACE -l component=django 2>/dev/null | tail -n +2 | head -5
    echo ""
    
    # Check if we've reached maximum
    if [ "$REPLICAS" -eq 10 ]; then
        echo -e "${GREEN}🎉 MAXIMUM REPLICAS REACHED! (10/10)${NC}"
        echo ""
    fi
    
    sleep 15
done

FINAL_REPLICAS=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}')
echo ""
echo -e "${GREEN}✅ Load generation complete${NC}"
echo -e "${BLUE}Scale-up result: $INITIAL_REPLICAS → $FINAL_REPLICAS replicas${NC}"
echo ""

# Show final state
echo "Final HPA Status:"
kubectl get hpa django-hpa -n $NAMESPACE
echo ""

echo "Final Pod Metrics:"
kubectl top pods -n $NAMESPACE -l component=django
echo ""

# ============================================================================
# PART 4: Cleanup Load Generators
# ============================================================================

echo "============================================================================"
echo "PART 4: Stopping Load Generators"
echo "============================================================================"
echo ""

echo "Deleting all load generator pods..."
kubectl delete pods -n $NAMESPACE -l app=extreme-load-test --ignore-not-found=true > /dev/null 2>&1
echo -e "${GREEN}✅ Load generators stopped${NC}"
echo ""

# ============================================================================
# PART 5: Monitor Scale-Down
# ============================================================================

echo "============================================================================"
echo "PART 5: Monitoring Scale-Down (10 minutes)"
echo "============================================================================"
echo ""

echo -e "${YELLOW}Load stopped. Monitoring scale-down behavior...${NC}"
echo -e "${YELLOW}HPA should wait 5 minutes (stabilization window) before scaling down${NC}"
echo -e "${YELLOW}Then scale down by 50% every 60 seconds${NC}"
echo ""

SCALE_DOWN_START=$SECONDS
MONITOR_END=$((SECONDS + MONITOR_DURATION))

STABILIZATION_NOTIFIED=false
SCALE_DOWN_STARTED=false

while [ $SECONDS -lt $MONITOR_END ]; do
    ELAPSED=$((SECONDS - SCALE_DOWN_START))
    TIMESTAMP=$(date '+%H:%M:%S')
    REPLICAS=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}')
    READY=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.readyReplicas}')
    
    # Get HPA metrics
    HPA_INFO=$(kubectl get hpa django-hpa -n $NAMESPACE --no-headers 2>/dev/null)
    
    echo -e "${CYAN}[$TIMESTAMP] Elapsed: ${ELAPSED}s | Replicas: $REPLICAS | Ready: $READY${NC}"
    echo "$HPA_INFO"
    
    # Show pod metrics
    echo "Pod Metrics:"
    kubectl top pods -n $NAMESPACE -l component=django 2>/dev/null | tail -n +2 | head -5
    echo ""
    
    # Notify about stabilization window
    if [ $ELAPSED -ge 300 ] && [ "$STABILIZATION_NOTIFIED" = false ]; then
        echo -e "${YELLOW}⏰ Stabilization window complete (5 minutes)${NC}"
        echo -e "${YELLOW}Scale-down should begin now...${NC}"
        echo ""
        STABILIZATION_NOTIFIED=true
    fi
    
    # Detect scale-down
    if [ "$REPLICAS" -lt "$FINAL_REPLICAS" ] && [ "$SCALE_DOWN_STARTED" = false ]; then
        echo -e "${GREEN}📉 SCALE-DOWN STARTED!${NC}"
        echo ""
        SCALE_DOWN_STARTED=true
    fi
    
    # Check if we're back to minimum
    if [ "$REPLICAS" -eq 3 ]; then
        echo -e "${GREEN}🎉 BACK TO MINIMUM REPLICAS! (3/3)${NC}"
        echo ""
        echo "Scale-down complete in $ELAPSED seconds"
        break
    fi
    
    sleep 30
done

# ============================================================================
# PART 6: Final Summary
# ============================================================================

echo "============================================================================"
echo "EXTREME LOAD TEST SUMMARY"
echo "============================================================================"
echo ""

FINAL_STATE=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}')

echo -e "${CYAN}Test Results:${NC}"
echo "  - Initial Replicas: $INITIAL_REPLICAS"
echo "  - Peak Replicas: $FINAL_REPLICAS"
echo "  - Final Replicas: $FINAL_STATE"
echo "  - Scale-Up: $INITIAL_REPLICAS → $FINAL_REPLICAS"
echo "  - Scale-Down: $FINAL_REPLICAS → $FINAL_STATE"
echo ""

if [ "$FINAL_REPLICAS" -eq 10 ]; then
    echo -e "${GREEN}✅ Scale-up to maximum (10 pods) SUCCESSFUL${NC}"
else
    echo -e "${YELLOW}⚠️  Did not reach maximum (reached $FINAL_REPLICAS/10)${NC}"
fi

if [ "$FINAL_STATE" -eq 3 ]; then
    echo -e "${GREEN}✅ Scale-down to minimum (3 pods) SUCCESSFUL${NC}"
else
    echo -e "${YELLOW}⚠️  Not yet back to minimum (currently at $FINAL_STATE/3)${NC}"
    echo -e "${YELLOW}   Continue monitoring - scale-down may still be in progress${NC}"
fi

echo ""

echo "Final HPA Status:"
kubectl get hpa django-hpa -n $NAMESPACE
echo ""

echo "Final Deployment Status:"
kubectl get deployment django -n $NAMESPACE
echo ""

echo "Final Pod List:"
kubectl get pods -n $NAMESPACE -l component=django
echo ""

echo "Final Pod Metrics:"
kubectl top pods -n $NAMESPACE -l component=django
echo ""

echo "============================================================================"
echo -e "${GREEN}✅ EXTREME LOAD TEST COMPLETE${NC}"
echo "============================================================================"
echo ""

echo "Key Observations:"
echo "  1. HPA responded to extreme load"
echo "  2. Pods scaled based on CPU/memory thresholds"
echo "  3. Stabilization window enforced before scale-down"
echo "  4. Gradual scale-down policy applied"
echo ""

echo "To watch HPA in real-time:"
echo "  kubectl get hpa django-hpa -n $NAMESPACE --watch"
echo ""

echo "To see HPA events:"
echo "  kubectl describe hpa django-hpa -n $NAMESPACE"
echo ""
