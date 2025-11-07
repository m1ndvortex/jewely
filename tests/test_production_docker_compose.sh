#!/bin/bash

# ============================================================================
# Production Docker Compose Configuration Test Suite
# ============================================================================
# This script comprehensively tests the production Docker Compose setup
# ============================================================================

# Don't exit on error - we want to run all tests
set +e

# Load environment variables if .env exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Test results array
declare -a FAILED_TESTS

# Functions
print_test_header() {
    echo
    echo -e "${BLUE}============================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================================${NC}"
    echo
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
    ((TESTS_PASSED++))
    ((TESTS_RUN++))
}

print_failure() {
    echo -e "${RED}✗ $1${NC}"
    FAILED_TESTS+=("$1")
    ((TESTS_FAILED++))
    ((TESTS_RUN++))
}

print_info() {
    echo -e "${NC}  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Cleanup function
cleanup() {
    if [ "$CLEANUP_ON_EXIT" = "true" ]; then
        print_info "Cleaning up test environment..."
        docker compose -f docker-compose.prod.yml down -v 2>/dev/null || true
    fi
}

trap cleanup EXIT

# Parse arguments
CLEANUP_ON_EXIT=false
SKIP_BUILD=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --cleanup)
            CLEANUP_ON_EXIT=true
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--cleanup] [--skip-build]"
            exit 1
            ;;
    esac
done

print_test_header "Production Docker Compose Configuration Tests"

# ============================================================================
# Test 1: File Existence
# ============================================================================
print_test_header "Test 1: Required Files Existence"

required_files=(
    "docker-compose.prod.yml"
    "Dockerfile.prod"
    ".env.production.example"
    "deploy-production.sh"
    "PRODUCTION_DEPLOYMENT.md"
    "docker/nginx/nginx.conf"
    "docker/nginx/conf.d/jewelry-shop.conf"
    "docker/postgresql.conf"
    "docker/prometheus.yml"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        print_success "File exists: $file"
    else
        print_failure "File missing: $file"
    fi
done

# ============================================================================
# Test 2: Docker Compose Syntax Validation
# ============================================================================
print_test_header "Test 2: Docker Compose Syntax Validation"

if docker compose -f docker-compose.prod.yml config --quiet 2>/dev/null; then
    print_success "Docker Compose syntax is valid"
else
    print_failure "Docker Compose syntax is invalid"
    docker compose -f docker-compose.prod.yml config 2>&1 | head -20
fi

# ============================================================================
# Test 3: Service Configuration
# ============================================================================
print_test_header "Test 3: Service Configuration"

expected_services=(
    "db"
    "redis"
    "pgbouncer"
    "web"
    "celery_worker"
    "celery_beat"
    "nginx"
    "certbot"
    "prometheus"
    "grafana"
    "nginx_exporter"
)

services=$(docker compose -f docker-compose.prod.yml config --services 2>/dev/null)

for service in "${expected_services[@]}"; do
    if echo "$services" | grep -q "^${service}$"; then
        print_success "Service configured: $service"
    else
        print_failure "Service missing: $service"
    fi
done

# ============================================================================
# Test 4: Network Configuration
# ============================================================================
print_test_header "Test 4: Network Configuration"

expected_networks=("frontend" "backend")

for network in "${expected_networks[@]}"; do
    if docker compose -f docker-compose.prod.yml config 2>/dev/null | grep -A 20 "^networks:" | grep -q "^  ${network}:"; then
        print_success "Network configured: $network"
    else
        print_failure "Network missing: $network"
    fi
done

# Check backend network is internal
if docker compose -f docker-compose.prod.yml config 2>/dev/null | grep -A 10 "backend:" | grep -q "internal: true"; then
    print_success "Backend network is internal (isolated)"
else
    print_failure "Backend network is not internal"
fi

# ============================================================================
# Test 5: Volume Configuration
# ============================================================================
print_test_header "Test 5: Volume Configuration"

expected_volumes=(
    "postgres_data"
    "postgres_wal_archive"
    "redis_data"
    "media_files"
    "static_files"
    "backups"
    "prometheus_data"
    "grafana_data"
    "certbot_www"
    "certbot_conf"
    "certbot_logs"
    "nginx_logs"
    "app_logs"
)

volumes=$(docker compose -f docker-compose.prod.yml config --volumes 2>/dev/null)

for volume in "${expected_volumes[@]}"; do
    if echo "$volumes" | grep -q "^${volume}$"; then
        print_success "Volume configured: $volume"
    else
        print_failure "Volume missing: $volume"
    fi
done

# ============================================================================
# Test 6: Health Check Configuration
# ============================================================================
print_test_header "Test 6: Health Check Configuration"

services_with_healthchecks=(
    "db"
    "redis"
    "pgbouncer"
    "web"
    "celery_worker"
    "celery_beat"
    "nginx"
    "prometheus"
    "grafana"
)

# Save config to temp file for easier parsing
config_file=$(mktemp)
docker compose -f docker-compose.prod.yml config 2>/dev/null > "$config_file"

for service in "${services_with_healthchecks[@]}"; do
    # Check if service has healthcheck in the YAML
    if grep -A 200 "^  ${service}:" "$config_file" | grep -B 200 "^  [a-z_]*:" | head -n -1 | grep -q "healthcheck:"; then
        print_success "Health check configured: $service"
    else
        print_failure "Health check missing: $service"
    fi
done

# ============================================================================
# Test 7: Security Configuration
# ============================================================================
print_test_header "Test 7: Security Configuration"

# Check for security_opt: no-new-privileges
services_with_security=(
    "db"
    "redis"
    "pgbouncer"
    "web"
    "celery_worker"
    "celery_beat"
    "nginx"
    "certbot"
    "prometheus"
    "grafana"
    "nginx_exporter"
)

for service in "${services_with_security[@]}"; do
    if grep -A 200 "^  ${service}:" "$config_file" | grep -B 200 "^  [a-z_]*:" | head -n -1 | grep -q "no-new-privileges"; then
        print_success "Security hardening (no-new-privileges): $service"
    else
        print_failure "Security hardening missing: $service"
    fi
done

# ============================================================================
# Test 8: Resource Limits
# ============================================================================
print_test_header "Test 8: Resource Limits Configuration"

services_with_limits=(
    "db"
    "redis"
    "pgbouncer"
    "web"
    "celery_worker"
    "celery_beat"
    "nginx"
    "prometheus"
    "grafana"
)

for service in "${services_with_limits[@]}"; do
    if grep -A 200 "^  ${service}:" "$config_file" | grep -B 200 "^  [a-z_]*:" | head -n -1 | grep -q "resources:"; then
        print_success "Resource limits configured: $service"
    else
        print_failure "Resource limits missing: $service"
    fi
done

# ============================================================================
# Test 9: Restart Policy
# ============================================================================
print_test_header "Test 9: Restart Policy Configuration"

for service in "${expected_services[@]}"; do
    if grep -A 200 "^  ${service}:" "$config_file" | grep -B 200 "^  [a-z_]*:" | head -n -1 | grep -q "restart: unless-stopped"; then
        print_success "Restart policy configured: $service"
    else
        print_failure "Restart policy missing: $service"
    fi
done

# ============================================================================
# Test 10: Dockerfile.prod Non-Root User
# ============================================================================
print_test_header "Test 10: Dockerfile.prod Non-Root User Configuration"

if grep -q "useradd.*appuser" Dockerfile.prod; then
    print_success "Non-root user (appuser) created in Dockerfile.prod"
else
    print_failure "Non-root user not created in Dockerfile.prod"
fi

if grep -q "USER appuser" Dockerfile.prod; then
    print_success "Container switches to non-root user (appuser)"
else
    print_failure "Container does not switch to non-root user"
fi

if grep -q "chown.*appuser:appgroup" Dockerfile.prod; then
    print_success "File permissions set for non-root user"
else
    print_failure "File permissions not set for non-root user"
fi

# ============================================================================
# Test 11: Environment Variables
# ============================================================================
print_test_header "Test 11: Environment Variables Configuration"

if [ -f .env ]; then
    print_success ".env file exists"
    
    # Check for required variables
    required_vars=(
        "POSTGRES_DB"
        "DB_SUPERUSER_PASSWORD"
        "APP_DB_PASSWORD"
        "GRAFANA_ADMIN_PASSWORD"
    )
    
    for var in "${required_vars[@]}"; do
        if grep -q "^${var}=" .env 2>/dev/null; then
            value=$(grep "^${var}=" .env | cut -d'=' -f2)
            if [ -n "$value" ]; then
                print_success "Environment variable set: $var"
            else
                print_failure "Environment variable empty: $var"
            fi
        else
            print_failure "Environment variable missing: $var"
        fi
    done
else
    print_failure ".env file not found"
fi

# ============================================================================
# Test 12: Script Permissions
# ============================================================================
print_test_header "Test 12: Script Permissions"

scripts=(
    "deploy-production.sh"
    "validate-production-config.sh"
)

for script in "${scripts[@]}"; do
    if [ -f "$script" ]; then
        if [ -x "$script" ]; then
            print_success "Script is executable: $script"
        else
            print_failure "Script is not executable: $script"
        fi
    else
        print_failure "Script not found: $script"
    fi
done

# ============================================================================
# Test 13: Build Test (Optional)
# ============================================================================
if [ "$SKIP_BUILD" = "false" ]; then
    print_test_header "Test 13: Docker Image Build Test"
    
    print_info "Building production Docker image..."
    if docker compose -f docker-compose.prod.yml build web 2>&1 | tee /tmp/build.log; then
        print_success "Production Docker image builds successfully"
        
        # Check if image was created
        if docker images | grep -q "jewelry-shop"; then
            print_success "Docker image created: jewelry-shop"
            
            # Verify non-root user in image
            print_info "Verifying non-root user in image..."
            user=$(docker run --rm jewelry-shop:${VERSION:-latest} whoami 2>/dev/null)
            if [ "$user" = "appuser" ]; then
                print_success "Container runs as non-root user: $user"
            else
                print_failure "Container runs as root or unknown user: $user"
            fi
        else
            print_failure "Docker image not created"
        fi
    else
        print_failure "Production Docker image build failed"
        print_info "Build log:"
        tail -20 /tmp/build.log
    fi
else
    print_warning "Skipping build test (--skip-build flag set)"
fi

# ============================================================================
# Test 14: Service Dependencies
# ============================================================================
print_test_header "Test 14: Service Dependencies Configuration"

# Check web depends on db, redis, pgbouncer
if grep -A 200 "^  web:" "$config_file" | grep -B 200 "^  [a-z_]*:" | head -n -1 | grep -q "db:"; then
    print_success "Web service depends on db"
else
    print_failure "Web service missing dependency: db"
fi

if grep -A 200 "^  web:" "$config_file" | grep -B 200 "^  [a-z_]*:" | head -n -1 | grep -q "redis:"; then
    print_success "Web service depends on redis"
else
    print_failure "Web service missing dependency: redis"
fi

if grep -A 200 "^  web:" "$config_file" | grep -B 200 "^  [a-z_]*:" | head -n -1 | grep -q "pgbouncer:"; then
    print_success "Web service depends on pgbouncer"
else
    print_failure "Web service missing dependency: pgbouncer"
fi

# ============================================================================
# Test 15: Logging Configuration
# ============================================================================
print_test_header "Test 15: Logging Configuration"

for service in "${expected_services[@]}"; do
    if grep -A 200 "^  ${service}:" "$config_file" | grep -B 200 "^  [a-z_]*:" | head -n -1 | grep -q "logging:"; then
        print_success "Logging configured: $service"
    else
        print_failure "Logging missing: $service"
    fi
done

# Cleanup temp file
rm -f "$config_file"

# ============================================================================
# Test Summary
# ============================================================================
print_test_header "Test Summary"

echo -e "${BLUE}Tests Run:    ${NC}$TESTS_RUN"
echo -e "${GREEN}Tests Passed: ${NC}$TESTS_PASSED"
echo -e "${RED}Tests Failed: ${NC}$TESTS_FAILED"
echo

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}============================================================================${NC}"
    echo -e "${GREEN}✓ ALL TESTS PASSED${NC}"
    echo -e "${GREEN}============================================================================${NC}"
    exit 0
else
    echo -e "${RED}============================================================================${NC}"
    echo -e "${RED}✗ SOME TESTS FAILED${NC}"
    echo -e "${RED}============================================================================${NC}"
    echo
    echo "Failed tests:"
    for test in "${FAILED_TESTS[@]}"; do
        echo -e "${RED}  ✗ $test${NC}"
    done
    echo
    exit 1
fi
