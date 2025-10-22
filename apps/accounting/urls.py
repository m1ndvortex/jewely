"""
URL patterns for the accounting module.
"""

from django.urls import path

from . import views

app_name = "accounting"

urlpatterns = [
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
]
