# Django Integration Guide for Alertmanager

## Overview

This guide explains how Alertmanager integrates with your Django application to send SMS alerts for critical system issues.

## Architecture

```
┌─────────────┐
│ Prometheus  │
│             │
│ Evaluates   │
│ alert rules │
└──────┬──────┘
       │ Fires alerts
       ▼
┌─────────────────┐
│ Alertmanager    │
│                 │
│ Routes critical │
│ alerts          │
└────────┬────────┘
         │ HTTP POST
         ▼
┌──────────────────────────────────┐
│ Django Application               │
│                                  │
│ /notifications/api/alerts/sms/   │
│                                  │
│ 1. Validates webhook token       │
│ 2. Parses alert payload          │
│ 3. Sends SMS to admins via Twilio│
└──────────────────────────────────┘
```

## Components Added

### 1. Django Webhook Endpoint

**File**: `apps/notifications/views.py`

**Function**: `alertmanager_webhook(request)`

**URL**: `/notifications/api/alerts/sms/`

**Purpose**: Receives alert notifications from Alertmanager and sends SMS to administrators.

**Features**:
- Bearer token authentication
- JSON payload parsing
- Filters for critical alerts only
- Sends SMS to all superusers with phone numbers
- Logs all activity

### 2. SMS Template

**File**: `apps/notifications/migrations/0003_add_system_alert_sms_template.py`

**Template Name**: `system_alert`

**Template Content**:
```
🚨 CRITICAL ALERT
{{ alertname }}
Service: {{ service }}
Instance: {{ instance }}
{{ summary }}
```

**Type**: ALERT

### 3. Configuration Settings

**File**: `config/settings/production.py`

**Setting**: `ALERT_WEBHOOK_TOKEN`

**Purpose**: Authenticates webhook requests from Alertmanager

**Required**: Yes (raises error if not set in production)

### 4. URL Route

**File**: `apps/notifications/urls.py`

**Route**: `path("api/alerts/sms/", views.alertmanager_webhook, name="alertmanager_webhook")`

**Full URL**: `http://django-service.jewelry-shop.svc.cluster.local/notifications/api/alerts/sms/`

## Setup Instructions

### Step 1: Run Database Migration

```bash
# Inside Django container
docker compose exec web python manage.py migrate notifications
```

This creates the `system_alert` SMS template.

### Step 2: Set Environment Variable

Add to your `.env` file or Kubernetes secret:

```bash
# Generate a secure random token
ALERT_WEBHOOK_TOKEN=$(openssl rand -hex 32)
echo "ALERT_WEBHOOK_TOKEN=$ALERT_WEBHOOK_TOKEN" >> .env
```

For Kubernetes, this is already handled by the `alertmanager-secrets` secret.

### Step 3: Verify Twilio Configuration

Ensure these environment variables are set:

```bash
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890
```

### Step 4: Configure Admin Phone Numbers

Admins must have phone numbers set in their user profiles to receive SMS alerts:

```python
# In Django shell or admin panel
from django.contrib.auth import get_user_model
User = get_user_model()

admin = User.objects.get(username='admin')
admin.phone = '+1234567890'  # E.164 format
admin.save()
```

### Step 5: Test the Webhook

```bash
# Test from inside the cluster
kubectl exec -n jewelry-shop -it $(kubectl get pods -n jewelry-shop -l app=django -o jsonpath='{.items[0].metadata.name}') -- bash

# Inside the pod
curl -X POST http://django-service.jewelry-shop.svc.cluster.local/notifications/api/alerts/sms/ \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "alerts": [
      {
        "status": "firing",
        "labels": {
          "alertname": "TestAlert",
          "severity": "critical",
          "service": "test",
          "instance": "test-instance"
        },
        "annotations": {
          "summary": "This is a test alert",
          "description": "Testing the alert webhook integration"
        }
      }
    ]
  }'
```

Expected response:
```json
{
  "status": "success",
  "message": "Processed 1 alerts, sent 1 SMS notifications"
}
```

## How It Works

### 1. Alert Fires in Prometheus

When a metric exceeds a threshold, Prometheus evaluates the alert rule and fires an alert.

### 2. Alertmanager Receives Alert

Alertmanager receives the alert from Prometheus and applies routing rules.

### 3. Critical Alert Routing

For critical alerts, Alertmanager sends a webhook to:
```
http://django-service.jewelry-shop.svc.cluster.local/notifications/api/alerts/sms/
```

### 4. Django Processes Webhook

The `alertmanager_webhook` view:
1. Validates the Bearer token
2. Parses the JSON payload
3. Extracts alert details (name, severity, service, instance, summary)
4. Filters for `status == "firing"` and `severity == "critical"`
5. Queries for active superusers with phone numbers
6. Sends SMS to each admin using the `send_alert_sms` service

### 5. SMS Sent via Twilio

The `send_alert_sms` function:
1. Checks if user is opted out of alert SMS
2. Renders the `system_alert` template with alert context
3. Calls Twilio API to send SMS
4. Creates `SMSNotification` record for tracking
5. Logs the delivery status

## Alert Payload Format

Alertmanager sends alerts in this format:

```json
{
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "HighCPUUsage",
        "severity": "critical",
        "service": "django",
        "instance": "django-pod-1",
        "component": "backend"
      },
      "annotations": {
        "summary": "High CPU usage on django-pod-1",
        "description": "CPU usage is above 95% for more than 5 minutes. Current value: 97%"
      },
      "startsAt": "2024-01-13T10:00:00Z",
      "endsAt": "0001-01-01T00:00:00Z"
    }
  ],
  "groupLabels": {
    "alertname": "HighCPUUsage"
  },
  "commonLabels": {
    "severity": "critical"
  },
  "commonAnnotations": {
    "summary": "High CPU usage on django-pod-1"
  },
  "externalURL": "http://alertmanager:9093",
  "version": "4",
  "groupKey": "{}:{alertname=\"HighCPUUsage\"}"
}
```

## SMS Template Variables

The `system_alert` template has access to these variables:

- `alertname`: Name of the alert (e.g., "HighCPUUsage")
- `severity`: Alert severity (e.g., "critical", "warning")
- `service`: Service name (e.g., "django", "postgresql")
- `instance`: Instance identifier (e.g., "django-pod-1")
- `summary`: Short summary of the alert
- `description`: Detailed description of the alert
- `status`: Alert status ("firing" or "resolved")

## Customization

### Modify SMS Template

Edit the template in Django admin or via migration:

```python
from apps.notifications.models import SMSTemplate

template = SMSTemplate.objects.get(name='system_alert')
template.message_template = '''
🚨 {{ alertname }}
{{ summary }}
Service: {{ service }}
Action required!
'''
template.save()
```

### Change Alert Recipients

By default, SMS alerts are sent to all superusers. To customize:

```python
# In apps/notifications/views.py, modify the alertmanager_webhook function

# Option 1: Send to specific group
from django.contrib.auth.models import Group
ops_group = Group.objects.get(name='Operations')
admin_users = ops_group.user_set.filter(
    is_active=True
).exclude(phone="").exclude(phone__isnull=True)

# Option 2: Send to users with specific permission
from django.contrib.auth import get_user_model
User = get_user_model()
admin_users = User.objects.filter(
    is_active=True,
    user_permissions__codename='receive_alerts'
).exclude(phone="").exclude(phone__isnull=True)
```

### Add Alert Filtering

To filter which alerts trigger SMS:

```python
# In alertmanager_webhook function, add conditions:

# Only send for specific services
if service not in ['django', 'postgresql', 'redis']:
    continue

# Only send for specific alert names
if alertname not in ['DatabaseDown', 'HighCPUUsage', 'DiskSpaceCritical']:
    continue

# Only send during business hours
from django.utils import timezone
current_hour = timezone.now().hour
if current_hour < 8 or current_hour > 18:
    continue  # Skip SMS outside business hours
```

## Monitoring and Debugging

### Check SMS Delivery Status

```python
from apps.notifications.models import SMSNotification

# Recent alert SMS
recent_alerts = SMSNotification.objects.filter(
    sms_type='ALERT'
).order_by('-created_at')[:10]

for sms in recent_alerts:
    print(f"{sms.created_at}: {sms.to_phone} - {sms.status}")
```

### View Webhook Logs

```bash
# Django logs
kubectl logs -n jewelry-shop -l app=django | grep "Alertmanager webhook"

# Alertmanager logs
kubectl logs -n jewelry-shop -l app=alertmanager | grep "webhook"
```

### Test SMS Sending

```python
from django.contrib.auth import get_user_model
from apps.notifications.services import send_alert_sms

User = get_user_model()
admin = User.objects.get(username='admin')

send_alert_sms(
    user=admin,
    template_name='system_alert',
    context={
        'alertname': 'TestAlert',
        'severity': 'critical',
        'service': 'test',
        'instance': 'test-1',
        'summary': 'This is a test',
        'description': 'Testing SMS alerts',
        'status': 'firing'
    }
)
```

## Troubleshooting

### SMS Not Sent

**Check 1**: Verify admin has phone number
```python
from django.contrib.auth import get_user_model
User = get_user_model()
admins = User.objects.filter(is_superuser=True)
for admin in admins:
    print(f"{admin.username}: {admin.phone or 'NO PHONE'}")
```

**Check 2**: Verify Twilio credentials
```bash
docker compose exec web python manage.py shell
>>> from django.conf import settings
>>> print(settings.TWILIO_ACCOUNT_SID)
>>> print(settings.TWILIO_PHONE_NUMBER)
```

**Check 3**: Check SMS opt-out status
```python
from apps.notifications.models import SMSOptOut
opt_outs = SMSOptOut.objects.filter(alert_opt_out=True)
print(f"Users opted out of alerts: {opt_outs.count()}")
```

### Webhook Not Receiving Alerts

**Check 1**: Verify Alertmanager can reach Django
```bash
kubectl exec -n jewelry-shop -it $(kubectl get pods -n jewelry-shop -l app=alertmanager -o jsonpath='{.items[0].metadata.name}') -- wget -O- http://django-service.jewelry-shop.svc.cluster.local/health/
```

**Check 2**: Verify webhook token matches
```bash
# In Alertmanager secret
kubectl get secret alertmanager-secrets -n jewelry-shop -o jsonpath='{.data.alert-webhook-token}' | base64 -d

# In Django environment
kubectl exec -n jewelry-shop $(kubectl get pods -n jewelry-shop -l app=django -o jsonpath='{.items[0].metadata.name}') -- env | grep ALERT_WEBHOOK_TOKEN
```

**Check 3**: Check Django logs for errors
```bash
kubectl logs -n jewelry-shop -l app=django --tail=100 | grep -i "alertmanager\|webhook\|error"
```

### Authentication Errors

If you see 401 Unauthorized:
1. Verify `ALERT_WEBHOOK_TOKEN` is set in Django
2. Verify token in Alertmanager secret matches
3. Check Authorization header format: `Bearer <token>`

## Security Considerations

1. **Token Security**: The `ALERT_WEBHOOK_TOKEN` should be a strong random value (32+ characters)
2. **HTTPS**: In production, use HTTPS for webhook endpoint
3. **Rate Limiting**: Consider adding rate limiting to prevent SMS spam
4. **Opt-Out**: Respect user SMS opt-out preferences
5. **Cost Control**: Monitor SMS costs, especially for high-frequency alerts

## Cost Optimization

SMS alerts can be expensive. Consider:

1. **Alert Throttling**: Group similar alerts
2. **Business Hours**: Only send SMS during business hours
3. **Escalation**: Send email first, SMS after 5 minutes if not acknowledged
4. **Severity Filtering**: Only send SMS for truly critical alerts
5. **Recipient Limiting**: Send to on-call person only, not all admins

## Integration with Existing Code

Your existing SMS infrastructure is fully utilized:

- ✅ `SMSNotification` model for tracking
- ✅ `SMSTemplate` model for templates
- ✅ `SMSOptOut` model for preferences
- ✅ `send_alert_sms` service for sending
- ✅ Twilio integration for delivery
- ✅ Webhook for status tracking

No changes needed to your existing SMS code!

## Next Steps

1. Run the migration to create the SMS template
2. Set the `ALERT_WEBHOOK_TOKEN` environment variable
3. Configure admin phone numbers
4. Test the webhook endpoint
5. Deploy Alertmanager with the configuration
6. Monitor SMS delivery and costs
7. Tune alert rules and routing as needed

## References

- [Alertmanager Webhook Configuration](https://prometheus.io/docs/alerting/latest/configuration/#webhook_config)
- [Twilio SMS API](https://www.twilio.com/docs/sms)
- [Django Notifications App](../../apps/notifications/README.md)
