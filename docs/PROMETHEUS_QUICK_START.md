# Prometheus Monitoring - Quick Start Guide

## Overview

Prometheus monitoring is now integrated into the Jewelry SaaS Platform. This guide provides quick access to common tasks.

## Quick Access

### Metrics Endpoint
```
http://localhost:8000/metrics
```

### Prometheus UI
```
http://localhost:9090
```

## Common Commands

### View Metrics from Command Line
```bash
# View first 50 lines of metrics
docker compose exec web python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/metrics').read().decode()[:2000])"
```

### Check Prometheus Status
```bash
# View Prometheus logs
docker compose logs prometheus --tail 50

# Check if Prometheus is running
docker compose ps prometheus
```

### Restart Prometheus
```bash
docker compose restart prometheus
```

## Common PromQL Queries

Copy these into the Prometheus UI (http://localhost:9090/graph):

### Request Metrics
```promql
# Total requests per second
rate(django_http_requests_total_by_method_total[5m])

# Requests by view
rate(django_http_requests_total_by_view_transport_method_total[5m])
```

### Latency Metrics
```promql
# 95th percentile latency
histogram_quantile(0.95, rate(django_http_requests_latency_seconds_bucket[5m]))

# Average latency
rate(django_http_requests_latency_seconds_sum[5m]) / rate(django_http_requests_latency_seconds_count[5m])

# Max latency
max(django_http_requests_latency_seconds_bucket)
```

### Error Metrics
```promql
# 5xx error rate
rate(django_http_responses_total_by_status_total{status=~"5.."}[5m])

# Error percentage
sum(rate(django_http_responses_total_by_status_total{status=~"5.."}[5m])) / sum(rate(django_http_responses_total_by_status_total[5m])) * 100

# 4xx error rate
rate(django_http_responses_total_by_status_total{status=~"4.."}[5m])
```

### Database Metrics
```promql
# Database query duration (95th percentile)
histogram_quantile(0.95, rate(django_db_query_duration_seconds_bucket[5m]))

# Database queries per second
rate(django_db_execute_total[5m])

# Database errors
rate(django_db_errors_total[5m])

# Database connections
django_db_new_connections_total
```

### Cache Metrics
```promql
# Cache hit rate (percentage)
sum(rate(django_cache_get_hits_total[5m])) / (sum(rate(django_cache_get_hits_total[5m])) + sum(rate(django_cache_get_misses_total[5m]))) * 100

# Cache operations per second
rate(django_cache_get_total[5m])

# Cache misses per second
rate(django_cache_get_misses_total[5m])
```

### System Metrics
```promql
# Memory usage
process_resident_memory_bytes

# CPU usage
rate(process_cpu_seconds_total[5m])

# Open file descriptors
process_open_fds
```

## Troubleshooting

### Metrics Endpoint Not Working

1. Check if web service is running:
   ```bash
   docker compose ps web
   ```

2. Check web service logs:
   ```bash
   docker compose logs web --tail 50
   ```

3. Verify django-prometheus is installed:
   ```bash
   docker compose exec web pip list | grep django-prometheus
   ```

### Prometheus Not Scraping

1. Check Prometheus logs:
   ```bash
   docker compose logs prometheus --tail 50
   ```

2. Check Prometheus targets:
   - Open http://localhost:9090/targets
   - Verify "django" target is "UP"

3. Test connectivity from Prometheus to Django:
   ```bash
   docker compose exec prometheus wget -qO- http://web:8000/metrics
   ```

### No Data in Prometheus

1. Wait 15-30 seconds for first scrape
2. Make some requests to generate metrics:
   ```bash
   curl http://localhost:8000/
   curl http://localhost:8000/metrics
   ```
3. Refresh Prometheus UI

## Next Steps

1. **Create Grafana Dashboards** (Task 19.4)
   - Visualize metrics with graphs and charts
   - Create custom dashboards for different teams

2. **Set Up Alerting** (Task 19.3)
   - Configure alert rules
   - Set up notification channels (email, SMS, Slack)

3. **Add More Exporters**
   - PostgreSQL exporter for database metrics
   - Redis exporter for cache metrics
   - Nginx exporter for web server metrics
   - Node exporter for system metrics

## Resources

- [Full Documentation](./PROMETHEUS_MONITORING.md)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [PromQL Basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [django-prometheus GitHub](https://github.com/korfuri/django-prometheus)

## Support

For issues or questions:
1. Check the full documentation: `docs/PROMETHEUS_MONITORING.md`
2. Review Prometheus logs: `docker compose logs prometheus`
3. Review Django logs: `docker compose logs web`
4. Check test results: `docker compose exec web pytest tests/test_prometheus_monitoring.py -v`
