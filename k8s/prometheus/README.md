# Prometheus Deployment for Jewelry SaaS Platform

## Overview

This directory contains Kubernetes manifests for deploying Prometheus to monitor the Jewelry SaaS Platform. Prometheus collects metrics from all services including Django, PostgreSQL, Redis, Nginx, and Celery.

**Task**: 35.1 - Deploy Prometheus  
**Requirement**: 24 - Monitoring and Observability

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Prometheus                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │  Service Discovery (Kubernetes API)                │     │
│  │  - Discovers pods, services, endpoints             │     │
│  │  - Auto-configures scraping targets                │     │
│  └────────────────────────────────────────────────────┘     │
│                          │                                   │
│                          ▼                                   │
│  ┌────────────────────────────────────────────────────┐     │
│  │  Metrics Collection                                 │     │
│  │  - Django: /metrics (django-prometheus)            │     │
│  │  - PostgreSQL: :9187 (postgres_exporter)           │     │
│  │  - Redis: :9121 (redis_exporter)                   │     │
│  │  - Nginx: :9113 (nginx-prometheus-exporter)        │     │
│  │  - Celery: :9808 (celery-exporter)                 │     │
│  │  - Kubernetes: API server, nodes, pods             │     │
│  └────────────────────────────────────────────────────┘     │
│                          │                                   │
│                          ▼                                   │
│  ┌────────────────────────────────────────────────────┐     │
│  │  Time Series Database (TSDB)                       │     │
│  │  - 30 days retention                               │     │
│  │  - 10GB max size                                   │     │
│  │  - Stored in PersistentVolume                      │     │
│  └────────────────────────────────────────────────────┘     │
│                          │                                   │
│                          ▼                                   │
│  ┌────────────────────────────────────────────────────┐     │
│  │  Query API (:9090)                                 │     │
│  │  - PromQL queries                                  │     │
│  │  - Grafana data source                             │     │
│  │  - Web UI                                          │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Prometheus Server
- **Image**: `prom/prometheus:v2.48.0`
- **Replicas**: 1 (single instance)
- **Resources**:
  - Requests: 500m CPU, 1Gi memory
  - Limits: 2000m CPU, 4Gi memory
- **Storage**: 20Gi PersistentVolume
- **Retention**: 30 days or 10GB (whichever comes first)

### 2. Service Discovery
Prometheus automatically discovers targets using Kubernetes service discovery:
- **Pods**: Discovers pods with `prometheus.io/scrape: "true"` annotation
- **Services**: Discovers services with scraping annotations
- **Endpoints**: Discovers service endpoints
- **Nodes**: Discovers Kubernetes nodes

### 3. Scraping Configuration
- **Django**: Scrapes `/metrics` endpoint on port 8000
- **PostgreSQL**: Scrapes postgres_exporter sidecar on port 9187
- **Redis**: Scrapes redis_exporter sidecar on port 9121
- **Nginx**: Scrapes nginx-exporter sidecar on port 9113
- **Celery**: Scrapes celery-exporter sidecar on port 9808
- **Kubernetes**: Scrapes API server, nodes, and pods

## Files

- `prometheus-rbac.yaml` - ServiceAccount, ClusterRole, and ClusterRoleBinding for Kubernetes API access
- `prometheus-configmap.yaml` - Prometheus configuration with service discovery rules
- `prometheus-deployment.yaml` - Deployment and PersistentVolumeClaim
- `prometheus-service.yaml` - ClusterIP service
- `install-prometheus.sh` - Installation script
- `validate-prometheus.sh` - Validation script

## Installation

### Prerequisites

1. Kubernetes cluster (k3d/k3s) is running
2. `jewelry-shop` namespace exists
3. Django application is deployed with django-prometheus configured

### Quick Install

```bash
# Make scripts executable
chmod +x install-prometheus.sh validate-prometheus.sh

# Install Prometheus
./install-prometheus.sh

# Validate installation
./validate-prometheus.sh
```

### Manual Install

```bash
# Apply RBAC resources
kubectl apply -f prometheus-rbac.yaml

# Apply ConfigMap
kubectl apply -f prometheus-configmap.yaml

# Apply Deployment and PVC
kubectl apply -f prometheus-deployment.yaml

# Apply Service
kubectl apply -f prometheus-service.yaml

# Wait for pod to be ready
kubectl wait --for=condition=ready pod -l app=prometheus -n jewelry-shop --timeout=300s
```

## Verification

### 1. Check Pod Status

```bash
kubectl get pods -n jewelry-shop -l app=prometheus
```

Expected output:
```
NAME                          READY   STATUS    RESTARTS   AGE
prometheus-xxxxxxxxxx-xxxxx   1/1     Running   0          2m
```

### 2. Check Service

```bash
kubectl get svc -n jewelry-shop prometheus
```

Expected output:
```
NAME         TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)    AGE
prometheus   ClusterIP   10.43.xxx.xxx   <none>        9090/TCP   2m
```

### 3. Check PVC

```bash
kubectl get pvc -n jewelry-shop prometheus-storage
```

Expected output:
```
NAME                 STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE
prometheus-storage   Bound    pvc-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx   20Gi       RWO            local-path     2m
```

### 4. Access Prometheus UI

```bash
# Port forward to access UI
kubectl port-forward -n jewelry-shop svc/prometheus 9090:9090
```

Then open: http://localhost:9090

### 5. Check Targets

In Prometheus UI:
1. Go to **Status** → **Targets**
2. Verify all targets are being discovered
3. Check that targets are in "UP" state

### 6. Query Metrics

Try these queries in Prometheus UI:

```promql
# Check if all services are up
up

# Django HTTP requests
django_http_requests_total

# Django request latency
django_http_requests_latency_seconds_by_view_method

# Database connections
django_db_connections_total

# Cache operations
django_cache_get_total

# PostgreSQL metrics (if exporter is running)
pg_up

# Redis metrics (if exporter is running)
redis_up
```

## Configuration

### Scrape Intervals

- **Django**: 15 seconds
- **PostgreSQL**: 30 seconds
- **Redis**: 30 seconds
- **Nginx**: 30 seconds
- **Celery**: 30 seconds
- **Kubernetes**: 30 seconds

### Annotations for Service Discovery

To make a service discoverable by Prometheus, add these annotations:

```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8000"
    prometheus.io/path: "/metrics"
```

For pods:

```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8000"
    prometheus.io/path: "/metrics"
```

## Metrics Exposed

### Django Metrics (django-prometheus)

- `django_http_requests_total` - Total HTTP requests
- `django_http_requests_latency_seconds` - Request latency
- `django_http_responses_total_by_status` - Responses by status code
- `django_db_query_duration_seconds` - Database query duration
- `django_db_connections_total` - Database connections
- `django_cache_get_total` - Cache get operations
- `django_cache_hit_total` - Cache hits
- `django_cache_miss_total` - Cache misses

### PostgreSQL Metrics (postgres_exporter)

- `pg_up` - PostgreSQL is up
- `pg_stat_database_*` - Database statistics
- `pg_stat_replication_*` - Replication statistics
- `pg_locks_*` - Lock statistics

### Redis Metrics (redis_exporter)

- `redis_up` - Redis is up
- `redis_connected_clients` - Connected clients
- `redis_used_memory_bytes` - Memory usage
- `redis_commands_total` - Total commands
- `redis_keyspace_hits_total` - Cache hits
- `redis_keyspace_misses_total` - Cache misses

### Nginx Metrics (nginx-prometheus-exporter)

- `nginx_up` - Nginx is up
- `nginx_http_requests_total` - Total HTTP requests
- `nginx_connections_active` - Active connections
- `nginx_connections_reading` - Reading connections
- `nginx_connections_writing` - Writing connections

### Kubernetes Metrics

- `kube_pod_status_phase` - Pod status
- `kube_deployment_status_replicas` - Deployment replicas
- `kube_node_status_condition` - Node conditions
- `container_cpu_usage_seconds_total` - Container CPU usage
- `container_memory_usage_bytes` - Container memory usage

## Troubleshooting

### Prometheus Pod Not Starting

```bash
# Check pod events
kubectl describe pod -n jewelry-shop -l app=prometheus

# Check logs
kubectl logs -n jewelry-shop -l app=prometheus
```

### PVC Not Binding

```bash
# Check PVC status
kubectl describe pvc -n jewelry-shop prometheus-storage

# Check if storage class exists
kubectl get storageclass
```

### No Targets Discovered

```bash
# Check RBAC permissions
kubectl get clusterrolebinding prometheus

# Check if ServiceAccount exists
kubectl get sa -n jewelry-shop prometheus

# Check Prometheus logs for errors
kubectl logs -n jewelry-shop -l app=prometheus | grep -i error
```

### Metrics Not Appearing

1. **Check if Django is exposing metrics**:
   ```bash
   kubectl exec -n jewelry-shop -it <django-pod> -- curl http://localhost:8000/metrics
   ```

2. **Check if service has annotations**:
   ```bash
   kubectl get svc -n jewelry-shop django-service -o yaml | grep prometheus
   ```

3. **Check Prometheus targets**:
   - Access Prometheus UI
   - Go to Status → Targets
   - Look for error messages

### Reload Configuration

If you update the ConfigMap:

```bash
# Reload Prometheus configuration without restart
kubectl exec -n jewelry-shop -it $(kubectl get pod -n jewelry-shop -l app=prometheus -o jsonpath='{.items[0].metadata.name}') -- kill -HUP 1
```

Or restart the pod:

```bash
kubectl rollout restart deployment/prometheus -n jewelry-shop
```

## Next Steps

After deploying Prometheus:

1. **Deploy Grafana** (Task 35.2)
   - Configure Prometheus as data source
   - Import dashboards

2. **Deploy Loki** (Task 35.3)
   - Centralized log aggregation
   - Correlate logs with metrics

3. **Configure Alerting** (Task 35.4)
   - Set up Alertmanager
   - Define alert rules
   - Configure notification channels

4. **Add Exporters**
   - Deploy postgres_exporter sidecar
   - Deploy redis_exporter sidecar
   - Deploy nginx-prometheus-exporter sidecar

## References

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Prometheus Kubernetes SD](https://prometheus.io/docs/prometheus/latest/configuration/configuration/#kubernetes_sd_config)
- [django-prometheus](https://github.com/korfuri/django-prometheus)
- [Requirement 24](../../.kiro/specs/jewelry-saas-platform/requirements.md#requirement-24-monitoring-and-observability)
