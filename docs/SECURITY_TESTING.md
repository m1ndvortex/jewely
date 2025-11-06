# Security Testing Guide

## Overview

This document describes the comprehensive security testing strategy for the jewelry management SaaS platform. Our security testing approach includes automated scanning, penetration testing, and continuous security validation.

**Requirements:** 25 (Security Hardening and Compliance), 28 (Comprehensive Testing)

## Table of Contents

1. [Security Testing Tools](#security-testing-tools)
2. [Running Security Scans](#running-security-scans)
3. [Security Test Categories](#security-test-categories)
4. [Penetration Testing](#penetration-testing)
5. [Continuous Security Monitoring](#continuous-security-monitoring)
6. [Security Best Practices](#security-best-practices)
7. [Vulnerability Response](#vulnerability-response)

## Security Testing Tools

### 1. Bandit - Python Security Scanner

**Purpose:** Static analysis tool for finding common security issues in Python code.

**What it checks:**
- Hardcoded passwords and secrets
- SQL injection vulnerabilities
- Shell injection risks
- Insecure cryptographic functions
- Unsafe deserialization
- XML vulnerabilities
- And 100+ other security issues

**Configuration:** `.bandit` file in project root

**Usage:**
```bash
# Run Bandit scan
docker compose exec web bandit -r apps/ config/ -c .bandit

# Generate detailed report
docker compose exec web bandit -r apps/ config/ -c .bandit -f html -o bandit_report.html
```

### 2. pip-audit - Dependency Vulnerability Scanner

**Purpose:** Checks Python dependencies for known security vulnerabilities using the PyPI Advisory Database.

**What it checks:**
- Known CVEs in installed packages
- Outdated packages with security fixes
- Vulnerable dependency versions
- Transitive dependencies

**Usage:**
```bash
# Check for vulnerabilities
docker compose exec web pip-audit

# Generate JSON report
docker compose exec web pip-audit --format json

# Check specific requirements file
docker compose exec web pip-audit -r requirements.txt
```

### 3. Pytest Security Test Suite

**Purpose:** Comprehensive automated security tests.

**Test Files:**
- `apps/core/tests/test_security_comprehensive.py` - Core security tests
- `tests/security/test_penetration.py` - Penetration testing scenarios
- `apps/core/tests/test_security_headers.py` - Security headers validation
- `apps/core/tests/test_rate_limiting.py` - Rate limiting tests
- `apps/core/tests/test_secrets_management.py` - Secrets management tests

**Usage:**
```bash
# Run all security tests
docker compose exec web pytest apps/core/tests/test_security_comprehensive.py -v

# Run penetration tests
docker compose exec web pytest tests/security/test_penetration.py -v

# Run all security-related tests
docker compose exec web pytest -k security -v
```

## Running Security Scans

### Quick Start

Run the comprehensive security scan script:

```bash
# From host machine
./scripts/run_security_scans.sh

# From inside Docker container
docker compose exec web bash /app/scripts/run_security_scans.sh
```

This script runs:
1. Bandit security scanner
2. pip-audit dependency checker
3. Comprehensive security tests
4. Penetration tests
5. Security headers validation
6. Rate limiting tests
7. Secrets management tests

### Individual Scans

#### 1. Run Bandit Only
```bash
docker compose exec web bandit -r apps/ config/ -c .bandit -f txt
```

#### 2. Run pip-audit Only
```bash
docker compose exec web pip-audit
```

#### 3. Run Security Tests Only
```bash
docker compose exec web pytest apps/core/tests/test_security_comprehensive.py -v
```

#### 4. Run Penetration Tests Only
```bash
docker compose exec web pytest tests/security/test_penetration.py -v
```

### Automated Scanning

Security scans should be run:
- **On every commit** (via pre-commit hooks)
- **In CI/CD pipeline** (before deployment)
- **Weekly scheduled scans** (via cron job)
- **Before production releases** (manual verification)

## Security Test Categories

### 1. SQL Injection Prevention

**Tests:** `SQLInjectionPreventionTests`

**What we test:**
- SQL injection through search queries
- SQL injection through form inputs
- ORM query safety
- Raw SQL parameterization

**Example attacks tested:**
```python
"'; DROP TABLE inventory_items; --"
"1' OR '1'='1"
"' UNION SELECT * FROM users--"
```

**Expected result:** All attacks blocked by Django ORM

### 2. XSS (Cross-Site Scripting) Prevention

**Tests:** `XSSPreventionTests`

**What we test:**
- XSS through product names
- XSS through customer notes
- XSS through form inputs
- Template auto-escaping
- Security headers (CSP, X-XSS-Protection)

**Example attacks tested:**
```javascript
<script>alert('XSS')</script>
<img src=x onerror=alert('XSS')>
<svg onload=alert('XSS')>
```

**Expected result:** All scripts escaped in HTML output

### 3. CSRF (Cross-Site Request Forgery) Protection

**Tests:** `CSRFProtectionTests`

**What we test:**
- CSRF token presence in forms
- CSRF token validation on POST requests
- CSRF protection for AJAX requests
- CSRF token rotation

**Expected result:** All POST requests without valid CSRF token rejected

### 4. Authentication Security

**Tests:** `AuthenticationSecurityTests`

**What we test:**
- Weak password rejection
- Password hashing (Argon2)
- Login rate limiting
- Session timeout
- MFA enforcement for admins
- Brute force protection

**Expected result:** Strong authentication mechanisms in place

### 5. Authorization Security

**Tests:** `AuthorizationSecurityTests`

**What we test:**
- Tenant data isolation (RLS)
- Role-based access control
- Object-level permissions
- Cross-tenant access prevention

**Expected result:** Users can only access authorized data

### 6. Session Security

**Tests:** `SessionSecurityTests`

**What we test:**
- Secure session cookies (HttpOnly, Secure, SameSite)
- Session regeneration on login
- Session invalidation on logout
- Session fixation prevention

**Expected result:** Sessions properly secured

### 7. Input Validation

**Tests:** `InputValidationTests`

**What we test:**
- Email validation
- Phone number validation
- Numeric field validation
- File upload validation

**Expected result:** All inputs properly validated

## Penetration Testing

### Authentication Bypass Tests

**Tests:** `AuthenticationBypassTests`

**Attack scenarios:**
- Direct URL access without login
- Session hijacking attempts
- Password reset token exploitation
- Brute force attacks

**Expected result:** All bypass attempts blocked

### Authorization Escalation Tests

**Tests:** `AuthorizationEscalationTests`

**Attack scenarios:**
- Employee accessing admin functions
- Role modification attempts
- Cross-tenant data access
- Privilege escalation

**Expected result:** All escalation attempts blocked

### Data Exfiltration Tests

**Tests:** `DataExfiltrationTests`

**Attack scenarios:**
- Bulk data export without permission
- API rate limit bypass
- Sensitive data in logs

**Expected result:** Data exfiltration prevented

### Injection Attack Tests

**Tests:** `InjectionAttackTests`

**Attack scenarios:**
- Command injection
- LDAP injection
- XML injection
- Template injection

**Expected result:** All injection attacks blocked

### Session Management Tests

**Tests:** `SessionManagementTests`

**Attack scenarios:**
- Concurrent session exploitation
- Session fixation
- Session not invalidated on logout

**Expected result:** Sessions properly managed

## Continuous Security Monitoring

### 1. Dependency Scanning

**Frequency:** Daily

**Tool:** pip-audit

**Action:** Automated alerts for new vulnerabilities

```bash
# Add to cron
0 2 * * * docker compose exec web pip-audit --format json > /var/log/pip_audit_$(date +\%Y\%m\%d).json
```

### 2. Code Security Scanning

**Frequency:** On every commit

**Tool:** Bandit (via pre-commit hooks)

**Configuration:** `.pre-commit-config.yaml`

```yaml
- repo: https://github.com/PyCQA/bandit
  rev: 1.7.7
  hooks:
    - id: bandit
      args: ['-c', '.bandit']
```

### 3. Security Test Suite

**Frequency:** On every commit, before deployment

**Tool:** Pytest

**CI/CD Integration:**
```yaml
# .github/workflows/security.yml
name: Security Tests
on: [push, pull_request]
jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run security tests
        run: docker compose exec web pytest -k security -v
```

### 4. Penetration Testing

**Frequency:** Monthly, before major releases

**Tool:** Custom penetration test suite

**Process:**
1. Run automated penetration tests
2. Manual security review
3. Third-party security audit (annually)

## Security Best Practices

### 1. Secure Coding Practices

✅ **DO:**
- Use Django ORM for database queries
- Use parameterized queries for raw SQL
- Escape all user inputs in templates
- Validate all inputs server-side
- Use CSRF protection for all forms
- Hash passwords with Argon2
- Use HTTPS for all communications
- Implement rate limiting
- Log security events

❌ **DON'T:**
- Use string concatenation for SQL queries
- Trust user input
- Store passwords in plain text
- Disable CSRF protection
- Use weak hashing algorithms (MD5, SHA1)
- Expose sensitive data in logs
- Use HTTP for sensitive data

### 2. Dependency Management

✅ **DO:**
- Keep dependencies up to date
- Review security advisories
- Use `safety check` regularly
- Pin dependency versions
- Review dependency licenses

❌ **DON'T:**
- Use outdated packages
- Ignore security warnings
- Use packages with known vulnerabilities

### 3. Configuration Security

✅ **DO:**
- Use environment variables for secrets
- Encrypt sensitive configuration
- Disable DEBUG in production
- Configure ALLOWED_HOSTS properly
- Enable security headers
- Use strong SECRET_KEY

❌ **DON'T:**
- Hardcode secrets in code
- Commit secrets to version control
- Use default SECRET_KEY
- Allow all hosts (*)

### 4. Authentication & Authorization

✅ **DO:**
- Enforce strong passwords
- Implement MFA for admins
- Use secure session management
- Implement rate limiting
- Log authentication events
- Use role-based access control

❌ **DON'T:**
- Allow weak passwords
- Store passwords in plain text
- Use predictable session IDs
- Allow unlimited login attempts

## Vulnerability Response

### Severity Levels

**Critical:** Immediate action required
- Remote code execution
- Authentication bypass
- Data breach potential

**High:** Fix within 24 hours
- SQL injection
- XSS vulnerabilities
- CSRF vulnerabilities

**Medium:** Fix within 1 week
- Information disclosure
- Weak encryption
- Missing security headers

**Low:** Fix in next release
- Minor configuration issues
- Non-critical warnings

### Response Process

1. **Detection**
   - Automated scan alerts
   - Security test failures
   - Manual discovery
   - Third-party reports

2. **Assessment**
   - Verify vulnerability
   - Determine severity
   - Assess impact
   - Identify affected systems

3. **Remediation**
   - Develop fix
   - Test fix thoroughly
   - Deploy to production
   - Verify fix effectiveness

4. **Communication**
   - Notify affected users (if applicable)
   - Document in changelog
   - Update security documentation
   - Report to security team

5. **Prevention**
   - Add test case for vulnerability
   - Update security guidelines
   - Review similar code
   - Improve detection mechanisms

## Security Checklist

### Before Deployment

- [ ] All security tests passing
- [ ] Bandit scan clean
- [ ] Safety check clean
- [ ] No hardcoded secrets
- [ ] DEBUG = False
- [ ] ALLOWED_HOSTS configured
- [ ] Security headers enabled
- [ ] HTTPS enforced
- [ ] Rate limiting active
- [ ] Backups configured
- [ ] Monitoring enabled
- [ ] Audit logging active

### Regular Maintenance

- [ ] Weekly dependency scans
- [ ] Monthly penetration tests
- [ ] Quarterly security audits
- [ ] Annual third-party assessment
- [ ] Review security logs daily
- [ ] Update dependencies monthly
- [ ] Review access controls quarterly

## Resources

### Documentation
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Django Security](https://docs.djangoproject.com/en/4.2/topics/security/)
- [Bandit Documentation](https://bandit.readthedocs.io/)
- [pip-audit Documentation](https://pypi.org/project/pip-audit/)

### Tools
- [Bandit](https://github.com/PyCQA/bandit) - Python security scanner
- [pip-audit](https://github.com/pypa/pip-audit) - Dependency vulnerability scanner
- [OWASP ZAP](https://www.zaproxy.org/) - Web app security scanner
- [Burp Suite](https://portswigger.net/burp) - Penetration testing tool

### Training
- OWASP Security Training
- Django Security Best Practices
- Secure Coding Guidelines
- Penetration Testing Fundamentals

## Support

For security issues or questions:
- **Security Team:** security@example.com
- **Emergency:** +1-XXX-XXX-XXXX
- **Bug Bounty:** https://example.com/security/bounty

---

**Last Updated:** 2024
**Version:** 1.0
**Owner:** Security Team
