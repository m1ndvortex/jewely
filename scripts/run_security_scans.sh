#!/bin/bash

# Security Scanning Script
# Runs comprehensive security scans using Bandit and Safety
# Requirements: 25 (Security Hardening), 28 (Comprehensive Testing)

set -e

echo "========================================="
echo "Security Scanning Suite"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running in Docker
if [ -f /.dockerenv ]; then
    echo "Running inside Docker container"
    DOCKER_CMD=""
else
    echo "Running on host machine - using Docker"
    DOCKER_CMD="docker compose exec -T web"
fi

# Function to print section headers
print_header() {
    echo ""
    echo "========================================="
    echo "$1"
    echo "========================================="
    echo ""
}

# Function to print success message
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Function to print error message
print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Function to print warning message
print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Track overall status
OVERALL_STATUS=0

# 1. Run Bandit security scanner
print_header "1. Running Bandit Security Scanner"
echo "Scanning Python code for security issues..."

if $DOCKER_CMD bandit -r apps/ config/ -c .bandit -f txt -o /tmp/bandit_report.txt; then
    print_success "Bandit scan completed"
    $DOCKER_CMD cat /tmp/bandit_report.txt
    
    # Check if any issues were found
    if $DOCKER_CMD grep -q "No issues identified" /tmp/bandit_report.txt; then
        print_success "No security issues found by Bandit"
    else
        print_warning "Bandit found potential security issues - review report above"
        OVERALL_STATUS=1
    fi
else
    print_error "Bandit scan failed"
    OVERALL_STATUS=1
fi

# 2. Run pip-audit dependency checker
print_header "2. Running pip-audit Dependency Checker"
echo "Checking for known security vulnerabilities in dependencies..."

if $DOCKER_CMD pip-audit --format json > /tmp/pip_audit_report.json 2>&1; then
    print_success "pip-audit check completed"
    $DOCKER_CMD cat /tmp/pip_audit_report.json
    print_success "No known vulnerabilities found in dependencies"
else
    print_warning "pip-audit found vulnerabilities in dependencies"
    $DOCKER_CMD cat /tmp/pip_audit_report.json || true
    print_warning "Review vulnerabilities and update dependencies"
    OVERALL_STATUS=1
fi

# 3. Run comprehensive security tests
print_header "3. Running Comprehensive Security Tests"
echo "Testing SQL injection, XSS, CSRF, and other vulnerabilities..."

if $DOCKER_CMD pytest apps/core/tests/test_security_comprehensive.py -v --tb=short; then
    print_success "All security tests passed"
else
    print_error "Some security tests failed"
    OVERALL_STATUS=1
fi

# 4. Run penetration tests
print_header "4. Running Penetration Tests"
echo "Simulating real-world attack scenarios..."

if $DOCKER_CMD pytest tests/security/test_penetration.py -v --tb=short; then
    print_success "All penetration tests passed (attacks blocked successfully)"
else
    print_error "Some penetration tests failed (vulnerabilities detected)"
    OVERALL_STATUS=1
fi

# 5. Check security headers
print_header "5. Checking Security Headers"
echo "Verifying security headers are properly configured..."

if $DOCKER_CMD pytest apps/core/tests/test_security_headers.py -v --tb=short; then
    print_success "Security headers properly configured"
else
    print_error "Security headers test failed"
    OVERALL_STATUS=1
fi

# 6. Check rate limiting
print_header "6. Checking Rate Limiting"
echo "Verifying rate limiting is working..."

if $DOCKER_CMD pytest apps/core/tests/test_rate_limiting.py -v --tb=short; then
    print_success "Rate limiting working correctly"
else
    print_error "Rate limiting test failed"
    OVERALL_STATUS=1
fi

# 7. Check secrets management
print_header "7. Checking Secrets Management"
echo "Verifying secrets are properly managed..."

if $DOCKER_CMD pytest apps/core/tests/test_secrets_management.py -v --tb=short; then
    print_success "Secrets management working correctly"
else
    print_error "Secrets management test failed"
    OVERALL_STATUS=1
fi

# 8. Generate security report
print_header "8. Generating Security Report"

REPORT_FILE="security_report_$(date +%Y%m%d_%H%M%S).txt"

cat > "$REPORT_FILE" << EOF
========================================
Security Scan Report
========================================
Date: $(date)
Scan Duration: $SECONDS seconds

1. Bandit Security Scanner
---------------------------
$(cat /tmp/bandit_report.txt 2>/dev/null || echo "Report not available")

2. pip-audit Dependency Checker
-------------------------------
$(cat /tmp/pip_audit_report.json 2>/dev/null || echo "Report not available")

3. Security Test Results
-------------------------
See test output above

4. Penetration Test Results
----------------------------
See test output above

========================================
Overall Status: $([ $OVERALL_STATUS -eq 0 ] && echo "PASS" || echo "FAIL")
========================================
EOF

print_success "Security report generated: $REPORT_FILE"

# Print summary
print_header "Security Scan Summary"

if [ $OVERALL_STATUS -eq 0 ]; then
    print_success "All security scans passed!"
    print_success "No critical vulnerabilities detected"
    echo ""
    echo "✓ Bandit scan: PASS"
    echo "✓ pip-audit check: PASS"
    echo "✓ Security tests: PASS"
    echo "✓ Penetration tests: PASS"
    echo "✓ Security headers: PASS"
    echo "✓ Rate limiting: PASS"
    echo "✓ Secrets management: PASS"
else
    print_error "Some security scans failed!"
    print_warning "Review the output above and fix identified issues"
    echo ""
    echo "Please address all security issues before deploying to production"
fi

echo ""
echo "========================================="
echo "Security scan completed"
echo "========================================="

exit $OVERALL_STATUS
