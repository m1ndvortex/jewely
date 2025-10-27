"""
Tests for the monitoring alert system.

Per Requirements 7 - System Monitoring and Health Dashboard
"""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

import pytest

from apps.core.alert_models import AlertRule, MonitoringAlert
from apps.core.alert_service import AlertService

User = get_user_model()


@pytest.mark.django_db
class TestAlertRule(TestCase):
    """Test AlertRule model."""

    def setUp(self):
        """Set up test data."""
        # Clean up any existing data
        AlertRule.objects.all().delete()
        MonitoringAlert.objects.all().delete()

        # Use unique username for each test
        unique_id = str(uuid.uuid4())[:8]
        self.user = User.objects.create_user(
            username=f"admin_{unique_id}",
            email=f"admin_{unique_id}@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

    def test_create_alert_rule(self):
        """Test creating an alert rule."""
        rule = AlertRule.objects.create(
            name="High CPU Usage",
            description="Alert when CPU usage exceeds 80%",
            metric_type=AlertRule.CPU_USAGE,
            operator=AlertRule.GREATER_THAN,
            threshold=80.0,
            severity=AlertRule.WARNING,
            is_enabled=True,
            check_interval_minutes=5,
            cooldown_minutes=30,
            send_email=True,
            email_recipients="admin@example.com",
            created_by=self.user,
        )

        assert rule.name == "High CPU Usage"
        assert rule.metric_type == AlertRule.CPU_USAGE
        assert rule.threshold == 80.0
        assert rule.is_enabled is True

    def test_should_trigger_greater_than(self):
        """Test alert triggering with greater than operator."""
        rule = AlertRule.objects.create(
            name="High CPU Usage",
            metric_type=AlertRule.CPU_USAGE,
            operator=AlertRule.GREATER_THAN,
            threshold=80.0,
            severity=AlertRule.WARNING,
            created_by=self.user,
        )

        assert rule.should_trigger(85.0) is True
        assert rule.should_trigger(75.0) is False
        assert rule.should_trigger(80.0) is False

    def test_should_trigger_less_than(self):
        """Test alert triggering with less than operator."""
        rule = AlertRule.objects.create(
            name="Low Disk Space",
            metric_type=AlertRule.DISK_USAGE,
            operator=AlertRule.LESS_THAN,
            threshold=10.0,
            severity=AlertRule.CRITICAL,
            created_by=self.user,
        )

        assert rule.should_trigger(5.0) is True
        assert rule.should_trigger(15.0) is False
        assert rule.should_trigger(10.0) is False

    def test_get_email_recipients_list(self):
        """Test parsing email recipients."""
        rule = AlertRule.objects.create(
            name="Test Rule",
            metric_type=AlertRule.CPU_USAGE,
            threshold=80.0,
            email_recipients="admin@example.com, user@example.com, test@example.com",
            created_by=self.user,
        )

        recipients = rule.get_email_recipients_list()
        assert len(recipients) == 3
        assert "admin@example.com" in recipients
        assert "user@example.com" in recipients
        assert "test@example.com" in recipients


@pytest.mark.django_db
class TestMonitoringAlert(TestCase):
    """Test MonitoringAlert model."""

    def setUp(self):
        """Set up test data."""
        # Clean up any existing data
        AlertRule.objects.all().delete()
        MonitoringAlert.objects.all().delete()

        # Use unique username for each test
        unique_id = str(uuid.uuid4())[:8]
        self.user = User.objects.create_user(
            username=f"admin_{unique_id}",
            email=f"admin_{unique_id}@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        self.rule = AlertRule.objects.create(
            name="High CPU Usage",
            metric_type=AlertRule.CPU_USAGE,
            operator=AlertRule.GREATER_THAN,
            threshold=80.0,
            severity=AlertRule.WARNING,
            created_by=self.user,
        )

    def test_create_monitoring_alert(self):
        """Test creating a monitoring alert."""
        alert = MonitoringAlert.objects.create(
            alert_rule=self.rule,
            message="CPU usage exceeded threshold",
            current_value=85.0,
            threshold_value=80.0,
            status=MonitoringAlert.ACTIVE,
        )

        assert alert.alert_rule == self.rule
        assert alert.current_value == 85.0
        assert alert.status == MonitoringAlert.ACTIVE

    def test_acknowledge_alert(self):
        """Test acknowledging an alert."""
        alert = MonitoringAlert.objects.create(
            alert_rule=self.rule,
            message="CPU usage exceeded threshold",
            current_value=85.0,
            threshold_value=80.0,
            status=MonitoringAlert.ACTIVE,
        )

        alert.acknowledge(self.user, "Investigating the issue")

        assert alert.status == MonitoringAlert.ACKNOWLEDGED
        assert alert.acknowledged_by == self.user
        assert alert.acknowledgment_notes == "Investigating the issue"
        assert alert.acknowledged_at is not None

    def test_resolve_alert(self):
        """Test resolving an alert."""
        alert = MonitoringAlert.objects.create(
            alert_rule=self.rule,
            message="CPU usage exceeded threshold",
            current_value=85.0,
            threshold_value=80.0,
            status=MonitoringAlert.ACTIVE,
        )

        alert.resolve(self.user, "Issue resolved")

        assert alert.status == MonitoringAlert.RESOLVED
        assert alert.resolved_by == self.user
        assert alert.resolution_notes == "Issue resolved"
        assert alert.resolved_at is not None

    def test_escalate_alert(self):
        """Test escalating an alert."""
        alert = MonitoringAlert.objects.create(
            alert_rule=self.rule,
            message="CPU usage exceeded threshold",
            current_value=85.0,
            threshold_value=80.0,
            status=MonitoringAlert.ACTIVE,
        )

        alert.escalate()

        assert alert.status == MonitoringAlert.ESCALATED
        assert alert.escalated_at is not None


@pytest.mark.django_db
class TestAlertService(TestCase):
    """Test AlertService."""

    def setUp(self):
        """Set up test data."""
        # Clean up any existing data
        AlertRule.objects.all().delete()
        MonitoringAlert.objects.all().delete()

        # Use unique username for each test
        unique_id = str(uuid.uuid4())[:8]
        self.user = User.objects.create_user(
            username=f"admin_{unique_id}",
            email=f"admin_{unique_id}@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        self.rule = AlertRule.objects.create(
            name="High CPU Usage",
            metric_type=AlertRule.CPU_USAGE,
            operator=AlertRule.GREATER_THAN,
            threshold=80.0,
            severity=AlertRule.WARNING,
            is_enabled=True,
            cooldown_minutes=30,
            created_by=self.user,
        )

    def test_check_metric_triggers_alert(self):
        """Test that check_metric creates an alert when threshold is exceeded."""
        alerts = AlertService.check_metric(AlertRule.CPU_USAGE, 85.0)

        assert len(alerts) == 1
        assert alerts[0].alert_rule == self.rule
        assert alerts[0].current_value == 85.0

    def test_check_metric_no_alert_below_threshold(self):
        """Test that check_metric doesn't create alert when below threshold."""
        alerts = AlertService.check_metric(AlertRule.CPU_USAGE, 75.0)

        assert len(alerts) == 0

    def test_check_metric_respects_cooldown(self):
        """Test that cooldown period is respected."""
        # First alert
        alerts1 = AlertService.check_metric(AlertRule.CPU_USAGE, 85.0)
        assert len(alerts1) == 1

        # Second alert immediately (should be blocked by cooldown)
        alerts2 = AlertService.check_metric(AlertRule.CPU_USAGE, 90.0)
        assert len(alerts2) == 0

    def test_check_metric_disabled_rule(self):
        """Test that disabled rules don't trigger alerts."""
        self.rule.is_enabled = False
        self.rule.save()

        alerts = AlertService.check_metric(AlertRule.CPU_USAGE, 85.0)

        assert len(alerts) == 0
