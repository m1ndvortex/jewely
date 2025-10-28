"""
Platform announcement models for communication system.

This module provides announcement and communication management for:
- Platform-wide announcements (maintenance, new features, policy changes)
- Scheduled announcements for future delivery
- Tenant segmentation and targeting
- Multi-channel delivery (in-app, email, SMS)
- Read/unread tracking
- Critical announcement acknowledgment
- Direct messaging to specific tenants
- Communication templates
- Communication history logging

Per Requirement 31 - Communication and Announcement System
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Announcement(models.Model):
    """
    Platform-wide announcements from administrators to tenants.

    Requirement 31.1: Allow administrators to create platform-wide announcements.
    Requirement 31.2: Allow administrators to schedule announcements for future delivery.
    Requirement 31.3: Allow administrators to target specific tenant segments.
    Requirement 31.4: Deliver announcements via in-app banner, email, SMS, or all channels.
    """

    # Severity levels
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    MAINTENANCE = "MAINTENANCE"

    SEVERITY_CHOICES = [
        (INFO, "Info"),
        (WARNING, "Warning"),
        (CRITICAL, "Critical"),
        (MAINTENANCE, "Maintenance"),
    ]

    # Status choices
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    SENT = "SENT"
    CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (SCHEDULED, "Scheduled"),
        (SENT, "Sent"),
        (CANCELLED, "Cancelled"),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the announcement",
    )

    # Announcement content
    title = models.CharField(
        max_length=255,
        help_text="Title of the announcement",
    )

    message = models.TextField(
        help_text="Full message content of the announcement",
    )

    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default=INFO,
        help_text="Severity level of the announcement",
    )

    # Targeting
    target_filter = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON filter for targeting specific tenants (by plan, region, status)",
    )

    target_all_tenants = models.BooleanField(
        default=True,
        help_text="Whether to send to all tenants (ignores target_filter if True)",
    )

    # Delivery channels
    channels = models.JSONField(
        default=list,
        help_text="List of delivery channels: ['in_app', 'email', 'sms']",
    )

    # Scheduling
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When to send the announcement (null for immediate)",
    )

    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the announcement was actually sent",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=DRAFT,
        help_text="Current status of the announcement",
    )

    # Acknowledgment requirement
    requires_acknowledgment = models.BooleanField(
        default=False,
        help_text="Whether tenants must acknowledge this announcement",
    )

    # Display settings
    is_dismissible = models.BooleanField(
        default=True,
        help_text="Whether the in-app banner can be dismissed",
    )

    display_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When to stop displaying the in-app banner (null for indefinite)",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_announcements",
        help_text="Administrator who created the announcement",
    )

    class Meta:
        db_table = "announcements"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["severity"]),
            models.Index(fields=["scheduled_at"]),
            models.Index(fields=["sent_at"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_severity_display()})"

    def is_active(self):
        """Check if announcement should be displayed."""
        if self.status != self.SENT:
            return False

        if self.display_until and timezone.now() > self.display_until:
            return False

        return True

    def should_send(self):
        """Check if announcement should be sent now."""
        if self.status != self.SCHEDULED:
            return False

        if not self.scheduled_at:
            return False

        return timezone.now() >= self.scheduled_at

    def mark_as_sent(self):
        """Mark announcement as sent."""
        self.status = self.SENT
        self.sent_at = timezone.now()
        self.save()

    def cancel(self):
        """Cancel a scheduled announcement."""
        if self.status == self.SCHEDULED:
            self.status = self.CANCELLED
            self.save()

    def get_target_tenants(self):
        """
        Get list of tenants that match the target filter.

        Returns QuerySet of Tenant objects.
        """
        from apps.core.models import Tenant

        if self.target_all_tenants:
            return Tenant.objects.filter(status=Tenant.ACTIVE)

        # Apply filters from target_filter JSON
        # Start with all tenants if status filter is specified, otherwise only active
        if "statuses" in self.target_filter and self.target_filter["statuses"]:
            queryset = Tenant.objects.filter(status__in=self.target_filter["statuses"])
        else:
            queryset = Tenant.objects.filter(status=Tenant.ACTIVE)

        if not self.target_filter:
            return queryset

        # Filter by subscription plan
        if "plans" in self.target_filter and self.target_filter["plans"]:
            queryset = queryset.filter(subscription__plan__name__in=self.target_filter["plans"])

        # Filter by region (if region field exists)
        if "regions" in self.target_filter and self.target_filter["regions"]:
            queryset = queryset.filter(region__in=self.target_filter["regions"])

        return queryset


class AnnouncementRead(models.Model):
    """
    Track which tenants have seen/read announcements.

    Requirement 31.6: Track which tenants have seen announcements with read and unread status.
    Requirement 31.7: Require tenant acknowledgment for critical announcements.
    """

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # References
    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        related_name="reads",
        help_text="The announcement that was read",
    )

    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        related_name="announcement_reads",
        help_text="The tenant who read the announcement",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="announcement_reads",
        help_text="The specific user who read the announcement",
    )

    # Read tracking
    read_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the announcement was first read",
    )

    # Acknowledgment tracking
    acknowledged = models.BooleanField(
        default=False,
        help_text="Whether the announcement has been acknowledged",
    )

    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the announcement was acknowledged",
    )

    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acknowledged_announcements",
        help_text="User who acknowledged the announcement",
    )

    # Dismissal tracking
    dismissed = models.BooleanField(
        default=False,
        help_text="Whether the user dismissed the banner",
    )

    dismissed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the banner was dismissed",
    )

    class Meta:
        db_table = "announcement_reads"
        ordering = ["-read_at"]
        unique_together = [["announcement", "tenant"]]
        indexes = [
            models.Index(fields=["announcement", "tenant"]),
            models.Index(fields=["tenant", "acknowledged"]),
            models.Index(fields=["read_at"]),
        ]

    def __str__(self):
        return f"{self.tenant} read {self.announcement.title}"

    def acknowledge(self, user):
        """Acknowledge the announcement."""
        self.acknowledged = True
        self.acknowledged_at = timezone.now()
        self.acknowledged_by = user
        self.save()

    def dismiss(self):
        """Dismiss the announcement banner."""
        self.dismissed = True
        self.dismissed_at = timezone.now()
        self.save()


class DirectMessage(models.Model):
    """
    Direct messages from administrators to specific tenants.

    Requirement 31.8: Allow administrators to send direct messages to specific tenants.
    Requirement 31.10: Log all platform-to-tenant communications.
    """

    # Status choices
    DRAFT = "DRAFT"
    SENT = "SENT"
    FAILED = "FAILED"

    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (SENT, "Sent"),
        (FAILED, "Failed"),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Recipients
    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        related_name="direct_messages",
        help_text="The tenant receiving the message",
    )

    # Message content
    subject = models.CharField(
        max_length=255,
        help_text="Subject line of the message",
    )

    message = models.TextField(
        help_text="Full message content",
    )

    # Delivery channels
    channels = models.JSONField(
        default=list,
        help_text="List of delivery channels: ['email', 'sms', 'in_app']",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=DRAFT,
    )

    # Delivery tracking
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the message was sent",
    )

    email_sent = models.BooleanField(
        default=False,
        help_text="Whether email was sent successfully",
    )

    sms_sent = models.BooleanField(
        default=False,
        help_text="Whether SMS was sent successfully",
    )

    in_app_sent = models.BooleanField(
        default=False,
        help_text="Whether in-app notification was created",
    )

    # Read tracking
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the message was first read",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_direct_messages",
        help_text="Administrator who sent the message",
    )

    class Meta:
        db_table = "direct_messages"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "-created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["sent_at"]),
        ]

    def __str__(self):
        return f"Message to {self.tenant}: {self.subject}"

    def mark_as_sent(self):
        """Mark message as sent."""
        self.status = self.SENT
        self.sent_at = timezone.now()
        self.save()

    def mark_as_read(self):
        """Mark message as read."""
        if not self.read_at:
            self.read_at = timezone.now()
            self.save()


class CommunicationTemplate(models.Model):
    """
    Reusable templates for common communications.

    Requirement 31.9: Provide communication templates for common messages.
    """

    # Template types
    MAINTENANCE = "MAINTENANCE"
    NEW_FEATURE = "NEW_FEATURE"
    POLICY_CHANGE = "POLICY_CHANGE"
    BILLING = "BILLING"
    SUPPORT = "SUPPORT"
    CUSTOM = "CUSTOM"

    TEMPLATE_TYPE_CHOICES = [
        (MAINTENANCE, "Maintenance Notice"),
        (NEW_FEATURE, "New Feature Announcement"),
        (POLICY_CHANGE, "Policy Change"),
        (BILLING, "Billing Notice"),
        (SUPPORT, "Support Message"),
        (CUSTOM, "Custom Template"),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Template details
    name = models.CharField(
        max_length=255,
        help_text="Name of the template",
    )

    template_type = models.CharField(
        max_length=50,
        choices=TEMPLATE_TYPE_CHOICES,
        help_text="Type of communication template",
    )

    subject = models.CharField(
        max_length=255,
        help_text="Subject line template (supports variables)",
    )

    message = models.TextField(
        help_text="Message template (supports variables like {{tenant_name}}, {{date}})",
    )

    # Default settings
    default_severity = models.CharField(
        max_length=20,
        choices=Announcement.SEVERITY_CHOICES,
        default=Announcement.INFO,
        help_text="Default severity for announcements using this template",
    )

    default_channels = models.JSONField(
        default=list,
        help_text="Default delivery channels",
    )

    # Usage tracking
    usage_count = models.IntegerField(
        default=0,
        help_text="Number of times this template has been used",
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this template is available for use",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_communication_templates",
    )

    class Meta:
        db_table = "communication_templates"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["template_type", "is_active"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"

    def render(self, context):
        """
        Render the template with provided context variables.

        Args:
            context: Dictionary of variables to replace in template

        Returns:
            Tuple of (subject, message) with variables replaced
        """
        subject = self.subject
        message = self.message

        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            subject = subject.replace(placeholder, str(value))
            message = message.replace(placeholder, str(value))

        return subject, message

    def increment_usage(self):
        """Increment the usage counter."""
        self.usage_count += 1
        self.save(update_fields=["usage_count"])


class CommunicationLog(models.Model):
    """
    Comprehensive log of all platform-to-tenant communications.

    Requirement 31.10: Log all platform-to-tenant communications.
    """

    # Communication types
    ANNOUNCEMENT = "ANNOUNCEMENT"
    DIRECT_MESSAGE = "DIRECT_MESSAGE"
    SYSTEM_NOTIFICATION = "SYSTEM_NOTIFICATION"

    COMMUNICATION_TYPE_CHOICES = [
        (ANNOUNCEMENT, "Announcement"),
        (DIRECT_MESSAGE, "Direct Message"),
        (SYSTEM_NOTIFICATION, "System Notification"),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Communication details
    communication_type = models.CharField(
        max_length=50,
        choices=COMMUNICATION_TYPE_CHOICES,
        help_text="Type of communication",
    )

    # References (nullable to support different types)
    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communication_logs",
    )

    direct_message = models.ForeignKey(
        DirectMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communication_logs",
    )

    # Recipient
    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        related_name="communication_logs",
        help_text="Tenant who received the communication",
    )

    # Content snapshot (for historical record)
    subject = models.CharField(
        max_length=255,
        help_text="Subject/title of the communication",
    )

    message_preview = models.TextField(
        help_text="Preview of the message content",
    )

    # Delivery details
    channels_used = models.JSONField(
        default=list,
        help_text="Channels used for delivery",
    )

    delivery_status = models.JSONField(
        default=dict,
        help_text="Status of delivery for each channel",
    )

    # Metadata
    sent_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the communication was sent",
    )

    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_communications",
        help_text="Administrator who sent the communication",
    )

    class Meta:
        db_table = "communication_logs"
        ordering = ["-sent_at"]
        indexes = [
            models.Index(fields=["tenant", "-sent_at"]),
            models.Index(fields=["communication_type", "-sent_at"]),
            models.Index(fields=["sent_at"]),
        ]

    def __str__(self):
        return f"{self.get_communication_type_display()} to {self.tenant}: {self.subject}"
