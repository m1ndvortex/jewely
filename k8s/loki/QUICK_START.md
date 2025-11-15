# Loki Quick Start Guide

## 🚀 Quick Installation (5 minutes)

### Step 1: Install Loki and Promtail

```bash
cd k8s/loki
./install-loki.sh
```

This script will:
- Deploy Loki for log storage
- Deploy Promtail on all nodes for log collection
- Configure Grafana datasource
- Wait for all components to be ready

### Step 2: Validate Installation

```bash
./validate-loki.sh
```

Expected output: All tests should pass ✓

### Step 3: View Logs in Grafana

1. Access Grafana:
   ```bash
   kubectl port-forward -n jewelry-shop svc/grafana 3000:3000
   ```

2. Open browser: http://localhost:3000

3. Navigate to **Explore** (compass icon in left sidebar)

4. Select **Loki** from datasource dropdown

5. Try these queries:
   ```logql
   # All logs from jewelry-shop namespace
   {namespace="jewelry-shop"}
   
   # Django application logs
   {app="django"}
   
   # Error logs only
   {app="django"} |= "error"
   ```

## 📊 Quick Log Queries

### View All Application Logs
```logql
{namespace="jewelry-shop"}
```

### Filter by Application
```logql
{app="django"}          # Django logs
{app="celery-worker"}   # Celery logs
{app="nginx"}           # Nginx logs
{application="spilo"}   # PostgreSQL logs
{app="redis"}           # Redis logs
```

### Search for Errors
```logql
{namespace="jewelry-shop"} |= "error"
{app="django"} |= "ERROR" or "Exception"
```

### Filter by Log Level
```logql
{app="django"} | json | level="ERROR"
```

### Time-based Queries
```logql
# Errors in last 5 minutes
{app="django"} |= "error" [5m]

# Count errors per minute
sum(count_over_time({app="django"} |= "error" [1m]))
```

## 🔍 Verify Log Collection

### Check if Loki is receiving logs

```bash
# Port forward to Loki
kubectl port-forward -n jewelry-shop svc/loki 3100:3100

# Query labels (should show namespace, app, pod, etc.)
curl http://localhost:3100/loki/api/v1/labels

# Query logs
curl 'http://localhost:3100/loki/api/v1/query?query={namespace="jewelry-shop"}&limit=10'
```

### Check Promtail status

```bash
# Check Promtail pods (should be one per node)
kubectl get pods -n jewelry-shop -l app=promtail

# Check Promtail logs
kubectl logs -n jewelry-shop -l app=promtail | tail -20
```

## 🛠️ Common Tasks

### Generate Test Logs

```bash
# Create a test pod that generates logs
kubectl run test-logger --image=busybox -n jewelry-shop -- sh -c "while true; do echo 'Test log at $(date)'; sleep 5; done"

# View logs in Loki
# Query: {pod="test-logger"}

# Cleanup
kubectl delete pod test-logger -n jewelry-shop
```

### View Logs from Specific Pod

```bash
# List pods
kubectl get pods -n jewelry-shop

# Query in Grafana
{pod="django-deployment-abc123"}
```

### Monitor Log Ingestion Rate

```bash
# Port forward to Loki
kubectl port-forward -n jewelry-shop svc/loki 3100:3100

# Check metrics
curl http://localhost:3100/metrics | grep loki_distributor_bytes_received_total
```

## 📈 Create Log-based Alerts

In Grafana:

1. Go to **Alerting** → **Alert rules**
2. Click **New alert rule**
3. Set query:
   ```logql
   sum(rate({app="django"} |= "error" [5m])) > 10
   ```
4. Configure alert conditions and notifications

## 🐛 Troubleshooting

### No logs appearing?

```bash
# 1. Check Promtail is running
kubectl get pods -n jewelry-shop -l app=promtail

# 2. Check Promtail logs for errors
kubectl logs -n jewelry-shop -l app=promtail

# 3. Verify Loki is receiving data
kubectl exec -n jewelry-shop $(kubectl get pod -n jewelry-shop -l app=loki -o jsonpath='{.items[0].metadata.name}') -- wget -q -O- http://localhost:3100/metrics | grep ingester_received
```

### Loki pod not starting?

```bash
# Check pod status
kubectl describe pod -n jewelry-shop -l app=loki

# Check PVC
kubectl get pvc loki-storage -n jewelry-shop

# Check logs
kubectl logs -n jewelry-shop -l app=loki
```

### Grafana not showing Loki datasource?

```bash
# Restart Grafana
kubectl rollout restart deployment/grafana -n jewelry-shop

# Check datasource ConfigMap
kubectl get configmap loki-datasource -n jewelry-shop -o yaml
```

## 📚 Next Steps

1. **Create Dashboards**: Build log dashboards in Grafana
2. **Set up Alerts**: Configure alerts for critical log patterns
3. **Optimize Queries**: Learn advanced LogQL syntax
4. **Tune Retention**: Adjust log retention based on needs

## 🔗 Useful Links

- [LogQL Cheat Sheet](https://grafana.com/docs/loki/latest/logql/)
- [Loki Best Practices](https://grafana.com/docs/loki/latest/best-practices/)
- [Full Documentation](./README.md)

## ✅ Success Checklist

- [ ] Loki pod is running
- [ ] Promtail pods running on all nodes
- [ ] Can query logs via Loki API
- [ ] Grafana shows Loki datasource
- [ ] Can view logs in Grafana Explore
- [ ] Test queries return results

---

**Need help?** Check the full [README.md](./README.md) or run `./validate-loki.sh` for diagnostics.
