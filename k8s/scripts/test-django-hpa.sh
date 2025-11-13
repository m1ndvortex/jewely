#!/bin/bash

# ============================================================================
# Test Django HPA Scaling Behavior
# ============================================================================
# This script tests the Horizontal Pod Autoscaler for Django pods by:
# 1. Verifying HPA is configured correctly
# 2. Checking current metrics and replica count
# 3. Generating load to trigger scale-up
# 4. Monitoring scale-up behavior
# 5. Stopping load and monitoring scale-down
# ============================================================================

set -e

NAMESPACE="jewelry-shop"
HPA_NAME="django-hpa"
SERVICE_NAME="django-service"
LOAD_DURATION=180  # 3 minutes of load

echo "============================================================================"
echo "Django HPA Scaling Test"
echo "============================================================================"

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl not found. Please install kubectl first."
    exit 1
fi

# Check if cluster is accessible
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster."
    exit 1
fi

echo ""
echo "📊 Step 1: Verify HPA Configuration"
echo "============================================================================"
echo ""

# Check if HPA exists
if ! kubectl get hpa $HPA_NAME -n $NAMESPACE &> /dev/null; then
    echo "❌ HPA '$HPA_NAME' not found in namespace '$NAMESPACE'"
    echo "Please deploy the HPA first: kubectl apply -f k8s/django-hpa.yaml"
    exit 1
fi

echo "✅ HPA found. Current configuration:"
echo ""
kubectl get hpa $HPA_NAME -n $NAMESPACE
echo ""

# Show detailed HPA configuration
echo "📋 Detailed HPA Configuration:"
echo ""
kubectl describe hpa $HPA_NAME -n $NAMESPACE
echo ""

echo "============================================================================"
echo "📊 Step 2: Check Current Metrics and Replica Count"
echo "============================================================================"
echo ""

# Check if metrics-server is working
if ! kubectl top pods -n $NAMESPACE &> /dev/null; then
    echo "⚠️  Metrics not available yet. Waiting 30 seconds..."
    sleep 30
fi

echo "Current Pod Metrics:"
echo ""
kubectl top pods -n $NAMESPACE -l component=django
echo ""

echo "Current Replica Count:"
echo ""
kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}' && echo " replicas"
echo ""

echo "============================================================================"
echo "📊 Step 3: Generate Load to Trigger Scale-Up"
echo "============================================================================"
echo ""

echo "Starting load generator for $LOAD_DURATION seconds..."
echo "This will send continuous requests to the Django service."
echo ""

# Create load generator pod
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: load-generator
  namespace: $NAMESPACE
  labels:
    app: load-generator
spec:
  containers:
  - name: load-generator
    image: busybox:1.35
    command:
    - /bin/sh
    - -c
    - |
      echo "Starting load generation..."
      END_TIME=\$((SECONDS + $LOAD_DURATION))
      REQUEST_COUNT=0
      
      while [ \$SECONDS -lt \$END_TIME ]; do
        wget -q -O- http://$SERVICE_NAME.$NAMESPACE.svc.cluster.local:80/ > /dev/null 2>&1 || true
        REQUEST_COUNT=\$((REQUEST_COUNT + 1))
        
        # Print progress every 100 requests
        if [ \$((REQUEST_COUNT % 100)) -eq 0 ]; then
          echo "Sent \$REQUEST_COUNT requests..."
        fi
      done
      
      echo "Load generation complete. Total requests: \$REQUEST_COUNT"
      echo "Sleeping to keep pod alive for inspection..."
      sleep 300
  restartPolicy: Never
EOF

echo ""
echo "✅ Load generator pod created"
echo ""

# Wait for load generator to start
echo "⏳ Waiting for load generator to start..."
kubectl wait --for=condition=Ready pod/load-generator -n $NAMESPACE --timeout=60s
echo ""

echo "============================================================================"
echo "📊 Step 4: Monitor Scale-Up Behavior"
echo "============================================================================"
echo ""

echo "Monitoring HPA and pod count for $LOAD_DURATION seconds..."
echo "Watch for pods scaling from 3 to 10 as load increases."
echo ""
echo "Press Ctrl+C to stop monitoring early (load will continue)"
echo ""

# Monitor for the duration of the load test
MONITOR_END=$((SECONDS + LOAD_DURATION))
while [ $SECONDS -lt $MONITOR_END ]; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    REPLICAS=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}')
    READY_REPLICAS=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.readyReplicas}')
    
    echo "[$TIMESTAMP] Replicas: $REPLICAS | Ready: $READY_REPLICAS"
    
    # Show HPA status
    kubectl get hpa $HPA_NAME -n $NAMESPACE --no-headers
    
    echo ""
    sleep 15
done

echo ""
echo "✅ Load generation complete"
echo ""

# Show final metrics
echo "Final Pod Metrics:"
echo ""
kubectl top pods -n $NAMESPACE -l component=django
echo ""

echo "Final HPA Status:"
echo ""
kubectl get hpa $HPA_NAME -n $NAMESPACE
echo ""

echo "============================================================================"
echo "📊 Step 5: Monitor Scale-Down Behavior"
echo "============================================================================"
echo ""

echo "Load has stopped. Monitoring scale-down behavior..."
echo "HPA should wait 5 minutes (stabilization window) before scaling down."
echo "Then it will scale down by 50% every 60 seconds."
echo ""
echo "Monitoring for 10 minutes. Press Ctrl+C to stop early."
echo ""

# Monitor scale-down for 10 minutes
MONITOR_END=$((SECONDS + 600))
while [ $SECONDS -lt $MONITOR_END ]; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    REPLICAS=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.replicas}')
    READY_REPLICAS=$(kubectl get deployment django -n $NAMESPACE -o jsonpath='{.status.readyReplicas}')
    
    echo "[$TIMESTAMP] Replicas: $REPLICAS | Ready: $READY_REPLICAS"
    
    # Show HPA status
    kubectl get hpa $HPA_NAME -n $NAMESPACE --no-headers
    
    echo ""
    
    # If we're back to 3 replicas, we're done
    if [ "$REPLICAS" -eq 3 ]; then
        echo "✅ Scaled back down to minimum (3 replicas)"
        break
    fi
    
    sleep 30
done

echo ""
echo "============================================================================"
echo "📊 Test Summary"
echo "============================================================================"
echo ""

echo "Final HPA Configuration:"
echo ""
kubectl get hpa $HPA_NAME -n $NAMESPACE
echo ""

echo "Final Deployment Status:"
echo ""
kubectl get deployment django -n $NAMESPACE
echo ""

echo "Final Pod Status:"
echo ""
kubectl get pods -n $NAMESPACE -l component=django
echo ""

# Cleanup load generator
echo "🧹 Cleaning up load generator pod..."
kubectl delete pod load-generator -n $NAMESPACE --ignore-not-found=true
echo ""

echo "============================================================================"
echo "✅ HPA Test Complete!"
echo "============================================================================"
echo ""
echo "Review the output above to verify:"
echo "  ✓ HPA scaled up from 3 to 10 pods under load"
echo "  ✓ Scale-up was aggressive (100% increase every 15s)"
echo "  ✓ HPA scaled down after 5-minute stabilization window"
echo "  ✓ Scale-down was gradual (50% decrease every 60s)"
echo ""
echo "To watch HPA in real-time, use:"
echo "  kubectl get hpa $HPA_NAME -n $NAMESPACE --watch"
echo ""
echo "To see current metrics, use:"
echo "  kubectl top pods -n $NAMESPACE -l component=django"
echo "============================================================================"
