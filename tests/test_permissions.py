"""
Tests for role-based permissions and object-level permissions.

Tests cover:
- Role-based permission decorators
- Permission classes for DRF views
- Object-level permissions with django-guardian
- Permission mixins
- Permission utility functions
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import RequestFactory

import pytest
from guardian.shortcuts import assign_perm, get_objects_for_user, remove_perm
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.views import APIView

from apps.core.decorators import (
    platform_admin_required,
    role_required,
    tenant_access_required,
    tenant_manager_or_owner_required,
    tenant_owner_required,
)
from apps.core.models import Branch, Tenant
from apps.core.permissions import (
    CanManageInventory,
    CanManageUsers,
    CanProcessSales,
    HasTenantAccess,
    IsOwnerOrReadOnly,
    IsPlatformAdmin,
    IsSameTenant,
    IsTenantManager,
    IsTenantManagerOrOwner,
    IsTenantOwner,
    RoleRequiredMixin,
    TenantFilterMixin,
    check_role_permission,
    check_tenant_access,
)

User = get_user_model()


@pytest.fixture
def api_client():
    """Create an API client for testing."""
    return APIClient()


@pytest.fixture
def request_factory():
    """Create a request factory for testing."""
    return RequestFactory()


@pytest.fixture
def api_request_factory():
    """Create an API request factory for testing."""
    return APIRequestFactory()


@pytest.fixture
def tenant1(db):
    """Create first test tenant."""
    return Tenant.objects.create(
        company_name="Test Jewelry Shop 1",
        slug="test-shop-1",
        status=Tenant.ACTIVE,
    )


@pytest.fixture
def tenant2(db):
    """Create second test tenant."""
    return Tenant.objects.create(
        company_name="Test Jewelry Shop 2",
        slug="test-shop-2",
        status=Tenant.ACTIVE,
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
def tenant1_owner(db, tenant1):
    """Create a tenant owner for tenant1."""
    return User.objects.create_user(
        username="owner1",
        email="owner1@example.com",
        password="OwnerPassword123!@#",
        tenant=tenant1,
        role=User.TENANT_OWNER,
    )


@pytest.fixture
def tenant1_manager(db, tenant1):
    """Create a tenant manager for tenant1."""
    return User.objects.create_user(
        username="manager1",
        email="manager1@example.com",
        password="ManagerPassword123!@#",
        tenant=tenant1,
        role=User.TENANT_MANAGER,
    )


@pytest.fixture
def tenant1_employee(db, tenant1):
    """Create a tenant employee for tenant1."""
    return User.objects.create_user(
        username="employee1",
        email="employee1@example.com",
        password="EmployeePassword123!@#",
        tenant=tenant1,
        role=User.TENANT_EMPLOYEE,
    )


@pytest.fixture
def tenant2_owner(db, tenant2):
    """Create a tenant owner for tenant2."""
    return User.objects.create_user(
        username="owner2",
        email="owner2@example.com",
        password="OwnerPassword123!@#",
        tenant=tenant2,
        role=User.TENANT_OWNER,
    )


@pytest.fixture
def branch1(db, tenant1):
    """Create a branch for tenant1."""
    return Branch.objects.create(
        tenant=tenant1,
        name="Main Branch",
        address="123 Main St",
        phone="+1234567890",
    )


@pytest.fixture
def branch2(db, tenant2):
    """Create a branch for tenant2."""
    return Branch.objects.create(
        tenant=tenant2,
        name="Downtown Branch",
        address="456 Downtown Ave",
        phone="+0987654321",
    )


@pytest.mark.django_db
class TestRoleBasedDecorators:
    """Test role-based permission decorators."""

    def test_role_required_decorator_allows_correct_role(self, request_factory, tenant1_owner):
        """Test that role_required decorator allows users with correct role."""

        @role_required("TENANT_OWNER")
        def test_view(request):
            return {"status": "success"}

        request = request_factory.get("/test/")
        request.user = tenant1_owner

        response = test_view(request)
        assert response["status"] == "success"

    def test_role_required_decorator_denies_wrong_role(self, request_factory, tenant1_employee):
        """Test that role_required decorator denies users with wrong role."""

        @role_required("TENANT_OWNER")
        def test_view(request):
            return {"status": "success"}

        request = request_factory.get("/test/")
        request.user = tenant1_employee

        response = test_view(request)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_role_required_decorator_allows_multiple_roles(
        self, request_factory, tenant1_manager, tenant1_owner
    ):
        """Test that role_required decorator allows multiple roles."""

        @role_required("TENANT_OWNER", "TENANT_MANAGER")
        def test_view(request):
            return {"status": "success"}

        # Test with owner
        request = request_factory.get("/test/")
        request.user = tenant1_owner
        response = test_view(request)
        assert response["status"] == "success"

        # Test with manager
        request = request_factory.get("/test/")
        request.user = tenant1_manager
        response = test_view(request)
        assert response["status"] == "success"

    def test_platform_admin_required_decorator(self, request_factory, platform_admin):
        """Test platform_admin_required decorator."""

        @platform_admin_required
        def test_view(request):
            return {"status": "success"}

        request = request_factory.get("/test/")
        request.user = platform_admin

        response = test_view(request)
        assert response["status"] == "success"

    def test_platform_admin_required_denies_tenant_user(self, request_factory, tenant1_owner):
        """Test platform_admin_required decorator denies tenant users."""

        @platform_admin_required
        def test_view(request):
            return {"status": "success"}

        request = request_factory.get("/test/")
        request.user = tenant1_owner

        response = test_view(request)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_tenant_owner_required_decorator(self, request_factory, tenant1_owner):
        """Test tenant_owner_required decorator."""

        @tenant_owner_required
        def test_view(request):
            return {"status": "success"}

        request = request_factory.get("/test/")
        request.user = tenant1_owner

        response = test_view(request)
        assert response["status"] == "success"

    def test_tenant_manager_or_owner_required_decorator(
        self, request_factory, tenant1_manager, tenant1_owner
    ):
        """Test tenant_manager_or_owner_required decorator."""

        @tenant_manager_or_owner_required
        def test_view(request):
            return {"status": "success"}

        # Test with owner
        request = request_factory.get("/test/")
        request.user = tenant1_owner
        response = test_view(request)
        assert response["status"] == "success"

        # Test with manager
        request = request_factory.get("/test/")
        request.user = tenant1_manager
        response = test_view(request)
        assert response["status"] == "success"

    def test_tenant_access_required_decorator(self, request_factory, tenant1_employee):
        """Test tenant_access_required decorator."""

        @tenant_access_required
        def test_view(request):
            return {"status": "success"}

        request = request_factory.get("/test/")
        request.user = tenant1_employee

        response = test_view(request)
        assert response["status"] == "success"

    def test_tenant_access_required_denies_platform_admin(self, request_factory, platform_admin):
        """Test tenant_access_required decorator denies platform admin."""

        @tenant_access_required
        def test_view(request):
            return {"status": "success"}

        request = request_factory.get("/test/")
        request.user = platform_admin

        response = test_view(request)
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestPermissionClasses:
    """Test DRF permission classes."""

    def test_is_platform_admin_permission(self, api_request_factory, platform_admin, tenant1_owner):
        """Test IsPlatformAdmin permission class."""

        class TestView(APIView):
            permission_classes = [IsPlatformAdmin]

            def get(self, request):
                return Response({"status": "success"})

        view = TestView.as_view()

        # Test with platform admin - should succeed
        request = api_request_factory.get("/test/")
        request.user = platform_admin
        response = view(request)
        assert response.status_code == status.HTTP_200_OK

        # Test with tenant owner - should fail
        request = api_request_factory.get("/test/")
        request.user = tenant1_owner
        response = view(request)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_is_tenant_owner_permission(self, api_request_factory, tenant1_owner, tenant1_manager):
        """Test IsTenantOwner permission class."""

        class TestView(APIView):
            permission_classes = [IsTenantOwner]

            def get(self, request):
                return Response({"status": "success"})

        view = TestView.as_view()

        # Test with tenant owner - should succeed
        request = api_request_factory.get("/test/")
        request.user = tenant1_owner
        response = view(request)
        assert response.status_code == status.HTTP_200_OK

        # Test with tenant manager - should fail
        request = api_request_factory.get("/test/")
        request.user = tenant1_manager
        response = view(request)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_is_tenant_manager_permission(
        self, api_request_factory, tenant1_manager, tenant1_employee
    ):
        """Test IsTenantManager permission class."""

        class TestView(APIView):
            permission_classes = [IsTenantManager]

            def get(self, request):
                return Response({"status": "success"})

        view = TestView.as_view()

        # Test with tenant manager - should succeed
        request = api_request_factory.get("/test/")
        request.user = tenant1_manager
        response = view(request)
        assert response.status_code == status.HTTP_200_OK

        # Test with tenant employee - should fail
        request = api_request_factory.get("/test/")
        request.user = tenant1_employee
        response = view(request)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_is_tenant_manager_or_owner_permission(
        self, api_request_factory, tenant1_owner, tenant1_manager, tenant1_employee
    ):
        """Test IsTenantManagerOrOwner permission class."""

        class TestView(APIView):
            permission_classes = [IsTenantManagerOrOwner]

            def get(self, request):
                return Response({"status": "success"})

        view = TestView.as_view()

        # Test with tenant owner - should succeed
        request = api_request_factory.get("/test/")
        request.user = tenant1_owner
        response = view(request)
        assert response.status_code == status.HTTP_200_OK

        # Test with tenant manager - should succeed
        request = api_request_factory.get("/test/")
        request.user = tenant1_manager
        response = view(request)
        assert response.status_code == status.HTTP_200_OK

        # Test with tenant employee - should fail
        request = api_request_factory.get("/test/")
        request.user = tenant1_employee
        response = view(request)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_has_tenant_access_permission(
        self, api_request_factory, tenant1_employee, platform_admin
    ):
        """Test HasTenantAccess permission class."""

        class TestView(APIView):
            permission_classes = [HasTenantAccess]

            def get(self, request):
                return Response({"status": "success"})

        view = TestView.as_view()

        # Test with tenant employee - should succeed
        request = api_request_factory.get("/test/")
        request.user = tenant1_employee
        response = view(request)
        assert response.status_code == status.HTTP_200_OK

        # Test with platform admin - should fail
        request = api_request_factory.get("/test/")
        request.user = platform_admin
        response = view(request)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_can_manage_users_permission(
        self, api_request_factory, tenant1_owner, tenant1_employee
    ):
        """Test CanManageUsers permission class."""

        class TestView(APIView):
            permission_classes = [CanManageUsers]

            def get(self, request):
                return Response({"status": "success"})

        view = TestView.as_view()

        # Test with tenant owner - should succeed
        request = api_request_factory.get("/test/")
        request.user = tenant1_owner
        response = view(request)
        assert response.status_code == status.HTTP_200_OK

        # Test with tenant employee - should fail
        request = api_request_factory.get("/test/")
        request.user = tenant1_employee
        response = view(request)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_can_manage_inventory_permission(
        self, api_request_factory, tenant1_manager, tenant1_employee
    ):
        """Test CanManageInventory permission class."""

        class TestView(APIView):
            permission_classes = [CanManageInventory]

            def get(self, request):
                return Response({"status": "success"})

        view = TestView.as_view()

        # Test with tenant manager - should succeed
        request = api_request_factory.get("/test/")
        request.user = tenant1_manager
        response = view(request)
        assert response.status_code == status.HTTP_200_OK

        # Test with tenant employee - should fail
        request = api_request_factory.get("/test/")
        request.user = tenant1_employee
        response = view(request)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_can_process_sales_permission(self, api_request_factory, tenant1_employee):
        """Test CanProcessSales permission class."""

        class TestView(APIView):
            permission_classes = [CanProcessSales]

            def get(self, request):
                return Response({"status": "success"})

        view = TestView.as_view()

        # Test with tenant employee - should succeed
        request = api_request_factory.get("/test/")
        request.user = tenant1_employee
        response = view(request)
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestObjectLevelPermissions:
    """Test object-level permissions."""

    def test_is_same_tenant_permission_allows_same_tenant(
        self, api_request_factory, tenant1_owner, branch1
    ):
        """Test IsSameTenant allows access to objects from same tenant."""
        permission = IsSameTenant()

        request = api_request_factory.get("/test/")
        request.user = tenant1_owner

        # Should allow access to branch from same tenant
        assert permission.has_object_permission(request, None, branch1) is True

    def test_is_same_tenant_permission_denies_different_tenant(
        self, api_request_factory, tenant1_owner, branch2
    ):
        """Test IsSameTenant denies access to objects from different tenant."""
        permission = IsSameTenant()

        request = api_request_factory.get("/test/")
        request.user = tenant1_owner

        # Should deny access to branch from different tenant
        assert permission.has_object_permission(request, None, branch2) is False

    def test_is_same_tenant_permission_allows_platform_admin(
        self, api_request_factory, platform_admin, branch1, branch2
    ):
        """Test IsSameTenant allows platform admin to access all objects."""
        permission = IsSameTenant()

        request = api_request_factory.get("/test/")
        request.user = platform_admin

        # Platform admin should access any tenant's objects
        assert permission.has_object_permission(request, None, branch1) is True
        assert permission.has_object_permission(request, None, branch2) is True

    def test_is_owner_or_read_only_permission(self, api_request_factory, tenant1_owner):
        """Test IsOwnerOrReadOnly permission."""
        permission = IsOwnerOrReadOnly()

        # Create a mock object with owner
        class MockObject:
            def __init__(self, owner):
                self.owner = owner

        obj = MockObject(owner=tenant1_owner)

        # Test read access (GET)
        request = api_request_factory.get("/test/")
        request.user = tenant1_owner
        assert permission.has_object_permission(request, None, obj) is True

        # Test write access (POST) by owner
        request = api_request_factory.post("/test/")
        request.user = tenant1_owner
        assert permission.has_object_permission(request, None, obj) is True

        # Test write access (POST) by non-owner
        other_user = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="Password123!@#",
            tenant=tenant1_owner.tenant,
            role=User.TENANT_EMPLOYEE,
        )
        request = api_request_factory.post("/test/")
        request.user = other_user
        assert permission.has_object_permission(request, None, obj) is False


@pytest.mark.django_db
class TestGuardianIntegration:
    """Test django-guardian object-level permissions."""

    def test_assign_and_check_object_permission(self, tenant1_owner, branch1):
        """Test assigning and checking object-level permissions."""
        # Assign permission
        assign_perm("view_branch", tenant1_owner, branch1)

        # Check permission
        assert tenant1_owner.has_perm("core.view_branch", branch1)

    def test_remove_object_permission(self, tenant1_owner, branch1):
        """Test removing object-level permissions."""
        # Assign permission
        assign_perm("view_branch", tenant1_owner, branch1)
        assert tenant1_owner.has_perm("core.view_branch", branch1)

        # Remove permission
        remove_perm("view_branch", tenant1_owner, branch1)
        assert not tenant1_owner.has_perm("core.view_branch", branch1)

    def test_get_objects_for_user(self, tenant1_owner, tenant1_manager, branch1, branch2):
        """Test getting objects user has permission for."""
        # Assign permissions
        assign_perm("view_branch", tenant1_owner, branch1)
        assign_perm("view_branch", tenant1_manager, branch1)

        # Get objects for owner
        owner_branches = get_objects_for_user(tenant1_owner, "core.view_branch", Branch)
        assert branch1 in owner_branches
        assert branch2 not in owner_branches

        # Get objects for manager
        manager_branches = get_objects_for_user(tenant1_manager, "core.view_branch", Branch)
        assert branch1 in manager_branches
        assert branch2 not in manager_branches


@pytest.mark.django_db
class TestPermissionMixins:
    """Test permission mixins."""

    def test_role_required_mixin(self, api_request_factory, tenant1_owner, tenant1_employee):
        """Test RoleRequiredMixin."""

        class TestView(RoleRequiredMixin, APIView):
            required_roles = ["TENANT_OWNER"]

            def get(self, request):
                return Response({"status": "success"})

        view = TestView.as_view()

        # Test with correct role
        request = api_request_factory.get("/test/")
        request.user = tenant1_owner
        response = view(request)
        assert response.status_code == status.HTTP_200_OK

        # Test with incorrect role
        request = api_request_factory.get("/test/")
        request.user = tenant1_employee
        response = view(request)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_tenant_filter_mixin_filters_by_tenant(
        self, api_request_factory, tenant1_owner, tenant2_owner
    ):
        """Test TenantFilterMixin filters queryset by tenant."""
        from rest_framework.generics import ListAPIView

        class TestView(TenantFilterMixin, ListAPIView):
            queryset = Branch.objects.all()

        view = TestView()

        # Test with tenant1 owner
        request = api_request_factory.get("/test/")
        request.user = tenant1_owner
        view.request = request
        queryset = view.get_queryset()

        # Should only see tenant1 branches
        assert queryset.filter(tenant=tenant1_owner.tenant).count() == queryset.count()

    def test_tenant_filter_mixin_allows_platform_admin_all_access(
        self, api_request_factory, platform_admin, branch1, branch2
    ):
        """Test TenantFilterMixin allows platform admin to see all objects."""
        from rest_framework.generics import ListAPIView

        class TestView(TenantFilterMixin, ListAPIView):
            queryset = Branch.objects.all()

        view = TestView()

        # Test with platform admin
        request = api_request_factory.get("/test/")
        request.user = platform_admin
        view.request = request
        queryset = view.get_queryset()

        # Should see all branches
        assert queryset.count() == Branch.objects.count()


@pytest.mark.django_db
class TestUtilityFunctions:
    """Test permission utility functions."""

    def test_check_role_permission(self, tenant1_owner, tenant1_employee):
        """Test check_role_permission utility function."""
        # Test with correct role
        assert check_role_permission(tenant1_owner, "TENANT_OWNER") is True
        assert check_role_permission(tenant1_owner, "TENANT_OWNER", "TENANT_MANAGER") is True

        # Test with incorrect role
        assert check_role_permission(tenant1_employee, "TENANT_OWNER") is False
        assert check_role_permission(tenant1_employee, "TENANT_OWNER", "TENANT_MANAGER") is False

    def test_check_tenant_access(self, tenant1_owner, branch1, branch2, platform_admin):
        """Test check_tenant_access utility function."""
        # Test with same tenant
        assert check_tenant_access(tenant1_owner, branch1) is True

        # Test with different tenant
        assert check_tenant_access(tenant1_owner, branch2) is False

        # Test with platform admin
        assert check_tenant_access(platform_admin, branch1) is True
        assert check_tenant_access(platform_admin, branch2) is True


@pytest.mark.django_db
class TestPermissionGroups:
    """Test permission groups setup."""

    def test_permission_groups_exist(self):
        """Test that permission groups are created."""
        # Run the setup command
        from django.core.management import call_command

        call_command("setup_permissions")

        # Check that groups exist
        assert Group.objects.filter(name="Platform Administrators").exists()
        assert Group.objects.filter(name="Tenant Owners").exists()
        assert Group.objects.filter(name="Tenant Managers").exists()
        assert Group.objects.filter(name="Tenant Employees").exists()

    def test_platform_admin_group_permissions(self):
        """Test Platform Administrator group has correct permissions."""
        from django.core.management import call_command

        call_command("setup_permissions")

        group = Group.objects.get(name="Platform Administrators")
        permissions = group.permissions.all()

        # Should have permissions for tenants, users, and branches
        assert permissions.filter(codename__contains="tenant").exists()
        assert permissions.filter(codename__contains="user").exists()
        assert permissions.filter(codename__contains="branch").exists()

    def test_tenant_owner_group_permissions(self):
        """Test Tenant Owner group has correct permissions."""
        from django.core.management import call_command

        call_command("setup_permissions")

        group = Group.objects.get(name="Tenant Owners")
        permissions = group.permissions.all()

        # Should have full user and branch permissions
        assert permissions.filter(codename="add_user").exists()
        assert permissions.filter(codename="change_user").exists()
        assert permissions.filter(codename="delete_user").exists()
        assert permissions.filter(codename="view_user").exists()

    def test_tenant_manager_group_permissions(self):
        """Test Tenant Manager group has correct permissions."""
        from django.core.management import call_command

        call_command("setup_permissions")

        group = Group.objects.get(name="Tenant Managers")
        permissions = group.permissions.all()

        # Should have limited user permissions
        assert permissions.filter(codename="change_user").exists()
        assert permissions.filter(codename="view_user").exists()
        # Should not have delete permission
        assert not permissions.filter(codename="delete_user").exists()

    def test_tenant_employee_group_permissions(self):
        """Test Tenant Employee group has correct permissions."""
        from django.core.management import call_command

        call_command("setup_permissions")

        group = Group.objects.get(name="Tenant Employees")
        permissions = group.permissions.all()

        # Should only have view permissions
        assert permissions.filter(codename="view_user").exists()
        assert permissions.filter(codename="view_branch").exists()
        # Should not have add, change, or delete permissions
        assert not permissions.filter(codename="add_user").exists()
        assert not permissions.filter(codename="change_user").exists()
        assert not permissions.filter(codename="delete_user").exists()


@pytest.mark.django_db
class TestBranchBasedPermissions:
    """Test branch-based access control."""

    def test_is_same_branch_permission_allows_same_branch(
        self, api_request_factory, tenant1_employee, branch1
    ):
        """Test IsSameBranch allows access to objects from same branch."""
        from apps.core.permissions import IsSameBranch

        # Assign user to branch
        tenant1_employee.branch = branch1
        tenant1_employee.save()

        permission = IsSameBranch()

        # Create mock object with branch
        class MockObject:
            def __init__(self, branch):
                self.branch = branch

        obj = MockObject(branch=branch1)

        request = api_request_factory.get("/test/")
        request.user = tenant1_employee

        # Should allow access to object from same branch
        assert permission.has_object_permission(request, None, obj) is True

    def test_is_same_branch_permission_denies_different_branch(
        self, api_request_factory, tenant1_employee, branch1, branch2
    ):
        """Test IsSameBranch denies access to objects from different branch."""
        from apps.core.permissions import IsSameBranch

        # Assign user to branch1
        tenant1_employee.branch = branch1
        tenant1_employee.save()

        permission = IsSameBranch()

        # Create mock object with branch2
        class MockObject:
            def __init__(self, branch):
                self.branch = branch

        obj = MockObject(branch=branch2)

        request = api_request_factory.get("/test/")
        request.user = tenant1_employee

        # Should deny access to object from different branch
        assert permission.has_object_permission(request, None, obj) is False

    def test_is_same_branch_permission_allows_owner_all_branches(
        self, api_request_factory, tenant1_owner, branch1
    ):
        """Test IsSameBranch allows tenant owner to access all branches."""
        from apps.core.permissions import IsSameBranch

        permission = IsSameBranch()

        class MockObject:
            def __init__(self, branch):
                self.branch = branch

        obj = MockObject(branch=branch1)

        request = api_request_factory.get("/test/")
        request.user = tenant1_owner

        # Tenant owner should access any branch in their tenant
        assert permission.has_object_permission(request, None, obj) is True

    def test_is_same_branch_permission_allows_platform_admin(
        self, api_request_factory, platform_admin, branch1, branch2
    ):
        """Test IsSameBranch allows platform admin to access all branches."""
        from apps.core.permissions import IsSameBranch

        permission = IsSameBranch()

        class MockObject:
            def __init__(self, branch):
                self.branch = branch

        request = api_request_factory.get("/test/")
        request.user = platform_admin

        # Platform admin should access any branch
        assert permission.has_object_permission(request, None, MockObject(branch1)) is True
        assert permission.has_object_permission(request, None, MockObject(branch2)) is True

    def test_check_branch_access_utility(self, tenant1_employee, branch1, branch2):
        """Test check_branch_access utility function."""
        from apps.core.permissions import check_branch_access

        # Assign user to branch1
        tenant1_employee.branch = branch1
        tenant1_employee.save()

        class MockObject:
            def __init__(self, branch):
                self.branch = branch

        obj1 = MockObject(branch=branch1)
        obj2 = MockObject(branch=branch2)

        # Should allow access to same branch
        assert check_branch_access(tenant1_employee, obj1) is True

        # Should deny access to different branch
        assert check_branch_access(tenant1_employee, obj2) is False


@pytest.mark.django_db
class TestPermissionAuditLogging:
    """Test permission audit logging."""

    def test_role_change_audit_log(self, tenant1_owner, tenant1_employee):
        """Test that role changes are logged."""
        from apps.core.audit import log_role_change
        from apps.core.models import PermissionAuditLog

        old_role = tenant1_employee.role
        new_role = User.TENANT_MANAGER

        log_role_change(
            actor=tenant1_owner,
            target_user=tenant1_employee,
            old_role=old_role,
            new_role=new_role,
        )

        # Verify log was created
        logs = PermissionAuditLog.objects.filter(
            target_user=tenant1_employee, action=PermissionAuditLog.ROLE_CHANGED
        )
        assert logs.count() == 1

        log = logs.first()
        assert log.actor == tenant1_owner
        assert log.old_value == old_role
        assert log.new_value == new_role

    def test_permission_grant_audit_log(self, tenant1_owner, tenant1_employee):
        """Test that permission grants are logged."""
        from apps.core.audit import log_permission_grant
        from apps.core.models import PermissionAuditLog

        log_permission_grant(
            actor=tenant1_owner, target_user=tenant1_employee, permission="view_inventory"
        )

        # Verify log was created
        logs = PermissionAuditLog.objects.filter(
            target_user=tenant1_employee, action=PermissionAuditLog.PERMISSION_GRANTED
        )
        assert logs.count() == 1

        log = logs.first()
        assert log.actor == tenant1_owner
        assert "view_inventory" in log.description

    def test_permission_revoke_audit_log(self, tenant1_owner, tenant1_employee):
        """Test that permission revocations are logged."""
        from apps.core.audit import log_permission_revoke
        from apps.core.models import PermissionAuditLog

        log_permission_revoke(
            actor=tenant1_owner, target_user=tenant1_employee, permission="delete_inventory"
        )

        # Verify log was created
        logs = PermissionAuditLog.objects.filter(
            target_user=tenant1_employee, action=PermissionAuditLog.PERMISSION_REVOKED
        )
        assert logs.count() == 1

        log = logs.first()
        assert log.actor == tenant1_owner
        assert "delete_inventory" in log.description

    def test_group_assignment_audit_log(self, tenant1_owner, tenant1_employee):
        """Test that group assignments are logged."""
        from django.contrib.auth.models import Group

        from apps.core.audit import log_group_assignment
        from apps.core.models import PermissionAuditLog

        group = Group.objects.create(name="Test Group")

        log_group_assignment(
            actor=tenant1_owner, target_user=tenant1_employee, group=group, added=True
        )

        # Verify log was created
        logs = PermissionAuditLog.objects.filter(
            target_user=tenant1_employee, action=PermissionAuditLog.GROUP_ADDED
        )
        assert logs.count() == 1

        log = logs.first()
        assert log.actor == tenant1_owner
        assert group.name in log.description

    def test_branch_assignment_audit_log(self, tenant1_owner, tenant1_employee, branch1):
        """Test that branch assignments are logged."""
        from apps.core.audit import log_branch_assignment
        from apps.core.models import PermissionAuditLog

        log_branch_assignment(
            actor=tenant1_owner, target_user=tenant1_employee, branch=branch1, assigned=True
        )

        # Verify log was created
        logs = PermissionAuditLog.objects.filter(
            target_user=tenant1_employee, action=PermissionAuditLog.BRANCH_ASSIGNED
        )
        assert logs.count() == 1

        log = logs.first()
        assert log.actor == tenant1_owner
        assert branch1.name in log.description

    def test_audit_log_includes_ip_and_user_agent(
        self, tenant1_owner, tenant1_employee, request_factory
    ):
        """Test that audit logs capture IP address and user agent."""
        from apps.core.audit import log_role_change
        from apps.core.models import PermissionAuditLog

        # Create a mock request with IP and user agent
        request = request_factory.get("/test/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.META["HTTP_USER_AGENT"] = "Mozilla/5.0 Test Browser"

        log_role_change(
            actor=tenant1_owner,
            target_user=tenant1_employee,
            old_role=User.TENANT_EMPLOYEE,
            new_role=User.TENANT_MANAGER,
            request=request,
        )

        log = PermissionAuditLog.objects.filter(target_user=tenant1_employee).first()
        assert log.ip_address == "192.168.1.1"
        assert log.user_agent == "Mozilla/5.0 Test Browser"

    def test_audit_log_ordering(self, tenant1_owner, tenant1_employee):
        """Test that audit logs are ordered by timestamp descending."""
        from apps.core.audit import log_role_change
        from apps.core.models import PermissionAuditLog

        # Create multiple logs
        log_role_change(tenant1_owner, tenant1_employee, "ROLE1", "ROLE2")
        log_role_change(tenant1_owner, tenant1_employee, "ROLE2", "ROLE3")
        log_role_change(tenant1_owner, tenant1_employee, "ROLE3", "ROLE4")

        logs = PermissionAuditLog.objects.filter(target_user=tenant1_employee)

        # Should be ordered newest first
        assert logs[0].new_value == "ROLE4"
        assert logs[1].new_value == "ROLE3"
        assert logs[2].new_value == "ROLE2"
