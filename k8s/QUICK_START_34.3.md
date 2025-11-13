# Quick Start Guide: Task 34.3 - Deploy Django Application

## Overview

This guide walks you through deploying the Django application to Kubernetes with comprehensive health checks, resource limits, and high availability configuration.

## Prerequisites

- ✅ Task 34.1 completed (k3d cluster running)
- ✅ Task 34.2 completed (namespace, ConfigMap, Secrets created)
- ✅ Docker image built and available
- ✅ kubectl configured and connected to cluster

## What This Task Deploys

1. **Django Deployment**
   - 3 replicas for high availability
   - Resource requests: CPU 500m, Memory 512Mi
   - Resource limits: CPU 1000m, Memory 1Gi
   - Liveness probe: `/health/live/` (every 10s, fail after 3 attempts)
   - Readiness probe: `/health/ready/` (every 5s, fail after 2 attempts)
   - Startup probe: `/health/startup/` (every 10s, 30 attempts max)

2. **Django Service**
   - ClusterIP service (internal only)
   - Port 80 → 8000 (container port)
   - Used by Nginx for reverse proxy

## Quick Deploy

### Option 1: Automated Deployment (Recommended)

```bash
# Run the deployment script
cd k8s
./scripts/deploy-task-34.3.sh
```

The script will:
- ✅ Check prerequisites
- ✅ Deploy Django Deployment and Service
- ✅ Wait for pods to be ready
- ✅ Verify health probes configuration
- ✅ Verify resource limits
- ✅ Display deployment summary

### Option 2: Manual Deployment

```bash
# Apply manifests
kubectl apply -f k8s/django-deployment.yaml
kubectl apply -f k8s/django-service.yaml

# Wait for deployment
kubectl wait --for=condition=available --timeout=300s \
  deployment/django -n jewelry-shop

# Verify
kubectl get pods -n jewelry-shop -l component=django
kubectl get service django-service -n jewelry-shop
```

## Validation

### Automated Validation

```bash
# Run validation script
./scripts/validate-task-34.3.sh
```

The validation script tests:
1. ✅ 3 pods are running
2. ✅ Health probes are configured correctly
3. ✅ Pod self-healing (kills and recreates pod)
4. ✅ Django health check inside pod
5. ✅ Service endpoint connectivity
6. ✅ Resource configuration

### Manual Validation

#### 1. Verify Pod Count

```bash
kubectl get pods -n jewelry-shop -l component=django
```

Expected output: 3 pods with STATUS=Running

#### 2. Verify Health Probes

```bash
# Get pod name
POD_NAME=$(kubectl get pods -n jewelry-shop -l component=django -o jsonpath='{.items[0].metadata.name}')

# Describe pod to see probes
kubectl describe pod $POD_NAME -n jewelry-shop | grep -A 10 "Liveness\|Readiness\|Startup"
```

Expected:
- Liveness: http-get http://:http/health/live/
- Readiness: http-get http://:http/health/ready/
- Startup: http-get http://:http/health/startup/

#### 3. Test Pod Self-Healing

```bash
# Delete a pod
kubectl delete pod $POD_NAME -n jewelry-shop

# Watch pods recreate (should be < 30 seconds)
kubectl get pods -n jewelry-shop -l component=django -w
```

#### 4. Test Django Health

```bash
# Run Django check inside pod
kubectl exec -it $POD_NAME -n jewelry-shop -- python manage.py check
```

#### 5. Test Service Endpoint

```bash
# Get service IP
SERVICE_IP=$(kubectl get service django-service -n jewelry-shop -o jsonpath='{.spec.clusterIP}')

# Test from within cluster
kubectl run test-curl --image=curlimages/curl:latest --rm -i --restart=Never -n jewelry-shop -- \
  curl -v http://$SERVICE_IP/health/
```

Expected: HTTP 200 response

## Monitoring

### Watch Pod Status

```bash
# Watch pods in real-time
kubectl get pods -n jewelry-shop -l component=django -w
```

### View Pod Logs

```bash
# All Django pods
kubectl logs -n jewelry-shop -l component=django --tail=50 -f

# Specific pod
kubectl logs -n jewelry-shop $POD_NAME -f
```

### Check Pod Events

```bash
kubectl get events -n jewelry-shop --sort-by='.lastTimestamp' | grep django
```

### Check Resource Usage

```bash
# Requires metrics-server
kubectl top pods -n jewelry-shop -l component=django
```

## Health Endpoints

The Django application exposes these health endpoints:

### 1. Liveness Probe: `/health/live/`

- **Purpose**: Checks if the process is alive
- **Kubernetes Action**: Restarts pod if fails
- **Check**: Simple process check
- **Response**: `{"status": "alive"}`

### 2. Readiness Probe: `/health/ready/`

- **Purpose**: Checks if app is ready to serve traffic
- **Kubernetes Action**: Removes from service endpoints if fails
- **Checks**: Database connectivity
- **Response**: `{"status": "ready"}` or 503

### 3. Startup Probe: `/health/startup/`

- **Purpose**: Checks if app has completed initialization
- **Kubernetes Action**: Restarts pod if fails during startup
- **Checks**: Database and cache connectivity
- **Response**: `{"status": "started"}` or 503

### 4. Detailed Health: `/health/detailed/`

- **Purpose**: Comprehensive health check for monitoring
- **Checks**: Database, Redis, Celery workers
- **Response**: Detailed JSON with all component statuses

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n jewelry-shop -l component=django

# Check pod events
kubectl describe pod $POD_NAME -n jewelry-shop

# Check logs
kubectl logs $POD_NAME -n jewelry-shop
```

Common issues:
- ConfigMap or Secrets missing → Run task 34.2
- Image pull errors → Check image name in deployment
- Database connection fails → Check database is running

### Health Probes Failing

```bash
# Check probe configuration
kubectl describe pod $POD_NAME -n jewelry-shop | grep -A 5 "Liveness\|Readiness"

# Test health endpoint manually
kubectl exec -it $POD_NAME -n jewelry-shop -- curl http://localhost:8000/health/live/
kubectl exec -it $POD_NAME -n jewelry-shop -- curl http://localhost:8000/health/ready/
kubectl exec -it $POD_NAME -n jewelry-shop -- curl http://localhost:8000/health/startup/
```

### Service Not Accessible

```bash
# Check service exists
kubectl get service django-service -n jewelry-shop

# Check endpoints
kubectl get endpoints django-service -n jewelry-shop

# Test connectivity
kubectl run test-curl --image=curlimages/curl:latest --rm -i --restart=Never -n jewelry-shop -- \
  curl -v http://django-service.jewelry-shop.svc.cluster.local/health/
```

### High Resource Usage

```bash
# Check resource usage
kubectl top pods -n jewelry-shop -l component=django

# Check resource limits
kubectl describe pod $POD_NAME -n jewelry-shop | grep -A 10 "Limits\|Requests"
```

## Configuration Details

### Resource Configuration

```yaml
resources:
  requests:
    cpu: 500m      # 0.5 CPU cores
    memory: 512Mi  # 512 MiB RAM
  limits:
    cpu: 1000m     # 1 CPU core
    memory: 1Gi    # 1 GiB RAM
```

### Probe Configuration

```yaml
livenessProbe:
  httpGet:
    path: /health/live/
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /health/ready/
    port: 8000
  initialDelaySeconds: 15
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 2

startupProbe:
  httpGet:
    path: /health/startup/
    port: 8000
  initialDelaySeconds: 0
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 30  # 300 seconds total
```

## Next Steps

After successful deployment:

1. ✅ Verify all validation tests pass
2. ✅ Monitor pod health for a few minutes
3. ✅ Proceed to **Task 34.4**: Deploy Nginx reverse proxy
4. ✅ Test end-to-end connectivity through Nginx

## Useful Commands

```bash
# Get all Django resources
kubectl get all -n jewelry-shop -l component=django

# Scale deployment
kubectl scale deployment django -n jewelry-shop --replicas=5

# Restart deployment (rolling restart)
kubectl rollout restart deployment django -n jewelry-shop

# Check rollout status
kubectl rollout status deployment django -n jewelry-shop

# View deployment history
kubectl rollout history deployment django -n jewelry-shop

# Rollback to previous version
kubectl rollout undo deployment django -n jewelry-shop

# Port forward to local machine
kubectl port-forward -n jewelry-shop service/django-service 8000:80

# Execute shell in pod
kubectl exec -it $POD_NAME -n jewelry-shop -- /bin/bash

# Copy files from pod
kubectl cp jewelry-shop/$POD_NAME:/app/logs/django.log ./django.log
```

## Success Criteria

✅ 3 Django pods running
✅ All pods show STATUS=Running
✅ Health probes configured correctly
✅ Pod self-healing works (recreates within 30s)
✅ Django health check passes
✅ Service endpoint returns HTTP 200
✅ Resource limits configured correctly

## Support

If you encounter issues:

1. Check pod logs: `kubectl logs -n jewelry-shop -l component=django`
2. Check events: `kubectl get events -n jewelry-shop --sort-by='.lastTimestamp'`
3. Describe pod: `kubectl describe pod $POD_NAME -n jewelry-shop`
4. Run validation script: `./scripts/validate-task-34.3.sh`
5. Review troubleshooting section above

---

**Task 34.3 Status**: Ready for deployment
**Estimated Time**: 5-10 minutes
**Difficulty**: Medium
