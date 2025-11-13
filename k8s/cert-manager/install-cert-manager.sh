#!/bin/bash

# cert-manager Installation Script
# This script installs cert-manager for automatic SSL certificate management
# using Let's Encrypt for the Jewelry Shop SaaS Platform

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
CERT_MANAGER_VERSION="v1.13.3"  # Latest stable version
CERT_MANAGER_NAMESPACE="cert-manager"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}cert-manager Installation${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl is not installed${NC}"
    exit 1
fi

# Check if cluster is accessible
echo -e "${YELLOW}Checking cluster connectivity...${NC}"
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}Error: Cannot connect to Kubernetes cluster${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Cluster is accessible${NC}"
echo ""

# Check if cert-manager is already installed
if kubectl get namespace ${CERT_MANAGER_NAMESPACE} &> /dev/null; then
    echo -e "${YELLOW}cert-manager namespace already exists${NC}"
    read -p "Do you want to reinstall cert-manager? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Skipping installation${NC}"
        exit 0
    fi
fi

# Install cert-manager CRDs
echo -e "${YELLOW}Installing cert-manager CRDs...${NC}"
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/${CERT_MANAGER_VERSION}/cert-manager.crds.yaml
echo -e "${GREEN}✓ CRDs installed${NC}"
echo ""

# Create namespace
echo -e "${YELLOW}Creating namespace: ${CERT_MANAGER_NAMESPACE}${NC}"
kubectl create namespace ${CERT_MANAGER_NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -
echo -e "${GREEN}✓ Namespace created/verified${NC}"
echo ""

# Install cert-manager using kubectl
echo -e "${YELLOW}Installing cert-manager ${CERT_MANAGER_VERSION}...${NC}"
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/${CERT_MANAGER_VERSION}/cert-manager.yaml
echo -e "${GREEN}✓ cert-manager installed${NC}"
echo ""

# Wait for cert-manager pods to be ready
echo -e "${YELLOW}Waiting for cert-manager pods to be ready...${NC}"
echo -e "${YELLOW}This may take a few minutes...${NC}"

# Wait for cert-manager webhook
kubectl wait --for=condition=ready pod \
    -l app.kubernetes.io/name=webhook \
    -n ${CERT_MANAGER_NAMESPACE} \
    --timeout=300s

# Wait for cert-manager controller
kubectl wait --for=condition=ready pod \
    -l app.kubernetes.io/name=cert-manager \
    -n ${CERT_MANAGER_NAMESPACE} \
    --timeout=300s

# Wait for cert-manager cainjector
kubectl wait --for=condition=ready pod \
    -l app.kubernetes.io/name=cainjector \
    -n ${CERT_MANAGER_NAMESPACE} \
    --timeout=300s

echo -e "${GREEN}✓ All cert-manager pods are ready${NC}"
echo ""

# Display cert-manager pods
echo -e "${YELLOW}cert-manager Pods:${NC}"
kubectl get pods -n ${CERT_MANAGER_NAMESPACE}
echo ""

# Verify cert-manager installation
echo -e "${YELLOW}Verifying cert-manager installation...${NC}"
kubectl get all -n ${CERT_MANAGER_NAMESPACE}
echo ""

# Check CRDs
echo -e "${YELLOW}Checking cert-manager CRDs:${NC}"
kubectl get crd | grep cert-manager
echo ""

# Display success message
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}cert-manager Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo -e "  1. Create Let's Encrypt ClusterIssuer:"
echo -e "     kubectl apply -f k8s/cert-manager/letsencrypt-issuer.yaml"
echo -e ""
echo -e "  2. Verify ClusterIssuer is ready:"
echo -e "     kubectl get clusterissuer"
echo -e ""
echo -e "  3. Create Ingress with TLS:"
echo -e "     kubectl apply -f k8s/ingress/jewelry-shop-ingress.yaml"
echo -e ""
echo -e "${YELLOW}Useful Commands:${NC}"
echo -e "  Check certificates: kubectl get certificate -A"
echo -e "  Check certificate requests: kubectl get certificaterequest -A"
echo -e "  Check orders: kubectl get order -A"
echo -e "  Check challenges: kubectl get challenge -A"
echo -e "  Describe certificate: kubectl describe certificate <name> -n <namespace>"
echo ""
