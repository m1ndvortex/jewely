# k3d Limitations and Production Kubernetes Guide

## Executive Summary

**k3d is a development tool, NOT a production-grade Kubernetes platform.** You are experiencing pod failures after PC restarts because k3d lacks the auto-healing and fault-tolerance capabilities of production Kubernetes.

## Current Issues After PC Restart

### Root Causes Identified

1. **PgBouncer Authentication Failure** (CRITICAL)
   - PgBouncer pods cannot authenticate to PostgreSQL after cluster restart
   - Error: `server login has been failing, try again later (server_login_retry)`
   - Direct PostgreSQL connections work, but PgBouncer layer is broken
   - This blocks all Django pods from starting

2. **Network State Loss**
   - k3d runs Kubernetes nodes as Docker containers
   - When PC restarts → Docker restarts → All container networking resets
   - Pod IPs change, causing connection state issues
   - Services and endpoints need time to reconcile

3. **StatefulSet Recovery Problems**
   - Pods stuck in "Unknown" state after abrupt shutdown
   - StatefulSets don't automatically recover without intervention
   - Redis Sentinel and database replicas require manual cleanup

4. **No Persistent Storage**
   - All volumes are `emptyDir` (ephemeral)
   - Data loss on pod restarts
   - No PersistentVolumeClaims configured

### Immediate Workaround

```bash
# 1. Restart k3d cluster properly
k3d cluster stop jewelry-shop
k3d cluster start jewelry-shop

# 2. Delete PgBouncer pods to reset connections
kubectl delete pod -n jewelry-shop -l application=db-connection-pooler --force --grace-period=0

# 3. Delete stuck StatefulSet pods
kubectl delete pod -n jewelry-shop redis-sentinel-1 redis-sentinel-2 --force --grace-period=0

# 4. Clean up Unknown/Failed pods
kubectl delete pods -n jewelry-shop --field-selector=status.phase=Unknown --force --grace-period=0
kubectl delete pods -n jewelry-shop --field-selector=status.phase=Failed --force --grace-period=0

# 5. Restart Django deployment
kubectl rollout restart deployment/django -n jewelry-shop

# 6. Wait for pods to become ready
kubectl wait --for=condition=ready pod -l component=django -n jewelry-shop --timeout=5m
```

## Why k3d Fails at Auto-Healing

### What k3d IS

- ✅ Lightweight Kubernetes for **development and testing**
- ✅ Fast local cluster creation
- ✅ Good for CI/CD pipelines
- ✅ Easy to set up and tear down

### What k3d IS NOT

- ❌ Production-grade infrastructure
- ❌ Fault-tolerant across host reboots
- ❌ Multi-node redundancy (nodes are Docker containers on same host)
- ❌ Network-attached storage
- ❌ Cloud load balancer integration
- ❌ Automatic disaster recovery

### Kubernetes Auto-Healing Requirements

For TRUE auto-healing, you need:

1. **Multiple Physical/Virtual Nodes**
   - k3d: All "nodes" are containers on your one PC
   - Production: Nodes are separate VMs/servers

2. **Persistent Storage with Network Access**
   - k3d: `emptyDir` volumes (data lost on pod restart)
   - Production: Cloud storage (EBS, Persistent Disks, Azure Disks)

3. **Cluster State Persistence**
   - k3d: etcd data in Docker volume (can become corrupt on hard restart)
   - Production: etcd replicated across multiple nodes with backups

4. **Network Overlay Resilience**
   - k3d: Docker bridge network (resets on Docker restart)
   - Production: Cloud VPC with persistent IPs and load balancers

5. **Control Plane Redundancy**
   - k3d: Single control plane node (if it fails, cluster is down)
   - Production: 3+ control plane nodes for high availability

## Production Kubernetes Options

### 1. **Managed Kubernetes (RECOMMENDED)**

#### Google Kubernetes Engine (GKE)
```bash
# Create production cluster
gcloud container clusters create jewelry-shop-prod \
  --region us-central1 \
  --num-nodes 3 \
  --machine-type n2-standard-4 \
  --enable-autoscaling --min-nodes 3 --max-nodes 10 \
  --enable-autorepair \
  --enable-autoupgrade \
  --maintenance-window-start "2025-01-01T00:00:00Z" \
  --maintenance-window-duration 4h
```

**Benefits:**
- ✅ Automatic node repairs
- ✅ Automatic security updates
- ✅ Cloud Load Balancer integration
- ✅ Persistent storage (Google Persistent Disks)
- ✅ Multi-zone redundancy
- ✅ 99.95% SLA

**Cost:** ~$200-500/month for small production cluster

#### Amazon EKS
```bash
# Create production cluster
eksctl create cluster \
  --name jewelry-shop-prod \
  --region us-east-1 \
  --nodegroup-name standard-workers \
  --node-type t3.medium \
  --nodes 3 \
  --nodes-min 3 \
  --nodes-max 10 \
  --managed \
  --asg-access \
  --external-dns-access \
  --full-ecr-access \
  --alb-ingress-access
```

**Benefits:**
- ✅ AWS integration (RDS, ElastiCache, S3)
- ✅ Auto Scaling Groups for node management
- ✅ EBS/EFS for persistent storage
- ✅ Application Load Balancer
- ✅ IAM integration for security
- ✅ 99.95% SLA

**Cost:** ~$150-400/month for small cluster

#### Azure Kubernetes Service (AKS)
```bash
# Create production cluster
az aks create \
  --resource-group jewelry-shop-rg \
  --name jewelry-shop-prod \
  --node-count 3 \
  --enable-managed-identity \
  --enable-cluster-autoscaler \
  --min-count 3 \
  --max-count 10 \
  --network-plugin azure \
  --enable-addons monitoring \
  --generate-ssh-keys
```

**Benefits:**
- ✅ Azure integration (SQL, Redis, Storage)
- ✅ Auto-scaling and auto-repair
- ✅ Azure Disk for persistent storage
- ✅ Azure Load Balancer
- ✅ Active Directory integration
- ✅ 99.95% SLA

**Cost:** ~$180-450/month for small cluster

### 2. **Self-Hosted Kubernetes on VPS**

For more control and potentially lower costs:

#### Linode Kubernetes Engine (LKE)
- **Cost:** ~$60-150/month for 3 nodes
- **Pros:** Simple, affordable, good documentation
- **Cons:** Smaller ecosystem than big clouds

#### DigitalOcean Kubernetes
- **Cost:** ~$60-120/month for 3 nodes
- **Pros:** Easy to use, good docs, affordable
- **Cons:** Limited regions, smaller ecosystem

#### Hetzner Cloud + k3s/k0s
- **Cost:** ~$30-90/month for 3 VMs + setup
- **Pros:** Very affordable, powerful VMs
- **Cons:** Manual setup, EU-only data centers

### 3. **On-Premise Kubernetes**

If you have physical servers:

#### Rancher RKE2
- Production-grade k3s successor
- Air-gapped installation support
- Multi-cluster management

#### VMware Tanzu
- Enterprise Kubernetes platform
- vSphere integration
- Advanced security features

#### Red Hat OpenShift
- Enterprise Kubernetes distribution
- Built-in CI/CD, monitoring, logging
- Enterprise support

## Migration from k3d to Production

### Phase 1: Preparation

1. **Audit Current Setup**
   ```bash
   # Export all resources
   kubectl get all -n jewelry-shop -o yaml > k3d-resources.yaml
   kubectl get configmap -n jewelry-shop -o yaml > k3d-configmaps.yaml
   kubectl get secret -n jewelry-shop -o yaml > k3d-secrets.yaml
   kubectl get pvc -n jewelry-shop -o yaml > k3d-pvcs.yaml
   ```

2. **Extract Environment Variables**
   ```bash
   kubectl get configmap -n jewelry-shop app-config -o yaml > production-config.yaml
   # Review and update for production
   ```

3. **Document Database Schema**
   ```bash
   kubectl exec -n jewelry-shop jewelry-shop-db-0 -c postgres -- \
     pg_dump -U jewelry_app jewelry_shop --schema-only > schema.sql
   ```

### Phase 2: Infrastructure Setup

1. **Choose Cloud Provider** (GKE recommended for ease)

2. **Create Production Cluster**
   - Multi-zone for high availability
   - Auto-scaling enabled
   - Security policies configured

3. **Set Up Managed Databases**
   ```bash
   # Instead of self-hosted PostgreSQL
   # Use Cloud SQL (GCP), RDS (AWS), or Azure Database
   
   # Benefits:
   # - Automatic backups
   # - Point-in-time recovery
   # - Automatic failover
   # - Scaling without downtime
   # - Managed security patches
   ```

4. **Configure Persistent Storage**
   ```yaml
   # Create StorageClass for production
   apiVersion: storage.k8s.io/v1
   kind: StorageClass
   metadata:
     name: fast-ssd
   provisioner: pd.csi.storage.gke.io  # GCP example
   parameters:
     type: pd-ssd
     replication-type: regional-pd  # Multi-zone replication
   ```

### Phase 3: Application Deployment

1. **Update Django Deployment**
   ```yaml
   spec:
     replicas: 3
     template:
       spec:
         affinity:
           podAntiAffinity:
             requiredDuringSchedulingIgnoredDuringExecution:
             - labelSelector:
                 matchExpressions:
                 - key: component
                   operator: In
                   values:
                   - django
               topologyKey: kubernetes.io/hostname
         # This ensures pods are on different nodes
   ```

2. **Add PersistentVolumeClaims**
   ```yaml
   apiVersion: v1
   kind: PersistentVolumeClaim
   metadata:
     name: django-media
   spec:
     storageClassName: fast-ssd
     accessModes:
       - ReadWriteMany
     resources:
       requests:
         storage: 100Gi
   ```

3. **Configure Ingress with Real Load Balancer**
   ```yaml
   apiVersion: networking.k8s.io/v1
   kind: Ingress
   metadata:
     name: jewelry-shop
     annotations:
       kubernetes.io/ingress.class: "gce"  # GCP
       cert-manager.io/cluster-issuer: "letsencrypt-prod"
   spec:
     tls:
     - hosts:
       - jewelry-shop.com
       secretName: jewelry-shop-tls
     rules:
     - host: jewelry-shop.com
       http:
         paths:
         - path: /
           pathType: Prefix
           backend:
             service:
               name: nginx
               port:
                 number: 80
   ```

### Phase 4: Data Migration

1. **Export Data from k3d**
   ```bash
   # Dump production data
   kubectl exec -n jewelry-shop jewelry-shop-db-0 -c postgres -- \
     pg_dump -U jewelry_app jewelry_shop -Fc > jewelry_shop.dump
   ```

2. **Import to Cloud Database**
   ```bash
   # Restore to Cloud SQL/RDS
   pg_restore -h <cloud-db-host> -U jewelry_app -d jewelry_shop jewelry_shop.dump
   ```

3. **Sync Media Files**
   ```bash
   # Upload to Cloud Storage (S3, GCS, Azure Blob)
   gsutil -m rsync -r ./media gs://jewelry-shop-media/
   ```

### Phase 5: Cutover

1. **Update DNS**
   - Point domain to cloud load balancer
   - Use short TTL during migration (5 minutes)

2. **Monitor**
   - Check application logs
   - Monitor database connections
   - Watch resource usage

3. **Rollback Plan**
   - Keep k3d running for 48 hours
   - Document rollback steps
   - Test rollback procedure

## Fixing k3d for Development Use

While k3d won't provide production auto-healing, we can make it more stable:

### 1. Bypass PgBouncer (IMMEDIATE FIX)

Update Django to connect directly to PostgreSQL:

```yaml
# In Django deployment
env:
  - name: DATABASE_URL
    value: "postgresql://$(DB_USER):$(APP_DB_PASSWORD)@jewelry-shop-db:5432/$(POSTGRES_DB)?sslmode=require&sslcert=/etc/postgresql-ssl/tls.crt&sslkey=/etc/postgresql-ssl/tls.key&sslrootcert=/etc/postgresql-ssl/tls.crt"
```

### 2. Add Startup Script

Create `/home/crystalah/kiro/jewely/scripts/k3d-startup.sh`:

```bash
#!/bin/bash
set -e

echo "Starting k3d cluster recovery..."

# Restart cluster
k3d cluster stop jewelry-shop 2>/dev/null || true
k3d cluster start jewelry-shop

# Wait for cluster to be ready
echo "Waiting for cluster to be ready..."
kubectl wait --for=condition=ready node --all --timeout=5m

# Delete stuck pods
echo "Cleaning up stuck pods..."
kubectl delete pods -n jewelry-shop --field-selector=status.phase=Unknown --force --grace-period=0 2>/dev/null || true
kubectl delete pods -n jewelry-shop --field-selector=status.phase=Failed --force --grace-period=0 2>/dev/null || true

# Restart critical deployments
echo "Restarting deployments..."
kubectl rollout restart deployment/django -n jewelry-shop
kubectl rollout restart deployment/nginx -n jewelry-shop
kubectl rollout restart deployment/celery-worker -n jewelry-shop

# Wait for services to be ready
echo "Waiting for services to be ready..."
kubectl wait --for=condition=ready pod -l component=django -n jewelry-shop --timeout=10m || true

echo "Cluster recovery complete!"
kubectl get pods -n jewelry-shop
```

### 3. Add systemd Service (Linux)

Create `/etc/systemd/system/k3d-jewelry-shop.service`:

```ini
[Unit]
Description=k3d Jewelry Shop Cluster
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/k3d cluster start jewelry-shop
ExecStop=/usr/local/bin/k3d cluster stop jewelry-shop
User=crystalah

[Install]
WantedBy=multi-user.target
```

Enable it:
```bash
sudo systemctl enable k3d-jewelry-shop
sudo systemctl start k3d-jewelry-shop
```

## Cost Comparison

| Solution | Monthly Cost | Auto-Healing | SLA | Maintenance |
|----------|-------------|--------------|-----|-------------|
| k3d (local) | $0 | ❌ No | None | High |
| GKE | $200-500 | ✅ Yes | 99.95% | Low |
| EKS | $150-400 | ✅ Yes | 99.95% | Low |
| AKS | $180-450 | ✅ Yes | 99.95% | Low |
| DigitalOcean | $60-120 | ✅ Yes | 99.95% | Medium |
| Linode | $60-150 | ✅ Yes | 99.9% | Medium |
| Hetzner + k3s | $30-90 | ⚠️ Partial | None | High |

## Recommendation

**For Production:**
1. **Start with GKE** (easiest, best auto-healing)
2. Use Cloud SQL for PostgreSQL (managed, auto-backup, auto-failover)
3. Use Cloud Memorystore for Redis (managed, highly available)
4. Set up Cloud CDN for static assets
5. Enable Google Cloud Armor for DDoS protection

**For Development:**
1. Keep k3d for local testing
2. Create startup script for PC restart recovery
3. Bypass PgBouncer connection pooler
4. Accept that manual intervention is needed after crashes

**Next Steps:**
1. Create GKE cluster (can use free trial credits)
2. Migrate one environment at a time (staging first)
3. Test thoroughly before production cutover
4. Keep k3d as development environment

## Questions?

- **Why is k3d failing?** Because it's designed for quick testing, not production resilience.
- **Can k3d be fixed?** Partially, but it will never have true auto-healing.
- **What's the minimum for production?** 3-node managed Kubernetes cluster + managed database.
- **How long to migrate?** 1-2 weeks for proper migration with testing.
- **Can I automate migration?** Yes, using Terraform or Pulumi.

---

**Bottom Line:** k3d served its purpose for development, but true auto-healing requires production Kubernetes infrastructure. The investment in cloud Kubernetes pays off through reduced downtime, automatic recovery, and peace of mind.
