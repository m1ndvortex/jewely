# Nginx Logging and Monitoring

This document describes the logging and monitoring configuration for Nginx in the Jewelry SaaS Platform.

## Overview

The Nginx logging and monitoring system provides:
- **Detailed access logs** with response time metrics
- **Multi-level error logging** for different severity levels
- **Prometheus metrics** via nginx-prometheus-exporter
- **Structured logging** support (JSON format)
- **Performance monitoring** capabilities

## Access Logging

### Log Format

Access logs use a custom format that includes detailed timing information:

```nginx
log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                '$status $body_bytes_sent "$http_referer" '
                '"$http_user_agent" "$http_x_forwarded_for" '
                'rt=$request_time uct="$upstream_connect_time" '
                'uht="$upstream_header_time" urt="$upstream_response_time"';
```

### Timing Metrics

| Metric | Variable | Description |
|--------|----------|-------------|
| Request Time | `$request_time` | Total time to process request (seconds) |
| Upstream Connect Time | `$upstream_connect_time` | Time to establish connection with Django |
| Upstream Header Time | `$upstream_header_time` | Time to receive response headers from Django |
| Upstream Response Time | `$upstream_response_time` | Time to receive full response from Django |

### Example Log Entry

```
172.18.0.1 - - [07/Nov/2025:10:30:45 +0000] "GET /api/inventory/ HTTP/1.1" 200 1234 "-" "Mozilla/5.0" "-" rt=0.123 uct="0.001" uht="0.050" urt="0.122"
```

### JSON Logging

For structured log aggregation (Loki, ELK, etc.), a JSON format is also available:

```nginx
log_format json_combined escape=json
    '{'
        '"time_local":"$time_local",'
        '"remote_addr":"$remote_addr",'
        '"request":"$request",'
        '"status": "$status",'
        '"request_time":"$request_time",'
        '"upstream_response_time":"$upstream_response_time"'
        // ... more fields
    '}';
```

To enable JSON logging, uncomment the line in `snippets/logging.conf`:

```nginx
access_log /var/log/nginx/access-json.log json_combined buffer=32k flush=5s;
```

### Log Buffering

Access logs use buffering for better performance:
- **Buffer size**: 32KB
- **Flush interval**: 5 seconds

This reduces disk I/O while ensuring logs are written regularly.

## Error Logging

### Log Levels

Two error logs are configured:

1. **Standard Error Log** (`/var/log/nginx/error.log`)
   - Level: `warn`
   - Logs warnings and above (warn, error, crit, alert, emerg)
   - Used for general error monitoring

2. **Critical Error Log** (`/var/log/nginx/error-critical.log`)
   - Level: `crit`
   - Logs only critical errors and above (crit, alert, emerg)
   - Used for alerting on severe issues

### Log Level Hierarchy

```
debug < info < notice < warn < error < crit < alert < emerg
```

## Prometheus Metrics

### Nginx Metrics Exporter

The `nginx-prometheus-exporter` scrapes metrics from Nginx's `stub_status` module and exposes them in Prometheus format.

**Service**: `nginx_exporter`
**Port**: 9113
**Metrics Endpoint**: `http://nginx_exporter:9113/metrics`

### Available Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `nginx_connections_active` | Gauge | Number of active connections |
| `nginx_connections_reading` | Gauge | Connections reading request |
| `nginx_connections_writing` | Gauge | Connections writing response |
| `nginx_connections_waiting` | Gauge | Idle keepalive connections |
| `nginx_http_requests_total` | Counter | Total HTTP requests |
| `nginx_connections_accepted` | Counter | Accepted connections |
| `nginx_connections_handled` | Counter | Handled connections |

### Stub Status Endpoint

**Endpoint**: `http://nginx/nginx_status`
**Access**: Restricted to internal networks only

Example output:
```
Active connections: 42
server accepts handled requests
 1234 1234 5678
Reading: 0 Writing: 5 Waiting: 37
```

### Security

The metrics endpoint is restricted to:
- Localhost (127.0.0.1)
- Docker networks (172.16.0.0/12)
- Private networks (10.0.0.0/8, 192.168.0.0/16)

Public access is denied for security.

## Prometheus Integration

### Scrape Configuration

Prometheus scrapes nginx_exporter every 30 seconds:

```yaml
scrape_configs:
  - job_name: 'nginx'
    static_configs:
      - targets: ['nginx_exporter:9113']
        labels:
          service: 'nginx'
          component: 'proxy'
    scrape_interval: 30s
    scrape_timeout: 10s
```

### Querying Metrics

Example Prometheus queries:

```promql
# Active connections
nginx_connections_active

# Request rate (requests per second)
rate(nginx_http_requests_total[5m])

# Connection acceptance rate
rate(nginx_connections_accepted[5m])

# Connection handling efficiency
nginx_connections_handled / nginx_connections_accepted
```

## Grafana Dashboards

Pre-built Grafana dashboards are available for visualizing Nginx metrics:

1. **Nginx Overview Dashboard**
   - Active connections
   - Request rate
   - Response times (from access logs)
   - Error rates

2. **Nginx Performance Dashboard**
   - Connection states (reading, writing, waiting)
   - Request throughput
   - Upstream response times
   - Cache hit rates

## Log Management

### Log Location

All logs are stored in a Docker volume for persistence:

```yaml
volumes:
  nginx_logs:/var/log/nginx
```

### Accessing Logs

View logs from the host:

```bash
# Access logs
docker compose exec nginx tail -f /var/log/nginx/access.log

# Error logs
docker compose exec nginx tail -f /var/log/nginx/error.log

# Critical errors only
docker compose exec nginx tail -f /var/log/nginx/error-critical.log
```

### Log Rotation

For production, configure log rotation using logrotate:

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

### Log Analysis

Analyze access logs for performance insights:

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

## Monitoring Best Practices

### 1. Set Up Alerts

Configure Prometheus alerts for:
- High error rates (5xx responses)
- Slow response times (>2 seconds)
- High connection counts
- Low connection handling efficiency

### 2. Monitor Key Metrics

Focus on:
- **Request rate**: Sudden spikes or drops
- **Response times**: P50, P95, P99 percentiles
- **Error rates**: 4xx and 5xx responses
- **Connection states**: High waiting connections may indicate keepalive issues

### 3. Regular Log Review

- Review error logs daily
- Investigate critical errors immediately
- Analyze slow requests weekly
- Monitor log growth and rotate appropriately

### 4. Performance Tuning

Use metrics to optimize:
- Worker processes and connections
- Buffer sizes
- Timeout values
- Keepalive settings

## Troubleshooting

### No Metrics Available

1. Check if nginx_exporter is running:
   ```bash
   docker compose ps nginx_exporter
   ```

2. Verify nginx_status endpoint:
   ```bash
   docker compose exec nginx curl http://localhost/nginx_status
   ```

3. Check exporter logs:
   ```bash
   docker compose logs nginx_exporter
   ```

### Missing Timing Metrics in Logs

1. Verify log format includes timing variables:
   ```bash
   docker compose exec nginx grep "log_format main" /etc/nginx/nginx.conf
   ```

2. Check if logging snippet is included:
   ```bash
   docker compose exec nginx nginx -T | grep "snippets/logging.conf"
   ```

### High Log Volume

1. Disable access logging for static files (already configured)
2. Disable access logging for health checks (already configured)
3. Increase buffer size and flush interval
4. Consider sampling (log 1 in N requests)

## Configuration Files

- **Main config**: `docker/nginx/nginx.conf`
- **Logging snippet**: `docker/nginx/snippets/logging.conf`
- **Metrics snippet**: `docker/nginx/snippets/metrics.conf`
- **Site config**: `docker/nginx/conf.d/jewelry-shop.conf`
- **Prometheus config**: `docker/prometheus.yml`

## Requirements Compliance

This configuration satisfies:

- **Requirement 22, Criterion 9**: Logs all requests with response times and status codes
- **Requirement 22, Criterion 10**: Exports metrics for Prometheus monitoring
- **Requirement 24, Criterion 3**: Exposes Nginx metrics using nginx-prometheus-exporter

## Additional Resources

- [Nginx Logging Documentation](http://nginx.org/en/docs/http/ngx_http_log_module.html)
- [Nginx Stub Status Module](http://nginx.org/en/docs/http/ngx_http_stub_status_module.html)
- [nginx-prometheus-exporter](https://github.com/nginxinc/nginx-prometheus-exporter)
- [Prometheus Nginx Monitoring](https://prometheus.io/docs/guides/nginx/)
