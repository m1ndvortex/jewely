# Testing Scripts for Jewelry Shop Platform

## Overview

This directory contains comprehensive testing scripts for validating the jewelry-shop platform deployment on Kubernetes (k3d/k3s).

## Test Scripts

### End-to-End Integration Tests

**Script**: `e2e-integration-test.sh`

**Purpose**: Comprehensive integration testing of all platform components

**Tests**: 18 automated tests covering:
- Infrastructure health
- Service connectivity
- Automatic failover
- Self-healing
- Horizontal scaling
- Data persistence
- Security policies
- Monitoring

**Usage**:
```bash
./k8s/scripts/e2e-integration-test.sh
```

**Output**: Colored console output + log file in `k8s/TASK_34.14_TEST_RESULTS_<timestamp>.log`

### Smoke Tests: User Journey

**Script**: `smoke-test-user-journey.sh`

**Purpose**: Validate complete business workflow from login to sale

**Tests**: 8 automated tests covering:
- Database connectivity
- Tenant management
- User management
- Inventory operations
- Sales processing
- Data consistency

**Usage**:
```bash
./k8s/scripts/smoke-test-user-journey.sh
```

**Output**: Colored console output + log file in `k8s/SMOKE_TEST_<timestamp>.log`

## Quick Start

### Run All Tests

```bash
# Make scripts executable
chmod +x k8s/scripts/*.sh

# Run E2E integration tests
./k8s/scripts/e2e-integration-test.sh

# Run smoke tests
./k8s/scripts/smoke-test-user-journey.sh
```

### Expected Results

Both test suites should show:
- ✅ 100% success rate
- ✅ All tests passed
- ✅ No manual intervention required

## Test Categories

### 1. Infrastructure Tests
- Cluster health
- Pod status
- Service discovery
- Persistent volumes
- Resource management

### 2. Connectivity Tests
- Django health endpoints
- Database connections
- Cache connections
- Worker connections
- Reverse proxy

### 3. Failover Tests
- PostgreSQL automatic failover (< 30s)
- Redis automatic failover (< 30s)
- Application reconnection

### 4. Resilience Tests
- Pod self-healing
- Automatic pod recreation
- Service availability

### 5. Scaling Tests
- HPA scale-up under load
- HPA scale-down after load
- Resource utilization

### 6. Business Logic Tests
- Tenant creation
- User management
- Inventory operations
- Sales processing
- Data consistency

## Prerequisites

- k3d cluster running
- All components deployed (tasks 34.1-34.13)
- kubectl configured
- All pods in `jewelry-shop` namespace Running

## Troubleshooting

### Tests Fail: Pods Not Running

```bash
# Check pod status
kubectl get pods -n jewelry-shop

# If pods are missing, redeploy
kubectl apply -f k8s/
```

### Tests Fail: Database Connection

```bash
# Check PostgreSQL cluster
kubectl get postgresql -n jewelry-shop
kubectl logs -n jewelry-shop <postgres-pod>
```

### Tests Fail: HPA Not Scaling

```bash
# Check metrics-server
kubectl get deployment -n kube-system metrics-server

# Install if missing
./k8s/scripts/install-metrics-server.sh
```

## Test Results

Test results are saved to log files:

- E2E Integration: `k8s/TASK_34.14_TEST_RESULTS_<timestamp>.log`
- Smoke Tests: `k8s/SMOKE_TEST_<timestamp>.log`

## Documentation

- **Quick Start Guide**: `k8s/QUICK_START_34.14.md`
- **Completion Report**: `k8s/TASK_34.14_COMPLETION_REPORT.md`
- **Final Summary**: `k8s/TASK_34.14_FINAL_SUMMARY.md`

## Success Criteria

Tests are successful when:

- ✅ All 18 E2E integration tests pass
- ✅ All 8 smoke tests pass
- ✅ PostgreSQL failover < 30 seconds
- ✅ Redis failover < 30 seconds
- ✅ Pod self-healing works automatically
- ✅ HPA scales up and down correctly
- ✅ Complete user journey works
- ✅ Data consistency maintained

## CI/CD Integration

Scripts return appropriate exit codes:

- `0`: All tests passed
- `1`: One or more tests failed

Example CI/CD usage:
```yaml
- name: Run E2E Tests
  run: ./k8s/scripts/e2e-integration-test.sh
  
- name: Run Smoke Tests
  run: ./k8s/scripts/smoke-test-user-journey.sh
```

## Performance Benchmarks

| Metric | Target | Typical |
|--------|--------|---------|
| PostgreSQL Failover | < 30s | 10-20s |
| Redis Failover | < 30s | 10-15s |
| Pod Self-Healing | < 60s | 20-30s |
| HPA Scale-Up | < 120s | 60-90s |
| HPA Scale-Down | < 300s | 120-180s |

## Support

For issues or questions:

1. Check the troubleshooting section
2. Review the documentation files
3. Check test logs for detailed error messages
4. Verify all prerequisites are met

## Version

- **Version**: 1.0.0
- **Last Updated**: 2025-11-13
- **Task**: 34.14 - End-to-End Integration Testing
