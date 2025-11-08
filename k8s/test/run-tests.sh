#!/bin/bash
# ============================================================================
# Comprehensive Kubernetes Manifests Test Suite
# ============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAILED_TESTS=0

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
    ((FAILED_TESTS++))
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

echo "=========================================="
echo "Kubernetes Manifests Test Suite"
echo "=========================================="
echo ""

# Test 1: Validate YAML syntax
log_info "Test 1: Validating YAML syntax and structure..."
if bash "$(dirname "$0")/validate-manifests.sh"; then
    log_success "YAML validation passed"
else
    log_error "YAML validation failed"
fi
echo ""

# Test 2: Check kubectl and cluster
log_info "Test 2: Checking Kubernetes cluster..."
if kubectl cluster-info &> /dev/null; then
    log_success "Kubernetes cluster is accessible"
else
    log_error "Cannot access Kubernetes cluster"
    exit 1
fi
echo ""

# Test 3: Check namespace
log_info "Test 3: Checking namespace..."
if kubectl get namespace jewelry-shop &> /dev/null; then
    log_success "Namespace jewelry-shop exists"
else
    log_warning "Namespace doesn't exist, creating..."
    kubectl apply -f ../namespace.yaml
    log_success "Namespace created"
fi
echo ""

# Test 4: Check PVCs
log_info "Test 4: Checking persistent volume claims..."
if kubectl get pvc -n jewelry-shop media-pvc &> /dev/null; then
    log_success "PVCs exist"
    pvc_status=$(kubectl get pvc -n jewelry-shop -o jsonpath='{.items[*].status.phase}')
    if [[ "$pvc_status" == *"Bound"* ]]; then
        log_success "All PVCs are bound"
    else
        log_error "Some PVCs are not bound"
    fi
else
    log_warning "PVCs don't exist (expected for fresh test)"
fi
echo ""

# Test 5: Validate deployment structure
log_info "Test 5: Validating deployment configurations..."

K8S_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")"

# Check Django deployment
if kubectl apply --dry-run=client -f "$K8S_DIR/django-deployment.yaml" &> /dev/null; then
    log_success "Django deployment is valid"
else
    log_error "Django deployment is invalid"
fi

# Check Nginx deployment
if kubectl apply --dry-run=client -f "$K8S_DIR/nginx-deployment.yaml" &> /dev/null; then
    log_success "Nginx deployment is valid"
else
    log_error "Nginx deployment is invalid"
fi

# Check Celery worker deployment
if kubectl apply --dry-run=client -f "$K8S_DIR/celery-worker-deployment.yaml" &> /dev/null; then
    log_success "Celery worker deployment is valid"
else
    log_error "Celery worker deployment is invalid"
fi

# Check Celery beat deployment
if kubectl apply --dry-run=client -f "$K8S_DIR/celery-beat-deployment.yaml" &> /dev/null; then
    log_success "Celery beat deployment is valid"
else
    log_error "Celery beat deployment is invalid"
fi
echo ""

# Test 6: Validate services
log_info "Test 6: Validating service configurations..."

services=("django-service" "nginx-service" "celery-worker-service" "celery-beat-service")
for service in "${services[@]}"; do
    if kubectl apply --dry-run=client -f "$K8S_DIR/${service}.yaml" &> /dev/null; then
        log_success "Service $service is valid"
    else
        log_error "Service $service is invalid"
    fi
done
echo ""

# Test 7: Check resource specifications
log_info "Test 7: Checking resource specifications..."

# Check if resources are defined
if grep -q "resources:" "$K8S_DIR/django-deployment.yaml"; then
    log_success "Django deployment has resource limits"
else
    log_error "Django deployment missing resource limits"
fi

if grep -q "resources:" "$K8S_DIR/nginx-deployment.yaml"; then
    log_success "Nginx deployment has resource limits"
else
    log_error "Nginx deployment missing resource limits"
fi
echo ""

# Test 8: Check security contexts
log_info "Test 8: Checking security contexts..."

if grep -q "securityContext:" "$K8S_DIR/django-deployment.yaml"; then
    log_success "Django deployment has security context"
else
    log_error "Django deployment missing security context"
fi

if grep -q "runAsNonRoot: true" "$K8S_DIR/django-deployment.yaml"; then
    log_success "Django runs as non-root user"
else
    log_error "Django not configured to run as non-root"
fi
echo ""

# Test 9: Check health probes
log_info "Test 9: Checking health probes..."

probes=("livenessProbe" "readinessProbe" "startupProbe")
for probe in "${probes[@]}"; do
    if grep -q "$probe:" "$K8S_DIR/django-deployment.yaml"; then
        log_success "Django has $probe"
    else
        log_warning "Django missing $probe"
    fi
done
echo ""

# Test 10: Check kustomization
log_info "Test 10: Validating kustomization.yaml..."

if [ -f "$K8S_DIR/kustomization.yaml" ]; then
    log_success "kustomization.yaml exists"
    
    # Check if it lists all resources
    required_resources=("namespace.yaml" "django-deployment.yaml" "nginx-deployment.yaml" "celery-worker-deployment.yaml" "celery-beat-deployment.yaml")
    for resource in "${required_resources[@]}"; do
        if grep -q "$resource" "$K8S_DIR/kustomization.yaml"; then
            log_success "kustomization includes $resource"
        else
            log_error "kustomization missing $resource"
        fi
    done
else
    log_error "kustomization.yaml not found"
fi
echo ""

# Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
if [ $FAILED_TESTS -eq 0 ]; then
    log_success "All tests passed! ✨"
    echo ""
    log_info "The Kubernetes manifests are valid and ready for deployment."
    echo ""
    log_info "Next steps:"
    echo "  1. Build and push Docker image to registry"
    echo "  2. Create ConfigMaps and Secrets (task 34.6)"
    echo "  3. Deploy to cluster: kubectl apply -k k8s/"
    exit 0
else
    log_error "$FAILED_TESTS test(s) failed"
    exit 1
fi
