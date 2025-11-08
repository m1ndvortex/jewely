#!/bin/bash
# ============================================================================
# Kubernetes Manifests Test Setup
# ============================================================================
# This script tests the Kubernetes manifests in a local minikube cluster
# ============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if minikube is running
log_info "Checking minikube status..."
if ! minikube status &> /dev/null; then
    log_error "Minikube is not running. Please start it with: minikube start"
    exit 1
fi
log_success "Minikube is running"

# Build a simple test image
log_info "Building test Docker image..."
cat > /tmp/Dockerfile.test << 'EOF'
FROM python:3.11-slim
WORKDIR /app
RUN pip install django gunicorn
RUN django-admin startproject testproject .
RUN echo "from django.http import JsonResponse; from django.urls import path; def health(request): return JsonResponse({'status': 'ok'}); urlpatterns = [path('health/', health)]" > testproject/urls.py
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "testproject.wsgi:application"]
EOF

docker build -f /tmp/Dockerfile.test -t jewelry-shop:test /tmp/
log_success "Test image built"

# Load image into minikube
log_info "Loading image into minikube..."
minikube image load jewelry-shop:test
log_success "Image loaded into minikube"

# Create namespace
log_info "Creating namespace..."
kubectl apply -f ../namespace.yaml
log_success "Namespace created"

# Create test ConfigMaps
log_info "Creating test ConfigMaps..."
kubectl create configmap django-config \
  --from-literal=DJANGO_SETTINGS_MODULE=testproject.settings \
  --from-literal=ENVIRONMENT=test \
  --namespace=jewelry-shop \
  --dry-run=client -o yaml | kubectl apply -f -

# Create minimal nginx config
cat > /tmp/nginx.conf << 'EOF'
events {
    worker_connections 1024;
}
http {
    server {
        listen 80;
        location /health/ {
            return 200 "OK";
        }
    }
}
EOF

kubectl create configmap nginx-config \
  --from-file=nginx.conf=/tmp/nginx.conf \
  --namespace=jewelry-shop \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create configmap nginx-conf-d \
  --from-literal=default.conf="server { listen 80; location / { return 200 'OK'; } }" \
  --namespace=jewelry-shop \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create configmap nginx-snippets \
  --from-literal=test.conf="# test" \
  --namespace=jewelry-shop \
  --dry-run=client -o yaml | kubectl apply -f -

log_success "ConfigMaps created"

# Create test Secrets
log_info "Creating test Secrets..."
kubectl create secret generic django-secrets \
  --from-literal=SECRET_KEY=test-secret-key-for-testing-only \
  --from-literal=DATABASE_URL=sqlite:///db.sqlite3 \
  --from-literal=REDIS_URL=redis://localhost:6379/0 \
  --namespace=jewelry-shop \
  --dry-run=client -o yaml | kubectl apply -f -

log_success "Secrets created"

log_success "Test setup complete!"
echo ""
log_info "You can now deploy the manifests with:"
echo "  kubectl apply -f ../persistent-volumes.yaml"
echo "  kubectl apply -f ../django-deployment.yaml"
echo "  kubectl apply -f ../django-service.yaml"
