"""
Comprehensive integration tests for feature flag management.
Per Requirement 30 - Feature Flag Management

Tests all 7 acceptance criteria:
1. Enable/disable features globally or per tenant
2. Gradual feature rollout by percentage
3. Feature enablement for specific tenants
4. Track feature flag changes and history
5. Emergency kill switch
6. A/B testing support
7. Conversion metrics tracking

NO MOCKS - All tests use real database and services.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

import pytest
from waffle.models import Flag, Sample, Switch
from waffle.testutils import override_flag, override_sample, override_switch

from apps.core.feature_flags import (
    ABTestVariant,
    EmergencyKillSwitch,
    FeatureFlagHistory,
    TenantFeatureFlag,
    disable_flag_for_tenant,
    emergency_disable_flag,
    enable_flag_for_tenant,
    get_ab_test_metrics,
    get_flag_conversion_metrics,
    is_flag_active_for_tenant,
    set_flag_percentage,
    track_flag_metric,
)
from apps.core.models import Tenant

User = get_user_model()


class FeatureFlagBasicTestCase(TestCase):
    """Test basic waffle integration."""

    def setUp(self):
        """Set up test data."""
        # Create test user (platform admin doesn't require tenant)
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

    def test_flag_creation(self):
        """Test creating a feature flag."""
        flag = Flag.objects.create(
            name="test_feature",
            note="Test feature flag",
            everyone=None,
        )

        assert flag.name == "test_feature"
        assert flag.note == "Test feature flag"
        assert flag.everyone is None

    def test_switch_creation(self):
        """Test creating a feature switch."""
        switch = Switch.objects.create(
            name="test_switch",
            active=True,
            note="Test switch",
        )

        assert switch.name == "test_switch"
        assert switch.active is True
        assert switch.note == "Test switch"

    def test_sample_creation(self):
        """Test creating a feature sample."""
        sample = Sample.objects.create(
            name="test_sample",
            percent=50.0,
            note="Test sample for A/B testing",
        )

        assert sample.name == "test_sample"
        assert sample.percent == 50.0
        assert sample.note == "Test sample for A/B testing"

    @override_flag("test_feature", active=True)
    def test_flag_override_active(self):
        """Test flag override decorator with active flag."""
        from waffle import flag_is_active

        # Flag should be active due to override
        assert flag_is_active(None, "test_feature") is True

    @override_flag("test_feature", active=False)
    def test_flag_override_inactive(self):
        """Test flag override decorator with inactive flag."""
        from waffle import flag_is_active

        # Flag should be inactive due to override
        assert flag_is_active(None, "test_feature") is False

    @override_switch("test_switch", active=True)
    def test_switch_override_active(self):
        """Test switch override decorator with active switch."""
        from waffle import switch_is_active

        # Switch should be active due to override
        assert switch_is_active("test_switch") is True

    @override_switch("test_switch", active=False)
    def test_switch_override_inactive(self):
        """Test switch override decorator with inactive switch."""
        from waffle import switch_is_active

        # Switch should be inactive due to override
        assert switch_is_active("test_switch") is False

    @override_sample("test_sample", active=True)
    def test_sample_override_active(self):
        """Test sample override decorator with active sample."""
        from waffle import sample_is_active

        # Sample should be active due to override
        assert sample_is_active("test_sample") is True

    @override_sample("test_sample", active=False)
    def test_sample_override_inactive(self):
        """Test sample override decorator with inactive sample."""
        from waffle import sample_is_active

        # Sample should be inactive due to override
        assert sample_is_active("test_sample") is False

    def test_flag_for_everyone(self):
        """Test flag enabled for everyone."""
        from waffle import flag_is_active

        Flag.objects.create(
            name="everyone_feature",
            everyone=True,
        )

        # Should be active for any user
        assert flag_is_active(None, "everyone_feature") is True
        assert flag_is_active(self.user, "everyone_feature") is True

    def test_flag_for_nobody(self):
        """Test flag disabled for everyone."""
        from waffle import flag_is_active

        Flag.objects.create(
            name="nobody_feature",
            everyone=False,
        )

        # Should be inactive for any user
        assert flag_is_active(None, "nobody_feature") is False
        assert flag_is_active(self.user, "nobody_feature") is False


@pytest.mark.django_db
class AcceptanceCriteria1And3TestCase(TestCase):
    """
    Test Acceptance Criteria 1 and 3:
    - Enable/disable features globally or per tenant
    - Feature enablement for specific tenants for beta testing
    """

    def setUp(self):
        """Set up test data."""
        # Create tenants
        self.tenant1 = Tenant.objects.create(
            company_name="Test Shop 1",
            slug="test-shop-1",
        )
        self.tenant2 = Tenant.objects.create(
            company_name="Test Shop 2",
            slug="test-shop-2",
        )

        # Create admin user
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="admin123",
            role="PLATFORM_ADMIN",
        )

        # Create tenant users
        self.user1 = User.objects.create_user(
            username="user1",
            email="user1@example.com",
            password="pass123",
            role="PLATFORM_ADMIN",
        )

        # Create a global flag (disabled by default)
        self.flag = Flag.objects.create(
            name="new_feature",
            note="New feature for testing",
            everyone=False,
        )

    def test_global_flag_disabled(self):
        """Test that global flag is disabled by default."""
        # Flag should be disabled globally
        assert is_flag_active_for_tenant("new_feature", self.tenant1, self.user1) is False
        assert is_flag_active_for_tenant("new_feature", self.tenant2, self.user1) is False

    def test_enable_flag_for_specific_tenant(self):
        """Test enabling flag for a specific tenant (beta testing)."""
        # Enable for tenant1 only
        enable_flag_for_tenant(
            "new_feature",
            self.tenant1,
            self.admin,
            notes="Beta testing for tenant1",
        )

        # Should be enabled for tenant1
        assert is_flag_active_for_tenant("new_feature", self.tenant1, self.user1) is True

        # Should still be disabled for tenant2
        assert is_flag_active_for_tenant("new_feature", self.tenant2, self.user1) is False

        # Verify TenantFeatureFlag was created
        tenant_flag = TenantFeatureFlag.objects.get(tenant=self.tenant1, flag=self.flag)
        assert tenant_flag.enabled is True
        assert tenant_flag.notes == "Beta testing for tenant1"
        assert tenant_flag.created_by == self.admin

    def test_disable_flag_for_specific_tenant(self):
        """Test disabling flag for a specific tenant."""
        # First enable globally
        self.flag.everyone = True
        self.flag.save()

        # Disable for tenant1 specifically
        disable_flag_for_tenant(
            "new_feature",
            self.tenant1,
            self.admin,
            notes="Disabling due to issues",
        )

        # Should be disabled for tenant1 (override takes precedence)
        assert is_flag_active_for_tenant("new_feature", self.tenant1, self.user1) is False

        # Should still be enabled for tenant2 (global setting)
        assert is_flag_active_for_tenant("new_feature", self.tenant2, self.user1) is True

    def test_tenant_override_precedence(self):
        """Test that tenant-specific overrides take precedence over global settings."""
        # Enable globally
        self.flag.everyone = True
        self.flag.save()

        # Disable for tenant1
        disable_flag_for_tenant("new_feature", self.tenant1, self.admin)

        # Tenant override should take precedence
        assert is_flag_active_for_tenant("new_feature", self.tenant1, self.user1) is False
        assert is_flag_active_for_tenant("new_feature", self.tenant2, self.user1) is True


@pytest.mark.django_db
class AcceptanceCriteria2TestCase(TestCase):
    """
    Test Acceptance Criteria 2:
    - Gradual feature rollout to a percentage of tenants
    """

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="admin123",
            role="PLATFORM_ADMIN",
        )

        self.flag = Flag.objects.create(
            name="gradual_feature",
            note="Feature with gradual rollout",
            percent=0.0,
        )

    def test_set_rollout_percentage(self):
        """Test setting gradual rollout percentage."""
        # Set to 25%
        set_flag_percentage(
            "gradual_feature",
            25.0,
            self.admin,
            reason="Starting gradual rollout",
        )

        # Verify percentage was set
        self.flag.refresh_from_db()
        assert self.flag.percent == 25.0

    def test_increase_rollout_percentage(self):
        """Test increasing rollout percentage over time."""
        # Start at 10%
        set_flag_percentage("gradual_feature", 10.0, self.admin, reason="Initial rollout")
        self.flag.refresh_from_db()
        assert float(self.flag.percent) == 10.0

        # Increase to 50%
        set_flag_percentage("gradual_feature", 50.0, self.admin, reason="Expanding rollout")
        self.flag.refresh_from_db()
        assert float(self.flag.percent) == 50.0

        # Increase to 99.9% (max value for waffle's decimal field)
        set_flag_percentage("gradual_feature", 99.9, self.admin, reason="Full rollout")
        self.flag.refresh_from_db()
        assert float(self.flag.percent) == 99.9


@pytest.mark.django_db
class AcceptanceCriteria4TestCase(TestCase):
    """
    Test Acceptance Criteria 4:
    - Track feature flag changes and rollout history
    """

    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="admin123",
            role="PLATFORM_ADMIN",
        )

        self.flag = Flag.objects.create(
            name="tracked_feature",
            note="Feature with change tracking",
            percent=0.0,
        )

    def test_track_tenant_flag_enable(self):
        """Test that enabling a flag for a tenant is tracked in history."""
        # Enable flag for tenant
        enable_flag_for_tenant(
            "tracked_feature",
            self.tenant,
            self.admin,
            notes="Enabling for beta testing",
        )

        # Verify history was created
        history = FeatureFlagHistory.objects.filter(
            flag_name="tracked_feature",
            tenant=self.tenant,
            action="enabled",
        ).first()

        assert history is not None
        assert history.flag_type == "tenant_override"
        assert history.changed_by == self.admin
        assert history.new_value["enabled"] is True
        assert "beta testing" in history.reason

    def test_track_tenant_flag_disable(self):
        """Test that disabling a flag for a tenant is tracked in history."""
        # Disable flag for tenant
        disable_flag_for_tenant(
            "tracked_feature",
            self.tenant,
            self.admin,
            notes="Disabling due to bug",
        )

        # Verify history was created
        history = FeatureFlagHistory.objects.filter(
            flag_name="tracked_feature",
            tenant=self.tenant,
            action="disabled",
        ).first()

        assert history is not None
        assert history.flag_type == "tenant_override"
        assert history.changed_by == self.admin
        assert history.new_value["enabled"] is False
        assert "bug" in history.reason

    def test_track_percentage_change(self):
        """Test that percentage changes are tracked in history."""
        # Change percentage
        set_flag_percentage(
            "tracked_feature",
            25.0,
            self.admin,
            reason="Starting gradual rollout",
        )

        # Verify history was created
        history = FeatureFlagHistory.objects.filter(
            flag_name="tracked_feature",
            action="percentage_changed",
        ).first()

        assert history is not None
        assert history.flag_type == "flag"
        assert history.changed_by == self.admin
        assert history.old_value["percent"] == 0.0
        assert history.new_value["percent"] == 25.0
        assert "gradual rollout" in history.reason

    def test_history_ordering(self):
        """Test that history is ordered by timestamp (newest first)."""
        # Make multiple changes
        enable_flag_for_tenant("tracked_feature", self.tenant, self.admin, notes="First change")
        disable_flag_for_tenant("tracked_feature", self.tenant, self.admin, notes="Second change")
        enable_flag_for_tenant("tracked_feature", self.tenant, self.admin, notes="Third change")

        # Get history
        history = FeatureFlagHistory.objects.filter(
            flag_name="tracked_feature",
            tenant=self.tenant,
        ).order_by("-timestamp")

        # Verify ordering
        assert history.count() == 3
        assert "Third change" in history[0].reason
        assert "Second change" in history[1].reason
        assert "First change" in history[2].reason


@pytest.mark.django_db
class AcceptanceCriteria5TestCase(TestCase):
    """
    Test Acceptance Criteria 5:
    - Emergency kill switch to quickly disable problematic features
    """

    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="admin123",
            role="PLATFORM_ADMIN",
        )

        self.user = User.objects.create_user(
            username="user",
            email="user@example.com",
            password="pass123",
            role="PLATFORM_ADMIN",
        )

        # Create a flag that's enabled globally
        self.flag = Flag.objects.create(
            name="problematic_feature",
            note="Feature that might have issues",
            everyone=True,
        )

    def test_emergency_disable(self):
        """Test emergency kill switch disables feature immediately."""
        # Verify flag is initially active
        assert is_flag_active_for_tenant("problematic_feature", self.tenant, self.user) is True

        # Activate emergency kill switch
        kill_switch = emergency_disable_flag(
            "problematic_feature",
            self.admin,
            reason="Critical bug causing data loss",
        )

        # Verify kill switch was created
        assert kill_switch is not None
        assert kill_switch.flag_name == "problematic_feature"
        assert kill_switch.is_active is True
        assert kill_switch.disabled_by == self.admin
        assert "data loss" in kill_switch.reason

        # Verify flag is now disabled (kill switch takes precedence)
        assert is_flag_active_for_tenant("problematic_feature", self.tenant, self.user) is False

    def test_emergency_disable_tracked_in_history(self):
        """Test that emergency disable is tracked in history."""
        # Activate emergency kill switch
        emergency_disable_flag(
            "problematic_feature",
            self.admin,
            reason="Critical bug",
        )

        # Verify history was created
        history = FeatureFlagHistory.objects.filter(
            flag_name="problematic_feature",
            action="emergency_disabled",
        ).first()

        assert history is not None
        assert history.changed_by == self.admin
        assert history.new_value["emergency_disabled"] is True
        assert "Critical bug" in history.reason

    def test_re_enable_after_emergency(self):
        """Test re-enabling feature after emergency disable."""
        # Activate emergency kill switch
        kill_switch = emergency_disable_flag(
            "problematic_feature",
            self.admin,
            reason="Critical bug",
        )

        # Verify flag is disabled
        assert is_flag_active_for_tenant("problematic_feature", self.tenant, self.user) is False

        # Re-enable
        kill_switch.re_enable(self.admin)

        # Verify kill switch is no longer active
        kill_switch.refresh_from_db()
        assert kill_switch.is_active is False
        assert kill_switch.re_enabled_by == self.admin
        assert kill_switch.re_enabled_at is not None

        # Verify flag is active again
        assert is_flag_active_for_tenant("problematic_feature", self.tenant, self.user) is True

    def test_multiple_emergency_disables(self):
        """Test that multiple emergency disables can exist."""
        # Create multiple kill switches
        emergency_disable_flag("feature1", self.admin, reason="Bug in feature1")
        emergency_disable_flag("feature2", self.admin, reason="Bug in feature2")

        # Verify both exist
        assert EmergencyKillSwitch.objects.filter(is_active=True).count() == 2


@pytest.mark.django_db
class AcceptanceCriteria6TestCase(TestCase):
    """
    Test Acceptance Criteria 6:
    - A/B testing with control and variant groups
    """

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="admin123",
            role="PLATFORM_ADMIN",
        )

        self.flag = Flag.objects.create(
            name="ab_test_feature",
            note="Feature for A/B testing",
        )

    def test_create_ab_test(self):
        """Test creating an A/B test variant."""
        ab_test = ABTestVariant.objects.create(
            name="checkout_flow_test",
            flag=self.flag,
            control_group_percentage=50.0,
            variant_group_percentage=50.0,
            description="Testing new checkout flow",
            hypothesis="New flow will increase conversion by 10%",
            created_by=self.admin,
        )

        assert ab_test.name == "checkout_flow_test"
        assert ab_test.flag == self.flag
        assert ab_test.control_group_percentage == 50.0
        assert ab_test.variant_group_percentage == 50.0
        assert ab_test.is_active is True
        assert ab_test.end_date is None

    def test_stop_ab_test(self):
        """Test stopping an A/B test."""
        ab_test = ABTestVariant.objects.create(
            name="test_to_stop",
            flag=self.flag,
            control_group_percentage=50.0,
            variant_group_percentage=50.0,
            created_by=self.admin,
        )

        # Verify test is active
        assert ab_test.is_active is True
        assert ab_test.end_date is None

        # Stop the test
        ab_test.stop_test()

        # Verify test is stopped
        assert ab_test.is_active is False
        assert ab_test.end_date is not None

    def test_ab_test_with_different_percentages(self):
        """Test A/B test with unequal group sizes."""
        ab_test = ABTestVariant.objects.create(
            name="unequal_test",
            flag=self.flag,
            control_group_percentage=70.0,
            variant_group_percentage=30.0,
            description="Testing with 70/30 split",
            created_by=self.admin,
        )

        assert ab_test.control_group_percentage == 70.0
        assert ab_test.variant_group_percentage == 30.0


@pytest.mark.django_db
class AcceptanceCriteria7TestCase(TestCase):
    """
    Test Acceptance Criteria 7:
    - Track conversion rates and metrics for each variant
    """

    def setUp(self):
        """Set up test data."""
        self.tenant = Tenant.objects.create(
            company_name="Test Shop",
            slug="test-shop",
        )

        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="admin123",
            role="PLATFORM_ADMIN",
        )

        self.user1 = User.objects.create_user(
            username="user1",
            email="user1@example.com",
            password="pass123",
            role="PLATFORM_ADMIN",
        )

        self.user2 = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            password="pass123",
            role="PLATFORM_ADMIN",
        )

        self.flag = Flag.objects.create(
            name="metric_feature",
            note="Feature with metrics tracking",
        )

        self.ab_test = ABTestVariant.objects.create(
            name="conversion_test",
            flag=self.flag,
            control_group_percentage=50.0,
            variant_group_percentage=50.0,
            created_by=self.admin,
        )

    def test_track_simple_metric(self):
        """Test tracking a simple metric event."""
        metric = track_flag_metric(
            flag_name="metric_feature",
            tenant=self.tenant,
            user=self.user1,
            event_type="viewed",
        )

        assert metric.flag_name == "metric_feature"
        assert metric.tenant == self.tenant
        assert metric.user == self.user1
        assert metric.event_type == "viewed"
        assert metric.variant_group == "none"

    def test_track_ab_test_metric(self):
        """Test tracking metrics for A/B test variants."""
        # Track control group event
        control_metric = track_flag_metric(
            flag_name="metric_feature",
            tenant=self.tenant,
            user=self.user1,
            event_type="clicked",
            ab_test=self.ab_test,
            variant_group="control",
        )

        # Track variant group event
        variant_metric = track_flag_metric(
            flag_name="metric_feature",
            tenant=self.tenant,
            user=self.user2,
            event_type="clicked",
            ab_test=self.ab_test,
            variant_group="variant",
        )

        assert control_metric.variant_group == "control"
        assert control_metric.ab_test == self.ab_test
        assert variant_metric.variant_group == "variant"
        assert variant_metric.ab_test == self.ab_test

    def test_track_metric_with_event_data(self):
        """Test tracking metrics with additional event data."""
        metric = track_flag_metric(
            flag_name="metric_feature",
            tenant=self.tenant,
            user=self.user1,
            event_type="converted",
            event_data={
                "amount": 299.99,
                "currency": "USD",
                "items": 3,
            },
        )

        assert metric.event_data["amount"] == 299.99
        assert metric.event_data["currency"] == "USD"
        assert metric.event_data["items"] == 3

    def test_get_flag_conversion_metrics(self):
        """Test retrieving conversion metrics for a flag."""
        # Track multiple events
        track_flag_metric("metric_feature", self.tenant, self.user1, "viewed")
        track_flag_metric("metric_feature", self.tenant, self.user1, "clicked")
        track_flag_metric("metric_feature", self.tenant, self.user2, "viewed")
        track_flag_metric("metric_feature", self.tenant, self.user2, "converted")

        # Get metrics
        metrics = get_flag_conversion_metrics("metric_feature")

        assert metrics["total_events"] == 4
        assert metrics["unique_users"] == 2
        assert metrics["unique_tenants"] == 1

        # Check events by type
        events_by_type = {item["event_type"]: item["count"] for item in metrics["events_by_type"]}
        assert events_by_type["viewed"] == 2
        assert events_by_type["clicked"] == 1
        assert events_by_type["converted"] == 1

    def test_get_ab_test_metrics(self):
        """Test retrieving A/B test metrics comparing control vs variant."""
        # Track control group events
        track_flag_metric(
            "metric_feature",
            self.tenant,
            self.user1,
            "viewed",
            ab_test=self.ab_test,
            variant_group="control",
        )
        track_flag_metric(
            "metric_feature",
            self.tenant,
            self.user1,
            "clicked",
            ab_test=self.ab_test,
            variant_group="control",
        )

        # Track variant group events
        track_flag_metric(
            "metric_feature",
            self.tenant,
            self.user2,
            "viewed",
            ab_test=self.ab_test,
            variant_group="variant",
        )
        track_flag_metric(
            "metric_feature",
            self.tenant,
            self.user2,
            "clicked",
            ab_test=self.ab_test,
            variant_group="variant",
        )
        track_flag_metric(
            "metric_feature",
            self.tenant,
            self.user2,
            "converted",
            ab_test=self.ab_test,
            variant_group="variant",
        )

        # Get A/B test metrics
        metrics = get_ab_test_metrics(self.ab_test.id)

        assert metrics["test_name"] == "conversion_test"
        assert metrics["control"]["total_events"] == 2
        assert metrics["control"]["unique_users"] == 1
        assert metrics["variant"]["total_events"] == 3
        assert metrics["variant"]["unique_users"] == 1

    def test_metrics_time_filtering(self):
        """Test filtering metrics by time range."""
        from datetime import timedelta

        # Track events
        track_flag_metric("metric_feature", self.tenant, self.user1, "viewed")
        track_flag_metric("metric_feature", self.tenant, self.user2, "clicked")

        # Get metrics for last hour
        now = timezone.now()
        one_hour_ago = now - timedelta(hours=1)

        metrics = get_flag_conversion_metrics(
            "metric_feature",
            start_date=one_hour_ago,
            end_date=now,
        )

        assert metrics["total_events"] == 2


@pytest.mark.django_db
class FeatureFlagManagementCommandTest:
    """Test feature flag management command."""

    def test_setup_feature_flags_command(self):
        """Test that setup_feature_flags command creates flags."""
        from django.core.management import call_command

        # Run the command
        call_command("setup_feature_flags")

        # Verify flags were created
        assert Flag.objects.filter(name="new_pos_interface").exists()
        assert Flag.objects.filter(name="advanced_reporting").exists()
        assert Flag.objects.filter(name="loyalty_program_v2").exists()

        # Verify switches were created
        assert Switch.objects.filter(name="maintenance_mode").exists()
        assert Switch.objects.filter(name="new_tenant_signups").exists()
        assert Switch.objects.filter(name="email_notifications").exists()

        # Verify samples were created
        assert Sample.objects.filter(name="new_dashboard_layout").exists()
        assert Sample.objects.filter(name="performance_monitoring").exists()
        assert Sample.objects.filter(name="ab_test_checkout_flow").exists()

    def test_setup_feature_flags_idempotent(self):
        """Test that running setup_feature_flags multiple times is safe."""
        from django.core.management import call_command

        # Run the command twice
        call_command("setup_feature_flags")
        initial_flag_count = Flag.objects.count()
        initial_switch_count = Switch.objects.count()
        initial_sample_count = Sample.objects.count()

        call_command("setup_feature_flags")

        # Counts should remain the same
        assert Flag.objects.count() == initial_flag_count
        assert Switch.objects.count() == initial_switch_count
        assert Sample.objects.count() == initial_sample_count
