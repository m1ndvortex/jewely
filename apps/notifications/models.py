import uuid

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
        ("TRANSACTIONAL", _("Transactional Email")),
        ("MARKETING", _("Marketing Email")),
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


class EmailNotification(models.Model):
    """
    Model to track email notifications and their delivery status.
    """

    STATUS_CHOICES = [
        ("PENDING", _("Pending")),
        ("SENT", _("Sent")),
        ("DELIVERED", _("Delivered")),
        ("BOUNCED", _("Bounced")),
        ("FAILED", _("Failed")),
        ("OPENED", _("Opened")),
        ("CLICKED", _("Clicked")),
        ("COMPLAINED", _("Complained")),
        ("UNSUBSCRIBED", _("Unsubscribed")),
    ]

    EMAIL_TYPES = [
        ("TRANSACTIONAL", _("Transactional")),
        ("MARKETING", _("Marketing")),
        ("SYSTEM", _("System")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="email_notifications",
        help_text=_("User who received this email"),
    )
    notification = models.OneToOneField(
        "Notification",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="email_notification",
        help_text=_("Associated in-app notification"),
    )

    # Email details
    subject = models.CharField(max_length=255, help_text=_("Email subject"))
    to_email = models.EmailField(help_text=_("Recipient email address"))
    from_email = models.EmailField(help_text=_("Sender email address"))
    template_name = models.CharField(
        max_length=100, null=True, blank=True, help_text=_("Email template used")
    )
    email_type = models.CharField(
        max_length=20, choices=EMAIL_TYPES, default="TRANSACTIONAL", help_text=_("Type of email")
    )

    # Delivery tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
        help_text=_("Current delivery status"),
    )
    message_id = models.CharField(
        max_length=255, null=True, blank=True, help_text=_("Email service provider message ID")
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    bounced_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)

    # Error tracking
    error_message = models.TextField(
        null=True, blank=True, help_text=_("Error message if delivery failed")
    )
    bounce_reason = models.CharField(
        max_length=255, null=True, blank=True, help_text=_("Reason for bounce if applicable")
    )

    # Scheduling
    scheduled_at = models.DateTimeField(
        null=True, blank=True, help_text=_("When to send this email (for scheduled emails)")
    )

    # Campaign tracking
    campaign_id = models.CharField(
        max_length=100, null=True, blank=True, help_text=_("Campaign ID for marketing emails")
    )

    class Meta:
        db_table = "notifications_email"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="email_user_created_idx"),
            models.Index(fields=["status"], name="email_status_idx"),
            models.Index(fields=["scheduled_at"], name="email_scheduled_idx"),
            models.Index(fields=["campaign_id"], name="email_campaign_idx"),
            models.Index(fields=["message_id"], name="email_message_id_idx"),
        ]
        verbose_name = _("Email Notification")
        verbose_name_plural = _("Email Notifications")

    def __str__(self):
        return f"{self.subject} - {self.to_email} ({self.status})"

    def update_status(self, status, timestamp=None, error_message=None, bounce_reason=None):
        """Update email status with appropriate timestamp"""
        from django.utils import timezone

        if timestamp is None:
            timestamp = timezone.now()

        self.status = status

        if status == "SENT":
            self.sent_at = timestamp
        elif status == "DELIVERED":
            self.delivered_at = timestamp
        elif status == "OPENED":
            self.opened_at = timestamp
        elif status == "CLICKED":
            self.clicked_at = timestamp
        elif status == "BOUNCED":
            self.bounced_at = timestamp
            self.bounce_reason = bounce_reason
        elif status == "FAILED":
            self.failed_at = timestamp
            self.error_message = error_message

        self.save()


class EmailTemplate(models.Model):
    """
    Model to store email templates for different types of notifications.
    """

    name = models.CharField(
        max_length=100, unique=True, help_text=_("Unique name for this email template")
    )
    subject_template = models.CharField(
        max_length=255, help_text=_("Template for email subject (supports Django template syntax)")
    )
    html_template = models.TextField(help_text=_("HTML template for email body"))
    text_template = models.TextField(
        null=True, blank=True, help_text=_("Plain text template for email body (optional)")
    )
    email_type = models.CharField(
        max_length=20,
        choices=EmailNotification.EMAIL_TYPES,
        default="TRANSACTIONAL",
        help_text=_("Type of email this template is for"),
    )
    is_active = models.BooleanField(
        default=True, help_text=_("Whether this template is active and can be used")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notifications_email_template"
        indexes = [
            models.Index(fields=["email_type", "is_active"], name="email_template_type_active_idx"),
        ]
        verbose_name = _("Email Template")
        verbose_name_plural = _("Email Templates")

    def __str__(self):
        return f"{self.name} ({self.email_type})"

    def render(self, context):
        """
        Render the email template with given context.
        Returns a dictionary with rendered subject, html_body, and text_body.
        """
        from django.template import Context, Template

        subject_template = Template(self.subject_template)
        html_template = Template(self.html_template)

        rendered = {
            "subject": subject_template.render(Context(context)),
            "html_body": html_template.render(Context(context)),
        }

        if self.text_template:
            text_template = Template(self.text_template)
            rendered["text_body"] = text_template.render(Context(context))

        return rendered


class SMSNotification(models.Model):
    """
    Model to track SMS notifications and their delivery status.
    """

    STATUS_CHOICES = [
        ("PENDING", _("Pending")),
        ("QUEUED", _("Queued")),
        ("SENT", _("Sent")),
        ("DELIVERED", _("Delivered")),
        ("FAILED", _("Failed")),
        ("UNDELIVERED", _("Undelivered")),
    ]

    SMS_TYPES = [
        ("TRANSACTIONAL", _("Transactional")),
        ("MARKETING", _("Marketing")),
        ("SYSTEM", _("System")),
        ("ALERT", _("Alert")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sms_notifications",
        help_text=_("User who received this SMS"),
    )
    notification = models.OneToOneField(
        "Notification",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sms_notification",
        help_text=_("Associated in-app notification"),
    )

    # SMS details
    message = models.TextField(max_length=1600, help_text=_("SMS message content"))
    to_phone = models.CharField(max_length=20, help_text=_("Recipient phone number"))
    from_phone = models.CharField(
        max_length=20, null=True, blank=True, help_text=_("Sender phone number")
    )
    template_name = models.CharField(
        max_length=100, null=True, blank=True, help_text=_("SMS template used")
    )
    sms_type = models.CharField(
        max_length=20, choices=SMS_TYPES, default="TRANSACTIONAL", help_text=_("Type of SMS")
    )

    # Delivery tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
        help_text=_("Current delivery status"),
    )
    message_sid = models.CharField(
        max_length=255, null=True, blank=True, help_text=_("Twilio message SID")
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)

    # Error tracking
    error_message = models.TextField(
        null=True, blank=True, help_text=_("Error message if delivery failed")
    )
    error_code = models.CharField(
        max_length=10, null=True, blank=True, help_text=_("Twilio error code if applicable")
    )

    # Scheduling
    scheduled_at = models.DateTimeField(
        null=True, blank=True, help_text=_("When to send this SMS (for scheduled SMS)")
    )

    # Campaign tracking
    campaign_id = models.CharField(
        max_length=100, null=True, blank=True, help_text=_("Campaign ID for marketing SMS")
    )

    # Cost tracking
    price = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text=_("Cost of sending this SMS"),
    )
    price_unit = models.CharField(
        max_length=10, null=True, blank=True, help_text=_("Currency unit for price")
    )

    class Meta:
        db_table = "notifications_sms"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="sms_user_created_idx"),
            models.Index(fields=["status"], name="sms_status_idx"),
            models.Index(fields=["scheduled_at"], name="sms_scheduled_idx"),
            models.Index(fields=["campaign_id"], name="sms_campaign_idx"),
            models.Index(fields=["message_sid"], name="sms_message_sid_idx"),
        ]
        verbose_name = _("SMS Notification")
        verbose_name_plural = _("SMS Notifications")

    def __str__(self):
        return f"SMS to {self.to_phone} ({self.status})"

    def update_status(self, status, timestamp=None, error_message=None, error_code=None, price=None, price_unit=None):
        """Update SMS status with appropriate timestamp"""
        from django.utils import timezone

        if timestamp is None:
            timestamp = timezone.now()

        self.status = status

        if status == "SENT":
            self.sent_at = timestamp
        elif status == "DELIVERED":
            self.delivered_at = timestamp
        elif status == "FAILED" or status == "UNDELIVERED":
            self.failed_at = timestamp
            self.error_message = error_message
            self.error_code = error_code

        if price is not None:
            self.price = price
            self.price_unit = price_unit

        self.save()


class SMSTemplate(models.Model):
    """
    Model to store SMS templates for different types of notifications.
    """

    name = models.CharField(
        max_length=100, unique=True, help_text=_("Unique name for this SMS template")
    )
    message_template = models.TextField(
        max_length=1600, help_text=_("SMS message template (supports Django template syntax)")
    )
    sms_type = models.CharField(
        max_length=20,
        choices=SMSNotification.SMS_TYPES,
        default="TRANSACTIONAL",
        help_text=_("Type of SMS this template is for"),
    )
    is_active = models.BooleanField(
        default=True, help_text=_("Whether this template is active and can be used")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notifications_sms_template"
        indexes = [
            models.Index(fields=["sms_type", "is_active"], name="sms_template_type_active_idx"),
        ]
        verbose_name = _("SMS Template")
        verbose_name_plural = _("SMS Templates")

    def __str__(self):
        return f"{self.name} ({self.sms_type})"

    def render(self, context):
        """
        Render the SMS template with given context.
        Returns a dictionary with rendered message.
        """
        from django.template import Context, Template

        message_template = Template(self.message_template)

        rendered = {
            "message": message_template.render(Context(context)),
        }

        return rendered


class SMSOptOut(models.Model):
    """
    Model to track SMS opt-out preferences for users.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="sms_opt_out",
        help_text=_("User who opted out of SMS"),
    )
    opted_out_at = models.DateTimeField(
        auto_now_add=True, help_text=_("When the user opted out")
    )
    reason = models.CharField(
        max_length=255, null=True, blank=True, help_text=_("Reason for opting out")
    )
    
    # Allow opt-out by SMS type
    transactional_opt_out = models.BooleanField(
        default=False, help_text=_("Opted out of transactional SMS")
    )
    marketing_opt_out = models.BooleanField(
        default=True, help_text=_("Opted out of marketing SMS (default: True)")
    )
    system_opt_out = models.BooleanField(
        default=False, help_text=_("Opted out of system SMS")
    )
    alert_opt_out = models.BooleanField(
        default=False, help_text=_("Opted out of alert SMS")
    )

    class Meta:
        db_table = "notifications_sms_opt_out"
        verbose_name = _("SMS Opt-Out")
        verbose_name_plural = _("SMS Opt-Outs")

    def __str__(self):
        return f"SMS Opt-Out: {self.user.username}"

    def is_opted_out_for_type(self, sms_type):
        """Check if user is opted out for a specific SMS type"""
        type_mapping = {
            "TRANSACTIONAL": self.transactional_opt_out,
            "MARKETING": self.marketing_opt_out,
            "SYSTEM": self.system_opt_out,
            "ALERT": self.alert_opt_out,
        }
        return type_mapping.get(sms_type, False)


class EmailCampaign(models.Model):
    """
    Model to manage email marketing campaigns.
    """

    STATUS_CHOICES = [
        ("DRAFT", _("Draft")),
        ("SCHEDULED", _("Scheduled")),
        ("SENDING", _("Sending")),
        ("SENT", _("Sent")),
        ("CANCELLED", _("Cancelled")),
    ]

    name = models.CharField(max_length=255, help_text=_("Campaign name"))
    subject = models.CharField(max_length=255, help_text=_("Email subject"))
    template = models.ForeignKey(
        "EmailTemplate", on_delete=models.PROTECT, help_text=_("Email template to use")
    )

    # Targeting
    target_users = models.ManyToManyField(
        User, blank=True, help_text=_("Specific users to target (leave empty for all users)")
    )
    target_roles = models.JSONField(default=list, blank=True, help_text=_("User roles to target"))
    target_tenant_status = models.JSONField(
        default=list, blank=True, help_text=_("Tenant statuses to target")
    )

    # Scheduling
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    scheduled_at = models.DateTimeField(
        null=True, blank=True, help_text=_("When to send this campaign")
    )

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_campaigns"
    )

    # Statistics (updated by signals)
    total_recipients = models.IntegerField(default=0)
    emails_sent = models.IntegerField(default=0)
    emails_delivered = models.IntegerField(default=0)
    emails_opened = models.IntegerField(default=0)
    emails_clicked = models.IntegerField(default=0)
    emails_bounced = models.IntegerField(default=0)
    emails_failed = models.IntegerField(default=0)

    class Meta:
        db_table = "notifications_email_campaign"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="email_campaign_status_idx"),
            models.Index(fields=["scheduled_at"], name="email_campaign_scheduled_idx"),
        ]
        verbose_name = _("Email Campaign")
        verbose_name_plural = _("Email Campaigns")

    def __str__(self):
        return f"{self.name} ({self.status})"

    def get_target_users(self):
        """Get all users that match the campaign targeting criteria"""
        if self.target_users.exists():
            return self.target_users.all()

        queryset = User.objects.all()

        if self.target_roles:
            queryset = queryset.filter(role__in=self.target_roles)

        if self.target_tenant_status:
            queryset = queryset.filter(tenant__status__in=self.target_tenant_status)

        return queryset

    def update_statistics(self):
        """Update campaign statistics based on email notifications"""
        emails = EmailNotification.objects.filter(campaign_id=str(self.id))

        self.total_recipients = emails.count()
        self.emails_sent = emails.filter(
            status__in=["SENT", "DELIVERED", "OPENED", "CLICKED"]
        ).count()
        self.emails_delivered = emails.filter(status__in=["DELIVERED", "OPENED", "CLICKED"]).count()
        self.emails_opened = emails.filter(status__in=["OPENED", "CLICKED"]).count()
        self.emails_clicked = emails.filter(status="CLICKED").count()
        self.emails_bounced = emails.filter(status="BOUNCED").count()
        self.emails_failed = emails.filter(status="FAILED").count()

        self.save(
            update_fields=[
                "total_recipients",
                "emails_sent",
                "emails_delivered",
                "emails_opened",
                "emails_clicked",
                "emails_bounced",
                "emails_failed",
            ]
        )


class SMSCampaign(models.Model):
    """
    Model to manage SMS marketing campaigns.
    """

    STATUS_CHOICES = [
        ("DRAFT", _("Draft")),
        ("SCHEDULED", _("Scheduled")),
        ("SENDING", _("Sending")),
        ("SENT", _("Sent")),
        ("CANCELLED", _("Cancelled")),
    ]

    name = models.CharField(max_length=255, help_text=_("Campaign name"))
    template = models.ForeignKey(
        "SMSTemplate", on_delete=models.PROTECT, help_text=_("SMS template to use")
    )

    # Targeting
    target_users = models.ManyToManyField(
        User, blank=True, help_text=_("Specific users to target (leave empty for all users)")
    )
    target_roles = models.JSONField(default=list, blank=True, help_text=_("User roles to target"))
    target_tenant_status = models.JSONField(
        default=list, blank=True, help_text=_("Tenant statuses to target")
    )

    # Scheduling
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    scheduled_at = models.DateTimeField(
        null=True, blank=True, help_text=_("When to send this campaign")
    )

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_sms_campaigns"
    )

    # Statistics (updated by signals)
    total_recipients = models.IntegerField(default=0)
    sms_sent = models.IntegerField(default=0)
    sms_delivered = models.IntegerField(default=0)
    sms_failed = models.IntegerField(default=0)
    total_cost = models.DecimalField(
        max_digits=10, decimal_places=4, default=0, help_text=_("Total cost of campaign")
    )

    class Meta:
        db_table = "notifications_sms_campaign"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="sms_campaign_status_idx"),
            models.Index(fields=["scheduled_at"], name="sms_campaign_scheduled_idx"),
        ]
        verbose_name = _("SMS Campaign")
        verbose_name_plural = _("SMS Campaigns")

    def __str__(self):
        return f"{self.name} ({self.status})"

    def get_target_users(self):
        """Get all users that match the campaign targeting criteria"""
        if self.target_users.exists():
            return self.target_users.all()

        queryset = User.objects.all()

        if self.target_roles:
            queryset = queryset.filter(role__in=self.target_roles)

        if self.target_tenant_status:
            queryset = queryset.filter(tenant__status__in=self.target_tenant_status)

        return queryset

    def update_statistics(self):
        """Update campaign statistics based on SMS notifications"""
        sms_messages = SMSNotification.objects.filter(campaign_id=str(self.id))

        self.total_recipients = sms_messages.count()
        self.sms_sent = sms_messages.filter(
            status__in=["SENT", "DELIVERED"]
        ).count()
        self.sms_delivered = sms_messages.filter(status="DELIVERED").count()
        self.sms_failed = sms_messages.filter(status__in=["FAILED", "UNDELIVERED"]).count()
        
        # Calculate total cost
        total_cost = sms_messages.aggregate(
            total=models.Sum('price')
        )['total'] or 0
        self.total_cost = total_cost

        self.save(
            update_fields=[
                "total_recipients",
                "sms_sent",
                "sms_delivered",
                "sms_failed",
                "total_cost",
            ]
        )
