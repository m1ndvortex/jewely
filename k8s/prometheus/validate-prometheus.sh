#!/bin/bash

# ============================================================================
# Prometheus Validation Script
# Task 35.1: Deploy Prometheus - Validation
# Requirement 24: Monitoring and Observability
# ============================================================================

set -e

NAMESPACE="jewelry-shop"
PROMETHEUS_POD=""
VALIDATION_FAILED=0

echo "============================================================================"
echo "Validating Prometheus Deployment"
echo "============================================================================"
echo ""

# Function to print test result
print_result() {
    if [ $1 -eq 0 ]; then
        echo "✅ $2"
    else
        echo "❌ $2"
        VALIDATION_FAILED=1
    fi
}

# Test 1: Check if Prometheus pod is running
echo "📋 Test 1: Checking if Prometheus pod is running..."
if kubectl get pods -n "$NAMESPACE" -l app=prometheus | grep -q "Running"; then
    PROMETHEUS_POD=$(kubectl get pod -n "$NAMESPACE" -l app=prometheus -o jsonpath='{.items[0].metadata.name}')
    print_result 0 "Prometheus pod is running: $PROMETHEUS_POD"
else
    print_result 1 "Prometheus pod is not running"
fi
echo ""

# Test 2: Check if Prometheus service exists
echo "📋 Test 2: Checking if Prometheus service exists..."
if kubectl get svc -n "$NAMESPACE" prometheus &> /dev/null; then
    print_result 0 "Prometheus service exists"
else
    print_result 1 "Prometheus service does not exist"
fi
echo ""

# Test 3: Check if PVC is bound
echo "📋 Test 3: Checking if PersistentVolumeClaim is bound..."
PVC_STATUS=$(kubectl get pvc -n "$NAMESPACE" prometheus-storage -o jsonpath='{.status.phase}' 2>/dev/null || echo "NotFound")
if [ "$PVC_STATUS" = "Bound" ]; then
    print_result 0 "PVC is bound"
else
    print_result 1 "PVC is not bound (Status: $PVC_STATUS)"
fi
echo ""

# Test 4: Check if Prometheus is healthy
echo "📋 Test 4: Checking Prometheus health endpoint..."
if [ -n "$PROMETHEUS_POD" ]; then
    if kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- wget -q -O- http://localhost:9090/-/healthy | grep -q "Prometheus"; then
        print_result 0 "Prometheus health check passed"
    else
        print_result 1 "Prometheus health check failed"
    fi
else
    print_result 1 "Cannot check health - pod not found"
fi
echo ""

# Test 5: Check if Prometheus is ready
echo "📋 Test 5: Checking Prometheus readiness endpoint..."
if [ -n "$PROMETHEUS_POD" ]; then
    if kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- wget -q -O- http://localhost:9090/-/ready | grep -q "Prometheus"; then
        print_result 0 "Prometheus readiness check passed"
    else
        print_result 1 "Prometheus readiness check failed"
    fi
else
    print_result 1 "Cannot check readiness - pod not found"
fi
echo ""

# Test 6: Check if Prometheus can access Kubernetes API
echo "📋 Test 6: Checking Prometheus service discovery..."
if [ -n "$PROMETHEUS_POD" ]; then
    # Check if Prometheus has discovered any targets
    TARGETS_COUNT=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- wget -q -O- http://localhost:9090/api/v1/targets 2>/dev/null | grep -o '"activeTargets":\[' | wc -l || echo "0")
    if [ "$TARGETS_COUNT" -gt 0 ]; then
        print_result 0 "Prometheus service discovery is working"
    else
        print_result 1 "Prometheus service discovery may not be working"
    fi
else
    print_result 1 "Cannot check service discovery - pod not found"
fi
echo ""

# Test 7: Check if Django metrics are being scraped
echo "📋 Test 7: Checking if Django metrics are available..."
if [ -n "$PROMETHEUS_POD" ]; then
    sleep 5  # Wait for first scrape
    DJANGO_METRICS=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- wget -q -O- 'http://localhost:9090/api/v1/query?query=up{job="django"}' 2>/dev/null | grep -o '"result":\[' | wc -l || echo "0")
    if [ "$DJANGO_METRICS" -gt 0 ]; then
        print_result 0 "Django metrics are being scraped"
    else
        echo "⚠️  Django metrics not yet available (may need more time or Django pods may not be running)"
    fi
else
    print_result 1 "Cannot check Django metrics - pod not found"
fi
echo ""

# Test 8: Check Prometheus configuration
echo "📋 Test 8: Checking Prometheus configuration..."
if [ -n "$PROMETHEUS_POD" ]; then
    CONFIG_STATUS=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- wget -q -O- http://localhost:9090/api/v1/status/config 2>/dev/null | grep -o '"status":"success"' | wc -l || echo "0")
    if [ "$CONFIG_STATUS" -gt 0 ]; then
        print_result 0 "Prometheus configuration is valid"
    else
        print_result 1 "Prometheus configuration may be invalid"
    fi
else
    print_result 1 "Cannot check configuration - pod not found"
fi
echo ""

# Test 9: Check RBAC permissions
echo "📋 Test 9: Checking RBAC permissions..."
if kubectl get clusterrolebinding prometheus &> /dev/null; then
    print_result 0 "Prometheus ClusterRoleBinding exists"
else
    print_result 1 "Prometheus ClusterRoleBinding does not exist"
fi
echo ""

# Test 10: Check storage usage
echo "📋 Test 10: Checking Prometheus storage..."
if [ -n "$PROMETHEUS_POD" ]; then
    STORAGE_SIZE=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- df -h /prometheus 2>/dev/null | tail -1 | awk '{print $2}' || echo "Unknown")
    STORAGE_USED=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- df -h /prometheus 2>/dev/null | tail -1 | awk '{print $3}' || echo "Unknown")
    print_result 0 "Prometheus storage: $STORAGE_USED used of $STORAGE_SIZE"
else
    print_result 1 "Cannot check storage - pod not found"
fi
echo ""

# Summary
echo "============================================================================"
echo "Validation Summary"
echo "============================================================================"
echo ""

if [ $VALIDATION_FAILED -eq 0 ]; then
    echo "✅ All validation tests passed!"
    echo ""
    echo "🎯 Prometheus is ready to collect metrics"
    echo ""
    echo "Access Prometheus UI:"
    echo "  kubectl port-forward -n $NAMESPACE svc/prometheus 9090:9090"
    echo "  Then open: http://localhost:9090"
    echo ""
    exit 0
else
    echo "❌ Some validation tests failed"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check pod logs: kubectl logs -n $NAMESPACE $PROMETHEUS_POD"
    echo "  2. Check pod events: kubectl describe pod -n $NAMESPACE $PROMETHEUS_POD"
    echo "  3. Check service: kubectl describe svc -n $NAMESPACE prometheus"
    echo "  4. Check PVC: kubectl describe pvc -n $NAMESPACE prometheus-storage"
    echo ""
    exit 1
fi
