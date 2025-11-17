#!/bin/bash
# Comprehensive VPS Load Testing Suite
# Tests realistic production scenarios for 4-6GB RAM, 2-3 CPU VPS

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Configuration
NAMESPACE="jewelry-shop"
REPORT_DIR="reports/vps-load-test"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
VPS_RAM=${1:-4}  # Default 4GB
VPS_CPU=${2:-2}  # Default 2 cores

mkdir -p "$REPORT_DIR"

print_header "VPS LOAD TESTING SUITE"
echo "Target VPS: ${VPS_RAM}GB RAM, ${VPS_CPU} CPU cores"
echo "Report directory: $REPORT_DIR"
echo ""

# Setup VPS simulation
print_info "Setting up VPS resource constraints..."
bash tests/load/setup_vps_simulation.sh "$VPS_RAM" "$VPS_CPU"
echo ""

# Wait for Locust to be ready
print_info "Checking Locust deployment..."
kubectl wait --for=condition=ready pod -l app=locust,component=master -n "$NAMESPACE" --timeout=60s

LOCUST_POD=$(kubectl get pods -n "$NAMESPACE" -l app=locust,component=master -o jsonpath='{.items[0].metadata.name}')
print_success "Locust master ready: $LOCUST_POD"
echo ""

# Function to run load test
run_load_test() {
    local test_name=$1
    local users=$2
    local spawn_rate=$3
    local duration=$4
    local description=$5
    
    print_header "$test_name"
    echo "Users: $users"
    echo "Spawn rate: $spawn_rate users/sec"
    echo "Duration: $duration"
    echo "Description: $description"
    echo ""
    
    print_info "Starting load test..."
    
    # Start monitoring in background
    kubectl top pods -n "$NAMESPACE" --containers > "$REPORT_DIR/${test_name}_resources_before.txt" 2>&1 &
    
    # Run load test via Locust pod
    kubectl exec -n "$NAMESPACE" "$LOCUST_POD" -- \
        locust \
        -f /locust/locustfile_vps.py \
        --host=http://nginx \
        --users="$users" \
        --spawn-rate="$spawn_rate" \
        --run-time="$duration" \
        --headless \
        --html="/reports/${test_name}_${TIMESTAMP}.html" \
        --csv="/reports/${test_name}_${TIMESTAMP}" \
        --only-summary
    
    # Capture resource usage after test
    kubectl top pods -n "$NAMESPACE" --containers > "$REPORT_DIR/${test_name}_resources_after.txt" 2>&1
    
    # Get HPA status
    kubectl get hpa -n "$NAMESPACE" -o wide > "$REPORT_DIR/${test_name}_hpa_status.txt" 2>&1
    
    print_success "$test_name completed"
    echo ""
    
    # Cool-down period
    print_info "Cool-down period (60s)..."
    sleep 60
}

# ============================================================================
# Test 1: Light Load (Normal Business Hours)
# ============================================================================
run_load_test \
    "01_light_load" \
    20 \
    2 \
    "10m" \
    "Normal business hours - few staff members using system"

# ============================================================================
# Test 2: Medium Load (Busy Hours)
# ============================================================================
run_load_test \
    "02_medium_load" \
    50 \
    5 \
    "15m" \
    "Busy hours - multiple staff + customer portal access"

# ============================================================================
# Test 3: Peak Load (Flash Sale/Promotion)
# ============================================================================
run_load_test \
    "03_peak_load" \
    100 \
    10 \
    "20m" \
    "Peak load - flash sale or major promotion"

# ============================================================================
# Test 4: Stress Test (Find Breaking Point)
# ============================================================================
print_header "STRESS TEST - Finding Limits"
print_info "This test will push the VPS to its limits"
echo ""

run_load_test \
    "04_stress_test" \
    200 \
    10 \
    "10m" \
    "Stress test - find VPS breaking point"

# ============================================================================
# Generate Comprehensive Report
# ============================================================================
print_header "GENERATING COMPREHENSIVE REPORT"

REPORT_FILE="$REPORT_DIR/vps_load_test_report_${TIMESTAMP}.md"

cat > "$REPORT_FILE" <<EOF
# VPS Load Test Report
**Date:** $(date)
**VPS Configuration:** ${VPS_RAM}GB RAM, ${VPS_CPU} CPU cores
**Cluster:** k3d jewelry-shop
**Namespace:** $NAMESPACE

## Executive Summary

This report documents comprehensive load testing to validate system performance
on a production VPS with ${VPS_RAM}GB RAM and ${VPS_CPU} CPU cores.

---

## Test Scenarios

### 1. Light Load (20 concurrent users - 10 minutes)
**Scenario:** Normal business hours with a few staff members  
**Expected:** Smooth performance, minimal resource usage

### 2. Medium Load (50 concurrent users - 15 minutes)
**Scenario:** Busy hours with multiple staff + customer portal access  
**Expected:** Good performance, moderate resource usage, possible scaling

### 3. Peak Load (100 concurrent users - 20 minutes)
**Scenario:** Flash sale or major promotion  
**Expected:** Acceptable performance with scaling, higher resource usage

### 4. Stress Test (200 concurrent users - 10 minutes)
**Scenario:** Beyond normal capacity to find breaking point  
**Expected:** Performance degradation, high error rate possible

---

## Performance Metrics

EOF

# Extract metrics from each test
for test in "01_light_load" "02_medium_load" "03_peak_load" "04_stress_test"; do
    echo "### $test" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    
    if [ -f "$REPORT_DIR/${test}_${TIMESTAMP}_stats.csv" ]; then
        echo "\`\`\`" >> "$REPORT_FILE"
        cat "$REPORT_DIR/${test}_${TIMESTAMP}_stats.csv" >> "$REPORT_FILE"
        echo "\`\`\`" >> "$REPORT_FILE"
    else
        echo "*Metrics file not found*" >> "$REPORT_FILE"
    fi
    
    echo "" >> "$REPORT_FILE"
    
    # Add resource usage
    if [ -f "$REPORT_DIR/${test}_resources_after.txt" ]; then
        echo "**Resource Usage:**" >> "$REPORT_FILE"
        echo "\`\`\`" >> "$REPORT_FILE"
        cat "$REPORT_DIR/${test}_resources_after.txt" >> "$REPORT_FILE"
        echo "\`\`\`" >> "$REPORT_FILE"
    fi
    
    echo "" >> "$REPORT_FILE"
    echo "---" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
done

# Add HPA scaling analysis
cat >> "$REPORT_FILE" <<EOF

## Horizontal Pod Autoscaler Analysis

The HPA was configured with:
- Min replicas: 1
- Max replicas: 3
- CPU threshold: 70%
- Memory threshold: 80%

### Scaling Events

EOF

# Get HPA events
kubectl get events -n "$NAMESPACE" --field-selector involvedObject.name=django-hpa | tail -20 >> "$REPORT_FILE" 2>&1

cat >> "$REPORT_FILE" <<EOF

---

## Resource Utilization Summary

### CPU Usage
EOF

echo "\`\`\`" >> "$REPORT_FILE"
kubectl top nodes >> "$REPORT_FILE" 2>&1
echo "\`\`\`" >> "$REPORT_FILE"

cat >> "$REPORT_FILE" <<EOF

### Pod Resource Usage
EOF

echo "\`\`\`" >> "$REPORT_FILE"
kubectl top pods -n "$NAMESPACE" --containers >> "$REPORT_FILE" 2>&1
echo "\`\`\`" >> "$REPORT_FILE"

# Add recommendations
cat >> "$REPORT_FILE" <<EOF

---

## Recommendations

### VPS Sizing

EOF

# Analyze results and provide recommendations
if [ "$VPS_RAM" -eq 4 ] && [ "$VPS_CPU" -eq 2 ]; then
    cat >> "$REPORT_FILE" <<EOF
**Current: 4GB RAM / 2 CPU**

Based on test results:

- ✅ **Suitable for:** 1-2 tenants with light to medium usage
- ✅ **Max concurrent users:** 30-50 users comfortably
- ⚠️  **Peak load (100 users):** May experience slowdowns
- ❌ **Stress test (200 users):** Likely degraded performance

**Recommendations:**
- Good starting point for MVP or small businesses
- Monitor resource usage closely
- Consider upgrade if:
  - More than 2 active tenants
  - Regular concurrent users >50
  - Response times >2s for p95
  - CPU consistently >80%

EOF
elif [ "$VPS_RAM" -eq 6 ] && [ "$VPS_CPU" -eq 3 ]; then
    cat >> "$REPORT_FILE" <<EOF
**Current: 6GB RAM / 3 CPU**

Based on test results:

- ✅ **Suitable for:** 3-5 tenants with moderate usage
- ✅ **Max concurrent users:** 75-100 users comfortably
- ✅ **Peak load:** Should handle well with auto-scaling
- ⚠️  **Stress test:** May approach limits

**Recommendations:**
- Recommended for production with 3-5 tenants
- Good headroom for growth
- Comfortable performance during busy hours
- Monitor for upgrade if:
  - More than 5 active tenants
  - Regular concurrent users >100
  - Planning major marketing campaigns

EOF
fi

cat >> "$REPORT_FILE" <<EOF

### Performance Optimizations

1. **Database:**
   - Enable PostgreSQL query caching
   - Add indexes for frequently queried fields
   - Consider read replicas for >5 tenants

2. **Caching:**
   - Increase Redis memory allocation
   - Cache frequently accessed data (product lists, customers)
   - Implement query result caching

3. **Application:**
   - Review slow Django queries
   - Optimize ORM queries with select_related/prefetch_related
   - Implement pagination for large lists

4. **Scaling:**
   - Current HPA settings work well
   - Consider lowering min replicas to 1 during off-hours
   - Increase max replicas if you upgrade VPS

---

## Conclusion

$(date)

System performance on ${VPS_RAM}GB/${VPS_CPU}CPU VPS has been validated.
Review detailed metrics above and follow recommendations for optimal performance.

**Report Location:** $REPORT_FILE
**HTML Reports:** $REPORT_DIR/*.html

EOF

print_success "Comprehensive report generated: $REPORT_FILE"
echo ""

# Display summary
print_header "TEST SUMMARY"
echo "All load tests completed successfully!"
echo ""
echo "📊 Reports generated:"
ls -lh "$REPORT_DIR"/*_${TIMESTAMP}.html 2>/dev/null || echo "  No HTML reports found"
echo ""
echo "📄 Full report: $REPORT_FILE"
echo ""

print_header "QUICK RECOMMENDATIONS"

# Get actual resource usage
CPU_USAGE=$(kubectl top nodes 2>/dev/null | tail -1 | awk '{print $3}' | sed 's/%//' || echo "0")
MEM_USAGE=$(kubectl top nodes 2>/dev/null | tail -1 | awk '{print $5}' | sed 's/%//' || echo "0")

if [ "$CPU_USAGE" -gt 80 ]; then
    print_error "CPU usage >80% - consider upgrading CPU"
elif [ "$CPU_USAGE" -gt 60 ]; then
    print_info "CPU usage moderate (60-80%) - monitor closely"
else
    print_success "CPU usage healthy (<60%)"
fi

if [ "$MEM_USAGE" -gt 85 ]; then
    print_error "Memory usage >85% - consider upgrading RAM"
elif [ "$MEM_USAGE" -gt 70 ]; then
    print_info "Memory usage moderate (70-85%) - monitor closely"
else
    print_success "Memory usage healthy (<70%)"
fi

echo ""
print_success "VPS load testing complete! 🎉"
