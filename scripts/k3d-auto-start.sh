#!/bin/bash
################################################################################
# K3D Auto-Start Script
# This script automatically starts the k3d cluster on system boot
################################################################################

set -e

# Configuration
CLUSTER_NAME="jewelry-shop"
MAX_RETRIES=30
RETRY_DELAY=2

echo "🚀 Starting k3d cluster: $CLUSTER_NAME"

# Check if cluster exists
if ! k3d cluster list | grep -q "$CLUSTER_NAME"; then
    echo "❌ Cluster '$CLUSTER_NAME' not found"
    exit 1
fi

# Start the cluster
echo "⏳ Starting cluster..."
k3d cluster start "$CLUSTER_NAME"

# Wait for cluster to be ready
echo "⏳ Waiting for cluster to be ready..."
retries=0
while [ $retries -lt $MAX_RETRIES ]; do
    if kubectl cluster-info &> /dev/null; then
        echo "✅ Cluster is ready!"
        break
    fi
    
    sleep $RETRY_DELAY
    retries=$((retries + 1))
    echo "   Retry $retries/$MAX_RETRIES..."
done

if [ $retries -eq $MAX_RETRIES ]; then
    echo "❌ Cluster failed to become ready"
    exit 1
fi

# Wait for all nodes to be ready
echo "⏳ Waiting for nodes to be ready..."
kubectl wait --for=condition=Ready nodes --all --timeout=120s

# Give pods time to restart
echo "⏳ Waiting for pods to restart (30 seconds)..."
sleep 30

# Check pod status
echo ""
echo "📊 Pod Status:"
kubectl get pods -n jewelry-shop

echo ""
echo "✅ K3d cluster started successfully!"
