#!/bin/bash

# Grafana Validation Script for Jewelry SaaS Platform
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
VALIDATION_FAILED=0

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Grafana Validation${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to check and report
check_status() {
    local test_name=$1
    local command=$2
    local expected=$3
    
    echo -e "${YELLOW}Testing: $test_name${NC}"
    
    if eval "$command"; then
        echo -e "${GREEN}✓ PASS: $test_name${NC}"
        return 0
    else
        echo -e "${RED}✗ FAIL: $test_name${NC}"
        VALIDATION_FAILED=1
        return 1
    fi
}

# 1. Check if Grafana pod is running
echo -e "${BLUE}[1/12] Checking Grafana Pod Status${NC}"
POD_STATUS=$(kubectl get pods -n "$NAMESPACE" -l app=grafana -o jsonpath='{.items[0].status.phase}' 2>/dev/null || echo "NotFound")
if [ "$POD_STATUS" = "Running" ]; then
    echo -e "${GREEN}✓ Grafana pod is Running${NC}"
    POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l app=grafana -o jsonpath='{.items[0].metadata.name}')
    echo "  Pod: $POD_NAME"
else
    echo -e "${RED}✗ Grafana pod status: $POD_STATUS${NC}"
    VALIDATION_FAILED=1
fi
echo ""

# 2. Check if Grafana service exists
echo -e "${BLUE}[2/12] Checking Grafana Service${NC}"
if kubectl get svc grafana -n "$NAMESPACE" &> /dev/null; then
    echo -e "${GREEN}✓ Grafana service exists${NC}"
    CLUSTER_IP=$(kubectl get svc grafana -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
    echo "  ClusterIP: $CLUSTER_IP"
else
    echo -e "${RED}✗ Grafana service not found${NC}"
    VALIDATION_FAILED=1
fi
echo ""

# 3. Check if PVC is bound
echo -e "${BLUE}[3/12] Checking Persistent Volume Claim${NC}"
PVC_STATUS=$(kubectl get pvc grafana-storage -n "$NAMESPACE" -o jsonpath='{.status.phase}' 2>/dev/null || echo "NotFound")
if [ "$PVC_STATUS" = "Bound" ]; then
    echo -e "${GREEN}✓ PVC is Bound${NC}"
    PVC_SIZE=$(kubectl get pvc grafana-storage -n "$NAMESPACE" -o jsonpath='{.status.capacity.storage}')
    echo "  Size: $PVC_SIZE"
else
    echo -e "${RED}✗ PVC status: $PVC_STATUS${NC}"
    VALIDATION_FAILED=1
fi
echo ""

# 4. Check if secrets exist
echo -e "${BLUE}[4/12] Checking Grafana Secrets${NC}"
if kubectl get secret grafana-secrets -n "$NAMESPACE" &> /dev/null; then
    echo -e "${GREEN}✓ Grafana secrets exist${NC}"
else
    echo -e "${RED}✗ Grafana secrets not found${NC}"
    VALIDATION_FAILED=1
fi
echo ""

# 5. Check if ConfigMaps exist
echo -e "${BLUE}[5/12] Checking ConfigMaps${NC}"
CONFIGMAPS=("grafana-config" "grafana-datasources" "grafana-dashboards-config")
for cm in "${CONFIGMAPS[@]}"; do
    if kubectl get configmap "$cm" -n "$NAMESPACE" &> /dev/null; then
        echo -e "${GREEN}✓ ConfigMap '$cm' exists${NC}"
    else
        echo -e "${RED}✗ ConfigMap '$cm' not found${NC}"
        VALIDATION_FAILED=1
    fi
done
echo ""

# 6. Check if dashboard ConfigMaps exist
echo -e "${BLUE}[6/12] Checking Dashboard ConfigMaps${NC}"
DASHBOARDS=("grafana-dashboard-system-overview" "grafana-dashboard-application-performance" "grafana-dashboard-database-performance" "grafana-dashboard-infrastructure-health")
for dashboard in "${DASHBOARDS[@]}"; do
    if kubectl get configmap "$dashboard" -n "$NAMESPACE" &> /dev/null; then
        echo -e "${GREEN}✓ Dashboard '$dashboard' exists${NC}"
    else
        echo -e "${RED}✗ Dashboard '$dashboard' not found${NC}"
        VALIDATION_FAILED=1
    fi
done
echo ""

# 7. Check if Grafana is responding
echo -e "${BLUE}[7/12] Checking Grafana HTTP Response${NC}"
if [ "$POD_STATUS" = "Running" ]; then
    HTTP_CODE=$(kubectl exec -n "$NAMESPACE" "$POD_NAME" -- wget -q -O /dev/null -S http://localhost:3000/api/health 2>&1 | grep "HTTP/" | awk '{print $2}' || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}✓ Grafana is responding (HTTP $HTTP_CODE)${NC}"
    else
        echo -e "${RED}✗ Grafana HTTP response: $HTTP_CODE${NC}"
        VALIDATION_FAILED=1
    fi
else
    echo -e "${YELLOW}⚠ Skipping (pod not running)${NC}"
fi
echo ""

# 8. Check if Prometheus data source is configured
echo -e "${BLUE}[8/12] Checking Prometheus Data Source${NC}"
if [ "$POD_STATUS" = "Running" ]; then
    # Wait a moment for Grafana to fully initialize
    sleep 5
    
    # Check if datasource is configured
    DS_CHECK=$(kubectl exec -n "$NAMESPACE" "$POD_NAME" -- wget -q -O - http://localhost:3000/api/datasources 2>/dev/null | grep -c "Prometheus" || echo "0")
    if [ "$DS_CHECK" -gt "0" ]; then
        echo -e "${GREEN}✓ Prometheus data source is configured${NC}"
    else
        echo -e "${RED}✗ Prometheus data source not found${NC}"
        VALIDATION_FAILED=1
    fi
else
    echo -e "${YELLOW}⚠ Skipping (pod not running)${NC}"
fi
echo ""

# 9. Check if Prometheus service is accessible
echo -e "${BLUE}[9/12] Checking Prometheus Connectivity${NC}"
if kubectl get svc prometheus -n "$NAMESPACE" &> /dev/null; then
    echo -e "${GREEN}✓ Prometheus service exists${NC}"
    PROM_IP=$(kubectl get svc prometheus -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
    echo "  Prometheus ClusterIP: $PROM_IP"
    
    # Test connectivity from Grafana pod
    if [ "$POD_STATUS" = "Running" ]; then
        if kubectl exec -n "$NAMESPACE" "$POD_NAME" -- wget -q -O /dev/null -T 5 http://prometheus:9090/-/healthy 2>/dev/null; then
            echo -e "${GREEN}✓ Grafana can reach Prometheus${NC}"
        else
            echo -e "${RED}✗ Grafana cannot reach Prometheus${NC}"
            VALIDATION_FAILED=1
        fi
    fi
else
    echo -e "${YELLOW}⚠ Prometheus service not found (expected if not deployed yet)${NC}"
fi
echo ""

# 10. Check resource usage
echo -e "${BLUE}[10/12] Checking Resource Usage${NC}"
if [ "$POD_STATUS" = "Running" ]; then
    METRICS=$(kubectl top pod "$POD_NAME" -n "$NAMESPACE" 2>/dev/null || echo "metrics-server not available")
    if [ "$METRICS" != "metrics-server not available" ]; then
        echo -e "${GREEN}✓ Resource metrics available${NC}"
        echo "$METRICS"
    else
        echo -e "${YELLOW}⚠ Metrics server not available${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Skipping (pod not running)${NC}"
fi
echo ""

# 11. Check pod logs for errors
echo -e "${BLUE}[11/12] Checking Pod Logs for Errors${NC}"
if [ "$POD_STATUS" = "Running" ]; then
    ERROR_COUNT=$(kubectl logs "$POD_NAME" -n "$NAMESPACE" --tail=100 2>/dev/null | grep -i "error\|fatal\|panic" | wc -l || echo "0")
    if [ "$ERROR_COUNT" -eq "0" ]; then
        echo -e "${GREEN}✓ No errors in recent logs${NC}"
    else
        echo -e "${YELLOW}⚠ Found $ERROR_COUNT error messages in logs${NC}"
        echo "Recent errors:"
        kubectl logs "$POD_NAME" -n "$NAMESPACE" --tail=100 | grep -i "error\|fatal\|panic" | tail -5
    fi
else
    echo -e "${YELLOW}⚠ Skipping (pod not running)${NC}"
fi
echo ""

# 12. Check if dashboards are loaded
echo -e "${BLUE}[12/12] Checking Dashboard Loading${NC}"
if [ "$POD_STATUS" = "Running" ]; then
    sleep 5  # Give Grafana time to load dashboards
    
    # Check if dashboards directory exists and has files
    DASHBOARD_COUNT=$(kubectl exec -n "$NAMESPACE" "$POD_NAME" -- sh -c "ls -1 /var/lib/grafana/dashboards/jewelry-shop/*.json 2>/dev/null | wc -l" || echo "0")
    if [ "$DASHBOARD_COUNT" -ge "4" ]; then
        echo -e "${GREEN}✓ Found $DASHBOARD_COUNT dashboard files${NC}"
    else
        echo -e "${YELLOW}⚠ Expected 4 dashboards, found $DASHBOARD_COUNT${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Skipping (pod not running)${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
if [ $VALIDATION_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All Validations Passed!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${BLUE}Next Steps:${NC}"
    echo "1. Access Grafana UI:"
    echo "   kubectl port-forward -n $NAMESPACE svc/grafana 3000:3000"
    echo "   Open: http://localhost:3000"
    echo ""
    echo "2. Login with default credentials:"
    echo "   Username: admin"
    echo "   Password: admin123!@#"
    echo ""
    echo "3. Explore pre-configured dashboards:"
    echo "   • System Overview"
    echo "   • Application Performance"
    echo "   • Database Performance"
    echo "   • Infrastructure Health"
    echo ""
    echo "4. Verify Prometheus data source:"
    echo "   Configuration → Data Sources → Prometheus"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Some Validations Failed${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo -e "${YELLOW}Troubleshooting:${NC}"
    echo "1. Check pod status:"
    echo "   kubectl get pods -n $NAMESPACE -l app=grafana"
    echo ""
    echo "2. Check pod logs:"
    echo "   kubectl logs -n $NAMESPACE -l app=grafana"
    echo ""
    echo "3. Describe pod for events:"
    echo "   kubectl describe pod -n $NAMESPACE -l app=grafana"
    echo ""
    echo "4. Check PVC status:"
    echo "   kubectl get pvc -n $NAMESPACE grafana-storage"
    echo ""
    echo "5. Verify ConfigMaps:"
    echo "   kubectl get configmap -n $NAMESPACE | grep grafana"
    echo ""
    exit 1
fi
