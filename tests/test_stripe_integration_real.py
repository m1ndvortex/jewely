"""
Real integration tests for Stripe payment gateway.

These tests make actual API calls to Stripe's test environment to verify
the integration works correctly. They require valid Stripe test API keys.

Run with: pytest tests/test_stripe_integration_real.py -v -s
"""

import time
from decimal import Decimal

from django.conf import settings

import pytest
import stripe

from apps.core.models import SubscriptionPlan, Tenant, TenantSubscription
from apps.core.stripe_service import StripeService
from apps.core.tenant_context import bypass_rls

# Skip these tests if Stripe keys are not configured
pytestmark = pytest.mark.skipif(
    not settings.STRIPE_SECRET_KEY or settings.STRIPE_SECRET_KEY == "",
    reason="Stripe API keys not configured. Set STRIPE_SECRET_KEY in environment.",
)


@pytest.fixture(scope="module")
def stripe_test_mode():
    """Ensure we're using Stripe test mode."""
    original_key = stripe.api_key
    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Verify we're in test mode
    assert stripe.api_key.startswith("sk_test_"), "Must use Stripe test API key"

    yield

    stripe.api_key = original_key


@pytest.fixture
def test_subscription_plan(db):
    """Create a test subscription plan."""
    with bypass_rls():
        plan = SubscriptionPlan.objects.create(
            name=f"Test Plan {int(time.time())}",
            description="Integration test plan",
            price=Decimal("29.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=5,
            branch_limit=1,
            inventory_limit=1000,
        )
    yield plan

    # Cleanup
    with bypass_rls():
        plan.delete()


@pytest.fixture
def test_tenant(db, test_subscription_plan):
    """Create a test tenant."""
    with bypass_rls():
        tenant = Tenant.objects.create(
            company_name=f"Test Shop {int(time.time())}",
            slug=f"test-shop-{int(time.time())}",
            status=Tenant.ACTIVE,
        )
    yield tenant

    # Cleanup
    with bypass_rls():
        tenant.delete()


@pytest.fixture
def test_tenant_subscription(db, test_tenant, test_subscription_plan):
    """Create a test tenant subscription."""
    with bypass_rls():
        subscription = TenantSubscription.objects.create(
            tenant=test_tenant,
            plan=test_subscription_plan,
            status=TenantSubscription.STATUS_TRIAL,
        )
    yield subscription

    # Cleanup Stripe resources
    if subscription.stripe_subscription_id:
        try:
            stripe.Subscription.delete(subscription.stripe_subscription_id)
        except stripe.error.StripeError:
            pass

    if subscription.stripe_customer_id:
        try:
            stripe.Customer.delete(subscription.stripe_customer_id)
        except stripe.error.StripeError:
            pass

    with bypass_rls():
        subscription.delete()


@pytest.mark.integration
class TestStripeRealIntegration:
    """Real integration tests with Stripe API."""

    def test_create_stripe_customer(self, stripe_test_mode, test_tenant):
        """Test creating a real Stripe customer."""
        # Create customer
        customer_id = StripeService.create_customer(
            tenant=test_tenant,
            email="test@example.com",
            name=test_tenant.company_name,
        )

        # Verify customer was created
        assert customer_id.startswith("cus_")

        # Retrieve customer from Stripe
        customer = stripe.Customer.retrieve(customer_id)
        assert customer.email == "test@example.com"
        assert customer.metadata["tenant_id"] == str(test_tenant.id)

        # Cleanup
        stripe.Customer.delete(customer_id)

    def test_create_and_cancel_subscription(
        self, stripe_test_mode, test_tenant_subscription, test_subscription_plan
    ):
        """Test creating and cancelling a real Stripe subscription."""
        # Create a test payment method
        payment_method = stripe.PaymentMethod.create(
            type="card",
            card={
                "number": "4242424242424242",  # Stripe test card
                "exp_month": 12,
                "exp_year": 2025,
                "cvc": "123",
            },
        )

        try:
            # Create subscription
            result = StripeService.create_subscription(
                tenant_subscription=test_tenant_subscription,
                payment_method_id=payment_method.id,
            )

            # Verify subscription was created
            assert result["subscription_id"].startswith("sub_")
            assert result["status"] in ["active", "trialing"]

            # Verify in database
            with bypass_rls():
                test_tenant_subscription.refresh_from_db()
                assert test_tenant_subscription.stripe_subscription_id
                assert test_tenant_subscription.stripe_customer_id
                assert test_tenant_subscription.status == TenantSubscription.STATUS_ACTIVE

            # Retrieve subscription from Stripe
            stripe_sub = stripe.Subscription.retrieve(result["subscription_id"])
            assert stripe_sub.status in ["active", "trialing"]
            assert stripe_sub.metadata["tenant_id"] == str(test_tenant_subscription.tenant.id)

            # Cancel subscription
            cancel_result = StripeService.cancel_subscription(
                tenant_subscription=test_tenant_subscription,
                immediately=True,
            )

            # Verify cancellation
            assert cancel_result["status"] == "canceled"

            with bypass_rls():
                test_tenant_subscription.refresh_from_db()
                assert test_tenant_subscription.status == TenantSubscription.STATUS_CANCELLED

        finally:
            # Cleanup payment method
            try:
                stripe.PaymentMethod.detach(payment_method.id)
            except stripe.error.StripeError:
                pass

    def test_update_subscription_plan(
        self, stripe_test_mode, test_tenant_subscription, test_subscription_plan, db
    ):
        """Test updating a subscription to a new plan."""
        # Create a test payment method
        payment_method = stripe.PaymentMethod.create(
            type="card",
            card={
                "number": "4242424242424242",
                "exp_month": 12,
                "exp_year": 2025,
                "cvc": "123",
            },
        )

        try:
            # Create initial subscription
            StripeService.create_subscription(
                tenant_subscription=test_tenant_subscription,
                payment_method_id=payment_method.id,
            )

            # Create new plan
            with bypass_rls():
                new_plan = SubscriptionPlan.objects.create(
                    name=f"Premium Plan {int(time.time())}",
                    description="Premium test plan",
                    price=Decimal("99.99"),
                    billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
                    user_limit=20,
                    branch_limit=5,
                    inventory_limit=10000,
                )

            try:
                # Update to new plan
                result = StripeService.update_subscription_plan(
                    tenant_subscription=test_tenant_subscription,
                    new_plan=new_plan,
                    prorate=True,
                )

                # Verify update
                assert result["plan_name"] == new_plan.name

                with bypass_rls():
                    test_tenant_subscription.refresh_from_db()
                    assert test_tenant_subscription.plan == new_plan

                # Verify in Stripe
                stripe_sub = stripe.Subscription.retrieve(
                    test_tenant_subscription.stripe_subscription_id
                )
                assert stripe_sub.metadata["plan_id"] == str(new_plan.id)

            finally:
                # Cleanup new plan
                with bypass_rls():
                    new_plan.delete()

        finally:
            # Cleanup
            try:
                stripe.PaymentMethod.detach(payment_method.id)
            except stripe.error.StripeError:
                pass

    def test_retrieve_subscription(self, stripe_test_mode, test_tenant_subscription):
        """Test retrieving a subscription from Stripe."""
        # Create a test payment method
        payment_method = stripe.PaymentMethod.create(
            type="card",
            card={
                "number": "4242424242424242",
                "exp_month": 12,
                "exp_year": 2025,
                "cvc": "123",
            },
        )

        try:
            # Create subscription
            result = StripeService.create_subscription(
                tenant_subscription=test_tenant_subscription,
                payment_method_id=payment_method.id,
            )

            # Retrieve subscription
            retrieved = StripeService.retrieve_subscription(result["subscription_id"])

            # Verify
            assert retrieved["id"] == result["subscription_id"]
            assert retrieved["status"] in ["active", "trialing"]
            assert "current_period_start" in retrieved
            assert "current_period_end" in retrieved

        finally:
            # Cleanup
            try:
                stripe.PaymentMethod.detach(payment_method.id)
            except stripe.error.StripeError:
                pass

    def test_create_payment_intent(self, stripe_test_mode, test_tenant_subscription):
        """Test creating a payment intent."""
        # Create customer first
        customer_id = StripeService.create_customer(
            tenant=test_tenant_subscription.tenant,
            email="test@example.com",
        )

        try:
            with bypass_rls():
                test_tenant_subscription.stripe_customer_id = customer_id
                test_tenant_subscription.save()

            # Create payment intent
            result = StripeService.create_payment_intent(
                amount=Decimal("50.00"),
                currency="usd",
                customer_id=customer_id,
                metadata={"tenant_id": str(test_tenant_subscription.tenant.id)},
            )

            # Verify
            assert result["id"].startswith("pi_")
            assert result["client_secret"]
            assert result["status"] in ["requires_payment_method", "requires_confirmation"]

            # Verify in Stripe
            intent = stripe.PaymentIntent.retrieve(result["id"])
            assert intent.amount == 5000  # $50.00 in cents
            assert intent.currency == "usd"
            assert intent.customer == customer_id

        finally:
            # Cleanup
            try:
                stripe.Customer.delete(customer_id)
            except stripe.error.StripeError:
                pass

    def test_subscription_with_trial(self, stripe_test_mode, test_tenant_subscription):
        """Test creating a subscription with trial period."""
        # Create subscription with 14-day trial
        result = StripeService.create_subscription(
            tenant_subscription=test_tenant_subscription,
            payment_method_id=None,  # No payment method needed for trial
            trial_days=14,
        )

        # Verify subscription was created with trial
        assert result["subscription_id"].startswith("sub_")

        # Verify in Stripe
        stripe_sub = stripe.Subscription.retrieve(result["subscription_id"])
        assert stripe_sub.status == "trialing"
        assert stripe_sub.trial_end is not None

        # Verify trial period is approximately 14 days
        trial_duration = stripe_sub.trial_end - stripe_sub.trial_start
        assert 13 * 24 * 3600 < trial_duration < 15 * 24 * 3600  # Between 13-15 days

    def test_error_handling_invalid_payment_method(
        self, stripe_test_mode, test_tenant_subscription
    ):
        """Test error handling with invalid payment method."""
        with pytest.raises(stripe.error.StripeError):
            StripeService.create_subscription(
                tenant_subscription=test_tenant_subscription,
                payment_method_id="pm_invalid_12345",
            )

    def test_error_handling_invalid_subscription(self, stripe_test_mode):
        """Test error handling when retrieving invalid subscription."""
        with pytest.raises(stripe.error.StripeError):
            StripeService.retrieve_subscription("sub_invalid_12345")
