"""
Tests for tenant subscription management functionality.

Tests manual plan assignment, limit overrides, and activation/deactivation
per Requirement 5.3, 5.4, and 5.5.
Integration tests with real database - no mocks allowed.
"""

from django.urls import reverse
from django.utils import timezone

import pytest

from apps.core.models import SubscriptionPlan, Tenant, TenantSubscription, User


@pytest.mark.django_db
class TestTenantSubscriptionManagement:
    """Test tenant subscription management views and operations."""

    @pytest.fixture
    def bypass_rls(self, db):
        """Bypass RLS for tests that need to create tenants."""
        from django.db import connection

        # Disable RLS for this test
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE tenants DISABLE ROW LEVEL SECURITY;")

        yield

        # Re-enable RLS after test
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;")

    @pytest.fixture
    def platform_admin(self, db):
        """Create a platform admin user for testing."""
        import uuid

        unique_id = str(uuid.uuid4())[:8]
        return User.objects.create_user(
            username=f"admin_{unique_id}",
            email=f"admin_{unique_id}@example.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

    @pytest.fixture
    def sample_plan(self):
        """Create a sample subscription plan for testing."""
        return SubscriptionPlan.objects.create(
            name="Standard Plan",
            description="Standard subscription plan",
            price=99.99,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=10,
            branch_limit=2,
            inventory_limit=5000,
            storage_limit_gb=50,
            api_calls_per_month=50000,
            enable_multi_branch=True,
            enable_advanced_reporting=False,
            enable_api_access=False,
            enable_custom_branding=False,
            enable_priority_support=False,
            status=SubscriptionPlan.STATUS_ACTIVE,
        )

    @pytest.fixture
    def premium_plan(self):
        """Create a premium subscription plan for testing."""
        return SubscriptionPlan.objects.create(
            name="Premium Plan",
            description="Premium subscription plan",
            price=199.99,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=50,
            branch_limit=10,
            inventory_limit=50000,
            storage_limit_gb=500,
            api_calls_per_month=500000,
            enable_multi_branch=True,
            enable_advanced_reporting=True,
            enable_api_access=True,
            enable_custom_branding=True,
            enable_priority_support=True,
            status=SubscriptionPlan.STATUS_ACTIVE,
        )

    @pytest.fixture
    def sample_tenant(self, bypass_rls):
        """Create a sample tenant for testing."""
        import uuid

        unique_slug = f"test-shop-{str(uuid.uuid4())[:8]}"
        return Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug=unique_slug,
            status=Tenant.ACTIVE,
        )

    @pytest.fixture
    def sample_subscription(self, sample_tenant, sample_plan):
        """Create a sample subscription for testing."""
        return TenantSubscription.objects.create(
            tenant=sample_tenant,
            plan=sample_plan,
            status=TenantSubscription.STATUS_ACTIVE,
            current_period_start=timezone.now(),
            next_billing_date=timezone.now() + timezone.timedelta(days=30),
        )

    def test_tenant_subscription_list_view_requires_admin(self, client):
        """Test that tenant subscription list view requires platform admin access."""
        url = reverse("core:admin_tenant_subscription_list")
        response = client.get(url)

        # Should redirect to login
        assert response.status_code == 302

    def test_tenant_subscription_list_view_accessible_by_admin(self, client, platform_admin):
        """Test that platform admin can access tenant subscription list."""
        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_subscription_list")
        response = client.get(url)

        assert response.status_code == 200
        assert "subscriptions" in response.context

    def test_tenant_subscription_list_displays_subscriptions(
        self, client, platform_admin, sample_subscription
    ):
        """
        Test that subscription list displays existing subscriptions.
        Requirement 5.3: Display all tenants with their current subscription plan, status, and next billing date.
        """
        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_subscription_list")
        response = client.get(url)

        assert response.status_code == 200
        assert sample_subscription in response.context["subscriptions"]

    def test_tenant_subscription_list_filter_by_status(
        self, client, platform_admin, sample_subscription, sample_tenant, sample_plan
    ):
        """Test filtering tenant subscriptions by status."""
        # Create a cancelled subscription
        cancelled_tenant = Tenant.objects.create(
            company_name="Cancelled Shop",
            slug="cancelled-shop",
            status=Tenant.ACTIVE,
        )
        cancelled_subscription = TenantSubscription.objects.create(
            tenant=cancelled_tenant,
            plan=sample_plan,
            status=TenantSubscription.STATUS_CANCELLED,
        )

        client.force_login(platform_admin)

        # Filter for active subscriptions
        url = reverse("core:admin_tenant_subscription_list") + "?status=active"
        response = client.get(url)
        assert sample_subscription in response.context["subscriptions"]
        assert cancelled_subscription not in response.context["subscriptions"]

        # Filter for cancelled subscriptions
        url = reverse("core:admin_tenant_subscription_list") + "?status=cancelled"
        response = client.get(url)
        assert cancelled_subscription in response.context["subscriptions"]
        assert sample_subscription not in response.context["subscriptions"]

    def test_tenant_subscription_list_filter_by_plan(
        self, client, platform_admin, sample_subscription, premium_plan
    ):
        """Test filtering tenant subscriptions by plan."""
        # Create subscription with different plan
        other_tenant = Tenant.objects.create(
            company_name="Other Shop",
            slug="other-shop",
            status=Tenant.ACTIVE,
        )
        other_subscription = TenantSubscription.objects.create(
            tenant=other_tenant,
            plan=premium_plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        client.force_login(platform_admin)

        # Filter by sample plan
        url = (
            reverse("core:admin_tenant_subscription_list") + f"?plan={sample_subscription.plan.id}"
        )
        response = client.get(url)
        assert sample_subscription in response.context["subscriptions"]
        assert other_subscription not in response.context["subscriptions"]

    def test_tenant_subscription_detail_view(self, client, platform_admin, sample_subscription):
        """Test subscription detail view displays subscription information."""
        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_subscription_detail", kwargs={"pk": sample_subscription.pk}
        )
        response = client.get(url)

        assert response.status_code == 200
        assert response.context["subscription"] == sample_subscription
        assert "effective_limits" in response.context
        assert "effective_features" in response.context

    def test_tenant_subscription_change_plan(
        self, client, platform_admin, sample_subscription, premium_plan
    ):
        """
        Test manually changing a tenant's subscription plan.
        Requirement 5.3: Allow administrators to manually assign or change a tenant's subscription plan.
        """
        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_subscription_change_plan", kwargs={"pk": sample_subscription.pk}
        )

        assert sample_subscription.plan.name == "Standard Plan"

        data = {"plan_id": str(premium_plan.id)}
        response = client.post(url, data)

        # Should redirect to detail view
        assert response.status_code == 302

        # Verify plan was changed
        sample_subscription.refresh_from_db()
        assert sample_subscription.plan == premium_plan
        assert sample_subscription.plan.name == "Premium Plan"

    def test_tenant_subscription_limit_override_view_get(
        self, client, platform_admin, sample_subscription
    ):
        """Test limit override view displays form with current values."""
        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_subscription_limit_override", kwargs={"pk": sample_subscription.pk}
        )
        response = client.get(url)

        assert response.status_code == 200
        assert "form" in response.context
        assert response.context["subscription"] == sample_subscription
        assert "plan_defaults" in response.context

    def test_tenant_subscription_limit_override_post(
        self, client, platform_admin, sample_subscription
    ):
        """
        Test updating limit overrides for a tenant subscription.
        Requirement 5.4: Allow administrators to override default plan limits for specific tenants.
        """
        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_subscription_limit_override", kwargs={"pk": sample_subscription.pk}
        )

        # Set overrides
        data = {
            "user_limit_override": 25,
            "branch_limit_override": 5,
            "inventory_limit_override": 10000,
            "storage_limit_gb_override": 100,
            "api_calls_per_month_override": 100000,
            "enable_multi_branch_override": "True",
            "enable_advanced_reporting_override": "True",
            "enable_api_access_override": "True",
            "enable_custom_branding_override": "",
            "enable_priority_support_override": "",
        }

        response = client.post(url, data)

        # Should redirect to detail view
        assert response.status_code == 302

        # Verify overrides were saved
        sample_subscription.refresh_from_db()
        assert sample_subscription.user_limit_override == 25
        assert sample_subscription.branch_limit_override == 5
        assert sample_subscription.inventory_limit_override == 10000
        assert sample_subscription.storage_limit_gb_override == 100
        assert sample_subscription.api_calls_per_month_override == 100000
        assert sample_subscription.enable_multi_branch_override is True
        assert sample_subscription.enable_advanced_reporting_override is True
        assert sample_subscription.enable_api_access_override is True

    def test_tenant_subscription_effective_limits_with_overrides(self, sample_subscription):
        """
        Test that effective limits use overrides when set.
        Requirement 5.4: Override default plan limits for specific tenants.
        """
        # Set some overrides
        sample_subscription.user_limit_override = 30
        sample_subscription.branch_limit_override = 8
        sample_subscription.save()

        # Verify effective limits use overrides
        assert sample_subscription.get_user_limit() == 30
        assert sample_subscription.get_branch_limit() == 8

        # Verify non-overridden limits use plan defaults
        assert sample_subscription.get_inventory_limit() == sample_subscription.plan.inventory_limit
        assert (
            sample_subscription.get_storage_limit_gb() == sample_subscription.plan.storage_limit_gb
        )

    def test_tenant_subscription_activate(self, client, platform_admin, sample_subscription):
        """
        Test manually activating a tenant subscription.
        Requirement 5.5: Allow administrators to manually activate tenant subscriptions.
        """
        # First deactivate the subscription
        sample_subscription.status = TenantSubscription.STATUS_CANCELLED
        sample_subscription.save()

        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_subscription_activate", kwargs={"pk": sample_subscription.pk}
        )

        response = client.post(url)

        # Should redirect to detail view
        assert response.status_code == 302

        # Verify subscription was activated
        sample_subscription.refresh_from_db()
        assert sample_subscription.status == TenantSubscription.STATUS_ACTIVE
        assert sample_subscription.cancelled_at is None

    def test_tenant_subscription_deactivate(self, client, platform_admin, sample_subscription):
        """
        Test manually deactivating a tenant subscription.
        Requirement 5.5: Allow administrators to manually deactivate tenant subscriptions.
        """
        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_subscription_deactivate", kwargs={"pk": sample_subscription.pk}
        )

        assert sample_subscription.status == TenantSubscription.STATUS_ACTIVE

        data = {"reason": "Test deactivation"}
        response = client.post(url, data)

        # Should redirect to detail view
        assert response.status_code == 302

        # Verify subscription was deactivated
        sample_subscription.refresh_from_db()
        assert sample_subscription.status == TenantSubscription.STATUS_CANCELLED
        assert sample_subscription.cancelled_at is not None
        assert sample_subscription.cancellation_reason == "Test deactivation"

    def test_tenant_subscription_clear_overrides(self, client, platform_admin, sample_subscription):
        """Test clearing all limit overrides for a subscription."""
        # Set some overrides
        sample_subscription.user_limit_override = 30
        sample_subscription.branch_limit_override = 8
        sample_subscription.inventory_limit_override = 15000
        sample_subscription.enable_multi_branch_override = False
        sample_subscription.save()

        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_subscription_clear_overrides", kwargs={"pk": sample_subscription.pk}
        )

        response = client.post(url)

        # Should redirect to detail view
        assert response.status_code == 302

        # Verify all overrides were cleared
        sample_subscription.refresh_from_db()
        assert sample_subscription.user_limit_override is None
        assert sample_subscription.branch_limit_override is None
        assert sample_subscription.inventory_limit_override is None
        assert sample_subscription.storage_limit_gb_override is None
        assert sample_subscription.api_calls_per_month_override is None
        assert sample_subscription.enable_multi_branch_override is None
        assert sample_subscription.enable_advanced_reporting_override is None
        assert sample_subscription.enable_api_access_override is None
        assert sample_subscription.enable_custom_branding_override is None
        assert sample_subscription.enable_priority_support_override is None

    def test_tenant_subscription_search(self, client, platform_admin, sample_subscription):
        """Test searching tenant subscriptions by tenant name."""
        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_subscription_list") + "?search=Test"
        response = client.get(url)

        assert response.status_code == 200
        assert sample_subscription in response.context["subscriptions"]

    def test_tenant_subscription_model_methods(self, sample_subscription):
        """Test TenantSubscription model helper methods."""
        # Test status check methods
        assert sample_subscription.is_active()
        assert not sample_subscription.is_trial()
        assert not sample_subscription.is_cancelled()

        # Test feature check methods
        assert (
            sample_subscription.has_multi_branch_enabled()
            == sample_subscription.plan.enable_multi_branch
        )
        assert (
            sample_subscription.has_advanced_reporting_enabled()
            == sample_subscription.plan.enable_advanced_reporting
        )

    def test_tenant_subscription_feature_overrides(self, sample_subscription):
        """Test that feature overrides work correctly."""
        # Plan has multi_branch enabled, but override disables it
        sample_subscription.enable_multi_branch_override = False
        sample_subscription.save()

        assert not sample_subscription.has_multi_branch_enabled()

        # Plan has advanced_reporting disabled, but override enables it
        sample_subscription.enable_advanced_reporting_override = True
        sample_subscription.save()

        assert sample_subscription.has_advanced_reporting_enabled()

    def test_tenant_subscription_list_shows_status_counts(
        self, client, platform_admin, sample_subscription, sample_plan
    ):
        """Test that subscription list shows correct status counts."""
        # Create subscriptions with different statuses
        trial_tenant = Tenant.objects.create(
            company_name="Trial Shop",
            slug="trial-shop",
            status=Tenant.ACTIVE,
        )
        TenantSubscription.objects.create(
            tenant=trial_tenant,
            plan=sample_plan,
            status=TenantSubscription.STATUS_TRIAL,
        )

        cancelled_tenant = Tenant.objects.create(
            company_name="Cancelled Shop",
            slug="cancelled-shop",
            status=Tenant.ACTIVE,
        )
        TenantSubscription.objects.create(
            tenant=cancelled_tenant,
            plan=sample_plan,
            status=TenantSubscription.STATUS_CANCELLED,
        )

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_subscription_list")
        response = client.get(url)

        assert response.status_code == 200
        assert response.context["active_count"] >= 1
        assert response.context["trial_count"] >= 1
        assert response.context["cancelled_count"] >= 1

    def test_tenant_subscription_detail_shows_effective_values(
        self, client, platform_admin, sample_subscription
    ):
        """Test that detail view shows effective limits and features with overrides applied."""
        # Set some overrides
        sample_subscription.user_limit_override = 40
        sample_subscription.enable_api_access_override = True
        sample_subscription.save()

        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_subscription_detail", kwargs={"pk": sample_subscription.pk}
        )
        response = client.get(url)

        assert response.status_code == 200

        # Check effective limits
        effective_limits = response.context["effective_limits"]
        assert effective_limits["user_limit"] == 40  # Overridden
        assert (
            effective_limits["branch_limit"] == sample_subscription.plan.branch_limit
        )  # Not overridden

        # Check effective features
        effective_features = response.context["effective_features"]
        assert effective_features["api_access"] is True  # Overridden
        assert (
            effective_features["multi_branch"] == sample_subscription.plan.enable_multi_branch
        )  # Not overridden

    def test_tenant_subscription_change_plan_same_plan_warning(
        self, client, platform_admin, sample_subscription
    ):
        """Test that changing to the same plan shows a warning."""
        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_subscription_change_plan", kwargs={"pk": sample_subscription.pk}
        )

        data = {"plan_id": str(sample_subscription.plan.id)}
        response = client.post(url, data, follow=True)

        # Should show warning message
        messages = list(response.context["messages"])
        assert any("already on this plan" in str(m) for m in messages)

    def test_tenant_subscription_activate_already_active_warning(
        self, client, platform_admin, sample_subscription
    ):
        """Test that activating an already active subscription shows a warning."""
        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_subscription_activate", kwargs={"pk": sample_subscription.pk}
        )

        response = client.post(url, follow=True)

        # Should show warning message
        messages = list(response.context["messages"])
        assert any("already active" in str(m) for m in messages)

    def test_tenant_subscription_filter_by_tenant_status(
        self, client, platform_admin, sample_subscription, sample_plan
    ):
        """Test filtering subscriptions by tenant status."""
        # Create subscription for suspended tenant
        suspended_tenant = Tenant.objects.create(
            company_name="Suspended Shop",
            slug="suspended-shop",
            status=Tenant.SUSPENDED,
        )
        suspended_subscription = TenantSubscription.objects.create(
            tenant=suspended_tenant,
            plan=sample_plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        client.force_login(platform_admin)

        # Filter for active tenants
        url = reverse("core:admin_tenant_subscription_list") + "?tenant_status=ACTIVE"
        response = client.get(url)
        assert sample_subscription in response.context["subscriptions"]
        assert suspended_subscription not in response.context["subscriptions"]

        # Filter for suspended tenants
        url = reverse("core:admin_tenant_subscription_list") + "?tenant_status=SUSPENDED"
        response = client.get(url)
        assert suspended_subscription in response.context["subscriptions"]
        assert sample_subscription not in response.context["subscriptions"]

    def test_complete_subscription_management_workflow(
        self, client, platform_admin, sample_plan, premium_plan, bypass_rls
    ):
        """
        Complete end-to-end integration test for subscription management workflow.
        Tests the full lifecycle: create tenant -> assign plan -> override limits -> change plan -> deactivate.
        This is a real integration test with no mocks.
        """
        # Step 1: Create a new tenant
        tenant = Tenant.objects.create(
            company_name="Complete Workflow Test Shop",
            slug="complete-workflow-test",
            status=Tenant.ACTIVE,
        )

        # Step 2: Create subscription with initial plan
        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            plan=sample_plan,
            status=TenantSubscription.STATUS_TRIAL,
            trial_start=timezone.now(),
            trial_end=timezone.now() + timezone.timedelta(days=14),
        )

        client.force_login(platform_admin)

        # Step 3: Verify subscription appears in list
        url = reverse("core:admin_tenant_subscription_list")
        response = client.get(url)
        assert response.status_code == 200
        assert subscription in response.context["subscriptions"]

        # Step 4: View subscription details
        url = reverse("core:admin_tenant_subscription_detail", kwargs={"pk": subscription.pk})
        response = client.get(url)
        assert response.status_code == 200
        assert response.context["subscription"] == subscription
        assert response.context["effective_limits"]["user_limit"] == sample_plan.user_limit

        # Step 5: Override limits
        url = reverse(
            "core:admin_tenant_subscription_limit_override", kwargs={"pk": subscription.pk}
        )
        data = {
            "user_limit_override": 100,
            "branch_limit_override": 20,
            "inventory_limit_override": 50000,
            "storage_limit_gb_override": 500,
            "api_calls_per_month_override": 1000000,
            "enable_multi_branch_override": "True",
            "enable_advanced_reporting_override": "True",
            "enable_api_access_override": "True",
            "enable_custom_branding_override": "True",
            "enable_priority_support_override": "True",
        }
        response = client.post(url, data)
        assert response.status_code == 302

        # Verify overrides were applied
        subscription.refresh_from_db()
        assert subscription.user_limit_override == 100
        assert subscription.get_user_limit() == 100
        assert subscription.enable_api_access_override is True
        assert subscription.has_api_access_enabled() is True

        # Step 6: Change plan
        url = reverse("core:admin_tenant_subscription_change_plan", kwargs={"pk": subscription.pk})
        data = {"plan_id": str(premium_plan.id)}
        response = client.post(url, data)
        assert response.status_code == 302

        subscription.refresh_from_db()
        assert subscription.plan == premium_plan

        # Verify overrides still exist after plan change
        assert subscription.user_limit_override == 100
        assert subscription.get_user_limit() == 100  # Override still applies

        # Step 7: Activate subscription (from trial to active)
        url = reverse("core:admin_tenant_subscription_activate", kwargs={"pk": subscription.pk})
        response = client.post(url)
        assert response.status_code == 302

        subscription.refresh_from_db()
        assert subscription.status == TenantSubscription.STATUS_ACTIVE

        # Step 8: Clear overrides
        url = reverse(
            "core:admin_tenant_subscription_clear_overrides", kwargs={"pk": subscription.pk}
        )
        response = client.post(url)
        assert response.status_code == 302

        subscription.refresh_from_db()
        assert subscription.user_limit_override is None
        assert subscription.get_user_limit() == premium_plan.user_limit  # Now uses plan default

        # Step 9: Deactivate subscription
        url = reverse("core:admin_tenant_subscription_deactivate", kwargs={"pk": subscription.pk})
        data = {"reason": "End-to-end test completion"}
        response = client.post(url, data)
        assert response.status_code == 302

        subscription.refresh_from_db()
        assert subscription.status == TenantSubscription.STATUS_CANCELLED
        assert subscription.cancellation_reason == "End-to-end test completion"

        # Step 10: Verify subscription still appears in list with correct status
        url = reverse("core:admin_tenant_subscription_list") + "?status=cancelled"
        response = client.get(url)
        assert response.status_code == 200
        assert subscription in response.context["subscriptions"]

    def test_subscription_management_with_multiple_tenants(
        self, client, platform_admin, sample_plan, premium_plan, bypass_rls
    ):
        """
        Test managing subscriptions for multiple tenants simultaneously.
        Verifies data isolation and correct filtering.
        """
        # Create multiple tenants with different subscriptions
        tenants_data = [
            ("Shop A", "shop-a", sample_plan, TenantSubscription.STATUS_ACTIVE),
            ("Shop B", "shop-b", premium_plan, TenantSubscription.STATUS_ACTIVE),
            ("Shop C", "shop-c", sample_plan, TenantSubscription.STATUS_TRIAL),
            ("Shop D", "shop-d", premium_plan, TenantSubscription.STATUS_CANCELLED),
        ]

        subscriptions = []
        for company_name, slug, plan, status in tenants_data:
            tenant = Tenant.objects.create(
                company_name=company_name,
                slug=slug,
                status=Tenant.ACTIVE,
            )
            subscription = TenantSubscription.objects.create(
                tenant=tenant,
                plan=plan,
                status=status,
            )
            subscriptions.append(subscription)

        client.force_login(platform_admin)

        # Test 1: List all subscriptions
        url = reverse("core:admin_tenant_subscription_list")
        response = client.get(url)
        assert response.status_code == 200
        for subscription in subscriptions:
            assert subscription in response.context["subscriptions"]

        # Test 2: Filter by plan
        url = reverse("core:admin_tenant_subscription_list") + f"?plan={sample_plan.id}"
        response = client.get(url)
        assert response.status_code == 200
        result_subscriptions = list(response.context["subscriptions"])
        assert subscriptions[0] in result_subscriptions  # Shop A
        assert subscriptions[2] in result_subscriptions  # Shop C
        assert subscriptions[1] not in result_subscriptions  # Shop B (different plan)
        assert subscriptions[3] not in result_subscriptions  # Shop D (different plan)

        # Test 3: Filter by status
        url = reverse("core:admin_tenant_subscription_list") + "?status=active"
        response = client.get(url)
        assert response.status_code == 200
        result_subscriptions = list(response.context["subscriptions"])
        assert subscriptions[0] in result_subscriptions  # Shop A
        assert subscriptions[1] in result_subscriptions  # Shop B
        assert subscriptions[2] not in result_subscriptions  # Shop C (trial)
        assert subscriptions[3] not in result_subscriptions  # Shop D (cancelled)

        # Test 4: Search by tenant name
        url = reverse("core:admin_tenant_subscription_list") + "?search=Shop A"
        response = client.get(url)
        assert response.status_code == 200
        result_subscriptions = list(response.context["subscriptions"])
        assert subscriptions[0] in result_subscriptions
        assert len(result_subscriptions) == 1

        # Test 5: Verify each subscription can be managed independently
        for subscription in subscriptions[:2]:  # Test first two
            # Set different overrides for each
            url = reverse(
                "core:admin_tenant_subscription_limit_override", kwargs={"pk": subscription.pk}
            )
            data = {
                "user_limit_override": 50 + subscriptions.index(subscription) * 10,
                "branch_limit_override": "",
                "inventory_limit_override": "",
                "storage_limit_gb_override": "",
                "api_calls_per_month_override": "",
                "enable_multi_branch_override": "",
                "enable_advanced_reporting_override": "",
                "enable_api_access_override": "",
                "enable_custom_branding_override": "",
                "enable_priority_support_override": "",
            }
            response = client.post(url, data)
            assert response.status_code == 302

        # Verify overrides are independent
        subscriptions[0].refresh_from_db()
        subscriptions[1].refresh_from_db()
        assert subscriptions[0].user_limit_override == 50
        assert subscriptions[1].user_limit_override == 60
        assert subscriptions[0].get_user_limit() != subscriptions[1].get_user_limit()
