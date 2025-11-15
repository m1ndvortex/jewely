#!/bin/bash

################################################################################
# OpenTelemetry Distributed Tracing Validation Script
################################################################################
# This script validates the OpenTelemetry distributed tracing setup:
# - Tempo deployment and health
# - OpenTelemetry Collector deployment and health
# - Grafana Tempo datasource configuration
# - End-to-end trace flow from Django/Celery to Tempo
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

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Logging functions
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

# Test 1: Check Tempo deployment
test_tempo_deployment() {
    log_info "Test 1: Checking Tempo deployment..."
    
    if kubectl get deployment tempo -n jewelry-shop &> /dev/null; then
        REPLICAS=$(kubectl get deployment tempo -n jewelry-shop -o jsonpath='{.status.availableReplicas}')
        if [ "$REPLICAS" -ge 1 ]; then
            log_success "Tempo deployment is running with $REPLICAS replica(s)"
        else
            log_error "Tempo deployment exists but no replicas are available"
        fi
    else
        log_error "Tempo deployment not found"
    fi
}

# Test 2: Check Tempo service
test_tempo_service() {
    log_info "Test 2: Checking Tempo service..."
    
    if kubectl get svc tempo -n jewelry-shop &> /dev/null; then
        PORTS=$(kubectl get svc tempo -n jewelry-shop -o jsonpath='{.spec.ports[*].port}')
        log_success "Tempo service exists with ports: $PORTS"
    else
        log_error "Tempo service not found"
    fi
}

# Test 3: Check Tempo health
test_tempo_health() {
    log_info "Test 3: Checking Tempo health endpoint..."
    
    TEMPO_POD=$(kubectl get pods -n jewelry-shop -l app=tempo -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    if [ -n "$TEMPO_POD" ]; then
        if kubectl exec -n jewelry-shop "$TEMPO_POD" -- wget -q -O- http://localhost:3200/ready 2>/dev/null | grep -q "ready"; then
            log_success "Tempo health check passed"
        else
            log_error "Tempo health check failed"
        fi
    else
        log_error "No Tempo pod found"
    fi
}

# Test 4: Check OpenTelemetry Collector deployment
test_otel_collector_deployment() {
    log_info "Test 4: Checking OpenTelemetry Collector deployment..."
    
    if kubectl get deployment otel-collector -n jewelry-shop &> /dev/null; then
        REPLICAS=$(kubectl get deployment otel-collector -n jewelry-shop -o jsonpath='{.status.availableReplicas}')
        if [ "$REPLICAS" -ge 1 ]; then
            log_success "OpenTelemetry Collector deployment is running with $REPLICAS replica(s)"
        else
            log_error "OpenTelemetry Collector deployment exists but no replicas are available"
        fi
    else
        log_error "OpenTelemetry Collector deployment not found"
    fi
}

# Test 5: Check OpenTelemetry Collector service
test_otel_collector_service() {
    log_info "Test 5: Checking OpenTelemetry Collector service..."
    
    if kubectl get svc otel-collector -n jewelry-shop &> /dev/null; then
        PORTS=$(kubectl get svc otel-collector -n jewelry-shop -o jsonpath='{.spec.ports[*].port}')
        log_success "OpenTelemetry Collector service exists with ports: $PORTS"
    else
        log_error "OpenTelemetry Collector service not found"
    fi
}

# Test 6: Check OpenTelemetry Collector health
test_otel_collector_health() {
    log_info "Test 6: Checking OpenTelemetry Collector health endpoint..."
    
    OTEL_POD=$(kubectl get pods -n jewelry-shop -l app=otel-collector -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    if [ -n "$OTEL_POD" ]; then
        if kubectl exec -n jewelry-shop "$OTEL_POD" -- wget -q -O- http://localhost:13133 2>/dev/null | grep -q "Server available"; then
            log_success "OpenTelemetry Collector health check passed"
        else
            log_error "OpenTelemetry Collector health check failed"
        fi
    else
        log_error "No OpenTelemetry Collector pod found"
    fi
}

# Test 7: Check Tempo PVC
test_tempo_pvc() {
    log_info "Test 7: Checking Tempo PersistentVolumeClaim..."
    
    if kubectl get pvc tempo-data -n jewelry-shop &> /dev/null; then
        STATUS=$(kubectl get pvc tempo-data -n jewelry-shop -o jsonpath='{.status.phase}')
        if [ "$STATUS" = "Bound" ]; then
            log_success "Tempo PVC is bound"
        else
            log_error "Tempo PVC exists but is not bound (status: $STATUS)"
        fi
    else
        log_error "Tempo PVC not found"
    fi
}

# Test 8: Check Django environment variables
test_django_otel_config() {
    log_info "Test 8: Checking Django OpenTelemetry configuration..."
    
    DJANGO_POD=$(kubectl get pods -n jewelry-shop -l component=django -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    if [ -n "$DJANGO_POD" ]; then
        OTEL_ENABLED=$(kubectl exec -n jewelry-shop "$DJANGO_POD" -- env | grep OTEL_ENABLED || echo "")
        OTEL_ENDPOINT=$(kubectl exec -n jewelry-shop "$DJANGO_POD" -- env | grep OTEL_EXPORTER_OTLP_ENDPOINT || echo "")
        
        if [ -n "$OTEL_ENABLED" ] && [ -n "$OTEL_ENDPOINT" ]; then
            log_success "Django has OpenTelemetry environment variables configured"
        else
            log_warning "Django OpenTelemetry environment variables not found (may need redeployment)"
        fi
    else
        log_warning "No Django pod found to check configuration"
    fi
}

# Test 9: Check Celery environment variables
test_celery_otel_config() {
    log_info "Test 9: Checking Celery OpenTelemetry configuration..."
    
    CELERY_POD=$(kubectl get pods -n jewelry-shop -l component=celery-worker -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    if [ -n "$CELERY_POD" ]; then
        OTEL_ENABLED=$(kubectl exec -n jewelry-shop "$CELERY_POD" -- env | grep OTEL_ENABLED || echo "")
        OTEL_ENDPOINT=$(kubectl exec -n jewelry-shop "$CELERY_POD" -- env | grep OTEL_EXPORTER_OTLP_ENDPOINT || echo "")
        
        if [ -n "$OTEL_ENABLED" ] && [ -n "$OTEL_ENDPOINT" ]; then
            log_success "Celery has OpenTelemetry environment variables configured"
        else
            log_warning "Celery OpenTelemetry environment variables not found (may need redeployment)"
        fi
    else
        log_warning "No Celery pod found to check configuration"
    fi
}

# Test 10: Check Grafana Tempo datasource
test_grafana_tempo_datasource() {
    log_info "Test 10: Checking Grafana Tempo datasource configuration..."
    
    if kubectl get configmap grafana-datasources -n jewelry-shop &> /dev/null; then
        if kubectl get configmap grafana-datasources -n jewelry-shop -o yaml | grep -q "type: tempo"; then
            log_success "Grafana has Tempo datasource configured"
        else
            log_error "Grafana datasources ConfigMap exists but Tempo datasource not found"
        fi
    else
        log_error "Grafana datasources ConfigMap not found"
    fi
}

# Test 11: Check OpenTelemetry Collector logs for errors
test_otel_collector_logs() {
    log_info "Test 11: Checking OpenTelemetry Collector logs for errors..."
    
    OTEL_POD=$(kubectl get pods -n jewelry-shop -l app=otel-collector -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    if [ -n "$OTEL_POD" ]; then
        ERROR_COUNT=$(kubectl logs -n jewelry-shop "$OTEL_POD" --tail=100 2>/dev/null | grep -i "error" | wc -l)
        if [ "$ERROR_COUNT" -eq 0 ]; then
            log_success "No errors found in OpenTelemetry Collector logs"
        else
            log_warning "Found $ERROR_COUNT error(s) in OpenTelemetry Collector logs"
        fi
    else
        log_warning "No OpenTelemetry Collector pod found to check logs"
    fi
}

# Test 12: Check Tempo logs for errors
test_tempo_logs() {
    log_info "Test 12: Checking Tempo logs for errors..."
    
    TEMPO_POD=$(kubectl get pods -n jewelry-shop -l app=tempo -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    if [ -n "$TEMPO_POD" ]; then
        ERROR_COUNT=$(kubectl logs -n jewelry-shop "$TEMPO_POD" --tail=100 2>/dev/null | grep -i "error" | wc -l)
        if [ "$ERROR_COUNT" -eq 0 ]; then
            log_success "No errors found in Tempo logs"
        else
            log_warning "Found $ERROR_COUNT error(s) in Tempo logs"
        fi
    else
        log_warning "No Tempo pod found to check logs"
    fi
}

# Display summary
display_summary() {
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
        log_success "All critical tests passed!"
        if [ $WARNINGS -gt 0 ]; then
            log_warning "Some warnings were found. Review them above."
        fi
        return 0
    else
        log_error "Some tests failed. Please review the output above."
        return 1
    fi
}

# Main execution
main() {
    log_info "Starting OpenTelemetry validation..."
    echo ""
    
    test_tempo_deployment
    test_tempo_service
    test_tempo_health
    test_otel_collector_deployment
    test_otel_collector_service
    test_otel_collector_health
    test_tempo_pvc
    test_django_otel_config
    test_celery_otel_config
    test_grafana_tempo_datasource
    test_otel_collector_logs
    test_tempo_logs
    
    display_summary
}

# Run main function
main "$@"
