# Quick Start Guide: Task 34.11 - Health Checks

## Overview

This guide shows you how to validate and test the comprehensive health check system implemented for all Kubernetes components.

---

## Prerequisites

- k3d cluster running with jewelry-shop namespace
- All deployments running (Django, Nginx, Celery, Redis, PostgreSQL)
- `kubectl` configured to access the cluster
- `curl` and `jq` installed for testing

---

## Quick Validation

### 1. Test Health Endpoints

```bash
# Get a Django pod name
DJANGO_POD=$(kubectl get pods -n jewelry-shop -l component=django -o jsonpath='{.items[0].metadata.name}')

# Port-forward to the pod
kubectl port-forward -n jewelry-shop $DJANGO_POD 8000:8000 &

# Test liveness endpoint
curl http://localhost:8000/health/live/ | jq '.'
# Expected: {"status": "alive"}

# Test readiness endpoint
curl http://localhost:8000/health/ready/ | jq '.'
# Expected: {"status": "ready"}

# Test startup endpoint
curl http://localhost:8000/health/startup/ | jq '.'
# Expected: {"status": "started"}

# Test detailed health check
curl http://localhost:8000/health/detailed/ | jq '.'
# Expected: Detailed JSON with all component statuses

# Kill port-forward
pkill -f "port-forward.*8000"
```

### 2. Verify Probe Configuration

```bash
# Check Django deployment probes
kubectl describe deployment django -n jewelry-shop | grep -A 10 "Liveness\|Readiness\|Startup"

# Check Nginx deployment probes
kubectl describe deployment nginx -n jewelry-shop | grep -A 10 "Liveness\|Readiness"

# Check Celery worker deployment probes
kubectl describe deployment celery-worker -n jewelry-shop | grep -A 10 "Liveness\|Readiness"

# Check Redis StatefulSet probes
kubectl describe statefulset redis -n jewelry-shop | grep -A 10 "Liveness\|Readiness"
```

### 3. Check Pod Health Status

```bash
# List all pods with their ready status
kubectl get pods -n jewelry-shop -o wide

# Check for any pods with failed probes
kubectl get pods -n jewelry-shop --field-selector=status.phase!=Running

# View service endpoints (should show ready pods only)
kubectl get endpoints -n jewelry-shop
```

---

## Automated Validation

### Run Complete Validation Script

```bash
cd k8s/scripts
./validate-health-checks.sh
```

This script will:
1. ✅ Test all health endpoints via port-forward
2. ✅ Verify probe configuration in all deployments
3. ✅ Check pod health status
4. ✅ Verify service endpoints

---

## Failure Scenario Testing

### Test Database Failure and Recovery

```bash
cd k8s/scripts
./test-health-failure-scenarios.sh
```

This script will:
1. ✅ Simulate database failure by scaling PostgreSQL to 0
2. ✅ Verify readiness probe fails
3. ✅ Verify pod is removed from service endpoints
4. ✅ Restore database by scaling back to 3 replicas
5. ✅ Verify readiness probe recovers
6. ✅ Verify pod is added back to service endpoints

### Manual Failure Testing

#### Test Readiness Probe Failure
```bash
# Scale PostgreSQL to 0 (simulate database failure)
kubectl scale statefulset jewelry-shop-db -n jewelry-shop --replicas=0

# Wait 30 seconds for readiness probe to fail
sleep 30

# Check pod status (should show 0/1 Ready)
kubectl get pods -n jewelry-shop -l component=django

# Check service endpoints (should have no ready endpoints)
kubectl get endpoints django -n jewelry-shop

# Restore PostgreSQL
kubectl scale statefulset jewelry-shop-db -n jewelry-shop --replicas=3

# Wait for recovery
kubectl wait --for=condition=ready pod -l application=spilo -n jewelry-shop --timeout=120s

# Wait 30 seconds for readiness probe to recover
sleep 30

# Check pod status (should show 1/1 Ready)
kubectl get pods -n jewelry-shop -l component=django
```

#### Test Liveness Probe Failure
```bash
# Get Django pod name
DJANGO_POD=$(kubectl get pods -n jewelry-shop -l component=django -o jsonpath='{.items[0].metadata.name}')

# Kill Django process (simulate crash)
kubectl exec -it $DJANGO_POD -n jewelry-shop -- pkill -9 gunicorn

# Watch pod status (should restart automatically)
kubectl get pods -n jewelry-shop -w
```

---

## Health Check Endpoints

### Available Endpoints

| Endpoint | Purpose | Used By |
|----------|---------|---------|
| `/health/` | Basic health check | Monitoring, uptime checks |
| `/health/live/` | Liveness probe | Kubernetes liveness probe |
| `/health/ready/` | Readiness probe | Kubernetes readiness probe |
| `/health/startup/` | Startup probe | Kubernetes startup probe |
| `/health/detailed/` | Detailed status | Monitoring dashboards, debugging |

### Endpoint Details

#### `/health/live/`
- **Returns**: `{"status": "alive"}`
- **Status Code**: 200 (always)
- **Purpose**: Verify process is running
- **Kubernetes Action**: Restart pod if fails

#### `/health/ready/`
- **Returns**: `{"status": "ready"}` or `{"status": "not_ready", "reason": "..."}`
- **Status Code**: 200 (ready) or 503 (not ready)
- **Checks**: Database connectivity
- **Kubernetes Action**: Remove from service if fails

#### `/health/startup/`
- **Returns**: `{"status": "started"}` or `{"status": "not_started", "reason": "..."}`
- **Status Code**: 200 (started) or 503 (not started)
- **Checks**: Database and cache connectivity
- **Kubernetes Action**: Restart pod if fails during startup

#### `/health/detailed/`
- **Returns**: Detailed JSON with all component statuses
- **Status Code**: 200 (healthy) or 503 (unhealthy)
- **Checks**: Database, Redis cache, Celery workers
- **Purpose**: Monitoring and debugging

---

## Probe Configuration Summary

### Django Deployment

| Probe | Path | Initial Delay | Period | Timeout | Failure Threshold |
|-------|------|---------------|--------|---------|-------------------|
| Liveness | `/health/live/` | 30s | 10s | 5s | 3 |
| Readiness | `/health/ready/` | 15s | 5s | 3s | 2 |
| Startup | `/health/startup/` | 0s | 10s | 5s | 30 |

### Nginx Deployment

| Probe | Type | Initial Delay | Period | Timeout | Failure Threshold |
|-------|------|---------------|--------|---------|-------------------|
| Liveness | TCP:80 | 15s | 20s | 3s | 3 |
| Readiness | TCP:80 | 5s | 10s | 3s | 3 |

### Celery Worker Deployment

| Probe | Command | Initial Delay | Period | Timeout | Failure Threshold |
|-------|---------|---------------|--------|---------|-------------------|
| Liveness | `pgrep celery` | 180s | 30s | 10s | 3 |
| Readiness | `pgrep celery` | 120s | 15s | 5s | 2 |

### Redis StatefulSet

| Probe | Type/Command | Initial Delay | Period | Timeout | Failure Threshold |
|-------|--------------|---------------|--------|---------|-------------------|
| Liveness | TCP:6379 | 30s | 10s | 5s | 3 |
| Readiness | `redis-cli ping` | 10s | 5s | 3s | 3 |

---

## Troubleshooting

### Pods Not Becoming Ready

```bash
# Check pod events
kubectl describe pod <pod-name> -n jewelry-shop

# Check pod logs
kubectl logs <pod-name> -n jewelry-shop

# Check readiness probe failures
kubectl get events -n jewelry-shop --field-selector involvedObject.name=<pod-name>
```

### Health Endpoints Returning 503

```bash
# Port-forward to pod
kubectl port-forward -n jewelry-shop <pod-name> 8000:8000

# Test detailed endpoint for more info
curl http://localhost:8000/health/detailed/ | jq '.'

# Check database connectivity
kubectl exec -it <pod-name> -n jewelry-shop -- python manage.py dbshell

# Check Redis connectivity
kubectl exec -it <pod-name> -n jewelry-shop -- python manage.py shell
>>> from django.core.cache import cache
>>> cache.set('test', 'value')
>>> cache.get('test')
```

### Pods Restarting Frequently

```bash
# Check restart count
kubectl get pods -n jewelry-shop

# Check pod events for restart reasons
kubectl describe pod <pod-name> -n jewelry-shop

# Check liveness probe configuration
kubectl get deployment <deployment-name> -n jewelry-shop -o yaml | grep -A 10 livenessProbe
```

---

## Monitoring Integration

### Prometheus Metrics

Health check metrics are automatically exposed at `/metrics`:

```bash
# Port-forward to Django pod
kubectl port-forward -n jewelry-shop <django-pod> 8000:8000

# View Prometheus metrics
curl http://localhost:8000/metrics | grep health
```

### Grafana Dashboard

Create a Grafana dashboard to visualize:
- Pod health status over time
- Probe success/failure rates
- Time to recovery after failures
- Service endpoint availability

---

## Next Steps

1. **Monitor health checks** in production
2. **Set up alerts** for repeated probe failures
3. **Create Grafana dashboard** for health visualization
4. **Add custom health checks** for business logic
5. **Implement health checks** for external dependencies

---

## Summary

✅ **Health endpoints implemented** in Django  
✅ **Kubernetes probes configured** for all deployments  
✅ **Validation scripts created** for testing  
✅ **Failure scenarios tested** and verified  
✅ **Documentation completed** with examples  

The health check system provides automatic recovery, zero-downtime deployments, and improved reliability for the jewelry shop SaaS platform.

---

## Quick Reference

```bash
# Test all health endpoints
cd k8s/scripts && ./validate-health-checks.sh

# Test failure scenarios
cd k8s/scripts && ./test-health-failure-scenarios.sh

# Check pod health
kubectl get pods -n jewelry-shop -o wide

# Check service endpoints
kubectl get endpoints -n jewelry-shop

# View pod events
kubectl describe pod <pod-name> -n jewelry-shop

# View pod logs
kubectl logs <pod-name> -n jewelry-shop -f
```
