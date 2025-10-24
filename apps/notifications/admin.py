from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Notification, NotificationPreference, NotificationTemplate


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
