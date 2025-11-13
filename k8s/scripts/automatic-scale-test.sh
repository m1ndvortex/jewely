#!/bin/bash

# ============================================================================
# Automatic Scale Test - Full Scale-Up and Scale-Down Cycle
# ============================================================================
# This script demonstrates AUTOMATIC scaling:
# 1. Scales UP from 3 to 10 pods (automatic)
# 2. Scales DOWN from 10 to 3 pods (automatic)
# No manual intervention required!
# ============================================================================

set -e

NAMESPACE="jewelry-shop"
STRESS_DURATION=180  # 3 minutes of stress
MONITOR_DURATION=600  # 10 minutes to monitor scale-down

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

echo "============================================================================"
echo -e "${CYAN}AUTOMATIC SCALE TEST - Full Up/Down Cycle${NC}"
echo "============================================================================"
echo ""

echo -e "${YELLOW}This test demonstrates FULLY AUTOMATIC scaling:${NC}"
echo ""
echo "  Phase 1: Inject time-limited CPU stress (3 minutes)"
echo "  Phase 2: Watch AUTOMATIC scale-up (3 → 10 pods)"
echo "  Phase 3: Stress stops automatically after 3 minutes"
echo "  Phase 4: Watch AUTOMATIC scale-down (10 → 3 pods)"
echo ""
echo "Total duration: ~15 minutes"
echo "  - 3 min stress + scale-up"
echo "  - 5 min stabilization window"
echo "  - 2-3 min gradual scale-down"
echo ""

read -p "Press Enter to start the AUTOMATIC scale test..."
echo ""

# ============================================================================
# PART 1: Initial State
# ============================================================================

echo "============================================================================"
echo -e "${BLUE}PART 1: Initial State${NC}"
echo "============================================================================"
echo ""

INITIAL_REPLICAS=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}')
echo -e "${GREEN}Initial Django replicas: $INITIAL_REPLICAS${NC}"
echo ""

kubectl get hpa django-hpa -n $NAMESPACE
echo ""

kubectl get pods -n $NAMESPACE -l component=django
echo ""

# ============================================================================
# PART 2: Deploy Time-Limited Stress
# ============================================================================

echo "============================================================================"
echo -e "${BLUE}PART 2: Deploying Time-Limited CPU Stress${NC}"
echo "============================================================================"
echo ""

echo "Creating stress pods that will run for exactly $STRESS_DURATION seconds..."
echo ""

# Create a job that stresses Django pods for a limited time
cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: django-cpu-stress
  namespace: $NAMESPACE
spec:
  ttlSecondsAfterFinished: 60
  template:
    metadata:
      labels:
        app: cpu-stress
    spec:
      restartPolicy: Never
      containers:
      - name: stress
        image: busybox:1.35
        command:
        - /bin/sh
        - -c
        - |
          echo "Starting time-limited CPU stress for $STRESS_DURATION seconds..."
          
          # Get all Django pods
          DJANGO_PODS=\$(wget -qO- --header="Authorization: Bearer \$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)" --no-check-certificate https://kubernetes.default.svc/api/v1/namespaces/$NAMESPACE/pods?labelSelector=component=django | grep -o '"name":"django-[^"]*"' | cut -d'"' -f4)
          
          echo "Found Django pods:"
          echo "\$DJANGO_PODS"
          
          # Start stress on each pod
          for POD in \$DJANGO_PODS; do
            echo "Stressing pod: \$POD"
            
            # Use kubectl exec via API (simplified - using direct pod exec)
            # In real scenario, we'd use proper API calls
            # For now, we'll stress via service calls
          done
          
          # Generate CPU-intensive load by hitting the service repeatedly
          END_TIME=\$((SECONDS + $STRESS_DURATION))
          REQUEST_COUNT=0
          
          echo "Generating load for $STRESS_DURATION seconds..."
          
          while [ \$SECONDS -lt \$END_TIME ]; do
            # Launch 50 parallel requests
            for i in \$(seq 1 50); do
              (
                # Multiple requests per worker
                for j in \$(seq 1 10); do
                  wget -q -O- --timeout=1 http://django-service.$NAMESPACE.svc.cluster.local:80/ > /dev/null 2>&1 || true
                done
              ) &
            done
            
            REQUEST_COUNT=\$((REQUEST_COUNT + 500))
            
            if [ \$((REQUEST_COUNT % 5000)) -eq 0 ]; then
              ELAPSED=\$((SECONDS))
              REMAINING=\$(($STRESS_DURATION - ELAPSED))
              echo "[\$(date +%H:%M:%S)] Sent \$REQUEST_COUNT requests | \${REMAINING}s remaining"
            fi
            
            # Small sleep
            sleep 0.5
          done
          
          # Wait for background jobs
          wait
          
          echo "Stress complete! Total requests: \$REQUEST_COUNT"
          echo "Stress will now stop automatically."
          echo "HPA will detect low CPU and scale down after 5-minute stabilization window."
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 256Mi
      serviceAccountName: default
EOF

echo ""
echo -e "${GREEN}✅ Time-limited stress job created${NC}"
echo -e "${YELLOW}⏱️  Stress will run for exactly $STRESS_DURATION seconds, then stop automatically${NC}"
echo ""

sleep 5

# ============================================================================
# PART 3: Monitor Automatic Scale-Up
# ============================================================================

echo "============================================================================"
echo -e "${BLUE}PART 3: Monitoring AUTOMATIC Scale-Up${NC}"
echo "============================================================================"
echo ""

echo -e "${CYAN}Watching Django scale from $INITIAL_REPLICAS to 10 pods automatically...${NC}"
echo ""

MAX_REPLICAS=$INITIAL_REPLICAS
SCALE_UP_COMPLETE=false

# Monitor for stress duration + buffer
MONITOR_END=$((SECONDS + STRESS_DURATION + 60))

while [ $SECONDS -lt $MONITOR_END ]; do
    TIMESTAMP=$(date '+%H:%M:%S')
    REPLICAS=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}')
    READY=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.readyReplicas}')
    
    # Track maximum
    if [ "$REPLICAS" -gt "$MAX_REPLICAS" ]; then
        MAX_REPLICAS=$REPLICAS
        echo -e "${GREEN}📈 Scaled up to $MAX_REPLICAS replicas!${NC}"
    fi
    
    # Color based on progress
    if [ "$REPLICAS" -ge 10 ]; then
        COLOR=$GREEN
        STATUS="🎯 MAXIMUM REACHED!"
        SCALE_UP_COMPLETE=true
    elif [ "$REPLICAS" -ge 7 ]; then
        COLOR=$YELLOW
        STATUS="📈 Scaling up..."
    elif [ "$REPLICAS" -ge 5 ]; then
        COLOR=$CYAN
        STATUS="⏫ Growing..."
    else
        COLOR=$BLUE
        STATUS="⏳ Starting..."
    fi
    
    echo -e "${COLOR}[$TIMESTAMP] Django: $REPLICAS/$READY replicas | $STATUS${NC}"
    
    # Show HPA
    HPA_LINE=$(kubectl get hpa django-hpa -n $NAMESPACE --no-headers 2>/dev/null)
    echo "  $HPA_LINE"
    
    # Show stress job status
    JOB_STATUS=$(kubectl get job django-cpu-stress -n $NAMESPACE -o jsonpath='{.status.active}' 2>/dev/null || echo "0")
    if [ "$JOB_STATUS" = "1" ]; then
        echo -e "  ${YELLOW}⚡ Stress job: ACTIVE${NC}"
    else
        echo -e "  ${GREEN}✅ Stress job: COMPLETED${NC}"
    fi
    
    echo ""
    
    # Check if stress job completed
    JOB_SUCCEEDED=$(kubectl get job django-cpu-stress -n $NAMESPACE -o jsonpath='{.status.succeeded}' 2>/dev/null || echo "0")
    if [ "$JOB_SUCCEEDED" = "1" ] && [ "$SCALE_UP_COMPLETE" = true ]; then
        echo -e "${GREEN}✅ Stress completed AND maximum replicas reached!${NC}"
        echo ""
        break
    fi
    
    sleep 15
done

echo -e "${GREEN}📊 Maximum replicas reached: $MAX_REPLICAS${NC}"
echo ""

# ============================================================================
# PART 4: Monitor Automatic Scale-Down
# ============================================================================

echo "============================================================================"
echo -e "${BLUE}PART 4: Monitoring AUTOMATIC Scale-Down${NC}"
echo "============================================================================"
echo ""

echo -e "${YELLOW}⏱️  HPA will wait 5 minutes (stabilization window) before scaling down${NC}"
echo -e "${YELLOW}📉 Then it will scale down by 50% every 60 seconds${NC}"
echo ""

CURRENT_REPLICAS=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}')
echo -e "${CYAN}Starting scale-down monitoring from $CURRENT_REPLICAS replicas...${NC}"
echo ""

SCALE_DOWN_STARTED=false
STABILIZATION_COMPLETE=false

# Monitor scale-down
MONITOR_END=$((SECONDS + MONITOR_DURATION))

while [ $SECONDS -lt $MONITOR_END ]; do
    TIMESTAMP=$(date '+%H:%M:%S')
    REPLICAS=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}')
    READY=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.readyReplicas}')
    
    # Detect scale-down start
    if [ "$REPLICAS" -lt "$CURRENT_REPLICAS" ]; then
        if [ "$SCALE_DOWN_STARTED" = false ]; then
            SCALE_DOWN_STARTED=true
            STABILIZATION_COMPLETE=true
            echo -e "${YELLOW}🔽 AUTOMATIC SCALE-DOWN STARTED!${NC}"
            echo -e "${GREEN}✅ Stabilization window (5 minutes) completed${NC}"
            echo ""
        fi
        CURRENT_REPLICAS=$REPLICAS
        echo -e "${YELLOW}📉 Scaled down to $REPLICAS replicas${NC}"
    fi
    
    # Color based on state
    if [ "$REPLICAS" -eq 3 ]; then
        COLOR=$GREEN
        STATUS="✅ MINIMUM REACHED!"
    elif [ "$REPLICAS" -le 5 ]; then
        COLOR=$YELLOW
        STATUS="📉 Scaling down..."
    elif [ "$SCALE_DOWN_STARTED" = true ]; then
        COLOR=$CYAN
        STATUS="📉 Scaling down..."
    else
        COLOR=$BLUE
        STATUS="⏳ Stabilizing..."
    fi
    
    echo -e "${COLOR}[$TIMESTAMP] Django: $REPLICAS/$READY replicas | $STATUS${NC}"
    
    # Show HPA
    HPA_LINE=$(kubectl get hpa django-hpa -n $NAMESPACE --no-headers 2>/dev/null)
    echo "  $HPA_LINE"
    
    echo ""
    
    # If back to minimum, we're done!
    if [ "$REPLICAS" -eq 3 ]; then
        echo -e "${GREEN}🎉 AUTOMATIC SCALE-DOWN COMPLETE!${NC}"
        echo -e "${GREEN}✅ Returned to minimum (3 replicas)${NC}"
        echo ""
        break
    fi
    
    sleep 30
done

# ============================================================================
# PART 5: Final Summary
# ============================================================================

echo "============================================================================"
echo -e "${BLUE}FINAL SUMMARY${NC}"
echo "============================================================================"
echo ""

FINAL_REPLICAS=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}')

echo -e "${CYAN}Complete Scaling Journey:${NC}"
echo "  🚀 Initial:  $INITIAL_REPLICAS replicas"
echo "  📈 Maximum:  $MAX_REPLICAS replicas (automatic scale-up)"
echo "  📉 Final:    $FINAL_REPLICAS replicas (automatic scale-down)"
echo ""

if [ "$MAX_REPLICAS" -ge 9 ]; then
    echo -e "${GREEN}✅ SUCCESS: Reached near-maximum replicas ($MAX_REPLICAS/10)${NC}"
else
    echo -e "${YELLOW}⚠️  Reached $MAX_REPLICAS replicas (target was 10)${NC}"
fi

if [ "$FINAL_REPLICAS" -eq 3 ]; then
    echo -e "${GREEN}✅ SUCCESS: Automatically scaled back to minimum (3)${NC}"
elif [ "$SCALE_DOWN_STARTED" = true ]; then
    echo -e "${YELLOW}⏳ Scale-down in progress (currently at $FINAL_REPLICAS)${NC}"
else
    echo -e "${YELLOW}⏳ Still in stabilization window (currently at $FINAL_REPLICAS)${NC}"
fi

echo ""

echo "Final HPA Status:"
kubectl get hpa django-hpa -n $NAMESPACE
echo ""

echo "Final Pod Status:"
kubectl get pods -n $NAMESPACE -l component=django
echo ""

echo "Pod Metrics:"
kubectl top pods -n $NAMESPACE -l component=django
echo ""

# Cleanup
echo "Cleaning up stress job..."
kubectl delete job django-cpu-stress -n $NAMESPACE --ignore-not-found=true
echo ""

echo "============================================================================"
echo -e "${GREEN}✅ AUTOMATIC SCALE TEST COMPLETE!${NC}"
echo "============================================================================"
echo ""

if [ "$MAX_REPLICAS" -ge 9 ] && [ "$FINAL_REPLICAS" -eq 3 ]; then
    echo -e "${GREEN}🎉 PERFECT! HPA automatically scaled UP and DOWN!${NC}"
    echo ""
    echo "  ✓ Scaled up from $INITIAL_REPLICAS to $MAX_REPLICAS (automatic)"
    echo "  ✓ Scaled down from $MAX_REPLICAS to $FINAL_REPLICAS (automatic)"
    echo "  ✓ No manual intervention required!"
elif [ "$MAX_REPLICAS" -ge 9 ]; then
    echo -e "${YELLOW}✓ Scaled up successfully, scale-down still in progress${NC}"
    echo ""
    echo "  ✓ Scaled up from $INITIAL_REPLICAS to $MAX_REPLICAS (automatic)"
    echo "  ⏳ Scale-down in progress (currently at $FINAL_REPLICAS)"
    echo ""
    echo "Continue watching with:"
    echo "  kubectl get hpa django-hpa -n $NAMESPACE --watch"
else
    echo -e "${YELLOW}⚠️  Did not reach maximum replicas${NC}"
    echo "  May need more aggressive load or longer stress duration"
fi

echo ""
echo "============================================================================"
