# Task 34.5: Zalando Postgres Operator Installation - Quick Start Guide

## Overview

This guide covers the installation and configuration of the Zalando Postgres Operator for Kubernetes. The operator provides automated PostgreSQL cluster management with high availability, automatic failover, and backup capabilities.

## Prerequisites

- k3d cluster running (from task 34.1)
- kubectl configured and working
- Internet connection for downloading Helm and operator images

## What Gets Installed

1. **Helm** - Kubernetes package manager (if not already installed)
2. **Zalando Postgres Operator** - Manages PostgreSQL clusters
3. **Custom Resource Definition (CRD)** - `postgresql.acid.zalan.do`
4. **Operator Pod** - Runs in `postgres-operator` namespace

## Quick Start

### Step 1: Deploy the Operator

```bash
# Run the deployment script
./k8s/scripts/deploy-task-34.5.sh
```

This script will:
- Install Helm if not present
- Add the Zalando Postgres Operator Helm repository
- Create the `postgres-operator` namespace
- Install the operator with Helm
- Wait for the operator pod to be ready
- Verify CRD installation

### Step 2: Validate the Installation

```bash
# Run the validation script
./k8s/scripts/validate-task-34.5.sh
```

This script validates:
- Helm installation
- Namespace existence
- Operator pod status and readiness
- CRD existence
- Operator logs for errors
- Operator watch capability
- Helm release status

## Manual Verification

### Check Operator Pod

```bash
# View operator pod
kubectl get pods -n postgres-operator

# Expected output:
# NAME                                 READY   STATUS    RESTARTS   AGE
# postgres-operator-xxxxxxxxxx-xxxxx   1/1     Running   0          2m
```

### Check CRD

```bash
# List PostgreSQL CRD
kubectl get crd postgresqls.acid.zalan.do

# Expected output:
# NAME                          CREATED AT
# postgresqls.acid.zalan.do     2024-XX-XXTXX:XX:XXZ
```

### Check Operator Logs

```bash
# View operator logs
kubectl logs -n postgres-operator -l app.kubernetes.io/name=postgres-operator --tail=50

# Look for messages like:
# - "controller started"
# - "watching namespace: *"
# - No critical errors
```

### Test Operator Watch Capability

```bash
# List postgresql resources (should return empty list, not error)
kubectl get postgresql --all-namespaces

# Expected output:
# No resources found
```

## Configuration Details

### Helm Values Used

The operator is installed with the following configuration:

```yaml
configKubernetes:
  enable_pod_antiaffinity: true  # Spread pods across nodes
  watched_namespace: "*"          # Watch all namespaces
```

### Operator Capabilities

The Zalando Postgres Operator provides:

1. **Automated Cluster Management**
   - Creates and manages PostgreSQL clusters
   - Handles pod lifecycle

2. **High Availability**
   - Patroni integration for leader election
   - Automatic failover on master failure
   - Streaming replication

3. **Backup and Recovery**
   - WAL archiving
   - Point-in-time recovery (PITR)
   - Scheduled backups

4. **Connection Pooling**
   - PgBouncer integration
   - Connection management

5. **Monitoring**
   - Prometheus metrics via postgres_exporter
   - Health checks

## Troubleshooting

### Operator Pod Not Starting

```bash
# Check pod events
kubectl describe pod -n postgres-operator -l app.kubernetes.io/name=postgres-operator

# Check pod logs
kubectl logs -n postgres-operator -l app.kubernetes.io/name=postgres-operator
```

### CRD Not Created

```bash
# List all CRDs
kubectl get crd | grep postgres

# If missing, reinstall operator
helm uninstall postgres-operator -n postgres-operator
./k8s/scripts/deploy-task-34.5.sh
```

### Helm Installation Issues

```bash
# Check Helm version
helm version

# List Helm repositories
helm repo list

# Update repositories
helm repo update
```

## Next Steps

After successful installation:

1. **Review Completion Report**
   ```bash
   cat k8s/TASK_34.5_COMPLETION_REPORT.md
   ```

2. **Proceed to Task 34.6**
   - Deploy PostgreSQL cluster with automatic failover
   - Configure Patroni for leader election
   - Set up streaming replication

## Useful Commands

### Operator Management

```bash
# View operator status
kubectl get pods -n postgres-operator -o wide

# View operator logs (live)
kubectl logs -n postgres-operator -l app.kubernetes.io/name=postgres-operator -f

# Restart operator
kubectl rollout restart deployment postgres-operator -n postgres-operator

# View Helm release
helm list -n postgres-operator

# Upgrade operator
helm upgrade postgres-operator postgres-operator-charts/postgres-operator -n postgres-operator
```

### CRD Management

```bash
# View CRD details
kubectl get crd postgresqls.acid.zalan.do -o yaml

# View CRD documentation
kubectl explain postgresql

# View CRD spec
kubectl explain postgresql.spec
```

### Cleanup (if needed)

```bash
# Uninstall operator
helm uninstall postgres-operator -n postgres-operator

# Delete namespace
kubectl delete namespace postgres-operator

# Remove CRD (careful - deletes all PostgreSQL clusters!)
kubectl delete crd postgresqls.acid.zalan.do
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Kubernetes Cluster                  │
│                                                      │
│  ┌────────────────────────────────────────────┐    │
│  │      postgres-operator namespace           │    │
│  │                                             │    │
│  │  ┌──────────────────────────────────┐     │    │
│  │  │   Postgres Operator Pod          │     │    │
│  │  │                                   │     │    │
│  │  │  - Watches postgresql CRs        │     │    │
│  │  │  - Creates/manages clusters      │     │    │
│  │  │  - Handles failover               │     │    │
│  │  │  - Manages backups                │     │    │
│  │  └──────────────────────────────────┘     │    │
│  └────────────────────────────────────────────┘    │
│                                                      │
│  ┌────────────────────────────────────────────┐    │
│  │      jewelry-shop namespace (future)       │    │
│  │                                             │    │
│  │  ┌──────────────────────────────────┐     │    │
│  │  │   PostgreSQL Cluster             │     │    │
│  │  │   (Created by operator)          │     │    │
│  │  │                                   │     │    │
│  │  │  - Master pod                     │     │    │
│  │  │  - Replica pods                   │     │    │
│  │  │  - PgBouncer                      │     │    │
│  │  │  - Patroni for HA                 │     │    │
│  │  └──────────────────────────────────┘     │    │
│  └────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

## References

- [Zalando Postgres Operator Documentation](https://postgres-operator.readthedocs.io/)
- [Postgres Operator GitHub](https://github.com/zalando/postgres-operator)
- [Patroni Documentation](https://patroni.readthedocs.io/)
- [PostgreSQL High Availability](https://www.postgresql.org/docs/current/high-availability.html)

## Support

For issues or questions:
1. Check operator logs
2. Review Zalando Postgres Operator documentation
3. Check GitHub issues
4. Review task completion report
