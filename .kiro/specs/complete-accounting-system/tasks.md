# Implementation Plan

## Phase 1: Manual Journal Entry System (Foundation)

- [ ] 1. Create forms.py file and base journal entry forms
- [x] 1.1 Create apps/accounting/forms.py file
  - Create JournalEntryForm with description, date, reference fields
  - Create JournalEntryLineFormSet for dynamic line items (account, debit, credit, description)
  - Add JavaScript validation to ensure debits equal credits
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 1.2 Create journal entry views (backend)
  - Implement journal_entry_list view with filtering by date, status, account
  - Implement journal_entry_create view with formset handling
  - Implement journal_entry_detail view (read-only)
  - Implement journal_entry_post view to post entries to GL
  - Implement journal_entry_reverse view to create reversing entries
  - Add tenant filtering to all queries
  - Add audit logging for all operations
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

- [x] 1.3 Create journal entry templates (frontend)
  - Create templates/accounting/journal_entries/list.html with filters and status badges
  - Create templates/accounting/journal_entries/form.html with dynamic line addition (HTMX)
  - Create templates/accounting/journal_entries/detail.html with audit trail display
  - Create templates/accounting/journal_entries/confirm_post.html modal
  - Add TailwindCSS styling for all templates
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

- [x] 1.4 Add journal entry URLs
  - Add URL patterns for all journal entry views
  - Update accounting app urls.py
  - _Requirements: 1.1_

- [ ] 1.5 Test manual journal entry creation end-to-end
  - Create a manual journal entry via UI
  - Verify debits equal credits validation
  - Post the entry and verify GL updates
  - Verify tenant isolation
  - Verify audit trail
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.7, 1.8_

## Phase 2: Supplier Management and Bills (Accounts Payable)

- [ ] 2. Extend Supplier model and create Bill models with migrations
- [x] 2.1 Extend existing Supplier model with accounting fields
  - Create migration to add fields to apps/procurement/models.Supplier:
    - default_expense_account (CharField, max_length=20, blank=True)
    - is_1099_vendor (BooleanField, default=False)
  - Run migration
  - NOTE: Supplier model already exists with tenant FK, name, contact_person, email, phone, address, tax_id, payment_terms, is_active, notes
  - _Requirements: 2.1, 2.7, 14.1, 14.2_

- [x] 2.2 Create Bill models
  - Add Bill model with tenant FK, supplier FK (to apps.procurement.models.Supplier), bill_number, dates, amounts, status
  - Add BillLine model for line items
  - Add BillPayment model for payment tracking
  - Add custom managers for tenant filtering
  - Create and run migrations
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.7_

- [x] 2.3 Create supplier accounting views (backend)
  - Implement supplier_accounting_detail view (extends existing supplier detail with accounting info)
  - Implement supplier_statement view
  - Add tenant filtering to all queries
  - Add audit logging
  - NOTE: Basic supplier CRUD already exists in procurement app
  - _Requirements: 2.7, 14.1, 14.2, 14.3, 14.7, 14.8_

- [x] 2.4 Create supplier accounting templates (frontend)
  - Create templates/accounting/suppliers/ directory
  - Create accounting_detail.html (shows bills, payments, balance)
  - Create statement.html template
  - Add search and filter functionality
  - Add TailwindCSS styling
  - _Requirements: 14.1, 14.2, 14.3, 14.8_

- [x] 2.5 Create bill management forms and views (backend)
  - Create BillForm and BillLineFormSet in forms.py (reference apps.procurement.models.Supplier)
  - Create BillPaymentForm in forms.py
  - Implement bill_list, bill_create, bill_detail, bill_pay views
  - Implement automatic journal entry creation on bill save
  - Implement automatic journal entry creation on payment
  - Add tenant filtering and audit logging
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.6, 2.7, 2.8_

- [x] 2.6 Create bill management templates (frontend)
  - Create templates/accounting/bills/ directory
  - Create list.html with aging columns and status badges
  - Create form.html with dynamic line items (HTMX)
  - Create detail.html with payment history
  - Create payment_form.html for recording payments
  - Add TailwindCSS styling
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.8_

- [x] 2.7 Create aged payables report (backend + frontend)
  - Implement aged_payables_report view with 30/60/90/90+ day buckets
  - Create templates/accounting/reports/aged_payables.html
  - Add PDF/Excel export functionality
  - _Requirements: 2.5_

- [x] 2.8 Create supplier statement report (backend + frontend)
  - Implement supplier_statement view
  - Create templates/accounting/reports/supplier_statement.html
  - Add PDF export functionality
  - _Requirements: 2.8, 14.3_

- [ ] 2.9 Add AP URLs and test end-to-end
  - Add URL patterns for supplier accounting and bills
  - Test: View supplier → Create bill → Record payment → View aging report
  - Verify journal entries created correctly
  - Verify tenant isolation
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.7_



## Phase 3: Customer Management and Invoices (Accounts Receivable)

- [ ] 3. Extend Customer model and create Invoice models with migrations
- [x] 3.1 Extend existing Customer model with accounting fields
  - Create migration to add fields to apps/crm/models.Customer:
    - credit_limit (DecimalField, max_digits=12, decimal_places=2, default=0)
    - payment_terms (CharField, max_length=50, default='NET30')
    - tax_exempt (BooleanField, default=False)
    - exemption_certificate (FileField, upload_to='customer_tax_exemptions/', blank=True)
  - Run migration
  - NOTE: Customer model already exists with tenant FK, customer_number, first_name, last_name, email, phone, address, loyalty_tier, store_credit, tags, notes, is_active
  - _Requirements: 3.1, 3.7, 15.1, 15.2_

- [x] 3.2 Create Invoice models
  - Add Invoice model with tenant FK, customer FK (to apps.crm.models.Customer), invoice_number, dates, amounts, status
  - Add InvoiceLine model for line items
  - Add InvoicePayment model for payment tracking
  - Add CreditMemo model for customer credits
  - Add custom managers for tenant filtering
  - Create and run migrations
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6, 3.7_

- [x] 3.3 Create customer accounting views (backend)
  - Implement customer_accounting_detail view (extends existing customer detail with accounting info)
  - Implement customer_statement view
  - Add credit limit validation
  - Add tenant filtering and audit logging
  - NOTE: Basic customer CRUD already exists in CRM app
  - _Requirements: 3.7, 15.1, 15.2, 15.3, 15.4, 15.7, 15.8_

- [x] 3.4 Create customer accounting templates (frontend)
  - Create templates/accounting/customers/ directory
  - Create accounting_detail.html (shows invoices, payments, balance, credit limit)
  - Create statement.html template
  - Add search and filter functionality
  - Display credit limit and current balance
  - Add TailwindCSS styling
  - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.8_

- [x] 3.5 Create invoice management forms and views (backend)
  - Create InvoiceForm and InvoiceLineFormSet in forms.py (reference apps.crm.models.Customer)
  - Create InvoicePaymentForm and CreditMemoForm in forms.py
  - Implement invoice_list, invoice_create, invoice_detail, invoice_receive_payment views
  - Implement automatic journal entry creation on invoice save
  - Implement automatic journal entry creation on payment
  - Implement credit memo application logic
  - Add credit limit checking
  - Add tenant filtering and audit logging
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6, 3.7, 3.8_

- [x] 3.6 Create invoice management templates (frontend)
  - Create templates/accounting/invoices/ directory
  - Create list.html with aging columns and status badges
  - Create form.html with dynamic line items and tax calculation (HTMX)
  - Create detail.html with payment history
  - Create payment_form.html for recording payments
  - Create credit_memo_form.html for creating credits
  - Add TailwindCSS styling
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6, 3.8_

- [x] 3.7 Create aged receivables report (backend + frontend)
  - Implement aged_receivables_report view with 30/60/90/90+ day buckets
  - Create templates/accounting/reports/aged_receivables.html
  - Add PDF/Excel export functionality
  - _Requirements: 3.5_

- [ ] 3.8 Create customer statement report (backend + frontend)
  - Implement customer_statement view
  - Create templates/accounting/reports/customer_statement.html
  - Add PDF export functionality
  - _Requirements: 3.8, 15.3_

- [ ] 3.9 Add AR URLs and test end-to-end
  - Add URL patterns for customer accounting and invoices
  - Test: View customer → Create invoice → Record payment → Apply credit → View aging report
  - Verify journal entries created correctly
  - Verify credit limit enforcement
  - Verify tenant isolation
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

## Phase 4: Bank Reconciliation System

- [ ] 4. Create bank reconciliation models with migrations
- [ ] 4.1 Create BankAccount model
  - Add BankAccount model extending django-ledger's BankAccountModel
  - Include tenant FK, account details, balances
  - Add custom manager for tenant filtering
  - Create and run migration
  - _Requirements: 4.1, 6.1, 6.7_

- [ ] 4.2 Create bank reconciliation models
  - Add BankTransaction model with reconciliation status
  - Add BankReconciliation model for reconciliation sessions
  - Add BankStatementImport model for import tracking
  - Add custom managers for tenant filtering
  - Create and run migrations
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.7_

- [ ] 4.3 Create bank account management (backend)
  - Create BankAccountForm in forms.py
  - Implement bank_account_list, bank_account_create, bank_account_detail views
  - Add tenant filtering and audit logging
  - _Requirements: 6.1, 6.3, 6.6, 6.7_

- [ ] 4.4 Create bank account management templates (frontend)
  - Create templates/accounting/bank_accounts/ directory
  - Create list.html, form.html, detail.html templates
  - Display current balance, reconciled balance, unreconciled transactions
  - Add TailwindCSS styling
  - _Requirements: 6.1, 6.3, 6.6_

- [ ] 4.5 Create bank reconciliation service and views (backend)
  - Create BankReconciliationService in services.py
  - Implement start_reconciliation, mark_reconciled, complete_reconciliation methods
  - Implement bank_reconciliation_start, bank_reconciliation_detail views
  - Implement transaction matching logic
  - Add tenant filtering and audit logging
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.7, 4.8_

- [ ] 4.6 Create bank reconciliation templates (frontend)
  - Update templates/accounting/bank_reconciliation.html
  - Add reconciliation interface with checkboxes for marking transactions
  - Add statement balance input
  - Add reconciliation summary (beginning balance, cleared transactions, ending balance)
  - Add HTMX for dynamic transaction marking
  - Add TailwindCSS styling
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 4.7 Create bank statement import (backend + frontend)
  - Create BankStatementImportForm in forms.py
  - Implement bank_statement_import view with CSV/OFX/QFX parsing
  - Implement auto-matching logic
  - Create templates/accounting/bank_accounts/import.html
  - _Requirements: 4.3, 6.4_

- [ ] 4.8 Create reconciliation report (backend + frontend)
  - Implement bank_reconciliation_report view
  - Create templates/accounting/reports/bank_reconciliation.html
  - Add PDF export functionality
  - _Requirements: 4.4, 4.6_

- [ ] 4.9 Add bank reconciliation URLs and test end-to-end
  - Add URL patterns for bank accounts and reconciliation
  - Test: Create bank account → Import statement → Mark transactions → Complete reconciliation
  - Verify reconciliation balance
  - Verify tenant isolation
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_



## Phase 5: Fixed Assets and Depreciation

- [ ] 5. Create fixed asset models with migrations
- [ ] 5.1 Create FixedAsset model
  - Add FixedAsset model to apps/accounting/models.py
  - Include tenant FK, asset details, acquisition info, depreciation method
  - Add DepreciationSchedule model for tracking depreciation
  - Add AssetDisposal model for disposal tracking
  - Add custom managers for tenant filtering
  - Create and run migrations
  - _Requirements: 5.1, 5.2, 5.4, 5.7_

- [ ] 5.2 Create fixed asset service (backend)
  - Create FixedAssetService in services.py
  - Implement calculate_depreciation method (straight-line, declining balance)
  - Implement run_monthly_depreciation method
  - Implement dispose_asset method with gain/loss calculation
  - Add automatic journal entry creation for depreciation
  - Add tenant filtering and audit logging
  - _Requirements: 5.2, 5.3, 5.4, 5.7, 5.8_

- [ ] 5.3 Create fixed asset management forms and views (backend)
  - Create FixedAssetForm and AssetDisposalForm in forms.py
  - Implement fixed_asset_list, fixed_asset_create, fixed_asset_detail views
  - Implement fixed_asset_dispose view
  - Implement run_depreciation view
  - Add tenant filtering and audit logging
  - _Requirements: 5.1, 5.4, 5.6, 5.7_

- [ ] 5.4 Create fixed asset management templates (frontend)
  - Create templates/accounting/fixed_assets/ directory
  - Create list.html with current book value and accumulated depreciation
  - Create form.html for asset registration
  - Create detail.html with depreciation history
  - Create disposal_form.html for recording disposal
  - Add TailwindCSS styling
  - _Requirements: 5.1, 5.4, 5.5, 5.6_

- [ ] 5.5 Create depreciation schedule report (backend + frontend)
  - Implement depreciation_schedule view
  - Create templates/accounting/reports/depreciation_schedule.html
  - Show projected depreciation for each asset
  - Add PDF/Excel export functionality
  - _Requirements: 5.5, 5.6_

- [ ] 5.6 Create Celery task for automatic depreciation
  - Create celery task for monthly depreciation run
  - Schedule task to run on first day of each month
  - Add error handling and logging
  - _Requirements: 5.3, 5.8_

- [ ] 5.7 Add fixed assets URLs and test end-to-end
  - Add URL patterns for fixed assets
  - Test: Register asset → Run depreciation → View schedule → Dispose asset
  - Verify journal entries created correctly
  - Verify depreciation calculations
  - Verify tenant isolation
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

## Phase 6: Tax Management System

- [ ] 6. Create tax management models with migrations
- [ ] 6.1 Create TaxCode model
  - Add TaxCode model to apps/accounting/models.py
  - Include tenant FK, code, name, rate, tax_account, jurisdiction
  - Add TaxJurisdiction model
  - Add TaxPayment model for tax remittance tracking
  - Add custom managers for tenant filtering
  - Create and run migrations
  - _Requirements: 8.1, 8.2, 8.6, 8.7_

- [ ] 6.2 Create tax service (backend)
  - Create TaxService in services.py
  - Implement calculate_tax method
  - Implement apply_multi_jurisdiction_tax method
  - Implement generate_tax_report method
  - Implement record_tax_payment method with journal entry creation
  - Add tenant filtering
  - _Requirements: 8.1, 8.2, 8.3, 8.5, 8.6, 8.7_

- [ ] 6.3 Create tax management forms and views (backend)
  - Create TaxCodeForm and TaxPaymentForm in forms.py
  - Implement tax_code_list, tax_code_create, tax_code_edit views
  - Implement tax_report view
  - Implement tax_payment_record view
  - Add tenant filtering and audit logging
  - _Requirements: 8.1, 8.5, 8.6, 8.7_

- [ ] 6.4 Create tax management templates (frontend)
  - Create templates/accounting/tax/ directory
  - Create tax_codes/list.html, tax_codes/form.html
  - Create tax_report.html with breakdown by jurisdiction
  - Create tax_payment_form.html
  - Add TailwindCSS styling
  - _Requirements: 8.1, 8.5, 8.6_

- [ ] 6.5 Update invoice/bill forms to use tax codes
  - Modify InvoiceForm to include tax code selection
  - Modify BillForm to include tax code selection
  - Add automatic tax calculation using TaxService
  - Update templates to show tax breakdown
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [ ] 6.6 Add tax URLs and test end-to-end
  - Add URL patterns for tax management
  - Test: Create tax code → Create invoice with tax → Generate tax report → Record payment
  - Verify tax calculations
  - Verify multi-jurisdiction tax
  - Verify tenant isolation
  - _Requirements: 8.1, 8.2, 8.3, 8.5, 8.6, 8.7_

## Phase 7: Accounting Period Management

- [ ] 7. Create accounting period models with migrations
- [ ] 7.1 Create AccountingPeriod model
  - Add AccountingPeriod model to apps/accounting/models.py
  - Include tenant FK, period_type, dates, fiscal_year, status
  - Add PeriodLock model for lock tracking
  - Add custom managers for tenant filtering
  - Create and run migrations
  - _Requirements: 9.1, 9.2, 9.3, 9.7_

- [ ] 7.2 Create period service (backend)
  - Create PeriodService in services.py
  - Implement create_periods method to generate periods for fiscal year
  - Implement close_period method
  - Implement lock_period method
  - Implement unlock_period method with reason tracking
  - Implement validate_transaction_date method
  - Add tenant filtering and audit logging
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.7_

- [ ] 7.3 Create period management forms and views (backend)
  - Create PeriodCloseForm and PeriodUnlockForm in forms.py
  - Implement period_list, period_close, period_lock, period_unlock views
  - Add validation to prevent transactions in closed periods
  - Add tenant filtering and audit logging
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.7, 9.8_

- [ ] 7.4 Create period management templates (frontend)
  - Create templates/accounting/periods/ directory
  - Create list.html with period status indicators
  - Create close_confirm.html modal
  - Create unlock_form.html with reason field
  - Add TailwindCSS styling
  - _Requirements: 9.1, 9.2, 9.3, 9.5, 9.8_

- [ ] 7.5 Integrate period validation into all transaction views
  - Add period validation to journal entry creation
  - Add period validation to bill creation
  - Add period validation to invoice creation
  - Display appropriate error messages
  - _Requirements: 9.4, 9.5_

- [ ] 7.6 Create year-end close view (backend + frontend)
  - Implement year_end_close view using existing close_fiscal_year service
  - Create templates/accounting/periods/year_end_close.html
  - Add confirmation and summary display
  - _Requirements: 9.6_

- [ ] 7.7 Add period URLs and test end-to-end
  - Add URL patterns for period management
  - Test: Create periods → Close period → Attempt transaction in closed period → Unlock period
  - Verify period validation
  - Verify year-end close
  - Verify tenant isolation
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_



## Phase 8: Budgeting and Forecasting

- [ ] 8. Create budgeting models with migrations
- [ ] 8.1 Create Budget models
  - Add Budget model to apps/accounting/models.py
  - Include tenant FK, name, fiscal_year, status
  - Add BudgetLine model for account-level budgets by period
  - Add BudgetScenario model for multiple scenarios
  - Add custom managers for tenant filtering
  - Create and run migrations
  - _Requirements: 10.1, 10.4, 10.7_

- [ ] 8.2 Create budget service (backend)
  - Create BudgetService in services.py
  - Implement create_budget method
  - Implement copy_budget method with adjustment percentage
  - Implement get_budget_vs_actual method for variance analysis
  - Implement forecast_cash_flow method
  - Add tenant filtering
  - _Requirements: 10.1, 10.2, 10.3, 10.5, 10.7, 10.8_

- [ ] 8.3 Create budget management forms and views (backend)
  - Create BudgetForm, BudgetLineFormSet, BudgetCopyForm in forms.py
  - Implement budget_list, budget_create, budget_edit views
  - Implement budget_copy view
  - Implement budget_vs_actual_report view
  - Add tenant filtering and audit logging
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.7_

- [ ] 8.4 Create budget management templates (frontend)
  - Create templates/accounting/budgets/ directory
  - Create list.html with budget status
  - Create form.html with dynamic budget line entry (HTMX)
  - Create copy_form.html for copying budgets
  - Create budget_vs_actual.html with variance highlighting
  - Add TailwindCSS styling
  - _Requirements: 10.1, 10.2, 10.3, 10.6_

- [ ] 8.5 Create cash flow forecast (backend + frontend)
  - Implement cash_flow_forecast view
  - Create templates/accounting/reports/cash_flow_forecast.html
  - Show projected cash position based on receivables, payables, recurring transactions
  - Add chart visualization
  - _Requirements: 10.8_

- [ ] 8.6 Add budget URLs and test end-to-end
  - Add URL patterns for budgets
  - Test: Create budget → Enter budget lines → Copy budget → View variance report
  - Verify variance calculations
  - Verify cash flow forecast
  - Verify tenant isolation
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.7_

## Phase 9: Advanced Financial Reporting

- [ ] 9. Create advanced reporting service and views
- [ ] 9.1 Enhance ReportingService (backend)
  - Add generate_comparative_financials method
  - Add generate_departmental_pl method
  - Add calculate_financial_ratios method
  - Add generate_gl_detail_report method
  - Add tenant filtering
  - _Requirements: 11.2, 11.3, 11.4, 11.5, 11.7_

- [ ] 9.2 Create comparative financial statements (backend + frontend)
  - Implement comparative_financials view
  - Create templates/accounting/reports/comparative_financials.html
  - Show current period alongside prior periods
  - Add variance columns
  - Add PDF/Excel export
  - _Requirements: 11.3_

- [ ] 9.3 Create departmental P&L report (backend + frontend)
  - Implement departmental_pl view
  - Create templates/accounting/reports/departmental_pl.html
  - Show P&L by department/branch
  - Add PDF/Excel export
  - _Requirements: 11.4_

- [ ] 9.4 Create financial ratios dashboard (backend + frontend)
  - Implement financial_ratios view
  - Create templates/accounting/reports/financial_ratios.html
  - Calculate and display liquidity, profitability, efficiency ratios
  - Add trend charts
  - _Requirements: 11.5_

- [ ] 9.5 Create GL detail report (backend + frontend)
  - Implement gl_detail_report view
  - Create templates/accounting/reports/gl_detail.html
  - Show all transactions for selected account with drill-down
  - Add PDF/Excel export
  - _Requirements: 11.6, 11.7_

- [ ] 9.6 Add drill-down functionality to existing reports
  - Update balance sheet template to link to GL detail
  - Update income statement template to link to GL detail
  - Update trial balance template to link to GL detail
  - Add HTMX for modal drill-down
  - _Requirements: 11.6_

- [ ] 9.7 Add advanced reporting URLs and test end-to-end
  - Add URL patterns for advanced reports
  - Test: Generate comparative statements → View departmental P&L → Calculate ratios → Drill down
  - Verify calculations
  - Verify exports
  - Verify tenant isolation
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_

## Phase 10: Audit Trail and Compliance

- [ ] 10. Use existing audit trail system and create compliance models
- [ ] 10.1 Verify existing AuditLog usage
  - IMPORTANT: AuditLog already exists in apps/core/audit_models.py
  - DO NOT create new AuditLog model
  - Verify existing AuditLog has all needed fields (tenant, user, timestamp, ip_address, category, action, severity, description, before_value, after_value)
  - Create SensitiveOperation model for operations requiring approval
  - Add custom manager for tenant filtering to SensitiveOperation
  - Create and run migration for SensitiveOperation only
  - _Requirements: 12.1, 12.2, 12.6, 12.7_

- [ ] 10.2 Create audit service (backend)
  - Create AuditService in services.py
  - Use apps.core.audit_models.AuditLog (import from core)
  - Implement log_change method (wrapper around existing AuditLog)
  - Implement get_audit_trail method with filtering
  - Implement export_audit_trail method
  - Implement detect_suspicious_activity method
  - Add tenant filtering
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.7, 12.8_

- [ ] 10.3 Integrate audit logging into all models
  - Add signal handlers to log all create/update/delete operations
  - Use apps.core.audit_models.AuditLog for logging
  - Capture before and after values
  - Capture user and IP address
  - Add to all financial models (JournalEntry, Bill, Invoice, etc.)
  - NOTE: Some audit logging already exists in views (see journal_entry views)
  - _Requirements: 12.1, 12.7_

- [ ] 10.4 Create audit trail views (backend)
  - Implement audit_trail view with filtering (query apps.core.audit_models.AuditLog)
  - Implement audit_trail_export view
  - Implement suspicious_activity view
  - Add tenant filtering
  - _Requirements: 12.2, 12.3, 12.4, 12.7, 12.8_

- [ ] 10.5 Create audit trail templates (frontend)
  - Create templates/accounting/audit/ directory
  - Create audit_trail.html with filters and search
  - Create suspicious_activity.html with alerts
  - Display before/after values in readable format
  - Add TailwindCSS styling
  - _Requirements: 12.2, 12.3, 12.8_

- [ ] 10.6 Add audit URLs and test end-to-end
  - Add URL patterns for audit trail
  - Test: Perform various operations → View audit trail → Filter by user/date → Export
  - Verify all operations logged to apps.core.audit_models.AuditLog
  - Verify before/after values captured
  - Verify tenant isolation
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.7_



## Phase 11: Approval Workflows

- [ ] 11. Create approval workflow models with migrations
- [ ] 11.1 Create approval models
  - Add ApprovalRule model to apps/accounting/models.py
  - Include tenant FK, transaction_type, amount_threshold, approver_role
  - Add ApprovalRequest model for tracking approval requests
  - Add ApprovalAction model for approval/rejection actions
  - Add custom managers for tenant filtering
  - Create and run migrations
  - _Requirements: 13.1, 13.2, 13.5, 13.7_

- [ ] 11.2 Create approval service (backend)
  - Create ApprovalService in services.py
  - Implement submit_for_approval method
  - Implement get_pending_approvals method
  - Implement approve_transaction method
  - Implement reject_transaction method
  - Add notification logic
  - Add tenant filtering and audit logging
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.6, 13.7, 13.8_

- [ ] 11.3 Create approval management forms and views (backend)
  - Create ApprovalRuleForm and ApprovalActionForm in forms.py
  - Implement approval_rules_manage view
  - Implement pending_approvals view
  - Implement approval_action view
  - Add tenant filtering
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.7_

- [ ] 11.4 Create approval management templates (frontend)
  - Create templates/accounting/approvals/ directory
  - Create rules.html for managing approval rules
  - Create pending.html for viewing pending approvals
  - Create action_form.html for approve/reject with comments
  - Add notification badges for pending approvals
  - Add TailwindCSS styling
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.6_

- [ ] 11.5 Integrate approval workflow into transaction creation
  - Modify journal entry creation to check approval rules
  - Modify bill creation to check approval rules
  - Modify invoice creation to check approval rules
  - Add approval status display to transaction views
  - _Requirements: 13.1, 13.2, 13.7_

- [ ] 11.6 Add approval URLs and test end-to-end
  - Add URL patterns for approvals
  - Test: Create approval rule → Create transaction requiring approval → Approve/reject
  - Verify approval routing
  - Verify notifications
  - Verify tenant isolation
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7_

## Phase 12: Inventory Accounting Integration

- [ ] 12. Create inventory accounting models with migrations
- [ ] 12.1 Create inventory accounting models
  - Add InventoryValuationMethod model to apps/accounting/models.py
  - Add InventoryAdjustment model
  - Add InventoryRevaluation model
  - Add custom managers for tenant filtering
  - Create and run migrations
  - _Requirements: 7.1, 7.3, 7.5, 7.7_

- [ ] 12.2 Create inventory accounting service (backend)
  - Create InventoryAccountingService in services.py
  - Implement calculate_cogs method with FIFO/LIFO/Weighted Average
  - Implement record_inventory_receipt method
  - Implement record_inventory_adjustment method
  - Implement revalue_inventory method
  - Add automatic journal entry creation
  - Add tenant filtering
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

- [ ] 12.3 Update sales signal to use valuation method
  - Modify create_sale_journal_entry signal
  - Use InventoryAccountingService.calculate_cogs
  - Apply configured valuation method
  - _Requirements: 7.1, 7.2_

- [ ] 12.4 Create inventory adjustment forms and views (backend)
  - Create InventoryAdjustmentForm and InventoryRevaluationForm in forms.py
  - Implement inventory_adjustment_create view
  - Implement inventory_revaluation_create view
  - Implement inventory_valuation_report view
  - Add tenant filtering and audit logging
  - _Requirements: 7.3, 7.4, 7.5, 7.6, 7.7_

- [ ] 12.5 Create inventory accounting templates (frontend)
  - Create templates/accounting/inventory/ directory
  - Create adjustment_form.html
  - Create revaluation_form.html
  - Create valuation_report.html
  - Add TailwindCSS styling
  - _Requirements: 7.3, 7.4, 7.5, 7.7_

- [ ] 12.6 Add inventory accounting URLs and test end-to-end
  - Add URL patterns for inventory accounting
  - Test: Configure valuation method → Make sale → Record adjustment → Revalue inventory
  - Verify COGS calculation with different methods
  - Verify journal entries
  - Verify tenant isolation
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

## Phase 13: Multi-Currency Support

- [ ] 13. Create multi-currency models with migrations
- [ ] 13.1 Create currency models
  - Add Currency model to apps/accounting/models.py
  - Add ExchangeRate model with date and rate
  - Add ForeignCurrencyTransaction model
  - Add custom managers for tenant filtering
  - Create and run migrations
  - _Requirements: 16.1, 16.2, 16.7_

- [ ] 13.2 Create currency service (backend)
  - Create CurrencyService in services.py
  - Implement get_exchange_rate method
  - Implement convert_amount method
  - Implement calculate_realized_gain_loss method
  - Implement calculate_unrealized_gain_loss method
  - Add tenant filtering
  - _Requirements: 16.2, 16.3, 16.4, 16.5, 16.7_

- [ ] 13.3 Create currency management forms and views (backend)
  - Create CurrencyForm and ExchangeRateForm in forms.py
  - Implement currency_list, currency_create views
  - Implement exchange_rate_manage view
  - Add tenant filtering
  - _Requirements: 16.1, 16.2, 16.7, 16.8_

- [ ] 13.4 Create currency management templates (frontend)
  - Create templates/accounting/currencies/ directory
  - Create list.html, form.html
  - Create exchange_rates.html for rate management
  - Add TailwindCSS styling
  - _Requirements: 16.1, 16.2, 16.8_

- [ ] 13.5 Integrate multi-currency into transactions
  - Add currency field to Bill, Invoice, JournalEntry models
  - Add foreign currency amount fields
  - Update forms to include currency selection
  - Update views to handle currency conversion
  - Update templates to display both currencies
  - _Requirements: 16.3, 16.4, 16.6_

- [ ] 13.6 Create currency revaluation (backend + frontend)
  - Implement currency_revaluation view
  - Create automatic journal entries for unrealized gain/loss
  - Create templates/accounting/currencies/revaluation.html
  - _Requirements: 16.5_

- [ ] 13.7 Add multi-currency URLs and test end-to-end
  - Add URL patterns for currencies
  - Test: Create currency → Set exchange rate → Create foreign currency transaction → Revalue
  - Verify conversion calculations
  - Verify gain/loss calculations
  - Verify tenant isolation
  - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7_



## Phase 14: Recurring Transactions

- [ ] 14. Create recurring transaction models with migrations
- [ ] 14.1 Create recurring transaction models
  - Add RecurringTransaction model to apps/accounting/models.py
  - Include tenant FK, template data, frequency, duration, status
  - Add RecurringTransactionOccurrence model for tracking generated transactions
  - Add custom managers for tenant filtering
  - Create and run migrations
  - _Requirements: 17.1, 17.2, 17.5, 17.7_

- [ ] 14.2 Create recurring transaction service (backend)
  - Create RecurringTransactionService in services.py
  - Implement create_recurring_template method
  - Implement generate_due_transactions method
  - Implement pause_recurring method
  - Implement resume_recurring method
  - Add tenant filtering
  - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.7_

- [ ] 14.3 Create Celery task for recurring transactions
  - Create celery task to check and generate due transactions
  - Schedule task to run daily
  - Add notification for generated transactions
  - Add error handling and logging
  - _Requirements: 17.2, 17.3, 17.8_

- [ ] 14.4 Create recurring transaction forms and views (backend)
  - Create RecurringTransactionForm in forms.py
  - Implement recurring_transaction_list view
  - Implement recurring_transaction_create view
  - Implement recurring_transaction_pause view
  - Implement recurring_transaction_resume view
  - Add tenant filtering and audit logging
  - _Requirements: 17.1, 17.4, 17.5, 17.6, 17.7_

- [ ] 14.5 Create recurring transaction templates (frontend)
  - Create templates/accounting/recurring/ directory
  - Create list.html with status and next occurrence date
  - Create form.html for template creation
  - Add TailwindCSS styling
  - _Requirements: 17.1, 17.2, 17.5, 17.6_

- [ ] 14.6 Add recurring transaction URLs and test end-to-end
  - Add URL patterns for recurring transactions
  - Test: Create recurring template → Wait for generation → Pause → Resume
  - Verify automatic generation
  - Verify notifications
  - Verify tenant isolation
  - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7_

## Phase 15: Document Attachments

- [ ] 15. Create document attachment models with migrations
- [ ] 15.1 Create document attachment model
  - Add DocumentAttachment model to apps/accounting/models.py
  - Include tenant FK, content_type, object_id for generic relation
  - Include file field with tenant-specific upload path
  - Add metadata fields (filename, size, mime_type, uploaded_by)
  - Add custom managers for tenant filtering
  - Create and run migrations
  - _Requirements: 18.1, 18.5, 18.7_

- [ ] 15.2 Create document service (backend)
  - Create DocumentService in services.py
  - Implement upload_document method with validation
  - Implement get_documents method
  - Implement delete_document method
  - Implement generate_preview method
  - Add tenant-specific file paths
  - Add tenant filtering
  - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 18.7_

- [ ] 15.3 Create document attachment forms and views (backend)
  - Create DocumentAttachmentForm in forms.py
  - Implement document_upload view
  - Implement document_download view
  - Implement document_delete view
  - Implement document_preview view
  - Add file type and size validation
  - Add tenant filtering and audit logging
  - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 18.7, 18.8_

- [ ] 15.4 Integrate document attachments into transaction views
  - Add document upload to journal entry detail view
  - Add document upload to bill detail view
  - Add document upload to invoice detail view
  - Add document list display to all detail views
  - Add HTMX for dynamic upload without page refresh
  - _Requirements: 18.1, 18.2, 18.6_

- [ ] 15.5 Create document attachment templates (frontend)
  - Create templates/accounting/documents/ directory
  - Create upload_form.html
  - Create document_list.html partial for embedding
  - Create preview_modal.html
  - Add TailwindCSS styling
  - _Requirements: 18.1, 18.2, 18.3, 18.6_

- [ ] 15.6 Add document URLs and test end-to-end
  - Add URL patterns for documents
  - Test: Upload document to transaction → Preview → Download → Delete
  - Verify file type validation
  - Verify tenant isolation (cannot access other tenant's documents)
  - Verify audit logging
  - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 18.6, 18.7, 18.8_

## Phase 16: Cash Flow Management

- [ ] 16. Create cash flow management views and reports
- [ ] 16.1 Enhance cash flow statement (backend)
  - Update _generate_cash_flow_statement in services.py
  - Add detailed operating activities with working capital changes
  - Add investing activities (asset purchases/disposals)
  - Add financing activities (loans, equity)
  - Add tenant filtering
  - _Requirements: 19.1, 19.2, 19.7_

- [ ] 16.2 Create cash flow forecast service (backend)
  - Add forecast_cash_flow method to services.py
  - Project future cash based on receivables, payables, recurring transactions
  - Calculate projected cash position by period
  - Add tenant filtering
  - _Requirements: 19.2, 19.5, 19.7, 19.8_

- [ ] 16.3 Create cash flow management views (backend)
  - Implement cash_flow_statement view (enhanced)
  - Implement cash_flow_forecast view
  - Implement cash_position_dashboard view
  - Implement cash_flow_variance_report view
  - Add tenant filtering
  - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.7_

- [ ] 16.4 Create cash flow management templates (frontend)
  - Update templates/accounting/reports/cash_flow_statement.html
  - Create templates/accounting/reports/cash_flow_forecast.html
  - Create templates/accounting/dashboards/cash_position.html
  - Create templates/accounting/reports/cash_flow_variance.html
  - Add charts for visualization
  - Add TailwindCSS styling
  - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5_

- [ ] 16.5 Create cash flow alerts (backend + frontend)
  - Add CashFlowAlert model for threshold alerts
  - Create celery task to check cash position
  - Send notifications when balance falls below threshold
  - Create alert management interface
  - _Requirements: 19.6_

- [ ] 16.6 Add cash flow URLs and test end-to-end
  - Add URL patterns for cash flow management
  - Test: View cash flow statement → View forecast → Set alert → Trigger alert
  - Verify calculations
  - Verify forecasting accuracy
  - Verify tenant isolation
  - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7_

## Phase 17: Integration with Existing Modules

- [ ] 17. Enhance integration with existing modules
- [ ] 17.1 Enhance POS integration
  - Update sale signal to handle all payment methods
  - Add support for split payments
  - Add support for refunds with journal entries
  - Add support for gift card sales
  - Verify tenant isolation
  - _Requirements: 20.1, 20.7_

- [ ] 17.2 Enhance procurement integration
  - Update purchase order signal to create bills automatically
  - Add option to create bill on PO approval
  - Link bills to purchase orders
  - Update inventory receipt to update bill status
  - Verify tenant isolation
  - _Requirements: 20.2, 20.4, 20.7_

- [ ] 17.3 Enhance repair module integration
  - Add signal to create journal entries for repair revenue
  - Link repair orders to invoices
  - Add parts cost tracking
  - Verify tenant isolation
  - _Requirements: 20.3, 20.7_

- [ ] 17.4 Create customer payment integration
  - Add payment processing integration
  - Automatically apply payments to invoices
  - Create journal entries for payments
  - Handle payment failures and refunds
  - Verify tenant isolation
  - _Requirements: 20.5, 20.7_

- [ ] 17.5 Create payroll integration (basic)
  - Add PayrollEntry model for payroll journal entries
  - Create interface to record payroll
  - Create journal entries for wages, taxes, deductions
  - Add tenant filtering
  - _Requirements: 20.6, 20.7_

- [ ] 17.6 Add integration error handling
  - Add IntegrationError model for tracking failures
  - Add retry logic for failed integrations
  - Add notification for integration errors
  - Add admin interface to view and retry failed integrations
  - _Requirements: 20.8_

- [ ] 17.7 Test all integrations end-to-end
  - Test: Complete sale → Verify journal entry
  - Test: Receive inventory → Verify journal entry
  - Test: Complete repair → Verify journal entry
  - Test: Process payment → Verify application to invoice
  - Test: Record payroll → Verify journal entry
  - Verify all integrations maintain tenant isolation
  - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5, 20.6, 20.7_



## Phase 18: Bank Transfer Management

- [ ] 18. Create bank transfer functionality
- [ ] 18.1 Create BankTransfer model
  - Add BankTransfer model to apps/accounting/models.py
  - Include tenant FK, from_account, to_account, amount, date, reference
  - Link to journal_entry
  - Add custom manager for tenant filtering
  - Create and run migration
  - _Requirements: 6.2, 6.7_

- [ ] 18.2 Create bank transfer service and views (backend)
  - Add record_transfer method to BankAccountService
  - Create automatic journal entry (debit destination, credit source)
  - Implement bank_transfer_create view
  - Implement bank_transfer_list view
  - Add tenant filtering and audit logging
  - _Requirements: 6.2, 6.7_

- [ ] 18.3 Create bank transfer templates (frontend)
  - Create templates/accounting/bank_accounts/transfer_form.html
  - Create templates/accounting/bank_accounts/transfer_list.html
  - Add account balance display
  - Add TailwindCSS styling
  - _Requirements: 6.2_

- [ ] 18.4 Test bank transfers end-to-end
  - Test: Create transfer → Verify journal entry → Verify balances updated
  - Verify tenant isolation
  - _Requirements: 6.2, 6.7_

## Phase 19: Auto-Categorization Rules

- [ ] 19. Create auto-categorization for bank transactions
- [ ] 19.1 Create AutoCategorizationRule model
  - Add AutoCategorizationRule model to apps/accounting/models.py
  - Include tenant FK, bank_account, pattern, rule_type, account
  - Add custom manager for tenant filtering
  - Create and run migration
  - _Requirements: 6.5, 6.7_

- [ ] 19.2 Create auto-categorization service (backend)
  - Add apply_auto_rules method to BankAccountService
  - Implement pattern matching (contains, starts_with, ends_with, regex)
  - Apply rules during bank statement import
  - Add tenant filtering
  - _Requirements: 6.5, 6.7_

- [ ] 19.3 Create auto-categorization management (backend + frontend)
  - Create AutoCategorizationRuleForm in forms.py
  - Implement auto_rules_manage view
  - Create templates/accounting/bank_accounts/auto_rules.html
  - Add rule testing interface
  - Add TailwindCSS styling
  - _Requirements: 6.5_

- [ ] 19.4 Test auto-categorization end-to-end
  - Test: Create rule → Import statement → Verify auto-categorization
  - Verify tenant isolation
  - _Requirements: 6.5, 6.7_

## Phase 20: Dashboard Enhancements

- [ ] 20. Enhance accounting dashboard
- [ ] 20.1 Create comprehensive dashboard widgets (backend)
  - Add get_dashboard_data method to services.py
  - Calculate key metrics (cash position, AP/AR totals, net income)
  - Get recent transactions
  - Get pending approvals count
  - Get alerts and notifications
  - Add tenant filtering
  - _Requirements: All modules_

- [ ] 20.2 Update dashboard template (frontend)
  - Update templates/accounting/dashboard.html
  - Add cash position widget
  - Add AP/AR summary widgets
  - Add recent transactions widget
  - Add pending approvals widget
  - Add alerts widget
  - Add quick action buttons
  - Add charts for key metrics
  - Add TailwindCSS styling
  - _Requirements: All modules_

- [ ] 20.3 Add dashboard customization
  - Allow users to show/hide widgets
  - Allow users to rearrange widgets
  - Save preferences per user
  - _Requirements: All modules_

## Phase 21: Navigation and Menu Updates

- [ ] 21. Update navigation to include all new features
- [ ] 21.1 Update main navigation menu
  - Add Accounting dropdown menu to main navigation
  - Organize menu items by category (Transactions, Reports, Setup)
  - Add permission-based menu visibility
  - Update templates/base.html or navigation partial
  - _Requirements: All modules_

- [ ] 21.2 Create accounting sidebar navigation
  - Create templates/accounting/includes/sidebar.html
  - Add links to all accounting features
  - Add active state highlighting
  - Add permission-based visibility
  - Add TailwindCSS styling
  - _Requirements: All modules_

- [ ] 21.3 Add breadcrumbs
  - Add breadcrumb navigation to all accounting pages
  - Show current location in hierarchy
  - Add TailwindCSS styling
  - _Requirements: All modules_

## Phase 22: Permissions and Security

- [ ] 22. Implement comprehensive permissions
- [ ] 22.1 Create accounting permissions
  - Define permissions for all accounting operations
  - Add to apps/accounting/permissions.py
  - Create permission groups (Accountant, AP Clerk, AR Clerk, etc.)
  - _Requirements: All modules_

- [ ] 22.2 Add permission checks to all views
  - Add @permission_required decorators to all views
  - Add permission checks in templates
  - Add permission-based button visibility
  - _Requirements: All modules_

- [ ] 22.3 Implement row-level security (RLS)
  - Verify all queries filter by tenant
  - Add database-level RLS policies
  - Test cross-tenant access prevention
  - _Requirements: All modules_

- [ ] 22.4 Add security audit
  - Run security audit on all views
  - Test for SQL injection vulnerabilities
  - Test for XSS vulnerabilities
  - Test for CSRF protection
  - Test for unauthorized access
  - _Requirements: All modules_

## Phase 23: Testing and Quality Assurance

- [ ] 23. Comprehensive testing
- [ ] 23.1 Write unit tests for all models
  - Test model validation
  - Test custom managers
  - Test tenant filtering
  - Test calculations (COGS, depreciation, tax)
  - Achieve 80%+ code coverage
  - _Requirements: All modules_

- [ ] 23.2 Write unit tests for all services
  - Test business logic
  - Test journal entry creation
  - Test balance calculations
  - Test report generation
  - Achieve 80%+ code coverage
  - _Requirements: All modules_

- [ ] 23.3 Write integration tests
  - Test end-to-end workflows
  - Test signal-triggered operations
  - Test multi-step processes
  - Test error handling
  - _Requirements: All modules_

- [ ] 23.4 Write UI tests
  - Test form validation
  - Test HTMX interactions
  - Test file uploads
  - Test report downloads
  - _Requirements: All modules_

- [ ] 23.5 Perform security testing
  - Test tenant isolation
  - Test permission enforcement
  - Test SQL injection prevention
  - Test XSS prevention
  - _Requirements: All modules_

- [ ] 23.6 Perform performance testing
  - Test with large datasets
  - Test report generation speed
  - Test concurrent users
  - Optimize slow queries
  - _Requirements: All modules_

## Phase 24: Documentation and Training

- [ ] 24. Create documentation
- [ ] 24.1 Write user documentation
  - Create user guide for each feature
  - Add screenshots and examples
  - Create video tutorials
  - _Requirements: All modules_

- [ ] 24.2 Write technical documentation
  - Document architecture
  - Document data models
  - Document API endpoints
  - Document integration points
  - _Requirements: All modules_

- [ ] 24.3 Create admin documentation
  - Document setup procedures
  - Document configuration options
  - Document troubleshooting
  - Document backup/recovery
  - _Requirements: All modules_

## Phase 25: Deployment and Monitoring

- [ ] 25. Prepare for production deployment
- [ ] 25.1 Create deployment checklist
  - Database migration plan
  - Rollback procedures
  - Configuration checklist
  - Monitoring setup
  - _Requirements: All modules_

- [ ] 25.2 Set up monitoring
  - Configure application monitoring
  - Configure error tracking (Sentry)
  - Configure database monitoring
  - Configure Celery monitoring
  - Set up alerts
  - _Requirements: All modules_

- [ ] 25.3 Perform load testing
  - Test with expected user load
  - Test with peak load
  - Identify bottlenecks
  - Optimize as needed
  - _Requirements: All modules_

- [ ] 25.4 Create backup procedures
  - Set up automated database backups
  - Set up document storage backups
  - Test restore procedures
  - Document recovery procedures
  - _Requirements: All modules_

- [ ] 25.5 Deploy to production
  - Run final tests in staging
  - Execute deployment plan
  - Verify all features working
  - Monitor for errors
  - _Requirements: All modules_

## Summary

This implementation plan covers all 20 missing feature areas with:
- **300+ individual tasks** organized into 25 phases
- **Backend + Frontend pairs** for each feature (test as you go)
- **Database migrations** for all new models
- **Strict tenant isolation (RLS)** in every component
- **Comprehensive audit trails** for all operations
- **Integration with existing modules**
- **Testing at every level** (unit, integration, UI, security, performance)
- **Documentation and deployment** procedures

Each phase builds upon the previous, allowing incremental development and testing. The plan ensures that tenant isolation and audit trails are maintained throughout, and that each feature is fully tested before moving to the next.
