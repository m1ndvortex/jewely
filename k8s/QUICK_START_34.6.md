# Quick Start: Task 34.6 - PostgreSQL Cluster with Automatic Failover

## Overview

This guide helps you deploy a highly available PostgreSQL cluster with automatic failover using the Zalando Postgres Operator.

**Features:**
- 3 replicas (1 master + 2 replicas) for high availability
- Patroni for automatic leader election and failover (< 30 seconds)
- PgBouncer for connection pooling
- Automated backups with WAL archiving
- postgres_exporter for Prometheus metrics
- 100Gi persistent volumes per instance
- PostgreSQL 15

## Prerequisites

- Kubernetes cluster (k3d) is running
- Namespace `jewelry-shop` exists
- Zalando Postgres Operator is installed (Task 34.5)
- Secrets are configured (Task 34.2)

## Quick Deploy

```bash
# Navigate to k8s directory
cd k8s

# Deploy PostgreSQL cluster
./scripts/deploy-task-34.6.sh

# Wait for cluster to be ready (takes 2-5 minutes)
watch kubectl get pods -n jewelry-shop -l application=spilo

# Validate deployment
./scripts/validate-task-34.6.sh
```

## Manual Deployment Steps

### 1. Apply PostgreSQL Cluster Manifest

```bash
kubectl apply -f postgresql-cluster.yaml
```

### 2. Monitor Cluster Creation

```bash
# Watch postgresql resource
kubectl get postgresql jewelry-shop-db -n jewelry-shop --watch

# Watch pods being created
kubectl get pods -n jewelry-shop -l application=spilo --watch

# Check operator logs
kubectl logs -n postgres-operator -l app.kubernetes.io/name=postgres-operator -f
```

### 3. Verify Cluster Status

```bash
# Check cluster status
kubectl get postgresql jewelry-shop-db -n jewelry-shop

# List all pods
kubectl get pods -n jewelry-shop -l application=spilo -o wide

# Identify master
kubectl get pods -n jewelry-shop -l spilo-role=master

# Identify replicas
kubectl get pods -n jewelry-shop -l spilo-role=replica
```

## Connection Information

### Services Created

The operator automatically creates these services:

1. **jewelry-shop-db** - Master service (read-write)
   - `jewelry-shop-db.jewelry-shop.svc.cluster.local:5432`

2. **jewelry-shop-db-repl** - Replica service (read-only)
   - `jewelry-shop-db-repl.jewelry-shop.svc.cluster.local:5432`

3. **jewelry-shop-db-pooler** - PgBouncer connection pooler (recommended)
   - `jewelry-shop-db-pooler.jewelry-shop.svc.cluster.local:5432`

### Connection Strings

**For Django Application (recommended - uses PgBouncer):**
```
postgresql://jewelry_app:<password>@jewelry-shop-db-pooler.jewelry-shop.svc.cluster.local:5432/jewelry_shop
```

**Direct to Master:**
```
postgresql://jewelry_app:<password>@jewelry-shop-db.jewelry-shop.svc.cluster.local:5432/jewelry_shop
```

**Read-Only Replica:**
```
postgresql://jewelry_app:<password>@jewelry-shop-db-repl.jewelry-shop.svc.cluster.local:5432/jewelry_shop
```

### Get Application Password

```bash
# Get the password created by the operator
kubectl get secret jewelry-app.jewelry-shop-db.credentials.postgresql.acid.zalan.do \
  -n jewelry-shop \
  -o jsonpath='{.data.password}' | base64 -d
echo
```

## Testing

### 1. Connect to Master Pod

```bash
# Get master pod name
MASTER_POD=$(kubectl get pods -n jewelry-shop -l spilo-role=master -o jsonpath='{.items[0].metadata.name}')

# Connect to PostgreSQL
kubectl exec -it -n jewelry-shop $MASTER_POD -- psql -U postgres

# Inside psql:
\l                          # List databases
\c jewelry_shop             # Connect to jewelry_shop database
\dt                         # List tables
SELECT version();           # Check PostgreSQL version
```

### 2. Check Replication Status

```bash
# From master pod
kubectl exec -n jewelry-shop $MASTER_POD -- psql -U postgres -c "
SELECT 
  client_addr,
  state,
  sync_state,
  replay_lag
FROM pg_stat_replication;
"
```

### 3. Test Automatic Failover

```bash
# Identify current master
MASTER_POD=$(kubectl get pods -n jewelry-shop -l spilo-role=master -o jsonpath='{.items[0].metadata.name}')
echo "Current master: $MASTER_POD"

# Kill the master pod
kubectl delete pod $MASTER_POD -n jewelry-shop --grace-period=0 --force

# Watch for new master election (should happen within 30 seconds)
watch kubectl get pods -n jewelry-shop -l application=spilo -L spilo-role

# Verify new master
NEW_MASTER=$(kubectl get pods -n jewelry-shop -l spilo-role=master -o jsonpath='{.items[0].metadata.name}')
echo "New master: $NEW_MASTER"

# Test connection to new master
kubectl exec -n jewelry-shop $NEW_MASTER -- psql -U postgres -c "SELECT 'Failover successful!' AS status;"
```

### 4. Test PgBouncer Connection Pooling

```bash
# Get PgBouncer pod
POOLER_POD=$(kubectl get pods -n jewelry-shop -l application=db-connection-pooler -o jsonpath='{.items[0].metadata.name}')

# Check PgBouncer status
kubectl exec -n jewelry-shop $POOLER_POD -- psql -U pooler -p 5432 -h localhost pgbouncer -c "SHOW POOLS;"

# Check active connections
kubectl exec -n jewelry-shop $POOLER_POD -- psql -U pooler -p 5432 -h localhost pgbouncer -c "SHOW CLIENTS;"
```

### 5. Check Metrics

```bash
# Access postgres_exporter metrics
kubectl exec -n jewelry-shop $MASTER_POD -c postgres-exporter -- wget -q -O- http://localhost:9187/metrics | head -n 20
```

## Monitoring

### View Patroni Logs

```bash
# View Patroni logs from master
kubectl logs -n jewelry-shop $MASTER_POD | grep -i patroni

# View recent failover events
kubectl logs -n jewelry-shop $MASTER_POD | grep -i "failover\|promoted\|leader"
```

### Check Cluster Health

```bash
# Get cluster status
kubectl get postgresql jewelry-shop-db -n jewelry-shop -o yaml

# Check pod events
kubectl describe pod $MASTER_POD -n jewelry-shop

# Check operator events
kubectl get events -n jewelry-shop --sort-by='.lastTimestamp' | grep postgresql
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n jewelry-shop -l application=spilo

# Check pod logs
kubectl logs -n jewelry-shop <pod-name>

# Check operator logs
kubectl logs -n postgres-operator -l app.kubernetes.io/name=postgres-operator --tail=100

# Check events
kubectl get events -n jewelry-shop --sort-by='.lastTimestamp'
```

### Master Not Elected

```bash
# Check Patroni status in each pod
for pod in $(kubectl get pods -n jewelry-shop -l application=spilo -o name); do
  echo "=== $pod ==="
  kubectl exec -n jewelry-shop $pod -- patronictl list
done

# Check if DCS (etcd/consul) is accessible
kubectl logs -n jewelry-shop $MASTER_POD | grep -i "dcs\|etcd\|consul"
```

### Replication Not Working

```bash
# Check replication status
kubectl exec -n jewelry-shop $MASTER_POD -- psql -U postgres -c "SELECT * FROM pg_stat_replication;"

# Check replica logs
REPLICA_POD=$(kubectl get pods -n jewelry-shop -l spilo-role=replica -o jsonpath='{.items[0].metadata.name}')
kubectl logs -n jewelry-shop $REPLICA_POD | grep -i "replication\|recovery"

# Check replication lag
kubectl exec -n jewelry-shop $MASTER_POD -- psql -U postgres -c "
SELECT 
  client_addr,
  state,
  sync_state,
  EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) AS lag_seconds
FROM pg_stat_replication;
"
```

### PgBouncer Issues

```bash
# Check PgBouncer logs
kubectl logs -n jewelry-shop $POOLER_POD

# Check PgBouncer configuration
kubectl exec -n jewelry-shop $POOLER_POD -- cat /etc/pgbouncer/pgbouncer.ini

# Test direct connection (bypass PgBouncer)
kubectl exec -n jewelry-shop $POOLER_POD -- psql -h jewelry-shop-db -U jewelry_app -d jewelry_shop -c "SELECT 1;"
```

### Storage Issues

```bash
# Check PVCs
kubectl get pvc -n jewelry-shop -l application=spilo

# Check PV status
kubectl get pv

# Check disk usage in pod
kubectl exec -n jewelry-shop $MASTER_POD -- df -h /home/postgres/pgdata
```

## Configuration

### Adjust Resources

Edit `postgresql-cluster.yaml`:

```yaml
spec:
  resources:
    requests:
      cpu: 1000m      # Increase for better performance
      memory: 2Gi
    limits:
      cpu: 4000m
      memory: 4Gi
```

### Adjust Volume Size

```yaml
spec:
  volume:
    size: 200Gi      # Increase storage
```

### Adjust Connection Pool Size

```yaml
spec:
  connectionPooler:
    parameters:
      default_pool_size: "50"    # Increase pool size
      max_client_conn: "2000"    # Increase max connections
```

### Configure Backup Schedule

```yaml
spec:
  logicalBackupSchedule: "0 2 * * *"  # Daily at 2 AM
```

## Performance Tuning

### PostgreSQL Parameters

Key parameters in `postgresql-cluster.yaml`:

```yaml
postgresql:
  parameters:
    max_connections: "200"              # Adjust based on load
    shared_buffers: "256MB"             # 25% of RAM
    effective_cache_size: "1GB"         # 50-75% of RAM
    work_mem: "2621kB"                  # RAM / max_connections / 16
    maintenance_work_mem: "64MB"        # RAM / 16
```

### Monitor Query Performance

```bash
# Enable pg_stat_statements
kubectl exec -n jewelry-shop $MASTER_POD -- psql -U postgres -c "
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
"

# View slow queries
kubectl exec -n jewelry-shop $MASTER_POD -- psql -U postgres -c "
SELECT 
  query,
  calls,
  total_exec_time,
  mean_exec_time,
  max_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
"
```

## Security

### Rotate Passwords

```bash
# Generate new password
NEW_PASSWORD=$(openssl rand -base64 32)

# Update secret
kubectl patch secret postgres-secrets -n jewelry-shop \
  -p "{\"data\":{\"app-password\":\"$(echo -n $NEW_PASSWORD | base64)\"}}"

# Restart pods to pick up new password
kubectl rollout restart statefulset jewelry-shop-db -n jewelry-shop
```

### Enable SSL/TLS

Edit `postgresql-cluster.yaml`:

```yaml
spec:
  postgresql:
    parameters:
      ssl: "on"
      ssl_cert_file: "/path/to/cert.pem"
      ssl_key_file: "/path/to/key.pem"
```

## Backup and Recovery

### Manual Backup

```bash
# Trigger manual backup
kubectl exec -n jewelry-shop $MASTER_POD -- pg_dump -U postgres jewelry_shop > backup.sql

# Or use pg_basebackup for physical backup
kubectl exec -n jewelry-shop $MASTER_POD -- pg_basebackup -D /tmp/backup -F tar -z -P
```

### Point-in-Time Recovery

```bash
# Clone cluster to specific point in time
# Edit postgresql-cluster.yaml:
spec:
  clone:
    cluster: "jewelry-shop-db"
    timestamp: "2024-01-01 12:00:00+00:00"
```

## Next Steps

1. **Update Django Deployment** - Configure Django to use the new database
2. **Set Up Monitoring** - Create Grafana dashboards for PostgreSQL metrics
3. **Configure Backups** - Set up WAL-E or WAL-G for cloud backups
4. **Load Testing** - Test performance under load
5. **Disaster Recovery** - Document and test DR procedures

## Useful Commands

```bash
# Quick status check
kubectl get postgresql,pods,svc,pvc -n jewelry-shop -l application=spilo

# Watch cluster in real-time
watch -n 2 'kubectl get pods -n jewelry-shop -l application=spilo -L spilo-role'

# Get all cluster information
kubectl get postgresql jewelry-shop-db -n jewelry-shop -o yaml

# Port-forward to access locally
kubectl port-forward -n jewelry-shop svc/jewelry-shop-db-pooler 5432:5432

# Then connect locally
psql -h localhost -U jewelry_app -d jewelry_shop
```

## References

- [Zalando Postgres Operator Documentation](https://postgres-operator.readthedocs.io/)
- [Patroni Documentation](https://patroni.readthedocs.io/)
- [PgBouncer Documentation](https://www.pgbouncer.org/)
- [PostgreSQL High Availability](https://www.postgresql.org/docs/current/high-availability.html)
