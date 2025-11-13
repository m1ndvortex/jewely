# Quick Start Guide - Task 34.12: Configure PersistentVolumes

## Overview

This guide covers the configuration and validation of PersistentVolumes (PVs) and PersistentVolumeClaims (PVCs) for stateful data in the Kubernetes cluster.

## Storage Architecture

### Storage Requirements

| Component | Size | Access Mode | Replicas | Total Storage |
|-----------|------|-------------|----------|---------------|
| PostgreSQL | 100Gi | ReadWriteOnce | 3 | 300Gi |
| Redis | 10Gi | ReadWriteOnce | 3 | 30Gi |
| Media Files | 50Gi | ReadWriteMany | N/A | 50Gi |
| Static Files | 10Gi | ReadWriteMany | N/A | 10Gi |
| Backups | 100Gi | ReadWriteMany | N/A | 100Gi |
| **Total** | | | | **490Gi** |

### Storage Classes

- **k3d Development**: `local-path` (default k3d storage class)
- **Production**: `longhorn` (distributed storage for high availability)

### PVC Types

1. **StatefulSet PVCs** (automatic):
   - PostgreSQL: Created automatically by Zalando Postgres Operator
   - Redis: Created automatically by StatefulSet volumeClaimTemplates

2. **Manual PVCs** (defined in persistent-volumes.yaml):
   - Media files: Shared across Django pods
   - Static files: Shared across Django/Nginx pods
   - Backups: Shared across backup jobs

## Prerequisites

- k3d cluster running with 3 nodes
- jewelry-shop namespace created
- kubectl configured to access the cluster

## Step 1: Verify Storage Class

Check that the storage class exists:

```bash
# List available storage classes
kubectl get storageclass

# Expected output should include:
# NAME                   PROVISIONER             RECLAIMPOLICY   VOLUMEBINDINGMODE      ALLOWVOLUMEEXPANSION
# local-path (default)   rancher.io/local-path   Delete          WaitForFirstConsumer   false
```

## Step 2: Apply PersistentVolumeClaims

Apply the PVC manifests:

```bash
# Apply PVCs for media, static, and backups
kubectl apply -f k8s/persistent-volumes.yaml

# Verify PVCs are created
kubectl get pvc -n jewelry-shop

# Expected output:
# NAME           STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE
# media-pvc      Bound    pvc-xxxxx                                  50Gi       RWX            local-path     1m
# static-pvc     Bound    pvc-xxxxx                                  10Gi       RWX            local-path     1m
# backups-pvc    Bound    pvc-xxxxx                                  100Gi      RWX            local-path     1m
```

**Note**: PVCs may show `Pending` status until a pod mounts them (WaitForFirstConsumer binding mode).

## Step 3: Verify PostgreSQL PVCs

PostgreSQL PVCs are created automatically by the Zalando Postgres Operator:

```bash
# Check PostgreSQL PVCs
kubectl get pvc -n jewelry-shop -l application=spilo

# Expected output (3 PVCs, one per replica):
# NAME                                STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE
# pgdata-jewelry-shop-db-0            Bound    pvc-xxxxx                                  100Gi      RWO            local-path     5m
# pgdata-jewelry-shop-db-1            Bound    pvc-xxxxx                                  100Gi      RWO            local-path     5m
# pgdata-jewelry-shop-db-2            Bound    pvc-xxxxx                                  100Gi      RWO            local-path     5m
```

## Step 4: Verify Redis PVCs

Redis PVCs are created automatically by the StatefulSet:

```bash
# Check Redis PVCs
kubectl get pvc -n jewelry-shop -l app=redis

# Expected output (3 PVCs, one per replica):
# NAME           STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE
# data-redis-0   Bound    pvc-xxxxx                                  10Gi       RWO            local-path     5m
# data-redis-1   Bound    pvc-xxxxx                                  10Gi       RWO            local-path     5m
# data-redis-2   Bound    pvc-xxxxx                                  10Gi       RWO            local-path     5m
```

## Step 5: Verify PersistentVolumes

Check that PersistentVolumes were automatically provisioned:

```bash
# List all PVs
kubectl get pv

# Filter PVs for jewelry-shop namespace
kubectl get pv -o json | jq -r '.items[] | select(.spec.claimRef.namespace=="jewelry-shop") | "\(.metadata.name) - \(.spec.capacity.storage) - \(.status.phase)"'

# Expected: At least 9 PVs (3 PostgreSQL + 3 Redis + 3 manual PVCs)
```

## Step 6: Run Comprehensive Tests

Run the automated test suite:

```bash
# Run all PersistentVolume tests
./k8s/scripts/test-persistent-volumes.sh
```

The test script validates:
1. ✓ PVC creation and binding
2. ✓ PV provisioning
3. ✓ Storage class configuration
4. ✓ PostgreSQL data persistence across pod deletions
5. ✓ Redis data persistence across pod deletions
6. ✓ ReadWriteMany access for media files

## Manual Validation Steps

### Test 1: PostgreSQL Data Persistence

```bash
# 1. Get PostgreSQL master pod
MASTER_POD=$(kubectl get pods -n jewelry-shop -l application=spilo,spilo-role=master -o jsonpath='{.items[0].metadata.name}')
echo "Master pod: $MASTER_POD"

# 2. Create test table and insert data
kubectl exec -n jewelry-shop $MASTER_POD -c postgres -- psql -U postgres -d jewelry_shop -c "
  CREATE TABLE IF NOT EXISTS test_persistence (
    id SERIAL PRIMARY KEY,
    data VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
  );
  INSERT INTO test_persistence (data) VALUES ('test_data_$(date +%s)');
"

# 3. Verify data exists
kubectl exec -n jewelry-shop $MASTER_POD -c postgres -- psql -U postgres -d jewelry_shop -c "SELECT * FROM test_persistence;"

# 4. Delete the pod
kubectl delete pod -n jewelry-shop $MASTER_POD --force --grace-period=0

# 5. Wait for new pod to be ready (30-60 seconds)
sleep 30

# 6. Get new master pod
NEW_MASTER=$(kubectl get pods -n jewelry-shop -l application=spilo,spilo-role=master -o jsonpath='{.items[0].metadata.name}')
echo "New master pod: $NEW_MASTER"

# 7. Verify data persists
kubectl exec -n jewelry-shop $NEW_MASTER -c postgres -- psql -U postgres -d jewelry_shop -c "SELECT * FROM test_persistence;"

# 8. Cleanup
kubectl exec -n jewelry-shop $NEW_MASTER -c postgres -- psql -U postgres -d jewelry_shop -c "DROP TABLE test_persistence;"
```

**Expected Result**: Data should persist after pod deletion and recreation.

### Test 2: Redis Data Persistence

```bash
# 1. Set test data in Redis
kubectl exec -n jewelry-shop redis-0 -c redis -- redis-cli SET test_key "test_value_$(date +%s)"

# 2. Verify data exists
kubectl exec -n jewelry-shop redis-0 -c redis -- redis-cli GET test_key

# 3. Delete the pod
kubectl delete pod -n jewelry-shop redis-0 --force --grace-period=0

# 4. Wait for pod to be recreated (30-60 seconds)
sleep 30

# 5. Verify pod is running
kubectl get pod -n jewelry-shop redis-0

# 6. Verify data persists
kubectl exec -n jewelry-shop redis-0 -c redis -- redis-cli GET test_key

# 7. Cleanup
kubectl exec -n jewelry-shop redis-0 -c redis -- redis-cli DEL test_key
```

**Expected Result**: Data should persist after pod deletion and recreation.

### Test 3: ReadWriteMany Access

```bash
# 1. Create test pods that mount media-pvc
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: rwx-writer
  namespace: jewelry-shop
spec:
  containers:
  - name: writer
    image: busybox
    command: ['sh', '-c', 'echo "shared data" > /media/test.txt && sleep 3600']
    volumeMounts:
    - name: media
      mountPath: /media
  volumes:
  - name: media
    persistentVolumeClaim:
      claimName: media-pvc
---
apiVersion: v1
kind: Pod
metadata:
  name: rwx-reader
  namespace: jewelry-shop
spec:
  containers:
  - name: reader
    image: busybox
    command: ['sh', '-c', 'sleep 3600']
    volumeMounts:
    - name: media
      mountPath: /media
  volumes:
  - name: media
    persistentVolumeClaim:
      claimName: media-pvc
EOF

# 2. Wait for pods to be ready
kubectl wait --for=condition=Ready pod/rwx-writer pod/rwx-reader -n jewelry-shop --timeout=60s

# 3. Read from the reader pod
kubectl exec -n jewelry-shop rwx-reader -- cat /media/test.txt

# 4. Cleanup
kubectl delete pod rwx-writer rwx-reader -n jewelry-shop --force --grace-period=0
```

**Expected Result**: Reader pod should be able to read the file written by writer pod.

## Troubleshooting

### PVC Stuck in Pending

If PVCs are stuck in `Pending` status:

```bash
# Check PVC events
kubectl describe pvc <pvc-name> -n jewelry-shop

# Common causes:
# 1. No storage class available
# 2. Insufficient storage capacity
# 3. WaitForFirstConsumer binding mode (normal, will bind when pod mounts it)
```

### PV Not Provisioned

```bash
# Check storage class provisioner
kubectl get storageclass local-path -o yaml

# Verify provisioner is running
kubectl get pods -n kube-system | grep local-path
```

### Data Not Persisting

```bash
# Check if volume is actually mounted
kubectl describe pod <pod-name> -n jewelry-shop | grep -A 10 "Volumes:"

# Check volume mount in container
kubectl exec -n jewelry-shop <pod-name> -- df -h

# Check PV reclaim policy (should be Retain or Delete)
kubectl get pv <pv-name> -o jsonpath='{.spec.persistentVolumeReclaimPolicy}'
```

### ReadWriteMany Not Working

```bash
# Check if storage class supports RWX
kubectl get storageclass local-path -o yaml | grep -i allowedTopologies

# Note: local-path storage class may not support true RWX
# For production, use longhorn or NFS-based storage
```

## Production Considerations

### Storage Class for Production

For production deployments, use a distributed storage solution:

```yaml
# Install Longhorn (distributed block storage)
kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/v1.5.3/deploy/longhorn.yaml

# Update PVCs to use longhorn storage class
storageClassName: longhorn
```

### Backup Strategy

```bash
# PVCs are backed up as part of the backup system
# See k8s/TASK_34.6_COMPLETION_REPORT.md for backup configuration

# Manual PVC snapshot (if supported by storage class)
kubectl create volumesnapshot <snapshot-name> \
  --volume-snapshot-class=<snapshot-class> \
  --claim=<pvc-name> \
  -n jewelry-shop
```

### Monitoring Storage Usage

```bash
# Check PVC usage
kubectl exec -n jewelry-shop <pod-name> -- df -h

# Monitor storage metrics with Prometheus
# Metrics: kubelet_volume_stats_capacity_bytes, kubelet_volume_stats_used_bytes
```

## Validation Checklist

- [ ] All PVCs are in `Bound` status
- [ ] PersistentVolumes are automatically provisioned
- [ ] PostgreSQL data persists across pod deletions
- [ ] Redis data persists across pod deletions
- [ ] Multiple pods can access ReadWriteMany volumes
- [ ] Storage class is correctly configured
- [ ] Total storage allocation: ~490Gi

## Success Criteria

✓ **All PVCs Bound**: 9 PVCs total (3 PostgreSQL + 3 Redis + 3 manual)
✓ **Data Persistence**: PostgreSQL and Redis data survives pod deletions
✓ **ReadWriteMany**: Multiple pods can access shared volumes
✓ **Storage Class**: Correct storage class configured (local-path for k3d)
✓ **Automated Tests**: All tests in test-persistent-volumes.sh pass

## Next Steps

After completing this task:
1. Proceed to Task 34.13: Implement network policies for security
2. Configure backup jobs to use backups-pvc
3. Update Django deployment to mount media-pvc and static-pvc
4. Monitor storage usage and set up alerts

## References

- Kubernetes PersistentVolumes: https://kubernetes.io/docs/concepts/storage/persistent-volumes/
- k3d Storage: https://k3d.io/v5.6.0/usage/advanced/volumes/
- Longhorn Documentation: https://longhorn.io/docs/
- Zalando Postgres Operator: https://postgres-operator.readthedocs.io/
