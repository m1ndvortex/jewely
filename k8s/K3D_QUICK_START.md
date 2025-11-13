# k3d Quick Start Guide

## ✅ Task 34.1 Completed!

Your k3d development cluster is ready to use.

## Cluster Information

- **Cluster Name**: jewelry-shop
- **Nodes**: 3 (1 server + 2 agents)
- **Status**: All nodes Ready ✅
- **HTTP Port**: 8080 → 80
- **HTTPS Port**: 8443 → 443
- **Traefik**: Disabled (custom version in task 34.9)

## Quick Commands

### Cluster Management
```bash
# View cluster info
kubectl cluster-info

# View nodes
kubectl get nodes

# View all resources
kubectl get all -A

# Delete cluster (when needed)
./k8s/scripts/cleanup-k3d-cluster.sh

# Recreate cluster
./k8s/scripts/setup-k3d-cluster.sh
```

### Validation
```bash
# Run full validation
./k8s/scripts/validate-cluster.sh

# Check system health
kubectl get pods -n kube-system
kubectl get componentstatuses
```

### Test Deployment
```bash
# Deploy test nginx
kubectl apply -f k8s/test/test-nginx.yaml

# Check test pods
kubectl get pods -n test

# Test nginx endpoint
kubectl exec -n test deployment/test-nginx -- curl -s localhost

# Clean up test
kubectl delete -f k8s/test/test-nginx.yaml
```

### Debugging
```bash
# View pod logs
kubectl logs -n <namespace> <pod-name>

# Follow logs
kubectl logs -n <namespace> <pod-name> -f

# Describe pod
kubectl describe pod -n <namespace> <pod-name>

# Execute command in pod
kubectl exec -it -n <namespace> <pod-name> -- /bin/sh

# Port forward to service
kubectl port-forward -n <namespace> svc/<service-name> 8080:80
```

## Current Status

```
✅ k3d cluster created
✅ 3 nodes running (1 server, 2 agents)
✅ All nodes Ready
✅ System pods healthy
✅ Traefik disabled
✅ Test nginx deployed and verified
✅ Cluster validated and ready
```

## Next Steps

1. **Task 34.2**: Create Kubernetes namespace and base resources
2. **Task 34.3**: Deploy Django application with health checks
3. **Task 34.4**: Deploy Nginx reverse proxy
4. Continue with remaining Kubernetes tasks...

## Documentation

- Full setup guide: `k8s/scripts/README.md`
- Completion report: `k8s/TASK_34.1_COMPLETION_REPORT.md`
- Scripts location: `k8s/scripts/`
- Test manifests: `k8s/test/`

## Support

If you encounter issues:
1. Check Docker is running: `docker info`
2. Check cluster status: `kubectl get nodes`
3. Check system pods: `kubectl get pods -n kube-system`
4. Review troubleshooting guide in `k8s/scripts/README.md`

---

**Cluster Ready!** 🚀
