"""
Serializers for authentication and user management.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.sales.models import Terminal

from .models import Branch, IntegrationSettings, InvoiceSettings, TenantSettings

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT token serializer that includes additional user information.
    Implements MFA verification in the login flow.
    """

    mfa_token = serializers.CharField(required=False, write_only=True)

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims
        token["username"] = user.username
        token["email"] = user.email
        token["role"] = user.role
        token["tenant_id"] = str(user.tenant_id) if user.tenant else None
        token["branch_id"] = str(user.branch_id) if user.branch else None
        token["language"] = user.language
        token["theme"] = user.theme

        return token

    def validate(self, attrs):
        # First, validate username and password
        data = super().validate(attrs)

        # Check if user has MFA enabled
        if self.user.is_mfa_enabled:
            mfa_token = attrs.get("mfa_token")

            # If no MFA token provided, return a response indicating MFA is required
            if not mfa_token:
                # Don't return actual tokens, return MFA required status
                return {
                    "mfa_required": True,
                    "user_id": str(self.user.id),
                    "message": "MFA verification required. Please provide your authentication code.",
                }

            # Verify the MFA token
            from django_otp.plugins.otp_totp.models import TOTPDevice

            try:
                device = TOTPDevice.objects.get(user=self.user, confirmed=True)
                if not device.verify_token(mfa_token):
                    raise serializers.ValidationError(
                        {"mfa_token": "Invalid MFA token. Please try again."}
                    )
            except TOTPDevice.DoesNotExist:
                raise serializers.ValidationError(
                    {"mfa_token": "MFA device not found. Please contact support."}
                )

        # Add user information to response
        data["user"] = {
            "id": str(self.user.id),
            "username": self.user.username,
            "email": self.user.email,
            "role": self.user.role,
            "tenant_id": str(self.user.tenant_id) if self.user.tenant else None,
            "branch_id": str(self.user.branch_id) if self.user.branch else None,
            "language": self.user.language,
            "theme": self.user.theme,
            "is_mfa_enabled": self.user.is_mfa_enabled,
        }
        data["mfa_required"] = False

        return data


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model.
    """

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "tenant",
            "branch",
            "language",
            "theme",
            "phone",
            "is_mfa_enabled",
            "is_active",
            "date_joined",
            "last_login",
        ]
        read_only_fields = ["id", "date_joined", "last_login"]


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.
    """

    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "password2",
            "first_name",
            "last_name",
            "phone",
            "language",
            "theme",
        ]

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        user = User.objects.create_user(**validated_data)
        return user


class PasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for password change.
    """

    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(
        required=True, write_only=True, validators=[validate_password]
    )
    new_password2 = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password2"]:
            raise serializers.ValidationError({"new_password": "Password fields didn't match."})
        return attrs

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def save(self):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user


class UserPreferencesSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user preferences.
    """

    class Meta:
        model = User
        fields = ["language", "theme"]


class BranchSerializer(serializers.ModelSerializer):
    """
    Serializer for Branch model.
    """

    manager_name = serializers.CharField(source="manager.get_full_name", read_only=True)
    tenant_name = serializers.CharField(source="tenant.company_name", read_only=True)

    class Meta:
        model = Branch
        fields = [
            "id",
            "name",
            "address",
            "phone",
            "manager",
            "manager_name",
            "opening_hours",
            "is_active",
            "tenant",
            "tenant_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tenant", "tenant_name", "created_at", "updated_at"]

    def validate_manager(self, value):
        """Ensure manager belongs to the same tenant."""
        if value and hasattr(self.context.get("request"), "user"):
            user = self.context["request"].user
            if user.tenant and value.tenant != user.tenant:
                raise serializers.ValidationError("Manager must belong to the same tenant.")
        return value


class TerminalSerializer(serializers.ModelSerializer):
    """
    Serializer for Terminal model.
    """

    branch_name = serializers.CharField(source="branch.name", read_only=True)
    assigned_user_username = serializers.CharField(
        source="assigned_user.username", read_only=True, allow_null=True
    )

    class Meta:
        model = Terminal
        fields = [
            "id",
            "terminal_id",
            "description",
            "is_active",
            "configuration",
            "branch",
            "branch_name",
            "assigned_user",
            "assigned_user_username",
            "created_at",
            "updated_at",
            "last_used_at",
        ]
        read_only_fields = [
            "id",
            "branch_name",
            "assigned_user_username",
            "created_at",
            "updated_at",
            "last_used_at",
        ]

    def validate_branch(self, value):
        """Ensure branch belongs to the same tenant."""
        if value and hasattr(self.context.get("request"), "user"):
            user = self.context["request"].user
            if user.tenant and value.tenant != user.tenant:
                raise serializers.ValidationError("Branch must belong to the same tenant.")
        return value


# Settings Serializers


class TenantSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer for TenantSettings model.
    """

    full_address = serializers.CharField(source="get_full_address", read_only=True)

    class Meta:
        model = TenantSettings
        fields = [
            "id",
            "business_name",
            "business_registration_number",
            "tax_identification_number",
            "address_line_1",
            "address_line_2",
            "city",
            "state_province",
            "postal_code",
            "country",
            "full_address",
            "phone",
            "fax",
            "email",
            "website",
            "logo",
            "primary_color",
            "secondary_color",
            "timezone",
            "currency",
            "date_format",
            "business_hours",
            "holidays",
            "default_tax_rate",
            "tax_inclusive_pricing",
            "require_mfa_for_managers",
            "password_expiry_days",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "full_address", "created_at", "updated_at"]

    def validate_primary_color(self, value):
        """Validate hex color format for primary color."""
        if value and (not value.startswith("#") or len(value) != 7):
            raise serializers.ValidationError("Primary color must be in hex format (e.g., #1f2937)")
        return value

    def validate_secondary_color(self, value):
        """Validate hex color format for secondary color."""
        if value and (not value.startswith("#") or len(value) != 7):
            raise serializers.ValidationError(
                "Secondary color must be in hex format (e.g., #6b7280)"
            )
        return value

    def validate_business_hours(self, value):
        """Validate business hours format."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Business hours must be a dictionary")

        valid_days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

        for day, hours in value.items():
            if day not in valid_days:
                raise serializers.ValidationError(f"Invalid day: {day}")

            if not isinstance(hours, dict):
                raise serializers.ValidationError(f"Hours for {day} must be a dictionary")

            required_keys = ["open", "close", "closed"]
            if not all(key in hours for key in required_keys):
                raise serializers.ValidationError(
                    f"Hours for {day} must contain 'open', 'close', and 'closed' keys"
                )

        return value

    def validate_holidays(self, value):
        """Validate holidays format."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Holidays must be a list")

        for holiday in value:
            if not isinstance(holiday, dict):
                raise serializers.ValidationError("Each holiday must be a dictionary")

            if "date" not in holiday or "name" not in holiday:
                raise serializers.ValidationError("Each holiday must have 'date' and 'name' keys")

            # Validate date format
            try:
                from datetime import datetime

                datetime.strptime(holiday["date"], "%Y-%m-%d")
            except ValueError:
                raise serializers.ValidationError(
                    f"Invalid date format for holiday: {holiday['date']}. Use YYYY-MM-DD"
                )

        return value


class InvoiceSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer for InvoiceSettings model.
    """

    class Meta:
        model = InvoiceSettings
        fields = [
            "id",
            "invoice_template",
            "receipt_template",
            "invoice_numbering_scheme",
            "invoice_number_prefix",
            "invoice_number_format",
            "next_invoice_number",
            "receipt_numbering_scheme",
            "receipt_number_prefix",
            "receipt_number_format",
            "next_receipt_number",
            "show_item_codes",
            "show_item_descriptions",
            "show_item_weights",
            "show_karat_purity",
            "show_tax_breakdown",
            "show_payment_terms",
            "custom_field_1_label",
            "custom_field_1_value",
            "custom_field_2_label",
            "custom_field_2_value",
            "invoice_footer_text",
            "receipt_footer_text",
            "payment_terms",
            "return_policy",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_invoice_number_prefix(self, value):
        """Validate invoice number prefix."""
        if value and len(value) > 10:
            raise serializers.ValidationError("Invoice number prefix cannot exceed 10 characters")
        return value

    def validate_receipt_number_prefix(self, value):
        """Validate receipt number prefix."""
        if value and len(value) > 10:
            raise serializers.ValidationError("Receipt number prefix cannot exceed 10 characters")
        return value


class IntegrationSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer for IntegrationSettings model.
    """

    # Exclude sensitive fields from serialization
    class Meta:
        model = IntegrationSettings
        fields = [
            "id",
            "payment_gateway_enabled",
            "payment_gateway_provider",
            "payment_gateway_test_mode",
            "sms_provider_enabled",
            "sms_provider",
            "sms_sender_id",
            "email_provider_enabled",
            "email_provider",
            "email_from_address",
            "email_from_name",
            "smtp_host",
            "smtp_port",
            "smtp_username",
            "smtp_use_tls",
            "gold_rate_api_enabled",
            "gold_rate_api_provider",
            "gold_rate_update_frequency",
            "webhook_url",
            "webhook_events",
            "additional_config",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_webhook_events(self, value):
        """Validate webhook events format."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Webhook events must be a list")

        valid_events = [
            "sale.created",
            "sale.updated",
            "sale.cancelled",
            "inventory.created",
            "inventory.updated",
            "inventory.low_stock",
            "customer.created",
            "customer.updated",
            "repair_order.created",
            "repair_order.status_changed",
        ]

        for event in value:
            if event not in valid_events:
                raise serializers.ValidationError(f"Invalid webhook event: {event}")

        return value

    def validate_additional_config(self, value):
        """Validate additional config format."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Additional config must be a dictionary")
        return value
