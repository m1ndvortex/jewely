"""
Tests for tenant user management functionality.

Tests the admin panel's ability to manage tenant users including:
- Password reset initiation
- Role changes
- User activation/deactivation
"""

import uuid

from django.contrib.auth import get_user_model
from django.urls import reverse

import pytest

from apps.core.models import Tenant
from apps.core.tenant_context import bypass_rls

User = get_user_model()


@pytest.fixture
def platform_admin(db):
    """Create a platform admin user."""
    unique_id = str(uuid.uuid4())[:8]
    with bypass_rls():
        return User.objects.create_user(
            username=f"admin-{unique_id}",
            email=f"admin-{unique_id}@example.com",
            password="AdminPassword123!@#",
            role=User.PLATFORM_ADMIN,
            is_staff=True,
            is_superuser=True,
        )


@pytest.fixture
def tenant(db):
    """Create a test tenant."""
    with bypass_rls():
        return Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug=f"test-shop-{uuid.uuid4().hex[:8]}",
            status=Tenant.ACTIVE,
        )


@pytest.fixture
def tenant_owner(db, tenant):
    """Create a tenant owner user."""
    unique_id = str(uuid.uuid4())[:8]
    with bypass_rls():
        return User.objects.create_user(
            username=f"owner-{unique_id}",
            email=f"owner-{unique_id}@example.com",
            password="OwnerPassword123!@#",
            tenant=tenant,
            role=User.TENANT_OWNER,
        )


@pytest.fixture
def tenant_employee(db, tenant):
    """Create a tenant employee user."""
    unique_id = str(uuid.uuid4())[:8]
    with bypass_rls():
        return User.objects.create_user(
            username=f"employee-{unique_id}",
            email=f"employee-{unique_id}@example.com",
            password="EmployeePassword123!@#",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )


@pytest.mark.django_db
class TestTenantUserPasswordReset:
    """Test password reset functionality for tenant users."""

    def test_password_reset_requires_authentication(self, client, tenant, tenant_owner):
        """Test that password reset requires authentication."""
        url = reverse(
            "core:admin_tenant_user_reset_password",
            kwargs={"tenant_pk": tenant.pk, "user_pk": tenant_owner.pk},
        )
        response = client.post(url)

        # Should redirect to login
        assert response.status_code == 302
        assert "login" in response.url.lower()

    def test_password_reset_requires_platform_admin(
        self, client, tenant, tenant_owner, tenant_employee
    ):
        """Test that password reset requires platform admin role."""
        client.force_login(tenant_owner)
        url = reverse(
            "core:admin_tenant_user_reset_password",
            kwargs={"tenant_pk": tenant.pk, "user_pk": tenant_employee.pk},
        )
        response = client.post(url)

        # Should return 403 Forbidden
        assert response.status_code == 403

    def test_password_reset_successful(self, client, platform_admin, tenant, tenant_owner):
        """Test successful password reset initiation."""
        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_user_reset_password",
            kwargs={"tenant_pk": tenant.pk, "user_pk": tenant_owner.pk},
        )
        response = client.post(url, follow=True)

        # Should redirect to tenant detail page with users tab
        assert response.status_code == 200
        # Check for success message in Django messages
        messages = list(response.context["messages"])
        assert len(messages) > 0
        assert any("password reset initiated" in str(m).lower() for m in messages)

    def test_password_reset_prevents_platform_admin_reset(self, client, platform_admin, tenant):
        """Test that platform admin passwords cannot be reset through this interface."""
        # Create another platform admin
        with bypass_rls():
            other_admin = User.objects.create_user(
                username=f"admin2-{uuid.uuid4().hex[:8]}",
                email=f"admin2-{uuid.uuid4().hex[:8]}@example.com",
                password="AdminPassword123!@#",
                role=User.PLATFORM_ADMIN,
                is_staff=True,
            )

        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_user_reset_password",
            kwargs={"tenant_pk": tenant.pk, "user_pk": other_admin.pk},
        )
        response = client.post(url, follow=True)

        # Should show error message
        assert response.status_code == 200
        messages = list(response.context["messages"])
        assert len(messages) > 0
        assert any(
            "cannot reset password for platform administrators" in str(m).lower() for m in messages
        )

    def test_password_reset_invalid_user(self, client, platform_admin, tenant):
        """Test password reset with invalid user ID."""
        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_user_reset_password",
            kwargs={"tenant_pk": tenant.pk, "user_pk": 99999},
        )
        response = client.post(url)

        # Should return 404
        assert response.status_code == 404

    def test_password_reset_user_from_different_tenant(self, client, platform_admin, tenant, db):
        """Test password reset for user from different tenant."""
        # Create another tenant and user
        with bypass_rls():
            other_tenant = Tenant.objects.create(
                company_name="Other Shop",
                slug=f"other-shop-{uuid.uuid4().hex[:8]}",
                status=Tenant.ACTIVE,
            )
            other_user = User.objects.create_user(
                username=f"other-user-{uuid.uuid4().hex[:8]}",
                email=f"other-user-{uuid.uuid4().hex[:8]}@example.com",
                password="Password123!@#",
                tenant=other_tenant,
                role=User.TENANT_EMPLOYEE,
            )

        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_user_reset_password",
            kwargs={"tenant_pk": tenant.pk, "user_pk": other_user.pk},
        )
        response = client.post(url)

        # Should return 404 (user not found in this tenant)
        assert response.status_code == 404


@pytest.mark.django_db
class TestTenantUserRoleChange:
    """Test role change functionality for tenant users."""

    def test_role_change_requires_authentication(self, client, tenant, tenant_employee):
        """Test that role change requires authentication."""
        url = reverse(
            "core:admin_tenant_user_change_role",
            kwargs={"tenant_pk": tenant.pk, "user_pk": tenant_employee.pk},
        )
        response = client.post(url, {"role": User.TENANT_MANAGER})

        # Should redirect to login
        assert response.status_code == 302
        assert "login" in response.url.lower()

    def test_role_change_requires_platform_admin(
        self, client, tenant, tenant_owner, tenant_employee
    ):
        """Test that role change requires platform admin role."""
        client.force_login(tenant_owner)
        url = reverse(
            "core:admin_tenant_user_change_role",
            kwargs={"tenant_pk": tenant.pk, "user_pk": tenant_employee.pk},
        )
        response = client.post(url, {"role": User.TENANT_MANAGER})

        # Should return 403 Forbidden
        assert response.status_code == 403

    def test_role_change_successful(self, client, platform_admin, tenant, tenant_employee):
        """Test successful role change."""
        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_user_change_role",
            kwargs={"tenant_pk": tenant.pk, "user_pk": tenant_employee.pk},
        )
        response = client.post(url, {"role": User.TENANT_MANAGER}, follow=True)

        # Should redirect to tenant detail page with users tab
        assert response.status_code == 200
        messages = list(response.context["messages"])
        assert len(messages) > 0
        assert any(
            "role for user" in str(m).lower() and "changed from" in str(m).lower() for m in messages
        )

        # Verify role was actually changed
        tenant_employee.refresh_from_db()
        assert tenant_employee.role == User.TENANT_MANAGER

    def test_role_change_prevents_platform_admin_role(
        self, client, platform_admin, tenant, tenant_employee
    ):
        """Test that users cannot be changed to platform admin role."""
        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_user_change_role",
            kwargs={"tenant_pk": tenant.pk, "user_pk": tenant_employee.pk},
        )
        response = client.post(url, {"role": User.PLATFORM_ADMIN}, follow=True)

        # Should show error message
        assert response.status_code == 200
        assert "Cannot change platform administrator roles" in response.content.decode()

        # Verify role was not changed
        tenant_employee.refresh_from_db()
        assert tenant_employee.role == User.TENANT_EMPLOYEE

    def test_role_change_invalid_role(self, client, platform_admin, tenant, tenant_employee):
        """Test role change with invalid role."""
        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_user_change_role",
            kwargs={"tenant_pk": tenant.pk, "user_pk": tenant_employee.pk},
        )
        response = client.post(url, {"role": "INVALID_ROLE"}, follow=True)

        # Should show error message
        assert response.status_code == 200
        assert "Invalid role selected" in response.content.decode()

        # Verify role was not changed
        tenant_employee.refresh_from_db()
        assert tenant_employee.role == User.TENANT_EMPLOYEE

    def test_role_change_from_owner_to_employee(self, client, platform_admin, tenant, tenant_owner):
        """Test changing role from owner to employee."""
        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_user_change_role",
            kwargs={"tenant_pk": tenant.pk, "user_pk": tenant_owner.pk},
        )
        response = client.post(url, {"role": User.TENANT_EMPLOYEE}, follow=True)

        # Should succeed
        assert response.status_code == 200
        assert "Role for user" in response.content.decode()

        # Verify role was changed
        tenant_owner.refresh_from_db()
        assert tenant_owner.role == User.TENANT_EMPLOYEE


@pytest.mark.django_db
class TestTenantUserToggleActive:
    """Test user activation/deactivation functionality."""

    def test_toggle_active_requires_authentication(self, client, tenant, tenant_employee):
        """Test that toggle active requires authentication."""
        url = reverse(
            "core:admin_tenant_user_toggle_active",
            kwargs={"tenant_pk": tenant.pk, "user_pk": tenant_employee.pk},
        )
        response = client.post(url)

        # Should redirect to login
        assert response.status_code == 302
        assert "login" in response.url.lower()

    def test_toggle_active_requires_platform_admin(
        self, client, tenant, tenant_owner, tenant_employee
    ):
        """Test that toggle active requires platform admin role."""
        client.force_login(tenant_owner)
        url = reverse(
            "core:admin_tenant_user_toggle_active",
            kwargs={"tenant_pk": tenant.pk, "user_pk": tenant_employee.pk},
        )
        response = client.post(url)

        # Should return 403 Forbidden
        assert response.status_code == 403

    def test_deactivate_user_successful(self, client, platform_admin, tenant, tenant_employee):
        """Test successful user deactivation."""
        # Ensure user is active
        tenant_employee.is_active = True
        tenant_employee.save()

        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_user_toggle_active",
            kwargs={"tenant_pk": tenant.pk, "user_pk": tenant_employee.pk},
        )
        response = client.post(url, follow=True)

        # Should redirect to tenant detail page with users tab
        assert response.status_code == 200
        assert "deactivated" in response.content.decode()

        # Verify user was deactivated
        tenant_employee.refresh_from_db()
        assert tenant_employee.is_active is False

    def test_activate_user_successful(self, client, platform_admin, tenant, tenant_employee):
        """Test successful user activation."""
        # Deactivate user first
        tenant_employee.is_active = False
        tenant_employee.save()

        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_user_toggle_active",
            kwargs={"tenant_pk": tenant.pk, "user_pk": tenant_employee.pk},
        )
        response = client.post(url, follow=True)

        # Should redirect to tenant detail page with users tab
        assert response.status_code == 200
        assert "activated" in response.content.decode()

        # Verify user was activated
        tenant_employee.refresh_from_db()
        assert tenant_employee.is_active is True

    def test_toggle_active_prevents_platform_admin_deactivation(
        self, client, platform_admin, tenant
    ):
        """Test that platform admins cannot be deactivated."""
        # Create another platform admin
        with bypass_rls():
            other_admin = User.objects.create_user(
                username=f"admin2-{uuid.uuid4().hex[:8]}",
                email=f"admin2-{uuid.uuid4().hex[:8]}@example.com",
                password="AdminPassword123!@#",
                role=User.PLATFORM_ADMIN,
                is_staff=True,
            )

        client.force_login(platform_admin)
        url = reverse(
            "core:admin_tenant_user_toggle_active",
            kwargs={"tenant_pk": tenant.pk, "user_pk": other_admin.pk},
        )
        response = client.post(url, follow=True)

        # Should show error message
        assert response.status_code == 200
        assert "Cannot deactivate platform administrators" in response.content.decode()

        # Verify admin is still active
        other_admin.refresh_from_db()
        assert other_admin.is_active is True


@pytest.mark.django_db
class TestTenantDetailUsersTab:
    """Test tenant detail page users tab functionality."""

    def test_users_tab_displays_all_tenant_users(
        self, client, platform_admin, tenant, tenant_owner, tenant_employee
    ):
        """Test that users tab displays all users for the tenant."""
        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_detail", kwargs={"pk": tenant.pk}) + "?tab=users"
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()

        # Check that both users are displayed
        assert tenant_owner.username in content
        assert tenant_employee.username in content
        assert tenant_owner.email in content
        assert tenant_employee.email in content

    def test_users_tab_shows_user_roles(
        self, client, platform_admin, tenant, tenant_owner, tenant_employee
    ):
        """Test that users tab shows correct user roles."""
        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_detail", kwargs={"pk": tenant.pk}) + "?tab=users"
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()

        # Check that roles are displayed
        assert "Shop Owner" in content
        assert "Shop Employee" in content

    def test_users_tab_shows_user_status(self, client, platform_admin, tenant, tenant_employee):
        """Test that users tab shows correct user status."""
        # Deactivate one user
        tenant_employee.is_active = False
        tenant_employee.save()

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_detail", kwargs={"pk": tenant.pk}) + "?tab=users"
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()

        # Check that status is displayed
        assert "Active" in content
        assert "Inactive" in content

    def test_users_tab_shows_action_buttons(self, client, platform_admin, tenant, tenant_employee):
        """Test that users tab shows action buttons for each user."""
        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_detail", kwargs={"pk": tenant.pk}) + "?tab=users"
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()

        # Check that action buttons are present
        assert "Change Role" in content
        assert "Reset Password" in content
        # The activate/deactivate button text depends on user status
        assert "Deactivate User" in content or "Activate User" in content

    def test_users_tab_empty_state(self, client, platform_admin, db):
        """Test users tab when tenant has no users."""
        # Create a tenant with no users
        with bypass_rls():
            empty_tenant = Tenant.objects.create(
                company_name="Empty Shop",
                slug=f"empty-shop-{uuid.uuid4().hex[:8]}",
                status=Tenant.ACTIVE,
            )

        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_detail", kwargs={"pk": empty_tenant.pk}) + "?tab=users"
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()

        # Check for empty state message
        assert "No users found for this tenant" in content


@pytest.mark.django_db
class TestTenantUserManagementSecurity:
    """Test security aspects of tenant user management."""

    def test_cannot_manage_users_from_different_tenant(self, client, platform_admin, tenant, db):
        """Test that user management respects tenant boundaries."""
        # Create another tenant with a user
        with bypass_rls():
            other_tenant = Tenant.objects.create(
                company_name="Other Shop",
                slug=f"other-shop-{uuid.uuid4().hex[:8]}",
                status=Tenant.ACTIVE,
            )
            other_user = User.objects.create_user(
                username=f"other-user-{uuid.uuid4().hex[:8]}",
                email=f"other-user-{uuid.uuid4().hex[:8]}@example.com",
                password="Password123!@#",
                tenant=other_tenant,
                role=User.TENANT_EMPLOYEE,
            )

        client.force_login(platform_admin)

        # Try to change role of user from different tenant
        url = reverse(
            "core:admin_tenant_user_change_role",
            kwargs={"tenant_pk": tenant.pk, "user_pk": other_user.pk},
        )
        response = client.post(url, {"role": User.TENANT_MANAGER})

        # Should return 404 (user not found in this tenant)
        assert response.status_code == 404

    def test_passwords_never_displayed(self, client, platform_admin, tenant, tenant_owner):
        """Test that passwords are never displayed in the interface."""
        client.force_login(platform_admin)
        url = reverse("core:admin_tenant_detail", kwargs={"pk": tenant.pk}) + "?tab=users"
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()

        # Ensure no password-related fields are displayed
        assert "password" not in content.lower() or "reset password" in content.lower()
        # The word "password" should only appear in "Reset Password" button
        assert content.lower().count("password") == content.lower().count("reset password")

    def test_all_actions_logged(self, client, platform_admin, tenant, tenant_employee, caplog):
        """Test that all user management actions are logged."""
        import logging

        caplog.set_level(logging.INFO)

        client.force_login(platform_admin)

        # Test password reset logging
        url = reverse(
            "core:admin_tenant_user_reset_password",
            kwargs={"tenant_pk": tenant.pk, "user_pk": tenant_employee.pk},
        )
        client.post(url)
        assert "Password reset initiated" in caplog.text

        # Test role change logging
        url = reverse(
            "core:admin_tenant_user_change_role",
            kwargs={"tenant_pk": tenant.pk, "user_pk": tenant_employee.pk},
        )
        client.post(url, {"role": User.TENANT_MANAGER})
        assert "User role changed" in caplog.text

        # Test toggle active logging
        url = reverse(
            "core:admin_tenant_user_toggle_active",
            kwargs={"tenant_pk": tenant.pk, "user_pk": tenant_employee.pk},
        )
        client.post(url)
        assert "deactivated" in caplog.text or "activated" in caplog.text
