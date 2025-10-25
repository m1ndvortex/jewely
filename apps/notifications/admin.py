from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import (
    EmailCampaign,
    EmailNotification,
    EmailTemplate,
    Notification,
    NotificationPreference,
    NotificationTemplate,
    SMSCampaign,
    SMSNotification,
    SMSOptOut,
    SMSTemplate,
)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin interface for Notification model"""

    list_display = [
        "title",
        "user",
        "notification_type",
        "is_read",
        "created_at",
        "expires_at",
        "action_button",
    ]
    list_filter = ["notification_type", "is_read", "created_at", "expires_at"]
    search_fields = ["title", "message", "user__username", "user__email"]
    readonly_fields = ["created_at", "read_at"]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]

    fieldsets = (
        (_("Basic Information"), {"fields": ("user", "title", "message", "notification_type")}),
        (_("Status"), {"fields": ("is_read", "read_at", "expires_at")}),
        (_("Action"), {"fields": ("action_text", "action_url"), "classes": ("collapse",)}),
        (_("Timestamps"), {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    def action_button(self, obj):
        """Display action button if available"""
        if obj.action_url and obj.action_text:
            return format_html(
                '<a href="{}" class="button" target="_blank">{}</a>',
                obj.action_url,
                obj.action_text,
            )
        return "-"

    action_button.short_description = _("Action")

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related("user")


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    """Admin interface for NotificationPreference model"""

    list_display = [
        "user",
        "notification_type",
        "channel",
        "is_enabled",
        "quiet_hours",
        "updated_at",
    ]
    list_filter = ["notification_type", "channel", "is_enabled", "updated_at"]
    search_fields = ["user__username", "user__email"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["user", "notification_type", "channel"]

    fieldsets = (
        (_("Basic Settings"), {"fields": ("user", "notification_type", "channel", "is_enabled")}),
        (
            _("Quiet Hours"),
            {"fields": ("quiet_hours_start", "quiet_hours_end"), "classes": ("collapse",)},
        ),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def quiet_hours(self, obj):
        """Display quiet hours range"""
        if obj.quiet_hours_start and obj.quiet_hours_end:
            return f"{obj.quiet_hours_start} - {obj.quiet_hours_end}"
        return "-"

    quiet_hours.short_description = _("Quiet Hours")

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related("user")


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    """Admin interface for NotificationTemplate model"""

    list_display = ["name", "notification_type", "is_active", "updated_at"]
    list_filter = ["notification_type", "is_active", "updated_at"]
    search_fields = ["name", "title_template", "message_template"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["notification_type", "name"]

    fieldsets = (
        (_("Basic Information"), {"fields": ("name", "notification_type", "is_active")}),
        (_("Templates"), {"fields": ("title_template", "message_template")}),
        (
            _("Action Templates"),
            {"fields": ("action_text_template", "action_url_template"), "classes": ("collapse",)},
        ),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_form(self, request, obj=None, **kwargs):
        """Customize form to show template syntax help"""
        form = super().get_form(request, obj, **kwargs)

        # Add help text for template fields
        if "title_template" in form.base_fields:
            form.base_fields["title_template"].help_text = _(
                "Use Django template syntax. Available variables depend on context."
            )
        if "message_template" in form.base_fields:
            form.base_fields["message_template"].help_text = _(
                "Use Django template syntax. Available variables depend on context."
            )

        return form


@admin.register(EmailNotification)
class EmailNotificationAdmin(admin.ModelAdmin):
    """Admin interface for EmailNotification model"""

    list_display = [
        "subject",
        "to_email",
        "status_badge",
        "email_type",
        "created_at",
        "sent_at",
    ]
    list_filter = [
        "status",
        "email_type",
        "created_at",
        "sent_at",
    ]
    search_fields = [
        "subject",
        "to_email",
        "user__username",
        "user__email",
        "message_id",
    ]
    readonly_fields = [
        "id",
        "created_at",
        "sent_at",
        "delivered_at",
        "opened_at",
        "clicked_at",
        "bounced_at",
        "failed_at",
        "message_id",
    ]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]

    fieldsets = (
        (
            _("Email Details"),
            {"fields": ("subject", "to_email", "from_email", "template_name", "email_type")},
        ),
        (
            _("Status & Tracking"),
            {"fields": ("status", "message_id", "error_message", "bounce_reason")},
        ),
        (_("Scheduling"), {"fields": ("scheduled_at", "campaign_id")}),
        (
            _("Timestamps"),
            {
                "fields": (
                    "created_at",
                    "sent_at",
                    "delivered_at",
                    "opened_at",
                    "clicked_at",
                    "bounced_at",
                    "failed_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "notification")

    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            "PENDING": "#f59e0b",
            "SENT": "#3b82f6",
            "DELIVERED": "#10b981",
            "OPENED": "#8b5cf6",
            "CLICKED": "#6366f1",
            "BOUNCED": "#ef4444",
            "FAILED": "#ef4444",
            "COMPLAINED": "#ef4444",
            "UNSUBSCRIBED": "#6b7280",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = _("Status")


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    """Admin interface for EmailTemplate model"""

    list_display = [
        "name",
        "email_type",
        "is_active",
        "updated_at",
    ]
    list_filter = [
        "email_type",
        "is_active",
        "updated_at",
    ]
    search_fields = [
        "name",
        "subject_template",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (_("Template Details"), {"fields": ("name", "email_type", "is_active")}),
        (_("Email Content"), {"fields": ("subject_template", "html_template", "text_template")}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(EmailCampaign)
class EmailCampaignAdmin(admin.ModelAdmin):
    """Admin interface for EmailCampaign model"""

    list_display = [
        "name",
        "status",
        "total_recipients",
        "emails_sent",
        "delivery_rate",
        "open_rate",
        "scheduled_at",
        "created_at",
    ]
    list_filter = [
        "status",
        "scheduled_at",
        "created_at",
        "sent_at",
    ]
    search_fields = [
        "name",
        "subject",
        "created_by__username",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
        "sent_at",
        "total_recipients",
        "emails_sent",
        "emails_delivered",
        "emails_opened",
        "emails_clicked",
        "emails_bounced",
        "emails_failed",
    ]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]

    fieldsets = (
        (_("Campaign Details"), {"fields": ("name", "subject", "template", "status")}),
        (_("Targeting"), {"fields": ("target_users", "target_roles", "target_tenant_status")}),
        (_("Scheduling"), {"fields": ("scheduled_at", "created_by")}),
        (
            _("Statistics"),
            {
                "fields": (
                    "total_recipients",
                    "emails_sent",
                    "emails_delivered",
                    "emails_opened",
                    "emails_clicked",
                    "emails_bounced",
                    "emails_failed",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Timestamps"),
            {"fields": ("created_at", "updated_at", "sent_at"), "classes": ("collapse",)},
        ),
    )

    filter_horizontal = ["target_users"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("template", "created_by")

    def delivery_rate(self, obj):
        """Calculate and display delivery rate"""
        if obj.emails_sent > 0:
            rate = (obj.emails_delivered / obj.emails_sent) * 100
            return f"{rate:.1f}%"
        return "0%"

    delivery_rate.short_description = _("Delivery Rate")

    def open_rate(self, obj):
        """Calculate and display open rate"""
        if obj.emails_sent > 0:
            rate = (obj.emails_opened / obj.emails_sent) * 100
            return f"{rate:.1f}%"
        return "0%"

    open_rate.short_description = _("Open Rate")


# SMS Admin Classes


@admin.register(SMSNotification)
class SMSNotificationAdmin(admin.ModelAdmin):
    """Admin interface for SMS notifications"""

    list_display = [
        "id",
        "user",
        "to_phone",
        "sms_type",
        "status_badge",
        "created_at",
        "sent_at",
        "delivered_at",
    ]
    list_filter = [
        "sms_type",
        "status",
        "created_at",
        "sent_at",
    ]
    search_fields = [
        "user__username",
        "user__email",
        "to_phone",
        "message",
        "message_sid",
    ]
    readonly_fields = [
        "id",
        "message_sid",
        "created_at",
        "sent_at",
        "delivered_at",
        "failed_at",
        "price",
        "price_unit",
    ]
    raw_id_fields = ["user", "notification"]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]

    fieldsets = [
        (
            _("SMS Details"),
            {
                "fields": (
                    "user",
                    "notification",
                    "message",
                    "to_phone",
                    "from_phone",
                    "sms_type",
                    "template_name",
                )
            },
        ),
        (
            _("Delivery Status"),
            {
                "fields": (
                    "status",
                    "message_sid",
                    "error_message",
                    "error_code",
                )
            },
        ),
        (
            _("Timestamps"),
            {
                "fields": (
                    "created_at",
                    "sent_at",
                    "delivered_at",
                    "failed_at",
                    "scheduled_at",
                )
            },
        ),
        (
            _("Campaign & Cost"),
            {
                "fields": (
                    "campaign_id",
                    "price",
                    "price_unit",
                )
            },
        ),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "notification")

    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            "PENDING": "#f59e0b",
            "QUEUED": "#3b82f6",
            "SENT": "#10b981",
            "DELIVERED": "#059669",
            "FAILED": "#ef4444",
            "UNDELIVERED": "#ef4444",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = _("Status")


@admin.register(SMSTemplate)
class SMSTemplateAdmin(admin.ModelAdmin):
    """Admin interface for SMS templates"""

    list_display = [
        "name",
        "sms_type",
        "is_active",
        "message_length",
        "created_at",
        "updated_at",
    ]
    list_filter = [
        "sms_type",
        "is_active",
        "created_at",
    ]
    search_fields = [
        "name",
        "message_template",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]
    ordering = ["sms_type", "name"]

    fieldsets = [
        (
            _("Template Details"),
            {
                "fields": (
                    "name",
                    "sms_type",
                    "is_active",
                )
            },
        ),
        (
            _("Message Content"),
            {"fields": ("message_template",)},
        ),
        (
            _("Timestamps"),
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    ]

    def message_length(self, obj):
        """Display message template length"""
        length = len(obj.message_template)
        if length > 160:
            color = "#ef4444"  # Red for long messages
        elif length > 120:
            color = "#f59e0b"  # Orange for medium messages
        else:
            color = "#10b981"  # Green for short messages

        return format_html(
            '<span style="color: {}; font-weight: bold;">{} chars</span>',
            color,
            length,
        )

    message_length.short_description = _("Length")

    def get_form(self, request, obj=None, **kwargs):
        """Customize form to show template syntax help"""
        form = super().get_form(request, obj, **kwargs)

        if "message_template" in form.base_fields:
            form.base_fields["message_template"].help_text = _(
                "Use Django template syntax. Keep under 160 characters for single SMS. Available variables depend on context."
            )

        return form


@admin.register(SMSOptOut)
class SMSOptOutAdmin(admin.ModelAdmin):
    """Admin interface for SMS opt-outs"""

    list_display = [
        "user",
        "transactional_opt_out",
        "marketing_opt_out",
        "system_opt_out",
        "alert_opt_out",
        "opted_out_at",
    ]
    list_filter = [
        "transactional_opt_out",
        "marketing_opt_out",
        "system_opt_out",
        "alert_opt_out",
        "opted_out_at",
    ]
    search_fields = [
        "user__username",
        "user__email",
        "reason",
    ]
    readonly_fields = [
        "opted_out_at",
    ]
    raw_id_fields = ["user"]
    date_hierarchy = "opted_out_at"
    ordering = ["-opted_out_at"]

    fieldsets = [
        (
            _("User"),
            {
                "fields": (
                    "user",
                    "reason",
                    "opted_out_at",
                )
            },
        ),
        (
            _("Opt-out Preferences"),
            {
                "fields": (
                    "transactional_opt_out",
                    "marketing_opt_out",
                    "system_opt_out",
                    "alert_opt_out",
                )
            },
        ),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")


@admin.register(SMSCampaign)
class SMSCampaignAdmin(admin.ModelAdmin):
    """Admin interface for SMS campaigns"""

    list_display = [
        "name",
        "template",
        "status",
        "total_recipients",
        "sms_sent",
        "sms_delivered",
        "delivery_rate",
        "total_cost",
        "created_at",
        "sent_at",
    ]
    list_filter = [
        "status",
        "created_at",
        "sent_at",
        "scheduled_at",
    ]
    search_fields = [
        "name",
        "template__name",
        "created_by__username",
    ]
    readonly_fields = [
        "total_recipients",
        "sms_sent",
        "sms_delivered",
        "sms_failed",
        "total_cost",
        "created_at",
        "updated_at",
        "sent_at",
    ]
    raw_id_fields = ["template", "created_by"]
    filter_horizontal = ["target_users"]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]

    fieldsets = [
        (
            _("Campaign Details"),
            {
                "fields": (
                    "name",
                    "template",
                    "status",
                    "created_by",
                )
            },
        ),
        (
            _("Targeting"),
            {
                "fields": (
                    "target_users",
                    "target_roles",
                    "target_tenant_status",
                )
            },
        ),
        (
            _("Scheduling"),
            {"fields": ("scheduled_at",)},
        ),
        (
            _("Statistics"),
            {
                "fields": (
                    "total_recipients",
                    "sms_sent",
                    "sms_delivered",
                    "sms_failed",
                    "total_cost",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Timestamps"),
            {
                "fields": (
                    "created_at",
                    "updated_at",
                    "sent_at",
                ),
                "classes": ("collapse",),
            },
        ),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("template", "created_by")

    def delivery_rate(self, obj):
        """Calculate and display delivery rate"""
        if obj.sms_sent > 0:
            rate = (obj.sms_delivered / obj.sms_sent) * 100
            return f"{rate:.1f}%"
        return "0%"

    delivery_rate.short_description = _("Delivery Rate")
