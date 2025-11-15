# Alertmanager for Jewelry SaaS Platform

## Overview

This directory contains the Alertmanager configuration for the Jewelry SaaS Platform monitoring stack. Alertmanager handles alerts sent by Prometheus and routes them to the appropriate notification channels (email, SMS, Slack, PagerDuty).

**Requirement**: Requirement 24 - Monitoring and Observability  
**Task**: Task 35.4 - Configure alerting with Alertmanager

## Architecture

```
┌─────────────┐
│ Prometheus  │
│             │
│ - Scrapes   │
│   metrics   │
│ - Evaluates │
│   rules     │
│ - Fires     │
│   alerts    │
└──────┬──────┘
       │
       │ Alerts
       ▼
┌─────────────────┐
│ Alertmanager    │
│                 │
│ - Deduplicates  │
│ - Groups        │
│ - Routes        │
│ - Silences      │
└────────┬────────┘
         │
         ├──────────┬──────────┬──────────┐
         ▼          ▼          ▼          ▼
    ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐
    │ Email  │ │ Slack  │ │  SMS   │ │PagerDuty │
    └────────┘ └────────┘ └────────┘ └──────────┘
```

## Components

### 1. Alertmanager Deployment
- **Replicas**: 2 (high availability)
- **Image**: prom/alertmanager:v0.26.0
- **Clustering**: Enabled for HA
- **Resources**: 100m CPU / 128Mi RAM (request), 500m CPU / 512Mi RAM (limit)

### 2. Alert Rules
Comprehensive alert rules covering:
- **Infrastructure**: CPU, memory, disk space, node health
- **Kubernetes**: Pod crashes, replica mismatches, resource issues
- **Application**: Django service health, request latency, error rates
- **Database**: PostgreSQL health, connections, slow queries, replication
- **Cache**: Redis health, memory usage, replication
- **Workers**: Celery worker health, queue length, task failures
- **Proxy**: Nginx health, error rates, connection count

### 3. Alert Routing
- **Critical alerts**: All channels (email, Slack, PagerDuty, SMS)
- **Warning alerts**: Email and Slack
- **Database alerts**: Database team channel
- **Infrastructure alerts**: Infrastructure team channel
- **Application alerts**: Development team channel

### 4. Notification Channels
- **Email**: SMTP-based email notifications
- **Slack**: Webhook-based Slack notifications
- **PagerDuty**: Integration for on-call escalation
- **SMS**: Custom webhook to Django for Twilio integration

## Files

- `alertmanager-configmap.yaml` - Alertmanager configuration and email templates
- `alertmanager-deployment.yaml` - Alertmanager deployment and services
- `alertmanager-rbac.yaml` - RBAC configuration
- `alertmanager-secrets.yaml` - Secrets template (credentials)
- `prometheus-alert-rules.yaml` - Alert rule definitions
- `install-alertmanager.sh` - Installation script
- `validate-alertmanager.sh` - Validation script
- `test-alertmanager-comprehensive.sh` - Comprehensive testing script

## Installation

### Prerequisites
- Kubernetes cluster (k3d/k3s)
- jewelry-shop namespace created
- Prometheus installed (Task 35.1)

### Quick Start

1. **Install Alertmanager**:
   ```bash
   cd k8s/alertmanager
   ./install-alertmanager.sh
   ```

   The script will prompt for:
   - SMTP password for email alerts
   - Slack webhook URL
   - PagerDuty service key

2. **Validate Installation**:
   ```bash
   ./validate-alertmanager.sh
   ```

3. **Run Comprehensive Tests**:
   ```bash
   ./test-alertmanager-comprehensive.sh
   ```

### Manual Installation

1. **Create secrets**:
   ```bash
   kubectl create secret generic alertmanager-secrets \
     --from-literal=smtp-password='your-password' \
     --from-literal=slack-webhook-url='https://hooks.slack.com/services/...' \
     --from-literal=pagerduty-service-key='your-key' \
     --from-literal=alert-webhook-token='your-token' \
     --namespace=jewelry-shop
   ```

2. **Apply RBAC**:
   ```bash
   kubectl apply -f alertmanager-rbac.yaml
   ```

3. **Apply configuration**:
   ```bash
   kubectl apply -f alertmanager-configmap.yaml
   kubectl apply -f prometheus-alert-rules.yaml
   ```

4. **Deploy Alertmanager**:
   ```bash
   kubectl apply -f alertmanager-deployment.yaml
   ```

5. **Update Prometheus**:
   ```bash
   kubectl apply -f ../prometheus/prometheus-configmap.yaml
   kubectl apply -f ../prometheus/prometheus-deployment.yaml
   ```

## Configuration

### Email Notifications

Edit `alertmanager-configmap.yaml`:
```yaml
smtp_smarthost: 'smtp.gmail.com:587'
smtp_from: 'alerts@jewelry-saas.com'
smtp_auth_username: 'alerts@jewelry-saas.com'
```

Update recipient addresses in receiver configurations.

### Slack Notifications

1. Create a Slack app and incoming webhook
2. Update the secret with your webhook URL
3. Configure channels in `alertmanager-configmap.yaml`:
   ```yaml
   slack_configs:
     - channel: '#alerts-critical'
   ```

### PagerDuty Integration

1. Create a PagerDuty service
2. Get the Events API V2 integration key
3. Update the secret with your service key

### SMS Notifications

SMS notifications use a custom webhook to Django:
```yaml
webhook_configs:
  - url: 'http://django-service.jewelry-shop.svc.cluster.local/api/alerts/sms/'
```

Implement the webhook endpoint in Django to send SMS via Twilio.

## Alert Rules

### Severity Levels
- **critical**: Immediate action required, sent to all channels
- **warning**: Attention needed, sent to email and Slack

### Alert Groups
1. **infrastructure**: Node health, CPU, memory, disk
2. **kubernetes**: Pod health, deployments, StatefulSets
3. **application**: Django service, request latency, errors
4. **database**: PostgreSQL health, connections, queries
5. **redis**: Redis health, memory, replication
6. **celery**: Worker health, queue length, task failures
7. **nginx**: Proxy health, error rates, connections

### Adding Custom Alert Rules

Edit `prometheus-alert-rules.yaml`:
```yaml
- alert: MyCustomAlert
  expr: my_metric > threshold
  for: 5m
  labels:
    severity: warning
    component: my-component
  annotations:
    summary: "Brief description"
    description: "Detailed description with {{ $value }}"
```

Apply changes:
```bash
kubectl apply -f prometheus-alert-rules.yaml
kubectl exec -n jewelry-shop $PROMETHEUS_POD -- wget --post-data="" -O- http://localhost:9090/-/reload
```

## Accessing UIs

### Alertmanager UI
```bash
kubectl port-forward -n jewelry-shop svc/alertmanager 9093:9093
```
Open: http://localhost:9093

Features:
- View active alerts
- Silence alerts
- View alert history
- Check receiver status

### Prometheus Alerts
```bash
kubectl port-forward -n jewelry-shop svc/prometheus 9090:9090
```
Open: http://localhost:9090/alerts

## Testing

### Trigger Test Alert
```bash
# Create a test alert that fires immediately
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-test-alert
  namespace: jewelry-shop
data:
  test-alert.yml: |
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

# Wait 30 seconds, then check
kubectl exec -n jewelry-shop $PROMETHEUS_POD -- wget -q -O- http://localhost:9090/api/v1/alerts

# Cleanup
kubectl delete configmap prometheus-test-alert -n jewelry-shop
```

### Silence Alerts
```bash
# Via UI: http://localhost:9093/#/silences
# Or via API:
curl -X POST http://localhost:9093/api/v2/silences \
  -H 'Content-Type: application/json' \
  -d '{
    "matchers": [{"name": "alertname", "value": "TestAlert", "isRegex": false}],
    "startsAt": "2024-01-01T00:00:00Z",
    "endsAt": "2024-01-01T01:00:00Z",
    "createdBy": "admin",
    "comment": "Testing silence"
  }'
```

## Troubleshooting

### Alerts Not Firing

1. **Check Prometheus is scraping targets**:
   ```bash
   kubectl exec -n jewelry-shop $PROMETHEUS_POD -- wget -q -O- http://localhost:9090/api/v1/targets
   ```

2. **Check alert rules are loaded**:
   ```bash
   kubectl exec -n jewelry-shop $PROMETHEUS_POD -- wget -q -O- http://localhost:9090/api/v1/rules
   ```

3. **Check Prometheus logs**:
   ```bash
   kubectl logs -n jewelry-shop -l app=prometheus
   ```

### Alerts Not Reaching Alertmanager

1. **Check Alertmanager is registered**:
   ```bash
   kubectl exec -n jewelry-shop $PROMETHEUS_POD -- wget -q -O- http://localhost:9090/api/v1/alertmanagers
   ```

2. **Check connectivity**:
   ```bash
   kubectl exec -n jewelry-shop $PROMETHEUS_POD -- wget -q -O- http://alertmanager.jewelry-shop.svc.cluster.local:9093/-/healthy
   ```

### Notifications Not Sent

1. **Check Alertmanager logs**:
   ```bash
   kubectl logs -n jewelry-shop -l app=alertmanager
   ```

2. **Check secrets are mounted**:
   ```bash
   kubectl exec -n jewelry-shop $ALERTMANAGER_POD -- env | grep -E '(SMTP|SLACK|PAGERDUTY)'
   ```

3. **Test notification manually**:
   ```bash
   # Send test email
   kubectl exec -n jewelry-shop $ALERTMANAGER_POD -- wget --post-data='[{"labels":{"alertname":"test"}}]' http://localhost:9093/api/v1/alerts
   ```

### Configuration Errors

1. **Validate configuration**:
   ```bash
   kubectl logs -n jewelry-shop -l app=alertmanager | grep -i error
   ```

2. **Check ConfigMap**:
   ```bash
   kubectl get configmap alertmanager-config -n jewelry-shop -o yaml
   ```

3. **Reload configuration**:
   ```bash
   kubectl exec -n jewelry-shop $ALERTMANAGER_POD -- wget --post-data="" -O- http://localhost:9093/-/reload
   ```

## Maintenance

### Update Alert Rules
```bash
# Edit prometheus-alert-rules.yaml
kubectl apply -f prometheus-alert-rules.yaml

# Reload Prometheus
kubectl exec -n jewelry-shop $PROMETHEUS_POD -- wget --post-data="" -O- http://localhost:9090/-/reload
```

### Update Alertmanager Configuration
```bash
# Edit alertmanager-configmap.yaml
kubectl apply -f alertmanager-configmap.yaml

# Reload Alertmanager
kubectl exec -n jewelry-shop $ALERTMANAGER_POD -- wget --post-data="" -O- http://localhost:9093/-/reload
```

### Update Secrets
```bash
# Delete old secret
kubectl delete secret alertmanager-secrets -n jewelry-shop

# Create new secret
kubectl create secret generic alertmanager-secrets \
  --from-literal=smtp-password='new-password' \
  --from-literal=slack-webhook-url='new-url' \
  --from-literal=pagerduty-service-key='new-key' \
  --from-literal=alert-webhook-token='new-token' \
  --namespace=jewelry-shop

# Restart Alertmanager
kubectl rollout restart deployment alertmanager -n jewelry-shop
```

## Best Practices

1. **Alert Fatigue**: Don't alert on everything, only actionable issues
2. **Severity Levels**: Use appropriate severity (critical vs warning)
3. **Grouping**: Group related alerts to reduce noise
4. **Inhibition**: Use inhibition rules to prevent alert storms
5. **Silences**: Use silences during maintenance windows
6. **Testing**: Regularly test alert routing and notifications
7. **Documentation**: Document alert meanings and remediation steps
8. **Review**: Regularly review and tune alert thresholds

## References

- [Alertmanager Documentation](https://prometheus.io/docs/alerting/latest/alertmanager/)
- [Alert Rule Best Practices](https://prometheus.io/docs/practices/alerting/)
- [Requirement 24](../../.kiro/specs/jewelry-saas-platform/requirements.md#requirement-24-monitoring-and-observability)
- [Task 35.4](../../.kiro/specs/jewelry-saas-platform/tasks.md#354-configure-alerting)
