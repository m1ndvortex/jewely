"""
Unit tests for Stripe payment gateway integration.

These tests use mocks to verify the logic without making real API calls.
For real integration tests that call Stripe API, see test_stripe_integration_real.py

Tests the Stripe service, webhook handlers, and subscription lifecycle
management per Requirement 5.7.
"""

import json
from datetime import datetime
from datetime import timezone as dt_timezone
from decimal import Decimal
from unittest.mock import Mock, patch

from django.urls import reverse

import pytest
import stripe

from apps.core.models import SubscriptionPlan, Tenant, TenantSubscription
from apps.core.stripe_service import StripeService
from apps.core.tenant_context import bypass_rls


@pytest.fixture
def subscription_plan(db):
    """Create a test subscription plan."""
    with bypass_rls():
        return SubscriptionPlan.objects.create(
            name="Professional",
            description="Professional plan for growing businesses",
            price=Decimal("99.00"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=10,
            branch_limit=3,
            inventory_limit=5000,
        )


@pytest.fixture
def tenant_subscription(db, tenant, subscription_plan):
    """Create a test tenant subscription."""
    with bypass_rls():
        return TenantSubscription.objects.create(
            tenant=tenant,
            plan=subscription_plan,
            status=TenantSubscription.STATUS_TRIAL,
        )


@pytest.mark.django_db
class TestStripeService:
    """Test Stripe service methods."""

    @patch("stripe.Customer.create")
    def test_create_customer(self, mock_create, tenant):
        """Test creating a Stripe customer."""
        # Mock Stripe response
        mock_customer = Mock()
        mock_customer.id = "cus_test123"
        mock_create.return_value = mock_customer

        # Create customer
        customer_id = StripeService.create_customer(
            tenant=tenant,
            email="test@example.com",
            name="Test Shop",
        )

        # Verify
        assert customer_id == "cus_test123"
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["email"] == "test@example.com"
        assert call_kwargs["name"] == "Test Shop"
        assert call_kwargs["metadata"]["tenant_id"] == str(tenant.id)

    @patch("stripe.Subscription.create")
    @patch("stripe.Customer.modify")
    @patch("stripe.PaymentMethod.attach")
    @patch("apps.core.stripe_service.StripeService._get_or_create_price")
    def test_create_subscription(
        self,
        mock_get_price,
        mock_attach,
        mock_modify,
        mock_create,
        tenant_subscription,
        tenant_owner,
    ):
        """Test creating a Stripe subscription."""
        # Setup mocks
        mock_get_price.return_value = "price_test123"
        tenant_subscription.stripe_customer_id = "cus_test123"
        tenant_subscription.save()

        mock_subscription = Mock()
        mock_subscription.id = "sub_test123"
        mock_subscription.status = "active"
        mock_subscription.current_period_start = int(datetime.now(dt_timezone.utc).timestamp())
        mock_subscription.current_period_end = (
            int(datetime.now(dt_timezone.utc).timestamp()) + 2592000
        )
        mock_create.return_value = mock_subscription

        # Create subscription
        result = StripeService.create_subscription(
            tenant_subscription=tenant_subscription,
            payment_method_id="pm_test123",
        )

        # Verify
        assert result["subscription_id"] == "sub_test123"
        assert result["status"] == "active"
        mock_attach.assert_called_once_with("pm_test123", customer="cus_test123")
        mock_create.assert_called_once()

        # Verify database update
        tenant_subscription.refresh_from_db()
        assert tenant_subscription.stripe_subscription_id == "sub_test123"
        assert tenant_subscription.status == TenantSubscription.STATUS_ACTIVE

    @patch("stripe.Subscription.cancel")
    def test_cancel_subscription_immediately(self, mock_cancel, tenant_subscription):
        """Test cancelling a subscription immediately."""
        # Setup
        tenant_subscription.stripe_subscription_id = "sub_test123"
        tenant_subscription.save()

        mock_subscription = Mock()
        mock_subscription.id = "sub_test123"
        mock_subscription.status = "canceled"
        mock_subscription.cancel_at_period_end = False
        mock_cancel.return_value = mock_subscription

        # Cancel subscription
        result = StripeService.cancel_subscription(
            tenant_subscription=tenant_subscription,
            immediately=True,
        )

        # Verify
        assert result["subscription_id"] == "sub_test123"
        assert result["status"] == "canceled"
        mock_cancel.assert_called_once_with("sub_test123")

        # Verify database update
        tenant_subscription.refresh_from_db()
        assert tenant_subscription.status == TenantSubscription.STATUS_CANCELLED
        assert tenant_subscription.cancelled_at is not None

    @patch("stripe.Subscription.modify")
    def test_cancel_subscription_at_period_end(self, mock_modify, tenant_subscription):
        """Test cancelling a subscription at period end."""
        # Setup
        tenant_subscription.stripe_subscription_id = "sub_test123"
        tenant_subscription.save()

        mock_subscription = Mock()
        mock_subscription.id = "sub_test123"
        mock_subscription.status = "active"
        mock_subscription.cancel_at_period_end = True
        mock_modify.return_value = mock_subscription

        # Cancel subscription
        result = StripeService.cancel_subscription(
            tenant_subscription=tenant_subscription,
            immediately=False,
        )

        # Verify
        assert result["cancel_at_period_end"] is True
        mock_modify.assert_called_once()

    @patch("stripe.Subscription.modify")
    @patch("stripe.Subscription.retrieve")
    @patch("apps.core.stripe_service.StripeService._get_or_create_price")
    def test_update_subscription_plan(
        self,
        mock_get_price,
        mock_retrieve,
        mock_modify,
        tenant_subscription,
        subscription_plan,
    ):
        """Test updating a subscription to a new plan."""
        # Setup
        tenant_subscription.stripe_subscription_id = "sub_test123"
        tenant_subscription.save()

        # Create new plan
        new_plan = SubscriptionPlan.objects.create(
            name="Enterprise",
            price=Decimal("199.00"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=50,
        )

        mock_get_price.return_value = "price_new123"

        mock_current_sub = Mock()
        mock_current_sub.__getitem__ = Mock(return_value={"data": [Mock(id="si_test123")]})
        mock_retrieve.return_value = mock_current_sub

        mock_updated_sub = Mock()
        mock_updated_sub.id = "sub_test123"
        mock_updated_sub.status = "active"
        mock_modify.return_value = mock_updated_sub

        # Update subscription
        result = StripeService.update_subscription_plan(
            tenant_subscription=tenant_subscription,
            new_plan=new_plan,
            prorate=True,
        )

        # Verify
        assert result["subscription_id"] == "sub_test123"
        assert result["plan_name"] == "Enterprise"
        mock_modify.assert_called_once()

        # Verify database update
        tenant_subscription.refresh_from_db()
        assert tenant_subscription.plan == new_plan

    @patch("stripe.Price.create")
    @patch("stripe.Product.create")
    @patch("stripe.Product.list")
    def test_get_or_create_price(
        self, mock_list, mock_create_product, mock_create_price, subscription_plan
    ):
        """Test creating a Stripe price for a plan."""
        # Setup mocks
        mock_list.return_value = Mock(data=[])

        mock_product = Mock()
        mock_product.id = "prod_test123"
        mock_create_product.return_value = mock_product

        mock_price = Mock()
        mock_price.id = "price_test123"
        mock_create_price.return_value = mock_price

        # Create price
        price_id = StripeService._get_or_create_price(subscription_plan)

        # Verify
        assert price_id == "price_test123"
        mock_create_product.assert_called_once()
        mock_create_price.assert_called_once()

        # Verify price parameters
        call_kwargs = mock_create_price.call_args[1]
        assert call_kwargs["unit_amount"] == 9900  # $99.00 in cents
        assert call_kwargs["currency"] == "usd"
        assert call_kwargs["recurring"]["interval"] == "month"


@pytest.mark.django_db
class TestStripeWebhooks:
    """Test Stripe webhook handlers."""

    def test_subscription_created_webhook(self, client, tenant_subscription):
        """Test handling subscription.created webhook."""
        with bypass_rls():
            tenant_subscription.stripe_subscription_id = "sub_test123"
            tenant_subscription.save()

        # Create webhook payload
        payload = {
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": "sub_test123",
                    "customer": "cus_test123",
                    "status": "active",
                    "current_period_start": int(datetime.now(dt_timezone.utc).timestamp()),
                    "current_period_end": int(datetime.now(dt_timezone.utc).timestamp()) + 2592000,
                }
            },
        }

        # Mock webhook signature verification
        with patch("stripe.Webhook.construct_event") as mock_construct:
            mock_construct.return_value = payload

            # Send webhook
            response = client.post(
                reverse("core:stripe_webhook"),
                data=json.dumps(payload),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="test_signature",
            )

            # Verify response
            assert response.status_code == 200

            # Verify database update
            with bypass_rls():
                tenant_subscription.refresh_from_db()
                assert tenant_subscription.status == TenantSubscription.STATUS_ACTIVE

    def test_subscription_deleted_webhook(self, client, tenant_subscription, tenant):
        """Test handling subscription.deleted webhook."""
        with bypass_rls():
            tenant_subscription.stripe_subscription_id = "sub_test123"
            tenant_subscription.status = TenantSubscription.STATUS_ACTIVE
            tenant_subscription.save()

        # Create webhook payload
        payload = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_test123",
                }
            },
        }

        # Mock webhook signature verification
        with patch("stripe.Webhook.construct_event") as mock_construct:
            mock_construct.return_value = payload

            # Send webhook
            response = client.post(
                reverse("core:stripe_webhook"),
                data=json.dumps(payload),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="test_signature",
            )

            # Verify response
            assert response.status_code == 200

            # Verify database update
            with bypass_rls():
                tenant_subscription.refresh_from_db()
                assert tenant_subscription.status == TenantSubscription.STATUS_CANCELLED
                assert tenant_subscription.cancelled_at is not None

                # Verify tenant suspended
                tenant.refresh_from_db()
                assert tenant.status == Tenant.SUSPENDED

    def test_payment_succeeded_webhook(self, client, tenant_subscription, tenant):
        """Test handling invoice.payment_succeeded webhook."""
        with bypass_rls():
            tenant_subscription.stripe_subscription_id = "sub_test123"
            tenant_subscription.status = TenantSubscription.STATUS_PAST_DUE
            tenant_subscription.save()

            tenant.status = Tenant.SUSPENDED
            tenant.save()

        # Create webhook payload
        payload = {
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "subscription": "sub_test123",
                    "amount_paid": 9900,  # $99.00 in cents
                }
            },
        }

        # Mock webhook signature verification
        with patch("stripe.Webhook.construct_event") as mock_construct:
            mock_construct.return_value = payload

            # Send webhook
            response = client.post(
                reverse("core:stripe_webhook"),
                data=json.dumps(payload),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="test_signature",
            )

            # Verify response
            assert response.status_code == 200

            # Verify subscription reactivated
            with bypass_rls():
                tenant_subscription.refresh_from_db()
                assert tenant_subscription.status == TenantSubscription.STATUS_ACTIVE

                # Verify tenant reactivated
                tenant.refresh_from_db()
                assert tenant.status == Tenant.ACTIVE

    def test_payment_failed_webhook(self, client, tenant_subscription, tenant):
        """Test handling invoice.payment_failed webhook."""
        with bypass_rls():
            tenant_subscription.stripe_subscription_id = "sub_test123"
            tenant_subscription.status = TenantSubscription.STATUS_ACTIVE
            tenant_subscription.save()

        # Create webhook payload
        payload = {
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "subscription": "sub_test123",
                    "attempt_count": 3,
                }
            },
        }

        # Mock webhook signature verification
        with patch("stripe.Webhook.construct_event") as mock_construct:
            mock_construct.return_value = payload

            # Send webhook
            response = client.post(
                reverse("core:stripe_webhook"),
                data=json.dumps(payload),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="test_signature",
            )

            # Verify response
            assert response.status_code == 200

            # Verify subscription marked as past due
            with bypass_rls():
                tenant_subscription.refresh_from_db()
                assert tenant_subscription.status == TenantSubscription.STATUS_PAST_DUE

                # Verify tenant suspended after 3 failed attempts
                tenant.refresh_from_db()
                assert tenant.status == Tenant.SUSPENDED

    def test_invalid_webhook_signature(self, client):
        """Test webhook with invalid signature."""
        payload = {"type": "test.event"}

        # Mock signature verification failure
        with patch("stripe.Webhook.construct_event") as mock_construct:
            mock_construct.side_effect = stripe.error.SignatureVerificationError(
                "Invalid signature", "sig_header"
            )

            # Send webhook
            response = client.post(
                reverse("core:stripe_webhook"),
                data=json.dumps(payload),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="invalid_signature",
            )

            # Verify response
            assert response.status_code == 400
