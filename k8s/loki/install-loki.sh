#!/bin/bash

# Loki Installation Script for Kubernetes
# This script deploys Loki and Promtail for centralized log aggregation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="jewelry-shop"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Loki Installation for Kubernetes${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to print colored messages
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
print_info "Checking prerequisites..."

if ! command_exists kubectl; then
    print_error "kubectl is not installed. Please install kubectl first."
    exit 1
fi

# Check if namespace exists
if ! kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
    print_warning "Namespace $NAMESPACE does not exist. Creating it..."
    kubectl create namespace "$NAMESPACE"
    print_success "Namespace $NAMESPACE created"
fi

# Step 1: Deploy Loki ConfigMap
print_info "Step 1/6: Deploying Loki ConfigMap..."
kubectl apply -f "$SCRIPT_DIR/loki-configmap.yaml"
print_success "Loki ConfigMap deployed"

# Step 2: Deploy Loki Deployment and Service
print_info "Step 2/6: Deploying Loki..."
kubectl apply -f "$SCRIPT_DIR/loki-deployment.yaml"
print_success "Loki deployment created"

# Wait for Loki to be ready
print_info "Waiting for Loki pod to be ready (this may take a minute)..."
kubectl wait --for=condition=ready pod -l app=loki -n "$NAMESPACE" --timeout=300s || {
    print_error "Loki pod failed to become ready"
    print_info "Checking pod status..."
    kubectl get pods -n "$NAMESPACE" -l app=loki
    print_info "Checking pod logs..."
    kubectl logs -n "$NAMESPACE" -l app=loki --tail=50
    exit 1
}
print_success "Loki is ready"

# Step 3: Deploy Promtail RBAC
print_info "Step 3/6: Deploying Promtail RBAC..."
kubectl apply -f "$SCRIPT_DIR/promtail-rbac.yaml"
print_success "Promtail RBAC deployed"

# Step 4: Deploy Promtail ConfigMap
print_info "Step 4/6: Deploying Promtail ConfigMap..."
kubectl apply -f "$SCRIPT_DIR/promtail-configmap.yaml"
print_success "Promtail ConfigMap deployed"

# Step 5: Deploy Promtail DaemonSet
print_info "Step 5/6: Deploying Promtail DaemonSet..."
kubectl apply -f "$SCRIPT_DIR/promtail-daemonset.yaml"
print_success "Promtail DaemonSet created"

# Wait for Promtail to be ready
print_info "Waiting for Promtail pods to be ready..."
sleep 10
PROMTAIL_PODS=$(kubectl get pods -n "$NAMESPACE" -l app=promtail --no-headers | wc -l)
print_info "Found $PROMTAIL_PODS Promtail pods (one per node)"

# Step 6: Deploy Loki Datasource for Grafana
print_info "Step 6/6: Deploying Loki Datasource for Grafana..."
kubectl apply -f "$SCRIPT_DIR/loki-datasource.yaml"
print_success "Loki Datasource deployed"

# Check if Grafana exists and restart it to pick up new datasource
if kubectl get deployment grafana -n "$NAMESPACE" >/dev/null 2>&1; then
    print_info "Restarting Grafana to load Loki datasource..."
    kubectl rollout restart deployment/grafana -n "$NAMESPACE"
    kubectl rollout status deployment/grafana -n "$NAMESPACE" --timeout=120s
    print_success "Grafana restarted"
else
    print_warning "Grafana not found. Deploy Grafana to visualize logs."
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Loki Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Display deployment status
print_info "Deployment Status:"
echo ""
echo "Loki:"
kubectl get deployment loki -n "$NAMESPACE"
echo ""
echo "Loki Service:"
kubectl get service loki -n "$NAMESPACE"
echo ""
echo "Promtail DaemonSet:"
kubectl get daemonset promtail -n "$NAMESPACE"
echo ""
echo "Promtail Pods:"
kubectl get pods -n "$NAMESPACE" -l app=promtail
echo ""

# Display access information
print_info "Access Information:"
echo ""
echo "Loki API URL (internal): http://loki.jewelry-shop.svc.cluster.local:3100"
echo ""
echo "To query logs from Loki:"
echo "  kubectl port-forward -n $NAMESPACE svc/loki 3100:3100"
echo "  curl http://localhost:3100/loki/api/v1/labels"
echo ""
echo "To view logs in Grafana:"
echo "  1. Access Grafana dashboard"
echo "  2. Go to Explore"
echo "  3. Select 'Loki' as data source"
echo "  4. Use LogQL queries to search logs"
echo ""
echo "Example LogQL queries:"
echo "  {namespace=\"jewelry-shop\"}"
echo "  {app=\"django\"} |= \"error\""
echo "  {app=\"celery-worker\"} |= \"task\""
echo "  {app=\"nginx\"} | json | status >= 400"
echo ""

print_info "Next Steps:"
echo "  1. Run validation: ./validate-loki.sh"
echo "  2. View logs in Grafana Explore"
echo "  3. Create log-based alerts in Grafana"
echo ""

print_success "Loki is now collecting logs from all pods in the $NAMESPACE namespace!"
