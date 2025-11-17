#!/bin/bash
# VPS Resource Simulation Script
# Constrains k3d cluster to match actual VPS resources (4-6GB RAM, 2-3 CPU)

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

# Configuration
NAMESPACE="jewelry-shop"
VPS_RAM_GB=${1:-4}  # Default 4GB, can pass 5 or 6
VPS_CPU_CORES=${2:-2}  # Default 2 cores, can pass 3

print_header "VPS RESOURCE SIMULATION"
echo "Simulating VPS with:"
echo "  RAM: ${VPS_RAM_GB}GB"
echo "  CPU: ${VPS_CPU_CORES} cores"
echo ""

# Create resource-constrained deployment files
print_info "Creating VPS-constrained deployments..."

# Create temporary directory for VPS configs
VPS_DIR="/tmp/k8s-vps-sim"
mkdir -p "$VPS_DIR"

# ============================================================================
# Django Deployment (VPS-sized)
# ============================================================================
cat > "$VPS_DIR/django-deployment-vps.yaml" <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: django
  namespace: jewelry-shop
spec:
  replicas: 2  # Reduced from 3 for VPS
  selector:
    matchLabels:
      component: django
  template:
    metadata:
      labels:
        component: django
    spec:
      containers:
      - name: django
        image: jewelry-shop-django:v1.0.0-secure
        ports:
        - containerPort: 8000
        resources:
          requests:
            cpu: "250m"      # 0.25 cores
            memory: "256Mi"  # 256MB
          limits:
            cpu: "500m"      # 0.5 cores max
            memory: "512Mi"  # 512MB max
        envFrom:
        - configMapRef:
            name: app-config
        - secretRef:
            name: app-secrets
        livenessProbe:
          httpGet:
            path: /health/
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
EOF

# ============================================================================
# HPA for Django (VPS-sized)
# ============================================================================
cat > "$VPS_DIR/django-hpa-vps.yaml" <<'EOF'
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: django-hpa
  namespace: jewelry-shop
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: django
  minReplicas: 1  # Start with 1 to save resources
  maxReplicas: 3  # Max 3 for small VPS
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30  # Quick scale-up
      policies:
      - type: Pods
        value: 1
        periodSeconds: 60  # Add 1 pod per minute max
    scaleDown:
      stabilizationWindowSeconds: 300  # Wait 5min before scaling down
      policies:
      - type: Pods
        value: 1
        periodSeconds: 120  # Remove 1 pod every 2min
EOF

# ============================================================================
# Nginx Deployment (VPS-sized)
# ============================================================================
cat > "$VPS_DIR/nginx-deployment-vps.yaml" <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx
  namespace: jewelry-shop
spec:
  replicas: 1  # Single instance for VPS
  selector:
    matchLabels:
      component: nginx
  template:
    metadata:
      labels:
        component: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:1.25-alpine
        ports:
        - containerPort: 80
        resources:
          requests:
            cpu: "100m"
            memory: "64Mi"
          limits:
            cpu: "200m"
            memory: "128Mi"
EOF

# ============================================================================
# Resource Quota for Namespace
# ============================================================================
cat > "$VPS_DIR/resource-quota-vps.yaml" <<EOF
apiVersion: v1
kind: ResourceQuota
metadata:
  name: vps-quota
  namespace: jewelry-shop
spec:
  hard:
    requests.cpu: "${VPS_CPU_CORES}"
    requests.memory: "${VPS_RAM_GB}Gi"
    limits.cpu: "$((VPS_CPU_CORES * 2))"  # Allow burst to 2x
    limits.memory: "$((VPS_RAM_GB + 2))Gi"
    pods: "20"  # Max pods for small VPS
EOF

# ============================================================================
# LimitRange for Namespace
# ============================================================================
cat > "$VPS_DIR/limit-range-vps.yaml" <<'EOF'
apiVersion: v1
kind: LimitRange
metadata:
  name: vps-limits
  namespace: jewelry-shop
spec:
  limits:
  - max:
      cpu: "1000m"    # No single pod can use more than 1 core
      memory: "1Gi"   # No single pod can use more than 1GB
    min:
      cpu: "50m"
      memory: "32Mi"
    type: Container
  - max:
      cpu: "2000m"
      memory: "2Gi"
    type: Pod
EOF

# Apply VPS configurations
print_info "Applying VPS-constrained resources..."

kubectl apply -f "$VPS_DIR/resource-quota-vps.yaml"
kubectl apply -f "$VPS_DIR/limit-range-vps.yaml"

print_success "Resource quotas and limits applied"

# Show current resource allocation
print_header "CURRENT RESOURCE ALLOCATION"

kubectl describe quota vps-quota -n "$NAMESPACE" 2>/dev/null || print_info "Quota will show usage after pods are created"

echo ""
print_header "DEPLOYMENT OPTIONS"
echo "To apply VPS-sized deployments:"
echo ""
echo "  kubectl apply -f $VPS_DIR/django-deployment-vps.yaml"
echo "  kubectl apply -f $VPS_DIR/django-hpa-vps.yaml"
echo "  kubectl apply -f $VPS_DIR/nginx-deployment-vps.yaml"
echo ""
echo "Or restore original deployments:"
echo ""
echo "  kubectl apply -f k8s/django-deployment.yaml"
echo "  kubectl apply -f k8s/nginx-deployment.yaml"
echo ""

# Calculate expected resource usage
print_header "EXPECTED RESOURCE USAGE"

DJANGO_PODS=2
NGINX_PODS=1
POSTGRES_PODS=2
REDIS_PODS=2
CELERY_PODS=1

CPU_REQUEST=$(echo "scale=2; ($DJANGO_PODS * 0.25) + ($NGINX_PODS * 0.1) + ($POSTGRES_PODS * 0.5) + ($REDIS_PODS * 0.1) + ($CELERY_PODS * 0.2)" | bc)
MEM_REQUEST=$(echo "scale=0; ($DJANGO_PODS * 256) + ($NGINX_PODS * 64) + ($POSTGRES_PODS * 512) + ($REDIS_PODS * 128) + ($CELERY_PODS * 256)" | bc)
MEM_REQUEST_GB=$(echo "scale=2; $MEM_REQUEST / 1024" | bc)

echo "Minimum resources needed:"
echo "  CPU: ${CPU_REQUEST} cores (out of ${VPS_CPU_CORES} available)"
echo "  Memory: ${MEM_REQUEST_GB}GB (out of ${VPS_RAM_GB}GB available)"
echo ""

CPU_PERCENT=$(echo "scale=1; $CPU_REQUEST * 100 / $VPS_CPU_CORES" | bc)
MEM_PERCENT=$(echo "scale=1; $MEM_REQUEST_GB * 100 / $VPS_RAM_GB" | bc)

echo "Resource utilization:"
echo "  CPU: ${CPU_PERCENT}%"
echo "  Memory: ${MEM_PERCENT}%"
echo ""

if (( $(echo "$CPU_REQUEST > $VPS_CPU_CORES" | bc -l) )); then
    print_info "⚠️  WARNING: CPU requests exceed VPS capacity"
    echo "   Consider reducing replicas or CPU requests"
elif (( $(echo "$CPU_PERCENT > 80" | bc -l) )); then
    print_info "⚠️  WARNING: CPU utilization >80%, tight on resources"
else
    print_success "CPU resources sufficient"
fi

if (( $(echo "$MEM_REQUEST_GB > $VPS_RAM_GB" | bc -l) )); then
    print_info "⚠️  WARNING: Memory requests exceed VPS capacity"
    echo "   Consider reducing replicas or memory requests"
elif (( $(echo "$MEM_PERCENT > 80" | bc -l) )); then
    print_info "⚠️  WARNING: Memory utilization >80%, tight on resources"
else
    print_success "Memory resources sufficient"
fi

print_info "VPS simulation configured in: $VPS_DIR"
print_success "Ready for load testing!"
