#!/bin/bash
################################################################################
# Professional VPS Deployment Script
# This script automates the complete deployment process for production
################################################################################

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VERSION=${VERSION:-"v1.0.0"}
REGISTRY=${REGISTRY:-"your-registry.com"}  # Change to your Docker registry
NAMESPACE=${NAMESPACE:-"jewelry-shop"}
KUBECONFIG=${KUBECONFIG:-"$HOME/.kube/config"}

# Functions
log_info() {
    echo -e "${BLUE}ℹ  ${1}${NC}"
}

log_success() {
    echo -e "${GREEN}✅ ${1}${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  ${1}${NC}"
}

log_error() {
    echo -e "${RED}❌ ${1}${NC}"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local missing=0
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Please install kubectl."
        missing=1
    fi
    
    # Check docker
    if ! command -v docker &> /dev/null; then
        log_error "docker not found. Please install Docker."
        missing=1
    fi
    
    # Check helm (optional but recommended)
    if ! command -v helm &> /dev/null; then
        log_warning "helm not found. Some features may be unavailable."
    fi
    
    # Check cluster connectivity
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster. Check your kubeconfig."
        missing=1
    fi
    
    if [ $missing -eq 1 ]; then
        exit 1
    fi
    
    log_success "All prerequisites satisfied"
}

build_docker_images() {
    log_info "Building Docker images..."
    
    cd "$PROJECT_ROOT"
    
    # Build Django production image
    docker build \
        -f Dockerfile.prod \
        -t jewelry-shop-django:${VERSION} \
        -t jewelry-shop-django:latest \
        --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
        --build-arg VCS_REF=$(git rev-parse --short HEAD) \
        --build-arg VERSION=${VERSION} \
        .
    
    log_success "Docker images built successfully"
}

push_to_registry() {
    log_info "Pushing images to registry..."
    
    # Tag for registry
    docker tag jewelry-shop-django:${VERSION} ${REGISTRY}/jewelry-shop-django:${VERSION}
    docker tag jewelry-shop-django:latest ${REGISTRY}/jewelry-shop-django:latest
    
    # Push
    docker push ${REGISTRY}/jewelry-shop-django:${VERSION}
    docker push ${REGISTRY}/jewelry-shop-django:latest
    
    log_success "Images pushed to registry"
}

create_namespace() {
    log_info "Creating/verifying namespace..."
    
    kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -
    
    log_success "Namespace ready"
}

apply_secrets() {
    log_info "Applying secrets..."
    
    # Check if secrets file exists
    if [ ! -f "$PROJECT_ROOT/.env.production" ]; then
        log_error "Missing .env.production file"
        log_info "Please create .env.production from .env.production.example"
        exit 1
    fi
    
    # Create secrets from .env file
    kubectl create secret generic django-secrets \
        --from-env-file="$PROJECT_ROOT/.env.production" \
        --namespace=${NAMESPACE} \
        --dry-run=client -o yaml | kubectl apply -f -
    
    log_success "Secrets applied"
}

apply_configmaps() {
    log_info "Applying ConfigMaps..."
    
    kubectl apply -f "$PROJECT_ROOT/k8s/configmap.yaml" -n ${NAMESPACE}
    
    log_success "ConfigMaps applied"
}

apply_postgresql() {
    log_info "Deploying PostgreSQL..."
    
    kubectl apply -f "$PROJECT_ROOT/k8s/postgresql/" -n ${NAMESPACE}
    
    # Wait for PostgreSQL to be ready
    kubectl wait --for=condition=ready pod -l app=postgresql -n ${NAMESPACE} --timeout=300s
    
    log_success "PostgreSQL ready"
}

apply_redis() {
    log_info "Deploying Redis Sentinel..."
    
    kubectl apply -f "$PROJECT_ROOT/k8s/redis/" -n ${NAMESPACE}
    
    # Wait for Redis to be ready
    kubectl wait --for=condition=ready pod -l app=redis -n ${NAMESPACE} --timeout=300s
    
    log_success "Redis Sentinel ready"
}

run_migrations() {
    log_info "Running database migrations..."
    
    # Create migration job
    cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: django-migrate-${VERSION//./}
  namespace: ${NAMESPACE}
spec:
  template:
    spec:
      restartPolicy: OnFailure
      initContainers:
        - name: wait-for-db
          image: busybox:1.35
          command:
            - sh
            - -c
            - |
              until nc -z jewelry-shop-db-pooler 5432; do
                echo "Waiting for database..."
                sleep 2
              done
              echo "Database ready!"
      containers:
        - name: migrate
          image: ${REGISTRY}/jewelry-shop-django:${VERSION}
          command:
            - sh
            - -c
            - |
              echo "Running migrations..."
              python manage.py migrate --noinput
              echo "Migrations complete!"
          envFrom:
            - configMapRef:
                name: django-config
            - secretRef:
                name: django-secrets
EOF
    
    # Wait for migration job to complete
    kubectl wait --for=condition=complete job/django-migrate-${VERSION//./} -n ${NAMESPACE} --timeout=600s
    
    log_success "Database migrations completed"
}

create_superuser() {
    log_info "Creating superuser (if not exists)..."
    
    # Create superuser job
    cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: django-createadmin-${VERSION//./}
  namespace: ${NAMESPACE}
spec:
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: createadmin
          image: ${REGISTRY}/jewelry-shop-django:${VERSION}
          command:
            - python
            - manage.py
            - shell
            - -c
            - |
              from apps.core.models import User
              if not User.objects.filter(username='platformadmin').exists():
                  User.objects.create_superuser(
                      username='platformadmin',
                      email='admin@${DOMAIN:-platform.local}',
                      password='${ADMIN_PASSWORD:-ChangeMe123!}',
                      role='PLATFORM_ADMIN'
                  )
                  print('✅ Superuser created')
              else:
                  print('ℹ️  Superuser already exists')
          envFrom:
            - configMapRef:
                name: django-config
            - secretRef:
                name: django-secrets
EOF
    
    kubectl wait --for=condition=complete job/django-createadmin-${VERSION//./} -n ${NAMESPACE} --timeout=120s
    
    log_success "Superuser setup completed"
}

deploy_application() {
    log_info "Deploying application..."
    
    # Update image tags in deployments
    cd "$PROJECT_ROOT/k8s"
    
    # Deploy Django
    kubectl apply -f django-deployment.yaml -n ${NAMESPACE}
    
    # Deploy Nginx
    kubectl apply -f nginx-deployment.yaml -n ${NAMESPACE}
    
    # Deploy Celery
    kubectl apply -f celery-deployment.yaml -n ${NAMESPACE}
    
    # Deploy monitoring
    kubectl apply -f prometheus/ -n ${NAMESPACE} || true
    kubectl apply -f grafana/ -n ${NAMESPACE} || true
    
    log_success "Application deployed"
}

apply_network_policies() {
    log_info "Applying network policies..."
    
    kubectl apply -f "$PROJECT_ROOT/k8s/network-policies.yaml" -n ${NAMESPACE} || true
    kubectl apply -f "$PROJECT_ROOT/k8s/network-policies-postgresql.yaml" -n ${NAMESPACE} || true
    
    log_success "Network policies applied"
}

wait_for_rollout() {
    log_info "Waiting for deployments to be ready..."
    
    kubectl rollout status deployment/django -n ${NAMESPACE} --timeout=600s
    kubectl rollout status deployment/nginx -n ${NAMESPACE} --timeout=300s
    kubectl rollout status deployment/celery-worker -n ${NAMESPACE} --timeout=300s || true
    
    log_success "All deployments ready"
}

run_health_checks() {
    log_info "Running health checks..."
    
    # Get Django pod
    DJANGO_POD=$(kubectl get pod -n ${NAMESPACE} -l component=django -o jsonpath='{.items[0].metadata.name}')
    
    # Check Django health
    if kubectl exec -n ${NAMESPACE} ${DJANGO_POD} -- curl -f http://localhost:8000/health/ > /dev/null 2>&1; then
        log_success "Django health check passed"
    else
        log_warning "Django health check failed (endpoint may not exist yet)"
    fi
    
    # Check database connectivity
    if kubectl exec -n ${NAMESPACE} ${DJANGO_POD} -- python manage.py check --database default > /dev/null 2>&1; then
        log_success "Database connectivity check passed"
    else
        log_error "Database connectivity check failed"
    fi
}

display_info() {
    echo ""
    echo "======================================================================"
    log_success "Deployment completed successfully!"
    echo "======================================================================"
    echo ""
    echo "Deployment Information:"
    echo "  Namespace: ${NAMESPACE}"
    echo "  Version: ${VERSION}"
    echo "  Registry: ${REGISTRY}"
    echo ""
    echo "Access Information:"
    echo "  - Get pods: kubectl get pods -n ${NAMESPACE}"
    echo "  - View logs: kubectl logs -f deployment/django -n ${NAMESPACE}"
    echo "  - Port forward: kubectl port-forward svc/nginx 8443:443 -n ${NAMESPACE}"
    echo ""
    echo "Next Steps:"
    echo "  1. Configure your domain DNS to point to your cluster IP"
    echo "  2. Set up SSL certificates (cert-manager + Let's Encrypt)"
    echo "  3. Update ADMIN_PASSWORD in secrets"
    echo "  4. Configure backups"
    echo "  5. Set up monitoring alerts"
    echo ""
}

rollback() {
    log_warning "Rolling back deployment..."
    
    kubectl rollout undo deployment/django -n ${NAMESPACE}
    kubectl rollout undo deployment/nginx -n ${NAMESPACE}
    kubectl rollout undo deployment/celery-worker -n ${NAMESPACE} || true
    
    log_info "Rollback initiated. Check status with: kubectl rollout status deployment/django -n ${NAMESPACE}"
}

# Main deployment flow
main() {
    local skip_build=false
    local skip_push=false
    local only_app=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-build)
                skip_build=true
                shift
                ;;
            --skip-push)
                skip_push=true
                shift
                ;;
            --only-app)
                only_app=true
                shift
                ;;
            --rollback)
                rollback
                exit 0
                ;;
            -h|--help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --skip-build    Skip Docker image building"
                echo "  --skip-push     Skip pushing images to registry"
                echo "  --only-app      Only deploy application (skip infrastructure)"
                echo "  --rollback      Rollback to previous deployment"
                echo "  -h, --help      Show this help message"
                echo ""
                echo "Environment Variables:"
                echo "  VERSION         Image version tag (default: v1.0.0)"
                echo "  REGISTRY        Docker registry URL (default: your-registry.com)"
                echo "  NAMESPACE       Kubernetes namespace (default: jewelry-shop)"
                echo "  DOMAIN          Application domain (default: platform.local)"
                echo "  ADMIN_PASSWORD  Initial admin password (default: ChangeMe123!)"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
    
    echo "======================================================================"
    echo "  🚀 Professional VPS Deployment Script"
    echo "======================================================================"
    echo ""
    
    check_prerequisites
    
    if [ "$skip_build" = false ]; then
        build_docker_images
    fi
    
    if [ "$skip_push" = false ]; then
        push_to_registry
    fi
    
    create_namespace
    apply_secrets
    apply_configmaps
    
    if [ "$only_app" = false ]; then
        apply_postgresql
        apply_redis
        run_migrations
        create_superuser
    fi
    
    deploy_application
    apply_network_policies
    wait_for_rollout
    run_health_checks
    display_info
}

# Trap errors and provide helpful message
trap 'log_error "Deployment failed at line $LINENO. Check logs above for details."; exit 1' ERR

# Run main function
main "$@"
