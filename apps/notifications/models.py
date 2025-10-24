from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class Notification(models.Model):
    """
    Model to store notifications for users.
    Supports in-app notifications with read/unread status.
    """

    NOTIFICATION_TYPES = [
        ("INFO", _("Information")),
        ("SUCCESS", _("Success")),
        ("WARNING", _("Warning")),
        ("ERROR", _("Error")),
        ("LOW_STOCK", _("Low Stock Alert")),
        ("PAYMENT_REMINDER", _("Payment Reminder")),
        ("ORDER_STATUS", _("Order Status Update")),
        ("SYSTEM", _("System Notification")),
        ("PROMOTION", _("Promotion")),
        ("APPOINTMENT", _("Appointment Reminder")),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
        help_text=_("User who will receive this notification"),
    )
    title = models.CharField(max_length=255, help_text=_("Notification title/subject"))
    message = models.TextField(help_text=_("Notification message content"))
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        default="INFO",
        help_text=_("Type of notification for styling and filtering"),
    )
    is_read = models.BooleanField(
        default=False, help_text=_("Whether the user has read this notification")
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text=_("When the notification was created")
    )
    read_at = models.DateTimeField(
        null=True, blank=True, help_text=_("When the notification was marked as read")
    )

    # Optional fields for enhanced functionality
    action_url = models.URLField(
        null=True, blank=True, help_text=_("URL to navigate to when notification is clicked")
    )
    action_text = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text=_('Text for action button (e.g., "View Order", "Update Inventory")'),
    )
    expires_at = models.DateTimeField(
        null=True, blank=True, help_text=_("When this notification expires and should be hidden")
    )

    class Meta:
        db_table = "notifications_notification"
        ordering = ["-created_at"]
        indexes = [
            # Index for efficient querying of user's notifications
            models.Index(fields=["user", "-created_at"], name="notif_user_created_idx"),
            # Index for unread notifications
            models.Index(fields=["user", "is_read", "-created_at"], name="notif_user_read_idx"),
            # Index for notification type filtering
            models.Index(
                fields=["user", "notification_type", "-created_at"], name="notif_user_type_idx"
            ),
            # Index for expired notifications cleanup
            models.Index(fields=["expires_at"], name="notif_expires_idx"),
        ]
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")

    def __str__(self):
        return f"{self.title} - {self.user.username}"

    def mark_as_read(self):
        """Mark notification as read and set read timestamp"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])

    def is_expired(self):
        """Check if notification has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False


class NotificationPreference(models.Model):
    """
    Model to store user preferences for different types of notifications.
    Allows users to control which notifications they receive and through which channels.
    """

    CHANNEL_CHOICES = [
        ("IN_APP", _("In-App Notification")),
        ("EMAIL", _("Email")),
        ("SMS", _("SMS")),
        ("PUSH", _("Push Notification")),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
        help_text=_("User these preferences belong to"),
    )
    notification_type = models.CharField(
        max_length=20,
        choices=Notification.NOTIFICATION_TYPES,
        help_text=_("Type of notification this preference applies to"),
    )
    channel = models.CharField(
        max_length=10, choices=CHANNEL_CHOICES, help_text=_("Notification delivery channel")
    )
    is_enabled = models.BooleanField(
        default=True, help_text=_("Whether this notification type is enabled for this channel")
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text=_("When this preference was created")
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text=_("When this preference was last updated")
    )

    # Time-based preferences
    quiet_hours_start = models.TimeField(
        null=True, blank=True, help_text=_("Start of quiet hours (no notifications sent)")
    )
    quiet_hours_end = models.TimeField(null=True, blank=True, help_text=_("End of quiet hours"))

    class Meta:
        db_table = "notifications_preference"
        unique_together = [["user", "notification_type", "channel"]]
        indexes = [
            # Index for efficient lookup of user preferences
            models.Index(fields=["user", "notification_type"], name="notif_pref_user_type_idx"),
            # Index for enabled preferences
            models.Index(fields=["user", "is_enabled"], name="notif_pref_user_enabled_idx"),
        ]
        verbose_name = _("Notification Preference")
        verbose_name_plural = _("Notification Preferences")

    def __str__(self):
        return f"{self.user.username} - {self.notification_type} via {self.channel}"

    def is_in_quiet_hours(self):
        """Check if current time is within user's quiet hours"""
        if not (self.quiet_hours_start and self.quiet_hours_end):
            return False

        from django.utils import timezone

        current_time = timezone.now().time()

        # Handle quiet hours that span midnight
        if self.quiet_hours_start <= self.quiet_hours_end:
            return self.quiet_hours_start <= current_time <= self.quiet_hours_end
        else:
            return current_time >= self.quiet_hours_start or current_time <= self.quiet_hours_end


class NotificationTemplate(models.Model):
    """
    Model to store reusable notification templates.
    Allows for consistent messaging and easy template management.
    """

    name = models.CharField(
        max_length=100, unique=True, help_text=_("Unique name for this template")
    )
    notification_type = models.CharField(
        max_length=20,
        choices=Notification.NOTIFICATION_TYPES,
        help_text=_("Type of notification this template is for"),
    )
    title_template = models.CharField(
        max_length=255,
        help_text=_("Template for notification title (supports Django template syntax)"),
    )
    message_template = models.TextField(
        help_text=_("Template for notification message (supports Django template syntax)")
    )
    action_text_template = models.CharField(
        max_length=100, null=True, blank=True, help_text=_("Template for action button text")
    )
    action_url_template = models.CharField(
        max_length=500, null=True, blank=True, help_text=_("Template for action URL")
    )
    is_active = models.BooleanField(
        default=True, help_text=_("Whether this template is active and can be used")
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text=_("When this template was created")
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text=_("When this template was last updated")
    )

    class Meta:
        db_table = "notifications_template"
        indexes = [
            # Index for active templates by type
            models.Index(
                fields=["notification_type", "is_active"], name="notif_template_type_active_idx"
            ),
        ]
        verbose_name = _("Notification Template")
        verbose_name_plural = _("Notification Templates")

    def __str__(self):
        return f"{self.name} ({self.notification_type})"

    def render(self, context):
        """
        Render the template with given context.
        Returns a dictionary with rendered title, message, action_text, and action_url.
        """
        from django.template import Context, Template

        title_template = Template(self.title_template)
        message_template = Template(self.message_template)

        rendered = {
            "title": title_template.render(Context(context)),
            "message": message_template.render(Context(context)),
        }

        if self.action_text_template:
            action_text_template = Template(self.action_text_template)
            rendered["action_text"] = action_text_template.render(Context(context))

        if self.action_url_template:
            action_url_template = Template(self.action_url_template)
            rendered["action_url"] = action_url_template.render(Context(context))

        return rendered
