#!/bin/bash

# ============================================================================
# Task 34.3: Deploy Django Application with Health Checks
# ============================================================================
# This script deploys the Django application to Kubernetes with:
# - 3 replicas for high availability
# - Comprehensive health probes (liveness, readiness, startup)
# - Resource requests and limits
# - ClusterIP service for internal access
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="jewelry-shop"
DEPLOYMENT_NAME="django"
SERVICE_NAME="django-service"
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

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if kubectl is installed
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        exit 1
    fi
    
    # Check if cluster is accessible
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    # Check if namespace exists
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_error "Namespace '$NAMESPACE' does not exist. Run task 34.2 first."
        exit 1
    fi
    
    # Check if ConfigMap and Secrets exist
    if ! kubectl get configmap app-config -n "$NAMESPACE" &> /dev/null; then
        log_error "ConfigMap 'app-config' does not exist. Run task 34.2 first."
        exit 1
    fi
    
    if ! kubectl get secret app-secrets -n "$NAMESPACE" &> /dev/null; then
        log_error "Secret 'app-secrets' does not exist. Run task 34.2 first."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

deploy_django() {
    log_info "Deploying Django application..."
    
    # Apply Django Deployment
    log_info "Creating Django Deployment with 3 replicas..."
    kubectl apply -f "$K8S_DIR/django-deployment.yaml"
    
    # Apply Django Service
    log_info "Creating Django ClusterIP Service..."
    kubectl apply -f "$K8S_DIR/django-service.yaml"
    
    log_success "Django manifests applied"
}

wait_for_deployment() {
    log_info "Waiting for Django deployment to be ready..."
    
    # Wait for deployment to be available (timeout: 5 minutes)
    if kubectl wait --for=condition=available --timeout=300s \
        deployment/"$DEPLOYMENT_NAME" -n "$NAMESPACE"; then
        log_success "Django deployment is ready"
    else
        log_error "Django deployment failed to become ready"
        log_info "Checking pod status..."
        kubectl get pods -n "$NAMESPACE" -l component=django
        log_info "Checking pod logs..."
        kubectl logs -n "$NAMESPACE" -l component=django --tail=50
        exit 1
    fi
}

verify_deployment() {
    log_info "Verifying Django deployment..."
    
    # Check pod count
    EXPECTED_REPLICAS=3
    READY_REPLICAS=$(kubectl get deployment "$DEPLOYMENT_NAME" -n "$NAMESPACE" \
        -o jsonpath='{.status.readyReplicas}')
    
    if [ "$READY_REPLICAS" -eq "$EXPECTED_REPLICAS" ]; then
        log_success "All $EXPECTED_REPLICAS Django pods are ready"
    else
        log_error "Expected $EXPECTED_REPLICAS pods, but only $READY_REPLICAS are ready"
        exit 1
    fi
    
    # Check service
    if kubectl get service "$SERVICE_NAME" -n "$NAMESPACE" &> /dev/null; then
        log_success "Django service is created"
        
        # Get service details
        SERVICE_IP=$(kubectl get service "$SERVICE_NAME" -n "$NAMESPACE" \
            -o jsonpath='{.spec.clusterIP}')
        SERVICE_PORT=$(kubectl get service "$SERVICE_NAME" -n "$NAMESPACE" \
            -o jsonpath='{.spec.ports[0].port}')
        
        log_info "Service ClusterIP: $SERVICE_IP"
        log_info "Service Port: $SERVICE_PORT"
    else
        log_error "Django service not found"
        exit 1
    fi
}

verify_health_probes() {
    log_info "Verifying health probes configuration..."
    
    # Get first pod name
    POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l component=django \
        -o jsonpath='{.items[0].metadata.name}')
    
    if [ -z "$POD_NAME" ]; then
        log_error "No Django pods found"
        exit 1
    fi
    
    log_info "Checking pod: $POD_NAME"
    
    # Check liveness probe
    LIVENESS_PATH=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" \
        -o jsonpath='{.spec.containers[0].livenessProbe.httpGet.path}')
    
    if [ "$LIVENESS_PATH" == "/health/live/" ]; then
        log_success "Liveness probe configured: $LIVENESS_PATH"
    else
        log_error "Liveness probe not configured correctly"
        exit 1
    fi
    
    # Check readiness probe
    READINESS_PATH=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" \
        -o jsonpath='{.spec.containers[0].readinessProbe.httpGet.path}')
    
    if [ "$READINESS_PATH" == "/health/ready/" ]; then
        log_success "Readiness probe configured: $READINESS_PATH"
    else
        log_error "Readiness probe not configured correctly"
        exit 1
    fi
    
    # Check startup probe
    STARTUP_PATH=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" \
        -o jsonpath='{.spec.containers[0].startupProbe.httpGet.path}')
    
    if [ "$STARTUP_PATH" == "/health/startup/" ]; then
        log_success "Startup probe configured: $STARTUP_PATH"
    else
        log_error "Startup probe not configured correctly"
        exit 1
    fi
}

verify_resource_limits() {
    log_info "Verifying resource requests and limits..."
    
    # Get first pod name
    POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l component=django \
        -o jsonpath='{.items[0].metadata.name}')
    
    # Check CPU requests
    CPU_REQUEST=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" \
        -o jsonpath='{.spec.containers[0].resources.requests.cpu}')
    
    if [ "$CPU_REQUEST" == "500m" ]; then
        log_success "CPU request: $CPU_REQUEST"
    else
        log_warning "CPU request: $CPU_REQUEST (expected: 500m)"
    fi
    
    # Check CPU limits
    CPU_LIMIT=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" \
        -o jsonpath='{.spec.containers[0].resources.limits.cpu}')
    
    if [ "$CPU_LIMIT" == "1000m" ] || [ "$CPU_LIMIT" == "1" ]; then
        log_success "CPU limit: $CPU_LIMIT"
    else
        log_warning "CPU limit: $CPU_LIMIT (expected: 1000m)"
    fi
    
    # Check memory requests
    MEMORY_REQUEST=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" \
        -o jsonpath='{.spec.containers[0].resources.requests.memory}')
    
    if [ "$MEMORY_REQUEST" == "512Mi" ]; then
        log_success "Memory request: $MEMORY_REQUEST"
    else
        log_warning "Memory request: $MEMORY_REQUEST (expected: 512Mi)"
    fi
    
    # Check memory limits
    MEMORY_LIMIT=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" \
        -o jsonpath='{.spec.containers[0].resources.limits.memory}')
    
    if [ "$MEMORY_LIMIT" == "1Gi" ]; then
        log_success "Memory limit: $MEMORY_LIMIT"
    else
        log_warning "Memory limit: $MEMORY_LIMIT (expected: 1Gi)"
    fi
}

display_summary() {
    log_info "Deployment Summary:"
    echo ""
    echo "Namespace: $NAMESPACE"
    echo "Deployment: $DEPLOYMENT_NAME"
    echo "Service: $SERVICE_NAME"
    echo ""
    
    log_info "Django Pods:"
    kubectl get pods -n "$NAMESPACE" -l component=django
    echo ""
    
    log_info "Django Service:"
    kubectl get service "$SERVICE_NAME" -n "$NAMESPACE"
    echo ""
    
    log_info "Deployment Details:"
    kubectl get deployment "$DEPLOYMENT_NAME" -n "$NAMESPACE"
    echo ""
}

# Main execution
main() {
    log_info "Starting Task 34.3: Deploy Django Application with Health Checks"
    echo ""
    
    check_prerequisites
    echo ""
    
    deploy_django
    echo ""
    
    wait_for_deployment
    echo ""
    
    verify_deployment
    echo ""
    
    verify_health_probes
    echo ""
    
    verify_resource_limits
    echo ""
    
    display_summary
    
    log_success "Task 34.3 completed successfully!"
    log_info "Next steps:"
    echo "  1. Run validation script: ./scripts/validate-task-34.3.sh"
    echo "  2. Test health endpoints manually"
    echo "  3. Proceed to Task 34.4: Deploy Nginx reverse proxy"
}

# Run main function
main
