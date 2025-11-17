# Load Testing & Chaos Engineering

This directory contains comprehensive load testing and chaos engineering tools for validating production readiness.

## Files

### VPS Load Testing (Realistic Production Simulation)
- `locustfile_vps.py` - Load test optimized for small VPS (4-6GB RAM, 2-3 CPU)
- `setup_vps_simulation.sh` - Configure cluster to match VPS constraints
- `run_vps_load_tests.sh` - Run complete test suite (4 scenarios)
- `vps_simulation_config.yaml` - VPS configuration reference
- `VPS_TESTING_GUIDE.md` - Complete usage guide

### Extreme Load Testing (Development/Large Clusters)
- `locustfile.py` - Load test for 1000+ concurrent users
- `run_extreme_load_test.sh` - Extreme load + chaos tests

### Chaos Engineering
- `chaos_test_suite.sh` - Automated chaos tests (failover, self-healing, etc.)

## Quick Start

### Realistic VPS Testing (Recommended)
```bash
# Test 4GB RAM / 2 CPU VPS
./tests/load/run_vps_load_tests.sh 4 2

# Test 6GB RAM / 3 CPU VPS (recommended)
./tests/load/run_vps_load_tests.sh 6 3
```

### Extreme Load Testing
```bash
# 1000 users for 30 minutes
./tests/run_extreme_load_test.sh
```

### Chaos Testing
```bash
# Test failover and self-healing
./tests/chaos/chaos_test_suite.sh
```

## See Also
- [VPS Testing Guide](VPS_TESTING_GUIDE.md) - Detailed instructions
- [Task 34.16](../../.kiro/specs/jewelry-saas-platform/tasks.md#L1342) - Full requirements
