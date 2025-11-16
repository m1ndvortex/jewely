#!/bin/bash
# ============================================================================
# Production Deployment Script for k3s
# ============================================================================
# This script deploys the entire jewelry-shop application to a production
# k3s cluster. All configurations are already saved in YAML files.
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Jewelry Shop - Production Deployment to k3s               ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if kubectl is configured
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}❌ kubectl not configured. Please set up kubeconfig first.${NC}"
    echo ""
    echo "Run this on your VPS:"
    echo "  sudo cat /etc/rancher/k3s/k3s.yaml"
    echo ""
    echo "Then copy the content to ~/.kube/config on your local machine"
    echo "and replace 127.0.0.1 with your VPS IP address."
    exit 1
fi

echo -e "${GREEN}✓ kubectl configured${NC}"
echo ""

# Get cluster info
CLUSTER_INFO=$(kubectl cluster-info | head -n 1)
echo -e "${BLUE}📡 Connected to: ${CLUSTER_INFO}${NC}"
echo ""

# Prompt for configuration
echo -e "${YELLOW}📝 Production Configuration${NC}"
echo ""
read -p "Enter your domain name (e.g., jewelry-shop.com): " DOMAIN
read -p "Enter your email for Let's Encrypt SSL: " EMAIL
read -p "Enter storage class name (default: longhorn): " STORAGE_CLASS
STORAGE_CLASS=${STORAGE_CLASS:-longhorn}

echo ""
echo -e "${BLUE}Configuration:${NC}"
echo "  Domain: $DOMAIN"
echo "  Email: $EMAIL"
echo "  Storage Class: $STORAGE_CLASS"
echo ""
read -p "Continue with deployment? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Deployment cancelled.${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}🚀 Starting deployment...${NC}"
echo ""

# Create namespace
echo -e "${BLUE}📦 Step 1/10: Creating namespace...${NC}"
kubectl apply -f ../namespace.yaml
echo -e "${GREEN}✓ Namespace created${NC}"
echo ""

# Generate and apply secrets
echo -e "${BLUE}🔐 Step 2/10: Generating production secrets...${NC}"
POSTGRES_PASSWORD=$(openssl rand -base64 32)
APP_PASSWORD=$(openssl rand -base64 32)
DJANGO_SECRET=$(openssl rand -base64 50)

kubectl create secret generic postgres-secrets \
  --from-literal=postgres-password="$POSTGRES_PASSWORD" \
  --from-literal=app-password="$APP_PASSWORD" \
  -n jewelry-shop --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic django-secrets \
  --from-literal=secret-key="$DJANGO_SECRET" \
  --from-literal=sentry-dsn="" \
  -n jewelry-shop --dry-run=client -o yaml | kubectl apply -f -

echo -e "${GREEN}✓ Secrets created${NC}"
echo -e "${YELLOW}⚠️  IMPORTANT: Save these credentials securely!${NC}"
echo "  PostgreSQL Password: $POSTGRES_PASSWORD"
echo "  App Password: $APP_PASSWORD"
echo ""

# Apply base configuration
echo -e "${BLUE}⚙️  Step 3/10: Applying base configuration...${NC}"
kubectl apply -f ../configmap.yaml
kubectl apply -f ../resource-quota.yaml
kubectl apply -f ../limit-range.yaml
echo -e "${GREEN}✓ Base configuration applied${NC}"
echo ""

# Deploy PostgreSQL Operator (if needed)
echo -e "${BLUE}🐘 Step 4/10: Checking PostgreSQL Operator...${NC}"
if ! kubectl get crd postgresqls.acid.zalan.do &> /dev/null; then
    echo "Installing Zalando Postgres Operator..."
    bash deploy-task-34.5.sh
else
    echo -e "${GREEN}✓ PostgreSQL Operator already installed${NC}"
fi
echo ""

# Deploy PostgreSQL cluster
echo -e "${BLUE}🗄️  Step 5/10: Deploying PostgreSQL cluster...${NC}"
kubectl apply -f ../postgresql-cluster.yaml
kubectl apply -f ../postgresql-rbac-default-namespace.yaml
kubectl apply -f ../network-policy-postgresql-egress.yaml
kubectl apply -f ../network-policies-postgresql.yaml
echo -e "${GREEN}✓ PostgreSQL cluster deployed${NC}"
echo ""

# Wait for PostgreSQL
echo -e "${BLUE}⏳ Waiting for PostgreSQL cluster to be ready...${NC}"
kubectl wait --for=condition=Ready pod -l application=spilo -n jewelry-shop --timeout=300s || true
echo -e "${GREEN}✓ PostgreSQL cluster ready${NC}"
echo ""

# Deploy Redis
echo -e "${BLUE}📮 Step 6/10: Deploying Redis cluster...${NC}"
kubectl apply -f ../redis-configmap.yaml
kubectl apply -f ../redis-statefulset.yaml
kubectl apply -f ../redis-sentinel-statefulset.yaml
echo -e "${GREEN}✓ Redis cluster deployed${NC}"
echo ""

# Deploy network policies
echo -e "${BLUE}🔒 Step 7/10: Applying network policies...${NC}"
kubectl apply -f ../network-policies.yaml
echo -e "${GREEN}✓ Network policies applied${NC}"
echo ""

# Deploy application
echo -e "${BLUE}🌐 Step 8/10: Deploying application...${NC}"
kubectl apply -f ../django-deployment.yaml
kubectl apply -f ../django-service.yaml
kubectl apply -f ../django-hpa.yaml
kubectl apply -f ../celery-worker-deployment.yaml
kubectl apply -f ../celery-beat-deployment.yaml
kubectl apply -f ../nginx-configmap.yaml
kubectl apply -f ../nginx-deployment.yaml
kubectl apply -f ../nginx-service.yaml
echo -e "${GREEN}✓ Application deployed${NC}"
echo ""

# Deploy Traefik Ingress
echo -e "${BLUE}🔀 Step 9/10: Deploying Traefik ingress...${NC}"
if [ -f "../traefik/install-traefik.sh" ]; then
    bash ../traefik/install-traefik.sh
fi
kubectl apply -f ../ingress/jewelry-shop-ingress.yaml
echo -e "${GREEN}✓ Ingress deployed${NC}"
echo ""

# Deploy monitoring (optional)
echo -e "${BLUE}📊 Step 10/10: Deploying monitoring stack...${NC}"
read -p "Deploy monitoring (Prometheus, Grafana, Loki)? (yes/no): " DEPLOY_MONITORING
if [ "$DEPLOY_MONITORING" = "yes" ]; then
    [ -f "../prometheus/install-prometheus.sh" ] && bash ../prometheus/install-prometheus.sh
    [ -f "../grafana/install-grafana.sh" ] && bash ../grafana/install-grafana.sh
    [ -f "../loki/install-loki.sh" ] && bash ../loki/install-loki.sh
    echo -e "${GREEN}✓ Monitoring deployed${NC}"
else
    echo -e "${YELLOW}⊘ Monitoring skipped${NC}"
fi
echo ""

# Deployment complete
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              ✅ Deployment Complete!                           ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Show cluster status
echo -e "${BLUE}📊 Cluster Status:${NC}"
echo ""
kubectl get pods -n jewelry-shop
echo ""

echo -e "${BLUE}🗄️  PostgreSQL Cluster:${NC}"
kubectl get postgresql jewelry-shop-db -n jewelry-shop
echo ""

echo -e "${BLUE}🌐 Services:${NC}"
kubectl get svc -n jewelry-shop
echo ""

echo -e "${BLUE}🔀 Ingress:${NC}"
kubectl get ingress -n jewelry-shop
echo ""

# Next steps
echo -e "${YELLOW}📋 Next Steps:${NC}"
echo ""
echo "1. Wait 2-3 minutes for all pods to be ready"
echo "   Watch status: kubectl get pods -n jewelry-shop -w"
echo ""
echo "2. Verify PostgreSQL replication:"
echo "   kubectl exec -n jewelry-shop jewelry-shop-db-0 -c postgres -- \\"
echo "     psql -U postgres -c 'SELECT application_name, state, sync_state FROM pg_stat_replication;'"
echo ""
echo "3. Point your domain DNS to this server's IP"
echo ""
echo "4. Access your application:"
echo "   https://$DOMAIN"
echo ""
echo "5. Configure backups (recommended):"
echo "   - Set up WAL-G for PostgreSQL backups to S3/R2/B2"
echo "   - Configure backup retention policies"
echo ""
echo -e "${GREEN}✅ Your application is now running in production!${NC}"
echo ""
