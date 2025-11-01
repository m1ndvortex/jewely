# Task 2.7: Aged Payables Report Implementation

## Status: ✅ COMPLETED

## Overview
Successfully implemented the aged payables report with backend view, frontend template, and PDF/Excel export functionality.

## Implementation Details

### 1. Backend View (`apps/accounting/views.py`)
- **Function**: `aged_payables_report(request)`
- **Features**:
  - Queries all unpaid bills (APPROVED, PARTIALLY_PAID status) for the tenant
  - Groups bills by supplier
  - Calculates aging buckets: Current, 1-30 days, 31-60 days, 61-90 days, 90+ days
  - Computes grand totals across all suppliers
  - Supports date filtering via `as_of_date` parameter
  - Enforces tenant isolation
  - Routes to PDF or Excel export based on query parameter

### 2. PDF Export (`_export_aged_payables_pdf`)
- Uses ReportLab library
- Landscape orientation for better table display
- Styled table with headers and totals row
- Professional formatting with tenant name and report date
- Filename: `aged_payables_YYYYMMDD.pdf`

### 3. Excel Export (`_export_aged_payables_excel`)
- Uses openpyxl library
- Styled headers with blue background
- Currency formatting for all amount columns
- Bold totals row with gray background
- Auto-adjusted column widths
- Filename: `aged_payables_YYYYMMDD.xlsx`

### 4. Frontend Template (`templates/accounting/reports/aged_payables.html`)
- **Features**:
  - Responsive design with TailwindCSS
  - Dark mode support
  - Summary cards showing grand totals for each aging bucket
  - Color-coded amounts (green for current, yellow/orange/red for overdue)
  - Date filter to view report as of any date
  - Export buttons for PDF and Excel
  - Empty state with helpful message
  - Help section explaining report usage
  - Breadcrumb navigation
  - Back to Bills button

### 5. URL Configuration (`apps/accounting/urls.py`)
- Added route: `/accounting/reports/aged-payables/`
- Named URL: `accounting:aged_payables_report`

### 6. Integration
- Added "Aged Payables" button to bills list page header
- Purple button with chart icon for easy access

## Requirements Verification

### Requirement 2.5
✅ **"WHEN a User views supplier aging report, THE System SHALL display amounts owed grouped by 30/60/90/90+ days overdue"**

**Implementation**:
- ✅ Displays amounts grouped by aging buckets (Current, 1-30, 31-60, 61-90, 90+)
- ✅ Groups by supplier with individual totals
- ✅ Shows grand totals across all suppliers
- ✅ Enforces tenant isolation
- ✅ Includes PDF export
- ✅ Includes Excel export
- ✅ Allows date filtering

## Technical Details

### Aging Calculation Logic
```python
days_overdue = (as_of_date - bill.due_date).days if as_of_date > bill.due_date else 0

if days_overdue <= 0:
    bucket = "current"
elif days_overdue <= 30:
    bucket = "days_1_30"
elif days_overdue <= 60:
    bucket = "days_31_60"
elif days_overdue <= 90:
    bucket = "days_61_90"
else:
    bucket = "days_90_plus"
```

### Data Structure
```python
supplier_data = {
    "supplier": Supplier object,
    "current": Decimal,
    "days_1_30": Decimal,
    "days_31_60": Decimal,
    "days_61_90": Decimal,
    "days_90_plus": Decimal,
    "total": Decimal,
    "bills": [list of bill details]
}
```

## Files Modified

1. **apps/accounting/views.py** - Added ~300 lines
   - `aged_payables_report()` view function
   - `_export_aged_payables_pdf()` helper function
   - `_export_aged_payables_excel()` helper function

2. **apps/accounting/urls.py** - Added 1 line
   - URL pattern for aged payables report

3. **templates/accounting/bills/list.html** - Modified header
   - Added "Aged Payables" button

4. **templates/accounting/reports/aged_payables.html** - Created ~300 lines
   - Complete report template with all features

## Testing Recommendations

### Manual Testing
1. Navigate to Bills page and click "Aged Payables" button
2. Verify report displays with correct aging buckets
3. Test date filter with different dates
4. Export to PDF and verify formatting
5. Export to Excel and verify formatting
6. Test with no unpaid bills (empty state)
7. Test with multiple suppliers
8. Verify tenant isolation (bills from other tenants not shown)

### Test Scenarios
- **Scenario 1**: Bills with various due dates
  - Current bills (due in future)
  - Bills 15 days overdue
  - Bills 45 days overdue
  - Bills 75 days overdue
  - Bills 120 days overdue

- **Scenario 2**: Multiple suppliers
  - Each supplier with bills in different buckets
  - Verify totals calculated correctly

- **Scenario 3**: Export functionality
  - PDF export with landscape orientation
  - Excel export with proper formatting
  - Verify filenames include date

## Dependencies
- ✅ ReportLab (already in requirements.txt)
- ✅ openpyxl (already in requirements.txt)
- ✅ Bill model with due_date and amount_due
- ✅ Supplier model from procurement app

## Next Steps
Task 2.7 is complete. The next task in the implementation plan is:
- **Task 2.8**: Create supplier statement report (backend + frontend)

## Notes
- The report uses the Bill model's `amount_due` property which calculates `total - amount_paid`
- Only bills with status APPROVED or PARTIALLY_PAID are included
- PAID and VOID bills are excluded from the report
- The aging calculation is based on the `as_of_date` parameter, defaulting to today
- All amounts are displayed with 2 decimal places
- Color coding helps identify urgency: green (current), yellow (1-30), orange (31-60), red (61-90), dark red (90+)
