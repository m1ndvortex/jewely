"""
Tests for the payments app.

This module provides comprehensive tests for:
- Subscription discount model
- Subscription purchase model
- Payment transaction model
- Forms
- Views
- URL routing
"""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core.models import SubscriptionPlan, Tenant, TenantSubscription
from apps.payments.forms import (
    BillingPeriodForm,
    PaymentMethodForm,
    SubscriptionCancellationForm,
    SubscriptionPlanSelectionForm,
    SubscriptionPurchaseConfirmForm,
    SubscriptionRenewalForm,
    SubscriptionUpgradeForm,
)
from apps.payments.models import PaymentTransaction, SubscriptionDiscount, SubscriptionPurchase

User = get_user_model()


def create_test_user(
    username="testuser", email="test@example.com", password="testpass123", role="PLATFORM_ADMIN"
):
    """Helper to create test users with proper role."""
    return User.objects.create_user(
        username=username,
        email=email,
        password=password,
        role=role,
    )


def create_test_plan(name="Professional", price=Decimal("99.99")):
    """Helper to create test subscription plans with correct fields."""
    plan, _ = SubscriptionPlan.objects.get_or_create(
        name=name,
        defaults={
            "description": f"{name} plan",
            "price": price,
            "user_limit": 10,
            "branch_limit": 5,
            "status": "active",
        },
    )
    return plan


def create_test_tenant(company_name="Test Store", slug="test-store"):
    """Helper to create test tenants with correct fields."""
    tenant, _ = Tenant.objects.get_or_create(
        slug=slug,
        defaults={
            "company_name": company_name,
            "status": "active",
        },
    )
    return tenant


class SubscriptionDiscountModelTests(TestCase):
    """Tests for SubscriptionDiscount model."""

    def setUp(self):
        """Set up test data - use existing seeded data or get_or_create."""
        self.discount_1_month, _ = SubscriptionDiscount.objects.get_or_create(
            billing_period_months=1,
            defaults={"discount_percentage": Decimal("0.00"), "is_active": True},
        )
        self.discount_3_months, _ = SubscriptionDiscount.objects.get_or_create(
            billing_period_months=3,
            defaults={"discount_percentage": Decimal("10.00"), "is_active": True},
        )
        self.discount_6_months, _ = SubscriptionDiscount.objects.get_or_create(
            billing_period_months=6,
            defaults={"discount_percentage": Decimal("15.00"), "is_active": True},
        )
        self.discount_12_months, _ = SubscriptionDiscount.objects.get_or_create(
            billing_period_months=12,
            defaults={"discount_percentage": Decimal("20.00"), "is_active": True},
        )

    def test_discount_creation(self):
        """Test discount model creation."""
        discount, created = SubscriptionDiscount.objects.get_or_create(
            billing_period_months=24,
            defaults={"discount_percentage": Decimal("25.00"), "is_active": True},
        )
        self.assertEqual(discount.billing_period_months, 24)
        self.assertTrue(discount.is_active)

    def test_discount_str_representation(self):
        """Test discount string representation."""
        discount_str = str(self.discount_3_months)
        self.assertIn("3", discount_str)
        self.assertIn("10", discount_str)

    def test_get_discount_for_period(self):
        """Test getting discount for a specific billing period."""
        discount = SubscriptionDiscount.objects.filter(
            billing_period_months=6, is_active=True
        ).first()
        self.assertEqual(discount.discount_percentage, Decimal("15.00"))

    def test_inactive_discount_not_returned(self):
        """Test that inactive discounts are filtered properly."""
        self.discount_3_months.is_active = False
        self.discount_3_months.save()

        active_discounts = SubscriptionDiscount.objects.filter(is_active=True)
        self.assertNotIn(self.discount_3_months, active_discounts)

    def test_calculate_discounted_price(self):
        """Test discount calculation."""
        base_price = Decimal("100.00")
        discount = self.discount_12_months

        # 20% off 100 = 80
        discount_amount = base_price * (discount.discount_percentage / 100)
        discounted_price = base_price - discount_amount

        self.assertEqual(discounted_price, Decimal("80.00"))

    def test_ordered_discounts(self):
        """Test discounts are ordered by billing period."""
        discounts = SubscriptionDiscount.objects.filter(is_active=True).order_by(
            "billing_period_months"
        )
        periods = [d.billing_period_months for d in discounts]
        self.assertEqual(periods, sorted(periods))


class SubscriptionPurchaseModelTests(TestCase):
    """Tests for SubscriptionPurchase model."""

    def setUp(self):
        """Set up test data."""
        # Create test user with proper role
        self.user = create_test_user()

        # Create subscription plan
        self.plan = create_test_plan()

        # Create tenant
        self.tenant = create_test_tenant()

        # Create discount (use get_or_create since seeded data exists)
        self.discount, _ = SubscriptionDiscount.objects.get_or_create(
            billing_period_months=3,
            defaults={"discount_percentage": Decimal("10.00"), "is_active": True},
        )

    def test_purchase_creation(self):
        """Test subscription purchase creation."""
        from datetime import date

        today = date.today()
        purchase = SubscriptionPurchase.objects.create(
            tenant=self.tenant,
            subscription_plan=self.plan,
            billing_period_months=3,
            base_price=Decimal("299.97"),
            discount_percentage=self.discount.discount_percentage,
            discount_amount=Decimal("29.99"),
            final_price=Decimal("269.98"),
            payment_status="pending",
            start_date=today,
            end_date=today,
        )

        self.assertIsNotNone(purchase.id)
        self.assertEqual(purchase.payment_status, "pending")
        self.assertEqual(purchase.billing_period_months, 3)

    def test_purchase_str_representation(self):
        """Test purchase string representation."""
        from datetime import date

        today = date.today()
        purchase = SubscriptionPurchase.objects.create(
            tenant=self.tenant,
            subscription_plan=self.plan,
            billing_period_months=1,
            base_price=Decimal("99.99"),
            discount_percentage=Decimal("0.00"),
            discount_amount=Decimal("0.00"),
            final_price=Decimal("99.99"),
            payment_status="completed",
            start_date=today,
            end_date=today,
        )

        purchase_str = str(purchase)
        # Just check it can be converted to string
        self.assertIsInstance(purchase_str, str)

    def test_purchase_status_transitions(self):
        """Test purchase status can be changed."""
        from datetime import date

        today = date.today()
        purchase = SubscriptionPurchase.objects.create(
            tenant=self.tenant,
            subscription_plan=self.plan,
            billing_period_months=1,
            base_price=Decimal("99.99"),
            discount_percentage=Decimal("0.00"),
            discount_amount=Decimal("0.00"),
            final_price=Decimal("99.99"),
            payment_status="pending",
            start_date=today,
            end_date=today,
        )

        # Transition to completed
        purchase.payment_status = "completed"
        purchase.payment_completed_at = timezone.now()
        purchase.save()

        purchase.refresh_from_db()
        self.assertEqual(purchase.payment_status, "completed")
        self.assertIsNotNone(purchase.payment_completed_at)

    def test_purchase_subscription_dates(self):
        """Test subscription date calculation."""
        from datetime import date

        today = date.today()
        end_date = today + timedelta(days=90)
        purchase = SubscriptionPurchase.objects.create(
            tenant=self.tenant,
            subscription_plan=self.plan,
            billing_period_months=3,
            base_price=Decimal("299.97"),
            discount_percentage=Decimal("0.00"),
            discount_amount=Decimal("0.00"),
            final_price=Decimal("299.97"),
            payment_status="completed",
            start_date=today,
            end_date=end_date,
        )

        # Subscription should be active
        self.assertLessEqual(purchase.start_date, today)
        self.assertGreater(purchase.end_date, today)


class PaymentTransactionModelTests(TestCase):
    """Tests for PaymentTransaction model."""

    def setUp(self):
        """Set up test data."""
        from datetime import date

        self.user = create_test_user(username="testuser2", email="test2@example.com")

        self.plan = create_test_plan(name="Professional2")

        self.tenant = create_test_tenant(company_name="Test Store 2", slug="test-store-2")

        today = date.today()
        self.purchase = SubscriptionPurchase.objects.create(
            tenant=self.tenant,
            subscription_plan=self.plan,
            billing_period_months=1,
            base_price=Decimal("99.99"),
            discount_percentage=Decimal("0.00"),
            discount_amount=Decimal("0.00"),
            final_price=Decimal("99.99"),
            payment_status="pending",
            start_date=today,
            end_date=today,
        )

    def test_transaction_creation(self):
        """Test payment transaction creation."""
        transaction = PaymentTransaction.objects.create(
            subscription_purchase=self.purchase,
            tenant=self.tenant,
            payment_gateway="placeholder",
            amount=Decimal("99.99"),
            currency="USD",
            status="pending",
        )

        self.assertIsNotNone(transaction.id)
        self.assertEqual(transaction.status, "pending")
        self.assertEqual(transaction.payment_gateway, "placeholder")

    def test_transaction_completion(self):
        """Test marking transaction as completed."""
        transaction = PaymentTransaction.objects.create(
            subscription_purchase=self.purchase,
            tenant=self.tenant,
            payment_gateway="placeholder",
            amount=Decimal("99.99"),
            currency="USD",
            status="pending",
        )

        transaction.status = "completed"
        transaction.completed_at = timezone.now()
        transaction.response_data = {"status": "success"}
        transaction.save()

        transaction.refresh_from_db()
        self.assertEqual(transaction.status, "completed")
        self.assertIsNotNone(transaction.completed_at)

    def test_transaction_failure(self):
        """Test marking transaction as failed."""
        transaction = PaymentTransaction.objects.create(
            subscription_purchase=self.purchase,
            tenant=self.tenant,
            payment_gateway="placeholder",
            amount=Decimal("99.99"),
            currency="USD",
            status="pending",
        )

        transaction.status = "failed"
        transaction.error_message = "Insufficient funds"
        transaction.response_data = {"error": "insufficient_funds"}
        transaction.save()

        transaction.refresh_from_db()
        self.assertEqual(transaction.status, "failed")
        self.assertEqual(transaction.error_message, "Insufficient funds")

    def test_multiple_transactions_for_purchase(self):
        """Test multiple payment attempts for same purchase."""
        # First attempt - failed
        PaymentTransaction.objects.create(
            subscription_purchase=self.purchase,
            tenant=self.tenant,
            payment_gateway="placeholder",
            amount=Decimal("99.99"),
            currency="USD",
            status="failed",
            error_message="Card declined",
        )

        # Second attempt - successful
        PaymentTransaction.objects.create(
            subscription_purchase=self.purchase,
            tenant=self.tenant,
            payment_gateway="placeholder",
            amount=Decimal("99.99"),
            currency="USD",
            status="completed",
        )

        transactions = PaymentTransaction.objects.filter(subscription_purchase=self.purchase)
        self.assertEqual(transactions.count(), 2)


class SubscriptionFormsTests(TestCase):
    """Tests for subscription forms."""

    def setUp(self):
        """Set up test data."""
        self.plan = create_test_plan(name="Professional3")

        self.discount, _ = SubscriptionDiscount.objects.get_or_create(
            billing_period_months=3,
            defaults={"discount_percentage": Decimal("10.00"), "is_active": True},
        )

    def test_plan_selection_form_valid(self):
        """Test plan selection form with valid data."""
        form = SubscriptionPlanSelectionForm(
            data={
                "plan": self.plan.id,
            }
        )
        self.assertTrue(form.is_valid())

    def test_plan_selection_form_invalid(self):
        """Test plan selection form with invalid data."""
        form = SubscriptionPlanSelectionForm(
            data={
                "plan": 99999,  # Non-existent plan
            }
        )
        self.assertFalse(form.is_valid())

    def test_billing_period_form_valid(self):
        """Test billing period form with valid data."""
        form = BillingPeriodForm(
            data={
                "billing_period": 3,
            }
        )
        self.assertTrue(form.is_valid())

    def test_billing_period_form_choices(self):
        """Test billing period form has correct choices."""
        form = BillingPeriodForm()
        # Check that billing period field exists
        self.assertIn("billing_period", form.fields)

    def test_payment_method_form_valid(self):
        """Test payment method form with valid data."""
        form = PaymentMethodForm(
            data={
                "payment_method": "placeholder",
            }
        )
        self.assertTrue(form.is_valid())

    def test_payment_method_form_invalid_method(self):
        """Test payment method form with invalid method."""
        form = PaymentMethodForm(
            data={
                "payment_method": "invalid_gateway",
            }
        )
        self.assertFalse(form.is_valid())

    def test_subscription_cancellation_form_valid(self):
        """Test cancellation form with confirmation."""
        form = SubscriptionCancellationForm(
            data={
                "confirm_cancellation": True,
                "reason": "too_expensive",  # Use choice key, not label
            }
        )
        self.assertTrue(form.is_valid())

    def test_subscription_cancellation_form_invalid(self):
        """Test cancellation form without confirmation."""
        form = SubscriptionCancellationForm(
            data={
                "confirm_cancellation": False,
                "reason": "too_expensive",
            }
        )
        self.assertFalse(form.is_valid())


class SubscriptionURLTests(TestCase):
    """Tests for subscription URL patterns."""

    def test_subscription_dashboard_url(self):
        """Test subscription dashboard URL."""
        url = reverse("payments:subscription_dashboard")
        self.assertEqual(url, "/subscription/")

    def test_subscription_plans_url(self):
        """Test subscription plans URL."""
        url = reverse("payments:subscription_plans")
        self.assertEqual(url, "/subscription/plans/")

    def test_purchase_subscription_url(self):
        """Test purchase subscription URL."""
        url = reverse("payments:purchase_subscription")
        self.assertEqual(url, "/subscription/purchase/")

    def test_subscription_renewal_url(self):
        """Test subscription renewal URL."""
        url = reverse("payments:subscription_renewal")
        self.assertEqual(url, "/subscription/renew/")

    def test_subscription_upgrade_url(self):
        """Test subscription upgrade URL."""
        url = reverse("payments:subscription_upgrade")
        self.assertEqual(url, "/subscription/upgrade/")

    def test_subscription_cancellation_url(self):
        """Test subscription cancellation URL."""
        url = reverse("payments:subscription_cancellation")
        self.assertEqual(url, "/subscription/cancel/")

    def test_purchase_history_url(self):
        """Test purchase history URL."""
        url = reverse("payments:purchase_history")
        self.assertEqual(url, "/subscription/history/")

    def test_payment_gateway_url(self):
        """Test payment gateway URL with purchase ID."""
        purchase_id = uuid.uuid4()
        url = reverse("payments:payment_gateway", kwargs={"purchase_id": purchase_id})
        self.assertEqual(url, f"/subscription/payment/{purchase_id}/")

    def test_purchase_detail_url(self):
        """Test purchase detail URL."""
        purchase_id = uuid.uuid4()
        url = reverse("payments:purchase_detail", kwargs={"pk": purchase_id})
        self.assertEqual(url, f"/subscription/purchase/{purchase_id}/")


class SubscriptionViewTests(TestCase):
    """Tests for subscription views."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()

        # Create test user with proper role
        self.user = create_test_user(username="testuser3", email="test3@example.com")

        # Create subscription plan
        self.plan = create_test_plan(name="Professional4")

        # Create tenant
        self.tenant = create_test_tenant(company_name="Test Store 3", slug="test-store-3")

        # Create discount
        self.discount, _ = SubscriptionDiscount.objects.get_or_create(
            billing_period_months=3,
            defaults={"discount_percentage": Decimal("10.00"), "is_active": True},
        )

    def test_subscription_dashboard_requires_login(self):
        """Test that subscription dashboard requires authentication."""
        response = self.client.get(reverse("payments:subscription_dashboard"))
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_subscription_plans_requires_login(self):
        """Test that subscription plans requires authentication."""
        response = self.client.get(reverse("payments:subscription_plans"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_purchase_subscription_requires_login(self):
        """Test that purchase subscription requires authentication."""
        response = self.client.get(reverse("payments:purchase_subscription"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)


class DiscountCalculationTests(TestCase):
    """Tests for discount calculation logic."""

    def setUp(self):
        """Set up test data - use get_or_create since seeded data exists."""
        SubscriptionDiscount.objects.get_or_create(
            billing_period_months=1,
            defaults={"discount_percentage": Decimal("0.00"), "is_active": True},
        )
        SubscriptionDiscount.objects.get_or_create(
            billing_period_months=3,
            defaults={"discount_percentage": Decimal("10.00"), "is_active": True},
        )
        SubscriptionDiscount.objects.get_or_create(
            billing_period_months=6,
            defaults={"discount_percentage": Decimal("15.00"), "is_active": True},
        )
        SubscriptionDiscount.objects.get_or_create(
            billing_period_months=12,
            defaults={"discount_percentage": Decimal("20.00"), "is_active": True},
        )

    def test_no_discount_for_1_month(self):
        """Test no discount for 1 month period."""
        discount = SubscriptionDiscount.objects.get(billing_period_months=1)
        base_price = Decimal("99.99")

        discount_amount = base_price * (discount.discount_percentage / 100)
        self.assertEqual(discount_amount, Decimal("0.00"))

    def test_10_percent_discount_for_3_months(self):
        """Test 10% discount for 3 month period."""
        discount = SubscriptionDiscount.objects.get(billing_period_months=3)
        monthly_price = Decimal("99.99")
        base_price = monthly_price * 3

        discount_amount = base_price * (discount.discount_percentage / 100)
        expected = base_price * Decimal("0.10")

        self.assertEqual(discount_amount, expected)

    def test_15_percent_discount_for_6_months(self):
        """Test 15% discount for 6 month period."""
        discount = SubscriptionDiscount.objects.get(billing_period_months=6)
        monthly_price = Decimal("99.99")
        base_price = monthly_price * 6

        discount_amount = base_price * (discount.discount_percentage / 100)
        expected = base_price * Decimal("0.15")

        self.assertEqual(discount_amount, expected)

    def test_20_percent_discount_for_12_months(self):
        """Test 20% discount for 12 month period."""
        discount = SubscriptionDiscount.objects.get(billing_period_months=12)
        monthly_price = Decimal("99.99")
        base_price = monthly_price * 12

        discount_amount = base_price * (discount.discount_percentage / 100)
        expected = base_price * Decimal("0.20")

        self.assertEqual(discount_amount, expected)

    def test_final_price_calculation(self):
        """Test full price calculation with discount."""
        discount = SubscriptionDiscount.objects.get(billing_period_months=12)
        monthly_price = Decimal("100.00")
        billing_months = 12

        base_price = monthly_price * billing_months
        discount_amount = base_price * (discount.discount_percentage / 100)
        final_price = base_price - discount_amount

        # 100 * 12 = 1200
        # 1200 * 0.20 = 240 discount
        # 1200 - 240 = 960 final
        self.assertEqual(base_price, Decimal("1200.00"))
        self.assertEqual(discount_amount, Decimal("240.00"))
        self.assertEqual(final_price, Decimal("960.00"))


class PaymentGatewayTests(TestCase):
    """Tests for payment gateway placeholder functionality."""

    def test_gateway_field_accepts_expected_values(self):
        """Test that all expected gateway values can be stored."""
        expected_gateways = [
            "placeholder",
            "paypal",
            "stripe",
            "iranian_bank",
            "crypto",
        ]

        # Verify field max_length can hold our gateway names
        field = PaymentTransaction._meta.get_field("payment_gateway")
        for gateway in expected_gateways:
            self.assertLessEqual(len(gateway), field.max_length)

    def test_placeholder_gateway_processing(self):
        """Test placeholder gateway can be used for testing."""
        from datetime import date

        user = create_test_user(username="testuser4", email="test4@example.com")

        plan = create_test_plan(name="Professional5")

        tenant = create_test_tenant(company_name="Test Store 4", slug="test-store-4")

        today = date.today()
        purchase = SubscriptionPurchase.objects.create(
            tenant=tenant,
            subscription_plan=plan,
            billing_period_months=1,
            base_price=Decimal("99.99"),
            discount_percentage=Decimal("0.00"),
            discount_amount=Decimal("0.00"),
            final_price=Decimal("99.99"),
            payment_status="pending",
            start_date=today,
            end_date=today,
        )

        transaction = PaymentTransaction.objects.create(
            subscription_purchase=purchase,
            tenant=tenant,
            payment_gateway="placeholder",
            amount=Decimal("99.99"),
            currency="USD",
            status="completed",
            response_data={"test": True, "simulated": True},
        )

        self.assertEqual(transaction.payment_gateway, "placeholder")
        self.assertEqual(transaction.status, "completed")
