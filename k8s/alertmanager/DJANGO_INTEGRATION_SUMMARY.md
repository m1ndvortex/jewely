# Django Integration Summary

## What Was Added to Your Django Application

### 1. New Webhook Endpoint

**File**: `apps/notifications/views.py`

**Function**: `alertmanager_webhook(request: HttpRequest) -> JsonResponse`

**Purpose**: Receives critical alerts from Alertmanager and sends SMS to administrators

**Features**:
- Bearer token authentication using `ALERT_WEBHOOK_TOKEN`
- Parses Alertmanager JSON payload
- Filters for critical, firing alerts only
- Sends SMS to all superusers with phone numbers
- Uses existing `send_alert_sms` service
- Comprehensive error handling and logging

### 2. New URL Route

**File**: `apps/notifications/urls.py`

**Route**: `/notifications/api/alerts/sms/`

**Full URL**: `http://django-service.jewelry-shop.svc.cluster.local/notifications/api/alerts/sms/`

**Method**: POST only

**Authentication**: Bearer token in Authorization header

### 3. New SMS Template

**File**: `apps/notifications/migrations/0003_add_system_alert_sms_template.py`

**Template Name**: `system_alert`

**Template Type**: ALERT

**Template Content**:
```
🚨 CRITICAL ALERT
{{ alertname }}
Service: {{ service }}
Instance: {{ instance }}
{{ summary }}
```

### 4. New Configuration Setting

**File**: `config/settings/production.py`

**Setting**: `ALERT_WEBHOOK_TOKEN`

**Purpose**: Authenticates webhook requests from Alertmanager

**Required**: Yes (raises ValueError if not set in production)

**Source**: Environment variable `ALERT_WEBHOOK_TOKEN`

## Integration with Existing Code

Your existing SMS infrastructure is fully utilized:

### ✅ Uses Existing Models
- `SMSNotification` - Tracks all SMS sent
- `SMSTemplate` - Stores the alert template
- `SMSOptOut` - Respects user preferences

### ✅ Uses Existing Services
- `send_alert_sms()` - Sends SMS via Twilio
- `track_sms_event()` - Tracks delivery status
- `is_user_opted_out_sms()` - Checks opt-out status

### ✅ Uses Existing Configuration
- `TWILIO_ACCOUNT_SID` - Your Twilio account
- `TWILIO_AUTH_TOKEN` - Your Twilio auth token
- `TWILIO_PHONE_NUMBER` - Your Twilio phone number

### ✅ No Breaking Changes
- All existing SMS functionality remains unchanged
- Existing webhook at `/notifications/webhooks/sms/` still works for Twilio status updates
- New endpoint is separate and independent

## How It Works

```
Prometheus → Alertmanager → Django Webhook → send_alert_sms() → Twilio → SMS to Admins
```

1. **Prometheus** evaluates alert rules and fires alerts
2. **Alertmanager** routes critical alerts to Django webhook
3. **Django webhook** (`alertmanager_webhook`) receives the alert
4. **Webhook** calls `send_alert_sms()` for each admin
5. **send_alert_sms()** uses Twilio to send SMS
6. **SMSNotification** record created for tracking

## Setup Required

### 1. Run Migration
```bash
docker compose exec web python manage.py migrate notifications
```

### 2. Set Environment Variable
```bash
# Generate token
ALERT_WEBHOOK_TOKEN=$(openssl rand -hex 32)

# Add to .env
echo "ALERT_WEBHOOK_TOKEN=$ALERT_WEBHOOK_TOKEN" >> .env

# Restart Django
docker compose restart web
```

### 3. Configure Admin Phone Numbers
```python
from django.contrib.auth import get_user_model
User = get_user_model()

admin = User.objects.get(username='admin')
admin.phone = '+1234567890'  # E.164 format
admin.save()
```

### 4. Test the Endpoint
```bash
curl -X POST http://localhost:8000/notifications/api/alerts/sms/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "TestAlert",
        "severity": "critical",
        "service": "test",
        "instance": "test-1"
      },
      "annotations": {
        "summary": "Test alert",
        "description": "Testing"
      }
    }]
  }'
```

## Files Modified

1. ✅ `apps/notifications/views.py` - Added `alertmanager_webhook` function
2. ✅ `apps/notifications/urls.py` - Added route for webhook
3. ✅ `apps/notifications/migrations/0003_add_system_alert_sms_template.py` - Created
4. ✅ `config/settings/production.py` - Added `ALERT_WEBHOOK_TOKEN` setting

## Files Created

1. ✅ `k8s/alertmanager/DJANGO_INTEGRATION_GUIDE.md` - Complete integration guide
2. ✅ `k8s/alertmanager/DJANGO_INTEGRATION_SUMMARY.md` - This file

## No Changes Needed To

- ❌ Existing SMS models
- ❌ Existing SMS services
- ❌ Existing SMS templates
- ❌ Existing Twilio configuration
- ❌ Existing webhook for Twilio status updates
- ❌ Any other part of your application

## Benefits

1. **Reuses Existing Code**: No duplication, uses your SMS infrastructure
2. **Respects Preferences**: Honors SMS opt-out settings
3. **Tracks Everything**: All SMS tracked in `SMSNotification` model
4. **Secure**: Bearer token authentication
5. **Flexible**: Easy to customize recipients, filtering, templates
6. **Cost-Aware**: Only sends for critical alerts
7. **Production-Ready**: Error handling, logging, validation

## Next Steps

1. Run the migration
2. Set the environment variable
3. Configure admin phone numbers
4. Test the endpoint locally
5. Deploy to Kubernetes
6. Monitor SMS delivery and costs

## Documentation

- Full guide: `k8s/alertmanager/DJANGO_INTEGRATION_GUIDE.md`
- Alertmanager setup: `k8s/alertmanager/README.md`
- Quick start: `k8s/alertmanager/QUICK_START.md`
