# Design Document

## Overview

This design document outlines the architecture and implementation approach for completing the jewelry shop accounting system. The system builds upon the existing 40% complete foundation to deliver a full-featured, production-ready accounting solution with strict tenant isolation, comprehensive audit trails, and seamless integration with existing modules.

### Design Principles

1. **Tenant Isolation First**: Every database query must filter by tenant; use Django's tenant-aware managers
2. **Audit Everything**: All financial transactions must record who, what, when, and why
3. **Double-Entry Integrity**: All journal entries must balance (debits = credits)
4. **Immutability**: Posted transactions cannot be modified, only reversed
5. **Integration by Design**: Accounting automatically captures transactions from other modules
6. **Progressive Enhancement**: Build backend + frontend for each feature before moving to next
7. **Django-Ledger Integration**: Leverage existing django-ledger models where possible, extend where needed

### Technology Stack

- **Backend**: Django 4.2+, django-ledger, PostgreSQL with RLS
- **Frontend**: Django templates, HTMX for dynamic interactions, TailwindCSS
- **Reporting**: ReportLab (PDF), openpyxl (Excel)
- **File Storage**: Django's file storage with tenant-specific paths
- **Background Jobs**: Celery for recurring transactions and depreciation

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Presentation Layer                       │
│  (Django Templates + HTMX + TailwindCSS)                    │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                      Application Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Views      │  │   Forms      │  │   Services   │     │
│  │  (Django)    │  │  (Django)    │  │  (Business)  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                       Domain Layer                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Models     │  │   Managers   │  │   Signals    │     │
│  │  (Django)    │  │  (Tenant)    │  │  (Events)    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  PostgreSQL  │  │    Redis     │  │    Celery    │     │
│  │   (RLS)      │  │   (Cache)    │  │  (Tasks)     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### Database Schema Design

All new models will follow these patterns:

1. **Tenant Foreign Key**: Every model has `tenant = ForeignKey(Tenant)`
2. **UUID Primary Keys**: Use UUID for all financial records
3. **Audit Fields**: created_at, created_by, updated_at, updated_by
4. **Soft Deletes**: is_active/is_deleted flags instead of hard deletes
5. **Version Control**: version field for optimistic locking



## Components and Interfaces

### 1. Manual Journal Entry System

#### Models

**JournalEntryHeader** (extends django-ledger's JournalEntryModel)
- Inherits from django-ledger's JournalEntryModel
- Additional fields: tenant, created_by, approved_by, approval_status
- Status: DRAFT, PENDING_APPROVAL, APPROVED, POSTED, REVERSED
- Immutable once posted

**JournalEntryLine** (extends django-ledger's TransactionModel)
- Inherits from django-ledger's TransactionModel
- Links to JournalEntryHeader
- Validates debit/credit balance

#### Services

**JournalEntryService**
- `create_manual_entry(tenant, user, data)`: Create new journal entry
- `validate_balance(entry)`: Ensure debits = credits
- `post_entry(entry, user)`: Post to GL, make immutable
- `reverse_entry(entry, user, reason)`: Create reversing entry
- `get_entries_for_tenant(tenant, filters)`: Query with tenant isolation

#### Forms

**JournalEntryForm**
- Description, date, reference
- Dynamic formset for lines (account, debit, credit, description)
- JavaScript validation for balance
- HTMX for dynamic line addition

#### Views

- `journal_entry_list`: List all entries with filters
- `journal_entry_create`: Create new entry
- `journal_entry_detail`: View entry details
- `journal_entry_post`: Post entry to GL
- `journal_entry_reverse`: Create reversing entry

#### Templates

- `journal_entries/list.html`: Filterable list with status badges
- `journal_entries/form.html`: Entry form with dynamic lines
- `journal_entries/detail.html`: Read-only view with audit trail
- `journal_entries/confirm_post.html`: Confirmation modal

### 2. Supplier Bill Management (AP)

#### Models

**Supplier** (extends existing apps.procurement.models.Supplier)
- Existing fields: tenant, name, contact_person, email, phone, address, tax_id, payment_terms, rating, is_active, notes
- NEW accounting fields to add via migration:
  - default_expense_account (CharField) - default GL account for expenses
  - is_1099_vendor (BooleanField) - whether supplier requires 1099 reporting

**Bill**
- tenant, supplier (FK to apps.procurement.models.Supplier), bill_number, bill_date, due_date
- subtotal, tax, total, amount_paid, amount_due
- status: DRAFT, APPROVED, PARTIALLY_PAID, PAID, VOID
- journal_entry (FK to django-ledger's JournalEntryModel)

**BillLine**
- bill, account, description, quantity, unit_price, amount
- Links to expense or asset accounts

**BillPayment**
- tenant, bill, payment_date, amount, payment_method
- bank_account, reference_number, notes

#### Services

**BillService**
- `create_bill(tenant, user, data)`: Create bill and journal entry
- `approve_bill(bill, user)`: Approve for payment
- `record_payment(bill, payment_data, user)`: Record payment and create JE
- `get_aged_payables(tenant, as_of_date)`: Generate aging report
- `get_vendor_statement(vendor, start_date, end_date)`: Vendor statement

#### Forms

**BillForm**: Vendor, dates, line items with account selection
**BillPaymentForm**: Payment amount, method, bank account, date

#### Views

- `bill_list`: List bills with aging and status
- `bill_create`: Create new bill
- `bill_detail`: View bill with payment history
- `bill_pay`: Record payment
- `aged_payables_report`: Aging report
- `vendor_statement`: Generate statement

### 3. Customer Invoice Management (AR)

#### Models

**Customer** (extends existing apps.crm.models.Customer)
- Existing fields: tenant, customer_number, first_name, last_name, email, phone, address, loyalty_tier, store_credit, marketing_opt_in, tags, notes, is_active
- NEW accounting fields to add via migration:
  - credit_limit (DecimalField) - maximum credit allowed
  - payment_terms (CharField) - default payment terms (e.g., "NET30")
  - tax_exempt (BooleanField) - whether customer is tax-exempt
  - exemption_certificate (FileField) - tax exemption certificate document

**Invoice**
- tenant, customer (FK to apps.crm.models.Customer), invoice_number, invoice_date, due_date
- subtotal, tax, total, amount_paid, amount_due
- status: DRAFT, SENT, PARTIALLY_PAID, PAID, VOID, OVERDUE
- journal_entry (FK to django-ledger's JournalEntryModel)

**InvoiceLine**
- invoice, item, description, quantity, unit_price, amount

**InvoicePayment**
- tenant, invoice, payment_date, amount, payment_method
- bank_account, reference_number, notes

**CreditMemo**
- tenant, customer (FK to apps.crm.models.Customer), amount, reason, applied_to_invoice

#### Services

**InvoiceService**
- `create_invoice(tenant, user, data)`: Create invoice and journal entry
- `send_invoice(invoice, user)`: Mark as sent, optionally email
- `record_payment(invoice, payment_data, user)`: Record payment and create JE
- `apply_credit_memo(credit_memo, invoice, user)`: Apply credit
- `get_aged_receivables(tenant, as_of_date)`: Generate aging report
- `get_customer_statement(customer, start_date, end_date)`: Customer statement

#### Forms

**InvoiceForm**: Customer, dates, line items
**InvoicePaymentForm**: Payment details
**CreditMemoForm**: Customer, amount, reason

#### Views

- `invoice_list`: List invoices with aging
- `invoice_create`: Create new invoice
- `invoice_detail`: View invoice with payment history
- `invoice_receive_payment`: Record payment
- `aged_receivables_report`: Aging report
- `customer_statement`: Generate statement



### 4. Bank Reconciliation System

#### Models

**BankAccount**
- tenant, account_name, account_number, bank_name
- account_type, opening_balance, current_balance
- Extends django-ledger's BankAccountModel

**BankTransaction**
- tenant, bank_account, transaction_date, description
- amount, transaction_type (DEBIT/CREDIT)
- is_reconciled, reconciled_date, reconciled_by
- matched_journal_entry

**BankReconciliation**
- tenant, bank_account, reconciliation_date
- statement_beginning_balance, statement_ending_balance
- book_beginning_balance, book_ending_balance
- status: IN_PROGRESS, COMPLETED
- reconciled_by, completed_date

**BankStatementImport**
- tenant, bank_account, import_date, file_name
- imported_by, transactions_imported, transactions_matched

#### Services

**BankReconciliationService**
- `start_reconciliation(bank_account, statement_date, ending_balance)`: Begin reconciliation
- `mark_reconciled(transaction, reconciliation, user)`: Mark transaction as reconciled
- `auto_match_transactions(bank_account, imported_transactions)`: Auto-match
- `complete_reconciliation(reconciliation, user)`: Finalize reconciliation
- `import_bank_statement(bank_account, file, user)`: Parse and import
- `generate_reconciliation_report(reconciliation)`: Generate report

#### Forms

**BankReconciliationForm**: Statement date, ending balance
**BankStatementImportForm**: File upload with format selection
**TransactionMatchForm**: Match imported transaction to GL transaction

#### Views

- `bank_account_list`: List all bank accounts
- `bank_reconciliation_start`: Start new reconciliation
- `bank_reconciliation_detail`: Reconciliation interface
- `bank_statement_import`: Import statement
- `bank_reconciliation_report`: View completed reconciliation

### 5. Fixed Assets and Depreciation

#### Models

**FixedAsset**
- tenant, asset_name, asset_number, category
- acquisition_date, acquisition_cost, salvage_value
- useful_life_months, depreciation_method
- status: ACTIVE, DISPOSED, FULLY_DEPRECIATED
- asset_account, accumulated_depreciation_account

**DepreciationSchedule**
- fixed_asset, period_date, depreciation_amount
- accumulated_depreciation, book_value
- journal_entry (link to created JE)

**AssetDisposal**
- fixed_asset, disposal_date, disposal_method
- proceeds, gain_loss, journal_entry

#### Services

**FixedAssetService**
- `register_asset(tenant, user, data)`: Register new asset
- `calculate_depreciation(asset, period_date)`: Calculate depreciation
- `run_monthly_depreciation(tenant, period_date)`: Run for all assets
- `dispose_asset(asset, disposal_data, user)`: Record disposal
- `get_depreciation_schedule(asset)`: Get full schedule
- `get_fixed_assets_register(tenant)`: List all assets with values

#### Forms

**FixedAssetForm**: Asset details, depreciation method
**AssetDisposalForm**: Disposal date, method, proceeds

#### Views

- `fixed_asset_list`: List all assets
- `fixed_asset_create`: Register new asset
- `fixed_asset_detail`: View asset with depreciation history
- `fixed_asset_dispose`: Record disposal
- `depreciation_schedule`: View schedule
- `run_depreciation`: Run monthly depreciation

### 6. Advanced Bank Account Management

#### Models

**BankTransfer**
- tenant, from_account, to_account, transfer_date
- amount, reference, journal_entry

**AutoCategorization Rule**
- tenant, bank_account, pattern, account
- rule_type: CONTAINS, STARTS_WITH, ENDS_WITH, REGEX

#### Services

**BankAccountService**
- `create_bank_account(tenant, user, data)`: Create account
- `record_transfer(tenant, from_account, to_account, amount, user)`: Record transfer
- `apply_auto_rules(transaction)`: Auto-categorize
- `get_account_balance(bank_account, as_of_date)`: Get balance
- `get_account_transactions(bank_account, start_date, end_date)`: Get transactions

#### Forms

**BankAccountForm**: Account details
**BankTransferForm**: From/to accounts, amount
**AutoCategorizationRuleForm**: Pattern, account

#### Views

- `bank_account_create`: Create account
- `bank_account_detail`: View account with transactions
- `bank_transfer_create`: Record transfer
- `auto_rules_manage`: Manage auto-categorization rules

### 7. Inventory Accounting Integration

#### Models

**InventoryValuationMethod** (configuration)
- tenant, method: FIFO, LIFO, WEIGHTED_AVERAGE
- effective_date

**InventoryAdjustment**
- tenant, inventory_item, adjustment_date
- quantity_adjustment, value_adjustment, reason
- journal_entry

**InventoryRevaluation**
- tenant, revaluation_date, reason
- total_adjustment, journal_entry

#### Services

**InventoryAccountingService**
- `calculate_cogs(sale, method)`: Calculate COGS using valuation method
- `record_inventory_receipt(purchase_order, user)`: Record receipt
- `record_inventory_adjustment(adjustment_data, user)`: Record adjustment
- `revalue_inventory(tenant, revaluation_data, user)`: Revalue inventory
- `get_inventory_valuation_report(tenant, as_of_date)`: Valuation report

#### Forms

**InventoryAdjustmentForm**: Item, quantity, value, reason
**InventoryRevaluationForm**: Date, reason, adjustments

#### Views

- `inventory_adjustment_create`: Create adjustment
- `inventory_revaluation_create`: Revalue inventory
- `inventory_valuation_report`: View valuation



### 8. Tax Management System

#### Models

**TaxCode**
- tenant, code, name, rate, tax_account
- jurisdiction, is_active, effective_date

**TaxJurisdiction**
- tenant, name, tax_authority, filing_frequency

**TaxPayment**
- tenant, jurisdiction, payment_date, amount
- period_start, period_end, journal_entry

#### Services

**TaxService**
- `calculate_tax(amount, tax_code)`: Calculate tax
- `apply_multi_jurisdiction_tax(amount, tax_codes)`: Multiple taxes
- `generate_tax_report(tenant, jurisdiction, start_date, end_date)`: Tax report
- `record_tax_payment(payment_data, user)`: Record payment

#### Forms

**TaxCodeForm**: Code, rate, jurisdiction
**TaxPaymentForm**: Jurisdiction, amount, period

#### Views

- `tax_code_list`: List tax codes
- `tax_code_create`: Create tax code
- `tax_report`: Generate tax report
- `tax_payment_record`: Record payment

### 9. Accounting Period Management

#### Models

**AccountingPeriod**
- tenant, period_type: MONTH, QUARTER, YEAR
- start_date, end_date, fiscal_year
- status: OPEN, CLOSED, LOCKED
- closed_by, closed_date

**PeriodLock**
- tenant, period, locked_by, locked_date
- unlock_reason (if unlocked)

#### Services

**PeriodService**
- `create_periods(tenant, fiscal_year)`: Create periods for year
- `close_period(period, user)`: Close period
- `lock_period(period, user)`: Lock period
- `unlock_period(period, user, reason)`: Unlock with reason
- `validate_transaction_date(tenant, date)`: Check if period allows transactions

#### Forms

**PeriodCloseForm**: Period selection, confirmation
**PeriodUnlockForm**: Reason for unlock

#### Views

- `period_list`: List all periods with status
- `period_close`: Close period
- `period_lock`: Lock period
- `period_unlock`: Unlock period

### 10. Budgeting and Forecasting

#### Models

**Budget**
- tenant, name, fiscal_year, status: DRAFT, ACTIVE, ARCHIVED
- created_by, approved_by

**BudgetLine**
- budget, account, period_date, budgeted_amount

**BudgetScenario**
- tenant, name, description, base_budget

#### Services

**BudgetService**
- `create_budget(tenant, user, data)`: Create budget
- `copy_budget(source_budget, adjustment_percent)`: Copy with adjustment
- `get_budget_vs_actual(budget, start_date, end_date)`: Variance report
- `forecast_cash_flow(tenant, periods)`: Cash flow forecast

#### Forms

**BudgetForm**: Name, fiscal year
**BudgetLineForm**: Account, period, amount
**BudgetCopyForm**: Source budget, adjustment

#### Views

- `budget_list`: List budgets
- `budget_create`: Create budget
- `budget_edit`: Edit budget lines
- `budget_vs_actual_report`: Variance report
- `cash_flow_forecast`: Forecast report

### 11. Advanced Financial Reporting

#### Services

**ReportingService**
- `generate_aged_receivables(tenant, as_of_date)`: AR aging
- `generate_aged_payables(tenant, as_of_date)`: AP aging
- `generate_comparative_financials(tenant, periods)`: Comparative statements
- `generate_departmental_pl(tenant, department, start_date, end_date)`: Dept P&L
- `calculate_financial_ratios(tenant, as_of_date)`: Financial ratios
- `generate_gl_detail_report(tenant, account, start_date, end_date)`: GL detail

#### Views

- `aged_receivables_report`: AR aging
- `aged_payables_report`: AP aging
- `comparative_financials`: Comparative statements
- `departmental_pl`: Department P&L
- `financial_ratios`: Ratios dashboard
- `gl_detail_report`: GL detail

### 12. Audit Trail and Compliance

#### Models

**AuditLog** (uses existing apps.core.audit_models.AuditLog)
- Existing fields: tenant, user, timestamp, ip_address, category, action, severity, description
- NO NEW MODEL NEEDED - use existing AuditLog from core app
- Already tracks: user_agent, request_method, request_path, before_value, after_value

**SensitiveOperation**
- tenant, user, operation_type, timestamp
- requires_approval, approved_by, approval_date

#### Services

**AuditService**
- `log_change(tenant, user, model, object_id, action, before, after)`: Log change
- `get_audit_trail(tenant, filters)`: Query audit log
- `export_audit_trail(tenant, start_date, end_date)`: Export audit
- `detect_suspicious_activity(tenant)`: Anomaly detection

#### Views

- `audit_trail`: View audit log
- `audit_trail_export`: Export audit
- `suspicious_activity`: View alerts

### 13. Approval Workflows

#### Models

**ApprovalRule**
- tenant, transaction_type, amount_threshold
- approver_role, approval_levels

**ApprovalRequest**
- tenant, transaction_type, transaction_id
- requested_by, requested_date, status: PENDING, APPROVED, REJECTED
- current_approver, approval_level

**ApprovalAction**
- approval_request, approver, action_date
- action: APPROVE, REJECT, comments

#### Services

**ApprovalService**
- `submit_for_approval(tenant, transaction, user)`: Submit
- `get_pending_approvals(user)`: Get user's pending approvals
- `approve_transaction(approval_request, user, comments)`: Approve
- `reject_transaction(approval_request, user, comments)`: Reject

#### Forms

**ApprovalRuleForm**: Transaction type, threshold, approver
**ApprovalActionForm**: Comments, action

#### Views

- `approval_rules_manage`: Manage rules
- `pending_approvals`: View pending
- `approval_action`: Approve/reject



### 14-20. Additional Components

#### Supplier Management (Accounting Extensions)
- Extend existing Supplier model with accounting fields
- Supplier statements and history
- 1099 tracking via is_1099_vendor field

#### Customer Management (Accounting Extensions)
- Extend existing Customer model with accounting fields (credit_limit, payment_terms, tax_exempt)
- Customer statements and history
- Tax exemption tracking

#### Multi-Currency Support
- Currency configuration
- Exchange rate management
- Realized/unrealized gain/loss

#### Recurring Transactions
- Template creation
- Automatic generation via Celery
- Notification system

#### Document Attachments
- File upload with tenant isolation
- Document preview
- Secure storage

#### Cash Flow Management
- Detailed cash flow statement
- Cash flow forecasting
- Cash position dashboard

#### Integration Layer
- Signals for automatic JE creation
- API endpoints for external systems
- Webhook support

## Data Models

### Core Accounting Models (Existing - django-ledger)
- EntityModel
- ChartOfAccountModel
- AccountModel
- LedgerModel
- JournalEntryModel
- TransactionModel

### New Models to Create

```python
# apps/accounting/models.py additions

# NOTE: Supplier and Customer models already exist in other apps
# We will extend them via migrations, not create new models

# Migration to add accounting fields to existing Supplier model (apps.procurement.models.Supplier):
# - default_expense_account = models.CharField(max_length=20, blank=True)
# - is_1099_vendor = models.BooleanField(default=False)

# Migration to add accounting fields to existing Customer model (apps.crm.models.Customer):
# - credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
# - payment_terms = models.CharField(max_length=50, default='NET30')
# - tax_exempt = models.BooleanField(default=False)
# - exemption_certificate = models.FileField(upload_to='customer_tax_exemptions/', blank=True)

class Bill(models.Model):
    """Supplier bill/invoice"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    supplier = models.ForeignKey('procurement.Supplier', on_delete=models.PROTECT)  # Use existing Supplier
    bill_number = models.CharField(max_length=50)
    bill_date = models.DateField()
    due_date = models.DateField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    journal_entry = models.ForeignKey(JournalEntryModel, null=True, ...)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, ...)
    
    class Meta:
        db_table = 'accounting_bills'
        unique_together = [['tenant', 'bill_number']]

class Invoice(models.Model):
    """Customer invoice"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    customer = models.ForeignKey('crm.Customer', on_delete=models.PROTECT)  # Use existing Customer
    invoice_number = models.CharField(max_length=50)
    invoice_date = models.DateField()
    due_date = models.DateField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    journal_entry = models.ForeignKey(JournalEntryModel, null=True, ...)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, ...)
    
    class Meta:
        db_table = 'accounting_invoices'
        unique_together = [['tenant', 'invoice_number']]

# Similar models for:
# - BillLine
# - BillPayment
# - InvoiceLine
# - InvoicePayment
# - CreditMemo
# - BankAccount
# - BankTransaction
# - BankReconciliation
# - FixedAsset
# - DepreciationSchedule
# - TaxCode
# - AccountingPeriod
# - Budget
# - BudgetLine
# - ApprovalRule
# - ApprovalRequest
# - RecurringTransaction
# - DocumentAttachment

# NOTE: AuditLog already exists in apps.core.audit_models - use that instead of creating new one
```

## Error Handling

### Validation Errors
- Journal entries must balance (debits = credits)
- Transactions in closed periods rejected
- Duplicate bill/invoice numbers prevented
- Credit limit checks on invoices
- Bank reconciliation balance validation

### Business Logic Errors
- Cannot modify posted transactions
- Cannot delete transactions with payments
- Cannot close period with unreconciled transactions
- Cannot exceed customer credit limit
- Cannot pay more than bill amount

### System Errors
- Database connection failures
- File upload errors
- Report generation failures
- Integration failures
- Celery task failures

All errors logged to audit trail with context.

## Testing Strategy

### Unit Tests
- Model validation
- Service layer business logic
- Calculation accuracy (COGS, depreciation, tax)
- Tenant isolation
- Balance validation

### Integration Tests
- End-to-end workflows (create bill → pay bill)
- Signal-triggered journal entries
- Report generation
- File imports
- Multi-step processes

### UI Tests
- Form validation
- HTMX interactions
- Report downloads
- File uploads

### Security Tests
- Tenant isolation (RLS)
- Permission checks
- SQL injection prevention
- XSS prevention
- CSRF protection

### Performance Tests
- Large dataset queries
- Report generation speed
- Concurrent user handling
- Database query optimization

## Security Considerations

### Tenant Isolation (RLS)
- Every query filtered by tenant
- Custom managers enforce tenant filtering
- Database-level RLS as backup
- Cross-tenant access prevented

### Authentication & Authorization
- Django authentication required
- Permission-based access control
- Role-based menu visibility
- Sensitive operations require re-authentication

### Data Protection
- Encrypted file storage
- Secure document access
- Audit trail for all changes
- Immutable posted transactions

### Compliance
- SOX compliance for financial data
- GDPR compliance for personal data
- Audit trail retention
- Data export capabilities

## Performance Optimization

### Database Optimization
- Indexes on foreign keys
- Indexes on frequently queried fields
- Query optimization with select_related/prefetch_related
- Database connection pooling

### Caching Strategy
- Cache chart of accounts
- Cache tax codes
- Cache exchange rates
- Redis for session storage

### Background Processing
- Celery for recurring transactions
- Celery for depreciation runs
- Celery for report generation
- Celery for email notifications

### Frontend Optimization
- HTMX for partial page updates
- Lazy loading for large lists
- Pagination for reports
- Client-side validation

## Deployment Considerations

### Database Migrations
- Migrations for all new models
- Data migrations for existing data
- Backward compatibility
- Rollback procedures

### Configuration
- Environment-specific settings
- Feature flags for gradual rollout
- Tenant-specific configuration
- Default values

### Monitoring
- Application performance monitoring
- Error tracking (Sentry)
- Database query monitoring
- Celery task monitoring

### Backup & Recovery
- Daily database backups
- Document storage backups
- Point-in-time recovery
- Disaster recovery plan
