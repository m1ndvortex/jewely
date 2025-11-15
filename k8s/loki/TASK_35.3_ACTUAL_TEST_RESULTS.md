# Task 35.3 Actual Test Results - Loki Deployment

## Test Execution Date
2025-11-13

## Environment
- Cluster: k3d-jewelry-shop (3 nodes)
- Namespace: jewelry-shop
- Kubernetes Version: v1.31.5+k3s1

## Test Results Summary

### ✅ PASSED Tests

#### 1. Loki Deployment
**Status:** ✅ PASS

```bash
$ kubectl get deployment loki -n jewelry-shop
NAME   READY   UP-TO-DATE   AVAILABLE   AGE
loki   1/1     1            1           13m

$ kubectl get pods -n jewelry-shop -l app=loki
NAME                    READY   STATUS    RESTARTS   AGE
loki-7f8585d76b-8pg9c   1/1     Running   0          13m
```

**Result:** Loki pod is running successfully

---

#### 2. Loki Service
**Status:** ✅ PASS

```bash
$ kubectl get service loki -n jewelry-shop
NAME   TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)             AGE
loki   ClusterIP   10.43.xxx.xxx   <none>        3100/TCP,9096/TCP   13m
```

**Result:** Loki service is created and accessible

---

#### 3. Loki PersistentVolumeClaim
**Status:** ✅ PASS

```bash
$ kubectl get pvc loki-storage -n jewelry-shop
NAME            STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE
loki-storage    Bound    pvc-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx   5Gi        RWO            local-path     13m
```

**Result:** PVC is bound successfully (reduced to 5Gi due to quota constraints)

---

#### 4. Loki Ready Endpoint
**Status:** ✅ PASS

```bash
$ kubectl exec -n jewelry-shop loki-7f8585d76b-8pg9c -- wget -q -O- http://localhost:3100/ready
ready
```

**Result:** Loki is ready and responding

---

#### 5. Loki API Functionality
**Status:** ✅ PASS

```bash
$ kubectl exec -n jewelry-shop loki-7f8585d76b-8pg9c -- wget -q -O- http://localhost:3100/loki/api/v1/labels
{"status":"success"}
```

**Result:** Loki API is functional

---

#### 6. Loki ConfigMap
**Status:** ✅ PASS

```bash
$ kubectl get configmap loki-config -n jewelry-shop
NAME          DATA   AGE
loki-config   1      15m
```

**Result:** Loki configuration is applied

---

#### 7. Loki Retention Configuration
**Status:** ✅ PASS

```bash
$ kubectl get configmap loki-config -n jewelry-shop -o yaml | grep retention_period
    retention_period: 744h  # 31 days
```

**Result:** 31-day retention policy is configured

---

#### 8. Grafana Datasource Configuration
**Status:** ✅ PASS

```bash
$ kubectl get configmap loki-datasource -n jewelry-shop
NAME              DATA   AGE
loki-datasource   1      2m
```

**Result:** Loki datasource ConfigMap created for Grafana

---

#### 9. Resource Limits
**Status:** ✅ PASS

- CPU Request: 250m (adjusted for LimitRange compliance)
- CPU Limit: 1000m
- Memory Request: 512Mi
- Memory Limit: 2Gi

**Result:** Resource limits comply with namespace LimitRange (4:1 ratio)

---

### ❌ FAILED / BLOCKED Tests

#### 10. Promtail DaemonSet Deployment
**Status:** ❌ BLOCKED

**Issue:** "too many open files" error

```bash
$ kubectl get daemonset promtail -n jewelry-shop
NAME       DESIRED   CURRENT   READY   UP-TO-DATE   AVAILABLE   NODE SELECTOR   AGE
promtail   3         0         0       0            0           <none>          5m

$ kubectl logs -n jewelry-shop promtail-xxxxx
level=error ts=2025-11-13T17:24:58.003666076Z caller=main.go:170 msg="error creating promtail" error="failed to make file target manager: too many open files"
```

**Root Cause:**
- Promtail attempts to watch all log files in `/var/log/pods/`
- With 32 pods in the namespace, each with multiple containers and historical log files, this exceeds the default file descriptor limit
- k3d/containerd log structure creates many files per pod

**Attempted Solutions:**
1. ✗ Simplified Promtail configuration to single job
2. ✗ Removed docker containers volume mount
3. ✗ Added file discovery limits
4. ✗ Used static configuration with glob patterns
5. ✗ Filtered to only Running pods

**Current Status:** Promtail cannot start due to file descriptor limits

---

## Workarounds and Alternatives

### Alternative 1: Manual Log Forwarding (Testing Only)
For testing purposes, logs can be sent directly to Loki API:

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"streams": [{"stream": {"job": "test"}, "values": [["'$(date +%s)000000000'", "test message"]]}]}' \
  http://loki.jewelry-shop.svc.cluster.local:3100/loki/api/v1/push
```

### Alternative 2: Fluent Bit
Consider using Fluent Bit instead of Promtail:
- Lower resource usage
- Better handling of large numbers of files
- More mature Kubernetes integration

### Alternative 3: Increase File Descriptor Limits
Modify node-level ulimits (requires cluster admin access):
```bash
# On each node
sysctl -w fs.inotify.max_user_instances=8192
sysctl -w fs.inotify.max_user_watches=524288
```

### Alternative 4: Selective Log Collection
Deploy Promtail with filters to only collect logs from specific apps:
- Only Django pods
- Only error-level logs
- Specific namespaces only

---

## Requirements Verification

### Requirement 24.7: Deploy Loki for centralized log aggregation

**Status:** ⚠️ PARTIALLY MET

| Requirement Component | Status | Notes |
|----------------------|--------|-------|
| Deploy Loki | ✅ COMPLETE | Loki is deployed and operational |
| Configure log collection from all pods | ❌ BLOCKED | Promtail cannot start due to file descriptor limits |
| Set up log retention policies | ✅ COMPLETE | 31-day retention configured |

---

## Task 35.3 Subtasks Status

### Subtask 1: Deploy Loki
**Status:** ✅ COMPLETE

- Loki deployment created
- Service exposed on ports 3100 (HTTP) and 9096 (gRPC)
- PersistentVolume (5Gi) bound
- Health checks passing
- API functional

### Subtask 2: Configure log collection from all pods
**Status:** ❌ BLOCKED

- Promtail RBAC created
- Promtail ConfigMap created
- Promtail DaemonSet created
- **ISSUE:** Promtail pods crash with "too many open files"
- Log collection not operational

### Subtask 3: Set up log retention policies
**Status:** ✅ COMPLETE

- 31-day retention period configured
- Automatic compaction enabled (every 10 minutes)
- Retention deletion enabled
- Storage limits configured

---

## Recommendations

### Immediate Actions

1. **Use Fluent Bit Instead of Promtail**
   - Deploy Fluent Bit DaemonSet
   - Configure Fluent Bit to forward to Loki
   - Fluent Bit handles large file counts better

2. **Increase Node-Level Limits**
   - Modify k3d cluster configuration
   - Increase fs.inotify limits
   - Restart Promtail

3. **Selective Collection**
   - Only collect from critical pods
   - Filter by app label
   - Reduce file watch count

### Long-Term Solutions

1. **Production Deployment**
   - Use managed Loki service (Grafana Cloud)
   - Deploy Loki in microservices mode
   - Use object storage backend (S3, R2)

2. **Alternative Log Collectors**
   - Fluent Bit (recommended)
   - Fluentd
   - Vector

3. **Cluster Configuration**
   - Increase default ulimits
   - Configure proper sysctl values
   - Use log rotation policies

---

## Conclusion

**Task Status:** ⚠️ PARTIALLY COMPLETE

**What Works:**
- ✅ Loki is deployed and operational
- ✅ Loki API is functional
- ✅ Log retention policies configured
- ✅ Grafana datasource configured
- ✅ Storage provisioned

**What Doesn't Work:**
- ❌ Promtail cannot collect logs (file descriptor limit)
- ❌ No logs are being ingested into Loki
- ❌ Log aggregation not operational

**Next Steps:**
1. Deploy Fluent Bit as alternative log collector
2. OR increase node-level file descriptor limits
3. OR implement selective log collection
4. Test log ingestion end-to-end
5. Verify logs appear in Grafana

---

## Files Status

### Created and Working
- ✅ `loki-configmap.yaml` - Applied successfully
- ✅ `loki-deployment.yaml` - Deployed successfully (with adjustments)
- ✅ `loki-datasource.yaml` - Applied successfully
- ✅ `promtail-rbac.yaml` - Applied successfully

### Created but Not Working
- ⚠️ `promtail-configmap.yaml` - Applied but Promtail crashes
- ⚠️ `promtail-daemonset.yaml` - Applied but pods crash

### Documentation
- ✅ `README.md` - Complete
- ✅ `QUICK_START.md` - Complete
- ✅ `install-loki.sh` - Created (needs update for Fluent Bit)
- ✅ `validate-loki.sh` - Created (needs update)
- ✅ `test-loki-comprehensive.sh` - Created (needs update)

---

## Test Evidence

### Loki Pod Status
```
NAME                    READY   STATUS    RESTARTS   AGE
loki-7f8585d76b-8pg9c   1/1     Running   0          13m
```

### Promtail Pod Status
```
NAME             READY   STATUS             RESTARTS      AGE
promtail-9w4dk   0/1     CrashLoopBackOff   2 (3s ago)    26s
promtail-kpdkl   0/1     CrashLoopBackOff   2 (5s ago)    26s
promtail-tfrxb   0/1     Error              2 (19s ago)   27s
```

### Promtail Error Log
```
level=error ts=2025-11-13T17:24:58.003666076Z caller=main.go:170 msg="error creating promtail" error="failed to make file target manager: too many open files"
```

---

**Test Completed:** 2025-11-13  
**Tester:** Automated validation  
**Result:** Loki deployed successfully, Promtail blocked by file descriptor limits
