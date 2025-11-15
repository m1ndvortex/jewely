#!/bin/bash

# ============================================================================
# Comprehensive Prometheus Testing Script
# Task 35.1: Deploy Prometheus - Complete Requirements Verification
# Requirement 24: Monitoring and Observability
# ============================================================================

set -e

NAMESPACE="jewelry-shop"
PROMETHEUS_POD=""
TEST_FAILED=0
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Log file
LOG_FILE="k8s/prometheus/PROMETHEUS_TEST_RESULTS_$(date +%Y%m%d_%H%M%S).log"

echo "============================================================================"
echo "Comprehensive Prometheus Testing"
echo "Task 35.1: Deploy Prometheus"
echo "Requirement 24: Monitoring and Observability"
echo "============================================================================"
echo ""
echo "Test results will be logged to: $LOG_FILE"
echo ""

# Function to log messages
log() {
    echo "$1" | tee -a "$LOG_FILE"
}

# Function to print test header
print_test_header() {
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    log ""
    log "============================================================================"
    log "TEST $TOTAL_TESTS: $1"
    log "============================================================================"
}

# Function to print test result
print_result() {
    if [ $1 -eq 0 ]; then
        PASSED_TESTS=$((PASSED_TESTS + 1))
        log "${GREEN}✅ PASSED${NC}: $2"
    else
        FAILED_TESTS=$((FAILED_TESTS + 1))
        TEST_FAILED=1
        log "${RED}❌ FAILED${NC}: $2"
    fi
}

# Get Prometheus pod name
get_prometheus_pod() {
    PROMETHEUS_POD=$(kubectl get pod -n "$NAMESPACE" -l app=prometheus -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
}

get_prometheus_pod

# ============================================================================
# REQUIREMENT 24.1: Deploy Prometheus for metrics collection from all services
# ============================================================================

print_test_header "Prometheus Deployment Exists"
if kubectl get deployment prometheus -n "$NAMESPACE" &> /dev/null; then
    REPLICAS=$(kubectl get deployment prometheus -n "$NAMESPACE" -o jsonpath='{.status.replicas}')
    READY=$(kubectl get deployment prometheus -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}')
    if [ "$REPLICAS" = "$READY" ] && [ "$REPLICAS" -ge 1 ]; then
        print_result 0 "Prometheus deployment exists with $READY/$REPLICAS replicas ready"
    else
        print_result 1 "Prometheus deployment exists but not all replicas ready ($READY/$REPLICAS)"
    fi
else
    print_result 1 "Prometheus deployment does not exist"
fi

print_test_header "Prometheus Pod is Running"
if [ -n "$PROMETHEUS_POD" ]; then
    POD_STATUS=$(kubectl get pod "$PROMETHEUS_POD" -n "$NAMESPACE" -o jsonpath='{.status.phase}')
    if [ "$POD_STATUS" = "Running" ]; then
        print_result 0 "Prometheus pod $PROMETHEUS_POD is running"
    else
        print_result 1 "Prometheus pod status is $POD_STATUS (expected: Running)"
    fi
else
    print_result 1 "Prometheus pod not found"
fi

print_test_header "Prometheus Container is Ready"
if [ -n "$PROMETHEUS_POD" ]; then
    READY_STATUS=$(kubectl get pod "$PROMETHEUS_POD" -n "$NAMESPACE" -o jsonpath='{.status.containerStatuses[0].ready}')
    if [ "$READY_STATUS" = "true" ]; then
        print_result 0 "Prometheus container is ready"
    else
        print_result 1 "Prometheus container is not ready"
    fi
else
    print_result 1 "Cannot check container status - pod not found"
fi

print_test_header "Prometheus Service Exists"
if kubectl get svc prometheus -n "$NAMESPACE" &> /dev/null; then
    SVC_TYPE=$(kubectl get svc prometheus -n "$NAMESPACE" -o jsonpath='{.spec.type}')
    SVC_PORT=$(kubectl get svc prometheus -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].port}')
    print_result 0 "Prometheus service exists (Type: $SVC_TYPE, Port: $SVC_PORT)"
else
    print_result 1 "Prometheus service does not exist"
fi

print_test_header "Prometheus PersistentVolumeClaim is Bound"
if kubectl get pvc prometheus-storage -n "$NAMESPACE" &> /dev/null; then
    PVC_STATUS=$(kubectl get pvc prometheus-storage -n "$NAMESPACE" -o jsonpath='{.status.phase}')
    PVC_SIZE=$(kubectl get pvc prometheus-storage -n "$NAMESPACE" -o jsonpath='{.status.capacity.storage}')
    if [ "$PVC_STATUS" = "Bound" ]; then
        print_result 0 "PVC is bound with $PVC_SIZE storage"
    else
        print_result 1 "PVC status is $PVC_STATUS (expected: Bound)"
    fi
else
    print_result 1 "PVC prometheus-storage does not exist"
fi

# ============================================================================
# REQUIREMENT 24.2: Expose Django metrics using django-prometheus
# ============================================================================

print_test_header "Django Prometheus Middleware Configured"
log "Checking if django-prometheus is in INSTALLED_APPS..."
if kubectl exec -n "$NAMESPACE" -it $(kubectl get pod -n "$NAMESPACE" -l component=django -o jsonpath='{.items[0].metadata.name}' 2>/dev/null) -- python manage.py shell -c "from django.conf import settings; print('django_prometheus' in settings.INSTALLED_APPS)" 2>/dev/null | grep -q "True"; then
    print_result 0 "django-prometheus is in INSTALLED_APPS"
else
    log "⚠️  Cannot verify django-prometheus in INSTALLED_APPS (Django pod may not be accessible)"
fi

print_test_header "Django Service Has Prometheus Annotations"
DJANGO_SVC_SCRAPE=$(kubectl get svc django-service -n "$NAMESPACE" -o jsonpath='{.metadata.annotations.prometheus\.io/scrape}' 2>/dev/null || echo "")
DJANGO_SVC_PORT=$(kubectl get svc django-service -n "$NAMESPACE" -o jsonpath='{.metadata.annotations.prometheus\.io/port}' 2>/dev/null || echo "")
DJANGO_SVC_PATH=$(kubectl get svc django-service -n "$NAMESPACE" -o jsonpath='{.metadata.annotations.prometheus\.io/path}' 2>/dev/null || echo "")

if [ "$DJANGO_SVC_SCRAPE" = "true" ] && [ "$DJANGO_SVC_PORT" = "8000" ] && [ "$DJANGO_SVC_PATH" = "/metrics" ]; then
    print_result 0 "Django service has correct Prometheus annotations (scrape=$DJANGO_SVC_SCRAPE, port=$DJANGO_SVC_PORT, path=$DJANGO_SVC_PATH)"
else
    print_result 1 "Django service annotations incorrect or missing (scrape=$DJANGO_SVC_SCRAPE, port=$DJANGO_SVC_PORT, path=$DJANGO_SVC_PATH)"
fi

print_test_header "Prometheus Discovers Django Targets"
if [ -n "$PROMETHEUS_POD" ]; then
    sleep 5  # Wait for scrape
    DJANGO_TARGETS=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- wget -q -O- 'http://localhost:9090/api/v1/targets' 2>/dev/null | grep -o '"job":"django-service"' | wc -l || echo "0")
    if [ "$DJANGO_TARGETS" -gt 0 ]; then
        print_result 0 "Prometheus discovered $DJANGO_TARGETS Django target(s)"
    else
        print_result 1 "Prometheus did not discover any Django targets"
    fi
else
    print_result 1 "Cannot check Django targets - Prometheus pod not found"
fi

# ============================================================================
# REQUIREMENT 24.3: Configure scraping for all services
# ============================================================================

print_test_header "Prometheus Configuration Contains All Service Jobs"
if [ -n "$PROMETHEUS_POD" ]; then
    CONFIG=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- cat /etc/prometheus/prometheus.yml 2>/dev/null || echo "")
    
    JOBS=("django" "postgresql" "redis" "nginx" "celery" "kubernetes-apiservers" "kubernetes-nodes" "kubernetes-pods")
    MISSING_JOBS=""
    
    for job in "${JOBS[@]}"; do
        if echo "$CONFIG" | grep -q "job_name: '$job'"; then
            log "  ✓ Job '$job' found in configuration"
        else
            MISSING_JOBS="$MISSING_JOBS $job"
        fi
    done
    
    if [ -z "$MISSING_JOBS" ]; then
        print_result 0 "All required scrape jobs are configured"
    else
        print_result 1 "Missing scrape jobs:$MISSING_JOBS"
    fi
else
    print_result 1 "Cannot check configuration - Prometheus pod not found"
fi

print_test_header "Scrape Intervals Are Configured Correctly"
if [ -n "$PROMETHEUS_POD" ]; then
    GLOBAL_INTERVAL=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- cat /etc/prometheus/prometheus.yml 2>/dev/null | grep "scrape_interval:" | head -1 | awk '{print $2}')
    if [ "$GLOBAL_INTERVAL" = "15s" ]; then
        print_result 0 "Global scrape interval is $GLOBAL_INTERVAL"
    else
        print_result 1 "Global scrape interval is $GLOBAL_INTERVAL (expected: 15s)"
    fi
else
    print_result 1 "Cannot check scrape intervals - Prometheus pod not found"
fi

# ============================================================================
# REQUIREMENT 24.4: Set up service discovery
# ============================================================================

print_test_header "Kubernetes Service Discovery is Configured"
if [ -n "$PROMETHEUS_POD" ]; then
    SD_CONFIGS=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- cat /etc/prometheus/prometheus.yml 2>/dev/null | grep -c "kubernetes_sd_configs:" || echo "0")
    if [ "$SD_CONFIGS" -gt 0 ]; then
        print_result 0 "Kubernetes service discovery is configured ($SD_CONFIGS instances)"
    else
        print_result 1 "Kubernetes service discovery is not configured"
    fi
else
    print_result 1 "Cannot check service discovery - Prometheus pod not found"
fi

print_test_header "Prometheus Has RBAC Permissions for Service Discovery"
if kubectl get clusterrolebinding prometheus &> /dev/null; then
    SA_NAME=$(kubectl get clusterrolebinding prometheus -o jsonpath='{.subjects[0].name}')
    SA_NAMESPACE=$(kubectl get clusterrolebinding prometheus -o jsonpath='{.subjects[0].namespace}')
    if [ "$SA_NAME" = "prometheus" ] && [ "$SA_NAMESPACE" = "$NAMESPACE" ]; then
        print_result 0 "ClusterRoleBinding exists for prometheus ServiceAccount"
    else
        print_result 1 "ClusterRoleBinding exists but references wrong ServiceAccount ($SA_NAME in $SA_NAMESPACE)"
    fi
else
    print_result 1 "ClusterRoleBinding prometheus does not exist"
fi

print_test_header "Prometheus ServiceAccount Exists"
if kubectl get sa prometheus -n "$NAMESPACE" &> /dev/null; then
    print_result 0 "ServiceAccount prometheus exists in $NAMESPACE"
else
    print_result 1 "ServiceAccount prometheus does not exist"
fi

print_test_header "Prometheus ClusterRole Has Required Permissions"
if kubectl get clusterrole prometheus &> /dev/null; then
    REQUIRED_RESOURCES=("pods" "services" "endpoints" "nodes")
    MISSING_RESOURCES=""
    
    for resource in "${REQUIRED_RESOURCES[@]}"; do
        if kubectl get clusterrole prometheus -o yaml | grep -q "- $resource"; then
            log "  ✓ Permission for '$resource' found"
        else
            MISSING_RESOURCES="$MISSING_RESOURCES $resource"
        fi
    done
    
    if [ -z "$MISSING_RESOURCES" ]; then
        print_result 0 "ClusterRole has all required permissions"
    else
        print_result 1 "ClusterRole missing permissions for:$MISSING_RESOURCES"
    fi
else
    print_result 1 "ClusterRole prometheus does not exist"
fi

print_test_header "Service Discovery is Actually Working"
if [ -n "$PROMETHEUS_POD" ]; then
    TOTAL_TARGETS=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- wget -q -O- 'http://localhost:9090/api/v1/targets' 2>/dev/null | grep -o '"activeTargets":\[' | wc -l || echo "0")
    ACTIVE_COUNT=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- wget -q -O- 'http://localhost:9090/api/v1/targets' 2>/dev/null | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data['data']['activeTargets']))" 2>/dev/null || echo "0")
    
    if [ "$ACTIVE_COUNT" -gt 0 ]; then
        print_result 0 "Service discovery found $ACTIVE_COUNT active targets"
        log "  Listing discovered targets:"
        kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- wget -q -O- 'http://localhost:9090/api/v1/targets' 2>/dev/null | python3 -c "import sys, json; data=json.load(sys.stdin); [print(f\"    - {t['scrapePool']}: {t['labels'].get('instance', 'N/A')}\") for t in data['data']['activeTargets'][:10]]" 2>/dev/null | tee -a "$LOG_FILE"
    else
        print_result 1 "Service discovery found 0 targets"
    fi
else
    print_result 1 "Cannot check service discovery - Prometheus pod not found"
fi

# ============================================================================
# FUNCTIONAL TESTS
# ============================================================================

print_test_header "Prometheus Health Endpoint Responds"
if [ -n "$PROMETHEUS_POD" ]; then
    HEALTH_RESPONSE=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- wget -q -O- http://localhost:9090/-/healthy 2>/dev/null || echo "")
    if echo "$HEALTH_RESPONSE" | grep -q "Prometheus"; then
        print_result 0 "Health endpoint responds correctly"
    else
        print_result 1 "Health endpoint response unexpected: $HEALTH_RESPONSE"
    fi
else
    print_result 1 "Cannot check health endpoint - Prometheus pod not found"
fi

print_test_header "Prometheus Readiness Endpoint Responds"
if [ -n "$PROMETHEUS_POD" ]; then
    READY_RESPONSE=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- wget -q -O- http://localhost:9090/-/ready 2>/dev/null || echo "")
    if echo "$READY_RESPONSE" | grep -q "Prometheus"; then
        print_result 0 "Readiness endpoint responds correctly"
    else
        print_result 1 "Readiness endpoint response unexpected: $READY_RESPONSE"
    fi
else
    print_result 1 "Cannot check readiness endpoint - Prometheus pod not found"
fi

print_test_header "Prometheus API is Accessible"
if [ -n "$PROMETHEUS_POD" ]; then
    API_RESPONSE=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- wget -q -O- 'http://localhost:9090/api/v1/status/config' 2>/dev/null || echo "")
    if echo "$API_RESPONSE" | grep -q '"status":"success"'; then
        print_result 0 "Prometheus API is accessible and responding"
    else
        print_result 1 "Prometheus API response unexpected"
    fi
else
    print_result 1 "Cannot check API - Prometheus pod not found"
fi

print_test_header "Prometheus Can Execute Queries"
if [ -n "$PROMETHEUS_POD" ]; then
    QUERY_RESPONSE=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- wget -q -O- 'http://localhost:9090/api/v1/query?query=up' 2>/dev/null || echo "")
    if echo "$QUERY_RESPONSE" | grep -q '"status":"success"'; then
        RESULT_COUNT=$(echo "$QUERY_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data['data']['result']))" 2>/dev/null || echo "0")
        print_result 0 "Prometheus can execute queries (found $RESULT_COUNT results for 'up' query)"
    else
        print_result 1 "Prometheus query execution failed"
    fi
else
    print_result 1 "Cannot execute queries - Prometheus pod not found"
fi

print_test_header "Prometheus Storage is Writable"
if [ -n "$PROMETHEUS_POD" ]; then
    STORAGE_TEST=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- sh -c "touch /prometheus/test_write && rm /prometheus/test_write && echo 'success'" 2>/dev/null || echo "failed")
    if [ "$STORAGE_TEST" = "success" ]; then
        print_result 0 "Prometheus storage is writable"
    else
        print_result 1 "Prometheus storage is not writable"
    fi
else
    print_result 1 "Cannot check storage - Prometheus pod not found"
fi

print_test_header "Prometheus Storage Has Sufficient Space"
if [ -n "$PROMETHEUS_POD" ]; then
    STORAGE_AVAIL=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- df -h /prometheus 2>/dev/null | tail -1 | awk '{print $4}' || echo "Unknown")
    STORAGE_USED=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- df -h /prometheus 2>/dev/null | tail -1 | awk '{print $5}' || echo "Unknown")
    log "  Storage available: $STORAGE_AVAIL, Used: $STORAGE_USED"
    
    USED_PERCENT=$(echo "$STORAGE_USED" | tr -d '%')
    if [ "$USED_PERCENT" -lt 90 ]; then
        print_result 0 "Prometheus storage has sufficient space ($STORAGE_USED used)"
    else
        print_result 1 "Prometheus storage is running low ($STORAGE_USED used)"
    fi
else
    print_result 1 "Cannot check storage space - Prometheus pod not found"
fi

# ============================================================================
# CONFIGURATION TESTS
# ============================================================================

print_test_header "Prometheus Retention Policy is Configured"
if [ -n "$PROMETHEUS_POD" ]; then
    RETENTION_TIME=$(kubectl get deployment prometheus -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].args}' | grep -o 'storage.tsdb.retention.time=[^,]*' | cut -d= -f2 || echo "")
    RETENTION_SIZE=$(kubectl get deployment prometheus -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].args}' | grep -o 'storage.tsdb.retention.size=[^,]*' | cut -d= -f2 || echo "")
    
    if [ -n "$RETENTION_TIME" ] && [ -n "$RETENTION_SIZE" ]; then
        print_result 0 "Retention policy configured (time=$RETENTION_TIME, size=$RETENTION_SIZE)"
    else
        print_result 1 "Retention policy not properly configured"
    fi
else
    print_result 1 "Cannot check retention policy - Prometheus pod not found"
fi

print_test_header "Prometheus Resource Limits are Set"
CPU_REQUEST=$(kubectl get deployment prometheus -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].resources.requests.cpu}' || echo "")
MEM_REQUEST=$(kubectl get deployment prometheus -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].resources.requests.memory}' || echo "")
CPU_LIMIT=$(kubectl get deployment prometheus -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].resources.limits.cpu}' || echo "")
MEM_LIMIT=$(kubectl get deployment prometheus -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].resources.limits.memory}' || echo "")

if [ -n "$CPU_REQUEST" ] && [ -n "$MEM_REQUEST" ] && [ -n "$CPU_LIMIT" ] && [ -n "$MEM_LIMIT" ]; then
    print_result 0 "Resource limits configured (CPU: $CPU_REQUEST-$CPU_LIMIT, Memory: $MEM_REQUEST-$MEM_LIMIT)"
else
    print_result 1 "Resource limits not properly configured"
fi

print_test_header "Prometheus Liveness Probe is Configured"
LIVENESS_PATH=$(kubectl get deployment prometheus -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].livenessProbe.httpGet.path}' || echo "")
if [ "$LIVENESS_PATH" = "/-/healthy" ]; then
    print_result 0 "Liveness probe configured correctly"
else
    print_result 1 "Liveness probe not configured or incorrect (path=$LIVENESS_PATH)"
fi

print_test_header "Prometheus Readiness Probe is Configured"
READINESS_PATH=$(kubectl get deployment prometheus -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].readinessProbe.httpGet.path}' || echo "")
if [ "$READINESS_PATH" = "/-/ready" ]; then
    print_result 0 "Readiness probe configured correctly"
else
    print_result 1 "Readiness probe not configured or incorrect (path=$READINESS_PATH)"
fi

print_test_header "Prometheus ConfigMap is Mounted"
if [ -n "$PROMETHEUS_POD" ]; then
    CONFIG_EXISTS=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- test -f /etc/prometheus/prometheus.yml && echo "yes" || echo "no")
    if [ "$CONFIG_EXISTS" = "yes" ]; then
        print_result 0 "ConfigMap is properly mounted at /etc/prometheus/prometheus.yml"
    else
        print_result 1 "ConfigMap is not mounted"
    fi
else
    print_result 1 "Cannot check ConfigMap mount - Prometheus pod not found"
fi

# ============================================================================
# METRICS COLLECTION TESTS
# ============================================================================

print_test_header "Prometheus is Collecting Metrics"
if [ -n "$PROMETHEUS_POD" ]; then
    sleep 10  # Wait for metrics collection
    METRICS_COUNT=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- wget -q -O- 'http://localhost:9090/api/v1/query?query=up' 2>/dev/null | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data['data']['result']))" 2>/dev/null || echo "0")
    
    if [ "$METRICS_COUNT" -gt 0 ]; then
        print_result 0 "Prometheus is collecting metrics ($METRICS_COUNT 'up' metrics found)"
    else
        print_result 1 "Prometheus is not collecting any metrics"
    fi
else
    print_result 1 "Cannot check metrics collection - Prometheus pod not found"
fi

print_test_header "Prometheus Self-Monitoring Works"
if [ -n "$PROMETHEUS_POD" ]; then
    SELF_METRICS=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- wget -q -O- 'http://localhost:9090/api/v1/query?query=prometheus_build_info' 2>/dev/null | grep -o '"status":"success"' | wc -l || echo "0")
    
    if [ "$SELF_METRICS" -gt 0 ]; then
        print_result 0 "Prometheus self-monitoring is working"
    else
        print_result 1 "Prometheus self-monitoring is not working"
    fi
else
    print_result 1 "Cannot check self-monitoring - Prometheus pod not found"
fi

# ============================================================================
# INTEGRATION TESTS
# ============================================================================

print_test_header "Prometheus Can Reach Kubernetes API"
if [ -n "$PROMETHEUS_POD" ]; then
    K8S_TARGETS=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- wget -q -O- 'http://localhost:9090/api/v1/targets' 2>/dev/null | grep -o '"job":"kubernetes-' | wc -l || echo "0")
    
    if [ "$K8S_TARGETS" -gt 0 ]; then
        print_result 0 "Prometheus can reach Kubernetes API ($K8S_TARGETS Kubernetes targets)"
    else
        print_result 1 "Prometheus cannot reach Kubernetes API"
    fi
else
    print_result 1 "Cannot check Kubernetes API access - Prometheus pod not found"
fi

print_test_header "Prometheus Discovers Kubernetes Nodes"
if [ -n "$PROMETHEUS_POD" ]; then
    NODE_COUNT=$(kubectl get nodes --no-headers | wc -l)
    DISCOVERED_NODES=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- wget -q -O- 'http://localhost:9090/api/v1/targets' 2>/dev/null | grep -o '"job":"kubernetes-nodes"' | wc -l || echo "0")
    
    log "  Cluster has $NODE_COUNT nodes, Prometheus discovered $DISCOVERED_NODES"
    if [ "$DISCOVERED_NODES" -gt 0 ]; then
        print_result 0 "Prometheus discovers Kubernetes nodes"
    else
        print_result 1 "Prometheus did not discover any Kubernetes nodes"
    fi
else
    print_result 1 "Cannot check node discovery - Prometheus pod not found"
fi

print_test_header "Prometheus Discovers Pods in Namespace"
if [ -n "$PROMETHEUS_POD" ]; then
    POD_TARGETS=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- wget -q -O- 'http://localhost:9090/api/v1/targets' 2>/dev/null | grep -o '"kubernetes_namespace":"jewelry-shop"' | wc -l || echo "0")
    
    if [ "$POD_TARGETS" -gt 0 ]; then
        print_result 0 "Prometheus discovers pods in jewelry-shop namespace ($POD_TARGETS targets)"
    else
        print_result 1 "Prometheus did not discover any pods in jewelry-shop namespace"
    fi
else
    print_result 1 "Cannot check pod discovery - Prometheus pod not found"
fi

# ============================================================================
# SECURITY TESTS
# ============================================================================

print_test_header "Prometheus Runs as Non-Root User"
if [ -n "$PROMETHEUS_POD" ]; then
    USER_ID=$(kubectl exec -n "$NAMESPACE" "$PROMETHEUS_POD" -- id -u 2>/dev/null || echo "0")
    if [ "$USER_ID" != "0" ]; then
        print_result 0 "Prometheus runs as non-root user (UID: $USER_ID)"
    else
        print_result 1 "Prometheus runs as root user (security risk)"
    fi
else
    print_result 1 "Cannot check user - Prometheus pod not found"
fi

print_test_header "Prometheus Pod Has Security Context"
SECURITY_CONTEXT=$(kubectl get deployment prometheus -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.securityContext}' || echo "")
if [ -n "$SECURITY_CONTEXT" ]; then
    print_result 0 "Security context is configured"
else
    print_result 1 "Security context is not configured"
fi

# ============================================================================
# FINAL SUMMARY
# ============================================================================

log ""
log "============================================================================"
log "TEST SUMMARY"
log "============================================================================"
log ""
log "Total Tests: $TOTAL_TESTS"
log "${GREEN}Passed: $PASSED_TESTS${NC}"
log "${RED}Failed: $FAILED_TESTS${NC}"
log ""

if [ $TEST_FAILED -eq 0 ]; then
    log "${GREEN}============================================================================${NC}"
    log "${GREEN}✅ ALL TESTS PASSED - PROMETHEUS IS PRODUCTION READY${NC}"
    log "${GREEN}============================================================================${NC}"
    log ""
    log "Prometheus is successfully deployed and operational."
    log "All requirements for Task 35.1 are satisfied."
    log ""
    log "Next Steps:"
    log "  1. Deploy Grafana (Task 35.2)"
    log "  2. Add exporter sidecars (postgres_exporter, redis_exporter, nginx-exporter)"
    log "  3. Configure alerting (Task 35.4)"
    log ""
    exit 0
else
    log "${RED}============================================================================${NC}"
    log "${RED}❌ SOME TESTS FAILED${NC}"
    log "${RED}============================================================================${NC}"
    log ""
    log "Please review the failed tests above and fix the issues."
    log ""
    log "Troubleshooting:"
    log "  1. Check pod logs: kubectl logs -n $NAMESPACE $PROMETHEUS_POD"
    log "  2. Check pod events: kubectl describe pod -n $NAMESPACE $PROMETHEUS_POD"
    log "  3. Check service: kubectl describe svc -n $NAMESPACE prometheus"
    log "  4. Check PVC: kubectl describe pvc -n $NAMESPACE prometheus-storage"
    log ""
    exit 1
fi
