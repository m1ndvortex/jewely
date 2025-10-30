"""
URL patterns for the accounting module.
"""

from django.urls import path

from . import views

app_name = "accounting"

urlpatterns = [
    # Main Dashboard
    path("", views.accounting_dashboard, name="dashboard"),
    # Financial Reports
    path("reports/", views.financial_reports, name="financial_reports"),
    # Chart of Accounts
    path("accounts/", views.chart_of_accounts, name="chart_of_accounts"),
    # Configuration
    path("config/", views.accounting_configuration, name="configuration"),
    # API Endpoints
    path(
        "api/account/<str:account_code>/balance/",
        views.account_balance_api,
        name="account_balance_api",
    ),
    path("api/setup/", views.setup_accounting_api, name="setup_accounting_api"),
    # Export Endpoints
    path("reports/export/pdf/", views.export_financial_reports_pdf, name="export_reports_pdf"),
    path(
        "reports/export/excel/", views.export_financial_reports_excel, name="export_reports_excel"
    ),
]
