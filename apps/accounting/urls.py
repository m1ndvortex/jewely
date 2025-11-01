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
    # Supplier Accounting Views (Task 2.3, 2.8)
    path("suppliers/", views.supplier_list, name="supplier_list"),
    path(
        "suppliers/<uuid:supplier_id>/accounting/",
        views.supplier_accounting_detail,
        name="supplier_accounting_detail",
    ),
    path(
        "suppliers/<uuid:supplier_id>/statement/",
        views.supplier_statement,
        name="supplier_statement",
    ),
    path(
        "suppliers/<uuid:supplier_id>/statement/pdf/",
        views.supplier_statement_pdf,
        name="supplier_statement_pdf",
    ),
    # Bill Management Views (Task 2.5)
    path("bills/", views.bill_list, name="bill_list"),
    path("bills/create/", views.bill_create, name="bill_create"),
    path("bills/<uuid:pk>/", views.bill_detail, name="bill_detail"),
    path("bills/<uuid:pk>/pay/", views.bill_pay, name="bill_pay"),
    # Aged Payables Report (Task 2.7)
    path("reports/aged-payables/", views.aged_payables_report, name="aged_payables_report"),
    # Customer Accounting Views (Task 3.3)
    path(
        "customers/<uuid:customer_id>/accounting/",
        views.customer_accounting_detail,
        name="customer_accounting_detail",
    ),
    path(
        "customers/<uuid:customer_id>/statement/",
        views.customer_statement,
        name="customer_statement",
    ),
    path(
        "api/customers/<uuid:customer_id>/check-credit-limit/",
        views.check_customer_credit_limit_api,
        name="check_customer_credit_limit_api",
    ),
    # Invoice Management Views (Task 3.5)
    path("invoices/", views.invoice_list, name="invoice_list"),
    path("invoices/create/", views.invoice_create, name="invoice_create"),
    path("invoices/<uuid:invoice_id>/", views.invoice_detail, name="invoice_detail"),
    path(
        "invoices/<uuid:invoice_id>/receive-payment/",
        views.invoice_receive_payment,
        name="invoice_receive_payment",
    ),
    # Credit Memo Views (Task 3.5)
    path("credit-memos/create/", views.credit_memo_create, name="credit_memo_create"),
    path(
        "credit-memos/<uuid:credit_memo_id>/",
        views.credit_memo_detail,
        name="credit_memo_detail",
    ),
    path(
        "credit-memos/<uuid:credit_memo_id>/apply/<uuid:invoice_id>/",
        views.credit_memo_apply,
        name="credit_memo_apply",
    ),
]
