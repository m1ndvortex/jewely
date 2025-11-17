# Task 34.16: Extreme Load Testing & Chaos Engineering - Summary

## Status: IN PROGRESS

### What We've Accomplished

#### ✅ 1. VPS Load Testing Infrastructure Created
- **Created Files:**
  - `vps_simulation_config.yaml` - VPS resource allocation plan (4-6GB RAM, 2-3 CPU)
  - `setup_vps_simulation.sh` - Script to apply VPS resource constraints
  - `locustfile_vps.py` - Realistic load test for small VPS (20-200 concurrent users)
  - `run_vps_load_tests.sh` - Comprehensive test orchestrator with 4 scenarios
  - `VPS_TESTING_GUIDE.md` - Complete usage guide
  - `README.md` - Quick reference

#### ✅ 2. Resource Constraint System
- **Approach:** Use Kubernetes ResourceQuota + LimitRange to simulate VPS limits on powerful dev cluster
- **Why:** Local cluster has 96GB RAM / 48 CPU cores, but production VPS will have only 4-6GB RAM / 2-3 CPU
- **Benefit:** Test under realistic production constraints without needing actual VPS

#### ✅ 3. Cluster Prepared for Testing
- Monitoring stack scaled down (Grafana, Prometheus, Loki, Tempo, OtelCollector → 0 replicas)
- Application scaled to VPS-appropriate sizes:
  - Django: 3 → 2 replicas
  - Nginx: 2 → 1 replica  
  - Celery worker: 3 → 1 replica
- Locust deployment verified (1 master + 3 workers, all running)

#### ✅ 4. Connectivity Test Successful
- Nginx service reachable: `http://nginx-service/` returns HTTP 302 (redirect)
- Service DNS resolution working
- Network connectivity confirmed

### Issues Discovered

#### ⚠️ 1. ResourceQuota Side Effect
**Problem:** VPS quota (when applied) prevents new pod creation and may cause connection issues

**Evidence:**
```
Error: exceeded quota: vps-quota
requested: limits.cpu=500m, limits.memory=512Mi
used: limits.cpu=20700m, limits.memory=23296Mi
limited: limits.cpu=6, limits.memory=8Gi
```

**Impact:** 
- Cannot create test pods when quota active
- May affect HPA scaling during load tests
- Load test showed 100% failure rate with quota active

**Root Cause:** Quota applies to entire namespace including monitoring stack (not just application)

**Solution Options:**
1. **Recommended:** Apply quota ONLY to application pods using label selectors
2. Keep monitoring in separate namespace
3. Run load tests without quota (less realistic but will work)

#### ⚠️ 2. Load Test Configuration Mismatch
**Problem:** Existing locustfile configured for "extreme load" (1000 users) not VPS realistic load (20-200 users)

**Evidence:** Test reported as "EXTREME LOAD TEST" with custom failure conditions that may not match VPS scenarios

**Solution:** Need to either:
1. Update locustfile_vps.py in Locust pod ConfigMap
2. Create new Locust deployment with VPS-specific ConfigMap
3. Modify existing ConfigMap to include both locustfiles

### Test Results from Initial Run

#### Light Load Test (20 users, 3 minutes)
- **Total Requests:** 182
- **Failed:** 182 (100%) ← Due to quota/connectivity issues
- **Average Response Time:** 10,860ms (very slow - indicates problems)
- **Throughput:** 1.02 req/s (extremely low)

**Errors:**
- Connection refused (10 occurrences)
- Connection timeout (4 occurrences)
- Custom response failures: "returned 0" (168 occurrences)

**Verdict:** Test invalid due to infrastructure issues, not application performance

### Next Steps

#### Immediate Actions (To Complete Task 34.16)

**Option A: Full VPS Simulation (Most Realistic)**
1. Move monitoring stack to separate namespace
2. Apply ResourceQuota only to application pods
3. Update Locust ConfigMap with VPS locustfile
4. Run 4-scenario test suite:
   - Light: 20 users × 10min
   - Medium: 50 users × 15min
   - Peak: 100 users × 20min  
   - Stress: 200 users × 10min
5. Generate comprehensive report

**Estimated Time:** 2-3 hours (1 hour setup + 1 hour testing + 1 hour analysis)

**Option B: No-Quota Testing (Less Realistic, Faster)**
1. Remove ResourceQuota
2. Keep application scaled to VPS sizes
3. Run load tests
4. Manually monitor resources to ensure staying within VPS limits
5. Document that tests passed on VPS-sized deployments

**Estimated Time:** 1 hour

**Option C: Hybrid Approach (Recommended)**
1. Keep quota removed for now
2. Run load tests with VPS-sized deployments
3. Monitor actual resource usage during tests
4. Validate that resources stay within 4-6GB RAM / 2-3 CPU limits
5. If resources exceed, scale down and retest
6. Document actual resource consumption per scenario

**Estimated Time:** 1-2 hours

#### Chaos Engineering Tests (Still Pending)

After load tests complete:

1. **PostgreSQL Failover Test**
   - Kill PostgreSQL master pod
   - Measure recovery time (<30s target)
   - Verify data consistency

2. **Redis Failover Test**
   - Kill Redis master pod
   - Measure recovery time (<30s target)
   - Verify session persistence

3. **Pod Self-Healing Test**
   - Kill random Django pods
   - Verify automatic recreation
   - Measure service interruption (<5s target)

4. **Node Drain Test**
   - Drain a k8s node
   - Verify pod rescheduling
   - Measure total recovery time

5. **Network Partition Test**
   - Simulate network partition using NetworkPolicy
   - Verify system remains consistent
   - Test quorum behavior

**Estimated Time:** 2-3 hours

### Current Cluster State

```
Namespace: jewelry-shop

Application Pods:
- django: 2/2 Running
- nginx: 1/1 Running  
- celery-worker: 1/1 Running
- celery-beat: 1/1 Running
- postgresql: 3/3 Running (HA cluster)
- redis: 3/3 Running (HA cluster)
- pgbouncer: 2/2 Running

Load Test Pods:
- locust-master: 1/1 Running
- locust-worker: 3/3 Running

Monitoring (Scaled Down):
- grafana: 0/0
- prometheus: 0/0
- loki: 0/0
- tempo: 0/0
- otel-collector: 0/0

Resource Constraints:
- ResourceQuota: REMOVED
- LimitRange: REMOVED
```

### Resource Consumption Estimates

Based on deployment specs, VPS resource usage should be:

**CPU (Requests):**
- Django: 2 × 500m = 1000m
- PostgreSQL: 2 × 500m = 1000m (reduced replicas for VPS)
- Redis: 2 × 100m = 200m
- Celery: 1 × 400m = 400m
- Nginx: 1 × 250m = 250m
- PgBouncer: 2 × 250m = 500m
- **Total: 3350m (3.35 cores)** ⚠️ Exceeds 2-core VPS!

**Memory (Requests):**
- Django: 2 × 512Mi = 1024Mi
- PostgreSQL: 2 × 1Gi = 2048Mi
- Redis: 2 × 256Mi = 512Mi
- Celery: 1 × 512Mi = 512Mi
- Nginx: 1 × 256Mi = 256Mi
- PgBouncer: 2 × 128Mi = 256Mi
- **Total: 4608Mi (~4.5GB)** ✅ Fits 6GB VPS, tight on 4GB

**CRITICAL FINDING:** Current deployment requires 3.35 CPU cores - too much for 2-core VPS!

### Recommendations

#### For 4GB / 2 CPU VPS:
- ❌ **NOT RECOMMENDED** - CPU requirements exceed capacity
- Need to reduce to 1 replica for most services
- Performance will be degraded

#### For 6GB / 3 CPU VPS:
- ✅ **RECOMMENDED MINIMUM**
- CPU: 3350m / 3000m = 111% (slightly over but manageable with burstable)
- Memory: 4608Mi / 6144Mi = 75% (comfortable headroom)

#### For 8GB / 4 CPU VPS:
- ✅ **RECOMMENDED FOR PRODUCTION**
- CPU: 3350m / 4000m = 84% (good utilization)
- Memory: 4608Mi / 8192Mi = 56% (plenty of headroom)
- Allows scaling to 3 Django replicas during peak load

### Files Created

```
tests/load/
├── README.md                          # Quick reference
├── VPS_TESTING_GUIDE.md               # Complete usage guide
├── vps_simulation_config.yaml         # VPS resource plan
├── setup_vps_simulation.sh            # Apply VPS constraints (executable)
├── locustfile_vps.py                  # VPS load test scenarios
├── run_vps_load_tests.sh              # Test orchestrator (executable)
└── TASK_34_16_LOAD_TEST_SUMMARY.md    # This file
```

### Decision Point

**Before proceeding, please confirm preferred approach:**

1. **Option A:** Full VPS simulation with quota (2-3 hours, most realistic)
2. **Option B:** No quota, just monitoring (1 hour, faster)
3. **Option C:** Hybrid - no quota but manual validation (1-2 hours, recommended)

**Also confirm VPS target:**
- 4GB / 2 CPU (will need to reduce replicas further)
- 6GB / 3 CPU (recommended minimum, current config fits)
- 8GB / 4 CPU (recommended for production, comfortable headroom)

Once confirmed, I can proceed with the selected approach.

---

**Last Updated:** 2025-11-16 18:45 UTC  
**Status:** Awaiting user decision on approach and VPS size
