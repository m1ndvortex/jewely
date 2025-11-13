#!/bin/bash

# ============================================================================
# Health Check Validation Script
# ============================================================================
# This script validates that all health check endpoints are working correctly
# and that Kubernetes probes are properly configured.
#
# Usage: ./validate-health-checks.sh
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Namespace
NAMESPACE="jewelry-shop"

echo "============================================================================"
echo "Health Check Validation"
echo "============================================================================"
echo ""

# Function to print success message
success() {
    echo -e "${GREEN}✓${NC} $1"
}

# Function to print error message
error() {
    echo -e "${RED}✗${NC} $1"
}

# Function to print info message
info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

# ============================================================================
# 1. Test Health Endpoints via Port-Forward
# ============================================================================
echo "1. Testing Health Endpoints via Port-Forward"
echo "-------------------------------------------"

# Get a Django pod
DJANGO_POD=$(kubectl get pods -n $NAMESPACE -l component=django -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -z "$DJANGO_POD" ]; then
    error "No Django pods found in namespace $NAMESPACE"
    exit 1
fi

info "Using Django pod: $DJANGO_POD"

# Start port-forward in background
kubectl port-forward -n $NAMESPACE $DJANGO_POD 8000:8000 > /dev/null 2>&1 &
PF_PID=$!
sleep 3

# Test /health/live/
echo ""
info "Testing /health/live/ endpoint..."
LIVE_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health/live/)
if [ "$LIVE_RESPONSE" = "200" ]; then
    success "Liveness endpoint returned 200 OK"
    curl -s http://localhost:8000/health/live/ | jq '.' 2>/dev/null || echo ""
else
    error "Liveness endpoint returned $LIVE_RESPONSE (expected 200)"
fi

# Test /health/ready/
echo ""
info "Testing /health/ready/ endpoint..."
READY_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health/ready/)
if [ "$READY_RESPONSE" = "200" ]; then
    success "Readiness endpoint returned 200 OK"
    curl -s http://localhost:8000/health/ready/ | jq '.' 2>/dev/null || echo ""
else
    error "Readiness endpoint returned $READY_RESPONSE (expected 200)"
fi

# Test /health/startup/
echo ""
info "Testing /health/startup/ endpoint..."
STARTUP_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health/startup/)
if [ "$STARTUP_RESPONSE" = "200" ]; then
    success "Startup endpoint returned 200 OK"
    curl -s http://localhost:8000/health/startup/ | jq '.' 2>/dev/null || echo ""
else
    error "Startup endpoint returned $STARTUP_RESPONSE (expected 200)"
fi

# Test /health/detailed/
echo ""
info "Testing /health/detailed/ endpoint..."
DETAILED_RESPONSE=$(curl -s http://localhost:8000/health/detailed/)
echo "$DETAILED_RESPONSE" | jq '.' 2>/dev/null || echo "$DETAILED_RESPONSE"

# Kill port-forward
kill $PF_PID 2>/dev/null || true

# ============================================================================
# 2. Verify Probe Configuration in Deployments
# ============================================================================
echo ""
echo "2. Verifying Probe Configuration in Deployments"
echo "-----------------------------------------------"

# Check Django deployment
echo ""
info "Checking Django deployment probes..."
DJANGO_PROBES=$(kubectl get deployment django -n $NAMESPACE -o json | jq '.spec.template.spec.containers[0] | {livenessProbe, readinessProbe, startupProbe}')
echo "$DJANGO_PROBES" | jq '.'

if echo "$DJANGO_PROBES" | grep -q "livenessProbe"; then
    success "Django has liveness probe configured"
else
    error "Django missing liveness probe"
fi

if echo "$DJANGO_PROBES" | grep -q "readinessProbe"; then
    success "Django has readiness probe configured"
else
    error "Django missing readiness probe"
fi

if echo "$DJANGO_PROBES" | grep -q "startupProbe"; then
    success "Django has startup probe configured"
else
    error "Django missing startup probe"
fi

# Check Nginx deployment
echo ""
info "Checking Nginx deployment probes..."
NGINX_PROBES=$(kubectl get deployment nginx -n $NAMESPACE -o json | jq '.spec.template.spec.containers[0] | {livenessProbe, readinessProbe}')
echo "$NGINX_PROBES" | jq '.'

if echo "$NGINX_PROBES" | grep -q "livenessProbe"; then
    success "Nginx has liveness probe configured"
else
    error "Nginx missing liveness probe"
fi

if echo "$NGINX_PROBES" | grep -q "readinessProbe"; then
    success "Nginx has readiness probe configured"
else
    error "Nginx missing readiness probe"
fi

# Check Celery worker deployment
echo ""
info "Checking Celery worker deployment probes..."
CELERY_PROBES=$(kubectl get deployment celery-worker -n $NAMESPACE -o json | jq '.spec.template.spec.containers[0] | {livenessProbe, readinessProbe}')
echo "$CELERY_PROBES" | jq '.'

if echo "$CELERY_PROBES" | grep -q "livenessProbe"; then
    success "Celery worker has liveness probe configured"
else
    error "Celery worker missing liveness probe"
fi

if echo "$CELERY_PROBES" | grep -q "readinessProbe"; then
    success "Celery worker has readiness probe configured"
else
    error "Celery worker missing readiness probe"
fi

# Check Redis StatefulSet
echo ""
info "Checking Redis StatefulSet probes..."
REDIS_PROBES=$(kubectl get statefulset redis -n $NAMESPACE -o json | jq '.spec.template.spec.containers[0] | {livenessProbe, readinessProbe}')
echo "$REDIS_PROBES" | jq '.'

if echo "$REDIS_PROBES" | grep -q "livenessProbe"; then
    success "Redis has liveness probe configured"
else
    error "Redis missing liveness probe"
fi

if echo "$REDIS_PROBES" | grep -q "readinessProbe"; then
    success "Redis has readiness probe configured"
else
    error "Redis missing readiness probe"
fi

# ============================================================================
# 3. Check Pod Health Status
# ============================================================================
echo ""
echo "3. Checking Pod Health Status"
echo "-----------------------------"

# Get all pods
echo ""
info "Listing all pods with their ready status..."
kubectl get pods -n $NAMESPACE -o wide

echo ""
info "Checking for pods with failed probes..."
FAILED_PODS=$(kubectl get pods -n $NAMESPACE --field-selector=status.phase!=Running,status.phase!=Succeeded 2>/dev/null)
if [ -z "$FAILED_PODS" ]; then
    success "All pods are running successfully"
else
    error "Some pods are not running:"
    echo "$FAILED_PODS"
fi

# ============================================================================
# 4. Verify Service Endpoints
# ============================================================================
echo ""
echo "4. Verifying Service Endpoints"
echo "------------------------------"

# Check Django service endpoints
echo ""
info "Checking Django service endpoints..."
DJANGO_ENDPOINTS=$(kubectl get endpoints django -n $NAMESPACE -o json | jq '.subsets[].addresses | length')
if [ "$DJANGO_ENDPOINTS" -gt 0 ]; then
    success "Django service has $DJANGO_ENDPOINTS ready endpoints"
    kubectl get endpoints django -n $NAMESPACE
else
    error "Django service has no ready endpoints"
fi

# Check Nginx service endpoints
echo ""
info "Checking Nginx service endpoints..."
NGINX_ENDPOINTS=$(kubectl get endpoints nginx -n $NAMESPACE -o json | jq '.subsets[].addresses | length')
if [ "$NGINX_ENDPOINTS" -gt 0 ]; then
    success "Nginx service has $NGINX_ENDPOINTS ready endpoints"
    kubectl get endpoints nginx -n $NAMESPACE
else
    error "Nginx service has no ready endpoints"
fi

echo ""
echo "============================================================================"
echo "Health Check Validation Complete"
echo "============================================================================"
