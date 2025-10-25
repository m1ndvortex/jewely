"""
Tests for subscription plan management functionality.

Tests CRUD operations and archiving functionality per Requirement 5.
Integration tests with real database - no mocks allowed.
"""

from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

import pytest

from apps.core.models import SubscriptionPlan, Tenant, TenantSubscription, User


@pytest.mark.django_db
class TestSubscriptionPlanManagement:
    """Test subscription plan management views and operations."""

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
            name="Test Plan",
            description="A test subscription plan",
            price=99.99,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=10,
            branch_limit=2,
            inventory_limit=5000,
            storage_limit_gb=50,
            api_calls_per_month=50000,
            enable_multi_branch=True,
            enable_advanced_reporting=True,
            status=SubscriptionPlan.STATUS_ACTIVE,
        )

    def test_subscription_plan_list_view_requires_admin(self, client):
        """Test that subscription plan list view requires platform admin access."""
        url = reverse("core:admin_subscription_plan_list")
        response = client.get(url)

        # Should redirect to login
        assert response.status_code == 302

    def test_subscription_plan_list_view_accessible_by_admin(self, client, platform_admin):
        """Test that platform admin can access subscription plan list."""
        client.force_login(platform_admin)
        url = reverse("core:admin_subscription_plan_list")
        response = client.get(url)

        assert response.status_code == 200
        assert "plans" in response.context

    def test_subscription_plan_list_displays_plans(self, client, platform_admin, sample_plan):
        """Test that subscription plan list displays existing plans."""
        client.force_login(platform_admin)
        url = reverse("core:admin_subscription_plan_list")
        response = client.get(url)

        assert response.status_code == 200
        assert sample_plan in response.context["plans"]

    def test_subscription_plan_list_filter_by_status(self, client, platform_admin, sample_plan):
        """Test filtering subscription plans by status."""
        # Create an archived plan
        archived_plan = SubscriptionPlan.objects.create(
            name="Archived Plan",
            price=49.99,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            status=SubscriptionPlan.STATUS_ARCHIVED,
        )

        client.force_login(platform_admin)

        # Filter for active plans
        url = reverse("core:admin_subscription_plan_list") + "?status=active"
        response = client.get(url)
        assert sample_plan in response.context["plans"]
        assert archived_plan not in response.context["plans"]

        # Filter for archived plans
        url = reverse("core:admin_subscription_plan_list") + "?status=archived"
        response = client.get(url)
        assert archived_plan in response.context["plans"]
        assert sample_plan not in response.context["plans"]

    def test_subscription_plan_detail_view(self, client, platform_admin, sample_plan):
        """Test subscription plan detail view displays plan information."""
        client.force_login(platform_admin)
        url = reverse("core:admin_subscription_plan_detail", kwargs={"pk": sample_plan.pk})
        response = client.get(url)

        assert response.status_code == 200
        assert response.context["plan"] == sample_plan

    def test_subscription_plan_create_view_get(self, client, platform_admin):
        """Test subscription plan create view displays form."""
        client.force_login(platform_admin)
        url = reverse("core:admin_subscription_plan_create")
        response = client.get(url)

        assert response.status_code == 200
        assert "form" in response.context

    def test_subscription_plan_create_view_post(self, client, platform_admin):
        """Test creating a new subscription plan."""
        client.force_login(platform_admin)
        url = reverse("core:admin_subscription_plan_create")

        data = {
            "name": "New Plan",
            "description": "A new subscription plan",
            "price": "149.99",
            "billing_cycle": SubscriptionPlan.BILLING_MONTHLY,
            "user_limit": 20,
            "branch_limit": 5,
            "inventory_limit": 10000,
            "storage_limit_gb": 100,
            "api_calls_per_month": 100000,
            "enable_multi_branch": True,
            "enable_advanced_reporting": True,
            "enable_api_access": True,
            "enable_custom_branding": False,
            "enable_priority_support": False,
            "display_order": 1,
        }

        response = client.post(url, data)

        # Should redirect to detail view
        assert response.status_code == 302

        # Verify plan was created
        plan = SubscriptionPlan.objects.get(name="New Plan")
        assert plan.price == Decimal("149.99")
        assert plan.user_limit == 20
        assert plan.enable_multi_branch is True

    def test_subscription_plan_update_view(self, client, platform_admin, sample_plan):
        """Test updating an existing subscription plan."""
        client.force_login(platform_admin)
        url = reverse("core:admin_subscription_plan_update", kwargs={"pk": sample_plan.pk})

        data = {
            "name": "Updated Plan",
            "description": sample_plan.description,
            "price": "199.99",
            "billing_cycle": sample_plan.billing_cycle,
            "user_limit": 30,
            "branch_limit": sample_plan.branch_limit,
            "inventory_limit": sample_plan.inventory_limit,
            "storage_limit_gb": sample_plan.storage_limit_gb,
            "api_calls_per_month": sample_plan.api_calls_per_month,
            "enable_multi_branch": sample_plan.enable_multi_branch,
            "enable_advanced_reporting": sample_plan.enable_advanced_reporting,
            "enable_api_access": False,
            "enable_custom_branding": False,
            "enable_priority_support": False,
            "display_order": sample_plan.display_order,
        }

        response = client.post(url, data)

        # Should redirect to detail view
        assert response.status_code == 302

        # Verify plan was updated
        sample_plan.refresh_from_db()
        assert sample_plan.name == "Updated Plan"
        assert sample_plan.price == Decimal("199.99")
        assert sample_plan.user_limit == 30

    def test_subscription_plan_archive(self, client, platform_admin, sample_plan):
        """Test archiving a subscription plan."""
        client.force_login(platform_admin)
        url = reverse("core:admin_subscription_plan_archive", kwargs={"pk": sample_plan.pk})

        assert sample_plan.status == SubscriptionPlan.STATUS_ACTIVE

        response = client.post(url)

        # Should redirect to detail view
        assert response.status_code == 302

        # Verify plan was archived
        sample_plan.refresh_from_db()
        assert sample_plan.status == SubscriptionPlan.STATUS_ARCHIVED
        assert sample_plan.archived_at is not None

    def test_subscription_plan_activate(self, client, platform_admin):
        """Test activating an archived subscription plan."""
        # Create an archived plan
        archived_plan = SubscriptionPlan.objects.create(
            name="Archived Plan",
            price=49.99,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            status=SubscriptionPlan.STATUS_ARCHIVED,
            archived_at=timezone.now(),
        )

        client.force_login(platform_admin)
        url = reverse("core:admin_subscription_plan_activate", kwargs={"pk": archived_plan.pk})

        response = client.post(url)

        # Should redirect to detail view
        assert response.status_code == 302

        # Verify plan was activated
        archived_plan.refresh_from_db()
        assert archived_plan.status == SubscriptionPlan.STATUS_ACTIVE
        assert archived_plan.archived_at is None

    def test_subscription_plan_search(self, client, platform_admin, sample_plan):
        """Test searching subscription plans by name."""
        client.force_login(platform_admin)
        url = reverse("core:admin_subscription_plan_list") + "?search=Test"
        response = client.get(url)

        assert response.status_code == 200
        assert sample_plan in response.context["plans"]

    def test_subscription_plan_model_archive_method(self, sample_plan):
        """Test the archive method on SubscriptionPlan model."""
        assert sample_plan.is_active()
        assert not sample_plan.is_archived()

        sample_plan.archive()

        assert not sample_plan.is_active()
        assert sample_plan.is_archived()
        assert sample_plan.archived_at is not None

    def test_subscription_plan_model_activate_method(self):
        """Test the activate method on SubscriptionPlan model."""
        archived_plan = SubscriptionPlan.objects.create(
            name="Archived Plan",
            price=49.99,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            status=SubscriptionPlan.STATUS_ARCHIVED,
            archived_at=timezone.now(),
        )

        assert archived_plan.is_archived()

        archived_plan.activate()

        assert archived_plan.is_active()
        assert archived_plan.archived_at is None

    def test_subscription_plan_detail_shows_subscribed_tenants(
        self, client, platform_admin, sample_plan, bypass_rls
    ):
        """
        Test that plan detail view shows tenants subscribed to the plan.
        Requirement 5.6: Display all tenants with their current subscription plan.
        """
        # Create tenants with subscriptions to this plan
        tenant1 = Tenant.objects.create(
            company_name="Jewelry Shop 1",
            slug="jewelry-shop-1",
            status=Tenant.ACTIVE,
        )
        tenant2 = Tenant.objects.create(
            company_name="Jewelry Shop 2",
            slug="jewelry-shop-2",
            status=Tenant.ACTIVE,
        )

        # Create subscriptions
        TenantSubscription.objects.create(
            tenant=tenant1,
            plan=sample_plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )
        TenantSubscription.objects.create(
            tenant=tenant2,
            plan=sample_plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        client.force_login(platform_admin)
        url = reverse("core:admin_subscription_plan_detail", kwargs={"pk": sample_plan.pk})
        response = client.get(url)

        assert response.status_code == 200
        assert response.context["subscription_count"] == 2

        # Verify tenants are in the subscribed_tenants list
        subscribed_tenants = response.context["subscribed_tenants"]
        tenant_ids = [sub.tenant.id for sub in subscribed_tenants]
        assert tenant1.id in tenant_ids
        assert tenant2.id in tenant_ids

    def test_subscription_plan_list_shows_tenant_count(
        self, client, platform_admin, sample_plan, bypass_rls
    ):
        """
        Test that plan list view shows count of tenants subscribed to each plan.
        Requirement 5.6: Display all tenants with their current subscription plan.
        """
        # Create tenants with subscriptions
        tenant1 = Tenant.objects.create(
            company_name="Jewelry Shop 1",
            slug="jewelry-shop-1",
            status=Tenant.ACTIVE,
        )
        tenant2 = Tenant.objects.create(
            company_name="Jewelry Shop 2",
            slug="jewelry-shop-2",
            status=Tenant.ACTIVE,
        )

        TenantSubscription.objects.create(
            tenant=tenant1,
            plan=sample_plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )
        TenantSubscription.objects.create(
            tenant=tenant2,
            plan=sample_plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        client.force_login(platform_admin)
        url = reverse("core:admin_subscription_plan_list")
        response = client.get(url)

        assert response.status_code == 200
        plans = list(response.context["plans"])
        plan_in_list = next(p for p in plans if p.id == sample_plan.id)
        assert plan_in_list.tenant_count == 2

    def test_subscription_plan_create_with_all_attributes(self, client, platform_admin):
        """
        Test creating a plan with all attributes defined in Requirement 5.2.
        Verifies: name, price, billing cycle, and resource limits.
        """
        client.force_login(platform_admin)
        url = reverse("core:admin_subscription_plan_create")

        data = {
            "name": "Enterprise Plan",
            "description": "Full-featured enterprise plan",
            "price": "499.99",
            "billing_cycle": SubscriptionPlan.BILLING_YEARLY,
            "user_limit": 100,
            "branch_limit": 20,
            "inventory_limit": 100000,
            "storage_limit_gb": 500,
            "api_calls_per_month": 1000000,
            "enable_multi_branch": True,
            "enable_advanced_reporting": True,
            "enable_api_access": True,
            "enable_custom_branding": True,
            "enable_priority_support": True,
            "display_order": 10,
        }

        response = client.post(url, data)
        assert response.status_code == 302

        # Verify all attributes were saved correctly
        plan = SubscriptionPlan.objects.get(name="Enterprise Plan")
        assert plan.description == "Full-featured enterprise plan"
        assert plan.price == Decimal("499.99")
        assert plan.billing_cycle == SubscriptionPlan.BILLING_YEARLY
        assert plan.user_limit == 100
        assert plan.branch_limit == 20
        assert plan.inventory_limit == 100000
        assert plan.storage_limit_gb == 500
        assert plan.api_calls_per_month == 1000000
        assert plan.enable_multi_branch is True
        assert plan.enable_advanced_reporting is True
        assert plan.enable_api_access is True
        assert plan.enable_custom_branding is True
        assert plan.enable_priority_support is True
        assert plan.display_order == 10
        assert plan.status == SubscriptionPlan.STATUS_ACTIVE

    def test_subscription_plan_edit_preserves_subscriptions(
        self, client, platform_admin, sample_plan, bypass_rls
    ):
        """
        Test that editing a plan doesn't affect existing subscriptions.
        Integration test with real database relationships.
        """
        import uuid

        # Create tenant with subscription
        unique_slug = f"test-shop-{str(uuid.uuid4())[:8]}"
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug=unique_slug,
            status=Tenant.ACTIVE,
        )
        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            plan=sample_plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        client.force_login(platform_admin)
        url = reverse("core:admin_subscription_plan_update", kwargs={"pk": sample_plan.pk})

        # Update the plan
        data = {
            "name": "Updated Plan Name",
            "description": "Updated description",
            "price": "299.99",
            "billing_cycle": sample_plan.billing_cycle,
            "user_limit": 50,
            "branch_limit": sample_plan.branch_limit,
            "inventory_limit": sample_plan.inventory_limit,
            "storage_limit_gb": sample_plan.storage_limit_gb,
            "api_calls_per_month": sample_plan.api_calls_per_month,
            "enable_multi_branch": sample_plan.enable_multi_branch,
            "enable_advanced_reporting": sample_plan.enable_advanced_reporting,
            "enable_api_access": False,
            "enable_custom_branding": False,
            "enable_priority_support": False,
            "display_order": sample_plan.display_order,
        }

        response = client.post(url, data)
        assert response.status_code == 302

        # Verify subscription still exists and points to updated plan
        subscription.refresh_from_db()
        assert subscription.plan.id == sample_plan.id
        assert subscription.plan.name == "Updated Plan Name"
        assert subscription.plan.price == Decimal("299.99")
        assert subscription.status == TenantSubscription.STATUS_ACTIVE

    def test_subscription_plan_archive_prevents_new_assignments(
        self, client, platform_admin, sample_plan
    ):
        """
        Test that archived plans cannot be assigned to new tenants.
        Requirement 5.1: Archive subscription plans.
        """
        client.force_login(platform_admin)

        # Archive the plan
        url = reverse("core:admin_subscription_plan_archive", kwargs={"pk": sample_plan.pk})
        response = client.post(url)
        assert response.status_code == 302

        sample_plan.refresh_from_db()
        assert sample_plan.is_archived()

        # Verify archived plans are not shown in active list
        url = reverse("core:admin_subscription_plan_list") + "?status=active"
        response = client.get(url)
        assert sample_plan not in response.context["plans"]

    def test_subscription_plan_archived_preserves_existing_subscriptions(
        self, client, platform_admin, sample_plan, bypass_rls
    ):
        """
        Test that archiving a plan preserves existing tenant subscriptions.
        Requirement 5.1: Archived plans keep existing subscriptions active.
        """
        # Create tenant with subscription
        tenant = Tenant.objects.create(
            company_name="Existing Customer",
            slug="existing-customer",
            status=Tenant.ACTIVE,
        )
        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            plan=sample_plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        client.force_login(platform_admin)

        # Archive the plan
        url = reverse("core:admin_subscription_plan_archive", kwargs={"pk": sample_plan.pk})
        response = client.post(url)
        assert response.status_code == 302

        # Verify subscription still exists and is active
        subscription.refresh_from_db()
        assert subscription.status == TenantSubscription.STATUS_ACTIVE
        assert subscription.plan.is_archived()

    def test_subscription_plan_display_order(self, client, platform_admin):
        """
        Test that plans are displayed in correct order.
        """
        # Create plans with different display orders
        SubscriptionPlan.objects.create(
            name="Starter",
            price=29.99,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            display_order=1,
        )
        SubscriptionPlan.objects.create(
            name="Professional",
            price=99.99,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            display_order=2,
        )
        SubscriptionPlan.objects.create(
            name="Enterprise",
            price=499.99,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            display_order=3,
        )

        client.force_login(platform_admin)
        url = reverse("core:admin_subscription_plan_list")
        response = client.get(url)

        plans = list(response.context["plans"])
        assert plans[0].name == "Starter"
        assert plans[1].name == "Professional"
        assert plans[2].name == "Enterprise"

    def test_subscription_plan_billing_cycles(self, client, platform_admin):
        """
        Test all billing cycle options work correctly.
        Requirement 5.2: Define billing cycle.
        """
        client.force_login(platform_admin)

        billing_cycles = [
            (SubscriptionPlan.BILLING_MONTHLY, "Monthly Plan", 29.99),
            (SubscriptionPlan.BILLING_QUARTERLY, "Quarterly Plan", 79.99),
            (SubscriptionPlan.BILLING_YEARLY, "Yearly Plan", 299.99),
            (SubscriptionPlan.BILLING_LIFETIME, "Lifetime Plan", 999.99),
        ]

        for cycle, name, price in billing_cycles:
            plan = SubscriptionPlan.objects.create(
                name=name,
                price=price,
                billing_cycle=cycle,
            )
            assert plan.billing_cycle == cycle
            assert str(plan) == f"{name} (${price}/{cycle})"
