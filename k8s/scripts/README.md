# k3d Cluster Setup Scripts

This directory contains scripts for setting up and managing the local k3d development cluster for the Jewelry Shop SaaS platform.

## Overview

k3d is a lightweight wrapper to run k3s (Rancher Lab's minimal Kubernetes distribution) in Docker. It creates Kubernetes clusters using Docker containers as nodes, making it perfect for local development and testing.

## Prerequisites

- Docker installed and running
- Bash shell (Linux/macOS) or WSL (Windows)
- Sufficient system resources (recommended: 4GB RAM, 2 CPU cores)

## Scripts

### 1. setup-k3d-cluster.sh

Creates a new k3d cluster with the following configuration:
- **Cluster name**: jewelry-shop
- **Server nodes**: 1 (control plane)
- **Agent nodes**: 2 (worker nodes)
- **Port mappings**:
  - HTTP: 8080:80
  - HTTPS: 8443:443
- **Traefik**: Disabled (custom version will be installed later)

**Usage:**
```bash
chmod +x k8s/scripts/setup-k3d-cluster.sh
./k8s/scripts/setup-k3d-cluster.sh
```

**What it does:**
1. Checks if Docker is running
2. Installs k3d if not already installed
3. Installs kubectl if not already installed
4. Creates the k3d cluster with specified configuration
5. Verifies cluster accessibility
6. Displays cluster information

**Features:**
- Idempotent: Can be run multiple times safely
- Interactive: Prompts before deleting existing cluster
- Automatic installation: Installs k3d and kubectl if missing
- Validation: Verifies cluster is accessible after creation

### 2. validate-cluster.sh

Validates that the k3d cluster meets all requirements from task 34.1.

**Usage:**
```bash
chmod +x k8s/scripts/validate-cluster.sh
./k8s/scripts/validate-cluster.sh
```

**Validations performed:**
1. ✓ kubectl is available
2. ✓ Cluster is accessible
3. ✓ 3 nodes exist (1 server, 2 agents)
4. ✓ All nodes are Ready
5. ✓ Node roles are correct
6. ✓ Traefik is disabled
7. ✓ System pods are running
8. ✓ Namespaces are created

**Exit codes:**
- 0: All validations passed
- 1: One or more validations failed

### 3. cleanup-k3d-cluster.sh

Deletes the k3d cluster and cleans up resources.

**Usage:**
```bash
chmod +x k8s/scripts/cleanup-k3d-cluster.sh
./k8s/scripts/cleanup-k3d-cluster.sh
```

**What it does:**
1. Checks if cluster exists
2. Prompts for confirmation
3. Deletes the cluster
4. Cleans up kubeconfig entries

**Warning:** This will delete all data in the cluster. Make sure to backup any important data before running.

## Quick Start

1. **Create the cluster:**
   ```bash
   ./k8s/scripts/setup-k3d-cluster.sh
   ```

2. **Validate the cluster:**
   ```bash
   ./k8s/scripts/validate-cluster.sh
   ```

3. **Deploy test nginx:**
   ```bash
   kubectl apply -f k8s/test/test-nginx.yaml
   ```

4. **Verify test deployment:**
   ```bash
   kubectl get pods -n test
   kubectl get svc -n test
   ```

5. **Test nginx is running:**
   ```bash
   kubectl exec -n test deployment/test-nginx -- curl -s localhost
   ```

6. **Clean up test deployment:**
   ```bash
   kubectl delete -f k8s/test/test-nginx.yaml
   ```

## Common Commands

### Cluster Management
```bash
# List all k3d clusters
k3d cluster list

# Get cluster info
kubectl cluster-info

# Get nodes
kubectl get nodes

# Get all resources in all namespaces
kubectl get all -A
```

### Context Management
```bash
# List contexts
kubectl config get-contexts

# Switch context
kubectl config use-context k3d-jewelry-shop

# View current context
kubectl config current-context
```

### Port Forwarding
```bash
# Forward local port to service
kubectl port-forward -n test svc/test-nginx 8080:80

# Access in browser: http://localhost:8080
```

### Logs and Debugging
```bash
# Get pod logs
kubectl logs -n test deployment/test-nginx

# Follow logs
kubectl logs -n test deployment/test-nginx -f

# Describe pod
kubectl describe pod -n test <pod-name>

# Execute command in pod
kubectl exec -it -n test <pod-name> -- /bin/sh
```

## Troubleshooting

### Cluster won't start
```bash
# Check Docker is running
docker info

# Check Docker resources
docker stats

# Delete and recreate cluster
./k8s/scripts/cleanup-k3d-cluster.sh
./k8s/scripts/setup-k3d-cluster.sh
```

### Nodes not Ready
```bash
# Check node status
kubectl get nodes -o wide

# Check system pods
kubectl get pods -n kube-system

# Describe node
kubectl describe node <node-name>
```

### Port conflicts
If ports 8080 or 8443 are already in use:
1. Stop the conflicting service
2. Or modify the ports in setup-k3d-cluster.sh
3. Recreate the cluster

### kubectl not working
```bash
# Verify kubeconfig
kubectl config view

# Merge kubeconfig
k3d kubeconfig merge jewelry-shop --kubeconfig-switch-context

# Test connection
kubectl cluster-info
```

## Architecture

```
┌─────────────────────────────────────────┐
│           Host Machine                   │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │         Docker Engine              │ │
│  │                                    │ │
│  │  ┌──────────────────────────────┐ │ │
│  │  │  k3d-jewelry-shop-server-0   │ │ │
│  │  │  (Control Plane)             │ │ │
│  │  │  - API Server                │ │ │
│  │  │  - Scheduler                 │ │ │
│  │  │  - Controller Manager        │ │ │
│  │  │  - etcd                      │ │ │
│  │  └──────────────────────────────┘ │ │
│  │                                    │ │
│  │  ┌──────────────────────────────┐ │ │
│  │  │  k3d-jewelry-shop-agent-0    │ │ │
│  │  │  (Worker Node)               │ │ │
│  │  │  - kubelet                   │ │ │
│  │  │  - kube-proxy                │ │ │
│  │  └──────────────────────────────┘ │ │
│  │                                    │ │
│  │  ┌──────────────────────────────┐ │ │
│  │  │  k3d-jewelry-shop-agent-1    │ │ │
│  │  │  (Worker Node)               │ │ │
│  │  │  - kubelet                   │ │ │
│  │  │  - kube-proxy                │ │ │
│  │  └──────────────────────────────┘ │ │
│  │                                    │ │
│  │  ┌──────────────────────────────┐ │ │
│  │  │  k3d-jewelry-shop-serverlb   │ │ │
│  │  │  (Load Balancer)             │ │ │
│  │  │  - Port 8080 → 80            │ │ │
│  │  │  - Port 8443 → 443           │ │ │
│  │  └──────────────────────────────┘ │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

## Next Steps

After successfully setting up the k3d cluster:

1. **Task 34.2**: Create Kubernetes namespace and base resources
2. **Task 34.3**: Deploy Django application with health checks
3. **Task 34.4**: Deploy Nginx reverse proxy
4. **Task 34.5**: Install Zalando Postgres Operator
5. Continue with remaining Kubernetes deployment tasks...

## References

- [k3d Documentation](https://k3d.io/)
- [k3s Documentation](https://k3s.io/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)

## Task Completion

This setup completes **Task 34.1** from the implementation plan:
- ✓ Install k3d on development machine
- ✓ Create k3d cluster with 1 server + 2 agents
- ✓ Configure port mappings for HTTP (8080:80) and HTTPS (8443:443)
- ✓ Disable default Traefik
- ✓ Validation: kubectl get nodes shows 3 nodes with STATUS=Ready
- ✓ Validation: kubectl cluster-info shows cluster is accessible
- ✓ Test: Deploy test nginx pod and verify it runs successfully
