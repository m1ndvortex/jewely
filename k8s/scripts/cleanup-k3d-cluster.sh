#!/bin/bash

# Cleanup k3d Development Cluster
# This script deletes the k3d cluster and cleans up resources

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CLUSTER_NAME="jewelry-shop"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}k3d Cluster Cleanup${NC}"
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

# Check if k3d is installed
if ! command -v k3d &> /dev/null; then
    print_error "k3d is not installed. Nothing to clean up."
    exit 1
fi

# Check if cluster exists
print_info "Checking if cluster '$CLUSTER_NAME' exists..."
if ! k3d cluster list | grep -q "$CLUSTER_NAME"; then
    print_warning "Cluster '$CLUSTER_NAME' does not exist. Nothing to clean up."
    exit 0
fi

# Confirm deletion
print_warning "This will delete the cluster '$CLUSTER_NAME' and all its resources."
read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_info "Cleanup cancelled"
    exit 0
fi

# Delete cluster
print_info "Deleting cluster '$CLUSTER_NAME'..."
k3d cluster delete $CLUSTER_NAME

if [ $? -eq 0 ]; then
    print_success "Cluster deleted successfully!"
else
    print_error "Failed to delete cluster"
    exit 1
fi

# Clean up kubeconfig
print_info "Cleaning up kubeconfig..."
kubectl config delete-context k3d-$CLUSTER_NAME 2>/dev/null || true
kubectl config delete-cluster k3d-$CLUSTER_NAME 2>/dev/null || true

print_success "Cleanup complete!"
echo ""
echo "To recreate the cluster, run: ./k8s/scripts/setup-k3d-cluster.sh"
echo ""
