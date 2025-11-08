# GitHub Actions CI/CD Workflows

This directory contains the automated CI/CD workflows for the Jewelry Shop Management SaaS Platform.

## Workflows Overview

### 1. CI/CD Pipeline (`ci.yml`)

**Triggers:**
- Push to `main`, `develop`, or `staging` branches
- Pull requests to `main` or `develop` branches

**Jobs:**

#### Code Quality & Security
- **Black**: Code formatting check
- **isort**: Import sorting check
- **Flake8**: Linting and code style
- **MyPy**: Static type checking
- **Bandit**: Security vulnerability scanning
- **Safety**: Dependency vulnerability scanning

#### Test & Coverage
- Runs full test suite with pytest
- Generates code coverage reports (HTML, XML, JSON)
- Uploads coverage to Codecov
- Fails if coverage drops below 75%
- Comments coverage on pull requests

#### Build Docker Images
- Builds Docker images for the application
- Pushes to GitHub Container Registry (ghcr.io)
- Tags images with branch name, SHA, and semantic version
- Uses layer caching for faster builds

#### Deploy to Staging
- **Automatic** on push to `main` branch
- Runs database migrations
- Performs rolling update deployment
- Runs smoke tests
- Notifies team via Slack

#### Deploy to Production
- **Manual approval required** (GitHub Environment protection)
- Creates backup before deployment
- Runs database migrations
- Performs rolling update deployment
- Automatic rollback on failure
- Notifies team via Slack and email

#### Container Security Scan
- Scans Docker images with Trivy
- Uploads results to GitHub Security tab

### 2. Security Scanning (`security-scan.yml`)

**Triggers:**
- Scheduled daily at 2 AM UTC
- Manual trigger via workflow_dispatch

**Jobs:**

#### Dependency Vulnerability Scan
- Runs `pip-audit` for Python dependencies
- Runs `safety` check for known vulnerabilities
- Creates GitHub issue if vulnerabilities found

#### Code Security Analysis
- Runs Bandit for code security issues
- Checks for high severity vulnerabilities
- Creates GitHub issue if critical issues found

#### Secret Scanning
- Runs Gitleaks to detect exposed secrets
- Scans full git history
- Creates critical issue if secrets detected

#### Security Team Notification
- Sends Slack alert if any scan fails
- Aggregates all security findings

### 3. Code Coverage Report (`coverage.yml`)

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches

**Jobs:**

#### Generate Coverage Report
- Runs full test suite with coverage
- Generates multiple report formats (HTML, XML, JSON)
- Creates coverage badge
- Uploads to Codecov
- Comments on pull requests with coverage details
- Fails if coverage below 75%
- Commits coverage badge to repository

## Required Secrets

Configure these secrets in your GitHub repository settings:

### Container Registry
- `GITHUB_TOKEN` - Automatically provided by GitHub Actions

### Code Coverage
- `CODECOV_TOKEN` - Token from codecov.io (optional but recommended)

### Kubernetes Deployment
- `KUBE_CONFIG_STAGING` - Base64-encoded kubeconfig for staging cluster
- `KUBE_CONFIG_PRODUCTION` - Base64-encoded kubeconfig for production cluster

### Notifications
- `SLACK_WEBHOOK_URL` - Slack webhook for deployment notifications
- `SLACK_SECURITY_WEBHOOK_URL` - Slack webhook for security alerts
- `EMAIL_USERNAME` - SMTP username for email notifications
- `EMAIL_PASSWORD` - SMTP password for email notifications

### Optional
- `GITLEAKS_LICENSE` - Gitleaks license key (if using commercial version)

## Environment Protection Rules

### Staging Environment
- No approval required
- Automatic deployment on `main` branch

### Production Environment
- **Manual approval required** from designated reviewers
- Deployment only from `main` branch
- Minimum 1 reviewer approval

## Setting Up Environments

1. Go to repository Settings → Environments
2. Create `staging` environment:
   - No protection rules
   - Add `KUBE_CONFIG_STAGING` secret
3. Create `production` environment:
   - Enable "Required reviewers"
   - Add production team members as reviewers
   - Add `KUBE_CONFIG_PRODUCTION` secret

## Workflow Artifacts

Each workflow run produces artifacts that are retained for 30-90 days:

- **Coverage Reports**: HTML coverage reports
- **Security Reports**: Bandit, Safety, pip-audit JSON reports
- **Test Results**: pytest XML reports

## Monitoring Workflow Status

### Badges

Add these badges to your README.md:

```markdown
![CI/CD Pipeline](https://github.com/YOUR_ORG/YOUR_REPO/actions/workflows/ci.yml/badge.svg)
![Security Scan](https://github.com/YOUR_ORG/YOUR_REPO/actions/workflows/security-scan.yml/badge.svg)
![Coverage](./coverage.svg)
```

### Notifications

- **Slack**: Deployment and security notifications
- **Email**: Production deployment notifications
- **GitHub Issues**: Automatic issue creation for security findings

## Rollback Procedure

If a production deployment fails:

1. Automatic rollback is triggered
2. Previous version is restored
3. Team is notified via Slack and email

Manual rollback:

```bash
# Get deployment history
kubectl rollout history deployment/web -n production

# Rollback to previous version
kubectl rollout undo deployment/web -n production

# Rollback to specific revision
kubectl rollout undo deployment/web -n production --to-revision=2
```

## Local Testing

Test workflows locally using [act](https://github.com/nektos/act):

```bash
# Install act
brew install act  # macOS
# or
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Run CI workflow
act push

# Run specific job
act -j test

# Run with secrets
act -s GITHUB_TOKEN=your_token
```

## Troubleshooting

### Tests Failing in CI but Passing Locally

1. Check service versions (PostgreSQL, Redis)
2. Verify environment variables in workflow
3. Check for timezone or locale differences
4. Review workflow logs for specific errors

### Docker Build Failing

1. Check Dockerfile syntax
2. Verify all dependencies in requirements.txt
3. Check for missing files in .dockerignore
4. Review build logs for specific errors

### Deployment Failing

1. Check kubectl configuration
2. Verify Kubernetes secrets are set
3. Check pod logs: `kubectl logs -n production deployment/web`
4. Verify database migrations completed
5. Check service health endpoints

### Coverage Dropping

1. Review coverage report artifacts
2. Check which files have reduced coverage
3. Add tests for uncovered code
4. Update coverage threshold if intentional

## Best Practices

1. **Always run tests locally** before pushing
2. **Keep workflows fast** - use caching and parallel jobs
3. **Monitor workflow costs** - GitHub Actions has usage limits
4. **Review security reports** regularly
5. **Keep secrets secure** - never commit secrets to repository
6. **Test deployment process** in staging first
7. **Document workflow changes** in this README

## Maintenance

### Updating Dependencies

When updating workflow dependencies:

1. Update action versions in workflow files
2. Test in a feature branch first
3. Review changelog for breaking changes
4. Update this README if needed

### Adding New Workflows

1. Create workflow file in `.github/workflows/`
2. Test with `act` or in a feature branch
3. Document in this README
4. Add required secrets to repository settings

## Support

For issues with workflows:

1. Check workflow run logs in GitHub Actions tab
2. Review this README for troubleshooting steps
3. Contact DevOps team
4. Create issue with `ci-cd` label
