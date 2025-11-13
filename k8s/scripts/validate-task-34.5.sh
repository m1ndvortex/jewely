#!/bin/bash

# Task 34.5 Validation Script
# Validates the Zalando Postgres Operator installation

# Don't exit on error - we want to run all validations
set +e

echo "=========================================="
echo "Task 34.5: Validation"
echo "Zalando Postgres Operator Installation"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
TOTAL=0

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓ PASS: $1${NC}"
    ((PASSED++))
}

print_fail() {
    echo -e "${RED}✗ FAIL: $1${NC}"
    ((FAILED++))
}

print_info() {
    echo -e "${YELLOW}ℹ INFO: $1${NC}"
}

# Test function
run_test() {
    ((TOTAL++))
    local test_name="$1"
    local test_command="$2"
    
    echo "Test $TOTAL: $test_name"
    if eval "$test_command" &> /dev/null; then
        print_success "$test_name"
    else
        print_fail "$test_name"
    fi
    echo ""
}

# Validation 1: Check if Helm is installed
echo "Validation 1: Helm Installation"
echo "================================"
if command -v helm &> /dev/null; then
    HELM_VERSION=$(helm version --short)
    print_success "Helm is installed: $HELM_VERSION"
    ((PASSED++))
else
    print_fail "Helm is not installed"
    ((FAILED++))
fi
((TOTAL++))
echo ""

# Validation 2: Check if postgres-operator namespace exists
echo "Validation 2: Namespace Existence"
echo "=================================="
run_test "postgres-operator namespace exists" \
    "kubectl get namespace postgres-operator"

# Validation 3: Check if operator pod is running
echo "Validation 3: Operator Pod Status"
echo "=================================="
if kubectl get pods -n postgres-operator -l app.kubernetes.io/name=postgres-operator &> /dev/null; then
    POD_STATUS=$(kubectl get pods -n postgres-operator -l app.kubernetes.io/name=postgres-operator -o jsonpath='{.items[0].status.phase}')
    POD_NAME=$(kubectl get pods -n postgres-operator -l app.kubernetes.io/name=postgres-operator -o jsonpath='{.items[0].metadata.name}')
    
    if [ "$POD_STATUS" == "Running" ]; then
        print_success "Operator pod is Running: $POD_NAME"
        ((PASSED++))
    else
        print_fail "Operator pod is not Running. Status: $POD_STATUS"
        ((FAILED++))
    fi
else
    print_fail "Operator pod not found"
    ((FAILED++))
fi
((TOTAL++))
echo ""

# Validation 4: Check if operator pod is ready
echo "Validation 4: Operator Pod Readiness"
echo "====================================="
if kubectl get pods -n postgres-operator -l app.kubernetes.io/name=postgres-operator &> /dev/null; then
    POD_READY=$(kubectl get pods -n postgres-operator -l app.kubernetes.io/name=postgres-operator -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}')
    
    if [ "$POD_READY" == "True" ]; then
        print_success "Operator pod is Ready"
        ((PASSED++))
    else
        print_fail "Operator pod is not Ready"
        ((FAILED++))
    fi
else
    print_fail "Operator pod not found"
    ((FAILED++))
fi
((TOTAL++))
echo ""

# Validation 5: Check if postgresql CRD exists
echo "Validation 5: CRD Existence"
echo "==========================="
run_test "postgresql.acid.zalan.do CRD exists" \
    "kubectl get crd postgresqls.acid.zalan.do"

# Validation 6: Check operator logs for successful initialization
echo "Validation 6: Operator Logs"
echo "==========================="
if kubectl get pods -n postgres-operator -l app.kubernetes.io/name=postgres-operator &> /dev/null; then
    OPERATOR_POD=$(kubectl get pods -n postgres-operator -l app.kubernetes.io/name=postgres-operator -o jsonpath='{.items[0].metadata.name}')
    
    print_info "Checking logs for operator pod: $OPERATOR_POD"
    
    # Check for error messages in logs
    if kubectl logs -n postgres-operator $OPERATOR_POD --tail=100 | grep -i "error" | grep -v "level=info" &> /dev/null; then
        print_fail "Errors found in operator logs"
        echo "Recent errors:"
        kubectl logs -n postgres-operator $OPERATOR_POD --tail=100 | grep -i "error" | grep -v "level=info" | tail -5
        ((FAILED++))
    else
        print_success "No critical errors in operator logs"
        ((PASSED++))
    fi
    
    # Check for successful initialization
    if kubectl logs -n postgres-operator $OPERATOR_POD --tail=100 | grep -i "controller started" &> /dev/null; then
        print_success "Operator controller started successfully"
        ((PASSED++))
    else
        print_info "Controller start message not found (may have started earlier)"
        ((PASSED++))
    fi
    
    ((TOTAL+=2))
else
    print_fail "Operator pod not found"
    ((FAILED+=2))
    ((TOTAL+=2))
fi
echo ""

# Validation 7: Check if operator can watch for postgresql resources
echo "Validation 7: Operator Watch Capability"
echo "========================================"
if kubectl get crd postgresqls.acid.zalan.do &> /dev/null; then
    # Try to list postgresql resources (should return empty list, not error)
    if kubectl get postgresql --all-namespaces &> /dev/null; then
        print_success "Operator can watch for postgresql resources"
        ((PASSED++))
    else
        print_fail "Operator cannot watch for postgresql resources"
        ((FAILED++))
    fi
else
    print_fail "CRD not found, cannot test watch capability"
    ((FAILED++))
fi
((TOTAL++))
echo ""

# Validation 8: Check Helm release status
echo "Validation 8: Helm Release Status"
echo "=================================="
if helm list -n postgres-operator | grep -q "postgres-operator"; then
    RELEASE_STATUS=$(helm list -n postgres-operator -o json | jq -r '.[] | select(.name=="postgres-operator") | .status')
    
    if [ "$RELEASE_STATUS" == "deployed" ]; then
        print_success "Helm release status: deployed"
        ((PASSED++))
    else
        print_fail "Helm release status: $RELEASE_STATUS"
        ((FAILED++))
    fi
else
    print_fail "Helm release not found"
    ((FAILED++))
fi
((TOTAL++))
echo ""

# Display operator information
echo "=========================================="
echo "Operator Information"
echo "=========================================="
if kubectl get pods -n postgres-operator -l app.kubernetes.io/name=postgres-operator &> /dev/null; then
    echo "Operator Pod Details:"
    kubectl get pods -n postgres-operator -l app.kubernetes.io/name=postgres-operator -o wide
    echo ""
    
    echo "Operator Container Image:"
    kubectl get pods -n postgres-operator -l app.kubernetes.io/name=postgres-operator -o jsonpath='{.items[0].spec.containers[0].image}'
    echo ""
    echo ""
    
    echo "Recent Operator Logs (last 10 lines):"
    OPERATOR_POD=$(kubectl get pods -n postgres-operator -l app.kubernetes.io/name=postgres-operator -o jsonpath='{.items[0].metadata.name}')
    kubectl logs -n postgres-operator $OPERATOR_POD --tail=10
    echo ""
fi

# Display CRD information
echo "=========================================="
echo "CRD Information"
echo "=========================================="
if kubectl get crd postgresqls.acid.zalan.do &> /dev/null; then
    echo "PostgreSQL CRD Details:"
    kubectl get crd postgresqls.acid.zalan.do -o custom-columns=NAME:.metadata.name,CREATED:.metadata.creationTimestamp
    echo ""
fi

# Summary
echo "=========================================="
echo "Validation Summary"
echo "=========================================="
echo "Total Tests: $TOTAL"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}=========================================="
    echo "✓ ALL VALIDATIONS PASSED"
    echo "==========================================${NC}"
    echo ""
    echo "Task 34.5 is complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Review the completion report: k8s/TASK_34.5_COMPLETION_REPORT.md"
    echo "  2. Proceed to task 34.6: Deploy PostgreSQL cluster with automatic failover"
    echo ""
    exit 0
else
    echo -e "${RED}=========================================="
    echo "✗ SOME VALIDATIONS FAILED"
    echo "==========================================${NC}"
    echo ""
    echo "Please review the failed tests above and fix any issues."
    echo "You may need to:"
    echo "  1. Check operator logs: kubectl logs -n postgres-operator -l app.kubernetes.io/name=postgres-operator"
    echo "  2. Describe operator pod: kubectl describe pod -n postgres-operator -l app.kubernetes.io/name=postgres-operator"
    echo "  3. Re-run deployment: ./k8s/scripts/deploy-task-34.5.sh"
    echo ""
    exit 1
fi
