# Stripe Payment Gateway Integration

## Overview

This document describes the Stripe payment gateway integration for automated subscription billing and lifecycle management, implementing Requirement 5.7.

## Architecture

### Components

1. **StripeService** (`apps/core/stripe_service.py`)
   - Service class for all Stripe API interactions
   - Handles customer creation, subscription management, and payments
   - Provides methods for subscription lifecycle operations

2. **Webhook Handlers** (`apps/core/stripe_webhooks.py`)
   - Processes Stripe webhook events
   - Automatically updates subscription status
   - Manages tenant suspension/reactivation based on payment status

3. **Management Commands** (`apps/core/management/commands/sync_stripe_plans.py`)
   - Syncs subscription plans with Stripe products and prices
   - Creates Stripe resources for existing plans

4. **Models** (`apps/core/models.py`)
   - `SubscriptionPlan` - Defines subscription tiers and pricing
   - `TenantSubscription` - Links tenants to plans with Stripe IDs

## Features

### Customer Management

- Create Stripe customers with tenant metadata
- Link customers to tenant subscriptions
- Automatic customer cleanup on tenant deletion

### Subscription Management

- Create subscriptions with payment methods
- Support trial periods (configurable days)
- Update subscription plans with proration
- Cancel subscriptions (immediate or at period end)
- Retrieve subscription details from Stripe

### Payment Processing

- Create payment intents for one-time payments
- Handle payment method attachment
- Support multiple payment methods per customer

### Automated Lifecycle Management

The system automatically handles subscription lifecycle events via webhooks:

#### Subscription Events

- **subscription.created** - Initializes subscription in database
- **subscription.updated** - Syncs status and billing period changes
- **subscription.deleted** - Marks subscription as cancelled, suspends tenant
- **subscription.trial_will_end** - Sends reminder notifications (3 days before)

#### Payment Events

- **invoice.payment_succeeded** - Activates subscription, reactivates tenant
- **invoice.payment_failed** - Marks subscription as past due, suspends tenant after 3 attempts
- **invoice.upcoming** - Sends upcoming payment notifications

#### Customer Events

- **customer.created** - Logs customer creation
- **customer.updated** - Syncs customer data
- **customer.deleted** - Clears Stripe customer ID

### Tenant Suspension Logic

The system automatically manages tenant access based on payment status:

1. **Payment Failed** - Subscription marked as "past_due"
2. **3 Failed Attempts** - Tenant automatically suspended
3. **Payment Succeeded** - Tenant automatically reactivated
4. **Subscription Cancelled** - Tenant suspended immediately

## Configuration

### Environment Variables

```bash
# Stripe API Keys (get from https://dashboard.stripe.com/apikeys)
STRIPE_SECRET_KEY=sk_test_...  # or sk_live_... for production
STRIPE_PUBLISHABLE_KEY=pk_test_...  # or pk_live_... for production

# Webhook Secret (get from https://dashboard.stripe.com/webhooks)
STRIPE_WEBHOOK_SECRET=whsec_...

# Mode
STRIPE_LIVE_MODE=False  # Set to True for production
```

### Settings

Configuration in `config/settings.py`:

```python
# Stripe Payment Gateway Configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_LIVE_MODE = os.getenv("STRIPE_LIVE_MODE", "False") == "True"
```

## Usage

### Creating a Subscription

```python
from apps.core.stripe_service import StripeService
from apps.core.models import TenantSubscription

# Create subscription with payment method
result = StripeService.create_subscription(
    tenant_subscription=tenant_subscription,
    payment_method_id="pm_card_visa",  # From Stripe.js
    trial_days=14,  # Optional trial period
)

# Result contains:
# - subscription_id: Stripe subscription ID
# - status: Subscription status
# - current_period_start: Billing period start
# - current_period_end: Billing period end
```

### Updating a Subscription

```python
# Change to a different plan
result = StripeService.update_subscription_plan(
    tenant_subscription=tenant_subscription,
    new_plan=premium_plan,
    prorate=True,  # Prorate the change
)
```

### Cancelling a Subscription

```python
# Cancel immediately
result = StripeService.cancel_subscription(
    tenant_subscription=tenant_subscription,
    immediately=True,
)

# Or cancel at period end
result = StripeService.cancel_subscription(
    tenant_subscription=tenant_subscription,
    immediately=False,
)
```

### Syncing Plans with Stripe

```python
# Run management command to sync all active plans
python manage.py sync_stripe_plans

# Dry run to see what would be created
python manage.py sync_stripe_plans --dry-run
```

## Webhook Setup

### 1. Configure Webhook Endpoint

In Stripe Dashboard (https://dashboard.stripe.com/webhooks):

1. Click "Add endpoint"
2. Enter URL: `https://yourdomain.com/webhooks/stripe/`
3. Select events to listen for:
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `customer.subscription.trial_will_end`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
   - `invoice.upcoming`
   - `customer.created`
   - `customer.updated`
   - `customer.deleted`
4. Copy the webhook signing secret
5. Add to `.env` as `STRIPE_WEBHOOK_SECRET`

### 2. Test Webhooks Locally

Use Stripe CLI for local testing:

```bash
# Install Stripe CLI
# https://stripe.com/docs/stripe-cli

# Login
stripe login

# Forward webhooks to local server
stripe listen --forward-to localhost:8000/webhooks/stripe/

# Trigger test events
stripe trigger customer.subscription.created
stripe trigger invoice.payment_succeeded
```

## Security

### Webhook Signature Verification

All webhook requests are verified using Stripe's signature:

```python
event = stripe.Webhook.construct_event(
    payload, sig_header, webhook_secret
)
```

Invalid signatures are rejected with 400 Bad Request.

### RLS (Row-Level Security)

All database operations use RLS bypass for webhook handlers since they run without user context:

```python
with bypass_rls():
    tenant_subscription = TenantSubscription.objects.get(...)
    tenant_subscription.status = new_status
    tenant_subscription.save()
```

### API Key Security

- Never commit API keys to version control
- Use environment variables for all keys
- Rotate keys quarterly
- Use test keys for development
- Use live keys only in production

## Error Handling

### Stripe API Errors

All Stripe API calls are wrapped in try-except blocks:

```python
try:
    customer = stripe.Customer.create(...)
except stripe.error.CardError as e:
    # Card was declined
    logger.error(f"Card declined: {e.user_message}")
except stripe.error.RateLimitError as e:
    # Too many requests
    logger.error(f"Rate limit exceeded: {str(e)}")
except stripe.error.InvalidRequestError as e:
    # Invalid parameters
    logger.error(f"Invalid request: {str(e)}")
except stripe.error.AuthenticationError as e:
    # Authentication failed
    logger.error(f"Authentication failed: {str(e)}")
except stripe.error.APIConnectionError as e:
    # Network communication failed
    logger.error(f"Network error: {str(e)}")
except stripe.error.StripeError as e:
    # Generic Stripe error
    logger.error(f"Stripe error: {str(e)}")
```

### Webhook Error Handling

Webhook handlers catch all exceptions and return appropriate HTTP status codes:

- **200 OK** - Event processed successfully
- **400 Bad Request** - Invalid payload or signature
- **500 Internal Server Error** - Processing error (Stripe will retry)

## Testing

### Unit Tests

Fast tests using mocks (no API calls):

```bash
docker compose exec web pytest tests/test_stripe_integration.py -v
```

### Integration Tests

Real API calls to Stripe test environment:

```bash
# Set up test API keys in .env first
docker compose exec web pytest tests/test_stripe_integration_real.py -v
```

See `tests/STRIPE_INTEGRATION_TESTING.md` for detailed testing instructions.

## Monitoring

### Logs

All Stripe operations are logged:

```python
logger.info(f"Created Stripe customer {customer.id} for tenant {tenant.id}")
logger.error(f"Failed to create subscription: {str(e)}")
```

### Metrics

Monitor these metrics:

- Subscription creation success rate
- Payment success rate
- Webhook processing time
- Failed payment attempts
- Tenant suspension rate

### Alerts

Set up alerts for:

- Webhook signature verification failures
- High payment failure rate
- Stripe API errors
- Webhook processing errors

## Troubleshooting

### Subscription Not Created

1. Check Stripe dashboard for errors
2. Verify API keys are correct
3. Check payment method is valid
4. Review application logs

### Webhooks Not Received

1. Verify webhook endpoint is accessible
2. Check webhook secret is correct
3. Verify events are selected in Stripe dashboard
4. Check firewall/security group settings

### Payment Failures

1. Check card details are valid
2. Verify sufficient funds
3. Check for fraud detection blocks
4. Review Stripe dashboard for decline reason

### Tenant Not Suspended

1. Check webhook is being received
2. Verify webhook handler is processing correctly
3. Check tenant status in database
4. Review application logs for errors

## Best Practices

1. **Always use test mode** for development
2. **Test webhooks** before going live
3. **Monitor webhook failures** and set up alerts
4. **Handle idempotency** - webhooks may be sent multiple times
5. **Log everything** for debugging
6. **Use metadata** to link Stripe resources to your models
7. **Implement retry logic** for API calls
8. **Keep Stripe library updated** for security patches
9. **Test subscription lifecycle** end-to-end
10. **Document custom logic** for future maintenance

## References

- [Stripe API Documentation](https://stripe.com/docs/api)
- [Stripe Webhooks Guide](https://stripe.com/docs/webhooks)
- [Stripe Testing Guide](https://stripe.com/docs/testing)
- [Stripe Security Best Practices](https://stripe.com/docs/security)
- [Stripe Subscriptions Guide](https://stripe.com/docs/billing/subscriptions/overview)
