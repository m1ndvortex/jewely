# Grafana Dashboard Configuration for PostgreSQL Cluster

## Overview

This document describes the Grafana dashboards for monitoring the PostgreSQL cluster deployed with Zalando Postgres Operator.

## Prometheus Scrape Configuration

Add this to your Prometheus configuration:

```yaml
scrape_configs:
  - job_name: 'postgresql-exporter'
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names:
            - jewelry-shop
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_port]
        action: replace
        target_label: __address__
        regex: ([^:]+)(?::\d+)?;(\d+)
        replacement: $1:$2
      - source_labels: [__meta_kubernetes_pod_label_application]
        action: keep
        regex: spilo
      - source_labels: [__meta_kubernetes_pod_label_spilo_role]
        action: replace
        target_label: role
      - source_labels: [__meta_kubernetes_pod_name]
        action: replace
        target_label: pod
```

## Dashboard Panels

### 1. Cluster Overview

**Panel: Cluster Status**
- Metric: `pg_up`
- Type: Stat
- Query: `pg_up{job="postgresql-exporter"}`
- Shows: 1 = UP, 0 = DOWN

**Panel: Master/Replica Count**
- Type: Stat
- Query Master: `count(pg_up{job="postgresql-exporter", role="master"})`
- Query Replicas: `count(pg_up{job="postgresql-exporter", role="replica"})`

**Panel: Pod Health**
- Type: Table
- Query: `pg_up{job="postgresql-exporter"}`
- Columns: Pod, Role, Status, Uptime

### 2. Replication Monitoring

**Panel: Replication Lag (Seconds)**
- Type: Graph
- Query: `pg_replication_lag{job="postgresql-exporter"}`
- Alert: > 10 seconds

**Panel: Replication State**
- Type: Table
- Query: `pg_stat_replication_state{job="postgresql-exporter"}`
- Shows: Client address, state, sync_state

**Panel: WAL Generation Rate**
- Type: Graph
- Query: `rate(pg_stat_wal_bytes[5m])`

### 3. Performance Metrics

**Panel: Queries Per Second**
- Type: Graph
- Query: `rate(pg_stat_database_xact_commit[1m]) + rate(pg_stat_database_xact_rollback[1m])`

**Panel: Transaction Rate**
- Type: Graph
- Query Commits: `rate(pg_stat_database_xact_commit[1m])`
- Query Rollbacks: `rate(pg_stat_database_xact_rollback[1m])`

**Panel: Cache Hit Ratio**
- Type: Gauge
- Query: `(sum(pg_stat_database_blks_hit) / (sum(pg_stat_database_blks_hit) + sum(pg_stat_database_blks_read))) * 100`
- Target: > 95%

**Panel: Active Connections**
- Type: Graph
- Query: `pg_stat_activity_count{state="active"}`

**Panel: Idle Connections**
- Type: Graph
- Query: `pg_stat_activity_count{state="idle"}`

**Panel: Connection Count by State**
- Type: Pie Chart
- Query: `pg_stat_activity_count`
- Group by: state

### 4. Resource Usage

**Panel: CPU Usage**
- Type: Graph
- Query: `rate(container_cpu_usage_seconds_total{pod=~"jewelry-shop-db-.*"}[5m]) * 100`

**Panel: Memory Usage**
- Type: Graph
- Query: `container_memory_usage_bytes{pod=~"jewelry-shop-db-.*"} / 1024 / 1024 / 1024`
- Unit: GB

**Panel: Disk I/O**
- Type: Graph
- Query Read: `rate(container_fs_reads_bytes_total{pod=~"jewelry-shop-db-.*"}[5m])`
- Query Write: `rate(container_fs_writes_bytes_total{pod=~"jewelry-shop-db-.*"}[5m])`

**Panel: Network Traffic**
- Type: Graph
- Query RX: `rate(container_network_receive_bytes_total{pod=~"jewelry-shop-db-.*"}[5m])`
- Query TX: `rate(container_network_transmit_bytes_total{pod=~"jewelry-shop-db-.*"}[5m])`

### 5. Database Size

**Panel: Total Database Size**
- Type: Stat
- Query: `pg_database_size_bytes{datname="jewelry_shop"} / 1024 / 1024 / 1024`
- Unit: GB

**Panel: Database Size Over Time**
- Type: Graph
- Query: `pg_database_size_bytes{datname="jewelry_shop"} / 1024 / 1024 / 1024`

**Panel: Top 10 Largest Tables**
- Type: Table
- Query: `topk(10, pg_table_size_bytes) / 1024 / 1024`
- Unit: MB

**Panel: Index Size**
- Type: Graph
- Query: `sum(pg_index_size_bytes) / 1024 / 1024 / 1024`
- Unit: GB

### 6. Tenant Metrics (Custom)

**Panel: Inventory Count by Tenant**
- Type: Table
- Query: `tenant_inventory_count`
- Shows: Top tenants by inventory size

**Panel: Sales Count by Tenant**
- Type: Table
- Query: `tenant_sales_count`
- Shows: Top tenants by sales volume

**Panel: Customer Count by Tenant**
- Type: Table
- Query: `tenant_customer_count`
- Shows: Top tenants by customer base

### 7. Slow Queries

**Panel: Queries > 1 Second**
- Type: Table
- Query: `pg_stat_statements_mean_exec_time_seconds > 1`
- Shows: Query, execution time, calls

**Panel: Most Called Queries**
- Type: Table
- Query: `topk(10, pg_stat_statements_calls)`

### 8. Locks and Deadlocks

**Panel: Active Locks**
- Type: Graph
- Query: `pg_locks_count`

**Panel: Deadlocks**
- Type: Graph
- Query: `rate(pg_stat_database_deadlocks[5m])`

## Alerts

### Critical Alerts

**PostgreSQL Down**
```yaml
alert: PostgreSQLDown
expr: pg_up == 0
for: 1m
labels:
  severity: critical
annotations:
  summary: "PostgreSQL instance {{ $labels.pod }} is down"
```

**Replication Lag High**
```yaml
alert: ReplicationLagHigh
expr: pg_replication_lag > 30
for: 5m
labels:
  severity: warning
annotations:
  summary: "Replication lag is {{ $value }} seconds on {{ $labels.pod }}"
```

**No Replicas**
```yaml
alert: NoReplicas
expr: count(pg_up{role="replica"}) < 2
for: 5m
labels:
  severity: critical
annotations:
  summary: "Less than 2 replicas available"
```

### Warning Alerts

**High Connection Count**
```yaml
alert: HighConnectionCount
expr: sum(pg_stat_activity_count) > 150
for: 10m
labels:
  severity: warning
annotations:
  summary: "High connection count: {{ $value }}"
```

**Low Cache Hit Ratio**
```yaml
alert: LowCacheHitRatio
expr: (sum(pg_stat_database_blks_hit) / (sum(pg_stat_database_blks_hit) + sum(pg_stat_database_blks_read))) * 100 < 90
for: 15m
labels:
  severity: warning
annotations:
  summary: "Cache hit ratio is {{ $value }}%"
```

**Disk Space Low**
```yaml
alert: DiskSpaceLow
expr: (pg_database_size_bytes / (100 * 1024 * 1024 * 1024)) > 80
for: 10m
labels:
  severity: warning
annotations:
  summary: "Database using {{ $value }}% of 100Gi volume"
```

## Dashboard Import

To import this dashboard into Grafana:

1. Go to Grafana → Dashboards → Import
2. Use the PostgreSQL Exporter dashboard ID: `9628`
3. Or create custom dashboard with the panels above
4. Select Prometheus data source
5. Customize as needed

## Useful Queries

### Check Replication Status
```promql
pg_stat_replication_state{job="postgresql-exporter"}
```

### Database Size Growth Rate
```promql
rate(pg_database_size_bytes{datname="jewelry_shop"}[1h])
```

### Connection Pool Utilization
```promql
pg_stat_activity_count / 200 * 100
```

### Transaction Throughput
```promql
sum(rate(pg_stat_database_xact_commit[5m]))
```

### Average Query Time
```promql
avg(pg_stat_statements_mean_exec_time_seconds)
```

## Dashboard JSON

For a complete dashboard JSON, you can use the community PostgreSQL dashboard:
- Dashboard ID: 9628 (PostgreSQL Database)
- Dashboard ID: 12485 (PostgreSQL Exporter Quickstart)

Or create a custom dashboard with the panels described above.

## Next Steps

1. Deploy Prometheus (Task 35.1)
2. Deploy Grafana (Task 35.2)
3. Import PostgreSQL dashboards
4. Configure alerts
5. Set up notification channels (email, Slack, PagerDuty)
