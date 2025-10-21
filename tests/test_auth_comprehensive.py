"""
Comprehensive authentication and authorization tests for Task 3.5.

This test file provides additional coverage for:
- Login flow with valid/invalid credentials
- JWT token generation and validation
- MFA flow
- Role-based access control
- Permission enforcement

Tests complement existing test_authentication.py and test_permissions.py files.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse

import pyotp
import pytest
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import Branch, Tenant

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
def tenant2(db):
    """Create a second test tenant."""
    return Tenant.objects.create(
        company_name="Another Jewelry Shop",
        slug="another-shop",
        status=Tenant.ACTIVE,
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
def manager_user(db, tenant):
    """Create a tenant manager user."""
    return User.objects.create_user(
        username="manager",
        email="manager@example.com",
        password="ManagerPassword123!@#",
        tenant=tenant,
        role=User.TENANT_MANAGER,
    )


@pytest.fixture
def employee_user(db, tenant):
    """Create a tenant employee user."""
    return User.objects.create_user(
        username="employee",
        email="employee@example.com",
        password="EmployeePassword123!@#",
        tenant=tenant,
        role=User.TENANT_EMPLOYEE,
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


@pytest.fixture
def branch(db, tenant):
    """Create a branch for testing."""
    return Branch.objects.create(
        tenant=tenant,
        name="Main Branch",
        address="123 Main St",
        phone="+1234567890",
    )


@pytest.mark.django_db
class TestLoginFlow:
    """Test complete login flow with various scenarios."""

    def test_successful_login_returns_tokens_and_user_info(self, api_client, owner_user):
        """Test successful login returns access token, refresh token, and user information."""
        url = reverse("core:token_obtain_pair")
        data = {
            "username": "owner",
            "password": "OwnerPassword123!@#",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data
        assert "user" in response.data
        assert response.data["user"]["username"] == "owner"
        assert response.data["user"]["role"] == User.TENANT_OWNER
        assert response.data["mfa_required"] is False

    def test_login_with_invalid_username(self, api_client):
        """Test login with non-existent username fails."""
        url = reverse("core:token_obtain_pair")
        data = {
            "username": "nonexistent",
            "password": "SomePassword123!@#",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "access" not in response.data

    def test_login_with_wrong_password(self, api_client, owner_user):
        """Test login with incorrect password fails."""
        url = reverse("core:token_obtain_pair")
        data = {
            "username": "owner",
            "password": "WrongPassword123!@#",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "access" not in response.data

    def test_login_with_empty_credentials(self, api_client):
        """Test login with empty credentials fails."""
        url = reverse("core:token_obtain_pair")
        data = {
            "username": "",
            "password": "",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_with_missing_password(self, api_client):
        """Test login with missing password field fails."""
        url = reverse("core:token_obtain_pair")
        data = {
            "username": "owner",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_with_email_as_username(self, api_client, owner_user):
        """Test login using email address instead of username."""
        url = reverse("core:token_obtain_pair")
        data = {
            "username": "owner@example.com",
            "password": "OwnerPassword123!@#",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data


@pytest.mark.django_db
class TestJWTTokenValidation:
    """Test JWT token generation, validation, and expiration."""

    def test_jwt_token_contains_custom_claims(self, api_client, owner_user):
        """Test that JWT tokens contain custom user claims."""
        url = reverse("core:token_obtain_pair")
        data = {
            "username": "owner",
            "password": "OwnerPassword123!@#",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        user_data = response.data["user"]
        assert user_data["username"] == owner_user.username
        assert user_data["email"] == owner_user.email
        assert user_data["role"] == owner_user.role
        assert str(user_data["tenant_id"]) == str(owner_user.tenant_id)
        assert user_data["language"] == owner_user.language
        assert user_data["theme"] == owner_user.theme

    def test_access_protected_endpoint_with_valid_token(self, api_client, owner_user):
        """Test accessing protected endpoint with valid JWT token."""
        # Get token
        refresh = RefreshToken.for_user(owner_user)
        access_token = str(refresh.access_token)

        # Access protected endpoint
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        url = reverse("core:user_profile")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["username"] == owner_user.username

    def test_access_protected_endpoint_without_token(self, api_client):
        """Test accessing protected endpoint without token fails."""
        url = reverse("core:user_profile")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_access_protected_endpoint_with_invalid_token(self, api_client):
        """Test accessing protected endpoint with invalid token fails."""
        api_client.credentials(HTTP_AUTHORIZATION="Bearer invalid_token_here")
        url = reverse("core:user_profile")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_token_generates_new_access_token(self, api_client, owner_user):
        """Test that refresh token can generate new access token."""
        # Get initial tokens
        refresh = RefreshToken.for_user(owner_user)
        refresh_token = str(refresh)

        # Use refresh token to get new access token
        url = reverse("core:token_refresh")
        data = {"refresh": refresh_token}
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data

    def test_invalid_refresh_token_fails(self, api_client):
        """Test that invalid refresh token fails."""
        url = reverse("core:token_refresh")
        data = {"refresh": "invalid_refresh_token"}
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestMFAFlow:
    """Test complete MFA flow from setup to login."""

    def test_mfa_enable_flow(self, api_client, owner_user):
        """Test enabling MFA creates device and returns QR code."""
        refresh = RefreshToken.for_user(owner_user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        # Enable MFA
        url = reverse("core:mfa_enable")
        response = api_client.post(url, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert "qr_code_url" in response.data
        assert "secret" in response.data

        # Verify device was created
        assert TOTPDevice.objects.filter(user=owner_user, confirmed=False).exists()

    def test_mfa_confirm_with_correct_token(self, api_client, owner_user):
        """Test confirming MFA with correct token."""
        refresh = RefreshToken.for_user(owner_user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        # Enable MFA
        enable_url = reverse("core:mfa_enable")
        api_client.post(enable_url, format="json")

        # Get device and generate valid token
        device = TOTPDevice.objects.get(user=owner_user, confirmed=False)
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

        # Verify device is confirmed
        device.refresh_from_db()
        assert device.confirmed is True
        owner_user.refresh_from_db()
        assert owner_user.is_mfa_enabled is True

    def test_mfa_confirm_with_incorrect_token(self, api_client, owner_user):
        """Test confirming MFA with incorrect token fails."""
        refresh = RefreshToken.for_user(owner_user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        # Enable MFA
        enable_url = reverse("core:mfa_enable")
        api_client.post(enable_url, format="json")

        # Try to confirm with wrong token
        confirm_url = reverse("core:mfa_confirm")
        data = {"token": "000000"}
        response = api_client.post(confirm_url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid token" in response.data["detail"]

    def test_login_with_mfa_requires_token(self, api_client, owner_user):
        """Test that login with MFA enabled requires MFA token."""
        # Setup MFA
        TOTPDevice.objects.create(user=owner_user, name="default", confirmed=True)
        owner_user.is_mfa_enabled = True
        owner_user.save()

        # Try to login without MFA token
        url = reverse("core:token_obtain_pair")
        data = {
            "username": "owner",
            "password": "OwnerPassword123!@#",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["mfa_required"] is True
        assert "access" not in response.data
        assert "user_id" in response.data

    def test_login_with_mfa_and_correct_token(self, api_client, owner_user):
        """Test successful login with MFA and correct token."""
        # Setup MFA
        device = TOTPDevice.objects.create(user=owner_user, name="default", confirmed=True)
        owner_user.is_mfa_enabled = True
        owner_user.save()

        # Generate valid token
        import base64

        key_bytes = bytes.fromhex(device.key)
        key_base32 = base64.b32encode(key_bytes).decode("utf-8")
        totp = pyotp.TOTP(key_base32)
        token = totp.now()

        # Login with MFA token
        url = reverse("core:token_obtain_pair")
        data = {
            "username": "owner",
            "password": "OwnerPassword123!@#",
            "mfa_token": token,
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data
        assert response.data["mfa_required"] is False

    def test_login_with_mfa_and_incorrect_token(self, api_client, owner_user):
        """Test login with MFA and incorrect token fails."""
        # Setup MFA
        TOTPDevice.objects.create(user=owner_user, name="default", confirmed=True)
        owner_user.is_mfa_enabled = True
        owner_user.save()

        # Try to login with wrong token
        url = reverse("core:token_obtain_pair")
        data = {
            "username": "owner",
            "password": "OwnerPassword123!@#",
            "mfa_token": "000000",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "mfa_token" in response.data

    def test_mfa_disable_with_correct_password(self, api_client, owner_user):
        """Test disabling MFA with correct password."""
        # Setup MFA
        TOTPDevice.objects.create(user=owner_user, name="default", confirmed=True)
        owner_user.is_mfa_enabled = True
        owner_user.save()

        refresh = RefreshToken.for_user(owner_user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        # Disable MFA
        url = reverse("core:mfa_disable")
        data = {"password": "OwnerPassword123!@#"}
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "MFA disabled successfully" in response.data["detail"]

        # Verify device deleted
        assert not TOTPDevice.objects.filter(user=owner_user).exists()
        owner_user.refresh_from_db()
        assert owner_user.is_mfa_enabled is False

    def test_mfa_disable_with_incorrect_password(self, api_client, owner_user):
        """Test disabling MFA with incorrect password fails."""
        # Setup MFA
        TOTPDevice.objects.create(user=owner_user, name="default", confirmed=True)
        owner_user.is_mfa_enabled = True
        owner_user.save()

        refresh = RefreshToken.for_user(owner_user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        # Try to disable with wrong password
        url = reverse("core:mfa_disable")
        data = {"password": "WrongPassword"}
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid password" in response.data["detail"]


@pytest.mark.django_db
class TestRoleBasedAccessControl:
    """Test role-based access control across different user roles."""

    def test_platform_admin_role_identification(self, platform_admin):
        """Test platform admin role identification methods."""
        assert platform_admin.is_platform_admin() is True
        assert platform_admin.is_tenant_owner() is False
        assert platform_admin.is_tenant_manager() is False
        assert platform_admin.is_tenant_employee() is False
        assert platform_admin.has_tenant_access() is False
        assert platform_admin.tenant is None

    def test_tenant_owner_role_identification(self, owner_user):
        """Test tenant owner role identification methods."""
        assert owner_user.is_platform_admin() is False
        assert owner_user.is_tenant_owner() is True
        assert owner_user.is_tenant_manager() is False
        assert owner_user.is_tenant_employee() is False
        assert owner_user.has_tenant_access() is True
        assert owner_user.tenant is not None

    def test_tenant_manager_role_identification(self, manager_user):
        """Test tenant manager role identification methods."""
        assert manager_user.is_platform_admin() is False
        assert manager_user.is_tenant_owner() is False
        assert manager_user.is_tenant_manager() is True
        assert manager_user.is_tenant_employee() is False
        assert manager_user.has_tenant_access() is True

    def test_tenant_employee_role_identification(self, employee_user):
        """Test tenant employee role identification methods."""
        assert employee_user.is_platform_admin() is False
        assert employee_user.is_tenant_owner() is False
        assert employee_user.is_tenant_manager() is False
        assert employee_user.is_tenant_employee() is True
        assert employee_user.has_tenant_access() is True

    def test_owner_can_manage_users(self, owner_user):
        """Test that tenant owner can manage users."""
        assert owner_user.can_manage_users() is True

    def test_manager_can_manage_users(self, manager_user):
        """Test that tenant manager can manage users."""
        assert manager_user.can_manage_users() is True

    def test_employee_cannot_manage_users(self, employee_user):
        """Test that tenant employee cannot manage users."""
        assert employee_user.can_manage_users() is False

    def test_owner_can_manage_inventory(self, owner_user):
        """Test that tenant owner can manage inventory."""
        assert owner_user.can_manage_inventory() is True

    def test_manager_can_manage_inventory(self, manager_user):
        """Test that tenant manager can manage inventory."""
        assert manager_user.can_manage_inventory() is True

    def test_employee_cannot_manage_inventory(self, employee_user):
        """Test that tenant employee cannot manage inventory."""
        assert employee_user.can_manage_inventory() is False

    def test_all_tenant_users_can_process_sales(self, owner_user, manager_user, employee_user):
        """Test that all tenant users can process sales."""
        assert owner_user.can_process_sales() is True
        assert manager_user.can_process_sales() is True
        assert employee_user.can_process_sales() is True

    def test_platform_admin_cannot_process_sales(self, platform_admin):
        """Test that platform admin cannot process sales."""
        assert platform_admin.can_process_sales() is False


@pytest.mark.django_db
class TestPermissionEnforcement:
    """Test permission enforcement at the API level."""

    def test_unauthenticated_user_cannot_access_profile(self, api_client):
        """Test that unauthenticated users cannot access protected endpoints."""
        url = reverse("core:user_profile")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_authenticated_user_can_access_own_profile(self, api_client, owner_user):
        """Test that authenticated users can access their own profile."""
        refresh = RefreshToken.for_user(owner_user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        url = reverse("core:user_profile")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["username"] == owner_user.username

    def test_user_can_update_own_profile(self, api_client, owner_user):
        """Test that users can update their own profile."""
        refresh = RefreshToken.for_user(owner_user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        url = reverse("core:user_profile")
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "phone": "+1234567890",
        }
        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        owner_user.refresh_from_db()
        assert owner_user.first_name == "John"
        assert owner_user.last_name == "Doe"
        assert owner_user.phone == "+1234567890"

    def test_user_can_change_preferences(self, api_client, owner_user):
        """Test that users can change their language and theme preferences."""
        refresh = RefreshToken.for_user(owner_user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        url = reverse("core:user_preferences")
        data = {
            "language": "fa",
            "theme": "dark",
        }
        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        owner_user.refresh_from_db()
        assert owner_user.language == "fa"
        assert owner_user.theme == "dark"

    def test_user_can_change_password(self, api_client, owner_user):
        """Test that users can change their password."""
        refresh = RefreshToken.for_user(owner_user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        url = reverse("core:password_change")
        data = {
            "old_password": "OwnerPassword123!@#",
            "new_password": "NewPassword456!@#",
            "new_password2": "NewPassword456!@#",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        owner_user.refresh_from_db()
        assert owner_user.check_password("NewPassword456!@#")


@pytest.mark.django_db
class TestTenantIsolation:
    """Test that users can only access data from their own tenant."""

    def test_users_from_different_tenants_have_different_tenant_ids(
        self, owner_user, tenant, tenant2
    ):
        """Test that users from different tenants have different tenant IDs."""
        user2 = User.objects.create_user(
            username="owner2",
            email="owner2@example.com",
            password="Password123!@#",
            tenant=tenant2,
            role=User.TENANT_OWNER,
        )

        assert owner_user.tenant_id != user2.tenant_id
        assert owner_user.tenant == tenant
        assert user2.tenant == tenant2

    def test_jwt_token_contains_correct_tenant_id(self, api_client, owner_user):
        """Test that JWT token contains the correct tenant ID."""
        url = reverse("core:token_obtain_pair")
        data = {
            "username": "owner",
            "password": "OwnerPassword123!@#",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert str(response.data["user"]["tenant_id"]) == str(owner_user.tenant_id)


@pytest.mark.django_db
class TestPasswordSecurity:
    """Test password security requirements."""

    def test_password_uses_argon2_hashing(self, owner_user):
        """Test that passwords are hashed using Argon2."""
        assert owner_user.password.startswith("argon2")

    def test_weak_password_rejected(self, db, tenant):
        """Test that weak passwords are rejected."""
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            validate_password("weak")

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


@pytest.mark.django_db
class TestPlatformAdminMFARequirement:
    """Test MFA requirement for platform administrators."""

    def test_platform_admin_requires_mfa(self, platform_admin):
        """Test that platform admins are required to have MFA."""
        assert platform_admin.requires_mfa() is True

    def test_tenant_users_do_not_require_mfa(self, owner_user, manager_user, employee_user):
        """Test that tenant users are not required to have MFA."""
        assert owner_user.requires_mfa() is False
        assert manager_user.requires_mfa() is False
        assert employee_user.requires_mfa() is False

    def test_platform_admin_can_login_without_mfa_but_warned(self, api_client, platform_admin):
        """Test that platform admin can login without MFA but should be warned."""
        url = reverse("core:token_obtain_pair")
        data = {
            "username": "admin",
            "password": "AdminPassword123!@#",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert response.data["user"]["is_mfa_enabled"] is False
        # In production, this should trigger a warning or restriction


@pytest.mark.django_db
class TestBranchBasedAccess:
    """Test branch-based access control."""

    def test_user_assigned_to_branch(self, employee_user, branch):
        """Test that users can be assigned to branches."""
        employee_user.branch = branch
        employee_user.save()

        assert employee_user.branch == branch
        assert employee_user.branch.tenant == employee_user.tenant

    def test_user_branch_must_belong_to_same_tenant(self, employee_user, tenant2):
        """Test that user's branch must belong to the same tenant."""
        other_branch = Branch.objects.create(
            tenant=tenant2,
            name="Other Branch",
            address="456 Other St",
            phone="+0987654321",
        )

        employee_user.branch = other_branch
        with pytest.raises(ValueError, match="Branch must belong to the same tenant"):
            employee_user.save()


@pytest.mark.django_db
class TestUserModelConstraints:
    """Test User model constraints and validation."""

    def test_platform_admin_cannot_have_tenant(self, db):
        """Test that platform admins cannot have a tenant."""
        admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="Password123!@#",
            role=User.PLATFORM_ADMIN,
        )

        assert admin.tenant is None
        assert admin.branch is None

    def test_tenant_user_must_have_tenant(self, db):
        """Test that tenant users must have a tenant."""
        with pytest.raises(ValueError, match="must have a tenant assigned"):
            User.objects.create_user(
                username="user",
                email="user@example.com",
                password="Password123!@#",
                role=User.TENANT_OWNER,
                tenant=None,
            )
