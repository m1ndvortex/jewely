from django.urls import path

from rest_framework_simplejwt.views import TokenRefreshView

from . import branch_views, dashboard_views, views

app_name = "core"

urlpatterns = [
    # Basic views
    path("", views.home, name="home"),
    path("health/", views.health_check, name="health_check"),
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
]
