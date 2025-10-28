"""
URL patterns for external service integration management.

Per Requirement 32.9: Manage API keys for external services
Per Requirement 32.10: Support OAuth2 for third-party service connections
"""

from django.urls import path

from . import integration_views

app_name = "integrations"

urlpatterns = [
    # Service management
    path("", integration_views.ExternalServiceListView.as_view(), name="service_list"),
    path("add/", integration_views.ExternalServiceCreateView.as_view(), name="service_create"),
    path(
        "<uuid:pk>/", integration_views.ExternalServiceDetailView.as_view(), name="service_detail"
    ),
    path(
        "<uuid:pk>/edit/",
        integration_views.ExternalServiceUpdateView.as_view(),
        name="service_update",
    ),
    path(
        "<uuid:pk>/delete/",
        integration_views.ExternalServiceDeleteView.as_view(),
        name="service_delete",
    ),
    path(
        "<uuid:pk>/toggle/",
        integration_views.ExternalServiceToggleView.as_view(),
        name="service_toggle",
    ),
    # Health monitoring
    path(
        "<uuid:pk>/health-check/",
        integration_views.ServiceHealthCheckView.as_view(),
        name="service_health_check",
    ),
    path(
        "health/dashboard/",
        integration_views.IntegrationHealthDashboardView.as_view(),
        name="health_dashboard",
    ),
    # OAuth2
    path(
        "<uuid:pk>/oauth2/initiate/",
        integration_views.OAuth2InitiateView.as_view(),
        name="oauth2_initiate",
    ),
    path(
        "<uuid:pk>/oauth2/callback/",
        integration_views.OAuth2CallbackView.as_view(),
        name="oauth2_callback",
    ),
]
