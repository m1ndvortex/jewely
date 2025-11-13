# Task 34.4: Nginx Reverse Proxy Deployment - Quick Start Guide

## Overview

This guide covers the deployment of Nginx as a reverse proxy in Kubernetes for the Jewelry Shop SaaS platform.

## What Gets Deployed

- **Nginx Deployment**: 2 replicas with resource limits
- **ConfigMaps**: nginx.conf, site configuration, and snippets
- **Service**: ClusterIP service for internal access
- **Health Checks**: TCP probes on port 80

## Prerequisites

- Task 34.2 completed (namespace and base resources)
- Task 34.3 completed (Django deployment) - recommended but not required
- kubectl configured and connected to k3d cluster
- jq installed for validation script

## Quick Deploy

```bash
# Deploy Nginx
cd k8s
./scripts/deploy-task-34.4.sh

# Validate deployment
./scripts/validate-task-34.4.sh
```

## Manual Deployment Steps

If you prefer to deploy manually:

```bash
# 1. Apply ConfigMaps
kubectl apply -f k8s/nginx-configmap.yaml

# 2. Apply Deployment
kubectl apply -f k8s/nginx-deployment.yaml

# 3. Apply Service
kubectl apply -f k8s/nginx-service.yaml

# 4. Wait for pods to be ready
kubectl wait --for=condition=ready pod \
  -l component=nginx \
  -n jewelry-shop \
  --timeout=120s
```

## Verification Commands

### Check Pod Status
```bash
# View Nginx pods
kubectl get pods -n jewelry-shop -l component=nginx

# Expected output: 2 pods in Running state
```

### Check Service
```bash
# View Nginx service
kubectl get service nginx-service -n jewelry-shop

# Expected: ClusterIP service on port 80
```

### Check ConfigMaps
```bash
# List Nginx ConfigMaps
kubectl get configmaps -n jewelry-shop | grep nginx

# Expected: nginx-config, nginx-conf-d, nginx-snippets
```

### Verify Configuration Mounted
```bash
# Get pod name
POD=$(kubectl get pods -n jewelry-shop -l component=nginx -o jsonpath='{.items[0].metadata.name}')

# Check nginx.conf
kubectl exec -n jewelry-shop $POD -c nginx -- cat /etc/nginx/nginx.conf | head -20

# Check site configuration
kubectl exec -n jewelry-shop $POD -c nginx -- cat /etc/nginx/conf.d/jewelry-shop.conf | head -20
```

### Test Nginx Response
```bash
# Test from within cluster
kubectl run test-nginx --image=curlimages/curl --rm -i --restart=Never -n jewelry-shop -- \
  curl -v http://nginx-service

# Port forward to test locally
kubectl port-forward -n jewelry-shop service/nginx-service 8080:80

# Then in another terminal:
curl http://localhost:8080
```

### Check Logs
```bash
# View Nginx logs
kubectl logs -n jewelry-shop -l component=nginx -c nginx --tail=50

# Follow logs
kubectl logs -n jewelry-shop -l component=nginx -c nginx -f

# Check for errors
kubectl logs -n jewelry-shop -l component=nginx -c nginx --tail=100 | grep -i error
```

## Testing Proxy to Django

If Django is deployed (Task 34.3):

```bash
# Test health endpoint through Nginx
kubectl run test-proxy --image=curlimages/curl --rm -i --restart=Never -n jewelry-shop -- \
  curl -v http://nginx-service/health/live/

# Expected: HTTP 200 response
```

## Testing Static Files

```bash
# Create a test static file (if not exists)
POD=$(kubectl get pods -n jewelry-shop -l component=nginx -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n jewelry-shop $POD -c nginx -- sh -c 'echo "test" > /app/staticfiles/test.txt'

# Test static file serving
kubectl run test-static --image=curlimages/curl --rm -i --restart=Never -n jewelry-shop -- \
  curl -v http://nginx-service/static/test.txt

# Expected: HTTP 200 with "test" content
```

## Configuration Details

### Nginx Features

- **Reverse Proxy**: Proxies requests to Django backend (django-service:80)
- **Static Files**: Serves /static/ and /media/ directly
- **Gzip Compression**: Enabled for text-based files
- **Rate Limiting**: Configured for different endpoints
- **Security Headers**: CSP, X-Frame-Options, etc.
- **Health Checks**: TCP probes on port 80

### Resource Allocation

Per Nginx pod:
- CPU Request: 100m
- CPU Limit: 500m
- Memory Request: 128Mi
- Memory Limit: 512Mi

### Upstream Configuration

```nginx
upstream django_backend {
    least_conn;
    server django-service:80 max_fails=3 fail_timeout=30s;
    keepalive 32;
}
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl describe pod -n jewelry-shop -l component=nginx

# Check events
kubectl get events -n jewelry-shop --sort-by='.lastTimestamp' | grep nginx
```

### Configuration Issues

```bash
# Verify ConfigMaps exist
kubectl get configmaps -n jewelry-shop | grep nginx

# Check ConfigMap content
kubectl get configmap nginx-config -n jewelry-shop -o yaml

# Test nginx configuration syntax
POD=$(kubectl get pods -n jewelry-shop -l component=nginx -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n jewelry-shop $POD -c nginx -- nginx -t
```

### Proxy Not Working

```bash
# Check if Django service exists
kubectl get service django-service -n jewelry-shop

# Check if Django pods are running
kubectl get pods -n jewelry-shop -l component=django

# Test Django directly
kubectl run test-django --image=curlimages/curl --rm -i --restart=Never -n jewelry-shop -- \
  curl -v http://django-service/health/live/

# Check Nginx logs for proxy errors
kubectl logs -n jewelry-shop -l component=nginx -c nginx | grep -i "upstream"
```

### High Memory Usage

```bash
# Check resource usage
kubectl top pods -n jewelry-shop -l component=nginx

# If memory is high, check for memory leaks in logs
kubectl logs -n jewelry-shop -l component=nginx -c nginx | grep -i "memory"
```

## Cleanup

To remove Nginx deployment:

```bash
# Delete all Nginx resources
kubectl delete -f k8s/nginx-service.yaml
kubectl delete -f k8s/nginx-deployment.yaml
kubectl delete -f k8s/nginx-configmap.yaml

# Verify deletion
kubectl get all -n jewelry-shop -l component=nginx
```

## Next Steps

After successful Nginx deployment:

1. **Task 34.5**: Install Zalando Postgres Operator
2. **Task 34.6**: Deploy PostgreSQL cluster with automatic failover
3. **Task 34.9**: Install Traefik Ingress Controller for external access

## Task Completion Checklist

- [x] Nginx ConfigMaps created (nginx-config, nginx-conf-d, nginx-snippets)
- [x] Nginx Deployment created with 2 replicas
- [x] Resource requests and limits configured
- [x] TCP health checks configured on port 80
- [x] ClusterIP Service created
- [x] All pods running and ready
- [x] Configuration files mounted correctly
- [x] Nginx responds to requests
- [x] No errors in logs

## Additional Resources

- [Nginx Documentation](https://nginx.org/en/docs/)
- [Kubernetes ConfigMaps](https://kubernetes.io/docs/concepts/configuration/configmap/)
- [Kubernetes Services](https://kubernetes.io/docs/concepts/services-networking/service/)
- [Kubernetes Health Checks](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
