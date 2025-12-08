"""
Property-based tests for impersonation audit trail in tenant management.

**Feature: advanced-tenant-management, Property 18: Impersonation Audit Trail**
**Validates: Requirements 12.2, 12.4**

Property 18: Impersonation Audit Trail
*For any* impersonation session, the system SHALL create exactly two AuditLog entries:
IMPERSONATION_START at begin and IMPERSONATION_END at end.
"""

import string
import uuid
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory

import pytest
from hypothesis import HealthCheck, assume, given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from apps.core.audit_models import AuditLog
from apps.core.models import Tenant
from apps.core.services.impersonation_service import ImpersonationService

User = get_user_model()


# ============================================================================
# Strategies for generating test data
# ============================================================================


@st.composite
def username_strategy(draw):
    """Generate valid usernames."""
    username = draw(
        st.text(alphabet=string.ascii_lowercase + string.digits + "_", min_size=3, max_size=20)
    )
    # Ensure username starts with letter
    assume(username and username[0].isalpha())
    return username


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


# ============================================================================
# Helper Functions
# ============================================================================


def create_platform_admin(username=None):
    """Create a platform administrator user (no tenant)."""
    if username is None:
        username = f"admin_{uuid.uuid4().hex[:8]}"

    return User.objects.create_user(
        username=username,
        email=f"{username}@platform.local",
        password="testpass123",
        tenant=None,  # Platform admin has no tenant
        role=User.PLATFORM_ADMIN,
        is_active=True,
    )


def create_tenant_user(tenant_slug=None, username=None):
    """Create a tenant and a user in that tenant."""
    if tenant_slug is None:
        tenant_slug = f"tenant-{uuid.uuid4().hex[:12]}"

    tenant = Tenant.objects.create(
        company_name=f"Test Company {uuid.uuid4().hex[:8]}",
        slug=tenant_slug,
        status=Tenant.ACTIVE,
    )

    if username is None:
        username = f"user_{uuid.uuid4().hex[:8]}"

    user = User.objects.create_user(
        username=username,
        email=f"{username}@{tenant_slug}.local",
        password="testpass123",
        tenant=tenant,
        role=User.TENANT_OWNER,
        is_active=True,
    )

    return tenant, user


def create_mock_request():
    """Create a mock HTTP request with session."""
    factory = RequestFactory()
    request = factory.get("/")

    # Add session
    request.session = SessionStore()
    request.session.create()

    # Add META for IP and user agent
    request.META["REMOTE_ADDR"] = "127.0.0.1"
    request.META["HTTP_USER_AGENT"] = "Test User Agent"

    return request


# ============================================================================
# Property Tests
# ============================================================================


@pytest.mark.django_db
class TestImpersonationAuditTrail:
    """
    **Feature: advanced-tenant-management, Property 18: Impersonation Audit Trail**
    **Validates: Requirements 12.2, 12.4**

    Property tests for impersonation audit trail ensuring:
    1. Starting impersonation creates exactly one IMPERSONATION_START log
    2. Ending impersonation creates exactly one IMPERSONATION_END log
    3. Complete session creates exactly two logs (START and END)
    4. Logs contain correct metadata (admin user, target user)
    5. Logs are created in the target user's tenant
    """

    @given(
        admin_username=username_strategy(),
        target_username=username_strategy(),
        tenant_slug=tenant_slug_strategy(),
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_impersonation_start_creates_audit_log(
        self, admin_username, target_username, tenant_slug
    ):
        """
        **Feature: advanced-tenant-management, Property 18: Impersonation Audit Trail**
        **Validates: Requirements 12.2**

        For any impersonation start, the system SHALL create exactly one AuditLog
        entry with action IMPERSONATION_START.
        """
        # Ensure usernames are different
        assume(admin_username != target_username)

        admin_user = None
        tenant = None
        target_user = None

        try:
            # Create platform admin
            admin_user = create_platform_admin(admin_username)

            # Create tenant and target user
            tenant, target_user = create_tenant_user(tenant_slug, target_username)

            # Create mock request
            request = create_mock_request()

            # Get initial log count
            initial_log_count = AuditLog.objects.filter(
                tenant=tenant, action=AuditLog.ACTION_IMPERSONATION_START
            ).count()

            # Start impersonation
            service = ImpersonationService()
            success, message = service.start_impersonation(request, target_user, admin_user)

            # Property: Impersonation should succeed
            assert success, f"Impersonation failed: {message}"

            # Property: Exactly one IMPERSONATION_START log should be created
            final_log_count = AuditLog.objects.filter(
                tenant=tenant, action=AuditLog.ACTION_IMPERSONATION_START
            ).count()

            assert final_log_count == initial_log_count + 1, (
                f"Expected exactly 1 IMPERSONATION_START log to be created, "
                f"but count changed from {initial_log_count} to {final_log_count}"
            )

            # Verify the log entry
            log = AuditLog.objects.filter(
                tenant=tenant, action=AuditLog.ACTION_IMPERSONATION_START
            ).latest("timestamp")

            # Property: Log should have correct category and severity
            assert (
                log.category == AuditLog.CATEGORY_SECURITY
            ), f"Expected category SECURITY, got {log.category}"
            assert (
                log.severity == AuditLog.SEVERITY_WARNING
            ), f"Expected severity WARNING, got {log.severity}"

            # Property: Log should have correct user (admin)
            assert (
                log.user_id == admin_user.id
            ), f"Expected log user to be admin {admin_user.id}, got {log.user_id}"

            # Property: Log should have correct tenant (target user's tenant)
            assert (
                log.tenant_id == tenant.id
            ), f"Expected log tenant to be {tenant.id}, got {log.tenant_id}"

        finally:
            # Cleanup
            if tenant:
                AuditLog.objects.filter(tenant=tenant).delete()
                User.objects.filter(tenant=tenant).delete()
                tenant.delete()
            if admin_user:
                admin_user.delete()

    @given(
        admin_username=username_strategy(),
        target_username=username_strategy(),
        tenant_slug=tenant_slug_strategy(),
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_impersonation_end_creates_audit_log(
        self, admin_username, target_username, tenant_slug
    ):
        """
        **Feature: advanced-tenant-management, Property 18: Impersonation Audit Trail**
        **Validates: Requirements 12.4**

        For any impersonation end, the system SHALL create exactly one AuditLog
        entry with action IMPERSONATION_END.
        """
        # Ensure usernames are different
        assume(admin_username != target_username)

        admin_user = None
        tenant = None
        target_user = None

        try:
            # Create platform admin
            admin_user = create_platform_admin(admin_username)

            # Create tenant and target user
            tenant, target_user = create_tenant_user(tenant_slug, target_username)

            # Create mock request
            request = create_mock_request()

            # Start impersonation first
            service = ImpersonationService()
            success, message = service.start_impersonation(request, target_user, admin_user)
            assert success, f"Impersonation start failed: {message}"

            # Get initial END log count
            initial_end_log_count = AuditLog.objects.filter(
                tenant=tenant, action=AuditLog.ACTION_IMPERSONATION_END
            ).count()

            # End impersonation
            success, message = service.end_impersonation(request)

            # Property: Ending impersonation should succeed
            assert success, f"Ending impersonation failed: {message}"

            # Property: Exactly one IMPERSONATION_END log should be created
            final_end_log_count = AuditLog.objects.filter(
                tenant=tenant, action=AuditLog.ACTION_IMPERSONATION_END
            ).count()

            assert final_end_log_count == initial_end_log_count + 1, (
                f"Expected exactly 1 IMPERSONATION_END log to be created, "
                f"but count changed from {initial_end_log_count} to {final_end_log_count}"
            )

            # Verify the log entry
            log = AuditLog.objects.filter(
                tenant=tenant, action=AuditLog.ACTION_IMPERSONATION_END
            ).latest("timestamp")

            # Property: Log should have correct category and severity
            assert (
                log.category == AuditLog.CATEGORY_SECURITY
            ), f"Expected category SECURITY, got {log.category}"
            assert (
                log.severity == AuditLog.SEVERITY_INFO
            ), f"Expected severity INFO, got {log.severity}"

            # Property: Log should have correct user (admin)
            assert (
                log.user_id == admin_user.id
            ), f"Expected log user to be admin {admin_user.id}, got {log.user_id}"

            # Property: Log should have correct tenant (target user's tenant)
            assert (
                log.tenant_id == tenant.id
            ), f"Expected log tenant to be {tenant.id}, got {log.tenant_id}"

        finally:
            # Cleanup
            if tenant:
                AuditLog.objects.filter(tenant=tenant).delete()
                User.objects.filter(tenant=tenant).delete()
                tenant.delete()
            if admin_user:
                admin_user.delete()

    @given(
        admin_username=username_strategy(),
        target_username=username_strategy(),
        tenant_slug=tenant_slug_strategy(),
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_complete_impersonation_session_creates_two_logs(
        self, admin_username, target_username, tenant_slug
    ):
        """
        **Feature: advanced-tenant-management, Property 18: Impersonation Audit Trail**
        **Validates: Requirements 12.2, 12.4**

        For any complete impersonation session (start + end), the system SHALL
        create exactly two AuditLog entries: one IMPERSONATION_START and one
        IMPERSONATION_END.
        """
        # Ensure usernames are different
        assume(admin_username != target_username)

        admin_user = None
        tenant = None
        target_user = None

        try:
            # Create platform admin
            admin_user = create_platform_admin(admin_username)

            # Create tenant and target user
            tenant, target_user = create_tenant_user(tenant_slug, target_username)

            # Create mock request
            request = create_mock_request()

            # Get initial log counts
            initial_start_count = AuditLog.objects.filter(
                tenant=tenant, action=AuditLog.ACTION_IMPERSONATION_START
            ).count()
            initial_end_count = AuditLog.objects.filter(
                tenant=tenant, action=AuditLog.ACTION_IMPERSONATION_END
            ).count()

            # Perform complete impersonation session
            service = ImpersonationService()

            # Start impersonation
            success, message = service.start_impersonation(request, target_user, admin_user)
            assert success, f"Impersonation start failed: {message}"

            # End impersonation
            success, message = service.end_impersonation(request)
            assert success, f"Ending impersonation failed: {message}"

            # Get final log counts
            final_start_count = AuditLog.objects.filter(
                tenant=tenant, action=AuditLog.ACTION_IMPERSONATION_START
            ).count()
            final_end_count = AuditLog.objects.filter(
                tenant=tenant, action=AuditLog.ACTION_IMPERSONATION_END
            ).count()

            # Property: Exactly one START log should be created
            assert final_start_count == initial_start_count + 1, (
                f"Expected exactly 1 IMPERSONATION_START log, "
                f"but count changed from {initial_start_count} to {final_start_count}"
            )

            # Property: Exactly one END log should be created
            assert final_end_count == initial_end_count + 1, (
                f"Expected exactly 1 IMPERSONATION_END log, "
                f"but count changed from {initial_end_count} to {final_end_count}"
            )

            # Property: Total of exactly 2 logs should be created for this session
            total_logs_created = (final_start_count - initial_start_count) + (
                final_end_count - initial_end_count
            )
            assert total_logs_created == 2, (
                f"Expected exactly 2 audit logs for complete impersonation session, "
                f"got {total_logs_created}"
            )

        finally:
            # Cleanup
            if tenant:
                AuditLog.objects.filter(tenant=tenant).delete()
                User.objects.filter(tenant=tenant).delete()
                tenant.delete()
            if admin_user:
                admin_user.delete()

    @given(
        admin_username=username_strategy(),
        target_username=username_strategy(),
        tenant_slug=tenant_slug_strategy(),
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_impersonation_logs_contain_correct_metadata(
        self, admin_username, target_username, tenant_slug
    ):
        """
        **Feature: advanced-tenant-management, Property 18: Impersonation Audit Trail**
        **Validates: Requirements 12.2, 12.4**

        For any impersonation session, the audit logs SHALL contain correct metadata
        including admin user ID, admin username, target user ID, and target username.
        """
        # Ensure usernames are different
        assume(admin_username != target_username)

        admin_user = None
        tenant = None
        target_user = None

        try:
            # Create platform admin
            admin_user = create_platform_admin(admin_username)

            # Create tenant and target user
            tenant, target_user = create_tenant_user(tenant_slug, target_username)

            # Create mock request
            request = create_mock_request()

            # Perform complete impersonation session
            service = ImpersonationService()
            service.start_impersonation(request, target_user, admin_user)
            service.end_impersonation(request)

            # Get the audit logs
            start_log = AuditLog.objects.filter(
                tenant=tenant, action=AuditLog.ACTION_IMPERSONATION_START
            ).latest("timestamp")

            end_log = AuditLog.objects.filter(
                tenant=tenant, action=AuditLog.ACTION_IMPERSONATION_END
            ).latest("timestamp")

            # Property: START log metadata should contain correct information
            assert "admin_user_id" in start_log.metadata, "START log missing admin_user_id"
            assert start_log.metadata["admin_user_id"] == admin_user.id, (
                f"START log admin_user_id mismatch: expected {admin_user.id}, "
                f"got {start_log.metadata['admin_user_id']}"
            )

            assert "admin_username" in start_log.metadata, "START log missing admin_username"
            assert start_log.metadata["admin_username"] == admin_username, (
                f"START log admin_username mismatch: expected {admin_username}, "
                f"got {start_log.metadata['admin_username']}"
            )

            assert "target_user_id" in start_log.metadata, "START log missing target_user_id"
            assert start_log.metadata["target_user_id"] == target_user.id, (
                f"START log target_user_id mismatch: expected {target_user.id}, "
                f"got {start_log.metadata['target_user_id']}"
            )

            assert "target_username" in start_log.metadata, "START log missing target_username"
            assert start_log.metadata["target_username"] == target_username, (
                f"START log target_username mismatch: expected {target_username}, "
                f"got {start_log.metadata['target_username']}"
            )

            # Property: END log metadata should contain correct information
            assert "admin_user_id" in end_log.metadata, "END log missing admin_user_id"
            assert end_log.metadata["admin_user_id"] == admin_user.id, (
                f"END log admin_user_id mismatch: expected {admin_user.id}, "
                f"got {end_log.metadata['admin_user_id']}"
            )

            assert "admin_username" in end_log.metadata, "END log missing admin_username"
            assert end_log.metadata["admin_username"] == admin_username, (
                f"END log admin_username mismatch: expected {admin_username}, "
                f"got {end_log.metadata['admin_username']}"
            )

            assert "target_user_id" in end_log.metadata, "END log missing target_user_id"
            assert end_log.metadata["target_user_id"] == target_user.id, (
                f"END log target_user_id mismatch: expected {target_user.id}, "
                f"got {end_log.metadata['target_user_id']}"
            )

            assert "target_username" in end_log.metadata, "END log missing target_username"
            assert end_log.metadata["target_username"] == target_username, (
                f"END log target_username mismatch: expected {target_username}, "
                f"got {end_log.metadata['target_username']}"
            )

            # Property: END log should contain duration
            assert "duration_seconds" in end_log.metadata, "END log missing duration_seconds"
            assert isinstance(
                end_log.metadata["duration_seconds"], (int, float)
            ), f"END log duration_seconds should be numeric, got {type(end_log.metadata['duration_seconds'])}"

        finally:
            # Cleanup
            if tenant:
                AuditLog.objects.filter(tenant=tenant).delete()
                User.objects.filter(tenant=tenant).delete()
                tenant.delete()
            if admin_user:
                admin_user.delete()

    @given(
        admin_username=username_strategy(),
        target_username=username_strategy(),
        tenant_slug=tenant_slug_strategy(),
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_impersonation_logs_in_target_tenant(
        self, admin_username, target_username, tenant_slug
    ):
        """
        **Feature: advanced-tenant-management, Property 18: Impersonation Audit Trail**
        **Validates: Requirements 12.2, 12.4**

        For any impersonation session, both audit logs SHALL be created in the
        target user's tenant, not the admin's tenant (which is None).
        """
        # Ensure usernames are different
        assume(admin_username != target_username)

        admin_user = None
        tenant = None
        target_user = None

        try:
            # Create platform admin (no tenant)
            admin_user = create_platform_admin(admin_username)

            # Create tenant and target user
            tenant, target_user = create_tenant_user(tenant_slug, target_username)

            # Create mock request
            request = create_mock_request()

            # Perform complete impersonation session
            service = ImpersonationService()
            service.start_impersonation(request, target_user, admin_user)
            service.end_impersonation(request)

            # Get the audit logs
            start_log = AuditLog.objects.filter(action=AuditLog.ACTION_IMPERSONATION_START).latest(
                "timestamp"
            )

            end_log = AuditLog.objects.filter(action=AuditLog.ACTION_IMPERSONATION_END).latest(
                "timestamp"
            )

            # Property: Both logs should be in the target user's tenant
            assert (
                start_log.tenant_id == tenant.id
            ), f"START log should be in tenant {tenant.id}, got {start_log.tenant_id}"

            assert (
                end_log.tenant_id == tenant.id
            ), f"END log should be in tenant {tenant.id}, got {end_log.tenant_id}"

            # Property: Logs should NOT be in admin's tenant (which is None)
            assert start_log.tenant_id is not None, "START log should not have null tenant_id"

            assert end_log.tenant_id is not None, "END log should not have null tenant_id"

        finally:
            # Cleanup
            if tenant:
                AuditLog.objects.filter(tenant=tenant).delete()
                User.objects.filter(tenant=tenant).delete()
                tenant.delete()
            if admin_user:
                admin_user.delete()

    @given(
        num_sessions=st.integers(min_value=2, max_value=4),
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_multiple_impersonation_sessions_create_correct_log_count(self, num_sessions):
        """
        **Feature: advanced-tenant-management, Property 18: Impersonation Audit Trail**
        **Validates: Requirements 12.2, 12.4**

        For any number of complete impersonation sessions, the system SHALL create
        exactly 2 * N audit logs (N START logs and N END logs).
        """
        admin_user = None
        tenant = None
        target_user = None

        try:
            # Create platform admin
            admin_user = create_platform_admin()

            # Create tenant and target user
            tenant, target_user = create_tenant_user()

            # Get initial log counts
            initial_start_count = AuditLog.objects.filter(
                tenant=tenant, action=AuditLog.ACTION_IMPERSONATION_START
            ).count()
            initial_end_count = AuditLog.objects.filter(
                tenant=tenant, action=AuditLog.ACTION_IMPERSONATION_END
            ).count()

            # Perform multiple impersonation sessions
            service = ImpersonationService()
            for i in range(num_sessions):
                request = create_mock_request()
                service.start_impersonation(request, target_user, admin_user)
                service.end_impersonation(request)

            # Get final log counts
            final_start_count = AuditLog.objects.filter(
                tenant=tenant, action=AuditLog.ACTION_IMPERSONATION_START
            ).count()
            final_end_count = AuditLog.objects.filter(
                tenant=tenant, action=AuditLog.ACTION_IMPERSONATION_END
            ).count()

            # Property: Exactly N START logs should be created
            assert final_start_count == initial_start_count + num_sessions, (
                f"Expected {num_sessions} IMPERSONATION_START logs, "
                f"but count changed from {initial_start_count} to {final_start_count}"
            )

            # Property: Exactly N END logs should be created
            assert final_end_count == initial_end_count + num_sessions, (
                f"Expected {num_sessions} IMPERSONATION_END logs, "
                f"but count changed from {initial_end_count} to {final_end_count}"
            )

            # Property: Total of exactly 2*N logs should be created
            total_logs_created = (final_start_count - initial_start_count) + (
                final_end_count - initial_end_count
            )
            expected_total = 2 * num_sessions
            assert total_logs_created == expected_total, (
                f"Expected exactly {expected_total} audit logs for {num_sessions} sessions, "
                f"got {total_logs_created}"
            )

        finally:
            # Cleanup
            if tenant:
                AuditLog.objects.filter(tenant=tenant).delete()
                User.objects.filter(tenant=tenant).delete()
                tenant.delete()
            if admin_user:
                admin_user.delete()
