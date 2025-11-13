#!/bin/bash

###############################################################################
# Task 34.8: Deploy Celery Workers and Beat Scheduler
#
# This script deploys Celery for background task processing:
# - 3 Celery worker replicas for high availability
# - 1 Celery beat replica (singleton) for task scheduling
# - Multiple queue support (backups, reports, notifications, etc.)
# - Health probes for automatic recovery
# - Resource limits for stability
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
    
    # Check Redis is deployed
    if ! kubectl get statefulset redis -n "$NAMESPACE" &> /dev/null; then
        log_warning "Redis StatefulSet not found. Celery requires Redis as broker."
        log_warning "Please deploy Redis first (task 34.7)"
    fi
    
    # Check PostgreSQL is deployed
    if ! kubectl get postgresql jewelry-shop-db -n "$NAMESPACE" &> /dev/null; then
        log_warning "PostgreSQL cluster not found. Celery requires database access."
        log_warning "Please deploy PostgreSQL first (task 34.6)"
    fi
    
    log_success "Prerequisites check passed"
}

deploy_celery_workers() {
    log_info "Deploying Celery Worker Deployment..."
    
    kubectl apply -f "$K8S_DIR/celery-worker-deployment.yaml"
    
    log_info "Deploying Celery Worker PodDisruptionBudget..."
    kubectl apply -f "$K8S_DIR/celery-worker-pdb.yaml"
    
    log_info "Waiting for Celery worker pods to be ready..."
    sleep 5
    
    if wait_for_pods "component=celery-worker" 3 300; then
        log_success "Celery workers deployed successfully"
    else
        log_error "Failed to deploy Celery workers"
        kubectl get pods -n "$NAMESPACE" -l component=celery-worker
        kubectl describe pods -n "$NAMESPACE" -l component=celery-worker
        exit 1
    fi
}

deploy_celery_beat() {
    log_info "Deploying Celery Beat Deployment..."
    
    kubectl apply -f "$K8S_DIR/celery-beat-deployment.yaml"
    
    log_info "Waiting for Celery beat pod to be ready..."
    sleep 5
    
    if wait_for_pods "component=celery-beat" 1 300; then
        log_success "Celery beat deployed successfully"
    else
        log_error "Failed to deploy Celery beat"
        kubectl get pods -n "$NAMESPACE" -l component=celery-beat
        kubectl describe pods -n "$NAMESPACE" -l component=celery-beat
        exit 1
    fi
}

verify_deployment() {
    log_info "Verifying Celery deployment..."
    
    echo ""
    log_info "Celery Worker Pods:"
    kubectl get pods -n "$NAMESPACE" -l component=celery-worker -o wide
    
    echo ""
    log_info "Celery Beat Pod:"
    kubectl get pods -n "$NAMESPACE" -l component=celery-beat -o wide
    
    echo ""
    log_info "Deployments:"
    kubectl get deployment -n "$NAMESPACE" -l tier=backend | grep celery
}

check_worker_connectivity() {
    log_info "Checking Celery worker connectivity to Redis..."
    
    # Get first worker pod
    local worker_pod=$(kubectl get pods -n "$NAMESPACE" -l component=celery-worker -o jsonpath='{.items[0].metadata.name}')
    
    if [ -z "$worker_pod" ]; then
        log_error "No worker pods found"
        return 1
    fi
    
    log_info "Checking worker pod: $worker_pod"
    
    # Check worker logs for connection
    log_info "Recent worker logs:"
    kubectl logs "$worker_pod" -n "$NAMESPACE" --tail=20 | grep -E "Connected|ready|celery@" || true
}

check_beat_connectivity() {
    log_info "Checking Celery beat connectivity..."
    
    # Get beat pod
    local beat_pod=$(kubectl get pods -n "$NAMESPACE" -l component=celery-beat -o jsonpath='{.items[0].metadata.name}')
    
    if [ -z "$beat_pod" ]; then
        log_error "No beat pod found"
        return 1
    fi
    
    log_info "Checking beat pod: $beat_pod"
    
    # Check beat logs
    log_info "Recent beat logs:"
    kubectl logs "$beat_pod" -n "$NAMESPACE" --tail=20 | grep -E "beat|Scheduler|DatabaseScheduler" || true
}

test_task_execution() {
    log_info "Testing task execution..."
    
    # Get first worker pod
    local worker_pod=$(kubectl get pods -n "$NAMESPACE" -l component=celery-worker -o jsonpath='{.items[0].metadata.name}')
    
    if [ -z "$worker_pod" ]; then
        log_error "No worker pods found"
        return 1
    fi
    
    log_info "Executing test task via Django shell..."
    
    # Execute debug task
    kubectl exec "$worker_pod" -n "$NAMESPACE" -- python manage.py shell -c "
from config.celery import debug_task
result = debug_task.delay()
print(f'Task ID: {result.id}')
print(f'Task sent successfully')
" 2>/dev/null || log_warning "Could not execute test task (Django may not be fully configured yet)"
    
    log_info "Check worker logs to verify task execution"
}

check_queue_configuration() {
    log_info "Checking queue configuration..."
    
    # Get first worker pod
    local worker_pod=$(kubectl get pods -n "$NAMESPACE" -l component=celery-worker -o jsonpath='{.items[0].metadata.name}')
    
    if [ -z "$worker_pod" ]; then
        log_error "No worker pods found"
        return 1
    fi
    
    log_info "Queues configured on worker:"
    kubectl logs "$worker_pod" -n "$NAMESPACE" --tail=50 | grep -E "celery|backups|pricing|reports|notifications|accounting|monitoring|webhooks" | head -5 || true
}

print_summary() {
    echo ""
    echo "=========================================="
    log_success "Task 34.8 Deployment Complete!"
    echo "=========================================="
    echo ""
    echo "Celery Status:"
    echo "  - Worker Pods: 3/3 Running"
    echo "  - Beat Pod: 1/1 Running"
    echo "  - Concurrency: 4 per worker (12 total)"
    echo "  - Queues: celery, backups, pricing, reports, notifications, accounting, monitoring, webhooks"
    echo ""
    echo "Resource Allocation:"
    echo "  - Workers: 400m-800m CPU, 512Mi-1Gi Memory each"
    echo "  - Beat: 250m-500m CPU, 256Mi-512Mi Memory"
    echo ""
    echo "High Availability:"
    echo "  - PodDisruptionBudget: Min 2 workers available"
    echo "  - Init containers: Wait for Redis & PostgreSQL"
    echo "  - Staggered startup: Random 0-10s delay"
    echo "  - Pod anti-affinity: Spread across nodes"
    echo ""
    echo "Health Checks:"
    echo "  - Liveness: Process check (every 30s)"
    echo "  - Readiness: Process check (every 15s)"
    echo "  - Startup: 360s timeout for initialization"
    echo ""
    echo "Scheduled Tasks:"
    echo "  - Daily full database backup (2:00 AM)"
    echo "  - Weekly per-tenant backup (Sunday 3:00 AM)"
    echo "  - Continuous WAL archiving (hourly)"
    echo "  - Gold rate updates (every 5 minutes)"
    echo "  - Report execution (every 15 minutes)"
    echo "  - System monitoring (every 5 minutes)"
    echo "  - And more... (see config/celery.py)"
    echo ""
    echo "Next Steps:"
    echo "  1. Run validation: ./scripts/validate-task-34.8.sh"
    echo "  2. Test failover: kubectl delete pod <worker-pod> -n jewelry-shop"
    echo "  3. Monitor tasks: kubectl logs -f <worker-pod> -n jewelry-shop"
    echo "  4. See QUICK_START_34.8.md for usage examples"
    echo ""
}

# Main execution
main() {
    log_info "Starting Task 34.8: Deploy Celery Workers and Beat Scheduler"
    echo ""
    
    check_prerequisites
    echo ""
    
    deploy_celery_workers
    echo ""
    
    deploy_celery_beat
    echo ""
    
    verify_deployment
    echo ""
    
    # Wait a bit for workers to connect
    log_info "Waiting for workers to connect to Redis..."
    sleep 10
    
    check_worker_connectivity
    echo ""
    
    check_beat_connectivity
    echo ""
    
    check_queue_configuration
    echo ""
    
    test_task_execution
    echo ""
    
    print_summary
}

# Run main function
main "$@"
