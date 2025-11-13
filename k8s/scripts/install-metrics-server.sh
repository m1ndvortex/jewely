#!/bin/bash

# ============================================================================
# Install Metrics Server for Kubernetes
# ============================================================================
# Metrics Server collects resource metrics from Kubelets and exposes them
# via the Metrics API for use by HPA and kubectl top commands.
# ============================================================================

set -e

echo "============================================================================"
echo "Installing Metrics Server for Kubernetes"
echo "============================================================================"

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl not found. Please install kubectl first."
    exit 1
fi

# Check if cluster is accessible
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster. Please check your kubeconfig."
    exit 1
fi

echo ""
echo "📦 Installing Metrics Server..."
echo ""

# Install metrics-server with insecure TLS for k3d/k3s
# In production, remove --kubelet-insecure-tls flag
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

echo ""
echo "⏳ Waiting for Metrics Server to be ready..."
echo ""

# Wait for metrics-server deployment to be ready
kubectl wait --for=condition=available --timeout=120s deployment/metrics-server -n kube-system

echo ""
echo "🔧 Patching Metrics Server for k3d/k3s compatibility..."
echo ""

# Patch metrics-server to work with k3d/k3s (self-signed certificates)
kubectl patch deployment metrics-server -n kube-system --type='json' -p='[
  {
    "op": "add",
    "path": "/spec/template/spec/containers/0/args/-",
    "value": "--kubelet-insecure-tls"
  }
]'

echo ""
echo "⏳ Waiting for patched Metrics Server to be ready..."
echo ""

# Wait for the patched deployment to roll out
kubectl rollout status deployment/metrics-server -n kube-system --timeout=120s

echo ""
echo "✅ Metrics Server installed successfully!"
echo ""

# Wait a bit for metrics to be collected
echo "⏳ Waiting 30 seconds for metrics collection to start..."
sleep 30

echo ""
echo "📊 Testing Metrics Server..."
echo ""

# Test if metrics are available
if kubectl top nodes &> /dev/null; then
    echo "✅ Node metrics available:"
    kubectl top nodes
else
    echo "⚠️  Node metrics not yet available. This may take a few more seconds."
fi

echo ""

if kubectl top pods -n jewelry-shop &> /dev/null; then
    echo "✅ Pod metrics available:"
    kubectl top pods -n jewelry-shop
else
    echo "⚠️  Pod metrics not yet available. This may take a few more seconds."
fi

echo ""
echo "============================================================================"
echo "✅ Metrics Server Installation Complete!"
echo "============================================================================"
echo ""
echo "You can now use:"
echo "  - kubectl top nodes"
echo "  - kubectl top pods -n jewelry-shop"
echo "  - Horizontal Pod Autoscaler (HPA)"
echo ""
echo "Note: It may take 1-2 minutes for metrics to be fully available."
echo "============================================================================"
