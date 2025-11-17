# VPS Load Testing Guide

## Overview

This test suite simulates realistic production load on a **small VPS** (4-6GB RAM, 2-3 CPU cores) to validate system performance before purchasing your actual VPS.

## Quick Start

### Option 1: Run All Tests (Recommended)

```bash
# Test with 4GB RAM / 2 CPU VPS (starter configuration)
./tests/load/run_vps_load_tests.sh 4 2

# Test with 6GB RAM / 3 CPU VPS (recommended configuration)
./tests/load/run_vps_load_tests.sh 6 3
```

This runs 4 comprehensive tests:
1. **Light Load** (20 users, 10 min) - Normal business hours
2. **Medium Load** (50 users, 15 min) - Busy hours
3. **Peak Load** (100 users, 20 min) - Flash sales
4. **Stress Test** (200 users, 10 min) - Find breaking point

**Total time:** ~1 hour

### Option 2: Run Individual Tests

```bash
# 1. Setup VPS simulation first
./tests/load/setup_vps_simulation.sh 4 2

# 2. Get Locust master pod
LOCUST_POD=$(kubectl get pods -n jewelry-shop -l app=locust,component=master -o jsonpath='{.items[0].metadata.name}')

# 3. Run specific test
kubectl exec -n jewelry-shop $LOCUST_POD -- \
  locust \
  -f /locust/locustfile_vps.py \
  --host=http://nginx \
  --users=50 \
  --spawn-rate=5 \
  --run-time=10m \
  --headless \
  --html=/reports/test_result.html \
  --only-summary
```

## Test Scenarios

### 1. Light Load (20 concurrent users)
**Use case:** Normal business hours  
**Users:** 1-2 staff members using POS + inventory  
**Expected:** Fast responses (<500ms), minimal resources

```bash
--users=20 --spawn-rate=2 --run-time=10m
```

### 2. Medium Load (50 concurrent users)
**Use case:** Busy hours  
**Users:** Multiple staff + some customer portal access  
**Expected:** Good performance (<1s), moderate scaling

```bash
--users=50 --spawn-rate=5 --run-time=15m
```

### 3. Peak Load (100 concurrent users)
**Use case:** Flash sale, promotion, busy season  
**Users:** All staff + many customers browsing/buying  
**Expected:** Acceptable performance (<2s), full scaling

```bash
--users=100 --spawn-rate=10 --run-time=20m
```

### 4. Stress Test (200 concurrent users)
**Use case:** Find system limits  
**Users:** Beyond normal capacity  
**Expected:** Performance degradation, understand breaking point

```bash
--users=200 --spawn-rate=10 --run-time=10m
```

## VPS Configurations Tested

### 4GB RAM / 2 CPU (Budget Starter)
**Cost:** ~$10-15/month  
**Suitable for:**
- 1-2 tenants
- Light to medium usage
- 30-50 concurrent users max
- Small jewelry shops

**Resource allocation:**
- Django: 2 pods × 256MB = 512MB
- PostgreSQL: 2 pods × 512MB = 1GB
- Redis: 2 pods × 128MB = 256MB
- Nginx: 1 pod × 64MB = 64MB
- Celery: 1 pod × 256MB = 256MB
- **Total:** ~2GB used, 2GB free for OS + buffers

### 6GB RAM / 3 CPU (Recommended)
**Cost:** ~$20-25/month  
**Suitable for:**
- 3-5 tenants
- Moderate to heavy usage
- 75-100 concurrent users
- Growing businesses

**Resource allocation:**
- Django: 2 pods × 512MB = 1GB
- PostgreSQL: 2 pods × 1GB = 2GB
- Redis: 2 pods × 256MB = 512MB
- Nginx: 1 pod × 128MB = 128MB
- Celery: 1 pod × 512MB = 512MB
- **Total:** ~4GB used, 2GB free

## Monitoring During Tests

### Watch Pod Scaling
```bash
# Watch HPA in real-time
watch kubectl get hpa -n jewelry-shop

# Watch pod creation
watch kubectl get pods -n jewelry-shop
```

### Monitor Resources
```bash
# Node resources
kubectl top nodes

# Pod resources
kubectl top pods -n jewelry-shop --containers

# Detailed pod metrics
kubectl describe hpa django-hpa -n jewelry-shop
```

### Check Application Health
```bash
# Django pod logs
kubectl logs -n jewelry-shop -l component=django --tail=50 -f

# Nginx access logs
kubectl logs -n jewelry-shop -l component=nginx --tail=50 -f
```

## Understanding Results

### Response Times (p95 = 95th percentile)

**Excellent:**
- Light load: <500ms
- Medium load: <800ms
- Peak load: <1200ms

**Good:**
- Light load: <1000ms
- Medium load: <1500ms
- Peak load: <2000ms

**Acceptable:**
- Light load: <1500ms
- Medium load: <2000ms
- Peak load: <3000ms

**Poor:**
- Any scenario: >3000ms
- *Action: Upgrade VPS or optimize*

### Error Rate

- **Excellent:** <1%
- **Acceptable:** 1-5%
- **Poor:** >5%

### Throughput (requests/second)

- **Good:** >50 req/s
- **Moderate:** 20-50 req/s
- **Low:** <20 req/s

## When to Upgrade VPS

Upgrade from 4GB→6GB if:
- ✅ CPU consistently >80% during normal hours
- ✅ Memory consistently >85%
- ✅ Response times >2s for p95
- ✅ Error rate >2%
- ✅ More than 2 active tenants
- ✅ Regular concurrent users >50

Upgrade from 6GB→8GB+ if:
- ✅ More than 5 active tenants
- ✅ Regular concurrent users >100
- ✅ Running marketing campaigns
- ✅ Response times degrading

## Troubleshooting

### Locust pod not found
```bash
# Check if Locust is deployed
kubectl get pods -n jewelry-shop -l app=locust

# If not deployed, deploy Locust first
# (Locust deployment YAML needed)
```

### Out of memory errors
```bash
# Check pod memory
kubectl top pods -n jewelry-shop

# Check node memory
kubectl top nodes

# Review resource quotas
kubectl describe quota -n jewelry-shop
```

### Slow response times
```bash
# Check for pod CPU throttling
kubectl describe pod -n jewelry-shop <pod-name> | grep -A 5 "cpu"

# Check database connections
kubectl exec -n jewelry-shop <postgres-pod> -- psql -c "SELECT count(*) FROM pg_stat_activity;"

# Check Redis memory
kubectl exec -n jewelry-shop redis-0 -- redis-cli info memory
```

## Sample Results Interpretation

### Good Result (4GB VPS, 50 users)
```
Total Requests: 15,000
Failed: 45 (0.3%)
p50: 450ms
p95: 850ms
p99: 1,200ms
RPS: 25
```
✅ **Verdict:** Excellent! 4GB VPS handles 50 users comfortably.

### Borderline Result (4GB VPS, 100 users)
```
Total Requests: 28,000
Failed: 850 (3%)
p50: 1,100ms
p95: 2,400ms
p99: 3,800ms
RPS: 23
```
⚠️ **Verdict:** VPS is at capacity. Consider 6GB for 100 users.

### Poor Result (4GB VPS, 200 users)
```
Total Requests: 32,000
Failed: 2,500 (7.8%)
p50: 2,500ms
p95: 5,200ms
p99: 12,000ms
RPS: 18
```
❌ **Verdict:** System overloaded. 4GB cannot handle 200 users.

## Reports Generated

After tests complete, find reports in `reports/vps-load-test/`:

1. **HTML Reports** (`*_report.html`) - Interactive charts and graphs
2. **CSV Data** (`*_stats.csv`) - Raw metrics for analysis
3. **Comprehensive Report** (`vps_load_test_report_*.md`) - Summary with recommendations
4. **Resource Usage** (`*_resources_*.txt`) - Pod/node metrics

## Next Steps

1. Run tests with both 4GB and 6GB configurations
2. Compare results
3. Make VPS purchase decision based on:
   - Number of tenants you expect
   - Concurrent users during busy hours
   - Budget
   - Growth plans

4. Deploy to actual VPS and run validation tests
5. Monitor for 1 week, adjust if needed

## Cost-Benefit Analysis

| VPS | Cost/mo | Tenants | Users | Best For |
|-----|---------|---------|-------|----------|
| 4GB/2CPU | $12 | 1-2 | 30-50 | MVP, Single shop |
| 6GB/3CPU | $24 | 3-5 | 75-100 | Small business |
| 8GB/4CPU | $48 | 6-10 | 150-200 | Growing platform |

**Recommendation:** Start with 6GB/3CPU for production. It provides good headroom and comfortable performance.
