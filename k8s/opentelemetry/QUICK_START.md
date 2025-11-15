# OpenTelemetry Distributed Tracing - Quick Start Guide

Get distributed tracing up and running in 5 minutes!

## Prerequisites

- Kubernetes cluster running
- jewelry-shop namespace exists
- Prometheus and Grafana deployed
- kubectl configured

## Step 1: Install OpenTelemetry Stack (2 minutes)

```bash
cd k8s/opentelemetry
./install-opentelemetry.sh
```

**Expected output:**
```
[INFO] Starting OpenTelemetry stack installation...
[SUCCESS] Namespace 'jewelry-shop' exists
[INFO] Deploying Grafana Tempo...
[SUCCESS] Tempo deployed successfully
[INFO] Deploying OpenTelemetry Collector...
[SUCCESS] OpenTelemetry Collector deployed successfully
[INFO] Updating Grafana datasources to include Tempo...
[SUCCESS] Grafana datasources updated
```

## Step 2: Validate Installation (1 minute)

```bash
./validate-opentelemetry.sh
```

**Expected output:**
```
[✓ PASS] Tempo deployment is running with 1 replica(s)
[✓ PASS] Tempo service exists with ports: 3200 4317 4318 9096
[✓ PASS] Tempo health check passed
[✓ PASS] OpenTelemetry Collector deployment is running with 2 replica(s)
[✓ PASS] OpenTelemetry Collector service exists with ports: 4317 4318 8889 13133
[✓ PASS] OpenTelemetry Collector health check passed
...
Passed:   12
Warnings: 0
Failed:   0
```

## Step 3: Rebuild and Redeploy Django/Celery (Required)

The Django and Celery containers need to be rebuilt with OpenTelemetry dependencies:

```bash
# Rebuild Docker image with new dependencies
docker compose build web

# Tag for Kubernetes
docker tag jewelry-shop:latest jewelry-shop:otel-v1

# Load into k3d cluster
k3d image import jewelry-shop:otel-v1 -c jewelry-shop

# Update deployments
kubectl set image deployment/django django=jewelry-shop:otel-v1 -n jewelry-shop
kubectl set image deployment/celery-worker celery-worker=jewelry-shop:otel-v1 -n jewelry-shop

# Wait for rollout
kubectl rollout status deployment/django -n jewelry-shop
kubectl rollout status deployment/celery-worker -n jewelry-shop
```

## Step 4: Generate Test Traces (30 seconds)

```bash
# Get Django pod name
DJANGO_POD=$(kubectl get pods -n jewelry-shop -l component=django -o jsonpath='{.items[0].metadata.name}')

# Generate some traces
for i in {1..10}; do
  kubectl exec -n jewelry-shop $DJANGO_POD -- wget -q -O- http://localhost:8000/health/live/
  sleep 1
done

echo "Test traces generated!"
```

## Step 5: View Traces in Grafana (1 minute)

```bash
# Port-forward Grafana
kubectl port-forward -n jewelry-shop svc/grafana 3000:3000
```

Then:

1. **Open browser:** http://localhost:3000
2. **Login:** admin / (check your Grafana password)
3. **Navigate:** Click "Explore" (compass icon) in left sidebar
4. **Select datasource:** Choose "Tempo" from dropdown
5. **Search traces:**
   - Click "Search" tab
   - Service Name: `jewelry-shop-django`
   - Click "Run query"
6. **View trace:** Click on any trace to see the detailed span timeline

## What You Should See

### In Grafana Explore (Tempo)

- **Service Map:** Visual representation of service dependencies
- **Trace List:** List of recent traces with duration and span count
- **Trace Details:** Click a trace to see:
  - Span timeline (waterfall view)
  - Individual span details
  - Tags and attributes
  - Logs correlation (if available)

### Example Trace

```
jewelry-shop-django: GET /health/live/
├─ django.request (50ms)
│  ├─ django.middleware (5ms)
│  ├─ django.view (40ms)
│  │  ├─ postgresql.query (10ms)
│  │  └─ redis.get (5ms)
│  └─ django.response (5ms)
```

## Quick Commands Reference

```bash
# Check status
kubectl get pods -n jewelry-shop -l component=tracing

# View Tempo logs
kubectl logs -n jewelry-shop -l app=tempo --tail=50

# View OpenTelemetry Collector logs
kubectl logs -n jewelry-shop -l app=otel-collector --tail=50

# Check Tempo health
TEMPO_POD=$(kubectl get pods -n jewelry-shop -l app=tempo -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n jewelry-shop $TEMPO_POD -- wget -q -O- http://localhost:3200/ready

# Check OpenTelemetry Collector health
OTEL_POD=$(kubectl get pods -n jewelry-shop -l app=otel-collector -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n jewelry-shop $OTEL_POD -- wget -q -O- http://localhost:13133

# Run comprehensive tests
./test-opentelemetry-comprehensive.sh
```

## Troubleshooting

### No traces appearing?

1. **Verify Django has OpenTelemetry packages:**
   ```bash
   kubectl exec -n jewelry-shop $DJANGO_POD -- pip list | grep opentelemetry
   ```
   If not found, rebuild and redeploy (Step 3).

2. **Check environment variables:**
   ```bash
   kubectl exec -n jewelry-shop $DJANGO_POD -- env | grep OTEL
   ```
   Should show:
   ```
   OTEL_ENABLED=true
   OTEL_SERVICE_NAME=jewelry-shop-django
   OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
   ```

3. **Check OpenTelemetry Collector logs:**
   ```bash
   kubectl logs -n jewelry-shop -l app=otel-collector --tail=100 | grep -i error
   ```

### Grafana can't connect to Tempo?

```bash
# Restart Grafana
kubectl rollout restart deployment/grafana -n jewelry-shop

# Verify Tempo datasource
kubectl get configmap grafana-datasources -n jewelry-shop -o yaml | grep -A 10 "type: tempo"
```

### High resource usage?

Reduce sampling in `otel-collector-configmap.yaml`:
```yaml
probabilistic_sampler:
  sampling_percentage: 10  # Sample only 10% of traces
```

Then apply:
```bash
kubectl apply -f otel-collector-configmap.yaml
kubectl rollout restart deployment/otel-collector -n jewelry-shop
```

## Next Steps

1. **Explore traces:** Try different search filters in Grafana
2. **Add custom spans:** Instrument your code with custom spans
3. **Set up alerts:** Alert on high error rates or slow traces
4. **Optimize sampling:** Adjust sampling rate based on volume
5. **Monitor resources:** Keep an eye on Tempo storage usage

## Need Help?

- **Full documentation:** See [README.md](README.md)
- **Validation script:** Run `./validate-opentelemetry.sh`
- **Comprehensive tests:** Run `./test-opentelemetry-comprehensive.sh`
- **Check logs:** `kubectl logs -n jewelry-shop -l component=tracing`

## Success Criteria

✅ All pods running (Tempo, OpenTelemetry Collector)  
✅ Validation script passes all tests  
✅ Traces visible in Grafana Explore  
✅ Service map shows Django → PostgreSQL → Redis  
✅ No errors in component logs  

**Congratulations! Distributed tracing is now operational! 🎉**
