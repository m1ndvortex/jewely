"""
URL patterns for the reporting app.

Implements Requirement 15: Advanced Reporting and Analytics
- Report list and detail views
- Report execution endpoints
- Pre-built report access
"""

from django.urls import path

from . import views

app_name = "reporting"

urlpatterns = [
    # Report management
    path("", views.ReportListView.as_view(), name="report_list"),
    path("create/", views.ReportCreateView.as_view(), name="report_create"),
    path("<uuid:pk>/", views.ReportDetailView.as_view(), name="report_detail"),
    path("<uuid:pk>/edit/", views.ReportUpdateView.as_view(), name="report_edit"),
    path("<uuid:pk>/delete/", views.ReportDeleteView.as_view(), name="report_delete"),
    # Report execution
    path("<uuid:pk>/execute/", views.ReportExecuteView.as_view(), name="report_execute"),
    path(
        "execution/<uuid:pk>/", views.ReportExecutionDetailView.as_view(), name="execution_detail"
    ),
    path(
        "execution/<uuid:pk>/download/",
        views.ReportDownloadView.as_view(),
        name="execution_download",
    ),
    # Pre-built reports
    path("prebuilt/", views.PrebuiltReportsView.as_view(), name="prebuilt_reports"),
    path("prebuilt/sales-summary/", views.SalesSummaryReportView.as_view(), name="sales_summary"),
    path(
        "prebuilt/sales-by-product/",
        views.SalesByProductReportView.as_view(),
        name="sales_by_product",
    ),
    path(
        "prebuilt/sales-by-employee/",
        views.SalesByEmployeeReportView.as_view(),
        name="sales_by_employee",
    ),
    path(
        "prebuilt/sales-by-branch/", views.SalesByBranchReportView.as_view(), name="sales_by_branch"
    ),
    path(
        "prebuilt/inventory-valuation/",
        views.InventoryValuationReportView.as_view(),
        name="inventory_valuation",
    ),
    path(
        "prebuilt/inventory-turnover/",
        views.InventoryTurnoverReportView.as_view(),
        name="inventory_turnover",
    ),
    path("prebuilt/dead-stock/", views.DeadStockReportView.as_view(), name="dead_stock"),
    path(
        "prebuilt/financial-summary/",
        views.FinancialSummaryReportView.as_view(),
        name="financial_summary",
    ),
    path(
        "prebuilt/revenue-trends/", views.RevenueTrendsReportView.as_view(), name="revenue_trends"
    ),
    path(
        "prebuilt/expense-breakdown/",
        views.ExpenseBreakdownReportView.as_view(),
        name="expense_breakdown",
    ),
    path("prebuilt/top-customers/", views.TopCustomersReportView.as_view(), name="top_customers"),
    path(
        "prebuilt/customer-acquisition/",
        views.CustomerAcquisitionReportView.as_view(),
        name="customer_acquisition",
    ),
    path(
        "prebuilt/loyalty-analytics/",
        views.LoyaltyAnalyticsReportView.as_view(),
        name="loyalty_analytics",
    ),
    # Report scheduling
    path("schedules/", views.ReportScheduleListView.as_view(), name="schedule_list"),
    path("schedules/create/", views.ReportScheduleCreateView.as_view(), name="schedule_create"),
    path("schedules/<uuid:pk>/", views.ReportScheduleDetailView.as_view(), name="schedule_detail"),
    path(
        "schedules/<uuid:pk>/edit/", views.ReportScheduleUpdateView.as_view(), name="schedule_edit"
    ),
    path(
        "schedules/<uuid:pk>/delete/",
        views.ReportScheduleDeleteView.as_view(),
        name="schedule_delete",
    ),
    # Dashboard
    path("dashboard/", views.ReportDashboardView.as_view(), name="dashboard"),
]
