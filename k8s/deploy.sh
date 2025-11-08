#!/bin/bash
# ============================================================================
# Kubernetes Deployment Script for Jewelry Shop SaaS Platform
# ============================================================================
# This script automates the deployment of the application to Kubernetes.
# It handles namespace creation, secret management, and resource deployment.
# ============================================================================

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="jewelry-shop"
KUSTOMIZE_DIR="$(dirname "$0")"
IMAGE_REGISTRY="${IMAGE_REGISTRY:-your-registry.com}"
IMAGE_NAME="${IMAGE_NAME:-jewelry-shop}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

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
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed. Please install kubectl first."
        exit 1
    fi
    
    # Check cluster connection
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster. Please check your kubeconfig."
        exit 1
    fi
    
    # Check kustomize (optional)
    if command -v kustomize &> /dev/null; then
        log_success "kustomize is available"
    else
        log_warning "kustomize not found. Using kubectl apply -k instead."
    fi
    
    log_success "Prerequisites check passed"
}

create_namespace() {
    log_info "Creating namespace: $NAMESPACE"
    
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_warning "Namespace $NAMESPACE already exists"
    else
        kubectl apply -f "$KUSTOMIZE_DIR/namespace.yaml"
        log_success "Namespace created"
    fi
}

check_secrets() {
    log_info "Checking for required secrets..."
    
    local missing_secrets=()
    
    if ! kubectl get secret django-secrets -n "$NAMESPACE" &> /dev/null; then
        missing_secrets+=("django-secrets")
    fi
    
    if [ ${#missing_secrets[@]} -gt 0 ]; then
        log_error "Missing required secrets: ${missing_secrets[*]}"
        log_info "Please create secrets before deploying. See k8s/README.md for instructions."
        exit 1
    fi
    
    log_success "All required secrets exist"
}

check_configmaps() {
    log_info "Checking for required ConfigMaps..."
    
    local missing_configmaps=()
    
    if ! kubectl get configmap django-config -n "$NAMESPACE" &> /dev/null; then
        missing_configmaps+=("django-config")
    fi
    
    if ! kubectl get configmap nginx-config -n "$NAMESPACE" &> /dev/null; then
        missing_configmaps+=("nginx-config")
    fi
    
    if [ ${#missing_configmaps[@]} -gt 0 ]; then
        log_error "Missing required ConfigMaps: ${missing_configmaps[*]}"
        log_info "Please create ConfigMaps before deploying. See k8s/README.md for instructions."
        exit 1
    fi
    
    log_success "All required ConfigMaps exist"
}

update_image() {
    log_info "Updating image reference to $IMAGE_REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
    
    cd "$KUSTOMIZE_DIR"
    
    if command -v kustomize &> /dev/null; then
        kustomize edit set image jewelry-shop="$IMAGE_REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
    else
        # Update kustomization.yaml manually
        sed -i.bak "s|newName:.*|newName: $IMAGE_REGISTRY/$IMAGE_NAME|" kustomization.yaml
        sed -i.bak "s|newTag:.*|newTag: $IMAGE_TAG|" kustomization.yaml
        rm -f kustomization.yaml.bak
    fi
    
    log_success "Image reference updated"
}

deploy_storage() {
    log_info "Deploying persistent volumes..."
    
    kubectl apply -f "$KUSTOMIZE_DIR/persistent-volumes.yaml"
    
    # Wait for PVCs to be bound
    log_info "Waiting for PVCs to be bound..."
    kubectl wait --for=condition=Bound pvc/media-pvc -n "$NAMESPACE" --timeout=120s || true
    kubectl wait --for=condition=Bound pvc/static-pvc -n "$NAMESPACE" --timeout=120s || true
    kubectl wait --for=condition=Bound pvc/backups-pvc -n "$NAMESPACE" --timeout=120s || true
    
    log_success "Storage deployed"
}

deploy_application() {
    log_info "Deploying application..."
    
    # Deploy using kustomize
    kubectl apply -k "$KUSTOMIZE_DIR"
    
    log_success "Application deployed"
}

wait_for_rollout() {
    log_info "Waiting for deployments to be ready..."
    
    local deployments=("django" "nginx" "celery-worker" "celery-beat")
    
    for deployment in "${deployments[@]}"; do
        log_info "Waiting for $deployment..."
        kubectl rollout status deployment/"$deployment" -n "$NAMESPACE" --timeout=300s
    done
    
    log_success "All deployments are ready"
}

run_migrations() {
    log_info "Running database migrations..."
    
    # Get first Django pod
    local pod=$(kubectl get pods -n "$NAMESPACE" -l component=django -o jsonpath='{.items[0].metadata.name}')
    
    if [ -z "$pod" ]; then
        log_error "No Django pods found"
        return 1
    fi
    
    kubectl exec -n "$NAMESPACE" "$pod" -- python manage.py migrate --noinput
    
    log_success "Migrations completed"
}

collect_static() {
    log_info "Collecting static files..."
    
    # Get first Django pod
    local pod=$(kubectl get pods -n "$NAMESPACE" -l component=django -o jsonpath='{.items[0].metadata.name}')
    
    if [ -z "$pod" ]; then
        log_error "No Django pods found"
        return 1
    fi
    
    kubectl exec -n "$NAMESPACE" "$pod" -- python manage.py collectstatic --noinput
    
    log_success "Static files collected"
}

show_status() {
    log_info "Deployment status:"
    echo ""
    
    kubectl get all -n "$NAMESPACE"
    echo ""
    
    log_info "Service endpoints:"
    kubectl get svc -n "$NAMESPACE"
    echo ""
    
    log_info "Persistent volumes:"
    kubectl get pvc -n "$NAMESPACE"
    echo ""
}

show_access_info() {
    log_info "Access information:"
    echo ""
    
    # Get LoadBalancer IP/hostname
    local lb_ip=$(kubectl get svc nginx-service -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    local lb_hostname=$(kubectl get svc nginx-service -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
    
    if [ -n "$lb_ip" ]; then
        log_success "Application is accessible at: http://$lb_ip"
    elif [ -n "$lb_hostname" ]; then
        log_success "Application is accessible at: http://$lb_hostname"
    else
        log_warning "LoadBalancer IP not yet assigned. Run 'kubectl get svc -n $NAMESPACE' to check status."
        log_info "You can also use port-forward for testing:"
        echo "  kubectl port-forward -n $NAMESPACE svc/nginx-service 8080:80"
    fi
    
    echo ""
}

# Main execution
main() {
    log_info "Starting deployment of Jewelry Shop SaaS Platform to Kubernetes"
    echo ""
    
    # Check prerequisites
    check_prerequisites
    
    # Create namespace
    create_namespace
    
    # Check secrets and configmaps
    check_secrets
    check_configmaps
    
    # Update image reference
    update_image
    
    # Deploy storage
    deploy_storage
    
    # Deploy application
    deploy_application
    
    # Wait for rollout
    wait_for_rollout
    
    # Run migrations
    if [ "${SKIP_MIGRATIONS:-false}" != "true" ]; then
        run_migrations
    else
        log_warning "Skipping migrations (SKIP_MIGRATIONS=true)"
    fi
    
    # Collect static files
    if [ "${SKIP_COLLECTSTATIC:-false}" != "true" ]; then
        collect_static
    else
        log_warning "Skipping collectstatic (SKIP_COLLECTSTATIC=true)"
    fi
    
    # Show status
    show_status
    
    # Show access info
    show_access_info
    
    log_success "Deployment completed successfully!"
}

# Run main function
main "$@"
