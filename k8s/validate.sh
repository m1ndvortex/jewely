#!/bin/bash
# ============================================================================
# Kubernetes Deployment Validation Script
# ============================================================================
# This script validates the Kubernetes deployment by checking:
# - All pods are running
# - Services are accessible
# - Health checks are passing
# - Storage is properly mounted
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

NAMESPACE="jewelry-shop"
FAILED_CHECKS=0

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
    ((FAILED_CHECKS++))
}

check_namespace() {
    log_info "Checking namespace..."
    
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_success "Namespace $NAMESPACE exists"
    else
        log_error "Namespace $NAMESPACE does not exist"
    fi
}

check_pods() {
    log_info "Checking pod status..."
    
    local pods=$(kubectl get pods -n "$NAMESPACE" -o json)
    local total=$(echo "$pods" | jq -r '.items | length')
    local running=$(echo "$pods" | jq -r '[.items[] | select(.status.phase=="Running")] | length')
    
    echo "  Total pods: $total"
    echo "  Running pods: $running"
    
    if [ "$total" -eq "$running" ]; then
        log_success "All pods are running"
    else
        log_error "Not all pods are running"
        kubectl get pods -n "$NAMESPACE"
    fi
    
    # Check for restarts
    local restarts=$(echo "$pods" | jq -r '[.items[].status.containerStatuses[]?.restartCount] | add // 0')
    if [ "$restarts" -gt 0 ]; then
        log_warning "Some pods have restarted ($restarts total restarts)"
    fi
}

check_deployments() {
    log_info "Checking deployments..."
    
    local deployments=("django" "nginx" "celery-worker" "celery-beat")
    
    for deployment in "${deployments[@]}"; do
        local ready=$(kubectl get deployment "$deployment" -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}')
        local desired=$(kubectl get deployment "$deployment" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}')
        
        if [ "$ready" = "$desired" ]; then
            log_success "Deployment $deployment: $ready/$desired replicas ready"
        else
            log_error "Deployment $deployment: $ready/$desired replicas ready"
        fi
    done
}

check_services() {
    log_info "Checking services..."
    
    local services=("django-service" "nginx-service" "celery-worker-service" "celery-beat-service")
    
    for service in "${services[@]}"; do
        if kubectl get svc "$service" -n "$NAMESPACE" &> /dev/null; then
            local endpoints=$(kubectl get endpoints "$service" -n "$NAMESPACE" -o jsonpath='{.subsets[*].addresses[*].ip}' | wc -w)
            if [ "$endpoints" -gt 0 ]; then
                log_success "Service $service has $endpoints endpoint(s)"
            else
                log_error "Service $service has no endpoints"
            fi
        else
            log_error "Service $service does not exist"
        fi
    done
}

check_pvcs() {
    log_info "Checking persistent volume claims..."
    
    local pvcs=("media-pvc" "static-pvc" "backups-pvc")
    
    for pvc in "${pvcs[@]}"; do
        local status=$(kubectl get pvc "$pvc" -n "$NAMESPACE" -o jsonpath='{.status.phase}')
        if [ "$status" = "Bound" ]; then
            log_success "PVC $pvc is bound"
        else
            log_error "PVC $pvc is not bound (status: $status)"
        fi
    done
}

check_health_endpoints() {
    log_info "Checking health endpoints..."
    
    # Port forward to Django service
    log_info "Testing Django health endpoint..."
    kubectl port-forward -n "$NAMESPACE" svc/django-service 8000:8000 &> /dev/null &
    local pf_pid=$!
    sleep 3
    
    if curl -sf http://localhost:8000/health/ &> /dev/null; then
        log_success "Django health endpoint is responding"
    else
        log_error "Django health endpoint is not responding"
    fi
    
    kill $pf_pid 2> /dev/null || true
    sleep 1
}

check_resource_usage() {
    log_info "Checking resource usage..."
    
    if kubectl top pods -n "$NAMESPACE" &> /dev/null; then
        echo ""
        kubectl top pods -n "$NAMESPACE"
        echo ""
        log_success "Resource metrics available"
    else
        log_warning "Resource metrics not available (metrics-server may not be installed)"
    fi
}

check_logs_for_errors() {
    log_info "Checking logs for errors..."
    
    local components=("django" "celery-worker" "celery-beat")
    
    for component in "${components[@]}"; do
        local pod=$(kubectl get pods -n "$NAMESPACE" -l component="$component" -o jsonpath='{.items[0].metadata.name}')
        
        if [ -n "$pod" ]; then
            local errors=$(kubectl logs -n "$NAMESPACE" "$pod" --tail=100 | grep -i "error" | wc -l)
            if [ "$errors" -gt 0 ]; then
                log_warning "Found $errors error(s) in $component logs"
            else
                log_success "No errors in $component logs"
            fi
        fi
    done
}

show_summary() {
    echo ""
    echo "=========================================="
    echo "Validation Summary"
    echo "=========================================="
    
    if [ $FAILED_CHECKS -eq 0 ]; then
        log_success "All checks passed!"
        return 0
    else
        log_error "$FAILED_CHECKS check(s) failed"
        return 1
    fi
}

main() {
    log_info "Starting validation of Kubernetes deployment"
    echo ""
    
    check_namespace
    check_pods
    check_deployments
    check_services
    check_pvcs
    check_health_endpoints
    check_resource_usage
    check_logs_for_errors
    
    show_summary
}

main "$@"
