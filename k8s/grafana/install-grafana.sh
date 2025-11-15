#!/bin/bash

# Grafana Installation Script for Jewelry SaaS Platform
# Task: 35.2 - Deploy Grafana
# Requirement: 24 - Monitoring and Observability

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="jewelry-shop"
GRAFANA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Grafana Installation for Jewelry SaaS${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if namespace exists
echo -e "${YELLOW}[1/7] Checking namespace...${NC}"
if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    echo -e "${RED}Error: Namespace '$NAMESPACE' does not exist${NC}"
    echo "Please create the namespace first:"
    echo "  kubectl create namespace $NAMESPACE"
    exit 1
fi
echo -e "${GREEN}✓ Namespace '$NAMESPACE' exists${NC}"
echo ""

# Check if Prometheus is running
echo -e "${YELLOW}[2/7] Checking Prometheus...${NC}"
if ! kubectl get deployment prometheus -n "$NAMESPACE" &> /dev/null; then
    echo -e "${RED}Warning: Prometheus deployment not found${NC}"
    echo "Grafana will be deployed but won't have data until Prometheus is running"
    echo "To deploy Prometheus, run: cd ../prometheus && ./install-prometheus.sh"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    PROMETHEUS_STATUS=$(kubectl get pods -n "$NAMESPACE" -l app=prometheus -o jsonpath='{.items[0].status.phase}' 2>/dev/null || echo "Unknown")
    if [ "$PROMETHEUS_STATUS" = "Running" ]; then
        echo -e "${GREEN}✓ Prometheus is running${NC}"
    else
        echo -e "${YELLOW}⚠ Prometheus status: $PROMETHEUS_STATUS${NC}"
    fi
fi
echo ""

# Apply Secrets
echo -e "${YELLOW}[3/7] Creating Grafana secrets...${NC}"
kubectl apply -f "$GRAFANA_DIR/grafana-secrets.yaml"
echo -e "${GREEN}✓ Secrets created${NC}"
echo ""

# Apply ConfigMaps
echo -e "${YELLOW}[4/7] Creating Grafana configuration...${NC}"
kubectl apply -f "$GRAFANA_DIR/grafana-configmap.yaml"
echo -e "${GREEN}✓ Configuration created${NC}"
echo ""

# Apply Dashboard ConfigMaps
echo -e "${YELLOW}[5/7] Creating Grafana dashboards...${NC}"
kubectl apply -f "$GRAFANA_DIR/grafana-dashboards.yaml"
echo -e "${GREEN}✓ Dashboards created${NC}"
echo ""

# Apply Deployment and PVC
echo -e "${YELLOW}[6/7] Deploying Grafana...${NC}"
kubectl apply -f "$GRAFANA_DIR/grafana-deployment.yaml"
echo -e "${GREEN}✓ Deployment created${NC}"
echo ""

# Apply Service
echo -e "${YELLOW}[7/7] Creating Grafana service...${NC}"
kubectl apply -f "$GRAFANA_DIR/grafana-service.yaml"
echo -e "${GREEN}✓ Service created${NC}"
echo ""

# Wait for pod to be ready
echo -e "${YELLOW}Waiting for Grafana pod to be ready...${NC}"
echo "This may take a few minutes..."
if kubectl wait --for=condition=ready pod -l app=grafana -n "$NAMESPACE" --timeout=300s; then
    echo -e "${GREEN}✓ Grafana pod is ready${NC}"
else
    echo -e "${RED}✗ Grafana pod failed to become ready${NC}"
    echo ""
    echo "Checking pod status:"
    kubectl get pods -n "$NAMESPACE" -l app=grafana
    echo ""
    echo "Pod events:"
    kubectl describe pod -n "$NAMESPACE" -l app=grafana | tail -20
    exit 1
fi
echo ""

# Get pod name
POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l app=grafana -o jsonpath='{.items[0].metadata.name}')

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Grafana Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Access Grafana:${NC}"
echo "  kubectl port-forward -n $NAMESPACE svc/grafana 3000:3000"
echo "  Then open: http://localhost:3000"
echo ""
echo -e "${BLUE}Default Credentials:${NC}"
echo "  Username: admin"
echo "  Password: admin123!@#"
echo "  ${RED}⚠ CHANGE THESE IN PRODUCTION!${NC}"
echo ""
echo -e "${BLUE}Pre-configured Dashboards:${NC}"
echo "  • System Overview - Overall platform health"
echo "  • Application Performance - Django metrics"
echo "  • Database Performance - PostgreSQL metrics"
echo "  • Infrastructure Health - Kubernetes metrics"
echo ""
echo -e "${BLUE}Prometheus Data Source:${NC}"
echo "  • Name: Prometheus"
echo "  • URL: http://prometheus:9090"
echo "  • Status: $(kubectl get svc prometheus -n "$NAMESPACE" &> /dev/null && echo -e "${GREEN}Available${NC}" || echo -e "${RED}Not Found${NC}")"
echo ""
echo -e "${BLUE}Verification:${NC}"
echo "  Run: ./validate-grafana.sh"
echo ""
echo -e "${BLUE}Pod Status:${NC}"
kubectl get pods -n "$NAMESPACE" -l app=grafana
echo ""
echo -e "${BLUE}Service Status:${NC}"
kubectl get svc -n "$NAMESPACE" grafana
echo ""
echo -e "${BLUE}PVC Status:${NC}"
kubectl get pvc -n "$NAMESPACE" grafana-storage
echo ""
