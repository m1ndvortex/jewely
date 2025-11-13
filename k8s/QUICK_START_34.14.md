# Quick Start Guide: Task 34.14 - End-to-End Integration Testing

## Overview

This guide covers comprehensive end-to-end integration testing for the jewelry-shop platform on k3d. It includes smoke tests, failover tests, self-healing tests, and HPA scaling tests.

## Prerequisites

- k3d cluster running with all components deployed (tasks 34.1-34.13 completed)
- kubectl configured to access the cluster
- All pods in `jewelry-shop` namespace should be Running

## Test Scripts

### 1. Main E2E Integration Test

**Script**: `k8s/scripts/e2e-integration-test.sh`

**What it tests**:
- Cluster health and pod status
- Service connectivity (Django, PostgreSQL, Redis, Celery, Nginx)
- PostgreSQL automatic failover (< 30 seconds)
- Redis automatic failover (< 30 seconds)
- Pod self-healing
- HPA scaling (scale-up and scale-down)
- Data persistence after pod restarts
- Network policies
- Ingress controller
- Monitoring and metrics
- Persistent volumes
- Resource management
- Configuration management

**Run the test**:
```bash
chmod +x k8s/scripts/e2e-integration-test.sh
./k8s/scripts/e2e-integration-test.sh
```

**Expected output**:
```
========================================
Task 34.14: End-to-End Integration Testing
========================================

✅ Test 1: Cluster is accessible - PASSED
✅ Test 2: All pods are running - PASSED
✅ Test 3: Django health endpoint responds - PASSED
...
========================================
FINAL TEST RESULTS
========================================

Total Tests: 18
Passed: 18
Failed: 0

Success Rate: 100%

✅ ALL TESTS PASSED! ✅
```

### 2. Smoke Test: User Journey

**Script**: `k8s/scripts/smoke-test-user-journey.sh`

**What it tests**:
- Complete user workflow from login to sale completion
- Database connection and schema
- Tenant creation
- User creation
- Inventory management
- Sale processing
- Data consistency

**Run the test**:
```bash
chmod +x k8s/scripts/smoke-test-user-journey.sh
./k8s/scripts/smoke-test-user-journey.sh
```

**Expected output**:
```
========================================
Smoke Test: Complete User Journey
========================================

✅ Database Connection: PASS
✅ Tenant Creation: PASS
✅ Inventory Management: PASS
✅ Sale Processing: PASS
✅ Data Consistency: PASS

✅ ALL SMOKE TESTS PASSED! ✅
```

## Manual Testing Procedures

### Test 1: Verify Cluster Status

```bash
# Check cluster info
kubectl cluster-info

# Check all pods
kubectl get pods -n jewelry-shop

# Check services
kubectl get svc -n jewelry-shop

# Check ingress
kubectl get ingress -n jewelry-shop
```

### Test 2: PostgreSQL Failover Test

```bash
# Identify current master
kubectl get pods -n jewelry-shop -l application=spilo,spilo-role=master

# Kill the master pod
MASTER_POD=$(kubectl get pods -n jewelry-shop -l spilo-role=master -o jsonpath='{.items[0].metadata.name}')
kubectl delete pod -n jewelry-shop $MASTER_POD --grace-period=0 --force

# Watch for new master election (should complete in < 30 seconds)
watch kubectl get pods -n jewelry-shop -l application=spilo

# Verify new master
kubectl get pods -n jewelry-shop -l spilo-role=master
```

### Test 3: Redis Failover Test

```bash
# Identify current Redis master
for pod in redis-0 redis-1 redis-2; do
  echo "Checking $pod..."
  kubectl exec -n jewelry-shop $pod -- redis-cli info replication | grep role
done

# Kill the master pod
kubectl delete pod -n jewelry-shop redis-0 --grace-period=0 --force

# Wait for Sentinel to elect new master (should complete in < 30 seconds)
sleep 10

# Verify new master
for pod in redis-0 redis-1 redis-2; do
  echo "Checking $pod..."
  kubectl exec -n jewelry-shop $pod -- redis-cli info replication | grep role
done
```

### Test 4: Pod Self-Healing Test

```bash
# Get current Django pods
kubectl get pods -n jewelry-shop -l component=django

# Delete one pod
DJANGO_POD=$(kubectl get pods -n jewelry-shop -l component=django -o jsonpath='{.items[0].metadata.name}')
kubectl delete pod -n jewelry-shop $DJANGO_POD

# Watch for automatic recreation
watch kubectl get pods -n jewelry-shop -l component=django

# Verify pod count returns to original
kubectl get pods -n jewelry-shop -l component=django
```

### Test 5: HPA Scaling Test

```bash
# Check current HPA status
kubectl get hpa -n jewelry-shop

# Get current replica count
kubectl get deployment -n jewelry-shop django-deployment

# Generate load
kubectl run load-generator -n jewelry-shop --image=busybox --restart=Never -- /bin/sh -c "while true; do wget -q -O- http://django-service:8000/health/; done"

# Watch HPA scale up (wait 60-120 seconds)
watch kubectl get hpa -n jewelry-shop

# Watch pods scale up
watch kubectl get pods -n jewelry-shop -l component=django

# Stop load generator
kubectl delete pod -n jewelry-shop load-generator

# Watch HPA scale down (wait 2-5 minutes)
watch kubectl get hpa -n jewelry-shop
```

### Test 6: Data Persistence Test

```bash
# Get Django pod
DJANGO_POD=$(kubectl get pods -n jewelry-shop -l component=django -o jsonpath='{.items[0].metadata.name}')

# Write test data to Redis
kubectl exec -n jewelry-shop $DJANGO_POD -- python -c "
from django.core.cache import cache
cache.set('test_key', 'test_value', 300)
print('Data written:', cache.get('test_key'))
"

# Restart Redis pod
kubectl delete pod -n jewelry-shop redis-0

# Wait for pod to restart
kubectl wait --for=condition=Ready pod/redis-0 -n jewelry-shop --timeout=60s

# Read test data (should still exist if persistence is configured)
kubectl exec -n jewelry-shop $DJANGO_POD -- python -c "
from django.core.cache import cache
print('Data after restart:', cache.get('test_key'))
"
```

### Test 7: Network Policy Verification

```bash
# Check NetworkPolicies
kubectl get networkpolicies -n jewelry-shop

# Test allowed connection (Django → PostgreSQL)
DJANGO_POD=$(kubectl get pods -n jewelry-shop -l component=django -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n jewelry-shop $DJANGO_POD -- python manage.py check --database default

# Test denied connection (external → PostgreSQL)
kubectl run test-external --image=busybox -n default -- sleep 3600
kubectl exec -n default test-external -- timeout 5 nc -zv jewelry-shop-db.jewelry-shop.svc.cluster.local 5432
# Should timeout or fail

# Cleanup
kubectl delete pod test-external -n default
```

### Test 8: Complete User Journey

```bash
# Run the smoke test script
./k8s/scripts/smoke-test-user-journey.sh

# Or manually test each step:

# 1. Check database connection
DJANGO_POD=$(kubectl get pods -n jewelry-shop -l component=django -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n jewelry-shop $DJANGO_POD -- python manage.py check --database default

# 2. Create test tenant
kubectl exec -n jewelry-shop $DJANGO_POD -- python manage.py shell -c "
from apps.core.models import Tenant
tenant = Tenant.objects.create(company_name='Test Shop', slug='test-shop', status='ACTIVE')
print(f'Tenant created: {tenant.id}')
"

# 3. Create inventory item
kubectl exec -n jewelry-shop $DJANGO_POD -- python manage.py shell -c "
from apps.inventory.models import InventoryItem, ProductCategory
from apps.core.models import Tenant, Branch
from decimal import Decimal

tenant = Tenant.objects.first()
branch = Branch.objects.filter(tenant=tenant).first()
category = ProductCategory.objects.filter(tenant=tenant).first()

item = InventoryItem.objects.create(
    tenant=tenant,
    sku='TEST-001',
    name='Test Ring',
    category=category,
    karat=18,
    weight_grams=Decimal('5.0'),
    cost_price=Decimal('500'),
    selling_price=Decimal('750'),
    quantity=10,
    branch=branch
)
print(f'Item created: {item.id}')
"

# 4. Create sale
kubectl exec -n jewelry-shop $DJANGO_POD -- python manage.py shell -c "
from apps.sales.models import Sale, SaleItem
from apps.inventory.models import InventoryItem
from apps.core.models import Tenant, Branch, Terminal
from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()
tenant = Tenant.objects.first()
branch = Branch.objects.filter(tenant=tenant).first()
user = User.objects.filter(tenant=tenant).first()
item = InventoryItem.objects.filter(tenant=tenant).first()
terminal = Terminal.objects.filter(branch=branch).first()

sale = Sale.objects.create(
    tenant=tenant,
    sale_number='SALE-001',
    branch=branch,
    terminal=terminal,
    employee=user,
    subtotal=Decimal('750'),
    tax=Decimal('75'),
    total=Decimal('825'),
    payment_method='CASH',
    status='COMPLETED'
)

SaleItem.objects.create(
    sale=sale,
    inventory_item=item,
    quantity=1,
    unit_price=Decimal('750'),
    subtotal=Decimal('750')
)

print(f'Sale created: {sale.id}')
"
```

## Validation Criteria

### ✅ All Smoke Tests Pass

- Database connection works
- Tenant creation succeeds
- User creation succeeds
- Inventory management works
- Sale processing works
- Data consistency maintained

### ✅ Failover Tests Complete Within 30 Seconds

- PostgreSQL master failover: < 30 seconds
- Redis master failover: < 30 seconds
- Application reconnects automatically
- No data loss during failover

### ✅ Self-Healing Tests Show Automatic Recovery

- Deleted pods are automatically recreated
- Pod count returns to desired state
- Services remain available during pod recreation

### ✅ HPA Scales Correctly Under Load

- Pods scale up when CPU/memory usage increases
- Pods scale down when load decreases
- Scaling respects min/max replica limits
- Application remains responsive during scaling

### ✅ Complete User Journey Works

- Login functionality works
- Tenant operations work
- Inventory operations work
- Sale operations work
- Data persists correctly

### ✅ Data Consistency After Failover Events

- No data loss during PostgreSQL failover
- No data loss during Redis failover
- Transactions complete successfully
- Database integrity maintained

## Troubleshooting

### Issue: Tests Fail Due to Missing Pods

**Solution**: Ensure all components are deployed
```bash
kubectl get pods -n jewelry-shop
# All pods should be Running

# If pods are missing, redeploy
kubectl apply -f k8s/
```

### Issue: Database Connection Fails

**Solution**: Check PostgreSQL cluster status
```bash
kubectl get postgresql -n jewelry-shop
kubectl get pods -n jewelry-shop -l application=spilo

# Check logs
kubectl logs -n jewelry-shop <postgres-pod>
```

### Issue: HPA Doesn't Scale

**Solution**: Check metrics-server
```bash
kubectl get deployment -n kube-system metrics-server

# Check if metrics are available
kubectl top pods -n jewelry-shop

# If metrics-server is not installed
./k8s/scripts/install-metrics-server.sh
```

### Issue: Failover Takes Too Long

**Solution**: Check Patroni/Sentinel configuration
```bash
# For PostgreSQL
kubectl logs -n jewelry-shop <postgres-pod> | grep -i failover

# For Redis
kubectl logs -n jewelry-shop redis-sentinel-0 | grep -i failover
```

### Issue: NetworkPolicies Not Enforced

**Note**: k3d uses Flannel CNI which doesn't enforce NetworkPolicies. This is expected in the test environment. NetworkPolicies will be enforced in production with Calico.

## Test Results Location

All test results are saved to log files:

- E2E Integration Test: `k8s/TASK_34.14_TEST_RESULTS_<timestamp>.log`
- Smoke Test: `k8s/SMOKE_TEST_<timestamp>.log`

## Next Steps

After all tests pass:

1. Review test results and logs
2. Document any issues found and fixes applied
3. Update task status to complete
4. Proceed to Task 34.15: Production deployment on k3s VPS

## Success Criteria

Task 34.14 is complete when:

- ✅ All smoke tests pass (8/8)
- ✅ All E2E integration tests pass (18/18)
- ✅ PostgreSQL failover completes in < 30 seconds
- ✅ Redis failover completes in < 30 seconds
- ✅ Pod self-healing works automatically
- ✅ HPA scales up and down correctly
- ✅ Complete user journey works end-to-end
- ✅ Data consistency maintained after all failover events
- ✅ No manual intervention required for any recovery

## Summary

This comprehensive testing suite validates that the jewelry-shop platform is production-ready with:

- Automatic failover for database and cache
- Self-healing capabilities
- Horizontal scaling under load
- Complete business functionality
- Data consistency and integrity

All tests are automated and can be run repeatedly to verify system reliability.
