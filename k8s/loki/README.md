# Loki Log Aggregation System

## Overview

This directory contains Kubernetes manifests and scripts for deploying **Loki** and **Promtail** for centralized log aggregation in the jewelry-shop platform.

**Loki** is a horizontally-scalable, highly-available log aggregation system inspired by Prometheus. It is designed to be cost-effective and easy to operate, as it does not index the contents of the logs, but rather a set of labels for each log stream.

**Promtail** is an agent which ships the contents of local logs to a Loki instance. It runs as a DaemonSet on every node in the cluster.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                        │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │  Node 1  │  │  Node 2  │  │  Node 3  │                  │
│  │          │  │          │  │          │                  │
│  │ Promtail │  │ Promtail │  │ Promtail │  (DaemonSet)     │
│  │    │     │  │    │     │  │    │     │                  │
│  └────┼─────┘  └────┼─────┘  └────┼─────┘                  │
│       │             │             │                         │
│       └─────────────┼─────────────┘                         │
│                     │                                        │
│                     ▼                                        │
│              ┌─────────────┐                                │
│              │    Loki     │  (Deployment)                  │
│              │             │                                │
│              │  - Ingester │                                │
│              │  - Querier  │                                │
│              │  - Storage  │                                │
│              └─────────────┘                                │
│                     │                                        │
│                     ▼                                        │
│              ┌─────────────┐                                │
│              │   Grafana   │  (Visualization)               │
│              └─────────────┘                                │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Loki
- **Purpose**: Log aggregation and storage
- **Deployment**: Single replica (can be scaled for production)
- **Storage**: 10Gi PersistentVolume
- **Retention**: 31 days (744 hours)
- **Ports**: 
  - 3100 (HTTP API)
  - 9096 (gRPC)

### 2. Promtail
- **Purpose**: Log collection agent
- **Deployment**: DaemonSet (runs on every node)
- **Collection**: Scrapes logs from all pods in jewelry-shop namespace
- **Parsing**: Supports multiple log formats (JSON, CRI, custom regex)
- **Port**: 9080 (metrics)

### 3. Log Sources
Promtail collects logs from:
- Django application pods
- Celery worker pods
- Nginx pods
- PostgreSQL pods
- Redis pods
- All other pods in the jewelry-shop namespace

## Files

- `loki-configmap.yaml` - Loki configuration
- `loki-deployment.yaml` - Loki deployment, service, and PVC
- `promtail-configmap.yaml` - Promtail configuration with log parsing rules
- `promtail-daemonset.yaml` - Promtail DaemonSet
- `promtail-rbac.yaml` - RBAC for Promtail (ServiceAccount, ClusterRole, ClusterRoleBinding)
- `loki-datasource.yaml` - Grafana datasource configuration
- `install-loki.sh` - Installation script
- `validate-loki.sh` - Validation script
- `test-loki-comprehensive.sh` - Comprehensive test suite

## Installation

### Prerequisites
- Kubernetes cluster (k3d/k3s)
- kubectl configured
- jewelry-shop namespace created
- Grafana deployed (optional, for visualization)

### Quick Start

```bash
# Install Loki and Promtail
./install-loki.sh

# Validate deployment
./validate-loki.sh

# Run comprehensive tests
./test-loki-comprehensive.sh
```

### Manual Installation

```bash
# 1. Deploy Loki
kubectl apply -f loki-configmap.yaml
kubectl apply -f loki-deployment.yaml

# 2. Deploy Promtail
kubectl apply -f promtail-rbac.yaml
kubectl apply -f promtail-configmap.yaml
kubectl apply -f promtail-daemonset.yaml

# 3. Configure Grafana datasource
kubectl apply -f loki-datasource.yaml

# 4. Restart Grafana to load datasource
kubectl rollout restart deployment/grafana -n jewelry-shop
```

## Usage

### Querying Logs

#### Using kubectl port-forward

```bash
# Forward Loki port
kubectl port-forward -n jewelry-shop svc/loki 3100:3100

# Query labels
curl http://localhost:3100/loki/api/v1/labels

# Query logs
curl 'http://localhost:3100/loki/api/v1/query?query={namespace="jewelry-shop"}&limit=100'
```

#### Using Grafana Explore

1. Access Grafana dashboard
2. Navigate to **Explore** (compass icon)
3. Select **Loki** as the datasource
4. Enter LogQL queries

### LogQL Query Examples

```logql
# All logs from jewelry-shop namespace
{namespace="jewelry-shop"}

# Django application logs
{app="django"}

# Error logs from Django
{app="django"} |= "error"

# Celery task logs
{app="celery-worker"} |= "task"

# Nginx access logs with status >= 400
{app="nginx"} | json | status >= 400

# PostgreSQL errors
{application="spilo"} |= "ERROR"

# Logs from specific pod
{pod="django-deployment-abc123"}

# Logs with specific label and time range
{app="django", level="error"} | json | line_format "{{.message}}"

# Count errors per minute
sum(count_over_time({app="django"} |= "error" [1m])) by (pod)
```

## Log Retention

- **Retention Period**: 31 days (744 hours)
- **Compaction**: Runs every 10 minutes
- **Storage**: Logs are stored in `/loki` directory in the pod
- **Cleanup**: Automatic deletion after retention period

## Monitoring

### Loki Metrics

Loki exposes Prometheus metrics on port 3100:

```bash
kubectl port-forward -n jewelry-shop svc/loki 3100:3100
curl http://localhost:3100/metrics
```

Key metrics:
- `loki_ingester_chunks_created_total` - Total chunks created
- `loki_ingester_received_chunks` - Chunks received
- `loki_distributor_bytes_received_total` - Bytes received
- `loki_request_duration_seconds` - Request duration

### Promtail Metrics

Promtail exposes metrics on port 9080:

```bash
PROMTAIL_POD=$(kubectl get pods -n jewelry-shop -l app=promtail -o jsonpath='{.items[0].metadata.name}')
kubectl port-forward -n jewelry-shop $PROMTAIL_POD 9080:9080
curl http://localhost:9080/metrics
```

Key metrics:
- `promtail_sent_entries_total` - Total log entries sent
- `promtail_dropped_entries_total` - Dropped entries
- `promtail_read_bytes_total` - Bytes read from logs
- `promtail_targets_active_total` - Active targets

## Troubleshooting

### Loki pod not starting

```bash
# Check pod status
kubectl get pods -n jewelry-shop -l app=loki

# Check pod logs
kubectl logs -n jewelry-shop -l app=loki

# Check events
kubectl get events -n jewelry-shop --sort-by='.lastTimestamp'

# Check PVC
kubectl get pvc loki-storage -n jewelry-shop
```

### Promtail not collecting logs

```bash
# Check DaemonSet status
kubectl get daemonset promtail -n jewelry-shop

# Check Promtail logs
kubectl logs -n jewelry-shop -l app=promtail

# Check RBAC permissions
kubectl get serviceaccount promtail -n jewelry-shop
kubectl get clusterrole promtail
kubectl get clusterrolebinding promtail
```

### No logs appearing in Loki

```bash
# Check if Promtail is sending logs
kubectl logs -n jewelry-shop -l app=promtail | grep "sent"

# Check Loki ingestion
kubectl exec -n jewelry-shop <loki-pod> -- wget -q -O- http://localhost:3100/metrics | grep ingester_received

# Verify log paths are correct
kubectl exec -n jewelry-shop <promtail-pod> -- ls -la /var/log/pods/
```

### Grafana not showing Loki datasource

```bash
# Check datasource ConfigMap
kubectl get configmap loki-datasource -n jewelry-shop

# Restart Grafana
kubectl rollout restart deployment/grafana -n jewelry-shop

# Check Grafana logs
kubectl logs -n jewelry-shop -l app=grafana
```

## Performance Tuning

### For High Log Volume

Edit `loki-configmap.yaml`:

```yaml
limits_config:
  ingestion_rate_mb: 50  # Increase from 10
  ingestion_burst_size_mb: 100  # Increase from 20
  max_query_series: 1000  # Increase from 500
```

### For Better Query Performance

```yaml
query_range:
  cache_results: true
  results_cache:
    cache:
      enable_fifocache: true
      fifocache:
        max_size_bytes: 1GB  # Increase from 500MB
```

## Security

- Loki runs as non-root user (UID 10001)
- Promtail requires root access to read logs (runs as UID 0)
- RBAC configured with minimal required permissions
- No authentication enabled (internal cluster use only)

## Backup and Recovery

### Backup Loki Data

```bash
# Backup PVC data
kubectl exec -n jewelry-shop <loki-pod> -- tar czf /tmp/loki-backup.tar.gz /loki
kubectl cp jewelry-shop/<loki-pod>:/tmp/loki-backup.tar.gz ./loki-backup.tar.gz
```

### Restore Loki Data

```bash
# Copy backup to pod
kubectl cp ./loki-backup.tar.gz jewelry-shop/<loki-pod>:/tmp/

# Extract backup
kubectl exec -n jewelry-shop <loki-pod> -- tar xzf /tmp/loki-backup.tar.gz -C /
```

## Scaling

### Scale Loki (Production)

For production, consider using Loki in microservices mode:

```yaml
# Separate components
- Distributor (receives logs)
- Ingester (writes to storage)
- Querier (handles queries)
- Query Frontend (caching layer)
```

### Scale Promtail

Promtail automatically scales as a DaemonSet - one pod per node.

## Integration with Alerting

Create alert rules in Grafana based on log patterns:

```yaml
# Example: Alert on high error rate
- alert: HighErrorRate
  expr: |
    sum(rate({app="django"} |= "error" [5m])) > 10
  annotations:
    summary: High error rate detected
```

## References

- [Loki Documentation](https://grafana.com/docs/loki/latest/)
- [LogQL Query Language](https://grafana.com/docs/loki/latest/logql/)
- [Promtail Configuration](https://grafana.com/docs/loki/latest/clients/promtail/)
- [Grafana Loki Best Practices](https://grafana.com/docs/loki/latest/best-practices/)
