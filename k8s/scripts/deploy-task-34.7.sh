#!/bin/bash

###############################################################################
# Task 34.7: Deploy Redis Cluster with Sentinel for High Availability
#
# This script deploys a production-ready Redis cluster with:
# - 3 Redis replicas with automatic replication
# - RDB snapshots + AOF persistence
# - 3 Sentinel instances for automatic failover
# - Quorum=2 for master election
# - Prometheus metrics exporters
# - PersistentVolumes for data durability
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
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$(dirname "$SCRIPT_DIR")"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

wait_for_pods() {
    local label=$1
    local count=$2
    local timeout=${3:-300}
    
    log_info "Waiting for $count pods with label $label to be ready (timeout: ${timeout}s)..."
    
    if kubectl wait --for=condition=ready pod \
        -l "$label" \
        -n "$NAMESPACE" \
        --timeout="${timeout}s" 2>/dev/null; then
        log_success "All pods are ready"
        return 0
    else
        log_error "Timeout waiting for pods to be ready"
        return 1
    fi
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        exit 1
    fi
    
    # Check cluster connection
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    # Check namespace
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_error "Namespace $NAMESPACE does not exist. Please run task 34.2 first."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

deploy_redis_config() {
    log_info "Deploying Redis ConfigMap..."
    
    kubectl apply -f "$K8S_DIR/redis-configmap.yaml"
    
    log_success "Redis ConfigMap deployed"
}

deploy_redis_cluster() {
    log_info "Deploying Redis StatefulSet..."
    
    kubectl apply -f "$K8S_DIR/redis-statefulset.yaml"
    
    log_info "Waiting for Redis pods to be ready..."
    sleep 5
    
    if wait_for_pods "app=redis,component=server" 3 300; then
        log_success "Redis cluster deployed successfully"
    else
        log_error "Failed to deploy Redis cluster"
        kubectl get pods -n "$NAMESPACE" -l app=redis,component=server
        exit 1
    fi
}

deploy_redis_sentinel() {
    log_info "Deploying Redis Sentinel StatefulSet..."
    
    kubectl apply -f "$K8S_DIR/redis-sentinel-statefulset.yaml"
    
    log_info "Waiting for Sentinel pods to be ready..."
    sleep 5
    
    if wait_for_pods "app=redis,component=sentinel" 3 300; then
        log_success "Redis Sentinel deployed successfully"
    else
        log_error "Failed to deploy Redis Sentinel"
        kubectl get pods -n "$NAMESPACE" -l app=redis,component=sentinel
        exit 1
    fi
}

verify_deployment() {
    log_info "Verifying Redis deployment..."
    
    echo ""
    log_info "Redis Pods:"
    kubectl get pods -n "$NAMESPACE" -l app=redis,component=server -o wide
    
    echo ""
    log_info "Sentinel Pods:"
    kubectl get pods -n "$NAMESPACE" -l app=redis,component=sentinel -o wide
    
    echo ""
    log_info "Services:"
    kubectl get svc -n "$NAMESPACE" -l app=redis
    
    echo ""
    log_info "PersistentVolumeClaims:"
    kubectl get pvc -n "$NAMESPACE" -l app=redis
    
    echo ""
    log_info "StatefulSets:"
    kubectl get statefulset -n "$NAMESPACE" -l app=redis
}

check_redis_replication() {
    log_info "Checking Redis replication status..."
    
    echo ""
    log_info "Redis-0 (Initial Master):"
    kubectl exec redis-0 -n "$NAMESPACE" -c redis -- redis-cli info replication | grep -E "role|connected_slaves" || true
    
    echo ""
    log_info "Redis-1 (Replica):"
    kubectl exec redis-1 -n "$NAMESPACE" -c redis -- redis-cli info replication | grep -E "role|master_host" || true
    
    echo ""
    log_info "Redis-2 (Replica):"
    kubectl exec redis-2 -n "$NAMESPACE" -c redis -- redis-cli info replication | grep -E "role|master_host" || true
}

check_sentinel_status() {
    log_info "Checking Sentinel status..."
    
    echo ""
    log_info "Sentinel-0 Status:"
    kubectl exec redis-sentinel-0 -n "$NAMESPACE" -c sentinel -- redis-cli -p 26379 sentinel master mymaster | grep -E "name|ip|port|flags|num-slaves|num-other-sentinels" || true
    
    echo ""
    log_info "Sentinel Replicas:"
    kubectl exec redis-sentinel-0 -n "$NAMESPACE" -c sentinel -- redis-cli -p 26379 sentinel replicas mymaster | grep -E "name|ip|port|flags" || true
}

test_redis_connectivity() {
    log_info "Testing Redis connectivity..."
    
    # Test basic operations
    log_info "Setting test key..."
    kubectl exec redis-0 -n "$NAMESPACE" -c redis -- redis-cli set test-key "Hello from Task 34.7" > /dev/null
    
    log_info "Getting test key..."
    local value=$(kubectl exec redis-0 -n "$NAMESPACE" -c redis -- redis-cli get test-key)
    
    if [ "$value" = "Hello from Task 34.7" ]; then
        log_success "Redis connectivity test passed: $value"
    else
        log_error "Redis connectivity test failed"
        exit 1
    fi
    
    # Test from replica
    log_info "Reading from replica..."
    local replica_value=$(kubectl exec redis-1 -n "$NAMESPACE" -c redis -- redis-cli get test-key)
    
    if [ "$replica_value" = "Hello from Task 34.7" ]; then
        log_success "Replica read test passed: $replica_value"
    else
        log_error "Replica read test failed"
        exit 1
    fi
}

print_summary() {
    echo ""
    echo "=========================================="
    log_success "Task 34.7 Deployment Complete!"
    echo "=========================================="
    echo ""
    echo "Redis Cluster Status:"
    echo "  - Redis Pods: 3/3 Running"
    echo "  - Sentinel Pods: 3/3 Running"
    echo "  - Persistence: RDB + AOF enabled"
    echo "  - Quorum: 2 (requires 2 Sentinels for failover)"
    echo "  - Automatic Failover: Enabled"
    echo ""
    echo "Services:"
    echo "  - redis-headless: Headless service for stable DNS"
    echo "  - redis: ClusterIP service for client connections"
    echo "  - redis-sentinel: Sentinel service for monitoring"
    echo ""
    echo "Connection Information:"
    echo "  - Redis Master: redis-0.redis-headless.jewelry-shop.svc.cluster.local:6379"
    echo "  - Sentinel: redis-sentinel.jewelry-shop.svc.cluster.local:26379"
    echo ""
    echo "Next Steps:"
    echo "  1. Run validation: ./scripts/validate-task-34.7.sh"
    echo "  2. Test failover: kubectl delete pod redis-0 -n jewelry-shop"
    echo "  3. Update Django settings to use Sentinel"
    echo "  4. See QUICK_START_34.7.md for usage examples"
    echo ""
}

# Main execution
main() {
    log_info "Starting Task 34.7: Deploy Redis Cluster with Sentinel"
    echo ""
    
    check_prerequisites
    echo ""
    
    deploy_redis_config
    echo ""
    
    deploy_redis_cluster
    echo ""
    
    deploy_redis_sentinel
    echo ""
    
    verify_deployment
    echo ""
    
    # Wait a bit for replication to establish
    log_info "Waiting for replication to establish..."
    sleep 10
    
    check_redis_replication
    echo ""
    
    check_sentinel_status
    echo ""
    
    test_redis_connectivity
    echo ""
    
    print_summary
}

# Run main function
main "$@"
