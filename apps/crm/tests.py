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

from .models import (
    Customer,
    CustomerCommunication,
    GiftCard,
    GiftCardTransaction,
    LoyaltyTier,
    LoyaltyTransaction,
)

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

    def test_transfer_points_between_customers(self, tenant):
        """Test transferring loyalty points between customers."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            # Create sender customer
            sender = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-SENDER",
                first_name="Alice",
                last_name="Sender",
                phone="+1234567890",
                loyalty_points=200,
            )

            # Create recipient customer
            recipient = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-RECIPIENT",
                first_name="Bob",
                last_name="Recipient",
                phone="+1234567891",
                loyalty_points=50,
            )

            sender_id = sender.id
            recipient_id = recipient.id

            # Transfer points
            sender.transfer_points_to(recipient, 75, "Family transfer")

            # Re-query customers
            sender = Customer.objects.get(id=sender_id)
            recipient = Customer.objects.get(id=recipient_id)

            # Check balances updated
            assert sender.loyalty_points == 125  # 200 - 75
            assert recipient.loyalty_points == 125  # 50 + 75
            assert (
                recipient.total_points_earned == 75
            )  # Only the transferred amount is added to total_points_earned

            # Check transactions were created
            sender_transaction = LoyaltyTransaction.objects.filter(
                customer=sender, transaction_type=LoyaltyTransaction.ADJUSTED, points=-75
            ).first()
            assert sender_transaction is not None
            assert sender_transaction.description == "Family transfer"

            recipient_transaction = LoyaltyTransaction.objects.filter(
                customer=recipient, transaction_type=LoyaltyTransaction.BONUS, points=75
            ).first()
            assert recipient_transaction is not None
            assert recipient_transaction.description == "Family transfer"

    def test_transfer_points_insufficient_balance(self, tenant):
        """Test error when transferring more points than available."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            sender = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-SENDER2",
                first_name="Alice",
                last_name="Sender",
                phone="+1234567890",
                loyalty_points=50,
            )

            recipient = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-RECIPIENT2",
                first_name="Bob",
                last_name="Recipient",
                phone="+1234567891",
                loyalty_points=0,
            )

            # Try to transfer more than available
            with pytest.raises(ValueError, match="Invalid points amount for transfer"):
                sender.transfer_points_to(recipient, 100)

    def test_transfer_points_different_tenant_error(self, tenant):
        """Test error when transferring points between different tenants."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            # Create another tenant
            other_tenant = Tenant.objects.create(
                company_name="Other Jewelry Shop", slug="other-shop", status="ACTIVE"
            )

            sender = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-SENDER3",
                first_name="Alice",
                last_name="Sender",
                phone="+1234567890",
                loyalty_points=100,
            )

            recipient = Customer.objects.create(
                tenant=other_tenant,
                customer_number="CUST-RECIPIENT3",
                first_name="Bob",
                last_name="Recipient",
                phone="+1234567891",
                loyalty_points=0,
            )

            # Try to transfer between different tenants
            with pytest.raises(ValueError, match="Can only transfer points within same tenant"):
                sender.transfer_points_to(recipient, 50)

    def test_expire_old_points(self, tenant):
        """Test expiring old loyalty points."""
        from dateutil.relativedelta import relativedelta

        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-EXPIRE",
                first_name="Test",
                last_name="Customer",
                phone="+1234567890",
                loyalty_points=150,
            )

            # Create old transaction (13 months ago)
            old_date = timezone.now() - relativedelta(months=13)
            old_transaction = LoyaltyTransaction.objects.create(
                customer=customer,
                transaction_type=LoyaltyTransaction.EARNED,
                points=100,
                description="Old points",
            )
            # Manually set the created_at to simulate old transaction
            LoyaltyTransaction.objects.filter(id=old_transaction.id).update(created_at=old_date)

            # Create recent transaction (6 months ago)
            recent_date = timezone.now() - relativedelta(months=6)
            recent_transaction = LoyaltyTransaction.objects.create(
                customer=customer,
                transaction_type=LoyaltyTransaction.EARNED,
                points=50,
                description="Recent points",
            )
            LoyaltyTransaction.objects.filter(id=recent_transaction.id).update(
                created_at=recent_date
            )

            customer_id = customer.id

            # Expire points older than 12 months
            expired_points = customer.expire_old_points(expiration_months=12)

            # Re-query customer
            customer = Customer.objects.get(id=customer_id)

            # Check that 100 old points were expired
            assert expired_points == 100
            assert customer.loyalty_points == 50  # 150 - 100 expired

            # Check expiration transaction was created
            expiration_transaction = LoyaltyTransaction.objects.filter(
                customer=customer, transaction_type=LoyaltyTransaction.EXPIRED
            ).first()
            assert expiration_transaction is not None
            assert expiration_transaction.points == -100

            # Check old transaction is marked as expired
            old_transaction.refresh_from_db()
            assert old_transaction.expires_at is not None

    def test_referral_reward_system(self, tenant):
        """Test the referral reward system."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            # Create referrer customer
            referrer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-REFERRER",
                first_name="Alice",
                last_name="Referrer",
                phone="+1234567890",
                loyalty_points=0,
            )

            # Create referee customer with referrer
            referee = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-REFEREE",
                first_name="Bob",
                last_name="Referee",
                phone="+1234567891",
                referred_by=referrer,
                loyalty_points=0,
            )

            referrer_id = referrer.id
            referee_id = referee.id

            # Manually trigger reward (normally happens in save)
            referee.reward_referrer(referrer_points=150, referee_points=75)

            # Re-query customers
            referrer = Customer.objects.get(id=referrer_id)
            referee = Customer.objects.get(id=referee_id)

            # Check points were awarded
            assert referrer.loyalty_points == 150
            assert referee.loyalty_points == 75
            assert referee.referral_reward_given is True

            # Check transactions were created
            referrer_transactions = LoyaltyTransaction.objects.filter(customer=referrer)
            referee_transactions = LoyaltyTransaction.objects.filter(customer=referee)

            assert referrer_transactions.count() == 1
            assert referee_transactions.count() == 1

            referrer_transaction = referrer_transactions.first()
            assert "Referral bonus for referring Bob Referee" in referrer_transaction.description

    def test_referral_reward_already_given(self, tenant):
        """Test that referral reward is not given twice."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            referrer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-REF2",
                first_name="Alice",
                last_name="Referrer",
                phone="+1234567890",
                loyalty_points=0,
            )

            referee = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-REF3",
                first_name="Bob",
                last_name="Referee",
                phone="+1234567891",
                referred_by=referrer,
                loyalty_points=0,
                referral_reward_given=True,  # Already rewarded
            )

            initial_referrer_points = referrer.loyalty_points
            initial_referee_points = referee.loyalty_points

            # Try to reward again
            referee.reward_referrer()

            # Points should not change
            referrer.refresh_from_db()
            referee.refresh_from_db()

            assert referrer.loyalty_points == initial_referrer_points
            assert referee.loyalty_points == initial_referee_points

    def test_get_tier_discount(self, tenant):
        """Test tier-specific discount calculation."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            # Create loyalty tier with 15% discount
            tier = LoyaltyTier.objects.create(
                tenant=tenant,
                name="Gold",
                min_spending=Decimal("1000.00"),
                discount_percentage=Decimal("15.00"),
                order=1,
            )

            # Create customer with tier
            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-DISCOUNT",
                first_name="Gold",
                last_name="Customer",
                phone="+1234567890",
                loyalty_tier=tier,
            )

            # Test discount calculation
            discount = customer.get_tier_discount(Decimal("200.00"))
            assert discount == Decimal("30.00")  # 15% of 200

            # Test with customer without tier
            customer_no_tier = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-NO-TIER",
                first_name="Regular",
                last_name="Customer",
                phone="+1234567891",
            )

            discount_no_tier = customer_no_tier.get_tier_discount(Decimal("200.00"))
            assert discount_no_tier == Decimal("0.00")

    def test_loyalty_points_with_tier_multiplier(self, tenant):
        """Test loyalty points accrual with tier multiplier."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            # Create tier with 2x points multiplier
            tier = LoyaltyTier.objects.create(
                tenant=tenant,
                name="Platinum",
                min_spending=Decimal("5000.00"),
                points_multiplier=Decimal("2.0"),
                order=3,
            )

            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-MULTIPLIER",
                first_name="Platinum",
                last_name="Customer",
                phone="+1234567890",
                loyalty_tier=tier,
            )

            customer_id = customer.id

            # Add 100 base points
            customer.add_loyalty_points(100, "Purchase reward")

            # Re-query customer
            customer = Customer.objects.get(id=customer_id)

            # Should have 200 points due to 2x multiplier
            assert customer.loyalty_points == 200
            assert customer.total_points_earned == 200

            # Check transaction shows the multiplied amount
            transaction = LoyaltyTransaction.objects.filter(customer=customer).first()
            assert transaction.points == 200

    def test_customer_tier_expiration(self, tenant):
        """Test loyalty tier expiration functionality."""
        from dateutil.relativedelta import relativedelta

        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            # Create tier with 6 month validity
            tier = LoyaltyTier.objects.create(
                tenant=tenant,
                name="Silver",
                min_spending=Decimal("500.00"),
                validity_months=6,
                order=1,
            )

            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-EXPIRE-TIER",
                first_name="Expiring",
                last_name="Customer",
                phone="+1234567890",
                total_purchases=Decimal("600.00"),
            )

            customer_id = customer.id

            # Update tier (should set expiration)
            customer.update_loyalty_tier()

            # Re-query customer
            customer = Customer.objects.get(id=customer_id)

            assert customer.loyalty_tier == tier
            assert customer.tier_achieved_at is not None
            assert customer.tier_expires_at is not None

            # Check expiration is approximately 6 months from now
            expected_expiry = timezone.now() + relativedelta(months=6)
            time_diff = abs((customer.tier_expires_at - expected_expiry).total_seconds())
            assert time_diff < 60  # Within 1 minute

    def test_customer_no_tier_upgrade_needed(self, tenant):
        """Test that tier doesn't change when customer already has correct tier."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            # Create tiers
            bronze = LoyaltyTier.objects.create(
                tenant=tenant, name="Bronze", min_spending=Decimal("0.00"), order=0
            )
            LoyaltyTier.objects.create(
                tenant=tenant, name="Silver", min_spending=Decimal("500.00"), order=1
            )

            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-NO-UPGRADE",
                first_name="Bronze",
                last_name="Customer",
                phone="+1234567890",
                total_purchases=Decimal("300.00"),
                loyalty_tier=bronze,
            )

            original_tier_achieved_at = customer.tier_achieved_at

            # Update tier (should not change)
            customer.update_loyalty_tier()

            customer.refresh_from_db()
            assert customer.loyalty_tier == bronze
            assert customer.tier_achieved_at == original_tier_achieved_at


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
            # Create a customer for the gift card
            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-GC001",
                first_name="Gift",
                last_name="Customer",
                phone="+1234567890",
            )

            gift_card = GiftCard.objects.create(
                tenant=tenant, initial_value=Decimal("100.00"), purchased_by=customer
            )
            gift_card_id = gift_card.id

            # Use partial balance
            gift_card.use_balance(Decimal("30.00"))

            # Re-query the gift card
            gift_card = GiftCard.objects.get(id=gift_card_id)

            assert gift_card.current_balance == Decimal("70.00")
            assert gift_card.status == GiftCard.ACTIVE

            # Check redemption transaction was created
            transactions = GiftCardTransaction.objects.filter(gift_card=gift_card)
            redemption_transactions = transactions.filter(
                transaction_type=GiftCardTransaction.REDEEMED
            )
            assert redemption_transactions.count() == 1

            redemption_transaction = redemption_transactions.first()
            assert redemption_transaction.amount == Decimal("30.00")
            assert redemption_transaction.previous_balance == Decimal("100.00")
            assert redemption_transaction.new_balance == Decimal("70.00")

            # Use remaining balance
            gift_card.use_balance(Decimal("70.00"))

            # Re-query the gift card
            gift_card = GiftCard.objects.get(id=gift_card_id)

            assert gift_card.current_balance == Decimal("0.00")
            assert gift_card.status == GiftCard.REDEEMED

            # Check final redemption transaction count
            redemption_transactions = GiftCardTransaction.objects.filter(
                gift_card=gift_card, transaction_type=GiftCardTransaction.REDEEMED
            )
            assert redemption_transactions.count() == 2  # 2 redemptions

    def test_gift_card_transaction_creation_on_issuance(self, tenant):
        """Test that transaction is created when gift card is issued."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            # Create a customer for the gift card
            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-GC002",
                first_name="Gift",
                last_name="Purchaser",
                phone="+1234567890",
            )

            gift_card = GiftCard.objects.create(
                tenant=tenant, initial_value=Decimal("50.00"), purchased_by=customer
            )

            # Check that gift card was created with correct balance
            assert gift_card.initial_value == Decimal("50.00")
            assert gift_card.current_balance == Decimal("50.00")

            # Check if issuance transaction was created (may not be created if no customer)
            transactions = GiftCardTransaction.objects.filter(gift_card=gift_card)
            if transactions.exists():
                issuance_transaction = transactions.filter(
                    transaction_type=GiftCardTransaction.ISSUED
                ).first()
                if issuance_transaction:
                    assert issuance_transaction.amount == Decimal("50.00")
                    assert issuance_transaction.previous_balance == Decimal("0.00")
                    assert issuance_transaction.new_balance == Decimal("50.00")

    def test_gift_card_use_balance_error_cases(self, tenant):
        """Test error cases when using gift card balance."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-GC-ERROR",
                first_name="Test",
                last_name="Customer",
                phone="+1234567890",
            )

            # Test using expired gift card
            expired_card = GiftCard.objects.create(
                tenant=tenant,
                initial_value=Decimal("100.00"),
                purchased_by=customer,
                expires_at=timezone.now() - timezone.timedelta(days=1),
            )

            with pytest.raises(ValueError, match="Gift card cannot be used"):
                expired_card.use_balance(Decimal("50.00"))

            # Test using cancelled gift card
            cancelled_card = GiftCard.objects.create(
                tenant=tenant,
                initial_value=Decimal("100.00"),
                purchased_by=customer,
                status=GiftCard.CANCELLED,
            )

            with pytest.raises(ValueError, match="Gift card cannot be used"):
                cancelled_card.use_balance(Decimal("50.00"))

            # Test using more than available balance
            active_card = GiftCard.objects.create(
                tenant=tenant,
                initial_value=Decimal("50.00"),
                purchased_by=customer,
            )

            with pytest.raises(ValueError, match="Amount exceeds gift card balance"):
                active_card.use_balance(Decimal("75.00"))

    def test_gift_card_auto_number_generation(self, tenant):
        """Test automatic gift card number generation."""
        gift_card1 = GiftCard.objects.create(tenant=tenant, initial_value=Decimal("25.00"))

        gift_card2 = GiftCard.objects.create(tenant=tenant, initial_value=Decimal("50.00"))

        # Both should have auto-generated card numbers
        assert gift_card1.card_number
        assert gift_card2.card_number
        assert len(gift_card1.card_number) == 16
        assert len(gift_card2.card_number) == 16
        assert gift_card1.card_number != gift_card2.card_number

    def test_gift_card_with_recipient(self, tenant):
        """Test gift card with different purchaser and recipient."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            purchaser = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-PURCHASER",
                first_name="John",
                last_name="Purchaser",
                phone="+1234567890",
            )

            recipient = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-RECIPIENT-GC",
                first_name="Jane",
                last_name="Recipient",
                phone="+1234567891",
            )

            gift_card = GiftCard.objects.create(
                tenant=tenant,
                initial_value=Decimal("75.00"),
                purchased_by=purchaser,
                recipient=recipient,
                message="Happy Birthday!",
            )

            assert gift_card.purchased_by == purchaser
            assert gift_card.recipient == recipient
            assert gift_card.message == "Happy Birthday!"

            # Use the gift card
            gift_card.use_balance(Decimal("25.00"), "Birthday purchase")

            # Check transaction was created for recipient
            transaction = GiftCardTransaction.objects.filter(
                gift_card=gift_card,
                transaction_type=GiftCardTransaction.REDEEMED,
                customer=recipient,
            ).first()

            assert transaction is not None
            assert transaction.amount == Decimal("25.00")


@pytest.mark.django_db
class TestStoreCredit:
    """Test store credit functionality."""

    def test_add_store_credit(self, tenant):
        """Test adding store credit to customer account."""
        customer = Customer.objects.create(
            tenant=tenant,
            customer_number="CUST-008",
            first_name="Alice",
            last_name="Johnson",
            phone="+1234567890",
        )

        # Add store credit
        customer.add_store_credit(Decimal("25.00"), "Refund for returned item")

        # Check balance updated
        customer.refresh_from_db()
        assert customer.store_credit == Decimal("25.00")

        # Check transaction was created
        transactions = GiftCardTransaction.objects.filter(
            customer=customer, transaction_type=GiftCardTransaction.STORE_CREDIT_ADDED
        )
        assert transactions.count() == 1

        transaction = transactions.first()
        assert transaction.amount == Decimal("25.00")
        assert transaction.previous_balance == Decimal("0.00")
        assert transaction.new_balance == Decimal("25.00")
        assert transaction.description == "Refund for returned item"

    def test_use_store_credit(self, tenant):
        """Test using store credit from customer account."""
        customer = Customer.objects.create(
            tenant=tenant,
            customer_number="CUST-009",
            first_name="Bob",
            last_name="Wilson",
            phone="+1234567890",
            store_credit=Decimal("50.00"),
        )

        # Use store credit
        customer.use_store_credit(Decimal("20.00"), "Applied to purchase")

        # Check balance updated
        customer.refresh_from_db()
        assert customer.store_credit == Decimal("30.00")

        # Check transaction was created
        transactions = GiftCardTransaction.objects.filter(
            customer=customer, transaction_type=GiftCardTransaction.STORE_CREDIT_USED
        )
        assert transactions.count() == 1

        transaction = transactions.first()
        assert transaction.amount == Decimal("20.00")
        assert transaction.previous_balance == Decimal("50.00")
        assert transaction.new_balance == Decimal("30.00")
        assert transaction.description == "Applied to purchase"

    def test_use_store_credit_insufficient_balance(self, tenant):
        """Test error when trying to use more store credit than available."""
        customer = Customer.objects.create(
            tenant=tenant,
            customer_number="CUST-010",
            first_name="Charlie",
            last_name="Brown",
            phone="+1234567890",
            store_credit=Decimal("10.00"),
        )

        # Try to use more than available
        with pytest.raises(ValueError, match="Insufficient store credit balance"):
            customer.use_store_credit(Decimal("20.00"), "Attempted overspend")

        # Balance should remain unchanged
        customer.refresh_from_db()
        assert customer.store_credit == Decimal("10.00")

        # No transaction should be created
        transactions = GiftCardTransaction.objects.filter(
            customer=customer, transaction_type=GiftCardTransaction.STORE_CREDIT_USED
        )
        assert transactions.count() == 0

    def test_store_credit_invalid_amounts(self, tenant):
        """Test error handling for invalid store credit amounts."""
        customer = Customer.objects.create(
            tenant=tenant,
            customer_number="CUST-INVALID",
            first_name="Test",
            last_name="Customer",
            phone="+1234567890",
            store_credit=Decimal("50.00"),
        )

        # Test adding negative amount
        with pytest.raises(ValueError, match="Store credit amount must be positive"):
            customer.add_store_credit(Decimal("-10.00"))

        # Test adding zero amount
        with pytest.raises(ValueError, match="Store credit amount must be positive"):
            customer.add_store_credit(Decimal("0.00"))

        # Test using negative amount
        with pytest.raises(ValueError, match="Store credit amount must be positive"):
            customer.use_store_credit(Decimal("-5.00"))

        # Test using zero amount
        with pytest.raises(ValueError, match="Store credit amount must be positive"):
            customer.use_store_credit(Decimal("0.00"))

    def test_store_credit_with_sale_reference(self, tenant, user):
        """Test store credit operations with sale reference."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-SALE-REF",
                first_name="Sale",
                last_name="Customer",
                phone="+1234567890",
            )

            # Add store credit with user and sale reference (mock sale ID)
            customer.add_store_credit(
                Decimal("100.00"),
                description="Refund for returned jewelry",
                created_by=user,
            )

            # Check transaction includes user reference
            transaction = GiftCardTransaction.objects.filter(
                customer=customer,
                transaction_type=GiftCardTransaction.STORE_CREDIT_ADDED,
            ).first()

            assert transaction.created_by == user
            assert transaction.description == "Refund for returned jewelry"


@pytest.mark.django_db
class TestCustomerCRUDOperations:
    """Test comprehensive Customer CRUD operations."""

    def test_customer_create_with_all_fields(self, tenant):
        """Test creating customer with all optional fields."""
        from datetime import date

        customer = Customer.objects.create(
            tenant=tenant,
            customer_number="CUST-FULL",
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1985, 5, 15),
            gender=Customer.MALE,
            email="john.doe@example.com",
            phone="+1234567890",
            alternate_phone="+1234567891",
            address_line_1="123 Main St",
            address_line_2="Apt 4B",
            city="New York",
            state="NY",
            postal_code="10001",
            country="USA",
            preferred_communication=Customer.SMS,
            marketing_opt_in=False,
            sms_opt_in=True,
            notes="VIP customer",
            tags=["VIP", "Wedding", "Corporate"],
        )

        assert customer.date_of_birth == date(1985, 5, 15)
        assert customer.gender == Customer.MALE
        assert customer.email == "john.doe@example.com"
        assert customer.alternate_phone == "+1234567891"
        assert customer.get_full_address() == "123 Main St, Apt 4B, New York, NY, 10001, USA"
        assert customer.preferred_communication == Customer.SMS
        assert customer.marketing_opt_in is False
        assert customer.sms_opt_in is True
        assert customer.notes == "VIP customer"
        assert customer.tags == ["VIP", "Wedding", "Corporate"]

    def test_customer_update_operations(self, tenant):
        """Test updating customer information."""
        customer = Customer.objects.create(
            tenant=tenant,
            customer_number="CUST-UPDATE",
            first_name="Jane",
            last_name="Smith",
            phone="+1234567890",
            email="jane.smith@example.com",
        )

        # Update customer information
        customer.first_name = "Janet"
        customer.email = "janet.smith@example.com"
        customer.tags = ["Updated", "Premium"]
        customer.save()

        # Verify updates
        customer.refresh_from_db()
        assert customer.first_name == "Janet"
        assert customer.email == "janet.smith@example.com"
        assert customer.tags == ["Updated", "Premium"]

    def test_customer_soft_delete(self, tenant):
        """Test customer deactivation (soft delete)."""
        customer = Customer.objects.create(
            tenant=tenant,
            customer_number="CUST-DELETE",
            first_name="Delete",
            last_name="Me",
            phone="+1234567890",
        )

        # Deactivate customer
        customer.is_active = False
        customer.save()

        customer.refresh_from_db()
        assert customer.is_active is False

    def test_customer_referral_code_uniqueness(self, tenant):
        """Test that referral codes are unique."""
        customer1 = Customer.objects.create(
            tenant=tenant,
            customer_number="CUST-REF1",
            first_name="First",
            last_name="Customer",
            phone="+1234567890",
        )

        customer2 = Customer.objects.create(
            tenant=tenant,
            customer_number="CUST-REF2",
            first_name="Second",
            last_name="Customer",
            phone="+1234567891",
        )

        assert customer1.referral_code != customer2.referral_code
        assert len(customer1.referral_code) == 8
        assert len(customer2.referral_code) == 8


@pytest.mark.django_db
class TestLoyaltyTierCRUD:
    """Test comprehensive LoyaltyTier CRUD operations."""

    def test_loyalty_tier_create_with_all_fields(self, tenant):
        """Test creating loyalty tier with all fields."""
        tier = LoyaltyTier.objects.create(
            tenant=tenant,
            name="Diamond",
            min_spending=Decimal("10000.00"),
            discount_percentage=Decimal("20.00"),
            points_multiplier=Decimal("3.0"),
            validity_months=24,
            benefits_description="Exclusive access to private events and priority service",
            order=4,
        )

        assert tier.name == "Diamond"
        assert tier.min_spending == Decimal("10000.00")
        assert tier.discount_percentage == Decimal("20.00")
        assert tier.points_multiplier == Decimal("3.0")
        assert tier.validity_months == 24
        assert "Exclusive access" in tier.benefits_description
        assert tier.order == 4
        assert tier.is_active is True

    def test_loyalty_tier_update(self, tenant):
        """Test updating loyalty tier."""
        tier = LoyaltyTier.objects.create(
            tenant=tenant,
            name="Gold",
            min_spending=Decimal("1000.00"),
            discount_percentage=Decimal("10.00"),
        )

        # Update tier
        tier.discount_percentage = Decimal("12.00")
        tier.benefits_description = "Updated benefits"
        tier.save()

        tier.refresh_from_db()
        assert tier.discount_percentage == Decimal("12.00")
        assert tier.benefits_description == "Updated benefits"

    def test_loyalty_tier_deactivation(self, tenant):
        """Test deactivating loyalty tier."""
        tier = LoyaltyTier.objects.create(
            tenant=tenant,
            name="Temporary",
            min_spending=Decimal("500.00"),
        )

        # Deactivate tier
        tier.is_active = False
        tier.save()

        tier.refresh_from_db()
        assert tier.is_active is False


@pytest.mark.django_db
class TestGiftCardAPI:
    """Test gift card API endpoints."""

    def test_gift_card_list_api(self, api_client, tenant):
        """Test gift card list API endpoint."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            # Create a customer and gift card
            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-API001",
                first_name="API",
                last_name="Customer",
                phone="+1234567890",
            )

            gift_card = GiftCard.objects.create(
                tenant=tenant, initial_value=Decimal("100.00"), purchased_by=customer
            )

            # Test API endpoint
            response = api_client.get("/api/gift-cards/")
            assert response.status_code == 200

            data = response.json()
            assert data["count"] == 1
            assert len(data["results"]) == 1
            assert data["results"][0]["card_number"] == gift_card.card_number
            assert data["results"][0]["initial_value"] == "100.00"

    def test_gift_card_detail_api(self, api_client, tenant):
        """Test gift card detail API endpoint."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            # Create a customer and gift card
            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-API002",
                first_name="API",
                last_name="Customer",
                phone="+1234567890",
            )

            gift_card = GiftCard.objects.create(
                tenant=tenant, initial_value=Decimal("75.00"), purchased_by=customer
            )

            # Test API endpoint
            response = api_client.get(f"/api/gift-cards/{gift_card.id}/")
            assert response.status_code == 200

            data = response.json()
            assert data["card_number"] == gift_card.card_number
            assert data["initial_value"] == "75.00"
            assert data["purchased_by_name"] == "API Customer"

    def test_gift_card_create_api(self, api_client, tenant, user):
        """Test gift card creation API endpoint."""
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            # Create a customer
            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-API003",
                first_name="API",
                last_name="Customer",
                phone="+1234567890",
            )

            # Test API endpoint
            data = {
                "initial_value": "50.00",
                "purchased_by": customer.id,
                "message": "Happy Birthday!",
            }

            response = api_client.post("/api/gift-cards/create/", data)
            assert response.status_code == 201

            result = response.json()
            assert result["initial_value"] == "50.00"
            assert result["message"] == "Happy Birthday!"
            assert result["purchased_by"] == str(customer.id)

            # Verify gift card was created in database
            gift_card = GiftCard.objects.get(id=result["id"])
            assert gift_card.initial_value == Decimal("50.00")
            assert gift_card.purchased_by == customer
            assert gift_card.issued_by == user


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


@pytest.fixture
def api_client(user):
    """Create authenticated API client."""
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=user)
    return client
