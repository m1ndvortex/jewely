# Sentry Integration Guide

## Overview

This document describes the Sentry error tracking integration for the Jewelry Shop SaaS platform. Sentry provides real-time error tracking, performance monitoring, and automatic error grouping to help identify and fix issues quickly.

**Requirements Implemented:**
- **24.8**: Integrate Sentry for error tracking with automatic error grouping
- **25.10**: Mask sensitive data in logs and error reports

## Features

### Error Tracking
- Automatic capture of unhandled exceptions
- Stack traces with source code context
- Error grouping and deduplication
- Release tracking for version-specific errors
- Breadcrumbs for debugging context

### Performance Monitoring
- Transaction tracing (10% sample rate by default)
- Database query performance
- HTTP request/response times
- Celery task performance

### Data Security
- Comprehensive sensitive data scrubbing
- PII (Personally Identifiable Information) protection
- Credit card number masking
- Email and phone number partial masking
- Password and token redaction

### Integrations
- Django (views, middleware, templates)
- Celery (background tasks)
- Redis (cache operations)

## Configuration

### Environment Variables

Add these variables to your `.env` file:

```bash
# Sentry DSN (Data Source Name)
# Get this from: https://sentry.io/settings/[organization]/projects/[project]/keys/
SENTRY_DSN=https://[key]@[organization].ingest.sentry.io/[project-id]

# Environment name (development, staging, production)
SENTRY_ENVIRONMENT=production

# Release version (optional, for tracking which version has errors)
SENTRY_RELEASE=1.0.0

# Traces sample rate (0.0 to 1.0)
# 1.0 = 100% of transactions traced (use for development)
# 0.1 = 10% of transactions traced (recommended for production)
SENTRY_TRACES_SAMPLE_RATE=0.1
```

### Getting Your Sentry DSN

1. Sign up for a free account at [sentry.io](https://sentry.io)
2. Create a new project (select Django as the platform)
3. Copy the DSN from the project settings
4. Add it to your `.env` file

### Disabling Sentry

To disable Sentry (e.g., in local development):

```bash
# Leave SENTRY_DSN empty or remove it
SENTRY_DSN=
```

Sentry will not initialize if the DSN is empty or not provided.

## Data Scrubbing

### Automatic Scrubbing

The following data is automatically scrubbed before being sent to Sentry:

#### Sensitive Field Names
Any field with these keywords in the name is redacted:
- `password`, `passwd`, `pwd`
- `secret`, `token`, `api_key`, `apikey`
- `access_token`, `refresh_token`
- `auth`, `authorization`
- `cookie`, `csrf`, `session`
- `private_key`, `public_key`, `encryption_key`
- `credit_card`, `card_number`, `cvv`
- `ssn`, `social_security`

#### Pattern-Based Scrubbing
- **Credit Cards**: `4532-1234-5678-9010` → `XXXX-XXXX-XXXX-XXXX`
- **Emails**: `john.doe@example.com` → `jo***@example.com`
- **Phone Numbers**: `555-123-4567` → `XXX-XXX-4567`
- **IP Addresses**: `192.168.1.1` → `XXX.XXX.XXX.XXX`

### Example

**Before Scrubbing:**
```python
{
    'username': 'john',
    'password': 'secret123',
    'email': 'john@example.com',
    'credit_card': '4532-1234-5678-9010',
}
```

**After Scrubbing:**
```python
{
    'username': 'john',
    'password': '[REDACTED]',
    'email': 'jo***@example.com',
    'credit_card': 'XXXX-XXXX-XXXX-XXXX',
}
```

## Usage

### Automatic Error Capture

Sentry automatically captures unhandled exceptions:

```python
# This error will be automatically captured
def my_view(request):
    result = 1 / 0  # ZeroDivisionError captured by Sentry
    return result
```

### Manual Error Capture

You can manually capture errors or messages:

```python
import sentry_sdk

# Capture an exception
try:
    risky_operation()
except Exception as e:
    sentry_sdk.capture_exception(e)

# Capture a message
sentry_sdk.capture_message('Something went wrong', level='error')
```

### Adding Context

Add custom context to errors:

```python
import sentry_sdk

# Set user context
sentry_sdk.set_user({
    'id': user.id,
    'username': user.username,
    'email': user.email,  # Will be scrubbed
})

# Set custom tags
sentry_sdk.set_tag('tenant_id', tenant.id)
sentry_sdk.set_tag('environment', 'production')

# Add extra context
sentry_sdk.set_context('business_context', {
    'order_id': order.id,
    'total_amount': order.total,
})
```

### Breadcrumbs

Breadcrumbs are automatically captured for:
- HTTP requests
- Database queries
- Cache operations
- Celery tasks
- Log messages

You can add custom breadcrumbs:

```python
import sentry_sdk

sentry_sdk.add_breadcrumb(
    category='business_logic',
    message='Processing payment',
    level='info',
    data={'amount': 100.00, 'currency': 'USD'}
)
```

## Performance Monitoring

### Transaction Tracing

Sentry automatically traces:
- HTTP requests (Django views)
- Database queries
- Cache operations
- Celery tasks

View performance data in the Sentry dashboard under "Performance".

### Custom Transactions

Create custom transactions for specific operations:

```python
import sentry_sdk

with sentry_sdk.start_transaction(op="task", name="process_inventory"):
    # Your code here
    process_inventory_items()
```

### Spans

Add spans to track specific operations within a transaction:

```python
import sentry_sdk

with sentry_sdk.start_span(op="db", description="Fetch inventory"):
    items = InventoryItem.objects.filter(tenant=tenant)
```

## Testing

### Running Tests

```bash
# Run Sentry integration tests
docker compose exec web pytest apps/core/tests/test_sentry_integration.py -v

# Run with coverage
docker compose exec web pytest apps/core/tests/test_sentry_integration.py --cov=apps.core.sentry_config
```

### Test Coverage

The test suite covers:
- Sensitive data scrubbing (dictionaries, lists, strings)
- Email, phone, and credit card masking
- Request data scrubbing
- User data scrubbing
- Exception value scrubbing
- Breadcrumb scrubbing
- Sentry initialization with/without DSN
- Integration configuration

## Monitoring

### Sentry Dashboard

Access your Sentry dashboard at: `https://sentry.io/organizations/[org]/issues/`

Key sections:
- **Issues**: View and manage errors
- **Performance**: Monitor transaction performance
- **Releases**: Track errors by version
- **Alerts**: Configure alert rules

### Alert Configuration

Configure alerts in Sentry to notify you when:
- New errors occur
- Error frequency exceeds threshold
- Performance degrades
- Release health drops

Alert channels:
- Email
- Slack
- PagerDuty
- Webhooks

## Best Practices

### 1. Use Releases

Tag errors with release versions:

```bash
# Set release version in environment
export SENTRY_RELEASE=$(git rev-parse --short HEAD)
```

This helps track which version introduced errors.

### 2. Set Appropriate Sample Rates

- **Development**: `SENTRY_TRACES_SAMPLE_RATE=1.0` (100%)
- **Staging**: `SENTRY_TRACES_SAMPLE_RATE=0.5` (50%)
- **Production**: `SENTRY_TRACES_SAMPLE_RATE=0.1` (10%)

Higher sample rates provide more data but increase costs.

### 3. Use Tags for Filtering

Add tags to make errors easier to filter:

```python
sentry_sdk.set_tag('tenant_id', tenant.id)
sentry_sdk.set_tag('feature', 'inventory')
sentry_sdk.set_tag('user_role', user.role)
```

### 4. Add Business Context

Include relevant business context in errors:

```python
sentry_sdk.set_context('order', {
    'id': order.id,
    'status': order.status,
    'total': str(order.total),
})
```

### 5. Review Errors Regularly

- Check Sentry dashboard daily
- Triage and assign errors
- Set up alerts for critical errors
- Track error trends over time

## Troubleshooting

### Sentry Not Capturing Errors

1. **Check DSN**: Ensure `SENTRY_DSN` is set correctly
2. **Check Environment**: Verify `SENTRY_ENVIRONMENT` is set
3. **Check Logs**: Look for Sentry initialization messages
4. **Test Manually**: Use `sentry_sdk.capture_message('test')`

### Too Many Events

1. **Reduce Sample Rate**: Lower `SENTRY_TRACES_SAMPLE_RATE`
2. **Filter Events**: Use `before_send` to filter unwanted events
3. **Set Rate Limits**: Configure rate limits in Sentry project settings

### Sensitive Data Leaking

1. **Review Scrubbing Rules**: Check `apps/core/sentry_config.py`
2. **Add Custom Patterns**: Extend `SENSITIVE_KEYS` or regex patterns
3. **Test Scrubbing**: Run tests to verify scrubbing works
4. **Use `before_send`**: Add custom scrubbing logic

## Cost Management

### Free Tier

Sentry offers a free tier with:
- 5,000 errors per month
- 10,000 performance units per month
- 1 GB of attachments

### Reducing Costs

1. **Lower Sample Rates**: Reduce `SENTRY_TRACES_SAMPLE_RATE`
2. **Filter Events**: Drop low-priority events in `before_send`
3. **Set Quotas**: Configure project quotas in Sentry
4. **Archive Old Issues**: Resolve and archive old issues

## Security Considerations

### Data Privacy

- All sensitive data is scrubbed before sending to Sentry
- PII is masked or redacted
- Passwords and tokens are never sent
- IP addresses are anonymized

### Compliance

- GDPR compliant (with proper scrubbing)
- HIPAA compliant (with Business Associate Agreement)
- SOC 2 Type II certified

### Access Control

- Limit Sentry access to authorized personnel
- Use role-based access control
- Enable two-factor authentication
- Audit access logs regularly

## References

- [Sentry Documentation](https://docs.sentry.io/)
- [Sentry Python SDK](https://docs.sentry.io/platforms/python/)
- [Sentry Django Integration](https://docs.sentry.io/platforms/python/guides/django/)
- [Data Scrubbing](https://docs.sentry.io/platforms/python/data-management/sensitive-data/)

## Support

For issues or questions:
1. Check this documentation
2. Review Sentry documentation
3. Check application logs
4. Contact the development team
