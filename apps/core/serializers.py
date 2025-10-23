"""
Serializers for authentication and user management.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.sales.models import Terminal

from .models import Branch

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
