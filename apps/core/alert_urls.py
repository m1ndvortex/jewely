"""
URL patterns for monitoring alerts.
"""

from django.urls import path

from apps.core import alert_views

app_name = "monitoring"

urlpatterns = [
    # Alert dashboard
    path("alerts/", alert_views.AlertDashboardView.as_view(), name="alert_dashboard"),
    # Alert rules
    path("alerts/rules/", alert_views.AlertRuleListView.as_view(), name="alert_rule_list"),
    path(
        "alerts/rules/create/", alert_views.AlertRuleCreateView.as_view(), name="alert_rule_create"
    ),
    path(
        "alerts/rules/<uuid:pk>/",
        alert_views.AlertRuleUpdateView.as_view(),
        name="alert_rule_update",
    ),
    path(
        "alerts/rules/<uuid:pk>/delete/",
        alert_views.AlertRuleDeleteView.as_view(),
        name="alert_rule_delete",
    ),
    path(
        "alerts/rules/<uuid:pk>/toggle/",
        alert_views.AlertRuleToggleView.as_view(),
        name="alert_rule_toggle",
    ),
    # Monitoring alerts
    path("alerts/history/", alert_views.MonitoringAlertListView.as_view(), name="alert_list"),
    path(
        "alerts/history/<uuid:pk>/",
        alert_views.MonitoringAlertDetailView.as_view(),
        name="alert_detail",
    ),
    path(
        "alerts/history/<uuid:pk>/acknowledge/",
        alert_views.AlertAcknowledgeView.as_view(),
        name="alert_acknowledge",
    ),
    path(
        "alerts/history/<uuid:pk>/resolve/",
        alert_views.AlertResolveView.as_view(),
        name="alert_resolve",
    ),
    path(
        "alerts/history/bulk-action/",
        alert_views.AlertBulkActionView.as_view(),
        name="alert_bulk_action",
    ),
    # API endpoints
    path("api/alerts/stats/", alert_views.AlertStatsAPIView.as_view(), name="alert_stats_api"),
]
