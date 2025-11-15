"""
URL patterns for the notifications app.
"""

from django.urls import path

from . import views
from .webhooks import MailgunWebhookView, PostmarkWebhookView, SendGridWebhookView, SESWebhookView

app_name = "notifications"

urlpatterns = [
    # Main notification center
    path("", views.NotificationCenterView.as_view(), name="center"),
    # HTMX endpoints for real-time updates
    path("count/", views.NotificationCountView.as_view(), name="count"),
    path("list/", views.NotificationListView.as_view(), name="list"),
    path("dropdown/", views.NotificationDropdownView.as_view(), name="dropdown"),
    # Mark as read endpoints
    path("mark-read/", views.mark_as_read, name="mark_read"),
    path("mark-read/<int:notification_id>/", views.mark_single_as_read, name="mark_single_read"),
    # Preferences
    path("preferences/", views.NotificationPreferencesView.as_view(), name="preferences"),
    # Email webhooks for delivery tracking
    path("webhooks/sendgrid/", SendGridWebhookView.as_view(), name="sendgrid_webhook"),
    path("webhooks/mailgun/", MailgunWebhookView.as_view(), name="mailgun_webhook"),
    path("webhooks/postmark/", PostmarkWebhookView.as_view(), name="postmark_webhook"),
    path("webhooks/ses/", SESWebhookView.as_view(), name="ses_webhook"),
    # SMS webhooks for delivery tracking
    path("webhooks/sms/", views.sms_webhook, name="sms_webhook"),
    # Alertmanager webhook for sending SMS alerts
    path("api/alerts/sms/", views.alertmanager_webhook, name="alertmanager_webhook"),
    # Customer Communication Tools
    path("segments/", views.CustomerSegmentListView.as_view(), name="segments"),
    path("segments/create/", views.CustomerSegmentCreateView.as_view(), name="segment_create"),
    path("segments/preview/", views.SegmentPreviewView.as_view(), name="segment_preview"),
    path("campaigns/bulk/", views.BulkCampaignView.as_view(), name="bulk_campaign"),
    path("analytics/", views.CampaignAnalyticsView.as_view(), name="campaign_analytics"),
    path("communications/", views.CommunicationLogView.as_view(), name="communication_log"),
    path("track-conversion/", views.track_conversion, name="track_conversion"),
]
