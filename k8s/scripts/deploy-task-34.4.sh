#!/bin/bash

# ============================================================================
# Task 34.4: Deploy Nginx Reverse Proxy
# ============================================================================
# This script deploys Nginx as a reverse proxy in Kubernetes with:
# - Nginx Deployment with 2 replicas
# - ConfigMaps for nginx.conf and site configuration
# - Resource requests and limits
# - TCP health checks on port 80
# - ClusterIP Service
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="jewelry-shop"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}Task 34.4: Deploying Nginx Reverse Proxy${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""

# Function to print status
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if namespace exists
print_status "Checking if namespace '$NAMESPACE' exists..."
if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    print_error "Namespace '$NAMESPACE' does not exist. Please run task 34.2 first."
    exit 1
fi
print_success "Namespace exists"
echo ""

# Check if Django service exists
print_status "Checking if Django service exists..."
if ! kubectl get service django-service -n "$NAMESPACE" &> /dev/null; then
    print_warning "Django service not found. Nginx will not be able to proxy requests."
    print_warning "Please deploy Django (task 34.3) before testing Nginx."
fi
echo ""

# Step 1: Apply Nginx ConfigMaps
print_status "Step 1: Applying Nginx ConfigMaps..."
if kubectl apply -f "$K8S_DIR/nginx-configmap.yaml"; then
    print_success "Nginx ConfigMaps applied"
else
    print_error "Failed to apply Nginx ConfigMaps"
    exit 1
fi
echo ""

# Verify ConfigMaps
print_status "Verifying ConfigMaps..."
for cm in nginx-config nginx-conf-d nginx-snippets; do
    if kubectl get configmap "$cm" -n "$NAMESPACE" &> /dev/null; then
        print_success "ConfigMap '$cm' exists"
    else
        print_error "ConfigMap '$cm' not found"
        exit 1
    fi
done
echo ""

# Step 2: Apply Nginx Deployment
print_status "Step 2: Applying Nginx Deployment..."
if kubectl apply -f "$K8S_DIR/nginx-deployment.yaml"; then
    print_success "Nginx Deployment applied"
else
    print_error "Failed to apply Nginx Deployment"
    exit 1
fi
echo ""

# Step 3: Apply Nginx Service
print_status "Step 3: Applying Nginx Service..."
if kubectl apply -f "$K8S_DIR/nginx-service.yaml"; then
    print_success "Nginx Service applied"
else
    print_error "Failed to apply Nginx Service"
    exit 1
fi
echo ""

# Step 4: Wait for Nginx pods to be ready
print_status "Step 4: Waiting for Nginx pods to be ready (timeout: 120s)..."
if kubectl wait --for=condition=ready pod \
    -l app=jewelry-shop,component=nginx \
    -n "$NAMESPACE" \
    --timeout=120s; then
    print_success "Nginx pods are ready"
else
    print_error "Nginx pods failed to become ready"
    print_status "Checking pod status..."
    kubectl get pods -n "$NAMESPACE" -l component=nginx
    print_status "Checking pod logs..."
    kubectl logs -n "$NAMESPACE" -l component=nginx --tail=50
    exit 1
fi
echo ""

# Step 5: Verify deployment
print_status "Step 5: Verifying Nginx deployment..."

# Check pod count
POD_COUNT=$(kubectl get pods -n "$NAMESPACE" -l component=nginx --field-selector=status.phase=Running -o json | jq '.items | length')
if [ "$POD_COUNT" -eq 2 ]; then
    print_success "Nginx has 2 running pods (as expected)"
else
    print_warning "Nginx has $POD_COUNT running pods (expected 2)"
fi

# Check service
if kubectl get service nginx-service -n "$NAMESPACE" &> /dev/null; then
    print_success "Nginx service exists"
    SERVICE_TYPE=$(kubectl get service nginx-service -n "$NAMESPACE" -o jsonpath='{.spec.type}')
    print_status "Service type: $SERVICE_TYPE"
else
    print_error "Nginx service not found"
    exit 1
fi
echo ""

# Display deployment information
print_status "Deployment Information:"
echo ""
echo -e "${BLUE}Pods:${NC}"
kubectl get pods -n "$NAMESPACE" -l component=nginx -o wide
echo ""
echo -e "${BLUE}Service:${NC}"
kubectl get service nginx-service -n "$NAMESPACE"
echo ""
echo -e "${BLUE}ConfigMaps:${NC}"
kubectl get configmaps -n "$NAMESPACE" | grep nginx
echo ""

# Display next steps
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}Task 34.4: Nginx Deployment Complete!${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "1. Run validation script: ./scripts/validate-task-34.4.sh"
echo "2. Test Nginx proxy to Django backend"
echo "3. Verify static file serving"
echo "4. Check Nginx logs for errors"
echo ""
echo -e "${BLUE}Useful Commands:${NC}"
echo "  # View Nginx pods"
echo "  kubectl get pods -n $NAMESPACE -l component=nginx"
echo ""
echo "  # View Nginx logs"
echo "  kubectl logs -n $NAMESPACE -l component=nginx -f"
echo ""
echo "  # Test Nginx service"
echo "  kubectl run -it --rm debug --image=curlimages/curl --restart=Never -n $NAMESPACE -- curl http://nginx-service"
echo ""
echo "  # Port forward to test locally"
echo "  kubectl port-forward -n $NAMESPACE service/nginx-service 8080:80"
echo ""
