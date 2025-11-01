"""
Views for the accounting module.
"""

import logging
from datetime import date, datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from django_ledger.models import AccountModel

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


# ============================================================================
# Supplier Accounting Views (Task 2.3)
# ============================================================================


@login_required
@tenant_access_required
def supplier_accounting_detail(request, supplier_id):
    """
    Display supplier accounting details with bills, payments, and balance.

    Extends existing supplier detail with accounting information including
    total purchases, outstanding balance, and payment history.

    Requirements: 2.7, 14.1, 14.2, 14.3, 14.7, 14.8
    """
    from decimal import Decimal

    from apps.procurement.models import Supplier

    from .bill_models import Bill, BillPayment

    try:
        # Get supplier with tenant filtering
        supplier = (
            Supplier.objects.filter(tenant=request.user.tenant, id=supplier_id)
            .select_related("tenant")
            .first()
        )

        if not supplier:
            messages.error(request, "Supplier not found.")
            return redirect("procurement:supplier_list")

        # Get all bills for this supplier with tenant filtering
        bills = (
            Bill.objects.filter(tenant=request.user.tenant, supplier=supplier)
            .select_related("supplier", "created_by", "approved_by")
            .prefetch_related("lines", "payments")
            .order_by("-bill_date")
        )

        # Calculate totals
        total_purchases = Decimal("0.00")
        outstanding_balance = Decimal("0.00")
        total_paid = Decimal("0.00")

        for bill in bills:
            total_purchases += bill.total
            outstanding_balance += bill.amount_due
            total_paid += bill.amount_paid

        # Get payment history (all payments for this supplier's bills)
        payment_history = (
            BillPayment.objects.filter(tenant=request.user.tenant, bill__supplier=supplier)
            .select_related("bill", "created_by")
            .order_by("-payment_date")[:20]  # Last 20 payments
        )

        # Get aging breakdown
        aging_buckets = {
            "Current": Decimal("0.00"),
            "1-30 days": Decimal("0.00"),
            "31-60 days": Decimal("0.00"),
            "61-90 days": Decimal("0.00"),
            "90+ days": Decimal("0.00"),
        }

        for bill in bills:
            if bill.amount_due > 0:
                aging_buckets[bill.aging_bucket] += bill.amount_due

        # Audit logging
        from apps.core.audit_models import AuditLog

        AuditLog.objects.create(
            tenant=request.user.tenant,
            user=request.user,
            category=AuditLog.CATEGORY_DATA,
            action=AuditLog.ACTION_API_GET,
            severity=AuditLog.SEVERITY_INFO,
            description=f"Viewed supplier accounting detail: {supplier.name}",
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            request_method=request.method,
            request_path=request.path,
        )

        context = {
            "supplier": supplier,
            "bills": bills,
            "payment_history": payment_history,
            "total_purchases": total_purchases,
            "outstanding_balance": outstanding_balance,
            "total_paid": total_paid,
            "aging_buckets": aging_buckets,
            "page_title": f"Supplier Accounting: {supplier.name}",
        }

        return render(request, "accounting/suppliers/accounting_detail.html", context)

    except Exception as e:
        logger.error(f"Error in supplier_accounting_detail: {str(e)}")
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect("procurement:supplier_list")


@login_required
@tenant_access_required
def supplier_statement(request, supplier_id):
    """
    Generate supplier statement showing all transactions and current balance.

    Displays all bills and payments for a supplier within a date range,
    with opening and closing balances.

    Requirements: 2.8, 14.3, 14.7, 14.8
    """
    from decimal import Decimal

    from apps.procurement.models import Supplier

    from .bill_models import Bill, BillPayment

    try:
        # Get supplier with tenant filtering
        supplier = (
            Supplier.objects.filter(tenant=request.user.tenant, id=supplier_id)
            .select_related("tenant")
            .first()
        )

        if not supplier:
            messages.error(request, "Supplier not found.")
            return redirect("procurement:supplier_list")

        # Get date range from request or default to current month
        end_date = date.today()
        start_date = date(end_date.year, end_date.month, 1)

        if request.GET.get("start_date"):
            start_date = datetime.strptime(request.GET["start_date"], "%Y-%m-%d").date()
        if request.GET.get("end_date"):
            end_date = datetime.strptime(request.GET["end_date"], "%Y-%m-%d").date()

        # Get bills within date range with tenant filtering
        bills = (
            Bill.objects.filter(
                tenant=request.user.tenant,
                supplier=supplier,
                bill_date__range=[start_date, end_date],
            )
            .select_related("supplier", "created_by")
            .prefetch_related("lines", "payments")
            .order_by("bill_date")
        )

        # Get payments within date range with tenant filtering
        payments = (
            BillPayment.objects.filter(
                tenant=request.user.tenant,
                bill__supplier=supplier,
                payment_date__range=[start_date, end_date],
            )
            .select_related("bill", "created_by")
            .order_by("payment_date")
        )

        # Calculate opening balance (bills before start_date minus payments before start_date)
        opening_bills = Bill.objects.filter(
            tenant=request.user.tenant, supplier=supplier, bill_date__lt=start_date
        ).aggregate(total=models.Sum("total"))["total"] or Decimal("0.00")

        opening_payments = BillPayment.objects.filter(
            tenant=request.user.tenant, bill__supplier=supplier, payment_date__lt=start_date
        ).aggregate(total=models.Sum("amount"))["total"] or Decimal("0.00")

        opening_balance = opening_bills - opening_payments

        # Calculate period totals
        period_bills_total = bills.aggregate(total=models.Sum("total"))["total"] or Decimal("0.00")
        period_payments_total = payments.aggregate(total=models.Sum("amount"))["total"] or Decimal(
            "0.00"
        )

        # Calculate closing balance
        closing_balance = opening_balance + period_bills_total - period_payments_total

        # Combine bills and payments into a single transaction list
        transactions = []

        for bill in bills:
            transactions.append(
                {
                    "date": bill.bill_date,
                    "type": "Bill",
                    "reference": bill.bill_number,
                    "description": f"Bill #{bill.bill_number}",
                    "debit": bill.total,
                    "credit": Decimal("0.00"),
                    "balance": None,  # Will calculate running balance below
                }
            )

        for payment in payments:
            transactions.append(
                {
                    "date": payment.payment_date,
                    "type": "Payment",
                    "reference": payment.reference_number or f"Payment #{payment.id}",
                    "description": f"Payment for Bill #{payment.bill.bill_number}",
                    "debit": Decimal("0.00"),
                    "credit": payment.amount,
                    "balance": None,
                }
            )

        # Sort by date
        transactions.sort(key=lambda x: x["date"])

        # Calculate running balance
        running_balance = opening_balance
        for txn in transactions:
            running_balance += txn["debit"] - txn["credit"]
            txn["balance"] = running_balance

        # Audit logging
        from apps.core.audit_models import AuditLog

        AuditLog.objects.create(
            tenant=request.user.tenant,
            user=request.user,
            category=AuditLog.CATEGORY_DATA,
            action=AuditLog.ACTION_API_GET,
            severity=AuditLog.SEVERITY_INFO,
            description=f"Generated supplier statement: {supplier.name} ({start_date} to {end_date})",
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            request_method=request.method,
            request_path=request.path,
        )

        context = {
            "supplier": supplier,
            "start_date": start_date,
            "end_date": end_date,
            "opening_balance": opening_balance,
            "closing_balance": closing_balance,
            "period_bills_total": period_bills_total,
            "period_payments_total": period_payments_total,
            "transactions": transactions,
            "page_title": f"Supplier Statement: {supplier.name}",
        }

        return render(request, "accounting/suppliers/statement.html", context)

    except Exception as e:
        logger.error(f"Error in supplier_statement: {str(e)}")
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect("procurement:supplier_list")


# ============================================================================
# Bill Management Views (Task 2.5)
# ============================================================================


@login_required
@tenant_access_required
def bill_list(request):
    """
    Display bills list with filtering by supplier, date range, status, and amount.

    Shows all bills for the tenant with aging information and status badges.
    Supports search and filtering.

    Requirements: 2.3, 2.7, 2.8
    """
    from decimal import Decimal

    from apps.procurement.models import Supplier

    from .bill_models import Bill

    try:
        # Get filter parameters
        supplier_filter = request.GET.get("supplier", "")
        status_filter = request.GET.get("status", "")
        start_date = request.GET.get("start_date", "")
        end_date = request.GET.get("end_date", "")
        min_amount = request.GET.get("min_amount", "")
        max_amount = request.GET.get("max_amount", "")
        search_query = request.GET.get("search", "")

        # Get all bills for this tenant
        bills = (
            Bill.objects.filter(tenant=request.user.tenant)
            .select_related("supplier", "created_by", "approved_by")
            .prefetch_related("lines", "payments")
        )

        # Apply filters
        if supplier_filter:
            bills = bills.filter(supplier_id=supplier_filter)

        if status_filter:
            bills = bills.filter(status=status_filter)

        if start_date:
            bills = bills.filter(bill_date__gte=datetime.strptime(start_date, "%Y-%m-%d").date())

        if end_date:
            bills = bills.filter(bill_date__lte=datetime.strptime(end_date, "%Y-%m-%d").date())

        if min_amount:
            bills = bills.filter(total__gte=Decimal(min_amount))

        if max_amount:
            bills = bills.filter(total__lte=Decimal(max_amount))

        if search_query:
            bills = bills.filter(
                models.Q(bill_number__icontains=search_query)
                | models.Q(supplier__name__icontains=search_query)
                | models.Q(notes__icontains=search_query)
            )

        bills = bills.order_by("-bill_date", "-created_at")

        # Calculate summary statistics
        total_bills = bills.count()
        total_amount = bills.aggregate(total=models.Sum("total"))["total"] or Decimal("0.00")
        total_outstanding = bills.aggregate(
            outstanding=models.Sum(models.F("total") - models.F("amount_paid"))
        )["outstanding"] or Decimal("0.00")

        # Get unpaid bills count
        unpaid_bills_count = bills.filter(status__in=["APPROVED", "PARTIALLY_PAID"]).count()

        # Get overdue bills count
        overdue_bills_count = bills.filter(
            status__in=["APPROVED", "PARTIALLY_PAID"], due_date__lt=date.today()
        ).count()

        # Get suppliers for filter dropdown
        suppliers = Supplier.objects.filter(tenant=request.user.tenant, is_active=True).order_by(
            "name"
        )

        # Audit logging
        from apps.core.audit_models import AuditLog

        AuditLog.objects.create(
            tenant=request.user.tenant,
            user=request.user,
            category=AuditLog.CATEGORY_DATA,
            action=AuditLog.ACTION_API_GET,
            severity=AuditLog.SEVERITY_INFO,
            description=f"Viewed bills list (filters: supplier={supplier_filter}, status={status_filter})",
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            request_method=request.method,
            request_path=request.path,
        )

        context = {
            "bills": bills,
            "suppliers": suppliers,
            "supplier_filter": supplier_filter,
            "status_filter": status_filter,
            "start_date": start_date,
            "end_date": end_date,
            "min_amount": min_amount,
            "max_amount": max_amount,
            "search_query": search_query,
            "total_bills": total_bills,
            "total_amount": total_amount,
            "total_outstanding": total_outstanding,
            "unpaid_bills_count": unpaid_bills_count,
            "overdue_bills_count": overdue_bills_count,
            "status_choices": Bill.STATUS_CHOICES,
            "page_title": "Bills",
        }

        return render(request, "accounting/bills/list.html", context)

    except Exception as e:
        logger.error(f"Error in bill_list: {str(e)}")
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect("accounting:dashboard")


@login_required
@tenant_access_required
def bill_create(request):  # noqa: C901
    """
    Create a new bill with automatic journal entry creation.

    Handles dynamic line items and creates journal entry debiting
    expense/asset accounts and crediting accounts payable.

    Requirements: 2.1, 2.2, 2.6, 2.7, 2.8
    """
    try:
        jewelry_entity = JewelryEntity.objects.get(tenant=request.user.tenant)
        entity = jewelry_entity.ledger_entity

        # Get chart of accounts (optional - can create bills without COA)
        coa = entity.chartofaccountmodel_set.first()
        if not coa:
            messages.warning(
                request,
                "Chart of Accounts not set up. Bills can be created but account codes won't be available.",
            )

        from .forms import BillForm, BillLineInlineFormSet

        if request.method == "POST":
            form = BillForm(request.POST, tenant=request.user.tenant, user=request.user)

            if form.is_valid():
                with transaction.atomic():
                    # Create bill
                    bill = form.save(commit=False)
                    bill.tenant = request.user.tenant
                    bill.created_by = request.user
                    bill.status = "DRAFT"
                    bill.subtotal = Decimal("0.00")
                    bill.total = Decimal("0.00")
                    bill.amount_paid = Decimal("0.00")
                    bill.save()

                    # Handle formset
                    formset = BillLineInlineFormSet(
                        request.POST, instance=bill, tenant=request.user.tenant, coa=coa
                    )

                    if formset.is_valid():
                        # Save the lines
                        lines = formset.save(commit=False)

                        for line in lines:
                            line.bill = bill
                            line.save()

                        # Delete removed lines
                        for obj in formset.deleted_objects:
                            obj.delete()

                        # Calculate totals
                        bill.calculate_totals()

                        # Create journal entry only if COA is set up
                        if coa:
                            try:
                                journal_entry = _create_bill_journal_entry(
                                    bill, request.user.tenant, entity, coa
                                )
                                bill.journal_entry = journal_entry
                            except Exception as je_error:
                                logger.warning(f"Could not create journal entry: {str(je_error)}")
                                messages.warning(
                                    request,
                                    "Bill created but journal entry could not be created. Please check account setup.",
                                )

                        bill.status = "APPROVED"  # Auto-approve for now
                        bill.approved_by = request.user
                        bill.approved_at = timezone.now()
                        bill.save()

                        # Audit logging
                        from apps.core.audit_models import AuditLog

                        AuditLog.objects.create(
                            tenant=request.user.tenant,
                            user=request.user,
                            category=AuditLog.CATEGORY_DATA,
                            action=AuditLog.ACTION_CREATE,
                            severity=AuditLog.SEVERITY_INFO,
                            description=f"Created bill: {bill.bill_number} for supplier {bill.supplier.name}",
                            metadata={
                                "bill_id": str(bill.id),
                                "bill_number": bill.bill_number,
                                "supplier": bill.supplier.name,
                                "total": str(bill.total),
                            },
                            ip_address=request.META.get("REMOTE_ADDR"),
                            user_agent=request.META.get("HTTP_USER_AGENT", ""),
                            request_method=request.method,
                            request_path=request.path,
                        )

                        messages.success(
                            request,
                            f"Bill {bill.bill_number} created successfully with journal entry.",
                        )
                        return redirect("accounting:bill_detail", pk=bill.id)
                    else:
                        # Formset validation failed
                        messages.error(request, "Please correct the errors in the bill lines.")
                        # Delete the bill since formset failed
                        bill.delete()
            else:
                # Form validation failed
                from .bill_models import Bill as BillModel

                temp_bill = BillModel()
                formset = BillLineInlineFormSet(
                    request.POST, instance=temp_bill, tenant=request.user.tenant, coa=coa
                )
        else:
            form = BillForm(tenant=request.user.tenant, user=request.user)
            # Create a temporary unsaved Bill instance for the formset
            from .bill_models import Bill as BillModel

            temp_bill = BillModel()
            formset = BillLineInlineFormSet(instance=temp_bill, tenant=request.user.tenant, coa=coa)

        context = {
            "form": form,
            "formset": formset,
            "page_title": "Create Bill",
        }

        return render(request, "accounting/bills/form.html", context)

    except JewelryEntity.DoesNotExist:
        messages.error(request, "Accounting not set up for this tenant.")
        return redirect("accounting:dashboard")
    except Exception as e:
        logger.error(f"Error in bill_create: {str(e)}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect("accounting:bill_list")


@login_required
@tenant_access_required
def bill_detail(request, pk):
    """
    Display bill details with payment history.

    Shows all line items, payments, and current balance.

    Requirements: 2.1, 2.2, 2.4, 2.7, 2.8
    """
    from .bill_models import Bill

    try:
        # Get bill with tenant filtering
        bill = (
            Bill.objects.filter(tenant=request.user.tenant, id=pk)
            .select_related("supplier", "created_by", "approved_by", "journal_entry")
            .prefetch_related("lines", "payments__created_by")
            .first()
        )

        if not bill:
            messages.error(request, "Bill not found.")
            return redirect("accounting:bill_list")

        # Audit logging
        from apps.core.audit_models import AuditLog

        AuditLog.objects.create(
            tenant=request.user.tenant,
            user=request.user,
            category=AuditLog.CATEGORY_DATA,
            action=AuditLog.ACTION_API_GET,
            severity=AuditLog.SEVERITY_INFO,
            description=f"Viewed bill detail: {bill.bill_number}",
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            request_method=request.method,
            request_path=request.path,
        )

        context = {
            "bill": bill,
            "page_title": f"Bill: {bill.bill_number}",
        }

        return render(request, "accounting/bills/detail.html", context)

    except Exception as e:
        logger.error(f"Error in bill_detail: {str(e)}")
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect("accounting:bill_list")


@login_required
@tenant_access_required
def bill_pay(request, pk):
    """
    Record a payment against a bill with automatic journal entry creation.

    Creates journal entry debiting accounts payable and crediting cash/bank.

    Requirements: 2.4, 2.6, 2.7, 2.8
    """
    from .bill_models import Bill

    try:
        jewelry_entity = JewelryEntity.objects.get(tenant=request.user.tenant)
        entity = jewelry_entity.ledger_entity

        # Get chart of accounts
        coa = entity.chartofaccountmodel_set.first()
        if not coa:
            messages.error(request, "Chart of Accounts not found. Please set up accounting first.")
            return redirect("accounting:dashboard")

        # Get bill with tenant filtering
        bill = (
            Bill.objects.filter(tenant=request.user.tenant, id=pk)
            .select_related("supplier")
            .first()
        )

        if not bill:
            messages.error(request, "Bill not found.")
            return redirect("accounting:bill_list")

        # Check if bill is already paid
        if bill.status == "PAID":
            messages.warning(request, "This bill is already fully paid.")
            return redirect("accounting:bill_detail", pk=pk)

        # Check if bill is void
        if bill.status == "VOID":
            messages.error(request, "Cannot pay a void bill.")
            return redirect("accounting:bill_detail", pk=pk)

        from .forms import BillPaymentForm

        if request.method == "POST":
            form = BillPaymentForm(
                request.POST, tenant=request.user.tenant, user=request.user, bill=bill
            )

            if form.is_valid():
                with transaction.atomic():
                    # Create payment
                    payment = form.save(commit=False)
                    payment.tenant = request.user.tenant
                    payment.bill = bill
                    payment.created_by = request.user

                    # Create journal entry (debit AP, credit cash)
                    journal_entry = _create_payment_journal_entry(
                        payment, bill, request.user.tenant, entity, coa
                    )
                    payment.journal_entry = journal_entry
                    payment.save()

                    # Update bill's amount_paid and status
                    # This is handled automatically by BillPayment.save() which calls bill.add_payment()

                    # Audit logging
                    from apps.core.audit_models import AuditLog

                    AuditLog.objects.create(
                        tenant=request.user.tenant,
                        user=request.user,
                        category=AuditLog.CATEGORY_DATA,
                        action=AuditLog.ACTION_CREATE,
                        severity=AuditLog.SEVERITY_INFO,
                        description=f"Recorded payment of ${payment.amount:,.2f} for bill {bill.bill_number}",
                        metadata={
                            "payment_id": str(payment.id),
                            "bill_id": str(bill.id),
                            "bill_number": bill.bill_number,
                            "amount": str(payment.amount),
                            "payment_method": payment.payment_method,
                        },
                        ip_address=request.META.get("REMOTE_ADDR"),
                        user_agent=request.META.get("HTTP_USER_AGENT", ""),
                        request_method=request.method,
                        request_path=request.path,
                    )

                    messages.success(
                        request,
                        f"Payment of ${payment.amount:,.2f} recorded successfully with journal entry.",
                    )
                    return redirect("accounting:bill_detail", pk=pk)
        else:
            form = BillPaymentForm(tenant=request.user.tenant, user=request.user, bill=bill)

        context = {
            "form": form,
            "bill": bill,
            "page_title": f"Record Payment: {bill.bill_number}",
        }

        return render(request, "accounting/bills/payment_form.html", context)

    except JewelryEntity.DoesNotExist:
        messages.error(request, "Accounting not set up for this tenant.")
        return redirect("accounting:dashboard")
    except Exception as e:
        logger.error(f"Error in bill_pay: {str(e)}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect("accounting:bill_detail", pk=pk)


# ============================================================================
# Helper Functions for Journal Entry Creation
# ============================================================================


def _create_bill_journal_entry(bill, tenant, entity, coa):
    """
    Create journal entry for a bill.

    Debits: Expense/Asset accounts (from line items)
    Credits: Accounts Payable

    Requirements: 2.2, 2.7
    """
    from django_ledger.models import JournalEntryModel, TransactionModel

    # Get the ledger
    ledger = entity.ledgermodel_set.first()

    # Get accounts payable account
    ap_account = AccountModel.objects.filter(
        coa_model=coa, role__in=["LIABILITY_CL_ACC_PAYABLE", "LIABILITY_CL"], active=True
    ).first()

    if not ap_account:
        raise ValueError("Accounts Payable account not found in chart of accounts")

    # Create journal entry
    journal_entry = JournalEntryModel.objects.create(
        ledger=ledger,
        description=f"Bill {bill.bill_number} from {bill.supplier.name}",
        posted=True,  # Auto-post bill entries
    )

    # Create debit transactions for each line item (expense/asset)
    for line in bill.lines.all():
        # Get the account from the line's account code
        account = AccountModel.objects.filter(coa_model=coa, code=line.account, active=True).first()

        if not account:
            raise ValueError(f"Account {line.account} not found in chart of accounts")

        TransactionModel.objects.create(
            journal_entry=journal_entry,
            account=account,
            amount=line.amount,
            tx_type="debit",
            description=line.description,
        )

    # Create credit transaction for accounts payable
    TransactionModel.objects.create(
        journal_entry=journal_entry,
        account=ap_account,
        amount=bill.total,
        tx_type="credit",
        description=f"Bill {bill.bill_number} - {bill.supplier.name}",
    )

    return journal_entry


def _create_payment_journal_entry(payment, bill, tenant, entity, coa):
    """
    Create journal entry for a bill payment.

    Debits: Accounts Payable
    Credits: Cash/Bank account

    Requirements: 2.4, 2.6, 2.7
    """
    from django_ledger.models import JournalEntryModel, TransactionModel

    # Get the ledger
    ledger = entity.ledgermodel_set.first()

    # Get accounts payable account
    ap_account = AccountModel.objects.filter(
        coa_model=coa, role__in=["LIABILITY_CL_ACC_PAYABLE", "LIABILITY_CL"], active=True
    ).first()

    if not ap_account:
        raise ValueError("Accounts Payable account not found in chart of accounts")

    # Get cash/bank account based on payment method
    if payment.payment_method in ["CASH"]:
        cash_account = AccountModel.objects.filter(
            coa_model=coa, role="ASSET_CA_CASH", active=True
        ).first()
    else:
        # For checks, cards, transfers, use checking account
        cash_account = AccountModel.objects.filter(
            coa_model=coa, role__in=["ASSET_CA_CHECKING", "ASSET_CA"], active=True
        ).first()

    if not cash_account:
        raise ValueError("Cash/Bank account not found in chart of accounts")

    # Create journal entry
    journal_entry = JournalEntryModel.objects.create(
        ledger=ledger,
        description=f"Payment for Bill {bill.bill_number} - {bill.supplier.name}",
        posted=True,  # Auto-post payment entries
    )

    # Create debit transaction for accounts payable
    TransactionModel.objects.create(
        journal_entry=journal_entry,
        account=ap_account,
        amount=payment.amount,
        tx_type="debit",
        description=f"Payment for Bill {bill.bill_number}",
    )

    # Create credit transaction for cash/bank
    TransactionModel.objects.create(
        journal_entry=journal_entry,
        account=cash_account,
        amount=payment.amount,
        tx_type="credit",
        description=f"Payment to {bill.supplier.name} - {payment.payment_method}",
    )

    return journal_entry


@login_required
@tenant_access_required
def aged_payables_report(request):
    """
    Display aged payables report with 30/60/90/90+ day buckets.

    Shows amounts owed to suppliers grouped by aging buckets.
    Supports PDF and Excel export.

    Requirements: 2.5
    """
    from collections import defaultdict
    from datetime import date

    from .bill_models import Bill

    # Get as_of_date from request or default to today
    as_of_date_str = request.GET.get("as_of_date")
    if as_of_date_str:
        try:
            as_of_date = datetime.strptime(as_of_date_str, "%Y-%m-%d").date()
        except ValueError:
            as_of_date = date.today()
    else:
        as_of_date = date.today()

    # Get all unpaid bills for the tenant
    bills = (
        Bill.objects.filter(
            tenant=request.user.tenant,
            status__in=["APPROVED", "PARTIALLY_PAID"],
        )
        .select_related("supplier")
        .order_by("supplier__name", "due_date")
    )

    # Group bills by supplier and calculate aging buckets
    supplier_data = defaultdict(
        lambda: {
            "supplier": None,
            "current": 0,
            "days_1_30": 0,
            "days_31_60": 0,
            "days_61_90": 0,
            "days_90_plus": 0,
            "total": 0,
            "bills": [],
        }
    )

    for bill in bills:
        supplier_id = bill.supplier.id
        amount_due = bill.amount_due

        # Store supplier reference
        if supplier_data[supplier_id]["supplier"] is None:
            supplier_data[supplier_id]["supplier"] = bill.supplier

        # Calculate days overdue based on as_of_date
        days_overdue = (as_of_date - bill.due_date).days if as_of_date > bill.due_date else 0

        # Categorize into aging buckets
        if days_overdue <= 0:
            supplier_data[supplier_id]["current"] += amount_due
        elif days_overdue <= 30:
            supplier_data[supplier_id]["days_1_30"] += amount_due
        elif days_overdue <= 60:
            supplier_data[supplier_id]["days_31_60"] += amount_due
        elif days_overdue <= 90:
            supplier_data[supplier_id]["days_61_90"] += amount_due
        else:
            supplier_data[supplier_id]["days_90_plus"] += amount_due

        supplier_data[supplier_id]["total"] += amount_due
        supplier_data[supplier_id]["bills"].append(
            {
                "bill_number": bill.bill_number,
                "bill_date": bill.bill_date,
                "due_date": bill.due_date,
                "amount_due": amount_due,
                "days_overdue": days_overdue,
            }
        )

    # Convert to list and sort by supplier name
    supplier_list = sorted(
        supplier_data.values(), key=lambda x: x["supplier"].name if x["supplier"] else ""
    )

    # Calculate grand totals
    grand_totals = {
        "current": sum(s["current"] for s in supplier_list),
        "days_1_30": sum(s["days_1_30"] for s in supplier_list),
        "days_31_60": sum(s["days_31_60"] for s in supplier_list),
        "days_61_90": sum(s["days_61_90"] for s in supplier_list),
        "days_90_plus": sum(s["days_90_plus"] for s in supplier_list),
        "total": sum(s["total"] for s in supplier_list),
    }

    # Check for export format
    export_format = request.GET.get("export")

    if export_format == "pdf":
        return _export_aged_payables_pdf(
            request.user.tenant, supplier_list, grand_totals, as_of_date
        )
    elif export_format == "excel":
        return _export_aged_payables_excel(
            request.user.tenant, supplier_list, grand_totals, as_of_date
        )

    context = {
        "supplier_list": supplier_list,
        "grand_totals": grand_totals,
        "as_of_date": as_of_date,
        "page_title": "Aged Payables Report",
    }

    return render(request, "accounting/reports/aged_payables.html", context)


def _export_aged_payables_pdf(tenant, supplier_list, grand_totals, as_of_date):
    """
    Export aged payables report as PDF.
    """
    from io import BytesIO

    from django.http import HttpResponse

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    # Create response
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="aged_payables_{as_of_date.strftime("%Y%m%d")}.pdf"'
    )

    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), topMargin=0.5 * inch)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    title = Paragraph(
        f"<b>{tenant.name}</b><br/>Aged Payables Report<br/>As of {as_of_date.strftime('%B %d, %Y')}",
        styles["Title"],
    )
    elements.append(title)
    elements.append(Spacer(1, 0.3 * inch))

    # Table data
    table_data = [
        ["Supplier", "Current", "1-30 Days", "31-60 Days", "61-90 Days", "90+ Days", "Total"]
    ]

    for supplier_data in supplier_list:
        table_data.append(
            [
                supplier_data["supplier"].name,
                f"${supplier_data['current']:,.2f}",
                f"${supplier_data['days_1_30']:,.2f}",
                f"${supplier_data['days_31_60']:,.2f}",
                f"${supplier_data['days_61_90']:,.2f}",
                f"${supplier_data['days_90_plus']:,.2f}",
                f"${supplier_data['total']:,.2f}",
            ]
        )

    # Add grand totals row
    table_data.append(
        [
            "TOTAL",
            f"${grand_totals['current']:,.2f}",
            f"${grand_totals['days_1_30']:,.2f}",
            f"${grand_totals['days_31_60']:,.2f}",
            f"${grand_totals['days_61_90']:,.2f}",
            f"${grand_totals['days_90_plus']:,.2f}",
            f"${grand_totals['total']:,.2f}",
        ]
    )

    # Create table
    table = Table(
        table_data,
        colWidths=[
            2.5 * inch,
            1.2 * inch,
            1.2 * inch,
            1.2 * inch,
            1.2 * inch,
            1.2 * inch,
            1.2 * inch,
        ],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, -1), (-1, -1), colors.lightgrey),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]
        )
    )

    elements.append(table)

    # Build PDF
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)

    return response


def _export_aged_payables_excel(tenant, supplier_list, grand_totals, as_of_date):
    """
    Export aged payables report as Excel.
    """
    from django.http import HttpResponse

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    # Create workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Aged Payables"

    # Title
    ws.merge_cells("A1:G1")
    ws["A1"] = f"{tenant.name} - Aged Payables Report"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A1"].alignment = Alignment(horizontal="center")

    ws.merge_cells("A2:G2")
    ws["A2"] = f"As of {as_of_date.strftime('%B %d, %Y')}"
    ws["A2"].alignment = Alignment(horizontal="center")

    # Headers
    headers = ["Supplier", "Current", "1-30 Days", "31-60 Days", "61-90 Days", "90+ Days", "Total"]
    ws.append([])  # Empty row
    ws.append(headers)

    # Style headers
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    # Data rows
    for supplier_data in supplier_list:
        ws.append(
            [
                supplier_data["supplier"].name,
                supplier_data["current"],
                supplier_data["days_1_30"],
                supplier_data["days_31_60"],
                supplier_data["days_61_90"],
                supplier_data["days_90_plus"],
                supplier_data["total"],
            ]
        )

    # Grand totals row
    total_row = ws.max_row + 1
    ws.append(
        [
            "TOTAL",
            grand_totals["current"],
            grand_totals["days_1_30"],
            grand_totals["days_31_60"],
            grand_totals["days_61_90"],
            grand_totals["days_90_plus"],
            grand_totals["total"],
        ]
    )

    # Style totals row
    total_fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")
    total_font = Font(bold=True)
    for col_num in range(1, 8):
        cell = ws.cell(row=total_row, column=col_num)
        cell.fill = total_fill
        cell.font = total_font

    # Format currency columns
    for row in ws.iter_rows(min_row=5, max_row=ws.max_row, min_col=2, max_col=7):
        for cell in row:
            cell.number_format = "$#,##0.00"
            cell.alignment = Alignment(horizontal="right")

    # Adjust column widths
    ws.column_dimensions["A"].width = 30
    for col in ["B", "C", "D", "E", "F", "G"]:
        ws.column_dimensions[col].width = 15

    # Create response
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = (
        f'attachment; filename="aged_payables_{as_of_date.strftime("%Y%m%d")}.xlsx"'
    )

    wb.save(response)
    return response
