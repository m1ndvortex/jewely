# VPS Deployment Quick Reference

## ✅ What's Already Persisted (You Don't Need to Do Manually)

### 1. ALLOWED_HOSTS Configuration
- **File**: `k8s/configmap.yaml`
- **Value**: `DJANGO_ALLOWED_HOSTS: "*"`
- **Status**: ✅ Saved in git

### 2. OpenTelemetry Stack
- **Files**: 
  - `k8s/opentelemetry/tempo-configmap.yaml`
  - `k8s/opentelemetry/tempo-deployment.yaml`
  - `k8s/opentelemetry/otel-collector-configmap.yaml`
  - `k8s/opentelemetry/otel-collector-deployment.yaml`
- **Status**: ✅ Already exists in git
- **Deployment**: ✅ Automated in `scripts/production-vps-complete-setup.sh`

### 3. PostgreSQL Streaming Replication
- **Files**: All PostgreSQL YAML configs
- **Status**: ✅ Already configured
- **Expected**: 3 pods (1 primary + 2 replicas)

### 4. Cluster Auto-Start
- **k3s (VPS)**: ✅ Native systemd integration (auto-starts on boot)
- **k3d (local)**: ✅ Systemd service created (`k3d-jewelry-shop.service`)

## 🚀 VPS Deployment Steps

### Step 1: Prepare VPS
```bash
# SSH to your VPS
ssh root@your-vps-ip

# Clone repository
git clone https://github.com/yourusername/jewelry-shop.git
cd jewelry-shop
```

### Step 2: Run Deployment Script
```bash
# Make script executable
chmod +x scripts/production-vps-complete-setup.sh

# Run deployment (will prompt for domain and email)
sudo bash scripts/production-vps-complete-setup.sh
```

**The script will ask for:**
- Domain name (e.g., `jewelry-shop.com`)
- Admin email (for Let's Encrypt SSL)
- Enable monitoring? (yes/no)

### Step 3: Wait for Deployment
- Takes 10-15 minutes
- Script shows progress for each step
- Creates all resources automatically

### Step 4: Verify Deployment
```bash
# Run health check
./scripts/cluster-health-check.sh
```

**Expected output:**
```
✅ Cluster Status: Running
✅ Nodes Ready: 3/3
✅ Pods Running: 24/24
✅ PostgreSQL: 3 pods
✅ Redis: 6 pods
✅ Django: 2-3 pods
✅ Nginx: 2 pods
✅ Monitoring: All running
```

## 📋 What Gets Deployed Automatically

### Core Application
- ✅ PostgreSQL with streaming replication (3 pods)
- ✅ Redis Sentinel (6 pods)
- ✅ Django application (2-3 pods)
- ✅ Celery workers
- ✅ Nginx reverse proxy (2 pods)

### Monitoring & Observability
- ✅ Prometheus (metrics collection)
- ✅ Grafana (dashboards)
- ✅ Loki (log aggregation)
- ✅ Tempo (distributed tracing)
- ✅ OpenTelemetry Collector (trace collection)

### Security & Networking
- ✅ Network policies (pod-to-pod security)
- ✅ TLS/SSL certificates (Let's Encrypt)
- ✅ Secrets management
- ✅ Resource limits

### Storage
- ✅ PersistentVolumeClaims (16 total)
- ✅ StatefulSets for stateful services
- ✅ Automatic backup system

## 🔧 Post-Deployment Tasks

### 1. Access Grafana
```bash
# Port-forward Grafana
kubectl port-forward -n jewelry-shop svc/grafana 3000:3000

# Open browser: http://localhost:3000
# Default: admin/admin (change password)
```

### 2. Configure Tempo Data Source in Grafana
1. Go to Configuration → Data Sources
2. Tempo should already be listed
3. Test connection
4. Explore traces

### 3. Check Django Admin
```bash
# Create superuser
POD=$(kubectl get pod -n jewelry-shop -l component=django -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it -n jewelry-shop $POD -- python manage.py createsuperuser
```

### 4. Verify PostgreSQL Replication
```bash
kubectl exec -n jewelry-shop jewelry-shop-db-0 -c postgres -- \
  psql -U postgres -c "SELECT client_addr, state, sync_state FROM pg_stat_replication;"
```

**Expected:**
- 2 replicas streaming
- 1 sync (blocks until confirmed)
- 1 async (non-blocking)

## 🔍 Troubleshooting

### If Pods Are Not Running
```bash
# Check pod status
kubectl get pods -n jewelry-shop

# Check specific pod logs
kubectl logs -n jewelry-shop <pod-name>

# Describe pod for events
kubectl describe pod -n jewelry-shop <pod-name>
```

### If ConfigMap Changes Don't Apply
```bash
# Force pod restart with new env vars
kubectl patch deployment <name> -n jewelry-shop -p \
  '{"spec":{"template":{"metadata":{"annotations":{"configmap-updated":"'$(date +%s)'"}}}}}'
```

### If Cluster Doesn't Auto-Start (VPS)
On VPS with k3s, cluster auto-starts via systemd. To check:
```bash
sudo systemctl status k3s
sudo systemctl enable k3s  # Should already be enabled
```

## ✅ Verification Checklist

After deployment, verify:

- [ ] All 24 pods running
- [ ] PostgreSQL streaming (2 replicas)
- [ ] Django no ALLOWED_HOSTS errors
- [ ] Nginx responding to requests
- [ ] Prometheus collecting metrics
- [ ] Grafana accessible
- [ ] Tempo receiving traces
- [ ] SSL certificates issued
- [ ] Cluster auto-starts on reboot

## 📊 Monitoring URLs

After port-forwarding:

- **Grafana**: http://localhost:3000
- **Prometheus**: http://localhost:9090
- **Django**: http://localhost:8000

## 🎯 Key Files Modified

1. `k8s/configmap.yaml` - ALLOWED_HOSTS wildcard
2. `scripts/production-vps-complete-setup.sh` - OpenTelemetry automation

**All changes committed to git** - Pull latest code before VPS deployment.

## 🚨 Important Notes

1. **ConfigMaps**: Changes require pod restart
2. **Secrets**: Never commit to git (use `app-secrets` ConfigMap)
3. **Backups**: Automatic PostgreSQL backups enabled
4. **SSL**: Let's Encrypt auto-renewal configured
5. **Auto-scaling**: HPA configured for Django (2-5 pods)

## 📞 Support Commands

```bash
# View all resources
kubectl get all -n jewelry-shop

# Check cluster health
./scripts/cluster-health-check.sh

# View logs
kubectl logs -n jewelry-shop -l component=django --tail=100

# Shell into pod
kubectl exec -it -n jewelry-shop <pod-name> -- /bin/bash

# Check resource usage
kubectl top pods -n jewelry-shop
```

---

**Ready for production VPS deployment!** All manual fixes have been automated.
