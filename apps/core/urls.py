from django.urls import include, path

from rest_framework_simplejwt.views import TokenRefreshView

from . import (
    admin_views,
    alert_views,
    announcement_views,
    audit_views,
    branch_views,
    dashboard_views,
    feature_flag_views,
    monitoring_views,
    security_views,
    settings_views,
    stripe_webhooks,
    subscription_views,
    tenant_subscription_views,
    views,
)

app_name = "core"

urlpatterns = [
    # Basic views
    path("", views.home, name="home"),
    path("health/", views.health_check, name="health_check"),
    # Stripe webhook
    path("webhooks/stripe/", stripe_webhooks.stripe_webhook, name="stripe_webhook"),
    # Platform Admin Panel
    path("platform/dashboard/", admin_views.AdminDashboardView.as_view(), name="admin_dashboard"),
    path(
        "platform/api/tenant-metrics/",
        admin_views.TenantMetricsAPIView.as_view(),
        name="admin_api_tenant_metrics",
    ),
    path(
        "platform/api/system-health/",
        admin_views.SystemHealthAPIView.as_view(),
        name="admin_api_system_health",
    ),
    path(
        "platform/api/tenant-signup-chart/",
        admin_views.TenantSignupChartAPIView.as_view(),
        name="admin_api_tenant_signup_chart",
    ),
    path(
        "platform/api/error-feed/",
        admin_views.ErrorFeedAPIView.as_view(),
        name="admin_api_error_feed",
    ),
    # Monitoring Dashboard
    path(
        "platform/monitoring/",
        monitoring_views.MonitoringDashboardView.as_view(),
        name="monitoring_dashboard",
    ),
    path(
        "platform/monitoring/api/system-metrics/",
        monitoring_views.SystemMetricsAPIView.as_view(),
        name="monitoring_system_metrics",
    ),
    path(
        "platform/monitoring/api/database-metrics/",
        monitoring_views.DatabaseMetricsAPIView.as_view(),
        name="monitoring_database_metrics",
    ),
    path(
        "platform/monitoring/api/cache-metrics/",
        monitoring_views.CacheMetricsAPIView.as_view(),
        name="monitoring_cache_metrics",
    ),
    path(
        "platform/monitoring/api/celery-metrics/",
        monitoring_views.CeleryMetricsAPIView.as_view(),
        name="monitoring_celery_metrics",
    ),
    path(
        "platform/monitoring/api/service-status/",
        monitoring_views.ServiceStatusAPIView.as_view(),
        name="monitoring_service_status",
    ),
    # Alert Management
    path(
        "platform/monitoring/alerts/",
        alert_views.AlertDashboardView.as_view(),
        name="alert_dashboard",
    ),
    path(
        "platform/monitoring/alerts/rules/",
        alert_views.AlertRuleListView.as_view(),
        name="alert_rule_list",
    ),
    path(
        "platform/monitoring/alerts/rules/create/",
        alert_views.AlertRuleCreateView.as_view(),
        name="alert_rule_create",
    ),
    path(
        "platform/monitoring/alerts/rules/<uuid:pk>/",
        alert_views.AlertRuleUpdateView.as_view(),
        name="alert_rule_update",
    ),
    path(
        "platform/monitoring/alerts/rules/<uuid:pk>/delete/",
        alert_views.AlertRuleDeleteView.as_view(),
        name="alert_rule_delete",
    ),
    path(
        "platform/monitoring/alerts/rules/<uuid:pk>/toggle/",
        alert_views.AlertRuleToggleView.as_view(),
        name="alert_rule_toggle",
    ),
    path(
        "platform/monitoring/alerts/history/",
        alert_views.MonitoringAlertListView.as_view(),
        name="alert_list",
    ),
    path(
        "platform/monitoring/alerts/history/<uuid:pk>/",
        alert_views.MonitoringAlertDetailView.as_view(),
        name="alert_detail",
    ),
    path(
        "platform/monitoring/alerts/history/<uuid:pk>/acknowledge/",
        alert_views.AlertAcknowledgeView.as_view(),
        name="alert_acknowledge",
    ),
    path(
        "platform/monitoring/alerts/history/<uuid:pk>/resolve/",
        alert_views.AlertResolveView.as_view(),
        name="alert_resolve",
    ),
    path(
        "platform/monitoring/alerts/history/bulk-action/",
        alert_views.AlertBulkActionView.as_view(),
        name="alert_bulk_action",
    ),
    path(
        "platform/monitoring/api/alerts/stats/",
        alert_views.AlertStatsAPIView.as_view(),
        name="alert_stats_api",
    ),
    # Tenant Management
    path("platform/tenants/", admin_views.TenantListView.as_view(), name="admin_tenant_list"),
    path(
        "platform/tenants/create/",
        admin_views.TenantCreateView.as_view(),
        name="admin_tenant_create",
    ),
    path(
        "platform/tenants/<uuid:pk>/",
        admin_views.TenantDetailView.as_view(),
        name="admin_tenant_detail",
    ),
    path(
        "platform/tenants/<uuid:pk>/edit/",
        admin_views.TenantUpdateView.as_view(),
        name="admin_tenant_update",
    ),
    path(
        "platform/tenants/<uuid:pk>/status/",
        admin_views.TenantStatusChangeView.as_view(),
        name="admin_tenant_status_change",
    ),
    path(
        "platform/tenants/<uuid:pk>/delete/",
        admin_views.TenantDeleteView.as_view(),
        name="admin_tenant_delete",
    ),
    # Tenant User Management
    path(
        "platform/tenants/<uuid:tenant_pk>/users/<int:user_pk>/reset-password/",
        admin_views.TenantUserPasswordResetView.as_view(),
        name="admin_tenant_user_reset_password",
    ),
    path(
        "platform/tenants/<uuid:tenant_pk>/users/<int:user_pk>/change-role/",
        admin_views.TenantUserRoleChangeView.as_view(),
        name="admin_tenant_user_change_role",
    ),
    path(
        "platform/tenants/<uuid:tenant_pk>/users/<int:user_pk>/toggle-active/",
        admin_views.TenantUserToggleActiveView.as_view(),
        name="admin_tenant_user_toggle_active",
    ),
    # Subscription Plan Management
    path(
        "platform/subscription-plans/",
        subscription_views.SubscriptionPlanListView.as_view(),
        name="admin_subscription_plan_list",
    ),
    path(
        "platform/subscription-plans/create/",
        subscription_views.SubscriptionPlanCreateView.as_view(),
        name="admin_subscription_plan_create",
    ),
    path(
        "platform/subscription-plans/<uuid:pk>/",
        subscription_views.SubscriptionPlanDetailView.as_view(),
        name="admin_subscription_plan_detail",
    ),
    path(
        "platform/subscription-plans/<uuid:pk>/edit/",
        subscription_views.SubscriptionPlanUpdateView.as_view(),
        name="admin_subscription_plan_update",
    ),
    path(
        "platform/subscription-plans/<uuid:pk>/archive/",
        subscription_views.SubscriptionPlanArchiveView.as_view(),
        name="admin_subscription_plan_archive",
    ),
    path(
        "platform/subscription-plans/<uuid:pk>/activate/",
        subscription_views.SubscriptionPlanActivateView.as_view(),
        name="admin_subscription_plan_activate",
    ),
    # Audit Log Explorer
    path(
        "platform/audit-logs/",
        audit_views.AuditLogExplorerView.as_view(),
        name="audit_log_explorer",
    ),
    path(
        "platform/audit-logs/<uuid:pk>/",
        audit_views.AuditLogDetailView.as_view(),
        name="audit_log_detail",
    ),
    path(
        "platform/audit-logs/export/",
        audit_views.AuditLogExportView.as_view(),
        name="audit_log_export",
    ),
    path(
        "platform/audit-logs/login-attempts/",
        audit_views.LoginAttemptExplorerView.as_view(),
        name="login_attempt_explorer",
    ),
    path(
        "platform/audit-logs/data-changes/",
        audit_views.DataChangeLogExplorerView.as_view(),
        name="data_change_explorer",
    ),
    path(
        "platform/audit-logs/api-requests/",
        audit_views.APIRequestLogExplorerView.as_view(),
        name="api_request_explorer",
    ),
    path(
        "platform/audit-logs/retention/",
        audit_views.AuditLogRetentionView.as_view(),
        name="audit_log_retention",
    ),
    path(
        "platform/audit-logs/retention/execute/",
        audit_views.AuditLogRetentionExecuteView.as_view(),
        name="audit_log_retention_execute",
    ),
    path(
        "platform/api/audit-logs/stats/",
        audit_views.AuditLogStatsAPIView.as_view(),
        name="audit_log_stats_api",
    ),
    # Security Monitoring
    path(
        "platform/security/dashboard/",
        security_views.security_dashboard,
        name="security_dashboard",
    ),
    path(
        "platform/security/flagged-ips/",
        security_views.flagged_ips_list,
        name="flagged_ips_list",
    ),
    path(
        "platform/security/flag-ip/",
        security_views.flag_ip,
        name="flag_ip",
    ),
    path(
        "platform/security/unflag-ip/",
        security_views.unflag_ip,
        name="unflag_ip",
    ),
    path(
        "platform/security/users/<int:user_id>/sessions/",
        security_views.user_sessions,
        name="user_sessions",
    ),
    path(
        "platform/security/users/<int:user_id>/force-logout/",
        security_views.force_logout_user,
        name="force_logout_user",
    ),
    path(
        "platform/security/brute-force-status/",
        security_views.brute_force_status,
        name="brute_force_status",
    ),
    path(
        "platform/security/users/<int:user_id>/unlock/",
        security_views.unlock_account,
        name="unlock_account",
    ),
    path(
        "platform/security/users/<int:user_id>/lock/",
        security_views.lock_account,
        name="lock_account",
    ),
    path(
        "platform/security/suspicious-activity/",
        security_views.suspicious_activity_report,
        name="suspicious_activity_report",
    ),
    # Security Monitoring API
    path(
        "platform/api/security/stats/",
        security_views.api_security_stats,
        name="api_security_stats",
    ),
    path(
        "platform/api/security/check-ip/<str:ip_address>/",
        security_views.api_check_ip,
        name="api_check_ip",
    ),
    path(
        "platform/api/security/users/<int:user_id>/sessions/",
        security_views.api_user_sessions,
        name="api_user_sessions",
    ),
    path(
        "platform/api/security/users/<int:user_id>/detect-suspicious/",
        security_views.api_detect_suspicious_activity,
        name="api_detect_suspicious_activity",
    ),
    # Tenant Subscription Management
    path(
        "platform/tenant-subscriptions/",
        tenant_subscription_views.TenantSubscriptionListView.as_view(),
        name="admin_tenant_subscription_list",
    ),
    path(
        "platform/tenant-subscriptions/<uuid:pk>/",
        tenant_subscription_views.TenantSubscriptionDetailView.as_view(),
        name="admin_tenant_subscription_detail",
    ),
    path(
        "platform/tenant-subscriptions/<uuid:pk>/change-plan/",
        tenant_subscription_views.TenantSubscriptionChangePlanView.as_view(),
        name="admin_tenant_subscription_change_plan",
    ),
    path(
        "platform/tenant-subscriptions/<uuid:pk>/limit-override/",
        tenant_subscription_views.TenantSubscriptionLimitOverrideView.as_view(),
        name="admin_tenant_subscription_limit_override",
    ),
    path(
        "platform/tenant-subscriptions/<uuid:pk>/activate/",
        tenant_subscription_views.TenantSubscriptionActivateView.as_view(),
        name="admin_tenant_subscription_activate",
    ),
    path(
        "platform/tenant-subscriptions/<uuid:pk>/deactivate/",
        tenant_subscription_views.TenantSubscriptionDeactivateView.as_view(),
        name="admin_tenant_subscription_deactivate",
    ),
    path(
        "platform/tenant-subscriptions/<uuid:pk>/clear-overrides/",
        tenant_subscription_views.TenantSubscriptionClearOverridesView.as_view(),
        name="admin_tenant_subscription_clear_overrides",
    ),
    # Dashboard
    path("dashboard/", dashboard_views.TenantDashboardView.as_view(), name="tenant_dashboard"),
    # Dashboard API endpoints
    path(
        "api/dashboard/sales-trend/",
        dashboard_views.SalesTrendChartView.as_view(),
        name="api_sales_trend",
    ),
    path(
        "api/dashboard/inventory-drill-down/",
        dashboard_views.InventoryDrillDownView.as_view(),
        name="api_inventory_drill_down",
    ),
    path(
        "api/dashboard/sales-drill-down/",
        dashboard_views.SalesDrillDownView.as_view(),
        name="api_sales_drill_down",
    ),
    path(
        "api/dashboard/stats/",
        dashboard_views.DashboardStatsView.as_view(),
        name="api_dashboard_stats",
    ),
    # Authentication endpoints
    path("api/auth/login/", views.CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/register/", views.UserRegistrationView.as_view(), name="register"),
    # User profile endpoints
    path("api/user/profile/", views.UserProfileView.as_view(), name="user_profile"),
    path("api/user/password/change/", views.PasswordChangeView.as_view(), name="password_change"),
    path("api/user/preferences/", views.UserPreferencesView.as_view(), name="user_preferences"),
    # MFA endpoints
    path("api/mfa/status/", views.MFAStatusView.as_view(), name="mfa_status"),
    path("api/mfa/enable/", views.MFAEnableView.as_view(), name="mfa_enable"),
    path("api/mfa/confirm/", views.MFAConfirmView.as_view(), name="mfa_confirm"),
    path("api/mfa/disable/", views.MFADisableView.as_view(), name="mfa_disable"),
    path("api/mfa/verify/", views.MFAVerifyView.as_view(), name="mfa_verify"),
    # Branch Management - Web Views
    path("branches/", branch_views.BranchListView.as_view(), name="branch_list"),
    path("branches/create/", branch_views.BranchCreateView.as_view(), name="branch_create"),
    path("branches/<uuid:pk>/", branch_views.BranchDetailView.as_view(), name="branch_detail"),
    path("branches/<uuid:pk>/edit/", branch_views.BranchUpdateView.as_view(), name="branch_update"),
    path(
        "branches/<uuid:pk>/delete/", branch_views.BranchDeleteView.as_view(), name="branch_delete"
    ),
    path(
        "branches/dashboard/",
        branch_views.branch_performance_dashboard,
        name="branch_performance_dashboard",
    ),
    # Terminal Management - Web Views
    path("terminals/", branch_views.TerminalListView.as_view(), name="terminal_list"),
    path("terminals/create/", branch_views.TerminalCreateView.as_view(), name="terminal_create"),
    path(
        "terminals/<uuid:pk>/edit/",
        branch_views.TerminalUpdateView.as_view(),
        name="terminal_update",
    ),
    path(
        "terminals/<uuid:pk>/delete/",
        branch_views.TerminalDeleteView.as_view(),
        name="terminal_delete",
    ),
    path(
        "terminals/<uuid:pk>/sales/",
        branch_views.TerminalSalesView.as_view(),
        name="terminal_sales",
    ),
    # Staff Assignment - Web Views
    path("staff/assignment/", branch_views.staff_assignment_view, name="staff_assignment"),
    # Branch Management - API Views
    path("api/branches/", branch_views.BranchListCreateAPIView.as_view(), name="api_branch_list"),
    path(
        "api/branches/<uuid:pk>/",
        branch_views.BranchRetrieveUpdateDestroyAPIView.as_view(),
        name="api_branch_detail",
    ),
    path(
        "api/branches/<uuid:branch_id>/inventory/",
        branch_views.branch_inventory_api,
        name="api_branch_inventory",
    ),
    # Terminal Management - API Views
    path(
        "api/terminals/", branch_views.TerminalListCreateAPIView.as_view(), name="api_terminal_list"
    ),
    path(
        "api/terminals/<uuid:pk>/",
        branch_views.TerminalRetrieveUpdateDestroyAPIView.as_view(),
        name="api_terminal_detail",
    ),
    # Staff Assignment - API Views
    path("api/staff/assign/", branch_views.assign_staff_to_branch, name="api_assign_staff"),
    # Settings - Web Views
    path("settings/", settings_views.SettingsOverviewView.as_view(), name="settings_overview"),
    path(
        "settings/shop-profile/",
        settings_views.ShopProfileView.as_view(),
        name="settings_shop_profile",
    ),
    path(
        "settings/branding/",
        settings_views.BrandingCustomizationView.as_view(),
        name="settings_branding",
    ),
    path(
        "settings/business-hours/",
        settings_views.BusinessHoursView.as_view(),
        name="settings_business_hours",
    ),
    path(
        "settings/holiday-calendar/",
        settings_views.HolidayCalendarView.as_view(),
        name="settings_holiday_calendar",
    ),
    path(
        "settings/invoice-customization/",
        settings_views.InvoiceCustomizationView.as_view(),
        name="settings_invoice_customization",
    ),
    path(
        "settings/integration/",
        settings_views.IntegrationSettingsView.as_view(),
        name="settings_integration",
    ),
    path(
        "settings/data-management/",
        settings_views.DataManagementView.as_view(),
        name="settings_data_management",
    ),
    path(
        "settings/backup-management/",
        settings_views.BackupManagementView.as_view(),
        name="settings_backup_management",
    ),
    path(
        "settings/security/",
        settings_views.SecuritySettingsView.as_view(),
        name="settings_security",
    ),
    path(
        "settings/download-template/<str:template_type>/",
        settings_views.download_template,
        name="download_template",
    ),
    # Settings - API Views
    path(
        "api/settings/tenant/",
        settings_views.TenantSettingsAPIView.as_view(),
        name="api_tenant_settings",
    ),
    path(
        "api/settings/invoice/",
        settings_views.InvoiceSettingsAPIView.as_view(),
        name="api_invoice_settings",
    ),
    path(
        "api/settings/integration/",
        settings_views.IntegrationSettingsAPIView.as_view(),
        name="api_integration_settings",
    ),
    path("api/settings/upload-logo/", settings_views.upload_logo_api, name="api_upload_logo"),
    path("api/settings/update-colors/", settings_views.update_colors_api, name="api_update_colors"),
    # Feature Flag Management
    path(
        "platform/feature-flags/",
        feature_flag_views.FeatureFlagListView.as_view(),
        name="feature_flag_list",
    ),
    path(
        "platform/feature-flags/create/",
        feature_flag_views.FeatureFlagCreateView.as_view(),
        name="feature_flag_create",
    ),
    path(
        "platform/feature-flags/<int:pk>/",
        feature_flag_views.FeatureFlagDetailView.as_view(),
        name="feature_flag_detail",
    ),
    path(
        "platform/feature-flags/<int:pk>/edit/",
        feature_flag_views.FeatureFlagUpdateView.as_view(),
        name="feature_flag_update",
    ),
    path(
        "platform/feature-flags/<int:pk>/toggle/",
        feature_flag_views.FeatureFlagToggleAPIView.as_view(),
        name="feature_flag_toggle",
    ),
    # Tenant Feature Flag Overrides
    path(
        "platform/tenant-feature-flags/",
        feature_flag_views.TenantFeatureFlagListView.as_view(),
        name="tenant_feature_flag_list",
    ),
    path(
        "platform/tenant-feature-flags/create/",
        feature_flag_views.TenantFeatureFlagCreateView.as_view(),
        name="tenant_feature_flag_create",
    ),
    # A/B Testing
    path(
        "platform/ab-tests/",
        feature_flag_views.ABTestListView.as_view(),
        name="ab_test_list",
    ),
    path(
        "platform/ab-tests/create/",
        feature_flag_views.ABTestCreateView.as_view(),
        name="ab_test_create",
    ),
    path(
        "platform/ab-tests/<int:pk>/",
        feature_flag_views.ABTestDetailView.as_view(),
        name="ab_test_detail",
    ),
    path(
        "platform/ab-tests/<int:pk>/stop/",
        feature_flag_views.ABTestStopView.as_view(),
        name="ab_test_stop",
    ),
    # Emergency Kill Switch
    path(
        "platform/kill-switches/",
        feature_flag_views.EmergencyKillSwitchListView.as_view(),
        name="kill_switch_list",
    ),
    path(
        "platform/kill-switches/create/",
        feature_flag_views.EmergencyKillSwitchCreateView.as_view(),
        name="kill_switch_create",
    ),
    path(
        "platform/kill-switches/<int:pk>/re-enable/",
        feature_flag_views.EmergencyKillSwitchReEnableView.as_view(),
        name="kill_switch_re_enable",
    ),
    # Metrics Dashboard
    path(
        "platform/feature-flags/metrics/",
        feature_flag_views.FeatureFlagMetricsDashboardView.as_view(),
        name="feature_flag_metrics",
    ),
    # API Endpoints
    path(
        "platform/api/feature-flags/stats/",
        feature_flag_views.FeatureFlagStatsAPIView.as_view(),
        name="feature_flag_stats_api",
    ),
    # Announcement Management
    path(
        "platform/announcements/",
        announcement_views.AnnouncementListView.as_view(),
        name="announcement_list",
    ),
    path(
        "platform/announcements/create/",
        announcement_views.AnnouncementCreateView.as_view(),
        name="announcement_create",
    ),
    path(
        "platform/announcements/<uuid:pk>/",
        announcement_views.AnnouncementDetailView.as_view(),
        name="announcement_detail",
    ),
    path(
        "platform/announcements/<uuid:pk>/edit/",
        announcement_views.AnnouncementUpdateView.as_view(),
        name="announcement_update",
    ),
    path(
        "platform/announcements/<uuid:pk>/send/",
        announcement_views.announcement_send,
        name="announcement_send",
    ),
    path(
        "platform/announcements/<uuid:pk>/cancel/",
        announcement_views.announcement_cancel,
        name="announcement_cancel",
    ),
    # Direct Message Management
    path(
        "platform/direct-messages/",
        announcement_views.DirectMessageListView.as_view(),
        name="direct_message_list",
    ),
    path(
        "platform/direct-messages/create/",
        announcement_views.DirectMessageCreateView.as_view(),
        name="direct_message_create",
    ),
    path(
        "platform/direct-messages/<uuid:pk>/",
        announcement_views.DirectMessageDetailView.as_view(),
        name="direct_message_detail",
    ),
    path(
        "platform/direct-messages/<uuid:pk>/send/",
        announcement_views.direct_message_send,
        name="direct_message_send",
    ),
    # Bulk Messaging
    path(
        "platform/bulk-messages/create/",
        announcement_views.BulkMessageCreateView.as_view(),
        name="bulk_message_create",
    ),
    path(
        "platform/bulk-messages/preview/",
        announcement_views.bulk_message_preview,
        name="bulk_message_preview",
    ),
    path(
        "platform/communication-templates/<uuid:pk>/apply-to-bulk/",
        announcement_views.template_apply_to_bulk,
        name="template_apply_to_bulk",
    ),
    # Communication Template Management
    path(
        "platform/communication-templates/",
        announcement_views.CommunicationTemplateListView.as_view(),
        name="template_list",
    ),
    path(
        "platform/communication-templates/create/",
        announcement_views.CommunicationTemplateCreateView.as_view(),
        name="template_create",
    ),
    path(
        "platform/communication-templates/<uuid:pk>/",
        announcement_views.CommunicationTemplateDetailView.as_view(),
        name="template_detail",
    ),
    path(
        "platform/communication-templates/<uuid:pk>/edit/",
        announcement_views.CommunicationTemplateUpdateView.as_view(),
        name="template_update",
    ),
    path(
        "platform/communication-templates/<uuid:pk>/use/",
        announcement_views.template_use,
        name="template_use",
    ),
    # Communication Log
    path(
        "platform/communication-logs/",
        announcement_views.CommunicationLogListView.as_view(),
        name="communication_log_list",
    ),
    # Tenant-Facing Announcement Display
    path(
        "announcements/",
        announcement_views.tenant_announcement_center,
        name="tenant_announcement_center",
    ),
    path(
        "announcements/<uuid:pk>/",
        announcement_views.tenant_announcement_detail,
        name="tenant_announcement_detail",
    ),
    path(
        "announcements/<uuid:pk>/dismiss/",
        announcement_views.tenant_announcement_dismiss,
        name="tenant_announcement_dismiss",
    ),
    path(
        "announcements/<uuid:pk>/acknowledge/",
        announcement_views.tenant_announcement_acknowledge,
        name="tenant_announcement_acknowledge",
    ),
    # Tenant Announcement API
    path(
        "api/announcements/active/",
        announcement_views.tenant_active_announcements_api,
        name="api_tenant_active_announcements",
    ),
    # Webhook Management
    path("webhooks/", include("apps.core.webhook_urls")),
]
