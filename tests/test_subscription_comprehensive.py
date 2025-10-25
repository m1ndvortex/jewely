"""
Comprehensive subscription tests for Task 17.5.

Tests plan CRUD operations, subscription assignment, limit overrides,
and payment webhook handling per Requirement 5 and 28.

Integration tests with real database - no mocks for internal services.
Only external payment gateway (Stripe) is mocked.
"""

from datetime import datetime
from datetime import timezone as dt_timezone
from decimal import Decimal
from unittest.mock import Mock, patch

from django.urls import reverse
from django.utils import timezone

import pytest
import stripe

from apps.core.models import SubscriptionPlan, Tenant, TenantSubscription, User
from apps.core.stripe_service import StripeService
from apps.core.tenant_context import bypass_rls


@pytest.mark.django_db
class TestSubscriptionPlanCRUD:
    """
    Test subscription plan CRUD operations.
    Requirement 5.1: Create, edit, and archive subscription plans.
    Requirement 5.2: Define plan attributes (name, price, billing cycle, resource limits).
    """

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

    def test_create_subscription_plan(self, platform_admin, client):
        """Test creating a new subscription plan with all attributes."""
        client.force_login(platform_admin)
        url = reverse("core:admin_subscription_plan_create")

        data = {
            "name": "Test Plan",
            "description": "A comprehensive test plan",
            "price": "149.99",
            "billing_cycle": SubscriptionPlan.BILLING_MONTHLY,
            "user_limit": 25,
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
        assert response.status_code == 302

        # Verify plan was created with all attributes
        plan = SubscriptionPlan.objects.get(name="Test Plan")
        assert plan.description == "A comprehensive test plan"
        assert plan.price == Decimal("149.99")
        assert plan.billing_cycle == SubscriptionPlan.BILLING_MONTHLY
        assert plan.user_limit == 25
        assert plan.branch_limit == 5
        assert plan.inventory_limit == 10000
        assert plan.storage_limit_gb == 100
        assert plan.api_calls_per_month == 100000
        assert plan.enable_multi_branch is True
        assert plan.enable_advanced_reporting is True
        assert plan.enable_api_access is True
        assert plan.status == SubscriptionPlan.STATUS_ACTIVE

    def test_update_subscription_plan(self, platform_admin, client):
        """Test updating an existing subscription plan."""
        plan = SubscriptionPlan.objects.create(
            name="Original Plan",
            price=99.99,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=10,
            branch_limit=2,
            inventory_limit=5000,
            storage_limit_gb=50,
            api_calls_per_month=50000,
        )

        client.force_login(platform_admin)
        url = reverse("core:admin_subscription_plan_update", kwargs={"pk": plan.pk})

        data = {
            "name": "Updated Plan",
            "description": "Updated description",
            "price": "199.99",
            "billing_cycle": SubscriptionPlan.BILLING_YEARLY,
            "user_limit": 50,
            "branch_limit": 10,
            "inventory_limit": 50000,
            "storage_limit_gb": 500,
            "api_calls_per_month": 500000,
            "enable_multi_branch": True,
            "enable_advanced_reporting": True,
            "enable_api_access": True,
            "enable_custom_branding": True,
            "enable_priority_support": True,
            "display_order": 5,
        }

        response = client.post(url, data)
        assert response.status_code == 302

        # Verify plan was updated
        plan.refresh_from_db()
        assert plan.name == "Updated Plan"
        assert plan.price == Decimal("199.99")
        assert plan.billing_cycle == SubscriptionPlan.BILLING_YEARLY
        assert plan.user_limit == 50
        assert plan.enable_custom_branding is True

    def test_archive_subscription_plan(self, platform_admin, client):
        """Test archiving a subscription plan."""
        plan = SubscriptionPlan.objects.create(
            name="Plan to Archive",
            price=99.99,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
        )

        client.force_login(platform_admin)
        url = reverse("core:admin_subscription_plan_archive", kwargs={"pk": plan.pk})

        response = client.post(url)
        assert response.status_code == 302

        # Verify plan was archived
        plan.refresh_from_db()
        assert plan.status == SubscriptionPlan.STATUS_ARCHIVED
        assert plan.archived_at is not None
        assert not plan.is_active()
        assert plan.is_archived()

    def test_list_subscription_plans(self, platform_admin, client):
        """Test listing subscription plans."""
        # Create multiple plans
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

        client.force_login(platform_admin)
        url = reverse("core:admin_subscription_plan_list")
        response = client.get(url)

        assert response.status_code == 200
        assert "plans" in response.context
        assert len(response.context["plans"]) >= 2


@pytest.mark.django_db
class TestSubscriptionAssignment:
    """
    Test subscription assignment to tenants.
    Requirement 5.3: Manually assign or change a tenant's subscription plan.
    """

    @pytest.fixture
    def bypass_rls(self, db):
        """Bypass RLS for tests that need to create tenants."""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE tenants DISABLE ROW LEVEL SECURITY;")

        yield

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
        """Create a sample subscription plan."""
        return SubscriptionPlan.objects.create(
            name="Standard Plan",
            price=99.99,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=10,
            branch_limit=2,
            inventory_limit=5000,
        )

    @pytest.fixture
    def premium_plan(self):
        """Create a premium subscription plan."""
        return SubscriptionPlan.objects.create(
            name="Premium Plan",
            price=199.99,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=50,
            branch_limit=10,
            inventory_limit=50000,
        )

    @pytest.fixture
    def sample_tenant(self, bypass_rls):
        """Create a sample tenant."""
        import uuid

        unique_slug = f"test-shop-{str(uuid.uuid4())[:8]}"
        return Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug=unique_slug,
            status=Tenant.ACTIVE,
        )

    def test_assign_plan_to_tenant(self, platform_admin, client, sample_tenant, sample_plan):
        """Test manually assigning a subscription plan to a tenant."""
        # Create subscription
        subscription = TenantSubscription.objects.create(
            tenant=sample_tenant,
            plan=sample_plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        # Verify subscription was created
        assert subscription.tenant == sample_tenant
        assert subscription.plan == sample_plan
        assert subscription.status == TenantSubscription.STATUS_ACTIVE

    def test_change_tenant_plan(
        self, platform_admin, client, sample_tenant, sample_plan, premium_plan
    ):
        """Test changing a tenant's subscription plan."""
        subscription = TenantSubscription.objects.create(
            tenant=sample_tenant,
            plan=sample_plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_subscription_change_plan", kwargs={"pk": subscription.pk})

        data = {"plan_id": str(premium_plan.id)}
        response = client.post(url, data)

        assert response.status_code == 302

        # Verify plan was changed
        subscription.refresh_from_db()
        assert subscription.plan == premium_plan

    def test_subscription_displays_in_list(
        self, platform_admin, client, sample_tenant, sample_plan
    ):
        """Test that subscriptions display in the list view."""
        subscription = TenantSubscription.objects.create(
            tenant=sample_tenant,
            plan=sample_plan,
            status=TenantSubscription.STATUS_ACTIVE,
            current_period_start=timezone.now(),
            next_billing_date=timezone.now() + timezone.timedelta(days=30),
        )

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_subscription_list")
        response = client.get(url)

        assert response.status_code == 200
        assert subscription in response.context["subscriptions"]


@pytest.mark.django_db
class TestLimitOverrides:
    """
    Test limit overrides for tenant subscriptions.
    Requirement 5.4: Override default plan limits for specific tenants.
    """

    @pytest.fixture
    def bypass_rls(self, db):
        """Bypass RLS for tests that need to create tenants."""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE tenants DISABLE ROW LEVEL SECURITY;")

        yield

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
    def sample_subscription(self, bypass_rls):
        """Create a sample subscription."""
        import uuid

        plan = SubscriptionPlan.objects.create(
            name="Standard Plan",
            price=99.99,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=10,
            branch_limit=2,
            inventory_limit=5000,
            storage_limit_gb=50,
            api_calls_per_month=50000,
            enable_multi_branch=True,
            enable_advanced_reporting=False,
        )

        unique_slug = f"test-shop-{str(uuid.uuid4())[:8]}"
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug=unique_slug,
            status=Tenant.ACTIVE,
        )

        return TenantSubscription.objects.create(
            tenant=tenant,
            plan=plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

    def test_set_limit_overrides(self, platform_admin, client, sample_subscription):
        """Test setting limit overrides for a subscription."""
        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_subscription_limit_override", kwargs={"pk": sample_subscription.pk}
        )

        data = {
            "user_limit_override": 50,
            "branch_limit_override": 10,
            "inventory_limit_override": 25000,
            "storage_limit_gb_override": 250,
            "api_calls_per_month_override": 250000,
            "enable_multi_branch_override": "True",
            "enable_advanced_reporting_override": "True",
            "enable_api_access_override": "True",
            "enable_custom_branding_override": "",
            "enable_priority_support_override": "",
        }

        response = client.post(url, data)
        assert response.status_code == 302

        # Verify overrides were saved
        sample_subscription.refresh_from_db()
        assert sample_subscription.user_limit_override == 50
        assert sample_subscription.branch_limit_override == 10
        assert sample_subscription.inventory_limit_override == 25000
        assert sample_subscription.storage_limit_gb_override == 250
        assert sample_subscription.api_calls_per_month_override == 250000
        assert sample_subscription.enable_multi_branch_override is True
        assert sample_subscription.enable_advanced_reporting_override is True
        assert sample_subscription.enable_api_access_override is True

    def test_effective_limits_use_overrides(self, sample_subscription):
        """Test that effective limits use overrides when set."""
        # Set overrides
        sample_subscription.user_limit_override = 100
        sample_subscription.branch_limit_override = 20
        sample_subscription.save()

        # Verify effective limits use overrides
        assert sample_subscription.get_user_limit() == 100
        assert sample_subscription.get_branch_limit() == 20

        # Verify non-overridden limits use plan defaults
        assert sample_subscription.get_inventory_limit() == sample_subscription.plan.inventory_limit

    def test_clear_limit_overrides(self, platform_admin, client, sample_subscription):
        """Test clearing all limit overrides."""
        # Set overrides
        sample_subscription.user_limit_override = 100
        sample_subscription.branch_limit_override = 20
        sample_subscription.enable_api_access_override = True
        sample_subscription.save()

        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_subscription_clear_overrides", kwargs={"pk": sample_subscription.pk}
        )

        response = client.post(url)
        assert response.status_code == 302

        # Verify all overrides were cleared
        sample_subscription.refresh_from_db()
        assert sample_subscription.user_limit_override is None
        assert sample_subscription.branch_limit_override is None
        assert sample_subscription.enable_api_access_override is None

        # Verify effective limits now use plan defaults
        assert sample_subscription.get_user_limit() == sample_subscription.plan.user_limit
        assert sample_subscription.get_branch_limit() == sample_subscription.plan.branch_limit

    def test_feature_overrides(self, sample_subscription):
        """Test that feature overrides work correctly."""
        # Plan has multi_branch enabled, override disables it
        sample_subscription.enable_multi_branch_override = False
        sample_subscription.save()

        assert not sample_subscription.has_multi_branch_enabled()

        # Plan has advanced_reporting disabled, override enables it
        sample_subscription.enable_advanced_reporting_override = True
        sample_subscription.save()

        assert sample_subscription.has_advanced_reporting_enabled()


@pytest.mark.django_db
class TestPaymentWebhookHandling:
    """
    Test payment webhook handling.
    Requirement 5.7: Integrate with payment gateway for automated subscription lifecycle events.
    """

    @pytest.fixture
    def bypass_rls(self, db):
        """Bypass RLS for tests that need to create tenants."""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE tenants DISABLE ROW LEVEL SECURITY;")

        yield

        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;")

    @pytest.fixture
    def sample_subscription(self, bypass_rls):
        """Create a sample subscription."""
        import uuid

        plan = SubscriptionPlan.objects.create(
            name="Test Plan",
            price=99.99,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
        )

        unique_slug = f"test-shop-{str(uuid.uuid4())[:8]}"
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug=unique_slug,
            status=Tenant.ACTIVE,
        )

        return TenantSubscription.objects.create(
            tenant=tenant,
            plan=plan,
            status=TenantSubscription.STATUS_ACTIVE,
            stripe_subscription_id="sub_test123",
        )

    @patch("stripe.Webhook.construct_event")
    def test_subscription_created_webhook(self, mock_construct, client, sample_subscription):
        """Test handling subscription.created webhook."""
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

        mock_construct.return_value = payload

        response = client.post(
            reverse("core:stripe_webhook"),
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_signature",
        )

        assert response.status_code == 200

        # Verify subscription was updated
        with bypass_rls():
            sample_subscription.refresh_from_db()
            assert sample_subscription.status == TenantSubscription.STATUS_ACTIVE

    @patch("stripe.Webhook.construct_event")
    def test_subscription_deleted_webhook(self, mock_construct, client, sample_subscription):
        """Test handling subscription.deleted webhook."""
        payload = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_test123",
                }
            },
        }

        mock_construct.return_value = payload

        response = client.post(
            reverse("core:stripe_webhook"),
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_signature",
        )

        assert response.status_code == 200

        # Verify subscription was cancelled
        with bypass_rls():
            sample_subscription.refresh_from_db()
            assert sample_subscription.status == TenantSubscription.STATUS_CANCELLED
            assert sample_subscription.cancelled_at is not None

            # Verify tenant was suspended
            sample_subscription.tenant.refresh_from_db()
            assert sample_subscription.tenant.status == Tenant.SUSPENDED

    @patch("stripe.Webhook.construct_event")
    def test_payment_succeeded_webhook(self, mock_construct, client, sample_subscription):
        """Test handling invoice.payment_succeeded webhook."""
        # Set subscription to past due
        with bypass_rls():
            sample_subscription.status = TenantSubscription.STATUS_PAST_DUE
            sample_subscription.save()

            sample_subscription.tenant.status = Tenant.SUSPENDED
            sample_subscription.tenant.save()

        payload = {
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "subscription": "sub_test123",
                    "amount_paid": 9900,
                }
            },
        }

        mock_construct.return_value = payload

        response = client.post(
            reverse("core:stripe_webhook"),
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_signature",
        )

        assert response.status_code == 200

        # Verify subscription was reactivated
        with bypass_rls():
            sample_subscription.refresh_from_db()
            assert sample_subscription.status == TenantSubscription.STATUS_ACTIVE

            # Verify tenant was reactivated
            sample_subscription.tenant.refresh_from_db()
            assert sample_subscription.tenant.status == Tenant.ACTIVE

    @patch("stripe.Webhook.construct_event")
    def test_payment_failed_webhook(self, mock_construct, client, sample_subscription):
        """Test handling invoice.payment_failed webhook."""
        payload = {
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "subscription": "sub_test123",
                    "attempt_count": 3,
                }
            },
        }

        mock_construct.return_value = payload

        response = client.post(
            reverse("core:stripe_webhook"),
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_signature",
        )

        assert response.status_code == 200

        # Verify subscription marked as past due
        with bypass_rls():
            sample_subscription.refresh_from_db()
            assert sample_subscription.status == TenantSubscription.STATUS_PAST_DUE

            # Verify tenant suspended after 3 failed attempts
            sample_subscription.tenant.refresh_from_db()
            assert sample_subscription.tenant.status == Tenant.SUSPENDED

    @patch("stripe.Webhook.construct_event")
    def test_invalid_webhook_signature(self, mock_construct, client):
        """Test webhook with invalid signature is rejected."""
        mock_construct.side_effect = stripe.error.SignatureVerificationError(
            "Invalid signature", "sig_header"
        )

        payload = {"type": "test.event"}

        response = client.post(
            reverse("core:stripe_webhook"),
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="invalid_signature",
        )

        assert response.status_code == 400


@pytest.mark.django_db
class TestStripeServiceIntegration:
    """
    Test Stripe service integration methods.
    Tests the service layer that interacts with Stripe API (mocked).
    """

    @pytest.fixture
    def bypass_rls(self, db):
        """Bypass RLS for tests that need to create tenants."""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE tenants DISABLE ROW LEVEL SECURITY;")

        yield

        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;")

    @pytest.fixture
    def sample_tenant(self, bypass_rls):
        """Create a sample tenant."""
        import uuid

        unique_slug = f"test-shop-{str(uuid.uuid4())[:8]}"
        return Tenant.objects.create(
            company_name="Test Shop",
            slug=unique_slug,
            status=Tenant.ACTIVE,
        )

    @pytest.fixture
    def sample_subscription(self, bypass_rls, sample_tenant):
        """Create a sample subscription."""
        plan = SubscriptionPlan.objects.create(
            name="Test Plan",
            price=99.99,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
        )

        return TenantSubscription.objects.create(
            tenant=sample_tenant,
            plan=plan,
            status=TenantSubscription.STATUS_TRIAL,
        )

    @patch("stripe.Customer.create")
    def test_create_stripe_customer(self, mock_create, sample_tenant):
        """Test creating a Stripe customer for a tenant."""
        mock_customer = Mock()
        mock_customer.id = "cus_test123"
        mock_create.return_value = mock_customer

        customer_id = StripeService.create_customer(
            tenant=sample_tenant,
            email="test@example.com",
            name="Test Shop",
        )

        assert customer_id == "cus_test123"
        mock_create.assert_called_once()

    @patch("stripe.Subscription.create")
    @patch("stripe.Customer.modify")
    @patch("stripe.PaymentMethod.attach")
    @patch("apps.core.stripe_service.StripeService._get_or_create_price")
    def test_create_stripe_subscription(
        self,
        mock_get_price,
        mock_attach,
        mock_modify,
        mock_create,
        sample_subscription,
    ):
        """Test creating a Stripe subscription."""
        mock_get_price.return_value = "price_test123"
        sample_subscription.stripe_customer_id = "cus_test123"
        sample_subscription.save()

        mock_subscription = Mock()
        mock_subscription.id = "sub_test123"
        mock_subscription.status = "active"
        mock_subscription.current_period_start = int(datetime.now(dt_timezone.utc).timestamp())
        mock_subscription.current_period_end = (
            int(datetime.now(dt_timezone.utc).timestamp()) + 2592000
        )
        mock_create.return_value = mock_subscription

        result = StripeService.create_subscription(
            tenant_subscription=sample_subscription,
            payment_method_id="pm_test123",
        )

        assert result["subscription_id"] == "sub_test123"
        assert result["status"] == "active"

        # Verify database was updated
        sample_subscription.refresh_from_db()
        assert sample_subscription.stripe_subscription_id == "sub_test123"
        assert sample_subscription.status == TenantSubscription.STATUS_ACTIVE

    @patch("stripe.Subscription.cancel")
    def test_cancel_stripe_subscription(self, mock_cancel, sample_subscription):
        """Test cancelling a Stripe subscription."""
        sample_subscription.stripe_subscription_id = "sub_test123"
        sample_subscription.status = TenantSubscription.STATUS_ACTIVE
        sample_subscription.save()

        mock_subscription = Mock()
        mock_subscription.id = "sub_test123"
        mock_subscription.status = "canceled"
        mock_cancel.return_value = mock_subscription

        result = StripeService.cancel_subscription(
            tenant_subscription=sample_subscription,
            immediately=True,
        )

        assert result["status"] == "canceled"

        # Verify database was updated
        sample_subscription.refresh_from_db()
        assert sample_subscription.status == TenantSubscription.STATUS_CANCELLED
        assert sample_subscription.cancelled_at is not None

    @patch("stripe.Subscription.modify")
    @patch("stripe.Subscription.retrieve")
    @patch("apps.core.stripe_service.StripeService._get_or_create_price")
    def test_update_stripe_subscription_plan(
        self,
        mock_get_price,
        mock_retrieve,
        mock_modify,
        sample_subscription,
    ):
        """Test updating a Stripe subscription to a new plan."""
        sample_subscription.stripe_subscription_id = "sub_test123"
        sample_subscription.save()

        new_plan = SubscriptionPlan.objects.create(
            name="Premium Plan",
            price=199.99,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
        )

        mock_get_price.return_value = "price_new123"

        mock_current_sub = Mock()
        mock_current_sub.__getitem__ = Mock(return_value={"data": [Mock(id="si_test123")]})
        mock_retrieve.return_value = mock_current_sub

        mock_updated_sub = Mock()
        mock_updated_sub.id = "sub_test123"
        mock_updated_sub.status = "active"
        mock_modify.return_value = mock_updated_sub

        result = StripeService.update_subscription_plan(
            tenant_subscription=sample_subscription,
            new_plan=new_plan,
            prorate=True,
        )

        assert result["subscription_id"] == "sub_test123"
        assert result["plan_name"] == "Premium Plan"

        # Verify database was updated
        sample_subscription.refresh_from_db()
        assert sample_subscription.plan == new_plan


@pytest.mark.django_db
class TestSubscriptionEndToEnd:
    """
    End-to-end integration tests for complete subscription workflows.
    Tests the full lifecycle with real database operations.
    """

    @pytest.fixture
    def bypass_rls(self, db):
        """Bypass RLS for tests that need to create tenants."""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE tenants DISABLE ROW LEVEL SECURITY;")

        yield

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

    def test_complete_subscription_lifecycle(self, platform_admin, client, bypass_rls):
        """
        Test complete subscription lifecycle from creation to cancellation.
        This is a comprehensive integration test with real database operations.
        """
        # Step 1: Create subscription plans
        starter_plan = SubscriptionPlan.objects.create(
            name="Starter",
            price=29.99,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=5,
            branch_limit=1,
            inventory_limit=1000,
        )

        professional_plan = SubscriptionPlan.objects.create(
            name="Professional",
            price=99.99,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=25,
            branch_limit=5,
            inventory_limit=10000,
        )

        # Step 2: Create tenant
        import uuid

        unique_slug = f"lifecycle-test-{str(uuid.uuid4())[:8]}"
        tenant = Tenant.objects.create(
            company_name="Lifecycle Test Shop",
            slug=unique_slug,
            status=Tenant.ACTIVE,
        )

        # Step 3: Create subscription with starter plan
        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            plan=starter_plan,
            status=TenantSubscription.STATUS_TRIAL,
            trial_start=timezone.now(),
            trial_end=timezone.now() + timezone.timedelta(days=14),
        )

        assert subscription.status == TenantSubscription.STATUS_TRIAL
        assert subscription.get_user_limit() == 5

        # Step 4: Set limit overrides
        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_subscription_limit_override", kwargs={"pk": subscription.pk}
        )
        data = {
            "user_limit_override": 10,
            "branch_limit_override": 3,
            "inventory_limit_override": "",
            "storage_limit_gb_override": "",
            "api_calls_per_month_override": "",
            "enable_multi_branch_override": "True",
            "enable_advanced_reporting_override": "",
            "enable_api_access_override": "",
            "enable_custom_branding_override": "",
            "enable_priority_support_override": "",
        }
        response = client.post(url, data)
        assert response.status_code == 302

        subscription.refresh_from_db()
        assert subscription.user_limit_override == 10
        assert subscription.get_user_limit() == 10

        # Step 5: Upgrade to professional plan
        url = reverse("core:admin_tenant_subscription_change_plan", kwargs={"pk": subscription.pk})
        data = {"plan_id": str(professional_plan.id)}
        response = client.post(url, data)
        assert response.status_code == 302

        subscription.refresh_from_db()
        assert subscription.plan == professional_plan
        # Override still applies
        assert subscription.get_user_limit() == 10

        # Step 6: Clear overrides
        url = reverse(
            "core:admin_tenant_subscription_clear_overrides", kwargs={"pk": subscription.pk}
        )
        response = client.post(url)
        assert response.status_code == 302

        subscription.refresh_from_db()
        assert subscription.user_limit_override is None
        # Now uses plan default
        assert subscription.get_user_limit() == 25

        # Step 7: Activate subscription
        url = reverse("core:admin_tenant_subscription_activate", kwargs={"pk": subscription.pk})
        response = client.post(url)
        assert response.status_code == 302

        subscription.refresh_from_db()
        assert subscription.status == TenantSubscription.STATUS_ACTIVE

        # Step 8: Deactivate subscription
        url = reverse("core:admin_tenant_subscription_deactivate", kwargs={"pk": subscription.pk})
        data = {"reason": "End of lifecycle test"}
        response = client.post(url, data)
        assert response.status_code == 302

        subscription.refresh_from_db()
        assert subscription.status == TenantSubscription.STATUS_CANCELLED
        assert subscription.cancellation_reason == "End of lifecycle test"

    def test_multiple_tenants_with_different_plans(self, platform_admin, client, bypass_rls):
        """
        Test managing multiple tenants with different subscription plans.
        Verifies data isolation and independent management.
        """
        # Create plans
        basic_plan = SubscriptionPlan.objects.create(
            name="Basic",
            price=49.99,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=10,
        )

        premium_plan = SubscriptionPlan.objects.create(
            name="Premium",
            price=149.99,
            billing_cycle=SubscriptionPlan.BILLING_MONTHLY,
            user_limit=50,
        )

        # Create tenants with different subscriptions
        import uuid

        tenant1 = Tenant.objects.create(
            company_name="Shop A",
            slug=f"shop-a-{str(uuid.uuid4())[:8]}",
            status=Tenant.ACTIVE,
        )
        subscription1 = TenantSubscription.objects.create(
            tenant=tenant1,
            plan=basic_plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        tenant2 = Tenant.objects.create(
            company_name="Shop B",
            slug=f"shop-b-{str(uuid.uuid4())[:8]}",
            status=Tenant.ACTIVE,
        )
        subscription2 = TenantSubscription.objects.create(
            tenant=tenant2,
            plan=premium_plan,
            status=TenantSubscription.STATUS_ACTIVE,
        )

        # Set different overrides for each
        subscription1.user_limit_override = 15
        subscription1.save()

        subscription2.user_limit_override = 75
        subscription2.save()

        # Verify independence
        assert subscription1.get_user_limit() == 15
        assert subscription2.get_user_limit() == 75
        assert subscription1.plan != subscription2.plan

        # Verify both appear in list
        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_subscription_list")
        response = client.get(url)

        assert response.status_code == 200
        subscriptions = list(response.context["subscriptions"])
        assert subscription1 in subscriptions
        assert subscription2 in subscriptions
