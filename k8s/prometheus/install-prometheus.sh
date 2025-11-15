#!/bin/bash

# ============================================================================
# Prometheus Installation Script for Kubernetes
# Task 35.1: Deploy Prometheus
# Requirement 24: Monitoring and Observability
# ============================================================================

set -e

NAMESPACE="jewelry-shop"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================================================"
echo "Installing Prometheus for Jewelry SaaS Platform"
echo "============================================================================"
echo ""

# Check if namespace exists
if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    echo "❌ Error: Namespace '$NAMESPACE' does not exist"
    echo "Please create the namespace first: kubectl create namespace $NAMESPACE"
    exit 1
fi

echo "✅ Namespace '$NAMESPACE' exists"
echo ""

# Step 1: Create RBAC resources
echo "📋 Step 1: Creating RBAC resources (ServiceAccount, ClusterRole, ClusterRoleBinding)..."
kubectl apply -f "$SCRIPT_DIR/prometheus-rbac.yaml"
echo "✅ RBAC resources created"
echo ""

# Step 2: Create ConfigMap
echo "📋 Step 2: Creating Prometheus ConfigMap..."
kubectl apply -f "$SCRIPT_DIR/prometheus-configmap.yaml"
echo "✅ ConfigMap created"
echo ""

# Step 3: Create PersistentVolumeClaim and Deployment
echo "📋 Step 3: Creating Prometheus Deployment and PersistentVolumeClaim..."
kubectl apply -f "$SCRIPT_DIR/prometheus-deployment.yaml"
echo "✅ Deployment and PVC created"
echo ""

# Step 4: Create Service
echo "📋 Step 4: Creating Prometheus Service..."
kubectl apply -f "$SCRIPT_DIR/prometheus-service.yaml"
echo "✅ Service created"
echo ""

# Wait for Prometheus to be ready
echo "⏳ Waiting for Prometheus pod to be ready..."
kubectl wait --for=condition=ready pod -l app=prometheus -n "$NAMESPACE" --timeout=300s

echo ""
echo "============================================================================"
echo "✅ Prometheus Installation Complete!"
echo "============================================================================"
echo ""

# Get pod status
echo "📊 Prometheus Pod Status:"
kubectl get pods -n "$NAMESPACE" -l app=prometheus
echo ""

# Get service info
echo "📊 Prometheus Service:"
kubectl get svc -n "$NAMESPACE" -l app=prometheus
echo ""

# Get PVC status
echo "📊 Prometheus Storage:"
kubectl get pvc -n "$NAMESPACE" -l app=prometheus
echo ""

echo "============================================================================"
echo "🎯 Next Steps:"
echo "============================================================================"
echo ""
echo "1. Access Prometheus UI:"
echo "   kubectl port-forward -n $NAMESPACE svc/prometheus 9090:9090"
echo "   Then open: http://localhost:9090"
echo ""
echo "2. Check Prometheus targets:"
echo "   Open Prometheus UI → Status → Targets"
echo ""
echo "3. Verify metrics collection:"
echo "   Query: up"
echo "   Query: django_http_requests_total"
echo ""
echo "4. Check Prometheus logs:"
echo "   kubectl logs -n $NAMESPACE -l app=prometheus -f"
echo ""
echo "5. Reload Prometheus configuration (if needed):"
echo "   kubectl exec -n $NAMESPACE -it \$(kubectl get pod -n $NAMESPACE -l app=prometheus -o jsonpath='{.items[0].metadata.name}') -- kill -HUP 1"
echo ""
echo "============================================================================"
