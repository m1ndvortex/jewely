#!/bin/bash

# Real-World Security Testing Script
# Tests actual security measures in a running system

set -e

echo "========================================="
echo "Real-World Security Testing"
echo "========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if running in Docker
if [ -f /.dockerenv ]; then
    DOCKER_CMD=""
else
    DOCKER_CMD="docker compose exec -T web"
fi

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_header() {
    echo ""
    echo "========================================="
    echo "$1"
    echo "========================================="
    echo ""
}

OVERALL_STATUS=0

# 1. Test SQL Injection Prevention
print_header "1. Testing SQL Injection Prevention"
echo "Attempting SQL injection attacks..."

if $DOCKER_CMD pytest apps/core/tests/test_security_comprehensive.py::SQLInjectionPreventionTests -v --tb=no -q; then
    print_success "SQL injection prevention working"
else
    print_error "SQL injection tests failed"
    OVERALL_STATUS=1
fi

# 2. Test XSS Prevention
print_header "2. Testing XSS Prevention"
echo "Attempting XSS attacks..."

if $DOCKER_CMD pytest apps/core/tests/test_security_comprehensive.py::XSSPreventionTests -v --tb=no -q; then
    print_success "XSS prevention working"
else
    print_error "XSS prevention tests failed"
    OVERALL_STATUS=1
fi

# 3. Test CSRF Protection
print_header "3. Testing CSRF Protection"
echo "Testing CSRF token validation..."

if $DOCKER_CMD pytest apps/core/tests/test_security_comprehensive.py::CSRFProtectionTests -v --tb=no -q; then
    print_success "CSRF protection working"
else
    print_error "CSRF protection tests failed"
    OVERALL_STATUS=1
fi

# 4. Test Authentication Security
print_header "4. Testing Authentication Security"
echo "Testing password hashing, rate limiting, etc..."

if $DOCKER_CMD pytest apps/core/tests/test_security_comprehensive.py::AuthenticationSecurityTests -v --tb=no -q; then
    print_success "Authentication security working"
else
    print_error "Authentication security tests failed"
    OVERALL_STATUS=1
fi

# 5. Test Authorization Security
print_header "5. Testing Authorization & Tenant Isolation"
echo "Testing tenant isolation and access control..."

if $DOCKER_CMD pytest apps/core/tests/test_security_comprehensive.py::AuthorizationSecurityTests -v --tb=no -q; then
    print_success "Authorization security working"
else
    print_error "Authorization security tests failed"
    OVERALL_STATUS=1
fi

# 6. Test Session Security
print_header "6. Testing Session Security"
echo "Testing secure session cookies and management..."

if $DOCKER_CMD pytest apps/core/tests/test_security_comprehensive.py::SessionSecurityTests -v --tb=no -q; then
    print_success "Session security working"
else
    print_error "Session security tests failed"
    OVERALL_STATUS=1
fi

# 7. Test Input Validation
print_header "7. Testing Input Validation"
echo "Testing email, phone, numeric validation..."

if $DOCKER_CMD pytest apps/core/tests/test_security_comprehensive.py::InputValidationTests -v --tb=no -q; then
    print_success "Input validation working"
else
    print_error "Input validation tests failed"
    OVERALL_STATUS=1
fi

# 8. Test Security Headers
print_header "8. Testing Security Headers"
echo "Testing security headers middleware..."

if $DOCKER_CMD pytest apps/core/tests/test_security_headers.py -v --tb=no -q; then
    print_success "Security headers working"
else
    print_error "Security headers tests failed"
    OVERALL_STATUS=1
fi

# 9. Test Rate Limiting
print_header "9. Testing Rate Limiting"
echo "Testing API and login rate limiting..."

if $DOCKER_CMD pytest apps/core/tests/test_rate_limiting.py -v --tb=no -q; then
    print_success "Rate limiting working"
else
    print_error "Rate limiting tests failed"
    OVERALL_STATUS=1
fi

# 10. Run Bandit Security Scanner
print_header "10. Running Bandit Security Scanner"
echo "Scanning code for security issues..."

if $DOCKER_CMD bandit -r apps/core/ config/ -c .bandit -ll -q; then
    print_success "Bandit scan passed (no high/medium issues)"
else
    print_error "Bandit found security issues"
    OVERALL_STATUS=1
fi

# 11. Run pip-audit
print_header "11. Running pip-audit Dependency Scanner"
echo "Checking dependencies for vulnerabilities..."

if $DOCKER_CMD pip-audit --desc -q 2>&1 | grep -q "No known vulnerabilities found"; then
    print_success "No vulnerabilities in dependencies"
else
    echo "Checking pip-audit results..."
    $DOCKER_CMD pip-audit --desc 2>&1 || true
    print_error "Vulnerabilities found in dependencies"
    OVERALL_STATUS=1
fi

# Summary
print_header "Security Testing Summary"

if [ $OVERALL_STATUS -eq 0 ]; then
    print_success "ALL SECURITY TESTS PASSED!"
    echo ""
    echo "✓ SQL Injection Prevention: WORKING"
    echo "✓ XSS Prevention: WORKING"
    echo "✓ CSRF Protection: WORKING"
    echo "✓ Authentication Security: WORKING"
    echo "✓ Authorization & Tenant Isolation: WORKING"
    echo "✓ Session Security: WORKING"
    echo "✓ Input Validation: WORKING"
    echo "✓ Security Headers: WORKING"
    echo "✓ Rate Limiting: WORKING"
    echo "✓ Code Security Scan: CLEAN"
    echo "✓ Dependency Scan: CLEAN"
    echo ""
    print_success "System is secure and ready for production!"
else
    print_error "SOME SECURITY TESTS FAILED"
    echo ""
    echo "Please review the failures above and fix them before deploying."
fi

echo ""
echo "========================================="
echo "Security testing completed"
echo "========================================="

exit $OVERALL_STATUS
