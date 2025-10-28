"""
URL patterns for webhook management.

Per Requirement 32 - Webhook and Integration Management
"""

from django.urls import path

from . import webhook_views

app_name = "webhooks"

urlpatterns = [
    # Webhook Management
    path("", webhook_views.WebhookListView.as_view(), name="webhook_list"),
    path("create/", webhook_views.WebhookCreateView.as_view(), name="webhook_create"),
    path("<uuid:pk>/", webhook_views.WebhookDetailView.as_view(), name="webhook_detail"),
    path("<uuid:pk>/edit/", webhook_views.WebhookUpdateView.as_view(), name="webhook_update"),
    path("<uuid:pk>/delete/", webhook_views.WebhookDeleteView.as_view(), name="webhook_delete"),
    path("<uuid:pk>/toggle/", webhook_views.WebhookToggleView.as_view(), name="webhook_toggle"),
    path(
        "<uuid:pk>/regenerate-secret/",
        webhook_views.WebhookRegenerateSecretView.as_view(),
        name="webhook_regenerate_secret",
    ),
    path("<uuid:pk>/test/", webhook_views.WebhookTestView.as_view(), name="webhook_test"),
    # Webhook Delivery History
    path(
        "<uuid:webhook_id>/deliveries/",
        webhook_views.WebhookDeliveryListView.as_view(),
        name="webhook_delivery_list",
    ),
    path(
        "deliveries/<uuid:pk>/",
        webhook_views.WebhookDeliveryDetailView.as_view(),
        name="webhook_delivery_detail",
    ),
]
