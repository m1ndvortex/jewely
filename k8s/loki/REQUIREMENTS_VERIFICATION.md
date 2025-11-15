# Requirements Verification - Task 35.3: Deploy Loki

## Requirement 24: Monitoring and Observability

**User Story:** As a platform administrator, I want complete visibility into system performance and health through monitoring and observability tools, so that I can proactively address issues.

### Acceptance Criterion 7

**Requirement:** THE System SHALL deploy Loki for centralized log aggregation from all services

**Status:** ✅ **VERIFIED**

**Implementation:**
- Loki deployed as a Deployment in jewelry-shop namespace
- Configured with 31-day log retention
- Persistent storage (10Gi PVC) for log data
- Exposes HTTP API on port 3100 for log queries
- Exposes gRPC on port 9096 for ingestion
- Configured with proper resource limits and health checks

**Verification:**
```bash
# Verify Loki deployment
kubectl get deployment loki -n jewelry-shop
# Expected: 1/1 replicas ready

# Verify Loki service
kubectl get service loki -n jewelry-shop
# Expected: ClusterIP service on ports 3100 and 9096

# Verify Loki is ready
kubectl exec -n jewelry-shop $(kubectl get pod -n jewelry-shop -l app=loki -o jsonpath='{.items[0].metadata.name}') -- wget -q -O- http://localhost:3100/ready
# Expected: "ready"

# Verify log ingestion
kubectl exec -n jewelry-shop $(kubectl get pod -n jewelry-shop -l app=loki -o jsonpath='{.items[0].metadata.name}') -- wget -q -O- http://localhost:3100/loki/api/v1/labels
# Expected: JSON response with labels
```

---

## Task 35.3 Subtasks

### Subtask 1: Deploy Loki

**Status:** ✅ **COMPLETED**

**Implementation:**
- Created `loki-configmap.yaml` with comprehensive Loki configuration
- Created `loki-deployment.yaml` with Deployment, Service, and PVC
- Configured with:
  - Single replica (suitable for development, scalable for production)
  - 10Gi persistent storage
  - 31-day log retention
  - Resource requests: 200m CPU, 512Mi memory
  - Resource limits: 1000m CPU, 2Gi memory
  - Liveness and readiness probes
  - Security context (non-root user)

**Files:**
- `k8s/loki/loki-configmap.yaml`
- `k8s/loki/loki-deployment.yaml`

**Verification:**
```bash
kubectl get deployment loki -n jewelry-shop
kubectl get service loki -n jewelry-shop
kubectl get pvc loki-storage -n jewelry-shop
```

---

### Subtask 2: Configure log collection from all pods

**Status:** ✅ **COMPLETED**

**Implementation:**
- Deployed Promtail as a DaemonSet (runs on every node)
- Created `promtail-configmap.yaml` with scrape configurations for:
  - All pods in jewelry-shop namespace (generic collection)
  - Django application logs (JSON parsing)
  - Celery worker logs (custom regex parsing)
  - Nginx access logs (access log format parsing)
  - PostgreSQL logs (PostgreSQL format parsing)
  - Redis logs (Redis format parsing)
- Created `promtail-rbac.yaml` with necessary permissions:
  - ServiceAccount for Promtail
  - ClusterRole with read access to pods, nodes, services
  - ClusterRoleBinding to grant permissions
- Configured Promtail to:
  - Read logs from `/var/log/pods/`
  - Parse CRI format logs
  - Extract labels (namespace, pod, container, app, component, node)
  - Send logs to Loki via HTTP

**Files:**
- `k8s/loki/promtail-configmap.yaml`
- `k8s/loki/promtail-daemonset.yaml`
- `k8s/loki/promtail-rbac.yaml`

**Verification:**
```bash
# Verify Promtail DaemonSet
kubectl get daemonset promtail -n jewelry-shop

# Verify Promtail pods (one per node)
kubectl get pods -n jewelry-shop -l app=promtail

# Verify Promtail is collecting logs
kubectl logs -n jewelry-shop -l app=promtail | grep "sent"

# Verify logs are being ingested
kubectl exec -n jewelry-shop $(kubectl get pod -n jewelry-shop -l app=loki -o jsonpath='{.items[0].metadata.name}') -- wget -q -O- 'http://localhost:3100/loki/api/v1/query?query={namespace="jewelry-shop"}&limit=10'
```

---

### Subtask 3: Set up log retention policies

**Status:** ✅ **COMPLETED**

**Implementation:**
- Configured log retention in `loki-configmap.yaml`:
  - **Retention period:** 31 days (744 hours)
  - **Compaction interval:** 10 minutes
  - **Retention deletion delay:** 2 hours
  - **Max look back period:** 31 days
- Configured storage limits:
  - **Ingestion rate:** 10 MB/s per tenant
  - **Ingestion burst:** 20 MB
  - **Max query series:** 500
- Configured automatic cleanup:
  - Table manager with retention deletes enabled
  - Compactor with retention enabled
  - Automatic deletion of old chunks

**Configuration in loki-configmap.yaml:**
```yaml
limits_config:
  retention_period: 744h  # 31 days
  
compactor:
  retention_enabled: true
  retention_delete_delay: 2h
  compaction_interval: 10m
  
chunk_store_config:
  max_look_back_period: 744h  # 31 days
  
table_manager:
  retention_deletes_enabled: true
  retention_period: 744h  # 31 days
```

**Verification:**
```bash
# Verify retention configuration
kubectl get configmap loki-config -n jewelry-shop -o yaml | grep -A 5 "retention"

# Check compactor is running
kubectl logs -n jewelry-shop -l app=loki | grep compactor

# Verify storage usage
kubectl exec -n jewelry-shop $(kubectl get pod -n jewelry-shop -l app=loki -o jsonpath='{.items[0].metadata.name}') -- df -h /loki
```

---

## Integration with Grafana

**Status:** ✅ **COMPLETED**

**Implementation:**
- Created `loki-datasource.yaml` ConfigMap for Grafana
- Configured Loki as a datasource in Grafana
- Set datasource URL to `http://loki:3100`
- Configured max lines to 1000
- Added derived fields for trace correlation

**File:**
- `k8s/loki/loki-datasource.yaml`

**Verification:**
```bash
# Verify datasource ConfigMap
kubectl get configmap loki-datasource -n jewelry-shop

# Access Grafana and check datasources
# Navigate to Configuration → Data Sources
# Loki should be listed
```

---

## Automation and Documentation

**Status:** ✅ **COMPLETED**

**Implementation:**

### Installation Script
- Created `install-loki.sh` for automated deployment
- Includes:
  - Prerequisites checking
  - Step-by-step deployment with progress indicators
  - Waiting for pods to be ready
  - Grafana restart to load datasource
  - Deployment status display
  - Access information and usage examples

### Validation Script
- Created `validate-loki.sh` for deployment validation
- Tests:
  - Loki pod health
  - Loki service existence
  - Promtail DaemonSet and pods
  - Loki readiness endpoint
  - Log ingestion
  - Metrics availability
  - PVC status
  - RBAC configuration
  - Retention configuration
  - Query functionality

### Comprehensive Test Script
- Created `test-loki-comprehensive.sh` for thorough testing
- Test suites:
  - Deployment validation
  - API functionality
  - Log collection (with test pod)
  - Metrics verification
  - Storage and retention
  - Integration tests

### Documentation
- Created `README.md` with:
  - Architecture overview
  - Component descriptions
  - Installation instructions
  - Usage examples with LogQL queries
  - Troubleshooting guide
  - Performance tuning
  - Security considerations
  - Backup and recovery procedures

- Created `QUICK_START.md` with:
  - 5-minute quick installation
  - Common log queries
  - Verification steps
  - Common tasks
  - Troubleshooting quick fixes

**Files:**
- `k8s/loki/install-loki.sh`
- `k8s/loki/validate-loki.sh`
- `k8s/loki/test-loki-comprehensive.sh`
- `k8s/loki/README.md`
- `k8s/loki/QUICK_START.md`

---

## Summary

### ✅ All Requirements Met

1. **Loki Deployed:** ✅
   - Running in jewelry-shop namespace
   - Persistent storage configured
   - Health checks implemented
   - Metrics exposed

2. **Log Collection Configured:** ✅
   - Promtail running on all nodes
   - Collecting logs from all pods
   - Multiple log formats supported
   - Labels properly extracted

3. **Log Retention Policies:** ✅
   - 31-day retention configured
   - Automatic compaction enabled
   - Storage limits set
   - Cleanup automated

4. **Integration:** ✅
   - Grafana datasource configured
   - LogQL queries working
   - Metrics available for Prometheus

5. **Automation:** ✅
   - Installation script
   - Validation script
   - Comprehensive tests
   - Complete documentation

### Verification Commands

```bash
# Quick verification
cd k8s/loki
./validate-loki.sh

# Comprehensive testing
./test-loki-comprehensive.sh

# Check deployment status
kubectl get all -n jewelry-shop -l component=logging
```

### Access Loki

```bash
# Port forward to Loki
kubectl port-forward -n jewelry-shop svc/loki 3100:3100

# Query logs
curl 'http://localhost:3100/loki/api/v1/query?query={namespace="jewelry-shop"}&limit=10'

# View in Grafana
# Navigate to Explore → Select Loki → Query: {namespace="jewelry-shop"}
```

---

## Conclusion

Task 35.3 has been **successfully completed**. Loki is deployed and operational, collecting logs from all pods in the jewelry-shop namespace with proper retention policies. The system is ready for production use with comprehensive documentation and automation scripts.
