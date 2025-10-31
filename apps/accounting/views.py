"""
Views for the accounting module.
"""

import logging
from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.decorators import tenant_access_required

from .models import AccountingConfiguration, JewelryEntity
from .services import AccountingService

logger = logging.getLogger(__name__)


@login_required
@tenant_access_required
def accounting_dashboard(request):
    """
    Main accounting dashboard landing page.
    """
    # Check if accounting is set up
    try:
        JewelryEntity.objects.get(tenant=request.user.tenant)
        is_setup = True
    except JewelryEntity.DoesNotExist:
        is_setup = False

    # Get quick stats
    context = {
        "is_setup": is_setup,
        "page_title": "Accounting Dashboard",
    }

    if is_setup:
        # Get current month financial summary
        end_date = date.today()
        start_date = date(end_date.year, end_date.month, 1)
        reports = AccountingService.get_financial_reports(request.user.tenant, start_date, end_date)

        context.update(
            {
                "reports": reports,
                "start_date": start_date,
                "end_date": end_date,
            }
        )

    return render(request, "accounting/dashboard.html", context)


@login_required
@tenant_access_required
def financial_reports(request):
    """
    Display financial reports dashboard.
    """
    # Get date range from request or default to current month
    end_date = date.today()
    start_date = date(end_date.year, end_date.month, 1)

    if request.GET.get("start_date"):
        start_date = datetime.strptime(request.GET["start_date"], "%Y-%m-%d").date()
    if request.GET.get("end_date"):
        end_date = datetime.strptime(request.GET["end_date"], "%Y-%m-%d").date()

    # Get financial reports
    reports = AccountingService.get_financial_reports(request.user.tenant, start_date, end_date)

    context = {
        "reports": reports,
        "start_date": start_date,
        "end_date": end_date,
        "page_title": "Financial Reports",
    }

    return render(request, "accounting/financial_reports.html", context)


@login_required
@tenant_access_required
def accounting_configuration(request):
    """
    Display and update accounting configuration.
    """
    config, created = AccountingConfiguration.objects.get_or_create(tenant=request.user.tenant)

    if request.method == "POST":
        # Update configuration
        config.use_automatic_journal_entries = (
            request.POST.get("use_automatic_journal_entries") == "on"
        )
        config.inventory_valuation_method = request.POST.get("inventory_valuation_method", "FIFO")
        config.default_cash_account = request.POST.get("default_cash_account", "1001")
        config.default_card_account = request.POST.get("default_card_account", "1002")
        config.default_inventory_account = request.POST.get("default_inventory_account", "1200")
        config.default_cogs_account = request.POST.get("default_cogs_account", "5001")
        config.default_sales_account = request.POST.get("default_sales_account", "4001")
        config.default_tax_account = request.POST.get("default_tax_account", "2003")

        config.save()
        messages.success(request, "Accounting configuration updated successfully.")

    context = {"config": config, "page_title": "Accounting Configuration"}

    return render(request, "accounting/configuration.html", context)


@login_required
@tenant_access_required
def chart_of_accounts(request):
    """
    Display chart of accounts.
    """
    try:
        jewelry_entity = JewelryEntity.objects.get(tenant=request.user.tenant)
        entity = jewelry_entity.ledger_entity

        # Get chart of accounts
        coa = entity.chartofaccountmodel_set.first()
        accounts = coa.accountmodel_set.all().order_by("code") if coa else []

        context = {"accounts": accounts, "entity": entity, "page_title": "Chart of Accounts"}

    except JewelryEntity.DoesNotExist:
        messages.error(request, "Accounting not set up for this tenant.")
        context = {"accounts": [], "entity": None, "page_title": "Chart of Accounts"}

    return render(request, "accounting/chart_of_accounts.html", context)


@login_required
@tenant_access_required
@require_http_methods(["GET"])
def account_balance_api(request, account_code):
    """
    API endpoint to get account balance.
    """
    as_of_date = request.GET.get("as_of_date")
    if as_of_date:
        as_of_date = datetime.strptime(as_of_date, "%Y-%m-%d").date()
    else:
        as_of_date = date.today()

    balance = AccountingService.get_account_balance(request.user.tenant, account_code, as_of_date)

    return JsonResponse(
        {
            "account_code": account_code,
            "balance": str(balance),
            "as_of_date": as_of_date.isoformat(),
        }
    )


@login_required
@tenant_access_required
@require_http_methods(["POST"])
def setup_accounting_api(request):
    """
    API endpoint to set up accounting for tenant.
    """
    try:
        with transaction.atomic():
            jewelry_entity = AccountingService.setup_tenant_accounting(
                request.user.tenant, request.user
            )

            return JsonResponse(
                {
                    "success": True,
                    "message": "Accounting set up successfully",
                    "entity_id": str(jewelry_entity.ledger_entity.uuid),
                }
            )

    except Exception as e:
        import traceback

        logger.error(f"Setup accounting API error: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return JsonResponse(
            {"success": False, "message": f"Failed to set up accounting: {str(e)}"}, status=500
        )


@login_required
@tenant_access_required
@require_http_methods(["GET"])
def export_financial_reports_pdf(request):
    """
    Export financial reports to PDF.
    """
    try:
        # Get date range from request or default to current month
        end_date = date.today()
        start_date = date(end_date.year, end_date.month, 1)

        if request.GET.get("start_date"):
            start_date = datetime.strptime(request.GET["start_date"], "%Y-%m-%d").date()
        if request.GET.get("end_date"):
            end_date = datetime.strptime(request.GET["end_date"], "%Y-%m-%d").date()

        # Generate PDF
        pdf_data = AccountingService.export_financial_reports_to_pdf(
            request.user.tenant, start_date, end_date
        )

        # Create response
        from django.http import HttpResponse

        response = HttpResponse(pdf_data, content_type="application/pdf")
        filename = f"{request.user.tenant.slug}_financial_reports_{start_date}_{end_date}.pdf"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        logger.error(f"Failed to export PDF: {str(e)}")
        messages.error(request, f"Failed to export PDF: {str(e)}")
        return redirect("accounting:financial_reports")


@login_required
@tenant_access_required
@require_http_methods(["GET"])
def export_financial_reports_excel(request):
    """
    Export financial reports to Excel.
    """
    try:
        # Get date range from request or default to current month
        end_date = date.today()
        start_date = date(end_date.year, end_date.month, 1)

        if request.GET.get("start_date"):
            start_date = datetime.strptime(request.GET["start_date"], "%Y-%m-%d").date()
        if request.GET.get("end_date"):
            end_date = datetime.strptime(request.GET["end_date"], "%Y-%m-%d").date()

        # Generate Excel
        excel_data = AccountingService.export_financial_reports_to_excel(
            request.user.tenant, start_date, end_date
        )

        # Create response
        from django.http import HttpResponse

        response = HttpResponse(
            excel_data,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        filename = f"{request.user.tenant.slug}_financial_reports_{start_date}_{end_date}.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        logger.error(f"Failed to export Excel: {str(e)}")
        messages.error(request, f"Failed to export Excel: {str(e)}")
        return redirect("accounting:financial_reports")


@login_required
@tenant_access_required
def journal_entries(request):
    """
    Display journal entries list (legacy view - redirects to journal_entry_list).
    """
    return redirect("accounting:journal_entry_list")


@login_required
@tenant_access_required
def general_ledger(request):
    """
    Display general ledger with all transactions.
    """
    try:
        jewelry_entity = JewelryEntity.objects.get(tenant=request.user.tenant)
        entity = jewelry_entity.ledger_entity

        # Get date range and account filter
        end_date = date.today()
        start_date = date(end_date.year, end_date.month, 1)
        account_code = request.GET.get("account")

        if request.GET.get("start_date"):
            start_date = datetime.strptime(request.GET["start_date"], "%Y-%m-%d").date()
        if request.GET.get("end_date"):
            end_date = datetime.strptime(request.GET["end_date"], "%Y-%m-%d").date()

        # Get chart of accounts
        coa = entity.chartofaccountmodel_set.first()
        accounts = coa.accountmodel_set.all().order_by("code") if coa else []

        # Get transactions
        from django_ledger.models import TransactionModel

        transactions = TransactionModel.objects.filter(
            journal_entry__ledger__entity=entity,
            journal_entry__timestamp__date__gte=start_date,
            journal_entry__timestamp__date__lte=end_date,
        ).select_related("journal_entry", "account")

        if account_code:
            transactions = transactions.filter(account__code=account_code)

        transactions = transactions.order_by("-journal_entry__timestamp")

        context = {
            "transactions": transactions,
            "accounts": accounts,
            "selected_account": account_code,
            "start_date": start_date,
            "end_date": end_date,
            "page_title": "General Ledger",
        }

    except JewelryEntity.DoesNotExist:
        messages.error(request, "Accounting not set up for this tenant.")
        context = {"transactions": [], "accounts": [], "page_title": "General Ledger"}

    return render(request, "accounting/general_ledger.html", context)


@login_required
@tenant_access_required
def accounts_payable(request):
    """
    Display accounts payable dashboard.
    """
    from apps.procurement.models import PurchaseOrder

    # Get outstanding purchase orders
    outstanding_pos = PurchaseOrder.objects.filter(
        tenant=request.user.tenant, status__in=["APPROVED", "SENT", "PARTIALLY_RECEIVED"]
    ).select_related("supplier")

    # Calculate totals
    total_payable = sum(po.total for po in outstanding_pos)
    overdue_pos = [
        po
        for po in outstanding_pos
        if po.expected_delivery_date and po.expected_delivery_date < date.today()
    ]
    total_overdue = sum(po.total for po in overdue_pos)

    context = {
        "outstanding_pos": outstanding_pos,
        "total_payable": total_payable,
        "overdue_count": len(overdue_pos),
        "total_overdue": total_overdue,
        "page_title": "Accounts Payable",
    }

    return render(request, "accounting/accounts_payable.html", context)


@login_required
@tenant_access_required
def accounts_receivable(request):
    """
    Display accounts receivable dashboard.
    """
    from apps.sales.models import Sale

    # Get sales with outstanding balances (if you have credit sales)
    # For now, showing recent sales
    recent_sales = (
        Sale.objects.filter(tenant=request.user.tenant)
        .select_related("customer", "branch")
        .order_by("-created_at")[:50]
    )

    # Calculate totals
    total_sales = sum(sale.total for sale in recent_sales)

    context = {
        "recent_sales": recent_sales,
        "total_sales": total_sales,
        "page_title": "Accounts Receivable",
    }

    return render(request, "accounting/accounts_receivable.html", context)


@login_required
@tenant_access_required
def bank_reconciliation(request):
    """
    Display bank reconciliation interface.
    """
    try:
        jewelry_entity = JewelryEntity.objects.get(tenant=request.user.tenant)
        entity = jewelry_entity.ledger_entity

        # Get cash/bank accounts
        coa = entity.chartofaccountmodel_set.first()
        bank_accounts = []
        if coa:
            bank_accounts = coa.accountmodel_set.filter(
                role__in=["ASSET_CA_CASH", "ASSET_CA_CHECKING", "ASSET_CA_SAVINGS"]
            ).order_by("code")

        # Get recent transactions for selected account
        account_code = request.GET.get("account")
        transactions = []

        if account_code:
            from django_ledger.models import TransactionModel

            end_date = date.today()
            start_date = date(end_date.year, end_date.month, 1)

            transactions = (
                TransactionModel.objects.filter(
                    journal_entry__ledger__entity=entity,
                    account__code=account_code,
                    journal_entry__timestamp__date__gte=start_date,
                    journal_entry__timestamp__date__lte=end_date,
                )
                .select_related("journal_entry", "account")
                .order_by("-journal_entry__timestamp")
            )

        context = {
            "bank_accounts": bank_accounts,
            "selected_account": account_code,
            "transactions": transactions,
            "page_title": "Bank Reconciliation",
        }

    except JewelryEntity.DoesNotExist:
        messages.error(request, "Accounting not set up for this tenant.")
        context = {"bank_accounts": [], "transactions": [], "page_title": "Bank Reconciliation"}

    return render(request, "accounting/bank_reconciliation.html", context)


@login_required
@tenant_access_required
def add_account(request):
    """
    Create a new account in the chart of accounts.
    """
    try:
        jewelry_entity = JewelryEntity.objects.get(tenant=request.user.tenant)
        entity = jewelry_entity.ledger_entity
        coa = entity.chartofaccountmodel_set.first()

        if not coa:
            messages.error(request, "Chart of Accounts not found. Please set up accounting first.")
            return redirect("accounting:dashboard")

        if request.method == "POST":
            code = request.POST.get("code")
            name = request.POST.get("name")
            role = request.POST.get("role")
            balance_type = request.POST.get("balance_type")
            active = request.POST.get("active") == "1"

            # Check if account code already exists
            from django_ledger.models import AccountModel

            if AccountModel.objects.filter(coa_model=coa, code=code).exists():
                messages.error(request, f"Account with code {code} already exists.")
            else:
                # Create the account as a root node in the MPTT tree
                # AccountModel uses MPTT (Modified Preorder Tree Traversal) for hierarchical structure
                AccountModel.add_root(
                    coa_model=coa,
                    code=code,
                    name=name,
                    role=role,
                    balance_type=balance_type,
                    active=active,
                )

                messages.success(request, f"Account {code} - {name} created successfully.")
                return redirect("accounting:chart_of_accounts")

        context = {"page_title": "Add Account"}
        return render(request, "accounting/account_form.html", context)

    except JewelryEntity.DoesNotExist:
        messages.error(request, "Accounting not set up for this tenant.")
        return redirect("accounting:dashboard")


@login_required
@tenant_access_required
def edit_account(request, account_code):
    """
    Edit an existing account in the chart of accounts.
    """
    try:
        jewelry_entity = JewelryEntity.objects.get(tenant=request.user.tenant)
        entity = jewelry_entity.ledger_entity
        coa = entity.chartofaccountmodel_set.first()

        if not coa:
            messages.error(request, "Chart of Accounts not found.")
            return redirect("accounting:dashboard")

        from django_ledger.models import AccountModel

        account = AccountModel.objects.get(coa_model=coa, code=account_code)

        if request.method == "POST":
            account.name = request.POST.get("name")
            account.role = request.POST.get("role")
            account.balance_type = request.POST.get("balance_type")
            account.active = request.POST.get("active") == "1"
            account.save()

            messages.success(
                request, f"Account {account.code} - {account.name} updated successfully."
            )
            return redirect("accounting:chart_of_accounts")

        context = {"account": account, "page_title": "Edit Account"}
        return render(request, "accounting/account_form.html", context)

    except JewelryEntity.DoesNotExist:
        messages.error(request, "Accounting not set up for this tenant.")
        return redirect("accounting:dashboard")
    except AccountModel.DoesNotExist:
        messages.error(request, f"Account {account_code} not found.")
        return redirect("accounting:chart_of_accounts")


# ============================================================================
# Manual Journal Entry Views (Task 1.2)
# ============================================================================


@login_required
@tenant_access_required
def journal_entry_list(request):
    """
    Display journal entries list with filtering by date, status, account.

    Implements filtering and pagination for manual journal entries.
    Requirement: 1.1, 1.2, 1.7, 1.8
    """
    try:
        jewelry_entity = JewelryEntity.objects.get(tenant=request.user.tenant)
        entity = jewelry_entity.ledger_entity

        # Get date range from request or default to current month
        end_date = date.today()
        start_date = date(end_date.year, end_date.month, 1)

        if request.GET.get("start_date"):
            start_date = datetime.strptime(request.GET["start_date"], "%Y-%m-%d").date()
        if request.GET.get("end_date"):
            end_date = datetime.strptime(request.GET["end_date"], "%Y-%m-%d").date()

        # Get filter parameters
        status_filter = request.GET.get("status", "")
        account_filter = request.GET.get("account", "")

        # Get journal entries from django-ledger with tenant filtering
        from django_ledger.models import JournalEntryModel

        entries = (
            JournalEntryModel.objects.filter(
                ledger__entity=entity,
                timestamp__date__gte=start_date,
                timestamp__date__lte=end_date,
            )
            .select_related("ledger")
            .prefetch_related("transactionmodel_set__account")
        )

        # Apply status filter
        if status_filter:
            if status_filter == "posted":
                entries = entries.filter(posted=True)
            elif status_filter == "unposted":
                entries = entries.filter(posted=False)

        # Apply account filter
        if account_filter:
            entries = entries.filter(transactionmodel__account__code=account_filter).distinct()

        entries = entries.order_by("-timestamp")

        # Get chart of accounts for filter dropdown
        coa = entity.chartofaccountmodel_set.first()
        accounts = []
        if coa:
            from django_ledger.models import AccountModel

            accounts = AccountModel.objects.filter(coa_model=coa, active=True).order_by("code")

        # Audit logging
        from apps.core.audit_models import AuditLog

        AuditLog.objects.create(
            tenant=request.user.tenant,
            user=request.user,
            category=AuditLog.CATEGORY_DATA,
            action=AuditLog.ACTION_API_GET,
            severity=AuditLog.SEVERITY_INFO,
            description=f"Viewed journal entries list (filters: status={status_filter}, account={account_filter})",
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            request_method=request.method,
            request_path=request.path,
        )

        context = {
            "entries": entries,
            "start_date": start_date,
            "end_date": end_date,
            "status_filter": status_filter,
            "account_filter": account_filter,
            "accounts": accounts,
            "page_title": "Journal Entries",
        }

    except JewelryEntity.DoesNotExist:
        messages.error(request, "Accounting not set up for this tenant.")
        context = {
            "entries": [],
            "accounts": [],
            "page_title": "Journal Entries",
        }

    return render(request, "accounting/journal_entries/list.html", context)


@login_required
@tenant_access_required
def journal_entry_create(request):  # noqa: C901
    """
    Create a new manual journal entry with formset handling.

    Handles dynamic line items and validates that debits equal credits.
    Requirement: 1.1, 1.2, 1.3, 1.7, 1.8
    """
    try:
        jewelry_entity = JewelryEntity.objects.get(tenant=request.user.tenant)
        entity = jewelry_entity.ledger_entity

        # Get chart of accounts
        coa = entity.chartofaccountmodel_set.first()
        if not coa:
            messages.error(request, "Chart of Accounts not found. Please set up accounting first.")
            return redirect("accounting:dashboard")

        # Get the ledger
        ledger = entity.ledgermodel_set.first()
        if not ledger:
            messages.error(request, "Ledger not found. Please set up accounting first.")
            return redirect("accounting:dashboard")

        from .forms import JournalEntryForm, JournalEntryLineInlineFormSet

        if request.method == "POST":
            form = JournalEntryForm(request.POST, tenant=request.user.tenant, user=request.user)

            # Create a temporary journal entry instance for the formset
            if form.is_valid():
                with transaction.atomic():
                    # Create journal entry (unposted)
                    journal_entry = form.save(commit=False)
                    journal_entry.ledger = ledger
                    journal_entry.posted = False
                    journal_entry.save()

                    # Handle formset
                    formset = JournalEntryLineInlineFormSet(
                        request.POST,
                        instance=journal_entry,
                        tenant=request.user.tenant,
                        coa=coa,
                    )

                    if formset.is_valid():
                        # Save the lines
                        lines = formset.save(commit=False)

                        for line in lines:
                            # Get debit/credit from cleaned_data
                            for form_instance in formset.forms:
                                if form_instance.instance == line:
                                    debit = form_instance.cleaned_data.get("debit") or 0
                                    credit = form_instance.cleaned_data.get("credit") or 0

                                    # Set transaction type and amount
                                    if debit > 0:
                                        line.tx_type = "debit"
                                        line.amount = debit
                                    else:
                                        line.tx_type = "credit"
                                        line.amount = credit

                                    line.journal_entry = journal_entry
                                    line.save()
                                    break

                        # Delete removed lines
                        for obj in formset.deleted_objects:
                            obj.delete()

                        # Audit logging
                        from apps.core.audit_models import AuditLog

                        AuditLog.objects.create(
                            tenant=request.user.tenant,
                            user=request.user,
                            category=AuditLog.CATEGORY_DATA,
                            action=AuditLog.ACTION_CREATE,
                            severity=AuditLog.SEVERITY_INFO,
                            description=f"Created journal entry: {journal_entry.description}",
                            ip_address=request.META.get("REMOTE_ADDR"),
                            user_agent=request.META.get("HTTP_USER_AGENT", ""),
                            request_method=request.method,
                            request_path=request.path,
                        )

                        messages.success(
                            request,
                            "Journal entry created successfully. Entry is unposted and can be edited.",
                        )
                        return redirect("accounting:journal_entry_detail", pk=journal_entry.uuid)
                    else:
                        # Formset validation failed
                        messages.error(
                            request, "Please correct the errors in the journal entry lines."
                        )
                        # Delete the journal entry since formset failed
                        journal_entry.delete()
            else:
                # Form validation failed
                formset = JournalEntryLineInlineFormSet(
                    request.POST,
                    tenant=request.user.tenant,
                    coa=coa,
                )
        else:
            form = JournalEntryForm(tenant=request.user.tenant, user=request.user)
            formset = JournalEntryLineInlineFormSet(tenant=request.user.tenant, coa=coa)

        context = {
            "form": form,
            "formset": formset,
            "page_title": "Create Journal Entry",
        }

    except JewelryEntity.DoesNotExist:
        messages.error(request, "Accounting not set up for this tenant.")
        return redirect("accounting:dashboard")

    return render(request, "accounting/journal_entries/form.html", context)


@login_required
@tenant_access_required
def journal_entry_detail(request, pk):
    """
    Display journal entry details (read-only).

    Shows all line items and audit trail information.
    Requirement: 1.1, 1.2, 1.6, 1.8
    """
    try:
        jewelry_entity = JewelryEntity.objects.get(tenant=request.user.tenant)
        entity = jewelry_entity.ledger_entity

        # Get journal entry with tenant filtering
        from django_ledger.models import JournalEntryModel

        entry = (
            JournalEntryModel.objects.filter(ledger__entity=entity, uuid=pk)
            .select_related("ledger")
            .prefetch_related("transactionmodel_set__account")
            .first()
        )

        if not entry:
            messages.error(request, "Journal entry not found.")
            return redirect("accounting:journal_entry_list")

        # Calculate totals
        from decimal import Decimal

        total_debits = Decimal("0.00")
        total_credits = Decimal("0.00")

        for txn in entry.transactionmodel_set.all():
            if txn.tx_type == "debit":
                total_debits += txn.amount
            else:
                total_credits += txn.amount

        # Audit logging
        from apps.core.audit_models import AuditLog

        AuditLog.objects.create(
            tenant=request.user.tenant,
            user=request.user,
            category=AuditLog.CATEGORY_DATA,
            action=AuditLog.ACTION_API_GET,
            severity=AuditLog.SEVERITY_INFO,
            description=f"Viewed journal entry detail: {entry.description}",
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            request_method=request.method,
            request_path=request.path,
        )

        context = {
            "entry": entry,
            "total_debits": total_debits,
            "total_credits": total_credits,
            "is_balanced": total_debits == total_credits,
            "page_title": f"Journal Entry: {entry.description}",
        }

    except JewelryEntity.DoesNotExist:
        messages.error(request, "Accounting not set up for this tenant.")
        return redirect("accounting:dashboard")

    return render(request, "accounting/journal_entries/detail.html", context)


@login_required
@tenant_access_required
@require_http_methods(["POST"])
def journal_entry_post(request, pk):
    """
    Post a journal entry to the general ledger.

    Makes the entry immutable and updates account balances.
    Requirement: 1.4, 1.7, 1.8
    """
    try:
        jewelry_entity = JewelryEntity.objects.get(tenant=request.user.tenant)
        entity = jewelry_entity.ledger_entity

        # Get journal entry with tenant filtering
        from django_ledger.models import JournalEntryModel

        entry = JournalEntryModel.objects.filter(ledger__entity=entity, uuid=pk).first()

        if not entry:
            messages.error(request, "Journal entry not found.")
            return redirect("accounting:journal_entry_list")

        # Check if already posted
        if entry.posted:
            messages.warning(request, "Journal entry is already posted.")
            return redirect("accounting:journal_entry_detail", pk=pk)

        # Validate that debits equal credits
        from decimal import Decimal

        total_debits = Decimal("0.00")
        total_credits = Decimal("0.00")

        for txn in entry.transactionmodel_set.all():
            if txn.tx_type == "debit":
                total_debits += txn.amount
            else:
                total_credits += txn.amount

        if total_debits != total_credits:
            messages.error(
                request,
                f"Cannot post journal entry: debits (${total_debits:,.2f}) do not equal credits (${total_credits:,.2f}).",
            )
            return redirect("accounting:journal_entry_detail", pk=pk)

        # Post the entry
        with transaction.atomic():
            entry.posted = True
            entry.save()

            # Audit logging
            from apps.core.audit_models import AuditLog

            AuditLog.objects.create(
                tenant=request.user.tenant,
                user=request.user,
                category=AuditLog.CATEGORY_DATA,
                action=AuditLog.ACTION_UPDATE,
                severity=AuditLog.SEVERITY_INFO,
                description=f"Posted journal entry: {entry.description}",
                old_values={"posted": False},
                new_values={"posted": True},
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                request_method=request.method,
                request_path=request.path,
            )

            messages.success(
                request,
                "Journal entry posted successfully. Entry is now immutable and affects account balances.",
            )

    except JewelryEntity.DoesNotExist:
        messages.error(request, "Accounting not set up for this tenant.")
        return redirect("accounting:dashboard")

    return redirect("accounting:journal_entry_detail", pk=pk)


@login_required
@tenant_access_required
def journal_entry_reverse(request, pk):
    """
    Create a reversing journal entry.

    Creates a new entry with debits and credits swapped.
    Requirement: 1.5, 1.7, 1.8
    """
    try:
        jewelry_entity = JewelryEntity.objects.get(tenant=request.user.tenant)
        entity = jewelry_entity.ledger_entity

        # Get original journal entry with tenant filtering
        from django_ledger.models import JournalEntryModel

        original_entry = JournalEntryModel.objects.filter(ledger__entity=entity, uuid=pk).first()

        if not original_entry:
            messages.error(request, "Journal entry not found.")
            return redirect("accounting:journal_entry_list")

        # Check if original entry is posted
        if not original_entry.posted:
            messages.error(request, "Cannot reverse an unposted journal entry.")
            return redirect("accounting:journal_entry_detail", pk=pk)

        if request.method == "POST":
            # Create reversing entry
            with transaction.atomic():
                # Get the ledger
                ledger = entity.ledgermodel_set.first()

                # Create new journal entry
                reversing_entry = JournalEntryModel.objects.create(
                    ledger=ledger,
                    description=f"REVERSAL: {original_entry.description}",
                    posted=False,  # Create as unposted so user can review
                )

                # Create reversed transactions
                from django_ledger.models import TransactionModel

                for original_txn in original_entry.transactionmodel_set.all():
                    # Swap debit/credit
                    reversed_tx_type = "credit" if original_txn.tx_type == "debit" else "debit"

                    TransactionModel.objects.create(
                        journal_entry=reversing_entry,
                        account=original_txn.account,
                        amount=original_txn.amount,
                        tx_type=reversed_tx_type,
                        description=f"Reversal of: {original_txn.description or ''}",
                    )

                # Audit logging
                from apps.core.audit_models import AuditLog

                AuditLog.objects.create(
                    tenant=request.user.tenant,
                    user=request.user,
                    category=AuditLog.CATEGORY_DATA,
                    action=AuditLog.ACTION_CREATE,
                    severity=AuditLog.SEVERITY_INFO,
                    description=f"Created reversing entry for: {original_entry.description}",
                    metadata={
                        "original_entry_id": str(original_entry.uuid),
                        "reversing_entry_id": str(reversing_entry.uuid),
                    },
                    ip_address=request.META.get("REMOTE_ADDR"),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                    request_method=request.method,
                    request_path=request.path,
                )

                messages.success(
                    request,
                    "Reversing entry created successfully. Please review and post the entry.",
                )
                return redirect("accounting:journal_entry_detail", pk=reversing_entry.uuid)

        context = {
            "original_entry": original_entry,
            "page_title": f"Reverse Journal Entry: {original_entry.description}",
        }

    except JewelryEntity.DoesNotExist:
        messages.error(request, "Accounting not set up for this tenant.")
        return redirect("accounting:dashboard")

    return render(request, "accounting/journal_entries/confirm_reverse.html", context)


@login_required
@tenant_access_required
def journal_entry_edit(request, pk):  # noqa: C901
    """
    Edit an unposted journal entry.

    Only allows editing of unposted entries. Posted entries are immutable.
    Requirement: 1.5, 1.7, 1.8
    """
    try:
        jewelry_entity = JewelryEntity.objects.get(tenant=request.user.tenant)
        entity = jewelry_entity.ledger_entity

        # Get journal entry with tenant filtering
        from django_ledger.models import JournalEntryModel

        entry = JournalEntryModel.objects.filter(ledger__entity=entity, uuid=pk).first()

        if not entry:
            messages.error(request, "Journal entry not found.")
            return redirect("accounting:journal_entry_list")

        # Check if entry is posted
        if entry.posted:
            messages.error(
                request,
                "Cannot edit a posted journal entry. Posted entries are immutable. Please create a reversing entry instead.",
            )
            return redirect("accounting:journal_entry_detail", pk=pk)

        # Get chart of accounts
        coa = entity.chartofaccountmodel_set.first()
        if not coa:
            messages.error(request, "Chart of Accounts not found.")
            return redirect("accounting:dashboard")

        from .forms import JournalEntryForm, JournalEntryLineInlineFormSet

        if request.method == "POST":
            form = JournalEntryForm(
                request.POST, instance=entry, tenant=request.user.tenant, user=request.user
            )

            if form.is_valid():
                with transaction.atomic():
                    journal_entry = form.save(commit=False)
                    journal_entry.save()

                    # Handle formset
                    formset = JournalEntryLineInlineFormSet(
                        request.POST,
                        instance=journal_entry,
                        tenant=request.user.tenant,
                        coa=coa,
                    )

                    if formset.is_valid():
                        # Delete all existing lines
                        journal_entry.transactionmodel_set.all().delete()

                        # Save new lines
                        lines = formset.save(commit=False)

                        for line in lines:
                            # Get debit/credit from cleaned_data
                            for form_instance in formset.forms:
                                if form_instance.instance == line:
                                    debit = form_instance.cleaned_data.get("debit") or 0
                                    credit = form_instance.cleaned_data.get("credit") or 0

                                    # Set transaction type and amount
                                    if debit > 0:
                                        line.tx_type = "debit"
                                        line.amount = debit
                                    else:
                                        line.tx_type = "credit"
                                        line.amount = credit

                                    line.journal_entry = journal_entry
                                    line.save()
                                    break

                        # Audit logging
                        from apps.core.audit_models import AuditLog

                        AuditLog.objects.create(
                            tenant=request.user.tenant,
                            user=request.user,
                            category=AuditLog.CATEGORY_DATA,
                            action=AuditLog.ACTION_UPDATE,
                            severity=AuditLog.SEVERITY_INFO,
                            description=f"Updated journal entry: {journal_entry.description}",
                            ip_address=request.META.get("REMOTE_ADDR"),
                            user_agent=request.META.get("HTTP_USER_AGENT", ""),
                            request_method=request.method,
                            request_path=request.path,
                        )

                        messages.success(request, "Journal entry updated successfully.")
                        return redirect("accounting:journal_entry_detail", pk=journal_entry.uuid)
                    else:
                        messages.error(
                            request, "Please correct the errors in the journal entry lines."
                        )
            else:
                formset = JournalEntryLineInlineFormSet(
                    request.POST,
                    instance=entry,
                    tenant=request.user.tenant,
                    coa=coa,
                )
        else:
            form = JournalEntryForm(instance=entry, tenant=request.user.tenant, user=request.user)
            formset = JournalEntryLineInlineFormSet(
                instance=entry, tenant=request.user.tenant, coa=coa
            )

        context = {
            "form": form,
            "formset": formset,
            "entry": entry,
            "page_title": f"Edit Journal Entry: {entry.description}",
        }

    except JewelryEntity.DoesNotExist:
        messages.error(request, "Accounting not set up for this tenant.")
        return redirect("accounting:dashboard")

    return render(request, "accounting/journal_entries/form.html", context)


@login_required
@tenant_access_required
@require_http_methods(["POST"])
def journal_entry_delete(request, pk):
    """
    Delete an unposted journal entry.

    Only allows deletion of unposted entries. Posted entries cannot be deleted.
    Requirement: 1.6, 1.7, 1.8
    """
    try:
        jewelry_entity = JewelryEntity.objects.get(tenant=request.user.tenant)
        entity = jewelry_entity.ledger_entity

        # Get journal entry with tenant filtering
        from django_ledger.models import JournalEntryModel

        entry = JournalEntryModel.objects.filter(ledger__entity=entity, uuid=pk).first()

        if not entry:
            messages.error(request, "Journal entry not found.")
            return redirect("accounting:journal_entry_list")

        # Check if entry is posted
        if entry.posted:
            messages.error(
                request,
                "Cannot delete a posted journal entry. Posted entries are immutable. Please create a reversing entry instead.",
            )
            return redirect("accounting:journal_entry_detail", pk=pk)

        # Store description for audit log
        description = entry.description

        # Delete the entry
        with transaction.atomic():
            entry.delete()

            # Audit logging
            from apps.core.audit_models import AuditLog

            AuditLog.objects.create(
                tenant=request.user.tenant,
                user=request.user,
                category=AuditLog.CATEGORY_DATA,
                action=AuditLog.ACTION_DELETE,
                severity=AuditLog.SEVERITY_INFO,
                description=f"Deleted unposted journal entry: {description}",
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                request_method=request.method,
                request_path=request.path,
            )

            messages.success(request, f"Journal entry '{description}' deleted successfully.")

    except JewelryEntity.DoesNotExist:
        messages.error(request, "Accounting not set up for this tenant.")
        return redirect("accounting:dashboard")

    return redirect("accounting:journal_entry_list")
