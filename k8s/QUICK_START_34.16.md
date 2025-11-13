# Quick Start: Task 34.16 - Load Testing & Chaos Engineering

## One-Command Execution

```bash
cd k8s
bash scripts/task-34.16-complete-test.sh
```

This single command will:
1. ✅ Validate prerequisites
2. ✅ Build and deploy Locust (1000 users)
3. ✅ Run 30-minute load test
4. ✅ Monitor HPA scaling (3 → 10 → 3 pods)
5. ✅ Execute all chaos tests
6. ✅ Generate comprehensive reports
7. ✅ Cleanup infrastructure

**Duration:** ~50 minutes total
- Load test: 30 minutes
- HPA monitoring: 10 minutes
- Chaos tests: 5 minutes
- Scale-down monitoring: 10 minutes

## What Gets Tested

### Load Testing
- 1000 concurrent users
- Realistic user behavior (dashboard, inventory, POS, customers, reports)
- 30-minute sustained load
- HPA scaling validation

### Chaos Engineering
- PostgreSQL master failure (RTO < 30s)
- Redis master failure (RTO < 30s)
- Random Django pod failures
- Node failure simulation
- Network partition simulation

## Expected Output

```
============================================================================
TASK 34.16: EXTREME LOAD TESTING AND CHAOS ENGINEERING
============================================================================

Test Configuration:
  - Concurrent Users: 1000
  - Spawn Rate: 50 users/second
  - Duration: 30m
  - Namespace: jewelry-shop

[... test execution ...]

============================================================================
TASK 34.16 COMPLETE
============================================================================

Test Summary:
  - Load Test: 1000 users for 30m
  - HPA Scale-Up: 3 → 10 pods
  - HPA Scale-Down: 10 → 3 pods
  - Chaos Tests: Completed
  - System Health: ✅ Healthy

✅ All tests completed successfully

Reports Generated:
  - Final Report: k8s/test-results-34.16/TASK_34.16_FINAL_REPORT_*.md
  - Chaos Report: k8s/test-results-34.16/chaos_test_report_*.md
  - Load Stats: k8s/test-results-34.16/locust-stats.json
```

## View Results

```bash
# View final report
cat k8s/test-results-34.16/TASK_34.16_FINAL_REPORT_*.md

# View chaos test report
cat k8s/test-results-34.16/chaos_test_report_*.md

# View load test statistics
cat k8s/test-results-34.16/locust-stats.json | jq .
```

## Monitor During Test

### Terminal 1: Run Test
```bash
bash scripts/task-34.16-complete-test.sh
```

### Terminal 2: Watch HPA
```bash
watch kubectl get hpa django-hpa -n jewelry-shop
```

### Terminal 3: Watch Pods
```bash
watch kubectl get pods -n jewelry-shop -l component=django
```

### Terminal 4: Watch Metrics
```bash
watch kubectl top pods -n jewelry-shop -l component=django
```

## Manual Locust Web UI Access

If you want to use the Locust web UI manually:

```bash
# Deploy Locust
cd k8s/locust
docker build -t locust-jewelry:latest .
k3d image import locust-jewelry:latest -c jewelry-shop
cd ..

kubectl apply -f locust/locust-master.yaml
kubectl apply -f locust/locust-worker.yaml

# Wait for ready
kubectl wait --for=condition=ready pod -l app=locust -n jewelry-shop --timeout=120s

# Access web UI
kubectl port-forward -n jewelry-shop svc/locust-master 8089:8089
```

Open http://localhost:8089 and configure:
- Number of users: 1000
- Spawn rate: 50
- Host: http://django-service.jewelry-shop.svc.cluster.local

## Troubleshooting

### Test Fails at Prerequisites
```bash
# Check cluster
kubectl cluster-info

# Check deployments
kubectl get deployments -n jewelry-shop

# Check HPA
kubectl get hpa -n jewelry-shop

# Install metrics server if missing
bash scripts/install-metrics-server.sh
```

### Locust Build Fails
```bash
# Check Docker
docker ps

# Rebuild
cd k8s/locust
docker build -t locust-jewelry:latest . --no-cache
k3d image import locust-jewelry:latest -c jewelry-shop
```

### HPA Not Scaling
```bash
# Check metrics server
kubectl get deployment metrics-server -n kube-system

# Check HPA events
kubectl describe hpa django-hpa -n jewelry-shop

# Check pod metrics
kubectl top pods -n jewelry-shop -l component=django
```

### Chaos Tests Fail
```bash
# Check PostgreSQL
kubectl get postgresql -n jewelry-shop

# Check Redis
kubectl get pods -n jewelry-shop -l app=redis

# Check Django
kubectl get pods -n jewelry-shop -l component=django
```

## Success Indicators

✅ **Load Test:**
- 1000 users spawned successfully
- > 100,000 total requests
- > 99% success rate
- < 500ms average response time

✅ **HPA Scaling:**
- Scaled from 3 to 10 pods
- Scaled back down to 3 pods
- All transitions smooth

✅ **Chaos Tests:**
- All failovers < 30s
- Zero data loss
- Zero manual intervention
- Automatic recovery

✅ **System Health:**
- All deployments healthy
- PostgreSQL master elected
- Redis master elected
- All pods running

## Next Steps

After successful completion:

1. Review generated reports
2. Document any findings
3. Update runbooks if needed
4. Proceed to task 34.15 (Production deployment)
5. Implement automated chaos testing in CI/CD

## Quick Reference

```bash
# Run complete test
bash scripts/task-34.16-complete-test.sh

# View reports
ls -lh k8s/test-results-34.16/

# Check system health
kubectl get all -n jewelry-shop

# View HPA status
kubectl get hpa -n jewelry-shop

# View pod metrics
kubectl top pods -n jewelry-shop

# Cleanup (if needed)
kubectl delete -f locust/locust-worker.yaml
kubectl delete -f locust/locust-master.yaml
```

---

**Estimated Time:** 50 minutes
**Difficulty:** Automated
**Prerequisites:** Tasks 34.1-34.14 complete
**Status:** ✅ Ready to run
