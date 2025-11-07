#!/bin/bash
# Simple Production Dockerfile Test Script

echo "=========================================="
echo "Production Dockerfile Tests"
echo "=========================================="
echo ""

PASSED=0
FAILED=0

# Test 1: Dockerfile.prod exists
echo "Test 1: Dockerfile.prod exists"
if [ -f "Dockerfile.prod" ]; then
    echo "✓ PASS"
    ((PASSED++))
else
    echo "✗ FAIL"
    ((FAILED++))
fi

# Test 2: Multi-stage build
echo "Test 2: Multi-stage build"
if grep -q "FROM.*as builder" Dockerfile.prod && grep -q "FROM.*as runtime" Dockerfile.prod; then
    echo "✓ PASS"
    ((PASSED++))
else
    echo "✗ FAIL"
    ((FAILED++))
fi

# Test 3: Non-root user
echo "Test 3: Non-root user configuration"
if grep -q "useradd.*appuser" Dockerfile.prod && grep -q "USER appuser" Dockerfile.prod; then
    echo "✓ PASS"
    ((PASSED++))
else
    echo "✗ FAIL"
    ((FAILED++))
fi

# Test 4: Health check
echo "Test 4: Health check configuration"
if grep -q "HEALTHCHECK" Dockerfile.prod; then
    echo "✓ PASS"
    ((PASSED++))
else
    echo "✗ FAIL"
    ((FAILED++))
fi

# Test 5: Gunicorn
echo "Test 5: Gunicorn configuration"
if grep -q "gunicorn" Dockerfile.prod; then
    echo "✓ PASS"
    ((PASSED++))
else
    echo "✗ FAIL"
    ((FAILED++))
fi

# Test 6: .dockerignore
echo "Test 6: .dockerignore exists"
if [ -f ".dockerignore" ]; then
    echo "✓ PASS"
    ((PASSED++))
else
    echo "✗ FAIL"
    ((FAILED++))
fi

# Test 7: Build image
echo "Test 7: Building Docker image..."
if docker build -f Dockerfile.prod -t jewelry-shop-test:latest . > /tmp/docker-build.log 2>&1; then
    echo "✓ PASS"
    ((PASSED++))
else
    echo "✗ FAIL - Check /tmp/docker-build.log"
    ((FAILED++))
    exit 1
fi

# Test 8: Image size
echo "Test 8: Image size check"
SIZE=$(docker images jewelry-shop-test:latest --format "{{.Size}}")
echo "  Image size: $SIZE"
echo "✓ PASS"
((PASSED++))

# Test 9: Non-root user in container
echo "Test 9: Container runs as non-root user"
USER=$(docker run --rm --entrypoint /bin/bash jewelry-shop-test:latest -c "whoami")
if [ "$USER" = "appuser" ]; then
    echo "✓ PASS - User: $USER"
    ((PASSED++))
else
    echo "✗ FAIL - User: $USER (expected appuser)"
    ((FAILED++))
fi

# Test 10: UID/GID
echo "Test 10: User ID and Group ID"
USER_ID=$(docker run --rm --entrypoint /bin/bash jewelry-shop-test:latest -c "id -u")
GROUP_ID=$(docker run --rm --entrypoint /bin/bash jewelry-shop-test:latest -c "id -g")
if [ "$USER_ID" = "1000" ] && [ "$GROUP_ID" = "1000" ]; then
    echo "✓ PASS - UID=$USER_ID, GID=$GROUP_ID"
    ((PASSED++))
else
    echo "✗ FAIL - UID=$USER_ID, GID=$GROUP_ID (expected 1000/1000)"
    ((FAILED++))
fi

# Test 11: Health check configured
echo "Test 11: Health check in image"
if docker inspect jewelry-shop-test:latest | grep -q "Healthcheck"; then
    echo "✓ PASS"
    ((PASSED++))
else
    echo "✗ FAIL"
    ((FAILED++))
fi

# Test 12: Gunicorn installed
echo "Test 12: Gunicorn installed"
VERSION=$(docker run --rm --entrypoint /bin/bash jewelry-shop-test:latest -c "gunicorn --version 2>&1" | grep "gunicorn")
if [ -n "$VERSION" ]; then
    echo "✓ PASS - $VERSION"
    ((PASSED++))
else
    echo "✗ FAIL"
    ((FAILED++))
fi

# Test 13: Required directories
echo "Test 13: Required directories exist"
if docker run --rm --entrypoint /bin/bash jewelry-shop-test:latest -c "test -d /app/staticfiles && test -d /app/media && test -d /app/logs && echo 'ok'" | grep -q "ok"; then
    echo "✓ PASS"
    ((PASSED++))
else
    echo "✗ FAIL"
    ((FAILED++))
fi

# Test 14: File permissions
echo "Test 14: File permissions"
OWNER=$(docker run --rm --entrypoint /bin/bash jewelry-shop-test:latest -c "stat -c '%U' /app")
if [ "$OWNER" = "appuser" ]; then
    echo "✓ PASS - /app owned by $OWNER"
    ((PASSED++))
else
    echo "✗ FAIL - /app owned by $OWNER (expected appuser)"
    ((FAILED++))
fi

# Test 15: Django installed
echo "Test 15: Django installed"
DJANGO_VER=$(docker run --rm --entrypoint /bin/bash jewelry-shop-test:latest -c "python -c 'import django; print(django.get_version())'")
if [ -n "$DJANGO_VER" ]; then
    echo "✓ PASS - Django $DJANGO_VER"
    ((PASSED++))
else
    echo "✗ FAIL"
    ((FAILED++))
fi

# Test 16: Build tools excluded
echo "Test 16: Build tools excluded from final image"
GCC=$(docker run --rm --entrypoint /bin/bash jewelry-shop-test:latest -c "which gcc 2>/dev/null || echo 'not_found'")
if [ "$GCC" = "not_found" ]; then
    echo "✓ PASS - gcc not in final image"
    ((PASSED++))
else
    echo "✗ FAIL - Build tools found in final image"
    ((FAILED++))
fi

# Cleanup
echo ""
echo "Cleaning up..."
docker rmi jewelry-shop-test:latest > /dev/null 2>&1 || true

# Summary
echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Tests Passed: $PASSED"
echo "Tests Failed: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "✓ All tests passed!"
    exit 0
else
    echo "✗ Some tests failed!"
    exit 1
fi
