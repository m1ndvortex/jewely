"""
Property-based tests for security warning threshold in tenant management.

**Feature: advanced-tenant-management, Property 17: Security Warning Threshold**
**Validates: Requirements 10.3**

Property 17: Security Warning Threshold
*For any* user with more than 5 failed logins in 24 hours, the system SHALL display
a warning badge on the Users tab.
"""

import uuid
from datetime import timedelta

from django.utils import timezone

import pytest
from hypothesis import HealthCheck, assume, given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from apps.core.audit_models import LoginAttempt
from apps.core.models import Tenant, User
from apps.core.services.user_service import UserManagementService

# ============================================================================
# Constants
# ============================================================================

# The threshold for displaying a warning badge (per Requirements 10.3)
WARNING_THRESHOLD = 5


# ============================================================================
# Strategies for generating test data
# ============================================================================


@st.composite
def failed_login_count_strategy(draw):
    """Generate a count of failed logins (0-15 range for testing threshold)."""
    return draw(st.integers(min_value=0, max_value=15))


@st.composite
def hours_ago_strategy(draw):
    """Generate hours ago for login attempts (0-48 hours)."""
    return draw(st.integers(min_value=0, max_value=48))


@st.composite
def failed_result_strategy(draw):
    """Generate a failed login result type."""
    return draw(
        st.sampled_from(
            [
                LoginAttempt.RESULT_FAILED_PASSWORD,
                LoginAttempt.RESULT_FAILED_USER_NOT_FOUND,
                LoginAttempt.RESULT_FAILED_ACCOUNT_DISABLED,
                LoginAttempt.RESULT_FAILED_MFA,
                LoginAttempt.RESULT_FAILED_RATE_LIMIT,
            ]
        )
    )


# ============================================================================
# Helper Functions
# ============================================================================


def create_login_attempt(user, result, hours_ago=0):
    """
    Create a login attempt for a user at a specific time.

    Args:
        user: The User instance
        result: The login result (SUCCESS, FAILED_PASSWORD, etc.)
        hours_ago: How many hours ago the attempt occurred

    Returns:
        The created LoginAttempt instance
    """
    attempt_time = timezone.now() - timedelta(hours=hours_ago)

    attempt = LoginAttempt.objects.create(
        user=user,
        username=user.username,
        result=result,
        ip_address="192.168.1.1",
        user_agent="Test Agent",
    )

    # Update timestamp manually since auto_now_add prevents setting it directly
    LoginAttempt.objects.filter(id=attempt.id).update(timestamp=attempt_time)

    return LoginAttempt.objects.get(id=attempt.id)


def should_show_warning(failed_count):
    """
    Determine if a warning badge should be shown based on failed login count.

    Per Requirements 10.3: Warning shown when failed logins > 5 in 24h.
    """
    return failed_count > WARNING_THRESHOLD


# ============================================================================
# Property Tests
# ============================================================================


@pytest.mark.django_db
class TestSecurityWarningThreshold:
    """
    **Feature: advanced-tenant-management, Property 17: Security Warning Threshold**
    **Validates: Requirements 10.3**

    Property tests for security warning threshold ensuring:
    1. Users with > 5 failed logins in 24h should have warning badge
    2. Users with <= 5 failed logins in 24h should NOT have warning badge
    3. Only failed logins (not successful) are counted
    4. Only logins within 24h are counted
    """

    @given(
        failed_count=st.integers(min_value=6, max_value=15),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_users_above_threshold_have_warning(self, failed_count):
        """
        **Feature: advanced-tenant-management, Property 17: Security Warning Threshold**
        **Validates: Requirements 10.3**

        For any user with more than 5 failed logins in 24 hours,
        the system SHALL display a warning badge.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            user = User.objects.create_user(
                username=f"testuser_{uuid.uuid4().hex[:8]}",
                email=f"test_{uuid.uuid4().hex[:8]}@test.com",
                password="TestPass123!",
                tenant=tenant,
                role=User.TENANT_EMPLOYEE,
            )

            # Create failed login attempts within 24h
            for i in range(failed_count):
                create_login_attempt(
                    user=user,
                    result=LoginAttempt.RESULT_FAILED_PASSWORD,
                    hours_ago=i % 23,  # Spread within 24h
                )

            # Get users with warnings
            service = UserManagementService()
            users_with_warnings = service.get_users_with_failed_login_warning(
                tenant=tenant,
                threshold=WARNING_THRESHOLD,
            )

            # Property: User with > 5 failed logins should be in warning list
            user_ids_with_warnings = [u["user_id"] for u in users_with_warnings]
            assert (
                user.id in user_ids_with_warnings
            ), f"User with {failed_count} failed logins should have warning badge"

            # Verify the count is accurate
            user_warning = next(u for u in users_with_warnings if u["user_id"] == user.id)
            assert (
                user_warning["failed_login_count"] == failed_count
            ), f"Expected {failed_count} failed logins, got {user_warning['failed_login_count']}"

        finally:
            LoginAttempt.objects.filter(user=user).delete()
            User.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        failed_count=st.integers(min_value=0, max_value=5),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_users_at_or_below_threshold_no_warning(self, failed_count):
        """
        **Feature: advanced-tenant-management, Property 17: Security Warning Threshold**
        **Validates: Requirements 10.3**

        For any user with 5 or fewer failed logins in 24 hours,
        the system SHALL NOT display a warning badge.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            user = User.objects.create_user(
                username=f"testuser_{uuid.uuid4().hex[:8]}",
                email=f"test_{uuid.uuid4().hex[:8]}@test.com",
                password="TestPass123!",
                tenant=tenant,
                role=User.TENANT_EMPLOYEE,
            )

            # Create failed login attempts within 24h
            for i in range(failed_count):
                create_login_attempt(
                    user=user,
                    result=LoginAttempt.RESULT_FAILED_PASSWORD,
                    hours_ago=i % 23,
                )

            # Get users with warnings
            service = UserManagementService()
            users_with_warnings = service.get_users_with_failed_login_warning(
                tenant=tenant,
                threshold=WARNING_THRESHOLD,
            )

            # Property: User with <= 5 failed logins should NOT be in warning list
            user_ids_with_warnings = [u["user_id"] for u in users_with_warnings]
            assert (
                user.id not in user_ids_with_warnings
            ), f"User with {failed_count} failed logins should NOT have warning badge"

        finally:
            LoginAttempt.objects.filter(user=user).delete()
            User.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        failed_count_24h=st.integers(min_value=0, max_value=5),
        failed_count_older=st.integers(min_value=6, max_value=10),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_only_24h_logins_counted(self, failed_count_24h, failed_count_older):
        """
        **Feature: advanced-tenant-management, Property 17: Security Warning Threshold**
        **Validates: Requirements 10.3**

        For any user, only failed logins within the last 24 hours SHALL be counted
        toward the warning threshold.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            user = User.objects.create_user(
                username=f"testuser_{uuid.uuid4().hex[:8]}",
                email=f"test_{uuid.uuid4().hex[:8]}@test.com",
                password="TestPass123!",
                tenant=tenant,
                role=User.TENANT_EMPLOYEE,
            )

            # Create failed login attempts within 24h
            for i in range(failed_count_24h):
                create_login_attempt(
                    user=user,
                    result=LoginAttempt.RESULT_FAILED_PASSWORD,
                    hours_ago=i % 23,
                )

            # Create failed login attempts older than 24h
            for i in range(failed_count_older):
                create_login_attempt(
                    user=user,
                    result=LoginAttempt.RESULT_FAILED_PASSWORD,
                    hours_ago=25 + i,  # 25+ hours ago
                )

            # Get users with warnings
            service = UserManagementService()
            users_with_warnings = service.get_users_with_failed_login_warning(
                tenant=tenant,
                threshold=WARNING_THRESHOLD,
            )

            # Property: Only 24h logins should be counted
            user_ids_with_warnings = [u["user_id"] for u in users_with_warnings]

            if failed_count_24h > WARNING_THRESHOLD:
                assert (
                    user.id in user_ids_with_warnings
                ), f"User with {failed_count_24h} failed logins in 24h should have warning"
            else:
                assert user.id not in user_ids_with_warnings, (
                    f"User with {failed_count_24h} failed logins in 24h should NOT have warning "
                    f"(older logins: {failed_count_older} should not count)"
                )

            # Verify the count using get_failed_login_count_24h
            actual_count = service.get_failed_login_count_24h(user)
            assert (
                actual_count == failed_count_24h
            ), f"Expected {failed_count_24h} failed logins in 24h, got {actual_count}"

        finally:
            LoginAttempt.objects.filter(user=user).delete()
            User.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        success_count=st.integers(min_value=6, max_value=10),
        failed_count=st.integers(min_value=0, max_value=5),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_only_failed_logins_counted(self, success_count, failed_count):
        """
        **Feature: advanced-tenant-management, Property 17: Security Warning Threshold**
        **Validates: Requirements 10.3**

        For any user, only failed login attempts SHALL be counted toward the warning
        threshold. Successful logins should not affect the count.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            user = User.objects.create_user(
                username=f"testuser_{uuid.uuid4().hex[:8]}",
                email=f"test_{uuid.uuid4().hex[:8]}@test.com",
                password="TestPass123!",
                tenant=tenant,
                role=User.TENANT_EMPLOYEE,
            )

            # Create successful login attempts
            for i in range(success_count):
                create_login_attempt(
                    user=user,
                    result=LoginAttempt.RESULT_SUCCESS,
                    hours_ago=i % 23,
                )

            # Create failed login attempts
            for i in range(failed_count):
                create_login_attempt(
                    user=user,
                    result=LoginAttempt.RESULT_FAILED_PASSWORD,
                    hours_ago=i % 23,
                )

            # Get users with warnings
            service = UserManagementService()
            users_with_warnings = service.get_users_with_failed_login_warning(
                tenant=tenant,
                threshold=WARNING_THRESHOLD,
            )

            # Property: Only failed logins should be counted
            user_ids_with_warnings = [u["user_id"] for u in users_with_warnings]

            # Since failed_count <= 5, user should NOT have warning
            # (successful logins should not count)
            assert user.id not in user_ids_with_warnings, (
                f"User with {failed_count} failed logins and {success_count} successful logins "
                f"should NOT have warning badge (only failed logins count)"
            )

            # Verify the count
            actual_count = service.get_failed_login_count_24h(user)
            assert (
                actual_count == failed_count
            ), f"Expected {failed_count} failed logins, got {actual_count}"

        finally:
            LoginAttempt.objects.filter(user=user).delete()
            User.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        failed_result=failed_result_strategy(),
        failed_count=st.integers(min_value=6, max_value=10),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_all_failure_types_counted(self, failed_result, failed_count):
        """
        **Feature: advanced-tenant-management, Property 17: Security Warning Threshold**
        **Validates: Requirements 10.3**

        For any type of failed login (password, MFA, rate limit, etc.),
        the attempt SHALL be counted toward the warning threshold.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            user = User.objects.create_user(
                username=f"testuser_{uuid.uuid4().hex[:8]}",
                email=f"test_{uuid.uuid4().hex[:8]}@test.com",
                password="TestPass123!",
                tenant=tenant,
                role=User.TENANT_EMPLOYEE,
            )

            # Create failed login attempts of the specified type
            for i in range(failed_count):
                create_login_attempt(
                    user=user,
                    result=failed_result,
                    hours_ago=i % 23,
                )

            # Get users with warnings
            service = UserManagementService()
            users_with_warnings = service.get_users_with_failed_login_warning(
                tenant=tenant,
                threshold=WARNING_THRESHOLD,
            )

            # Property: All failure types should be counted
            user_ids_with_warnings = [u["user_id"] for u in users_with_warnings]
            assert (
                user.id in user_ids_with_warnings
            ), f"User with {failed_count} '{failed_result}' logins should have warning badge"

        finally:
            LoginAttempt.objects.filter(user=user).delete()
            User.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        failed_count=st.integers(min_value=6, max_value=10),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_warning_count_accuracy(self, failed_count):
        """
        **Feature: advanced-tenant-management, Property 17: Security Warning Threshold**
        **Validates: Requirements 10.3**

        For any user with warnings, the displayed failed login count SHALL match
        the actual count of failed login attempts in the last 24 hours.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            user = User.objects.create_user(
                username=f"testuser_{uuid.uuid4().hex[:8]}",
                email=f"test_{uuid.uuid4().hex[:8]}@test.com",
                password="TestPass123!",
                tenant=tenant,
                role=User.TENANT_EMPLOYEE,
            )

            # Create failed login attempts
            for i in range(failed_count):
                create_login_attempt(
                    user=user,
                    result=LoginAttempt.RESULT_FAILED_PASSWORD,
                    hours_ago=i % 23,
                )

            # Get users with warnings
            service = UserManagementService()
            users_with_warnings = service.get_users_with_failed_login_warning(
                tenant=tenant,
                threshold=WARNING_THRESHOLD,
            )

            # Find the user in warnings
            user_warning = next((u for u in users_with_warnings if u["user_id"] == user.id), None)

            assert user_warning is not None, "User should be in warning list"

            # Property: Count should be accurate
            assert user_warning["failed_login_count"] == failed_count, (
                f"Warning count {user_warning['failed_login_count']} does not match "
                f"actual count {failed_count}"
            )

            # Also verify using get_failed_login_count_24h
            actual_count = service.get_failed_login_count_24h(user)
            assert (
                actual_count == failed_count
            ), f"get_failed_login_count_24h returned {actual_count}, expected {failed_count}"

        finally:
            LoginAttempt.objects.filter(user=user).delete()
            User.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        num_users_with_warning=st.integers(min_value=1, max_value=3),
        num_users_without_warning=st.integers(min_value=1, max_value=3),
    )
    @hypothesis_settings(
        max_examples=30,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_multiple_users_warning_isolation(
        self, num_users_with_warning, num_users_without_warning
    ):
        """
        **Feature: advanced-tenant-management, Property 17: Security Warning Threshold**
        **Validates: Requirements 10.3**

        For any tenant with multiple users, only users with > 5 failed logins
        SHALL have warning badges. Other users should not be affected.
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            users_should_warn = []
            users_should_not_warn = []

            # Create users that should have warnings (> 5 failed logins)
            for i in range(num_users_with_warning):
                user = User.objects.create_user(
                    username=f"warnuser{i}_{uuid.uuid4().hex[:6]}",
                    email=f"warn{i}_{uuid.uuid4().hex[:6]}@test.com",
                    password="TestPass123!",
                    tenant=tenant,
                    role=User.TENANT_EMPLOYEE,
                )
                users_should_warn.append(user)

                # Create 6+ failed logins
                for j in range(6 + i):
                    create_login_attempt(
                        user=user,
                        result=LoginAttempt.RESULT_FAILED_PASSWORD,
                        hours_ago=j % 23,
                    )

            # Create users that should NOT have warnings (<= 5 failed logins)
            for i in range(num_users_without_warning):
                user = User.objects.create_user(
                    username=f"nowarnuser{i}_{uuid.uuid4().hex[:6]}",
                    email=f"nowarn{i}_{uuid.uuid4().hex[:6]}@test.com",
                    password="TestPass123!",
                    tenant=tenant,
                    role=User.TENANT_EMPLOYEE,
                )
                users_should_not_warn.append(user)

                # Create <= 5 failed logins
                for j in range(i % 6):  # 0-5 failed logins
                    create_login_attempt(
                        user=user,
                        result=LoginAttempt.RESULT_FAILED_PASSWORD,
                        hours_ago=j % 23,
                    )

            # Get users with warnings
            service = UserManagementService()
            users_with_warnings = service.get_users_with_failed_login_warning(
                tenant=tenant,
                threshold=WARNING_THRESHOLD,
            )

            user_ids_with_warnings = [u["user_id"] for u in users_with_warnings]

            # Property: All users that should warn are in the list
            for user in users_should_warn:
                assert (
                    user.id in user_ids_with_warnings
                ), f"User {user.username} should have warning badge"

            # Property: No users that shouldn't warn are in the list
            for user in users_should_not_warn:
                assert (
                    user.id not in user_ids_with_warnings
                ), f"User {user.username} should NOT have warning badge"

        finally:
            LoginAttempt.objects.filter(user__tenant=tenant).delete()
            User.objects.filter(tenant=tenant).delete()
            tenant.delete()

    @given(
        failed_count=st.integers(min_value=6, max_value=10),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_inactive_users_not_in_warning_list(self, failed_count):
        """
        **Feature: advanced-tenant-management, Property 17: Security Warning Threshold**
        **Validates: Requirements 10.3**

        For any inactive user, even with > 5 failed logins, the system SHALL NOT
        display a warning badge (inactive users are not shown in Users tab).
        """
        tenant = Tenant.objects.create(
            company_name=f"Test Company {uuid.uuid4().hex[:8]}",
            slug=f"test-{uuid.uuid4().hex[:12]}",
            status=Tenant.ACTIVE,
        )

        try:
            # Create an inactive user
            user = User.objects.create_user(
                username=f"testuser_{uuid.uuid4().hex[:8]}",
                email=f"test_{uuid.uuid4().hex[:8]}@test.com",
                password="TestPass123!",
                tenant=tenant,
                role=User.TENANT_EMPLOYEE,
                is_active=False,  # Inactive user
            )

            # Create failed login attempts
            for i in range(failed_count):
                create_login_attempt(
                    user=user,
                    result=LoginAttempt.RESULT_FAILED_PASSWORD,
                    hours_ago=i % 23,
                )

            # Get users with warnings
            service = UserManagementService()
            users_with_warnings = service.get_users_with_failed_login_warning(
                tenant=tenant,
                threshold=WARNING_THRESHOLD,
            )

            # Property: Inactive users should not be in warning list
            user_ids_with_warnings = [u["user_id"] for u in users_with_warnings]
            assert (
                user.id not in user_ids_with_warnings
            ), f"Inactive user with {failed_count} failed logins should NOT have warning badge"

        finally:
            LoginAttempt.objects.filter(user=user).delete()
            User.objects.filter(tenant=tenant).delete()
            tenant.delete()
