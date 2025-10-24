"""
URL patterns for the notifications app.
"""

from django.urls import path

from . import views

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
]
