"""
Property-based tests for tenant list sorting correctness.

**Feature: advanced-tenant-management, Property 13: Sorting Correctness**
**Validates: Requirements 8.2**

Property 13: Sorting Correctness
*For any* column sort on the tenant list, the results SHALL be ordered correctly
(ascending or descending) by that column's values.
"""

import uuid

from django.test import RequestFactory

import pytest
from hypothesis import HealthCheck, given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from apps.core.admin_views import TenantListView
from apps.core.models import Tenant, User
from apps.core.tenant_context import bypass_rls

# Strategy for sort columns
sort_column_strategy = st.sampled_from(
    [
        "company_name",
        "slug",
        "status",
        "created_at",
    ]
)


# Strategy for sort order
sort_order_strategy = st.sampled_from(["asc", "desc"])


def create_test_tenant(company_name: str, status: str, unique_id: str) -> Tenant:
    """Create a test tenant with the given parameters."""
    slug = f"test-{unique_id}"
    return Tenant.objects.create(
        company_name=company_name,
        slug=slug,
        status=status,
    )


def create_platform_admin():
    """Create a platform admin user for testing."""
    unique_id = str(uuid.uuid4())[:8]
    with bypass_rls():
        return User.objects.create_user(
            username=f"admin-{unique_id}",
            email=f"admin-{unique_id}@example.com",
            password="adminpass123",
            tenant=None,
            role=User.PLATFORM_ADMIN,
        )


@pytest.mark.django_db
class TestSortingCorrectness:
    """
    **Feature: advanced-tenant-management, Property 13: Sorting Correctness**
    **Validates: Requirements 8.2**

    Property tests for tenant list sorting ensuring:
    1. Results are correctly ordered by the specified column
    2. Both ascending and descending orders work correctly
    3. Null values are handled appropriately
    """

    @given(
        sort_column=sort_column_strategy,
        sort_order=sort_order_strategy,
        num_tenants=st.integers(min_value=3, max_value=8),
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_sorting_produces_correct_order(self, sort_column, sort_order, num_tenants):
        """
        **Feature: advanced-tenant-management, Property 13: Sorting Correctness**
        **Validates: Requirements 8.2**

        For any valid sort column and order, the TenantListView SHALL return
        results ordered correctly by that column's values.
        """
        created_tenants = []
        test_id = str(uuid.uuid4())[:8]
        admin_user = None

        try:
            with bypass_rls():
                # Create admin user for this test
                admin_user = create_platform_admin()

                # Create test tenants with varying values
                statuses = [Tenant.ACTIVE, Tenant.SUSPENDED, Tenant.PENDING_DELETION]
                for i in range(num_tenants):
                    company_name = f"Company {chr(65 + (i % 26))} {test_id} {i}"
                    status = statuses[i % len(statuses)]
                    tenant = create_test_tenant(
                        company_name=company_name,
                        status=status,
                        unique_id=f"{test_id}-{i}",
                    )
                    created_tenants.append(tenant)

            # Create request with sort parameters
            factory = RequestFactory()
            request = factory.get(
                "/admin/tenants/", {"sort_by": sort_column, "sort_order": sort_order}
            )
            request.user = admin_user

            # Get the view's queryset
            view = TenantListView()
            view.request = request
            queryset = view.get_queryset()

            # Filter to only our test tenants
            test_tenant_ids = [t.id for t in created_tenants]
            filtered_qs = queryset.filter(id__in=test_tenant_ids)

            # Extract the sorted values
            results = list(filtered_qs)

            if len(results) < 2:
                # Not enough results to verify sorting
                return

            # Get the values for the sort column
            if sort_column == "company_name":
                values = [t.company_name for t in results]
            elif sort_column == "slug":
                values = [t.slug for t in results]
            elif sort_column == "status":
                values = [t.status for t in results]
            elif sort_column == "created_at":
                values = [t.created_at for t in results]
            elif sort_column == "user_count":
                values = [getattr(t, "user_count", 0) for t in results]
            elif sort_column == "last_activity":
                values = [getattr(t, "last_activity", None) for t in results]
            else:
                # Unknown column, skip
                return

            # Verify sorting
            is_ascending = sort_order == "asc"

            # Check each adjacent pair
            for i in range(len(values) - 1):
                current = values[i]
                next_val = values[i + 1]

                # Handle None values
                if current is None or next_val is None:
                    continue

                # Compare non-None values
                if is_ascending:
                    assert current <= next_val, (
                        f"Sorting by {sort_column} {sort_order} failed: "
                        f"'{current}' should come before or equal to '{next_val}'"
                    )
                else:
                    assert current >= next_val, (
                        f"Sorting by {sort_column} {sort_order} failed: "
                        f"'{current}' should come after or equal to '{next_val}'"
                    )

        finally:
            # Cleanup
            with bypass_rls():
                for tenant in created_tenants:
                    try:
                        tenant.delete()
                    except Exception:
                        pass
                if admin_user:
                    try:
                        admin_user.delete()
                    except Exception:
                        pass

    @given(sort_order=sort_order_strategy)
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_company_name_sorting(self, sort_order):
        """
        **Feature: advanced-tenant-management, Property 13: Sorting Correctness**
        **Validates: Requirements 8.2**

        For any sort order, sorting by company_name SHALL produce alphabetically
        ordered results.
        """
        created_tenants = []
        test_id = str(uuid.uuid4())[:8]
        admin_user = None

        try:
            with bypass_rls():
                admin_user = create_platform_admin()

                # Create tenants with specific names for predictable sorting
                names = ["Alpha Corp", "Beta Inc", "Gamma LLC", "Delta Co", "Epsilon Ltd"]
                for i, name in enumerate(names):
                    tenant = create_test_tenant(
                        company_name=f"{name} {test_id}",
                        status=Tenant.ACTIVE,
                        unique_id=f"{test_id}-{i}",
                    )
                    created_tenants.append(tenant)

            # Create request
            factory = RequestFactory()
            request = factory.get(
                "/admin/tenants/", {"sort_by": "company_name", "sort_order": sort_order}
            )
            request.user = admin_user

            # Get sorted results
            view = TenantListView()
            view.request = request
            queryset = view.get_queryset()

            # Filter to test tenants
            test_tenant_ids = [t.id for t in created_tenants]
            results = list(queryset.filter(id__in=test_tenant_ids))

            # Extract company names
            result_names = [t.company_name for t in results]

            # Verify order
            is_ascending = sort_order == "asc"
            expected_names = sorted(result_names, reverse=not is_ascending)

            assert result_names == expected_names, (
                f"Company name sorting ({sort_order}) failed: "
                f"got {result_names}, expected {expected_names}"
            )

        finally:
            with bypass_rls():
                for tenant in created_tenants:
                    try:
                        tenant.delete()
                    except Exception:
                        pass
                if admin_user:
                    try:
                        admin_user.delete()
                    except Exception:
                        pass

    @given(sort_order=sort_order_strategy)
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_status_sorting(self, sort_order):
        """
        **Feature: advanced-tenant-management, Property 13: Sorting Correctness**
        **Validates: Requirements 8.2**

        For any sort order, sorting by status SHALL produce correctly ordered
        results by status value.
        """
        created_tenants = []
        test_id = str(uuid.uuid4())[:8]
        admin_user = None

        try:
            with bypass_rls():
                admin_user = create_platform_admin()

                # Create tenants with different statuses
                statuses = [
                    Tenant.ACTIVE,
                    Tenant.SUSPENDED,
                    Tenant.PENDING_DELETION,
                    Tenant.ACTIVE,
                    Tenant.SUSPENDED,
                ]
                for i, status in enumerate(statuses):
                    tenant = create_test_tenant(
                        company_name=f"Status Test {test_id} {i}",
                        status=status,
                        unique_id=f"{test_id}-{i}",
                    )
                    created_tenants.append(tenant)

            # Create request
            factory = RequestFactory()
            request = factory.get(
                "/admin/tenants/", {"sort_by": "status", "sort_order": sort_order}
            )
            request.user = admin_user

            # Get sorted results
            view = TenantListView()
            view.request = request
            queryset = view.get_queryset()

            # Filter to test tenants
            test_tenant_ids = [t.id for t in created_tenants]
            results = list(queryset.filter(id__in=test_tenant_ids))

            # Extract statuses
            result_statuses = [t.status for t in results]

            # Verify order
            is_ascending = sort_order == "asc"
            expected_statuses = sorted(result_statuses, reverse=not is_ascending)

            assert result_statuses == expected_statuses, (
                f"Status sorting ({sort_order}) failed: "
                f"got {result_statuses}, expected {expected_statuses}"
            )

        finally:
            with bypass_rls():
                for tenant in created_tenants:
                    try:
                        tenant.delete()
                    except Exception:
                        pass
                if admin_user:
                    try:
                        admin_user.delete()
                    except Exception:
                        pass

    @given(sort_order=sort_order_strategy)
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_created_at_sorting(self, sort_order):
        """
        **Feature: advanced-tenant-management, Property 13: Sorting Correctness**
        **Validates: Requirements 8.2**

        For any sort order, sorting by created_at SHALL produce chronologically
        ordered results.
        """
        created_tenants = []
        test_id = str(uuid.uuid4())[:8]
        admin_user = None

        try:
            with bypass_rls():
                admin_user = create_platform_admin()

                # Create tenants (they will have sequential created_at times)
                for i in range(5):
                    tenant = create_test_tenant(
                        company_name=f"Date Test {test_id} {i}",
                        status=Tenant.ACTIVE,
                        unique_id=f"{test_id}-{i}",
                    )
                    created_tenants.append(tenant)

            # Create request
            factory = RequestFactory()
            request = factory.get(
                "/admin/tenants/", {"sort_by": "created_at", "sort_order": sort_order}
            )
            request.user = admin_user

            # Get sorted results
            view = TenantListView()
            view.request = request
            queryset = view.get_queryset()

            # Filter to test tenants
            test_tenant_ids = [t.id for t in created_tenants]
            results = list(queryset.filter(id__in=test_tenant_ids))

            # Extract created_at timestamps
            result_dates = [t.created_at for t in results]

            # Verify order
            is_ascending = sort_order == "asc"
            expected_dates = sorted(result_dates, reverse=not is_ascending)

            assert result_dates == expected_dates, (
                f"Created_at sorting ({sort_order}) failed: "
                f"got {result_dates}, expected {expected_dates}"
            )

        finally:
            with bypass_rls():
                for tenant in created_tenants:
                    try:
                        tenant.delete()
                    except Exception:
                        pass
                if admin_user:
                    try:
                        admin_user.delete()
                    except Exception:
                        pass

    @given(sort_order=sort_order_strategy)
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_user_count_sorting(self, sort_order):
        """
        **Feature: advanced-tenant-management, Property 13: Sorting Correctness**
        **Validates: Requirements 8.2**

        For any sort order, sorting by user_count SHALL produce correctly ordered
        results by the number of users in each tenant.
        """
        created_tenants = []
        created_users = []
        test_id = str(uuid.uuid4())[:8]
        admin_user = None

        try:
            with bypass_rls():
                admin_user = create_platform_admin()

                # Create tenants with different user counts
                user_counts = [0, 2, 1, 3, 1]
                for i, user_count in enumerate(user_counts):
                    tenant = create_test_tenant(
                        company_name=f"User Count Test {test_id} {i}",
                        status=Tenant.ACTIVE,
                        unique_id=f"{test_id}-{i}",
                    )
                    created_tenants.append(tenant)

                    # Create users for this tenant
                    for j in range(user_count):
                        user = User.objects.create_user(
                            username=f"user-{test_id}-{i}-{j}",
                            email=f"user-{test_id}-{i}-{j}@example.com",
                            password="testpass123",
                            tenant=tenant,
                            role=User.TENANT_EMPLOYEE,
                        )
                        created_users.append(user)

            # Create request
            factory = RequestFactory()
            request = factory.get(
                "/admin/tenants/", {"sort_by": "user_count", "sort_order": sort_order}
            )
            request.user = admin_user

            # Get sorted results
            view = TenantListView()
            view.request = request
            queryset = view.get_queryset()

            # Filter to test tenants
            test_tenant_ids = [t.id for t in created_tenants]
            results = list(queryset.filter(id__in=test_tenant_ids))

            # Extract user counts
            result_counts = [getattr(t, "user_count", 0) for t in results]

            # Verify order
            is_ascending = sort_order == "asc"
            expected_counts = sorted(result_counts, reverse=not is_ascending)

            assert result_counts == expected_counts, (
                f"User count sorting ({sort_order}) failed: "
                f"got {result_counts}, expected {expected_counts}"
            )

        finally:
            with bypass_rls():
                for user in created_users:
                    try:
                        user.delete()
                    except Exception:
                        pass
                for tenant in created_tenants:
                    try:
                        tenant.delete()
                    except Exception:
                        pass
                if admin_user:
                    try:
                        admin_user.delete()
                    except Exception:
                        pass

    def test_invalid_sort_column_defaults_to_created_at(self, platform_admin):
        """
        **Feature: advanced-tenant-management, Property 13: Sorting Correctness**
        **Validates: Requirements 8.2**

        When an invalid sort column is provided, the system SHALL default to
        sorting by created_at.
        """
        created_tenants = []
        test_id = str(uuid.uuid4())[:8]

        try:
            with bypass_rls():
                for i in range(3):
                    tenant = create_test_tenant(
                        company_name=f"Default Sort Test {test_id} {i}",
                        status=Tenant.ACTIVE,
                        unique_id=f"{test_id}-{i}",
                    )
                    created_tenants.append(tenant)

            # Create request with invalid sort column
            factory = RequestFactory()
            request = factory.get(
                "/admin/tenants/", {"sort_by": "invalid_column", "sort_order": "desc"}
            )
            request.user = platform_admin

            # Get sorted results
            view = TenantListView()
            view.request = request
            queryset = view.get_queryset()

            # Filter to test tenants
            test_tenant_ids = [t.id for t in created_tenants]
            results = list(queryset.filter(id__in=test_tenant_ids))

            # Should be sorted by created_at descending (default)
            result_dates = [t.created_at for t in results]
            expected_dates = sorted(result_dates, reverse=True)

            assert (
                result_dates == expected_dates
            ), "Invalid sort column should default to created_at descending"

        finally:
            with bypass_rls():
                for tenant in created_tenants:
                    try:
                        tenant.delete()
                    except Exception:
                        pass

    @given(
        sort_column=sort_column_strategy,
        sort_order=sort_order_strategy,
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_sorting_is_deterministic(self, sort_column, sort_order):
        """
        **Feature: advanced-tenant-management, Property 13: Sorting Correctness**
        **Validates: Requirements 8.2**

        For any sort column and order, calling the sort multiple times SHALL
        produce the same result (deterministic).
        """
        created_tenants = []
        test_id = str(uuid.uuid4())[:8]
        admin_user = None

        try:
            with bypass_rls():
                admin_user = create_platform_admin()

                for i in range(5):
                    tenant = create_test_tenant(
                        company_name=f"Deterministic Test {test_id} {i}",
                        status=[Tenant.ACTIVE, Tenant.SUSPENDED][i % 2],
                        unique_id=f"{test_id}-{i}",
                    )
                    created_tenants.append(tenant)

            # Create request
            factory = RequestFactory()
            request = factory.get(
                "/admin/tenants/", {"sort_by": sort_column, "sort_order": sort_order}
            )
            request.user = admin_user

            # Get sorted results multiple times
            view = TenantListView()
            view.request = request

            test_tenant_ids = [t.id for t in created_tenants]

            results1 = list(view.get_queryset().filter(id__in=test_tenant_ids))
            results2 = list(view.get_queryset().filter(id__in=test_tenant_ids))
            results3 = list(view.get_queryset().filter(id__in=test_tenant_ids))

            # Extract IDs for comparison
            ids1 = [t.id for t in results1]
            ids2 = [t.id for t in results2]
            ids3 = [t.id for t in results3]

            assert (
                ids1 == ids2 == ids3
            ), f"Sorting by {sort_column} {sort_order} is not deterministic"

        finally:
            with bypass_rls():
                for tenant in created_tenants:
                    try:
                        tenant.delete()
                    except Exception:
                        pass
                if admin_user:
                    try:
                        admin_user.delete()
                    except Exception:
                        pass
