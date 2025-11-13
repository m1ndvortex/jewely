# Quick Start Guide: Task 34.8 - Celery Workers and Beat Scheduler

## Overview

This guide provides quick commands and examples for deploying and managing Celery workers and beat scheduler in Kubernetes.

## Prerequisites

- k3d cluster running (task 34.1)
- Namespace and resources created (task 34.2)
- PostgreSQL deployed (task 34.6)
- Redis deployed (task 34.7)
- Docker image built and loaded

## Quick Deploy

```bash
# Deploy Celery workers and beat
./k8s/scripts/deploy-task-34.8.sh

# Validate deployment
./k8s/scripts/validate-task-34.8.sh
```

## Manual Deployment

```bash
# Apply worker deployment
kubectl apply -f k8s/celery-worker-deployment.yaml

# Apply beat deployment
kubectl apply -f k8s/celery-beat-deployment.yaml

# Check status
kubectl get pods -n jewelry-shop -l tier=backend | grep celery
```

## Verification Commands

### Check Pod Status

```bash
# List all Celery pods
kubectl get pods -n jewelry-shop -l tier=backend | grep celery

# Get worker pods
kubectl get pods -n jewelry-shop -l component=celery-worker

# Get beat pod
kubectl get pods -n jewelry-shop -l component=celery-beat

# Watch pods
kubectl get pods -n jewelry-shop -l tier=backend -w | grep celery
```

### Check Logs

```bash
# Worker logs (first pod)
kubectl logs -f $(kubectl get pods -n jewelry-shop -l component=celery-worker -o jsonpath='{.items[0].metadata.name}') -n jewelry-shop

# Beat logs
kubectl logs -f $(kubectl get pods -n jewelry-shop -l component=celery-beat -o jsonpath='{.items[0].metadata.name}') -n jewelry-shop

# All worker logs
kubectl logs -n jewelry-shop -l component=celery-worker --tail=50

# Recent logs from all Celery pods
kubectl logs -n jewelry-shop -l tier=backend --tail=20 | grep -E "celery|beat|worker"
```

### Check Deployments

```bash
# Get deployment status
kubectl get deployment -n jewelry-shop | grep celery

# Describe worker deployment
kubectl describe deployment celery-worker -n jewelry-shop

# Describe beat deployment
kubectl describe deployment celery-beat -n jewelry-shop

# Check replica counts
kubectl get deployment celery-worker -n jewelry-shop -o jsonpath='{.status.replicas}/{.status.readyReplicas}'
```

## Testing

### Test Worker Connectivity

```bash
# Check if workers are connected to Redis
WORKER_POD=$(kubectl get pods -n jewelry-shop -l component=celery-worker -o jsonpath='{.items[0].metadata.name}')
kubectl logs $WORKER_POD -n jewelry-shop --tail=50 | grep -E "Connected|ready"
```

### Test Task Execution

```bash
# Execute a test task
WORKER_POD=$(kubectl get pods -n jewelry-shop -l component=celery-worker -o jsonpath='{.items[0].metadata.name}')

kubectl exec $WORKER_POD -n jewelry-shop -- python manage.py shell -c "
from config.celery import debug_task
result = debug_task.delay()
print(f'Task ID: {result.id}')
"

# Check worker logs for task execution
kubectl logs $WORKER_POD -n jewelry-shop --tail=20
```

### Test Worker Failover

```bash
# Get initial worker count
kubectl get pods -n jewelry-shop -l component=celery-worker

# Delete one worker
WORKER_POD=$(kubectl get pods -n jewelry-shop -l component=celery-worker -o jsonpath='{.items[0].metadata.name}')
kubectl delete pod $WORKER_POD -n jewelry-shop

# Wait and verify new pod is created
sleep 30
kubectl get pods -n jewelry-shop -l component=celery-worker

# Should show 3 workers again
```

### Check Queue Configuration

```bash
# View configured queues
WORKER_POD=$(kubectl get pods -n jewelry-shop -l component=celery-worker -o jsonpath='{.items[0].metadata.name}')
kubectl logs $WORKER_POD -n jewelry-shop --tail=100 | grep -E "celery|backups|pricing|reports|notifications"
```

## Monitoring

### Resource Usage

```bash
# Check resource usage
kubectl top pods -n jewelry-shop -l tier=backend | grep celery

# Detailed resource info
kubectl describe pod $(kubectl get pods -n jewelry-shop -l component=celery-worker -o jsonpath='{.items[0].metadata.name}') -n jewelry-shop | grep -A 5 "Limits\|Requests"
```

### Health Checks

```bash
# Check health probe status
WORKER_POD=$(kubectl get pods -n jewelry-shop -l component=celery-worker -o jsonpath='{.items[0].metadata.name}')
kubectl describe pod $WORKER_POD -n jewelry-shop | grep -A 10 "Liveness\|Readiness"

# Manually test health check
kubectl exec $WORKER_POD -n jewelry-shop -- celery -A config inspect ping
```

### Active Tasks

```bash
# Check active tasks
WORKER_POD=$(kubectl get pods -n jewelry-shop -l component=celery-worker -o jsonpath='{.items[0].metadata.name}')
kubectl exec $WORKER_POD -n jewelry-shop -- celery -A config inspect active

# Check registered tasks
kubectl exec $WORKER_POD -n jewelry-shop -- celery -A config inspect registered
```

## Scaling

### Scale Workers

```bash
# Scale to 5 workers
kubectl scale deployment celery-worker -n jewelry-shop --replicas=5

# Scale back to 3 workers
kubectl scale deployment celery-worker -n jewelry-shop --replicas=3

# Verify scaling
kubectl get deployment celery-worker -n jewelry-shop
```

### Auto-scaling (Future)

```bash
# Create HPA for workers (example)
kubectl autoscale deployment celery-worker -n jewelry-shop \
  --cpu-percent=70 \
  --min=3 \
  --max=10
```

## Troubleshooting

### Workers Not Starting

```bash
# Check pod events
kubectl describe pod $(kubectl get pods -n jewelry-shop -l component=celery-worker -o jsonpath='{.items[0].metadata.name}') -n jewelry-shop

# Check logs for errors
kubectl logs $(kubectl get pods -n jewelry-shop -l component=celery-worker -o jsonpath='{.items[0].metadata.name}') -n jewelry-shop

# Common issues:
# 1. Redis not available - check Redis pods
# 2. Database not available - check PostgreSQL pods
# 3. ConfigMap/Secrets missing - check task 34.2
# 4. Image not found - build and load image
```

### Workers Not Connecting to Redis

```bash
# Check Redis connectivity
WORKER_POD=$(kubectl get pods -n jewelry-shop -l component=celery-worker -o jsonpath='{.items[0].metadata.name}')
kubectl exec $WORKER_POD -n jewelry-shop -- redis-cli -h redis.jewelry-shop.svc.cluster.local ping

# Check Redis service
kubectl get svc redis -n jewelry-shop

# Check environment variables
kubectl exec $WORKER_POD -n jewelry-shop -- env | grep REDIS
```

### Beat Not Scheduling Tasks

```bash
# Check beat logs
BEAT_POD=$(kubectl get pods -n jewelry-shop -l component=celery-beat -o jsonpath='{.items[0].metadata.name}')
kubectl logs $BEAT_POD -n jewelry-shop --tail=50

# Check database connectivity
kubectl exec $BEAT_POD -n jewelry-shop -- python manage.py check

# Verify beat schedule
kubectl exec $BEAT_POD -n jewelry-shop -- python manage.py shell -c "
from django_celery_beat.models import PeriodicTask
print(f'Periodic tasks: {PeriodicTask.objects.count()}')
"
```

### Tasks Not Executing

```bash
# Check worker logs
kubectl logs -n jewelry-shop -l component=celery-worker --tail=100

# Check queue status
WORKER_POD=$(kubectl get pods -n jewelry-shop -l component=celery-worker -o jsonpath='{.items[0].metadata.name}')
kubectl exec $WORKER_POD -n jewelry-shop -- celery -A config inspect stats

# Check for errors in Django
kubectl logs -n jewelry-shop -l component=django --tail=50
```

## Configuration

### Update Worker Concurrency

Edit `k8s/celery-worker-deployment.yaml`:

```yaml
args:
  - "-A"
  - "config"
  - "worker"
  - "--loglevel=info"
  - "--concurrency=8"  # Change from 4 to 8
```

Apply changes:

```bash
kubectl apply -f k8s/celery-worker-deployment.yaml
```

### Add/Remove Queues

Edit `k8s/celery-worker-deployment.yaml`:

```yaml
args:
  - "-Q"
  - "celery,backups,pricing,reports,notifications,accounting,monitoring,webhooks,new-queue"
```

Apply changes:

```bash
kubectl apply -f k8s/celery-worker-deployment.yaml
```

### Update Resource Limits

Edit `k8s/celery-worker-deployment.yaml`:

```yaml
resources:
  requests:
    cpu: 500m      # Increase from 300m
    memory: 1Gi    # Increase from 512Mi
  limits:
    cpu: 1500m     # Increase from 800m
    memory: 2Gi    # Increase from 1Gi
```

Apply changes:

```bash
kubectl apply -f k8s/celery-worker-deployment.yaml
```

## Cleanup

```bash
# Delete Celery deployments
kubectl delete deployment celery-worker celery-beat -n jewelry-shop

# Verify deletion
kubectl get pods -n jewelry-shop -l tier=backend | grep celery
```

## Next Steps

After successful deployment:

1. ✅ Verify all validations pass
2. ✅ Test task execution
3. ✅ Test worker failover
4. ✅ Monitor logs for errors
5. ➡️ Proceed to task 34.9 (Traefik Ingress Controller)

## Useful Commands Reference

```bash
# Quick status check
kubectl get pods,deployments -n jewelry-shop -l tier=backend | grep celery

# Follow all Celery logs
kubectl logs -n jewelry-shop -l tier=backend -f | grep -E "celery|beat|worker"

# Restart all workers
kubectl rollout restart deployment celery-worker -n jewelry-shop

# Restart beat
kubectl rollout restart deployment celery-beat -n jewelry-shop

# Check deployment history
kubectl rollout history deployment celery-worker -n jewelry-shop

# Rollback if needed
kubectl rollout undo deployment celery-worker -n jewelry-shop
```

## Scheduled Tasks

The following tasks are scheduled in Celery beat:

- **Daily full database backup** - 2:00 AM
- **Weekly per-tenant backup** - Sunday 3:00 AM
- **Continuous WAL archiving** - Every hour
- **Configuration backup** - 4:00 AM daily
- **Storage integrity verification** - Every hour
- **Gold rate updates** - Every 5 minutes
- **Inventory price updates** - 2:00 AM daily
- **Report execution** - Every 15 minutes
- **System monitoring** - Every 5 minutes
- **Webhook retries** - Every minute

See `config/celery.py` for complete schedule.

## Support

For issues or questions:
- Check logs: `kubectl logs -n jewelry-shop -l component=celery-worker`
- Review task 34.8 requirements
- Verify prerequisites (Redis, PostgreSQL)
- Check TASK_34.8_COMPLETION_REPORT.md
