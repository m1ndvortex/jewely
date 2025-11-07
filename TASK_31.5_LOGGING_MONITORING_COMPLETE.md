# Task 31.5: Configure Logging and Monitoring - COMPLETE

## Summary

Successfully implemented comprehensive logging and monitoring configuration for Nginx, satisfying Requirements 22 (Criteria 9-10) and 24 (Criterion 3).

## Implementation Details

### 1. Access Logs with Response Times ✅

**Created**: `docker/nginx/snippets/logging.conf`

- Configured custom log format with detailed timing metrics:
  - `$request_time`: Total request processing time
  - `$upstream_connect_time`: Time to connect to Django
  - `$upstream_header_time`: Time to receive headers from Django
  - `$upstream_response_time`: Time to receive full response from Django

- Implemented log buffering for performance:
  - Buffer size: 32KB
  - Flush interval: 5 seconds

- Added JSON log format for structured logging (optional):
  - Supports log aggregation systems (Loki, ELK, etc.)
  - Includes all timing metrics in JSON format

**Example Log Entry**:
```
172.18.0.1 - - [07/Nov/2025:10:30:45 +0000] "GET /api/inventory/ HTTP/1.1" 200 1234 "-" "Mozilla/5.0" "-" rt=0.123 uct="0.001" uht="0.050" urt="0.122"
```

### 2. Error Logs Configuration ✅

**Configured in**: `docker/nginx/snippets/logging.conf`

- **Standard Error Log** (`/var/log/nginx/error.log`):
  - Level: `warn`
  - Logs warnings and above (warn, error, crit, alert, emerg)
  - Used for general error monitoring

- **Critical Error Log** (`/var/log/nginx/error-critical.log`):
  - Level: `crit`
  - Logs only critical errors and above
  - Used for alerting on severe issues

### 3. Nginx Prometheus Exporter Integration ✅

**Created**: `docker/nginx/snippets/metrics.conf`

- Configured stub_status module for metrics exposure
- Created `/nginx_status` endpoint with access restrictions:
  - Allowed: localhost, Docker networks, private networks
  - Denied: public access

- nginx-prometheus-exporter service (already in docker-compose.yml):
  - Image: `nginx/nginx-prometheus-exporter:latest`
  - Port: 9113
  - Scrapes: `http://nginx/nginx_status`

**Available Metrics**:
- `nginx_connections_active`: Active connections
- `nginx_connections_reading`: Connections reading request
- `nginx_connections_writing`: Connections writing response
- `nginx_connections_waiting`: Idle keepalive connections
- `nginx_http_requests_total`: Total HTTP requests
- `nginx_connections_accepted`: Accepted connections
- `nginx_connections_handled`: Handled connections

### 4. Prometheus Integration ✅

**Verified**: `docker/prometheus.yml`

- Prometheus scrapes nginx_exporter every 30 seconds
- Job name: `nginx`
- Target: `nginx_exporter:9113`
- Labels: service=nginx, component=proxy

## Files Created/Modified

### Created Files:
1. `docker/nginx/snippets/logging.conf` - Logging configuration
2. `docker/nginx/snippets/metrics.conf` - Metrics endpoint configuration
3. `docker/nginx/LOGGING_MONITORING.md` - Comprehensive documentation
4. `tests/test_nginx_logging_monitoring.py` - Python tests (24 tests)
5. `tests/test_logging_monitoring.sh` - Shell integration tests

### Modified Files:
1. `docker/nginx/nginx.conf` - Include logging snippet
2. `docker/nginx/conf.d/jewelry-shop.conf` - Include metrics snippet

## Test Results

### Python Tests: ✅ ALL PASSED (24/24)

```
tests/test_nginx_logging_monitoring.py::TestNginxLogging::test_logging_snippet_exists PASSED
tests/test_nginx_logging_monitoring.py::TestNginxLogging::test_access_log_format_includes_response_times PASSED
tests/test_nginx_logging_monitoring.py::TestNginxLogging::test_json_log_format_configured PASSED
tests/test_nginx_logging_monitoring.py::TestNginxLogging::test_error_log_levels_configured PASSED
tests/test_nginx_logging_monitoring.py::TestNginxLogging::test_logging_snippet_included_in_nginx_conf PASSED
tests/test_nginx_logging_monitoring.py::TestNginxLogging::test_access_log_buffering_configured PASSED
tests/test_nginx_logging_monitoring.py::TestNginxMetrics::test_metrics_snippet_exists PASSED
tests/test_nginx_logging_monitoring.py::TestNginxMetrics::test_stub_status_module_configured PASSED
tests/test_nginx_logging_monitoring.py::TestNginxMetrics::test_metrics_endpoint_access_restricted PASSED
tests/test_nginx_logging_monitoring.py::TestNginxMetrics::test_metrics_endpoint_no_access_logging PASSED
tests/test_nginx_logging_monitoring.py::TestNginxMetrics::test_metrics_snippet_included_in_site_config PASSED
tests/test_nginx_logging_monitoring.py::TestNginxMetrics::test_health_check_endpoint_configured PASSED
tests/test_nginx_logging_monitoring.py::TestPrometheusIntegration::test_nginx_exporter_in_docker_compose PASSED
tests/test_nginx_logging_monitoring.py::TestPrometheusIntegration::test_nginx_exporter_scrape_uri_configured PASSED
tests/test_nginx_logging_monitoring.py::TestPrometheusIntegration::test_nginx_exporter_port_exposed PASSED
tests/test_nginx_logging_monitoring.py::TestPrometheusIntegration::test_nginx_exporter_depends_on_nginx PASSED
tests/test_nginx_logging_monitoring.py::TestPrometheusIntegration::test_prometheus_scrapes_nginx_exporter PASSED
tests/test_nginx_logging_monitoring.py::TestDockerComposeConfiguration::test_nginx_logs_volume_mounted PASSED
tests/test_nginx_logging_monitoring.py::TestDockerComposeConfiguration::test_nginx_snippets_mounted PASSED
tests/test_nginx_logging_monitoring.py::TestLoggingDocumentation::test_logging_snippet_has_comments PASSED
tests/test_nginx_logging_monitoring.py::TestLoggingDocumentation::test_metrics_snippet_has_comments PASSED
tests/test_nginx_logging_monitoring.py::TestRequirementCompliance::test_requirement_22_criterion_9_compliance PASSED
tests/test_nginx_logging_monitoring.py::TestRequirementCompliance::test_requirement_22_criterion_10_compliance PASSED
tests/test_nginx_logging_monitoring.py::TestRequirementCompliance::test_requirement_24_criterion_3_compliance PASSED
```

## Requirements Compliance

### ✅ Requirement 22, Criterion 9
**"THE System SHALL configure Nginx to log all requests with response times and status codes"**

- Access logs configured with custom format including:
  - Status codes: `$status`
  - Request time: `$request_time`
  - Upstream connect time: `$upstream_connect_time`
  - Upstream header time: `$upstream_header_time`
  - Upstream response time: `$upstream_response_time`

### ✅ Requirement 22, Criterion 10
**"THE System SHALL configure Nginx to export metrics for Prometheus monitoring"**

- stub_status module enabled at `/nginx_status`
- Metrics endpoint properly secured (internal networks only)
- nginx-prometheus-exporter configured and running

### ✅ Requirement 24, Criterion 3
**"THE System SHALL expose Nginx metrics using nginx-prometheus-exporter"**

- nginx-prometheus-exporter service deployed
- Configured to scrape nginx_status endpoint
- Prometheus configured to scrape exporter
- Metrics exposed on port 9113

## Usage

### Viewing Logs

```bash
# Access logs
docker compose exec nginx tail -f /var/log/nginx/access.log

# Error logs
docker compose exec nginx tail -f /var/log/nginx/error.log

# Critical errors only
docker compose exec nginx tail -f /var/log/nginx/error-critical.log
```

### Accessing Metrics

```bash
# Nginx status (from inside Docker network)
docker compose exec nginx curl http://localhost/nginx_status

# Prometheus metrics
curl http://localhost:9113/metrics

# Query Prometheus
curl "http://localhost:9090/api/v1/query?query=nginx_connections_active"
```

### Log Analysis

```bash
# Top 10 slowest requests
docker compose exec nginx awk '{print $NF, $7}' /var/log/nginx/access.log | \
    grep 'urt=' | sort -rn | head -10

# Average response time
docker compose exec nginx awk '{print $NF}' /var/log/nginx/access.log | \
    grep -oP 'rt=\K[0-9.]+' | awk '{sum+=$1; count++} END {print sum/count}'

# Requests by status code
docker compose exec nginx awk '{print $9}' /var/log/nginx/access.log | \
    sort | uniq -c | sort -rn
```

## Documentation

Comprehensive documentation created at:
- `docker/nginx/LOGGING_MONITORING.md`

Includes:
- Log format details and examples
- Metrics description and usage
- Prometheus integration guide
- Grafana dashboard recommendations
- Log management and rotation
- Troubleshooting guide
- Best practices

## Monitoring Best Practices

1. **Set Up Alerts**:
   - High error rates (5xx responses)
   - Slow response times (>2 seconds)
   - High connection counts
   - Low connection handling efficiency

2. **Monitor Key Metrics**:
   - Request rate (sudden spikes or drops)
   - Response times (P50, P95, P99 percentiles)
   - Error rates (4xx and 5xx responses)
   - Connection states (high waiting connections)

3. **Regular Log Review**:
   - Review error logs daily
   - Investigate critical errors immediately
   - Analyze slow requests weekly
   - Monitor log growth and rotate appropriately

## Next Steps

1. **Configure Log Rotation** (Production):
   ```bash
   # /etc/logrotate.d/nginx
   /var/log/nginx/*.log {
       daily
       missingok
       rotate 14
       compress
       delaycompress
       notifempty
       create 0640 nginx nginx
       sharedscripts
       postrotate
           docker compose exec nginx nginx -s reopen
       endscript
   }
   ```

2. **Set Up Grafana Dashboards**:
   - Import Nginx overview dashboard
   - Create custom dashboards for business metrics
   - Configure alert rules in Prometheus

3. **Enable JSON Logging** (Optional):
   - Uncomment JSON log line in `snippets/logging.conf`
   - Configure log aggregation system (Loki, ELK)
   - Set up log parsing and indexing

4. **Configure Alerting**:
   - Set up Alertmanager
   - Define alert rules for critical metrics
   - Configure notification channels (email, SMS, Slack)

## Conclusion

Task 31.5 is complete with all requirements satisfied:
- ✅ Access logs with response times configured
- ✅ Error logs configured at multiple levels
- ✅ nginx-prometheus-exporter integrated
- ✅ Prometheus scraping configured
- ✅ Comprehensive tests passing (24/24)
- ✅ Documentation complete

The logging and monitoring system provides comprehensive visibility into Nginx performance and health, enabling proactive issue detection and resolution.
