"""
Property-based tests for pagination consistency in tenant management.

**Feature: advanced-tenant-management, Property 11: Pagination Consistency**
**Validates: Requirements 4.7**

Property 11: Pagination Consistency
*For any* paginated result set, the page size SHALL be exactly 50 entries (or fewer
for the last page), and navigating through all pages SHALL return all matching
entries exactly once.
"""

import uuid
from datetime import timedelta

from django.core.paginator import Paginator
from django.utils import timezone

import pytest
from hypothesis import HealthCheck, given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from apps.core.audit_models import AuditLog
from apps.core.models import Tenant

# ============================================================================
# Constants
# ============================================================================

PAGE_SIZE = 50  # As per Requirement 4.7


# ============================================================================
# Helper Functions
# ============================================================================


def create_audit_logs_for_tenant(tenant, count):
    """Create a specified number of audit log entries for a tenant."""
    logs = []
    for i in range(count):
        log = AuditLog.objects.create(
            tenant=tenant,
            category=AuditLog.CATEGORY_USER,
            action=AuditLog.ACTION_LOGIN_SUCCESS,
            severity=AuditLog.SEVERITY_INFO,
            description=f"Test audit log {i} for tenant {tenant.slug}",
            ip_address="127.0.0.1",
            user_agent="Test User Agent",
        )
        logs.append(log)
    return logs


def get_paginated_activity_logs(tenant, page_number=1):
    """
    Get paginated activity logs for a tenant using the same logic as _get_activity_context.

    This mirrors the implementation in apps/core/admin_views.py:
    - Filter by tenant
    - Order by -timestamp
    - Paginate with 50 entries per page
    """
    logs = AuditLog.objects.filter(tenant=tenant).order_by("-timestamp")
    paginator = Paginator(logs, PAGE_SIZE)
    return paginator, paginator.get_page(page_number)


def collect_all_pages(tenant):
    """
    Collect all entries from all pages for a tenant.

    Returns:
        tuple: (all_entry_ids, page_sizes, total_pages)
    """
    logs = AuditLog.objects.filter(tenant=tenant).order_by("-timestamp")
    paginator = Paginator(logs, PAGE_SIZE)

    all_entry_ids = []
    page_sizes = []

    for page_num in range(1, paginator.num_pages + 1):
        page = paginator.get_page(page_num)
        page_ids = [log.id for log in page.object_list]
        all_entry_ids.extend(page_ids)
        page_sizes.append(len(page_ids))

    return all_entry_ids, page_sizes, paginator.num_pages


# ============================================================================
# Property Tests
# ============================================================================


@pytest.mark.django_db
class TestPaginationConsistency:
    """
    **Feature: advanced-tenant-management, Property 11: Pagination Consistency**
    **Validates: Requirements 4.7**

    Property tests for pagination consistency ensuring:
    1. Each page has exactly 50 entries (except possibly the last page)
    2. The last page has <= 50 entries
    3. Navigating through all pages returns all matching entries exactly once
    """

    @given(
        num_logs=st.integers(min_value=1, max_value=150),
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_page_size_is_exactly_50_except_last_page(self, num_logs):
        """
        **Feature: advanced-tenant-management, Property 11: Pagination Consistency**
        **Validates: Requirements 4.7**

        For any paginated result set, each page (except the last) SHALL have
        exactly 50 entries.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create audit logs
            create_audit_logs_for_tenant(tenant, num_logs)

            # Collect all pages
            all_entry_ids, page_sizes, total_pages = collect_all_pages(tenant)

            # Property: All pages except the last should have exactly PAGE_SIZE entries
            if total_pages > 1:
                for i, size in enumerate(page_sizes[:-1]):
                    assert (
                        size == PAGE_SIZE
                    ), f"Page {i + 1} has {size} entries, expected {PAGE_SIZE}"

            # Property: Last page should have <= PAGE_SIZE entries
            if page_sizes:
                last_page_size = page_sizes[-1]
                assert (
                    last_page_size <= PAGE_SIZE
                ), f"Last page has {last_page_size} entries, expected <= {PAGE_SIZE}"
                assert last_page_size > 0, "Last page should have at least 1 entry"

        finally:
            # Cleanup
            AuditLog.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        num_logs=st.integers(min_value=1, max_value=150),
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_all_entries_returned_exactly_once(self, num_logs):
        """
        **Feature: advanced-tenant-management, Property 11: Pagination Consistency**
        **Validates: Requirements 4.7**

        For any paginated result set, navigating through all pages SHALL return
        all matching entries exactly once (no duplicates, no missing entries).
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create audit logs and track their IDs
            created_logs = create_audit_logs_for_tenant(tenant, num_logs)
            created_ids = set(log.id for log in created_logs)

            # Collect all pages
            all_entry_ids, page_sizes, total_pages = collect_all_pages(tenant)

            # Property: Total entries across all pages equals the total count
            assert (
                len(all_entry_ids) == num_logs
            ), f"Total entries across pages is {len(all_entry_ids)}, expected {num_logs}"

            # Property: No duplicates exist across pages
            unique_ids = set(all_entry_ids)
            assert len(unique_ids) == len(
                all_entry_ids
            ), f"Found {len(all_entry_ids) - len(unique_ids)} duplicate entries across pages"

            # Property: All created entries are returned
            assert unique_ids == created_ids, (
                f"Missing entries: {created_ids - unique_ids}, "
                f"Extra entries: {unique_ids - created_ids}"
            )

        finally:
            # Cleanup
            AuditLog.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        num_logs=st.integers(min_value=1, max_value=150),
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_total_pages_calculation_is_correct(self, num_logs):
        """
        **Feature: advanced-tenant-management, Property 11: Pagination Consistency**
        **Validates: Requirements 4.7**

        For any paginated result set, the total number of pages SHALL be
        ceil(total_entries / PAGE_SIZE).
        """
        import math

        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create audit logs
            create_audit_logs_for_tenant(tenant, num_logs)

            # Get paginator
            paginator, _ = get_paginated_activity_logs(tenant)

            # Property: Total pages should be ceil(num_logs / PAGE_SIZE)
            expected_pages = math.ceil(num_logs / PAGE_SIZE)
            assert (
                paginator.num_pages == expected_pages
            ), f"Total pages is {paginator.num_pages}, expected {expected_pages}"

        finally:
            # Cleanup
            AuditLog.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        num_logs=st.integers(min_value=51, max_value=150),
        page_number=st.integers(min_value=1, max_value=3),
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_specific_page_returns_correct_entries(self, num_logs, page_number):
        """
        **Feature: advanced-tenant-management, Property 11: Pagination Consistency**
        **Validates: Requirements 4.7**

        For any specific page request, the returned entries SHALL be the correct
        subset of the total result set.
        """
        import math

        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create audit logs
            create_audit_logs_for_tenant(tenant, num_logs)

            # Calculate expected pages
            expected_pages = math.ceil(num_logs / PAGE_SIZE)

            # Adjust page_number to be within valid range
            valid_page = min(page_number, expected_pages)

            # Get specific page
            paginator, page = get_paginated_activity_logs(tenant, valid_page)

            # Get all logs ordered by -timestamp
            all_logs = list(AuditLog.objects.filter(tenant=tenant).order_by("-timestamp"))

            # Calculate expected entries for this page
            start_idx = (valid_page - 1) * PAGE_SIZE
            end_idx = min(start_idx + PAGE_SIZE, num_logs)
            expected_ids = [log.id for log in all_logs[start_idx:end_idx]]

            # Get actual entries from page
            actual_ids = [log.id for log in page.object_list]

            # Property: Page entries should match expected subset
            assert actual_ids == expected_ids, (
                f"Page {valid_page} entries don't match expected subset. "
                f"Expected {len(expected_ids)} entries, got {len(actual_ids)}"
            )

        finally:
            # Cleanup
            AuditLog.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        num_logs=st.integers(min_value=1, max_value=50),
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_single_page_when_entries_less_than_page_size(self, num_logs):
        """
        **Feature: advanced-tenant-management, Property 11: Pagination Consistency**
        **Validates: Requirements 4.7**

        When total entries <= PAGE_SIZE, there SHALL be exactly one page
        containing all entries.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create audit logs
            created_logs = create_audit_logs_for_tenant(tenant, num_logs)
            created_ids = set(log.id for log in created_logs)

            # Get paginator
            paginator, page = get_paginated_activity_logs(tenant)

            # Property: Should have exactly one page
            assert (
                paginator.num_pages == 1
            ), f"Expected 1 page for {num_logs} entries, got {paginator.num_pages}"

            # Property: Single page should contain all entries
            page_ids = set(log.id for log in page.object_list)
            assert page_ids == created_ids, (
                f"Single page doesn't contain all entries. " f"Missing: {created_ids - page_ids}"
            )

        finally:
            # Cleanup
            AuditLog.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        num_logs=st.integers(min_value=51, max_value=150),
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_pagination_preserves_ordering(self, num_logs):
        """
        **Feature: advanced-tenant-management, Property 11: Pagination Consistency**
        **Validates: Requirements 4.7**

        For any paginated result set, the ordering SHALL be preserved across pages
        (entries on page N+1 should come after entries on page N in the sort order).
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create audit logs
            create_audit_logs_for_tenant(tenant, num_logs)

            # Collect all pages
            all_entry_ids, page_sizes, total_pages = collect_all_pages(tenant)

            # Get all logs in expected order
            all_logs_ordered = list(
                AuditLog.objects.filter(tenant=tenant)
                .order_by("-timestamp")
                .values_list("id", flat=True)
            )

            # Property: Collected entries should be in the same order as the full query
            assert (
                all_entry_ids == all_logs_ordered
            ), "Pagination does not preserve ordering across pages"

        finally:
            # Cleanup
            AuditLog.objects.filter(tenant=tenant).delete()
            tenant.delete()

    def test_empty_result_set_pagination(self):
        """
        **Feature: advanced-tenant-management, Property 11: Pagination Consistency**
        **Validates: Requirements 4.7**

        For an empty result set, pagination SHALL return zero pages with no entries.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Get paginator for empty tenant
            paginator, page = get_paginated_activity_logs(tenant)

            # Property: Should have one page (Django's Paginator behavior)
            # Note: Django's Paginator returns 1 page even for empty queryset
            assert (
                paginator.num_pages == 1
            ), f"Expected 1 page for empty result set, got {paginator.num_pages}"

            # Property: Page should have no entries
            assert (
                len(page.object_list) == 0
            ), f"Expected 0 entries for empty result set, got {len(page.object_list)}"

        finally:
            # Cleanup
            tenant.delete()

    @given(
        num_logs=st.integers(min_value=100, max_value=150),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_last_page_size_calculation(self, num_logs):
        """
        **Feature: advanced-tenant-management, Property 11: Pagination Consistency**
        **Validates: Requirements 4.7**

        For any paginated result set, the last page size SHALL be
        (total_entries % PAGE_SIZE) or PAGE_SIZE if evenly divisible.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create audit logs
            create_audit_logs_for_tenant(tenant, num_logs)

            # Collect all pages
            all_entry_ids, page_sizes, total_pages = collect_all_pages(tenant)

            # Calculate expected last page size
            remainder = num_logs % PAGE_SIZE
            expected_last_page_size = remainder if remainder > 0 else PAGE_SIZE

            # Property: Last page size should match expected
            actual_last_page_size = page_sizes[-1]
            assert actual_last_page_size == expected_last_page_size, (
                f"Last page has {actual_last_page_size} entries, "
                f"expected {expected_last_page_size} for {num_logs} total entries"
            )

        finally:
            # Cleanup
            AuditLog.objects.filter(tenant=tenant).delete()
            tenant.delete()
