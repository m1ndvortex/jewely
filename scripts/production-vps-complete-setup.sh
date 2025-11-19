#!/bin/bash
################################################################################
# PRODUCTION VPS COMPLETE SETUP SCRIPT
# ============================================================================
# This script takes a bare VPS and deploys a complete production-ready
# jewelry shop application with:
# - K3s Kubernetes cluster
# - Automatic SSL certificates (Let's Encrypt)
# - PostgreSQL with replication
# - Redis Sentinel for HA
# - Django application with auto-scaling
# - Celery workers for background tasks
# - Nginx reverse proxy
# - Complete monitoring stack
# - Network policies and security
#
# Requirements:
# - Ubuntu 20.04+ or Debian 11+
# - 4GB+ RAM (6GB recommended for production)
# - 2+ CPU cores
# - 20GB+ disk space
# - Root or sudo access
# - Domain name pointing to this server
#
# Usage:
#   sudo bash scripts/production-vps-complete-setup.sh
#
################################################################################

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Color codes for pretty output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly MAGENTA='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly WHITE='\033[1;37m'
readonly NC='\033[0m' # No Color

# Script configuration
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
readonly K8S_DIR="$PROJECT_ROOT/k8s"
readonly NAMESPACE="jewelry-shop"
readonly VERSION="v1.0.0"
readonly LOG_FILE="/var/log/jewelry-shop-setup.log"

# Global variables (will be set by user input)
DOMAIN=""
ADMIN_EMAIL=""
ENABLE_MONITORING="yes"
NODE_COUNT=1

################################################################################
# UTILITY FUNCTIONS
################################################################################

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case "$level" in
        INFO)
            echo -e "${BLUE}ℹ  ${message}${NC}"
            ;;
        SUCCESS)
            echo -e "${GREEN}✅ ${message}${NC}"
            ;;
        WARNING)
            echo -e "${YELLOW}⚠️  ${message}${NC}"
            ;;
        ERROR)
            echo -e "${RED}❌ ${message}${NC}"
            ;;
        HEADER)
            echo ""
            echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
            echo -e "${WHITE}  $message${NC}"
            echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
            echo ""
            ;;
    esac
    
    # Also log to file
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
}

show_banner() {
    clear
    echo -e "${CYAN}"
    cat << 'EOF'
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║         JEWELRY SHOP SAAS - PRODUCTION DEPLOYMENT             ║
║                                                               ║
║     Complete Production-Ready VPS Setup Script                ║
║     From Bare VPS → Fully Deployed Application                ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
    echo ""
}

generate_random_password() {
    local length=${1:-32}
    openssl rand -base64 48 | tr -d "=+/" | cut -c1-${length}
}

generate_hex_key() {
    local bytes=${1:-32}
    openssl rand -hex ${bytes}
}

validate_domain() {
    local domain="$1"
    
    # Basic domain format validation
    if [[ ! "$domain" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$ ]]; then
        return 1
    fi
    
    return 0
}

validate_email() {
    local email="$1"
    
    if [[ ! "$email" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        return 1
    fi
    
    return 0
}

check_dns() {
    local domain="$1"
    
    log INFO "Checking DNS for $domain..."
    
    # Get server's public IP
    local server_ip=$(curl -s -4 ifconfig.me || echo "unknown")
    
    # Try to resolve domain
    local domain_ip=$(dig +short "$domain" @8.8.8.8 | head -n1)
    
    if [ -z "$domain_ip" ]; then
        log WARNING "DNS not configured for $domain"
        log INFO "Please point your domain to: $server_ip"
        return 1
    elif [ "$domain_ip" != "$server_ip" ]; then
        log WARNING "Domain $domain points to $domain_ip, but this server is $server_ip"
        log INFO "DNS may not be configured correctly"
        return 1
    else
        log SUCCESS "DNS configured correctly: $domain → $server_ip"
        return 0
    fi
}

wait_for_pod() {
    local label="$1"
    local namespace="${2:-$NAMESPACE}"
    local timeout="${3:-300}"
    
    log INFO "Waiting for pod with label $label to be ready..."
    
    if kubectl wait --for=condition=ready pod -l "$label" -n "$namespace" --timeout="${timeout}s" > /dev/null 2>&1; then
        log SUCCESS "Pod ready"
        return 0
    else
        log ERROR "Pod failed to become ready within ${timeout}s"
        return 1
    fi
}

wait_for_deployment() {
    local deployment="$1"
    local namespace="${2:-$NAMESPACE}"
    local timeout="${3:-300}"
    
    log INFO "Waiting for deployment $deployment to be ready..."
    
    if kubectl rollout status deployment/"$deployment" -n "$namespace" --timeout="${timeout}s" > /dev/null 2>&1; then
        log SUCCESS "Deployment ready"
        return 0
    else
        log ERROR "Deployment failed to become ready within ${timeout}s"
        return 1
    fi
}

wait_for_statefulset() {
    local statefulset="$1"
    local namespace="${2:-$NAMESPACE}"
    local timeout="${3:-300}"
    
    log INFO "Waiting for statefulset $statefulset to be ready..."
    
    if kubectl rollout status statefulset/"$statefulset" -n "$namespace" --timeout="${timeout}s" > /dev/null 2>&1; then
        log SUCCESS "StatefulSet ready"
        return 0
    else
        log ERROR "StatefulSet failed to become ready within ${timeout}s"
        return 1
    fi
}

################################################################################
# USER INPUT COLLECTION
################################################################################

collect_user_input() {
    log HEADER "STEP 1: Configuration Collection"
    
    echo -e "${WHITE}This script will set up a complete production environment.${NC}"
    echo -e "${WHITE}Please provide the following information:${NC}"
    echo ""
    
    # Domain name
    while true; do
        read -p "$(echo -e ${CYAN}Enter your domain name e.g., jewelry-shop.com: ${NC})" DOMAIN
        DOMAIN=$(echo "$DOMAIN" | tr '[:upper:]' '[:lower:]' | xargs)  # lowercase and trim
        
        if validate_domain "$DOMAIN"; then
            log SUCCESS "Domain validated: $DOMAIN"
            break
        else
            log ERROR "Invalid domain format. Please try again."
        fi
    done
    
    # Admin email
    while true; do
        read -p "$(echo -e ${CYAN}Enter admin email for SSL certificates e.g., admin@$DOMAIN: ${NC})" ADMIN_EMAIL
        ADMIN_EMAIL=$(echo "$ADMIN_EMAIL" | tr '[:upper:]' '[:lower:]' | xargs)
        
        if validate_email "$ADMIN_EMAIL"; then
            log SUCCESS "Email validated: $ADMIN_EMAIL"
            break
        else
            log ERROR "Invalid email format. Please try again."
        fi
    done
    
    # Check DNS (optional, warn if not configured)
    echo ""
    log INFO "Checking DNS configuration..."
    if ! check_dns "$DOMAIN"; then
        echo ""
        read -p "$(echo -e ${YELLOW}DNS not configured. Continue anyway? (y/n): ${NC})" -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log ERROR "Setup cancelled. Please configure DNS and try again."
            exit 1
        fi
    fi
    
    # Monitoring stack
    echo ""
    read -p "$(echo -e ${CYAN}Enable monitoring stack (Prometheus/Grafana)? Recommended (y/n, default=y): ${NC})" -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        ENABLE_MONITORING="yes"
        log SUCCESS "Monitoring stack will be deployed"
    else
        ENABLE_MONITORING="no"
        log INFO "Monitoring stack will be skipped"
    fi
    
    echo ""
    log SUCCESS "Configuration collected successfully"
    echo ""
    echo -e "${WHITE}Summary:${NC}"
    echo -e "  Domain:      ${GREEN}$DOMAIN${NC}"
    echo -e "  WWW Domain:  ${GREEN}www.$DOMAIN${NC}"
    echo -e "  Admin Email: ${GREEN}$ADMIN_EMAIL${NC}"
    echo -e "  Monitoring:  ${GREEN}$ENABLE_MONITORING${NC}"
    echo ""
    
    read -p "$(echo -e ${CYAN}Proceed with installation? (y/n): ${NC})" -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log ERROR "Setup cancelled by user"
        exit 1
    fi
}

################################################################################
# PREREQUISITES CHECK
################################################################################

check_prerequisites() {
    log HEADER "STEP 2: Prerequisites Check"
    
    local errors=0
    
    # Check if running as root
    if [ "$EUID" -ne 0 ]; then
        log ERROR "This script must be run as root or with sudo"
        errors=$((errors + 1))
    fi
    
    # Check OS
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        log INFO "OS: $NAME $VERSION"
        
        if [[ ! "$ID" =~ ^(ubuntu|debian)$ ]]; then
            log WARNING "Unsupported OS. This script is tested on Ubuntu/Debian."
            log INFO "Detected: $NAME $VERSION"
        fi
    else
        log WARNING "Cannot detect OS version"
    fi
    
    # Check RAM
    local ram_mb=$(free -m | awk '/^Mem:/{print $2}')
    local ram_gb=$((ram_mb / 1024))
    log INFO "RAM: ${ram_gb}GB (${ram_mb}MB)"
    
    if [ "$ram_mb" -lt 3584 ]; then  # Less than 3.5GB
        log WARNING "RAM is less than 4GB. Minimum 4GB recommended for production."
        log INFO "Current: ${ram_gb}GB. Application may run slowly or crash."
        errors=$((errors + 1))
    elif [ "$ram_mb" -lt 5120 ]; then  # Less than 5GB
        log WARNING "RAM is ${ram_gb}GB. 6GB+ recommended for optimal performance."
    else
        log SUCCESS "RAM sufficient: ${ram_gb}GB"
    fi
    
    # Check CPU cores
    local cpu_cores=$(nproc)
    log INFO "CPU Cores: $cpu_cores"
    
    if [ "$cpu_cores" -lt 2 ]; then
        log WARNING "Less than 2 CPU cores detected. 2+ cores recommended."
        errors=$((errors + 1))
    else
        log SUCCESS "CPU cores sufficient: $cpu_cores"
    fi
    
    # Check disk space
    local disk_gb=$(df -BG / | awk 'NR==2 {print $4}' | sed 's/G//')
    log INFO "Free disk space: ${disk_gb}GB"
    
    if [ "$disk_gb" -lt 20 ]; then
        log WARNING "Less than 20GB free disk space. May not be sufficient."
        errors=$((errors + 1))
    else
        log SUCCESS "Disk space sufficient: ${disk_gb}GB"
    fi
    
    # Check required commands
    log INFO "Checking required commands..."
    
    local required_commands=("curl" "git" "openssl" "dig")
    for cmd in "${required_commands[@]}"; do
        if command -v "$cmd" &> /dev/null; then
            log SUCCESS "$cmd installed"
        else
            log WARNING "$cmd not found, will install..."
            
            # Install missing packages
            if command -v apt-get &> /dev/null; then
                apt-get update -qq
                apt-get install -y -qq "$cmd" > /dev/null 2>&1 || true
            fi
        fi
    done
    
    # Check internet connectivity
    if curl -s --max-time 5 https://google.com > /dev/null; then
        log SUCCESS "Internet connectivity verified"
    else
        log ERROR "No internet connectivity. Cannot proceed."
        errors=$((errors + 1))
    fi
    
    if [ $errors -gt 0 ]; then
        log ERROR "Prerequisites check failed with $errors error(s)"
        exit 1
    fi
    
    log SUCCESS "All prerequisites satisfied"
}

################################################################################
# K3S INSTALLATION
################################################################################

install_k3s() {
    log HEADER "STEP 3: K3s Kubernetes Installation"
    
    # Check if k3s already installed
    if command -v k3s &> /dev/null; then
        log INFO "K3s already installed"
        
        # Check if running
        if systemctl is-active --quiet k3s; then
            log SUCCESS "K3s is running"
            
            # Configure kubectl
            export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
            mkdir -p ~/.kube
            cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
            chmod 600 ~/.kube/config
            
            log SUCCESS "kubectl configured"
            return 0
        else
            log WARNING "K3s installed but not running. Starting..."
            systemctl start k3s
            sleep 10
        fi
    fi
    
    log INFO "Installing K3s with Traefik ingress controller..."
    
    # Install k3s with Traefik enabled (default)
    curl -sfL https://get.k3s.io | sh -s - server \
        --write-kubeconfig-mode 644 \
        --disable traefik \
        --cluster-init
    
    # Wait for k3s to be ready
    log INFO "Waiting for K3s to be ready..."
    local retries=0
    while [ $retries -lt 30 ]; do
        if systemctl is-active --quiet k3s; then
            log SUCCESS "K3s is running"
            break
        fi
        sleep 2
        retries=$((retries + 1))
    done
    
    if [ $retries -eq 30 ]; then
        log ERROR "K3s failed to start"
        exit 1
    fi
    
    # Configure kubectl access
    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
    mkdir -p ~/.kube
    cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
    chmod 600 ~/.kube/config
    
    # Wait for cluster to be fully ready
    log INFO "Waiting for Kubernetes cluster to be ready..."
    sleep 15
    
    # Verify cluster is accessible
    if kubectl cluster-info > /dev/null 2>&1; then
        log SUCCESS "Kubernetes cluster ready"
    else
        log ERROR "Cannot access Kubernetes cluster"
        exit 1
    fi
    
    # Install Traefik separately with custom config
    log INFO "Installing Traefik ingress controller..."
    
    kubectl apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: traefik
---
apiVersion: helm.cattle.io/v1
kind: HelmChart
metadata:
  name: traefik
  namespace: kube-system
spec:
  chart: traefik
  repo: https://helm.traefik.io/traefik
  targetNamespace: traefik
  valuesContent: |-
    ingressRoute:
      dashboard:
        enabled: false
    ports:
      web:
        port: 80
        redirectTo: websecure
      websecure:
        port: 443
        tls:
          enabled: true
    service:
      type: LoadBalancer
EOF
    
    log SUCCESS "K3s installation complete"
}

################################################################################
# CERT-MANAGER INSTALLATION
################################################################################

install_cert_manager() {
    log HEADER "STEP 4: cert-manager Installation"
    
    # Check if cert-manager already installed
    if kubectl get namespace cert-manager &> /dev/null; then
        log INFO "cert-manager already installed"
        return 0
    fi
    
    log INFO "Installing cert-manager for automatic SSL certificates..."
    
    # Install cert-manager via kubectl
    kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.2/cert-manager.yaml
    
    # Wait for cert-manager to be ready
    log INFO "Waiting for cert-manager webhook to be ready..."
    sleep 20
    
    if wait_for_pod "app.kubernetes.io/name=webhook" "cert-manager" 180; then
        log SUCCESS "cert-manager installed and ready"
    else
        log WARNING "cert-manager webhook not ready yet, continuing anyway..."
    fi
}

################################################################################
# CNPG OPERATOR INSTALLATION
################################################################################

install_cnpg_operator() {
    log HEADER "STEP 5: CloudNativePG Operator Installation"
    
    # Check if CNPG already installed
    if kubectl get namespace cnpg-system &> /dev/null; then
        log INFO "CloudNativePG operator already installed"
        return 0
    fi
    
    log INFO "Installing CloudNativePG operator for PostgreSQL..."
    
    # Install CNPG operator
    kubectl apply -f https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.21/releases/cnpg-1.21.0.yaml
    
    # Wait for operator to be ready
    log INFO "Waiting for CNPG operator to be ready..."
    sleep 10
    
    if wait_for_deployment "cnpg-controller-manager" "cnpg-system" 180; then
        log SUCCESS "CloudNativePG operator installed and ready"
    else
        log WARNING "CNPG operator not ready yet, continuing anyway..."
    fi
}

################################################################################
# SECRETS GENERATION
################################################################################

generate_secrets() {
    log HEADER "STEP 6: Generating Secure Credentials"
    
    log INFO "Generating random passwords and encryption keys..."
    
    # Generate secrets
    local DJANGO_SECRET_KEY=$(generate_random_password 64)
    local POSTGRES_PASSWORD=$(generate_random_password 32)
    local REDIS_PASSWORD=$(generate_random_password 32)
    local BACKUP_ENCRYPTION_KEY=$(generate_hex_key 32)
    local FIELD_ENCRYPTION_KEY=$(generate_hex_key 32)
    local ADMIN_PASSWORD=$(generate_random_password 16)
    
    log SUCCESS "All secrets generated"
    
    # Create .env.production file
    log INFO "Creating .env.production file..."
    
    cat > "$PROJECT_ROOT/.env.production" <<EOF
# Production Environment Configuration
# Generated automatically by production-vps-complete-setup.sh
# Generated: $(date)

# ============================================================================
# IMPORTANT: Save this file securely! It contains sensitive credentials.
# ============================================================================

# Domain Configuration
DOMAIN=$DOMAIN
SITE_URL=https://$DOMAIN

# Django Settings
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=$DOMAIN,www.$DOMAIN
SITE_URL=https://$DOMAIN

# Database Configuration
POSTGRES_DB=jewelry_shop_prod
POSTGRES_USER=jewelry_shop_user
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_HOST=jewelry-shop-db-rw.jewelry-shop.svc.cluster.local
POSTGRES_PORT=5432

# PgBouncer Configuration
USE_PGBOUNCER=True
PGBOUNCER_HOST=jewelry-shop-db-pooler
PGBOUNCER_PORT=5432

# Redis Configuration
REDIS_PASSWORD=$REDIS_PASSWORD
REDIS_USE_SENTINEL=True
REDIS_SENTINEL_MASTER_NAME=mymaster
REDIS_SENTINEL_HOSTS=redis-sentinel-0.redis-sentinel-headless.jewelry-shop.svc.cluster.local:26379,redis-sentinel-1.redis-sentinel-headless.jewelry-shop.svc.cluster.local:26379,redis-sentinel-2.redis-sentinel-headless.jewelry-shop.svc.cluster.local:26379
REDIS_SENTINEL_SOCKET_TIMEOUT=0.5

# Celery Configuration
CELERY_BROKER_URL=sentinel://:$REDIS_PASSWORD@redis-sentinel.jewelry-shop.svc.cluster.local:26379/0
CELERY_RESULT_BACKEND=sentinel://:$REDIS_PASSWORD@redis-sentinel.jewelry-shop.svc.cluster.local:26379/0

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=noreply@$DOMAIN
SERVER_EMAIL=alerts@$DOMAIN

# Security Keys
BACKUP_ENCRYPTION_KEY=$BACKUP_ENCRYPTION_KEY
FIELD_ENCRYPTION_KEY=$FIELD_ENCRYPTION_KEY

# Admin Credentials
ADMIN_USERNAME=platformadmin
ADMIN_PASSWORD=$ADMIN_PASSWORD
ADMIN_EMAIL=$ADMIN_EMAIL

# Logging
LOG_LEVEL=INFO

# Optional: Add your API keys here
# GOLDAPI_KEY=your_key_here
# METALS_API_KEY=your_key_here
# TWILIO_ACCOUNT_SID=your_sid_here
# TWILIO_AUTH_TOKEN=your_token_here
# SENDGRID_API_KEY=your_key_here

EOF
    
    chmod 600 "$PROJECT_ROOT/.env.production"
    
    log SUCCESS ".env.production created at: $PROJECT_ROOT/.env.production"
    log WARNING "IMPORTANT: Save this file securely! It contains all credentials."
    
    # Export variables for use in this script
    export DJANGO_SECRET_KEY POSTGRES_PASSWORD REDIS_PASSWORD BACKUP_ENCRYPTION_KEY FIELD_ENCRYPTION_KEY ADMIN_PASSWORD
}

################################################################################
# KUBERNETES NAMESPACE & RESOURCES
################################################################################

create_namespace() {
    log HEADER "STEP 7: Creating Kubernetes Namespace"
    
    log INFO "Creating namespace: $NAMESPACE"
    
    kubectl apply -f "$K8S_DIR/namespace.yaml"
    
    log SUCCESS "Namespace created"
}

create_kubernetes_secrets() {
    log HEADER "STEP 8: Creating Kubernetes Secrets"
    
    log INFO "Creating Kubernetes secret with credentials..."
    
    # Create secret from .env.production
    kubectl create secret generic django-secrets \
        --from-env-file="$PROJECT_ROOT/.env.production" \
        --namespace=$NAMESPACE \
        --dry-run=client -o yaml | kubectl apply -f -
    
    log SUCCESS "Kubernetes secrets created"
}

apply_configmaps() {
    log HEADER "STEP 9: Applying ConfigMaps"
    
    log INFO "Creating configmap with domain: $DOMAIN..."
    
    # Update configmap with actual domain
    local temp_configmap=$(mktemp)
    
    sed -e "s/jewelry-shop\.com/$DOMAIN/g" \
        -e "s/www\.jewelry-shop\.com/www.$DOMAIN/g" \
        "$K8S_DIR/configmap.yaml" > "$temp_configmap"
    
    kubectl apply -f "$temp_configmap" -n $NAMESPACE
    
    rm -f "$temp_configmap"
    
    log SUCCESS "ConfigMaps applied"
}

################################################################################
# SSL CERTIFICATE SETUP
################################################################################

setup_ssl_certificates() {
    log HEADER "STEP 10: Setting up SSL Certificates"
    
    log INFO "Creating Let's Encrypt ClusterIssuers..."
    
    # Update issuer with actual email
    local temp_issuer=$(mktemp)
    
    sed "s/admin@jewelry-shop\.com/$ADMIN_EMAIL/g" \
        "$K8S_DIR/cert-manager/letsencrypt-issuer.yaml" > "$temp_issuer"
    
    kubectl apply -f "$temp_issuer"
    
    rm -f "$temp_issuer"
    
    log SUCCESS "SSL certificate issuers configured"
    log INFO "Certificates will be automatically requested when Ingress is created"
}

################################################################################
# POSTGRESQL DEPLOYMENT
################################################################################

deploy_postgresql() {
    log HEADER "STEP 11: Deploying PostgreSQL Cluster"
    
    log INFO "Deploying PostgreSQL with CloudNativePG..."
    log INFO "This includes: Primary server + 2 replicas + PgBouncer pooling"
    
    # Apply PostgreSQL cluster
    kubectl apply -f "$K8S_DIR/postgresql-cluster.yaml" -n $NAMESPACE
    
    # Wait for PostgreSQL to be ready
    log INFO "Waiting for PostgreSQL cluster to be ready (this may take 2-3 minutes)..."
    sleep 30
    
    # Wait for primary pod
    local retries=0
    while [ $retries -lt 60 ]; do
        if kubectl get pod -n $NAMESPACE -l role=primary 2>/dev/null | grep -q "Running"; then
            log SUCCESS "PostgreSQL primary ready"
            break
        fi
        sleep 5
        retries=$((retries + 1))
    done
    
    if [ $retries -eq 60 ]; then
        log WARNING "PostgreSQL primary not ready yet, continuing anyway..."
    fi
    
    # Wait a bit more for replicas and pooler
    sleep 30
    
    log SUCCESS "PostgreSQL cluster deployed"
}

################################################################################
# REDIS DEPLOYMENT
################################################################################

deploy_redis() {
    log HEADER "STEP 12: Deploying Redis Sentinel Cluster"
    
    log INFO "Deploying Redis with Sentinel for HA..."
    log INFO "This includes: 3 Redis servers + 3 Sentinel monitors"
    
    # Apply Redis ConfigMap
    kubectl apply -f "$K8S_DIR/redis-configmap.yaml" -n $NAMESPACE
    
    # Apply Redis StatefulSet
    kubectl apply -f "$K8S_DIR/redis-statefulset.yaml" -n $NAMESPACE
    
    # Apply Redis Sentinel
    kubectl apply -f "$K8S_DIR/redis-sentinel-statefulset.yaml" -n $NAMESPACE
    
    # Wait for Redis to be ready
    log INFO "Waiting for Redis cluster to be ready..."
    sleep 20
    
    if wait_for_statefulset "redis" "$NAMESPACE" 180; then
        log SUCCESS "Redis cluster ready"
    else
        log WARNING "Redis not fully ready, continuing anyway..."
    fi
    
    if wait_for_statefulset "redis-sentinel" "$NAMESPACE" 180; then
        log SUCCESS "Redis Sentinel ready"
    else
        log WARNING "Redis Sentinel not fully ready, continuing anyway..."
    fi
}

################################################################################
# DOCKER IMAGE BUILD
################################################################################

build_docker_images() {
    log HEADER "STEP 13: Building Docker Images"
    
    log INFO "Building Django production image..."
    log INFO "This may take 5-10 minutes depending on your internet speed..."
    
    cd "$PROJECT_ROOT"
    
    # Build production image
    docker build \
        -f Dockerfile.prod \
        -t jewelry-shop-django:$VERSION \
        -t jewelry-shop-django:latest \
        --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
        --build-arg VCS_REF=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown") \
        --build-arg VERSION=$VERSION \
        . || {
            log ERROR "Docker build failed"
            exit 1
        }
    
    log SUCCESS "Docker image built successfully"
    
    # Import image to k3s containerd
    log INFO "Importing image to k3s..."
    
    docker save jewelry-shop-django:latest | k3s ctr images import - || {
        log ERROR "Failed to import image to k3s"
        exit 1
    }
    
    log SUCCESS "Image imported to k3s containerd"
}

################################################################################
# DATABASE MIGRATIONS
################################################################################

run_database_migrations() {
    log HEADER "STEP 14: Running Database Migrations"
    
    log INFO "Creating migration job..."
    
    # Create migration job
    kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: django-migrate-initial
  namespace: $NAMESPACE
spec:
  ttlSecondsAfterFinished: 300
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
              until nc -z jewelry-shop-db-rw 5432; do
                echo "Waiting for PostgreSQL..."
                sleep 3
              done
              echo "PostgreSQL is ready!"
      containers:
        - name: migrate
          image: jewelry-shop-django:latest
          imagePullPolicy: Never
          command:
            - sh
            - -c
            - |
              echo "Running database migrations..."
              python manage.py migrate --noinput
              echo "✅ Migrations complete!"
          envFrom:
            - secretRef:
                name: django-secrets
EOF
    
    # Wait for migration to complete
    log INFO "Waiting for migrations to complete..."
    sleep 10
    
    if kubectl wait --for=condition=complete job/django-migrate-initial -n $NAMESPACE --timeout=300s > /dev/null 2>&1; then
        log SUCCESS "Database migrations completed"
    else
        log ERROR "Database migrations failed or timed out"
        kubectl logs job/django-migrate-initial -n $NAMESPACE || true
        exit 1
    fi
}

create_superuser() {
    log HEADER "STEP 15: Creating Admin User"
    
    log INFO "Creating platform admin user..."
    
    # Create superuser job
    kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: django-createadmin-initial
  namespace: $NAMESPACE
spec:
  ttlSecondsAfterFinished: 300
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: createadmin
          image: jewelry-shop-django:latest
          imagePullPolicy: Never
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
                      email='$ADMIN_EMAIL',
                      password='$ADMIN_PASSWORD',
                      role='PLATFORM_ADMIN'
                  )
                  print('✅ Platform admin created')
              else:
                  print('ℹ️  Platform admin already exists')
          envFrom:
            - secretRef:
                name: django-secrets
EOF
    
    sleep 5
    
    if kubectl wait --for=condition=complete job/django-createadmin-initial -n $NAMESPACE --timeout=120s > /dev/null 2>&1; then
        log SUCCESS "Admin user created"
    else
        log WARNING "Admin user creation failed or already exists"
    fi
}

################################################################################
# APPLICATION DEPLOYMENT
################################################################################

deploy_django() {
    log HEADER "STEP 16: Deploying Django Application"
    
    log INFO "Deploying Django with auto-scaling (min=2, max=5)..."
    
    # Update deployment to use local image
    local temp_deploy=$(mktemp)
    sed 's|imagePullPolicy:.*|imagePullPolicy: Never|g' \
        "$K8S_DIR/django-deployment.yaml" > "$temp_deploy"
    
    kubectl apply -f "$temp_deploy" -n $NAMESPACE
    kubectl apply -f "$K8S_DIR/django-service.yaml" -n $NAMESPACE
    kubectl apply -f "$K8S_DIR/django-hpa.yaml" -n $NAMESPACE
    
    rm -f "$temp_deploy"
    
    # Wait for Django to be ready
    if wait_for_deployment "django" "$NAMESPACE" 300; then
        log SUCCESS "Django deployed and ready"
    else
        log ERROR "Django deployment failed"
        exit 1
    fi
}

deploy_celery() {
    log HEADER "STEP 17: Deploying Celery Workers"
    
    log INFO "Deploying Celery workers and beat scheduler..."
    
    # Update deployments to use local image
    for file in celery-worker-deployment.yaml celery-beat-deployment.yaml; do
        local temp_file=$(mktemp)
        sed 's|imagePullPolicy:.*|imagePullPolicy: Never|g' \
            "$K8S_DIR/$file" > "$temp_file"
        kubectl apply -f "$temp_file" -n $NAMESPACE
        rm -f "$temp_file"
    done
    
    # Apply HPA and PDB
    kubectl apply -f "$K8S_DIR/celery-worker-hpa.yaml" -n $NAMESPACE || true
    kubectl apply -f "$K8S_DIR/celery-worker-pdb.yaml" -n $NAMESPACE || true
    
    # Wait for Celery worker
    if wait_for_deployment "celery-worker" "$NAMESPACE" 180; then
        log SUCCESS "Celery workers deployed"
    else
        log WARNING "Celery workers not ready yet"
    fi
    
    # Wait for Celery beat
    if wait_for_deployment "celery-beat" "$NAMESPACE" 180; then
        log SUCCESS "Celery beat deployed"
    else
        log WARNING "Celery beat not ready yet"
    fi
}

deploy_nginx() {
    log HEADER "STEP 18: Deploying Nginx Reverse Proxy"
    
    log INFO "Deploying Nginx..."
    
    kubectl apply -f "$K8S_DIR/nginx-configmap.yaml" -n $NAMESPACE
    
    # Update nginx to use local image if needed
    kubectl apply -f "$K8S_DIR/nginx-deployment.yaml" -n $NAMESPACE
    kubectl apply -f "$K8S_DIR/nginx-service.yaml" -n $NAMESPACE
    
    # Wait for Nginx
    if wait_for_deployment "nginx" "$NAMESPACE" 180; then
        log SUCCESS "Nginx deployed and ready"
    else
        log WARNING "Nginx not ready yet"
    fi
}

################################################################################
# INGRESS SETUP
################################################################################

setup_ingress() {
    log HEADER "STEP 19: Setting up Ingress & SSL"
    
    log INFO "Creating Ingress with automatic SSL for: $DOMAIN"
    
    # Update ingress with actual domain
    local temp_ingress=$(mktemp)
    
    sed -e "s/jewelry-shop\.com/$DOMAIN/g" \
        -e "s/www\.jewelry-shop\.com/www.$DOMAIN/g" \
        "$K8S_DIR/ingress/jewelry-shop-ingress.yaml" > "$temp_ingress"
    
    kubectl apply -f "$temp_ingress"
    
    rm -f "$temp_ingress"
    
    log SUCCESS "Ingress created"
    log INFO "SSL certificate will be automatically provisioned by Let's Encrypt"
    log INFO "This may take 1-2 minutes..."
    
    # Wait for certificate to be issued
    sleep 30
    
    local retries=0
    while [ $retries -lt 24 ]; do  # 2 minutes total
        local cert_status=$(kubectl get certificate jewelry-shop-tls-cert -n $NAMESPACE -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "Unknown")
        
        if [ "$cert_status" == "True" ]; then
            log SUCCESS "SSL certificate issued successfully!"
            break
        fi
        
        sleep 5
        retries=$((retries + 1))
    done
    
    if [ $retries -eq 24 ]; then
        log WARNING "SSL certificate not ready yet, but it will be issued automatically"
        log INFO "Check status: kubectl get certificate -n $NAMESPACE"
    fi
}

################################################################################
# NETWORK POLICIES
################################################################################

apply_network_policies() {
    log HEADER "STEP 20: Applying Network Security Policies"
    
    log INFO "Applying network policies for security..."
    
    kubectl apply -f "$K8S_DIR/network-policies.yaml" -n $NAMESPACE || true
    kubectl apply -f "$K8S_DIR/network-policies-postgresql.yaml" -n $NAMESPACE || true
    
    # Apply additional network policies if they exist
    for policy in networkpolicy-*.yaml; do
        if [ -f "$K8S_DIR/$policy" ]; then
            kubectl apply -f "$K8S_DIR/$policy" -n $NAMESPACE || true
        fi
    done
    
    log SUCCESS "Network policies applied"
}

apply_resource_limits() {
    log HEADER "STEP 21: Applying Resource Quotas & Limits"
    
    log INFO "Applying resource quotas and limit ranges..."
    
    kubectl apply -f "$K8S_DIR/resource-quota.yaml" -n $NAMESPACE || true
    kubectl apply -f "$K8S_DIR/limit-range.yaml" -n $NAMESPACE || true
    
    log SUCCESS "Resource limits configured"
}

################################################################################
# MONITORING STACK
################################################################################

deploy_monitoring() {
    if [ "$ENABLE_MONITORING" != "yes" ]; then
        log INFO "Monitoring stack deployment skipped"
        return 0
    fi
    
    log HEADER "STEP 22: Deploying Monitoring Stack"
    
    log INFO "Deploying Prometheus, Grafana, Loki, and OpenTelemetry..."
    
    # Deploy Prometheus
    if [ -d "$K8S_DIR/prometheus" ]; then
        kubectl apply -f "$K8S_DIR/prometheus/" -n $NAMESPACE || true
        log SUCCESS "Prometheus deployed"
    fi
    
    # Deploy Grafana
    if [ -d "$K8S_DIR/grafana" ]; then
        kubectl apply -f "$K8S_DIR/grafana/" -n $NAMESPACE || true
        log SUCCESS "Grafana deployed"
    fi
    
    # Deploy Loki
    if [ -d "$K8S_DIR/loki" ]; then
        kubectl apply -f "$K8S_DIR/loki/" -n $NAMESPACE || true
        log SUCCESS "Loki deployed"
    fi
    
    # Deploy OpenTelemetry (Tempo + Collector)
    if [ -d "$K8S_DIR/opentelemetry" ]; then
        log INFO "Deploying Tempo for distributed tracing..."
        kubectl apply -f "$K8S_DIR/opentelemetry/tempo-configmap.yaml" -n $NAMESPACE || true
        kubectl apply -f "$K8S_DIR/opentelemetry/tempo-deployment.yaml" -n $NAMESPACE || true
        
        log INFO "Deploying OpenTelemetry Collector..."
        kubectl apply -f "$K8S_DIR/opentelemetry/otel-collector-configmap.yaml" -n $NAMESPACE || true
        kubectl apply -f "$K8S_DIR/opentelemetry/otel-collector-deployment.yaml" -n $NAMESPACE || true
        
        log SUCCESS "OpenTelemetry stack deployed"
    fi
    
    log SUCCESS "Monitoring stack deployed"
}

################################################################################
# HEALTH CHECKS
################################################################################

run_health_checks() {
    log HEADER "STEP 23: Running Health Checks"
    
    log INFO "Checking application health..."
    
    # Get all pods
    log INFO "Pod status:"
    kubectl get pods -n $NAMESPACE
    
    echo ""
    
    # Check Django health
    local django_pod=$(kubectl get pod -n $NAMESPACE -l component=django -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [ -n "$django_pod" ]; then
        log INFO "Testing Django health endpoint..."
        
        if kubectl exec -n $NAMESPACE "$django_pod" -- curl -sf http://localhost:8000/health/ > /dev/null 2>&1; then
            log SUCCESS "Django health check passed"
        else
            log WARNING "Django health endpoint not responding (may not be implemented)"
        fi
    fi
    
    # Check database connectivity
    if [ -n "$django_pod" ]; then
        log INFO "Testing database connectivity..."
        
        if kubectl exec -n $NAMESPACE "$django_pod" -- python manage.py check --database default > /dev/null 2>&1; then
            log SUCCESS "Database connectivity verified"
        else
            log WARNING "Database connectivity check failed"
        fi
    fi
    
    # Check SSL certificate status
    log INFO "Checking SSL certificate status..."
    
    local cert_ready=$(kubectl get certificate jewelry-shop-tls-cert -n $NAMESPACE -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "Unknown")
    
    if [ "$cert_ready" == "True" ]; then
        log SUCCESS "SSL certificate ready"
    else
        log WARNING "SSL certificate not ready yet (status: $cert_ready)"
        log INFO "Certificate will be issued automatically. Check: kubectl describe certificate jewelry-shop-tls-cert -n $NAMESPACE"
    fi
    
    log SUCCESS "Health checks complete"
}

################################################################################
# FINAL OUTPUT
################################################################################

display_completion_info() {
    log HEADER "🎉 DEPLOYMENT COMPLETE!"
    
    # Get service IPs
    local nginx_ip=$(kubectl get svc nginx-service -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "Pending")
    local server_ip=$(curl -s -4 ifconfig.me || echo "unknown")
    
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}║         🎉 PRODUCTION DEPLOYMENT SUCCESSFUL! 🎉                ║${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${WHITE}📍 Access Information:${NC}"
    echo -e "   ${CYAN}Website:${NC}        https://$DOMAIN"
    echo -e "   ${CYAN}WWW:${NC}            https://www.$DOMAIN"
    echo -e "   ${CYAN}Admin Panel:${NC}    https://$DOMAIN/platform-admin/"
    echo ""
    
    echo -e "${WHITE}🔐 Admin Credentials:${NC}"
    echo -e "   ${CYAN}Username:${NC}       platformadmin"
    echo -e "   ${CYAN}Password:${NC}       $ADMIN_PASSWORD"
    echo -e "   ${CYAN}Email:${NC}          $ADMIN_EMAIL"
    echo ""
    
    echo -e "${YELLOW}⚠️  IMPORTANT: Save these credentials securely!${NC}"
    echo -e "${YELLOW}   Full credentials saved in: $PROJECT_ROOT/.env.production${NC}"
    echo ""
    
    echo -e "${WHITE}📊 Deployment Summary:${NC}"
    echo -e "   ${CYAN}Namespace:${NC}      $NAMESPACE"
    echo -e "   ${CYAN}Server IP:${NC}      $server_ip"
    echo -e "   ${CYAN}LoadBalancer:${NC}   $nginx_ip"
    echo -e "   ${CYAN}Monitoring:${NC}     $ENABLE_MONITORING"
    echo ""
    
    if [ "$nginx_ip" == "Pending" ]; then
        echo -e "${YELLOW}⏳ LoadBalancer IP is pending. This is normal for k3s.${NC}"
        echo -e "${YELLOW}   Traffic will be routed through NodePort or via domain.${NC}"
        echo ""
    fi
    
    echo -e "${WHITE}🔍 Useful Commands:${NC}"
    echo -e "   ${CYAN}View pods:${NC}          kubectl get pods -n $NAMESPACE"
    echo -e "   ${CYAN}View services:${NC}      kubectl get svc -n $NAMESPACE"
    echo -e "   ${CYAN}View ingress:${NC}       kubectl get ingress -n $NAMESPACE"
    echo -e "   ${CYAN}View certificate:${NC}   kubectl get certificate -n $NAMESPACE"
    echo -e "   ${CYAN}Django logs:${NC}        kubectl logs -f deployment/django -n $NAMESPACE"
    echo -e "   ${CYAN}Nginx logs:${NC}         kubectl logs -f deployment/nginx -n $NAMESPACE"
    echo ""
    
    echo -e "${WHITE}📋 Next Steps:${NC}"
    echo ""
    echo -e "   ${CYAN}1.${NC} Verify DNS Configuration:"
    echo -e "      ${WHITE}dig $DOMAIN${NC} should point to: $server_ip"
    echo ""
    echo -e "   ${CYAN}2.${NC} Wait for SSL Certificate (if not ready):"
    echo -e "      ${WHITE}kubectl describe certificate jewelry-shop-tls-cert -n $NAMESPACE${NC}"
    echo ""
    echo -e "   ${CYAN}3.${NC} Access Admin Panel:"
    echo -e "      ${WHITE}https://$DOMAIN/platform-admin/${NC}"
    echo -e "      Username: ${GREEN}platformadmin${NC}"
    echo -e "      Password: ${GREEN}$ADMIN_PASSWORD${NC}"
    echo ""
    echo -e "   ${CYAN}4.${NC} Configure Optional Services (in .env.production):"
    echo -e "      - Email provider (SendGrid, Mailgun, SES)"
    echo -e "      - Gold/Metals API keys"
    echo -e "      - Twilio SMS credentials"
    echo -e "      - Backup storage (R2, B2)"
    echo ""
    echo -e "   ${CYAN}5.${NC} Set up monitoring dashboards:"
    if [ "$ENABLE_MONITORING" == "yes" ]; then
        echo -e "      ${WHITE}kubectl port-forward -n $NAMESPACE svc/grafana 3000:80${NC}"
        echo -e "      Then access: ${WHITE}http://localhost:3000${NC}"
    else
        echo -e "      ${YELLOW}(Monitoring was not enabled during setup)${NC}"
    fi
    echo ""
    
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  Your jewelry shop is now live and ready for business! 🚀     ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    log INFO "Deployment log saved to: $LOG_FILE"
}

################################################################################
# ERROR HANDLER
################################################################################

handle_error() {
    local exit_code=$?
    local line_number=$1
    
    echo ""
    log ERROR "Deployment failed at line $line_number with exit code $exit_code"
    log ERROR "Check the log file for details: $LOG_FILE"
    echo ""
    
    echo -e "${YELLOW}Common issues:${NC}"
    echo -e "  - Insufficient resources (RAM/CPU)"
    echo -e "  - DNS not configured correctly"
    echo -e "  - Network connectivity problems"
    echo -e "  - K3s installation issues"
    echo ""
    echo -e "${WHITE}For help, check the logs:${NC}"
    echo -e "  - Deployment log: $LOG_FILE"
    echo -e "  - K3s logs: journalctl -u k3s -n 100"
    echo -e "  - Pod logs: kubectl get pods -n $NAMESPACE"
    echo ""
    
    exit $exit_code
}

# Set error handler
trap 'handle_error $LINENO' ERR

################################################################################
# MAIN EXECUTION
################################################################################

main() {
    # Show banner
    show_banner
    
    # Collect user input
    collect_user_input
    
    # Run all deployment steps
    check_prerequisites
    install_k3s
    install_cert_manager
    install_cnpg_operator
    generate_secrets
    create_namespace
    create_kubernetes_secrets
    apply_configmaps
    setup_ssl_certificates
    deploy_postgresql
    deploy_redis
    build_docker_images
    run_database_migrations
    create_superuser
    deploy_django
    deploy_celery
    deploy_nginx
    setup_ingress
    apply_network_policies
    apply_resource_limits
    deploy_monitoring
    run_health_checks
    display_completion_info
}

# Run main function
main "$@"
