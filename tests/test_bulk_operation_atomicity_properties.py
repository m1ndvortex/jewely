"""
Property-based tests for bulk operation atomicity.

**Feature: advanced-tenant-management, Property 14: Bulk Operation Atomicity**
**Validates: Requirements 8.4**

Property 14: Bulk Operation Atomicity
*For any* bulk status change operation, either all selected tenants SHALL be
updated or none SHALL be updated (atomic transaction).
"""

import uuid
from unittest.mock import MagicMock, patch

from django.db import transaction

import pytest
from hypothesis import HealthCheck, given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from apps.core.models import Tenant, User
from apps.core.services.tenant_service import TenantService
from apps.core.tenant_context import bypass_rls

# Strategy for valid status values
status_strategy = st.sampled_from(
    [
        Tenant.ACTIVE,
        Tenant.SUSPENDED,
    ]
)


# Strategy for number of tenants in bulk operation
num_tenants_strategy = st.integers(min_value=2, max_value=6)


def create_test_tenant(company_name: str, status: str, unique_id: str) -> Tenant:
    """Create a test tenant with the given parameters."""
    slug = f"bulk-test-{unique_id}"
    return Tenant.objects.create(
        company_name=company_name,
        slug=slug,
        status=status,
    )


def create_platform_admin(unique_id: str) -> User:
    """Create a platform admin user for testing."""
    with bypass_rls():
        return User.objects.create_user(
            username=f"bulk-admin-{unique_id}",
            email=f"bulk-admin-{unique_id}@example.com",
            password="adminpass123",
            tenant=None,
            role=User.PLATFORM_ADMIN,
        )


@pytest.mark.django_db
class TestBulkOperationAtomicity:
    """
    **Feature: advanced-tenant-management, Property 14: Bulk Operation Atomicity**
    **Validates: Requirements 8.4**

    Property tests for bulk status change operations ensuring:
    1. All selected tenants are updated when operation succeeds
    2. No tenants are updated when operation fails (rollback)
    3. The returned count matches actual updates
    """

    @given(
        new_status=status_strategy,
        num_tenants=num_tenants_strategy,
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_successful_bulk_operation_updates_all_tenants(self, new_status, num_tenants):
        """
        **Feature: advanced-tenant-management, Property 14: Bulk Operation Atomicity**
        **Validates: Requirements 8.4**

        For any successful bulk status change, ALL selected tenants SHALL be
        updated to the new status.
        """
        created_tenants = []
        admin_user = None
        test_id = str(uuid.uuid4())[:8]

        try:
            with bypass_rls():
                # Create admin user
                admin_user = create_platform_admin(test_id)

                # Create test tenants with opposite status
                initial_status = Tenant.SUSPENDED if new_status == Tenant.ACTIVE else Tenant.ACTIVE

                for i in range(num_tenants):
                    tenant = create_test_tenant(
                        company_name=f"Bulk Test {test_id} {i}",
                        status=initial_status,
                        unique_id=f"{test_id}-{i}",
                    )
                    created_tenants.append(tenant)

                # Get tenant IDs
                tenant_ids = [t.id for t in created_tenants]

                # Perform bulk status change
                service = TenantService()
                updated_count = service.bulk_change_status(
                    tenant_ids=tenant_ids,
                    new_status=new_status,
                    reason="Property test - bulk operation",
                    modified_by=admin_user,
                )

                # Verify all tenants were updated
                assert (
                    updated_count == num_tenants
                ), f"Expected {num_tenants} updates, got {updated_count}"

                # Refresh tenants from database and verify status
                for tenant in created_tenants:
                    tenant.refresh_from_db()
                    assert tenant.status == new_status, (
                        f"Tenant {tenant.id} status is {tenant.status}, " f"expected {new_status}"
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

    @given(
        new_status=status_strategy,
        num_tenants=num_tenants_strategy,
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_bulk_operation_skips_tenants_with_same_status(self, new_status, num_tenants):
        """
        **Feature: advanced-tenant-management, Property 14: Bulk Operation Atomicity**
        **Validates: Requirements 8.4**

        For any bulk status change where some tenants already have the target
        status, only tenants with different status SHALL be updated.
        """
        created_tenants = []
        admin_user = None
        test_id = str(uuid.uuid4())[:8]

        try:
            with bypass_rls():
                admin_user = create_platform_admin(test_id)

                # Create mix of tenants - some with target status, some without
                tenants_needing_update = 0
                for i in range(num_tenants):
                    # Alternate between target status and different status
                    if i % 2 == 0:
                        status = new_status  # Already has target status
                    else:
                        status = Tenant.SUSPENDED if new_status == Tenant.ACTIVE else Tenant.ACTIVE
                        tenants_needing_update += 1

                    tenant = create_test_tenant(
                        company_name=f"Mixed Status Test {test_id} {i}",
                        status=status,
                        unique_id=f"{test_id}-{i}",
                    )
                    created_tenants.append(tenant)

                tenant_ids = [t.id for t in created_tenants]

                # Perform bulk status change
                service = TenantService()
                updated_count = service.bulk_change_status(
                    tenant_ids=tenant_ids,
                    new_status=new_status,
                    reason="Property test - mixed status",
                    modified_by=admin_user,
                )

                # Verify only tenants that needed update were counted
                assert (
                    updated_count == tenants_needing_update
                ), f"Expected {tenants_needing_update} updates, got {updated_count}"

                # Verify all tenants now have target status
                for tenant in created_tenants:
                    tenant.refresh_from_db()
                    assert tenant.status == new_status, (
                        f"Tenant {tenant.id} status is {tenant.status}, " f"expected {new_status}"
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

    @given(num_tenants=num_tenants_strategy)
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_bulk_operation_with_invalid_status_raises_error(self, num_tenants):
        """
        **Feature: advanced-tenant-management, Property 14: Bulk Operation Atomicity**
        **Validates: Requirements 8.4**

        For any bulk status change with invalid status, the operation SHALL
        raise ValueError and no tenants SHALL be modified.
        """
        created_tenants = []
        admin_user = None
        test_id = str(uuid.uuid4())[:8]

        try:
            with bypass_rls():
                admin_user = create_platform_admin(test_id)

                # Create test tenants
                for i in range(num_tenants):
                    tenant = create_test_tenant(
                        company_name=f"Invalid Status Test {test_id} {i}",
                        status=Tenant.ACTIVE,
                        unique_id=f"{test_id}-{i}",
                    )
                    created_tenants.append(tenant)

                tenant_ids = [t.id for t in created_tenants]
                original_statuses = {t.id: t.status for t in created_tenants}

                # Attempt bulk status change with invalid status
                service = TenantService()
                with pytest.raises(ValueError):
                    service.bulk_change_status(
                        tenant_ids=tenant_ids,
                        new_status="INVALID_STATUS",
                        reason="Property test - invalid status",
                        modified_by=admin_user,
                    )

                # Verify no tenants were modified
                for tenant in created_tenants:
                    tenant.refresh_from_db()
                    assert (
                        tenant.status == original_statuses[tenant.id]
                    ), f"Tenant {tenant.id} was modified despite error"

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

    @given(
        new_status=status_strategy,
        num_tenants=num_tenants_strategy,
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_bulk_operation_with_empty_list_returns_zero(self, new_status, num_tenants):
        """
        **Feature: advanced-tenant-management, Property 14: Bulk Operation Atomicity**
        **Validates: Requirements 8.4**

        For any bulk status change with empty tenant list, the operation SHALL
        return 0 and complete successfully.
        """
        admin_user = None
        test_id = str(uuid.uuid4())[:8]

        try:
            with bypass_rls():
                admin_user = create_platform_admin(test_id)

                # Perform bulk status change with empty list
                service = TenantService()
                updated_count = service.bulk_change_status(
                    tenant_ids=[],
                    new_status=new_status,
                    reason="Property test - empty list",
                    modified_by=admin_user,
                )

                assert updated_count == 0, f"Expected 0 updates for empty list, got {updated_count}"

        finally:
            with bypass_rls():
                if admin_user:
                    try:
                        admin_user.delete()
                    except Exception:
                        pass

    @given(
        new_status=status_strategy,
        num_tenants=num_tenants_strategy,
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_bulk_operation_with_nonexistent_ids_handles_gracefully(self, new_status, num_tenants):
        """
        **Feature: advanced-tenant-management, Property 14: Bulk Operation Atomicity**
        **Validates: Requirements 8.4**

        For any bulk status change with non-existent tenant IDs, the operation
        SHALL complete without error and return 0 updates.
        """
        admin_user = None
        test_id = str(uuid.uuid4())[:8]

        try:
            with bypass_rls():
                admin_user = create_platform_admin(test_id)

                # Generate random non-existent UUIDs
                fake_ids = [uuid.uuid4() for _ in range(num_tenants)]

                # Perform bulk status change
                service = TenantService()
                updated_count = service.bulk_change_status(
                    tenant_ids=fake_ids,
                    new_status=new_status,
                    reason="Property test - nonexistent IDs",
                    modified_by=admin_user,
                )

                assert (
                    updated_count == 0
                ), f"Expected 0 updates for nonexistent IDs, got {updated_count}"

        finally:
            with bypass_rls():
                if admin_user:
                    try:
                        admin_user.delete()
                    except Exception:
                        pass

    @given(
        new_status=status_strategy,
        num_tenants=num_tenants_strategy,
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_bulk_operation_creates_audit_log_for_each_update(self, new_status, num_tenants):
        """
        **Feature: advanced-tenant-management, Property 14: Bulk Operation Atomicity**
        **Validates: Requirements 8.4**

        For any successful bulk status change, the system SHALL create an
        AuditLog entry for each tenant that was updated.
        """
        from apps.core.audit_models import AuditLog

        created_tenants = []
        admin_user = None
        test_id = str(uuid.uuid4())[:8]

        try:
            with bypass_rls():
                admin_user = create_platform_admin(test_id)

                # Create test tenants with opposite status
                initial_status = Tenant.SUSPENDED if new_status == Tenant.ACTIVE else Tenant.ACTIVE

                for i in range(num_tenants):
                    tenant = create_test_tenant(
                        company_name=f"Audit Log Test {test_id} {i}",
                        status=initial_status,
                        unique_id=f"{test_id}-{i}",
                    )
                    created_tenants.append(tenant)

                tenant_ids = [t.id for t in created_tenants]

                # Count existing audit logs for these tenants
                initial_log_count = AuditLog.objects.filter(
                    object_id__in=[str(tid) for tid in tenant_ids]
                ).count()

                # Perform bulk status change
                service = TenantService()
                updated_count = service.bulk_change_status(
                    tenant_ids=tenant_ids,
                    new_status=new_status,
                    reason="Property test - audit log",
                    modified_by=admin_user,
                )

                # Count audit logs after operation
                final_log_count = AuditLog.objects.filter(
                    object_id__in=[str(tid) for tid in tenant_ids]
                ).count()

                # Verify audit logs were created for each update
                new_logs = final_log_count - initial_log_count
                assert (
                    new_logs == updated_count
                ), f"Expected {updated_count} new audit logs, got {new_logs}"

                # Verify audit log content
                for tenant in created_tenants:
                    log = AuditLog.objects.filter(
                        object_id=str(tenant.id),
                        new_values__status=new_status,
                    ).first()

                    assert log is not None, f"No audit log found for tenant {tenant.id}"
                    assert (
                        log.metadata.get("bulk_operation") is True
                    ), "Audit log should indicate bulk operation"

        finally:
            with bypass_rls():
                for tenant in created_tenants:
                    try:
                        # Delete audit logs first
                        AuditLog.objects.filter(object_id=str(tenant.id)).delete()
                        tenant.delete()
                    except Exception:
                        pass
                if admin_user:
                    try:
                        admin_user.delete()
                    except Exception:
                        pass

    @given(num_tenants=num_tenants_strategy)
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_bulk_suspend_sets_suspended_at_timestamp(self, num_tenants):
        """
        **Feature: advanced-tenant-management, Property 14: Bulk Operation Atomicity**
        **Validates: Requirements 8.4**

        For any bulk suspend operation, all updated tenants SHALL have their
        suspended_at timestamp set.
        """
        created_tenants = []
        admin_user = None
        test_id = str(uuid.uuid4())[:8]

        try:
            with bypass_rls():
                admin_user = create_platform_admin(test_id)

                # Create active tenants
                for i in range(num_tenants):
                    tenant = create_test_tenant(
                        company_name=f"Suspend Test {test_id} {i}",
                        status=Tenant.ACTIVE,
                        unique_id=f"{test_id}-{i}",
                    )
                    created_tenants.append(tenant)

                tenant_ids = [t.id for t in created_tenants]

                # Perform bulk suspend
                service = TenantService()
                service.bulk_change_status(
                    tenant_ids=tenant_ids,
                    new_status=Tenant.SUSPENDED,
                    reason="Property test - suspend timestamp",
                    modified_by=admin_user,
                )

                # Verify suspended_at is set for all tenants
                for tenant in created_tenants:
                    tenant.refresh_from_db()
                    assert (
                        tenant.suspended_at is not None
                    ), f"Tenant {tenant.id} suspended_at should be set"

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

    @given(num_tenants=num_tenants_strategy)
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_bulk_activate_clears_suspended_at_timestamp(self, num_tenants):
        """
        **Feature: advanced-tenant-management, Property 14: Bulk Operation Atomicity**
        **Validates: Requirements 8.4**

        For any bulk activate operation on suspended tenants, all updated
        tenants SHALL have their suspended_at timestamp cleared.
        """
        from django.utils import timezone

        created_tenants = []
        admin_user = None
        test_id = str(uuid.uuid4())[:8]

        try:
            with bypass_rls():
                admin_user = create_platform_admin(test_id)

                # Create suspended tenants with suspended_at set
                for i in range(num_tenants):
                    tenant = create_test_tenant(
                        company_name=f"Activate Test {test_id} {i}",
                        status=Tenant.SUSPENDED,
                        unique_id=f"{test_id}-{i}",
                    )
                    tenant.suspended_at = timezone.now()
                    tenant.save()
                    created_tenants.append(tenant)

                tenant_ids = [t.id for t in created_tenants]

                # Perform bulk activate
                service = TenantService()
                service.bulk_change_status(
                    tenant_ids=tenant_ids,
                    new_status=Tenant.ACTIVE,
                    reason="Property test - activate clears timestamp",
                    modified_by=admin_user,
                )

                # Verify suspended_at is cleared for all tenants
                for tenant in created_tenants:
                    tenant.refresh_from_db()
                    assert (
                        tenant.suspended_at is None
                    ), f"Tenant {tenant.id} suspended_at should be cleared"

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

    @given(
        new_status=status_strategy,
        num_tenants=num_tenants_strategy,
    )
    @hypothesis_settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_bulk_operation_is_idempotent(self, new_status, num_tenants):
        """
        **Feature: advanced-tenant-management, Property 14: Bulk Operation Atomicity**
        **Validates: Requirements 8.4**

        For any bulk status change, calling the operation twice with the same
        parameters SHALL result in the same final state (idempotent).
        """
        created_tenants = []
        admin_user = None
        test_id = str(uuid.uuid4())[:8]

        try:
            with bypass_rls():
                admin_user = create_platform_admin(test_id)

                # Create test tenants
                initial_status = Tenant.SUSPENDED if new_status == Tenant.ACTIVE else Tenant.ACTIVE

                for i in range(num_tenants):
                    tenant = create_test_tenant(
                        company_name=f"Idempotent Test {test_id} {i}",
                        status=initial_status,
                        unique_id=f"{test_id}-{i}",
                    )
                    created_tenants.append(tenant)

                tenant_ids = [t.id for t in created_tenants]

                # Perform bulk status change twice
                service = TenantService()

                first_count = service.bulk_change_status(
                    tenant_ids=tenant_ids,
                    new_status=new_status,
                    reason="Property test - idempotent first",
                    modified_by=admin_user,
                )

                second_count = service.bulk_change_status(
                    tenant_ids=tenant_ids,
                    new_status=new_status,
                    reason="Property test - idempotent second",
                    modified_by=admin_user,
                )

                # First call should update all, second should update none
                assert (
                    first_count == num_tenants
                ), f"First call should update {num_tenants}, got {first_count}"
                assert (
                    second_count == 0
                ), f"Second call should update 0 (already at target status), got {second_count}"

                # Verify final state
                for tenant in created_tenants:
                    tenant.refresh_from_db()
                    assert (
                        tenant.status == new_status
                    ), f"Tenant {tenant.id} should have status {new_status}"

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
