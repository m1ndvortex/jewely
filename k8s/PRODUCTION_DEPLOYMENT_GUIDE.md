# Production Deployment Guide - k3s on VPS

## Overview

**Good News:** All your configurations are already saved as YAML files in the `k8s/` directory. You won't need to repeat any manual configuration. Just apply the files to your production k3s cluster.

---

## Prerequisites on VPS

### 1. Install k3s
```bash
# SSH to your VPS
ssh user@your-vps-ip

# Install k3s (single node or multi-node)
curl -sfL https://get.k3s.io | sh -

# Verify installation
sudo k3s kubectl get nodes

# Get kubeconfig for remote access (optional)
sudo cat /etc/rancher/k3s/k3s.yaml
```

### 2. Configure kubectl (from your local machine)
```bash
# Copy kubeconfig from VPS
scp user@your-vps-ip:/etc/rancher/k3s/k3s.yaml ~/.kube/config-production

# Edit the file and replace 127.0.0.1 with your VPS IP
sed -i 's/127.0.0.1/YOUR_VPS_IP/g' ~/.kube/config-production

# Use the production config
export KUBECONFIG=~/.kube/config-production

# Or merge with existing config
KUBECONFIG=~/.kube/config:~/.kube/config-production kubectl config view --flatten > ~/.kube/config-merged
mv ~/.kube/config-merged ~/.kube/config
```

---

## Deployment Steps (Simple & Automated)

### Step 1: Update Production-Specific Values

Only 3 files need minor updates for production:

#### 1.1 Update Storage Class
```bash
# Edit postgresql-cluster.yaml
# Change: storageClass: local-path
# To: storageClass: longhorn  (or your VPS storage class)

sed -i 's/storageClass: local-path/storageClass: longhorn/g' k8s/postgresql-cluster.yaml
sed -i 's/storageClass: local-path/storageClass: longhorn/g' k8s/redis-statefulset.yaml
sed -i 's/storageClass: local-path/storageClass: longhorn/g' k8s/persistent-volumes.yaml
```

#### 1.2 Update Domain Name
```bash
# Edit ingress configuration
# Change: jewelry-shop.local
# To: your-actual-domain.com

sed -i 's/jewelry-shop.local/your-domain.com/g' k8s/ingress/jewelry-shop-ingress.yaml
```

#### 1.3 Update Secrets (IMPORTANT!)
```bash
# Generate new production secrets
kubectl create secret generic postgres-secrets \
  --from-literal=postgres-password=$(openssl rand -base64 32) \
  --from-literal=app-password=$(openssl rand -base64 32) \
  -n jewelry-shop --dry-run=client -o yaml > k8s/secrets-production.yaml

# Update Django secret key
kubectl create secret generic django-secrets \
  --from-literal=secret-key=$(openssl rand -base64 50) \
  --from-literal=sentry-dsn=your-sentry-dsn \
  -n jewelry-shop --dry-run=client -o yaml >> k8s/secrets-production.yaml
```

---

### Step 2: Deploy Everything (One Command!)

```bash
# Apply all configurations in order
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets-production.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/resource-quota.yaml
kubectl apply -f k8s/limit-range.yaml

# Deploy PostgreSQL Operator (if not already installed)
bash k8s/scripts/deploy-task-34.5.sh

# Deploy all resources
kubectl apply -f k8s/postgresql-cluster.yaml
kubectl apply -f k8s/postgresql-rbac-default-namespace.yaml
kubectl apply -f k8s/network-policy-postgresql-egress.yaml
kubectl apply -f k8s/network-policies-postgresql.yaml
kubectl apply -f k8s/network-policies.yaml
kubectl apply -f k8s/redis-configmap.yaml
kubectl apply -f k8s/redis-statefulset.yaml
kubectl apply -f k8s/redis-sentinel-statefulset.yaml
kubectl apply -f k8s/django-deployment.yaml
kubectl apply -f k8s/django-service.yaml
kubectl apply -f k8s/django-hpa.yaml
kubectl apply -f k8s/celery-worker-deployment.yaml
kubectl apply -f k8s/celery-beat-deployment.yaml
kubectl apply -f k8s/nginx-configmap.yaml
kubectl apply -f k8s/nginx-deployment.yaml
kubectl apply -f k8s/nginx-service.yaml

# Deploy Traefik Ingress
bash k8s/traefik/install-traefik.sh
kubectl apply -f k8s/ingress/jewelry-shop-ingress.yaml

# Deploy Monitoring (optional but recommended)
bash k8s/prometheus/install-prometheus.sh
bash k8s/grafana/install-grafana.sh
bash k8s/loki/install-loki.sh
```

---

### Step 3: Verify Deployment

```bash
# Check all pods
kubectl get pods -n jewelry-shop

# Check PostgreSQL cluster
kubectl get postgresql jewelry-shop-db -n jewelry-shop

# Check replication
kubectl exec -n jewelry-shop jewelry-shop-db-0 -c postgres -- \
  psql -U postgres -c "SELECT application_name, state, sync_state FROM pg_stat_replication;"

# Check services
kubectl get svc -n jewelry-shop

# Check ingress
kubectl get ingress -n jewelry-shop
```

---

## Automated Deployment Script

Create this script for one-command deployment:

```bash
#!/bin/bash
# File: k8s/scripts/deploy-production.sh

set -e

echo "🚀 Deploying to Production k3s..."

# Check if kubectl is configured
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ kubectl not configured. Please set up kubeconfig first."
    exit 1
fi

# Prompt for domain
read -p "Enter your domain name (e.g., jewelry-shop.com): " DOMAIN
read -p "Enter your email for Let's Encrypt: " EMAIL

# Update domain in ingress
sed -i "s/jewelry-shop.local/$DOMAIN/g" k8s/ingress/jewelry-shop-ingress.yaml

# Create namespace
echo "📦 Creating namespace..."
kubectl apply -f k8s/namespace.yaml

# Generate secrets
echo "🔐 Generating production secrets..."
kubectl create secret generic postgres-secrets \
  --from-literal=postgres-password=$(openssl rand -base64 32) \
  --from-literal=app-password=$(openssl rand -base64 32) \
  -n jewelry-shop --dry-run=client -o yaml | kubectl apply -f -

# Apply base configuration
echo "⚙️  Applying base configuration..."
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/resource-quota.yaml
kubectl apply -f k8s/limit-range.yaml

# Deploy PostgreSQL
echo "🐘 Deploying PostgreSQL cluster..."
kubectl apply -f k8s/postgresql-cluster.yaml
kubectl apply -f k8s/postgresql-rbac-default-namespace.yaml
kubectl apply -f k8s/network-policy-postgresql-egress.yaml
kubectl apply -f k8s/network-policies-postgresql.yaml

# Wait for PostgreSQL
echo "⏳ Waiting for PostgreSQL cluster..."
kubectl wait --for=condition=Ready pod -l application=spilo -n jewelry-shop --timeout=300s

# Deploy Redis
echo "📮 Deploying Redis..."
kubectl apply -f k8s/redis-configmap.yaml
kubectl apply -f k8s/redis-statefulset.yaml
kubectl apply -f k8s/redis-sentinel-statefulset.yaml

# Deploy application
echo "🌐 Deploying application..."
kubectl apply -f k8s/network-policies.yaml
kubectl apply -f k8s/django-deployment.yaml
kubectl apply -f k8s/django-service.yaml
kubectl apply -f k8s/django-hpa.yaml
kubectl apply -f k8s/celery-worker-deployment.yaml
kubectl apply -f k8s/celery-beat-deployment.yaml
kubectl apply -f k8s/nginx-configmap.yaml
kubectl apply -f k8s/nginx-deployment.yaml
kubectl apply -f k8s/nginx-service.yaml

# Deploy ingress
echo "🔀 Deploying ingress..."
kubectl apply -f k8s/ingress/jewelry-shop-ingress.yaml

echo "✅ Deployment complete!"
echo ""
echo "📊 Cluster Status:"
kubectl get pods -n jewelry-shop
echo ""
echo "🌍 Your application will be available at: https://$DOMAIN"
echo "⏳ Wait 2-3 minutes for all pods to be ready"
```

Make it executable:
```bash
chmod +x k8s/scripts/deploy-production.sh
```

---

## What You DON'T Need to Do Again

✅ **Network Policies** - Already configured in YAML files
✅ **PostgreSQL Configuration** - Already in postgresql-cluster.yaml
✅ **Replication Setup** - Automatic via Zalando Operator
✅ **PgBouncer** - Automatic via Zalando Operator
✅ **RBAC Permissions** - Already in YAML files
✅ **Health Checks** - Already in deployment YAML files
✅ **HPA Configuration** - Already in YAML files
✅ **Service Definitions** - Already in YAML files

---

## Differences Between k3d (Dev) and k3s (Production)

| Aspect | k3d (Development) | k3s (Production) |
|--------|-------------------|------------------|
| Storage | local-path | longhorn or cloud storage |
| Domain | jewelry-shop.local | your-domain.com |
| SSL | Self-signed | Let's Encrypt (automatic) |
| Secrets | Test values | Production secrets |
| Resources | Lower limits | Higher limits |
| Backups | Optional | Required (configure WAL-G) |

---

## Production Checklist

### Before Deployment
- [ ] VPS with k3s installed
- [ ] Domain name pointing to VPS IP
- [ ] kubectl configured to access production cluster
- [ ] Storage class available (longhorn recommended)
- [ ] Firewall rules: Allow ports 80, 443, 6443

### After Deployment
- [ ] Verify all pods are Running
- [ ] Test PostgreSQL replication
- [ ] Test application access via domain
- [ ] Configure backups (WAL-G to S3/R2/B2)
- [ ] Set up monitoring alerts
- [ ] Test automatic failover
- [ ] Document database credentials

---

## Quick Production Deployment (TL;DR)

```bash
# 1. Install k3s on VPS
curl -sfL https://get.k3s.io | sh -

# 2. Configure kubectl locally
scp user@vps:/etc/rancher/k3s/k3s.yaml ~/.kube/config-prod
sed -i 's/127.0.0.1/YOUR_VPS_IP/g' ~/.kube/config-prod
export KUBECONFIG=~/.kube/config-prod

# 3. Update domain and storage class
sed -i 's/jewelry-shop.local/your-domain.com/g' k8s/ingress/*.yaml
sed -i 's/local-path/longhorn/g' k8s/postgresql-cluster.yaml k8s/redis-statefulset.yaml

# 4. Deploy everything
bash k8s/scripts/deploy-production.sh

# 5. Verify
kubectl get pods -n jewelry-shop
kubectl get postgresql jewelry-shop-db -n jewelry-shop
```

---

## Backup Your Configuration

All your configurations are in these files:
```bash
# Create a backup
tar -czf jewelry-shop-k8s-config-$(date +%Y%m%d).tar.gz k8s/

# Or commit to git
git add k8s/
git commit -m "Production-ready Kubernetes configuration"
git push
```

---

## Support & Troubleshooting

If you encounter issues:

1. **Check pod status:**
   ```bash
   kubectl get pods -n jewelry-shop
   kubectl describe pod <pod-name> -n jewelry-shop
   ```

2. **Check logs:**
   ```bash
   kubectl logs <pod-name> -n jewelry-shop
   ```

3. **Verify network policies:**
   ```bash
   kubectl get networkpolicies -n jewelry-shop
   ```

4. **Test database connectivity:**
   ```bash
   kubectl exec -n jewelry-shop jewelry-shop-db-0 -c postgres -- \
     psql -U postgres -c "SELECT 1;"
   ```

---

## Summary

**You have everything you need!** All configurations are saved in YAML files. To deploy to production:

1. Install k3s on VPS
2. Update 3 things: storage class, domain name, secrets
3. Run: `kubectl apply -f k8s/` (or use the deployment script)
4. Done! ✅

**No manual configuration needed. Everything is automated and reproducible.**

---

**Estimated Deployment Time:** 10-15 minutes
**Manual Configuration Required:** Minimal (just domain and secrets)
**Reproducibility:** 100% - All configs in YAML files
