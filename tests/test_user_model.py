"""
Tests for the extended User model.
"""

from django.contrib.auth import get_user_model

import pytest

from apps.core.models import Branch, Tenant

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    """Test User model functionality."""

    @pytest.fixture
    def tenant(self):
        """Create a test tenant."""
        return Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

    @pytest.fixture
    def branch(self, tenant):
        """Create a test branch."""
        return Branch.objects.create(
            tenant=tenant,
            name="Main Branch",
            address="123 Main St",
            phone="555-0100",
        )

    def test_create_platform_admin(self):
        """Test creating a platform administrator."""
        user = User.objects.create_user(
            username="admin",
            password="testpass123",
            email="admin@example.com",
            role=User.PLATFORM_ADMIN,
        )

        assert user.username == "admin"
        assert user.role == User.PLATFORM_ADMIN
        assert user.tenant is None
        assert user.branch is None
        assert user.is_platform_admin()

    def test_create_tenant_owner(self, tenant):
        """Test creating a tenant owner."""
        user = User.objects.create_user(
            username="owner",
            password="testpass123",
            email="owner@example.com",
            tenant=tenant,
            role=User.TENANT_OWNER,
        )

        assert user.username == "owner"
        assert user.role == User.TENANT_OWNER
        assert user.tenant == tenant
        assert user.is_tenant_owner()
        assert user.has_tenant_access()

    def test_create_tenant_manager(self, tenant, branch):
        """Test creating a tenant manager."""
        user = User.objects.create_user(
            username="manager",
            password="testpass123",
            email="manager@example.com",
            tenant=tenant,
            branch=branch,
            role=User.TENANT_MANAGER,
        )

        assert user.username == "manager"
        assert user.role == User.TENANT_MANAGER
        assert user.tenant == tenant
        assert user.branch == branch
        assert user.is_tenant_manager()
        assert user.has_tenant_access()

    def test_create_tenant_employee(self, tenant, branch):
        """Test creating a tenant employee."""
        user = User.objects.create_user(
            username="employee",
            password="testpass123",
            email="employee@example.com",
            tenant=tenant,
            branch=branch,
            role=User.TENANT_EMPLOYEE,
        )

        assert user.username == "employee"
        assert user.role == User.TENANT_EMPLOYEE
        assert user.tenant == tenant
        assert user.branch == branch
        assert user.is_tenant_employee()
        assert user.has_tenant_access()

    def test_user_language_preference(self, tenant):
        """Test user language preference."""
        user = User.objects.create_user(
            username="user_fa",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
            language=User.LANGUAGE_PERSIAN,
        )

        assert user.language == User.LANGUAGE_PERSIAN

    def test_user_theme_preference(self, tenant):
        """Test user theme preference."""
        user = User.objects.create_user(
            username="user_dark",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
            theme=User.THEME_DARK,
        )

        assert user.theme == User.THEME_DARK

    def test_user_phone_field(self, tenant):
        """Test user phone field."""
        user = User.objects.create_user(
            username="user_phone",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
            phone="+1234567890",
        )

        assert user.phone == "+1234567890"

    def test_user_mfa_enabled(self, tenant):
        """Test MFA enabled field."""
        user = User.objects.create_user(
            username="user_mfa",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
            is_mfa_enabled=True,
        )

        assert user.is_mfa_enabled is True

    def test_platform_admin_cannot_have_tenant(self):
        """Test that platform admin cannot have a tenant assigned."""
        tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test",
            status=Tenant.ACTIVE,
        )

        user = User.objects.create_user(
            username="admin",
            password="testpass123",
            tenant=tenant,
            role=User.PLATFORM_ADMIN,
        )

        # Tenant should be automatically set to None
        assert user.tenant is None
        assert user.branch is None

    def test_tenant_user_must_have_tenant(self):
        """Test that tenant users must have a tenant assigned."""
        with pytest.raises(ValueError, match="must have a tenant assigned"):
            User.objects.create_user(
                username="owner",
                password="testpass123",
                role=User.TENANT_OWNER,
                tenant=None,
            )

    def test_branch_must_belong_to_same_tenant(self, tenant):
        """Test that branch must belong to the same tenant as the user."""
        other_tenant = Tenant.objects.create(
            company_name="Other Shop",
            slug="other-shop",
            status=Tenant.ACTIVE,
        )

        other_branch = Branch.objects.create(
            tenant=other_tenant,
            name="Other Branch",
        )

        with pytest.raises(ValueError, match="Branch must belong to the same tenant"):
            User.objects.create_user(
                username="employee",
                password="testpass123",
                tenant=tenant,
                branch=other_branch,
                role=User.TENANT_EMPLOYEE,
            )

    def test_user_can_manage_users(self, tenant):
        """Test can_manage_users permission check."""
        owner = User.objects.create_user(
            username="owner",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_OWNER,
        )

        manager = User.objects.create_user(
            username="manager",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_MANAGER,
        )

        employee = User.objects.create_user(
            username="employee",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        assert owner.can_manage_users()
        assert manager.can_manage_users()
        assert not employee.can_manage_users()

    def test_user_can_manage_inventory(self, tenant):
        """Test can_manage_inventory permission check."""
        owner = User.objects.create_user(
            username="owner",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_OWNER,
        )

        manager = User.objects.create_user(
            username="manager",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_MANAGER,
        )

        employee = User.objects.create_user(
            username="employee",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        assert owner.can_manage_inventory()
        assert manager.can_manage_inventory()
        assert not employee.can_manage_inventory()

    def test_user_can_process_sales(self, tenant):
        """Test can_process_sales permission check."""
        owner = User.objects.create_user(
            username="owner",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_OWNER,
        )

        manager = User.objects.create_user(
            username="manager",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_MANAGER,
        )

        employee = User.objects.create_user(
            username="employee",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        admin = User.objects.create_user(
            username="admin",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

        assert owner.can_process_sales()
        assert manager.can_process_sales()
        assert employee.can_process_sales()
        assert not admin.can_process_sales()

    def test_user_string_representation(self, tenant):
        """Test user string representation."""
        user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        assert "testuser" in str(user)
        assert "Shop Employee" in str(user)
        assert tenant.company_name in str(user)

    def test_platform_admin_string_representation(self):
        """Test platform admin string representation."""
        admin = User.objects.create_user(
            username="admin",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

        assert "admin" in str(admin)
        assert "Platform Administrator" in str(admin)

    def test_user_default_values(self, tenant):
        """Test user default values."""
        user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            tenant=tenant,
            role=User.TENANT_EMPLOYEE,
        )

        assert user.language == User.LANGUAGE_ENGLISH
        assert user.theme == User.THEME_LIGHT
        assert user.is_mfa_enabled is False
        assert user.phone == ""


@pytest.mark.django_db
class TestBranchModel:
    """Test Branch model functionality."""

    @pytest.fixture
    def tenant(self):
        """Create a test tenant."""
        return Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-shop",
            status=Tenant.ACTIVE,
        )

    def test_create_branch(self, tenant):
        """Test creating a branch."""
        branch = Branch.objects.create(
            tenant=tenant,
            name="Main Branch",
            address="123 Main St",
            phone="555-0100",
        )

        assert branch.name == "Main Branch"
        assert branch.tenant == tenant
        assert branch.address == "123 Main St"
        assert branch.phone == "555-0100"
        assert branch.is_active is True

    def test_branch_string_representation(self, tenant):
        """Test branch string representation."""
        branch = Branch.objects.create(
            tenant=tenant,
            name="Main Branch",
        )

        assert "Main Branch" in str(branch)
        assert tenant.company_name in str(branch)

    def test_branch_unique_name_per_tenant(self, tenant):
        """Test that branch names must be unique per tenant."""
        Branch.objects.create(
            tenant=tenant,
            name="Main Branch",
        )

        # Creating another branch with the same name for the same tenant should fail
        with pytest.raises(Exception):  # IntegrityError
            Branch.objects.create(
                tenant=tenant,
                name="Main Branch",
            )

    def test_branch_same_name_different_tenant(self, tenant):
        """Test that branches can have the same name for different tenants."""
        other_tenant = Tenant.objects.create(
            company_name="Other Shop",
            slug="other-shop",
            status=Tenant.ACTIVE,
        )

        branch1 = Branch.objects.create(
            tenant=tenant,
            name="Main Branch",
        )

        branch2 = Branch.objects.create(
            tenant=other_tenant,
            name="Main Branch",
        )

        assert branch1.name == branch2.name
        assert branch1.tenant != branch2.tenant
