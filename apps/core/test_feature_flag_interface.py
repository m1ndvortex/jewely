"""
Integration tests for feature flag interface (views, forms, templates).
Per Requirement 30 - Feature Flag Management

Tests the complete interface implementation:
- Flag list view with status
- Flag configuration form (name, rollout %, target tenants)
- A/B test configuration
- Metrics dashboard
- Emergency kill switch

NO MOCKS - All tests use real database, views, and HTTP requests.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.test import Client, TestCase, override_settings
from django.urls import reverse

import pytest
from waffle.models import Flag

from apps.core.audit_signals import log_user_login, log_user_logout_signal
from apps.core.feature_flags import (
    ABTestVariant,
    EmergencyKillSwitch,
    FeatureFlagHistory,
    TenantFeatureFlag,
    track_flag_metric,
)
from apps.core.models import Tenant

User = get_user_model()


class BaseFeatureFlagTest(TestCase):
    """Base test class that disables audit logging."""

    @classmethod
    def setUpClass(cls):
        """Disconnect audit signals for all tests."""
        super().setUpClass()
        user_logged_in.disconnect(log_user_login)
        user_logged_out.disconnect(log_user_logout_signal)

    @classmethod
    def tearDownClass(cls):
        """Reconnect audit signals after tests."""
        super().tearDownClass()
        user_logged_in.connect(log_user_login)
        user_logged_out.connect(log_user_logout_signal)


@pytest.mark.django_db
class FeatureFlagListViewIntegrationTest(BaseFeatureFlagTest):
    """Test flag list view with status display."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="admin123",
            role="PLATFORM_ADMIN",
        )
        self.client.force_login(self.admin)

        # Create test flags
        self.active_flag = Flag.objects.create(
            name="active_feature",
            everyone=True,
            note="Active feature",
        )
        self.inactive_flag = Flag.objects.create(
            name="inactive_feature",
            everyone=False,
            note="Inactive feature",
        )
        self.percentage_flag = Flag.objects.create(
            name="percentage_feature",
            everyone=None,
            percent=50.0,
            note="Percentage rollout",
        )

    def test_flag_list_view_loads(self):
        """Test that flag list view loads successfully."""
        response = self.client.get(reverse("core:feature_flag_list"))
        assert response.status_code == 200
        assert "flags" in response.context
        assert "stats" in response.context

    def test_flag_list_shows_all_flags(self):
        """Test that all flags are displayed in the list."""
        response = self.client.get(reverse("core:feature_flag_list"))
        flags = response.context["flags"]
        assert flags.count() == 3
        flag_names = [f.name for f in flags]
        assert "active_feature" in flag_names
        assert "inactive_feature" in flag_names
        assert "percentage_feature" in flag_names

    def test_flag_list_statistics(self):
        """Test that statistics are calculated correctly."""
        response = self.client.get(reverse("core:feature_flag_list"))
        stats = response.context["stats"]
        assert stats["total_flags"] == 3
        assert stats["active_flags"] == 1
        assert stats["inactive_flags"] == 1
        assert stats["percentage_flags"] == 1

    def test_flag_list_search_filter(self):
        """Test search functionality."""
        # Search for "percentage" which should only match percentage_feature
        response = self.client.get(reverse("core:feature_flag_list") + "?search=percentage")
        flags = response.context["flags"]
        assert flags.count() == 1
        assert flags[0].name == "percentage_feature"

    def test_flag_list_status_filter(self):
        """Test status filter."""
        response = self.client.get(reverse("core:feature_flag_list") + "?status=active")
        flags = response.context["flags"]
        assert flags.count() == 1
        assert flags[0].everyone is True

    def test_flag_list_requires_authentication(self):
        """Test that unauthenticated users cannot access."""
        self.client.logout()
        response = self.client.get(reverse("core:feature_flag_list"))
        assert response.status_code == 302  # Redirect to login

    def test_flag_list_requires_platform_admin(self):
        """Test that non-admin users cannot access."""
        tenant = Tenant.objects.create(company_name="Test Shop", slug="test-shop")
        regular_user = User.objects.create_user(
            username="regular",
            email="regular@example.com",
            password="pass123",
            role="SHOP_OWNER",
            tenant=tenant,
        )
        self.client.logout()
        self.client.force_login(regular_user)
        response = self.client.get(reverse("core:feature_flag_list"))
        assert response.status_code == 403  # Forbidden


@pytest.mark.django_db
@override_settings(AUDIT_LOGGING_ENABLED=False)
class FeatureFlagCreateViewIntegrationTest(BaseFeatureFlagTest):
    """Test flag creation form."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="admin123",
            role="PLATFORM_ADMIN",
        )
        self.client.force_login(self.admin)

    def test_flag_create_view_loads(self):
        """Test that create view loads successfully."""
        response = self.client.get(reverse("core:feature_flag_create"))
        assert response.status_code == 200
        assert "form" in response.context

    def test_create_flag_with_valid_data(self):
        """Test creating a flag with valid data."""
        data = {
            "name": "new_feature",
            "everyone": "True",
            "note": "New feature for testing",
        }
        response = self.client.post(reverse("core:feature_flag_create"), data)
        assert response.status_code == 302  # Redirect after success

        # Verify flag was created
        flag = Flag.objects.get(name="new_feature")
        assert flag.everyone is True
        assert flag.note == "New feature for testing"

        # Verify history was tracked
        history = FeatureFlagHistory.objects.filter(flag_name="new_feature", action="created")
        assert history.exists()

    def test_create_flag_with_percentage(self):
        """Test creating a flag with percentage rollout."""
        data = {
            "name": "gradual_feature",
            "everyone": "",  # None for percentage
            "percent": "25.5",
            "note": "Gradual rollout",
        }
        response = self.client.post(reverse("core:feature_flag_create"), data)
        assert response.status_code == 302

        flag = Flag.objects.get(name="gradual_feature")
        assert flag.everyone is None
        assert float(flag.percent) == 25.5

    def test_create_flag_with_invalid_data(self):
        """Test that invalid data shows errors."""
        data = {
            "name": "",  # Empty name
            "everyone": "True",
        }
        response = self.client.post(reverse("core:feature_flag_create"), data)
        assert response.status_code == 200  # Stays on form
        assert "form" in response.context
        assert response.context["form"].errors


@pytest.mark.django_db
@override_settings(AUDIT_LOGGING_ENABLED=False)
class FeatureFlagUpdateViewIntegrationTest(BaseFeatureFlagTest):
    """Test flag update form."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="admin123",
            role="PLATFORM_ADMIN",
        )
        self.client.force_login(self.admin)

        self.flag = Flag.objects.create(
            name="test_feature",
            everyone=False,
            note="Test feature",
        )

    def test_flag_update_view_loads(self):
        """Test that update view loads successfully."""
        response = self.client.get(reverse("core:feature_flag_update", args=[self.flag.pk]))
        assert response.status_code == 200
        assert "form" in response.context
        assert response.context["object"] == self.flag

    def test_update_flag_status(self):
        """Test updating flag status."""
        data = {
            "name": "test_feature",
            "everyone": "True",  # Change to active
            "note": "Test feature",
            "reason": "Enabling for production",
        }
        response = self.client.post(reverse("core:feature_flag_update", args=[self.flag.pk]), data)
        assert response.status_code == 302

        self.flag.refresh_from_db()
        assert self.flag.everyone is True

        # Verify history was tracked
        history = FeatureFlagHistory.objects.filter(
            flag_name="test_feature", action="enabled"
        ).first()
        assert history is not None
        assert "production" in history.reason

    def test_update_flag_percentage(self):
        """Test updating rollout percentage."""
        data = {
            "name": "test_feature",
            "everyone": "",
            "percent": "75.0",
            "note": "Test feature",
            "reason": "Increasing rollout",
        }
        response = self.client.post(reverse("core:feature_flag_update", args=[self.flag.pk]), data)
        assert response.status_code == 302

        self.flag.refresh_from_db()
        assert float(self.flag.percent) == 75.0


@pytest.mark.django_db
@override_settings(AUDIT_LOGGING_ENABLED=False)
class FeatureFlagDetailViewIntegrationTest(BaseFeatureFlagTest):
    """Test flag detail view."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="admin123",
            role="PLATFORM_ADMIN",
        )
        self.client.force_login(self.admin)

        self.tenant = Tenant.objects.create(company_name="Test Shop", slug="test-shop")
        self.flag = Flag.objects.create(name="test_feature", everyone=True)

        # Create some history
        FeatureFlagHistory.objects.create(
            flag_name="test_feature",
            flag_type="flag",
            action="created",
            changed_by=self.admin,
        )

        # Create tenant override
        TenantFeatureFlag.objects.create(
            tenant=self.tenant,
            flag=self.flag,
            enabled=True,
            created_by=self.admin,
        )

    def test_flag_detail_view_loads(self):
        """Test that detail view loads successfully."""
        response = self.client.get(reverse("core:feature_flag_detail", args=[self.flag.pk]))
        assert response.status_code == 200
        assert response.context["flag"] == self.flag

    def test_flag_detail_shows_history(self):
        """Test that history is displayed."""
        response = self.client.get(reverse("core:feature_flag_detail", args=[self.flag.pk]))
        history = response.context["history"]
        assert history.count() > 0

    def test_flag_detail_shows_tenant_overrides(self):
        """Test that tenant overrides are displayed."""
        response = self.client.get(reverse("core:feature_flag_detail", args=[self.flag.pk]))
        overrides = response.context["tenant_overrides"]
        assert overrides.count() == 1
        assert overrides[0].tenant == self.tenant

    def test_flag_detail_shows_metrics(self):
        """Test that metrics are displayed."""
        # Track some metrics
        user = User.objects.create_user(
            username="user1", email="user1@example.com", password="pass123", role="PLATFORM_ADMIN"
        )
        track_flag_metric("test_feature", self.tenant, user, "viewed")

        response = self.client.get(reverse("core:feature_flag_detail", args=[self.flag.pk]))
        metrics = response.context["metrics"]
        assert metrics["total_events"] == 1


@pytest.mark.django_db
@override_settings(AUDIT_LOGGING_ENABLED=False)
class TenantFeatureFlagIntegrationTest(BaseFeatureFlagTest):
    """Test tenant-specific flag overrides."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="admin123",
            role="PLATFORM_ADMIN",
        )
        self.client.force_login(self.admin)

        self.tenant = Tenant.objects.create(company_name="Test Shop", slug="test-shop")
        self.flag = Flag.objects.create(name="test_feature", everyone=False)

    def test_tenant_flag_list_view_loads(self):
        """Test that tenant flag list loads."""
        response = self.client.get(reverse("core:tenant_feature_flag_list"))
        assert response.status_code == 200

    def test_create_tenant_override(self):
        """Test creating tenant-specific override."""
        data = {
            "tenant": self.tenant.pk,
            "flag": self.flag.pk,
            "enabled": True,
            "notes": "Beta testing for this tenant",
        }
        response = self.client.post(reverse("core:tenant_feature_flag_create"), data)
        assert response.status_code == 302

        # Verify override was created
        override = TenantFeatureFlag.objects.get(tenant=self.tenant, flag=self.flag)
        assert override.enabled is True
        assert "Beta testing" in override.notes

        # Verify history was tracked
        history = FeatureFlagHistory.objects.filter(
            flag_name="test_feature", tenant=self.tenant, action="enabled"
        )
        assert history.exists()


@pytest.mark.django_db
@override_settings(AUDIT_LOGGING_ENABLED=False)
class ABTestIntegrationTest(BaseFeatureFlagTest):
    """Test A/B testing functionality."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="admin123",
            role="PLATFORM_ADMIN",
        )
        self.client.force_login(self.admin)

        self.flag = Flag.objects.create(name="test_feature")

    def test_ab_test_list_view_loads(self):
        """Test that A/B test list loads."""
        response = self.client.get(reverse("core:ab_test_list"))
        assert response.status_code == 200

    def test_create_ab_test(self):
        """Test creating an A/B test."""
        data = {
            "name": "checkout_test",
            "flag": self.flag.pk,
            "control_group_percentage": "50.0",
            "variant_group_percentage": "50.0",
            "description": "Testing new checkout flow",
            "hypothesis": "New flow will increase conversion",
        }
        response = self.client.post(reverse("core:ab_test_create"), data)
        assert response.status_code == 302

        # Verify A/B test was created
        ab_test = ABTestVariant.objects.get(name="checkout_test")
        assert ab_test.flag == self.flag
        assert ab_test.control_group_percentage == 50.0
        assert ab_test.is_active is True

    def test_create_ab_test_invalid_percentages(self):
        """Test that invalid percentages are rejected."""
        data = {
            "name": "invalid_test",
            "flag": self.flag.pk,
            "control_group_percentage": "60.0",
            "variant_group_percentage": "50.0",  # Total = 110%
            "description": "Invalid test",
        }
        response = self.client.post(reverse("core:ab_test_create"), data)
        assert response.status_code == 200  # Stays on form
        assert "form" in response.context
        assert response.context["form"].errors

    def test_ab_test_detail_view(self):
        """Test A/B test detail view with metrics."""
        ab_test = ABTestVariant.objects.create(
            name="test_ab",
            flag=self.flag,
            control_group_percentage=50.0,
            variant_group_percentage=50.0,
            created_by=self.admin,
        )

        # Track some metrics
        tenant = Tenant.objects.create(company_name="Test Shop", slug="test-shop")
        user = User.objects.create_user(
            username="user1", email="user1@example.com", password="pass123", role="PLATFORM_ADMIN"
        )
        track_flag_metric(
            "test_feature",
            tenant,
            user,
            "converted",
            ab_test=ab_test,
            variant_group="control",
        )

        response = self.client.get(reverse("core:ab_test_detail", args=[ab_test.pk]))
        assert response.status_code == 200
        assert "metrics" in response.context
        assert "conversion_rates" in response.context

    def test_stop_ab_test(self):
        """Test stopping an A/B test."""
        ab_test = ABTestVariant.objects.create(
            name="test_ab",
            flag=self.flag,
            control_group_percentage=50.0,
            variant_group_percentage=50.0,
            created_by=self.admin,
        )

        response = self.client.post(reverse("core:ab_test_stop", args=[ab_test.pk]))
        assert response.status_code == 302

        ab_test.refresh_from_db()
        assert ab_test.is_active is False
        assert ab_test.end_date is not None


@pytest.mark.django_db
@override_settings(AUDIT_LOGGING_ENABLED=False)
class EmergencyKillSwitchIntegrationTest(BaseFeatureFlagTest):
    """Test emergency kill switch functionality."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="admin123",
            role="PLATFORM_ADMIN",
        )
        self.client.force_login(self.admin)

        self.flag = Flag.objects.create(name="problematic_feature", everyone=True)

    def test_kill_switch_list_view_loads(self):
        """Test that kill switch list loads."""
        response = self.client.get(reverse("core:kill_switch_list"))
        assert response.status_code == 200

    def test_activate_kill_switch(self):
        """Test activating emergency kill switch."""
        data = {
            "flag_name": "problematic_feature",
            "reason": "Critical bug causing data loss",
        }
        response = self.client.post(reverse("core:kill_switch_create"), data)
        assert response.status_code == 302

        # Verify kill switch was created
        kill_switch = EmergencyKillSwitch.objects.get(flag_name="problematic_feature")
        assert kill_switch.is_active is True
        assert "data loss" in kill_switch.reason
        assert kill_switch.disabled_by == self.admin

        # Verify history was tracked
        history = FeatureFlagHistory.objects.filter(
            flag_name="problematic_feature", action="emergency_disabled"
        )
        assert history.exists()

    def test_re_enable_after_kill_switch(self):
        """Test re-enabling feature after kill switch."""
        kill_switch = EmergencyKillSwitch.objects.create(
            flag_name="problematic_feature",
            reason="Critical bug",
            disabled_by=self.admin,
        )

        response = self.client.post(reverse("core:kill_switch_re_enable", args=[kill_switch.pk]))
        assert response.status_code == 302

        kill_switch.refresh_from_db()
        assert kill_switch.is_active is False
        assert kill_switch.re_enabled_by == self.admin
        assert kill_switch.re_enabled_at is not None


@pytest.mark.django_db
@override_settings(AUDIT_LOGGING_ENABLED=False)
class MetricsDashboardIntegrationTest(BaseFeatureFlagTest):
    """Test metrics dashboard."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="admin123",
            role="PLATFORM_ADMIN",
        )
        self.client.force_login(self.admin)

        self.tenant = Tenant.objects.create(company_name="Test Shop", slug="test-shop")
        self.flag = Flag.objects.create(name="test_feature", everyone=True)
        self.user = User.objects.create_user(
            username="user1", email="user1@example.com", password="pass123", role="PLATFORM_ADMIN"
        )

        # Track some metrics
        track_flag_metric("test_feature", self.tenant, self.user, "viewed")
        track_flag_metric("test_feature", self.tenant, self.user, "clicked")

    def test_metrics_dashboard_loads(self):
        """Test that metrics dashboard loads."""
        response = self.client.get(reverse("core:feature_flag_metrics"))
        assert response.status_code == 200
        assert "flag_metrics" in response.context

    def test_metrics_dashboard_shows_data(self):
        """Test that metrics data is displayed."""
        response = self.client.get(reverse("core:feature_flag_metrics"))
        flag_metrics = response.context["flag_metrics"]
        assert len(flag_metrics) > 0


@pytest.mark.django_db
@override_settings(AUDIT_LOGGING_ENABLED=False)
class FeatureFlagAPIIntegrationTest(BaseFeatureFlagTest):
    """Test API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="admin123",
            role="PLATFORM_ADMIN",
        )
        self.client.force_login(self.admin)

        self.flag = Flag.objects.create(name="test_feature", everyone=False)

    def test_stats_api_endpoint(self):
        """Test stats API endpoint."""
        response = self.client.get(reverse("core:feature_flag_stats_api"))
        assert response.status_code == 200
        data = response.json()
        assert "total_flags" in data
        assert "active_flags" in data
        assert data["total_flags"] >= 1

    def test_toggle_flag_api(self):
        """Test toggle flag API endpoint."""
        response = self.client.post(reverse("core:feature_flag_toggle", args=[self.flag.pk]))
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["enabled"] is True

        # Verify flag was toggled
        self.flag.refresh_from_db()
        assert self.flag.everyone is True

        # Verify history was tracked
        history = FeatureFlagHistory.objects.filter(flag_name="test_feature", action="enabled")
        assert history.exists()
