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
    path("accounts/add/", views.add_account, name="add_account"),
    path("accounts/<str:account_code>/edit/", views.edit_account, name="edit_account"),
    # Journal Entries (legacy redirect)
    path("journal-entries/", views.journal_entries, name="journal_entries"),
    # Manual Journal Entry Views (Task 1.2)
    path("journal-entries/list/", views.journal_entry_list, name="journal_entry_list"),
    path("journal-entries/create/", views.journal_entry_create, name="journal_entry_create"),
    path("journal-entries/<uuid:pk>/", views.journal_entry_detail, name="journal_entry_detail"),
    path("journal-entries/<uuid:pk>/edit/", views.journal_entry_edit, name="journal_entry_edit"),
    path(
        "journal-entries/<uuid:pk>/delete/", views.journal_entry_delete, name="journal_entry_delete"
    ),
    path("journal-entries/<uuid:pk>/post/", views.journal_entry_post, name="journal_entry_post"),
    path(
        "journal-entries/<uuid:pk>/reverse/",
        views.journal_entry_reverse,
        name="journal_entry_reverse",
    ),
    # General Ledger
    path("general-ledger/", views.general_ledger, name="general_ledger"),
    # Accounts Payable
    path("payables/", views.accounts_payable, name="accounts_payable"),
    # Accounts Receivable
    path("receivables/", views.accounts_receivable, name="accounts_receivable"),
    # Bank Reconciliation
    path("bank-reconciliation/", views.bank_reconciliation, name="bank_reconciliation"),
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
