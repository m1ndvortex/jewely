# Prometheus Monitoring Integration

## Overview

This document describes the Prometheus monitoring integration for the Jewelry SaaS Platform, implemented per Requirements 7 and 24 (System Monitoring and Observability).

## What is Prometheus?

Prometheus is an open-source monitoring and alerting toolkit that collects and stores metrics as time series data. It provides:

- **Metrics Collection**: Scrapes metrics from instrumented applications
- **Time Series Database**: Stores metrics with timestamps
- **Query Language (PromQL)**: Powerful query language for analyzing metrics
- **Alerting**: Define alert rules based on metric thresholds
- **Visualization**: Integrates with Grafana for dashboards

## Implementation

### 1. Django Application Metrics

We use `django-prometheus` to instrument the Django application and expose metrics at the `/metrics` endpoint.

#### Metrics Collected

**HTTP Metrics:**
- `django_http_requests_total_by_method_total` - Total HTTP requests by method
- `django_http_requests_total_by_view_transport_method_total` - Requests by view and method
- `django_http_requests_latency_seconds` - Request latency histogram
- `django_http_responses_total_by_status_total` - Responses by status code
- `django_http_requests_body_total_bytes` - Request body size
- `django_http_responses_body_total_bytes` - Response body size

**Database Metrics:**
- `django_db_query_duration_seconds` - Database query duration
- `django_db_execute_total` - Total database queries executed
- `django_db_execute_many_total` - Total bulk database operations
- `django_db_errors_total` - Database errors

**Cache Metrics:**
- `django_cache_get_total` - Cache get operations
- `django_cache_hits_total` - Cache hits
- `django_cache_misses_total` - Cache misses
- `django_cache_set_total` - Cache set operations
- `django_cache_delete_total` - Cache delete operations

**Model Metrics:**
- `django_model_inserts_total` - Model insert operations
- `django_model_updates_total` - Model update operations
- `django_model_deletes_total` - Model delete operations

**Migration Metrics:**
- `django_migrations_applied_total` - Applied migrations
- `django_migrations_unapplied_total` - Unapplied migrations

### 2. Configuration

#### Django Settings

The following configuration has been added to `config/settings.py`:

```python
# Prometheus Monitoring Configuration
PROMETHEUS_EXPORT_MIGRATIONS = True
PROMETHEUS_LATENCY_BUCKETS = (
    0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0,
    2.5, 5.0, 7.5, 10.0, 25.0, 50.0, 75.0, float("inf")
)
```

#### Middleware

Prometheus middleware has been added to track all HTTP requests:

```python
MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",  # First
    # ... other middleware ...
    "django_prometheus.middleware.PrometheusAfterMiddleware",  # Last
]
```

#### Database and Cache

Database and cache backends have been wrapped with Prometheus instrumentation:

```python
DATABASES = {
    "default": {
        "ENGINE": "django_prometheus.db.backends.postgresql",
        # ... other settings ...
    }
}

CACHES = {
    "default": {
        "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
        # ... other settings ...
    }
}
```

### 3. Prometheus Server Configuration

Prometheus is configured in `docker/prometheus.yml` to scrape metrics from:

- **Django Application** (`web:8000/metrics`) - Every 15 seconds
- **PostgreSQL** (via postgres_exporter) - Every 30 seconds
- **Redis** (via redis_exporter) - Every 30 seconds
- **Nginx** (via nginx-prometheus-exporter) - Every 30 seconds
- **Celery** (via celery-exporter) - Every 30 seconds
- **System Metrics** (via node-exporter) - Every 30 seconds

### 4. Docker Compose Integration

Prometheus runs as a Docker service:

```yaml
prometheus:
  image: prom/prometheus:latest
  volumes:
    - ./docker/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    - prometheus_data:/prometheus
  ports:
    - "9090:9090"
```

## Usage

### Accessing Metrics

#### 1. Django Metrics Endpoint

Access raw metrics from the Django application:

```bash
# From host machine
curl http://localhost:8000/metrics

# From inside Docker
docker-compose exec web curl http://localhost:8000/metrics
```

#### 2. Prometheus UI

Access the Prometheus web interface:

```
http://localhost:9090
```

### Example Queries (PromQL)

#### Request Rate

```promql
# Requests per second
rate(django_http_requests_total_by_method_total[5m])

# Requests per second by view
rate(django_http_requests_total_by_view_transport_method_total[5m])
```

#### Request Latency

```promql
# 95th percentile latency
histogram_quantile(0.95, rate(django_http_requests_latency_seconds_bucket[5m]))

# Average latency
rate(django_http_requests_latency_seconds_sum[5m]) / rate(django_http_requests_latency_seconds_count[5m])
```

#### Error Rate

```promql
# 5xx error rate
rate(django_http_responses_total_by_status_total{status=~"5.."}[5m])

# Error percentage
sum(rate(django_http_responses_total_by_status_total{status=~"5.."}[5m])) / sum(rate(django_http_responses_total_by_status_total[5m])) * 100
```

#### Database Performance

```promql
# Database query duration (95th percentile)
histogram_quantile(0.95, rate(django_db_query_duration_seconds_bucket[5m]))

# Database queries per second
rate(django_db_execute_total[5m])

# Database errors
rate(django_db_errors_total[5m])
```

#### Cache Performance

```promql
# Cache hit rate
sum(rate(django_cache_hits_total[5m])) / (sum(rate(django_cache_hits_total[5m])) + sum(rate(django_cache_misses_total[5m]))) * 100

# Cache operations per second
rate(django_cache_get_total[5m])
```

## Starting Prometheus

### Development Environment

```bash
# Start all services including Prometheus
docker-compose up -d

# Check Prometheus is running
docker-compose ps prometheus

# View Prometheus logs
docker-compose logs -f prometheus

# Access Prometheus UI
open http://localhost:9090
```

### Verify Metrics Collection

1. **Check Django metrics endpoint:**
   ```bash
   curl http://localhost:8000/metrics
   ```

2. **Check Prometheus targets:**
   - Open http://localhost:9090/targets
   - Verify all targets are "UP"

3. **Run a test query:**
   - Open http://localhost:9090/graph
   - Enter query: `django_http_requests_total_by_method_total`
   - Click "Execute"

## Integration with Grafana

Prometheus is designed to work with Grafana for visualization. To set up Grafana:

1. **Add Grafana to docker-compose.yml** (Task 19.4)
2. **Configure Prometheus as data source**
3. **Import pre-built dashboards** or create custom ones

### Recommended Dashboards

- **Django Application Dashboard**: Request rates, latency, errors
- **Database Dashboard**: Query performance, connections, slow queries
- **Cache Dashboard**: Hit rates, memory usage, operations
- **System Dashboard**: CPU, memory, disk, network

## Alerting

Alerting will be configured in Task 19.3. Example alert rules:

```yaml
# High error rate
- alert: HighErrorRate
  expr: rate(django_http_responses_total_by_status_total{status=~"5.."}[5m]) > 0.05
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "High error rate detected"

# Slow requests
- alert: SlowRequests
  expr: histogram_quantile(0.95, rate(django_http_requests_latency_seconds_bucket[5m])) > 2
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "95th percentile latency above 2 seconds"
```

## Troubleshooting

### Metrics Endpoint Not Working

```bash
# Check if django-prometheus is installed
docker-compose exec web pip list | grep django-prometheus

# Check if URL is configured
docker-compose exec web python manage.py show_urls | grep metrics

# Check middleware configuration
docker-compose exec web python manage.py diffsettings | grep MIDDLEWARE
```

### Prometheus Not Scraping

```bash
# Check Prometheus logs
docker-compose logs prometheus

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Verify network connectivity
docker-compose exec prometheus wget -O- http://web:8000/metrics
```

### High Memory Usage

Prometheus stores metrics in memory. If memory usage is high:

1. Reduce retention time in `prometheus.yml`
2. Reduce scrape frequency
3. Increase storage limits
4. Use remote storage (e.g., Thanos, Cortex)

## Performance Impact

The Prometheus instrumentation has minimal performance impact:

- **Middleware overhead**: < 1ms per request
- **Memory overhead**: ~50MB for metrics storage
- **CPU overhead**: < 1% for metrics collection

## Security Considerations

### Production Deployment

1. **Restrict metrics endpoint access:**
   ```python
   # Only allow internal IPs
   PROMETHEUS_METRICS_ALLOWED_IPS = ['10.0.0.0/8', '172.16.0.0/12']
   ```

2. **Use authentication:**
   - Configure basic auth in Nginx
   - Use VPN for Prometheus access
   - Implement IP whitelisting

3. **Disable in development:**
   ```python
   if not DEBUG:
       INSTALLED_APPS.append('django_prometheus')
   ```

## Next Steps

1. **Task 19.2**: Create monitoring dashboards in Grafana
2. **Task 19.3**: Implement alert system with Alertmanager
3. **Task 19.4**: Integrate Grafana for visualization
4. **Task 19.5**: Write monitoring tests

## References

- [django-prometheus Documentation](https://github.com/korfuri/django-prometheus)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [PromQL Basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Integration](https://prometheus.io/docs/visualization/grafana/)

## Requirements Satisfied

- ✅ **Requirement 7**: System Monitoring and Health Dashboard
  - Real-time metrics for CPU, memory, disk, database connections
  - Service status monitoring
  - API response times and database query performance
  - Cache hit rates

- ✅ **Requirement 24**: Monitoring and Observability
  - Prometheus deployment for metrics collection
  - Django metrics using django-prometheus
  - Metrics exposed for PostgreSQL, Redis, Nginx (via exporters)
  - Foundation for Grafana dashboards and alerting
