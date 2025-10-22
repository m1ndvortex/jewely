"""
Tests for CRM models.

Tests the customer relationship management functionality including:
- Customer model with loyalty program integration
- Loyalty tier management and automatic upgrades
- Loyalty transaction tracking
- Gift card issuance and redemption
- Customer communication logging
- Row-Level Security (RLS) tenant isolation
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from apps.core.models import Tenant

from .models import Customer, CustomerCommunication, GiftCard, LoyaltyTier, LoyaltyTransaction

User = get_user_model()


@pytest.mark.django_db
class TestLoyaltyTier:
    """Test LoyaltyTier model functionality."""

    def test_create_loyalty_tier(self, tenant):
        """Test creating a loyalty tier."""
        tier = LoyaltyTier.objects.create(
            tenant=tenant,
            name="Gold",
            min_spending=Decimal("1000.00"),
            discount_percentage=Decimal("10.00"),
            points_multiplier=Decimal("1.5"),
            validity_months=12,
            order=2,
        )

        assert tier.name == "Gold"
        assert tier.min_spending == Decimal("1000.00")
        assert tier.discount_percentage == Decimal("10.00")
        assert tier.points_multiplier == Decimal("1.5")
        assert tier.validity_months == 12
        assert tier.is_active is True
        assert str(tier) == "Gold ($1000.00+)"

    def test_loyalty_tier_ordering(self, tenant):
        """Test loyalty tier ordering."""
        bronze = LoyaltyTier.objects.create(
            tenant=tenant, name="Bronze", min_spending=Decimal("0.00"), order=0
        )
        gold = LoyaltyTier.objects.create(
            tenant=tenant, name="Gold", min_spending=Decimal("1000.00"), order=2
        )
        silver = LoyaltyTier.objects.create(
            tenant=tenant, name="Silver", min_spending=Decimal("500.00"), order=1
        )

        tiers = list(LoyaltyTier.objects.all())
        assert tiers[0] == bronze
        assert tiers[1] == silver
        assert tiers[2] == gold


@pytest.mark.django_db
class TestCustomer:
    """Test Customer model functionality."""

    def test_create_customer(self, tenant):
        """Test creating a customer."""
        customer = Customer.objects.create(
            tenant=tenant,
            customer_number="CUST-001",
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            phone="+1234567890",
        )

        assert customer.customer_number == "CUST-001"
        assert customer.get_full_name() == "John Doe"
        assert customer.email == "john.doe@example.com"
        assert customer.phone == "+1234567890"
        assert customer.loyalty_points == 0
        assert customer.store_credit == Decimal("0.00")
        assert customer.total_purchases == Decimal("0.00")
        assert customer.is_active is True
        assert customer.referral_code  # Should be auto-generated

    def test_customer_full_address(self, tenant):
        """Test customer full address formatting."""
        customer = Customer.objects.create(
            tenant=tenant,
            customer_number="CUST-002",
            first_name="Jane",
            last_name="Smith",
            phone="+1234567890",
            address_line_1="123 Main St",
            address_line_2="Apt 4B",
            city="New York",
            state="NY",
            postal_code="10001",
            country="USA",
        )

        expected_address = "123 Main St, Apt 4B, New York, NY, 10001, USA"
        assert customer.get_full_address() == expected_address

    def test_customer_loyalty_tier_upgrade(self, tenant):
        """Test automatic loyalty tier upgrade based on spending."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            # Create loyalty tiers
            LoyaltyTier.objects.create(
                tenant=tenant, name="Bronze", min_spending=Decimal("0.00"), order=0
            )
            silver = LoyaltyTier.objects.create(
                tenant=tenant, name="Silver", min_spending=Decimal("500.00"), order=1
            )
            LoyaltyTier.objects.create(
                tenant=tenant, name="Gold", min_spending=Decimal("1000.00"), order=2
            )

            # Create customer
            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-003",
                first_name="Alice",
                last_name="Johnson",
                phone="+1234567890",
                total_purchases=Decimal("750.00"),
            )
            customer_id = customer.id

            # Update loyalty tier
            customer.update_loyalty_tier()

            # Re-query the customer
            customer = Customer.objects.get(id=customer_id)

            assert customer.loyalty_tier == silver
            assert customer.tier_achieved_at is not None
            assert customer.tier_expires_at is not None

    def test_add_loyalty_points(self, tenant):
        """Test adding loyalty points to customer."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-004",
                first_name="Bob",
                last_name="Wilson",
                phone="+1234567890",
            )
            customer_id = customer.id

            # Add points
            customer.add_loyalty_points(100, "Purchase reward")

            # Re-query the customer
            customer = Customer.objects.get(id=customer_id)

            assert customer.loyalty_points == 100
            assert customer.total_points_earned == 100

            # Check transaction was created
            transaction = LoyaltyTransaction.objects.get(customer=customer)
            assert transaction.transaction_type == LoyaltyTransaction.EARNED
            assert transaction.points == 100
            assert transaction.description == "Purchase reward"

    def test_redeem_loyalty_points(self, tenant):
        """Test redeeming loyalty points."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-005",
                first_name="Carol",
                last_name="Brown",
                phone="+1234567890",
                loyalty_points=200,
            )
            customer_id = customer.id

            # Redeem points
            customer.redeem_loyalty_points(50, "Discount applied")

            # Re-query the customer
            customer = Customer.objects.get(id=customer_id)

            assert customer.loyalty_points == 150
            assert customer.total_points_redeemed == 50

            # Check transaction was created
            transaction = LoyaltyTransaction.objects.filter(
                customer=customer, transaction_type=LoyaltyTransaction.REDEEMED
            ).first()
            assert transaction is not None
            assert transaction.points == -50
            assert transaction.description == "Discount applied"

    def test_redeem_insufficient_points(self, tenant):
        """Test redeeming more points than available raises error."""
        customer = Customer.objects.create(
            tenant=tenant,
            customer_number="CUST-006",
            first_name="Dave",
            last_name="Miller",
            phone="+1234567890",
            loyalty_points=50,
        )

        with pytest.raises(ValueError, match="Invalid points amount for redemption"):
            customer.redeem_loyalty_points(100)


@pytest.mark.django_db
class TestGiftCard:
    """Test GiftCard model functionality."""

    def test_create_gift_card(self, tenant):
        """Test creating a gift card."""
        gift_card = GiftCard.objects.create(
            tenant=tenant, initial_value=Decimal("100.00"), message="Happy Birthday!"
        )

        assert gift_card.initial_value == Decimal("100.00")
        assert gift_card.current_balance == Decimal("100.00")
        assert gift_card.status == GiftCard.ACTIVE
        assert gift_card.message == "Happy Birthday!"
        assert gift_card.card_number  # Should be auto-generated
        assert len(gift_card.card_number) == 16

    def test_gift_card_can_be_used(self, tenant):
        """Test gift card usage validation."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            gift_card = GiftCard.objects.create(
                tenant=tenant,
                initial_value=Decimal("100.00"),
                current_balance=Decimal("50.00"),
                status=GiftCard.ACTIVE,
            )
            gift_card_id = gift_card.id

            assert gift_card.can_be_used() is True

            # Test expired card
            gift_card.expires_at = timezone.now() - timezone.timedelta(days=1)
            gift_card.save()
            gift_card = GiftCard.objects.get(id=gift_card_id)
            assert gift_card.can_be_used() is False

            # Test zero balance
            gift_card.expires_at = None
            gift_card.current_balance = Decimal("0.00")
            gift_card.save()
            gift_card = GiftCard.objects.get(id=gift_card_id)
            assert gift_card.can_be_used() is False

    def test_use_gift_card_balance(self, tenant):
        """Test using gift card balance."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            gift_card = GiftCard.objects.create(
                tenant=tenant, initial_value=Decimal("100.00"), current_balance=Decimal("100.00")
            )
            gift_card_id = gift_card.id

            # Use partial balance
            gift_card.use_balance(Decimal("30.00"))

            # Re-query the gift card
            gift_card = GiftCard.objects.get(id=gift_card_id)

            assert gift_card.current_balance == Decimal("70.00")
            assert gift_card.status == GiftCard.ACTIVE

            # Use remaining balance
            gift_card.use_balance(Decimal("70.00"))

            # Re-query the gift card
            gift_card = GiftCard.objects.get(id=gift_card_id)

            assert gift_card.current_balance == Decimal("0.00")
            assert gift_card.status == GiftCard.REDEEMED


@pytest.mark.django_db
class TestCustomerCommunication:
    """Test CustomerCommunication model functionality."""

    def test_create_communication(self, tenant, user):
        """Test creating a customer communication record."""
        customer = Customer.objects.create(
            tenant=tenant,
            customer_number="CUST-007",
            first_name="Eve",
            last_name="Davis",
            phone="+1234567890",
        )

        communication = CustomerCommunication.objects.create(
            customer=customer,
            communication_type=CustomerCommunication.EMAIL,
            direction=CustomerCommunication.OUTBOUND,
            subject="Welcome to our store",
            content="Thank you for joining our loyalty program!",
            created_by=user,
        )

        assert communication.customer == customer
        assert communication.communication_type == CustomerCommunication.EMAIL
        assert communication.direction == CustomerCommunication.OUTBOUND
        assert communication.subject == "Welcome to our store"
        assert communication.content == "Thank you for joining our loyalty program!"
        assert communication.created_by == user
        assert communication.communication_date is not None


# Fixtures for tests
@pytest.fixture
def tenant():
    """Create a test tenant."""
    from apps.core.tenant_context import bypass_rls

    with bypass_rls():
        return Tenant.objects.create(
            company_name="Test Jewelry Shop", slug="test-shop", status="ACTIVE"
        )


@pytest.fixture
def user(tenant):
    """Create a test user."""
    from apps.core.tenant_context import bypass_rls

    with bypass_rls():
        return User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=tenant,
            role="TENANT_OWNER",
        )
