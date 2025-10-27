"""
Monitoring alert models for system health monitoring.

This module provides alert configuration and management for:
- System metrics (CPU, memory, disk)
- Service health (PostgreSQL, Redis, Celery)
- Custom alert rules and thresholds
- Alert delivery (email, SMS, Slack)
- Alert history and acknowledgment
- Alert escalation

Per Requirements 7 - System Monitoring and Health Dashboard
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class AlertRule(models.Model):
    """
    Define alert rules and thresholds for monitoring.

    Requirement 7.5: Send alerts when system metrics exceed defined thresholds.
    Requirement 7.6: Provide alert configuration for CPU, memory, disk space, and other metrics.
    """

    # Metric type choices
    CPU_USAGE = "CPU_USAGE"
    MEMORY_USAGE = "MEMORY_USAGE"
    DISK_USAGE = "DISK_USAGE"
    DATABASE_CONNECTIONS = "DATABASE_CONNECTIONS"
    REDIS_MEMORY = "REDIS_MEMORY"
    CELERY_QUEUE_LENGTH = "CELERY_QUEUE_LENGTH"
    SERVICE_DOWN = "SERVICE_DOWN"
    SLOW_QUERY = "SLOW_QUERY"
    ERROR_RATE = "ERROR_RATE"
    CUSTOM = "CUSTOM"

    METRIC_TYPE_CHOICES = [
        (CPU_USAGE, "CPU Usage"),
        (MEMORY_USAGE, "Memory Usage"),
        (DISK_USAGE, "Disk Usage"),
        (DATABASE_CONNECTIONS, "Database Connections"),
        (REDIS_MEMORY, "Redis Memory"),
        (CELERY_QUEUE_LENGTH, "Celery Queue Length"),
        (SERVICE_DOWN, "Service Down"),
        (SLOW_QUERY, "Slow Query"),
        (ERROR_RATE, "Error Rate"),
        (CUSTOM, "Custom Metric"),
    ]

    # Comparison operators
    GREATER_THAN = "GT"
    LESS_THAN = "LT"
    EQUALS = "EQ"
    NOT_EQUALS = "NE"

    OPERATOR_CHOICES = [
        (GREATER_THAN, "Greater Than"),
        (LESS_THAN, "Less Than"),
        (EQUALS, "Equals"),
        (NOT_EQUALS, "Not Equals"),
    ]

    # Severity levels
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    SEVERITY_CHOICES = [
        (INFO, "Info"),
        (WARNING, "Warning"),
        (ERROR, "Error"),
        (CRITICAL, "Critical"),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the alert rule",
    )

    # Rule configuration
    name = models.CharField(
        max_length=255,
        help_text="Name of the alert rule",
    )

    description = models.TextField(
        blank=True,
        help_text="Description of what this alert monitors",
    )

    metric_type = models.CharField(
        max_length=50,
        choices=METRIC_TYPE_CHOICES,
        help_text="Type of metric to monitor",
    )

    operator = models.CharField(
        max_length=10,
        choices=OPERATOR_CHOICES,
        default=GREATER_THAN,
        help_text="Comparison operator",
    )

    threshold = models.FloatField(
        help_text="Threshold value to trigger alert",
    )

    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default=WARNING,
        help_text="Severity level of the alert",
    )

    # Alert behavior
    is_enabled = models.BooleanField(
        default=True,
        help_text="Whether this alert rule is active",
    )

    check_interval_minutes = models.IntegerField(
        default=5,
        help_text="How often to check this metric (in minutes)",
    )

    cooldown_minutes = models.IntegerField(
        default=30,
        help_text="Minimum time between alerts for the same rule (in minutes)",
    )

    # Delivery channels
    send_email = models.BooleanField(
        default=True,
        help_text="Send alert via email",
    )

    send_sms = models.BooleanField(
        default=False,
        help_text="Send alert via SMS",
    )

    send_slack = models.BooleanField(
        default=False,
        help_text="Send alert to Slack",
    )

    # Recipients
    email_recipients = models.TextField(
        blank=True,
        help_text="Comma-separated list of email addresses",
    )

    sms_recipients = models.TextField(
        blank=True,
        help_text="Comma-separated list of phone numbers",
    )

    slack_channel = models.CharField(
        max_length=255,
        blank=True,
        help_text="Slack channel to send alerts to (e.g., #alerts)",
    )

    # Escalation
    escalate_after_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Escalate if not acknowledged within this time (minutes)",
    )

    escalation_email_recipients = models.TextField(
        blank=True,
        help_text="Comma-separated list of escalation email addresses",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_alert_rules",
    )

    class Meta:
        db_table = "monitoring_alert_rules"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["metric_type", "is_enabled"]),
            models.Index(fields=["severity"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_metric_type_display()})"

    def get_email_recipients_list(self):
        """Get list of email recipients."""
        if not self.email_recipients:
            return []
        return [email.strip() for email in self.email_recipients.split(",") if email.strip()]

    def get_sms_recipients_list(self):
        """Get list of SMS recipients."""
        if not self.sms_recipients:
            return []
        return [phone.strip() for phone in self.sms_recipients.split(",") if phone.strip()]

    def get_escalation_email_recipients_list(self):
        """Get list of escalation email recipients."""
        if not self.escalation_email_recipients:
            return []
        return [
            email.strip() for email in self.escalation_email_recipients.split(",") if email.strip()
        ]

    def should_trigger(self, current_value):
        """Check if alert should trigger based on current value."""
        if self.operator == self.GREATER_THAN:
            return current_value > self.threshold
        elif self.operator == self.LESS_THAN:
            return current_value < self.threshold
        elif self.operator == self.EQUALS:
            return current_value == self.threshold
        elif self.operator == self.NOT_EQUALS:
            return current_value != self.threshold
        return False

    def can_send_alert(self):
        """Check if enough time has passed since last alert (cooldown)."""
        if not self.cooldown_minutes:
            return True

        last_alert = (
            MonitoringAlert.objects.filter(alert_rule=self, status=MonitoringAlert.ACTIVE)
            .order_by("-created_at")
            .first()
        )

        if not last_alert:
            return True

        cooldown_period = timezone.timedelta(minutes=self.cooldown_minutes)
        return timezone.now() - last_alert.created_at >= cooldown_period


class MonitoringAlert(models.Model):
    """
    Track monitoring alerts triggered by alert rules.

    Requirement 7.7: Deliver alerts via email, SMS, and in-app notifications.
    Requirement 7.8: Log all alerts with timestamps and resolution status.
    """

    # Status choices
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"

    STATUS_CHOICES = [
        (ACTIVE, "Active"),
        (ACKNOWLEDGED, "Acknowledged"),
        (RESOLVED, "Resolved"),
        (ESCALATED, "Escalated"),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the alert",
    )

    # Alert metadata
    alert_rule = models.ForeignKey(
        AlertRule,
        on_delete=models.CASCADE,
        related_name="alerts",
        help_text="Alert rule that triggered this alert",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=ACTIVE,
        help_text="Current status of the alert",
    )

    # Alert details
    message = models.TextField(
        help_text="Alert message",
    )

    current_value = models.FloatField(
        help_text="Current value of the metric that triggered the alert",
    )

    threshold_value = models.FloatField(
        help_text="Threshold value that was exceeded",
    )

    # Delivery tracking
    email_sent = models.BooleanField(
        default=False,
        help_text="Whether email notification was sent",
    )

    sms_sent = models.BooleanField(
        default=False,
        help_text="Whether SMS notification was sent",
    )

    slack_sent = models.BooleanField(
        default=False,
        help_text="Whether Slack notification was sent",
    )

    email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When email was sent",
    )

    sms_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When SMS was sent",
    )

    slack_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When Slack message was sent",
    )

    # Acknowledgment
    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the alert was acknowledged",
    )

    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acknowledged_monitoring_alerts",
        help_text="User who acknowledged the alert",
    )

    acknowledgment_notes = models.TextField(
        blank=True,
        help_text="Notes added when acknowledging the alert",
    )

    # Resolution
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the alert was resolved",
    )

    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_monitoring_alerts",
        help_text="User who resolved the alert",
    )

    resolution_notes = models.TextField(
        blank=True,
        help_text="Notes added when resolving the alert",
    )

    # Escalation
    escalated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the alert was escalated",
    )

    escalation_sent = models.BooleanField(
        default=False,
        help_text="Whether escalation notification was sent",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "monitoring_alerts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["alert_rule", "status"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.alert_rule.name} - {self.status} ({self.created_at})"

    def acknowledge(self, user, notes=""):
        """Acknowledge the alert."""
        self.status = self.ACKNOWLEDGED
        self.acknowledged_at = timezone.now()
        self.acknowledged_by = user
        self.acknowledgment_notes = notes
        self.save()

    def resolve(self, user, notes=""):
        """Resolve the alert."""
        self.status = self.RESOLVED
        self.resolved_at = timezone.now()
        self.resolved_by = user
        self.resolution_notes = notes
        self.save()

    def escalate(self):
        """Escalate the alert."""
        self.status = self.ESCALATED
        self.escalated_at = timezone.now()
        self.save()

    def should_escalate(self):
        """Check if alert should be escalated."""
        if self.status != self.ACTIVE:
            return False

        if not self.alert_rule.escalate_after_minutes:
            return False

        if self.escalated_at:
            return False

        escalation_time = timezone.timedelta(minutes=self.alert_rule.escalate_after_minutes)
        return timezone.now() - self.created_at >= escalation_time


class AlertDeliveryLog(models.Model):
    """
    Track alert delivery attempts and results.

    Logs all delivery attempts for auditing and troubleshooting.
    """

    # Delivery channel choices
    EMAIL = "EMAIL"
    SMS = "SMS"
    SLACK = "SLACK"

    CHANNEL_CHOICES = [
        (EMAIL, "Email"),
        (SMS, "SMS"),
        (SLACK, "Slack"),
    ]

    # Status choices
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (SENT, "Sent"),
        (FAILED, "Failed"),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Alert reference
    alert = models.ForeignKey(
        MonitoringAlert,
        on_delete=models.CASCADE,
        related_name="delivery_logs",
    )

    # Delivery details
    channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES,
    )

    recipient = models.CharField(
        max_length=255,
        help_text="Email address, phone number, or Slack channel",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PENDING,
    )

    # Result tracking
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    error_message = models.TextField(
        blank=True,
        help_text="Error message if delivery failed",
    )

    retry_count = models.IntegerField(
        default=0,
        help_text="Number of delivery attempts",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "monitoring_alert_delivery_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["alert", "channel"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.get_channel_display()} to {self.recipient} - {self.status}"
