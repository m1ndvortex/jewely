# Kubernetes Quick Reference Guide

## Essential Commands

### Deployment
```bash
# Deploy everything
kubectl apply -k k8s/

# Deploy with script
./k8s/deploy.sh

# Validate deployment
./k8s/validate.sh
```

### Status Checks
```bash
# All resources
kubectl get all -n jewelry-shop

# Pods
kubectl get pods -n jewelry-shop -o wide

# Services
kubectl get svc -n jewelry-shop

# Deployments
kubectl get deployments -n jewelry-shop

# PVCs
kubectl get pvc -n jewelry-shop
```

### Logs
```bash
# Django logs
kubectl logs -n jewelry-shop -l component=django -f --tail=100

# Celery worker logs
kubectl logs -n jewelry-shop -l component=celery-worker -f --tail=100

# Celery beat logs
kubectl logs -n jewelry-shop -l component=celery-beat -f --tail=100

# Nginx logs
kubectl logs -n jewelry-shop -l component=nginx -f --tail=100

# All logs
kubectl logs -n jewelry-shop --all-containers=true -f
```

### Exec into Pods
```bash
# Django shell
kubectl exec -n jewelry-shop -it deployment/django -- python manage.py shell

# Bash in Django pod
kubectl exec -n jewelry-shop -it deployment/django -- bash

# Celery worker bash
kubectl exec -n jewelry-shop -it deployment/celery-worker -- bash
```

### Scaling
```bash
# Scale Django
kubectl scale deployment django -n jewelry-shop --replicas=5

# Scale Celery workers
kubectl scale deployment celery-worker -n jewelry-shop --replicas=4

# Scale Nginx
kubectl scale deployment nginx -n jewelry-shop --replicas=3
```

### Updates
```bash
# Update image
kubectl set image deployment/django django=jewelry-shop:v1.1.0 -n jewelry-shop

# Check rollout status
kubectl rollout status deployment/django -n jewelry-shop

# Rollout history
kubectl rollout history deployment/django -n jewelry-shop

# Rollback
kubectl rollout undo deployment/django -n jewelry-shop
```

### Port Forwarding
```bash
# Django
kubectl port-forward -n jewelry-shop svc/django-service 8000:8000

# Nginx
kubectl port-forward -n jewelry-shop svc/nginx-service 8080:80
```

### Resource Usage
```bash
# Pod metrics
kubectl top pods -n jewelry-shop

# Node metrics
kubectl top nodes
```

### Troubleshooting
```bash
# Describe pod
kubectl describe pod <pod-name> -n jewelry-shop

# Events
kubectl get events -n jewelry-shop --sort-by='.lastTimestamp'

# Previous logs (if restarted)
kubectl logs <pod-name> -n jewelry-shop --previous
```

### Cleanup
```bash
# Delete all resources
kubectl delete -k k8s/

# Delete namespace (removes everything)
kubectl delete namespace jewelry-shop
```

## Component Endpoints

### Health Checks
- Django: `http://django-service:8000/health/`
- Django Liveness: `http://django-service:8000/health/live/`
- Django Readiness: `http://django-service:8000/health/ready/`
- Django Detailed: `http://django-service:8000/health/detailed/`

### Metrics
- Django: `http://django-service:8000/metrics`
- Nginx: `http://nginx-exporter:9113/metrics`

## Default Replicas

- Django: 3
- Nginx: 2
- Celery Worker: 2
- Celery Beat: 1 (must be 1)

## Resource Limits

### Django
- CPU: 500m-2000m
- Memory: 512Mi-2Gi

### Nginx
- CPU: 100m-500m
- Memory: 128Mi-512Mi

### Celery Worker
- CPU: 500m-2000m
- Memory: 512Mi-2Gi

### Celery Beat
- CPU: 100m-500m
- Memory: 256Mi-512Mi

## Storage

- Media: 50Gi (ReadWriteMany)
- Static: 10Gi (ReadWriteMany)
- Backups: 100Gi (ReadWriteMany)

## Common Issues

### Pods Pending
- Check PVC binding: `kubectl get pvc -n jewelry-shop`
- Check node resources: `kubectl top nodes`
- Check events: `kubectl get events -n jewelry-shop`

### Pods CrashLoopBackOff
- Check logs: `kubectl logs <pod-name> -n jewelry-shop`
- Check previous logs: `kubectl logs <pod-name> -n jewelry-shop --previous`
- Check secrets: `kubectl get secret django-secrets -n jewelry-shop`

### Service Not Accessible
- Check endpoints: `kubectl get endpoints -n jewelry-shop`
- Check pod status: `kubectl get pods -n jewelry-shop`
- Port forward: `kubectl port-forward -n jewelry-shop svc/django-service 8000:8000`

### Database Connection Failed
- Check if database service exists: `kubectl get svc postgres-service -n jewelry-shop`
- Check database credentials in secrets
- Test connection: `kubectl exec -n jewelry-shop -it deployment/django -- nc -zv postgres-service 5432`
