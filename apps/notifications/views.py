"""
Views for the notification system.

This module provides views for managing in-app notifications including:
- Notification center
- Real-time notification updates via HTMX
- Notification preferences management
- Mark as read functionality
"""

import json
from typing import Any, Dict

import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView

from .models import Notification, NotificationPreference
from .services import get_unread_count, get_user_notifications, mark_notifications_as_read, track_sms_event

logger = logging.getLogger(__name__)


class NotificationCenterView(LoginRequiredMixin, ListView):
    """
    Main notification center view showing all user notifications.
    """

    model = Notification
    template_name = "notifications/notification_center.html"
    context_object_name = "notifications"
    paginate_by = 20

    def get_queryset(self):
        """Get notifications for the current user"""
        return get_user_notifications(
            user=self.request.user,
            unread_only=self.request.GET.get("unread_only") == "true",
            notification_type=self.request.GET.get("type"),
            limit=None,  # Pagination handles limiting
        )

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        """Add additional context for the notification center"""
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "unread_count": get_unread_count(self.request.user),
                "notification_types": Notification.NOTIFICATION_TYPES,
                "current_filter": {
                    "unread_only": self.request.GET.get("unread_only") == "true",
                    "type": self.request.GET.get("type", ""),
                },
            }
        )
        return context


@method_decorator(login_required, name="dispatch")
class NotificationCountView(View):
    """
    HTMX endpoint for real-time notification count updates.
    Returns just the unread count badge HTML fragment.
    """

    def get(self, request: HttpRequest) -> HttpResponse:
        """Return unread notification count as HTML fragment"""
        unread_count = get_unread_count(request.user)

        return render(
            request,
            "notifications/partials/unread_count_badge.html",
            {"unread_count": unread_count},
        )


@method_decorator(login_required, name="dispatch")
class NotificationListView(View):
    """
    HTMX endpoint for real-time notification list updates.
    Returns the notification list HTML fragment.
    """

    def get(self, request: HttpRequest) -> HttpResponse:
        """Return notification list as HTML fragment"""
        notifications = get_user_notifications(
            user=request.user,
            unread_only=request.GET.get("unread_only") == "true",
            notification_type=request.GET.get("type"),
            limit=10,  # Limit for dropdown/widget
        )

        return render(
            request,
            "notifications/partials/notification_list.html",
            {"notifications": notifications, "show_all_link": True},
        )


@require_http_methods(["POST"])
@login_required
def mark_as_read(request: HttpRequest) -> JsonResponse:
    """
    Mark notifications as read.
    Accepts either specific notification IDs or marks all as read.
    """
    try:
        data = json.loads(request.body) if request.body else {}
        notification_ids = data.get("notification_ids")

        if notification_ids:
            # Mark specific notifications as read
            count = mark_notifications_as_read(request.user, notification_ids)
        else:
            # Mark all notifications as read
            count = mark_notifications_as_read(request.user)

        return JsonResponse(
            {
                "success": True,
                "marked_count": count,
                "message": f'Marked {count} notification{"s" if count != 1 else ""} as read',
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@require_http_methods(["POST"])
@login_required
def mark_single_as_read(request: HttpRequest, notification_id: int) -> JsonResponse:
    """
    Mark a single notification as read.
    """
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)

    try:
        notification.mark_as_read()

        return JsonResponse({"success": True, "message": "Notification marked as read"})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


class NotificationPreferencesView(LoginRequiredMixin, View):
    """
    View for managing user notification preferences.
    """

    template_name = "notifications/preferences.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        """Display notification preferences form"""
        # Get or create preferences for all notification types and channels
        preferences = {}

        for notification_type, _ in Notification.NOTIFICATION_TYPES:
            preferences[notification_type] = {}
            for channel, _ in NotificationPreference.CHANNEL_CHOICES:
                try:
                    pref = NotificationPreference.objects.get(
                        user=request.user, notification_type=notification_type, channel=channel
                    )
                except NotificationPreference.DoesNotExist:
                    # Create default preference
                    pref = NotificationPreference.objects.create(
                        user=request.user,
                        notification_type=notification_type,
                        channel=channel,
                        is_enabled=(channel == "IN_APP"),  # Default: only in-app enabled
                    )

                preferences[notification_type][channel] = pref

        return render(
            request,
            self.template_name,
            {
                "preferences": preferences,
                "notification_types": Notification.NOTIFICATION_TYPES,
                "channels": NotificationPreference.CHANNEL_CHOICES,
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        """Update notification preferences"""
        try:
            # Process form data
            for notification_type, _ in Notification.NOTIFICATION_TYPES:
                for channel, _ in NotificationPreference.CHANNEL_CHOICES:
                    field_name = f"{notification_type}_{channel}"
                    is_enabled = field_name in request.POST

                    # Update or create preference
                    NotificationPreference.objects.update_or_create(
                        user=request.user,
                        notification_type=notification_type,
                        channel=channel,
                        defaults={"is_enabled": is_enabled},
                    )

            # Handle quiet hours if provided
            quiet_hours_start = request.POST.get("quiet_hours_start")
            quiet_hours_end = request.POST.get("quiet_hours_end")

            if quiet_hours_start and quiet_hours_end:
                # Update quiet hours for all preferences
                NotificationPreference.objects.filter(user=request.user).update(
                    quiet_hours_start=quiet_hours_start, quiet_hours_end=quiet_hours_end
                )

            return render(
                request,
                self.template_name,
                {
                    "success_message": "Notification preferences updated successfully!",
                    "preferences": self._get_preferences_dict(request.user),
                    "notification_types": Notification.NOTIFICATION_TYPES,
                    "channels": NotificationPreference.CHANNEL_CHOICES,
                },
            )

        except Exception as e:
            return render(
                request,
                self.template_name,
                {
                    "error_message": f"Error updating preferences: {str(e)}",
                    "preferences": self._get_preferences_dict(request.user),
                    "notification_types": Notification.NOTIFICATION_TYPES,
                    "channels": NotificationPreference.CHANNEL_CHOICES,
                },
            )

    def _get_preferences_dict(self, user):
        """Helper method to get preferences as a nested dictionary"""
        preferences = {}

        for notification_type, _ in Notification.NOTIFICATION_TYPES:
            preferences[notification_type] = {}
            for channel, _ in NotificationPreference.CHANNEL_CHOICES:
                try:
                    pref = NotificationPreference.objects.get(
                        user=user, notification_type=notification_type, channel=channel
                    )
                except NotificationPreference.DoesNotExist:
                    pref = NotificationPreference.objects.create(
                        user=user,
                        notification_type=notification_type,
                        channel=channel,
                        is_enabled=(channel == "IN_APP"),
                    )

                preferences[notification_type][channel] = pref

        return preferences


@method_decorator(login_required, name="dispatch")
class NotificationDropdownView(View):
    """
    HTMX endpoint for notification dropdown widget.
    Used in the main navigation to show recent notifications.
    """

    def get(self, request: HttpRequest) -> HttpResponse:
        """Return notification dropdown HTML fragment"""
        notifications = get_user_notifications(
            user=request.user, unread_only=False, limit=5  # Show only 5 most recent
        )

        unread_count = get_unread_count(request.user)

        return render(
            request,
            "notifications/partials/notification_dropdown.html",
            {
                "notifications": notifications,
                "unread_count": unread_count,
            },
        )


@require_http_methods(["POST"])
def sms_webhook(request: HttpRequest) -> HttpResponse:
    """
    Webhook endpoint for Twilio SMS delivery status updates.
    """
    try:
        # Verify webhook signature if secret is configured
        webhook_secret = getattr(settings, 'SMS_WEBHOOK_SECRET', '')
        if webhook_secret:
            # TODO: Implement Twilio signature verification
            # This would verify the X-Twilio-Signature header
            pass
        
        # Extract Twilio webhook data
        message_sid = request.POST.get('MessageSid')
        message_status = request.POST.get('MessageStatus')
        error_code = request.POST.get('ErrorCode')
        error_message = request.POST.get('ErrorMessage')
        
        if message_sid and message_status:
            # Track the SMS event
            track_sms_event(
                message_sid=message_sid,
                event_type=message_status,
                error_code=error_code,
                error_message=error_message,
            )
            
            return HttpResponse("OK", status=200)
        else:
            return HttpResponse("Missing required parameters", status=400)
            
    except Exception as e:
        logger.error(f"SMS webhook error: {str(e)}")
        return HttpResponse("Internal Server Error", status=500)
