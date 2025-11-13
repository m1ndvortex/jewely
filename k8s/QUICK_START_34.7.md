# Quick Start: Task 34.7 - Redis Cluster with Sentinel

## Overview

This guide provides quick instructions for deploying and using the Redis cluster with Sentinel for high availability in the jewelry-shop Kubernetes cluster.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Redis Cluster                             │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │ redis-0  │  │ redis-1  │  │ redis-2  │                  │
│  │ (Master) │  │ (Replica)│  │ (Replica)│                  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                  │
│       │             │             │                         │
│       └─────────────┴─────────────┘                         │
│                     │                                        │
│                     │ Monitored by                           │
│                     ▼                                        │
│  ┌──────────────────────────────────────────┐               │
│  │         Redis Sentinel Cluster           │               │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐          │
│  │  │ sentinel-0 │ │ sentinel-1 │ │ sentinel-2 │          │
│  │  └────────────┘ └────────────┘ └────────────┘          │
│  │         Quorum = 2 (2/3 must agree)          │          │
│  └──────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

## Features

- **High Availability**: 3 Redis instances with automatic failover
- **Persistence**: RDB snapshots + AOF for data durability
- **Automatic Failover**: Sentinel detects failures and promotes new master within 30 seconds
- **Quorum-based**: Requires 2/3 Sentinels to agree before failover
- **Monitoring**: Prometheus exporters for Redis and Sentinel metrics
- **Stable DNS**: Headless service provides stable pod DNS names

## Prerequisites

- Kubernetes cluster (k3d/k3s) running
- Namespace `jewelry-shop` created (Task 34.2)
- kubectl configured and connected

## Quick Deploy

```bash
# Deploy Redis cluster
cd k8s
./scripts/deploy-task-34.7.sh

# Validate deployment
./scripts/validate-task-34.7.sh

# Optional: Test failover (destructive)
./scripts/validate-task-34.7.sh --test-failover
```

## Manual Deployment

```bash
# 1. Deploy ConfigMap
kubectl apply -f redis-configmap.yaml

# 2. Deploy Redis StatefulSet
kubectl apply -f redis-statefulset.yaml

# 3. Deploy Sentinel StatefulSet
kubectl apply -f redis-sentinel-statefulset.yaml

# 4. Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=redis -n jewelry-shop --timeout=300s
```

## Verification

### Check Pod Status

```bash
# Check Redis pods
kubectl get pods -n jewelry-shop -l app=redis,component=server

# Check Sentinel pods
kubectl get pods -n jewelry-shop -l app=redis,component=sentinel

# Check all Redis resources
kubectl get all -n jewelry-shop -l app=redis
```

### Check Replication Status

```bash
# Check master (redis-0 initially)
kubectl exec redis-0 -n jewelry-shop -c redis -- redis-cli info replication

# Check replica
kubectl exec redis-1 -n jewelry-shop -c redis -- redis-cli info replication
```

### Check Sentinel Status

```bash
# Get master information from Sentinel
kubectl exec redis-sentinel-0 -n jewelry-shop -c sentinel -- \
  redis-cli -p 26379 sentinel master mymaster

# Get replica information
kubectl exec redis-sentinel-0 -n jewelry-shop -c sentinel -- \
  redis-cli -p 26379 sentinel replicas mymaster

# Get sentinel information
kubectl exec redis-sentinel-0 -n jewelry-shop -c sentinel -- \
  redis-cli -p 26379 sentinel sentinels mymaster
```

## Testing

### Basic Connectivity Test

```bash
# Set a key
kubectl exec redis-0 -n jewelry-shop -c redis -- \
  redis-cli set test-key "Hello Redis"

# Get the key
kubectl exec redis-0 -n jewelry-shop -c redis -- \
  redis-cli get test-key

# Read from replica
kubectl exec redis-1 -n jewelry-shop -c redis -- \
  redis-cli get test-key
```

### Test Persistence

```bash
# Set a key
kubectl exec redis-0 -n jewelry-shop -c redis -- \
  redis-cli set persistent-key "This should survive restart"

# Restart the pod
kubectl delete pod redis-0 -n jewelry-shop

# Wait for pod to restart
kubectl wait --for=condition=ready pod redis-0 -n jewelry-shop --timeout=60s

# Verify key still exists
kubectl exec redis-0 -n jewelry-shop -c redis -- \
  redis-cli get persistent-key
```

### Test Automatic Failover

```bash
# 1. Identify current master
kubectl exec redis-sentinel-0 -n jewelry-shop -c sentinel -- \
  redis-cli -p 26379 sentinel get-master-addr-by-name mymaster

# 2. Delete master pod (assuming redis-0 is master)
kubectl delete pod redis-0 -n jewelry-shop

# 3. Watch Sentinel logs for failover
kubectl logs -f redis-sentinel-0 -n jewelry-shop -c sentinel

# 4. Check new master (should be redis-1 or redis-2)
kubectl exec redis-sentinel-0 -n jewelry-shop -c sentinel -- \
  redis-cli -p 26379 sentinel get-master-addr-by-name mymaster

# 5. Verify all pods are running
kubectl get pods -n jewelry-shop -l app=redis,component=server
```

## Django Integration

### Update Django Settings

```python
# config/settings/base.py

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://mymaster/0',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.SentinelClient',
            'SENTINELS': [
                ('redis-sentinel-0.redis-sentinel-headless.jewelry-shop.svc.cluster.local', 26379),
                ('redis-sentinel-1.redis-sentinel-headless.jewelry-shop.svc.cluster.local', 26379),
                ('redis-sentinel-2.redis-sentinel-headless.jewelry-shop.svc.cluster.local', 26379),
            ],
            'SENTINEL_KWARGS': {
                'service_name': 'mymaster',
                'socket_timeout': 0.1,
            },
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
        }
    }
}

# Celery broker with Sentinel
CELERY_BROKER_URL = 'sentinel://redis-sentinel-0.redis-sentinel-headless.jewelry-shop.svc.cluster.local:26379;sentinel://redis-sentinel-1.redis-sentinel-headless.jewelry-shop.svc.cluster.local:26379;sentinel://redis-sentinel-2.redis-sentinel-headless.jewelry-shop.svc.cluster.local:26379'
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'master_name': 'mymaster',
    'sentinel_kwargs': {
        'socket_timeout': 0.1,
    },
}
```

### Test from Django Pod

```bash
# Connect to Django pod
kubectl exec -it <django-pod-name> -n jewelry-shop -- python manage.py shell

# In Django shell
from django.core.cache import cache

# Set a value
cache.set('test_key', 'Hello from Django', 300)

# Get the value
print(cache.get('test_key'))

# Test Celery
from celery import current_app
print(current_app.connection().as_uri())
```

## Monitoring

### View Logs

```bash
# Redis logs
kubectl logs -f redis-0 -n jewelry-shop -c redis

# Sentinel logs
kubectl logs -f redis-sentinel-0 -n jewelry-shop -c sentinel

# All Redis logs
kubectl logs -f -l app=redis,component=server -n jewelry-shop -c redis

# All Sentinel logs
kubectl logs -f -l app=redis,component=sentinel -n jewelry-shop -c sentinel
```

### Prometheus Metrics

```bash
# Redis metrics (from redis-exporter sidecar)
kubectl port-forward redis-0 -n jewelry-shop 9121:9121
# Access: http://localhost:9121/metrics

# Sentinel metrics (from sentinel-exporter sidecar)
kubectl port-forward redis-sentinel-0 -n jewelry-shop 9355:9355
# Access: http://localhost:9355/metrics
```

### Check Resource Usage

```bash
# CPU and memory usage
kubectl top pods -n jewelry-shop -l app=redis

# Storage usage
kubectl get pvc -n jewelry-shop -l app=redis
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod events
kubectl describe pod redis-0 -n jewelry-shop

# Check logs
kubectl logs redis-0 -n jewelry-shop -c redis
kubectl logs redis-0 -n jewelry-shop -c config  # init container
```

### Replication Not Working

```bash
# Check master status
kubectl exec redis-0 -n jewelry-shop -c redis -- redis-cli info replication

# Check replica status
kubectl exec redis-1 -n jewelry-shop -c redis -- redis-cli info replication

# Check network connectivity
kubectl exec redis-1 -n jewelry-shop -c redis -- \
  redis-cli -h redis-0.redis-headless.jewelry-shop.svc.cluster.local ping
```

### Sentinel Not Monitoring

```bash
# Check Sentinel configuration
kubectl exec redis-sentinel-0 -n jewelry-shop -c sentinel -- \
  cat /etc/redis/sentinel.conf

# Check Sentinel logs
kubectl logs redis-sentinel-0 -n jewelry-shop -c sentinel

# Manually check master
kubectl exec redis-sentinel-0 -n jewelry-shop -c sentinel -- \
  redis-cli -p 26379 sentinel masters
```

### Failover Not Happening

```bash
# Check Sentinel quorum
kubectl exec redis-sentinel-0 -n jewelry-shop -c sentinel -- \
  redis-cli -p 26379 sentinel master mymaster | grep quorum

# Check number of sentinels
kubectl exec redis-sentinel-0 -n jewelry-shop -c sentinel -- \
  redis-cli -p 26379 sentinel sentinels mymaster

# Check Sentinel logs for errors
kubectl logs -l app=redis,component=sentinel -n jewelry-shop -c sentinel --tail=100
```

### Data Not Persisting

```bash
# Check PVC status
kubectl get pvc -n jewelry-shop -l app=redis

# Check if data directory is mounted
kubectl exec redis-0 -n jewelry-shop -c redis -- ls -la /data

# Check persistence configuration
kubectl exec redis-0 -n jewelry-shop -c redis -- redis-cli config get save
kubectl exec redis-0 -n jewelry-shop -c redis -- redis-cli config get appendonly
```

## Maintenance

### Backup Redis Data

```bash
# Trigger RDB snapshot
kubectl exec redis-0 -n jewelry-shop -c redis -- redis-cli bgsave

# Check last save time
kubectl exec redis-0 -n jewelry-shop -c redis -- redis-cli lastsave

# Copy RDB file from pod
kubectl cp jewelry-shop/redis-0:/data/dump.rdb ./redis-backup-$(date +%Y%m%d).rdb -c redis
```

### Scale Redis (Not Recommended)

```bash
# Note: Scaling Redis requires careful planning
# This is just for reference, not recommended without proper testing

# Scale to 5 replicas
kubectl scale statefulset redis -n jewelry-shop --replicas=5

# Update Sentinel to monitor new replicas (manual intervention required)
```

### Update Redis Configuration

```bash
# Edit ConfigMap
kubectl edit configmap redis-config -n jewelry-shop

# Restart pods to apply changes
kubectl rollout restart statefulset redis -n jewelry-shop
kubectl rollout restart statefulset redis-sentinel -n jewelry-shop
```

## Cleanup

```bash
# Delete Redis cluster
kubectl delete statefulset redis redis-sentinel -n jewelry-shop

# Delete services
kubectl delete svc redis redis-headless redis-sentinel redis-sentinel-headless -n jewelry-shop

# Delete ConfigMap
kubectl delete configmap redis-config -n jewelry-shop

# Delete PVCs (WARNING: This deletes all data)
kubectl delete pvc -l app=redis -n jewelry-shop
```

## Connection Information

### Internal (from within cluster)

- **Redis Master**: `redis-0.redis-headless.jewelry-shop.svc.cluster.local:6379`
- **Redis Service**: `redis.jewelry-shop.svc.cluster.local:6379`
- **Sentinel**: `redis-sentinel.jewelry-shop.svc.cluster.local:26379`

### External (port-forward)

```bash
# Redis
kubectl port-forward redis-0 -n jewelry-shop 6379:6379
# Connect: redis-cli -h localhost -p 6379

# Sentinel
kubectl port-forward redis-sentinel-0 -n jewelry-shop 26379:26379
# Connect: redis-cli -h localhost -p 26379
```

## Performance Tuning

### Adjust Memory Limits

```yaml
# Edit redis-statefulset.yaml
resources:
  requests:
    memory: 512Mi  # Increase if needed
  limits:
    memory: 1Gi    # Increase if needed
```

### Adjust Persistence Settings

```yaml
# Edit redis-configmap.yaml
# More frequent snapshots (more I/O)
save 300 10
save 60 1000

# Less frequent snapshots (less I/O)
save 900 1
save 3600 1
```

### Adjust Sentinel Timing

```yaml
# Edit redis-configmap.yaml
# Faster failover (more sensitive)
sentinel down-after-milliseconds mymaster 3000
sentinel failover-timeout mymaster 20000

# Slower failover (less sensitive)
sentinel down-after-milliseconds mymaster 10000
sentinel failover-timeout mymaster 60000
```

## Next Steps

1. ✅ Redis cluster deployed and validated
2. ⏭️ Update Django settings to use Sentinel
3. ⏭️ Deploy Celery workers (Task 34.8)
4. ⏭️ Test end-to-end application with Redis
5. ⏭️ Set up monitoring dashboards for Redis metrics

## References

- [Redis Sentinel Documentation](https://redis.io/docs/management/sentinel/)
- [Redis Persistence](https://redis.io/docs/management/persistence/)
- [django-redis with Sentinel](https://github.com/jazzband/django-redis#sentinel-support)
- [Kubernetes StatefulSets](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
