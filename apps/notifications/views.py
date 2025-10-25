"""
Views for the notification system.

This module provides views for managing in-app notifications including:
- Notification center
- Real-time notification updates via HTMX
- Notification preferences management
- Mark as read functionality
"""

import json
import logging
from typing import Any, Dict

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
from .services import (
    get_unread_count,
    get_user_notifications,
    mark_notifications_as_read,
    track_sms_event,
)

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
        webhook_secret = getattr(settings, "SMS_WEBHOOK_SECRET", "")
        if webhook_secret:
            # TODO: Implement Twilio signature verification
            # This would verify the X-Twilio-Signature header
            pass

        # Extract Twilio webhook data
        message_sid = request.POST.get("MessageSid")
        message_status = request.POST.get("MessageStatus")
        error_code = request.POST.get("ErrorCode")
        error_message = request.POST.get("ErrorMessage")

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


# Customer Communication Tools Views


class CustomerSegmentListView(LoginRequiredMixin, ListView):
    """
    View for listing customer segments.
    """

    model = None  # Will be set in get_queryset
    template_name = "notifications/customer_segments.html"
    context_object_name = "segments"
    paginate_by = 20

    def get_queryset(self):
        from .models import CustomerSegment

        self.model = CustomerSegment
        return CustomerSegment.objects.filter(is_active=True).order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Customer Segments"
        return context


class CustomerSegmentCreateView(LoginRequiredMixin, View):
    """
    View for creating customer segments.
    """

    template_name = "notifications/segment_form.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        from apps.crm.models import LoyaltyTier

        context = {
            "page_title": "Create Customer Segment",
            "loyalty_tiers": LoyaltyTier.objects.filter(is_active=True),
            "segment_types": [
                ("STATIC", "Static Segment"),
                ("DYNAMIC", "Dynamic Segment"),
            ],
        }
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest) -> HttpResponse:
        from apps.crm.models import Customer

        from .services import create_customer_segment

        try:
            name = request.POST.get("name")
            description = request.POST.get("description", "")
            segment_type = request.POST.get("segment_type", "STATIC")

            if segment_type == "DYNAMIC":
                # Build criteria from form data
                criteria = {}

                if request.POST.get("min_total_purchases"):
                    criteria["min_total_purchases"] = float(request.POST.get("min_total_purchases"))

                if request.POST.get("max_total_purchases"):
                    criteria["max_total_purchases"] = float(request.POST.get("max_total_purchases"))

                if request.POST.get("last_purchase_days"):
                    criteria["last_purchase_days"] = int(request.POST.get("last_purchase_days"))

                loyalty_tiers = request.POST.getlist("loyalty_tiers")
                if loyalty_tiers:
                    criteria["loyalty_tiers"] = loyalty_tiers

                tags = request.POST.get("tags")
                if tags:
                    criteria["tags"] = [tag.strip() for tag in tags.split(",")]

                if request.POST.get("marketing_opt_in"):
                    criteria["marketing_opt_in"] = request.POST.get("marketing_opt_in") == "true"

                if request.POST.get("sms_opt_in"):
                    criteria["sms_opt_in"] = request.POST.get("sms_opt_in") == "true"

                segment = create_customer_segment(
                    name=name,
                    description=description,
                    segment_type=segment_type,
                    criteria=criteria,
                    created_by=request.user,
                )
            else:
                # Static segment - get selected customers
                customer_ids = request.POST.getlist("customers")
                customers = Customer.objects.filter(id__in=customer_ids) if customer_ids else []

                segment = create_customer_segment(
                    name=name,
                    description=description,
                    segment_type=segment_type,
                    customers=customers,
                    created_by=request.user,
                )

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Segment '{name}' created successfully with {segment.customer_count} customers",
                    "segment_id": str(segment.id),
                }
            )

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)


class BulkCampaignView(LoginRequiredMixin, View):
    """
    View for creating and sending bulk campaigns to customer segments.
    """

    template_name = "notifications/bulk_campaign.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        from .models import CustomerSegment, EmailTemplate, SMSTemplate

        context = {
            "page_title": "Bulk Campaign",
            "segments": CustomerSegment.objects.filter(is_active=True),
            "email_templates": EmailTemplate.objects.filter(is_active=True, email_type="MARKETING"),
            "sms_templates": SMSTemplate.objects.filter(is_active=True, sms_type="MARKETING"),
            "campaign_types": [
                ("EMAIL", "Email Campaign"),
                ("SMS", "SMS Campaign"),
            ],
        }
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest) -> HttpResponse:
        from .services import send_bulk_campaign_to_segment

        try:
            segment_id = request.POST.get("segment_id")
            campaign_type = request.POST.get("campaign_type")
            template_name = request.POST.get("template_name")
            subject = request.POST.get("subject", "")

            # Build context from form data
            context = {}
            for key, value in request.POST.items():
                if key.startswith("context_"):
                    context_key = key.replace("context_", "")
                    context[context_key] = value

            result = send_bulk_campaign_to_segment(
                segment_id=segment_id,
                campaign_type=campaign_type,
                template_name=template_name,
                subject=subject,
                context=context,
                created_by=request.user,
            )

            if "error" in result:
                return JsonResponse({"success": False, "error": result["error"]}, status=400)

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Campaign sent successfully to {result['sent_count']} customers",
                    "result": result,
                }
            )

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)


class CampaignAnalyticsView(LoginRequiredMixin, View):
    """
    View for displaying campaign analytics and performance metrics.
    """

    template_name = "notifications/campaign_analytics.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        from datetime import datetime, timedelta

        from .models import CampaignAnalytics
        from .services import get_campaign_performance_report

        # Get date range from query parameters
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)  # Default to last 30 days

        if request.GET.get("start_date"):
            start_date = datetime.strptime(request.GET.get("start_date"), "%Y-%m-%d")

        if request.GET.get("end_date"):
            end_date = datetime.strptime(request.GET.get("end_date"), "%Y-%m-%d")

        campaign_type = request.GET.get("campaign_type")

        # Get performance report
        performance_report = get_campaign_performance_report(
            start_date=start_date,
            end_date=end_date,
            campaign_type=campaign_type,
        )

        # Get recent campaigns
        recent_campaigns = CampaignAnalytics.objects.filter(
            campaign_sent_at__gte=start_date,
            campaign_sent_at__lte=end_date,
        )

        if campaign_type:
            recent_campaigns = recent_campaigns.filter(campaign_type=campaign_type)

        recent_campaigns = recent_campaigns.order_by("-campaign_sent_at")[:20]

        context = {
            "page_title": "Campaign Analytics",
            "performance_report": performance_report,
            "recent_campaigns": recent_campaigns,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "campaign_type": campaign_type,
            "campaign_types": [
                ("", "All Types"),
                ("EMAIL", "Email"),
                ("SMS", "SMS"),
                ("MIXED", "Mixed"),
            ],
        }
        return render(request, self.template_name, context)


class CommunicationLogView(LoginRequiredMixin, ListView):
    """
    View for displaying customer communication logs.
    """

    model = None  # Will be set in get_queryset
    template_name = "notifications/communication_log.html"
    context_object_name = "communications"
    paginate_by = 50

    def get_queryset(self):
        from .models import CommunicationLog

        self.model = CommunicationLog

        queryset = CommunicationLog.objects.select_related("customer").order_by(
            "-communication_date"
        )

        # Filter by customer if provided
        customer_id = self.request.GET.get("customer_id")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        # Filter by communication type
        comm_type = self.request.GET.get("type")
        if comm_type:
            queryset = queryset.filter(communication_type=comm_type)

        # Filter by campaign
        campaign_id = self.request.GET.get("campaign_id")
        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)

        return queryset

    def get_context_data(self, **kwargs):
        from .models import CommunicationLog

        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Communication Log",
                "communication_types": CommunicationLog.COMMUNICATION_TYPES,
                "current_filters": {
                    "customer_id": self.request.GET.get("customer_id", ""),
                    "type": self.request.GET.get("type", ""),
                    "campaign_id": self.request.GET.get("campaign_id", ""),
                },
            }
        )
        return context


@require_http_methods(["POST"])
@login_required
def track_conversion(request: HttpRequest) -> JsonResponse:
    """
    API endpoint to track campaign conversions.
    """
    try:
        from .services import track_campaign_conversion

        data = json.loads(request.body) if request.body else {}
        campaign_id = data.get("campaign_id")
        conversion_value = data.get("conversion_value")
        customer_id = data.get("customer_id")

        if not campaign_id:
            return JsonResponse({"success": False, "error": "Campaign ID is required"}, status=400)

        success = track_campaign_conversion(
            campaign_id=campaign_id,
            conversion_value=conversion_value,
            customer_id=customer_id,
        )

        if success:
            return JsonResponse(
                {
                    "success": True,
                    "message": "Conversion tracked successfully",
                }
            )
        else:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Failed to track conversion",
                },
                status=400,
            )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@method_decorator(login_required, name="dispatch")
class SegmentPreviewView(View):
    """
    HTMX endpoint for previewing customer segment results.
    """

    def post(self, request: HttpRequest) -> HttpResponse:
        from apps.crm.models import Customer

        from .services import get_segment_customers

        try:
            segment_type = request.POST.get("segment_type")

            if segment_type == "DYNAMIC":
                # Build criteria and preview customers
                criteria = {}

                if request.POST.get("min_total_purchases"):
                    criteria["min_total_purchases"] = float(request.POST.get("min_total_purchases"))

                if request.POST.get("max_total_purchases"):
                    criteria["max_total_purchases"] = float(request.POST.get("max_total_purchases"))

                if request.POST.get("last_purchase_days"):
                    criteria["last_purchase_days"] = int(request.POST.get("last_purchase_days"))

                loyalty_tiers = request.POST.getlist("loyalty_tiers")
                if loyalty_tiers:
                    criteria["loyalty_tiers"] = loyalty_tiers

                tags = request.POST.get("tags")
                if tags:
                    criteria["tags"] = [tag.strip() for tag in tags.split(",")]

                # Apply criteria to get preview
                queryset = Customer.objects.filter(is_active=True)

                if criteria.get("loyalty_tiers"):
                    queryset = queryset.filter(loyalty_tier__name__in=criteria["loyalty_tiers"])

                if criteria.get("min_total_purchases"):
                    queryset = queryset.filter(total_purchases__gte=criteria["min_total_purchases"])

                if criteria.get("max_total_purchases"):
                    queryset = queryset.filter(total_purchases__lte=criteria["max_total_purchases"])

                if criteria.get("last_purchase_days"):
                    from datetime import timedelta

                    from django.utils import timezone

                    cutoff_date = timezone.now() - timedelta(days=criteria["last_purchase_days"])
                    queryset = queryset.filter(last_purchase_at__gte=cutoff_date)

                if criteria.get("tags"):
                    for tag in criteria["tags"]:
                        queryset = queryset.filter(tags__contains=[tag])

                customers = queryset[:10]  # Preview first 10
                total_count = queryset.count()

            else:
                # Static segment preview
                customer_ids = request.POST.getlist("customers")
                customers = Customer.objects.filter(id__in=customer_ids)[:10]
                total_count = len(customer_ids)

            return render(
                request,
                "notifications/partials/segment_preview.html",
                {
                    "customers": customers,
                    "total_count": total_count,
                    "showing_count": len(customers),
                },
            )

        except Exception as e:
            return render(
                request,
                "notifications/partials/segment_preview.html",
                {
                    "error": str(e),
                    "customers": [],
                    "total_count": 0,
                    "showing_count": 0,
                },
            )
