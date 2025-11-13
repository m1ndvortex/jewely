#!/bin/bash

# Validate k3d Cluster Setup
# This script validates that the k3d cluster meets all requirements from task 34.1

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CLUSTER_NAME="jewelry-shop"
EXPECTED_NODES=3
EXPECTED_SERVER_NODES=1
EXPECTED_AGENT_NODES=2

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}k3d Cluster Validation${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to print colored messages
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Track validation results
VALIDATION_PASSED=true

# Validation 1: Check if kubectl is available
print_info "Validation 1: Checking if kubectl is available..."
if command -v kubectl &> /dev/null; then
    print_success "kubectl is available"
else
    print_error "kubectl is not available"
    VALIDATION_PASSED=false
fi
echo ""

# Validation 2: Check if cluster is accessible
print_info "Validation 2: Checking if cluster is accessible..."
if kubectl cluster-info &> /dev/null; then
    print_success "Cluster is accessible"
    kubectl cluster-info
else
    print_error "Cluster is not accessible"
    VALIDATION_PASSED=false
fi
echo ""

# Validation 3: Check node count and status
print_info "Validation 3: Checking nodes (expecting $EXPECTED_NODES nodes: $EXPECTED_SERVER_NODES server, $EXPECTED_AGENT_NODES agents)..."
NODE_COUNT=$(kubectl get nodes --no-headers 2>/dev/null | wc -l)

if [ "$NODE_COUNT" -eq "$EXPECTED_NODES" ]; then
    print_success "Found $NODE_COUNT nodes (expected $EXPECTED_NODES)"
else
    print_error "Found $NODE_COUNT nodes (expected $EXPECTED_NODES)"
    VALIDATION_PASSED=false
fi

# Check if all nodes are Ready
NOT_READY_NODES=$(kubectl get nodes --no-headers 2>/dev/null | grep -v " Ready " | wc -l)
if [ "$NOT_READY_NODES" -eq 0 ]; then
    print_success "All nodes are Ready"
else
    print_error "$NOT_READY_NODES nodes are not Ready"
    VALIDATION_PASSED=false
fi

# Display node details
echo ""
echo "Node Details:"
kubectl get nodes -o wide
echo ""

# Validation 4: Check node roles
print_info "Validation 4: Checking node roles..."
SERVER_COUNT=$(kubectl get nodes --no-headers 2>/dev/null | grep -c "control-plane" || echo 0)
AGENT_COUNT=$(kubectl get nodes --no-headers 2>/dev/null | grep -v "control-plane" | wc -l)

if [ "$SERVER_COUNT" -eq "$EXPECTED_SERVER_NODES" ]; then
    print_success "Found $SERVER_COUNT server node(s) (expected $EXPECTED_SERVER_NODES)"
else
    print_error "Found $SERVER_COUNT server node(s) (expected $EXPECTED_SERVER_NODES)"
    VALIDATION_PASSED=false
fi

if [ "$AGENT_COUNT" -eq "$EXPECTED_AGENT_NODES" ]; then
    print_success "Found $AGENT_COUNT agent node(s) (expected $EXPECTED_AGENT_NODES)"
else
    print_error "Found $AGENT_COUNT agent node(s) (expected $EXPECTED_AGENT_NODES)"
    VALIDATION_PASSED=false
fi
echo ""

# Validation 5: Check if Traefik is disabled
print_info "Validation 5: Checking if Traefik is disabled..."
TRAEFIK_PODS=$(kubectl get pods -n kube-system -l app.kubernetes.io/name=traefik --no-headers 2>/dev/null | wc -l)
if [ "$TRAEFIK_PODS" -eq 0 ]; then
    print_success "Traefik is disabled (no Traefik pods found)"
else
    print_warning "Found $TRAEFIK_PODS Traefik pod(s) - Traefik may not be disabled"
fi
echo ""

# Validation 6: Check cluster components
print_info "Validation 6: Checking cluster components..."
COMPONENT_STATUS=$(kubectl get componentstatuses 2>/dev/null || echo "ComponentStatus API not available (normal for k3s)")
if [ $? -eq 0 ]; then
    echo "$COMPONENT_STATUS"
else
    print_info "ComponentStatus API not available (this is normal for k3s)"
fi
echo ""

# Validation 7: Check system pods
print_info "Validation 7: Checking system pods..."
echo "System Pods:"
kubectl get pods -n kube-system
echo ""

NOT_RUNNING_PODS=$(kubectl get pods -n kube-system --no-headers 2>/dev/null | grep -v "Running\|Completed" | wc -l)
if [ "$NOT_RUNNING_PODS" -eq 0 ]; then
    print_success "All system pods are Running or Completed"
else
    print_warning "$NOT_RUNNING_PODS system pod(s) are not Running"
fi
echo ""

# Validation 8: Check namespaces
print_info "Validation 8: Checking namespaces..."
kubectl get namespaces
echo ""

# Final validation summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Validation Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ "$VALIDATION_PASSED" = true ]; then
    echo -e "${GREEN}✓ All validations passed!${NC}"
    echo ""
    echo "The k3d cluster is properly configured and ready for use."
    echo ""
    echo -e "${BLUE}Next Steps:${NC}"
    echo "1. Deploy test nginx: kubectl apply -f k8s/test/test-nginx.yaml"
    echo "2. Verify test deployment: kubectl get pods"
    echo "3. Continue with task 34.2: Create Kubernetes namespace and base resources"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Some validations failed!${NC}"
    echo ""
    echo "Please review the errors above and fix any issues."
    echo "You may need to recreate the cluster: ./k8s/scripts/cleanup-k3d-cluster.sh && ./k8s/scripts/setup-k3d-cluster.sh"
    echo ""
    exit 1
fi
