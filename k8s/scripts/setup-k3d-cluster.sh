#!/bin/bash

# Setup k3d Development Cluster for Jewelry Shop SaaS Platform
# This script installs k3d and creates a local Kubernetes cluster for development

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CLUSTER_NAME="jewelry-shop"
SERVER_COUNT=1
AGENT_COUNT=2
HTTP_PORT=8080
HTTPS_PORT=8443

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}k3d Cluster Setup for Jewelry Shop SaaS${NC}"
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

# Check if Docker is running
print_info "Checking if Docker is running..."
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker and try again."
    exit 1
fi
print_success "Docker is running"

# Check if k3d is installed
print_info "Checking if k3d is installed..."
if ! command -v k3d &> /dev/null; then
    print_warning "k3d is not installed. Installing k3d..."
    
    # Install k3d
    curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
    
    if ! command -v k3d &> /dev/null; then
        print_error "Failed to install k3d. Please install manually."
        exit 1
    fi
    
    print_success "k3d installed successfully"
else
    K3D_VERSION=$(k3d version | head -n 1)
    print_success "k3d is already installed: $K3D_VERSION"
fi

# Check if kubectl is installed
print_info "Checking if kubectl is installed..."
if ! command -v kubectl &> /dev/null; then
    print_warning "kubectl is not installed. Installing kubectl..."
    
    # Detect OS and install kubectl
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
        chmod +x kubectl
        sudo mv kubectl /usr/local/bin/
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/darwin/amd64/kubectl"
        chmod +x kubectl
        sudo mv kubectl /usr/local/bin/
    else
        print_error "Unsupported OS. Please install kubectl manually."
        exit 1
    fi
    
    print_success "kubectl installed successfully"
else
    KUBECTL_VERSION=$(kubectl version --client --short 2>/dev/null || kubectl version --client)
    print_success "kubectl is already installed"
fi

# Check if cluster already exists
print_info "Checking if cluster '$CLUSTER_NAME' already exists..."
if k3d cluster list | grep -q "$CLUSTER_NAME"; then
    print_warning "Cluster '$CLUSTER_NAME' already exists."
    read -p "Do you want to delete and recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Deleting existing cluster..."
        k3d cluster delete $CLUSTER_NAME
        print_success "Existing cluster deleted"
    else
        print_info "Using existing cluster"
        k3d kubeconfig merge $CLUSTER_NAME --kubeconfig-switch-context
        print_success "Switched to existing cluster context"
        exit 0
    fi
fi

# Create k3d cluster
print_info "Creating k3d cluster with configuration:"
echo "  - Cluster name: $CLUSTER_NAME"
echo "  - Server nodes: $SERVER_COUNT"
echo "  - Agent nodes: $AGENT_COUNT"
echo "  - HTTP port mapping: $HTTP_PORT:80"
echo "  - HTTPS port mapping: $HTTPS_PORT:443"
echo "  - Traefik: Disabled (will install custom version later)"
echo ""

k3d cluster create $CLUSTER_NAME \
    --servers $SERVER_COUNT \
    --agents $AGENT_COUNT \
    --port "$HTTP_PORT:80@loadbalancer" \
    --port "$HTTPS_PORT:443@loadbalancer" \
    --k3s-arg "--disable=traefik@server:0" \
    --wait

if [ $? -eq 0 ]; then
    print_success "Cluster created successfully!"
else
    print_error "Failed to create cluster"
    exit 1
fi

# Wait for cluster to be ready
print_info "Waiting for cluster to be ready..."
sleep 5

# Verify cluster is accessible
print_info "Verifying cluster accessibility..."
if kubectl cluster-info &> /dev/null; then
    print_success "Cluster is accessible"
else
    print_error "Cluster is not accessible"
    exit 1
fi

# Display cluster information
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Cluster Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Cluster Information:"
kubectl cluster-info
echo ""
echo "Nodes:"
kubectl get nodes
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "1. Run validation: ./k8s/scripts/validate-cluster.sh"
echo "2. Deploy test nginx: kubectl apply -f k8s/test/test-nginx.yaml"
echo "3. Check test deployment: kubectl get pods -n default"
echo ""
echo -e "${YELLOW}Note:${NC} Traefik is disabled. You'll install a custom version in task 34.9"
echo ""
