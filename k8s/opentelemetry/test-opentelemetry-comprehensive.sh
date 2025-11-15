#!/bin/bash

################################################################################
# OpenTelemetry Comprehensive Testing Script
################################################################################
# This script performs comprehensive testing of the OpenTelemetry stack:
# - Component health checks
# - Trace generation and verification
# - End-to-end trace flow testing
# - Grafana integration testing
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

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓ PASS]${NC} $1"
    ((PASSED++))
}

log_error() {
    echo -e "${RED}[✗ FAIL]${NC} $1"
    ((FAILED++))
}

# Test 1: Verify all components are running
test_components_running() {
    log_info "Test 1: Verifying all OpenTelemetry components are running..."
    
    # Check Tempo
    TEMPO_READY=$(kubectl get deployment tempo -n jewelry-shop -o jsonpath='{.status.availableReplicas}' 2>/dev/null || echo "0")
    if [ "$TEMPO_READY" -ge 1 ]; then
        log_success "Tempo is running ($TEMPO_READY replica(s))"
    else
        log_error "Tempo is not running"
        return 1
    fi
    
    # Check OpenTelemetry Collector
    OTEL_READY=$(kubectl get deployment otel-collector -n jewelry-shop -o jsonpath='{.status.availableReplicas}' 2>/dev/null || echo "0")
    if [ "$OTEL_READY" -ge 1 ]; then
        log_success "OpenTelemetry Collector is running ($OTEL_READY replica(s))"
    else
        log_error "OpenTelemetry Collector is not running"
        return 1
    fi
}

# Test 2: Test OTLP gRPC endpoint
test_otlp_grpc_endpoint() {
    log_info "Test 2: Testing OTLP gRPC endpoint connectivity..."
    
    OTEL_POD=$(kubectl get pods -n jewelry-shop -l app=otel-collector -o jsonpath='{.items[0].metadata.name}')
    
    # Check if port 4317 is listening
    if kubectl exec -n jewelry-shop "$OTEL_POD" -- netstat -ln 2>/dev/null | grep -q ":4317"; then
        log_success "OTLP gRPC endpoint (port 4317) is listening"
    else
        log_error "OTLP gRPC endpoint (port 4317) is not listening"
    fi
}

# Test 3: Test OTLP HTTP endpoint
test_otlp_http_endpoint() {
    log_info "Test 3: Testing OTLP HTTP endpoint connectivity..."
    
    OTEL_POD=$(kubectl get pods -n jewelry-shop -l app=otel-collector -o jsonpath='{.items[0].metadata.name}')
    
    # Check if port 4318 is listening
    if kubectl exec -n jewelry-shop "$OTEL_POD" -- netstat -ln 2>/dev/null | grep -q ":4318"; then
        log_success "OTLP HTTP endpoint (port 4318) is listening"
    else
        log_error "OTLP HTTP endpoint (port 4318) is not listening"
    fi
}

# Test 4: Test Tempo API
test_tempo_api() {
    log_info "Test 4: Testing Tempo API endpoints..."
    
    TEMPO_POD=$(kubectl get pods -n jewelry-shop -l app=tempo -o jsonpath='{.items[0].metadata.name}')
    
    # Test ready endpoint
    if kubectl exec -n jewelry-shop "$TEMPO_POD" -- wget -q -O- http://localhost:3200/ready 2>/dev/null | grep -q "ready"; then
        log_success "Tempo /ready endpoint is responding"
    else
        log_error "Tempo /ready endpoint is not responding"
    fi
    
    # Test metrics endpoint
    if kubectl exec -n jewelry-shop "$TEMPO_POD" -- wget -q -O- http://localhost:3200/metrics 2>/dev/null | grep -q "tempo_"; then
        log_success "Tempo /metrics endpoint is responding"
    else
        log_error "Tempo /metrics endpoint is not responding"
    fi
}

# Test 5: Generate test trace
test_generate_trace() {
    log_info "Test 5: Generating test trace from Django..."
    
    DJANGO_POD=$(kubectl get pods -n jewelry-shop -l component=django -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [ -z "$DJANGO_POD" ]; then
        log_error "No Django pod found to generate test trace"
        return 1
    fi
    
    # Make a request to Django to generate a trace
    log_info "Making HTTP request to Django to generate trace..."
    if kubectl exec -n jewelry-shop "$DJANGO_POD" -- wget -q -O- http://localhost:8000/health/live/ &>/dev/null; then
        log_success "Test request sent to Django (trace should be generated)"
    else
        log_error "Failed to send test request to Django"
    fi
}

# Test 6: Check OpenTelemetry Collector received traces
test_collector_received_traces() {
    log_info "Test 6: Checking if OpenTelemetry Collector received traces..."
    
    sleep 5  # Wait for traces to be processed
    
    OTEL_POD=$(kubectl get pods -n jewelry-shop -l app=otel-collector -o jsonpath='{.items[0].metadata.name}')
    
    # Check collector logs for trace processing
    TRACE_COUNT=$(kubectl logs -n jewelry-shop "$OTEL_POD" --tail=100 2>/dev/null | grep -i "trace" | wc -l)
    
    if [ "$TRACE_COUNT" -gt 0 ]; then
        log_success "OpenTelemetry Collector has trace-related log entries ($TRACE_COUNT)"
    else
        log_error "No trace-related log entries found in OpenTelemetry Collector"
    fi
}

# Test 7: Check Tempo received traces
test_tempo_received_traces() {
    log_info "Test 7: Checking if Tempo received traces..."
    
    TEMPO_POD=$(kubectl get pods -n jewelry-shop -l app=tempo -o jsonpath='{.items[0].metadata.name}')
    
    # Check Tempo metrics for ingested spans
    METRICS=$(kubectl exec -n jewelry-shop "$TEMPO_POD" -- wget -q -O- http://localhost:3200/metrics 2>/dev/null)
    
    if echo "$METRICS" | grep -q "tempo_distributor_spans_received_total"; then
        log_success "Tempo has span ingestion metrics"
    else
        log_error "Tempo span ingestion metrics not found"
    fi
}

# Test 8: Test Grafana can query Tempo
test_grafana_tempo_query() {
    log_info "Test 8: Testing Grafana can query Tempo..."
    
    GRAFANA_POD=$(kubectl get pods -n jewelry-shop -l app=grafana -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [ -z "$GRAFANA_POD" ]; then
        log_error "No Grafana pod found"
        return 1
    fi
    
    # Check if Grafana can reach Tempo
    if kubectl exec -n jewelry-shop "$GRAFANA_POD" -- wget -q -O- http://tempo:3200/ready 2>/dev/null | grep -q "ready"; then
        log_success "Grafana can reach Tempo service"
    else
        log_error "Grafana cannot reach Tempo service"
    fi
}

# Test 9: Check resource usage
test_resource_usage() {
    log_info "Test 9: Checking resource usage..."
    
    # Check Tempo resource usage
    TEMPO_POD=$(kubectl get pods -n jewelry-shop -l app=tempo -o jsonpath='{.items[0].metadata.name}')
    TEMPO_CPU=$(kubectl top pod "$TEMPO_POD" -n jewelry-shop 2>/dev/null | tail -1 | awk '{print $2}')
    TEMPO_MEM=$(kubectl top pod "$TEMPO_POD" -n jewelry-shop 2>/dev/null | tail -1 | awk '{print $3}')
    
    if [ -n "$TEMPO_CPU" ]; then
        log_success "Tempo resource usage: CPU=$TEMPO_CPU, Memory=$TEMPO_MEM"
    else
        log_error "Could not get Tempo resource usage (metrics-server may not be installed)"
    fi
    
    # Check OpenTelemetry Collector resource usage
    OTEL_POD=$(kubectl get pods -n jewelry-shop -l app=otel-collector -o jsonpath='{.items[0].metadata.name}')
    OTEL_CPU=$(kubectl top pod "$OTEL_POD" -n jewelry-shop 2>/dev/null | tail -1 | awk '{print $2}')
    OTEL_MEM=$(kubectl top pod "$OTEL_POD" -n jewelry-shop 2>/dev/null | tail -1 | awk '{print $3}')
    
    if [ -n "$OTEL_CPU" ]; then
        log_success "OpenTelemetry Collector resource usage: CPU=$OTEL_CPU, Memory=$OTEL_MEM"
    else
        log_error "Could not get OpenTelemetry Collector resource usage"
    fi
}

# Test 10: Check persistent storage
test_persistent_storage() {
    log_info "Test 10: Checking Tempo persistent storage..."
    
    TEMPO_POD=$(kubectl get pods -n jewelry-shop -l app=tempo -o jsonpath='{.items[0].metadata.name}')
    
    # Check if data directory exists and has content
    if kubectl exec -n jewelry-shop "$TEMPO_POD" -- ls -la /var/tempo/traces 2>/dev/null | grep -q "total"; then
        log_success "Tempo persistent storage is mounted and accessible"
    else
        log_error "Tempo persistent storage is not accessible"
    fi
}

# Display summary and next steps
display_summary() {
    echo ""
    echo "=========================================="
    echo "Test Summary"
    echo "=========================================="
    echo -e "${GREEN}Passed:${NC} $PASSED"
    echo -e "${RED}Failed:${NC} $FAILED"
    echo "=========================================="
    echo ""
    
    if [ $FAILED -eq 0 ]; then
        log_success "All tests passed! OpenTelemetry stack is working correctly."
        echo ""
        log_info "Next steps:"
        echo "  1. Access Grafana: kubectl port-forward -n jewelry-shop svc/grafana 3000:3000"
        echo "  2. Open browser: http://localhost:3000"
        echo "  3. Navigate to Explore > Select 'Tempo' datasource"
        echo "  4. Search for traces by:"
        echo "     - Service name: jewelry-shop-django or jewelry-shop-celery"
        echo "     - Operation name"
        echo "     - Trace ID"
        echo "  5. Generate more traces by using the application"
        echo ""
        return 0
    else
        log_error "Some tests failed. Please review the output above."
        echo ""
        log_info "Troubleshooting:"
        echo "  1. Check pod logs: kubectl logs -n jewelry-shop <pod-name>"
        echo "  2. Check pod status: kubectl describe pod -n jewelry-shop <pod-name>"
        echo "  3. Verify network connectivity between components"
        echo "  4. Ensure Django and Celery have been redeployed with OpenTelemetry dependencies"
        echo ""
        return 1
    fi
}

# Main execution
main() {
    log_info "Starting comprehensive OpenTelemetry testing..."
    echo ""
    
    test_components_running
    test_otlp_grpc_endpoint
    test_otlp_http_endpoint
    test_tempo_api
    test_generate_trace
    test_collector_received_traces
    test_tempo_received_traces
    test_grafana_tempo_query
    test_resource_usage
    test_persistent_storage
    
    display_summary
}

# Run main function
main "$@"
