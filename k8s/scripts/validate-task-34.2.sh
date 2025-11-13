#!/bin/bash

# ============================================================================
# Validation Script for Task 34.2
# ============================================================================
# This script validates that all resources for task 34.2 are created correctly:
# - Namespace exists
# - ConfigMaps are created
# - Secrets are created and base64 encoded
# - ResourceQuotas are applied
# - LimitRanges are applied
# ============================================================================

# Note: We don't use 'set -e' here because we want to continue testing
# even if some tests fail, and report all results at the end

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0

# Function to print section headers
print_header() {
    echo ""
    echo -e "${BLUE}============================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================================${NC}"
    echo ""
}

# Function to print test results
print_test() {
    local test_name="$1"
    local result="$2"
    local details="$3"
    
    if [ "$result" = "PASS" ]; then
        echo -e "${GREEN}✓${NC} $test_name"
        [ -n "$details" ] && echo -e "  ${details}"
        ((PASSED++))
    else
        echo -e "${RED}✗${NC} $test_name"
        [ -n "$details" ] && echo -e "  ${RED}${details}${NC}"
        ((FAILED++))
    fi
}

# Function to check if kubectl is available
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}Error: kubectl is not installed or not in PATH${NC}"
        exit 1
    fi
}

# Function to check if cluster is accessible
check_cluster() {
    if ! kubectl cluster-info &> /dev/null; then
        echo -e "${RED}Error: Cannot access Kubernetes cluster${NC}"
        echo -e "${YELLOW}Hint: Make sure k3d cluster is running: k3d cluster list${NC}"
        exit 1
    fi
}

print_header "Task 34.2 Validation: Kubernetes Namespace and Base Resources"

echo "Starting validation checks..."
echo ""

check_kubectl
check_cluster

# ============================================================================
# Test 1: Verify namespace exists
# ============================================================================
print_header "Test 1: Namespace Verification"

if kubectl get namespace jewelry-shop &> /dev/null; then
    NAMESPACE_STATUS=$(kubectl get namespace jewelry-shop -o jsonpath='{.status.phase}')
    if [ "$NAMESPACE_STATUS" = "Active" ]; then
        print_test "Namespace 'jewelry-shop' exists and is Active" "PASS" "Status: $NAMESPACE_STATUS"
    else
        print_test "Namespace 'jewelry-shop' exists but not Active" "FAIL" "Status: $NAMESPACE_STATUS"
    fi
else
    print_test "Namespace 'jewelry-shop' exists" "FAIL" "Namespace not found"
fi

# Check namespace labels
NAMESPACE_LABELS=$(kubectl get namespace jewelry-shop -o jsonpath='{.metadata.labels}' 2>/dev/null || echo "{}")
if [ -n "$NAMESPACE_LABELS" ] && echo "$NAMESPACE_LABELS" | grep -q "jewelry-shop"; then
    print_test "Namespace has correct labels" "PASS"
else
    print_test "Namespace has correct labels" "FAIL" "Labels missing or incorrect"
fi

# ============================================================================
# Test 2: Verify ConfigMaps
# ============================================================================
print_header "Test 2: ConfigMap Verification"

# Check app-config ConfigMap
if kubectl get configmap app-config -n jewelry-shop &> /dev/null; then
    print_test "ConfigMap 'app-config' exists" "PASS"
    
    # Check for key configuration values
    DJANGO_SETTINGS=$(kubectl get configmap app-config -n jewelry-shop -o jsonpath='{.data.DJANGO_SETTINGS_MODULE}' 2>/dev/null)
    if [ "$DJANGO_SETTINGS" = "config.settings.production" ]; then
        print_test "ConfigMap contains DJANGO_SETTINGS_MODULE" "PASS" "Value: $DJANGO_SETTINGS"
    else
        print_test "ConfigMap contains DJANGO_SETTINGS_MODULE" "FAIL" "Value: $DJANGO_SETTINGS"
    fi
    
    POSTGRES_HOST=$(kubectl get configmap app-config -n jewelry-shop -o jsonpath='{.data.POSTGRES_HOST}' 2>/dev/null)
    if [ -n "$POSTGRES_HOST" ]; then
        print_test "ConfigMap contains POSTGRES_HOST" "PASS" "Value: $POSTGRES_HOST"
    else
        print_test "ConfigMap contains POSTGRES_HOST" "FAIL" "Value not found"
    fi
    
    REDIS_HOST=$(kubectl get configmap app-config -n jewelry-shop -o jsonpath='{.data.REDIS_HOST}' 2>/dev/null)
    if [ -n "$REDIS_HOST" ]; then
        print_test "ConfigMap contains REDIS_HOST" "PASS" "Value: $REDIS_HOST"
    else
        print_test "ConfigMap contains REDIS_HOST" "FAIL" "Value not found"
    fi
else
    print_test "ConfigMap 'app-config' exists" "FAIL" "ConfigMap not found"
fi

# Check nginx-config ConfigMap
if kubectl get configmap nginx-config -n jewelry-shop &> /dev/null; then
    print_test "ConfigMap 'nginx-config' exists" "PASS"
else
    print_test "ConfigMap 'nginx-config' exists" "FAIL" "ConfigMap not found"
fi

# ============================================================================
# Test 3: Verify Secrets
# ============================================================================
print_header "Test 3: Secret Verification"

# Check app-secrets Secret
if kubectl get secret app-secrets -n jewelry-shop &> /dev/null; then
    print_test "Secret 'app-secrets' exists" "PASS"
    
    # Verify secrets are base64 encoded and not readable in plain text
    SECRET_TYPE=$(kubectl get secret app-secrets -n jewelry-shop -o jsonpath='{.type}')
    if [ "$SECRET_TYPE" = "Opaque" ]; then
        print_test "Secret type is Opaque" "PASS" "Type: $SECRET_TYPE"
    else
        print_test "Secret type is Opaque" "FAIL" "Type: $SECRET_TYPE"
    fi
    
    # Check for key secret values (should be base64 encoded)
    DJANGO_SECRET=$(kubectl get secret app-secrets -n jewelry-shop -o jsonpath='{.data.DJANGO_SECRET_KEY}' 2>/dev/null)
    if [ -n "$DJANGO_SECRET" ]; then
        # Verify it's base64 encoded (should not contain spaces or special chars typical of plain text)
        if echo "$DJANGO_SECRET" | base64 -d &> /dev/null; then
            print_test "Secret DJANGO_SECRET_KEY is base64 encoded" "PASS" "✓ Properly encoded"
        else
            print_test "Secret DJANGO_SECRET_KEY is base64 encoded" "FAIL" "Not valid base64"
        fi
    else
        print_test "Secret contains DJANGO_SECRET_KEY" "FAIL" "Key not found"
    fi
    
    DB_PASSWORD=$(kubectl get secret app-secrets -n jewelry-shop -o jsonpath='{.data.APP_DB_PASSWORD}' 2>/dev/null)
    if [ -n "$DB_PASSWORD" ]; then
        if echo "$DB_PASSWORD" | base64 -d &> /dev/null; then
            print_test "Secret APP_DB_PASSWORD is base64 encoded" "PASS" "✓ Properly encoded"
        else
            print_test "Secret APP_DB_PASSWORD is base64 encoded" "FAIL" "Not valid base64"
        fi
    else
        print_test "Secret contains APP_DB_PASSWORD" "FAIL" "Key not found"
    fi
    
    # Verify secrets are NOT readable in plain text
    SECRET_DATA=$(kubectl get secret app-secrets -n jewelry-shop -o yaml 2>/dev/null | grep "DJANGO_SECRET_KEY:")
    if echo "$SECRET_DATA" | grep -qv "django-insecure"; then
        print_test "Secrets are not readable in plain text" "PASS" "✓ Secrets are encoded"
    else
        print_test "Secrets are not readable in plain text" "FAIL" "Plain text detected"
    fi
else
    print_test "Secret 'app-secrets' exists" "FAIL" "Secret not found"
fi

# Check postgres-secrets Secret
if kubectl get secret postgres-secrets -n jewelry-shop &> /dev/null; then
    print_test "Secret 'postgres-secrets' exists" "PASS"
else
    print_test "Secret 'postgres-secrets' exists" "FAIL" "Secret not found"
fi

# Check redis-secrets Secret
if kubectl get secret redis-secrets -n jewelry-shop &> /dev/null; then
    print_test "Secret 'redis-secrets' exists" "PASS"
else
    print_test "Secret 'redis-secrets' exists" "FAIL" "Secret not found"
fi

# ============================================================================
# Test 4: Verify ResourceQuotas
# ============================================================================
print_header "Test 4: ResourceQuota Verification"

# Check main ResourceQuota
if kubectl get resourcequota jewelry-shop-quota -n jewelry-shop &> /dev/null; then
    print_test "ResourceQuota 'jewelry-shop-quota' exists" "PASS"
    
    # Check CPU quota
    CPU_HARD=$(kubectl get resourcequota jewelry-shop-quota -n jewelry-shop -o jsonpath='{.spec.hard.requests\.cpu}' 2>/dev/null)
    if [ -n "$CPU_HARD" ]; then
        print_test "ResourceQuota has CPU limits" "PASS" "CPU requests: $CPU_HARD"
    else
        print_test "ResourceQuota has CPU limits" "FAIL" "CPU limits not found"
    fi
    
    # Check Memory quota
    MEMORY_HARD=$(kubectl get resourcequota jewelry-shop-quota -n jewelry-shop -o jsonpath='{.spec.hard.requests\.memory}' 2>/dev/null)
    if [ -n "$MEMORY_HARD" ]; then
        print_test "ResourceQuota has Memory limits" "PASS" "Memory requests: $MEMORY_HARD"
    else
        print_test "ResourceQuota has Memory limits" "FAIL" "Memory limits not found"
    fi
    
    # Check Pod quota
    POD_HARD=$(kubectl get resourcequota jewelry-shop-quota -n jewelry-shop -o jsonpath='{.spec.hard.pods}' 2>/dev/null)
    if [ -n "$POD_HARD" ]; then
        print_test "ResourceQuota has Pod limits" "PASS" "Max pods: $POD_HARD"
    else
        print_test "ResourceQuota has Pod limits" "FAIL" "Pod limits not found"
    fi
else
    print_test "ResourceQuota 'jewelry-shop-quota' exists" "FAIL" "ResourceQuota not found"
fi

# Check priority ResourceQuota
if kubectl get resourcequota jewelry-shop-priority-quota -n jewelry-shop &> /dev/null; then
    print_test "ResourceQuota 'jewelry-shop-priority-quota' exists" "PASS"
else
    print_test "ResourceQuota 'jewelry-shop-priority-quota' exists" "FAIL" "ResourceQuota not found"
fi

# ============================================================================
# Test 5: Verify LimitRanges
# ============================================================================
print_header "Test 5: LimitRange Verification"

# Check main LimitRange
if kubectl get limitrange jewelry-shop-limits -n jewelry-shop &> /dev/null; then
    print_test "LimitRange 'jewelry-shop-limits' exists" "PASS"
    
    # Check Container limits
    CONTAINER_LIMITS=$(kubectl get limitrange jewelry-shop-limits -n jewelry-shop -o jsonpath='{.spec.limits[?(@.type=="Container")]}' 2>/dev/null)
    if [ -n "$CONTAINER_LIMITS" ]; then
        print_test "LimitRange has Container limits" "PASS" "✓ Container limits configured"
    else
        print_test "LimitRange has Container limits" "FAIL" "Container limits not found"
    fi
    
    # Check Pod limits
    POD_LIMITS=$(kubectl get limitrange jewelry-shop-limits -n jewelry-shop -o jsonpath='{.spec.limits[?(@.type=="Pod")]}' 2>/dev/null)
    if [ -n "$POD_LIMITS" ]; then
        print_test "LimitRange has Pod limits" "PASS" "✓ Pod limits configured"
    else
        print_test "LimitRange has Pod limits" "FAIL" "Pod limits not found"
    fi
    
    # Check PVC limits
    PVC_LIMITS=$(kubectl get limitrange jewelry-shop-limits -n jewelry-shop -o jsonpath='{.spec.limits[?(@.type=="PersistentVolumeClaim")]}' 2>/dev/null)
    if [ -n "$PVC_LIMITS" ]; then
        print_test "LimitRange has PVC limits" "PASS" "✓ PVC limits configured"
    else
        print_test "LimitRange has PVC limits" "FAIL" "PVC limits not found"
    fi
else
    print_test "LimitRange 'jewelry-shop-limits' exists" "FAIL" "LimitRange not found"
fi

# Check dev LimitRange
if kubectl get limitrange jewelry-shop-dev-limits -n jewelry-shop &> /dev/null; then
    print_test "LimitRange 'jewelry-shop-dev-limits' exists" "PASS"
else
    print_test "LimitRange 'jewelry-shop-dev-limits' exists" "FAIL" "LimitRange not found"
fi

# ============================================================================
# Test 6: List all resources in namespace
# ============================================================================
print_header "Test 6: Complete Resource Inventory"

echo "All resources in jewelry-shop namespace:"
echo ""
kubectl get all,configmaps,secrets,resourcequotas,limitranges -n jewelry-shop 2>/dev/null || echo "No resources found"

# ============================================================================
# Summary
# ============================================================================
print_header "Validation Summary"

TOTAL=$((PASSED + FAILED))
PASS_RATE=$((PASSED * 100 / TOTAL))

echo -e "Total Tests: ${BLUE}$TOTAL${NC}"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo -e "Pass Rate: ${BLUE}${PASS_RATE}%${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}============================================================================${NC}"
    echo -e "${GREEN}✓ ALL VALIDATIONS PASSED${NC}"
    echo -e "${GREEN}Task 34.2 is complete and all resources are properly configured!${NC}"
    echo -e "${GREEN}============================================================================${NC}"
    exit 0
else
    echo -e "${RED}============================================================================${NC}"
    echo -e "${RED}✗ SOME VALIDATIONS FAILED${NC}"
    echo -e "${RED}Please review the failed tests above and fix the issues.${NC}"
    echo -e "${RED}============================================================================${NC}"
    exit 1
fi
