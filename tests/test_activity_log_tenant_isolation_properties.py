"""
Property-based tests for activity log tenant isolation in tenant management.

**Feature: advanced-tenant-management, Property 9: Activity Log Tenant Isolation**
**Validates: Requirements 4.1, 11.2**

Property 9: Activity Log Tenant Isolation
*For any* tenant's Activity tab, all displayed AuditLog entries SHALL have tenant_id
matching the selected tenant.
"""

import string
import uuid
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

import pytest
from hypothesis import HealthCheck, assume, given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from apps.core.audit_models import AuditLog
from apps.core.models import Tenant, User

# ============================================================================
# Strategies for generating test data
# ============================================================================


@st.composite
def tenant_slug_strategy(draw):
    """Generate valid tenant slugs."""
    slug = draw(
        st.text(alphabet=string.ascii_lowercase + string.digits + "-", min_size=3, max_size=20)
    )
    # Ensure slug starts and ends with alphanumeric
    assume(slug and slug[0].isalnum() and slug[-1].isalnum())
    # Ensure no consecutive hyphens
    assume("--" not in slug)
    return slug


@st.composite
def audit_log_category_strategy(draw):
    """Generate valid audit log categories."""
    categories = [choice[0] for choice in AuditLog.CATEGORY_CHOICES]
    return draw(st.sampled_from(categories))


@st.composite
def audit_log_action_strategy(draw):
    """Generate valid audit log actions."""
    actions = [choice[0] for choice in AuditLog.ACTION_CHOICES]
    return draw(st.sampled_from(actions))


@st.composite
def audit_log_severity_strategy(draw):
    """Generate valid audit log severity levels."""
    severities = [choice[0] for choice in AuditLog.SEVERITY_CHOICES]
    return draw(st.sampled_from(severities))


# ============================================================================
# Helper Functions
# ============================================================================


def get_activity_logs_for_tenant(tenant, category_filter=None, date_range=None):
    """
    Execute activity log query for a tenant using the same logic as _get_activity_context.

    This mirrors the implementation in apps/core/admin_views.py:
    - Filter by tenant
    - Optionally filter by category
    - Optionally filter by date range
    """
    logs = AuditLog.objects.filter(tenant=tenant).select_related("user").order_by("-timestamp")

    if category_filter:
        logs = logs.filter(category=category_filter)

    if date_range:
        if date_range == "24h":
            since = timezone.now() - timedelta(hours=24)
            logs = logs.filter(timestamp__gte=since)
        elif date_range == "7d":
            since = timezone.now() - timedelta(days=7)
            logs = logs.filter(timestamp__gte=since)
        elif date_range == "30d":
            since = timezone.now() - timedelta(days=30)
            logs = logs.filter(timestamp__gte=since)
        elif date_range == "90d":
            since = timezone.now() - timedelta(days=90)
            logs = logs.filter(timestamp__gte=since)

    return logs


def create_audit_log_for_tenant(tenant, user=None, category=None, action=None, severity=None):
    """Create an audit log entry for a tenant."""
    return AuditLog.objects.create(
        tenant=tenant,
        user=user,
        category=category or AuditLog.CATEGORY_USER,
        action=action or AuditLog.ACTION_LOGIN_SUCCESS,
        severity=severity or AuditLog.SEVERITY_INFO,
        description=f"Test audit log for tenant {tenant.slug}",
        ip_address="127.0.0.1",
        user_agent="Test User Agent",
    )


# ============================================================================
# Property Tests
# ============================================================================


@pytest.mark.django_db
class TestActivityLogTenantIsolation:
    """
    **Feature: advanced-tenant-management, Property 9: Activity Log Tenant Isolation**
    **Validates: Requirements 4.1, 11.2**

    Property tests for activity log tenant isolation ensuring:
    1. All returned audit logs have tenant_id matching the selected tenant
    2. No audit logs from other tenants are returned
    3. Tenant isolation is maintained with various filters
    """

    @given(
        num_logs_per_tenant=st.integers(min_value=2, max_value=5),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_activity_logs_belong_to_selected_tenant(self, num_logs_per_tenant):
        """
        **Feature: advanced-tenant-management, Property 9: Activity Log Tenant Isolation**
        **Validates: Requirements 4.1**

        For any tenant's Activity tab, all displayed AuditLog entries SHALL have
        tenant_id matching the selected tenant.
        """
        # Create a unique tenant for this test
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create audit logs for the tenant
            created_log_ids = []
            for i in range(num_logs_per_tenant):
                log = create_audit_log_for_tenant(tenant)
                created_log_ids.append(log.id)

            # Execute query
            results = get_activity_logs_for_tenant(tenant)

            # Property: All returned logs must have tenant_id matching the selected tenant
            for log in results:
                assert log.tenant_id == tenant.id, (
                    f"Audit log {log.id} has tenant_id {log.tenant_id}, "
                    f"but query was for tenant {tenant.id}"
                )

        finally:
            # Cleanup
            AuditLog.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        num_logs_per_tenant=st.integers(min_value=2, max_value=4),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_no_cross_tenant_log_leakage(self, num_logs_per_tenant):
        """
        **Feature: advanced-tenant-management, Property 9: Activity Log Tenant Isolation**
        **Validates: Requirements 11.2**

        For any tenant's Activity tab, no audit logs from other tenants SHALL be returned.
        """
        # Create two tenants
        tenant1 = Tenant.objects.create(
            company_name=f"Tenant One {uuid.uuid4().hex[:8]}",
            slug=f"tenant-one-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )
        tenant2 = Tenant.objects.create(
            company_name=f"Tenant Two {uuid.uuid4().hex[:8]}",
            slug=f"tenant-two-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create audit logs for tenant1
            tenant1_log_ids = []
            for i in range(num_logs_per_tenant):
                log = create_audit_log_for_tenant(tenant1)
                tenant1_log_ids.append(log.id)

            # Create audit logs for tenant2
            tenant2_log_ids = []
            for i in range(num_logs_per_tenant):
                log = create_audit_log_for_tenant(tenant2)
                tenant2_log_ids.append(log.id)

            # Execute query for tenant1
            results = get_activity_logs_for_tenant(tenant1)
            result_ids = set(results.values_list("id", flat=True))

            # Property: All returned logs must belong to tenant1
            for log in results:
                assert log.tenant_id == tenant1.id, (
                    f"Audit log {log.id} belongs to tenant {log.tenant_id}, "
                    f"but query was for tenant {tenant1.id}"
                )

            # Property: No logs from tenant2 should be in results
            tenant2_log_ids_set = set(tenant2_log_ids)
            assert not tenant2_log_ids_set.intersection(
                result_ids
            ), f"Query for tenant1 returned logs from tenant2"

        finally:
            # Cleanup
            AuditLog.objects.filter(tenant__in=[tenant1, tenant2]).delete()
            tenant1.delete()
            tenant2.delete()

    @given(
        category=audit_log_category_strategy(),
        num_logs=st.integers(min_value=2, max_value=4),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_tenant_isolation_with_category_filter(self, category, num_logs):
        """
        **Feature: advanced-tenant-management, Property 9: Activity Log Tenant Isolation**
        **Validates: Requirements 4.1, 11.2**

        For any tenant's Activity tab with category filter applied, all displayed
        AuditLog entries SHALL have tenant_id matching the selected tenant.
        """
        # Create two tenants
        tenant1 = Tenant.objects.create(
            company_name=f"Tenant One {uuid.uuid4().hex[:8]}",
            slug=f"tenant-one-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )
        tenant2 = Tenant.objects.create(
            company_name=f"Tenant Two {uuid.uuid4().hex[:8]}",
            slug=f"tenant-two-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create audit logs with the specified category for both tenants
            for i in range(num_logs):
                create_audit_log_for_tenant(tenant1, category=category)
                create_audit_log_for_tenant(tenant2, category=category)

            # Execute query for tenant1 with category filter
            results = get_activity_logs_for_tenant(tenant1, category_filter=category)

            # Property: All returned logs must belong to tenant1
            for log in results:
                assert log.tenant_id == tenant1.id, (
                    f"Audit log {log.id} belongs to tenant {log.tenant_id}, "
                    f"but query was for tenant {tenant1.id}"
                )
                assert log.category == category, (
                    f"Audit log {log.id} has category {log.category}, "
                    f"but filter was for category {category}"
                )

        finally:
            # Cleanup
            AuditLog.objects.filter(tenant__in=[tenant1, tenant2]).delete()
            tenant1.delete()
            tenant2.delete()

    @given(
        date_range=st.sampled_from(["24h", "7d", "30d", "90d"]),
        num_logs=st.integers(min_value=2, max_value=4),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_tenant_isolation_with_date_range_filter(self, date_range, num_logs):
        """
        **Feature: advanced-tenant-management, Property 9: Activity Log Tenant Isolation**
        **Validates: Requirements 4.1, 11.2**

        For any tenant's Activity tab with date range filter applied, all displayed
        AuditLog entries SHALL have tenant_id matching the selected tenant.
        """
        # Create two tenants
        tenant1 = Tenant.objects.create(
            company_name=f"Tenant One {uuid.uuid4().hex[:8]}",
            slug=f"tenant-one-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )
        tenant2 = Tenant.objects.create(
            company_name=f"Tenant Two {uuid.uuid4().hex[:8]}",
            slug=f"tenant-two-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create audit logs for both tenants (they will have current timestamp)
            for i in range(num_logs):
                create_audit_log_for_tenant(tenant1)
                create_audit_log_for_tenant(tenant2)

            # Execute query for tenant1 with date range filter
            results = get_activity_logs_for_tenant(tenant1, date_range=date_range)

            # Property: All returned logs must belong to tenant1
            for log in results:
                assert log.tenant_id == tenant1.id, (
                    f"Audit log {log.id} belongs to tenant {log.tenant_id}, "
                    f"but query was for tenant {tenant1.id}"
                )

        finally:
            # Cleanup
            AuditLog.objects.filter(tenant__in=[tenant1, tenant2]).delete()
            tenant1.delete()
            tenant2.delete()

    @given(
        num_logs_other_tenant=st.integers(min_value=2, max_value=5),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_empty_tenant_returns_no_logs(self, num_logs_other_tenant):
        """
        **Feature: advanced-tenant-management, Property 9: Activity Log Tenant Isolation**
        **Validates: Requirements 4.1, 11.2**

        For a tenant with no audit logs, the query SHALL return empty results,
        not logs from other tenants.
        """
        # Create two tenants
        tenant_empty = Tenant.objects.create(
            company_name=f"Empty Tenant {uuid.uuid4().hex[:8]}",
            slug=f"empty-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )
        tenant_with_logs = Tenant.objects.create(
            company_name=f"Tenant With Logs {uuid.uuid4().hex[:8]}",
            slug=f"with-logs-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create audit logs only for tenant_with_logs
            for i in range(num_logs_other_tenant):
                create_audit_log_for_tenant(tenant_with_logs)

            # Execute query for tenant_empty
            results = get_activity_logs_for_tenant(tenant_empty)

            # Property: Empty tenant should return no logs
            assert results.count() == 0, f"Empty tenant returned {results.count()} logs, expected 0"

        finally:
            # Cleanup
            AuditLog.objects.filter(tenant__in=[tenant_empty, tenant_with_logs]).delete()
            tenant_empty.delete()
            tenant_with_logs.delete()

    @given(
        num_logs=st.integers(min_value=2, max_value=4),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_tenant_isolation_is_deterministic(self, num_logs):
        """
        **Feature: advanced-tenant-management, Property 9: Activity Log Tenant Isolation**
        **Validates: Requirements 4.1**

        For any tenant's Activity tab, executing the same query multiple times
        SHALL return the same results.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create audit logs for the tenant
            for i in range(num_logs):
                create_audit_log_for_tenant(tenant)

            # Execute query multiple times
            results1 = set(get_activity_logs_for_tenant(tenant).values_list("id", flat=True))
            results2 = set(get_activity_logs_for_tenant(tenant).values_list("id", flat=True))
            results3 = set(get_activity_logs_for_tenant(tenant).values_list("id", flat=True))

            # Property: All queries should return the same results
            assert results1 == results2 == results3, (
                f"Query results are not deterministic. "
                f"Results: {len(results1)}, {len(results2)}, {len(results3)}"
            )

        finally:
            # Cleanup
            AuditLog.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        num_tenants=st.integers(min_value=3, max_value=5),
        num_logs_per_tenant=st.integers(min_value=2, max_value=3),
    )
    @hypothesis_settings(
        max_examples=30,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_tenant_isolation_with_multiple_tenants(self, num_tenants, num_logs_per_tenant):
        """
        **Feature: advanced-tenant-management, Property 9: Activity Log Tenant Isolation**
        **Validates: Requirements 4.1, 11.2**

        For any tenant in a system with multiple tenants, the Activity tab SHALL
        only display logs belonging to that specific tenant.
        """
        tenants = []

        try:
            # Create multiple tenants
            for i in range(num_tenants):
                tenant = Tenant.objects.create(
                    company_name=f"Tenant {i} {uuid.uuid4().hex[:8]}",
                    slug=f"tenant-{i}-{uuid.uuid4().hex[:12]}",
                    status=Tenant.ACTIVE,
                )
                tenants.append(tenant)

                # Create audit logs for each tenant
                for j in range(num_logs_per_tenant):
                    create_audit_log_for_tenant(tenant)

            # For each tenant, verify isolation
            for target_tenant in tenants:
                results = get_activity_logs_for_tenant(target_tenant)

                # Property: All returned logs must belong to target_tenant
                for log in results:
                    assert log.tenant_id == target_tenant.id, (
                        f"Audit log {log.id} belongs to tenant {log.tenant_id}, "
                        f"but query was for tenant {target_tenant.id}"
                    )

                # Property: Result count should match logs created for this tenant
                assert results.count() == num_logs_per_tenant, (
                    f"Expected {num_logs_per_tenant} logs for tenant {target_tenant.id}, "
                    f"got {results.count()}"
                )

        finally:
            # Cleanup
            for tenant in tenants:
                AuditLog.objects.filter(tenant=tenant).delete()
                tenant.delete()

    @given(
        num_logs=st.integers(min_value=2, max_value=4),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_tenant_isolation_with_security_filter(self, num_logs):
        """
        **Feature: advanced-tenant-management, Property 9: Activity Log Tenant Isolation**
        **Validates: Requirements 4.1, 11.2**

        For any tenant's Activity tab with security events filter, all displayed
        AuditLog entries SHALL have tenant_id matching the selected tenant.
        """
        # Create two tenants
        tenant1 = Tenant.objects.create(
            company_name=f"Tenant One {uuid.uuid4().hex[:8]}",
            slug=f"tenant-one-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )
        tenant2 = Tenant.objects.create(
            company_name=f"Tenant Two {uuid.uuid4().hex[:8]}",
            slug=f"tenant-two-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create security audit logs for both tenants
            for i in range(num_logs):
                create_audit_log_for_tenant(
                    tenant1,
                    category=AuditLog.CATEGORY_SECURITY,
                    action=AuditLog.ACTION_LOGIN_FAILED,
                )
                create_audit_log_for_tenant(
                    tenant2,
                    category=AuditLog.CATEGORY_SECURITY,
                    action=AuditLog.ACTION_LOGIN_FAILED,
                )

            # Execute query for tenant1 with security category filter
            results = get_activity_logs_for_tenant(
                tenant1, category_filter=AuditLog.CATEGORY_SECURITY
            )

            # Property: All returned logs must belong to tenant1
            for log in results:
                assert log.tenant_id == tenant1.id, (
                    f"Audit log {log.id} belongs to tenant {log.tenant_id}, "
                    f"but query was for tenant {tenant1.id}"
                )

        finally:
            # Cleanup
            AuditLog.objects.filter(tenant__in=[tenant1, tenant2]).delete()
            tenant1.delete()
            tenant2.delete()
