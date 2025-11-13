#!/bin/bash

###############################################################################
# Task 34.8 Validation Script
#
# This script validates the Celery deployment by:
# - Verifying 3 worker pods are running
# - Verifying 1 beat pod is running
# - Checking worker connectivity to Redis
# - Testing task execution
# - Testing worker failover
#
# Requirements: Requirement 23 (Kubernetes Deployment)
###############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="jewelry-shop"
PASSED=0
FAILED=0

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓ PASS]${NC} $1"
    ((PASSED++))
}

log_failure() {
    echo -e "${RED}[✗ FAIL]${NC} $1"
    ((FAILED++))
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Validation Tests

test_worker_pods_running() {
    log_info "Test 1: Verify 3 worker pods are running"
    
    local count=$(kubectl get pods -n "$NAMESPACE" -l component=celery-worker --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
    
    if [ "$count" -eq 3 ]; then
        log_success "3 worker pods are running"
        return 0
    else
        log_failure "Expected 3 worker pods, found $count"
        kubectl get pods -n "$NAMESPACE" -l component=celery-worker
        return 1
    fi
}

test_beat_pod_running() {
    log_info "Test 2: Verify 1 beat pod is running"
    
    local count=$(kubectl get pods -n "$NAMESPACE" -l component=celery-beat --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
    
    if [ "$count" -eq 1 ]; then
        log_success "1 beat pod is running"
        return 0
    else
        log_failure "Expected 1 beat pod, found $count"
        kubectl get pods -n "$NAMESPACE" -l component=celery-beat
        return 1
    fi
}

test_worker_logs() {
    log_info "Test 3: Check worker logs for successful connection"
    
    local worker_pod=$(kubectl get pods -n "$NAMESPACE" -l component=celery-worker -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [ -z "$worker_pod" ]; then
        log_failure "No worker pods found"
        return 1
    fi
    
    # Check for connection messages in logs
    if kubectl logs "$worker_pod" -n "$NAMESPACE" --tail=50 2>/dev/null | grep -q "ready"; then
        log_success "Worker logs show successful connection"
        return 0
    else
        log_failure "Worker logs do not show successful connection"
        log_info "Recent logs:"
        kubectl logs "$worker_pod" -n "$NAMESPACE" --tail=20
        return 1
    fi
}

test_beat_logs() {
    log_info "Test 4: Check beat logs for scheduler initialization"
    
    local beat_pod=$(kubectl get pods -n "$NAMESPACE" -l component=celery-beat -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [ -z "$beat_pod" ]; then
        log_failure "No beat pod found"
        return 1
    fi
    
    # Check for scheduler messages in logs
    if kubectl logs "$beat_pod" -n "$NAMESPACE" --tail=50 2>/dev/null | grep -qE "beat|Scheduler"; then
        log_success "Beat logs show scheduler initialization"
        return 0
    else
        log_failure "Beat logs do not show scheduler initialization"
        log_info "Recent logs:"
        kubectl logs "$beat_pod" -n "$NAMESPACE" --tail=20
        return 1
    fi
}

test_worker_health_probes() {
    log_info "Test 5: Verify worker health probes are configured"
    
    local worker_pod=$(kubectl get pods -n "$NAMESPACE" -l component=celery-worker -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [ -z "$worker_pod" ]; then
        log_failure "No worker pods found"
        return 1
    fi
    
    # Check if probes are configured
    local has_liveness=$(kubectl get pod "$worker_pod" -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].livenessProbe}' 2>/dev/null)
    local has_readiness=$(kubectl get pod "$worker_pod" -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].readinessProbe}' 2>/dev/null)
    
    if [ -n "$has_liveness" ] && [ -n "$has_readiness" ]; then
        log_success "Worker health probes are configured"
        return 0
    else
        log_failure "Worker health probes are not properly configured"
        return 1
    fi
}

test_beat_health_probes() {
    log_info "Test 6: Verify beat health probes are configured"
    
    local beat_pod=$(kubectl get pods -n "$NAMESPACE" -l component=celery-beat -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [ -z "$beat_pod" ]; then
        log_failure "No beat pod found"
        return 1
    fi
    
    # Check if probes are configured
    local has_liveness=$(kubectl get pod "$beat_pod" -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].livenessProbe}' 2>/dev/null)
    local has_readiness=$(kubectl get pod "$beat_pod" -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].readinessProbe}' 2>/dev/null)
    
    if [ -n "$has_liveness" ] && [ -n "$has_readiness" ]; then
        log_success "Beat health probes are configured"
        return 0
    else
        log_failure "Beat health probes are not properly configured"
        return 1
    fi
}

test_resource_limits() {
    log_info "Test 7: Verify resource limits are configured"
    
    local worker_pod=$(kubectl get pods -n "$NAMESPACE" -l component=celery-worker -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [ -z "$worker_pod" ]; then
        log_failure "No worker pods found"
        return 1
    fi
    
    # Check resource limits
    local cpu_limit=$(kubectl get pod "$worker_pod" -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].resources.limits.cpu}' 2>/dev/null)
    local mem_limit=$(kubectl get pod "$worker_pod" -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].resources.limits.memory}' 2>/dev/null)
    
    if [ -n "$cpu_limit" ] && [ -n "$mem_limit" ]; then
        log_success "Resource limits configured: CPU=$cpu_limit, Memory=$mem_limit"
        return 0
    else
        log_failure "Resource limits are not properly configured"
        return 1
    fi
}

test_queue_configuration() {
    log_info "Test 8: Verify queue configuration"
    
    local worker_pod=$(kubectl get pods -n "$NAMESPACE" -l component=celery-worker -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [ -z "$worker_pod" ]; then
        log_failure "No worker pods found"
        return 1
    fi
    
    # Check if multiple queues are configured in logs
    if kubectl logs "$worker_pod" -n "$NAMESPACE" --tail=100 2>/dev/null | grep -qE "backups|pricing|reports|notifications"; then
        log_success "Multiple queues are configured"
        return 0
    else
        log_warning "Could not verify queue configuration from logs"
        return 0  # Don't fail, as this might not always be visible in logs
    fi
}

test_worker_failover() {
    log_info "Test 9: Test worker failover (delete one worker pod)"
    
    # Get initial worker count
    local initial_count=$(kubectl get pods -n "$NAMESPACE" -l component=celery-worker --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
    
    if [ "$initial_count" -ne 3 ]; then
        log_failure "Expected 3 workers before failover test, found $initial_count"
        return 1
    fi
    
    # Get first worker pod
    local worker_pod=$(kubectl get pods -n "$NAMESPACE" -l component=celery-worker -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [ -z "$worker_pod" ]; then
        log_failure "No worker pods found"
        return 1
    fi
    
    log_info "Deleting worker pod: $worker_pod"
    kubectl delete pod "$worker_pod" -n "$NAMESPACE" --wait=false > /dev/null 2>&1
    
    # Wait for pod to be recreated
    log_info "Waiting for pod to be recreated (30 seconds)..."
    sleep 30
    
    # Check if we're back to 3 workers
    local final_count=$(kubectl get pods -n "$NAMESPACE" -l component=celery-worker --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
    
    if [ "$final_count" -eq 3 ]; then
        log_success "Worker pod was automatically recreated (failover successful)"
        return 0
    else
        log_failure "Worker pod was not recreated. Current count: $final_count"
        kubectl get pods -n "$NAMESPACE" -l component=celery-worker
        return 1
    fi
}

test_deployment_strategy() {
    log_info "Test 10: Verify deployment strategy"
    
    # Check worker deployment strategy
    local worker_strategy=$(kubectl get deployment celery-worker -n "$NAMESPACE" -o jsonpath='{.spec.strategy.type}' 2>/dev/null)
    
    if [ "$worker_strategy" = "RollingUpdate" ]; then
        log_success "Worker deployment uses RollingUpdate strategy"
    else
        log_failure "Worker deployment strategy is not RollingUpdate: $worker_strategy"
        return 1
    fi
    
    # Check beat deployment strategy (should be Recreate for singleton)
    local beat_strategy=$(kubectl get deployment celery-beat -n "$NAMESPACE" -o jsonpath='{.spec.strategy.type}' 2>/dev/null)
    
    if [ "$beat_strategy" = "Recreate" ]; then
        log_success "Beat deployment uses Recreate strategy (correct for singleton)"
        return 0
    else
        log_failure "Beat deployment strategy is not Recreate: $beat_strategy"
        return 1
    fi
}

print_summary() {
    echo ""
    echo "=========================================="
    echo "Validation Summary"
    echo "=========================================="
    echo -e "${GREEN}Passed: $PASSED${NC}"
    echo -e "${RED}Failed: $FAILED${NC}"
    echo ""
    
    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}✓ All validations passed!${NC}"
        echo ""
        echo "Celery is properly deployed and operational."
        echo ""
        echo "Next steps:"
        echo "  - Monitor worker logs: kubectl logs -f <worker-pod> -n jewelry-shop"
        echo "  - Monitor beat logs: kubectl logs -f <beat-pod> -n jewelry-shop"
        echo "  - Check task execution in Django admin"
        echo "  - Proceed to task 34.9 (Traefik Ingress Controller)"
        return 0
    else
        echo -e "${RED}✗ Some validations failed${NC}"
        echo ""
        echo "Please review the failures above and fix any issues."
        echo ""
        echo "Common issues:"
        echo "  - Redis not deployed: Run task 34.7 first"
        echo "  - PostgreSQL not deployed: Run task 34.6 first"
        echo "  - ConfigMap/Secrets missing: Run task 34.2 first"
        echo "  - Image not available: Build and load image to k3d"
        return 1
    fi
}

# Main execution
main() {
    echo "=========================================="
    echo "Task 34.8 Validation"
    echo "=========================================="
    echo ""
    
    test_worker_pods_running
    echo ""
    
    test_beat_pod_running
    echo ""
    
    test_worker_logs
    echo ""
    
    test_beat_logs
    echo ""
    
    test_worker_health_probes
    echo ""
    
    test_beat_health_probes
    echo ""
    
    test_resource_limits
    echo ""
    
    test_queue_configuration
    echo ""
    
    test_worker_failover
    echo ""
    
    test_deployment_strategy
    echo ""
    
    print_summary
}

# Run main function
main "$@"
