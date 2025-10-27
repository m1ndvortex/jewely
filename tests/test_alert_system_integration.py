"""
Integration tests for the monitoring alert system.

These tests verify the alert system works end-to-end with real services.
No mocks allowed - tests use real PostgreSQL, Redis, and Celery.

Per Requirements 7 - System Monitoring and Health Dashboard
"""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

import pytest

from apps.core.alert_models import AlertDeliveryLog, AlertRule, MonitoringAlert
from apps.core.alert_service import AlertService

User = get_user_model()


@pytest.mark.django_db
class TestAlertSystemIntegration(TestCase):
    """
    Integration tests for the complete alert system.

    Tests the full workflow from metric checking to alert delivery.
    """

    def setUp(self):
        """Set up test data."""
        # Clean up any existing data
        AlertRule.objects.all().delete()
        MonitoringAlert.objects.all().delete()
        AlertDeliveryLog.objects.all().delete()

        # Create admin user
        unique_id = str(uuid.uuid4())[:8]
        self.user = User.objects.create_user(
            username=f"admin_{unique_id}",
            email=f"test_{unique_id}@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

    def test_end_to_end_alert_creation_and_delivery(self):
        """
        Test complete alert workflow from creation to delivery.

        Requirement 7.5: Send alerts when system metrics exceed defined thresholds.
        Requirement 7.7: Deliver alerts via email, SMS, and in-app notifications.
        """
        # Create an alert rule
        rule = AlertRule.objects.create(
            name="Test High CPU Alert",
            description="Alert when CPU exceeds 80%",
            metric_type=AlertRule.CPU_USAGE,
            operator=AlertRule.GREATER_THAN,
            threshold=80.0,
            severity=AlertRule.CRITICAL,
            is_enabled=True,
            check_interval_minutes=5,
            cooldown_minutes=30,
            send_email=True,
            email_recipients=self.user.email,
            created_by=self.user,
        )

        # Trigger alert by checking metric above threshold
        alerts = AlertService.check_metric(AlertRule.CPU_USAGE, 85.0)

        # Verify alert was created
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.alert_rule == rule
        assert alert.current_value == 85.0
        assert alert.status == MonitoringAlert.ACTIVE

        # Verify email was sent
        assert alert.email_sent is True
        assert alert.email_sent_at is not None

        # Verify delivery log was created
        delivery_logs = AlertDeliveryLog.objects.filter(alert=alert)
        assert delivery_logs.count() > 0

        email_log = delivery_logs.filter(channel=AlertDeliveryLog.EMAIL).first()
        assert email_log is not None
        assert email_log.recipient == self.user.email
        assert email_log.status == AlertDeliveryLog.SENT

    def test_alert_acknowledgment_workflow(self):
        """
        Test alert acknowledgment workflow.

        Requirement 7.8: Log all alerts with timestamps and resolution status.
        """
        # Create rule and trigger alert
        rule = AlertRule.objects.create(
            name="Test Memory Alert",
            metric_type=AlertRule.MEMORY_USAGE,
            operator=AlertRule.GREATER_THAN,
            threshold=85.0,
            severity=AlertRule.WARNING,
            is_enabled=True,
            created_by=self.user,
        )

        alerts = AlertService.check_metric(AlertRule.MEMORY_USAGE, 90.0)
        alert = alerts[0]
        assert alert.alert_rule == rule

        # Acknowledge the alert
        alert.acknowledge(self.user, "Investigating high memory usage")

        # Verify acknowledgment
        alert.refresh_from_db()
        assert alert.status == MonitoringAlert.ACKNOWLEDGED
        assert alert.acknowledged_by == self.user
        assert alert.acknowledged_at is not None
        assert "Investigating" in alert.acknowledgment_notes

    def test_alert_resolution_workflow(self):
        """
        Test alert resolution workflow.

        Requirement 7.8: Log all alerts with timestamps and resolution status.
        """
        # Create rule and trigger alert
        rule = AlertRule.objects.create(
            name="Test Disk Alert",
            metric_type=AlertRule.DISK_USAGE,
            operator=AlertRule.GREATER_THAN,
            threshold=90.0,
            severity=AlertRule.CRITICAL,
            is_enabled=True,
            created_by=self.user,
        )

        alerts = AlertService.check_metric(AlertRule.DISK_USAGE, 95.0)
        alert = alerts[0]
        assert alert.alert_rule == rule

        # Resolve the alert
        alert.resolve(self.user, "Cleaned up disk space")

        # Verify resolution
        alert.refresh_from_db()
        assert alert.status == MonitoringAlert.RESOLVED
        assert alert.resolved_by == self.user
        assert alert.resolved_at is not None
        assert "Cleaned up" in alert.resolution_notes

    def test_alert_escalation_workflow(self):
        """
        Test alert escalation for unacknowledged alerts.

        Requirement 7.9: Implement alert escalation.
        """
        # Create rule with escalation
        rule = AlertRule.objects.create(
            name="Test Escalation Alert",
            metric_type=AlertRule.DATABASE_CONNECTIONS,
            operator=AlertRule.GREATER_THAN,
            threshold=80.0,
            severity=AlertRule.CRITICAL,
            is_enabled=True,
            escalate_after_minutes=1,  # Short time for testing
            escalation_email_recipients=f"escalation_{self.user.email}",
            created_by=self.user,
        )

        # Create alert
        alert = MonitoringAlert.objects.create(
            alert_rule=rule,
            message="Database connections exceeded threshold",
            current_value=85.0,
            threshold_value=80.0,
            status=MonitoringAlert.ACTIVE,
        )

        # Backdate the alert to trigger escalation
        alert.created_at = timezone.now() - timezone.timedelta(minutes=2)
        alert.save()

        # Check if alert should escalate
        assert alert.should_escalate() is True

        # Escalate the alert
        AlertService.escalate_alert(alert)

        # Verify escalation
        alert.refresh_from_db()
        assert alert.status == MonitoringAlert.ESCALATED
        assert alert.escalated_at is not None
        assert alert.escalation_sent is True

    def test_cooldown_period_prevents_duplicate_alerts(self):
        """
        Test that cooldown period prevents duplicate alerts.

        Requirement 7.6: Provide alert configuration for CPU, memory, disk space, and other metrics.
        """
        # Create rule with cooldown
        rule = AlertRule.objects.create(
            name="Test Cooldown Alert",
            metric_type=AlertRule.CPU_USAGE,
            operator=AlertRule.GREATER_THAN,
            threshold=75.0,
            severity=AlertRule.WARNING,
            is_enabled=True,
            cooldown_minutes=30,
            created_by=self.user,
        )

        # First alert should be created
        alerts1 = AlertService.check_metric(AlertRule.CPU_USAGE, 80.0)
        assert len(alerts1) == 1
        assert alerts1[0].alert_rule == rule

        # Second alert immediately should be blocked by cooldown
        alerts2 = AlertService.check_metric(AlertRule.CPU_USAGE, 85.0)
        assert len(alerts2) == 0

        # Verify only one alert exists
        total_alerts = MonitoringAlert.objects.filter(alert_rule=rule).count()
        assert total_alerts == 1

    def test_disabled_rule_does_not_trigger_alerts(self):
        """
        Test that disabled rules don't trigger alerts.

        Requirement 7.6: Provide alert configuration for CPU, memory, disk space, and other metrics.
        """
        # Create disabled rule
        rule = AlertRule.objects.create(
            name="Test Disabled Alert",
            metric_type=AlertRule.MEMORY_USAGE,
            operator=AlertRule.GREATER_THAN,
            threshold=70.0,
            severity=AlertRule.WARNING,
            is_enabled=False,  # Disabled
            created_by=self.user,
        )
        assert rule.is_enabled is False

        # Try to trigger alert
        alerts = AlertService.check_metric(AlertRule.MEMORY_USAGE, 80.0)

        # No alerts should be created
        assert len(alerts) == 0

    def test_multiple_alert_rules_for_same_metric(self):
        """
        Test multiple alert rules for the same metric type.

        Requirement 7.6: Provide alert configuration for CPU, memory, disk space, and other metrics.
        """
        # Create multiple rules for CPU
        rule1 = AlertRule.objects.create(
            name="CPU Warning",
            metric_type=AlertRule.CPU_USAGE,
            operator=AlertRule.GREATER_THAN,
            threshold=70.0,
            severity=AlertRule.WARNING,
            is_enabled=True,
            created_by=self.user,
        )

        rule2 = AlertRule.objects.create(
            name="CPU Critical",
            metric_type=AlertRule.CPU_USAGE,
            operator=AlertRule.GREATER_THAN,
            threshold=90.0,
            severity=AlertRule.CRITICAL,
            is_enabled=True,
            created_by=self.user,
        )

        # Trigger with value that exceeds both thresholds
        alerts = AlertService.check_metric(AlertRule.CPU_USAGE, 95.0)

        # Both alerts should be created
        assert len(alerts) == 2

        # Verify both rules triggered
        alert_rules = [alert.alert_rule for alert in alerts]
        assert rule1 in alert_rules
        assert rule2 in alert_rules

    def test_alert_delivery_log_tracking(self):
        """
        Test that alert delivery attempts are logged.

        Requirement 7.7: Deliver alerts via email, SMS, and in-app notifications.
        """
        # Create rule with multiple delivery channels
        rule = AlertRule.objects.create(
            name="Test Multi-Channel Alert",
            metric_type=AlertRule.REDIS_MEMORY,
            operator=AlertRule.GREATER_THAN,
            threshold=80.0,
            severity=AlertRule.WARNING,
            is_enabled=True,
            send_email=True,
            send_sms=True,
            send_slack=True,
            email_recipients=self.user.email,
            sms_recipients="+1234567890",
            slack_channel="#alerts",
            created_by=self.user,
        )

        # Trigger alert
        alerts = AlertService.check_metric(AlertRule.REDIS_MEMORY, 85.0)
        alert = alerts[0]
        assert alert.alert_rule == rule

        # Verify delivery logs were created
        delivery_logs = AlertDeliveryLog.objects.filter(alert=alert)
        assert delivery_logs.count() >= 1  # At least email should be logged

        # Verify email delivery log
        email_log = delivery_logs.filter(channel=AlertDeliveryLog.EMAIL).first()
        assert email_log is not None
        assert email_log.recipient == self.user.email
        assert email_log.status in [AlertDeliveryLog.SENT, AlertDeliveryLog.FAILED]

    def test_alert_with_different_operators(self):
        """
        Test alert rules with different comparison operators.

        Requirement 7.6: Provide alert configuration for CPU, memory, disk space, and other metrics.
        """
        # Test LESS_THAN operator (e.g., low disk space)
        rule_lt = AlertRule.objects.create(
            name="Low Disk Space",
            metric_type=AlertRule.DISK_USAGE,
            operator=AlertRule.LESS_THAN,
            threshold=10.0,
            severity=AlertRule.CRITICAL,
            is_enabled=True,
            created_by=self.user,
        )

        # Should trigger when value is below threshold
        alerts_lt = AlertService.check_metric(AlertRule.DISK_USAGE, 5.0)
        assert len(alerts_lt) == 1
        assert alerts_lt[0].alert_rule == rule_lt

        # Should not trigger when value is above threshold
        alerts_lt2 = AlertService.check_metric(AlertRule.DISK_USAGE, 15.0)
        assert len(alerts_lt2) == 0

    def test_alert_history_tracking(self):
        """
        Test that alert history is properly tracked.

        Requirement 7.8: Log all alerts with timestamps and resolution status.
        """
        # Create rule
        rule = AlertRule.objects.create(
            name="Test History Alert",
            metric_type=AlertRule.CELERY_QUEUE_LENGTH,
            operator=AlertRule.GREATER_THAN,
            threshold=100.0,
            severity=AlertRule.WARNING,
            is_enabled=True,
            created_by=self.user,
        )
        assert rule.is_enabled is True

        # Create multiple alerts over time
        alert1 = MonitoringAlert.objects.create(
            alert_rule=rule,
            message="Queue length exceeded",
            current_value=150.0,
            threshold_value=100.0,
            status=MonitoringAlert.ACTIVE,
        )

        alert2 = MonitoringAlert.objects.create(
            alert_rule=rule,
            message="Queue length exceeded again",
            current_value=200.0,
            threshold_value=100.0,
            status=MonitoringAlert.ACTIVE,
        )

        # Acknowledge first alert
        alert1.acknowledge(self.user, "Working on it")

        # Resolve second alert
        alert2.resolve(self.user, "Queue cleared")

        # Verify history
        all_alerts = MonitoringAlert.objects.filter(alert_rule=rule).order_by("created_at")
        assert all_alerts.count() == 2

        # Verify statuses
        assert all_alerts[0].status == MonitoringAlert.ACKNOWLEDGED
        assert all_alerts[1].status == MonitoringAlert.RESOLVED

        # Verify timestamps
        assert all_alerts[0].acknowledged_at is not None
        assert all_alerts[1].resolved_at is not None
