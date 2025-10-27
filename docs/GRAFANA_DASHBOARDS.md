# Grafana Dashboards Guide

## Overview

This document provides comprehensive guidance on using Grafana dashboards for monitoring the Jewelry SaaS Platform. Grafana provides powerful visualization and analytics capabilities for all system metrics collected by Prometheus.

**Per Requirement 24.6**: The System SHALL provide Grafana dashboards for system overview, application performance, database performance, and infrastructure health.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Accessing Grafana](#accessing-grafana)
3. [Available Dashboards](#available-dashboards)
4. [Dashboard Details](#dashboard-details)
5. [Creating Custom Dashboards](#creating-custom-dashboards)
6. [Alert Configuration](#alert-configuration)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Starting Grafana

```bash
# Start all services including Grafana
docker-compose up -d

# Check Grafana is running
docker-compose ps grafana

# View Grafana logs
docker-compose logs -f grafana
```

### First-Time Setup

1. **Access Grafana**: Navigate to http://localhost:3000
2. **Login**: Use credentials from `.env` file (default: admin/admin)
3. **Change Password**: You'll be prompted to change the default password
4. **Verify Data Source**: Go to Configuration → Data Sources → Prometheus (should be pre-configured)
5. **View Dashboards**: Go to Dashboards → Browse to see all available dashboards

---

## Accessing Grafana

### Local Development

- **URL**: http://localhost:3000
- **Default Username**: admin
- **Default Password**: admin (change on first login)

### Production

- **URL**: https://grafana.yourdomain.com
- **Authentication**: Configure via environment variables in `.env`

### Environment Variables

```bash
# .env file
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=your-secure-password-here
```

---

## Available Dashboards

The platform includes four comprehensive pre-built dashboards:

### 1. System Overview
**UID**: `system-overview`  
**Purpose**: High-level view of overall system health  
**Refresh Rate**: 30 seconds  
**Key Metrics**:
- CPU Usage (gauge)
- Memory Usage (gauge)
- Disk Usage (gauge)
- Database Connections (time series)
- HTTP Requests per Second (time series)
- Response Time p50/p95 (time series)

**Use Cases**:
- Quick health check
- Identifying system-wide issues
- Monitoring resource utilization
- Tracking request patterns

### 2. Application Performance
**UID**: `application-performance`  
**Purpose**: Deep dive into Django application metrics  
**Refresh Rate**: 30 seconds  
**Key Metrics**:
- HTTP Response Status Codes (2xx, 4xx, 5xx)
- Error Rate (gauge)
- Response Time p95 (gauge)
- Response Time by Endpoint (time series)
- Requests per Second by Endpoint (time series)
- Database Operations by Model (time series)
- Exceptions by Type (time series)

**Use Cases**:
- Identifying slow endpoints
- Monitoring error rates
- Tracking application performance
- Debugging performance issues

### 3. Database Performance
**UID**: `database-performance`  
**Purpose**: PostgreSQL database monitoring  
**Refresh Rate**: 30 seconds  
**Key Metrics**:
- Active Connections (gauge)
- Cache Hit Ratio (gauge)
- Transactions per Second (gauge)
- Database Size (gauge)
- Database Operations per Second (inserts, updates, deletes)
- Connection Usage (time series)
- Cache Performance (time series)
- Transaction Activity (commits, rollbacks)

**Use Cases**:
- Monitoring database health
- Identifying connection pool issues
- Optimizing query performance
- Tracking database growth

### 4. Infrastructure Health
**UID**: `infrastructure-health`  
**Purpose**: System-level infrastructure monitoring  
**Refresh Rate**: 30 seconds  
**Key Metrics**:
- CPU Usage Over Time (time series)
- Memory Usage (time series)
- Disk Usage (time series)
- Network Traffic (time series)
- Redis Memory Usage (time series)
- Redis Activity (time series)
- Service Health Status (bar gauge for all services)

**Use Cases**:
- Infrastructure capacity planning
- Identifying resource bottlenecks
- Monitoring service availability
- Tracking Redis performance

---

## Dashboard Details

### System Overview Dashboard

#### CPU Usage Gauge
- **Metric**: `100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)`
- **Thresholds**: 
  - Green: 0-80%
  - Red: >80%
- **Action**: If consistently >80%, consider scaling or optimizing

#### Memory Usage Gauge
- **Metric**: `(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100`
- **Thresholds**:
  - Green: 0-70%
  - Yellow: 70-85%
  - Red: >85%
- **Action**: If >85%, investigate memory leaks or scale up

#### Disk Usage Gauge
- **Metric**: `100 - ((node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100)`
- **Thresholds**:
  - Green: 0-75%
  - Yellow: 75-90%
  - Red: >90%
- **Action**: If >90%, clean up old backups or expand storage

#### Database Connections
- **Metric**: `pg_stat_database_numbackends{datname="jewelry_shop"}`
- **Purpose**: Monitor connection pool usage
- **Action**: If approaching max_connections, tune connection pooling

#### HTTP Requests per Second
- **Metric**: `rate(django_http_requests_total_by_method_total[5m])`
- **Purpose**: Track request volume by HTTP method
- **Action**: Use for capacity planning and traffic analysis

#### Response Time (p50, p95)
- **Metrics**: 
  - p95: `histogram_quantile(0.95, rate(django_http_requests_latency_seconds_by_view_method_bucket[5m]))`
  - p50: `histogram_quantile(0.50, rate(django_http_requests_latency_seconds_by_view_method_bucket[5m]))`
- **Target**: p95 < 500ms (per Requirement 26.2)
- **Action**: If p95 >500ms, investigate slow endpoints

### Application Performance Dashboard

#### HTTP Response Status Codes
- **Metrics**:
  - 2xx Success: `rate(django_http_responses_total_by_status_total{status=~"2.."}[5m])`
  - 4xx Client Error: `rate(django_http_responses_total_by_status_total{status=~"4.."}[5m])`
  - 5xx Server Error: `rate(django_http_responses_total_by_status_total{status=~"5.."}[5m])`
- **Purpose**: Monitor request success/failure rates
- **Action**: Investigate spikes in 4xx or 5xx errors

#### Error Rate Gauge
- **Metric**: `rate(django_http_responses_total_by_status_total{status=~"5.."}[5m]) / rate(django_http_responses_total_by_status_total[5m])`
- **Thresholds**:
  - Green: 0-1%
  - Yellow: 1-5%
  - Red: >5%
- **Action**: If >1%, check Sentry for error details

#### Response Time by Endpoint
- **Metric**: `histogram_quantile(0.95, rate(django_http_requests_latency_seconds_by_view_method_bucket[5m]))`
- **Purpose**: Identify slow endpoints
- **Action**: Optimize queries, add caching, or refactor slow views

#### Database Operations by Model
- **Metrics**:
  - Inserts: `django_model_inserts_total`
  - Updates: `django_model_updates_total`
  - Deletes: `django_model_deletes_total`
- **Purpose**: Track database activity by Django model
- **Action**: Identify hot models for optimization

### Database Performance Dashboard

#### Active Connections Gauge
- **Metric**: `pg_stat_database_numbackends{datname="jewelry_shop"}`
- **Thresholds**:
  - Green: 0-50
  - Yellow: 50-80
  - Red: >80
- **Action**: If >80, check for connection leaks or tune pool size

#### Cache Hit Ratio Gauge
- **Metric**: `pg_stat_database_blks_hit{datname="jewelry_shop"} / (pg_stat_database_blks_hit{datname="jewelry_shop"} + pg_stat_database_blks_read{datname="jewelry_shop"})`
- **Target**: >90%
- **Action**: If <90%, increase shared_buffers or optimize queries

#### Transactions per Second
- **Metric**: `rate(pg_stat_database_xact_commit{datname="jewelry_shop"}[5m])`
- **Purpose**: Monitor transaction throughput
- **Action**: Use for capacity planning

#### Database Size
- **Metric**: `pg_database_size_bytes{datname="jewelry_shop"}`
- **Purpose**: Track database growth
- **Action**: Plan for storage expansion

### Infrastructure Health Dashboard

#### Service Health Status
- **Metrics**: `up{job="<service_name>"}`
- **Services Monitored**:
  - Django
  - PostgreSQL
  - Redis
  - Celery
  - Nginx
- **Display**: Bar gauge (Green=Up, Red=Down)
- **Action**: If any service is down, check logs immediately

#### Redis Memory Usage
- **Metrics**:
  - Used: `redis_memory_used_bytes`
  - Max: `redis_memory_max_bytes`
- **Purpose**: Monitor Redis memory consumption
- **Action**: If approaching max, increase memory or tune eviction policy

#### Network Traffic
- **Metrics**:
  - Receive: `rate(node_network_receive_bytes_total[5m])`
  - Transmit: `rate(node_network_transmit_bytes_total[5m])`
- **Purpose**: Monitor network bandwidth usage
- **Action**: Identify traffic spikes or DDoS attacks

---

## Creating Custom Dashboards

### Using the Grafana UI

1. **Create New Dashboard**:
   - Click "+" icon → Dashboard
   - Click "Add new panel"

2. **Configure Panel**:
   - Select Prometheus data source
   - Enter PromQL query
   - Choose visualization type (Time series, Gauge, Bar gauge, etc.)
   - Configure thresholds and colors

3. **Save Dashboard**:
   - Click "Save dashboard" icon
   - Enter title and description
   - Choose folder
   - Click "Save"

### Example: Custom Sales Dashboard

```promql
# Total sales today
sum(increase(django_model_inserts_total{model="Sale"}[24h]))

# Average sale amount (requires custom metric)
avg(sale_total_amount)

# Sales by branch
sum by (branch) (increase(django_model_inserts_total{model="Sale"}[24h]))

# Top selling products
topk(10, sum by (product) (sale_item_quantity))
```

### Exporting Dashboards

```bash
# Export dashboard JSON
# Go to Dashboard → Settings → JSON Model
# Copy JSON and save to file

# Import dashboard
# Go to Dashboards → Import
# Paste JSON or upload file
```

---

## Alert Configuration

### Creating Alerts in Grafana

1. **Edit Panel**:
   - Open dashboard
   - Click panel title → Edit

2. **Add Alert Rule**:
   - Go to "Alert" tab
   - Click "Create alert rule from this panel"
   - Configure conditions

3. **Configure Notification**:
   - Set alert name
   - Define evaluation interval
   - Set conditions (e.g., "WHEN avg() OF query(A, 5m) IS ABOVE 80")
   - Add notification channel

### Example Alert Rules

#### High CPU Usage
```yaml
Alert Name: High CPU Usage
Condition: avg() OF query(A, 5m) IS ABOVE 80
Evaluation: Every 1m for 5m
Notification: Email, Slack
Message: "CPU usage is above 80% for 5 minutes"
```

#### High Error Rate
```yaml
Alert Name: High Error Rate
Condition: avg() OF query(A, 5m) IS ABOVE 0.05
Evaluation: Every 1m for 2m
Notification: Email, SMS, Slack
Message: "Error rate is above 5% for 2 minutes"
```

#### Database Connection Pool Exhaustion
```yaml
Alert Name: Database Connection Pool Near Limit
Condition: avg() OF query(A, 5m) IS ABOVE 80
Evaluation: Every 1m for 3m
Notification: Email, Slack
Message: "Database connections are above 80 for 3 minutes"
```

### Notification Channels

#### Email
```bash
# Configure in Grafana UI
# Alerting → Notification channels → New channel
# Type: Email
# Addresses: admin@example.com, ops@example.com
```

#### Slack
```bash
# Type: Slack
# Webhook URL: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
# Channel: #alerts
```

---

## Best Practices

### Dashboard Organization

1. **Use Folders**: Organize dashboards by category (System, Application, Business)
2. **Naming Convention**: Use clear, descriptive names (e.g., "Production - System Overview")
3. **Tags**: Add tags for easy filtering (e.g., "production", "database", "critical")
4. **Variables**: Use template variables for dynamic filtering

### Performance Optimization

1. **Limit Time Range**: Use shorter time ranges for better performance
2. **Reduce Query Frequency**: Use appropriate refresh intervals (30s-1m)
3. **Optimize Queries**: Use recording rules for complex queries
4. **Limit Panels**: Keep dashboards focused (8-12 panels max)

### Monitoring Strategy

1. **Start with Overview**: Check System Overview dashboard first
2. **Drill Down**: Use specific dashboards for detailed investigation
3. **Set Baselines**: Understand normal behavior for your system
4. **Regular Reviews**: Review dashboards weekly to identify trends

### Security

1. **Change Default Password**: Always change admin password on first login
2. **Use HTTPS**: Enable SSL/TLS in production
3. **Restrict Access**: Use authentication and role-based access control
4. **Audit Logs**: Enable and review Grafana audit logs

---

## Troubleshooting

### Grafana Won't Start

```bash
# Check container status
docker-compose ps grafana

# View logs
docker-compose logs grafana

# Common issues:
# - Port 3000 already in use
# - Volume permission issues
# - Invalid configuration

# Solution: Check docker-compose.yml and .env file
```

### No Data in Dashboards

```bash
# Check Prometheus is running
docker-compose ps prometheus

# Check Prometheus targets
# Open http://localhost:9090/targets
# All targets should be "UP"

# Check data source configuration
# Grafana → Configuration → Data Sources → Prometheus
# Test connection should succeed

# Check metrics are being collected
# Open http://localhost:9090/graph
# Query: up
# Should show all services
```

### Dashboard Not Loading

```bash
# Check browser console for errors
# F12 → Console

# Common issues:
# - Invalid PromQL query
# - Missing metrics
# - Time range too large

# Solution: Simplify query or reduce time range
```

### Slow Dashboard Performance

```bash
# Reduce time range (e.g., from 24h to 1h)
# Increase refresh interval (e.g., from 10s to 30s)
# Simplify complex queries
# Use recording rules in Prometheus
```

### Authentication Issues

```bash
# Reset admin password
docker-compose exec grafana grafana-cli admin reset-admin-password newpassword

# Check environment variables
docker-compose exec grafana env | grep GRAFANA
```

---

## Advanced Features

### Template Variables

Create dynamic dashboards with variables:

```bash
# Example: Branch selector
# Variable name: branch
# Type: Query
# Data source: Prometheus
# Query: label_values(django_http_requests_total, branch)

# Use in queries: django_http_requests_total{branch="$branch"}
```

### Annotations

Mark important events on dashboards:

```bash
# Example: Deployment annotations
# Query: deployment_timestamp
# Display: Vertical line with deployment version
```

### Playlist

Auto-rotate through dashboards:

```bash
# Dashboards → Playlists → New Playlist
# Add dashboards
# Set interval (e.g., 30 seconds)
# Start playlist
```

### Reporting

Generate PDF reports:

```bash
# Requires Grafana Enterprise or Image Renderer plugin
# Dashboard → Share → Export → PDF
```

---

## Integration with Other Tools

### Prometheus

- **Data Source**: Pre-configured automatically
- **URL**: http://prometheus:9090
- **Access**: Proxy mode (through Grafana backend)

### Loki (Future)

- **Purpose**: Log aggregation and visualization
- **Configuration**: Add Loki data source when deployed
- **URL**: http://loki:3100

### Sentry

- **Purpose**: Error tracking
- **Integration**: Link from Grafana alerts to Sentry issues
- **URL**: Configure in notification templates

---

## Resources

### Official Documentation

- [Grafana Documentation](https://grafana.com/docs/grafana/latest/)
- [Prometheus Data Source](https://grafana.com/docs/grafana/latest/datasources/prometheus/)
- [Dashboard Best Practices](https://grafana.com/docs/grafana/latest/best-practices/best-practices-for-creating-dashboards/)

### Community Dashboards

- [Grafana Dashboard Library](https://grafana.com/grafana/dashboards/)
- [Django Monitoring Dashboard](https://grafana.com/grafana/dashboards/12900)
- [PostgreSQL Dashboard](https://grafana.com/grafana/dashboards/9628)

### Training

- [Grafana Fundamentals](https://grafana.com/tutorials/grafana-fundamentals/)
- [PromQL Basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)

---

## Requirements Satisfied

This Grafana integration satisfies the following requirements:

- ✅ **Requirement 24.6**: Grafana dashboards for system overview, application performance, database performance, and infrastructure health
- ✅ **Requirement 7.2**: Service status monitoring (via Infrastructure Health dashboard)
- ✅ **Requirement 7.4**: API response times and database query performance monitoring
- ✅ **Requirement 7.5**: Alert configuration for system metrics

---

## Next Steps

1. **Task 19.5**: Write monitoring tests
2. **Task 20**: Implement audit logs and security monitoring
3. **Task 35.3**: Deploy Loki for log aggregation
4. **Task 35.4**: Implement distributed tracing with OpenTelemetry

---

## Support

For issues or questions:
- Check logs: `docker-compose logs grafana`
- Review Prometheus metrics: http://localhost:9090
- Consult [Grafana Community](https://community.grafana.com/)
