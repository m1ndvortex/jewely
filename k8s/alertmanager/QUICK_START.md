# Alertmanager Quick Start Guide

## 5-Minute Setup

### Step 1: Install Alertmanager
```bash
cd k8s/alertmanager
./install-alertmanager.sh
```

When prompted, provide:
- **SMTP Password**: Your email service password
- **Slack Webhook**: Get from https://api.slack.com/messaging/webhooks
- **PagerDuty Key**: Get from PagerDuty service integration

### Step 2: Validate Installation
```bash
./validate-alertmanager.sh
```

Expected output: All tests should pass ✓

### Step 3: Run Tests
```bash
./test-alertmanager-comprehensive.sh
```

This will:
- Verify all components are working
- Trigger a test alert
- Confirm alert routing

### Step 4: Access UIs

**Alertmanager UI**:
```bash
kubectl port-forward -n jewelry-shop svc/alertmanager 9093:9093
```
Open: http://localhost:9093

**Prometheus Alerts**:
```bash
kubectl port-forward -n jewelry-shop svc/prometheus 9090:9090
```
Open: http://localhost:9090/alerts

## What You Get

### Alert Rules
- ✅ Infrastructure monitoring (CPU, memory, disk)
- ✅ Kubernetes health (pods, deployments)
- ✅ Application monitoring (Django, Celery)
- ✅ Database monitoring (PostgreSQL)
- ✅ Cache monitoring (Redis)
- ✅ Proxy monitoring (Nginx)

### Notification Channels
- ✅ Email notifications
- ✅ Slack notifications
- ✅ PagerDuty integration
- ✅ SMS via webhook

### Alert Routing
- 🚨 **Critical alerts** → All channels
- ⚠️ **Warning alerts** → Email + Slack
- 🗄️ **Database alerts** → Database team
- 🏗️ **Infrastructure alerts** → Ops team
- 💻 **Application alerts** → Dev team

## Quick Commands

### View Active Alerts
```bash
kubectl exec -n jewelry-shop $(kubectl get pods -n jewelry-shop -l app=prometheus -o jsonpath='{.items[0].metadata.name}') -- wget -q -O- http://localhost:9090/api/v1/alerts
```

### View Alertmanager Status
```bash
kubectl get pods -n jewelry-shop -l app=alertmanager
```

### Check Logs
```bash
kubectl logs -n jewelry-shop -l app=alertmanager -f
```

### Trigger Test Alert
```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: test-alert
  namespace: jewelry-shop
data:
  test.yml: |
    groups:
      - name: test
        rules:
          - alert: TestAlert
            expr: vector(1)
            labels:
              severity: warning
            annotations:
              summary: "Test alert"
EOF

# Wait 30 seconds, then check Alertmanager UI
# Cleanup: kubectl delete configmap test-alert -n jewelry-shop
```

## Common Tasks

### Update Email Recipients
1. Edit `alertmanager-configmap.yaml`
2. Find the receiver you want to update
3. Change the `to:` field
4. Apply: `kubectl apply -f alertmanager-configmap.yaml`
5. Reload: `kubectl exec -n jewelry-shop $ALERTMANAGER_POD -- wget --post-data="" -O- http://localhost:9093/-/reload`

### Add New Alert Rule
1. Edit `prometheus-alert-rules.yaml`
2. Add your rule under appropriate group
3. Apply: `kubectl apply -f prometheus-alert-rules.yaml`
4. Reload Prometheus: `kubectl exec -n jewelry-shop $PROMETHEUS_POD -- wget --post-data="" -O- http://localhost:9090/-/reload`

### Silence an Alert
1. Open Alertmanager UI: http://localhost:9093
2. Click "Silences" tab
3. Click "New Silence"
4. Fill in matcher (e.g., alertname="MyAlert")
5. Set duration
6. Add comment
7. Click "Create"

## Troubleshooting

### Alerts Not Showing
```bash
# Check Prometheus is scraping
kubectl exec -n jewelry-shop $PROMETHEUS_POD -- wget -q -O- http://localhost:9090/api/v1/targets

# Check alert rules loaded
kubectl exec -n jewelry-shop $PROMETHEUS_POD -- wget -q -O- http://localhost:9090/api/v1/rules
```

### Notifications Not Sent
```bash
# Check Alertmanager logs
kubectl logs -n jewelry-shop -l app=alertmanager | tail -50

# Check secrets
kubectl get secret alertmanager-secrets -n jewelry-shop -o yaml
```

### Configuration Errors
```bash
# Check ConfigMap
kubectl get configmap alertmanager-config -n jewelry-shop -o yaml

# Check pod events
kubectl describe pod -n jewelry-shop -l app=alertmanager
```

## Next Steps

1. **Customize Alert Rules**: Edit thresholds in `prometheus-alert-rules.yaml`
2. **Configure Channels**: Update email addresses, Slack channels
3. **Add Custom Alerts**: Create alerts specific to your application
4. **Set Up Runbooks**: Document response procedures for each alert
5. **Test Regularly**: Run `./test-alertmanager-comprehensive.sh` weekly

## Support

- 📖 Full documentation: [README.md](README.md)
- 🔧 Validation script: `./validate-alertmanager.sh`
- 🧪 Test script: `./test-alertmanager-comprehensive.sh`
- 📋 Requirements: [Requirement 24](../../.kiro/specs/jewelry-saas-platform/requirements.md#requirement-24-monitoring-and-observability)
