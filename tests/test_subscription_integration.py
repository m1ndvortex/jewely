"""
Integration tests for subscription management system.

Tests real-world scenarios for subscription plans and tenant subscriptions
per Requirement 5.
"""

import uuid
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

import pytest

from apps.core.models import SubscriptionPlan, Tenant, TenantSubscription
from apps.core.tenant_context import bypass_rls, tenant_context


@pytest.mark.django_db
class TestSubscriptionIntegration:
    """Integration tests for subscription management."""

    def test_complete_subscription_lifecycle(self):
        """
        Test complete subscription lifecycle from plan creation to cancellation.

        This tests Requirement 5.1, 5.2, 5.3, 5.4, and 5.5.
        """
        # Step 1: Platform admin creates subscription plans (Requirement 5.1, 5.2)
        starter_plan = SubscriptionPlan.objects.create(
            name="Starter Plan",
            description="Perfect for small jewelry shops",
            price=Decimal("49.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=5,
            branch_limit=1,
            inventory_limit=1000,
            storage_limit_gb=10,
            api_calls_per_month=10000,
            enable_multi_branch=False,
            enable_advanced_reporting=False,
            enable_api_access=False,
            display_order=1,
        )

        professional_plan = SubscriptionPlan.objects.create(
            name="Professional Plan",
            description="For growing jewelry businesses",
            price=Decimal("99.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=15,
            branch_limit=3,
            inventory_limit=5000,
            storage_limit_gb=50,
            api_calls_per_month=50000,
            enable_multi_branch=True,
            enable_advanced_reporting=True,
            enable_api_access=True,
            display_order=2,
        )

        # Verify plans were created
        assert SubscriptionPlan.objects.count() == 2
        assert starter_plan.is_active()
        assert professional_plan.is_active()

        # Step 2: Create a new tenant (jewelry shop)
        with bypass_rls():
            tenant = Tenant.objects.create(
                company_name="Golden Treasures Jewelry",
                slug=f"golden-treasures-{uuid.uuid4().hex[:8]}",
                status=Tenant.ACTIVE,
            )

        # Step 3: Assign starter plan to tenant with trial period (Requirement 5.3)
        trial_start = timezone.now()
        trial_end = trial_start + timedelta(days=14)

        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            plan=starter_plan,
            status=TenantSubscription.STATUS_TRIAL,
            trial_start=trial_start,
            trial_end=trial_end,
        )

        # Verify subscription was created correctly
        assert subscription.tenant == tenant
        assert subscription.plan == starter_plan
        assert subscription.is_trial()
        assert not subscription.is_trial_expired()
        assert subscription.get_user_limit() == 5
        assert subscription.get_branch_limit() == 1
        assert subscription.get_inventory_limit() == 1000

        # Step 4: Tenant uses the service during trial
        # Verify they have access to plan features
        assert not subscription.has_multi_branch_enabled()
        assert not subscription.has_advanced_reporting_enabled()
        assert not subscription.has_api_access_enabled()

        # Step 5: Trial ends, convert to paid subscription (Requirement 5.5)
        subscription.status = TenantSubscription.STATUS_ACTIVE
        subscription.current_period_start = timezone.now()
        subscription.current_period_end = timezone.now() + timedelta(days=30)
        subscription.next_billing_date = timezone.now() + timedelta(days=30)
        subscription.save()

        assert subscription.is_active()
        assert not subscription.is_trial()

        # Step 6: Tenant grows and needs to upgrade (Requirement 5.3)
        subscription.change_plan(professional_plan)

        # Verify plan was changed
        subscription.refresh_from_db()
        assert subscription.plan == professional_plan
        assert subscription.get_user_limit() == 15
        assert subscription.get_branch_limit() == 3
        assert subscription.get_inventory_limit() == 5000
        assert subscription.has_multi_branch_enabled()
        assert subscription.has_advanced_reporting_enabled()

        # Step 7: Admin provides custom limits for this tenant (Requirement 5.4)
        subscription.user_limit_override = 25  # Give them extra users
        subscription.branch_limit_override = 5  # Give them extra branches
        subscription.enable_custom_branding_override = True  # Enable premium feature
        subscription.save()

        # Verify overrides work
        assert subscription.get_user_limit() == 25  # Override value
        assert subscription.get_branch_limit() == 5  # Override value
        assert subscription.get_inventory_limit() == 5000  # Plan default
        assert subscription.has_custom_branding_enabled()  # Override enabled

        # Step 8: Tenant decides to cancel (Requirement 5.5)
        subscription.cancel(reason="Moving to in-house solution")

        # Verify cancellation
        assert subscription.is_cancelled()
        assert subscription.cancelled_at is not None
        assert subscription.cancellation_reason == "Moving to in-house solution"

    def test_multiple_tenants_with_different_plans(self):
        """
        Test multiple tenants with different subscription plans.

        Verifies data isolation and independent subscription management.
        """
        # Create plans
        basic_plan = SubscriptionPlan.objects.create(
            name="Basic",
            price=Decimal("29.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=3,
            branch_limit=1,
            inventory_limit=500,
        )

        premium_plan = SubscriptionPlan.objects.create(
            name="Premium",
            price=Decimal("149.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=25,
            branch_limit=10,
            inventory_limit=10000,
        )

        # Create multiple tenants
        tenants = []
        subscriptions = []

        with bypass_rls():
            for i in range(3):
                tenant = Tenant.objects.create(
                    company_name=f"Jewelry Shop {i+1}",
                    slug=f"shop-{i+1}-{uuid.uuid4().hex[:8]}",
                )
                tenants.append(tenant)

                # Assign different plans
                plan = basic_plan if i % 2 == 0 else premium_plan
                subscription = TenantSubscription.objects.create(
                    tenant=tenant,
                    plan=plan,
                    status=TenantSubscription.STATUS_ACTIVE,
                )
                subscriptions.append(subscription)

        # Verify each tenant has correct subscription
        assert subscriptions[0].plan == basic_plan
        assert subscriptions[0].get_user_limit() == 3
        assert subscriptions[1].plan == premium_plan
        assert subscriptions[1].get_user_limit() == 25
        assert subscriptions[2].plan == basic_plan
        assert subscriptions[2].get_user_limit() == 3

        # Verify data isolation - each tenant only sees their own subscription
        for i, tenant in enumerate(tenants):
            with tenant_context(tenant.id):
                tenant_subs = TenantSubscription.objects.filter(tenant=tenant)
                assert tenant_subs.count() == 1
                assert tenant_subs.first() == subscriptions[i]

    def test_plan_archival_and_existing_subscriptions(self):
        """
        Test that archiving a plan doesn't affect existing subscriptions.

        Per Requirement 5.2: "Archived plans cannot be assigned to new tenants
        but existing subscriptions remain active."
        """
        # Create a plan
        plan = SubscriptionPlan.objects.create(
            name="Legacy Plan",
            price=Decimal("79.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=10,
            branch_limit=2,
            inventory_limit=3000,
        )

        # Create tenant with this plan
        with bypass_rls():
            tenant = Tenant.objects.create(
                company_name="Existing Customer",
                slug=f"existing-{uuid.uuid4().hex[:8]}",
            )

        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            plan=plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        # Archive the plan
        plan.archive()

        # Verify plan is archived
        assert plan.is_archived()
        assert plan.archived_at is not None

        # Verify existing subscription still works
        subscription.refresh_from_db()
        assert subscription.is_active()
        assert subscription.plan == plan
        assert subscription.get_user_limit() == 10

        # Verify archived plan can't be assigned to new tenants
        # (This would be enforced in the admin/API layer)
        assert not plan.is_active()

    def test_subscription_with_payment_gateway_integration(self):
        """
        Test subscription with payment gateway integration fields.

        Tests Requirement 5.7: "Integrate with payment gateway for automated
        subscription lifecycle events."
        """
        # Create plan
        plan = SubscriptionPlan.objects.create(
            name="Business Plan",
            price=Decimal("199.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=50,
            branch_limit=20,
            inventory_limit=50000,
        )

        # Create tenant
        with bypass_rls():
            tenant = Tenant.objects.create(
                company_name="Premium Jewelers",
                slug=f"premium-{uuid.uuid4().hex[:8]}",
            )

        # Create subscription with Stripe integration
        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            plan=plan,
            status=TenantSubscription.STATUS_ACTIVE,
            stripe_customer_id="cus_test123456789",
            stripe_subscription_id="sub_test987654321",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            next_billing_date=timezone.now() + timedelta(days=30),
        )

        # Verify Stripe integration fields
        assert subscription.stripe_customer_id == "cus_test123456789"
        assert subscription.stripe_subscription_id == "sub_test987654321"
        assert subscription.next_billing_date is not None

        # Simulate payment failure - subscription becomes past due
        subscription.status = TenantSubscription.STATUS_PAST_DUE
        subscription.save()

        assert subscription.is_past_due()
        assert not subscription.is_active()

        # Simulate successful payment retry - reactivate subscription
        subscription.activate()

        assert subscription.is_active()
        assert not subscription.is_past_due()

    def test_subscription_limit_enforcement_scenarios(self):
        """
        Test various scenarios for subscription limit enforcement.

        Tests Requirement 5.4: "Allow administrators to override default
        plan limits for specific tenants."
        """
        # Create plan with specific limits
        plan = SubscriptionPlan.objects.create(
            name="Standard Plan",
            price=Decimal("69.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=10,
            branch_limit=2,
            inventory_limit=2000,
            storage_limit_gb=25,
            api_calls_per_month=25000,
        )

        # Create tenant
        with bypass_rls():
            tenant = Tenant.objects.create(
                company_name="Test Jewelers",
                slug=f"test-{uuid.uuid4().hex[:8]}",
            )

        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            plan=plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        # Scenario 1: No overrides - use plan defaults
        assert subscription.get_user_limit() == 10
        assert subscription.get_branch_limit() == 2
        assert subscription.get_inventory_limit() == 2000
        assert subscription.get_storage_limit_gb() == 25
        assert subscription.get_api_calls_per_month() == 25000

        # Scenario 2: Partial overrides - some limits increased
        subscription.user_limit_override = 20
        subscription.inventory_limit_override = 5000
        subscription.save()

        assert subscription.get_user_limit() == 20  # Overridden
        assert subscription.get_branch_limit() == 2  # Plan default
        assert subscription.get_inventory_limit() == 5000  # Overridden
        assert subscription.get_storage_limit_gb() == 25  # Plan default
        assert subscription.get_api_calls_per_month() == 25000  # Plan default

        # Scenario 3: Override can also decrease limits (for special cases)
        subscription.api_calls_per_month_override = 10000
        subscription.save()

        assert subscription.get_api_calls_per_month() == 10000  # Decreased

        # Scenario 4: Remove override by setting to None
        subscription.user_limit_override = None
        subscription.save()

        assert subscription.get_user_limit() == 10  # Back to plan default

    def test_billing_cycle_calculations(self):
        """
        Test billing cycle calculations for different plan types.

        Tests price calculations for monthly, quarterly, and yearly plans.
        """
        # Create plans with different billing cycles
        monthly = SubscriptionPlan.objects.create(
            name="Monthly",
            price=Decimal("100.00"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=10,
        )

        quarterly = SubscriptionPlan.objects.create(
            name="Quarterly",
            price=Decimal("270.00"),  # 10% discount
            billing_cycle=SubscriptionPlan.BILLING_QUARTERLY,
            user_limit=10,
        )

        yearly = SubscriptionPlan.objects.create(
            name="Yearly",
            price=Decimal("1000.00"),  # ~17% discount
            billing_cycle=SubscriptionPlan.BILLING_YEARLY,
            user_limit=10,
        )

        # Verify monthly price calculations
        assert monthly.get_monthly_price() == Decimal("100.00")
        assert quarterly.get_monthly_price() == Decimal("90.00")
        assert yearly.get_monthly_price() == Decimal("83.33333333333333333333333333")

        # Verify annual price calculations
        assert monthly.get_annual_price() == Decimal("1200.00")
        assert quarterly.get_annual_price() == Decimal("1080.00")
        assert yearly.get_annual_price() == Decimal("1000.00")

    def test_subscription_status_transitions(self):
        """
        Test all valid subscription status transitions.

        Tests Requirement 5.5: "Allow administrators to manually activate
        or deactivate tenant subscriptions."
        """
        plan = SubscriptionPlan.objects.create(
            name="Test Plan",
            price=Decimal("50.00"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=5,
        )

        with bypass_rls():
            tenant = Tenant.objects.create(
                company_name="Status Test Shop",
                slug=f"status-test-{uuid.uuid4().hex[:8]}",
            )

        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            plan=plan,
            status=TenantSubscription.STATUS_TRIAL,
        )

        # Trial -> Active
        subscription.activate()
        assert subscription.is_active()

        # Active -> Past Due (payment failed)
        subscription.status = TenantSubscription.STATUS_PAST_DUE
        subscription.save()
        assert subscription.is_past_due()

        # Past Due -> Active (payment recovered)
        subscription.activate()
        assert subscription.is_active()

        # Active -> Cancelled
        subscription.cancel(reason="Customer request")
        assert subscription.is_cancelled()
        assert subscription.cancellation_reason == "Customer request"

        # Cancelled -> Active (reactivation)
        subscription.activate()
        assert subscription.is_active()
        assert subscription.cancelled_at is None

        # Active -> Expired (end of billing period, not renewed)
        subscription.status = TenantSubscription.STATUS_EXPIRED
        subscription.save()
        assert subscription.is_expired()

    def test_feature_flag_overrides(self):
        """
        Test feature flag overrides for custom tenant configurations.

        Tests Requirement 5.4 for feature-level customization.
        """
        # Create basic plan without premium features
        plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            price=Decimal("39.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=5,
            enable_multi_branch=False,
            enable_advanced_reporting=False,
            enable_api_access=False,
            enable_custom_branding=False,
            enable_priority_support=False,
        )

        with bypass_rls():
            tenant = Tenant.objects.create(
                company_name="Special Customer",
                slug=f"special-{uuid.uuid4().hex[:8]}",
            )

        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            plan=plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        # Verify default features (all disabled)
        assert not subscription.has_multi_branch_enabled()
        assert not subscription.has_advanced_reporting_enabled()
        assert not subscription.has_api_access_enabled()
        assert not subscription.has_custom_branding_enabled()
        assert not subscription.has_priority_support_enabled()

        # Enable specific features for this tenant
        subscription.enable_api_access_override = True
        subscription.enable_priority_support_override = True
        subscription.save()

        # Verify overrides work
        assert not subscription.has_multi_branch_enabled()  # Still disabled
        assert not subscription.has_advanced_reporting_enabled()  # Still disabled
        assert subscription.has_api_access_enabled()  # Enabled via override
        assert not subscription.has_custom_branding_enabled()  # Still disabled
        assert subscription.has_priority_support_enabled()  # Enabled via override

    def test_admin_can_view_all_subscriptions(self):
        """
        Test that platform admins can view all tenant subscriptions.

        Tests Requirement 5.6: "Display all tenants with their current
        subscription plan, status, and next billing date."
        """
        # Create multiple plans
        plans = []
        for i in range(3):
            plan = SubscriptionPlan.objects.create(
                name=f"Plan {i+1}",
                price=Decimal(f"{(i+1)*50}.00"),
                billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
                user_limit=(i + 1) * 10,
            )
            plans.append(plan)

        # Create multiple tenants with subscriptions
        with bypass_rls():
            for i in range(5):
                tenant = Tenant.objects.create(
                    company_name=f"Shop {i+1}",
                    slug=f"shop-{i+1}-{uuid.uuid4().hex[:8]}",
                )

                TenantSubscription.objects.create(
                    tenant=tenant,
                    plan=plans[i % 3],
                    status=TenantSubscription.STATUS_ACTIVE,
                    next_billing_date=timezone.now() + timedelta(days=30),
                )

        # Admin can see all subscriptions
        with bypass_rls():
            all_subscriptions = TenantSubscription.objects.all()
            assert all_subscriptions.count() == 5

            # Verify we can access subscription details
            for sub in all_subscriptions:
                assert sub.tenant is not None
                assert sub.plan is not None
                assert sub.status == TenantSubscription.STATUS_ACTIVE
                assert sub.next_billing_date is not None
