# Stripe Integration Testing

This document explains how to run the real Stripe integration tests.

## Overview

The Stripe integration has two types of tests:

1. **Unit Tests** (`test_stripe_integration.py`) - Fast tests using mocks, run in CI/CD
2. **Integration Tests** (`test_stripe_integration_real.py`) - Real API calls to Stripe test environment

## Running Unit Tests

Unit tests run automatically and don't require Stripe API keys:

```bash
docker compose exec web pytest tests/test_stripe_integration.py -v
```

## Running Integration Tests

Integration tests require valid Stripe test API keys.

### Prerequisites

1. Create a Stripe account at https://stripe.com
2. Get your test API keys from https://dashboard.stripe.com/test/apikeys
3. Get your webhook secret from https://dashboard.stripe.com/test/webhooks

### Setup

1. Add Stripe test keys to your `.env` file:

```bash
# Stripe Payment Gateway (TEST MODE)
STRIPE_SECRET_KEY=sk_test_your_secret_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_publishable_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here
STRIPE_LIVE_MODE=False
```

2. Restart the Docker containers:

```bash
docker compose down
docker compose up -d
```

3. Run the integration tests:

```bash
docker compose exec web pytest tests/test_stripe_integration_real.py -v -s
```

### What the Integration Tests Do

The integration tests make real API calls to Stripe's test environment to verify:

1. **Customer Creation** - Creates a real Stripe customer with metadata
2. **Subscription Creation** - Creates a subscription with test payment method
3. **Subscription Cancellation** - Cancels an active subscription
4. **Plan Updates** - Changes subscription to a different plan with proration
5. **Subscription Retrieval** - Fetches subscription details from Stripe
6. **Payment Intents** - Creates payment intents for one-time payments
7. **Trial Periods** - Creates subscriptions with trial periods
8. **Error Handling** - Tests error scenarios with invalid data

### Test Data Cleanup

The integration tests automatically clean up all test data:
- Stripe customers are deleted after tests
- Stripe subscriptions are cancelled and deleted
- Database records are rolled back (Django test transactions)

### Important Notes

- **Never use production API keys** - Always use test mode keys (sk_test_...)
- **Test cards** - Use Stripe's test card numbers (e.g., 4242424242424242)
- **No real charges** - Test mode never processes real payments
- **Rate limits** - Stripe test mode has rate limits, run tests sequentially

### Troubleshooting

**Tests are skipped:**
- Check that STRIPE_SECRET_KEY is set in .env
- Verify the key starts with `sk_test_`
- Restart Docker containers after changing .env

**API errors:**
- Verify your Stripe account is active
- Check that test mode is enabled in Stripe dashboard
- Ensure API keys haven't expired

**Webhook tests fail:**
- Webhook tests in `test_stripe_integration.py` use mocks (no real webhooks)
- Real webhook testing requires ngrok or similar tunnel
- See Stripe documentation for webhook testing: https://stripe.com/docs/webhooks/test

## CI/CD Integration

For CI/CD pipelines:

1. **Unit tests** run on every commit (no API keys needed)
2. **Integration tests** run nightly or on release branches with encrypted secrets
3. Use GitHub Actions secrets or similar to store test API keys securely

Example GitHub Actions workflow:

```yaml
- name: Run Stripe Integration Tests
  env:
    STRIPE_SECRET_KEY: ${{ secrets.STRIPE_TEST_SECRET_KEY }}
    STRIPE_PUBLISHABLE_KEY: ${{ secrets.STRIPE_TEST_PUBLISHABLE_KEY }}
    STRIPE_WEBHOOK_SECRET: ${{ secrets.STRIPE_TEST_WEBHOOK_SECRET }}
  run: |
    docker compose exec -T web pytest tests/test_stripe_integration_real.py -v
```

## Manual Testing

For manual testing of the Stripe integration:

1. Start the development server
2. Create a subscription plan in the admin panel
3. Assign it to a tenant
4. Use Stripe's test card numbers to simulate payments
5. Check webhook events in Stripe dashboard

Test card numbers:
- Success: 4242424242424242
- Decline: 4000000000000002
- Insufficient funds: 4000000000009995

See full list: https://stripe.com/docs/testing#cards
