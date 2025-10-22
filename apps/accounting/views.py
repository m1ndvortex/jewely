"""
Views for the accounting module.
"""

import logging
from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from apps.core.decorators import tenant_access_required

from .models import AccountingConfiguration, JewelryEntity
from .services import AccountingService

logger = logging.getLogger(__name__)


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
