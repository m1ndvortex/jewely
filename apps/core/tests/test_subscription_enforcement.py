"""
Comprehensive unit tests for the Subscription Enforcement System.

This module tests:
- SubscriptionEnforcementService for all limit types
- Limit enforcement across different plan tiers
- Feature flag checking
- Unlimited (-1) handling
- Override functionality
- Usage tracking
- Monthly reset

Author: Enterprise Subscription System Tests
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, PropertyMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from apps.core.models import Branch, SubscriptionPlan, Tenant, TenantSubscription
from apps.core.subscription_enforcement import (
    EnforcementResult,
    FeatureNotEnabled,
    LimitCheckResult,
    LimitType,
    SubscriptionEnforcementService,
    SubscriptionLimitExceeded,
    UsageStats,
    check_subscription_feature,
    check_subscription_limit,
)

User = get_user_model()


class SubscriptionPlanTestMixin:
    """Mixin providing subscription plan fixtures for tests."""

    @classmethod
    def create_free_plan(cls):
        """Create a Free tier plan with minimal limits."""
        return SubscriptionPlan.objects.create(
            name="Free Test Plan",
            description="Free plan for testing",
            is_free=True,
            price=Decimal("0.00"),
            price_irr=0,
            billing_cycle="monthly",
            display_order=1,
            trial_days=0,
            # Resource Limits (conservative)
            user_limit=1,
            branch_limit=1,
            inventory_limit=100,
            contacts_limit=50,
            products_limit=50,
            invoices_limit=20,
            transactions_limit=50,
            storage_limit_gb=1,
            api_calls_per_month=1000,
            # Features (minimal)
            enable_multi_branch=False,
            enable_advanced_reporting=False,
            enable_api_access=False,
            enable_custom_branding=False,
            enable_priority_support=False,
            enable_export_import=False,
            enable_email_notifications=True,
            enable_sms_notifications=False,
            status="active",
        )

    @classmethod
    def create_starter_plan(cls):
        """Create a Starter tier plan."""
        return SubscriptionPlan.objects.create(
            name="Starter Test Plan",
            description="Starter plan for testing",
            is_free=False,
            price=Decimal("29.00"),
            price_irr=1500000,
            billing_cycle="monthly",
            display_order=2,
            trial_days=14,
            # Resource Limits
            user_limit=3,
            branch_limit=1,
            inventory_limit=1000,
            contacts_limit=500,
            products_limit=500,
            invoices_limit=100,
            transactions_limit=500,
            storage_limit_gb=5,
            api_calls_per_month=10000,
            # Features
            enable_multi_branch=False,
            enable_advanced_reporting=True,
            enable_api_access=False,
            enable_custom_branding=False,
            enable_priority_support=False,
            enable_export_import=True,
            enable_email_notifications=True,
            enable_sms_notifications=False,
            status="active",
        )

    @classmethod
    def create_professional_plan(cls):
        """Create a Professional tier plan."""
        return SubscriptionPlan.objects.create(
            name="Professional Test Plan",
            description="Professional plan for testing",
            is_free=False,
            price=Decimal("79.00"),
            price_irr=4000000,
            billing_cycle="monthly",
            display_order=3,
            trial_days=14,
            # Resource Limits (generous)
            user_limit=10,
            branch_limit=5,
            inventory_limit=10000,
            contacts_limit=5000,
            products_limit=5000,
            invoices_limit=500,
            transactions_limit=5000,
            storage_limit_gb=25,
            api_calls_per_month=100000,
            # Features (all enabled)
            enable_multi_branch=True,
            enable_advanced_reporting=True,
            enable_api_access=True,
            enable_custom_branding=True,
            enable_priority_support=True,
            enable_export_import=True,
            enable_email_notifications=True,
            enable_sms_notifications=True,
            status="active",
        )

    @classmethod
    def create_enterprise_plan(cls):
        """Create an Enterprise tier plan with unlimited resources."""
        return SubscriptionPlan.objects.create(
            name="Enterprise Test Plan",
            description="Enterprise plan with unlimited resources",
            is_free=False,
            price=Decimal("199.00"),
            price_irr=10000000,
            billing_cycle="monthly",
            display_order=4,
            trial_days=30,
            # Resource Limits (unlimited = -1)
            user_limit=-1,
            branch_limit=-1,
            inventory_limit=-1,
            contacts_limit=-1,
            products_limit=-1,
            invoices_limit=-1,
            transactions_limit=-1,
            storage_limit_gb=100,
            api_calls_per_month=-1,
            # Features (all enabled)
            enable_multi_branch=True,
            enable_advanced_reporting=True,
            enable_api_access=True,
            enable_custom_branding=True,
            enable_priority_support=True,
            enable_export_import=True,
            enable_email_notifications=True,
            enable_sms_notifications=True,
            status="active",
            custom_limits={"reports_per_day": -1},
            custom_features={"dedicated_support": True},
        )

    @classmethod
    def create_tenant_with_subscription(cls, plan, status="active"):
        """Create a tenant with a subscription to the given plan."""
        tenant = Tenant.objects.create(
            company_name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:8]}",
        )
        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            plan=plan,
            status=status,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timezone.timedelta(days=30),
        )
        return tenant, subscription


class TestSubscriptionEnforcementServiceBasic(TestCase, SubscriptionPlanTestMixin):
    """Test basic functionality of SubscriptionEnforcementService."""

    def setUp(self):
        """Set up test fixtures."""
        self.free_plan = self.create_free_plan()
        self.starter_plan = self.create_starter_plan()
        self.professional_plan = self.create_professional_plan()
        self.enterprise_plan = self.create_enterprise_plan()

    def test_service_initialization(self):
        """Test that service initializes correctly with a tenant."""
        tenant, _ = self.create_tenant_with_subscription(self.free_plan)
        service = SubscriptionEnforcementService(tenant)

        self.assertEqual(service.tenant, tenant)
        self.assertIsNotNone(service.subscription)

    def test_service_no_subscription(self):
        """Test service behavior when tenant has no subscription."""
        tenant = Tenant.objects.create(
            company_name="No Subscription Tenant",
            slug="no-sub-test",
        )
        service = SubscriptionEnforcementService(tenant)

        self.assertIsNone(service.subscription)
        self.assertFalse(service.has_active_subscription())

    def test_has_active_subscription_active_status(self):
        """Test active subscription detection."""
        tenant, _ = self.create_tenant_with_subscription(self.starter_plan, status="active")
        service = SubscriptionEnforcementService(tenant)

        self.assertTrue(service.has_active_subscription())

    def test_has_active_subscription_trial_status(self):
        """Test trial subscription is considered active."""
        tenant, subscription = self.create_tenant_with_subscription(
            self.starter_plan, status="trial"
        )
        subscription.trial_start = timezone.now()
        subscription.trial_end = timezone.now() + timezone.timedelta(days=14)
        subscription.save()

        service = SubscriptionEnforcementService(tenant)
        self.assertTrue(service.has_active_subscription())

    def test_has_active_subscription_expired_status(self):
        """Test expired subscription is not considered active."""
        tenant, subscription = self.create_tenant_with_subscription(
            self.starter_plan, status="expired"
        )
        service = SubscriptionEnforcementService(tenant)

        self.assertFalse(service.has_active_subscription())


class TestFreePlanLimits(TestCase, SubscriptionPlanTestMixin):
    """Test limit enforcement for Free plan."""

    def setUp(self):
        """Set up Free plan test fixtures."""
        self.plan = self.create_free_plan()
        self.tenant, self.subscription = self.create_tenant_with_subscription(self.plan)
        self.service = SubscriptionEnforcementService(self.tenant)

    def test_free_plan_user_limit(self):
        """Test Free plan has user limit of 1."""
        self.assertEqual(self.subscription.get_user_limit(), 1)

    def test_free_plan_branch_limit(self):
        """Test Free plan has branch limit of 1."""
        self.assertEqual(self.subscription.get_branch_limit(), 1)

    def test_free_plan_inventory_limit(self):
        """Test Free plan has inventory limit of 100."""
        self.assertEqual(self.subscription.get_inventory_limit(), 100)

    def test_free_plan_contacts_limit(self):
        """Test Free plan has contacts limit of 50."""
        self.assertEqual(self.subscription.get_contacts_limit(), 50)

    def test_free_plan_invoices_limit(self):
        """Test Free plan has monthly invoices limit of 20."""
        self.assertEqual(self.subscription.get_invoices_limit(), 20)

    def test_free_plan_api_calls_limit(self):
        """Test Free plan has API calls limit of 1000."""
        self.assertEqual(self.subscription.get_api_calls_per_month(), 1000)

    def test_free_plan_no_multi_branch(self):
        """Test Free plan does not have multi-branch enabled."""
        self.assertFalse(self.subscription.has_multi_branch_enabled())
        self.assertFalse(self.service.check_feature("multi_branch"))

    def test_free_plan_no_api_access(self):
        """Test Free plan does not have API access."""
        self.assertFalse(self.subscription.has_api_access_enabled())
        self.assertFalse(self.service.check_feature("api_access"))

    def test_free_plan_has_email_notifications(self):
        """Test Free plan has email notifications enabled."""
        self.assertTrue(self.subscription.has_email_notifications_enabled())
        self.assertTrue(self.service.check_feature("email_notifications"))


class TestStarterPlanLimits(TestCase, SubscriptionPlanTestMixin):
    """Test limit enforcement for Starter plan."""

    def setUp(self):
        """Set up Starter plan test fixtures."""
        self.plan = self.create_starter_plan()
        self.tenant, self.subscription = self.create_tenant_with_subscription(self.plan)
        self.service = SubscriptionEnforcementService(self.tenant)

    def test_starter_plan_user_limit(self):
        """Test Starter plan has user limit of 3."""
        self.assertEqual(self.subscription.get_user_limit(), 3)

    def test_starter_plan_inventory_limit(self):
        """Test Starter plan has inventory limit of 1000."""
        self.assertEqual(self.subscription.get_inventory_limit(), 1000)

    def test_starter_plan_contacts_limit(self):
        """Test Starter plan has contacts limit of 500."""
        self.assertEqual(self.subscription.get_contacts_limit(), 500)

    def test_starter_plan_invoices_limit(self):
        """Test Starter plan has invoices limit of 100."""
        self.assertEqual(self.subscription.get_invoices_limit(), 100)

    def test_starter_plan_has_advanced_reporting(self):
        """Test Starter plan has advanced reporting."""
        self.assertTrue(self.subscription.has_advanced_reporting_enabled())
        self.assertTrue(self.service.check_feature("advanced_reporting"))

    def test_starter_plan_has_export_import(self):
        """Test Starter plan has export/import."""
        self.assertTrue(self.subscription.has_export_import_enabled())
        self.assertTrue(self.service.check_feature("export_import"))

    def test_starter_plan_no_multi_branch(self):
        """Test Starter plan does not have multi-branch."""
        self.assertFalse(self.subscription.has_multi_branch_enabled())
        self.assertFalse(self.service.check_feature("multi_branch"))


class TestProfessionalPlanLimits(TestCase, SubscriptionPlanTestMixin):
    """Test limit enforcement for Professional plan."""

    def setUp(self):
        """Set up Professional plan test fixtures."""
        self.plan = self.create_professional_plan()
        self.tenant, self.subscription = self.create_tenant_with_subscription(self.plan)
        self.service = SubscriptionEnforcementService(self.tenant)

    def test_professional_plan_user_limit(self):
        """Test Professional plan has user limit of 10."""
        self.assertEqual(self.subscription.get_user_limit(), 10)

    def test_professional_plan_branch_limit(self):
        """Test Professional plan has branch limit of 5."""
        self.assertEqual(self.subscription.get_branch_limit(), 5)

    def test_professional_plan_inventory_limit(self):
        """Test Professional plan has inventory limit of 10000."""
        self.assertEqual(self.subscription.get_inventory_limit(), 10000)

    def test_professional_plan_has_multi_branch(self):
        """Test Professional plan has multi-branch enabled."""
        self.assertTrue(self.subscription.has_multi_branch_enabled())
        self.assertTrue(self.service.check_feature("multi_branch"))

    def test_professional_plan_has_api_access(self):
        """Test Professional plan has API access."""
        self.assertTrue(self.subscription.has_api_access_enabled())
        self.assertTrue(self.service.check_feature("api_access"))

    def test_professional_plan_has_sms_notifications(self):
        """Test Professional plan has SMS notifications."""
        self.assertTrue(self.subscription.has_sms_notifications_enabled())
        self.assertTrue(self.service.check_feature("sms_notifications"))

    def test_professional_plan_all_features_enabled(self):
        """Test Professional plan has all features enabled."""
        features = [
            "multi_branch",
            "advanced_reporting",
            "api_access",
            "custom_branding",
            "priority_support",
            "export_import",
            "email_notifications",
            "sms_notifications",
        ]
        for feature in features:
            self.assertTrue(
                self.service.check_feature(feature),
                f"Feature {feature} should be enabled for Professional plan",
            )


class TestEnterprisePlanUnlimited(TestCase, SubscriptionPlanTestMixin):
    """Test unlimited resource handling for Enterprise plan."""

    def setUp(self):
        """Set up Enterprise plan test fixtures."""
        self.plan = self.create_enterprise_plan()
        self.tenant, self.subscription = self.create_tenant_with_subscription(self.plan)
        self.service = SubscriptionEnforcementService(self.tenant)

    def test_enterprise_unlimited_users(self):
        """Test Enterprise plan has unlimited users (-1)."""
        self.assertEqual(self.subscription.get_user_limit(), -1)
        self.assertTrue(self.subscription.is_limit_unlimited("user_limit"))

    def test_enterprise_unlimited_branches(self):
        """Test Enterprise plan has unlimited branches (-1)."""
        self.assertEqual(self.subscription.get_branch_limit(), -1)
        self.assertTrue(self.subscription.is_limit_unlimited("branch_limit"))

    def test_enterprise_unlimited_inventory(self):
        """Test Enterprise plan has unlimited inventory (-1)."""
        self.assertEqual(self.subscription.get_inventory_limit(), -1)
        self.assertTrue(self.subscription.is_limit_unlimited("inventory_limit"))

    def test_enterprise_unlimited_contacts(self):
        """Test Enterprise plan has unlimited contacts (-1)."""
        self.assertEqual(self.subscription.get_contacts_limit(), -1)
        self.assertTrue(self.subscription.is_limit_unlimited("contacts_limit"))

    def test_enterprise_unlimited_api_calls(self):
        """Test Enterprise plan has unlimited API calls (-1)."""
        self.assertEqual(self.subscription.get_api_calls_per_month(), -1)
        self.assertTrue(self.subscription.is_limit_unlimited("api_calls_per_month"))

    def test_enterprise_custom_features(self):
        """Test Enterprise plan has custom features."""
        self.assertTrue(self.subscription.get_custom_feature("dedicated_support"))


class TestLimitCheckingAllowed(TestCase, SubscriptionPlanTestMixin):
    """Test limit checking when action should be ALLOWED."""

    def setUp(self):
        """Set up test fixtures."""
        self.plan = self.create_starter_plan()
        self.tenant, self.subscription = self.create_tenant_with_subscription(self.plan)
        self.service = SubscriptionEnforcementService(self.tenant)

    @patch.object(SubscriptionEnforcementService, "get_usage_stats")
    def test_check_limit_allowed_under_limit(self, mock_stats):
        """Test limit check returns ALLOWED when under limit."""
        mock_stats.return_value = UsageStats(users=1)

        result = self.service.check_limit(LimitType.USERS)

        self.assertEqual(result.result, EnforcementResult.ALLOWED)
        self.assertTrue(result.is_allowed)
        self.assertFalse(result.is_blocked)
        self.assertEqual(result.current_usage, 1)
        self.assertEqual(result.limit, 3)  # Starter plan limit
        self.assertEqual(result.remaining, 2)

    @patch.object(SubscriptionEnforcementService, "get_usage_stats")
    def test_check_limit_allowed_can_add_one(self, mock_stats):
        """Test limit check allows adding when space available."""
        mock_stats.return_value = UsageStats(users=2)

        result = self.service.check_limit(LimitType.USERS, increment=1)

        self.assertEqual(result.result, EnforcementResult.ALLOWED)
        self.assertTrue(result.is_allowed)

    @patch.object(SubscriptionEnforcementService, "get_usage_stats")
    def test_check_inventory_limit_allowed(self, mock_stats):
        """Test inventory limit check returns ALLOWED when under limit."""
        mock_stats.return_value = UsageStats(inventory_items=500)

        result = self.service.check_limit(LimitType.INVENTORY)

        self.assertEqual(result.result, EnforcementResult.ALLOWED)
        self.assertEqual(result.limit, 1000)  # Starter plan limit
        self.assertEqual(result.remaining, 500)


class TestLimitCheckingBlocked(TestCase, SubscriptionPlanTestMixin):
    """Test limit checking when action should be BLOCKED."""

    def setUp(self):
        """Set up test fixtures."""
        self.plan = self.create_free_plan()
        self.tenant, self.subscription = self.create_tenant_with_subscription(self.plan)
        self.service = SubscriptionEnforcementService(self.tenant)

    @patch.object(SubscriptionEnforcementService, "get_usage_stats")
    def test_check_limit_blocked_at_limit(self, mock_stats):
        """Test limit check returns BLOCKED when at limit."""
        mock_stats.return_value = UsageStats(users=1)  # Free plan limit is 1

        result = self.service.check_limit(LimitType.USERS, increment=1)

        self.assertEqual(result.result, EnforcementResult.BLOCKED)
        self.assertTrue(result.is_blocked)
        self.assertFalse(result.is_allowed)
        self.assertIn("User limit reached", result.message)

    @patch.object(SubscriptionEnforcementService, "get_usage_stats")
    def test_check_limit_blocked_over_limit(self, mock_stats):
        """Test limit check returns BLOCKED when would exceed limit."""
        mock_stats.return_value = UsageStats(inventory_items=100)  # Free plan limit is 100

        result = self.service.check_limit(LimitType.INVENTORY, increment=1)

        self.assertEqual(result.result, EnforcementResult.BLOCKED)
        self.assertIn("Inventory limit reached", result.message)

    @patch.object(SubscriptionEnforcementService, "get_usage_stats")
    def test_check_contacts_limit_blocked(self, mock_stats):
        """Test contacts limit check returns BLOCKED when exceeded."""
        mock_stats.return_value = UsageStats(contacts=50)  # Free plan limit is 50

        result = self.service.check_limit(LimitType.CONTACTS, increment=1)

        self.assertEqual(result.result, EnforcementResult.BLOCKED)
        self.assertIn("Contact limit reached", result.message)

    @patch.object(SubscriptionEnforcementService, "get_usage_stats")
    def test_check_invoices_limit_blocked(self, mock_stats):
        """Test invoices limit check returns BLOCKED when exceeded."""
        mock_stats.return_value = UsageStats(invoices_this_month=20)  # Free plan limit is 20

        result = self.service.check_limit(LimitType.INVOICES, increment=1)

        self.assertEqual(result.result, EnforcementResult.BLOCKED)
        self.assertIn("Monthly invoice limit reached", result.message)


class TestLimitCheckingWarning(TestCase, SubscriptionPlanTestMixin):
    """Test limit checking when usage triggers WARNING threshold (80%)."""

    def setUp(self):
        """Set up test fixtures."""
        self.plan = self.create_starter_plan()
        self.tenant, self.subscription = self.create_tenant_with_subscription(self.plan)
        self.service = SubscriptionEnforcementService(self.tenant)

    @patch.object(SubscriptionEnforcementService, "get_usage_stats")
    def test_check_limit_warning_at_80_percent(self, mock_stats):
        """Test limit check returns WARNING at 80% usage."""
        # Starter plan: inventory_limit=1000, 80% = 800
        mock_stats.return_value = UsageStats(inventory_items=800)

        result = self.service.check_limit(LimitType.INVENTORY)

        self.assertEqual(result.result, EnforcementResult.WARNING)
        self.assertTrue(result.is_allowed)  # Still allowed
        self.assertFalse(result.is_blocked)
        self.assertGreaterEqual(result.percentage_used, 80)

    @patch.object(SubscriptionEnforcementService, "get_usage_stats")
    def test_check_limit_warning_above_80_percent(self, mock_stats):
        """Test limit check returns WARNING above 80% usage."""
        # Starter plan: contacts_limit=500, 90% = 450
        mock_stats.return_value = UsageStats(contacts=450)

        result = self.service.check_limit(LimitType.CONTACTS)

        self.assertEqual(result.result, EnforcementResult.WARNING)
        self.assertEqual(result.percentage_used, 90.0)


class TestLimitCheckingUnlimited(TestCase, SubscriptionPlanTestMixin):
    """Test limit checking for unlimited resources (-1)."""

    def setUp(self):
        """Set up Enterprise plan test fixtures."""
        self.plan = self.create_enterprise_plan()
        self.tenant, self.subscription = self.create_tenant_with_subscription(self.plan)
        self.service = SubscriptionEnforcementService(self.tenant)

    @patch.object(SubscriptionEnforcementService, "get_usage_stats")
    def test_check_unlimited_users(self, mock_stats):
        """Test unlimited users always returns UNLIMITED."""
        mock_stats.return_value = UsageStats(users=1000)  # Any large number

        result = self.service.check_limit(LimitType.USERS)

        self.assertEqual(result.result, EnforcementResult.UNLIMITED)
        self.assertTrue(result.is_allowed)
        self.assertEqual(result.limit, -1)
        self.assertIn("Unlimited", result.message)

    @patch.object(SubscriptionEnforcementService, "get_usage_stats")
    def test_check_unlimited_inventory(self, mock_stats):
        """Test unlimited inventory always returns UNLIMITED."""
        mock_stats.return_value = UsageStats(inventory_items=1000000)

        result = self.service.check_limit(LimitType.INVENTORY)

        self.assertEqual(result.result, EnforcementResult.UNLIMITED)
        self.assertTrue(result.is_allowed)

    @patch.object(SubscriptionEnforcementService, "get_usage_stats")
    def test_check_unlimited_api_calls(self, mock_stats):
        """Test unlimited API calls always returns UNLIMITED."""
        mock_stats.return_value = UsageStats(api_calls_this_month=10000000)

        result = self.service.check_limit(LimitType.API_CALLS)

        self.assertEqual(result.result, EnforcementResult.UNLIMITED)


class TestNoSubscriptionHandling(TestCase, SubscriptionPlanTestMixin):
    """Test handling when tenant has no subscription."""

    def setUp(self):
        """Set up tenant without subscription."""
        self.tenant = Tenant.objects.create(
            company_name="No Subscription Tenant",
            slug="no-sub-test",
        )
        self.service = SubscriptionEnforcementService(self.tenant)

    def test_check_limit_no_subscription(self):
        """Test limit check returns NO_SUBSCRIPTION when no subscription."""
        result = self.service.check_limit(LimitType.USERS)

        self.assertEqual(result.result, EnforcementResult.NO_SUBSCRIPTION)
        self.assertFalse(result.is_allowed)
        self.assertIn("No active subscription", result.message)

    def test_check_feature_no_subscription(self):
        """Test feature check returns False when no subscription."""
        result = self.service.check_feature("api_access")

        self.assertFalse(result)


class TestSubscriptionOverrides(TestCase, SubscriptionPlanTestMixin):
    """Test subscription limit overrides."""

    def setUp(self):
        """Set up test fixtures."""
        self.plan = self.create_free_plan()
        self.tenant, self.subscription = self.create_tenant_with_subscription(self.plan)
        self.service = SubscriptionEnforcementService(self.tenant)

    def test_user_limit_override(self):
        """Test user limit can be overridden."""
        # Free plan default is 1
        self.assertEqual(self.subscription.get_user_limit(), 1)

        # Override to 5
        self.subscription.user_limit_override = 5
        self.subscription.save()

        self.assertEqual(self.subscription.get_user_limit(), 5)

    def test_inventory_limit_override(self):
        """Test inventory limit can be overridden."""
        # Free plan default is 100
        self.assertEqual(self.subscription.get_inventory_limit(), 100)

        # Override to 500
        self.subscription.inventory_limit_override = 500
        self.subscription.save()

        self.assertEqual(self.subscription.get_inventory_limit(), 500)

    def test_feature_override_enable(self):
        """Test feature can be enabled via override."""
        # Free plan doesn't have API access
        self.assertFalse(self.subscription.has_api_access_enabled())

        # Override to enable
        self.subscription.enable_api_access_override = True
        self.subscription.save()

        self.assertTrue(self.subscription.has_api_access_enabled())

    def test_feature_override_disable(self):
        """Test feature can be disabled via override."""
        # Set up Professional plan with API access
        pro_plan = self.create_professional_plan()
        tenant, subscription = self.create_tenant_with_subscription(pro_plan)

        # Professional plan has API access
        self.assertTrue(subscription.has_api_access_enabled())

        # Override to disable
        subscription.enable_api_access_override = False
        subscription.save()

        self.assertFalse(subscription.has_api_access_enabled())

    def test_override_to_unlimited(self):
        """Test limit can be overridden to unlimited (-1)."""
        # Free plan default user limit is 1
        self.assertEqual(self.subscription.get_user_limit(), 1)

        # Override to unlimited
        self.subscription.user_limit_override = -1
        self.subscription.save()

        self.assertEqual(self.subscription.get_user_limit(), -1)
        self.assertTrue(self.subscription.is_limit_unlimited("user_limit"))


class TestUsageTracking(TestCase, SubscriptionPlanTestMixin):
    """Test usage tracking functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.plan = self.create_starter_plan()
        self.tenant, self.subscription = self.create_tenant_with_subscription(self.plan)

    def test_increment_api_calls(self):
        """Test API calls counter increment."""
        self.assertEqual(self.subscription.api_calls_used_this_month, 0)

        self.subscription.increment_api_calls(5)
        self.subscription.refresh_from_db()

        self.assertEqual(self.subscription.api_calls_used_this_month, 5)

    def test_increment_invoices(self):
        """Test invoices counter increment."""
        self.assertEqual(self.subscription.invoices_created_this_month, 0)

        self.subscription.increment_invoices(1)
        self.subscription.refresh_from_db()

        self.assertEqual(self.subscription.invoices_created_this_month, 1)

    def test_increment_transactions(self):
        """Test transactions counter increment."""
        self.assertEqual(self.subscription.transactions_this_month, 0)

        self.subscription.increment_transactions(10)
        self.subscription.refresh_from_db()

        self.assertEqual(self.subscription.transactions_this_month, 10)

    def test_update_storage_used(self):
        """Test storage used counter update."""
        self.assertEqual(self.subscription.storage_used_bytes, 0)

        # Add 1GB
        one_gb = 1024 * 1024 * 1024
        self.subscription.update_storage_used(one_gb)
        self.subscription.refresh_from_db()

        self.assertEqual(self.subscription.storage_used_bytes, one_gb)
        self.assertAlmostEqual(self.subscription.get_storage_used_gb(), 1.0, places=2)

    def test_storage_percentage_calculation(self):
        """Test storage percentage calculation."""
        # Starter plan has 5GB limit
        one_gb = 1024 * 1024 * 1024
        self.subscription.update_storage_used(one_gb)  # 1GB = 20%
        self.subscription.refresh_from_db()

        self.assertAlmostEqual(self.subscription.get_storage_percentage(), 20.0, places=1)


class TestMonthlyReset(TestCase, SubscriptionPlanTestMixin):
    """Test monthly usage reset functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.plan = self.create_starter_plan()
        self.tenant, self.subscription = self.create_tenant_with_subscription(self.plan)

    def test_reset_monthly_usage(self):
        """Test that reset_monthly_usage clears all monthly counters."""
        # Set up some usage
        self.subscription.api_calls_used_this_month = 5000
        self.subscription.invoices_created_this_month = 50
        self.subscription.transactions_this_month = 200
        self.subscription.save()

        # Reset
        self.subscription.reset_monthly_usage()
        self.subscription.refresh_from_db()

        # Verify reset
        self.assertEqual(self.subscription.api_calls_used_this_month, 0)
        self.assertEqual(self.subscription.invoices_created_this_month, 0)
        self.assertEqual(self.subscription.transactions_this_month, 0)
        self.assertIsNotNone(self.subscription.usage_reset_date)


class TestConvenienceFunctions(TestCase, SubscriptionPlanTestMixin):
    """Test convenience functions for limit checking."""

    def setUp(self):
        """Set up test fixtures."""
        self.plan = self.create_starter_plan()
        self.tenant, self.subscription = self.create_tenant_with_subscription(self.plan)

    @patch.object(SubscriptionEnforcementService, "get_usage_stats")
    def test_check_subscription_limit_function(self, mock_stats):
        """Test check_subscription_limit convenience function."""
        mock_stats.return_value = UsageStats(users=1)

        result = check_subscription_limit(self.tenant, LimitType.USERS)

        self.assertIsInstance(result, LimitCheckResult)
        self.assertEqual(result.result, EnforcementResult.ALLOWED)

    def test_check_subscription_feature_function(self):
        """Test check_subscription_feature convenience function."""
        result = check_subscription_feature(self.tenant, "advanced_reporting")

        self.assertTrue(result)


class TestLimitCheckResultDataclass(TestCase):
    """Test LimitCheckResult dataclass functionality."""

    def test_to_dict_normal_limit(self):
        """Test to_dict with normal limit."""
        result = LimitCheckResult(
            result=EnforcementResult.ALLOWED,
            limit_type=LimitType.USERS,
            current_usage=5,
            limit=10,
            remaining=5,
            percentage_used=50.0,
            message="Action allowed.",
        )

        data = result.to_dict()

        self.assertEqual(data["result"], "allowed")
        self.assertEqual(data["limit_type"], "users")
        self.assertEqual(data["current_usage"], 5)
        self.assertEqual(data["limit"], 10)
        self.assertEqual(data["remaining"], 5)
        self.assertEqual(data["percentage_used"], 50.0)

    def test_to_dict_unlimited(self):
        """Test to_dict with unlimited (-1) limit."""
        result = LimitCheckResult(
            result=EnforcementResult.UNLIMITED,
            limit_type=LimitType.USERS,
            current_usage=1000,
            limit=-1,
            remaining=-1,
            percentage_used=0,
            message="Unlimited.",
        )

        data = result.to_dict()

        self.assertEqual(data["limit"], "unlimited")
        self.assertEqual(data["remaining"], "unlimited")


class TestAllLimitTypes(TestCase, SubscriptionPlanTestMixin):
    """Test all limit types are properly enforced."""

    def setUp(self):
        """Set up test fixtures."""
        self.plan = self.create_starter_plan()
        self.tenant, self.subscription = self.create_tenant_with_subscription(self.plan)
        self.service = SubscriptionEnforcementService(self.tenant)

    @patch.object(SubscriptionEnforcementService, "get_usage_stats")
    def test_all_limit_types_can_be_checked(self, mock_stats):
        """Test that all limit types can be checked without errors."""
        mock_stats.return_value = UsageStats()

        limit_types = [
            LimitType.USERS,
            LimitType.BRANCHES,
            LimitType.INVENTORY,
            LimitType.CONTACTS,
            LimitType.INVOICES,
            LimitType.PRODUCTS,
            LimitType.TRANSACTIONS,
            LimitType.STORAGE,
            LimitType.API_CALLS,
        ]

        for limit_type in limit_types:
            result = self.service.check_limit(limit_type)
            self.assertIsInstance(result, LimitCheckResult)
            self.assertIn(
                result.result,
                [
                    EnforcementResult.ALLOWED,
                    EnforcementResult.WARNING,
                    EnforcementResult.BLOCKED,
                    EnforcementResult.UNLIMITED,
                ],
            )


class TestGetAllLimitsStatus(TestCase, SubscriptionPlanTestMixin):
    """Test get_all_limits_status method."""

    def setUp(self):
        """Set up test fixtures."""
        self.plan = self.create_starter_plan()
        self.tenant, self.subscription = self.create_tenant_with_subscription(self.plan)
        self.service = SubscriptionEnforcementService(self.tenant)

    @patch.object(SubscriptionEnforcementService, "get_usage_stats")
    def test_get_all_limits_status_returns_all_limits(self, mock_stats):
        """Test that get_all_limits_status returns status for all limits."""
        mock_stats.return_value = UsageStats()

        status = self.service.get_all_limits_status()

        expected_keys = [
            "users",
            "branches",
            "inventory",
            "contacts",
            "invoices",
            "products",
            "transactions",
            "storage",
            "api_calls",
        ]

        for key in expected_keys:
            self.assertIn(key, status)
            self.assertIsInstance(status[key], LimitCheckResult)


class TestSubscriptionSummary(TestCase, SubscriptionPlanTestMixin):
    """Test get_subscription_summary method."""

    def setUp(self):
        """Set up test fixtures."""
        self.plan = self.create_starter_plan()
        self.tenant, self.subscription = self.create_tenant_with_subscription(self.plan)
        self.service = SubscriptionEnforcementService(self.tenant)

    @patch.object(SubscriptionEnforcementService, "get_usage_stats")
    def test_get_subscription_summary_has_all_fields(self, mock_stats):
        """Test subscription summary contains all expected fields."""
        mock_stats.return_value = UsageStats()

        summary = self.service.get_subscription_summary()

        self.assertTrue(summary["has_subscription"])
        self.assertEqual(summary["plan_name"], "Starter Test Plan")
        self.assertEqual(summary["status"], "active")
        self.assertIn("usage", summary)
        self.assertIn("limits_status", summary)
        self.assertIn("features", summary)

    def test_get_subscription_summary_no_subscription(self):
        """Test subscription summary when no subscription."""
        tenant = Tenant.objects.create(
            company_name="No Sub",
            slug="nosub",
        )
        service = SubscriptionEnforcementService(tenant)

        summary = service.get_subscription_summary()

        self.assertFalse(summary["has_subscription"])


class TestExceptions(TestCase):
    """Test custom exception classes."""

    def test_subscription_limit_exceeded_exception(self):
        """Test SubscriptionLimitExceeded exception."""
        result = LimitCheckResult(
            result=EnforcementResult.BLOCKED,
            limit_type=LimitType.USERS,
            current_usage=10,
            limit=10,
            remaining=0,
            percentage_used=100,
            message="User limit reached (10/10).",
        )

        exc = SubscriptionLimitExceeded(result)

        self.assertEqual(exc.result, result)
        self.assertIn("User limit reached", str(exc))

    def test_feature_not_enabled_exception(self):
        """Test FeatureNotEnabled exception."""
        exc = FeatureNotEnabled("api_access")

        self.assertEqual(exc.feature_name, "api_access")
        self.assertIn("api_access", exc.message)

    def test_feature_not_enabled_custom_message(self):
        """Test FeatureNotEnabled with custom message."""
        exc = FeatureNotEnabled("api_access", "Custom message")

        self.assertEqual(exc.message, "Custom message")


class TestMultiCurrencyPricing(TestCase, SubscriptionPlanTestMixin):
    """Test multi-currency pricing in plans."""

    def test_free_plan_zero_pricing(self):
        """Test Free plan has zero pricing in both currencies."""
        plan = self.create_free_plan()

        self.assertEqual(plan.price, Decimal("0.00"))
        self.assertEqual(plan.price_irr, 0)

    def test_starter_plan_pricing(self):
        """Test Starter plan has correct multi-currency pricing."""
        plan = self.create_starter_plan()

        self.assertEqual(plan.price, Decimal("29.00"))
        self.assertEqual(plan.price_irr, 1500000)

    def test_professional_plan_pricing(self):
        """Test Professional plan has correct multi-currency pricing."""
        plan = self.create_professional_plan()

        self.assertEqual(plan.price, Decimal("79.00"))
        self.assertEqual(plan.price_irr, 4000000)

    def test_enterprise_plan_pricing(self):
        """Test Enterprise plan has correct multi-currency pricing."""
        plan = self.create_enterprise_plan()

        self.assertEqual(plan.price, Decimal("199.00"))
        self.assertEqual(plan.price_irr, 10000000)
