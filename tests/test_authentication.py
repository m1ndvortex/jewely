"""
Tests for authentication system including JWT, MFA, and password management.

Tests cover:
- JWT token generation and validation
- Login flow with valid/invalid credentials
- Password change functionality
- Multi-factor authentication (MFA) setup and verification
- Role-based access control
- Token expiration and refresh
"""

from django.contrib.auth import get_user_model
from django.urls import reverse

import pyotp
import pytest
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import Tenant

User = get_user_model()


@pytest.fixture
def api_client():
    """Create an API client for testing."""
    return APIClient()


@pytest.fixture
def tenant(db):
    """Create a test tenant."""
    return Tenant.objects.create(
        company_name="Test Jewelry Shop",
        slug="test-shop",
        status=Tenant.ACTIVE,
    )


@pytest.fixture
def user(db, tenant):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="TestPassword123!@#",
        tenant=tenant,
        role=User.TENANT_EMPLOYEE,
    )


@pytest.fixture
def owner_user(db, tenant):
    """Create a tenant owner user."""
    return User.objects.create_user(
        username="owner",
        email="owner@example.com",
        password="OwnerPassword123!@#",
        tenant=tenant,
        role=User.TENANT_OWNER,
    )


@pytest.fixture
def platform_admin(db):
    """Create a platform admin user."""
    return User.objects.create_user(
        username="admin",
        email="admin@example.com",
        password="AdminPassword123!@#",
        role=User.PLATFORM_ADMIN,
        is_staff=True,
        is_superuser=True,
    )


@pytest.mark.django_db
class TestJWTAuthentication:
    """Test JWT token generation and validation."""

    def test_login_with_valid_credentials(self, api_client, user):
        """Test successful login with valid credentials returns JWT tokens."""
        url = reverse("core:token_obtain_pair")
        data = {
            "username": "testuser",
            "password": "TestPassword123!@#",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data
        assert "user" in response.data
        assert response.data["user"]["username"] == "testuser"
        assert response.data["user"]["email"] == "testuser@example.com"
        assert response.data["user"]["role"] == User.TENANT_EMPLOYEE

    def test_login_with_email(self, api_client, user):
        """Test login using email instead of username."""
        url = reverse("core:token_obtain_pair")
        data = {
            "username": "testuser@example.com",  # Using email
            "password": "TestPassword123!@#",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data

    def test_login_with_invalid_password(self, api_client, user):
        """Test login fails with invalid password."""
        url = reverse("core:token_obtain_pair")
        data = {
            "username": "testuser",
            "password": "WrongPassword",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_with_nonexistent_user(self, api_client):
        """Test login fails with nonexistent user."""
        url = reverse("core:token_obtain_pair")
        data = {
            "username": "nonexistent",
            "password": "SomePassword123",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_refresh(self, api_client, user):
        """Test JWT token refresh functionality."""
        # Get initial tokens
        refresh = RefreshToken.for_user(user)
        refresh_token = str(refresh)

        # Refresh the token
        url = reverse("core:token_refresh")
        data = {"refresh": refresh_token}
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data

    def test_jwt_token_contains_user_info(self, api_client, user):
        """Test that JWT token contains custom user claims."""
        url = reverse("core:token_obtain_pair")
        data = {
            "username": "testuser",
            "password": "TestPassword123!@#",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        user_data = response.data["user"]
        assert user_data["username"] == user.username
        assert user_data["email"] == user.email
        assert user_data["role"] == user.role
        assert str(user_data["tenant_id"]) == str(user.tenant_id)
        assert user_data["language"] == user.language
        assert user_data["theme"] == user.theme

    def test_authenticated_request_with_jwt(self, api_client, user):
        """Test making authenticated requests with JWT token."""
        # Get token
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        # Make authenticated request
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        url = reverse("core:user_profile")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["username"] == user.username


@pytest.mark.django_db
class TestPasswordManagement:
    """Test password change and validation."""

    def test_password_change_with_valid_old_password(self, api_client, user):
        """Test successful password change."""
        # Authenticate
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        url = reverse("core:password_change")
        data = {
            "old_password": "TestPassword123!@#",
            "new_password": "NewPassword456!@#",
            "new_password2": "NewPassword456!@#",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "Password changed successfully" in response.data["detail"]

        # Verify new password works
        user.refresh_from_db()
        assert user.check_password("NewPassword456!@#")

    def test_password_change_with_invalid_old_password(self, api_client, user):
        """Test password change fails with wrong old password."""
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        url = reverse("core:password_change")
        data = {
            "old_password": "WrongOldPassword",
            "new_password": "NewPassword456!@#",
            "new_password2": "NewPassword456!@#",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_password_change_with_mismatched_passwords(self, api_client, user):
        """Test password change fails when new passwords don't match."""
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        url = reverse("core:password_change")
        data = {
            "old_password": "TestPassword123!@#",
            "new_password": "NewPassword456!@#",
            "new_password2": "DifferentPassword789!@#",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_password_uses_argon2_hashing(self, user):
        """Test that passwords are hashed using Argon2."""
        # Check that the password hash starts with argon2
        assert user.password.startswith("argon2")


@pytest.mark.django_db
class TestMultiFactorAuthentication:
    """Test MFA setup, verification, and management."""

    def test_mfa_status_for_user_without_mfa(self, api_client, user):
        """Test MFA status check for user without MFA enabled."""
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        url = reverse("core:mfa_status")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_mfa_enabled"] is False
        assert response.data["has_device"] is False

    def test_mfa_enable_creates_totp_device(self, api_client, user):
        """Test enabling MFA creates a TOTP device."""
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        url = reverse("core:mfa_enable")
        response = api_client.post(url, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert "qr_code_url" in response.data
        assert "secret" in response.data

        # Verify device was created
        assert TOTPDevice.objects.filter(user=user, confirmed=False).exists()

    def test_mfa_confirm_with_valid_token(self, api_client, user):
        """Test confirming MFA with valid token."""
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        # Enable MFA first
        enable_url = reverse("core:mfa_enable")
        api_client.post(enable_url, format="json")

        # Get the device and generate a valid token
        device = TOTPDevice.objects.get(user=user, confirmed=False)
        # Convert hex key to base32 for pyotp
        import base64

        key_bytes = bytes.fromhex(device.key)
        key_base32 = base64.b32encode(key_bytes).decode("utf-8")
        totp = pyotp.TOTP(key_base32)
        token = totp.now()

        # Confirm MFA
        confirm_url = reverse("core:mfa_confirm")
        data = {"token": token}
        response = api_client.post(confirm_url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "MFA enabled successfully" in response.data["detail"]

        # Verify device is confirmed and user MFA status updated
        device.refresh_from_db()
        assert device.confirmed is True
        user.refresh_from_db()
        assert user.is_mfa_enabled is True

    def test_mfa_confirm_with_invalid_token(self, api_client, user):
        """Test confirming MFA with invalid token fails."""
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        # Enable MFA first
        enable_url = reverse("core:mfa_enable")
        api_client.post(enable_url, format="json")

        # Try to confirm with invalid token
        confirm_url = reverse("core:mfa_confirm")
        data = {"token": "000000"}  # Invalid token
        response = api_client.post(confirm_url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid token" in response.data["detail"]

    def test_mfa_disable_with_valid_password(self, api_client, user):
        """Test disabling MFA with valid password."""
        # Setup: Enable and confirm MFA
        TOTPDevice.objects.create(user=user, name="default", confirmed=True)
        user.is_mfa_enabled = True
        user.save()

        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        # Disable MFA
        url = reverse("core:mfa_disable")
        data = {"password": "TestPassword123!@#"}
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "MFA disabled successfully" in response.data["detail"]

        # Verify device deleted and user MFA status updated
        assert not TOTPDevice.objects.filter(user=user).exists()
        user.refresh_from_db()
        assert user.is_mfa_enabled is False

    def test_mfa_disable_with_invalid_password(self, api_client, user):
        """Test disabling MFA with invalid password fails."""
        TOTPDevice.objects.create(user=user, name="default", confirmed=True)
        user.is_mfa_enabled = True
        user.save()

        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        url = reverse("core:mfa_disable")
        data = {"password": "WrongPassword"}
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid password" in response.data["detail"]

    def test_mfa_verify_with_valid_token(self, api_client, user):
        """Test verifying MFA token during login."""
        # Setup: Enable and confirm MFA
        device = TOTPDevice.objects.create(user=user, name="default", confirmed=True)
        user.is_mfa_enabled = True
        user.save()

        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        # Generate valid token using pyotp
        # Convert hex key to base32 for pyotp
        import base64

        key_bytes = bytes.fromhex(device.key)
        key_base32 = base64.b32encode(key_bytes).decode("utf-8")
        totp = pyotp.TOTP(key_base32)
        token = totp.now()

        # Verify token
        url = reverse("core:mfa_verify")
        data = {"token": token}
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "Token verified successfully" in response.data["detail"]


@pytest.mark.django_db
class TestUserProfile:
    """Test user profile management."""

    def test_get_user_profile(self, api_client, user):
        """Test retrieving user profile."""
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        url = reverse("core:user_profile")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["username"] == user.username
        assert response.data["email"] == user.email
        assert response.data["role"] == user.role

    def test_update_user_profile(self, api_client, user):
        """Test updating user profile."""
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        url = reverse("core:user_profile")
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "phone": "+1234567890",
        }
        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert user.phone == "+1234567890"

    def test_update_user_preferences(self, api_client, user):
        """Test updating user language and theme preferences."""
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        url = reverse("core:user_preferences")
        data = {
            "language": "fa",
            "theme": "dark",
        }
        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.language == "fa"
        assert user.theme == "dark"


@pytest.mark.django_db
class TestRoleBasedAccess:
    """Test role-based access control."""

    def test_platform_admin_has_no_tenant(self, platform_admin):
        """Test that platform admins have no tenant association."""
        assert platform_admin.tenant is None
        assert platform_admin.is_platform_admin()

    def test_tenant_owner_permissions(self, owner_user):
        """Test tenant owner has appropriate permissions."""
        assert owner_user.is_tenant_owner()
        assert owner_user.has_tenant_access()
        assert owner_user.can_manage_users()
        assert owner_user.can_manage_inventory()
        assert owner_user.can_process_sales()

    def test_tenant_employee_permissions(self, user):
        """Test tenant employee has limited permissions."""
        assert user.is_tenant_employee()
        assert user.has_tenant_access()
        assert not user.can_manage_users()
        assert not user.can_manage_inventory()
        assert user.can_process_sales()

    def test_unauthenticated_access_denied(self, api_client):
        """Test that unauthenticated requests are denied."""
        url = reverse("core:user_profile")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestPasswordComplexity:
    """Test password complexity requirements."""

    def test_password_minimum_length_enforced(self, db, tenant):
        """Test that minimum password length is enforced."""
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError

        # Test that short password fails validation
        with pytest.raises(ValidationError):
            validate_password("short")

    def test_strong_password_accepted(self, db, tenant):
        """Test that strong passwords are accepted."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="StrongPassword123!@#",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )
        assert user is not None
        assert user.check_password("StrongPassword123!@#")
