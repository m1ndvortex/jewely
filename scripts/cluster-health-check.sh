#!/bin/bash
################################################################################
# Jewelry Shop Cluster Health Check & Recovery Script
# Use this script to verify cluster health and auto-recover from issues
################################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

NAMESPACE="jewelry-shop"
TIMEOUT=300  # 5 minutes

echo -e "${BLUE}╔═══════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Jewelry Shop Kubernetes Cluster Health Check        ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if k3d cluster is running
echo -e "${BLUE}[1/7]${NC} Checking k3d cluster status..."
if ! k3d cluster list | grep -q "jewelry-shop.*1/1.*2/2"; then
    echo -e "${YELLOW}⚠  Cluster not running. Starting...${NC}"
    k3d cluster start jewelry-shop
    echo -e "${YELLOW}⏳ Waiting for cluster to be ready...${NC}"
    sleep 20
fi

if kubectl cluster-info &> /dev/null; then
    echo -e "${GREEN}✅ Cluster is accessible${NC}"
else
    echo -e "${RED}❌ Cannot access cluster${NC}"
    exit 1
fi

# Check nodes
echo -e "${BLUE}[2/7]${NC} Checking node status..."
node_count=$(kubectl get nodes --no-headers | grep -c "Ready" || echo "0")
expected_nodes=3

if [ "$node_count" -eq "$expected_nodes" ]; then
    echo -e "${GREEN}✅ All $node_count/$expected_nodes nodes Ready${NC}"
else
    echo -e "${YELLOW}⚠  Only $node_count/$expected_nodes nodes Ready${NC}"
fi

# Check pods
echo -e "${BLUE}[3/7]${NC} Checking pod status..."
total_pods=$(kubectl get pods -n $NAMESPACE --no-headers | wc -l)
running_pods=$(kubectl get pods -n $NAMESPACE --no-headers | grep -c "Running" || echo "0")

echo -e "   Total pods: $total_pods"
echo -e "   Running: $running_pods"

if [ "$running_pods" -eq "$total_pods" ]; then
    echo -e "${GREEN}✅ All pods are Running${NC}"
else
    not_running=$((total_pods - running_pods))
    echo -e "${YELLOW}⚠  $not_running pods not Running${NC}"
    
    # Check for problematic pods
    crash_pods=$(kubectl get pods -n $NAMESPACE --no-headers | grep -E "CrashLoop|Error|Unknown" | wc -l)
    
    if [ "$crash_pods" -gt 0 ]; then
        echo -e "${YELLOW}   Found $crash_pods problematic pods${NC}"
        echo ""
        kubectl get pods -n $NAMESPACE | grep -E "CrashLoop|Error|Unknown|NAME"
        echo ""
        
        read -p "Delete problematic pods to force restart? (y/n): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            kubectl get pods -n $NAMESPACE --no-headers | grep -E "CrashLoop|Error|Unknown" | awk '{print $1}' | xargs -I {} kubectl delete pod {} -n $NAMESPACE --force --grace-period=0
            echo -e "${GREEN}✅ Problematic pods deleted${NC}"
            echo -e "${YELLOW}⏳ Waiting 30 seconds for pods to restart...${NC}"
            sleep 30
        fi
    fi
fi

# Check critical services
echo -e "${BLUE}[4/7]${NC} Checking critical services..."

# PostgreSQL
pg_ready=$(kubectl get pods -n $NAMESPACE --no-headers 2>/dev/null | grep "jewelry-shop-db-[0-9]" | grep -c "Running" || echo "0")
if [ "$pg_ready" -ge 3 ] 2>/dev/null; then
    echo -e "${GREEN}✅ PostgreSQL cluster healthy ($pg_ready pods)${NC}"
else
    echo -e "${YELLOW}⚠  PostgreSQL: $pg_ready/3 pods running${NC}"
fi

# Redis
redis_ready=$(kubectl get pods -n $NAMESPACE -l app=redis --no-headers 2>/dev/null | grep -c "Running" || echo "0")
if [ "$redis_ready" -ge 3 ]; then
    echo -e "${GREEN}✅ Redis cluster healthy ($redis_ready pods)${NC}"
else
    echo -e "${YELLOW}⚠  Redis: $redis_ready/3 pods running${NC}"
fi

# Django
django_ready=$(kubectl get pods -n $NAMESPACE -l component=django --no-headers 2>/dev/null | grep -c "Running" || echo "0")
if [ "$django_ready" -ge 2 ]; then
    echo -e "${GREEN}✅ Django app healthy ($django_ready pods)${NC}"
else
    echo -e "${YELLOW}⚠  Django: $django_ready/2 pods running${NC}"
fi

# Nginx
nginx_ready=$(kubectl get pods -n $NAMESPACE -l component=nginx --no-headers 2>/dev/null | grep -c "Running" || echo "0")
if [ "$nginx_ready" -ge 2 ]; then
    echo -e "${GREEN}✅ Nginx healthy ($nginx_ready pods)${NC}"
else
    echo -e "${YELLOW}⚠  Nginx: $nginx_ready/2 pods running${NC}"
fi

# Check services
echo -e "${BLUE}[5/7]${NC} Checking services..."
services=$(kubectl get svc -n $NAMESPACE --no-headers | wc -l)
echo -e "${GREEN}✅ $services services configured${NC}"

# Check persistent volumes
echo -e "${BLUE}[6/7]${NC} Checking persistent volumes..."
pvcs=$(kubectl get pvc -n $NAMESPACE --no-headers | grep -c "Bound" || echo "0")
total_pvcs=$(kubectl get pvc -n $NAMESPACE --no-headers | wc -l || echo "0")

if [ "$pvcs" -eq "$total_pvcs" ] && [ "$pvcs" -gt 0 ]; then
    echo -e "${GREEN}✅ All $pvcs PVCs bound${NC}"
else
    echo -e "${YELLOW}⚠  Only $pvcs/$total_pvcs PVCs bound${NC}"
fi

# Overall health
echo -e "${BLUE}[7/7]${NC} Overall health status..."
echo ""

if [ "$running_pods" -eq "$total_pods" ] && [ "$node_count" -eq "$expected_nodes" ]; then
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                       ║${NC}"
    echo -e "${GREEN}║         ✅ CLUSTER IS HEALTHY AND READY! 🚀           ║${NC}"
    echo -e "${GREEN}║                                                       ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${WHITE}Quick Stats:${NC}"
    echo -e "  Nodes:      ${GREEN}$node_count Ready${NC}"
    echo -e "  Pods:       ${GREEN}$running_pods/$total_pods Running${NC}"
    echo -e "  PostgreSQL: ${GREEN}$pg_ready pods${NC}"
    echo -e "  Redis:      ${GREEN}$redis_ready pods${NC}"
    echo -e "  Django:     ${GREEN}$django_ready pods${NC}"
    echo -e "  Nginx:      ${GREEN}$nginx_ready pods${NC}"
else
    echo -e "${YELLOW}╔═══════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║                                                       ║${NC}"
    echo -e "${YELLOW}║    ⚠  CLUSTER HAS ISSUES - NEEDS ATTENTION           ║${NC}"
    echo -e "${YELLOW}║                                                       ║${NC}"
    echo -e "${YELLOW}╚═══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${WHITE}Troubleshooting:${NC}"
    echo -e "  View pod logs:    ${BLUE}kubectl logs -f <pod-name> -n $NAMESPACE${NC}"
    echo -e "  Describe pod:     ${BLUE}kubectl describe pod <pod-name> -n $NAMESPACE${NC}"
    echo -e "  Restart pod:      ${BLUE}kubectl delete pod <pod-name> -n $NAMESPACE${NC}"
    echo -e "  View all issues:  ${BLUE}kubectl get pods -n $NAMESPACE${NC}"
fi

echo ""
echo -e "${BLUE}Useful Commands:${NC}"
echo -e "  View all pods:    ${WHITE}kubectl get pods -n $NAMESPACE${NC}"
echo -e "  Watch pods:       ${WHITE}watch kubectl get pods -n $NAMESPACE${NC}"
echo -e "  Check services:   ${WHITE}kubectl get svc -n $NAMESPACE${NC}"
echo -e "  Run this check:   ${WHITE}./scripts/cluster-health-check.sh${NC}"
echo ""
