"""
Tests for subscription models.

Tests the SubscriptionPlan and TenantSubscription models per Requirement 5.
"""

import uuid
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

import pytest

from apps.core.models import SubscriptionPlan, Tenant, TenantSubscription
from apps.core.tenant_context import bypass_rls


@pytest.mark.django_db
class TestSubscriptionPlan:
    """Test SubscriptionPlan model."""

    def test_create_subscription_plan(self):
        """Test creating a subscription plan with all required fields."""
        plan = SubscriptionPlan.objects.create(
            name="Professional",
            description="Professional plan for growing businesses",
            price=Decimal("99.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=10,
            branch_limit=3,
            inventory_limit=5000,
            storage_limit_gb=50,
            api_calls_per_month=50000,
            enable_multi_branch=True,
            enable_advanced_reporting=True,
            enable_api_access=True,
        )

        assert plan.id is not None
        assert plan.name == "Professional"
        assert plan.price == Decimal("99.99")
        assert plan.billing_cycle == SubscriptionPlan.BILLING_MONTHLY
        assert plan.user_limit == 10
        assert plan.branch_limit == 3
        assert plan.inventory_limit == 5000
        assert plan.status == SubscriptionPlan.STATUS_ACTIVE
        assert plan.is_active() is True
        assert plan.is_archived() is False

    def test_subscription_plan_str(self):
        """Test string representation of subscription plan."""
        plan = SubscriptionPlan.objects.create(
            name="Starter",
            price=Decimal("29.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
        )

        assert str(plan) == "Starter ($29.99/monthly)"

    def test_archive_plan(self):
        """Test archiving a subscription plan."""
        plan = SubscriptionPlan.objects.create(
            name="Enterprise",
            price=Decimal("299.99"),
            billing_cycle=SubscriptionPlan.BILLING_YEARLY,
        )

        assert plan.is_active() is True
        assert plan.archived_at is None

        plan.archive()

        assert plan.is_archived() is True
        assert plan.archived_at is not None
        assert plan.status == SubscriptionPlan.STATUS_ARCHIVED

    def test_activate_archived_plan(self):
        """Test activating an archived plan."""
        plan = SubscriptionPlan.objects.create(
            name="Premium",
            price=Decimal("149.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            status=SubscriptionPlan.STATUS_ARCHIVED,
        )

        plan.activate()

        assert plan.is_active() is True
        assert plan.archived_at is None
        assert plan.status == SubscriptionPlan.STATUS_ACTIVE

    def test_get_monthly_price(self):
        """Test monthly price calculation for different billing cycles."""
        monthly_plan = SubscriptionPlan.objects.create(
            name="Monthly",
            price=Decimal("100.00"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
        )
        assert monthly_plan.get_monthly_price() == Decimal("100.00")

        quarterly_plan = SubscriptionPlan.objects.create(
            name="Quarterly",
            price=Decimal("270.00"),
            billing_cycle=SubscriptionPlan.BILLING_QUARTERLY,
        )
        assert quarterly_plan.get_monthly_price() == Decimal("90.00")

        yearly_plan = SubscriptionPlan.objects.create(
            name="Yearly",
            price=Decimal("1000.00"),
            billing_cycle=SubscriptionPlan.BILLING_YEARLY,
        )
        assert yearly_plan.get_monthly_price() == Decimal("83.33333333333333333333333333")

    def test_get_annual_price(self):
        """Test annual price calculation for different billing cycles."""
        monthly_plan = SubscriptionPlan.objects.create(
            name="Monthly",
            price=Decimal("100.00"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
        )
        assert monthly_plan.get_annual_price() == Decimal("1200.00")

        yearly_plan = SubscriptionPlan.objects.create(
            name="Yearly",
            price=Decimal("1000.00"),
            billing_cycle=SubscriptionPlan.BILLING_YEARLY,
        )
        assert yearly_plan.get_annual_price() == Decimal("1000.00")


@pytest.mark.django_db
class TestTenantSubscription:
    """Test TenantSubscription model."""

    def test_create_tenant_subscription(self):
        """Test creating a tenant subscription."""
        with bypass_rls():
            tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop",
                slug=f"test-jewelry-shop-{uuid.uuid4().hex[:8]}",
            )

        plan = SubscriptionPlan.objects.create(
            name="Professional",
            price=Decimal("99.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=10,
            branch_limit=3,
            inventory_limit=5000,
        )

        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            plan=plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        assert subscription.id is not None
        assert subscription.tenant == tenant
        assert subscription.plan == plan
        assert subscription.status == TenantSubscription.STATUS_ACTIVE
        assert subscription.is_active() is True

    def test_subscription_str(self):
        """Test string representation of tenant subscription."""
        with bypass_rls():
            tenant = Tenant.objects.create(
                company_name="Gold Palace",
                slug=f"gold-palace-{uuid.uuid4().hex[:8]}",
            )

        plan = SubscriptionPlan.objects.create(
            name="Starter",
            price=Decimal("29.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
        )

        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            plan=plan,
            status=TenantSubscription.STATUS_TRIAL,
        )

        assert str(subscription) == "Gold Palace - Starter (trial)"

    def test_get_effective_limits_without_overrides(self):
        """Test that effective limits use plan defaults when no overrides are set."""
        with bypass_rls():
            tenant = Tenant.objects.create(
                company_name="Test Shop",
                slug=f"test-shop-{uuid.uuid4().hex[:8]}",
            )

        plan = SubscriptionPlan.objects.create(
            name="Basic",
            price=Decimal("49.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=5,
            branch_limit=1,
            inventory_limit=1000,
            storage_limit_gb=10,
            api_calls_per_month=10000,
        )

        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            plan=plan,
        )

        # Should use plan defaults
        assert subscription.get_user_limit() == 5
        assert subscription.get_branch_limit() == 1
        assert subscription.get_inventory_limit() == 1000
        assert subscription.get_storage_limit_gb() == 10
        assert subscription.get_api_calls_per_month() == 10000

    def test_get_effective_limits_with_overrides(self):
        """Test that effective limits use overrides when set."""
        with bypass_rls():
            tenant = Tenant.objects.create(
                company_name="Premium Shop",
                slug=f"premium-shop-{uuid.uuid4().hex[:8]}",
            )

        plan = SubscriptionPlan.objects.create(
            name="Basic",
            price=Decimal("49.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=5,
            branch_limit=1,
            inventory_limit=1000,
        )

        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            plan=plan,
            user_limit_override=20,
            branch_limit_override=5,
            inventory_limit_override=10000,
        )

        # Should use overrides
        assert subscription.get_user_limit() == 20
        assert subscription.get_branch_limit() == 5
        assert subscription.get_inventory_limit() == 10000

    def test_feature_flags_without_overrides(self):
        """Test that feature flags use plan defaults when no overrides are set."""
        with bypass_rls():
            tenant = Tenant.objects.create(
                company_name="Test Shop",
                slug=f"test-shop-{uuid.uuid4().hex[:8]}",
            )

        plan = SubscriptionPlan.objects.create(
            name="Professional",
            price=Decimal("99.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            enable_multi_branch=True,
            enable_advanced_reporting=True,
            enable_api_access=False,
        )

        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            plan=plan,
        )

        # Should use plan defaults
        assert subscription.has_multi_branch_enabled() is True
        assert subscription.has_advanced_reporting_enabled() is True
        assert subscription.has_api_access_enabled() is False

    def test_feature_flags_with_overrides(self):
        """Test that feature flags use overrides when set."""
        with bypass_rls():
            tenant = Tenant.objects.create(
                company_name="Custom Shop",
                slug=f"custom-shop-{uuid.uuid4().hex[:8]}",
            )

        plan = SubscriptionPlan.objects.create(
            name="Basic",
            price=Decimal("49.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            enable_multi_branch=False,
            enable_api_access=False,
        )

        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            plan=plan,
            enable_multi_branch_override=True,
            enable_api_access_override=True,
        )

        # Should use overrides
        assert subscription.has_multi_branch_enabled() is True
        assert subscription.has_api_access_enabled() is True

    def test_activate_subscription(self):
        """Test activating a subscription."""
        with bypass_rls():
            tenant = Tenant.objects.create(
                company_name="Test Shop",
                slug=f"test-shop-{uuid.uuid4().hex[:8]}",
            )

        plan = SubscriptionPlan.objects.create(
            name="Basic",
            price=Decimal("49.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
        )

        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            plan=plan,
            status=TenantSubscription.STATUS_CANCELLED,
        )

        subscription.activate()

        assert subscription.is_active() is True
        assert subscription.status == TenantSubscription.STATUS_ACTIVE
        assert subscription.cancelled_at is None

    def test_deactivate_subscription(self):
        """Test deactivating a subscription."""
        with bypass_rls():
            tenant = Tenant.objects.create(
                company_name="Test Shop",
                slug=f"test-shop-{uuid.uuid4().hex[:8]}",
            )

        plan = SubscriptionPlan.objects.create(
            name="Basic",
            price=Decimal("49.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
        )

        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            plan=plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        subscription.deactivate()

        assert subscription.is_cancelled() is True
        assert subscription.status == TenantSubscription.STATUS_CANCELLED
        assert subscription.cancelled_at is not None

    def test_cancel_subscription_with_reason(self):
        """Test cancelling a subscription with a reason."""
        with bypass_rls():
            tenant = Tenant.objects.create(
                company_name="Test Shop",
                slug=f"test-shop-{uuid.uuid4().hex[:8]}",
            )

        plan = SubscriptionPlan.objects.create(
            name="Basic",
            price=Decimal("49.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
        )

        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            plan=plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        subscription.cancel(reason="Customer requested cancellation")

        assert subscription.is_cancelled() is True
        assert subscription.cancellation_reason == "Customer requested cancellation"
        assert subscription.cancelled_at is not None

    def test_days_until_renewal(self):
        """Test calculating days until renewal."""
        with bypass_rls():
            tenant = Tenant.objects.create(
                company_name="Test Shop",
                slug=f"test-shop-{uuid.uuid4().hex[:8]}",
            )

        plan = SubscriptionPlan.objects.create(
            name="Basic",
            price=Decimal("49.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
        )

        next_billing = timezone.now() + timedelta(days=15)

        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            plan=plan,
            next_billing_date=next_billing,
        )

        days = subscription.days_until_renewal()
        assert days is not None
        assert 14 <= days <= 15  # Allow for timing differences

    def test_trial_period_tracking(self):
        """Test trial period tracking."""
        with bypass_rls():
            tenant = Tenant.objects.create(
                company_name="Test Shop",
                slug=f"test-shop-{uuid.uuid4().hex[:8]}",
            )

        plan = SubscriptionPlan.objects.create(
            name="Basic",
            price=Decimal("49.99"),
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
        )

        trial_start = timezone.now()
        trial_end = trial_start + timedelta(days=14)

        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            plan=plan,
            status=TenantSubscription.STATUS_TRIAL,
            trial_start=trial_start,
            trial_end=trial_end,
        )

        assert subscription.is_trial() is True
        assert subscription.is_trial_expired() is False

        days_remaining = subscription.days_remaining_in_trial()
        assert days_remaining is not None
        assert 13 <= days_remaining <= 14  # Allow for timing differences
