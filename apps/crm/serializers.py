"""
Serializers for CRM functionality.

Implements Requirement 12: Customer Relationship Management (CRM)
"""

from rest_framework import serializers

from .models import Customer, CustomerCommunication, GiftCard, LoyaltyTier, LoyaltyTransaction


class LoyaltyTierSerializer(serializers.ModelSerializer):
    """Serializer for LoyaltyTier model."""

    class Meta:
        model = LoyaltyTier
        fields = [
            "id",
            "name",
            "min_spending",
            "discount_percentage",
            "points_multiplier",
            "validity_months",
            "benefits_description",
            "order",
        ]


class CustomerListSerializer(serializers.ModelSerializer):
    """Serializer for customer list view."""

    loyalty_tier_name = serializers.CharField(source="loyalty_tier.name", read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "id",
            "customer_number",
            "full_name",
            "first_name",
            "last_name",
            "email",
            "phone",
            "loyalty_tier",
            "loyalty_tier_name",
            "loyalty_points",
            "store_credit",
            "total_purchases",
            "last_purchase_at",
            "is_active",
            "created_at",
        ]

    def get_full_name(self, obj):
        """Get customer's full name."""
        return obj.get_full_name()


class CustomerSerializer(serializers.ModelSerializer):
    """Serializer for customer create/update."""

    class Meta:
        model = Customer
        fields = [
            "id",
            "customer_number",
            "first_name",
            "last_name",
            "date_of_birth",
            "gender",
            "email",
            "phone",
            "alternate_phone",
            "address_line_1",
            "address_line_2",
            "city",
            "state",
            "postal_code",
            "country",
            "loyalty_tier",
            "loyalty_points",
            "store_credit",
            "total_purchases",
            "preferred_communication",
            "marketing_opt_in",
            "sms_opt_in",
            "notes",
            "tags",
            "is_active",
        ]
        read_only_fields = [
            "id",
            "customer_number",
            "loyalty_points",
            "store_credit",
            "total_purchases",
        ]


class LoyaltyTransactionSerializer(serializers.ModelSerializer):
    """Serializer for loyalty transactions."""

    class Meta:
        model = LoyaltyTransaction
        fields = [
            "id",
            "transaction_type",
            "points",
            "description",
            "expires_at",
            "created_at",
        ]


class CustomerCommunicationSerializer(serializers.ModelSerializer):
    """Serializer for customer communications."""

    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, allow_null=True
    )

    class Meta:
        model = CustomerCommunication
        fields = [
            "id",
            "communication_type",
            "direction",
            "subject",
            "content",
            "duration_minutes",
            "communication_date",
            "created_at",
            "created_by",
            "created_by_name",
        ]
        read_only_fields = ["id", "created_at", "created_by", "created_by_name"]


class GiftCardSerializer(serializers.ModelSerializer):
    """Serializer for gift cards."""

    purchased_by_name = serializers.CharField(
        source="purchased_by.get_full_name", read_only=True, allow_null=True
    )
    recipient_name = serializers.CharField(
        source="recipient.get_full_name", read_only=True, allow_null=True
    )

    class Meta:
        model = GiftCard
        fields = [
            "id",
            "card_number",
            "initial_value",
            "current_balance",
            "status",
            "purchased_by",
            "purchased_by_name",
            "recipient",
            "recipient_name",
            "expires_at",
            "message",
            "created_at",
        ]


class CustomerDetailSerializer(serializers.ModelSerializer):
    """Serializer for customer detail view with related data."""

    loyalty_tier_name = serializers.CharField(source="loyalty_tier.name", read_only=True)
    loyalty_tier_details = LoyaltyTierSerializer(source="loyalty_tier", read_only=True)
    full_name = serializers.SerializerMethodField()
    full_address = serializers.SerializerMethodField()
    referred_by_name = serializers.CharField(
        source="referred_by.get_full_name", read_only=True, allow_null=True
    )
    recent_transactions = LoyaltyTransactionSerializer(
        source="loyalty_transactions", many=True, read_only=True
    )
    recent_communications = CustomerCommunicationSerializer(
        source="communications", many=True, read_only=True
    )

    class Meta:
        model = Customer
        fields = [
            "id",
            "customer_number",
            "full_name",
            "first_name",
            "last_name",
            "date_of_birth",
            "gender",
            "email",
            "phone",
            "alternate_phone",
            "full_address",
            "address_line_1",
            "address_line_2",
            "city",
            "state",
            "postal_code",
            "country",
            "loyalty_tier",
            "loyalty_tier_name",
            "loyalty_tier_details",
            "loyalty_points",
            "tier_achieved_at",
            "tier_expires_at",
            "total_points_earned",
            "total_points_redeemed",
            "store_credit",
            "total_purchases",
            "last_purchase_at",
            "preferred_communication",
            "marketing_opt_in",
            "sms_opt_in",
            "referral_code",
            "referred_by",
            "referred_by_name",
            "referral_reward_given",
            "notes",
            "tags",
            "is_active",
            "created_at",
            "updated_at",
            "recent_transactions",
            "recent_communications",
        ]

    def get_full_name(self, obj):
        """Get customer's full name."""
        return obj.get_full_name()

    def get_full_address(self, obj):
        """Get customer's full address."""
        return obj.get_full_address()
