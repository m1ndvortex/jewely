# Grafana Deployment for Jewelry SaaS Platform

## Overview

This directory contains Kubernetes manifests for deploying Grafana to visualize metrics from the Jewelry SaaS Platform. Grafana provides beautiful dashboards for monitoring Django applications, PostgreSQL databases, Redis caches, and Kubernetes infrastructure.

**Task**: 35.2 - Deploy Grafana  
**Requirement**: 24 - Monitoring and Observability

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Grafana                               │
│  ┌────────────────────────────────────────────────────┐     │
│  │  Data Sources                                       │     │
│  │  • Prometheus (http://prometheus:9090)             │     │
│  │  • Future: Loki for logs                           │     │
│  └────────────────────────────────────────────────────┘     │
│                          │                                   │
│                          ▼                                   │
│  ┌────────────────────────────────────────────────────┐     │
│  │  Pre-configured Dashboards                         │     │
│  │  • System Overview                                 │     │
│  │  • Application Performance                         │     │
│  │  • Database Performance                            │     │
│  │  • Infrastructure Health                           │     │
│  └────────────────────────────────────────────────────┘     │
│                          │                                   │
│                          ▼                                   │
│  ┌────────────────────────────────────────────────────┐     │
│  │  Visualization Engine                              │     │
│  │  • Time series graphs                              │     │
│  │  • Gauges and stats                                │     │
│  │  • Tables and heatmaps                             │     │
│  │  • Alerts and annotations                          │     │
│  └────────────────────────────────────────────────────┘     │
│                          │                                   │
│                          ▼                                   │
│  ┌────────────────────────────────────────────────────┐     │
│  │  Web UI (:3000)                                    │     │
│  │  • Dashboard viewer                                │     │
│  │  • Query editor                                    │     │
│  │  • Admin interface                                 │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Grafana Server
- **Image**: `grafana/grafana:10.2.2`
- **Replicas**: 1 (single instance)
- **Resources**:
  - Requests: 250m CPU, 512Mi memory
  - Limits: 1000m CPU, 2Gi memory
- **Storage**: 2Gi PersistentVolume for dashboards and data
- **Port**: 3000 (HTTP)

### 2. Data Sources
- **Prometheus**: Pre-configured to connect to `http://prometheus:9090`
- **Auto-provisioned**: Configured via ConfigMap, no manual setup needed
- **Default**: Set as the default data source

### 3. Pre-built Dashboards

#### System Overview Dashboard
- Total HTTP requests per second
- HTTP request latency (p95)
- HTTP status code distribution
- Active pods count
- CPU and memory usage
- Database connections

#### Application Performance Dashboard
- Request rate by Django view
- Request latency by view (p95)
- Database query duration
- Cache hit rate
- Error rate (5xx responses)
- Active database connections

#### Database Performance Dashboard
- PostgreSQL status
- Active connections
- Transaction rate (commits/rollbacks)
- Database size
- Lock statistics
- Replication lag
- Cache hit ratio

#### Infrastructure Health Dashboard
- Pod status (Running/Pending/Failed)
- Node CPU usage
- Node memory usage
- Container CPU usage by pod
- Container memory usage by pod
- Network I/O
- Disk I/O
- Pod restart count

## Files

- `grafana-secrets.yaml` - Admin credentials and secret key
- `grafana-configmap.yaml` - Grafana configuration and data source provisioning
- `grafana-dashboards.yaml` - Pre-built dashboard definitions
- `grafana-deployment.yaml` - Deployment and PersistentVolumeClaim
- `grafana-service.yaml` - ClusterIP service
- `install-grafana.sh` - Installation script
- `validate-grafana.sh` - Validation script
- `README.md` - This file

## Installation

### Prerequisites

1. Kubernetes cluster (k3d/k3s) is running
2. `jewelry-shop` namespace exists
3. Prometheus is deployed and running (recommended but not required)

### Quick Install

```bash
# Make scripts executable
chmod +x install-grafana.sh validate-grafana.sh

# Install Grafana
./install-grafana.sh

# Validate installation
./validate-grafana.sh
```

### Manual Install

```bash
# Apply secrets
kubectl apply -f grafana-secrets.yaml

# Apply ConfigMaps
kubectl apply -f grafana-configmap.yaml
kubectl apply -f grafana-dashboards.yaml

# Apply Deployment and PVC
kubectl apply -f grafana-deployment.yaml

# Apply Service
kubectl apply -f grafana-service.yaml

# Wait for pod to be ready
kubectl wait --for=condition=ready pod -l app=grafana -n jewelry-shop --timeout=300s
```

## Accessing Grafana

### Port Forward Method

```bash
# Forward port 3000 to localhost
kubectl port-forward -n jewelry-shop svc/grafana 3000:3000

# Open in browser
open http://localhost:3000
```

### Default Credentials

```
Username: admin
Password: admin123!@#
```

**⚠️ IMPORTANT**: Change these credentials immediately in production!

### First Login

1. Open http://localhost:3000
2. Login with default credentials
3. You'll be prompted to change the password (recommended)
4. Navigate to **Dashboards** → **Browse**
5. Open the **Jewelry Shop** folder
6. Explore the pre-configured dashboards

## Verification

### 1. Check Pod Status

```bash
kubectl get pods -n jewelry-shop -l app=grafana
```

Expected output:
```
NAME                       READY   STATUS    RESTARTS   AGE
grafana-xxxxxxxxxx-xxxxx   1/1     Running   0          2m
```

### 2. Check Service

```bash
kubectl get svc -n jewelry-shop grafana
```

Expected output:
```
NAME      TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)    AGE
grafana   ClusterIP   10.43.xxx.xxx   <none>        3000/TCP   2m
```

### 3. Check PVC

```bash
kubectl get pvc -n jewelry-shop grafana-storage
```

Expected output:
```
NAME              STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE
grafana-storage   Bound    pvc-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx   10Gi       RWO            local-path     2m
```

### 4. Test HTTP Response

```bash
kubectl exec -n jewelry-shop -it $(kubectl get pod -n jewelry-shop -l app=grafana -o jsonpath='{.items[0].metadata.name}') -- wget -q -O - http://localhost:3000/api/health
```

Expected output:
```json
{
  "commit": "...",
  "database": "ok",
  "version": "10.2.2"
}
```

### 5. Verify Prometheus Data Source

In Grafana UI:
1. Go to **Configuration** → **Data Sources**
2. Click on **Prometheus**
3. Scroll down and click **Save & Test**
4. Should see: "Data source is working"

### 6. Test Dashboards

1. Go to **Dashboards** → **Browse**
2. Open **Jewelry Shop** folder
3. Click on **System Overview**
4. Verify that panels are loading data
5. If no data appears, check if Prometheus is collecting metrics

## Configuration

### Changing Admin Password

#### Method 1: Via UI
1. Login to Grafana
2. Click on user icon → **Profile**
3. Click **Change Password**

#### Method 2: Via Secret
```bash
# Edit the secret
kubectl edit secret grafana-secrets -n jewelry-shop

# Update the admin-password field (base64 encoded)
# Then restart Grafana
kubectl rollout restart deployment/grafana -n jewelry-shop
```

### Adding New Dashboards

#### Method 1: Via UI
1. Login to Grafana
2. Click **+** → **Dashboard**
3. Add panels and configure queries
4. Click **Save dashboard**

#### Method 2: Via ConfigMap
1. Create a new ConfigMap with dashboard JSON
2. Mount it in the deployment
3. Restart Grafana

Example:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-dashboard-custom
  namespace: jewelry-shop
data:
  custom.json: |
    {
      "dashboard": {
        "title": "My Custom Dashboard",
        ...
      }
    }
```

### Configuring Additional Data Sources

Edit `grafana-configmap.yaml` and add to the `datasources.yaml` section:

```yaml
- name: Loki
  type: loki
  access: proxy
  url: http://loki:3100
  editable: false
```

Then apply and restart:
```bash
kubectl apply -f grafana-configmap.yaml
kubectl rollout restart deployment/grafana -n jewelry-shop
```

## Dashboard Queries

### Common PromQL Queries

#### HTTP Request Rate
```promql
sum(rate(django_http_requests_total[5m]))
```

#### Request Latency (p95)
```promql
histogram_quantile(0.95, sum(rate(django_http_requests_latency_seconds_bucket[5m])) by (le))
```

#### Error Rate
```promql
sum(rate(django_http_responses_total_by_status{status=~"5.."}[5m]))
```

#### Database Query Time
```promql
rate(django_db_query_duration_seconds_sum[5m]) / rate(django_db_query_duration_seconds_count[5m])
```

#### Cache Hit Rate
```promql
rate(django_cache_hit_total[5m]) / (rate(django_cache_hit_total[5m]) + rate(django_cache_miss_total[5m])) * 100
```

#### Pod CPU Usage
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="jewelry-shop"}[5m])) by (pod)
```

#### Pod Memory Usage
```promql
sum(container_memory_usage_bytes{namespace="jewelry-shop"}) by (pod)
```

## Troubleshooting

### Grafana Pod Not Starting

```bash
# Check pod events
kubectl describe pod -n jewelry-shop -l app=grafana

# Check logs
kubectl logs -n jewelry-shop -l app=grafana

# Common issues:
# - PVC not binding: Check storage class
# - Image pull errors: Check image name and registry
# - Permission errors: Check securityContext settings
```

### PVC Not Binding

```bash
# Check PVC status
kubectl describe pvc -n jewelry-shop grafana-storage

# Check if storage class exists
kubectl get storageclass

# For k3d/k3s, local-path should be available
kubectl get storageclass local-path
```

### No Data in Dashboards

1. **Check if Prometheus is running**:
   ```bash
   kubectl get pods -n jewelry-shop -l app=prometheus
   ```

2. **Check if Prometheus data source is working**:
   - Go to Configuration → Data Sources → Prometheus
   - Click "Save & Test"
   - Should see "Data source is working"

3. **Check if Prometheus has metrics**:
   ```bash
   kubectl port-forward -n jewelry-shop svc/prometheus 9090:9090
   # Open http://localhost:9090
   # Try query: up
   ```

4. **Check if Django is exposing metrics**:
   ```bash
   kubectl exec -n jewelry-shop -it <django-pod> -- curl http://localhost:8000/metrics
   ```

### Cannot Access Grafana UI

```bash
# Check if service exists
kubectl get svc grafana -n jewelry-shop

# Check if pod is running
kubectl get pods -n jewelry-shop -l app=grafana

# Check if port-forward is working
kubectl port-forward -n jewelry-shop svc/grafana 3000:3000

# Try accessing from within cluster
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- curl http://grafana.jewelry-shop.svc.cluster.local:3000/api/health
```

### Dashboards Not Loading

```bash
# Check if dashboard ConfigMaps exist
kubectl get configmap -n jewelry-shop | grep dashboard

# Check if dashboards are mounted
kubectl exec -n jewelry-shop -it $(kubectl get pod -n jewelry-shop -l app=grafana -o jsonpath='{.items[0].metadata.name}') -- ls -la /var/lib/grafana/dashboards/jewelry-shop/

# Check Grafana logs for provisioning errors
kubectl logs -n jewelry-shop -l app=grafana | grep -i "dashboard\|provision"
```

### Reset Grafana

If you need to start fresh:

```bash
# Delete everything
kubectl delete -f grafana-service.yaml
kubectl delete -f grafana-deployment.yaml
kubectl delete -f grafana-dashboards.yaml
kubectl delete -f grafana-configmap.yaml
kubectl delete -f grafana-secrets.yaml

# Delete PVC (this will delete all data!)
kubectl delete pvc grafana-storage -n jewelry-shop

# Reinstall
./install-grafana.sh
```

## Customization

### Adding Plugins

Edit `grafana-deployment.yaml` and add to the `GF_INSTALL_PLUGINS` environment variable:

```yaml
- name: GF_INSTALL_PLUGINS
  value: "grafana-clock-panel,grafana-simple-json-datasource,grafana-piechart-panel,grafana-worldmap-panel"
```

Then restart:
```bash
kubectl apply -f grafana-deployment.yaml
kubectl rollout restart deployment/grafana -n jewelry-shop
```

### Changing Theme

Edit `grafana-configmap.yaml` and add to the `[users]` section:

```ini
[users]
default_theme = dark
```

### Enabling Anonymous Access

Edit `grafana-configmap.yaml`:

```ini
[auth.anonymous]
enabled = true
org_role = Viewer
```

**⚠️ Warning**: Only enable in trusted environments!

## Integration with Ingress

To expose Grafana externally via Traefik:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: grafana-ingress
  namespace: jewelry-shop
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: traefik
  rules:
  - host: grafana.jewelry-shop.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: grafana
            port:
              number: 3000
  tls:
  - hosts:
    - grafana.jewelry-shop.example.com
    secretName: grafana-tls
```

## Backup and Restore

### Backup Grafana Data

```bash
# Backup PVC data
kubectl exec -n jewelry-shop $(kubectl get pod -n jewelry-shop -l app=grafana -o jsonpath='{.items[0].metadata.name}') -- tar czf /tmp/grafana-backup.tar.gz /var/lib/grafana

# Copy to local machine
kubectl cp jewelry-shop/$(kubectl get pod -n jewelry-shop -l app=grafana -o jsonpath='{.items[0].metadata.name}'):/tmp/grafana-backup.tar.gz ./grafana-backup.tar.gz
```

### Restore Grafana Data

```bash
# Copy backup to pod
kubectl cp ./grafana-backup.tar.gz jewelry-shop/$(kubectl get pod -n jewelry-shop -l app=grafana -o jsonpath='{.items[0].metadata.name}'):/tmp/grafana-backup.tar.gz

# Extract
kubectl exec -n jewelry-shop $(kubectl get pod -n jewelry-shop -l app=grafana -o jsonpath='{.items[0].metadata.name}') -- tar xzf /tmp/grafana-backup.tar.gz -C /

# Restart Grafana
kubectl rollout restart deployment/grafana -n jewelry-shop
```

## Performance Tuning

### Increase Resources

If Grafana is slow, increase resources in `grafana-deployment.yaml`:

```yaml
resources:
  requests:
    cpu: 500m
    memory: 1Gi
  limits:
    cpu: 2000m
    memory: 4Gi
```

### Increase Storage

If running out of space:

```bash
# Edit PVC (if supported by storage class)
kubectl edit pvc grafana-storage -n jewelry-shop

# Or create new PVC and migrate data
```

## Next Steps

After deploying Grafana:

1. **Deploy Loki** (Task 35.3)
   - Centralized log aggregation
   - Add Loki as data source in Grafana
   - Create log dashboards

2. **Configure Alerting** (Task 35.4)
   - Set up Alertmanager
   - Define alert rules in Grafana
   - Configure notification channels

3. **Add More Dashboards**
   - Celery worker metrics
   - Redis performance
   - Nginx metrics
   - Business metrics (sales, inventory)

4. **Set Up User Management**
   - Create teams and users
   - Configure LDAP/OAuth if needed
   - Set up role-based access

## References

- [Grafana Documentation](https://grafana.com/docs/grafana/latest/)
- [Grafana Provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/)
- [Grafana Dashboards](https://grafana.com/grafana/dashboards/)
- [PromQL Basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Requirement 24](../../.kiro/specs/jewelry-saas-platform/requirements.md#requirement-24-monitoring-and-observability)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Grafana logs: `kubectl logs -n jewelry-shop -l app=grafana`
3. Check pod events: `kubectl describe pod -n jewelry-shop -l app=grafana`
4. Consult Grafana documentation: https://grafana.com/docs/
