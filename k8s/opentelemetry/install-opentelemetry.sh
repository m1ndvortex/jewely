#!/bin/bash

################################################################################
# OpenTelemetry Distributed Tracing Installation Script
################################################################################
# This script deploys the complete OpenTelemetry stack for distributed tracing:
# - Grafana Tempo: Trace storage and query backend
# - OpenTelemetry Collector: Trace collection and processing
# - Grafana integration: Tempo data source configuration
#
# Requirements: Requirement 24 - Monitoring and Observability
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
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

# Check if namespace exists
check_namespace() {
    if ! kubectl get namespace jewelry-shop &> /dev/null; then
        log_error "Namespace 'jewelry-shop' does not exist. Please create it first."
        exit 1
    fi
    log_success "Namespace 'jewelry-shop' exists"
}

# Deploy Tempo
deploy_tempo() {
    log_info "Deploying Grafana Tempo..."
    
    kubectl apply -f tempo-configmap.yaml
    kubectl apply -f tempo-deployment.yaml
    
    log_info "Waiting for Tempo to be ready..."
    kubectl wait --for=condition=available --timeout=300s deployment/tempo -n jewelry-shop
    
    log_success "Tempo deployed successfully"
}

# Deploy OpenTelemetry Collector
deploy_otel_collector() {
    log_info "Deploying OpenTelemetry Collector..."
    
    kubectl apply -f otel-collector-configmap.yaml
    kubectl apply -f otel-collector-deployment.yaml
    
    log_info "Waiting for OpenTelemetry Collector to be ready..."
    kubectl wait --for=condition=available --timeout=300s deployment/otel-collector -n jewelry-shop
    
    log_success "OpenTelemetry Collector deployed successfully"
}

# Update Grafana datasources
update_grafana_datasources() {
    log_info "Updating Grafana datasources to include Tempo..."
    
    # Apply updated Grafana configmap
    kubectl apply -f ../grafana/grafana-configmap.yaml
    
    # Restart Grafana to pick up new datasource
    log_info "Restarting Grafana to load Tempo datasource..."
    kubectl rollout restart deployment/grafana -n jewelry-shop
    kubectl rollout status deployment/grafana -n jewelry-shop --timeout=300s
    
    log_success "Grafana datasources updated"
}

# Verify deployment
verify_deployment() {
    log_info "Verifying OpenTelemetry deployment..."
    
    echo ""
    log_info "=== Tempo Status ==="
    kubectl get pods -n jewelry-shop -l app=tempo
    kubectl get svc -n jewelry-shop -l app=tempo
    
    echo ""
    log_info "=== OpenTelemetry Collector Status ==="
    kubectl get pods -n jewelry-shop -l app=otel-collector
    kubectl get svc -n jewelry-shop -l app=otel-collector
    
    echo ""
    log_info "=== Checking Tempo health ==="
    TEMPO_POD=$(kubectl get pods -n jewelry-shop -l app=tempo -o jsonpath='{.items[0].metadata.name}')
    if kubectl exec -n jewelry-shop "$TEMPO_POD" -- wget -q -O- http://localhost:3200/ready 2>/dev/null | grep -q "ready"; then
        log_success "Tempo is healthy"
    else
        log_warning "Tempo health check failed"
    fi
    
    echo ""
    log_info "=== Checking OpenTelemetry Collector health ==="
    OTEL_POD=$(kubectl get pods -n jewelry-shop -l app=otel-collector -o jsonpath='{.items[0].metadata.name}')
    if kubectl exec -n jewelry-shop "$OTEL_POD" -- wget -q -O- http://localhost:13133 2>/dev/null | grep -q "Server available"; then
        log_success "OpenTelemetry Collector is healthy"
    else
        log_warning "OpenTelemetry Collector health check failed"
    fi
}

# Display access information
display_access_info() {
    echo ""
    log_success "=========================================="
    log_success "OpenTelemetry Stack Deployed Successfully"
    log_success "=========================================="
    echo ""
    log_info "Services:"
    echo "  - Tempo:                http://tempo.jewelry-shop.svc.cluster.local:3200"
    echo "  - Tempo OTLP gRPC:      tempo.jewelry-shop.svc.cluster.local:4317"
    echo "  - Tempo OTLP HTTP:      tempo.jewelry-shop.svc.cluster.local:4318"
    echo "  - OTEL Collector gRPC:  otel-collector.jewelry-shop.svc.cluster.local:4317"
    echo "  - OTEL Collector HTTP:  otel-collector.jewelry-shop.svc.cluster.local:4318"
    echo ""
    log_info "Access Grafana to view traces:"
    echo "  1. Port-forward Grafana: kubectl port-forward -n jewelry-shop svc/grafana 3000:3000"
    echo "  2. Open browser: http://localhost:3000"
    echo "  3. Navigate to Explore > Select 'Tempo' datasource"
    echo "  4. Search for traces by service name, operation, or trace ID"
    echo ""
    log_info "Django and Celery will automatically send traces to:"
    echo "  OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317"
    echo ""
    log_info "Next steps:"
    echo "  1. Rebuild Django and Celery containers with OpenTelemetry dependencies"
    echo "  2. Redeploy Django and Celery with updated environment variables"
    echo "  3. Generate some traffic to create traces"
    echo "  4. View traces in Grafana"
    echo ""
}

# Main execution
main() {
    log_info "Starting OpenTelemetry stack installation..."
    echo ""
    
    check_namespace
    deploy_tempo
    deploy_otel_collector
    update_grafana_datasources
    verify_deployment
    display_access_info
    
    log_success "Installation complete!"
}

# Run main function
main "$@"
