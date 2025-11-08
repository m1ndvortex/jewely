#!/bin/bash
# ============================================================================
# Deployment Test Script
# ============================================================================
# This script tests that all services are properly configured and running.
#
# Usage:
#   ./scripts/test_deployment.sh development
#   ./scripts/test_deployment.sh staging
#   ./scripts/test_deployment.sh production
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Environment
ENV=${1:-development}
COMPOSE_FILE="docker-compose.yml"

if [ "$ENV" = "production" ] || [ "$ENV" = "staging" ]; then
    COMPOSE_FILE="docker-compose.prod.yml"
fi

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}Testing ${ENV} Deployment${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""

# Function to print test result
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
        return 1
    fi
}

# Function to run test
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo -n "Testing: $test_name... "
    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        return 0
    else
        echo -e "${RED}✗${NC}"
        return 1
    fi
}

# Counter for passed/failed tests
PASSED=0
FAILED=0

echo -e "${BLUE}1. Environment Validation${NC}"
echo "-----------------------------------"

# Validate environment variables
if python3 scripts/validate_env.py --env "$ENV"; then
    ((PASSED++))
else
    ((FAILED++))
fi
echo ""

echo -e "${BLUE}2. Docker Services${NC}"
echo "-----------------------------------"

# Check if Docker is running
if run_test "Docker daemon" "docker info"; then
    ((PASSED++))
else
    ((FAILED++))
fi

# Check if services are running
SERVICES=("db" "redis" "web")
if [ "$ENV" = "production" ] || [ "$ENV" = "staging" ]; then
    SERVICES+=("pgbouncer" "celery_worker" "celery_beat" "nginx")
fi

for service in "${SERVICES[@]}"; do
    if run_test "$service service" "docker compose -f $COMPOSE_FILE ps $service | grep -q 'Up'"; then
        ((PASSED++))
    else
        ((FAILED++))
    fi
done
echo ""

echo -e "${BLUE}3. Service Health Checks${NC}"
echo "-----------------------------------"

# Check database connection
if run_test "Database connection" "docker compose -f $COMPOSE_FILE exec -T web python manage.py dbshell --command='SELECT 1;'"; then
    ((PASSED++))
else
    ((FAILED++))
fi

# Check Redis connection
if run_test "Redis connection" "docker compose -f $COMPOSE_FILE exec -T redis redis-cli ping | grep -q 'PONG'"; then
    ((PASSED++))
else
    ((FAILED++))
fi

# Check web health endpoint
if run_test "Web health endpoint" "docker compose -f $COMPOSE_FILE exec -T web curl -f http://localhost:8000/health/"; then
    ((PASSED++))
else
    ((FAILED++))
fi
echo ""

echo -e "${BLUE}4. Django Configuration${NC}"
echo "-----------------------------------"

# Check Django settings
if run_test "Django check" "docker compose -f $COMPOSE_FILE exec -T web python manage.py check"; then
    ((PASSED++))
else
    ((FAILED++))
fi

# Verify settings module
EXPECTED_MODULE="config.settings.$ENV"
ACTUAL_MODULE=$(docker compose -f $COMPOSE_FILE exec -T web python -c "from django.conf import settings; print(settings.SETTINGS_MODULE)" 2>/dev/null | tr -d '\r')

if [ "$ACTUAL_MODULE" = "$EXPECTED_MODULE" ]; then
    echo -e "${GREEN}✓${NC} Settings module: $ACTUAL_MODULE"
    ((PASSED++))
else
    echo -e "${RED}✗${NC} Settings module: Expected $EXPECTED_MODULE, got $ACTUAL_MODULE"
    ((FAILED++))
fi

# Verify DEBUG setting
if [ "$ENV" = "production" ]; then
    DEBUG_VALUE=$(docker compose -f $COMPOSE_FILE exec -T web python -c "from django.conf import settings; print(settings.DEBUG)" 2>/dev/null | tr -d '\r')
    if [ "$DEBUG_VALUE" = "False" ]; then
        echo -e "${GREEN}✓${NC} DEBUG=False in production"
        ((PASSED++))
    else
        echo -e "${RED}✗${NC} DEBUG should be False in production, got $DEBUG_VALUE"
        ((FAILED++))
    fi
fi
echo ""

echo -e "${BLUE}5. Database Migrations${NC}"
echo "-----------------------------------"

# Check for pending migrations
if run_test "No pending migrations" "docker compose -f $COMPOSE_FILE exec -T web python manage.py showmigrations | grep -q '\[ \]' && exit 1 || exit 0"; then
    ((PASSED++))
else
    echo -e "${YELLOW}⚠${NC} Warning: Pending migrations found"
    ((FAILED++))
fi
echo ""

echo -e "${BLUE}6. Static Files${NC}"
echo "-----------------------------------"

# Check if static files are collected
if run_test "Static files collected" "docker compose -f $COMPOSE_FILE exec -T web test -d /app/staticfiles/admin"; then
    ((PASSED++))
else
    ((FAILED++))
fi
echo ""

echo -e "${BLUE}7. Celery Workers${NC}"
echo "-----------------------------------"

if [ "$ENV" = "production" ] || [ "$ENV" = "staging" ]; then
    # Check Celery worker
    if run_test "Celery worker" "docker compose -f $COMPOSE_FILE exec -T celery_worker celery -A config inspect ping"; then
        ((PASSED++))
    else
        ((FAILED++))
    fi
    
    # Check Celery beat
    if run_test "Celery beat" "docker compose -f $COMPOSE_FILE ps celery_beat | grep -q 'Up'"; then
        ((PASSED++))
    else
        ((FAILED++))
    fi
fi
echo ""

echo -e "${BLUE}8. Security Checks${NC}"
echo "-----------------------------------"

# Check SECRET_KEY is not default
SECRET_KEY=$(docker compose -f $COMPOSE_FILE exec -T web python -c "from django.conf import settings; print(settings.SECRET_KEY)" 2>/dev/null | tr -d '\r')
if [[ "$SECRET_KEY" == *"change-in-production"* ]]; then
    echo -e "${RED}✗${NC} SECRET_KEY contains default value"
    ((FAILED++))
else
    echo -e "${GREEN}✓${NC} SECRET_KEY is customized"
    ((PASSED++))
fi

# Check SECRET_KEY length
if [ ${#SECRET_KEY} -ge 50 ]; then
    echo -e "${GREEN}✓${NC} SECRET_KEY length >= 50 characters"
    ((PASSED++))
else
    echo -e "${RED}✗${NC} SECRET_KEY length < 50 characters"
    ((FAILED++))
fi

# Check ALLOWED_HOSTS in production
if [ "$ENV" = "production" ]; then
    ALLOWED_HOSTS=$(docker compose -f $COMPOSE_FILE exec -T web python -c "from django.conf import settings; print(settings.ALLOWED_HOSTS)" 2>/dev/null | tr -d '\r')
    if [[ "$ALLOWED_HOSTS" == *"localhost"* ]] && [[ "$ALLOWED_HOSTS" != *"."* ]]; then
        echo -e "${RED}✗${NC} ALLOWED_HOSTS should not contain only localhost in production"
        ((FAILED++))
    else
        echo -e "${GREEN}✓${NC} ALLOWED_HOSTS configured for production"
        ((PASSED++))
    fi
fi
echo ""

echo -e "${BLUE}9. Backup Configuration${NC}"
echo "-----------------------------------"

# Check backup encryption key
BACKUP_KEY=$(docker compose -f $COMPOSE_FILE exec -T web python -c "from django.conf import settings; print(settings.BACKUP_ENCRYPTION_KEY)" 2>/dev/null | tr -d '\r')
if [ -n "$BACKUP_KEY" ] && [ "$BACKUP_KEY" != "None" ]; then
    echo -e "${GREEN}✓${NC} Backup encryption key configured"
    ((PASSED++))
else
    echo -e "${RED}✗${NC} Backup encryption key not configured"
    ((FAILED++))
fi
echo ""

echo -e "${BLUE}10. Monitoring${NC}"
echo "-----------------------------------"

# Check Prometheus metrics endpoint
if [ "$ENV" = "production" ] || [ "$ENV" = "staging" ]; then
    if run_test "Prometheus metrics" "docker compose -f $COMPOSE_FILE exec -T web curl -f http://localhost:8000/metrics"; then
        ((PASSED++))
    else
        ((FAILED++))
    fi
fi
echo ""

# Summary
echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo -e "Environment: ${YELLOW}$ENV${NC}"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed! Deployment is ready.${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please fix the issues before deploying.${NC}"
    exit 1
fi
