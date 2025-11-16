# Production Readiness Plan - Professional VPS Deployment

## Executive Summary

**Problem 1:** Manual fixes in Kubernetes won't transfer to VPS
**Problem 2:** 34 security vulnerabilities detected by GitHub

**Solution:** Create fully automated, repeatable deployment pipeline

---

## Phase 1: Fix Security Vulnerabilities (Priority: CRITICAL)

### Step 1: Upgrade Vulnerable Packages

Create automated security audit:
```bash
# Run in Docker to check vulnerabilities
docker run --rm -v $(pwd):/app python:3.11-slim bash -c "
  cd /app && \
  pip install safety pip-audit && \
  pip-audit -r requirements.txt --desc
"
```

**Common Vulnerable Packages to Check:**
- Django (CVE issues in older versions)
- Pillow (image processing vulnerabilities)
- cryptography (security fixes)
- urllib3 (header injection)
- requests (security updates)
- jinja2 (XSS vulnerabilities)

### Step 2: Update requirements.txt

```bash
# Create updated requirements file
pip-compile --upgrade requirements.in
```

---

## Phase 2: Automate Database Setup (Repeatable Deployment)

### Problem: Manual migrations & user creation won't exist on VPS

### Solution 1: Database Migration Job (Kubernetes Job)

**Create: `k8s/django-migrate-job.yaml`**
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: django-migrate
  namespace: jewelry-shop
spec:
  template:
    spec:
      restartPolicy: OnFailure
      initContainers:
        - name: wait-for-db
          image: busybox:1.35
          command: ['sh', '-c', 'until nc -z postgresql 5432; do sleep 2; done']
      containers:
        - name: migrate
          image: jewelry-shop-django:latest
          command:
            - sh
            - -c
            - |
              python manage.py migrate --noinput
              python manage.py collectstatic --noinput
          envFrom:
            - configMapRef:
                name: django-config
            - secretRef:
                name: django-secrets
```

### Solution 2: Initial Admin User Creation

**Create: `k8s/django-createadmin-job.yaml`**
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: django-createadmin
  namespace: jewelry-shop
spec:
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: createadmin
          image: jewelry-shop-django:latest
          command:
            - python
            - manage.py
            - shell
            - -c
            - |
              from apps.core.models import User, Tenant
              from django.contrib.auth import get_user_model
              
              # Create platform admin
              if not User.objects.filter(username='platformadmin').exists():
                  User.objects.create_superuser(
                      username='platformadmin',
                      email='admin@platform.local',
                      password='CHANGE_ME_IN_PRODUCTION',
                      role='PLATFORM_ADMIN'
                  )
                  print("✅ Platform admin created")
          envFrom:
            - configMapRef:
                name: django-config
            - secretRef:
                name: django-secrets
```

### Solution 3: Database Fixtures (Better approach)

**Create: `apps/core/fixtures/initial_data.json`**
```json
[
  {
    "model": "core.user",
    "pk": 1,
    "fields": {
      "username": "platformadmin",
      "email": "admin@platform.local",
      "role": "PLATFORM_ADMIN",
      "is_superuser": true,
      "is_staff": true,
      "is_active": true
    }
  }
]
```

Load with:
```bash
python manage.py loaddata initial_data
```

---

## Phase 3: Docker Registry Setup (Image Distribution)

### Problem: Docker images only in local k3d cluster

### Solution: Push to Docker Hub or Private Registry

**Option A: Docker Hub (Public/Private)**
```bash
# Tag image
docker tag jewelry-shop-django:static-fixed yourusername/jewelry-shop-django:v1.0.0

# Push to Docker Hub
docker login
docker push yourusername/jewelry-shop-django:v1.0.0
```

**Option B: Private Registry**
```bash
# Deploy private registry on VPS
docker run -d -p 5000:5000 --name registry registry:2

# Tag and push
docker tag jewelry-shop-django:static-fixed vps-ip:5000/jewelry-shop-django:v1.0.0
docker push vps-ip:5000/jewelry-shop-django:v1.0.0
```

**Update k8s manifests:**
```yaml
# k8s/django-deployment.yaml
spec:
  containers:
    - name: django
      image: yourusername/jewelry-shop-django:v1.0.0  # ← From registry
      imagePullPolicy: Always
```

---

## Phase 4: Secrets Management (No Manual kubectl create)

### Problem: Secrets created manually won't exist on VPS

### Solution: Sealed Secrets or External Secrets Operator

**Create: `k8s/secrets-template.yaml`**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: django-secrets
  namespace: jewelry-shop
type: Opaque
stringData:
  SECRET_KEY: "CHANGE_ME_50_CHARS_MINIMUM_XXXXXXXXXXXXXXXXXXXXXXX"
  POSTGRES_PASSWORD: "CHANGE_ME"
  REDIS_PASSWORD: "CHANGE_ME"
  SENTRY_DSN: "https://your-sentry-dsn"
  STRIPE_SECRET_KEY: "sk_test_CHANGE_ME"
```

**Better: Use environment-specific secrets:**
```bash
# Create from .env file
kubectl create secret generic django-secrets \
  --from-env-file=.env.production \
  --namespace=jewelry-shop \
  --dry-run=client -o yaml > k8s/django-secrets.yaml
```

---

## Phase 5: One-Command Deployment Script

**Create: `deploy-to-vps.sh`**
```bash
#!/bin/bash
set -e

echo "🚀 Starting professional VPS deployment..."

# 1. Build Docker images
echo "📦 Building Docker images..."
docker build -f Dockerfile.prod -t jewelry-shop-django:latest .

# 2. Push to registry
echo "⬆️  Pushing to Docker registry..."
docker tag jewelry-shop-django:latest $REGISTRY/jewelry-shop-django:$VERSION
docker push $REGISTRY/jewelry-shop-django:$VERSION

# 3. Apply Kubernetes manifests
echo "☸️  Applying Kubernetes manifests..."
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml  # Must exist before deployment
kubectl apply -f k8s/postgresql/
kubectl apply -f k8s/redis/
kubectl apply -f k8s/

# 4. Run database migrations
echo "🗄️  Running database migrations..."
kubectl apply -f k8s/django-migrate-job.yaml
kubectl wait --for=condition=complete job/django-migrate --timeout=300s

# 5. Create admin user
echo "👤 Creating admin user..."
kubectl apply -f k8s/django-createadmin-job.yaml
kubectl wait --for=condition=complete job/django-createadmin --timeout=120s

# 6. Wait for deployments
echo "⏳ Waiting for deployments..."
kubectl rollout status deployment/django -n jewelry-shop --timeout=300s
kubectl rollout status deployment/nginx -n jewelry-shop --timeout=300s

echo "✅ Deployment complete!"
echo "🌐 Access your app at: https://your-vps-domain.com"
```

---

## Phase 6: Health Checks & Readiness Probes

**Update: `k8s/django-deployment.yaml`**
```yaml
containers:
  - name: django
    image: jewelry-shop-django:latest
    livenessProbe:
      httpGet:
        path: /health/
        port: 8000
      initialDelaySeconds: 30
      periodSeconds: 10
      failureThreshold: 3
    readinessProbe:
      httpGet:
        path: /health/ready/
        port: 8000
      initialDelaySeconds: 10
      periodSeconds: 5
      failureThreshold: 3
```

**Create health check endpoint: `apps/core/views/health.py`**
```python
from django.http import JsonResponse
from django.db import connection
from redis import Redis

def health_check(request):
    """Basic liveness check"""
    return JsonResponse({"status": "healthy"})

def readiness_check(request):
    """Check if app can serve traffic"""
    checks = {}
    
    # Database
    try:
        connection.ensure_connection()
        checks['database'] = 'ok'
    except Exception as e:
        checks['database'] = f'error: {e}'
    
    # Redis
    try:
        from django.core.cache import cache
        cache.set('health_check', 'ok', 10)
        checks['redis'] = 'ok'
    except Exception as e:
        checks['redis'] = f'error: {e}'
    
    all_ok = all(v == 'ok' for v in checks.values())
    status = 200 if all_ok else 503
    
    return JsonResponse(checks, status=status)
```

---

## Phase 7: Documentation & Runbooks

**Create: `DEPLOYMENT.md`**
- Prerequisites (kubectl, docker, credentials)
- Step-by-step deployment guide
- Rollback procedures
- Troubleshooting common issues

**Create: `RUNBOOK.md`**
- How to scale pods
- How to update secrets
- How to perform database backups
- How to check logs
- Emergency procedures

---

## Implementation Checklist

### Immediate Actions (Before VPS Deployment)

- [ ] **Audit security vulnerabilities** - Run pip-audit
- [ ] **Update requirements.txt** - Fix all CVEs
- [ ] **Create migration Job** - k8s/django-migrate-job.yaml
- [ ] **Create admin user Job** - k8s/django-createadmin-job.yaml
- [ ] **Set up Docker registry** - Docker Hub or private
- [ ] **Push all images** - Tag with versions
- [ ] **Create secrets template** - k8s/secrets-template.yaml
- [ ] **Document all secrets needed** - Update .env.production.example
- [ ] **Create deployment script** - deploy-to-vps.sh
- [ ] **Add health checks** - Liveness & readiness probes
- [ ] **Test deployment** - Fresh k3d cluster test
- [ ] **Create rollback procedure** - Document in RUNBOOK.md

### VPS Deployment Steps

1. **Provision VPS** - Ubuntu 22.04, 4GB+ RAM
2. **Install K3s** - Lightweight Kubernetes
3. **Configure kubectl** - Connect to VPS cluster
4. **Create secrets** - kubectl create secret from .env.production
5. **Run deployment script** - ./deploy-to-vps.sh
6. **Verify health** - Check all pods running
7. **Configure DNS** - Point domain to VPS IP
8. **Enable SSL** - cert-manager with Let's Encrypt
9. **Set up monitoring** - Prometheus, Grafana
10. **Configure backups** - Database & media files

---

## Success Criteria

✅ **One command deploys everything** - ./deploy-to-vps.sh
✅ **No manual kubectl commands** - All in manifests
✅ **All secrets documented** - .env.production.example complete
✅ **Zero vulnerabilities** - pip-audit clean
✅ **Health checks working** - Auto-restart on failure
✅ **Rollback works** - Can revert to previous version
✅ **Documentation complete** - Anyone can deploy

---

## Next Steps

**Recommended Order:**
1. Fix vulnerabilities first (security)
2. Create Jobs for migrations/admin (automation)
3. Set up Docker registry (image distribution)
4. Create deployment script (repeatability)
5. Test on fresh k3d cluster (validation)
6. Deploy to VPS (production)

**Estimated Time:** 4-6 hours for complete professional setup
