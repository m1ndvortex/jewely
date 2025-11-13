#!/bin/bash

# ============================================================================
# Deployment Script for Task 34.2
# ============================================================================
# This script deploys all resources for task 34.2:
# - Creates namespace
# - Creates ConfigMaps
# - Creates Secrets
# - Applies ResourceQuotas
# - Applies LimitRanges
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print section headers
print_header() {
    echo ""
    echo -e "${BLUE}============================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================================${NC}"
    echo ""
}

# Function to print success messages
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

# Function to print error messages
print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Function to print info messages
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Function to print warning messages
print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Function to check if kubectl is available
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed or not in PATH"
        exit 1
    fi
    print_success "kubectl is available"
}

# Function to check if cluster is accessible
check_cluster() {
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot access Kubernetes cluster"
        print_info "Make sure k3d cluster is running: k3d cluster list"
        exit 1
    fi
    print_success "Kubernetes cluster is accessible"
}

print_header "Task 34.2 Deployment: Kubernetes Namespace and Base Resources"

echo "This script will deploy the following resources:"
echo "  - Namespace: jewelry-shop"
echo "  - ConfigMaps: app-config, nginx-config"
echo "  - Secrets: app-secrets, postgres-secrets, redis-secrets"
echo "  - ResourceQuotas: jewelry-shop-quota, jewelry-shop-priority-quota"
echo "  - LimitRanges: jewelry-shop-limits, jewelry-shop-dev-limits"
echo ""

# Check prerequisites
print_header "Step 1: Checking Prerequisites"
check_kubectl
check_cluster

# Deploy namespace
print_header "Step 2: Creating Namespace"
if kubectl get namespace jewelry-shop &> /dev/null; then
    print_warning "Namespace 'jewelry-shop' already exists, skipping creation"
else
    kubectl apply -f k8s/namespace.yaml
    print_success "Namespace 'jewelry-shop' created"
fi

# Wait for namespace to be active
print_info "Waiting for namespace to be active..."
kubectl wait --for=jsonpath='{.status.phase}'=Active namespace/jewelry-shop --timeout=30s
print_success "Namespace is active"

# Deploy ConfigMaps
print_header "Step 3: Creating ConfigMaps"
kubectl apply -f k8s/configmap.yaml
print_success "ConfigMaps created"

# Verify ConfigMaps
CONFIGMAPS=$(kubectl get configmaps -n jewelry-shop --no-headers | wc -l)
print_info "Total ConfigMaps in namespace: $CONFIGMAPS"

# Deploy Secrets
print_header "Step 4: Creating Secrets"
print_warning "IMPORTANT: The secrets in secrets.yaml are for development only!"
print_warning "In production, use proper secrets management (Sealed Secrets, Vault, etc.)"
echo ""

kubectl apply -f k8s/secrets.yaml
print_success "Secrets created"

# Verify Secrets
SECRETS=$(kubectl get secrets -n jewelry-shop --no-headers | wc -l)
print_info "Total Secrets in namespace: $SECRETS"

# Deploy ResourceQuotas
print_header "Step 5: Applying ResourceQuotas"
kubectl apply -f k8s/resource-quota.yaml
print_success "ResourceQuotas applied"

# Verify ResourceQuotas
QUOTAS=$(kubectl get resourcequotas -n jewelry-shop --no-headers | wc -l)
print_info "Total ResourceQuotas in namespace: $QUOTAS"

# Deploy LimitRanges
print_header "Step 6: Applying LimitRanges"
kubectl apply -f k8s/limit-range.yaml
print_success "LimitRanges applied"

# Verify LimitRanges
LIMITS=$(kubectl get limitranges -n jewelry-shop --no-headers | wc -l)
print_info "Total LimitRanges in namespace: $LIMITS"

# Display all resources
print_header "Step 7: Verifying Deployment"
echo "All resources in jewelry-shop namespace:"
echo ""
kubectl get all,configmaps,secrets,resourcequotas,limitranges -n jewelry-shop

# Summary
print_header "Deployment Summary"
echo -e "${GREEN}✓ Namespace created${NC}"
echo -e "${GREEN}✓ ConfigMaps created ($CONFIGMAPS total)${NC}"
echo -e "${GREEN}✓ Secrets created ($SECRETS total)${NC}"
echo -e "${GREEN}✓ ResourceQuotas applied ($QUOTAS total)${NC}"
echo -e "${GREEN}✓ LimitRanges applied ($LIMITS total)${NC}"
echo ""

print_header "Next Steps"
echo "1. Run validation script to verify all resources:"
echo -e "   ${BLUE}./k8s/scripts/validate-task-34.2.sh${NC}"
echo ""
echo "2. View resource details:"
echo -e "   ${BLUE}kubectl describe namespace jewelry-shop${NC}"
echo -e "   ${BLUE}kubectl describe configmap app-config -n jewelry-shop${NC}"
echo -e "   ${BLUE}kubectl describe secret app-secrets -n jewelry-shop${NC}"
echo -e "   ${BLUE}kubectl describe resourcequota jewelry-shop-quota -n jewelry-shop${NC}"
echo -e "   ${BLUE}kubectl describe limitrange jewelry-shop-limits -n jewelry-shop${NC}"
echo ""
echo "3. Proceed to Task 34.3: Deploy Django application with health checks"
echo ""

print_header "Deployment Complete"
print_success "Task 34.2 resources have been successfully deployed!"
