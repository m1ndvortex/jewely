#!/bin/bash

###############################################################################
# Task 34.7: Validation Script for Redis Cluster with Sentinel
#
# This script validates the Redis deployment according to task requirements:
# - 3 Redis replicas running
# - Persistence configured (RDB + AOF)
# - 3 Sentinel instances monitoring
# - Quorum=2 configured
# - Connectivity tests
# - Optional: Failover test
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
WARNINGS=0

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓ PASS]${NC} $1"
    ((PASSED++))
}

log_warning() {
    echo -e "${YELLOW}[⚠ WARN]${NC} $1"
    ((WARNINGS++))
}

log_error() {
    echo -e "${RED}[✗ FAIL]${NC} $1"
    ((FAILED++))
}

test_statefulset() {
    log_info "Test 1: Checking Redis StatefulSet..."
    
    local ready=$(kubectl get statefulset redis -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    local desired=$(kubectl get statefulset redis -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
    
    if [ "$ready" = "3" ] && [ "$desired" = "3" ]; then
        log_success "Redis StatefulSet: 3/3 replicas ready"
    else
        log_error "Redis StatefulSet: $ready/$desired replicas ready (expected 3/3)"
    fi
}

test_sentinel_statefulset() {
    log_info "Test 2: Checking Sentinel StatefulSet..."
    
    local ready=$(kubectl get statefulset redis-sentinel -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    local desired=$(kubectl get statefulset redis-sentinel -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
    
    if [ "$ready" = "3" ] && [ "$desired" = "3" ]; then
        log_success "Sentinel StatefulSet: 3/3 replicas ready"
    else
        log_error "Sentinel StatefulSet: $ready/$desired replicas ready (expected 3/3)"
    fi
}

test_pods_running() {
    log_info "Test 3: Checking all Redis pods are Running..."
    
    local redis_pods=$(kubectl get pods -n "$NAMESPACE" -l app=redis,component=server --no-headers 2>/dev/null | wc -l)
    local redis_running=$(kubectl get pods -n "$NAMESPACE" -l app=redis,component=server --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
    
    if [ "$redis_running" = "3" ]; then
        log_success "All 3 Redis pods are Running"
    else
        log_error "Only $redis_running/3 Redis pods are Running"
    fi
    
    local sentinel_pods=$(kubectl get pods -n "$NAMESPACE" -l app=redis,component=sentinel --no-headers 2>/dev/null | wc -l)
    local sentinel_running=$(kubectl get pods -n "$NAMESPACE" -l app=redis,component=sentinel --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
    
    if [ "$sentinel_running" = "3" ]; then
        log_success "All 3 Sentinel pods are Running"
    else
        log_error "Only $sentinel_running/3 Sentinel pods are Running"
    fi
}

test_services() {
    log_info "Test 4: Checking Services..."
    
    if kubectl get svc redis-headless -n "$NAMESPACE" &>/dev/null; then
        log_success "Headless service 'redis-headless' exists"
    else
        log_error "Headless service 'redis-headless' not found"
    fi
    
    if kubectl get svc redis -n "$NAMESPACE" &>/dev/null; then
        log_success "ClusterIP service 'redis' exists"
    else
        log_error "ClusterIP service 'redis' not found"
    fi
    
    if kubectl get svc redis-sentinel -n "$NAMESPACE" &>/dev/null; then
        log_success "Sentinel service 'redis-sentinel' exists"
    else
        log_error "Sentinel service 'redis-sentinel' not found"
    fi
}

test_pvcs() {
    log_info "Test 5: Checking PersistentVolumeClaims..."
    
    local redis_pvcs=$(kubectl get pvc -n "$NAMESPACE" -l app=redis,component=server --no-headers 2>/dev/null | wc -l)
    local redis_bound=$(kubectl get pvc -n "$NAMESPACE" -l app=redis,component=server --field-selector=status.phase=Bound --no-headers 2>/dev/null | wc -l)
    
    if [ "$redis_bound" = "3" ]; then
        log_success "All 3 Redis PVCs are Bound"
    else
        log_error "Only $redis_bound/3 Redis PVCs are Bound"
    fi
    
    local sentinel_pvcs=$(kubectl get pvc -n "$NAMESPACE" -l app=redis,component=sentinel --no-headers 2>/dev/null | wc -l)
    local sentinel_bound=$(kubectl get pvc -n "$NAMESPACE" -l app=redis,component=sentinel --field-selector=status.phase=Bound --no-headers 2>/dev/null | wc -l)
    
    if [ "$sentinel_bound" = "3" ]; then
        log_success "All 3 Sentinel PVCs are Bound"
    else
        log_error "Only $sentinel_bound/3 Sentinel PVCs are Bound"
    fi
}

test_replication() {
    log_info "Test 6: Checking Redis replication..."
    
    # Check redis-0 (should be master initially)
    local role=$(kubectl exec redis-0 -n "$NAMESPACE" -c redis -- redis-cli info replication 2>/dev/null | grep "role:" | cut -d: -f2 | tr -d '\r')
    
    if [ "$role" = "master" ]; then
        log_success "redis-0 is master"
        
        local slaves=$(kubectl exec redis-0 -n "$NAMESPACE" -c redis -- redis-cli info replication 2>/dev/null | grep "connected_slaves:" | cut -d: -f2 | tr -d '\r')
        
        if [ "$slaves" = "2" ]; then
            log_success "Master has 2 connected replicas"
        else
            log_warning "Master has $slaves connected replicas (expected 2)"
        fi
    else
        log_warning "redis-0 is $role (may have failed over)"
    fi
    
    # Check replicas
    for i in 1 2; do
        local replica_role=$(kubectl exec redis-$i -n "$NAMESPACE" -c redis -- redis-cli info replication 2>/dev/null | grep "role:" | cut -d: -f2 | tr -d '\r')
        
        if [ "$replica_role" = "slave" ]; then
            log_success "redis-$i is replica"
        else
            log_error "redis-$i is $replica_role (expected replica)"
        fi
    done
}

test_persistence() {
    log_info "Test 7: Checking persistence configuration..."
    
    # Check RDB
    local rdb_enabled=$(kubectl exec redis-0 -n "$NAMESPACE" -c redis -- redis-cli config get save 2>/dev/null | grep -c "900 1" || echo "0")
    
    if [ "$rdb_enabled" != "0" ]; then
        log_success "RDB snapshots are configured"
    else
        log_error "RDB snapshots are not configured"
    fi
    
    # Check AOF
    local aof_enabled=$(kubectl exec redis-0 -n "$NAMESPACE" -c redis -- redis-cli config get appendonly 2>/dev/null | grep -c "yes" || echo "0")
    
    if [ "$aof_enabled" != "0" ]; then
        log_success "AOF (Append Only File) is enabled"
    else
        log_error "AOF is not enabled"
    fi
    
    # Check if data directory has files
    local data_files=$(kubectl exec redis-0 -n "$NAMESPACE" -c redis -- ls -la /data 2>/dev/null | wc -l)
    
    if [ "$data_files" -gt "2" ]; then
        log_success "Data directory contains persistence files"
    else
        log_warning "Data directory may be empty"
    fi
}

test_sentinel_monitoring() {
    log_info "Test 8: Checking Sentinel monitoring..."
    
    # Check if Sentinel is monitoring the master
    local master_name=$(kubectl exec redis-sentinel-0 -n "$NAMESPACE" -c sentinel -- redis-cli -p 26379 sentinel masters 2>/dev/null | grep "name" | head -1 | cut -d, -f2 | tr -d '\r')
    
    if [ "$master_name" = "mymaster" ]; then
        log_success "Sentinel is monitoring master 'mymaster'"
    else
        log_error "Sentinel is not monitoring expected master"
    fi
    
    # Check quorum
    local quorum=$(kubectl exec redis-sentinel-0 -n "$NAMESPACE" -c sentinel -- redis-cli -p 26379 sentinel master mymaster 2>/dev/null | grep "quorum" | cut -d, -f2 | tr -d '\r')
    
    if [ "$quorum" = "2" ]; then
        log_success "Sentinel quorum is set to 2"
    else
        log_error "Sentinel quorum is $quorum (expected 2)"
    fi
    
    # Check number of sentinels
    local num_sentinels=$(kubectl exec redis-sentinel-0 -n "$NAMESPACE" -c sentinel -- redis-cli -p 26379 sentinel master mymaster 2>/dev/null | grep "num-other-sentinels" | cut -d, -f2 | tr -d '\r')
    
    if [ "$num_sentinels" = "2" ]; then
        log_success "Sentinel sees 2 other sentinels (3 total)"
    else
        log_warning "Sentinel sees $num_sentinels other sentinels (expected 2)"
    fi
}

test_connectivity() {
    log_info "Test 9: Testing Redis connectivity..."
    
    # Set a test key
    local test_key="validation-test-$(date +%s)"
    local test_value="Task 34.7 Validation"
    
    kubectl exec redis-0 -n "$NAMESPACE" -c redis -- redis-cli set "$test_key" "$test_value" &>/dev/null
    
    # Get the key
    local retrieved=$(kubectl exec redis-0 -n "$NAMESPACE" -c redis -- redis-cli get "$test_key" 2>/dev/null | tr -d '\r')
    
    if [ "$retrieved" = "$test_value" ]; then
        log_success "Can set and get keys on master"
    else
        log_error "Failed to set/get keys on master"
    fi
    
    # Read from replica
    sleep 1  # Give replication a moment
    local replica_value=$(kubectl exec redis-1 -n "$NAMESPACE" -c redis -- redis-cli get "$test_key" 2>/dev/null | tr -d '\r')
    
    if [ "$replica_value" = "$test_value" ]; then
        log_success "Data replicated to replica successfully"
    else
        log_error "Data not replicated to replica"
    fi
    
    # Clean up
    kubectl exec redis-0 -n "$NAMESPACE" -c redis -- redis-cli del "$test_key" &>/dev/null
}

test_health_checks() {
    log_info "Test 10: Checking health probes..."
    
    # Check if pods have liveness and readiness probes
    local redis_liveness=$(kubectl get pod redis-0 -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].livenessProbe}' 2>/dev/null)
    local redis_readiness=$(kubectl get pod redis-0 -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].readinessProbe}' 2>/dev/null)
    
    if [ -n "$redis_liveness" ]; then
        log_success "Redis pods have liveness probes configured"
    else
        log_error "Redis pods missing liveness probes"
    fi
    
    if [ -n "$redis_readiness" ]; then
        log_success "Redis pods have readiness probes configured"
    else
        log_error "Redis pods missing readiness probes"
    fi
    
    local sentinel_liveness=$(kubectl get pod redis-sentinel-0 -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].livenessProbe}' 2>/dev/null)
    local sentinel_readiness=$(kubectl get pod redis-sentinel-0 -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].readinessProbe}' 2>/dev/null)
    
    if [ -n "$sentinel_liveness" ]; then
        log_success "Sentinel pods have liveness probes configured"
    else
        log_error "Sentinel pods missing liveness probes"
    fi
    
    if [ -n "$sentinel_readiness" ]; then
        log_success "Sentinel pods have readiness probes configured"
    else
        log_error "Sentinel pods missing readiness probes"
    fi
}

test_metrics_exporters() {
    log_info "Test 11: Checking metrics exporters..."
    
    # Check if redis-exporter sidecar is running
    local redis_exporter=$(kubectl get pod redis-0 -n "$NAMESPACE" -o jsonpath='{.spec.containers[?(@.name=="redis-exporter")].name}' 2>/dev/null)
    
    if [ "$redis_exporter" = "redis-exporter" ]; then
        log_success "Redis exporter sidecar is configured"
    else
        log_warning "Redis exporter sidecar not found"
    fi
    
    # Check if sentinel-exporter sidecar is running
    local sentinel_exporter=$(kubectl get pod redis-sentinel-0 -n "$NAMESPACE" -o jsonpath='{.spec.containers[?(@.name=="sentinel-exporter")].name}' 2>/dev/null)
    
    if [ "$sentinel_exporter" = "sentinel-exporter" ]; then
        log_success "Sentinel exporter sidecar is configured"
    else
        log_warning "Sentinel exporter sidecar not found"
    fi
}

test_failover_optional() {
    if [ "$1" = "--test-failover" ]; then
        log_info "Test 12: Testing automatic failover (DESTRUCTIVE)..."
        
        # Identify current master
        local current_master=$(kubectl exec redis-sentinel-0 -n "$NAMESPACE" -c sentinel -- redis-cli -p 26379 sentinel get-master-addr-by-name mymaster 2>/dev/null | head -1 | tr -d '\r')
        log_info "Current master IP: $current_master"
        
        # Find which pod is the master
        local master_pod=""
        for i in 0 1 2; do
            local pod_ip=$(kubectl get pod redis-$i -n "$NAMESPACE" -o jsonpath='{.status.podIP}' 2>/dev/null)
            if [ "$pod_ip" = "$current_master" ]; then
                master_pod="redis-$i"
                break
            fi
        done
        
        if [ -z "$master_pod" ]; then
            log_error "Could not identify master pod"
            return
        fi
        
        log_info "Master pod is: $master_pod"
        log_info "Deleting master pod to trigger failover..."
        
        kubectl delete pod "$master_pod" -n "$NAMESPACE" --wait=false
        
        log_info "Waiting 30 seconds for failover..."
        sleep 30
        
        # Check if new master was elected
        local new_master=$(kubectl exec redis-sentinel-0 -n "$NAMESPACE" -c sentinel -- redis-cli -p 26379 sentinel get-master-addr-by-name mymaster 2>/dev/null | head -1 | tr -d '\r')
        
        if [ "$new_master" != "$current_master" ]; then
            log_success "Failover successful! New master IP: $new_master"
        else
            log_error "Failover did not occur or took longer than 30 seconds"
        fi
        
        # Wait for old master to come back as replica
        log_info "Waiting for deleted pod to restart..."
        sleep 30
        
        # Verify all pods are running again
        local running=$(kubectl get pods -n "$NAMESPACE" -l app=redis,component=server --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
        
        if [ "$running" = "3" ]; then
            log_success "All Redis pods are running again"
        else
            log_warning "Only $running/3 Redis pods are running"
        fi
    else
        log_info "Test 12: Skipping failover test (use --test-failover to enable)"
    fi
}

print_summary() {
    echo ""
    echo "=========================================="
    echo "Validation Summary"
    echo "=========================================="
    echo -e "${GREEN}Passed:${NC}   $PASSED"
    echo -e "${YELLOW}Warnings:${NC} $WARNINGS"
    echo -e "${RED}Failed:${NC}   $FAILED"
    echo "=========================================="
    echo ""
    
    if [ $FAILED -eq 0 ]; then
        log_success "All critical tests passed! ✓"
        echo ""
        echo "Redis cluster is ready for production use."
        echo ""
        echo "Next steps:"
        echo "  - Update Django settings to use Sentinel"
        echo "  - Run optional failover test: $0 --test-failover"
        echo "  - Monitor with: kubectl logs -f redis-sentinel-0 -n jewelry-shop -c sentinel"
        return 0
    else
        log_error "Some tests failed. Please review the output above."
        return 1
    fi
}

# Main execution
main() {
    echo "=========================================="
    log_info "Task 34.7: Redis Cluster Validation"
    echo "=========================================="
    echo ""
    
    test_statefulset
    echo ""
    
    test_sentinel_statefulset
    echo ""
    
    test_pods_running
    echo ""
    
    test_services
    echo ""
    
    test_pvcs
    echo ""
    
    test_replication
    echo ""
    
    test_persistence
    echo ""
    
    test_sentinel_monitoring
    echo ""
    
    test_connectivity
    echo ""
    
    test_health_checks
    echo ""
    
    test_metrics_exporters
    echo ""
    
    test_failover_optional "$@"
    echo ""
    
    print_summary
}

# Run main function
main "$@"
