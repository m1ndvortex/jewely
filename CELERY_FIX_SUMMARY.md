# Celery Deployment Issues - Analysis & Solutions

## Current Status
- ❌ Celery workers crash after loading tasks  
- ❌ Celery beat crashes on startup
- ✅ Redis connectivity working
- ✅ Database connectivity working  
- ✅ Django app loads successfully
- ✅ All tasks discovered and registered

## Issues Fixed
1. ✅ SENTRY_DSN warning suppressed
2. ✅ Health probe delays increased (180s liveness, 120s readiness)
3. ✅ Startup probe removed (was killing pods prematurely)
4. ✅ Pod staggering improved (deterministic 5-25s delay)
5. ✅ Security context relaxed for testing

## Root Cause Analysis

### Symptoms
- Celery prints full task list banner
- Process exits immediately after (within 1-2 seconds)
- Exit code 0 (clean exit, not error)
- No error messages in logs
- Happens with solo, threads, and prefork pools

### Investigation Results
```
Testing completed:
- ✅ Redis connection: PING successful
- ✅ Task autodiscovery: 48 tasks found
- ✅ Django settings: Load successfully  
- ❌ Worker loop: Never starts

Log pattern:
1. Django startup messages
2. Celery banner with config
3. Full task list printed
4. [STOPS HERE] - No "ready" or "connected" message
5. Process exits silently
```

### Likely Root Causes

**Primary Suspect:** Celery prefork pool failing to spawn worker processes
- Containers have limited capabilities (no CAP_SYS_ADMIN)
- Security context may prevent fork()
- Resource limits too restrictive for multiple processes
- Missing /dev/shm or shared memory access

**Secondary Issues:**
- Silent failure mode in Celery when worker pool initialization fails
- No stderr output captured when process exits during pool setup
- Possible billiard (multiprocessing library) incompatibility

## Recommended Solutions

### Option 1: Use gevent Pool (Recommended for K8s)
```yaml
command: ["celery"]
args:
  - "-A"
  - "config"
  - "worker"
  - "--loglevel=info"
  - "--pool=gevent"
  - "--concurrency=100"  # gevent can handle many concurrent tasks
  - "-Q"
  - "celery,backups,pricing,reports,notifications,accounting,monitoring,webhooks"
```

**Pros:**
- Single process, no forking required
- Works well in containers with limited capabilities
- Can handle high concurrency with cooperative multitasking
- Used successfully by many production Django+Celery deployments

**Cons:**
- Requires `gevent` library installed
- Tasks must be I/O-bound (not CPU-bound)

**Installation:**
```dockerfile
RUN pip install gevent
```

### Option 2: Use eventlet Pool
```yaml
command: ["celery"]
args:
  - "-A"
  - "config"
  - "worker"
  - "--loglevel=info"
  - "--pool=eventlet"
  - "--concurrency=100"
  - "-Q"
  - "celery,backups,pricing,reports,notifications,accounting,monitoring,webhooks"
```

**Pros:**
- Similar benefits to gevent
- Alternative if gevent doesn't work

**Cons:**
- Requires `eventlet` library
- Some compatibility issues with newer Python versions

### Option 3: Fix prefork with Capabilities
Add to deployment:
```yaml
securityContext:
  capabilities:
    add:
      - SYS_RESOURCE
      - IPC_LOCK
```

Mount /dev/shm:
```yaml
volumeMounts:
  - name: dshm
    mountPath: /dev/shm
volumes:
  - name: dshm
    emptyDir:
      medium: Memory
      sizeLimit: 128Mi
```

### Option 4: Run Celery outside container process manager
Use `sh -c` wrapper to capture all output:
```yaml
command: ["/bin/sh", "-c"]
args:
  - |
    celery -A config worker \
      --loglevel=debug \
      --pool=prefork \
      --concurrency=4 \
      -Q celery,backups,pricing,reports,notifications,accounting,monitoring,webhooks \
      2>&1 | tee /tmp/celery.log
    echo "Exit code: $?"
    tail -f /tmp/celery.log
```

## Next Steps

### Immediate Actions
1. **Try gevent pool** (fastest fix, most compatible with K8s)
2. **Check Docker image** - Ensure gevent is installed
3. **Test locally** - Run same command outside K8s to isolate issue

### Testing Procedure
```bash
# 1. Install gevent in image
pip install gevent

# 2. Update deployment
kubectl apply -f k8s/celery-worker-deployment.yaml

# 3. Monitor logs
kubectl logs -f -l component=celery-worker -n jewelry-shop

# Expected output should include:
# - Task list (already working)
# - "celery@hostname ready" message
# - No crashes/restarts
```

### Validation Steps (from Requirements 34.8)
Once workers are running:

```bash
# ✓ Verify 3 worker pods running
kubectl get pods -n jewelry-shop -l component=celery-worker

# ✓ Verify 1 beat pod running  
kubectl get pods -n jewelry-shop -l component=celery-beat

# ✓ Check logs for Redis connection
kubectl logs -n jewelry-shop -l component=celery-worker --tail=50 | grep "connected to redis"

# ✓ Trigger test task
kubectl exec -n jewelry-shop <django-pod> -- python manage.py shell -c "
from apps.core.data_tasks import cleanup_old_exports
result = cleanup_old_exports.delay()
print(f'Task ID: {result.id}')
"

# ✓ Kill worker and verify task redistribution
kubectl delete pod -n jewelry-shop <worker-pod-name>
# Watch logs to see task picked up by another worker

# ✓ Check worker resource usage
kubectl top pods -n jewelry-shop -l component=celery-worker
```

## Files Modified
- `k8s/celery-worker-deployment.yaml` - Health probes, security context, command
- `k8s/celery-beat-deployment.yaml` - Health probes, SENTRY_DSN

## Additional Resources
- [Celery in Docker](https://docs.celeryproject.org/en/stable/userguide/daemonizing.html)
- [Gevent Pool Documentation](https://docs.celeryproject.org/en/stable/userguide/concurrency/gevent.html)
- [Kubernetes Best Practices for Celery](https://learnk8s.io/deploying-celery-to-kubernetes)

## Contact Points
If gevent doesn't work, we need to:
1. Check if there are any Django signals or middleware interfering
2. Test Celery command directly in a pod without K8s overhead
3. Review Celery app configuration in `config/celery.py`
4. Check for any custom Celery beat schedule or periodic task issues
