"""
Comprehensive RLS Isolation Tests for Multi-Tenant Data Isolation.

This test suite validates complete tenant isolation through PostgreSQL Row-Level Security:
- Tenants cannot access other tenant's data across all models
- RLS policy enforcement on all tenant-scoped models
- Tenant context switching works correctly
- Cross-tenant data leakage is prevented
- RLS bypass works correctly for platform admins

Requirements: Requirement 1, 28 - Multi-Tenant Architecture with Data Isolation
"""

import uuid

from django.db import connection, models
from django.test import TestCase, TransactionTestCase

import pytest

from apps.core.models import Tenant
from apps.core.tenant_context import (
    bypass_rls,
    clear_tenant_context,
    disable_rls_bypass,
    enable_rls_bypass,
    get_current_tenant,
    set_tenant_context,
    tenant_context,
)


# Create a mock tenant-scoped model for testing RLS on non-Tenant tables
class MockTenantScopedModel(models.Model):
    """
    Mock model to test RLS on tenant-scoped tables.
    This simulates inventory, sales, or any other tenant-scoped data.
    """

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    value = models.IntegerField(default=0)

    class Meta:
        app_label = "core"
        db_table = "test_tenant_scoped_data"


@pytest.mark.django_db(transaction=True)
class TestRLSIsolationComprehensive(TransactionTestCase):
    """
    Comprehensive test suite for RLS isolation across all tenant-scoped models.
    """

    def _ensure_rls_enabled(self):
        """Helper to ensure RLS is enabled and bypass is disabled."""
        # Force disable bypass using direct SQL
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.bypass_rls', 'false', false);")
            cursor.execute("SELECT set_config('app.current_tenant', NULL, false);")

    @classmethod
    def setUpClass(cls):
        """Set up test database table for mock model."""
        super().setUpClass()

        # Create the test table with RLS enabled
        with connection.cursor() as cursor:
            # Drop table if exists
            cursor.execute("DROP TABLE IF EXISTS test_tenant_scoped_data CASCADE;")

            # Create table
            cursor.execute(
                """
                CREATE TABLE test_tenant_scoped_data (
                    id SERIAL PRIMARY KEY,
                    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    value INTEGER DEFAULT 0
                );
            """
            )

            # Enable RLS
            cursor.execute("ALTER TABLE test_tenant_scoped_data ENABLE ROW LEVEL SECURITY;")

            # Force RLS even for table owner (important for test database)
            cursor.execute("ALTER TABLE test_tenant_scoped_data FORCE ROW LEVEL SECURITY;")

            # Create RLS policies
            cursor.execute(
                """
                CREATE POLICY tenant_isolation_policy ON test_tenant_scoped_data
                    USING (
                        tenant_id = get_current_tenant()
                        OR is_rls_bypassed()
                    );
            """
            )

            cursor.execute(
                """
                CREATE POLICY tenant_insert_policy ON test_tenant_scoped_data
                    FOR INSERT
                    WITH CHECK (
                        tenant_id = get_current_tenant()
                        OR is_rls_bypassed()
                    );
            """
            )

            cursor.execute(
                """
                CREATE POLICY tenant_update_policy ON test_tenant_scoped_data
                    FOR UPDATE
                    USING (
                        tenant_id = get_current_tenant()
                        OR is_rls_bypassed()
                    );
            """
            )

            cursor.execute(
                """
                CREATE POLICY tenant_delete_policy ON test_tenant_scoped_data
                    FOR DELETE
                    USING (
                        tenant_id = get_current_tenant()
                        OR is_rls_bypassed()
                    );
            """
            )

    @classmethod
    def tearDownClass(cls):
        """Clean up test database table."""
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS test_tenant_scoped_data CASCADE;")
        super().tearDownClass()

    def setUp(self):
        """Set up test fixtures."""
        # Force clear any existing state
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.current_tenant', NULL, false);")
            cursor.execute("SELECT set_config('app.bypass_rls', 'false', false);")

        # Create test tenants with RLS bypass
        enable_rls_bypass()

        self.tenant1 = Tenant.objects.create(
            company_name="Tenant 1 Jewelry", slug="tenant-1-jewelry", status=Tenant.ACTIVE
        )

        self.tenant2 = Tenant.objects.create(
            company_name="Tenant 2 Jewelry", slug="tenant-2-jewelry", status=Tenant.ACTIVE
        )

        self.tenant3 = Tenant.objects.create(
            company_name="Tenant 3 Jewelry", slug="tenant-3-jewelry", status=Tenant.ACTIVE
        )

        # Create test data for each tenant using raw SQL
        with connection.cursor() as cursor:
            # Tenant 1 data
            cursor.execute(
                """
                INSERT INTO test_tenant_scoped_data (tenant_id, name, value)
                VALUES (%s, %s, %s), (%s, %s, %s), (%s, %s, %s)
            """,
                [
                    str(self.tenant1.id),
                    "Item 1-1",
                    100,
                    str(self.tenant1.id),
                    "Item 1-2",
                    200,
                    str(self.tenant1.id),
                    "Item 1-3",
                    300,
                ],
            )

            # Tenant 2 data
            cursor.execute(
                """
                INSERT INTO test_tenant_scoped_data (tenant_id, name, value)
                VALUES (%s, %s, %s), (%s, %s, %s)
            """,
                [
                    str(self.tenant2.id),
                    "Item 2-1",
                    400,
                    str(self.tenant2.id),
                    "Item 2-2",
                    500,
                ],
            )

            # Tenant 3 data
            cursor.execute(
                """
                INSERT INTO test_tenant_scoped_data (tenant_id, name, value)
                VALUES (%s, %s, %s)
            """,
                [str(self.tenant3.id), "Item 3-1", 600],
            )

        # CRITICAL: Force disable bypass after setup
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.current_tenant', NULL, false);")
            cursor.execute("SELECT set_config('app.bypass_rls', 'false', false);")

    def tearDown(self):
        """Clean up after tests."""
        try:
            # Clean up test data with bypass enabled
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.bypass_rls', 'true', false);")
                cursor.execute("DELETE FROM test_tenant_scoped_data;")

            # Delete test tenants
            Tenant.objects.filter(
                slug__in=["tenant-1-jewelry", "tenant-2-jewelry", "tenant-3-jewelry"]
            ).delete()

            # CRITICAL: Force disable bypass after cleanup
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.current_tenant', NULL, false);")
                cursor.execute("SELECT set_config('app.bypass_rls', 'false', false);")
        except Exception:
            pass

    def test_tenant_can_only_see_own_data(self):
        """Test that tenant 1 can only see their own data."""
        # Ensure RLS bypass is disabled
        self._ensure_rls_enabled()

        # Verify RLS policies exist
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM pg_policies
                WHERE tablename = 'test_tenant_scoped_data';
            """
            )
            policy_count = cursor.fetchone()[0]
            assert (
                policy_count >= 4
            ), f"Should have at least 4 RLS policies but found: {policy_count}"

        # Verify RLS is enabled on the table
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT relrowsecurity, relforcerowsecurity
                FROM pg_class
                WHERE relname = 'test_tenant_scoped_data';
            """
            )
            rls_enabled, rls_forced = cursor.fetchone()
            assert rls_enabled, "RLS should be enabled on test_tenant_scoped_data"

        # Verify bypass is disabled
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.bypass_rls', true);")
            bypass_state = cursor.fetchone()[0]
            assert (
                bypass_state == "false" or bypass_state is None
            ), f"RLS bypass should be disabled but is: {bypass_state}"

        set_tenant_context(self.tenant1.id)

        # Verify tenant context is set
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_tenant', true);")
            current_tenant = cursor.fetchone()[0]
            assert current_tenant == str(
                self.tenant1.id
            ), f"Tenant context should be {self.tenant1.id} but is: {current_tenant}"

        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM test_tenant_scoped_data;")
            count = cursor.fetchone()[0]

        # Tenant 1 should only see their 3 items
        assert count == 3

    def test_different_tenants_see_different_data(self):
        """Test that different tenants see completely different datasets."""
        # Ensure RLS bypass is disabled
        self._ensure_rls_enabled()

        # Tenant 1 sees 3 items
        set_tenant_context(self.tenant1.id)
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM test_tenant_scoped_data ORDER BY name;")
            tenant1_items = [row[0] for row in cursor.fetchall()]

        # Tenant 2 sees 2 items
        set_tenant_context(self.tenant2.id)
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM test_tenant_scoped_data ORDER BY name;")
            tenant2_items = [row[0] for row in cursor.fetchall()]

        # Tenant 3 sees 1 item
        set_tenant_context(self.tenant3.id)
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM test_tenant_scoped_data ORDER BY name;")
            tenant3_items = [row[0] for row in cursor.fetchall()]

        # Verify counts
        assert len(tenant1_items) == 3
        assert len(tenant2_items) == 2
        assert len(tenant3_items) == 1

        # Verify no overlap
        assert set(tenant1_items).isdisjoint(set(tenant2_items))
        assert set(tenant1_items).isdisjoint(set(tenant3_items))
        assert set(tenant2_items).isdisjoint(set(tenant3_items))

        # Verify correct data
        assert "Item 1-1" in tenant1_items
        assert "Item 2-1" in tenant2_items
        assert "Item 3-1" in tenant3_items

    def test_no_tenant_context_returns_no_data(self):
        """Test that queries without tenant context return no data."""
        self._ensure_rls_enabled()

        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM test_tenant_scoped_data;")
            count = cursor.fetchone()[0]

        # Should see no data without tenant context
        assert count == 0

    def test_tenant_cannot_access_specific_other_tenant_record(self):
        """Test that tenant 1 cannot access a specific record from tenant 2."""
        self._ensure_rls_enabled()

        # Get a record ID from tenant 2
        set_tenant_context(self.tenant2.id)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM test_tenant_scoped_data WHERE name = 'Item 2-1' LIMIT 1;"
            )
            tenant2_record_id = cursor.fetchone()[0]

        # Switch to tenant 1 and try to access tenant 2's record
        set_tenant_context(self.tenant1.id)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM test_tenant_scoped_data WHERE id = %s;",
                [tenant2_record_id],
            )
            count = cursor.fetchone()[0]

        # Tenant 1 should not see tenant 2's record
        assert count == 0

    def test_tenant_can_insert_own_data(self):
        """Test that tenant can insert data for themselves."""
        self._ensure_rls_enabled()
        set_tenant_context(self.tenant1.id)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO test_tenant_scoped_data (tenant_id, name, value)
                VALUES (%s, %s, %s)
            """,
                [str(self.tenant1.id), "New Item 1-4", 700],
            )

            # Verify insertion
            cursor.execute("SELECT COUNT(*) FROM test_tenant_scoped_data;")
            count = cursor.fetchone()[0]

        # Should now have 4 items
        assert count == 4

    def test_tenant_cannot_insert_data_for_other_tenant(self):
        """Test that tenant 1 cannot insert data for tenant 2."""
        self._ensure_rls_enabled()
        set_tenant_context(self.tenant1.id)

        from django.db.utils import DatabaseError

        # Try to insert data for tenant 2 while in tenant 1 context
        with pytest.raises(DatabaseError):
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO test_tenant_scoped_data (tenant_id, name, value)
                    VALUES (%s, %s, %s)
                """,
                    [str(self.tenant2.id), "Malicious Item", 999],
                )

    def test_tenant_can_update_own_data(self):
        """Test that tenant can update their own data."""
        self._ensure_rls_enabled()
        set_tenant_context(self.tenant1.id)

        with connection.cursor() as cursor:
            # Update tenant 1's data
            cursor.execute(
                """
                UPDATE test_tenant_scoped_data
                SET value = 1000
                WHERE name = 'Item 1-1'
            """
            )

            # Verify update
            cursor.execute("SELECT value FROM test_tenant_scoped_data WHERE name = 'Item 1-1';")
            updated_value = cursor.fetchone()[0]

        assert updated_value == 1000

    def test_tenant_cannot_update_other_tenant_data(self):
        """Test that tenant 1 cannot update tenant 2's data."""
        self._ensure_rls_enabled()

        # Get tenant 2's record ID
        set_tenant_context(self.tenant2.id)
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, value FROM test_tenant_scoped_data WHERE name = 'Item 2-1';")
            tenant2_record_id, original_value = cursor.fetchone()

        # Switch to tenant 1 and try to update tenant 2's record
        set_tenant_context(self.tenant1.id)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE test_tenant_scoped_data
                SET value = 9999
                WHERE id = %s
            """,
                [tenant2_record_id],
            )

        # Verify tenant 2's data was NOT updated
        set_tenant_context(self.tenant2.id)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT value FROM test_tenant_scoped_data WHERE id = %s;", [tenant2_record_id]
            )
            current_value = cursor.fetchone()[0]

        # Value should remain unchanged
        assert current_value == original_value

    def test_tenant_can_delete_own_data(self):
        """Test that tenant can delete their own data."""
        self._ensure_rls_enabled()
        set_tenant_context(self.tenant1.id)

        with connection.cursor() as cursor:
            # Delete one of tenant 1's items
            cursor.execute("DELETE FROM test_tenant_scoped_data WHERE name = 'Item 1-1';")

            # Verify deletion
            cursor.execute("SELECT COUNT(*) FROM test_tenant_scoped_data;")
            count = cursor.fetchone()[0]

        # Should now have 2 items (down from 3)
        assert count == 2

    def test_tenant_cannot_delete_other_tenant_data(self):
        """Test that tenant 1 cannot delete tenant 2's data."""
        self._ensure_rls_enabled()

        # Get tenant 2's record ID
        set_tenant_context(self.tenant2.id)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM test_tenant_scoped_data WHERE name = 'Item 2-1' LIMIT 1;"
            )
            tenant2_record_id = cursor.fetchone()[0]

            # Count tenant 2's records
            cursor.execute("SELECT COUNT(*) FROM test_tenant_scoped_data;")
            tenant2_count_before = cursor.fetchone()[0]

        # Switch to tenant 1 and try to delete tenant 2's record
        set_tenant_context(self.tenant1.id)
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM test_tenant_scoped_data WHERE id = %s;", [tenant2_record_id]
            )

        # Verify tenant 2's data was NOT deleted
        set_tenant_context(self.tenant2.id)
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM test_tenant_scoped_data;")
            tenant2_count_after = cursor.fetchone()[0]

        # Count should remain the same
        assert tenant2_count_after == tenant2_count_before

    def test_rls_bypass_allows_access_to_all_data(self):
        """Test that RLS bypass allows platform admin to see all tenant data."""
        enable_rls_bypass()

        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM test_tenant_scoped_data;")
            count = cursor.fetchone()[0]

        # Should see all 6 items (3 + 2 + 1)
        assert count == 6

    def test_rls_bypass_allows_cross_tenant_operations(self):
        """Test that RLS bypass allows operations across all tenants."""
        enable_rls_bypass()

        with connection.cursor() as cursor:
            # Update all records regardless of tenant
            cursor.execute("UPDATE test_tenant_scoped_data SET value = value + 1000;")

            # Verify all records were updated
            cursor.execute("SELECT COUNT(*) FROM test_tenant_scoped_data WHERE value >= 1000;")
            count = cursor.fetchone()[0]

        # All 6 records should have been updated
        assert count == 6


@pytest.mark.django_db
class TestTenantContextSwitching(TestCase):
    """
    Test tenant context switching to ensure no data leakage between contexts.
    """

    def setUp(self):
        """Set up test fixtures."""
        # Force clear any existing state
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.current_tenant', NULL, false);")
            cursor.execute("SELECT set_config('app.bypass_rls', 'false', false);")

        enable_rls_bypass()
        self.tenant_a = Tenant.objects.create(
            company_name="Tenant A", slug="tenant-a", status=Tenant.ACTIVE
        )
        self.tenant_b = Tenant.objects.create(
            company_name="Tenant B", slug="tenant-b", status=Tenant.ACTIVE
        )
        self.tenant_c = Tenant.objects.create(
            company_name="Tenant C", slug="tenant-c", status=Tenant.ACTIVE
        )

        # Force disable bypass after setup
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.current_tenant', NULL, false);")
            cursor.execute("SELECT set_config('app.bypass_rls', 'false', false);")

    def tearDown(self):
        """Clean up after tests."""
        try:
            # Delete test tenants with bypass enabled
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.bypass_rls', 'true', false);")

            # Delete tenants
            Tenant.objects.filter(slug__in=["tenant-a", "tenant-b", "tenant-c"]).delete()

            # Force clear all state
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.current_tenant', NULL, false);")
                cursor.execute("SELECT set_config('app.bypass_rls', 'false', false);")
        except Exception:
            pass

    def test_rapid_context_switching(self):
        """Test rapid switching between tenant contexts."""
        disable_rls_bypass()

        # Switch between tenants multiple times
        for _ in range(10):
            set_tenant_context(self.tenant_a.id)
            assert get_current_tenant() == self.tenant_a.id
            assert Tenant.objects.count() == 1

            set_tenant_context(self.tenant_b.id)
            assert get_current_tenant() == self.tenant_b.id
            assert Tenant.objects.count() == 1

            set_tenant_context(self.tenant_c.id)
            assert get_current_tenant() == self.tenant_c.id
            assert Tenant.objects.count() == 1

    def test_context_manager_properly_restores_context(self):
        """Test that tenant_context manager properly restores previous context."""
        disable_rls_bypass()

        # Set initial context to tenant A
        set_tenant_context(self.tenant_a.id)
        assert get_current_tenant() == self.tenant_a.id

        # Use context manager to switch to tenant B
        with tenant_context(self.tenant_b.id):
            assert get_current_tenant() == self.tenant_b.id
            tenant_b_data = Tenant.objects.first()
            assert tenant_b_data.id == self.tenant_b.id

        # Should be back to tenant A
        assert get_current_tenant() == self.tenant_a.id
        tenant_a_data = Tenant.objects.first()
        assert tenant_a_data.id == self.tenant_a.id

    def test_nested_context_managers(self):
        """Test nested tenant context managers."""
        set_tenant_context(self.tenant_a.id)

        with tenant_context(self.tenant_b.id):
            assert get_current_tenant() == self.tenant_b.id

            with tenant_context(self.tenant_c.id):
                assert get_current_tenant() == self.tenant_c.id

            # Back to tenant B
            assert get_current_tenant() == self.tenant_b.id

        # Back to tenant A
        assert get_current_tenant() == self.tenant_a.id

    def test_context_switching_with_bypass(self):
        """Test context switching combined with RLS bypass."""
        disable_rls_bypass()

        # Start with tenant A
        set_tenant_context(self.tenant_a.id)
        assert Tenant.objects.count() == 1

        # Enable bypass
        with bypass_rls():
            assert Tenant.objects.count() >= 3

            # Switch tenant within bypass
            with tenant_context(self.tenant_b.id):
                # Still bypassed, should see all
                assert Tenant.objects.count() >= 3

        # Back to tenant A, no bypass
        assert get_current_tenant() == self.tenant_a.id
        assert Tenant.objects.count() == 1

    def test_context_cleared_between_requests(self):
        """Test that context is properly cleared between simulated requests."""
        # Simulate request 1 for tenant A
        set_tenant_context(self.tenant_a.id)
        assert get_current_tenant() == self.tenant_a.id
        clear_tenant_context()

        # Simulate request 2 for tenant B
        set_tenant_context(self.tenant_b.id)
        assert get_current_tenant() == self.tenant_b.id
        clear_tenant_context()

        # Simulate request 3 with no tenant
        assert get_current_tenant() is None

    def test_exception_during_context_switch_doesnt_leak(self):
        """Test that exceptions during context operations don't leak context."""
        set_tenant_context(self.tenant_a.id)

        try:
            with tenant_context(self.tenant_b.id):
                assert get_current_tenant() == self.tenant_b.id
                raise ValueError("Simulated error")
        except ValueError:
            pass

        # Should be back to tenant A despite exception
        assert get_current_tenant() == self.tenant_a.id


@pytest.mark.django_db
class TestRLSPolicyEnforcement(TestCase):
    """
    Test that RLS policies are properly enforced at the database level.
    """

    def setUp(self):
        """Set up test fixtures."""
        # Force clear any existing state
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.current_tenant', NULL, false);")
            cursor.execute("SELECT set_config('app.bypass_rls', 'false', false);")

        enable_rls_bypass()
        self.tenant1 = Tenant.objects.create(
            company_name="Policy Test 1", slug="policy-test-1", status=Tenant.ACTIVE
        )
        self.tenant2 = Tenant.objects.create(
            company_name="Policy Test 2", slug="policy-test-2", status=Tenant.ACTIVE
        )

        # Force disable bypass after setup
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.current_tenant', NULL, false);")
            cursor.execute("SELECT set_config('app.bypass_rls', 'false', false);")

    def tearDown(self):
        """Clean up after tests."""
        try:
            # Delete test tenants with bypass enabled
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.bypass_rls', 'true', false);")

            # Delete tenants
            Tenant.objects.filter(slug__in=["policy-test-1", "policy-test-2"]).delete()

            # Force clear all state
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.current_tenant', NULL, false);")
                cursor.execute("SELECT set_config('app.bypass_rls', 'false', false);")
        except Exception:
            pass

    def test_rls_enforced_even_with_direct_sql(self):
        """Test that RLS is enforced even when using raw SQL queries."""
        disable_rls_bypass()
        set_tenant_context(self.tenant1.id)

        # Try to access all tenants using raw SQL
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM tenants;")
            count = cursor.fetchone()[0]

        # Should only see tenant1 due to RLS
        assert count == 1

    def test_rls_enforced_on_joins(self):
        """Test that RLS is enforced on JOIN operations."""
        # This test verifies RLS works with complex queries
        disable_rls_bypass()
        set_tenant_context(self.tenant1.id)

        with connection.cursor() as cursor:
            # Self-join query
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM tenants t1
                JOIN tenants t2 ON t1.id = t2.id
            """
            )
            count = cursor.fetchone()[0]

        # Should only see tenant1
        assert count == 1

    def test_rls_enforced_on_subqueries(self):
        """Test that RLS is enforced on subqueries."""
        disable_rls_bypass()
        set_tenant_context(self.tenant1.id)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM tenants
                WHERE id IN (SELECT id FROM tenants)
            """
            )
            count = cursor.fetchone()[0]

        # Should only see tenant1
        assert count == 1

    def test_rls_policies_exist_for_all_operations(self):
        """Test that RLS policies exist for SELECT, INSERT, UPDATE, DELETE."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT cmd
                FROM pg_policies
                WHERE tablename = 'tenants'
                ORDER BY cmd;
            """
            )
            policies = [row[0] for row in cursor.fetchall()]

        # Should have policies for all operations
        assert "SELECT" in policies
        assert "INSERT" in policies
        assert "UPDATE" in policies
        assert "DELETE" in policies

    def test_rls_cannot_be_disabled_by_tenant(self):
        """Test that RLS policies are enforced even with malicious SQL attempts."""
        disable_rls_bypass()
        set_tenant_context(self.tenant1.id)

        # Verify RLS is working correctly
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM tenants;")
            count_before = cursor.fetchone()[0]

        assert count_before == 1, "Should only see own tenant"

        # Try SQL injection-style attack to see other tenants
        # This should still be filtered by RLS
        malicious_query = f"SELECT COUNT(*) FROM tenants WHERE id = '{self.tenant2.id}' OR 1=1;"

        with connection.cursor() as cursor:
            cursor.execute(malicious_query)
            count_after = cursor.fetchone()[0]

        # RLS should still filter, so should only see tenant1
        assert count_after == 1, "RLS should prevent SQL injection attacks"


@pytest.mark.django_db
class TestCrossTenantDataLeakage(TestCase):
    """
    Test for potential cross-tenant data leakage scenarios.
    """

    def setUp(self):
        """Set up test fixtures."""
        # Force clear any existing state
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.current_tenant', NULL, false);")
            cursor.execute("SELECT set_config('app.bypass_rls', 'false', false);")

        enable_rls_bypass()
        self.tenant_x = Tenant.objects.create(
            company_name="Tenant X", slug="tenant-x", status=Tenant.ACTIVE
        )
        self.tenant_y = Tenant.objects.create(
            company_name="Tenant Y", slug="tenant-y", status=Tenant.ACTIVE
        )

        # Force disable bypass after setup
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.current_tenant', NULL, false);")
            cursor.execute("SELECT set_config('app.bypass_rls', 'false', false);")

    def tearDown(self):
        """Clean up after tests."""
        try:
            # Delete test tenants with bypass enabled
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.bypass_rls', 'true', false);")

            # Delete tenants
            Tenant.objects.filter(slug__in=["tenant-x", "tenant-y"]).delete()

            # Force clear all state
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.current_tenant', NULL, false);")
                cursor.execute("SELECT set_config('app.bypass_rls', 'false', false);")
        except Exception:
            pass

    def test_no_leakage_through_aggregate_queries(self):
        """Test that aggregate queries don't leak cross-tenant data."""
        disable_rls_bypass()
        set_tenant_context(self.tenant_x.id)

        # Count should only include tenant X
        count = Tenant.objects.count()
        assert count == 1

        # Aggregate should only include tenant X
        from django.db.models import Count

        result = Tenant.objects.aggregate(total=Count("id"))
        assert result["total"] == 1

    def test_no_leakage_through_exists_queries(self):
        """Test that exists() queries don't leak cross-tenant data."""
        disable_rls_bypass()
        set_tenant_context(self.tenant_x.id)

        # Should find tenant X
        assert Tenant.objects.filter(id=self.tenant_x.id).exists()

        # Should NOT find tenant Y
        assert not Tenant.objects.filter(id=self.tenant_y.id).exists()

    def test_no_leakage_through_values_queries(self):
        """Test that values() queries don't leak cross-tenant data."""
        disable_rls_bypass()
        set_tenant_context(self.tenant_x.id)

        tenant_ids = list(Tenant.objects.values_list("id", flat=True))

        # Should only contain tenant X's ID
        assert len(tenant_ids) == 1
        assert tenant_ids[0] == self.tenant_x.id

    def test_no_leakage_through_raw_queries(self):
        """Test that raw() queries respect RLS."""
        disable_rls_bypass()
        set_tenant_context(self.tenant_x.id)

        tenants = list(Tenant.objects.raw("SELECT * FROM tenants"))

        # Should only return tenant X
        assert len(tenants) == 1
        assert tenants[0].id == self.tenant_x.id

    def test_no_leakage_through_extra_queries(self):
        """Test that extra() queries respect RLS."""
        disable_rls_bypass()
        set_tenant_context(self.tenant_x.id)

        tenants = Tenant.objects.extra(where=["status = 'ACTIVE'"])

        # Should only return tenant X
        assert tenants.count() == 1
        assert tenants.first().id == self.tenant_x.id

    def test_no_leakage_after_context_clear(self):
        """Test that clearing context prevents all data access."""
        disable_rls_bypass()

        # Set context
        set_tenant_context(self.tenant_x.id)
        assert Tenant.objects.count() == 1

        # Clear context
        clear_tenant_context()

        # Should see no data
        assert Tenant.objects.count() == 0

    def test_no_leakage_with_invalid_tenant_id(self):
        """Test that invalid tenant ID doesn't bypass RLS."""
        disable_rls_bypass()

        # Set context with non-existent tenant ID
        fake_tenant_id = uuid.uuid4()
        set_tenant_context(fake_tenant_id)

        # Should see no data
        assert Tenant.objects.count() == 0
