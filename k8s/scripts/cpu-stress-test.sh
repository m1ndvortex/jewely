#!/bin/bash

# ============================================================================
# CPU Stress Test - Force HPA Scaling with Direct CPU Load
# ============================================================================
# This script uses stress-ng to directly stress Django pods' CPU
# ============================================================================

set -e

NAMESPACE="jewelry-shop"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "============================================================================"
echo -e "${CYAN}CPU STRESS TEST - Force HPA to Scale${NC}"
echo "============================================================================"
echo ""

echo "This test will:"
echo "  1. Inject CPU stress directly into Django pods"
echo "  2. Force CPU usage above 70% threshold"
echo "  3. Trigger HPA scale-up to maximum (10 pods)"
echo "  4. Monitor the scaling in real-time"
echo "  5. Stop stress and watch scale-down"
echo ""

read -p "Press Enter to start..."
echo ""

# Get initial state
INITIAL_REPLICAS=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}')
echo -e "${GREEN}Initial replicas: $INITIAL_REPLICAS${NC}"
echo ""

# Get all Django pods
DJANGO_PODS=$(kubectl get pods -n $NAMESPACE -l component=django -o jsonpath='{.items[*].metadata.name}')

echo "Injecting CPU stress into Django pods..."
echo ""

# Inject stress into each pod
for POD in $DJANGO_PODS; do
    echo "Stressing pod: $POD"
    kubectl exec -n $NAMESPACE $POD -- sh -c "nohup sh -c 'while true; do :; done' > /dev/null 2>&1 &" &
    kubectl exec -n $NAMESPACE $POD -- sh -c "nohup sh -c 'while true; do :; done' > /dev/null 2>&1 &" &
    kubectl exec -n $NAMESPACE $POD -- sh -c "nohup sh -c 'while true; do :; done' > /dev/null 2>&1 &" &
done

echo ""
echo -e "${GREEN}✅ CPU stress injected into all Django pods${NC}"
echo ""

echo "Waiting 30 seconds for metrics to update..."
sleep 30

echo ""
echo "Monitoring HPA scaling for 5 minutes..."
echo ""

# Monitor for 5 minutes
for i in {1..20}; do
    TIMESTAMP=$(date '+%H:%M:%S')
    REPLICAS=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}')
    READY=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.readyReplicas}')
    
    if [ "$REPLICAS" -ge 10 ]; then
        COLOR=$GREEN
        STATUS="🎯 MAX!"
    elif [ "$REPLICAS" -ge 7 ]; then
        COLOR=$YELLOW
        STATUS="📈 Scaling..."
    else
        COLOR=$CYAN
        STATUS="⏳ Starting..."
    fi
    
    echo -e "${COLOR}[$TIMESTAMP] Replicas: $REPLICAS/$READY | $STATUS${NC}"
    kubectl get hpa django-hpa -n $NAMESPACE --no-headers
    
    echo "  Top CPU pods:"
    kubectl top pods -n $NAMESPACE -l component=django --no-headers 2>/dev/null | sort -k2 -rn | head -5 | while read line; do
        echo "    $line"
    done
    
    echo ""
    
    if [ "$REPLICAS" -eq 10 ]; then
        echo -e "${GREEN}🎉 MAXIMUM REACHED!${NC}"
        break
    fi
    
    sleep 15
done

echo ""
echo -e "${YELLOW}Stopping CPU stress...${NC}"
echo ""

# Kill stress processes in all pods
DJANGO_PODS=$(kubectl get pods -n $NAMESPACE -l component=django -o jsonpath='{.items[*].metadata.name}')
for POD in $DJANGO_PODS; do
    echo "Stopping stress in: $POD"
    kubectl exec -n $NAMESPACE $POD -- sh -c "killall sh" 2>/dev/null || true
done

echo ""
echo -e "${GREEN}✅ Stress stopped${NC}"
echo ""

FINAL_REPLICAS=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}')
echo "Final replica count: $FINAL_REPLICAS"
echo ""

echo "Monitoring scale-down for 7 minutes..."
echo ""

# Monitor scale-down
for i in {1..14}; do
    TIMESTAMP=$(date '+%H:%M:%S')
    REPLICAS=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}')
    READY=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.readyReplicas}')
    
    if [ "$REPLICAS" -eq 3 ]; then
        COLOR=$GREEN
        STATUS="✅ Minimum!"
    else
        COLOR=$YELLOW
        STATUS="📉 Scaling down..."
    fi
    
    echo -e "${COLOR}[$TIMESTAMP] Replicas: $REPLICAS/$READY | $STATUS${NC}"
    kubectl get hpa django-hpa -n $NAMESPACE --no-headers
    echo ""
    
    if [ "$REPLICAS" -eq 3 ]; then
        echo -e "${GREEN}🎉 BACK TO MINIMUM!${NC}"
        break
    fi
    
    sleep 30
done

echo ""
echo "============================================================================"
echo -e "${GREEN}TEST COMPLETE!${NC}"
echo "============================================================================"
echo ""
echo "Journey: $INITIAL_REPLICAS → $FINAL_REPLICAS → $(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}')"
echo ""
