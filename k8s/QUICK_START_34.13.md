# Quick Start Guide: Task 34.13 - Network Policies for Security

## Overview

This guide covers the implementation of Kubernetes NetworkPolicies for the jewelry-shop platform. NetworkPolicies provide network-level security by controlling traffic flow between pods, implementing a zero-trust networking model.

## What Was Implemented

### NetworkPolicies Created

1. **allow-nginx-to-django** - Allows Nginx to proxy requests to Django
2. **allow-django-to-postgresql** - Allows Django to access PostgreSQL database
3. **allow-django-to-pgbouncer** - Allows Django to use PgBouncer connection pooler
4. **allow-django-to-redis** - Allows Django to access Redis cache
5. **allow-celery-to-postgresql** - Allows Celery workers to access database
6. **allow-celery-to-redis** - Allows Celery workers to access Redis message broker
7. **allow-celery-beat-to-redis** - Allows Celery Beat scheduler to access Redis
8. **allow-celery-beat-to-postgresql** - Allows Celery Beat to access database
9. **allow-sentinel-to-redis** - Allows Redis Sentinel to monitor Redis instances
10. **allow-monitoring-to-all-pods** - Allows Prometheus to scrape metrics
11. **allow-ingress-to-nginx** - Allows Traefik to route traffic to Nginx
12. **deny-external-to-postgresql** - Explicitly denies external access to database
13. **deny-external-to-redis** - Explicitly denies external access to Redis
14. **allow-dns-access** - Allows all pods to resolve DNS names
15. **allow-django-egress** - Allows Django to make outbound connections
16. **allow-celery-worker-egress** - Allows Celery workers to make outbound connections
17. **allow-nginx-egress** - Allows Nginx to proxy to Django

## Prerequisites

- Kubernetes cluster with NetworkPolicy support (k3d/k3s has this enabled by default)
- jewelry-shop namespace created
- Pods deployed (Django, Nginx, PostgreSQL, Redis, Celery)

## Step 1: Apply NetworkPolicies

```bash
# Apply all network policies
kubectl apply -f k8s/network-policies.yaml

# Verify policies are created
kubectl get networkpolicies -n jewelry-shop
```

Expected output:
```
NAME                              POD-SELECTOR                        AGE
allow-celery-beat-to-postgresql   application=db-connection-pooler    1m
allow-celery-beat-to-redis        app=redis,component=server          1m
allow-celery-to-postgresql        application=db-connection-pooler    1m
allow-celery-to-redis             app=redis,component=server          1m
allow-celery-worker-egress        component=celery-worker             1m
allow-django-egress               component=django                    1m
allow-django-to-pgbouncer         application=db-connection-pooler    1m
allow-django-to-postgresql        application=spilo                   1m
allow-django-to-redis             app=redis,component=server          1m
allow-dns-access                  <none>                              1m
allow-ingress-to-nginx            component=nginx                     1m
allow-monitoring-to-all-pods      <none>                              1m
allow-nginx-egress                component=nginx                     1m
allow-nginx-to-django             component=django                    1m
allow-sentinel-to-redis           app=redis,component=server          1m
deny-external-to-postgresql       application=spilo                   1m
deny-external-to-redis            app=redis,component=server          1m
```

## Step 2: Validate NetworkPolicies

Run the validation script to test that policies are working correctly:

```bash
# Run validation tests
./k8s/scripts/validate-network-policies.sh
```

The script will test:
- ✓ Django can connect to PostgreSQL (should succeed)
- ✓ Django can connect to Redis (should succeed)
- ✓ Nginx can connect to Django (should succeed)
- ✓ Celery workers can connect to PostgreSQL (should succeed)
- ✓ Celery workers can connect to Redis (should succeed)
- ✗ External pods cannot connect to PostgreSQL (should fail - blocked)
- ✗ External pods cannot connect to Redis (should fail - blocked)

## Step 3: Manual Testing

### Test 1: Verify Django can connect to PostgreSQL

```bash
# Get Django pod name
DJANGO_POD=$(kubectl get pods -n jewelry-shop -l component=django -o jsonpath='{.items[0].metadata.name}')

# Test connection
kubectl exec -n jewelry-shop $DJANGO_POD -- nc -zv jewelry-shop-db-pooler 5432
```

Expected: Connection succeeds

### Test 2: Verify Django can connect to Redis

```bash
# Test Redis connection
kubectl exec -n jewelry-shop $DJANGO_POD -- nc -zv redis 6379
```

Expected: Connection succeeds

### Test 3: Verify Nginx can connect to Django

```bash
# Get Nginx pod name
NGINX_POD=$(kubectl get pods -n jewelry-shop -l component=nginx -o jsonpath='{.items[0].metadata.name}')

# Test connection
kubectl exec -n jewelry-shop $NGINX_POD -- nc -zv django-service 80
```

Expected: Connection succeeds

### Test 4: Try to connect to PostgreSQL from outside cluster (should fail)

```bash
# Create test pod in default namespace
kubectl run netpol-test --image=busybox:1.35 --restart=Never -- sleep 3600

# Wait for pod to be ready
kubectl wait --for=condition=Ready pod/netpol-test -n default --timeout=30s

# Try to connect to PostgreSQL (should timeout/fail)
kubectl exec -n default netpol-test -- timeout 5 nc -zv jewelry-shop-db-pooler.jewelry-shop.svc.cluster.local 5432

# Cleanup
kubectl delete pod netpol-test -n default
```

Expected: Connection fails or times out (blocked by NetworkPolicy)

### Test 5: Try to connect to Redis from outside cluster (should fail)

```bash
# Create test pod in default namespace
kubectl run netpol-test --image=busybox:1.35 --restart=Never -- sleep 3600

# Wait for pod to be ready
kubectl wait --for=condition=Ready pod/netpol-test -n default --timeout=30s

# Try to connect to Redis (should timeout/fail)
kubectl exec -n default netpol-test -- timeout 5 nc -zv redis.jewelry-shop.svc.cluster.local 6379

# Cleanup
kubectl delete pod netpol-test -n default
```

Expected: Connection fails or times out (blocked by NetworkPolicy)

## Step 4: Inspect NetworkPolicies

### View all policies

```bash
kubectl get networkpolicies -n jewelry-shop
```

### Describe a specific policy

```bash
# View Django to PostgreSQL policy
kubectl describe networkpolicy allow-django-to-postgresql -n jewelry-shop

# View deny external to PostgreSQL policy
kubectl describe networkpolicy deny-external-to-postgresql -n jewelry-shop
```

### View policy in YAML format

```bash
kubectl get networkpolicy allow-django-to-redis -n jewelry-shop -o yaml
```

## Understanding NetworkPolicy Behavior

### Default Deny

Once a NetworkPolicy selects a pod (via `podSelector`), all traffic not explicitly allowed is denied. This is the "default deny" behavior.

### Ingress vs Egress

- **Ingress**: Controls incoming traffic to pods
- **Egress**: Controls outgoing traffic from pods

### Policy Combination

Multiple NetworkPolicies can select the same pod. The rules are additive - if any policy allows the traffic, it's permitted.

### Example: Django Pod

The Django pod is selected by multiple policies:
1. `allow-nginx-to-django` - Allows ingress from Nginx
2. `allow-monitoring-to-all-pods` - Allows ingress from monitoring tools
3. `allow-django-egress` - Allows egress to PostgreSQL, Redis, and external services

All these rules combine to define what traffic is allowed to/from Django pods.

## Troubleshooting

### Issue: Pods cannot communicate after applying NetworkPolicies

**Cause**: NetworkPolicies are too restrictive or missing required rules

**Solution**:
1. Check if the policy exists:
   ```bash
   kubectl get networkpolicies -n jewelry-shop
   ```

2. Verify pod labels match policy selectors:
   ```bash
   kubectl get pods -n jewelry-shop --show-labels
   ```

3. Check policy details:
   ```bash
   kubectl describe networkpolicy <policy-name> -n jewelry-shop
   ```

4. Temporarily delete policies to test:
   ```bash
   kubectl delete networkpolicy <policy-name> -n jewelry-shop
   ```

### Issue: DNS resolution not working

**Cause**: Missing DNS egress rule

**Solution**: The `allow-dns-access` policy should allow DNS. Verify it's applied:
```bash
kubectl get networkpolicy allow-dns-access -n jewelry-shop
```

### Issue: Monitoring not working

**Cause**: Prometheus cannot scrape metrics

**Solution**: Verify the `allow-monitoring-to-all-pods` policy is applied and the monitoring namespace has the correct label:
```bash
kubectl get networkpolicy allow-monitoring-to-all-pods -n jewelry-shop
kubectl get namespace monitoring --show-labels
```

## Security Best Practices

### 1. Principle of Least Privilege

Only allow the minimum required traffic. Each policy should be as specific as possible.

### 2. Explicit Deny

While NetworkPolicies have default deny behavior, explicit deny policies make intent clear and serve as documentation.

### 3. Label Consistency

Use consistent labels across all resources to make NetworkPolicy management easier.

### 4. Regular Audits

Periodically review NetworkPolicies to ensure they still match your security requirements:
```bash
kubectl get networkpolicies -n jewelry-shop -o yaml > network-policies-backup.yaml
```

### 5. Testing

Always test NetworkPolicies in a non-production environment first. Use the validation script regularly.

## Monitoring NetworkPolicy Effectiveness

### Check policy events

```bash
kubectl get events -n jewelry-shop --field-selector involvedObject.kind=NetworkPolicy
```

### Monitor denied connections (requires CNI plugin support)

Some CNI plugins (like Calico) can log denied connections. Check your CNI documentation for details.

### Use network policy visualization tools

Tools like `kubectl-netpol` can help visualize NetworkPolicies:
```bash
# Install kubectl-netpol plugin
kubectl krew install np-viewer

# Visualize policies
kubectl np-viewer -n jewelry-shop
```

## Next Steps

After implementing NetworkPolicies:

1. **Task 34.14**: End-to-end integration testing
   - Test complete application stack
   - Verify all features work with NetworkPolicies enabled

2. **Task 34.15**: Deploy to production k3s
   - Apply same NetworkPolicies to production
   - Monitor for any connectivity issues

3. **Task 34.16**: Extreme load testing
   - Verify NetworkPolicies don't impact performance
   - Test under high load conditions

## Additional Resources

- [Kubernetes NetworkPolicy Documentation](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [NetworkPolicy Recipes](https://github.com/ahmetb/kubernetes-network-policy-recipes)
- [Calico NetworkPolicy Tutorial](https://docs.projectcalico.org/security/tutorials/kubernetes-policy-basic)

## Summary

NetworkPolicies provide essential network-level security for the jewelry-shop platform:

✅ **Zero-trust networking**: Only explicitly allowed traffic is permitted
✅ **Database isolation**: PostgreSQL and Redis are not accessible from outside the namespace
✅ **Service segmentation**: Each service can only communicate with authorized services
✅ **Monitoring access**: Prometheus can collect metrics from all pods
✅ **External connectivity**: Django and Celery can access external APIs as needed

The platform now has defense-in-depth security with both application-level and network-level controls.
