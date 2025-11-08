# Kubernetes Deployment for Jewelry Shop SaaS Platform

This directory contains Kubernetes manifests for deploying the Jewelry Shop SaaS Platform to a Kubernetes cluster.

## Architecture Overview

The deployment consists of the following components:

### Application Tier
- **Django Application** (3 replicas): Web application serving the admin and tenant panels
- **Nginx** (2 replicas): Reverse proxy, static file server, and SSL termination
- **Celery Workers** (2 replicas): Background task processing
- **Celery Beat** (1 replica): Periodic task scheduler (singleton)

### Data Tier (Not included - see tasks 34.2 and 34.3)
- **PostgreSQL with Patroni**: High-availability database cluster
- **Redis with Sentinel**: High-availability cache and message broker

### Storage
- **Media PVC** (50Gi): User uploads and product images
- **Static PVC** (10Gi): CSS, JavaScript, and static assets
- **Backups PVC** (100Gi): Database backups and WAL archives

## Prerequisites

1. **Kubernetes Cluster**: v1.24 or higher
2. **kubectl**: Configured to access your cluster
3. **Storage Class**: A storage class that supports ReadWriteMany access mode
4. **Container Registry**: Docker registry with the jewelry-shop image
5. **ConfigMaps and Secrets**: Created as per task 34.6

## Quick Start

### 1. Update Image References

Edit `kustomization.yaml` to point to your container registry:

```yaml
images:
  - name: jewelry-shop
    newName: your-registry.com/jewelry-shop
    newTag: v1.0.0
```

### 2. Create ConfigMaps and Secrets

Before deploying, create the required ConfigMaps and Secrets (task 34.6):

```bash
# Create Django configuration ConfigMap
kubectl create configmap django-config \
  --from-literal=DJANGO_SETTINGS_MODULE=config.settings.production \
  --from-literal=ENVIRONMENT=production \
  --namespace=jewelry-shop

# Create Django secrets
kubectl create secret generic django-secrets \
  --from-literal=SECRET_KEY=your-secret-key \
  --from-literal=DATABASE_URL=postgres://... \
  --from-literal=REDIS_URL=redis://... \
  --namespace=jewelry-shop

# Create Nginx configuration ConfigMaps
kubectl create configmap nginx-config \
  --from-file=nginx.conf=../docker/nginx/nginx.conf \
  --namespace=jewelry-shop

kubectl create configmap nginx-conf-d \
  --from-file=../docker/nginx/conf.d/ \
  --namespace=jewelry-shop

kubectl create configmap nginx-snippets \
  --from-file=../docker/nginx/snippets/ \
  --namespace=jewelry-shop
```

### 3. Deploy to Kubernetes

```bash
# Deploy all resources
kubectl apply -k k8s/

# Or deploy individual resources
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/persistent-volumes.yaml
kubectl apply -f k8s/django-deployment.yaml
kubectl apply -f k8s/django-service.yaml
kubectl apply -f k8s/nginx-deployment.yaml
kubectl apply -f k8s/nginx-service.yaml
kubectl apply -f k8s/celery-worker-deployment.yaml
kubectl apply -f k8s/celery-worker-service.yaml
kubectl apply -f k8s/celery-beat-deployment.yaml
kubectl apply -f k8s/celery-beat-service.yaml
```

### 4. Verify Deployment

```bash
# Check all resources
kubectl get all -n jewelry-shop

# Check pod status
kubectl get pods -n jewelry-shop

# Check services
kubectl get svc -n jewelry-shop

# Check persistent volume claims
kubectl get pvc -n jewelry-shop

# View logs
kubectl logs -n jewelry-shop -l component=django
kubectl logs -n jewelry-shop -l component=celery-worker
kubectl logs -n jewelry-shop -l component=celery-beat
```

### 5. Run Database Migrations

```bash
# Run migrations on one Django pod
kubectl exec -n jewelry-shop -it deployment/django -- python manage.py migrate

# Create superuser
kubectl exec -n jewelry-shop -it deployment/django -- python manage.py createsuperuser

# Collect static files (if not done in build)
kubectl exec -n jewelry-shop -it deployment/django -- python manage.py collectstatic --noinput
```

## Scaling

### Manual Scaling

```bash
# Scale Django pods
kubectl scale deployment django -n jewelry-shop --replicas=5

# Scale Celery workers
kubectl scale deployment celery-worker -n jewelry-shop --replicas=4

# Scale Nginx
kubectl scale deployment nginx -n jewelry-shop --replicas=3
```

### Horizontal Pod Autoscaler (HPA)

HPA configuration is in task 34.4. Example:

```bash
# Create HPA for Django
kubectl autoscale deployment django -n jewelry-shop \
  --cpu-percent=70 \
  --min=3 \
  --max=10
```

## Monitoring

### Health Checks

The deployments include health probes:

- **Liveness Probe**: Restarts pod if unhealthy
- **Readiness Probe**: Stops routing traffic if not ready
- **Startup Probe**: Allows extra time for initial startup

### Endpoints

- Django health: `http://django-service:8000/health/`
- Django liveness: `http://django-service:8000/health/live/`
- Django readiness: `http://django-service:8000/health/ready/`
- Nginx health: `http://nginx-service/health/`

### Prometheus Metrics

All services expose Prometheus metrics:

- Django: `http://django-service:8000/metrics`
- Nginx: `http://nginx-exporter:9113/metrics`
- Celery: Available through Django metrics endpoint

## Troubleshooting

### Pod Not Starting

```bash
# Describe pod to see events
kubectl describe pod <pod-name> -n jewelry-shop

# Check logs
kubectl logs <pod-name> -n jewelry-shop

# Check previous logs if pod restarted
kubectl logs <pod-name> -n jewelry-shop --previous
```

### Database Connection Issues

```bash
# Check if database service is accessible
kubectl exec -n jewelry-shop -it deployment/django -- nc -zv postgres-service 5432

# Check database credentials in secrets
kubectl get secret django-secrets -n jewelry-shop -o yaml
```

### Storage Issues

```bash
# Check PVC status
kubectl get pvc -n jewelry-shop

# Describe PVC to see binding issues
kubectl describe pvc media-pvc -n jewelry-shop

# Check if storage class exists
kubectl get storageclass
```

### Service Not Accessible

```bash
# Check service endpoints
kubectl get endpoints -n jewelry-shop

# Check if pods are ready
kubectl get pods -n jewelry-shop

# Port forward for testing
kubectl port-forward -n jewelry-shop svc/django-service 8000:8000
```

## Rolling Updates

```bash
# Update image
kubectl set image deployment/django django=jewelry-shop:v1.1.0 -n jewelry-shop

# Check rollout status
kubectl rollout status deployment/django -n jewelry-shop

# View rollout history
kubectl rollout history deployment/django -n jewelry-shop

# Rollback to previous version
kubectl rollout undo deployment/django -n jewelry-shop

# Rollback to specific revision
kubectl rollout undo deployment/django -n jewelry-shop --to-revision=2
```

## Resource Management

### View Resource Usage

```bash
# View pod resource usage
kubectl top pods -n jewelry-shop

# View node resource usage
kubectl top nodes
```

### Update Resource Limits

Edit the deployment YAML files and update the `resources` section:

```yaml
resources:
  requests:
    cpu: 500m
    memory: 512Mi
  limits:
    cpu: 2000m
    memory: 2Gi
```

Then apply the changes:

```bash
kubectl apply -f k8s/django-deployment.yaml
```

## Security

### Security Context

All pods run with security contexts:
- Non-root user (UID 1000 for Django/Celery, 101 for Nginx)
- Read-only root filesystem where possible
- Dropped capabilities
- No privilege escalation

### Network Policies

Network policies (task 34.8) restrict traffic between pods:
- Only Nginx can receive external traffic
- Only Django can access database
- Only Django and Celery can access Redis

## Backup and Restore

### Backup

Backups are handled by the Celery workers and stored in the backups PVC:

```bash
# Trigger manual backup
kubectl exec -n jewelry-shop -it deployment/django -- \
  python manage.py trigger_backup --type=full

# View backup files
kubectl exec -n jewelry-shop -it deployment/celery-worker -- \
  ls -lh /backups
```

### Restore

```bash
# Copy backup file to pod
kubectl cp backup.dump jewelry-shop/django-pod:/tmp/

# Restore database
kubectl exec -n jewelry-shop -it deployment/django -- \
  python manage.py restore_backup --file=/tmp/backup.dump
```

## Cleanup

```bash
# Delete all resources
kubectl delete -k k8s/

# Or delete namespace (removes everything)
kubectl delete namespace jewelry-shop
```

## Next Steps

1. **Task 34.2**: Deploy PostgreSQL with Patroni for high availability
2. **Task 34.3**: Deploy Redis with Sentinel for high availability
3. **Task 34.4**: Configure Horizontal Pod Autoscaler
4. **Task 34.5**: Configure Traefik Ingress for SSL termination
5. **Task 34.6**: Create ConfigMaps and Secrets
6. **Task 34.7**: Configure health checks (already included in deployments)
7. **Task 34.8**: Implement network policies

## References

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Django Deployment Best Practices](https://docs.djangoproject.com/en/4.2/howto/deployment/)
- [Celery on Kubernetes](https://docs.celeryproject.org/en/stable/userguide/deployment.html)
- [Nginx Ingress Controller](https://kubernetes.github.io/ingress-nginx/)
