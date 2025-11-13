#!/bin/bash

# Task 34.5: Install and Configure Zalando Postgres Operator
# This script installs Helm and the Zalando Postgres Operator for PostgreSQL high availability

set -e

echo "=========================================="
echo "Task 34.5: Zalando Postgres Operator Setup"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Check if k3d cluster is running
echo "Step 1: Checking k3d cluster status..."
if ! kubectl cluster-info &> /dev/null; then
    print_error "k3d cluster is not running"
    echo "Please start the cluster first with: k3d cluster start jewelry-shop"
    exit 1
fi
print_success "k3d cluster is running"
echo ""

# Install Helm if not already installed
echo "Step 2: Installing Helm..."
if ! command -v helm &> /dev/null; then
    print_info "Helm not found, installing..."
    curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
    print_success "Helm installed successfully"
else
    HELM_VERSION=$(helm version --short)
    print_success "Helm is already installed: $HELM_VERSION"
fi
echo ""

# Add Zalando Postgres Operator Helm repository
echo "Step 3: Adding Zalando Postgres Operator Helm repository..."
if helm repo list | grep -q "postgres-operator-charts"; then
    print_info "Repository already exists, updating..."
    helm repo update postgres-operator-charts
else
    helm repo add postgres-operator-charts https://opensource.zalando.com/postgres-operator/charts/postgres-operator
    print_success "Helm repository added"
fi
helm repo update
print_success "Helm repositories updated"
echo ""

# Create postgres-operator namespace
echo "Step 4: Creating postgres-operator namespace..."
if kubectl get namespace postgres-operator &> /dev/null; then
    print_info "Namespace postgres-operator already exists"
else
    kubectl create namespace postgres-operator
    print_success "Namespace postgres-operator created"
fi
echo ""

# Install Zalando Postgres Operator
echo "Step 5: Installing Zalando Postgres Operator..."
if helm list -n postgres-operator | grep -q "postgres-operator"; then
    print_info "Postgres Operator already installed, upgrading..."
    helm upgrade postgres-operator postgres-operator-charts/postgres-operator \
        --namespace postgres-operator \
        --set configKubernetes.enable_pod_antiaffinity=true \
        --set configKubernetes.watched_namespace="*" \
        --wait \
        --timeout 5m
    print_success "Postgres Operator upgraded"
else
    helm install postgres-operator postgres-operator-charts/postgres-operator \
        --namespace postgres-operator \
        --set configKubernetes.enable_pod_antiaffinity=true \
        --set configKubernetes.watched_namespace="*" \
        --wait \
        --timeout 5m
    print_success "Postgres Operator installed"
fi
echo ""

# Wait for operator pod to be ready
echo "Step 6: Waiting for operator pod to be ready..."
kubectl wait --for=condition=ready pod \
    -l app.kubernetes.io/name=postgres-operator \
    -n postgres-operator \
    --timeout=300s
print_success "Operator pod is ready"
echo ""

# Verify CRD installation
echo "Step 7: Verifying CRD installation..."
if kubectl get crd postgresqls.acid.zalan.do &> /dev/null; then
    print_success "postgresql.acid.zalan.do CRD exists"
else
    print_error "postgresql.acid.zalan.do CRD not found"
    exit 1
fi
echo ""

# Check operator logs
echo "Step 8: Checking operator logs for successful initialization..."
OPERATOR_POD=$(kubectl get pods -n postgres-operator -l app.kubernetes.io/name=postgres-operator -o jsonpath='{.items[0].metadata.name}')
echo "Operator pod: $OPERATOR_POD"
echo ""
echo "Recent operator logs:"
kubectl logs -n postgres-operator $OPERATOR_POD --tail=20
echo ""

# Summary
echo "=========================================="
echo "Deployment Summary"
echo "=========================================="
print_success "Helm installed and configured"
print_success "Zalando Postgres Operator Helm repository added"
print_success "postgres-operator namespace created"
print_success "Postgres Operator installed and running"
print_success "postgresql.acid.zalan.do CRD created"
echo ""
print_info "Next steps:"
echo "  1. Run validation script: ./k8s/scripts/validate-task-34.5.sh"
echo "  2. Proceed to task 34.6: Deploy PostgreSQL cluster with automatic failover"
echo ""
