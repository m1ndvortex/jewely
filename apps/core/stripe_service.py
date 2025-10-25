"""
Stripe payment gateway integration service.

This module handles all Stripe API interactions for subscription management,
including customer creation, subscription lifecycle, and webhook processing
per Requirement 5.7.
"""

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from django.conf import settings
from django.utils import timezone

import stripe

from apps.core.models import SubscriptionPlan, Tenant, TenantSubscription

logger = logging.getLogger(__name__)

# Initialize Stripe with API key
stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")


class StripeService:
    """
    Service class for Stripe payment gateway integration.

    Handles customer creation, subscription management, and payment processing
    for tenant subscriptions.
    """

    @staticmethod
    def create_customer(tenant: Tenant, email: str, name: Optional[str] = None) -> str:
        """
        Create a Stripe customer for a tenant.

        Args:
            tenant: Tenant instance
            email: Customer email address
            name: Customer name (optional)

        Returns:
            Stripe customer ID

        Raises:
            stripe.error.StripeError: If customer creation fails
        """
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name or tenant.company_name,
                metadata={
                    "tenant_id": str(tenant.id),
                    "tenant_slug": tenant.slug,
                    "company_name": tenant.company_name,
                },
            )

            logger.info(f"Created Stripe customer {customer.id} for tenant {tenant.id}")

            return customer.id

        except stripe.error.StripeError as e:
            logger.error(f"Failed to create Stripe customer for tenant {tenant.id}: {str(e)}")
            raise

    @staticmethod
    def create_subscription(
        tenant_subscription: TenantSubscription,
        payment_method_id: Optional[str] = None,
        trial_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Create a Stripe subscription for a tenant.

        Args:
            tenant_subscription: TenantSubscription instance
            payment_method_id: Stripe payment method ID (optional for trials)
            trial_days: Number of trial days (optional)

        Returns:
            Dictionary with subscription details

        Raises:
            stripe.error.StripeError: If subscription creation fails
        """
        try:
            tenant = tenant_subscription.tenant
            plan = tenant_subscription.plan

            # Create customer if not exists
            if not tenant_subscription.stripe_customer_id:
                # Get tenant owner email
                owner = tenant.users.filter(role="TENANT_OWNER").first()
                email = owner.email if owner else f"{tenant.slug}@example.com"

                customer_id = StripeService.create_customer(
                    tenant=tenant,
                    email=email,
                )
                tenant_subscription.stripe_customer_id = customer_id
                tenant_subscription.save(update_fields=["stripe_customer_id"])

            # Attach payment method if provided
            if payment_method_id:
                stripe.PaymentMethod.attach(
                    payment_method_id,
                    customer=tenant_subscription.stripe_customer_id,
                )

                # Set as default payment method
                stripe.Customer.modify(
                    tenant_subscription.stripe_customer_id,
                    invoice_settings={
                        "default_payment_method": payment_method_id,
                    },
                )

            # Create Stripe price if not exists
            price_id = StripeService._get_or_create_price(plan)

            # Create subscription
            subscription_params = {
                "customer": tenant_subscription.stripe_customer_id,
                "items": [{"price": price_id}],
                "metadata": {
                    "tenant_id": str(tenant.id),
                    "tenant_subscription_id": str(tenant_subscription.id),
                    "plan_id": str(plan.id),
                },
            }

            # Add trial period if specified
            if trial_days:
                subscription_params["trial_period_days"] = trial_days

            stripe_subscription = stripe.Subscription.create(**subscription_params)

            # Update tenant subscription with Stripe details
            tenant_subscription.stripe_subscription_id = stripe_subscription.id
            tenant_subscription.status = TenantSubscription.STATUS_ACTIVE
            tenant_subscription.current_period_start = timezone.datetime.fromtimestamp(
                stripe_subscription.current_period_start, tz=timezone.utc
            )
            tenant_subscription.current_period_end = timezone.datetime.fromtimestamp(
                stripe_subscription.current_period_end, tz=timezone.utc
            )
            tenant_subscription.save(
                update_fields=[
                    "stripe_subscription_id",
                    "status",
                    "current_period_start",
                    "current_period_end",
                ]
            )

            logger.info(
                f"Created Stripe subscription {stripe_subscription.id} " f"for tenant {tenant.id}"
            )

            return {
                "subscription_id": stripe_subscription.id,
                "status": stripe_subscription.status,
                "current_period_start": stripe_subscription.current_period_start,
                "current_period_end": stripe_subscription.current_period_end,
            }

        except stripe.error.StripeError as e:
            logger.error(
                f"Failed to create Stripe subscription for tenant "
                f"{tenant_subscription.tenant.id}: {str(e)}"
            )
            raise

    @staticmethod
    def cancel_subscription(
        tenant_subscription: TenantSubscription,
        immediately: bool = False,
    ) -> Dict[str, Any]:
        """
        Cancel a Stripe subscription.

        Args:
            tenant_subscription: TenantSubscription instance
            immediately: If True, cancel immediately; otherwise at period end

        Returns:
            Dictionary with cancellation details

        Raises:
            stripe.error.StripeError: If cancellation fails
        """
        try:
            if not tenant_subscription.stripe_subscription_id:
                raise ValueError("No Stripe subscription ID found")

            if immediately:
                stripe_subscription = stripe.Subscription.cancel(
                    tenant_subscription.stripe_subscription_id
                )
            else:
                stripe_subscription = stripe.Subscription.modify(
                    tenant_subscription.stripe_subscription_id,
                    cancel_at_period_end=True,
                )

            # Update tenant subscription status
            tenant_subscription.status = TenantSubscription.STATUS_CANCELLED
            tenant_subscription.cancelled_at = timezone.now()
            tenant_subscription.save(update_fields=["status", "cancelled_at", "updated_at"])

            logger.info(
                f"Cancelled Stripe subscription {stripe_subscription.id} "
                f"for tenant {tenant_subscription.tenant.id}"
            )

            return {
                "subscription_id": stripe_subscription.id,
                "status": stripe_subscription.status,
                "cancel_at_period_end": stripe_subscription.cancel_at_period_end,
            }

        except stripe.error.StripeError as e:
            logger.error(
                f"Failed to cancel Stripe subscription for tenant "
                f"{tenant_subscription.tenant.id}: {str(e)}"
            )
            raise

    @staticmethod
    def update_subscription_plan(
        tenant_subscription: TenantSubscription,
        new_plan: SubscriptionPlan,
        prorate: bool = True,
    ) -> Dict[str, Any]:
        """
        Update a Stripe subscription to a new plan.

        Args:
            tenant_subscription: TenantSubscription instance
            new_plan: New SubscriptionPlan to switch to
            prorate: Whether to prorate the subscription change

        Returns:
            Dictionary with update details

        Raises:
            stripe.error.StripeError: If update fails
        """
        try:
            if not tenant_subscription.stripe_subscription_id:
                raise ValueError("No Stripe subscription ID found")

            # Get or create price for new plan
            new_price_id = StripeService._get_or_create_price(new_plan)

            # Get current subscription
            stripe_subscription = stripe.Subscription.retrieve(
                tenant_subscription.stripe_subscription_id
            )

            # Update subscription with new price
            updated_subscription = stripe.Subscription.modify(
                tenant_subscription.stripe_subscription_id,
                items=[
                    {
                        "id": stripe_subscription["items"]["data"][0].id,
                        "price": new_price_id,
                    }
                ],
                proration_behavior="create_prorations" if prorate else "none",
                metadata={
                    "tenant_id": str(tenant_subscription.tenant.id),
                    "tenant_subscription_id": str(tenant_subscription.id),
                    "plan_id": str(new_plan.id),
                },
            )

            # Update tenant subscription
            tenant_subscription.plan = new_plan
            tenant_subscription.save(update_fields=["plan", "updated_at"])

            logger.info(
                f"Updated Stripe subscription {updated_subscription.id} "
                f"to plan {new_plan.name} for tenant {tenant_subscription.tenant.id}"
            )

            return {
                "subscription_id": updated_subscription.id,
                "status": updated_subscription.status,
                "plan_name": new_plan.name,
            }

        except stripe.error.StripeError as e:
            logger.error(
                f"Failed to update Stripe subscription for tenant "
                f"{tenant_subscription.tenant.id}: {str(e)}"
            )
            raise

    @staticmethod
    def _get_or_create_price(plan: SubscriptionPlan) -> str:
        """
        Get or create a Stripe price for a subscription plan.

        Args:
            plan: SubscriptionPlan instance

        Returns:
            Stripe price ID
        """
        # Check if price already exists in metadata
        if hasattr(plan, "stripe_price_id") and plan.stripe_price_id:
            return plan.stripe_price_id

        # Map billing cycle to Stripe interval
        interval_map = {
            SubscriptionPlan.BILLING_MONTHLY: "month",
            SubscriptionPlan.BILLING_QUARTERLY: "month",
            SubscriptionPlan.BILLING_YEARLY: "year",
        }

        interval = interval_map.get(plan.billing_cycle, "month")
        interval_count = 3 if plan.billing_cycle == SubscriptionPlan.BILLING_QUARTERLY else 1

        # Create Stripe product if not exists
        try:
            products = stripe.Product.list(limit=100)
            product = next(
                (p for p in products.data if p.metadata.get("plan_id") == str(plan.id)),
                None,
            )

            if not product:
                product = stripe.Product.create(
                    name=plan.name,
                    description=plan.description,
                    metadata={"plan_id": str(plan.id)},
                )

            # Create price
            price = stripe.Price.create(
                product=product.id,
                unit_amount=int(plan.price * 100),  # Convert to cents
                currency="usd",
                recurring={
                    "interval": interval,
                    "interval_count": interval_count,
                },
                metadata={"plan_id": str(plan.id)},
            )

            logger.info(f"Created Stripe price {price.id} for plan {plan.name}")

            return price.id

        except stripe.error.StripeError as e:
            logger.error(f"Failed to create Stripe price for plan {plan.id}: {str(e)}")
            raise

    @staticmethod
    def retrieve_subscription(subscription_id: str) -> Dict[str, Any]:
        """
        Retrieve a Stripe subscription.

        Args:
            subscription_id: Stripe subscription ID

        Returns:
            Dictionary with subscription details
        """
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return {
                "id": subscription.id,
                "status": subscription.status,
                "current_period_start": subscription.current_period_start,
                "current_period_end": subscription.current_period_end,
                "cancel_at_period_end": subscription.cancel_at_period_end,
            }
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve subscription {subscription_id}: {str(e)}")
            raise

    @staticmethod
    def create_payment_intent(
        amount: Decimal,
        currency: str = "usd",
        customer_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a Stripe payment intent for one-time payments.

        Args:
            amount: Payment amount
            currency: Currency code (default: usd)
            customer_id: Stripe customer ID (optional)
            metadata: Additional metadata (optional)

        Returns:
            Dictionary with payment intent details
        """
        try:
            intent_params = {
                "amount": int(amount * 100),  # Convert to cents
                "currency": currency,
                "metadata": metadata or {},
            }

            if customer_id:
                intent_params["customer"] = customer_id

            payment_intent = stripe.PaymentIntent.create(**intent_params)

            return {
                "id": payment_intent.id,
                "client_secret": payment_intent.client_secret,
                "status": payment_intent.status,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Failed to create payment intent: {str(e)}")
            raise
