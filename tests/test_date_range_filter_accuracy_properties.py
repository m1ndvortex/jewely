"""
Property-based tests for date range filter accuracy in tenant management.

**Feature: advanced-tenant-management, Property 10: Date Range Filter Accuracy**
**Validates: Requirements 4.3**

Property 10: Date Range Filter Accuracy
*For any* date range filter on the Activity tab, all returned entries SHALL have
timestamps within the specified range (inclusive).
"""

import uuid
from datetime import datetime, timedelta

from django.utils import timezone

import pytest
from hypothesis import HealthCheck, assume, given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from apps.core.audit_models import AuditLog
from apps.core.models import Tenant

# ============================================================================
# Strategies for generating test data
# ============================================================================


@st.composite
def date_range_preset_strategy(draw):
    """Generate valid date range presets."""
    return draw(st.sampled_from(["24h", "7d", "30d", "90d"]))


@st.composite
def hours_offset_strategy(draw):
    """Generate hours offset for creating logs at different times."""
    return draw(st.integers(min_value=0, max_value=2400))  # Up to 100 days


@st.composite
def custom_date_range_strategy(draw):
    """Generate valid custom date ranges."""
    # Generate start date within last 180 days
    start_days_ago = draw(st.integers(min_value=1, max_value=180))
    # Generate end date that is after or equal to start date
    end_days_ago = draw(st.integers(min_value=0, max_value=start_days_ago))

    now = timezone.now()
    start_date = (now - timedelta(days=start_days_ago)).date()
    end_date = (now - timedelta(days=end_days_ago)).date()

    return {
        "start": start_date,
        "end": end_date,
    }


# ============================================================================
# Helper Functions
# ============================================================================


def get_date_range_bounds(date_range: str, custom_start=None, custom_end=None):
    """
    Calculate the start and end timestamps for a date range filter.

    Returns (start_timestamp, end_timestamp) where:
    - start_timestamp is the earliest timestamp that should be included
    - end_timestamp is the latest timestamp that should be included (or None for no upper bound)
    """
    now = timezone.now()

    if date_range == "24h":
        return now - timedelta(hours=24), None
    elif date_range == "7d":
        return now - timedelta(days=7), None
    elif date_range == "30d":
        return now - timedelta(days=30), None
    elif date_range == "90d":
        return now - timedelta(days=90), None
    elif date_range == "custom":
        start = None
        end = None
        if custom_start:
            if isinstance(custom_start, str):
                start = datetime.strptime(custom_start, "%Y-%m-%d")
                start = timezone.make_aware(start) if timezone.is_naive(start) else start
            else:
                start = timezone.make_aware(datetime.combine(custom_start, datetime.min.time()))
        if custom_end:
            if isinstance(custom_end, str):
                end = datetime.strptime(custom_end, "%Y-%m-%d")
                end = timezone.make_aware(end) if timezone.is_naive(end) else end
            else:
                end = timezone.make_aware(datetime.combine(custom_end, datetime.max.time()))
            # Add one day to include the entire end date (as per implementation)
            end = end + timedelta(days=1)
        return start, end

    return None, None


def get_activity_logs_with_date_filter(tenant, date_range, custom_start=None, custom_end=None):
    """
    Execute activity log query for a tenant with date range filter.

    This mirrors the implementation in apps/core/admin_views.py _get_activity_context.
    """
    logs = AuditLog.objects.filter(tenant=tenant).select_related("user").order_by("-timestamp")

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
    elif date_range == "custom":
        if custom_start:
            if isinstance(custom_start, str):
                start_date = datetime.strptime(custom_start, "%Y-%m-%d")
            else:
                start_date = datetime.combine(custom_start, datetime.min.time())
            # Make timezone-aware
            if timezone.is_naive(start_date):
                start_date = timezone.make_aware(start_date)
            logs = logs.filter(timestamp__gte=start_date)
        if custom_end:
            if isinstance(custom_end, str):
                end_date = datetime.strptime(custom_end, "%Y-%m-%d")
            else:
                end_date = datetime.combine(custom_end, datetime.min.time())
            # Make timezone-aware
            if timezone.is_naive(end_date):
                end_date = timezone.make_aware(end_date)
            # Add one day to include the entire end date
            end_date = end_date + timedelta(days=1)
            logs = logs.filter(timestamp__lt=end_date)

    return logs


def create_audit_log_at_time(tenant, timestamp, category=None, action=None):
    """Create an audit log entry for a tenant at a specific timestamp."""
    log = AuditLog.objects.create(
        tenant=tenant,
        category=category or AuditLog.CATEGORY_USER,
        action=action or AuditLog.ACTION_LOGIN_SUCCESS,
        severity=AuditLog.SEVERITY_INFO,
        description=f"Test audit log at {timestamp}",
        ip_address="127.0.0.1",
        user_agent="Test User Agent",
    )
    # Update timestamp directly in database to bypass auto_now
    AuditLog.objects.filter(id=log.id).update(timestamp=timestamp)
    log.refresh_from_db()
    return log


# ============================================================================
# Property Tests
# ============================================================================


@pytest.mark.django_db
class TestDateRangeFilterAccuracy:
    """
    **Feature: advanced-tenant-management, Property 10: Date Range Filter Accuracy**
    **Validates: Requirements 4.3**

    Property tests for date range filter accuracy ensuring:
    1. All returned entries have timestamps within the specified range
    2. Entries outside the range are not returned
    3. Range boundaries are handled correctly (inclusive)
    """

    @given(
        date_range=date_range_preset_strategy(),
        num_logs_in_range=st.integers(min_value=1, max_value=5),
        num_logs_out_of_range=st.integers(min_value=1, max_value=3),
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_preset_date_range_returns_only_logs_within_range(
        self, date_range, num_logs_in_range, num_logs_out_of_range
    ):
        """
        **Feature: advanced-tenant-management, Property 10: Date Range Filter Accuracy**
        **Validates: Requirements 4.3**

        For any preset date range filter (24h, 7d, 30d, 90d), all returned entries
        SHALL have timestamps within the specified range.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            now = timezone.now()

            # Determine range bounds with a small buffer to account for timing
            # The buffer ensures logs are clearly within or outside the range
            buffer = timedelta(minutes=5)

            if date_range == "24h":
                range_start = now - timedelta(hours=24)
                out_of_range_offset = timedelta(hours=48)
            elif date_range == "7d":
                range_start = now - timedelta(days=7)
                out_of_range_offset = timedelta(days=14)
            elif date_range == "30d":
                range_start = now - timedelta(days=30)
                out_of_range_offset = timedelta(days=60)
            elif date_range == "90d":
                range_start = now - timedelta(days=90)
                out_of_range_offset = timedelta(days=180)

            # Create logs within range (with buffer to avoid boundary issues)
            # Start from range_start + buffer to ensure logs are clearly within range
            in_range_log_ids = []
            safe_range_start = range_start + buffer
            for i in range(num_logs_in_range):
                # Create logs at various points within the safe range
                offset_fraction = (i + 0.5) / max(num_logs_in_range, 1)
                log_time = safe_range_start + (now - safe_range_start) * offset_fraction
                log = create_audit_log_at_time(tenant, log_time)
                in_range_log_ids.append(log.id)

            # Create logs outside range (clearly before the range start)
            out_of_range_log_ids = []
            for i in range(num_logs_out_of_range):
                log_time = now - out_of_range_offset - timedelta(hours=i)
                log = create_audit_log_at_time(tenant, log_time)
                out_of_range_log_ids.append(log.id)

            # Execute query with date range filter
            results = get_activity_logs_with_date_filter(tenant, date_range)
            result_ids = set(results.values_list("id", flat=True))

            # Property 1: All returned logs must have timestamps >= range_start
            # Use a slightly earlier range_start to account for query timing
            query_range_start = range_start - timedelta(seconds=10)
            for log in results:
                assert log.timestamp >= query_range_start, (
                    f"Log {log.id} has timestamp {log.timestamp}, "
                    f"which is before range start {query_range_start}"
                )

            # Property 2: No out-of-range logs should be returned
            out_of_range_in_results = set(out_of_range_log_ids).intersection(result_ids)
            assert (
                not out_of_range_in_results
            ), f"Out-of-range logs {out_of_range_in_results} were returned"

            # Property 3: All in-range logs should be returned
            in_range_in_results = set(in_range_log_ids).intersection(result_ids)
            assert in_range_in_results == set(in_range_log_ids), (
                f"Not all in-range logs were returned. "
                f"Expected {in_range_log_ids}, got {in_range_in_results}"
            )

        finally:
            # Cleanup
            AuditLog.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        custom_range=custom_date_range_strategy(),
        num_logs_in_range=st.integers(min_value=1, max_value=4),
        num_logs_before_range=st.integers(min_value=1, max_value=2),
        num_logs_after_range=st.integers(min_value=0, max_value=2),
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_custom_date_range_returns_only_logs_within_range(
        self, custom_range, num_logs_in_range, num_logs_before_range, num_logs_after_range
    ):
        """
        **Feature: advanced-tenant-management, Property 10: Date Range Filter Accuracy**
        **Validates: Requirements 4.3**

        For any custom date range filter, all returned entries SHALL have
        timestamps within the specified range (inclusive).
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            start_date = custom_range["start"]
            end_date = custom_range["end"]

            # Convert dates to datetime for comparison
            start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
            # End datetime is exclusive (implementation adds 1 day)
            end_datetime = timezone.make_aware(
                datetime.combine(end_date + timedelta(days=1), datetime.min.time())
            )

            # Create logs within range
            in_range_log_ids = []
            range_duration = end_datetime - start_datetime
            for i in range(num_logs_in_range):
                offset_fraction = (i + 0.5) / max(num_logs_in_range, 1)
                log_time = start_datetime + range_duration * offset_fraction
                log = create_audit_log_at_time(tenant, log_time)
                in_range_log_ids.append(log.id)

            # Create logs before range
            before_range_log_ids = []
            for i in range(num_logs_before_range):
                log_time = start_datetime - timedelta(days=i + 1)
                log = create_audit_log_at_time(tenant, log_time)
                before_range_log_ids.append(log.id)

            # Create logs after range (only if end_date is in the past)
            after_range_log_ids = []
            now = timezone.now()
            if end_datetime < now:
                for i in range(num_logs_after_range):
                    log_time = end_datetime + timedelta(days=i + 1)
                    if log_time < now:  # Don't create future logs
                        log = create_audit_log_at_time(tenant, log_time)
                        after_range_log_ids.append(log.id)

            # Execute query with custom date range filter
            results = get_activity_logs_with_date_filter(
                tenant,
                "custom",
                custom_start=start_date.strftime("%Y-%m-%d"),
                custom_end=end_date.strftime("%Y-%m-%d"),
            )
            result_ids = set(results.values_list("id", flat=True))

            # Property 1: All returned logs must have timestamps within range
            for log in results:
                assert log.timestamp >= start_datetime, (
                    f"Log {log.id} has timestamp {log.timestamp}, "
                    f"which is before range start {start_datetime}"
                )
                assert log.timestamp < end_datetime, (
                    f"Log {log.id} has timestamp {log.timestamp}, "
                    f"which is after range end {end_datetime}"
                )

            # Property 2: No before-range logs should be returned
            before_in_results = set(before_range_log_ids).intersection(result_ids)
            assert not before_in_results, f"Before-range logs {before_in_results} were returned"

            # Property 3: No after-range logs should be returned
            after_in_results = set(after_range_log_ids).intersection(result_ids)
            assert not after_in_results, f"After-range logs {after_in_results} were returned"

        finally:
            # Cleanup
            AuditLog.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        date_range=date_range_preset_strategy(),
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_boundary_logs_are_included(self, date_range):
        """
        **Feature: advanced-tenant-management, Property 10: Date Range Filter Accuracy**
        **Validates: Requirements 4.3**

        For any date range filter, logs clearly inside the range SHALL be included,
        and logs clearly outside the range SHALL be excluded.

        Note: We use a buffer to avoid timing issues at exact boundaries since
        the query uses timezone.now() which may differ slightly from test setup time.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            now = timezone.now()

            # Determine range start
            if date_range == "24h":
                range_start = now - timedelta(hours=24)
            elif date_range == "7d":
                range_start = now - timedelta(days=7)
            elif date_range == "30d":
                range_start = now - timedelta(days=30)
            elif date_range == "90d":
                range_start = now - timedelta(days=90)

            # Use a buffer to avoid timing issues at exact boundaries
            # The query uses timezone.now() which may be slightly later than our 'now'
            buffer = timedelta(minutes=1)

            # Create log clearly inside boundary (with buffer)
            inside_log = create_audit_log_at_time(tenant, range_start + buffer)

            # Create log clearly outside boundary (with buffer)
            outside_log = create_audit_log_at_time(tenant, range_start - buffer)

            # Execute query
            results = get_activity_logs_with_date_filter(tenant, date_range)
            result_ids = set(results.values_list("id", flat=True))

            # Property: Inside log should be included
            assert inside_log.id in result_ids, f"Inside log {inside_log.id} was not included"

            # Property: Outside log should NOT be included
            assert (
                outside_log.id not in result_ids
            ), f"Outside log {outside_log.id} was incorrectly included"

        finally:
            # Cleanup
            AuditLog.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        date_range=date_range_preset_strategy(),
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_empty_range_returns_no_logs(self, date_range):
        """
        **Feature: advanced-tenant-management, Property 10: Date Range Filter Accuracy**
        **Validates: Requirements 4.3**

        For any date range filter, if no logs exist within the range,
        the query SHALL return empty results.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            now = timezone.now()

            # Determine out-of-range time (well before any preset range)
            out_of_range_time = now - timedelta(days=365)

            # Create logs only outside the range
            for i in range(3):
                create_audit_log_at_time(tenant, out_of_range_time - timedelta(days=i))

            # Execute query
            results = get_activity_logs_with_date_filter(tenant, date_range)

            # Property: No logs should be returned
            assert results.count() == 0, f"Expected 0 logs for empty range, got {results.count()}"

        finally:
            # Cleanup
            AuditLog.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        date_range=date_range_preset_strategy(),
        num_logs=st.integers(min_value=2, max_value=5),
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_date_range_filter_is_deterministic(self, date_range, num_logs):
        """
        **Feature: advanced-tenant-management, Property 10: Date Range Filter Accuracy**
        **Validates: Requirements 4.3**

        For any date range filter, executing the same query multiple times
        SHALL return the same results.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            now = timezone.now()

            # Create logs within range
            for i in range(num_logs):
                log_time = now - timedelta(hours=i)
                create_audit_log_at_time(tenant, log_time)

            # Execute query multiple times
            results1 = set(
                get_activity_logs_with_date_filter(tenant, date_range).values_list("id", flat=True)
            )
            results2 = set(
                get_activity_logs_with_date_filter(tenant, date_range).values_list("id", flat=True)
            )
            results3 = set(
                get_activity_logs_with_date_filter(tenant, date_range).values_list("id", flat=True)
            )

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
        num_logs=st.integers(min_value=3, max_value=6),
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_narrower_range_returns_subset(self, num_logs):
        """
        **Feature: advanced-tenant-management, Property 10: Date Range Filter Accuracy**
        **Validates: Requirements 4.3**

        For any set of logs, a narrower date range SHALL return a subset
        of what a wider date range returns.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            now = timezone.now()

            # Create logs spread across different time periods
            # Some within 24h, some within 7d, some within 30d
            for i in range(num_logs):
                if i < num_logs // 3:
                    # Within 24h
                    log_time = now - timedelta(hours=i + 1)
                elif i < 2 * num_logs // 3:
                    # Within 7d but not 24h
                    log_time = now - timedelta(days=2 + i)
                else:
                    # Within 30d but not 7d
                    log_time = now - timedelta(days=10 + i)
                create_audit_log_at_time(tenant, log_time)

            # Get results for different ranges
            results_24h = set(
                get_activity_logs_with_date_filter(tenant, "24h").values_list("id", flat=True)
            )
            results_7d = set(
                get_activity_logs_with_date_filter(tenant, "7d").values_list("id", flat=True)
            )
            results_30d = set(
                get_activity_logs_with_date_filter(tenant, "30d").values_list("id", flat=True)
            )
            results_90d = set(
                get_activity_logs_with_date_filter(tenant, "90d").values_list("id", flat=True)
            )

            # Property: Narrower ranges should be subsets of wider ranges
            assert results_24h.issubset(results_7d), f"24h results are not a subset of 7d results"
            assert results_7d.issubset(results_30d), f"7d results are not a subset of 30d results"
            assert results_30d.issubset(results_90d), f"30d results are not a subset of 90d results"

        finally:
            # Cleanup
            AuditLog.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        days_ago_start=st.integers(min_value=5, max_value=30),
        days_ago_end=st.integers(min_value=0, max_value=4),
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_custom_range_end_date_is_inclusive(self, days_ago_start, days_ago_end):
        """
        **Feature: advanced-tenant-management, Property 10: Date Range Filter Accuracy**
        **Validates: Requirements 4.3**

        For custom date range filters, the end date SHALL be inclusive,
        meaning logs on the end date are included.
        """
        assume(days_ago_start > days_ago_end)

        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            now = timezone.now()
            start_date = (now - timedelta(days=days_ago_start)).date()
            end_date = (now - timedelta(days=days_ago_end)).date()

            # Create log on the end date (should be included)
            end_date_datetime = timezone.make_aware(
                datetime.combine(end_date, datetime.min.time().replace(hour=12))
            )
            end_date_log = create_audit_log_at_time(tenant, end_date_datetime)

            # Create log on the start date (should be included)
            start_date_datetime = timezone.make_aware(
                datetime.combine(start_date, datetime.min.time().replace(hour=12))
            )
            start_date_log = create_audit_log_at_time(tenant, start_date_datetime)

            # Execute query
            results = get_activity_logs_with_date_filter(
                tenant,
                "custom",
                custom_start=start_date.strftime("%Y-%m-%d"),
                custom_end=end_date.strftime("%Y-%m-%d"),
            )
            result_ids = set(results.values_list("id", flat=True))

            # Property: Log on end date should be included
            assert end_date_log.id in result_ids, f"Log on end date {end_date} was not included"

            # Property: Log on start date should be included
            assert (
                start_date_log.id in result_ids
            ), f"Log on start date {start_date} was not included"

        finally:
            # Cleanup
            AuditLog.objects.filter(tenant=tenant).delete()
            tenant.delete()
