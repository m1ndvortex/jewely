#!/bin/bash

# Traefik Ingress Controller Installation Script
# This script installs Traefik v2.x using Helm with custom values
# for the Jewelry Shop SaaS Platform

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
TRAEFIK_NAMESPACE="traefik"
TRAEFIK_RELEASE="traefik"
HELM_REPO_NAME="traefik"
HELM_REPO_URL="https://traefik.github.io/charts"
VALUES_FILE="$(dirname "$0")/values.yaml"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Traefik Ingress Controller Installation${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl is not installed${NC}"
    exit 1
fi

# Check if helm is installed
if ! command -v helm &> /dev/null; then
    echo -e "${RED}Error: helm is not installed${NC}"
    echo -e "${YELLOW}Install helm: https://helm.sh/docs/intro/install/${NC}"
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

# Create namespace if it doesn't exist
echo -e "${YELLOW}Creating namespace: ${TRAEFIK_NAMESPACE}${NC}"
kubectl create namespace ${TRAEFIK_NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -
echo -e "${GREEN}✓ Namespace created/verified${NC}"
echo ""

# Add Traefik Helm repository
echo -e "${YELLOW}Adding Traefik Helm repository...${NC}"
helm repo add ${HELM_REPO_NAME} ${HELM_REPO_URL} 2>/dev/null || true
helm repo update
echo -e "${GREEN}✓ Helm repository added and updated${NC}"
echo ""

# Check if values file exists
if [ ! -f "${VALUES_FILE}" ]; then
    echo -e "${RED}Error: Values file not found: ${VALUES_FILE}${NC}"
    exit 1
fi

# Install or upgrade Traefik
echo -e "${YELLOW}Installing/Upgrading Traefik...${NC}"
helm upgrade --install ${TRAEFIK_RELEASE} ${HELM_REPO_NAME}/traefik \
    --namespace ${TRAEFIK_NAMESPACE} \
    --values ${VALUES_FILE} \
    --wait \
    --timeout 5m

echo -e "${GREEN}✓ Traefik installed/upgraded successfully${NC}"
echo ""

# Wait for Traefik pods to be ready
echo -e "${YELLOW}Waiting for Traefik pods to be ready...${NC}"
kubectl wait --for=condition=ready pod \
    -l app.kubernetes.io/name=traefik \
    -n ${TRAEFIK_NAMESPACE} \
    --timeout=300s

echo -e "${GREEN}✓ Traefik pods are ready${NC}"
echo ""

# Display Traefik service information
echo -e "${YELLOW}Traefik Service Information:${NC}"
kubectl get svc -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik
echo ""

# Display Traefik pods
echo -e "${YELLOW}Traefik Pods:${NC}"
kubectl get pods -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik
echo ""

# Get LoadBalancer IP/Hostname
echo -e "${YELLOW}Getting LoadBalancer endpoint...${NC}"
EXTERNAL_IP=""
for i in {1..30}; do
    EXTERNAL_IP=$(kubectl get svc ${TRAEFIK_RELEASE} -n ${TRAEFIK_NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
    if [ -z "$EXTERNAL_IP" ]; then
        EXTERNAL_IP=$(kubectl get svc ${TRAEFIK_RELEASE} -n ${TRAEFIK_NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "")
    fi
    
    if [ -n "$EXTERNAL_IP" ]; then
        echo -e "${GREEN}✓ LoadBalancer endpoint: ${EXTERNAL_IP}${NC}"
        break
    fi
    
    echo -e "${YELLOW}Waiting for LoadBalancer IP... (${i}/30)${NC}"
    sleep 2
done

if [ -z "$EXTERNAL_IP" ]; then
    echo -e "${YELLOW}Warning: LoadBalancer IP not assigned yet${NC}"
    echo -e "${YELLOW}For k3d, you may need to use NodePort or port-forward${NC}"
    echo -e "${YELLOW}Check service with: kubectl get svc -n ${TRAEFIK_NAMESPACE}${NC}"
fi
echo ""

# Display Traefik dashboard access information
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Traefik Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Access Traefik Dashboard:${NC}"
echo -e "  kubectl port-forward -n ${TRAEFIK_NAMESPACE} \$(kubectl get pods -n ${TRAEFIK_NAMESPACE} -l app.kubernetes.io/name=traefik -o name | head -1) 9000:9000"
echo -e "  Then visit: http://localhost:9000/dashboard/"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo -e "  1. Install cert-manager: ./k8s/cert-manager/install-cert-manager.sh"
echo -e "  2. Create Let's Encrypt ClusterIssuer: kubectl apply -f k8s/cert-manager/letsencrypt-issuer.yaml"
echo -e "  3. Create Ingress resource: kubectl apply -f k8s/ingress/jewelry-shop-ingress.yaml"
echo ""
