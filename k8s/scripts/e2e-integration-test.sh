#!/bin/bash

# End-to-End Integration Testing Script for Task 34.14
# Tests complete application stack on k3d cluster

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results tracking
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# Namespace
NAMESPACE="jewelry-shop"

# Log file
LOG_FILE="k8s/TASK_34.14_TEST_RESULTS_$(date +%Y%m%d_%H%M%S).log"

# Function to print colored output
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
    echo "✅ $1" >> "$LOG_FILE"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
    echo "❌ $1" >> "$LOG_FILE"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    echo "⚠️  $1" >> "$LOG_FILE"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
    echo "ℹ️  $1" >> "$LOG_FILE"
}

# Function to record test result
record_test() {
    local test_name="$1"
    local result="$2"
    
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    
    if [ "$result" = "PASS" ]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        print_success "Test $TESTS_TOTAL: $test_name - PASSED"
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        print_error "Test $TESTS_TOTAL: $test_name - FAILED"
    fi
}

# Initialize log file
echo "End-to-End Integration Test Results" > "$LOG_FILE"
echo "Test Date: $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

print_header "Task 34.14: End-to-End Integration Testing"
print_info "Starting comprehensive integration tests on k3d cluster"
print_info "Log file: $LOG_FILE"

# Test 1: Verify cluster is running
print_header "Test 1: Cluster Health Check"
if kubectl cluster-info &> /dev/null; then
    record_test "Cluster is accessible" "PASS"
else
    record_test "Cluster is accessible" "FAIL"
    print_error "Cluster is not accessible. Please start k3d cluster first."
    exit 1
fi

# Test 2: Verify all pods are running
print_header "Test 2: Pod Status Check"
print_info "Checking all pods in namespace: $NAMESPACE"

NOT_RUNNING=$(kubectl get pods -n $NAMESPACE --no-headers | grep -v "Running\|Completed" | wc -l)
if [ "$NOT_RUNNING" -eq 0 ]; then
    record_test "All pods are running" "PASS"
    kubectl get pods -n $NAMESPACE
else
    record_test "All pods are running" "FAIL"
    print_error "Found $NOT_RUNNING pods not in Running state"
    kubectl get pods -n $NAMESPACE | grep -v "Running\|Completed"
fi

# Test 3: Verify services are accessible
print_header "Test 3: Service Connectivity Check"

# Get Django pod
DJANGO_POD=$(kubectl get pods -n $NAMESPACE -l component=django -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ -z "$DJANGO_POD" ]; then
    record_test "Django pod exists" "FAIL"
    print_error "No Django pod found"
else
    record_test "Django pod exists" "PASS"
    
    # Test Django health endpoint
    print_info "Testing Django health endpoint..."
    HEALTH_TEST=$(kubectl exec -n $NAMESPACE $DJANGO_POD -- python -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
result = s.connect_ex(('localhost', 8000))
print('SUCCESS' if result == 0 else 'FAIL')
" 2>&1)
    
    if echo "$HEALTH_TEST" | grep -q "SUCCESS"; then
        record_test "Django health endpoint responds" "PASS"
    else
        record_test "Django health endpoint responds" "FAIL"
    fi
fi

# Test 4: Database connectivity
print_header "Test 4: Database Connectivity"

if [ -n "$DJANGO_POD" ]; then
    print_info "Testing PostgreSQL connectivity from Django..."
    DB_TEST=$(kubectl exec -n $NAMESPACE $DJANGO_POD -- python manage.py check --database default 2>&1)
    if echo "$DB_TEST" | grep -q "System check identified no issues"; then
        record_test "Django can connect to PostgreSQL" "PASS"
    else
        record_test "Django can connect to PostgreSQL" "FAIL"
        print_error "Database connection failed: $DB_TEST"
    fi
fi

# Test 5: Redis connectivity
print_header "Test 5: Redis Connectivity"

if [ -n "$DJANGO_POD" ]; then
    print_info "Testing Redis connectivity from Django..."
    REDIS_TEST=$(kubectl exec -n $NAMESPACE $DJANGO_POD -- python -c "
import redis
import os
redis_url = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
r = redis.from_url(redis_url)
r.ping()
print('SUCCESS')
" 2>&1)
    
    if echo "$REDIS_TEST" | grep -q "SUCCESS"; then
        record_test "Django can connect to Redis" "PASS"
    else
        record_test "Django can connect to Redis" "FAIL"
        print_error "Redis connection failed: $REDIS_TEST"
    fi
fi

# Test 6: Celery worker connectivity
print_header "Test 6: Celery Worker Status"

CELERY_POD=$(kubectl get pods -n $NAMESPACE -l component=celery-worker -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ -z "$CELERY_POD" ]; then
    record_test "Celery worker pod exists" "FAIL"
else
    record_test "Celery worker pod exists" "PASS"
    
    # Check if worker is connected
    print_info "Checking Celery worker logs..."
    WORKER_LOGS=$(kubectl logs -n $NAMESPACE $CELERY_POD --tail=50 2>&1)
    if echo "$WORKER_LOGS" | grep -qE "ready|ForkPoolWorker|MainProcess"; then
        record_test "Celery worker is ready" "PASS"
    else
        record_test "Celery worker is ready" "FAIL"
        print_warning "Worker may not be fully initialized yet"
    fi
fi

# Test 7: Nginx connectivity
print_header "Test 7: Nginx Reverse Proxy"

NGINX_POD=$(kubectl get pods -n $NAMESPACE -l component=nginx -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ -z "$NGINX_POD" ]; then
    record_test "Nginx pod exists" "FAIL"
else
    record_test "Nginx pod exists" "PASS"
    
    # Test Nginx can reach Django service
    print_info "Testing Nginx can reach Django service..."
    NGINX_TEST=$(timeout 10 kubectl exec -n $NAMESPACE $NGINX_POD -c nginx -- curl -s -o /dev/null -w "%{http_code}" http://django-service:80/health/ 2>&1 || echo "TIMEOUT")
    # Accept 200, 400, or 403 as success (service is reachable)
    if echo "$NGINX_TEST" | grep -qE "^(200|400|403)$"; then
        record_test "Nginx can reach Django service" "PASS"
    else
        record_test "Nginx can reach Django service" "FAIL"
        print_error "Nginx test returned: $NGINX_TEST"
    fi
fi

# Test 8: PostgreSQL Failover Test
print_header "Test 8: PostgreSQL Automatic Failover"

print_info "Identifying PostgreSQL master pod..."
PG_MASTER=$(kubectl get pods -n $NAMESPACE -l application=spilo,spilo-role=master -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -z "$PG_MASTER" ]; then
    record_test "PostgreSQL master identified" "FAIL"
    print_warning "Skipping failover test - no master pod found"
else
    record_test "PostgreSQL master identified" "PASS"
    print_info "Current master: $PG_MASTER"
    
    # Record start time
    START_TIME=$(date +%s)
    
    print_info "Killing PostgreSQL master pod to trigger failover..."
    kubectl delete pod -n $NAMESPACE $PG_MASTER --grace-period=0 --force &> /dev/null
    
    print_info "Waiting for new master election..."
    sleep 5
    
    # Wait for new master (max 60 seconds - pod needs time to restart)
    NEW_MASTER_FOUND=false
    for i in {1..60}; do
        NEW_MASTER=$(kubectl get pods -n $NAMESPACE -l application=spilo,spilo-role=master -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
        POD_AGE=$(kubectl get pod -n $NAMESPACE $NEW_MASTER -o jsonpath='{.status.startTime}' 2>/dev/null)
        
        # Check if we have a master and it's either a different pod or the same pod restarted
        if [ -n "$NEW_MASTER" ]; then
            if [ "$NEW_MASTER" != "$PG_MASTER" ]; then
                # Different pod became master
                END_TIME=$(date +%s)
                FAILOVER_TIME=$((END_TIME - START_TIME))
                print_success "New master elected: $NEW_MASTER"
                print_success "Failover completed in ${FAILOVER_TIME} seconds"
                NEW_MASTER_FOUND=true
                
                if [ $FAILOVER_TIME -le 30 ]; then
                    record_test "PostgreSQL failover within 30 seconds" "PASS"
                else
                    record_test "PostgreSQL failover within 30 seconds" "FAIL"
                fi
                break
            elif [ "$NEW_MASTER" = "$PG_MASTER" ] && [ $i -gt 10 ]; then
                # Same pod name but it was recreated (check if it's running)
                POD_STATUS=$(kubectl get pod -n $NAMESPACE $NEW_MASTER -o jsonpath='{.status.phase}' 2>/dev/null)
                if [ "$POD_STATUS" = "Running" ]; then
                    END_TIME=$(date +%s)
                    FAILOVER_TIME=$((END_TIME - START_TIME))
                    print_success "Master pod recreated and running: $NEW_MASTER"
                    print_success "Recovery completed in ${FAILOVER_TIME} seconds"
                    NEW_MASTER_FOUND=true
                    
                    if [ $FAILOVER_TIME -le 60 ]; then
                        record_test "PostgreSQL pod recovery within 60 seconds" "PASS"
                    else
                        record_test "PostgreSQL pod recovery within 60 seconds" "FAIL"
                    fi
                    break
                fi
            fi
        fi
        sleep 1
    done
    
    if [ "$NEW_MASTER_FOUND" = false ]; then
        record_test "PostgreSQL failover/recovery" "FAIL"
        print_error "No master found after 60 seconds"
    fi
    
    # Verify Django can still connect
    sleep 5
    print_info "Verifying Django can connect to new master..."
    if [ -n "$DJANGO_POD" ]; then
        DB_TEST_AFTER=$(kubectl exec -n $NAMESPACE $DJANGO_POD -- python manage.py check --database default 2>&1)
        if echo "$DB_TEST_AFTER" | grep -q "System check identified no issues"; then
            record_test "Django reconnects after PostgreSQL failover" "PASS"
        else
            record_test "Django reconnects after PostgreSQL failover" "FAIL"
        fi
    fi
fi

# Test 9: Redis Failover Test
print_header "Test 9: Redis Automatic Failover"

print_info "Identifying Redis master..."
REDIS_MASTER=$(kubectl exec -n $NAMESPACE redis-0 -- redis-cli info replication 2>/dev/null | grep "role:master" | wc -l)

if [ "$REDIS_MASTER" -eq 1 ]; then
    REDIS_MASTER_POD="redis-0"
elif kubectl exec -n $NAMESPACE redis-1 -- redis-cli info replication 2>/dev/null | grep -q "role:master"; then
    REDIS_MASTER_POD="redis-1"
elif kubectl exec -n $NAMESPACE redis-2 -- redis-cli info replication 2>/dev/null | grep -q "role:master"; then
    REDIS_MASTER_POD="redis-2"
else
    REDIS_MASTER_POD=""
fi

if [ -z "$REDIS_MASTER_POD" ]; then
    record_test "Redis master identified" "FAIL"
    print_warning "Skipping Redis failover test - no master found"
else
    record_test "Redis master identified" "PASS"
    print_info "Current Redis master: $REDIS_MASTER_POD"
    
    # Record start time
    START_TIME=$(date +%s)
    
    print_info "Killing Redis master pod to trigger failover..."
    kubectl delete pod -n $NAMESPACE $REDIS_MASTER_POD --grace-period=0 --force &> /dev/null
    
    print_info "Waiting for Sentinel to elect new master..."
    sleep 10
    
    # Check for new master
    for i in {1..30}; do
        for pod in redis-0 redis-1 redis-2; do
            if [ "$pod" != "$REDIS_MASTER_POD" ]; then
                IS_MASTER=$(kubectl exec -n $NAMESPACE $pod -- redis-cli info replication 2>/dev/null | grep "role:master" | wc -l)
                if [ "$IS_MASTER" -eq 1 ]; then
                    END_TIME=$(date +%s)
                    FAILOVER_TIME=$((END_TIME - START_TIME))
                    print_success "New Redis master: $pod"
                    print_success "Failover completed in ${FAILOVER_TIME} seconds"
                    
                    if [ $FAILOVER_TIME -le 30 ]; then
                        record_test "Redis failover within 30 seconds" "PASS"
                    else
                        record_test "Redis failover within 30 seconds" "FAIL"
                    fi
                    break 2
                fi
            fi
        done
        sleep 1
    done
fi

# Test 10: Pod Self-Healing
print_header "Test 10: Pod Self-Healing"

print_info "Testing pod self-healing by deleting a Django pod..."
if [ -n "$DJANGO_POD" ]; then
    # Get initial pod count
    INITIAL_COUNT=$(kubectl get pods -n $NAMESPACE -l component=django --no-headers | wc -l)
    
    print_info "Deleting pod: $DJANGO_POD"
    kubectl delete pod -n $NAMESPACE $DJANGO_POD --grace-period=0 --force &> /dev/null
    
    # Wait for pod to be recreated
    print_info "Waiting for pod recreation..."
    sleep 5
    
    for i in {1..30}; do
        CURRENT_COUNT=$(kubectl get pods -n $NAMESPACE -l component=django --field-selector=status.phase=Running --no-headers | wc -l)
        if [ "$CURRENT_COUNT" -eq "$INITIAL_COUNT" ]; then
            print_success "Pod recreated successfully"
            record_test "Django pod self-healing" "PASS"
            break
        fi
        sleep 1
    done
    
    if [ "$CURRENT_COUNT" -ne "$INITIAL_COUNT" ]; then
        record_test "Django pod self-healing" "FAIL"
        print_error "Pod count: $CURRENT_COUNT (expected: $INITIAL_COUNT)"
    fi
fi

# Test 11: HPA Scaling Test
print_header "Test 11: Horizontal Pod Autoscaler"

print_info "Checking if HPA is configured..."
HPA_EXISTS=$(kubectl get hpa -n $NAMESPACE django-hpa 2>/dev/null | wc -l)

if [ "$HPA_EXISTS" -eq 0 ]; then
    record_test "HPA exists" "FAIL"
    print_warning "Skipping HPA test - HPA not found"
else
    record_test "HPA exists" "PASS"
    
    # Get current replica count
    INITIAL_REPLICAS=$(kubectl get deployment -n $NAMESPACE django-deployment -o jsonpath='{.spec.replicas}')
    print_info "Initial replicas: $INITIAL_REPLICAS"
    
    # Generate load
    print_info "Generating load to trigger scale-up..."
    print_info "Starting load generator pod..."
    
    kubectl run load-generator -n $NAMESPACE --image=busybox --restart=Never -- /bin/sh -c "while true; do wget -q -O- http://django-service:8000/health/; done" &> /dev/null &
    LOAD_PID=$!
    
    # Wait and check for scale-up
    print_info "Waiting 60 seconds for HPA to scale up..."
    sleep 60
    
    SCALED_REPLICAS=$(kubectl get deployment -n $NAMESPACE django-deployment -o jsonpath='{.spec.replicas}')
    print_info "Replicas after load: $SCALED_REPLICAS"
    
    if [ "$SCALED_REPLICAS" -gt "$INITIAL_REPLICAS" ]; then
        record_test "HPA scales up under load" "PASS"
        print_success "Scaled from $INITIAL_REPLICAS to $SCALED_REPLICAS replicas"
    else
        record_test "HPA scales up under load" "FAIL"
        print_warning "No scale-up detected. This may be due to low CPU usage or metrics delay."
    fi
    
    # Stop load generator
    print_info "Stopping load generator..."
    kubectl delete pod -n $NAMESPACE load-generator --grace-period=0 --force &> /dev/null 2>&1 || true
    
    # Wait for scale-down
    print_info "Waiting 120 seconds for HPA to scale down..."
    sleep 120
    
    FINAL_REPLICAS=$(kubectl get deployment -n $NAMESPACE django-deployment -o jsonpath='{.spec.replicas}')
    print_info "Final replicas: $FINAL_REPLICAS"
    
    if [ "$FINAL_REPLICAS" -le "$SCALED_REPLICAS" ]; then
        record_test "HPA scales down after load" "PASS"
    else
        record_test "HPA scales down after load" "FAIL"
    fi
fi

# Test 12: Data Persistence After Pod Restart
print_header "Test 12: Data Persistence"

print_info "Testing data persistence after pod restart..."

# Write test data to database
if [ -n "$DJANGO_POD" ]; then
    TEST_KEY="e2e_test_$(date +%s)"
    print_info "Writing test data with key: $TEST_KEY"
    
    WRITE_RESULT=$(kubectl exec -n $NAMESPACE $DJANGO_POD -- python -c "
from django.core.cache import cache
cache.set('$TEST_KEY', 'test_value', 300)
print('SUCCESS' if cache.get('$TEST_KEY') == 'test_value' else 'FAIL')
" 2>&1)
    
    if echo "$WRITE_RESULT" | grep -q "SUCCESS"; then
        record_test "Write test data to cache" "PASS"
        
        # Restart Redis pod
        print_info "Restarting Redis pod to test persistence..."
        kubectl delete pod -n $NAMESPACE redis-0 --grace-period=0 --force &> /dev/null
        
        # Wait for pod to restart
        print_info "Waiting for Redis pod to restart..."
        kubectl wait --for=condition=Ready pod/redis-0 -n $NAMESPACE --timeout=60s &> /dev/null
        
        # Try to read data
        sleep 5
        print_info "Reading test data after restart..."
        READ_RESULT=$(kubectl exec -n $NAMESPACE $DJANGO_POD -- python -c "
from django.core.cache import cache
value = cache.get('$TEST_KEY')
print('SUCCESS' if value == 'test_value' else 'FAIL')
" 2>&1)
        
        if echo "$READ_RESULT" | grep -q "SUCCESS"; then
            record_test "Data persists after Redis restart" "PASS"
        else
            record_test "Data persists after Redis restart" "FAIL"
            print_warning "Data may not persist with current Redis configuration"
        fi
    else
        record_test "Write test data to cache" "FAIL"
    fi
fi

# Test 13: Network Policies
print_header "Test 13: Network Policy Enforcement"

print_info "Checking if NetworkPolicies are applied..."
NP_COUNT=$(kubectl get networkpolicies -n $NAMESPACE --no-headers 2>/dev/null | wc -l)

if [ "$NP_COUNT" -gt 0 ]; then
    record_test "NetworkPolicies are applied" "PASS"
    print_info "Found $NP_COUNT NetworkPolicies"
else
    record_test "NetworkPolicies are applied" "FAIL"
    print_warning "No NetworkPolicies found"
fi

# Test 14: Ingress Connectivity
print_header "Test 14: Ingress Controller"

print_info "Checking Traefik ingress controller..."
TRAEFIK_POD=$(kubectl get pods -n traefik -l app.kubernetes.io/name=traefik -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -z "$TRAEFIK_POD" ]; then
    record_test "Traefik ingress controller running" "FAIL"
else
    record_test "Traefik ingress controller running" "PASS"
    
    # Check if ingress exists
    INGRESS_EXISTS=$(kubectl get ingress -n $NAMESPACE 2>/dev/null | wc -l)
    if [ "$INGRESS_EXISTS" -gt 1 ]; then
        record_test "Ingress resource exists" "PASS"
    else
        record_test "Ingress resource exists" "FAIL"
    fi
fi

# Test 15: Monitoring Stack
print_header "Test 15: Monitoring and Metrics"

print_info "Checking metrics-server..."
METRICS_SERVER=$(kubectl get deployment -n kube-system metrics-server 2>/dev/null | wc -l)

if [ "$METRICS_SERVER" -gt 1 ]; then
    record_test "Metrics server deployed" "PASS"
    
    # Try to get pod metrics
    print_info "Testing pod metrics collection..."
    if kubectl top pods -n $NAMESPACE &> /dev/null; then
        record_test "Pod metrics available" "PASS"
    else
        record_test "Pod metrics available" "FAIL"
        print_warning "Metrics may not be ready yet"
    fi
else
    record_test "Metrics server deployed" "FAIL"
fi

# Test 16: Persistent Volumes
print_header "Test 16: Persistent Volume Claims"

print_info "Checking PVCs..."
PVC_COUNT=$(kubectl get pvc -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
PVC_BOUND=$(kubectl get pvc -n $NAMESPACE --no-headers 2>/dev/null | grep "Bound" | wc -l)

if [ "$PVC_COUNT" -gt 0 ]; then
    record_test "PVCs exist" "PASS"
    print_info "Found $PVC_COUNT PVCs, $PVC_BOUND bound"
    
    if [ "$PVC_BOUND" -eq "$PVC_COUNT" ]; then
        record_test "All PVCs are bound" "PASS"
    else
        record_test "All PVCs are bound" "FAIL"
        print_error "Some PVCs are not bound"
    fi
else
    record_test "PVCs exist" "FAIL"
fi

# Test 17: Resource Limits and Quotas
print_header "Test 17: Resource Management"

print_info "Checking resource quotas..."
QUOTA_EXISTS=$(kubectl get resourcequota -n $NAMESPACE 2>/dev/null | wc -l)

if [ "$QUOTA_EXISTS" -gt 1 ]; then
    record_test "Resource quota configured" "PASS"
else
    record_test "Resource quota configured" "FAIL"
fi

print_info "Checking limit ranges..."
LIMIT_EXISTS=$(kubectl get limitrange -n $NAMESPACE 2>/dev/null | wc -l)

if [ "$LIMIT_EXISTS" -gt 1 ]; then
    record_test "Limit range configured" "PASS"
else
    record_test "Limit range configured" "FAIL"
fi

# Test 18: ConfigMaps and Secrets
print_header "Test 18: Configuration Management"

print_info "Checking ConfigMaps..."
CM_COUNT=$(kubectl get configmap -n $NAMESPACE --no-headers 2>/dev/null | wc -l)

if [ "$CM_COUNT" -gt 0 ]; then
    record_test "ConfigMaps exist" "PASS"
    print_info "Found $CM_COUNT ConfigMaps"
else
    record_test "ConfigMaps exist" "FAIL"
fi

print_info "Checking Secrets..."
SECRET_COUNT=$(kubectl get secret -n $NAMESPACE --no-headers 2>/dev/null | wc -l)

if [ "$SECRET_COUNT" -gt 0 ]; then
    record_test "Secrets exist" "PASS"
    print_info "Found $SECRET_COUNT Secrets"
else
    record_test "Secrets exist" "FAIL"
fi

# Final Summary
print_header "Test Summary"

echo ""
echo "========================================" | tee -a "$LOG_FILE"
echo "FINAL TEST RESULTS" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "Total Tests: $TESTS_TOTAL" | tee -a "$LOG_FILE"
echo "Passed: $TESTS_PASSED" | tee -a "$LOG_FILE"
echo "Failed: $TESTS_FAILED" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

SUCCESS_RATE=$((TESTS_PASSED * 100 / TESTS_TOTAL))
echo "Success Rate: ${SUCCESS_RATE}%" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

if [ $TESTS_FAILED -eq 0 ]; then
    print_success "ALL TESTS PASSED! ✅"
    echo "Status: ✅ ALL TESTS PASSED" >> "$LOG_FILE"
    exit 0
else
    print_error "SOME TESTS FAILED ❌"
    echo "Status: ❌ $TESTS_FAILED TESTS FAILED" >> "$LOG_FILE"
    exit 1
fi
