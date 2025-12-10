# Tenant Subscription Purchase System Implementation Plan

**Date:** December 9, 2025  
**Status:** Enterprise Production Ready Roadmap  
**Complexity:** High - Multi-tenant, Payment Integration, RLS Enforcement

## Overview

Implement a comprehensive self-service subscription purchase system that allows tenants to:
- View available subscription plans
- Purchase subscriptions for 1, 3, 6, or 12 months with progressive discounts
- Manage their active subscriptions
- Upgrade/downgrade plans
- View billing history
- Pay via multiple payment gateways (Iranian banks, PayPal, Credit Cards, Crypto)

## Architecture Requirements

### 1. **Data Models** (Priority: HIGH)

#### 1.1 SubscriptionPurchase Model
```python
class SubscriptionPurchase(TenantAwareModel):
    """
    Tracks subscription purchase transactions.
    Each purchase creates or extends a TenantSubscription.
    """
    # Core fields
    tenant = ForeignKey(Tenant)
    subscription_plan = ForeignKey(SubscriptionPlan)
    purchased_by = ForeignKey(User)  # User who made purchase
    
    # Billing period
    billing_period_months = IntegerField(choices=[(1, '1 Month'), (3, '3 Months'), (6, '6 Months'), (12, '1 Year')])
    start_date = DateField()
    end_date = DateField()  # Calculated based on billing_period
    
    # Pricing
    base_price = DecimalField()  # Plan price × months
    discount_percentage = DecimalField()  # Discount based on period
    discount_amount = DecimalField()
    final_price = DecimalField()  # After discount
    currency = CharField(default='USD')
    
    # Payment
    payment_status = CharField(choices=[
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled')
    ])
    payment_method = CharField(choices=[
        ('bank_transfer_iran', 'Iranian Bank Transfer'),
        ('paypal', 'PayPal'),
        ('stripe', 'Credit/Debit Card'),
        ('crypto_btc', 'Bitcoin'),
        ('crypto_eth', 'Ethereum'),
        ('crypto_usdt', 'USDT'),
    ])
    payment_gateway_transaction_id = CharField(blank=True)
    payment_completed_at = DateTimeField(null=True)
    
    # Metadata
    invoice_number = CharField(unique=True)  # AUTO-INV-2025-12-09-XXXXX
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    # RLS
    class Meta:
        db_table = 'subscription_purchases'
        indexes = [...]
        permissions = [...]
```

#### 1.2 PaymentTransaction Model
```python
class PaymentTransaction(TenantAwareModel):
    """
    Detailed payment transaction log.
    One SubscriptionPurchase can have multiple payment attempts.
    """
    subscription_purchase = ForeignKey(SubscriptionPurchase)
    tenant = ForeignKey(Tenant)
    
    # Transaction details
    transaction_id = UUIDField(default=uuid4, unique=True)
    payment_gateway = CharField()  # 'paypal', 'stripe', 'crypto', etc.
    gateway_transaction_id = CharField(blank=True)
    
    # Amount
    amount = DecimalField()
    currency = CharField()
    exchange_rate = DecimalField(null=True)  # For crypto/IRR conversions
    
    # Status
    status = CharField(choices=[...])
    response_data = JSONField()  # Gateway response
    error_message = TextField(blank=True)
    
    # Timestamps
    initiated_at = DateTimeField(auto_now_add=True)
    completed_at = DateTimeField(null=True)
    
    class Meta:
        db_table = 'payment_transactions'
```

#### 1.3 SubscriptionDiscount Model
```python
class SubscriptionDiscount(models.Model):
    """
    Configurable discount rules for multi-month purchases.
    Platform admin configurable.
    """
    billing_period_months = IntegerField(unique=True)
    discount_percentage = DecimalField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    description = CharField()  # "3 months - Save 10%"
    is_active = BooleanField(default=True)
    
    # Audit
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscription_discounts'
        ordering = ['billing_period_months']
```

Default discount structure:
- 1 month: 0% discount
- 3 months: 10% discount
- 6 months: 15% discount
- 12 months: 20% discount

#### 1.4 Update TenantSubscription Model
Add fields to track purchase history:
```python
# Add to existing TenantSubscription model
last_purchase = ForeignKey(SubscriptionPurchase, null=True, related_name='active_subscription')
auto_renew = BooleanField(default=False)
auto_renew_payment_method = CharField(blank=True)
next_billing_date = DateField(null=True)
```

---

### 2. **Pricing Calculator Service** (Priority: HIGH)

```python
# apps/core/subscription_pricing.py

class SubscriptionPricingCalculator:
    """
    Enterprise-grade pricing calculator with discount logic.
    """
    
    @staticmethod
    def calculate_price(
        subscription_plan: SubscriptionPlan,
        billing_period_months: int,
        currency: str = 'USD'
    ) -> Dict[str, Decimal]:
        """
        Calculate final price with discounts.
        
        Returns:
            {
                'base_price': Decimal('100.00'),
                'discount_percentage': Decimal('10.00'),
                'discount_amount': Decimal('10.00'),
                'final_price': Decimal('90.00'),
                'monthly_equivalent': Decimal('30.00'),
                'savings': Decimal('10.00')
            }
        """
        # Get plan price based on currency
        if currency == 'USD':
            monthly_price = subscription_plan.price
        elif currency == 'IRR':
            monthly_price = subscription_plan.price_irr
        else:
            raise ValueError(f"Unsupported currency: {currency}")
        
        # Calculate base price (monthly × months)
        base_price = monthly_price * billing_period_months
        
        # Get discount for billing period
        discount = SubscriptionDiscount.objects.filter(
            billing_period_months=billing_period_months,
            is_active=True
        ).first()
        
        discount_percentage = discount.discount_percentage if discount else Decimal('0')
        discount_amount = (base_price * discount_percentage) / Decimal('100')
        final_price = base_price - discount_amount
        
        return {
            'base_price': base_price,
            'discount_percentage': discount_percentage,
            'discount_amount': discount_amount,
            'final_price': final_price,
            'monthly_equivalent': final_price / billing_period_months,
            'savings': discount_amount,
            'currency': currency
        }
    
    @staticmethod
    def get_all_pricing_options(subscription_plan: SubscriptionPlan, currency: str = 'USD'):
        """Get pricing for all billing periods (1, 3, 6, 12 months)."""
        periods = [1, 3, 6, 12]
        return {
            period: SubscriptionPricingCalculator.calculate_price(
                subscription_plan, period, currency
            )
            for period in periods
        }
```

---

### 3. **Views & Templates** (Priority: HIGH)

#### 3.1 Tenant Subscription Dashboard View
**URL:** `/subscriptions/`  
**Template:** `tenant/subscriptions/dashboard.html`

Features:
- Current subscription status
- Days remaining
- Usage statistics (via SubscriptionEnforcementService)
- Quick upgrade button
- Billing history table

#### 3.2 Available Plans View
**URL:** `/subscriptions/plans/`  
**Template:** `tenant/subscriptions/available_plans.html`

Features:
- Display all active subscription plans
- Pricing table with 1/3/6/12 month options
- Highlight current plan
- Compare plans side-by-side
- "Upgrade" / "Purchase" buttons

#### 3.3 Purchase Checkout View
**URL:** `/subscriptions/purchase/<plan_id>/`  
**Template:** `tenant/subscriptions/checkout.html`

Features:
- Plan summary
- Billing period selector (tabs for 1/3/6/12 months)
- Real-time price calculation with discount display
- Payment method selector
- Terms & Conditions checkbox
- Purchase summary panel

#### 3.4 Payment Processing View
**URL:** `/subscriptions/payment/<purchase_id>/`  
**Template:** `tenant/subscriptions/payment.html`

Features:
- Payment gateway integration (placeholder)
- Loading state during processing
- Success/failure handling
- Redirect to invoice on success

#### 3.5 Billing History View
**URL:** `/subscriptions/billing-history/`  
**Template:** `tenant/subscriptions/billing_history.html`

Features:
- Table of all purchases
- Invoice download links
- Payment status
- Filter by date/status

---

### 4. **Payment Gateway Abstraction** (Priority: MEDIUM)

```python
# apps/payments/gateways/base.py

class PaymentGatewayInterface(ABC):
    """Abstract base for all payment gateways."""
    
    @abstractmethod
    def create_payment(self, amount: Decimal, currency: str, metadata: dict) -> dict:
        """Initialize payment and return gateway URL or token."""
        pass
    
    @abstractmethod
    def verify_payment(self, transaction_id: str) -> dict:
        """Verify payment completion."""
        pass
    
    @abstractmethod
    def refund_payment(self, transaction_id: str, amount: Decimal) -> dict:
        """Process refund."""
        pass


# apps/payments/gateways/placeholder.py

class PlaceholderGateway(PaymentGatewayInterface):
    """Placeholder for payment testing."""
    
    def create_payment(self, amount, currency, metadata):
        return {
            'status': 'pending',
            'payment_url': '/subscriptions/payment/mock/',
            'transaction_id': f'MOCK-{uuid4()}'
        }
    
    def verify_payment(self, transaction_id):
        # Auto-approve for testing
        return {'status': 'completed', 'transaction_id': transaction_id}


# apps/payments/gateways/factory.py

class PaymentGatewayFactory:
    """Factory to get appropriate payment gateway."""
    
    GATEWAYS = {
        'placeholder': PlaceholderGateway,
        # 'paypal': PayPalGateway,  # Future
        # 'stripe': StripeGateway,   # Future
        # 'crypto_btc': BitcoinGateway,  # Future
    }
    
    @classmethod
    def get_gateway(cls, gateway_name: str) -> PaymentGatewayInterface:
        gateway_class = cls.GATEWAYS.get(gateway_name)
        if not gateway_class:
            raise ValueError(f"Unknown gateway: {gateway_name}")
        return gateway_class()
```

---

### 5. **Subscription Purchase Service** (Priority: HIGH)

```python
# apps/core/subscription_purchase_service.py

class SubscriptionPurchaseService:
    """
    Business logic for subscription purchases.
    Handles purchase creation, payment processing, subscription activation.
    """
    
    @staticmethod
    def initiate_purchase(
        tenant: Tenant,
        user: User,
        subscription_plan: SubscriptionPlan,
        billing_period_months: int,
        payment_method: str,
        currency: str = 'USD'
    ) -> SubscriptionPurchase:
        """
        Create a new subscription purchase.
        Does NOT activate subscription until payment is confirmed.
        """
        # Calculate pricing
        pricing = SubscriptionPricingCalculator.calculate_price(
            subscription_plan, billing_period_months, currency
        )
        
        # Determine start/end dates
        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=30 * billing_period_months)
        
        # Create purchase record
        purchase = SubscriptionPurchase.objects.create(
            tenant=tenant,
            subscription_plan=subscription_plan,
            purchased_by=user,
            billing_period_months=billing_period_months,
            start_date=start_date,
            end_date=end_date,
            base_price=pricing['base_price'],
            discount_percentage=pricing['discount_percentage'],
            discount_amount=pricing['discount_amount'],
            final_price=pricing['final_price'],
            currency=currency,
            payment_status='pending',
            payment_method=payment_method,
            invoice_number=SubscriptionPurchaseService._generate_invoice_number()
        )
        
        return purchase
    
    @staticmethod
    def process_payment(purchase: SubscriptionPurchase) -> PaymentTransaction:
        """
        Process payment via selected gateway.
        """
        gateway = PaymentGatewayFactory.get_gateway(
            purchase.payment_method or 'placeholder'
        )
        
        # Create transaction record
        transaction = PaymentTransaction.objects.create(
            subscription_purchase=purchase,
            tenant=purchase.tenant,
            payment_gateway=purchase.payment_method,
            amount=purchase.final_price,
            currency=purchase.currency,
            status='pending'
        )
        
        try:
            # Initiate payment with gateway
            response = gateway.create_payment(
                amount=purchase.final_price,
                currency=purchase.currency,
                metadata={
                    'purchase_id': str(purchase.id),
                    'tenant_id': str(purchase.tenant.id),
                    'invoice_number': purchase.invoice_number
                }
            )
            
            transaction.gateway_transaction_id = response.get('transaction_id')
            transaction.response_data = response
            transaction.status = response.get('status', 'processing')
            transaction.save()
            
            return transaction
            
        except Exception as e:
            transaction.status = 'failed'
            transaction.error_message = str(e)
            transaction.save()
            raise
    
    @staticmethod
    def confirm_payment(purchase: SubscriptionPurchase, transaction_id: str):
        """
        Confirm payment and activate subscription.
        Called by webhook or after payment verification.
        """
        with transaction.atomic():
            # Update purchase status
            purchase.payment_status = 'completed'
            purchase.payment_gateway_transaction_id = transaction_id
            purchase.payment_completed_at = timezone.now()
            purchase.save()
            
            # Activate or extend subscription
            SubscriptionPurchaseService._activate_subscription(purchase)
            
            # Send confirmation email
            SubscriptionPurchaseService._send_purchase_confirmation(purchase)
            
            # Create audit log
            AuditLog.objects.create(
                tenant=purchase.tenant,
                user=purchase.purchased_by,
                action='subscription_purchase_completed',
                details={
                    'purchase_id': str(purchase.id),
                    'plan': purchase.subscription_plan.name,
                    'amount': float(purchase.final_price),
                    'period_months': purchase.billing_period_months
                }
            )
    
    @staticmethod
    def _activate_subscription(purchase: SubscriptionPurchase):
        """
        Activate or extend tenant subscription based on purchase.
        """
        tenant = purchase.tenant
        
        try:
            # Get existing subscription
            subscription = tenant.subscription
            
            # If upgrading to a different plan
            if subscription.plan != purchase.subscription_plan:
                subscription.plan = purchase.subscription_plan
                subscription.status = 'active'
                subscription.start_date = purchase.start_date
                subscription.end_date = purchase.end_date
            else:
                # Extending current plan
                if subscription.end_date and subscription.end_date > timezone.now().date():
                    # Extend from current end date
                    subscription.end_date = subscription.end_date + timedelta(
                        days=30 * purchase.billing_period_months
                    )
                else:
                    # Reactivate
                    subscription.start_date = purchase.start_date
                    subscription.end_date = purchase.end_date
                    subscription.status = 'active'
            
            subscription.last_purchase = purchase
            subscription.save()
            
        except TenantSubscription.DoesNotExist:
            # Create new subscription
            subscription = TenantSubscription.objects.create(
                tenant=tenant,
                plan=purchase.subscription_plan,
                status='active',
                start_date=purchase.start_date,
                end_date=purchase.end_date,
                last_purchase=purchase
            )
    
    @staticmethod
    def _generate_invoice_number() -> str:
        """Generate unique invoice number."""
        date_part = timezone.now().strftime('%Y%m%d')
        random_part = get_random_string(6, '0123456789')
        return f"INV-{date_part}-{random_part}"
```

---

### 6. **RLS Policies** (Priority: CRITICAL)

```sql
-- Migration: 0033_subscription_purchase_rls_policies.py

-- SubscriptionPurchase table RLS
ALTER TABLE subscription_purchases ENABLE ROW LEVEL SECURITY;

-- Tenants can only see their own purchases
CREATE POLICY tenant_subscription_purchases_select ON subscription_purchases
    FOR SELECT
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid);

-- Tenants can only insert their own purchases
CREATE POLICY tenant_subscription_purchases_insert ON subscription_purchases
    FOR INSERT
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid);

-- Tenants cannot update purchases (only platform admin can)
CREATE POLICY tenant_subscription_purchases_update ON subscription_purchases
    FOR UPDATE
    USING (false);

-- Tenants cannot delete purchases
CREATE POLICY tenant_subscription_purchases_delete ON subscription_purchases
    FOR DELETE
    USING (false);

-- Platform admins can see all
CREATE POLICY admin_subscription_purchases_all ON subscription_purchases
    FOR ALL
    USING (current_setting('app.bypass_rls', TRUE)::boolean = true);


-- PaymentTransaction table RLS
ALTER TABLE payment_transactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_payment_transactions_select ON payment_transactions
    FOR SELECT
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid);

CREATE POLICY tenant_payment_transactions_insert ON payment_transactions
    FOR INSERT
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid);

CREATE POLICY admin_payment_transactions_all ON payment_transactions
    FOR ALL
    USING (current_setting('app.bypass_rls', TRUE)::boolean = true);
```

---

### 7. **URL Routing** (Priority: HIGH)

```python
# apps/core/urls.py (tenant subscriptions section)

urlpatterns = [
    # ... existing patterns ...
    
    # Tenant Subscription Management
    path(
        'subscriptions/',
        subscription_tenant_views.SubscriptionDashboardView.as_view(),
        name='tenant_subscription_dashboard'
    ),
    path(
        'subscriptions/plans/',
        subscription_tenant_views.AvailablePlansView.as_view(),
        name='tenant_available_plans'
    ),
    path(
        'subscriptions/purchase/<uuid:plan_id>/',
        subscription_tenant_views.PurchaseCheckoutView.as_view(),
        name='tenant_subscription_purchase'
    ),
    path(
        'subscriptions/payment/<uuid:purchase_id>/',
        subscription_tenant_views.PaymentProcessView.as_view(),
        name='tenant_subscription_payment'
    ),
    path(
        'subscriptions/payment/<uuid:purchase_id>/confirm/',
        subscription_tenant_views.PaymentConfirmView.as_view(),
        name='tenant_subscription_payment_confirm'
    ),
    path(
        'subscriptions/billing-history/',
        subscription_tenant_views.BillingHistoryView.as_view(),
        name='tenant_billing_history'
    ),
    path(
        'subscriptions/invoice/<uuid:purchase_id>/',
        subscription_tenant_views.InvoiceDownloadView.as_view(),
        name='tenant_subscription_invoice'
    ),
    
    # API endpoints for real-time pricing
    path(
        'api/subscriptions/calculate-price/',
        subscription_tenant_views.CalculatePriceAPIView.as_view(),
        name='api_calculate_subscription_price'
    ),
]
```

---

### 8. **Frontend Components** (Priority: HIGH)

#### 8.1 Subscription Dashboard Template
```html
<!-- templates/tenant/subscriptions/dashboard.html -->

{% extends "base.html" %}
{% load i18n static %}

{% block content %}
<div class="container mx-auto px-4 py-8">
    <!-- Current Subscription Card -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 mb-6">
        <h2 class="text-2xl font-bold mb-4">{% trans "Current Subscription" %}</h2>
        
        {% if subscription %}
            <div class="grid md:grid-cols-3 gap-6">
                <div>
                    <p class="text-gray-600 dark:text-gray-400 text-sm">{% trans "Plan" %}</p>
                    <p class="text-xl font-semibold">{{ subscription.plan.name }}</p>
                </div>
                <div>
                    <p class="text-gray-600 dark:text-gray-400 text-sm">{% trans "Status" %}</p>
                    <span class="px-3 py-1 rounded-full text-sm 
                        {% if subscription.status == 'active' %}bg-green-100 text-green-800{% endif %}">
                        {{ subscription.get_status_display }}
                    </span>
                </div>
                <div>
                    <p class="text-gray-600 dark:text-gray-400 text-sm">{% trans "Expires" %}</p>
                    <p class="text-xl font-semibold">{{ subscription.end_date|date:"M d, Y" }}</p>
                    <p class="text-sm text-gray-500">{{ days_remaining }} {% trans "days remaining" %}</p>
                </div>
            </div>
            
            <!-- Usage Stats -->
            <div class="mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
                <h3 class="font-semibold mb-4">{% trans "Usage Statistics" %}</h3>
                <div class="grid md:grid-cols-4 gap-4">
                    <div>
                        <p class="text-sm text-gray-600">{% trans "Users" %}</p>
                        <p class="text-lg">{{ usage.users_count }} / {{ subscription.plan.user_limit }}</p>
                    </div>
                    <!-- More usage stats -->
                </div>
            </div>
            
            <div class="mt-6">
                <a href="{% url 'core:tenant_available_plans' %}" 
                   class="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg">
                    {% trans "Upgrade Plan" %}
                </a>
            </div>
        {% else %}
            <p class="text-gray-600">{% trans "No active subscription" %}</p>
            <a href="{% url 'core:tenant_available_plans' %}" 
               class="mt-4 inline-block bg-blue-600 text-white px-6 py-2 rounded-lg">
                {% trans "Choose a Plan" %}
            </a>
        {% endif %}
    </div>
    
    <!-- Recent Purchases -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
        <h2 class="text-2xl font-bold mb-4">{% trans "Recent Purchases" %}</h2>
        <!-- Purchases table -->
    </div>
</div>
{% endblock %}
```

#### 8.2 Pricing Table Component
```html
<!-- templates/tenant/subscriptions/components/pricing_card.html -->

<div class="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 
     {% if is_current_plan %}ring-2 ring-blue-500{% endif %}">
    <h3 class="text-2xl font-bold mb-2">{{ plan.name }}</h3>
    <p class="text-gray-600 dark:text-gray-400 mb-6">{{ plan.description }}</p>
    
    <!-- Billing Period Tabs -->
    <div class="mb-6">
        <div class="flex space-x-2 mb-4" x-data="{ period: 1 }">
            <button @click="period = 1" 
                    :class="period === 1 ? 'bg-blue-600 text-white' : 'bg-gray-200'"
                    class="px-4 py-2 rounded">1 {% trans "Month" %}</button>
            <button @click="period = 3" 
                    :class="period === 3 ? 'bg-blue-600 text-white' : 'bg-gray-200'"
                    class="px-4 py-2 rounded">3 {% trans "Months" %}</button>
            <button @click="period = 6" 
                    :class="period === 6 ? 'bg-blue-600 text-white' : 'bg-gray-200'"
                    class="px-4 py-2 rounded">6 {% trans "Months" %}</button>
            <button @click="period = 12" 
                    :class="period === 12 ? 'bg-blue-600 text-white' : 'bg-gray-200'"
                    class="px-4 py-2 rounded">12 {% trans "Months" %}</button>
        </div>
        
        <!-- Price Display -->
        <div x-show="period === 1">
            <p class="text-4xl font-bold">${{ pricing.1_month.final_price }}</p>
            <p class="text-gray-600">/month</p>
        </div>
        <div x-show="period === 3">
            <p class="text-4xl font-bold">${{ pricing.3_months.final_price }}</p>
            <p class="text-sm text-green-600">{% trans "Save" %} {{ pricing.3_months.discount_percentage }}%</p>
            <p class="text-gray-600">${{ pricing.3_months.monthly_equivalent }}/month</p>
        </div>
        <!-- Repeat for 6 and 12 -->
    </div>
    
    <a :href="'/subscriptions/purchase/{{ plan.id }}/?period=' + period"
       class="block w-full bg-blue-600 hover:bg-blue-700 text-white text-center py-3 rounded-lg">
        {% if is_current_plan %}
            {% trans "Extend Subscription" %}
        {% else %}
            {% trans "Choose Plan" %}
        {% endif %}
    </a>
</div>
```

---

### 9. **Payment Webhook Handlers** (Priority: MEDIUM)

```python
# apps/payments/webhooks.py

class PaymentWebhookHandler:
    """
    Handle webhook callbacks from payment gateways.
    Each gateway will have its own handler.
    """
    
    @staticmethod
    def handle_paypal_webhook(request):
        """Handle PayPal IPN/Webhook."""
        # Verify webhook signature
        # Extract payment info
        # Find corresponding purchase
        # Confirm payment
        pass
    
    @staticmethod
    def handle_stripe_webhook(request):
        """Handle Stripe webhook."""
        pass
    
    @staticmethod
    def handle_crypto_webhook(request):
        """Handle crypto payment confirmation."""
        pass


# URLs
urlpatterns = [
    path('webhooks/paypal/', PayPal WebhookView.as_view(), name='webhook_paypal'),
    path('webhooks/stripe/', StripeWebhookView.as_view(), name='webhook_stripe'),
    path('webhooks/crypto/', CryptoWebhookView.as_view(), name='webhook_crypto'),
]
```

---

### 10. **Automated Subscription Renewal** (Priority: MEDIUM)

```python
# apps/core/tasks.py (Celery tasks)

@shared_task
def check_expiring_subscriptions():
    """
    Daily task to check for expiring subscriptions.
    Send renewal reminders.
    """
    upcoming_expiry = timezone.now().date() + timedelta(days=7)
    
    expiring_subscriptions = TenantSubscription.objects.filter(
        status='active',
        end_date__lte=upcoming_expiry,
        end_date__gte=timezone.now().date()
    )
    
    for subscription in expiring_subscriptions:
        # Send renewal reminder email
        send_renewal_reminder_email(subscription)


@shared_task
def auto_renew_subscriptions():
    """
    Process auto-renewal for subscriptions with auto_renew=True.
    """
    today = timezone.now().date()
    
    subscriptions_to_renew = TenantSubscription.objects.filter(
        status='active',
        auto_renew=True,
        end_date=today
    )
    
    for subscription in subscriptions_to_renew:
        try:
            # Create renewal purchase
            # Process payment with saved method
            # Extend subscription
            pass
        except Exception as e:
            # Send failure notification
            logger.error(f"Auto-renewal failed for {subscription.tenant}: {e}")


@shared_task
def expire_subscriptions():
    """
    Mark expired subscriptions as 'expired'.
    """
    yesterday = timezone.now().date() - timedelta(days=1)
    
    TenantSubscription.objects.filter(
        status='active',
        end_date__lt=yesterday
    ).update(status='expired')
```

---

## Implementation Phases

### **Phase 1: Foundation** (Days 1-3)
1. Create data models (SubscriptionPurchase, PaymentTransaction, SubscriptionDiscount)
2. Run migrations
3. Add RLS policies
4. Create seed data for discounts

### **Phase 2: Core Logic** (Days 4-6)
5. Implement SubscriptionPricingCalculator
6. Implement SubscriptionPurchaseService
7. Create payment gateway abstraction
8. Add placeholder gateway

### **Phase 3: UI/UX** (Days 7-10)
9. Create subscription dashboard view
10. Create available plans view
11. Create checkout flow
12. Create billing history view

### **Phase 4: Integration** (Days 11-13)
13. Connect views to services
14. Add real-time pricing API
15. Implement payment confirmation flow
16. Create invoice generation

### **Phase 5: Automation** (Days 14-15)
17. Create Celery tasks for renewals
18. Add email notifications
19. Implement webhook placeholders

### **Phase 6: Testing** (Days 16-18)
20. Unit tests for pricing calculator
21. Unit tests for purchase service
22. Integration tests for complete flow
23. E2E tests with Playwright

### **Phase 7: Polish** (Days 19-20)
24. Add comprehensive error handling
25. Optimize queries
26. Add admin panel views for purchase management
27. Documentation

---

## Security Considerations

1. **RLS Enforcement**: All purchase/payment tables have strict RLS
2. **Payment Validation**: Verify all webhook signatures
3. **Idempotency**: Prevent duplicate payments
4. **Audit Logging**: Log all purchase events
5. **Data Encryption**: Encrypt sensitive payment data
6. **CSRF Protection**: All forms have CSRF tokens
7. **Rate Limiting**: Limit purchase attempts per tenant

---

## Testing Strategy

### Unit Tests
- Pricing calculator accuracy
- Discount calculations
- Purchase creation
- Subscription activation/extension
- Invoice number generation

### Integration Tests
- Complete purchase flow
- Payment processing
- Subscription upgrade/downgrade
- Auto-renewal

### E2E Tests
- User journey from plan selection to payment
- Multiple payment methods
- Plan comparison
- Billing history

---

## Performance Optimization

1. **Database Indexes**: On tenant_id, payment_status, created_at
2. **Caching**: Cache subscription plans and discount rules
3. **Async Processing**: Payment processing via Celery
4. **Query Optimization**: Select_related/prefetch_related for purchases

---

## Monitoring & Alerts

1. **Failed Payments**: Alert on payment failure rate
2. **Expiring Subscriptions**: Daily report
3. **Revenue Metrics**: Track MRR/ARR
4. **Payment Gateway Health**: Monitor API response times

---

## Future Enhancements

1. **Trial Periods**: Auto-convert trials to paid
2. **Promo Codes**: Discount codes system
3. **Referral System**: Refer-a-friend discounts
4. **Annual Billing**: Special pricing for yearly upfront
5. **Enterprise Contracts**: Custom billing arrangements
6. **Multi-Currency**: Automatic currency conversion
7. **Tax Calculation**: VAT/GST handling
8. **Invoice Customization**: Branded invoices

---

## Success Metrics

- **Payment Success Rate**: >95%
- **Checkout Abandonment**: <20%
- **Upgrade Conversion**: >10%
- **Auto-Renewal Rate**: >60%
- **Average Billing Period**: >3 months

