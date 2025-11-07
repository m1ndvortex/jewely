#!/bin/bash

# ============================================================================
# Production Dockerfile Test Script
# ============================================================================
# This script tests the production Dockerfile to ensure it meets all
# requirements for task 32.1:
# - Multi-stage build optimization
# - Minimal image size
# - Health checks configured
# - Runs as non-root user
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0

# Function to print test results
print_test() {
    local test_name=$1
    local result=$2
    local message=$3
    
    if [ "$result" = "PASS" ]; then
        echo -e "${GREEN}✓ PASS${NC}: $test_name"
        [ -n "$message" ] && echo "  → $message"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC}: $test_name"
        [ -n "$message" ] && echo "  → $message"
        ((TESTS_FAILED++))
    fi
}

echo "============================================================================"
echo "Production Dockerfile Tests"
echo "============================================================================"
echo ""

# ============================================================================
# Test 1: Dockerfile.prod exists
# ============================================================================
echo "Test 1: Checking if Dockerfile.prod exists..."
if [ -f "Dockerfile.prod" ]; then
    print_test "Dockerfile.prod exists" "PASS" "File found at root directory"
else
    print_test "Dockerfile.prod exists" "FAIL" "File not found"
    exit 1
fi

# ============================================================================
# Test 2: Multi-stage build verification
# ============================================================================
echo ""
echo "Test 2: Verifying multi-stage build..."
if grep -q "FROM.*as builder" Dockerfile.prod && grep -q "FROM.*as runtime" Dockerfile.prod; then
    print_test "Multi-stage build" "PASS" "Builder and runtime stages found"
else
    print_test "Multi-stage build" "FAIL" "Multi-stage build not properly configured"
fi

# ============================================================================
# Test 3: Non-root user configuration
# ============================================================================
echo ""
echo "Test 3: Checking non-root user configuration..."
if grep -q "useradd.*appuser" Dockerfile.prod && grep -q "USER appuser" Dockerfile.prod; then
    print_test "Non-root user" "PASS" "appuser created and set as default user"
else
    print_test "Non-root user" "FAIL" "Non-root user not properly configured"
fi

# ============================================================================
# Test 4: Health check configuration
# ============================================================================
echo ""
echo "Test 4: Verifying health check configuration..."
if grep -q "HEALTHCHECK" Dockerfile.prod; then
    print_test "Health check" "PASS" "HEALTHCHECK instruction found"
else
    print_test "Health check" "FAIL" "HEALTHCHECK instruction not found"
fi

# ============================================================================
# Test 5: Gunicorn configuration
# ============================================================================
echo ""
echo "Test 5: Checking Gunicorn production server..."
if grep -q "gunicorn" Dockerfile.prod; then
    print_test "Gunicorn server" "PASS" "Gunicorn configured as production server"
else
    print_test "Gunicorn server" "FAIL" "Gunicorn not configured"
fi

# ============================================================================
# Test 6: .dockerignore exists
# ============================================================================
echo ""
echo "Test 6: Checking .dockerignore file..."
if [ -f ".dockerignore" ]; then
    print_test ".dockerignore exists" "PASS" "File found at root directory"
else
    print_test ".dockerignore exists" "FAIL" "File not found"
fi

# ============================================================================
# Test 7: Build the production image
# ============================================================================
echo ""
echo "Test 7: Building production Docker image..."
echo "This may take a few minutes..."

if DOCKER_BUILDKIT=1 docker build -f Dockerfile.prod -t jewelry-shop-test:latest . > /tmp/docker-build.log 2>&1; then
    print_test "Docker build" "PASS" "Image built successfully"
else
    print_test "Docker build" "FAIL" "Build failed - check /tmp/docker-build.log"
    cat /tmp/docker-build.log
    exit 1
fi

# ============================================================================
# Test 8: Image size verification
# ============================================================================
echo ""
echo "Test 8: Checking image size..."
IMAGE_SIZE=$(docker images jewelry-shop-test:latest --format "{{.Size}}")
IMAGE_SIZE_MB=$(docker images jewelry-shop-test:latest --format "{{.Size}}" | sed 's/MB//' | sed 's/GB/*1024/' | bc 2>/dev/null || echo "0")

echo "  Image size: $IMAGE_SIZE"

# Check if image is reasonably sized (should be under 800MB for production)
if [ -n "$IMAGE_SIZE_MB" ] && [ $(echo "$IMAGE_SIZE_MB < 800" | bc -l) -eq 1 ]; then
    print_test "Image size optimization" "PASS" "Image size is $IMAGE_SIZE (under 800MB)"
else
    print_test "Image size optimization" "WARN" "Image size is $IMAGE_SIZE (consider further optimization)"
fi

# ============================================================================
# Test 9: Verify non-root user in running container
# ============================================================================
echo ""
echo "Test 9: Verifying container runs as non-root user..."

# Check user without starting the full application
CONTAINER_USER=$(docker run --rm --entrypoint /bin/bash jewelry-shop-test:latest -c "whoami" 2>/dev/null || echo "error")

if [ "$CONTAINER_USER" = "appuser" ]; then
    print_test "Container user" "PASS" "Container runs as appuser"
else
    print_test "Container user" "FAIL" "Container runs as $CONTAINER_USER (expected appuser)"
fi

# Verify UID/GID
USER_ID=$(docker run --rm --entrypoint /bin/bash jewelry-shop-test:latest -c "id -u" 2>/dev/null || echo "error")
GROUP_ID=$(docker run --rm --entrypoint /bin/bash jewelry-shop-test:latest -c "id -g" 2>/dev/null || echo "error")

if [ "$USER_ID" = "1000" ] && [ "$GROUP_ID" = "1000" ]; then
    print_test "User ID/Group ID" "PASS" "UID=1000, GID=1000"
else
    print_test "User ID/Group ID" "FAIL" "UID=$USER_ID, GID=$GROUP_ID (expected 1000/1000)"
fi

# ============================================================================
# Test 10: Health check configuration
# ============================================================================
echo ""
echo "Test 10: Verifying health check configuration..."

HEALTH_CHECK=$(docker inspect jewelry-shop-test:latest | grep -c "Healthcheck" || echo "0")

if [ "$HEALTH_CHECK" -gt 0 ]; then
    print_test "Health check config" "PASS" "HEALTHCHECK instruction configured"
else
    print_test "Health check config" "FAIL" "HEALTHCHECK instruction not found"
fi

# ============================================================================
# Test 11: Verify Gunicorn is installed
# ============================================================================
echo ""
echo "Test 11: Verifying Gunicorn installation..."

GUNICORN_VERSION=$(docker run --rm --entrypoint /bin/bash jewelry-shop-test:latest -c "gunicorn --version 2>&1" | grep -o "gunicorn.*" || echo "error")

if [ "$GUNICORN_VERSION" != "error" ]; then
    print_test "Gunicorn installation" "PASS" "$GUNICORN_VERSION"
else
    print_test "Gunicorn installation" "FAIL" "Gunicorn not installed"
fi

# ============================================================================
# Test 12: Verify static files directory exists
# ============================================================================
echo ""
echo "Test 12: Checking static files directory..."

STATIC_DIR=$(docker run --rm --entrypoint /bin/bash jewelry-shop-test:latest -c "test -d /app/staticfiles && echo 'exists' || echo 'missing'" 2>/dev/null)

if [ "$STATIC_DIR" = "exists" ]; then
    print_test "Static files directory" "PASS" "/app/staticfiles directory exists"
else
    print_test "Static files directory" "FAIL" "/app/staticfiles directory missing"
fi

# ============================================================================
# Test 13: Verify file permissions
# ============================================================================
echo ""
echo "Test 13: Checking file permissions..."

APP_OWNER=$(docker run --rm --entrypoint /bin/bash jewelry-shop-test:latest -c "stat -c '%U' /app" 2>/dev/null || echo "error")

if [ "$APP_OWNER" = "appuser" ]; then
    print_test "File permissions" "PASS" "/app directory owned by appuser"
else
    print_test "File permissions" "FAIL" "/app directory owned by $APP_OWNER (expected appuser)"
fi

# ============================================================================
# Test 14: Verify required directories exist
# ============================================================================
echo ""
echo "Test 14: Checking required directories..."

DIRS_CHECK=$(docker run --rm --entrypoint /bin/bash jewelry-shop-test:latest -c "test -d /app/staticfiles && test -d /app/media && test -d /app/logs && echo 'all_exist' || echo 'missing'" 2>/dev/null)

if [ "$DIRS_CHECK" = "all_exist" ]; then
    print_test "Required directories" "PASS" "All required directories exist"
else
    print_test "Required directories" "FAIL" "Some required directories are missing"
fi

# ============================================================================
# Test 15: Verify Python packages installed
# ============================================================================
echo ""
echo "Test 15: Verifying Python packages..."

DJANGO_VERSION=$(docker run --rm --entrypoint /bin/bash jewelry-shop-test:latest -c "python -c 'import django; print(django.get_version())'" 2>/dev/null || echo "error")

if [ "$DJANGO_VERSION" != "error" ]; then
    print_test "Python packages" "PASS" "Django $DJANGO_VERSION installed"
else
    print_test "Python packages" "FAIL" "Django not properly installed"
fi

# ============================================================================
# Test 16: Verify build tools not in final image
# ============================================================================
echo ""
echo "Test 16: Verifying build tools excluded..."

GCC_CHECK=$(docker run --rm --entrypoint /bin/bash jewelry-shop-test:latest -c "which gcc 2>/dev/null || echo 'not_found'" 2>/dev/null)

if [ "$GCC_CHECK" = "not_found" ]; then
    print_test "Build tools excluded" "PASS" "gcc not found in final image (multi-stage working)"
else
    print_test "Build tools excluded" "FAIL" "Build tools found in final image"
fi

# ============================================================================
# Cleanup
# ============================================================================
echo ""
echo "Cleaning up..."
docker rmi jewelry-shop-test:latest > /dev/null 2>&1 || true

# ============================================================================
# Summary
# ============================================================================
echo ""
echo "============================================================================"
echo "Test Summary"
echo "============================================================================"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo "Production Dockerfile is ready for deployment."
    exit 0
else
    echo -e "${RED}✗ Some tests failed!${NC}"
    echo ""
    echo "Please review the failures above and fix the issues."
    exit 1
fi
