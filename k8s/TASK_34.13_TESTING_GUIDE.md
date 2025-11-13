# Task 34.13 Testing Guide: Network Policies

## Quick Test Commands

### 1. Apply NetworkPolicies

```bash
# Apply all network policies
kubectl apply -f k8s/network-policies.yaml

# Verify 17 policies are created
kubectl get networkpolicies -n jewelry-shop
```

Expected: 17 NetworkPolicies listed

### 2. Run Automated Validation

```bash
# Run the validation script
./k8s/scripts/validate-network-policies.sh
```

Expected output:
```
✓ PASS: Found 17 NetworkPolicies
✓ PASS: Django can connect to PostgreSQL
✓ PASS: Django can connect to Redis
✓ PASS: Nginx can connect to Django
✓ PASS: External pod cannot connect to PostgreSQL (blocked by NetworkPolicy)
✓ PASS: External pod cannot connect to Redis (blocked by NetworkPolicy)
✓ PASS: Celery worker can connect to PostgreSQL
✓ PASS: Celery worker can connect to Redis
```

### 3. Manual Connectivity Tests

#### Test Django → PostgreSQL (should succeed)

```bash
DJANGO_POD=$(kubectl get pods -n jewelry-shop -l component=django -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n jewelry-shop $DJANGO_POD -- nc -zv jewelry-shop-db-pooler 5432
```

Expected: `succeeded!` or `open`

#### Test Django → Redis (should succeed)

```bash
kubectl exec -n jewelry-shop $DJANGO_POD -- nc -zv redis 6379
```

Expected: `succeeded!` or `open`

#### Test Nginx → Django (should succeed)

```bash
NGINX_POD=$(kubectl get pods -n jewelry-shop -l component=nginx -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n jewelry-shop $NGINX_POD -- nc -zv django-service 80
```

Expected: `succeeded!` or `open`

#### Test External → PostgreSQL (should fail)

```bash
# Create test pod in default namespace
kubectl run netpol-test --image=busybox:1.35 --restart=Never -- sleep 3600

# Wait for pod
sleep 5

# Try to connect (should timeout)
kubectl exec -n default netpol-test -- timeout 5 nc -zv jewelry-shop-db-pooler.jewelry-shop.svc.cluster.local 5432

# Cleanup
kubectl delete pod netpol-test -n default --force --grace-period=0
```

Expected: Connection timeout or failure

#### Test External → Redis (should fail)

```bash
# Create test pod in default namespace
kubectl run netpol-test --image=busybox:1.35 --restart=Never -- sleep 3600

# Wait for pod
sleep 5

# Try to connect (should timeout)
kubectl exec -n default netpol-test -- timeout 5 nc -zv redis.jewelry-shop.svc.cluster.local 6379

# Cleanup
kubectl delete pod netpol-test -n default --force --grace-period=0
```

Expected: Connection timeout or failure

### 4. Inspect NetworkPolicies

#### List all policies

```bash
kubectl get networkpolicies -n jewelry-shop
```

#### Describe specific policy

```bash
# Django to PostgreSQL policy
kubectl describe networkpolicy allow-django-to-postgresql -n jewelry-shop

# Deny external to PostgreSQL policy
kubectl describe networkpolicy deny-external-to-postgresql -n jewelry-shop
```

#### View policy YAML

```bash
kubectl get networkpolicy allow-django-to-redis -n jewelry-shop -o yaml
```

### 5. Test Application Functionality

After applying NetworkPolicies, verify the application still works:

```bash
# Test Django health endpoint
kubectl exec -n jewelry-shop $DJANGO_POD -- curl -s http://localhost:8000/health/live/

# Test Redis connection from Django
kubectl exec -n jewelry-shop $DJANGO_POD -- python manage.py shell -c "from django.core.cache import cache; cache.set('test', 'value'); print(cache.get('test'))"

# Test database connection from Django
kubectl exec -n jewelry-shop $DJANGO_POD -- python manage.py check --database default
```

Expected: All commands succeed

### 6. Test Celery Worker Connectivity

```bash
CELERY_POD=$(kubectl get pods -n jewelry-shop -l component=celery-worker -o jsonpath='{.items[0].metadata.name}')

# Test PostgreSQL connection
kubectl exec -n jewelry-shop $CELERY_POD -- nc -zv jewelry-shop-db-pooler 5432

# Test Redis connection
kubectl exec -n jewelry-shop $CELERY_POD -- nc -zv redis 6379
```

Expected: Both connections succeed

## Validation Checklist

- [ ] 17 NetworkPolicies created
- [ ] Django can connect to PostgreSQL ✓
- [ ] Django can connect to Redis ✓
- [ ] Nginx can connect to Django ✓
- [ ] Celery workers can connect to PostgreSQL ✓
- [ ] Celery workers can connect to Redis ✓
- [ ] External pods CANNOT connect to PostgreSQL ✗
- [ ] External pods CANNOT connect to Redis ✗
- [ ] Application health checks pass
- [ ] Django can query database
- [ ] Django can access cache
- [ ] Celery workers can process tasks

## Troubleshooting

### If Django cannot connect to PostgreSQL

```bash
# Check if policy exists
kubectl get networkpolicy allow-django-to-postgresql -n jewelry-shop

# Check Django pod labels
kubectl get pods -n jewelry-shop -l component=django --show-labels

# Check PostgreSQL pod labels
kubectl get pods -n jewelry-shop -l application=spilo --show-labels

# Describe the policy
kubectl describe networkpolicy allow-django-to-postgresql -n jewelry-shop
```

### If external test succeeds (should fail)

This means NetworkPolicies are not being enforced. Check:

```bash
# Verify CNI supports NetworkPolicies
kubectl get nodes -o wide

# Check if NetworkPolicy controller is running
kubectl get pods -n kube-system | grep -i network

# For k3d/k3s, NetworkPolicies should work by default
```

### If monitoring stops working

```bash
# Check monitoring policy
kubectl get networkpolicy allow-monitoring-to-all-pods -n jewelry-shop

# Verify monitoring namespace label
kubectl get namespace monitoring --show-labels

# Add label if missing
kubectl label namespace monitoring name=monitoring
```

## Performance Testing

After applying NetworkPolicies, verify no performance degradation:

```bash
# Test response time before NetworkPolicies
time kubectl exec -n jewelry-shop $DJANGO_POD -- curl -s http://localhost:8000/health/live/

# Apply NetworkPolicies
kubectl apply -f k8s/network-policies.yaml

# Test response time after NetworkPolicies
time kubectl exec -n jewelry-shop $DJANGO_POD -- curl -s http://localhost:8000/health/live/
```

Expected: No significant difference (< 1ms)

## Cleanup (if needed)

To remove all NetworkPolicies:

```bash
# Delete all NetworkPolicies
kubectl delete -f k8s/network-policies.yaml

# Or delete individually
kubectl delete networkpolicy <policy-name> -n jewelry-shop

# Or delete all in namespace
kubectl delete networkpolicies --all -n jewelry-shop
```

## Success Criteria

✅ All 17 NetworkPolicies created
✅ Authorized traffic flows work (Django ↔ PostgreSQL, Django ↔ Redis, Nginx ↔ Django)
✅ Unauthorized traffic is blocked (External → PostgreSQL, External → Redis)
✅ Application functionality unchanged
✅ No performance degradation
✅ Monitoring still works

## Next Steps

After successful testing:

1. Document any issues found
2. Proceed to Task 34.14 (End-to-end integration testing)
3. Apply to production in Task 34.15
4. Include in load testing for Task 34.16
