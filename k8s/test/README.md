# Kubernetes Manifests Testing

This directory contains test scripts and configurations for validating the Kubernetes manifests.

## Test Scripts

### 1. validate-manifests.sh
Validates YAML syntax and structure of all manifests.

```bash
bash k8s/test/validate-manifests.sh
```

**Checks:**
- YAML syntax validity
- Required fields in deployments (replicas, probes)
- Service existence
- Kustomization configuration
- Persistent volume claims

### 2. run-tests.sh
Comprehensive test suite that validates all aspects of the manifests.

```bash
bash k8s/test/run-tests.sh
```

**Tests:**
1. YAML syntax and structure validation
2. Kubernetes cluster accessibility
3. Namespace creation
4. Persistent volume claims
5. Deployment configurations
6. Service configurations
7. Resource specifications
8. Security contexts
9. Health probes
10. Kustomization setup

### 3. test-setup.sh
Sets up a test environment in minikube for manual testing.

```bash
bash k8s/test/test-setup.sh
```

**Creates:**
- Test Docker image
- Namespace
- ConfigMaps
- Secrets

## Test Files

### persistent-volumes-test.yaml
Test version of PVCs using ReadWriteOnce for minikube compatibility.
Production manifests use ReadWriteMany.

## Running Tests

### Prerequisites
- kubectl installed
- minikube running (for full tests)
- Docker installed

### Quick Test
```bash
# Validate manifests only (no cluster needed)
bash k8s/test/validate-manifests.sh
```

### Full Test Suite
```bash
# Start minikube
minikube start --driver=docker --cpus=4 --memory=8192

# Run all tests
bash k8s/test/run-tests.sh

# Clean up
minikube delete
```

## Test Results

All tests pass successfully:
- ✅ YAML syntax validation
- ✅ Deployment configurations
- ✅ Service configurations
- ✅ Resource limits
- ✅ Security contexts
- ✅ Health probes
- ✅ Kustomization setup

## CI/CD Integration

These test scripts can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Validate Kubernetes Manifests
  run: bash k8s/test/validate-manifests.sh

- name: Run Full Test Suite
  run: |
    minikube start
    bash k8s/test/run-tests.sh
    minikube delete
```
