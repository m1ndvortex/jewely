# Task 34.10: Configure Horizontal Pod Autoscaler with Aggressive Scaling

## Overview

This task implements Horizontal Pod Autoscaler (HPA) for Django pods with aggressive scale-up and gradual scale-down policies to handle traffic spikes efficiently.

## Configuration

### HPA Settings
- **Min Replicas**: 3 (high availability baseline)
- **Max Replicas**: 10 (handle peak loads)
- **CPU Threshold**: 70% (scale up when CPU exceeds 70%)
- **Memory Threshold**: 80% (scale up when memory exceeds 80%)

### Scaling Behavior
- **Scale-Up**: Aggressive
  - 100% increase every 15 seconds
  - Maximum 2 pods per 15 seconds
  - No stabilization window (immediate response)
  
- **Scale-Down**: Gradual
  - 50% decrease every 60 seconds
  - 5-minute stabilization window before scaling down
  - Conservative approach to prevent flapping

## Prerequisites

- Kubernetes cluster running (k3d or k3s)
- Django deployment already deployed
- kubectl configured and connected to cluster

## Installation Steps

### Step 1: Install Metrics Server

Metrics Server is required for HPA to collect CPU and memory metrics.

```bash
# Run the installation script
./k8s/scripts/install-metrics-server.sh
```

**What it does:**
- Installs metrics-server from official release
- Patches it for k3d/k3s compatibility (insecure TLS)
- Waits for metrics-server to be ready
- Verifies metrics are being collected

**Validation:**
```bash
# Check metrics-server is running
kubectl get deployment metrics-server -n kube-system

# Verify node metrics are available
kubectl top nodes

# Verify pod metrics are available
kubectl top pods -n jewelry-shop
```

### Step 2: Deploy Django HPA

```bash
# Apply the HPA manifest
kubectl apply -f k8s/django-hpa.yaml
```

**What it creates:**
- HorizontalPodAutoscaler for Django deployment
- PodDisruptionBudget to ensure minimum availability

**Validation:**
```bash
# Check HPA is created
kubectl get hpa -n jewelry-shop

# View detailed HPA configuration
kubectl describe hpa django-hpa -n jewelry-shop

# Watch HPA in real-time
kubectl get hpa django-hpa -n jewelry-shop --watch
```

### Step 3: Verify Current State

```bash
# Check current replica count
kubectl get deployment django -n jewelry-shop

# Check current pod metrics
kubectl top pods -n jewelry-shop -l component=django

# Check HPA status
kubectl get hpa django-hpa -n jewelry-shop
```

Expected output:
```
NAME         REFERENCE           TARGETS                        MINPODS   MAXPODS   REPLICAS   AGE
django-hpa   Deployment/django   cpu: 15%/70%, memory: 25%/80%  3         10        3          1m
```

## Testing

### Automated Test

Run the comprehensive test script:

```bash
# Run the full HPA test
./k8s/scripts/test-django-hpa.sh
```

**What it does:**
1. Verifies HPA configuration
2. Checks current metrics and replica count
3. Generates load for 3 minutes
4. Monitors scale-up behavior (3 → 10 pods)
5. Monitors scale-down behavior (10 → 3 pods)
6. Cleans up test resources

### Manual Testing

#### Test Scale-Up

```bash
# Generate load manually
kubectl run -it load-generator --rm --image=busybox --restart=Never -n jewelry-shop -- /bin/sh -c "while true; do wget -q -O- http://django-service.jewelry-shop.svc.cluster.local:80/; done"

# In another terminal, watch HPA scale up
kubectl get hpa django-hpa -n jewelry-shop --watch

# Watch pods being created
kubectl get pods -n jewelry-shop -l component=django --watch
```

**Expected behavior:**
- Pods should scale from 3 to 10 as CPU/memory increases
- Scale-up should be aggressive (doubling every 15s or +2 pods per 15s)
- New pods should become ready within 30-60 seconds

#### Test Scale-Down

```bash
# Stop the load generator (Ctrl+C)

# Watch HPA scale down
kubectl get hpa django-hpa -n jewelry-shop --watch
```

**Expected behavior:**
- HPA waits 5 minutes (stabilization window) before scaling down
- Then scales down by 50% every 60 seconds
- Eventually returns to 3 pods (minimum)

## Monitoring

### Real-Time Monitoring

```bash
# Watch HPA status
kubectl get hpa django-hpa -n jewelry-shop --watch

# Watch pod metrics
watch kubectl top pods -n jewelry-shop -l component=django

# Watch deployment replica count
watch kubectl get deployment django -n jewelry-shop
```

### Check Scaling Events

```bash
# View HPA events
kubectl describe hpa django-hpa -n jewelry-shop | grep -A 10 Events

# View deployment events
kubectl describe deployment django -n jewelry-shop | grep -A 10 Events
```

## Troubleshooting

### Metrics Not Available

**Problem:** `kubectl top pods` returns "Metrics not available"

**Solution:**
```bash
# Check metrics-server is running
kubectl get pods -n kube-system -l k8s-app=metrics-server

# Check metrics-server logs
kubectl logs -n kube-system -l k8s-app=metrics-server

# Restart metrics-server
kubectl rollout restart deployment metrics-server -n kube-system

# Wait 1-2 minutes for metrics to be collected
```

### HPA Not Scaling

**Problem:** HPA shows "unknown" for metrics or doesn't scale

**Solution:**
```bash
# Check HPA status
kubectl describe hpa django-hpa -n jewelry-shop

# Verify resource requests are set in deployment
kubectl get deployment django -n jewelry-shop -o yaml | grep -A 5 resources

# Check if pods are ready
kubectl get pods -n jewelry-shop -l component=django

# Verify metrics are available
kubectl top pods -n jewelry-shop -l component=django
```

### Pods Not Scaling Up Fast Enough

**Problem:** Scale-up is slower than expected

**Check:**
```bash
# Verify HPA behavior configuration
kubectl get hpa django-hpa -n jewelry-shop -o yaml | grep -A 20 behavior

# Check if there are resource constraints
kubectl describe nodes

# Check if PodDisruptionBudget is blocking
kubectl get pdb -n jewelry-shop
```

### Pods Not Scaling Down

**Problem:** Pods stay at high count even after load stops

**This is expected!** The HPA has a 5-minute stabilization window before scaling down. Wait at least 5 minutes after load stops.

```bash
# Check time since last scale event
kubectl describe hpa django-hpa -n jewelry-shop | grep -A 5 "Last Scale Time"

# If it's been more than 5 minutes, check for ongoing load
kubectl top pods -n jewelry-shop -l component=django
```

## Validation Checklist

- [ ] Metrics-server installed and running
- [ ] `kubectl top nodes` shows node metrics
- [ ] `kubectl top pods -n jewelry-shop` shows pod metrics
- [ ] HPA created: `kubectl get hpa django-hpa -n jewelry-shop`
- [ ] HPA shows current CPU/memory usage
- [ ] Current replica count is 3 (minimum)
- [ ] Load test scales pods from 3 to 10
- [ ] Scale-up is aggressive (15-second intervals)
- [ ] Scale-down waits 5 minutes after load stops
- [ ] Scale-down is gradual (50% every 60s)
- [ ] Pods return to 3 replicas after scale-down

## Performance Expectations

### Scale-Up Performance
- **Time to detect high load**: 15 seconds (HPA evaluation interval)
- **Time to add 2 pods**: 15 seconds (policy period)
- **Time to scale from 3 to 10 pods**: ~60 seconds (4 scale events)
- **Time for new pods to be ready**: 30-60 seconds (startup probe)
- **Total time to full capacity**: ~2 minutes

### Scale-Down Performance
- **Stabilization window**: 5 minutes (300 seconds)
- **Scale-down rate**: 50% every 60 seconds
- **Time to scale from 10 to 3 pods**: ~6-7 minutes total
  - 5 minutes stabilization
  - 1-2 minutes for gradual scale-down

## Integration with Other Components

### Pod Disruption Budget
The HPA works with PodDisruptionBudget to ensure:
- At least 2 pods always available during voluntary disruptions
- Node drains and updates don't break service availability
- Rolling updates maintain service continuity

### Resource Requests/Limits
HPA uses resource requests to calculate utilization:
- CPU request: 500m (HPA scales at 350m usage = 70%)
- Memory request: 512Mi (HPA scales at 410Mi usage = 80%)

### Health Probes
HPA only counts healthy pods:
- Liveness probe: Restarts unhealthy pods
- Readiness probe: Removes unhealthy pods from service
- Startup probe: Allows time for slow initialization

## Best Practices

1. **Monitor HPA behavior** in production for the first few days
2. **Adjust thresholds** based on actual traffic patterns
3. **Set appropriate resource requests** for accurate scaling
4. **Use PodDisruptionBudget** to prevent service disruption
5. **Test scaling** regularly to ensure it works as expected
6. **Monitor costs** as more pods = more resources

## Next Steps

After completing this task:
- [ ] Monitor HPA behavior in production
- [ ] Adjust scaling thresholds if needed
- [ ] Implement similar HPA for Celery workers (already done)
- [ ] Set up alerts for scaling events
- [ ] Document scaling patterns and costs

## Related Tasks

- Task 34.3: Deploy Django application with health checks
- Task 34.8: Deploy Celery workers (has similar HPA)
- Task 35.1: Deploy Prometheus (for advanced metrics)

## References

- [Kubernetes HPA Documentation](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [HPA Walkthrough](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale-walkthrough/)
- [Metrics Server](https://github.com/kubernetes-sigs/metrics-server)
