# Prometheus Quick Start Guide

## Installation

```bash
# Navigate to prometheus directory
cd k8s/prometheus

# Make scripts executable
chmod +x install-prometheus.sh validate-prometheus.sh

# Install Prometheus
./install-prometheus.sh

# Validate installation
./validate-prometheus.sh
```

## Access Prometheus UI

```bash
# Port forward to access UI
kubectl port-forward -n jewelry-shop svc/prometheus 9090:9090
```

Then open: http://localhost:9090

## Quick Checks

### Check Pod Status
```bash
kubectl get pods -n jewelry-shop -l app=prometheus
```

### Check Service
```bash
kubectl get svc -n jewelry-shop prometheus
```

### Check Storage
```bash
kubectl get pvc -n jewelry-shop prometheus-storage
```

### Check Logs
```bash
kubectl logs -n jewelry-shop -l app=prometheus -f
```

## Useful Queries

### Check Service Health
```promql
up
```

### Django Metrics
```promql
# Total HTTP requests
django_http_requests_total

# Request latency
django_http_requests_latency_seconds_by_view_method

# Database connections
django_db_connections_total

# Cache hits/misses
rate(django_cache_hit_total[5m])
rate(django_cache_miss_total[5m])
```

### Kubernetes Metrics
```promql
# Pod status
kube_pod_status_phase{namespace="jewelry-shop"}

# Container CPU usage
rate(container_cpu_usage_seconds_total{namespace="jewelry-shop"}[5m])

# Container memory usage
container_memory_usage_bytes{namespace="jewelry-shop"}
```

## Troubleshooting

### Prometheus Not Starting
```bash
# Check pod events
kubectl describe pod -n jewelry-shop -l app=prometheus

# Check logs
kubectl logs -n jewelry-shop -l app=prometheus
```

### No Targets Discovered
```bash
# Check RBAC
kubectl get clusterrolebinding prometheus

# Check ServiceAccount
kubectl get sa -n jewelry-shop prometheus

# Check for errors in logs
kubectl logs -n jewelry-shop -l app=prometheus | grep -i error
```

### Reload Configuration
```bash
# After updating ConfigMap
kubectl exec -n jewelry-shop -it $(kubectl get pod -n jewelry-shop -l app=prometheus -o jsonpath='{.items[0].metadata.name}') -- kill -HUP 1
```

## Next Steps

1. Deploy Grafana (Task 35.2)
2. Add exporter sidecars (postgres_exporter, redis_exporter, nginx-exporter)
3. Configure alerting (Task 35.4)
4. Deploy Loki for logs (Task 35.3)

## Documentation

- Full documentation: [README.md](README.md)
- Completion report: [TASK_35.1_COMPLETION_REPORT.md](TASK_35.1_COMPLETION_REPORT.md)
