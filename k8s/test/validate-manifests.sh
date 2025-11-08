#!/bin/bash
# ============================================================================
# Kubernetes Manifests Validation Script
# ============================================================================
# This script validates the YAML syntax and structure of all manifests
# ============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAILED=0

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
    ((FAILED++))
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_info "Validating Kubernetes manifests..."
echo ""

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    log_error "kubectl is not installed"
    exit 1
fi
log_success "kubectl is installed"

# Get the k8s directory
K8S_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")"

# Validate YAML syntax
log_info "Checking YAML syntax..."
for file in "$K8S_DIR"/*.yaml; do
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        # Skip kustomization.yaml as it's not a regular K8s resource
        if [ "$filename" = "kustomization.yaml" ]; then
            log_success "Skipping kustomization.yaml (not a K8s resource)"
            continue
        fi
        if kubectl apply --dry-run=client -f "$file" &> /dev/null; then
            log_success "YAML syntax valid: $filename"
        else
            log_error "YAML syntax invalid: $filename"
            kubectl apply --dry-run=client -f "$file" 2>&1 | head -5
        fi
    fi
done

echo ""
log_info "Checking required fields in deployments..."

# Check Django deployment
if grep -q "replicas: 3" "$K8S_DIR/django-deployment.yaml"; then
    log_success "Django deployment has 3 replicas"
else
    log_error "Django deployment does not have 3 replicas"
fi

if grep -q "livenessProbe" "$K8S_DIR/django-deployment.yaml"; then
    log_success "Django deployment has liveness probe"
else
    log_error "Django deployment missing liveness probe"
fi

if grep -q "readinessProbe" "$K8S_DIR/django-deployment.yaml"; then
    log_success "Django deployment has readiness probe"
else
    log_error "Django deployment missing readiness probe"
fi

# Check Nginx deployment
if grep -q "replicas:" "$K8S_DIR/nginx-deployment.yaml"; then
    log_success "Nginx deployment has replicas defined"
else
    log_error "Nginx deployment missing replicas"
fi

# Check Celery worker deployment
if grep -q "replicas:" "$K8S_DIR/celery-worker-deployment.yaml"; then
    log_success "Celery worker deployment has replicas defined"
else
    log_error "Celery worker deployment missing replicas"
fi

# Check Celery beat deployment
if grep -q "replicas: 1" "$K8S_DIR/celery-beat-deployment.yaml"; then
    log_success "Celery beat deployment has 1 replica (singleton)"
else
    log_error "Celery beat deployment does not have exactly 1 replica"
fi

echo ""
log_info "Checking services..."

# Check if all services exist
services=("django-service.yaml" "nginx-service.yaml" "celery-worker-service.yaml" "celery-beat-service.yaml")
for service in "${services[@]}"; do
    if [ -f "$K8S_DIR/$service" ]; then
        log_success "Service exists: $service"
    else
        log_error "Service missing: $service"
    fi
done

echo ""
log_info "Checking kustomization.yaml..."

if [ -f "$K8S_DIR/kustomization.yaml" ]; then
    log_success "kustomization.yaml exists"
    
    # Check if all resources are listed
    if grep -q "django-deployment.yaml" "$K8S_DIR/kustomization.yaml"; then
        log_success "Django deployment listed in kustomization"
    else
        log_error "Django deployment not listed in kustomization"
    fi
    
    if grep -q "nginx-deployment.yaml" "$K8S_DIR/kustomization.yaml"; then
        log_success "Nginx deployment listed in kustomization"
    else
        log_error "Nginx deployment not listed in kustomization"
    fi
else
    log_error "kustomization.yaml missing"
fi

echo ""
log_info "Checking persistent volumes..."

if [ -f "$K8S_DIR/persistent-volumes.yaml" ]; then
    log_success "persistent-volumes.yaml exists"
    
    if grep -q "media-pvc" "$K8S_DIR/persistent-volumes.yaml"; then
        log_success "Media PVC defined"
    else
        log_error "Media PVC not defined"
    fi
    
    if grep -q "static-pvc" "$K8S_DIR/persistent-volumes.yaml"; then
        log_success "Static PVC defined"
    else
        log_error "Static PVC not defined"
    fi
    
    if grep -q "backups-pvc" "$K8S_DIR/persistent-volumes.yaml"; then
        log_success "Backups PVC defined"
    else
        log_error "Backups PVC not defined"
    fi
else
    log_error "persistent-volumes.yaml missing"
fi

echo ""
echo "=========================================="
if [ $FAILED -eq 0 ]; then
    log_success "All validation checks passed!"
    exit 0
else
    log_error "$FAILED validation check(s) failed"
    exit 1
fi
