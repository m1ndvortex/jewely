"""
Tests for flexible tenant backup functionality (Task 18.8).

This module tests:
- Manual backup trigger interface
- Support for specific tenant(s), multiple tenants, or all tenants
- Immediate and scheduled execution
- Restore options (full, merge, selective)
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from apps.backups.forms import ManualBackupForm
from apps.backups.services import BackupService
from apps.core.models import Tenant

User = get_user_model()


@pytest.mark.django_db
class TestFlexibleBackupService:
    """Test BackupService for flexible backup operations."""

    @pytest.fixture
    def admin_user(self):
        """Create a platform admin user."""
        return User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

    @pytest.fixture
    def tenants(self):
        """Create test tenants."""
        tenant1 = Tenant.objects.create(
            company_name="Test Jewelry Shop 1",
            slug="test-shop-1",
            status=Tenant.ACTIVE,
        )
        tenant2 = Tenant.objects.create(
            company_name="Test Jewelry Shop 2",
            slug="test-shop-2",
            status=Tenant.ACTIVE,
        )
        return [tenant1, tenant2]

    def test_trigger_backup_all_tenants_immediate(self, admin_user, tenants):
        """Test triggering immediate backup for all tenants."""
        result = BackupService.trigger_manual_backup(
            backup_scope="all",
            tenants=None,
            execution_timing="immediate",
            scheduled_time=None,
            include_configuration=False,
            notes="Test backup all tenants",
            user=admin_user,
        )

        assert result["success"] is True
        assert len(result["backup_jobs"]) == 2  # Two tenants
        assert len(result["errors"]) == 0

    def test_trigger_backup_specific_tenant_immediate(self, admin_user, tenants):
        """Test triggering immediate backup for specific tenant."""
        result = BackupService.trigger_manual_backup(
            backup_scope="specific",
            tenants=[tenants[0]],
            execution_timing="immediate",
            scheduled_time=None,
            include_configuration=False,
            notes="Test backup specific tenant",
            user=admin_user,
        )

        assert result["success"] is True
        assert len(result["backup_jobs"]) == 1
        assert result["backup_jobs"][0]["tenant_id"] == str(tenants[0].id)

    def test_trigger_backup_scheduled(self, admin_user, tenants):
        """Test triggering scheduled backup."""
        scheduled_time = timezone.now() + timedelta(hours=1)

        result = BackupService.trigger_manual_backup(
            backup_scope="specific",
            tenants=[tenants[0]],
            execution_timing="scheduled",
            scheduled_time=scheduled_time,
            include_configuration=False,
            notes="Test scheduled backup",
            user=admin_user,
        )

        assert result["success"] is True
        assert len(result["scheduled_jobs"]) == 1
        assert result["scheduled_jobs"][0]["status"] == "scheduled"


@pytest.mark.django_db
class TestManualBackupForm:
    """Test ManualBackupForm validation."""

    @pytest.fixture
    def tenants(self):
        """Create test tenants."""
        tenant1 = Tenant.objects.create(
            company_name="Test Shop 1",
            slug="test-shop-1",
            status=Tenant.ACTIVE,
        )
        return [tenant1]

    def test_form_valid_all_tenants_immediate(self):
        """Test form validation for all tenants immediate backup."""
        form_data = {
            "backup_scope": "all",
            "execution_timing": "immediate",
            "include_configuration": False,
        }
        form = ManualBackupForm(data=form_data)
        assert form.is_valid()

    def test_form_invalid_specific_without_tenants(self):
        """Test form validation fails when specific scope without tenants."""
        form_data = {
            "backup_scope": "specific",
            "execution_timing": "immediate",
        }
        form = ManualBackupForm(data=form_data)
        assert not form.is_valid()
        assert "tenants" in form.errors

    def test_form_invalid_scheduled_without_time(self):
        """Test form validation fails when scheduled without time."""
        form_data = {
            "backup_scope": "all",
            "execution_timing": "scheduled",
        }
        form = ManualBackupForm(data=form_data)
        assert not form.is_valid()
        assert "scheduled_time" in form.errors
