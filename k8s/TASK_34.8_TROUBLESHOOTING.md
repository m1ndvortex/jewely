# Task 34.8 Troubleshooting Guide

## Common Issues and Solutions

### Issue 1: CrashLoopBackOff on Startup

**Symptoms**:
- Pods show `CrashLoopBackOff` status
- 2 out of 3 workers fail to start consistently
- Logs show connection errors to Redis or PostgreSQL

**Root Causes**:
1. **Thundering Herd**: All pods try to connect simultaneously
2. **Resource Contention**: Insufficient resources during startup
3. **Dependencies Not Ready**: Redis or PostgreSQL not fully initialized

**Solutions Implemented**:

#### 1. Init Container with Dependency Checks
```yaml
initContainers:
  - name: wait-for-dependencies
    command:
      - sh
      - -c
      - |
        # Wait for Redis
        until nc -z redis.jewelry-shop.svc.cluster.local 6379; do
          sleep 2
        done
        
        # Wait for PostgreSQL
        until nc -z jewelry-shop-db-pooler.jewelry-shop.svc.cluster.local 5432; do
          sleep 2
        done
        
        # Stagger startup (0-10 seconds random delay)
        sleep $((RANDOM % 10))
```

**Benefits**:
- ✅ Ensures dependencies are ready before starting Celery
- ✅ Prevents connection failures during startup
- ✅ Staggers pod startup to prevent thundering herd
- ✅ Reduces resource contention

#### 2. Pod Disruption Budget
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: celery-worker-pdb
spec:
  minAvailable: 2  # At least 2 workers always available
```

**Benefits**:
- ✅ Ensures minimum availability during updates
- ✅ Prevents all workers from being down simultaneously
- ✅ Protects against voluntary disruptions

#### 3. Extended Startup Probe
```yaml
startupProbe:
  initialDelaySeconds: 45  # Account for init container
  periodSeconds: 10
  failureThreshold: 36  # 360 seconds total (6 minutes)
```

**Benefits**:
- ✅ Gives more time for slow startup
- ✅ Prevents premature pod restarts
- ✅ Accounts for init container delay

#### 4. Pod Anti-Affinity
```yaml
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          topologyKey: kubernetes.io/hostname
```

**Benefits**:
- ✅ Spreads workers across different nodes
- ✅ Reduces resource contention on single node
- ✅ Improves fault tolerance

### Issue 2: Sentry DSN Error

**Symptoms**:
- Pods crash with `BadDsn: Invalid project in DSN`
- Error: `Invalid project in DSN ('xxxxxxx')`

**Root Cause**:
- Placeholder Sentry DSN value in secrets
- Production settings try to initialize Sentry with invalid DSN

**Solution**:
```bash
# Remove SENTRY_DSN from secrets
kubectl patch secret app-secrets -n jewelry-shop --type='json' \
  -p='[{"op": "remove", "path": "/data/SENTRY_DSN"}]'

# Restart pods
kubectl rollout restart deployment celery-worker celery-beat -n jewelry-shop
```

**Prevention**:
- Production settings check if SENTRY_DSN is set before initializing
- If not set, Sentry is disabled with a warning message
- No crash occurs when SENTRY_DSN is missing

### Issue 3: Redis Connection Error

**Symptoms**:
- Error: `Name or service not known` for `redis-service:6379`
- Workers can't connect to Redis broker

**Root Cause**:
- ConfigMap has incorrect Redis service name
- Should be `redis.jewelry-shop.svc.cluster.local` not `redis-service`

**Solution**:
```bash
# Update ConfigMap
kubectl patch configmap app-config -n jewelry-shop --type='json' -p='[
  {"op": "replace", "path": "/data/REDIS_HOST", "value": "redis.jewelry-shop.svc.cluster.local"},
  {"op": "replace", "path": "/data/CELERY_BROKER_URL", "value": "redis://redis.jewelry-shop.svc.cluster.local:6379/0"},
  {"op": "replace", "path": "/data/CELERY_RESULT_BACKEND", "value": "redis://redis.jewelry-shop.svc.cluster.local:6379/0"}
]'

# Delete pods to pick up new config
kubectl delete pods -n jewelry-shop -l component=celery-worker
kubectl delete pods -n jewelry-shop -l component=celery-beat
```

### Issue 4: Database Authentication Failed

**Symptoms**:
- Error: `password authentication failed`
- Error: `SSL required`

**Root Cause**:
- Using wrong database credentials
- Not using PostgreSQL operator-generated credentials

**Solution**:
Ensure deployment uses correct secret:
```yaml
env:
  - name: POSTGRES_USER
    valueFrom:
      configMapKeyRef:
        name: app-config
        key: DB_USER
  - name: POSTGRES_PASSWORD
    valueFrom:
      secretKeyRef:
        name: jewelry-app.jewelry-shop-db.credentials.postgresql.acid.zalan.do
        key: password
```

### Issue 5: LimitRange Violation

**Symptoms**:
- Error: `cpu max limit to request ratio per Container is 2, but provided ratio is 2.666667`
- Pods fail to create

**Root Cause**:
- Namespace LimitRange enforces max 2:1 CPU limit-to-request ratio
- Initial config had 300m request / 800m limit = 2.67:1 ratio

**Solution**:
```yaml
resources:
  requests:
    cpu: 400m      # Changed from 300m
    memory: 512Mi
  limits:
    cpu: 800m      # 800m / 400m = 2:1 ratio ✓
    memory: 1Gi
```

### Issue 6: Missing Environment Variables

**Symptoms**:
- Error: `FIELD_ENCRYPTION_KEY must be set in production!`
- Error: `DJANGO_SECRET_KEY must be at least 50 characters long`

**Root Cause**:
- Required environment variables missing from secrets
- Production settings validate required variables

**Solution**:
```bash
# Generate and add FIELD_ENCRYPTION_KEY
FIELD_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
kubectl patch secret app-secrets -n jewelry-shop --type='json' \
  -p="[{'op': 'add', 'path': '/data/FIELD_ENCRYPTION_KEY', 'value': '$(echo -n $FIELD_KEY | base64)'}]"

# Generate and add proper DJANGO_SECRET_KEY (50+ characters)
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
kubectl get secret app-secrets -n jewelry-shop -o json | \
  jq ".data.DJANGO_SECRET_KEY = \"$(echo -n $SECRET_KEY | base64 -w0)\"" | \
  kubectl apply -f -
```

## Diagnostic Commands

### Check Pod Status
```bash
# Get all Celery pods
kubectl get pods -n jewelry-shop -l tier=backend | grep celery

# Watch pod status in real-time
kubectl get pods -n jewelry-shop -l component=celery-worker -w

# Get detailed pod information
kubectl describe pod <pod-name> -n jewelry-shop
```

### Check Logs
```bash
# Worker logs
kubectl logs -f <worker-pod> -n jewelry-shop

# Beat logs
kubectl logs -f <beat-pod> -n jewelry-shop

# Init container logs
kubectl logs <pod-name> -n jewelry-shop -c wait-for-dependencies

# Previous container logs (if crashed)
kubectl logs <pod-name> -n jewelry-shop --previous
```

### Check Events
```bash
# Pod events
kubectl get events -n jewelry-shop --field-selector involvedObject.name=<pod-name>

# Deployment events
kubectl get events -n jewelry-shop --field-selector involvedObject.name=celery-worker

# All recent events
kubectl get events -n jewelry-shop --sort-by='.lastTimestamp' | tail -20
```

### Check Configuration
```bash
# ConfigMap values
kubectl get configmap app-config -n jewelry-shop -o yaml

# Secret keys (not values)
kubectl get secret app-secrets -n jewelry-shop -o jsonpath='{.data}' | jq -r 'keys[]'

# Environment variables in pod
kubectl exec <pod-name> -n jewelry-shop -- env | sort
```

### Check Connectivity
```bash
# Test Redis connection
kubectl exec <pod-name> -n jewelry-shop -- nc -zv redis.jewelry-shop.svc.cluster.local 6379

# Test PostgreSQL connection
kubectl exec <pod-name> -n jewelry-shop -- nc -zv jewelry-shop-db-pooler.jewelry-shop.svc.cluster.local 5432

# Test from Django shell
kubectl exec <pod-name> -n jewelry-shop -- python manage.py shell -c "
from django.core.cache import cache
cache.set('test', 'value')
print('Redis OK:', cache.get('test'))
"
```

### Check Resources
```bash
# Resource usage
kubectl top pods -n jewelry-shop -l component=celery-worker

# Resource limits
kubectl get pod <pod-name> -n jewelry-shop -o jsonpath='{.spec.containers[0].resources}'

# Node resources
kubectl top nodes
```

### Check PodDisruptionBudget
```bash
# Get PDB status
kubectl get pdb -n jewelry-shop

# Describe PDB
kubectl describe pdb celery-worker-pdb -n jewelry-shop
```

## Recovery Procedures

### Clean Redeploy
```bash
# 1. Delete deployments
kubectl delete deployment celery-worker celery-beat -n jewelry-shop

# 2. Wait for pods to terminate
kubectl wait --for=delete pod -l tier=backend -n jewelry-shop --timeout=60s

# 3. Verify no pods remain
kubectl get pods -n jewelry-shop -l tier=backend | grep celery

# 4. Redeploy
kubectl apply -f k8s/celery-worker-deployment.yaml
kubectl apply -f k8s/celery-worker-pdb.yaml
kubectl apply -f k8s/celery-beat-deployment.yaml

# 5. Wait for ready
kubectl wait --for=condition=ready pod -l component=celery-worker -n jewelry-shop --timeout=300s
kubectl wait --for=condition=ready pod -l component=celery-beat -n jewelry-shop --timeout=300s
```

### Force Pod Recreation
```bash
# Delete specific pod
kubectl delete pod <pod-name> -n jewelry-shop

# Delete all worker pods
kubectl delete pods -n jewelry-shop -l component=celery-worker

# Rollout restart (graceful)
kubectl rollout restart deployment celery-worker -n jewelry-shop
```

### Update Configuration
```bash
# Update ConfigMap
kubectl edit configmap app-config -n jewelry-shop

# Update Secret
kubectl edit secret app-secrets -n jewelry-shop

# Force pods to pick up changes
kubectl rollout restart deployment celery-worker celery-beat -n jewelry-shop
```

## Performance Tuning

### Increase Worker Concurrency
```yaml
args:
  - "--concurrency=8"  # Increase from 4 to 8
```

### Adjust Resource Limits
```yaml
resources:
  requests:
    cpu: 500m      # Increase if needed
    memory: 1Gi
  limits:
    cpu: 1000m
    memory: 2Gi
```

### Scale Workers
```bash
# Scale to 5 workers
kubectl scale deployment celery-worker -n jewelry-shop --replicas=5

# Update PDB
kubectl patch pdb celery-worker-pdb -n jewelry-shop -p '{"spec":{"minAvailable":3}}'
```

## Monitoring

### Key Metrics to Watch
- Pod restart count
- CPU and memory usage
- Task execution time
- Queue length
- Error rate

### Prometheus Queries
```promql
# Worker pod restarts
rate(kube_pod_container_status_restarts_total{namespace="jewelry-shop",pod=~"celery-worker.*"}[5m])

# CPU usage
rate(container_cpu_usage_seconds_total{namespace="jewelry-shop",pod=~"celery-worker.*"}[5m])

# Memory usage
container_memory_working_set_bytes{namespace="jewelry-shop",pod=~"celery-worker.*"}
```

## Prevention Best Practices

1. **Always use init containers** for dependency checks
2. **Implement PodDisruptionBudgets** for critical services
3. **Use pod anti-affinity** to spread pods across nodes
4. **Set appropriate resource requests** to prevent contention
5. **Configure generous startup probes** for slow-starting apps
6. **Stagger pod startup** to prevent thundering herd
7. **Monitor pod restart rates** to catch issues early
8. **Test configuration changes** in staging first
9. **Use proper secrets management** for credentials
10. **Document all configuration** for team reference

## Support

For additional help:
- Check pod logs: `kubectl logs <pod-name> -n jewelry-shop`
- Check events: `kubectl get events -n jewelry-shop`
- Review documentation: `k8s/QUICK_START_34.8.md`
- Run validation: `bash k8s/scripts/validate-task-34.8.sh`
