# Webhook Delivery System Implementation

## Task 23.3: Implement webhook delivery

**Status:** ✅ COMPLETE

## Overview

Implemented a complete webhook delivery system with HMAC signing, exponential backoff retry logic, delivery tracking, and failure alerting per Requirement 32 - Webhook and Integration Management.

## Requirements Satisfied

### ✅ Requirement 32.1: Register webhook URLs
- Webhooks can be registered with tenant-specific URLs
- Multiple webhooks can subscribe to the same events

### ✅ Requirement 32.2: Select events
- Tenants can select which events trigger webhooks
- Supported events: sale.created, sale.updated, sale.refunded, inventory.created, inventory.updated, inventory.low_stock, customer.created, customer.updated, repair_order.created, repair_order.status_changed, purchase_order.created, purchase_order.received

### ✅ Requirement 32.3: HMAC payload signing
- All webhook payloads are signed with HMAC-SHA256
- Signature included in `X-Webhook-Signature` header
- Recipients can verify payload authenticity

### ✅ Requirement 32.4: Automatic retry with exponential backoff
- Failed deliveries automatically retry up to 5 times
- Exponential backoff schedule:
  - 1st retry: 1 minute
  - 2nd retry: 5 minutes
  - 3rd retry: 15 minutes
  - 4th retry: 1 hour
  - 5th retry: 4 hours
- Periodic task runs every minute to process retries

### ✅ Requirement 32.5: Track delivery status
- Status tracking: PENDING, SUCCESS, FAILED, RETRYING
- Tracks attempt count and next retry time
- Records completion timestamps

### ✅ Requirement 32.6: Log request/response data
- Logs HTTP status codes
- Stores response body (truncated to 10KB)
- Records response headers
- Tracks request duration in milliseconds
- Stores error messages for failures

### ✅ Requirement 32.7: Alert on consistent failures
- Alerts sent on 3rd, 5th, and 10th consecutive failure
- In-app notifications created for webhook creator and tenant owner
- Webhooks automatically disabled after 10 consecutive failures
- Detailed error information included in alerts

## Files Created

### 1. `apps/core/webhook_tasks.py` (148 lines)
Celery tasks for webhook delivery:
- `deliver_webhook()` - Main delivery task with HMAC signing and retry logic
- `send_webhook_failure_alert()` - Creates notifications for failures
- `retry_failed_webhooks()` - Periodic task to retry failed deliveries
- `cleanup_old_deliveries()` - Cleanup task for old delivery records
- Helper functions for HMAC generation and retry delay calculation

### 2. `apps/core/webhook_utils.py` (55 lines)
Utility functions to trigger webhooks from application events:
- `trigger_webhook_event()` - Generic function to trigger webhooks
- Event-specific trigger functions for sales, inventory, customers, repair orders, and purchase orders

### 3. `apps/core/test_webhook_delivery.py` (15 tests)
Unit tests with mocked HTTP responses:
- HMAC signature generation and verification
- Successful delivery tracking
- Failed delivery with retry scheduling
- Timeout handling
- Exponential backoff calculation
- Max retries enforcement
- Failure alert creation
- Auto-disable after 10 failures
- Periodic retry task
- Cleanup task
- Event triggering

### 4. `apps/core/test_webhook_delivery_integration.py` (11 tests)
Integration tests with REAL HTTP server and REAL database:
- Real HTTP requests to test server
- Real database operations (no mocks)
- HMAC signature verification by receiver
- Timeout testing with slow server
- Multiple webhooks for same event
- Failure alerts with real notifications
- Exponential backoff timing verification
- Cleanup with real database deletes

### 5. `config/celery.py` (updated)
Added webhook task configuration:
- Periodic retry task (every minute)
- Weekly cleanup task (Sunday 4 AM)
- Task routing to dedicated "webhooks" queue with priority 8

## Test Results

**All 26 tests passing:**
- 15 unit tests (with mocked HTTP)
- 11 integration tests (with REAL HTTP and database)

```
======================== 26 passed in 122.51s (0:02:02) ========================
```

## Key Features

### HMAC Signing
- SHA-256 HMAC signatures for payload verification
- Signature sent in `X-Webhook-Signature` header
- Additional headers: `X-Webhook-Event`, `X-Webhook-Delivery`, `X-Webhook-Timestamp`

### Retry Logic
- Automatic retry scheduling with exponential backoff
- Maximum 5 attempts per delivery
- Retries skip inactive webhooks
- Failed deliveries tracked with detailed error messages

### Delivery Tracking
- Complete request/response logging
- Duration tracking in milliseconds
- Status transitions: PENDING → SUCCESS or PENDING → RETRYING → FAILED
- Webhook-level success/failure tracking

### Failure Handling
- Consecutive failure counter on webhook
- Alerts at 3, 5, and 10 failures
- Auto-disable after 10 consecutive failures
- Detailed error messages and timestamps

### Cleanup
- Successful deliveries deleted after 90 days
- Failed deliveries deleted after 120 days
- Weekly automated cleanup task

## Integration Points

### Triggering Webhooks
```python
from apps.core.webhook_utils import trigger_sale_created

# Trigger webhook when sale is created
trigger_sale_created(sale)
```

### Verifying Signatures (Receiver Side)
```python
import hmac
import hashlib

# Receiver verifies signature
received_signature = request.headers['X-Webhook-Signature']
payload_bytes = request.body
expected_signature = hmac.new(
    webhook_secret.encode('utf-8'),
    payload_bytes,
    hashlib.sha256
).hexdigest()

if received_signature == expected_signature:
    # Signature valid, process webhook
    pass
```

## Celery Configuration

### Periodic Tasks
- `retry-failed-webhooks`: Runs every 60 seconds
- `cleanup-old-webhook-deliveries`: Runs weekly on Sunday at 4 AM

### Task Routing
- All webhook tasks route to "webhooks" queue
- Priority: 8 (high priority)

## Database Schema

### WebhookDelivery Model
- Tracks individual delivery attempts
- Stores payload, signature, status
- Records response data and errors
- Manages retry scheduling

### Webhook Model
- Stores webhook configuration
- Tracks consecutive failures
- Records last success/failure timestamps
- Auto-generates HMAC secrets

## Security

- HMAC-SHA256 payload signing
- 30-second request timeout
- No redirect following
- Webhook secrets auto-generated (48-byte URL-safe)
- Inactive webhooks skip delivery

## Performance

- Asynchronous delivery via Celery
- Dedicated queue for webhook tasks
- Response body truncated to 10KB
- Efficient database indexes for retry queries

## Monitoring

- Delivery status tracking
- Duration metrics
- Failure rate monitoring
- Alert notifications
- Comprehensive logging

## Compliance

All requirements from Requirement 32 (Webhook and Integration Management) are fully satisfied with comprehensive test coverage using REAL HTTP requests and REAL database operations.
