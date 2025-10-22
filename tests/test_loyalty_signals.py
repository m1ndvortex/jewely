"""
Tests for loyalty program signal handlers.

Implements Requirement 36: Enhanced Loyalty Program
- Test automatic points accrual on purchases
- Test automatic tier upgrades based on spending
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from apps.core.models import Branch, Tenant
from apps.core.tenant_context import bypass_rls
from apps.crm.models import Customer, LoyaltyTier, LoyaltyTransaction
from apps.sales.models import Sale, Terminal

User = get_user_model()


@pytest.fixture(scope="function")
def loyalty_tenant(db):
    """Create a test tenant for loyalty signals."""
    with bypass_rls():
        tenant = Tenant.objects.create(
            company_name="Test Loyalty Shop", slug="test-loyalty-signals", status="ACTIVE"
        )
    yield tenant
    with bypass_rls():
        tenant.delete()


@pytest.fixture(scope="function")
def loyalty_branch(loyalty_tenant):
    """Create a test branch."""
    with bypass_rls():
        branch = Branch.objects.create(
            tenant=loyalty_tenant, name="Main Branch", address="123 Main St", phone="+1234567890"
        )
    return branch


@pytest.fixture(scope="function")
def loyalty_terminal(loyalty_branch):
    """Create a test terminal."""
    with bypass_rls():
        terminal = Terminal.objects.create(
            branch=loyalty_branch,
            terminal_id="TERM-001",
            is_active=True,
        )
    return terminal


@pytest.fixture(scope="function")
def loyalty_user(loyalty_tenant):
    """Create a test user."""
    with bypass_rls():
        user = User.objects.create_user(
            username="testloyaltyuser",
            email="testloyalty@example.com",
            password="testpass123",
            tenant=loyalty_tenant,
            role="TENANT_EMPLOYEE",
        )
    return user


@pytest.fixture(scope="function")
def bronze_tier(loyalty_tenant):
    """Create bronze loyalty tier."""
    with bypass_rls():
        tier = LoyaltyTier.objects.create(
            tenant=loyalty_tenant,
            name="Bronze",
            min_spending=Decimal("0.00"),
            discount_percentage=Decimal("5.00"),
            points_multiplier=Decimal("1.0"),
            order=0,
        )
    return tier


@pytest.fixture(scope="function")
def silver_tier(loyalty_tenant):
    """Create silver loyalty tier."""
    with bypass_rls():
        tier = LoyaltyTier.objects.create(
            tenant=loyalty_tenant,
            name="Silver",
            min_spending=Decimal("500.00"),
            discount_percentage=Decimal("10.00"),
            points_multiplier=Decimal("1.5"),
            order=1,
        )
    return tier


@pytest.fixture(scope="function")
def gold_tier(loyalty_tenant):
    """Create gold loyalty tier."""
    with bypass_rls():
        tier = LoyaltyTier.objects.create(
            tenant=loyalty_tenant,
            name="Gold",
            min_spending=Decimal("1000.00"),
            discount_percentage=Decimal("15.00"),
            points_multiplier=Decimal("2.0"),
            order=2,
        )
    return tier


@pytest.fixture(scope="function")
def loyalty_customer(loyalty_tenant, bronze_tier):
    """Create test customer with bronze tier."""
    with bypass_rls():
        customer = Customer.objects.create(
            tenant=loyalty_tenant,
            customer_number="CUST-LOYALTY-001",
            first_name="Test",
            last_name="Customer",
            phone="+1234567890",
            loyalty_tier=bronze_tier,
            loyalty_points=0,
            total_purchases=Decimal("0.00"),
        )
    return customer


@pytest.mark.django_db
class TestLoyaltySignals:
    """Test loyalty program signal handlers."""

    def test_award_points_on_completed_sale(
        self,
        loyalty_customer,
        loyalty_branch,
        loyalty_terminal,
        loyalty_user,
        loyalty_tenant,
    ):
        """Test that points are awarded when a sale is completed."""
        initial_points = loyalty_customer.loyalty_points

        # Create a completed sale
        with bypass_rls():
            sale = Sale.objects.create(
                tenant=loyalty_tenant,
                sale_number="SALE-TEST-001",
                customer=loyalty_customer,
                branch=loyalty_branch,
                terminal=loyalty_terminal,
                employee=loyalty_user,
                subtotal=Decimal("100.00"),
                tax=Decimal("10.00"),
                discount=Decimal("0.00"),
                total=Decimal("110.00"),
                payment_method=Sale.CASH,
                status=Sale.COMPLETED,
                completed_at=timezone.now(),
            )

        # Verify points were awarded
        with bypass_rls():
            customer = Customer.objects.get(id=loyalty_customer.id)
            # Should get 110 points (1 point per dollar) with 1.0 multiplier
            assert customer.loyalty_points == initial_points + 110
            assert customer.total_points_earned == 110

            # Verify loyalty transaction was created
            transaction = LoyaltyTransaction.objects.filter(
                customer=customer, sale=sale, transaction_type=LoyaltyTransaction.EARNED
            ).first()
            assert transaction is not None
            assert transaction.points == 110

    def test_no_points_for_sale_without_customer(
        self,
        loyalty_branch,
        loyalty_terminal,
        loyalty_user,
        loyalty_tenant,
    ):
        """Test that no points are awarded for sales without a customer."""
        # Create a sale without a customer
        with bypass_rls():
            sale = Sale.objects.create(
                tenant=loyalty_tenant,
                sale_number="SALE-TEST-002",
                customer=None,  # No customer
                branch=loyalty_branch,
                terminal=loyalty_terminal,
                employee=loyalty_user,
                subtotal=Decimal("100.00"),
                tax=Decimal("10.00"),
                discount=Decimal("0.00"),
                total=Decimal("110.00"),
                payment_method=Sale.CASH,
                status=Sale.COMPLETED,
                completed_at=timezone.now(),
            )

            # Verify no loyalty transaction was created
            transaction_count = LoyaltyTransaction.objects.filter(sale=sale).count()
            assert transaction_count == 0

    def test_no_points_for_non_completed_sale(
        self,
        loyalty_customer,
        loyalty_branch,
        loyalty_terminal,
        loyalty_user,
        loyalty_tenant,
    ):
        """Test that no points are awarded for non-completed sales."""
        initial_points = loyalty_customer.loyalty_points

        # Create a sale on hold
        with bypass_rls():
            sale = Sale.objects.create(
                tenant=loyalty_tenant,
                sale_number="SALE-TEST-003",
                customer=loyalty_customer,
                branch=loyalty_branch,
                terminal=loyalty_terminal,
                employee=loyalty_user,
                subtotal=Decimal("100.00"),
                tax=Decimal("10.00"),
                discount=Decimal("0.00"),
                total=Decimal("110.00"),
                payment_method=Sale.CASH,
                status=Sale.ON_HOLD,  # Not completed
            )

        # Verify no points were awarded
        with bypass_rls():
            customer = Customer.objects.get(id=loyalty_customer.id)
            assert customer.loyalty_points == initial_points

            # Verify no loyalty transaction was created
            transaction_count = LoyaltyTransaction.objects.filter(
                customer=customer, sale=sale
            ).count()
            assert transaction_count == 0

    def test_points_with_tier_multiplier(
        self,
        loyalty_customer,
        loyalty_branch,
        loyalty_terminal,
        loyalty_user,
        loyalty_tenant,
        silver_tier,
    ):
        """Test that tier multiplier is applied to points."""
        # Upgrade customer to silver tier (1.5x multiplier)
        with bypass_rls():
            loyalty_customer.loyalty_tier = silver_tier
            loyalty_customer.save()

        initial_points = loyalty_customer.loyalty_points

        # Create a completed sale
        with bypass_rls():
            sale = Sale.objects.create(  # noqa: F841
                tenant=loyalty_tenant,
                sale_number="SALE-TEST-004",
                customer=loyalty_customer,
                branch=loyalty_branch,
                terminal=loyalty_terminal,
                employee=loyalty_user,
                subtotal=Decimal("100.00"),
                tax=Decimal("0.00"),
                discount=Decimal("0.00"),
                total=Decimal("100.00"),
                payment_method=Sale.CASH,
                status=Sale.COMPLETED,
                completed_at=timezone.now(),
            )

        # Verify points were awarded with multiplier
        with bypass_rls():
            customer = Customer.objects.get(id=loyalty_customer.id)
            # Should get 100 * 1.5 = 150 points
            assert customer.loyalty_points == initial_points + 150

    def test_automatic_tier_upgrade_on_purchase(
        self,
        loyalty_customer,
        loyalty_branch,
        loyalty_terminal,
        loyalty_user,
        loyalty_tenant,
        bronze_tier,
        silver_tier,
    ):
        """Test that customer is automatically upgraded to higher tier after purchase."""
        # Customer starts with bronze tier
        assert loyalty_customer.loyalty_tier == bronze_tier

        # Create a large sale that qualifies customer for silver tier
        with bypass_rls():
            sale = Sale.objects.create(  # noqa: F841
                tenant=loyalty_tenant,
                sale_number="SALE-TEST-005",
                customer=loyalty_customer,
                branch=loyalty_branch,
                terminal=loyalty_terminal,
                employee=loyalty_user,
                subtotal=Decimal("500.00"),
                tax=Decimal("50.00"),
                discount=Decimal("0.00"),
                total=Decimal("550.00"),
                payment_method=Sale.CASH,
                status=Sale.COMPLETED,
                completed_at=timezone.now(),
            )

        # Verify customer was upgraded to silver tier
        with bypass_rls():
            customer = Customer.objects.get(id=loyalty_customer.id)
            assert customer.loyalty_tier == silver_tier
            assert customer.total_purchases == Decimal("550.00")
            assert customer.tier_achieved_at is not None

    def test_no_duplicate_points_on_multiple_saves(
        self,
        loyalty_customer,
        loyalty_branch,
        loyalty_terminal,
        loyalty_user,
        loyalty_tenant,
    ):
        """Test that points are not awarded multiple times for the same sale."""
        initial_points = loyalty_customer.loyalty_points

        # Create a completed sale
        with bypass_rls():
            sale = Sale.objects.create(
                tenant=loyalty_tenant,
                sale_number="SALE-TEST-006",
                customer=loyalty_customer,
                branch=loyalty_branch,
                terminal=loyalty_terminal,
                employee=loyalty_user,
                subtotal=Decimal("100.00"),
                tax=Decimal("10.00"),
                discount=Decimal("0.00"),
                total=Decimal("110.00"),
                payment_method=Sale.CASH,
                status=Sale.COMPLETED,
                completed_at=timezone.now(),
            )

            # Save the sale again (simulating an update)
            sale.notes = "Updated notes"
            sale.save()

        # Verify points were only awarded once
        with bypass_rls():
            customer = Customer.objects.get(id=loyalty_customer.id)
            assert customer.loyalty_points == initial_points + 110

            # Verify only one loyalty transaction was created
            transaction_count = LoyaltyTransaction.objects.filter(
                customer=customer, sale=sale, transaction_type=LoyaltyTransaction.EARNED
            ).count()
            assert transaction_count == 1

    def test_customer_total_purchases_updated(
        self,
        loyalty_customer,
        loyalty_branch,
        loyalty_terminal,
        loyalty_user,
        loyalty_tenant,
    ):
        """Test that customer's total purchases is updated on sale."""
        initial_total = loyalty_customer.total_purchases

        # Create a completed sale
        with bypass_rls():
            sale = Sale.objects.create(  # noqa: F841
                tenant=loyalty_tenant,
                sale_number="SALE-TEST-007",
                customer=loyalty_customer,
                branch=loyalty_branch,
                terminal=loyalty_terminal,
                employee=loyalty_user,
                subtotal=Decimal("200.00"),
                tax=Decimal("20.00"),
                discount=Decimal("10.00"),
                total=Decimal("210.00"),
                payment_method=Sale.CASH,
                status=Sale.COMPLETED,
                completed_at=timezone.now(),
            )

        # Verify total purchases was updated
        with bypass_rls():
            customer = Customer.objects.get(id=loyalty_customer.id)
            assert customer.total_purchases == initial_total + Decimal("210.00")
            assert customer.last_purchase_at is not None

    def test_tier_upgrade_through_multiple_purchases(
        self,
        loyalty_customer,
        loyalty_branch,
        loyalty_terminal,
        loyalty_user,
        loyalty_tenant,
        bronze_tier,
        silver_tier,
        gold_tier,
    ):
        """Test tier upgrade through multiple purchases."""
        # Customer starts with bronze tier
        assert loyalty_customer.loyalty_tier == bronze_tier

        # First purchase - still bronze
        with bypass_rls():
            Sale.objects.create(
                tenant=loyalty_tenant,
                sale_number="SALE-TEST-008",
                customer=loyalty_customer,
                branch=loyalty_branch,
                terminal=loyalty_terminal,
                employee=loyalty_user,
                subtotal=Decimal("200.00"),
                tax=Decimal("20.00"),
                total=Decimal("220.00"),
                payment_method=Sale.CASH,
                status=Sale.COMPLETED,
                completed_at=timezone.now(),
            )

            customer = Customer.objects.get(id=loyalty_customer.id)
            assert customer.loyalty_tier == bronze_tier

        # Second purchase - upgrade to silver
        with bypass_rls():
            Sale.objects.create(
                tenant=loyalty_tenant,
                sale_number="SALE-TEST-009",
                customer=loyalty_customer,
                branch=loyalty_branch,
                terminal=loyalty_terminal,
                employee=loyalty_user,
                subtotal=Decimal("300.00"),
                tax=Decimal("30.00"),
                total=Decimal("330.00"),
                payment_method=Sale.CASH,
                status=Sale.COMPLETED,
                completed_at=timezone.now(),
            )

            customer = Customer.objects.get(id=loyalty_customer.id)
            assert customer.loyalty_tier == silver_tier
            assert customer.total_purchases == Decimal("550.00")

        # Third purchase - upgrade to gold
        with bypass_rls():
            Sale.objects.create(
                tenant=loyalty_tenant,
                sale_number="SALE-TEST-010",
                customer=loyalty_customer,
                branch=loyalty_branch,
                terminal=loyalty_terminal,
                employee=loyalty_user,
                subtotal=Decimal("500.00"),
                tax=Decimal("50.00"),
                total=Decimal("550.00"),
                payment_method=Sale.CASH,
                status=Sale.COMPLETED,
                completed_at=timezone.now(),
            )

            customer = Customer.objects.get(id=loyalty_customer.id)
            assert customer.loyalty_tier == gold_tier
            assert customer.total_purchases == Decimal("1100.00")
