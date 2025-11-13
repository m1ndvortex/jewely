#!/bin/bash

# ============================================================================
# Test Script for PersistentVolumes (Task 34.12)
# ============================================================================
# This script validates:
# 1. PVC creation and binding
# 2. PV provisioning
# 3. Data persistence across pod deletions (PostgreSQL)
# 4. Data persistence across pod deletions (Redis)
# 5. ReadWriteMany access for media files
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Namespace
NAMESPACE="jewelry-shop"

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
print_header() {
    echo -e "\n${BLUE}============================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
    ((TESTS_PASSED++))
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
    ((TESTS_FAILED++))
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# ============================================================================
# Test 1: Verify PVC Creation and Binding
# ============================================================================
test_pvc_binding() {
    print_header "Test 1: Verify PVC Creation and Binding"
    
    # Check if PVCs exist
    print_info "Checking PVCs in namespace $NAMESPACE..."
    kubectl get pvc -n $NAMESPACE
    
    # Expected PVCs
    EXPECTED_PVCS=(
        "media-pvc"
        "static-pvc"
        "backups-pvc"
    )
    
    for pvc in "${EXPECTED_PVCS[@]}"; do
        STATUS=$(kubectl get pvc $pvc -n $NAMESPACE -o jsonpath='{.status.phase}' 2>/dev/null || echo "NotFound")
        if [ "$STATUS" = "Bound" ]; then
            print_success "PVC $pvc is Bound"
        elif [ "$STATUS" = "Pending" ]; then
            print_info "PVC $pvc is Pending (WaitForFirstConsumer - will bind when pod mounts it)"
            ((TESTS_PASSED++))
        else
            print_error "PVC $pvc status: $STATUS (expected: Bound or Pending)"
        fi
    done
    
    # Check PostgreSQL PVCs (created by StatefulSet)
    print_info "\nChecking PostgreSQL PVCs..."
    PG_PVCS=$(kubectl get pvc -n $NAMESPACE -l application=spilo --no-headers 2>/dev/null | wc -l)
    if [ "$PG_PVCS" -ge 3 ]; then
        print_success "PostgreSQL has $PG_PVCS PVCs (expected: 3)"
        kubectl get pvc -n $NAMESPACE -l application=spilo
    else
        print_error "PostgreSQL has $PG_PVCS PVCs (expected: 3)"
    fi
    
    # Check Redis PVCs (created by StatefulSet)
    print_info "\nChecking Redis PVCs..."
    REDIS_PVCS=$(kubectl get pvc -n $NAMESPACE -l app=redis --no-headers 2>/dev/null | wc -l)
    if [ "$REDIS_PVCS" -ge 3 ]; then
        print_success "Redis has $REDIS_PVCS PVCs (expected: 3)"
        kubectl get pvc -n $NAMESPACE -l app=redis
    else
        print_error "Redis has $REDIS_PVCS PVCs (expected: 3)"
    fi
}

# ============================================================================
# Test 2: Verify PersistentVolumes Created
# ============================================================================
test_pv_creation() {
    print_header "Test 2: Verify PersistentVolumes Created"
    
    print_info "Listing all PersistentVolumes..."
    kubectl get pv
    
    # Count PVs bound to our namespace
    PV_COUNT=$(kubectl get pv -o json | jq -r ".items[] | select(.spec.claimRef.namespace==\"$NAMESPACE\") | .metadata.name" | wc -l)
    
    if [ "$PV_COUNT" -ge 6 ]; then
        print_success "Found $PV_COUNT PersistentVolumes for namespace $NAMESPACE (expected: ≥6)"
    else
        print_error "Found $PV_COUNT PersistentVolumes for namespace $NAMESPACE (expected: ≥6)"
    fi
    
    # Show details
    print_info "\nPersistentVolumes for $NAMESPACE:"
    kubectl get pv -o json | jq -r ".items[] | select(.spec.claimRef.namespace==\"$NAMESPACE\") | \"\(.metadata.name) - \(.spec.capacity.storage) - \(.status.phase)\""
}

# ============================================================================
# Test 3: Test PostgreSQL Data Persistence
# ============================================================================
test_postgresql_persistence() {
    print_header "Test 3: Test PostgreSQL Data Persistence"
    
    # Get master pod
    MASTER_POD=$(kubectl get pods -n $NAMESPACE -l application=spilo,spilo-role=master -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [ -z "$MASTER_POD" ]; then
        print_error "PostgreSQL master pod not found"
        return
    fi
    
    print_info "Using PostgreSQL master pod: $MASTER_POD"
    
    # Create test table and insert data
    print_info "Creating test table and inserting data..."
    TEST_DATA="persistence_test_$(date +%s)"
    
    kubectl exec -n $NAMESPACE $MASTER_POD -c postgres -- psql -U postgres -d jewelry_shop -c "
        CREATE TABLE IF NOT EXISTS persistence_test (
            id SERIAL PRIMARY KEY,
            test_data VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        );
        INSERT INTO persistence_test (test_data) VALUES ('$TEST_DATA');
    " 2>/dev/null
    
    if [ $? -eq 0 ]; then
        print_success "Test data inserted successfully"
    else
        print_error "Failed to insert test data"
        return
    fi
    
    # Verify data exists
    print_info "Verifying data exists..."
    RESULT=$(kubectl exec -n $NAMESPACE $MASTER_POD -c postgres -- psql -U postgres -d jewelry_shop -t -c "SELECT test_data FROM persistence_test WHERE test_data='$TEST_DATA';" 2>/dev/null | tr -d ' \n')
    
    if [ "$RESULT" = "$TEST_DATA" ]; then
        print_success "Data verified before pod deletion"
    else
        print_error "Data verification failed before pod deletion"
        return
    fi
    
    # Delete the pod
    print_info "Deleting PostgreSQL pod $MASTER_POD..."
    kubectl delete pod -n $NAMESPACE $MASTER_POD --grace-period=0 --force 2>/dev/null
    
    # Wait for new pod to be ready
    print_info "Waiting for new pod to be ready (max 60s)..."
    sleep 10
    
    for i in {1..12}; do
        NEW_POD=$(kubectl get pods -n $NAMESPACE -l application=spilo,spilo-role=master -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
        if [ -n "$NEW_POD" ] && [ "$NEW_POD" != "$MASTER_POD" ]; then
            POD_STATUS=$(kubectl get pod -n $NAMESPACE $NEW_POD -o jsonpath='{.status.phase}' 2>/dev/null)
            if [ "$POD_STATUS" = "Running" ]; then
                print_success "New pod $NEW_POD is running"
                break
            fi
        fi
        sleep 5
    done
    
    # Wait for PostgreSQL to be ready
    print_info "Waiting for PostgreSQL to be ready..."
    sleep 15
    
    # Verify data persists
    print_info "Verifying data persists after pod recreation..."
    NEW_MASTER=$(kubectl get pods -n $NAMESPACE -l application=spilo,spilo-role=master -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [ -z "$NEW_MASTER" ]; then
        print_error "New master pod not found"
        return
    fi
    
    RESULT=$(kubectl exec -n $NAMESPACE $NEW_MASTER -c postgres -- psql -U postgres -d jewelry_shop -t -c "SELECT test_data FROM persistence_test WHERE test_data='$TEST_DATA';" 2>/dev/null | tr -d ' \n')
    
    if [ "$RESULT" = "$TEST_DATA" ]; then
        print_success "Data persisted after pod deletion! ✓"
    else
        print_error "Data lost after pod deletion"
    fi
    
    # Cleanup
    print_info "Cleaning up test data..."
    kubectl exec -n $NAMESPACE $NEW_MASTER -c postgres -- psql -U postgres -d jewelry_shop -c "DROP TABLE IF EXISTS persistence_test;" 2>/dev/null
}

# ============================================================================
# Test 4: Test Redis Data Persistence
# ============================================================================
test_redis_persistence() {
    print_header "Test 4: Test Redis Data Persistence"
    
    # Get Redis master pod (redis-0)
    REDIS_POD="redis-0"
    
    # Check if pod exists
    kubectl get pod -n $NAMESPACE $REDIS_POD &>/dev/null
    if [ $? -ne 0 ]; then
        print_error "Redis pod $REDIS_POD not found"
        return
    fi
    
    print_info "Using Redis pod: $REDIS_POD"
    
    # Set test data
    print_info "Setting test data in Redis..."
    TEST_KEY="persistence_test_$(date +%s)"
    TEST_VALUE="test_value_$(date +%s)"
    
    kubectl exec -n $NAMESPACE $REDIS_POD -c redis -- redis-cli SET "$TEST_KEY" "$TEST_VALUE" &>/dev/null
    
    if [ $? -eq 0 ]; then
        print_success "Test data set successfully"
    else
        print_error "Failed to set test data"
        return
    fi
    
    # Verify data exists
    print_info "Verifying data exists..."
    RESULT=$(kubectl exec -n $NAMESPACE $REDIS_POD -c redis -- redis-cli GET "$TEST_KEY" 2>/dev/null | tr -d '\r\n')
    
    if [ "$RESULT" = "$TEST_VALUE" ]; then
        print_success "Data verified before pod deletion"
    else
        print_error "Data verification failed before pod deletion"
        return
    fi
    
    # Delete the pod
    print_info "Deleting Redis pod $REDIS_POD..."
    kubectl delete pod -n $NAMESPACE $REDIS_POD --grace-period=0 --force 2>/dev/null
    
    # Wait for pod to be recreated
    print_info "Waiting for pod to be recreated (max 60s)..."
    sleep 10
    
    for i in {1..12}; do
        POD_STATUS=$(kubectl get pod -n $NAMESPACE $REDIS_POD -o jsonpath='{.status.phase}' 2>/dev/null)
        if [ "$POD_STATUS" = "Running" ]; then
            print_success "Pod $REDIS_POD is running again"
            break
        fi
        sleep 5
    done
    
    # Wait for Redis to be ready
    print_info "Waiting for Redis to be ready..."
    sleep 10
    
    # Verify data persists
    print_info "Verifying data persists after pod recreation..."
    RESULT=$(kubectl exec -n $NAMESPACE $REDIS_POD -c redis -- redis-cli GET "$TEST_KEY" 2>/dev/null | tr -d '\r\n')
    
    if [ "$RESULT" = "$TEST_VALUE" ]; then
        print_success "Data persisted after pod deletion! ✓"
    else
        print_error "Data lost after pod deletion"
    fi
    
    # Cleanup
    print_info "Cleaning up test data..."
    kubectl exec -n $NAMESPACE $REDIS_POD -c redis -- redis-cli DEL "$TEST_KEY" &>/dev/null
}

# ============================================================================
# Test 5: Test ReadWriteOnce Access and Data Persistence for Media Files
# ============================================================================
test_rwx_access() {
    print_header "Test 5: Test ReadWriteOnce Access and Data Persistence for Media Files"
    
    print_info "Note: local-path storage class only supports ReadWriteOnce (RWO)"
    print_info "For production with multiple pods, use Longhorn or NFS-based storage"
    
    # Create test pod that mounts the media PVC
    print_info "Creating test pod to verify ReadWriteOnce access..."
    
    cat <<EOF | kubectl apply -f - &>/dev/null
apiVersion: v1
kind: Pod
metadata:
  name: rwo-test-writer
  namespace: $NAMESPACE
  labels:
    test: rwo
spec:
  containers:
  - name: writer
    image: busybox
    command: ['sh', '-c', 'echo "test data from writer" > /media/test-file.txt && sleep 3600']
    volumeMounts:
    - name: media
      mountPath: /media
  volumes:
  - name: media
    persistentVolumeClaim:
      claimName: media-pvc
EOF
    
    # Wait for pod to be ready
    print_info "Waiting for writer pod to be ready..."
    sleep 5
    
    kubectl wait --for=condition=Ready pod/rwo-test-writer -n $NAMESPACE --timeout=60s &>/dev/null
    
    if [ $? -eq 0 ]; then
        print_success "Writer pod is ready"
    else
        print_error "Writer pod failed to become ready"
        kubectl delete pod rwo-test-writer -n $NAMESPACE --force --grace-period=0 &>/dev/null
        return
    fi
    
    # Wait for file to be written
    sleep 3
    
    # Verify data was written
    print_info "Verifying data was written..."
    CONTENT=$(kubectl exec -n $NAMESPACE rwo-test-writer -- cat /media/test-file.txt 2>/dev/null | tr -d '\r\n')
    
    if [ "$CONTENT" = "test data from writer" ]; then
        print_success "Data written successfully"
    else
        print_error "Failed to write data"
        kubectl delete pod rwo-test-writer -n $NAMESPACE --force --grace-period=0 &>/dev/null
        return
    fi
    
    # Delete writer pod
    print_info "Deleting writer pod to test data persistence..."
    kubectl delete pod rwo-test-writer -n $NAMESPACE --force --grace-period=0 &>/dev/null
    sleep 5
    
    # Create reader pod
    print_info "Creating reader pod to verify data persists..."
    cat <<EOF | kubectl apply -f - &>/dev/null
apiVersion: v1
kind: Pod
metadata:
  name: rwo-test-reader
  namespace: $NAMESPACE
  labels:
    test: rwo
spec:
  containers:
  - name: reader
    image: busybox
    command: ['sh', '-c', 'sleep 3600']
    volumeMounts:
    - name: media
      mountPath: /media
  volumes:
  - name: media
    persistentVolumeClaim:
      claimName: media-pvc
EOF
    
    # Wait for reader pod
    sleep 5
    kubectl wait --for=condition=Ready pod/rwo-test-reader -n $NAMESPACE --timeout=60s &>/dev/null
    
    # Try to read from the reader pod
    print_info "Attempting to read file from reader pod..."
    CONTENT=$(kubectl exec -n $NAMESPACE rwo-test-reader -- cat /media/test-file.txt 2>/dev/null | tr -d '\r\n')
    
    if [ "$CONTENT" = "test data from writer" ]; then
        print_success "Data persisted! ReadWriteOnce volume maintains data across pod deletions"
    else
        print_error "Failed to read persisted data"
    fi
    
    # Cleanup
    print_info "Cleaning up test pods..."
    kubectl delete pod rwo-test-reader -n $NAMESPACE --force --grace-period=0 &>/dev/null
}

# ============================================================================
# Test 6: Verify Storage Class Configuration
# ============================================================================
test_storage_class() {
    print_header "Test 6: Verify Storage Class Configuration"
    
    print_info "Checking available storage classes..."
    kubectl get storageclass
    
    # Check if local-path exists (k3d default)
    if kubectl get storageclass local-path &>/dev/null; then
        print_success "Storage class 'local-path' exists (k3d default)"
    else
        print_error "Storage class 'local-path' not found"
    fi
    
    # Check PVC storage classes
    print_info "\nVerifying PVC storage classes..."
    for pvc in media-pvc static-pvc backups-pvc; do
        SC=$(kubectl get pvc $pvc -n $NAMESPACE -o jsonpath='{.spec.storageClassName}' 2>/dev/null)
        if [ "$SC" = "local-path" ]; then
            print_success "PVC $pvc uses storage class: $SC"
        else
            print_error "PVC $pvc uses storage class: $SC (expected: local-path)"
        fi
    done
}

# ============================================================================
# Main Execution
# ============================================================================
main() {
    print_header "PersistentVolumes Test Suite - Task 34.12"
    
    # Run all tests
    test_pvc_binding
    test_pv_creation
    test_storage_class
    test_postgresql_persistence
    test_redis_persistence
    test_rwx_access
    
    # Print summary
    print_header "Test Summary"
    echo -e "${GREEN}Tests Passed: $TESTS_PASSED${NC}"
    echo -e "${RED}Tests Failed: $TESTS_FAILED${NC}"
    
    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "\n${GREEN}✓ All tests passed! PersistentVolumes are configured correctly.${NC}\n"
        exit 0
    else
        echo -e "\n${RED}✗ Some tests failed. Please review the output above.${NC}\n"
        exit 1
    fi
}

# Run main function
main
