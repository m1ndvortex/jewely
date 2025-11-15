# OpenTelemetry Distributed Tracing

This directory contains the complete OpenTelemetry distributed tracing stack for the Jewelry Shop SaaS platform.

## Overview

The distributed tracing implementation provides end-to-end visibility into request flows across Django, Celery, PostgreSQL, Redis, and external services. This helps identify performance bottlenecks, debug issues, and understand system behavior.

**Requirements:** Requirement 24 - Monitoring and Observability

## Architecture

```
┌─────────────┐     ┌─────────────┐
│   Django    │────▶│   Celery    │
│  (Traces)   │     │  (Traces)   │
└──────┬──────┘     └──────┬──────┘
       │                   │
       │  OTLP gRPC/HTTP   │
       │                   │
       ▼                   ▼
┌────────────────────────────────┐
│  OpenTelemetry Collector       │
│  - Receives traces             │
│  - Processes & batches         │
│  - Exports to Tempo            │
└────────────┬───────────────────┘
             │
             │ OTLP
             ▼
┌────────────────────────────────┐
│         Grafana Tempo          │
│  - Stores traces               │
│  - Provides query API          │
│  - 7-day retention             │
└────────────┬───────────────────┘
             │
             │ Query API
             ▼
┌────────────────────────────────┐
│          Grafana               │
│  - Visualizes traces           │
│  - Trace search                │
│  - Service map                 │
└────────────────────────────────┘
```

## Components

### 1. Grafana Tempo
- **Purpose:** Distributed tracing backend
- **Storage:** Local filesystem with 7-day retention
- **Ports:**
  - 3200: HTTP API
  - 4317: OTLP gRPC receiver
  - 4318: OTLP HTTP receiver
- **Resources:** 200m CPU, 512Mi memory (requests)

### 2. OpenTelemetry Collector
- **Purpose:** Trace collection, processing, and export
- **Replicas:** 2 for high availability
- **Ports:**
  - 4317: OTLP gRPC receiver
  - 4318: OTLP HTTP receiver
  - 8889: Prometheus metrics
  - 13133: Health check
- **Resources:** 200m CPU, 256Mi memory (requests)

### 3. Django Instrumentation
- **Library:** `opentelemetry-instrumentation-django`
- **Auto-instruments:**
  - HTTP requests/responses
  - Database queries (PostgreSQL)
  - Redis operations
  - External HTTP calls
- **Configuration:** Environment variables in deployment

### 4. Celery Instrumentation
- **Library:** `opentelemetry-instrumentation-celery`
- **Auto-instruments:**
  - Task execution
  - Task retries
  - Task failures
- **Configuration:** Environment variables in deployment

## Installation

### Prerequisites
- Kubernetes cluster with jewelry-shop namespace
- Prometheus and Grafana already deployed
- kubectl configured

### Quick Install

```bash
cd k8s/opentelemetry
./install-opentelemetry.sh
```

This script will:
1. Deploy Grafana Tempo
2. Deploy OpenTelemetry Collector
3. Update Grafana datasources
4. Verify deployment

### Manual Installation

```bash
# Deploy Tempo
kubectl apply -f tempo-configmap.yaml
kubectl apply -f tempo-deployment.yaml

# Deploy OpenTelemetry Collector
kubectl apply -f otel-collector-configmap.yaml
kubectl apply -f otel-collector-deployment.yaml

# Update Grafana datasources
kubectl apply -f ../grafana/grafana-configmap.yaml
kubectl rollout restart deployment/grafana -n jewelry-shop

# Wait for pods to be ready
kubectl wait --for=condition=available --timeout=300s deployment/tempo -n jewelry-shop
kubectl wait --for=condition=available --timeout=300s deployment/otel-collector -n jewelry-shop
```

## Validation

### Quick Validation

```bash
./validate-opentelemetry.sh
```

### Comprehensive Testing

```bash
./test-opentelemetry-comprehensive.sh
```

### Manual Verification

```bash
# Check pod status
kubectl get pods -n jewelry-shop -l component=tracing

# Check Tempo health
TEMPO_POD=$(kubectl get pods -n jewelry-shop -l app=tempo -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n jewelry-shop $TEMPO_POD -- wget -q -O- http://localhost:3200/ready

# Check OpenTelemetry Collector health
OTEL_POD=$(kubectl get pods -n jewelry-shop -l app=otel-collector -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n jewelry-shop $OTEL_POD -- wget -q -O- http://localhost:13133

# Check logs
kubectl logs -n jewelry-shop -l app=tempo --tail=50
kubectl logs -n jewelry-shop -l app=otel-collector --tail=50
```

## Usage

### Viewing Traces in Grafana

1. **Access Grafana:**
   ```bash
   kubectl port-forward -n jewelry-shop svc/grafana 3000:3000
   ```
   Open http://localhost:3000

2. **Navigate to Explore:**
   - Click "Explore" in the left sidebar
   - Select "Tempo" from the datasource dropdown

3. **Search for Traces:**
   - **By Service:** Select "jewelry-shop-django" or "jewelry-shop-celery"
   - **By Operation:** Filter by specific operations (e.g., "GET /api/inventory/")
   - **By Trace ID:** Enter a specific trace ID
   - **By Tags:** Filter by custom tags

4. **Analyze Traces:**
   - View span timeline
   - See service dependencies
   - Identify slow operations
   - Debug errors

### Generating Test Traces

```bash
# Generate traces from Django
DJANGO_POD=$(kubectl get pods -n jewelry-shop -l component=django -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n jewelry-shop $DJANGO_POD -- wget -q -O- http://localhost:8000/health/live/

# Generate traces from Celery
kubectl exec -n jewelry-shop $DJANGO_POD -- python manage.py shell -c "from apps.pricing.tasks import fetch_gold_rates; fetch_gold_rates.delay()"
```

### Custom Instrumentation

Add custom spans to your code:

```python
from apps.core.tracing import get_tracer

tracer = get_tracer(__name__)

def my_function():
    with tracer.start_as_current_span("my_operation"):
        # Your code here
        result = do_something()
        
        # Add attributes to span
        span = trace.get_current_span()
        span.set_attribute("result.count", len(result))
        span.set_attribute("user.id", user_id)
        
        return result
```

## Configuration

### Environment Variables

Django and Celery deployments use these environment variables:

```yaml
- name: OTEL_ENABLED
  value: "true"
- name: OTEL_SERVICE_NAME
  value: "jewelry-shop-django"  # or "jewelry-shop-celery"
- name: OTEL_EXPORTER_OTLP_ENDPOINT
  value: "http://otel-collector:4317"
- name: OTEL_EXPORTER_OTLP_INSECURE
  value: "true"
- name: ENVIRONMENT
  value: "production"
- name: APP_VERSION
  value: "1.0.0"
```

### Tempo Configuration

Key settings in `tempo-configmap.yaml`:

- **Retention:** 7 days (168 hours)
- **Storage:** Local filesystem at `/var/tempo/traces`
- **Receivers:** OTLP gRPC (4317) and HTTP (4318)

### OpenTelemetry Collector Configuration

Key settings in `otel-collector-configmap.yaml`:

- **Batch Processing:** 10s timeout, 1024 batch size
- **Memory Limiter:** 512 MiB limit
- **Sampling:** 100% (adjust based on volume)
- **Exporters:** Tempo (OTLP), Prometheus (metrics), Logging (debug)

## Troubleshooting

### No Traces Appearing

1. **Check Django/Celery have OpenTelemetry dependencies:**
   ```bash
   kubectl exec -n jewelry-shop <django-pod> -- pip list | grep opentelemetry
   ```

2. **Verify environment variables:**
   ```bash
   kubectl exec -n jewelry-shop <django-pod> -- env | grep OTEL
   ```

3. **Check OpenTelemetry Collector logs:**
   ```bash
   kubectl logs -n jewelry-shop -l app=otel-collector --tail=100
   ```

4. **Verify connectivity:**
   ```bash
   kubectl exec -n jewelry-shop <django-pod> -- nc -zv otel-collector 4317
   ```

### Tempo Not Receiving Traces

1. **Check Tempo logs:**
   ```bash
   kubectl logs -n jewelry-shop -l app=tempo --tail=100
   ```

2. **Verify Tempo metrics:**
   ```bash
   TEMPO_POD=$(kubectl get pods -n jewelry-shop -l app=tempo -o jsonpath='{.items[0].metadata.name}')
   kubectl exec -n jewelry-shop $TEMPO_POD -- wget -q -O- http://localhost:3200/metrics | grep tempo_distributor
   ```

3. **Check OpenTelemetry Collector → Tempo connectivity:**
   ```bash
   OTEL_POD=$(kubectl get pods -n jewelry-shop -l app=otel-collector -o jsonpath='{.items[0].metadata.name}')
   kubectl exec -n jewelry-shop $OTEL_POD -- nc -zv tempo 4317
   ```

### High Resource Usage

1. **Reduce sampling rate** in `otel-collector-configmap.yaml`:
   ```yaml
   probabilistic_sampler:
     sampling_percentage: 10  # Sample 10% of traces
   ```

2. **Reduce retention** in `tempo-configmap.yaml`:
   ```yaml
   compaction:
     block_retention: 72h  # 3 days instead of 7
   ```

3. **Increase batch size** in `otel-collector-configmap.yaml`:
   ```yaml
   batch:
     timeout: 30s
     send_batch_size: 2048
   ```

### Grafana Can't Query Tempo

1. **Verify Tempo datasource configuration:**
   ```bash
   kubectl get configmap grafana-datasources -n jewelry-shop -o yaml
   ```

2. **Restart Grafana:**
   ```bash
   kubectl rollout restart deployment/grafana -n jewelry-shop
   ```

3. **Check Grafana logs:**
   ```bash
   kubectl logs -n jewelry-shop -l app=grafana --tail=100
   ```

## Maintenance

### Viewing Trace Storage Usage

```bash
TEMPO_POD=$(kubectl get pods -n jewelry-shop -l app=tempo -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n jewelry-shop $TEMPO_POD -- du -sh /var/tempo/traces
```

### Cleaning Up Old Traces

Tempo automatically removes traces older than the retention period (7 days). To manually clean up:

```bash
# Delete and recreate Tempo pod (will lose all traces)
kubectl delete pod -n jewelry-shop -l app=tempo
```

### Scaling OpenTelemetry Collector

```bash
# Scale to 3 replicas for higher load
kubectl scale deployment otel-collector -n jewelry-shop --replicas=3
```

### Updating Configuration

```bash
# Update Tempo configuration
kubectl apply -f tempo-configmap.yaml
kubectl rollout restart deployment/tempo -n jewelry-shop

# Update OpenTelemetry Collector configuration
kubectl apply -f otel-collector-configmap.yaml
kubectl rollout restart deployment/otel-collector -n jewelry-shop
```

## Metrics

### OpenTelemetry Collector Metrics

Available at `http://otel-collector:8889/metrics`:

- `otelcol_receiver_accepted_spans`: Spans received
- `otelcol_receiver_refused_spans`: Spans refused
- `otelcol_exporter_sent_spans`: Spans exported
- `otelcol_processor_batch_batch_send_size`: Batch sizes

### Tempo Metrics

Available at `http://tempo:3200/metrics`:

- `tempo_distributor_spans_received_total`: Total spans received
- `tempo_ingester_blocks_flushed_total`: Blocks flushed to storage
- `tempo_query_frontend_queries_total`: Total queries
- `tempo_querier_spans_per_query`: Spans per query

## Best Practices

1. **Use meaningful span names:** Describe the operation clearly
2. **Add relevant attributes:** Include user IDs, tenant IDs, request IDs
3. **Don't over-instrument:** Focus on critical paths
4. **Monitor resource usage:** Adjust sampling if needed
5. **Set up alerts:** Alert on high error rates in traces
6. **Regular cleanup:** Monitor storage usage
7. **Test trace generation:** Verify traces appear in Grafana

## References

- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Grafana Tempo Documentation](https://grafana.com/docs/tempo/latest/)
- [OpenTelemetry Python Instrumentation](https://opentelemetry-python-contrib.readthedocs.io/)
- [Requirement 24: Monitoring and Observability](../../.kiro/specs/jewelry-saas-platform/requirements.md#requirement-24-monitoring-and-observability)
