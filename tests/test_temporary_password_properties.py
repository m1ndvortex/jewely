"""
Property-based tests for TemporaryPassword model expiry behavior.

**Feature: advanced-tenant-management, Property 8: Temporary Password Expiry**
**Validates: Requirements 3.9, 7.4**

Property 8: Temporary Password Expiry
*For any* temporary password with expiry time T, the password SHALL be
invalid for authentication after time T.
"""

import uuid
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.utils import timezone

import pytest
from hypothesis import HealthCheck, assume, given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from apps.core.models import TemporaryPassword, Tenant, User
from apps.core.tenant_context import bypass_rls

# Strategy for generating expiry durations (in seconds)
# Range: 1 second to 7 days (reasonable for temporary passwords)
expiry_duration_strategy = st.integers(min_value=1, max_value=7 * 24 * 60 * 60)

# Strategy for generating time offsets (in seconds)
# Used to test before/after expiry scenarios
time_offset_strategy = st.integers(min_value=1, max_value=24 * 60 * 60)

# Strategy for generating raw passwords
password_strategy = st.text(
    alphabet=st.sampled_from(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    ),
    min_size=8,
    max_size=32,
)


@pytest.fixture(scope="function")
def test_data(db):
    """Create test data for property tests."""
    with bypass_rls():
        tenant = Tenant.objects.create(
            company_name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
        )
        test_user = User.objects.create_user(
            username=f"testuser_{uuid.uuid4().hex[:8]}",
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            password="TestPassword123!",
            tenant=tenant,
        )
        admin_user = User.objects.create_user(
            username=f"admin_{uuid.uuid4().hex[:8]}",
            email=f"admin_{uuid.uuid4().hex[:8]}@example.com",
            password="AdminPassword123!",
            tenant=tenant,
            role="PLATFORM_ADMIN",
        )

        yield {"tenant": tenant, "test_user": test_user, "admin_user": admin_user}

        # Cleanup
        TemporaryPassword.objects.filter(user=test_user).delete()
        test_user.delete()
        admin_user.delete()
        tenant.delete()


@pytest.mark.django_db
class TestTemporaryPasswordExpiry:
    """
    **Feature: advanced-tenant-management, Property 8: Temporary Password Expiry**
    **Validates: Requirements 3.9, 7.4**

    Property tests for TemporaryPassword expiry behavior ensuring:
    1. Password is valid before expiry time (when not used)
    2. Password is invalid after expiry time
    3. Used password is invalid regardless of expiry time
    """

    @given(expiry_seconds=expiry_duration_strategy)
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_password_valid_before_expiry(self, expiry_seconds, test_data):
        """
        **Feature: advanced-tenant-management, Property 8: Temporary Password Expiry**
        **Validates: Requirements 3.9, 7.4**

        For any temporary password with expiry time T in the future,
        the password SHALL be valid before time T (when not used).
        """
        with bypass_rls():
            # Create temporary password with future expiry
            expires_at = timezone.now() + timedelta(seconds=expiry_seconds)

            temp_password = TemporaryPassword.objects.create(
                user=test_data["test_user"],
                password_hash=make_password("TempPass123!"),
                expires_at=expires_at,
                created_by=test_data["admin_user"],
            )

            try:
                # Property: Password should be valid before expiry (not used, not expired)
                assert temp_password.is_valid() is True, (
                    f"Temporary password should be valid before expiry time. "
                    f"Expires at: {expires_at}, Now: {timezone.now()}"
                )

                # Property: Password should not be expired
                assert (
                    temp_password.is_expired() is False
                ), f"Temporary password should not be expired before expiry time"

                # Property: Password should not be marked as used
                assert (
                    temp_password.is_used() is False
                ), f"Newly created temporary password should not be marked as used"
            finally:
                temp_password.delete()

    @given(past_seconds=time_offset_strategy)
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_password_invalid_after_expiry(self, past_seconds, test_data):
        """
        **Feature: advanced-tenant-management, Property 8: Temporary Password Expiry**
        **Validates: Requirements 3.9, 7.4**

        For any temporary password with expiry time T in the past,
        the password SHALL be invalid after time T.
        """
        with bypass_rls():
            # Create temporary password with past expiry
            expires_at = timezone.now() - timedelta(seconds=past_seconds)

            temp_password = TemporaryPassword.objects.create(
                user=test_data["test_user"],
                password_hash=make_password("TempPass123!"),
                expires_at=expires_at,
                created_by=test_data["admin_user"],
            )

            try:
                # Property: Password should be invalid after expiry
                assert temp_password.is_valid() is False, (
                    f"Temporary password should be invalid after expiry time. "
                    f"Expires at: {expires_at}, Now: {timezone.now()}"
                )

                # Property: Password should be expired
                assert (
                    temp_password.is_expired() is True
                ), f"Temporary password should be expired after expiry time"
            finally:
                temp_password.delete()

    @given(expiry_seconds=expiry_duration_strategy)
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_used_password_invalid_regardless_of_expiry(self, expiry_seconds, test_data):
        """
        **Feature: advanced-tenant-management, Property 8: Temporary Password Expiry**
        **Validates: Requirements 3.9, 7.4**

        For any temporary password that has been used, the password SHALL be
        invalid regardless of whether the expiry time has passed.
        """
        with bypass_rls():
            # Create temporary password with future expiry
            expires_at = timezone.now() + timedelta(seconds=expiry_seconds)

            temp_password = TemporaryPassword.objects.create(
                user=test_data["test_user"],
                password_hash=make_password("TempPass123!"),
                expires_at=expires_at,
                created_by=test_data["admin_user"],
            )

            try:
                # Mark as used
                temp_password.mark_as_used()

                # Property: Used password should be invalid even if not expired
                assert temp_password.is_valid() is False, (
                    f"Used temporary password should be invalid even before expiry. "
                    f"Expires at: {expires_at}, Now: {timezone.now()}"
                )

                # Property: Password should be marked as used
                assert (
                    temp_password.is_used() is True
                ), f"Temporary password should be marked as used after mark_as_used()"

                # Property: used_at should be set
                assert (
                    temp_password.used_at is not None
                ), f"used_at should be set after mark_as_used()"
            finally:
                temp_password.delete()

    @given(
        raw_password=password_strategy,
        expiry_seconds=expiry_duration_strategy,
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_check_password_respects_expiry(self, raw_password, expiry_seconds, test_data):
        """
        **Feature: advanced-tenant-management, Property 8: Temporary Password Expiry**
        **Validates: Requirements 3.9, 7.4**

        For any temporary password, check_password() SHALL return False
        if the password has expired, even if the raw password matches.
        """
        # Skip empty passwords
        assume(len(raw_password) >= 8)

        with bypass_rls():
            # Create temporary password with past expiry (expired)
            expires_at = timezone.now() - timedelta(seconds=1)
            password_hash = make_password(raw_password)

            temp_password = TemporaryPassword.objects.create(
                user=test_data["test_user"],
                password_hash=password_hash,
                expires_at=expires_at,
                created_by=test_data["admin_user"],
            )

            try:
                # Property: check_password should return False for expired password
                # even if the raw password matches the hash
                result = temp_password.check_password(raw_password)
                assert result is False, (
                    f"check_password() should return False for expired password, "
                    f"even if raw password matches"
                )
            finally:
                temp_password.delete()

    @given(
        raw_password=password_strategy,
        expiry_seconds=expiry_duration_strategy,
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_check_password_respects_used_status(self, raw_password, expiry_seconds, test_data):
        """
        **Feature: advanced-tenant-management, Property 8: Temporary Password Expiry**
        **Validates: Requirements 3.9, 7.4**

        For any temporary password that has been used, check_password() SHALL
        return False even if the raw password matches and expiry hasn't passed.
        """
        # Skip empty passwords
        assume(len(raw_password) >= 8)

        with bypass_rls():
            # Create temporary password with future expiry
            expires_at = timezone.now() + timedelta(seconds=expiry_seconds)
            password_hash = make_password(raw_password)

            temp_password = TemporaryPassword.objects.create(
                user=test_data["test_user"],
                password_hash=password_hash,
                expires_at=expires_at,
                created_by=test_data["admin_user"],
            )

            try:
                # Mark as used
                temp_password.mark_as_used()

                # Property: check_password should return False for used password
                # even if the raw password matches and not expired
                result = temp_password.check_password(raw_password)
                assert result is False, (
                    f"check_password() should return False for used password, "
                    f"even if raw password matches and not expired"
                )
            finally:
                temp_password.delete()

    @given(
        raw_password=password_strategy,
        expiry_seconds=expiry_duration_strategy,
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_check_password_succeeds_when_valid(self, raw_password, expiry_seconds, test_data):
        """
        **Feature: advanced-tenant-management, Property 8: Temporary Password Expiry**
        **Validates: Requirements 3.9, 7.4**

        For any valid (not expired, not used) temporary password,
        check_password() SHALL return True when the correct password is provided.
        """
        # Skip empty passwords
        assume(len(raw_password) >= 8)

        with bypass_rls():
            # Create temporary password with future expiry
            expires_at = timezone.now() + timedelta(seconds=expiry_seconds)
            password_hash = make_password(raw_password)

            temp_password = TemporaryPassword.objects.create(
                user=test_data["test_user"],
                password_hash=password_hash,
                expires_at=expires_at,
                created_by=test_data["admin_user"],
            )

            try:
                # Property: check_password should return True for valid password
                result = temp_password.check_password(raw_password)
                assert result is True, (
                    f"check_password() should return True for valid, non-expired, "
                    f"non-used password with correct raw password"
                )
            finally:
                temp_password.delete()
