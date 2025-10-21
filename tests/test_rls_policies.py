"""
Tests for PostgreSQL Row-Level Security (RLS) policies.

This test suite validates the RLS implementation for multi-tenant data isolation:
- RLS is enabled on tenant-scoped tables
- set_tenant_context() function works correctly
- RLS policies filter data based on current_setting('app.current_tenant')
- Tenant isolation is enforced at the database level
- Platform admins can bypass RLS when needed

Requirements: Requirement 1 - Multi-Tenant Architecture with Data Isolation
"""

import uuid

from django.db import connection
from django.test import TestCase

import pytest

from apps.core.models import Tenant
from apps.core.tenant_context import (
    bypass_rls,
    clear_tenant_context,
    disable_rls_bypass,
    enable_rls_bypass,
    get_current_tenant,
    is_rls_bypassed,
    set_tenant_context,
    tenant_context,
)


@pytest.mark.django_db
class TestRLSFunctions(TestCase):
    """Test PostgreSQL RLS helper functions."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing context
        clear_tenant_context()

    def tearDown(self):
        """Clean up after tests."""
        clear_tenant_context()

    def test_set_tenant_context_function_exists(self):
        """Test that set_tenant_context() PostgreSQL function exists."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_proc
                    WHERE proname = 'set_tenant_context'
                );
            """
            )
            result = cursor.fetchone()

        assert result[0] is True

    def test_get_current_tenant_function_exists(self):
        """Test that get_current_tenant() PostgreSQL function exists."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_proc
                    WHERE proname = 'get_current_tenant'
                );
            """
            )
            result = cursor.fetchone()

        assert result[0] is True

    def test_is_rls_bypassed_function_exists(self):
        """Test that is_rls_bypassed() PostgreSQL function exists."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_proc
                    WHERE proname = 'is_rls_bypassed'
                );
            """
            )
            result = cursor.fetchone()

        assert result[0] is True

    def test_set_and_get_tenant_context(self):
        """Test setting and getting tenant context."""
        tenant_id = uuid.uuid4()

        # Set tenant context
        set_tenant_context(tenant_id)

        # Get tenant context
        current_tenant = get_current_tenant()

        assert current_tenant == tenant_id

    def test_clear_tenant_context(self):
        """Test clearing tenant context."""
        tenant_id = uuid.uuid4()

        # Set tenant context
        set_tenant_context(tenant_id)
        assert get_current_tenant() == tenant_id

        # Clear context
        set_tenant_context(None)
        assert get_current_tenant() is None

    def test_enable_and_check_rls_bypass(self):
        """Test enabling RLS bypass."""
        # Initially should be disabled
        assert is_rls_bypassed() is False

        # Enable bypass
        enable_rls_bypass()
        assert is_rls_bypassed() is True

        # Disable bypass
        disable_rls_bypass()
        assert is_rls_bypassed() is False


@pytest.mark.django_db
class TestRLSEnabled(TestCase):
    """Test that RLS is enabled on tenant-scoped tables."""

    def test_rls_enabled_on_tenants_table(self):
        """Test that RLS is enabled on the tenants table."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT relrowsecurity
                FROM pg_class
                WHERE relname = 'tenants';
            """
            )
            result = cursor.fetchone()

        assert result is not None
        assert result[0] is True  # relrowsecurity should be True

    def test_rls_policies_exist_on_tenants_table(self):
        """Test that RLS policies exist on the tenants table."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM pg_policies
                WHERE tablename = 'tenants';
            """
            )
            result = cursor.fetchone()

        # Should have 4 policies: SELECT, INSERT, UPDATE, DELETE
        assert result[0] >= 4


@pytest.mark.django_db(transaction=True)
class TestTenantIsolation(TestCase):
    """Test tenant data isolation through RLS policies."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing context
        clear_tenant_context()

        # Create test tenants with RLS bypass enabled
        enable_rls_bypass()
        self.tenant1 = Tenant.objects.create(
            company_name="Isolation Tenant 1", slug="isolation-tenant-1", status=Tenant.ACTIVE
        )
        self.tenant2 = Tenant.objects.create(
            company_name="Isolation Tenant 2", slug="isolation-tenant-2", status=Tenant.ACTIVE
        )
        self.tenant3 = Tenant.objects.create(
            company_name="Isolation Tenant 3", slug="isolation-tenant-3", status=Tenant.SUSPENDED
        )
        # Important: Clear context after creating test data
        clear_tenant_context()

    def tearDown(self):
        """Clean up after tests."""
        # Don't try to clear context if transaction is broken
        # Django's TestCase will handle the rollback
        try:
            clear_tenant_context()
        except Exception:
            pass  # Ignore errors in tearDown if transaction is broken

    def test_tenant_can_only_see_own_record(self):
        """Test that a tenant can only see their own record."""
        # Set context to tenant1
        set_tenant_context(self.tenant1.id)

        # Query all tenants
        tenants = Tenant.objects.all()

        # Should only see tenant1
        assert tenants.count() == 1
        assert tenants.first().id == self.tenant1.id

    def test_different_tenants_see_different_data(self):
        """Test that different tenants see different data."""
        # Set context to tenant1
        set_tenant_context(self.tenant1.id)
        tenant1_data = list(Tenant.objects.all())

        # Set context to tenant2
        set_tenant_context(self.tenant2.id)
        tenant2_data = list(Tenant.objects.all())

        # Each should see only their own data
        assert len(tenant1_data) == 1
        assert len(tenant2_data) == 1
        assert tenant1_data[0].id != tenant2_data[0].id

    def test_no_tenant_context_returns_no_data(self):
        """Test that queries without tenant context return no data."""
        # Clear tenant context
        clear_tenant_context()

        # Query should return no results
        tenants = Tenant.objects.all()
        assert tenants.count() == 0

    def test_tenant_cannot_access_other_tenant_data(self):
        """Test that a tenant cannot access another tenant's data."""
        # Set context to tenant1
        set_tenant_context(self.tenant1.id)

        # Try to get tenant2 by ID
        with pytest.raises(Tenant.DoesNotExist):
            Tenant.objects.get(id=self.tenant2.id)

    def test_tenant_can_update_own_record(self):
        """Test that a tenant can update their own record."""
        # Set context to tenant1
        set_tenant_context(self.tenant1.id)

        # Update tenant1
        tenant = Tenant.objects.get(id=self.tenant1.id)
        tenant.company_name = "Updated Tenant 1"
        tenant.save()

        # Verify update
        tenant.refresh_from_db()
        assert tenant.company_name == "Updated Tenant 1"

    def test_tenant_cannot_update_other_tenant_record(self):
        """Test that a tenant cannot update another tenant's record."""
        # Set context to tenant1
        set_tenant_context(self.tenant1.id)

        # Try to update tenant2 (should fail because we can't even see it)
        with pytest.raises(Tenant.DoesNotExist):
            tenant = Tenant.objects.get(id=self.tenant2.id)
            tenant.company_name = "Hacked Tenant 2"
            tenant.save()


@pytest.mark.django_db(transaction=True)
class TestRLSBypass(TestCase):
    """Test RLS bypass functionality for platform admins."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing context
        clear_tenant_context()

        # Create test tenants with RLS bypass enabled
        enable_rls_bypass()
        self.tenant1 = Tenant.objects.create(
            company_name="Bypass Tenant 1", slug="bypass-tenant-1", status=Tenant.ACTIVE
        )
        self.tenant2 = Tenant.objects.create(
            company_name="Bypass Tenant 2", slug="bypass-tenant-2", status=Tenant.ACTIVE
        )
        # Important: Clear context after creating test data
        clear_tenant_context()

    def tearDown(self):
        """Clean up after tests."""
        # Don't try to clear context if transaction is broken
        # Django's TestCase will handle the rollback
        try:
            clear_tenant_context()
        except Exception:
            pass  # Ignore errors in tearDown if transaction is broken

    def test_bypass_rls_allows_access_to_all_tenants(self):
        """Test that enabling RLS bypass allows access to all tenant data."""
        # Enable RLS bypass (platform admin mode)
        enable_rls_bypass()

        # Query all tenants
        tenants = Tenant.objects.all()

        # Should see all tenants
        assert tenants.count() >= 2
        tenant_ids = [t.id for t in tenants]
        assert self.tenant1.id in tenant_ids
        assert self.tenant2.id in tenant_ids

    def test_bypass_rls_context_manager(self):
        """Test the bypass_rls context manager."""
        # Set tenant context first
        set_tenant_context(self.tenant1.id)

        # Without bypass, should only see tenant1
        assert Tenant.objects.count() == 1

        # With bypass context manager
        with bypass_rls():
            # Should see all tenants
            assert Tenant.objects.count() >= 2

        # After exiting context, should be back to tenant1 only
        assert Tenant.objects.count() == 1

    def test_platform_admin_can_create_tenants(self):
        """Test that platform admins can create new tenants."""
        # Enable RLS bypass
        enable_rls_bypass()

        # Create a new tenant
        new_tenant = Tenant.objects.create(
            company_name="New Tenant", slug="new-tenant", status=Tenant.ACTIVE
        )

        assert new_tenant.id is not None
        assert new_tenant.company_name == "New Tenant"

    def test_tenant_cannot_create_other_tenants(self):
        """Test that regular tenants cannot create new tenants."""
        # Set context to tenant1 (not admin)
        set_tenant_context(self.tenant1.id)

        # Try to create a new tenant (should fail due to RLS policy)
        # Note: This will raise an exception at the database level
        from django.db.utils import DatabaseError

        with pytest.raises(DatabaseError):
            Tenant.objects.create(
                company_name="Unauthorized Tenant",
                slug="unauthorized-tenant",
                status=Tenant.ACTIVE,
            )


@pytest.mark.django_db(transaction=True)
class TestTenantContextManager(TestCase):
    """Test the tenant_context context manager."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing context
        clear_tenant_context()

        # Create test tenants with RLS bypass enabled
        enable_rls_bypass()
        self.tenant1 = Tenant.objects.create(
            company_name="Context Tenant 1", slug="context-tenant-1", status=Tenant.ACTIVE
        )
        self.tenant2 = Tenant.objects.create(
            company_name="Context Tenant 2", slug="context-tenant-2", status=Tenant.ACTIVE
        )
        # Important: Clear context after creating test data
        clear_tenant_context()

    def tearDown(self):
        """Clean up after tests."""
        # Don't try to clear context if transaction is broken
        # Django's TestCase will handle the rollback
        try:
            clear_tenant_context()
        except Exception:
            pass  # Ignore errors in tearDown if transaction is broken

    def test_tenant_context_manager_sets_and_restores_context(self):
        """Test that tenant_context manager sets and restores context."""
        # Set initial context to tenant1
        set_tenant_context(self.tenant1.id)
        assert get_current_tenant() == self.tenant1.id

        # Use context manager to temporarily switch to tenant2
        with tenant_context(self.tenant2.id):
            assert get_current_tenant() == self.tenant2.id
            # Should only see tenant2
            assert Tenant.objects.count() == 1
            assert Tenant.objects.first().id == self.tenant2.id

        # After exiting, should be back to tenant1
        assert get_current_tenant() == self.tenant1.id
        assert Tenant.objects.count() == 1
        assert Tenant.objects.first().id == self.tenant1.id

    def test_tenant_context_manager_with_none(self):
        """Test tenant_context manager with None clears context."""
        # Set initial context
        set_tenant_context(self.tenant1.id)
        assert get_current_tenant() == self.tenant1.id

        # Use context manager with None
        with tenant_context(None):
            assert get_current_tenant() is None
            # Should see no tenants
            assert Tenant.objects.count() == 0

        # After exiting, should be back to tenant1
        assert get_current_tenant() == self.tenant1.id

    def test_nested_tenant_contexts(self):
        """Test nested tenant context managers."""
        # Set initial context to tenant1
        set_tenant_context(self.tenant1.id)

        with tenant_context(self.tenant2.id):
            assert get_current_tenant() == self.tenant2.id

            with tenant_context(None):
                assert get_current_tenant() is None

            # Back to tenant2
            assert get_current_tenant() == self.tenant2.id

        # Back to tenant1
        assert get_current_tenant() == self.tenant1.id


@pytest.mark.django_db(transaction=True)
class TestRLSPolicyDetails(TestCase):
    """Test specific RLS policy behaviors."""

    def setUp(self):
        """Set up test fixtures."""
        clear_tenant_context()

        # Create test tenant with RLS bypass
        enable_rls_bypass()
        self.tenant = Tenant.objects.create(
            company_name="Policy Test Tenant", slug="policy-test-tenant", status=Tenant.ACTIVE
        )
        # Important: Clear context after creating test data
        clear_tenant_context()

    def tearDown(self):
        """Clean up after tests."""
        # Don't try to clear context if transaction is broken
        # Django's TestCase will handle the rollback
        try:
            clear_tenant_context()
        except Exception:
            pass  # Ignore errors in tearDown if transaction is broken

    def test_select_policy_filters_by_tenant_id(self):
        """Test that SELECT policy filters by tenant_id."""
        # Set tenant context
        set_tenant_context(self.tenant.id)

        # Query should return only this tenant
        tenants = Tenant.objects.all()
        assert tenants.count() == 1
        assert tenants.first().id == self.tenant.id

    def test_insert_policy_requires_bypass(self):
        """Test that INSERT policy requires RLS bypass."""
        # Set tenant context (not admin)
        set_tenant_context(self.tenant.id)

        # Try to insert without bypass (should fail with RLS policy violation)
        from django.db.utils import DatabaseError

        with pytest.raises(DatabaseError):
            Tenant.objects.create(
                company_name="New Tenant", slug="new-tenant-unique", status=Tenant.ACTIVE
            )

    def test_update_policy_allows_own_record(self):
        """Test that UPDATE policy allows updating own record."""
        # Set tenant context
        set_tenant_context(self.tenant.id)

        # Update own record
        tenant = Tenant.objects.get(id=self.tenant.id)
        tenant.company_name = "Updated Name"
        tenant.save()

        # Verify update
        tenant.refresh_from_db()
        assert tenant.company_name == "Updated Name"

    def test_delete_policy_requires_bypass(self):
        """Test that DELETE policy requires RLS bypass."""
        # Set tenant context (not admin)
        set_tenant_context(self.tenant.id)

        # Get the tenant (we can see it via SELECT policy)
        tenant = Tenant.objects.get(id=self.tenant.id)
        tenant_id = tenant.id

        # Try to delete without bypass
        # The DELETE policy blocks deletion, but Django doesn't raise an error
        # Instead, the delete() returns (0, {}) indicating nothing was deleted
        deleted_count, _ = tenant.delete()

        # Verify nothing was deleted (RLS blocked it)
        assert deleted_count == 0

        # Verify tenant still exists (can see it because SELECT policy allows it)
        assert Tenant.objects.filter(id=tenant_id).exists()

    def test_admin_can_delete_with_bypass(self):
        """Test that admin can delete tenants with RLS bypass."""
        # Enable bypass
        enable_rls_bypass()

        # Delete tenant
        tenant_id = self.tenant.id
        self.tenant.delete()

        # Verify deletion
        assert not Tenant.objects.filter(id=tenant_id).exists()
