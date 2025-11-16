# Complete VPS Setup Guide - From Zero to Production

## Overview

This guide takes you from a fresh VPS to a fully running production Kubernetes cluster with your jewelry shop application.

**Important:** You do NOT need Docker on the VPS! k3s includes its own container runtime (containerd). You only need k3s.

---

## Step 1: VPS Requirements

### Minimum Specifications
- **CPU:** 4 cores (8 cores recommended)
- **RAM:** 8GB (16GB recommended)
- **Storage:** 100GB SSD (200GB recommended)
- **OS:** Ubuntu 22.04 LTS (or any Linux)
- **Network:** Public IP address

### Firewall Ports to Open
```bash
# SSH
sudo ufw allow 22/tcp

# HTTP/HTTPS (for your application)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Kubernetes API (for kubectl access)
sudo ufw allow 6443/tcp

# Enable firewall
sudo ufw enable
```

---

## Step 2: Install k3s (No Docker Needed!)

### Why No Docker?
k3s includes **containerd** as its container runtime. You don't need to install Docker separately. k3s is a complete Kubernetes distribution.

### Install k3s

```bash
# SSH to your VPS
ssh user@your-vps-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Install k3s (single command!)
curl -sfL https://get.k3s.io | sh -

# This installs:
# - Kubernetes (k3s)
# - containerd (container runtime)
# - kubectl (Kubernetes CLI)
# - All necessary components

# Verify installation
sudo k3s kubectl get nodes

# Expected output:
# NAME        STATUS   ROLES                  AGE   VERSION
# your-vps    Ready    control-plane,master   1m    v1.28.x+k3s1
```

### Configure kubectl Access

```bash
# Allow non-root access (optional)
sudo chmod 644 /etc/rancher/k3s/k3s.yaml

# Or add your user to the group
sudo usermod -aG sudo $USER

# Test kubectl
kubectl get nodes
```

---

## Step 3: Install Required Tools on VPS

### Install Helm (for operators)

```bash
# Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Verify
helm version
```

### Install Longhorn (Storage - Optional but Recommended)

```bash
# Install Longhorn for persistent storage
kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/v1.5.3/deploy/longhorn.yaml

# Wait for Longhorn to be ready
kubectl wait --for=condition=ready pod -l app=longhorn-manager -n longhorn-system --timeout=300s

# Verify
kubectl get storageclass
# You should see: longhorn (default)
```

**Note:** If you skip Longhorn, k3s will use `local-path` storage (works but less features).

---

## Step 4: Configure kubectl on Your Local Machine

### Get kubeconfig from VPS

```bash
# On your VPS, display the kubeconfig
sudo cat /etc/rancher/k3s/k3s.yaml
```

### Save on Local Machine

```bash
# On your local machine
nano ~/.kube/config-production

# Paste the content from VPS
# IMPORTANT: Replace this line:
#   server: https://127.0.0.1:6443
# With:
#   server: https://YOUR_VPS_IP:6443

# Save and exit (Ctrl+X, Y, Enter)

# Use the production config
export KUBECONFIG=~/.kube/config-production

# Test connection
kubectl get nodes

# Expected output:
# NAME        STATUS   ROLES                  AGE   VERSION
# your-vps    Ready    control-plane,master   5m    v1.28.x+k3s1
```

---

## Step 5: Configure DNS

### Point Your Domain to VPS

In your domain registrar (Namecheap, GoDaddy, Cloudflare, etc.):

```
Type    Name    Value           TTL
A       @       YOUR_VPS_IP     300
A       *       YOUR_VPS_IP     300
```

**Wait 5-10 minutes** for DNS propagation.

### Verify DNS

```bash
# Check if domain resolves to your VPS
dig your-domain.com +short
# Should show: YOUR_VPS_IP

# Or use nslookup
nslookup your-domain.com
```

---

## Step 6: Deploy Application (Automated!)

### Run the Deployment Script

```bash
# On your local machine (with kubectl configured)
cd k8s/scripts
bash deploy-production.sh
```

### The Script Will Ask:

1. **Domain name:** `your-domain.com`
2. **Email for SSL:** `your-email@example.com` (for Let's Encrypt)
3. **Storage class:** `longhorn` (or press Enter for default)
4. **Deploy monitoring:** `yes` or `no`

### What Happens Automatically:

1. ✅ Creates namespace
2. ✅ Generates secure passwords (saves them for you)
3. ✅ Deploys PostgreSQL cluster (3 replicas with automatic failover)
4. ✅ Deploys Redis cluster (3 replicas with Sentinel)
5. ✅ Deploys Django application (3 replicas with HPA)
6. ✅ Deploys Celery workers and beat
7. ✅ Deploys Nginx reverse proxy
8. ✅ Configures Traefik ingress
9. ✅ Requests SSL certificate from Let's Encrypt (automatic!)
10. ✅ Applies all network policies

**Total Time:** 10-15 minutes

---

## Step 7: Verify Deployment

### Check All Pods

```bash
kubectl get pods -n jewelry-shop

# All pods should be Running
```

### Check PostgreSQL

```bash
# Cluster status
kubectl get postgresql jewelry-shop-db -n jewelry-shop

# Should show: STATUS = Running

# Check replication
kubectl exec -n jewelry-shop jewelry-shop-db-0 -c postgres -- \
  psql -U postgres -c "SELECT application_name, state, sync_state FROM pg_stat_replication;"

# Should show 2 replicas streaming
```

### Check SSL Certificate

```bash
# Check certificate status
kubectl get certificate -n jewelry-shop

# Should show: READY = True

# Test HTTPS
curl -I https://your-domain.com
# Should show: HTTP/2 200
```

### Access Your Application

Open browser: `https://your-domain.com`

You should see your jewelry shop application! 🎉

---

## Complete Installation Summary

### What You Need to Install on VPS:

1. ✅ **k3s** - Includes Kubernetes + containerd (NO Docker needed!)
2. ✅ **Helm** - For installing operators
3. ✅ **Longhorn** (optional) - For better storage

### What You DON'T Need:

- ❌ Docker
- ❌ Docker Compose
- ❌ PostgreSQL
- ❌ Redis
- ❌ Nginx
- ❌ Python
- ❌ Node.js

**Everything runs inside Kubernetes containers!**

---

## Quick Command Reference

### On VPS (One-Time Setup)

```bash
# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Configure firewall
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 6443/tcp
sudo ufw enable

# 3. Install k3s
curl -sfL https://get.k3s.io | sh -

# 4. Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# 5. Install Longhorn (optional)
kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/v1.5.3/deploy/longhorn.yaml

# 6. Get kubeconfig
sudo cat /etc/rancher/k3s/k3s.yaml
```

### On Local Machine (Deploy Application)

```bash
# 1. Save kubeconfig
nano ~/.kube/config-production
# Paste content and replace 127.0.0.1 with VPS IP

# 2. Configure kubectl
export KUBECONFIG=~/.kube/config-production

# 3. Deploy everything
cd k8s/scripts
bash deploy-production.sh

# 4. Wait and verify
kubectl get pods -n jewelry-shop -w
```

---

## SSL Certificate (Automatic!)

### Let's Encrypt Integration

The deployment script automatically:
1. ✅ Installs cert-manager
2. ✅ Configures Let's Encrypt issuer
3. ✅ Requests SSL certificate for your domain
4. ✅ Configures automatic renewal (every 60 days)

**You don't need to do anything!** Just provide your email when the script asks.

### Verify SSL

```bash
# Check certificate
kubectl get certificate -n jewelry-shop

# Test HTTPS
curl -I https://your-domain.com
```

---

## Domain Configuration

### The Script Asks For:

1. **Domain name:** `jewelry-shop.com` (or whatever you own)
2. **Email:** `admin@jewelry-shop.com` (for Let's Encrypt notifications)

### The Script Automatically:

1. ✅ Updates ingress configuration with your domain
2. ✅ Configures Traefik to handle your domain
3. ✅ Requests SSL certificate from Let's Encrypt
4. ✅ Configures HTTP → HTTPS redirect

**No manual SSL configuration needed!**

---

## Estimated Timeline

| Step | Time | Complexity |
|------|------|------------|
| VPS Setup | 5 min | Easy |
| k3s Installation | 2 min | Easy |
| kubectl Configuration | 2 min | Easy |
| DNS Configuration | 5 min | Easy |
| Run Deployment Script | 10 min | Easy |
| **Total** | **~25 min** | **Easy** |

---

## What Makes This Easy?

1. ✅ **All configurations saved** - No manual work to repeat
2. ✅ **Automated script** - Just answer 3 questions
3. ✅ **No Docker needed** - k3s includes everything
4. ✅ **Automatic SSL** - Let's Encrypt integration
5. ✅ **Self-healing** - Kubernetes handles failures
6. ✅ **One command deployment** - `bash deploy-production.sh`

---

## Summary

### On VPS (One-Time):
```bash
# Install k3s (includes container runtime)
curl -sfL https://get.k3s.io | sh -

# Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Optional: Install Longhorn for better storage
kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/v1.5.3/deploy/longhorn.yaml
```

### On Local Machine:
```bash
# Configure kubectl
export KUBECONFIG=~/.kube/config-production

# Deploy everything
bash k8s/scripts/deploy-production.sh
# Enter: domain name, email, storage class
# Done! ✅
```

**No Docker. No manual configuration. Just k3s + your YAML files!**

---

## Questions Answered

**Q: Do I need Docker?**
A: ❌ No! k3s includes containerd (container runtime). Docker is not needed.

**Q: Do I need to enter my domain?**
A: ✅ Yes! The script will ask you for it and configure everything automatically.

**Q: What about SSL/Let's Encrypt?**
A: ✅ Automatic! The script installs cert-manager and requests SSL certificate. Just provide your email.

**Q: Do I need to install packages?**
A: ✅ Only k3s and Helm on the VPS. Everything else runs in containers.

**Q: Will I need to repeat all the configuration?**
A: ❌ No! Everything is saved in YAML files. Just apply them.

---

**You're ready! Just follow the steps above and you'll have production running in ~25 minutes.** 🚀
