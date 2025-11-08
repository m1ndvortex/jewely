# GitHub Actions Setup Checklist

Use this checklist to configure GitHub Actions for the Jewelry Shop Management Platform.

## Prerequisites

- [ ] GitHub repository created
- [ ] Admin access to repository
- [ ] Kubernetes clusters ready (staging and production)
- [ ] Container registry access (GitHub Container Registry)
- [ ] Slack workspace for notifications
- [ ] Email SMTP credentials

## Step 1: Configure Repository Secrets

Go to **Settings → Secrets and variables → Actions**

### Required Secrets

- [ ] `KUBE_CONFIG_STAGING` - Base64-encoded kubeconfig for staging
  ```bash
  cat ~/.kube/config-staging | base64 | pbcopy
  ```

- [ ] `KUBE_CONFIG_PRODUCTION` - Base64-encoded kubeconfig for production
  ```bash
  cat ~/.kube/config-production | base64 | pbcopy
  ```

- [ ] `SLACK_WEBHOOK_URL` - Slack webhook for deployment notifications
  - Create at: https://api.slack.com/messaging/webhooks
  - Channel: #deployments

- [ ] `SLACK_SECURITY_WEBHOOK_URL` - Slack webhook for security alerts
  - Create at: https://api.slack.com/messaging/webhooks
  - Channel: #security-alerts

- [ ] `EMAIL_USERNAME` - SMTP username for email notifications
  - Example: notifications@jewelry-shop.example.com

- [ ] `EMAIL_PASSWORD` - SMTP password
  - Use app-specific password if using Gmail

### Optional Secrets

- [ ] `CODECOV_TOKEN` - Token from codecov.io
  - Sign up at: https://codecov.io
  - Add repository
  - Copy token

- [ ] `GITLEAKS_LICENSE` - Gitleaks commercial license (if applicable)
  - Only needed for commercial version

## Step 2: Configure Environments

### Staging Environment

Go to **Settings → Environments → New environment**

- [ ] Create environment named `staging`
- [ ] **Protection rules:** None (automatic deployment)
- [ ] **Environment secrets:** None needed (uses repository secrets)
- [ ] **Deployment branches:** Only `main` branch

### Production Environment

- [ ] Create environment named `production`
- [ ] **Protection rules:**
  - [x] Required reviewers (add team members)
  - [x] Wait timer: 0 minutes (optional)
  - [ ] Prevent self-review (optional)
- [ ] **Environment secrets:** None needed (uses repository secrets)
- [ ] **Deployment branches:** Only `main` branch
- [ ] **Reviewers:** Add at least 2 team members

## Step 3: Configure Branch Protection

Go to **Settings → Branches → Add rule**

### Main Branch Protection

- [ ] Branch name pattern: `main`
- [ ] **Require pull request before merging**
  - [x] Require approvals: 1
  - [x] Dismiss stale reviews
  - [x] Require review from Code Owners
- [ ] **Require status checks to pass**
  - [x] Require branches to be up to date
  - [x] Status checks:
    - `Code Quality & Security`
    - `Run Tests & Coverage`
    - `Code Quality Checks` (from lint.yml)
- [ ] **Require conversation resolution**
- [ ] **Require signed commits** (optional)
- [ ] **Include administrators** (recommended)

### Develop Branch Protection

- [ ] Branch name pattern: `develop`
- [ ] **Require pull request before merging**
  - [x] Require approvals: 1
- [ ] **Require status checks to pass**
  - [x] Status checks:
    - `Code Quality & Security`
    - `Run Tests & Coverage`

## Step 4: Enable GitHub Features

### Security Features

Go to **Settings → Security**

- [ ] **Dependabot alerts:** Enabled
- [ ] **Dependabot security updates:** Enabled
- [ ] **Code scanning:** Enabled
  - Will be populated by Trivy scans
- [ ] **Secret scanning:** Enabled
- [ ] **Secret scanning push protection:** Enabled

### Actions Permissions

Go to **Settings → Actions → General**

- [ ] **Actions permissions:** Allow all actions and reusable workflows
- [ ] **Workflow permissions:** Read and write permissions
- [ ] **Allow GitHub Actions to create and approve pull requests:** Enabled (for auto-fix)

## Step 5: Configure Notifications

### Slack Integration

1. [ ] Create Slack app at https://api.slack.com/apps
2. [ ] Enable Incoming Webhooks
3. [ ] Create webhooks for:
   - [ ] #deployments channel
   - [ ] #security-alerts channel
4. [ ] Add webhook URLs to repository secrets

### Email Notifications

1. [ ] Set up SMTP credentials
2. [ ] Test email delivery:
   ```bash
   # Use a test script or manual SMTP test
   ```
3. [ ] Add credentials to repository secrets

## Step 6: Test Workflows

### Test Linting Workflow

- [ ] Create test branch
  ```bash
  git checkout -b test/ci-setup
  ```
- [ ] Make a small change
  ```bash
  echo "# Test" >> README.md
  git add README.md
  git commit -m "test: verify CI setup"
  git push origin test/ci-setup
  ```
- [ ] Check Actions tab for workflow run
- [ ] Verify all checks pass

### Test Full CI Pipeline

- [ ] Create pull request from test branch to `develop`
- [ ] Verify workflows run:
  - [ ] Lint & Format Check
  - [ ] Code Coverage Report
  - [ ] CI/CD Pipeline (code-quality and test jobs)
- [ ] Check for PR comments (coverage report)
- [ ] Verify all checks pass

### Test Staging Deployment

- [ ] Merge PR to `main` branch
- [ ] Verify workflows run:
  - [ ] Build Docker Images
  - [ ] Deploy to Staging
- [ ] Check Slack for deployment notification
- [ ] Verify staging environment is updated

### Test Production Deployment

- [ ] Check Actions tab for production deployment waiting for approval
- [ ] Approve deployment (if you're a reviewer)
- [ ] Verify production deployment completes
- [ ] Check Slack and email for notifications

## Step 7: Configure Codecov (Optional)

If using Codecov for coverage tracking:

1. [ ] Sign up at https://codecov.io
2. [ ] Add repository
3. [ ] Copy upload token
4. [ ] Add `CODECOV_TOKEN` to repository secrets
5. [ ] Configure Codecov settings:
   - [ ] Coverage threshold: 75%
   - [ ] PR comments: Enabled
   - [ ] Status checks: Enabled

## Step 8: Documentation

- [ ] Add workflow status badges to README.md:
  ```markdown
  ![CI/CD](https://github.com/YOUR_ORG/YOUR_REPO/actions/workflows/ci.yml/badge.svg)
  ![Security](https://github.com/YOUR_ORG/YOUR_REPO/actions/workflows/security-scan.yml/badge.svg)
  ![Coverage](./coverage.svg)
  ```

- [ ] Update team documentation with:
  - [ ] How to run workflows manually
  - [ ] How to approve production deployments
  - [ ] How to rollback deployments
  - [ ] How to interpret workflow results

## Step 9: Team Training

- [ ] Share `.github/workflows/README.md` with team
- [ ] Share `.github/CONTRIBUTING.md` with contributors
- [ ] Conduct walkthrough of CI/CD pipeline
- [ ] Demonstrate:
  - [ ] Creating PRs
  - [ ] Reviewing workflow results
  - [ ] Approving production deployments
  - [ ] Handling failures
  - [ ] Rolling back deployments

## Step 10: Monitoring

### Set Up Monitoring

- [ ] Monitor workflow run times
- [ ] Track success/failure rates
- [ ] Review security scan results weekly
- [ ] Check coverage trends

### Regular Maintenance

- [ ] Review and update workflows monthly
- [ ] Update action versions quarterly
- [ ] Rotate secrets quarterly
- [ ] Review and optimize slow jobs

## Verification Checklist

After setup, verify:

- [ ] Workflows run on push to any branch
- [ ] Workflows run on pull requests
- [ ] Code quality checks catch issues
- [ ] Tests run with real database and Redis
- [ ] Coverage reports are generated
- [ ] Security scans detect vulnerabilities
- [ ] Docker images are built and pushed
- [ ] Staging deploys automatically on main
- [ ] Production requires manual approval
- [ ] Notifications are sent to Slack
- [ ] Email notifications work
- [ ] Rollback works on failure
- [ ] All documentation is accessible

## Troubleshooting

### Workflows Not Running

**Check:**
- [ ] Actions are enabled in repository settings
- [ ] Workflow files are in `.github/workflows/`
- [ ] YAML syntax is valid
- [ ] Branch protection rules don't block workflows

### Secrets Not Working

**Check:**
- [ ] Secret names match exactly (case-sensitive)
- [ ] Secrets are set at repository level (not organization)
- [ ] Secrets are available to workflows
- [ ] Base64 encoding is correct for kubeconfig

### Deployment Failing

**Check:**
- [ ] Kubernetes credentials are valid
- [ ] Cluster is accessible from GitHub Actions
- [ ] Namespace exists
- [ ] Deployment manifests are correct
- [ ] Image is available in registry

### Notifications Not Sending

**Check:**
- [ ] Webhook URLs are correct
- [ ] Slack app has permissions
- [ ] SMTP credentials are valid
- [ ] Network connectivity from GitHub Actions

## Support

If you encounter issues:

1. Check workflow logs in Actions tab
2. Review `.github/workflows/README.md`
3. Search existing issues
4. Contact DevOps team
5. Create issue with `ci-cd` label

## Completion

- [ ] All secrets configured
- [ ] All environments set up
- [ ] Branch protection enabled
- [ ] Workflows tested
- [ ] Team trained
- [ ] Documentation updated
- [ ] Monitoring in place

**Setup completed by:** _______________  
**Date:** _______________  
**Verified by:** _______________  
**Date:** _______________

---

**Next Steps:**
1. Monitor first few deployments closely
2. Gather team feedback
3. Optimize workflow performance
4. Document any issues and solutions
