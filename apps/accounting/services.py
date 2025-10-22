"""
Accounting services for jewelry shop management.

This module provides services for integrating with django-ledger and
automating accounting operations for jewelry businesses.
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Dict, Optional

from django.contrib.auth import get_user_model
from django.db import transaction

from django_ledger.models import (
    AccountModel,
    ChartOfAccountModel,
    EntityModel,
    JournalEntryModel,
    TransactionModel,
)

from apps.core.models import Tenant

from .models import (
    AccountingConfiguration,
    JewelryChartOfAccounts,
    JewelryEntity,
    JournalEntryTemplate,
    JournalEntryTemplateLine,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class AccountingService:
    """
    Service class for handling accounting operations.
    """

    @staticmethod
    def setup_tenant_accounting(tenant: Tenant, user: User) -> JewelryEntity:
        """
        Set up accounting for a new tenant.
        Creates EntityModel, chart of accounts, and configuration.
        """
        # Check if accounting already exists
        try:
            existing_entity = JewelryEntity.objects.get(tenant=tenant)
            logger.info(f"Accounting already exists for tenant: {tenant.company_name}")
            return existing_entity
        except JewelryEntity.DoesNotExist:
            pass

        with transaction.atomic():
            # Create django-ledger entity
            entity = EntityModel.add_root(
                name=tenant.company_name,
                slug=tenant.slug,
                admin=user,
                hidden=False,
                address_1="",  # Required field
                accrual_method=True,
                fy_start_month=1,
            )

            # Create jewelry entity wrapper
            jewelry_entity = JewelryEntity.objects.create(
                tenant=tenant,
                ledger_entity=entity,
                fiscal_year_start_month=1,  # January
                default_currency="USD",
            )

            # Create chart of accounts
            AccountingService._create_chart_of_accounts(entity)

            # Create accounting configuration
            AccountingConfiguration.objects.create(
                tenant=tenant, use_automatic_journal_entries=True, inventory_valuation_method="FIFO"
            )

            # Create journal entry templates
            AccountingService._create_journal_templates()

            logger.info(f"Accounting setup completed for tenant: {tenant.company_name}")
            return jewelry_entity

    @staticmethod
    def _create_chart_of_accounts(entity: EntityModel) -> None:
        """
        Create standard chart of accounts for jewelry business.
        """
        # Get predefined chart of accounts
        chart_templates = JewelryChartOfAccounts.objects.filter(is_active=True)

        if not chart_templates.exists():
            # Create default chart of accounts if not exists
            AccountingService._create_default_chart_templates()
            chart_templates = JewelryChartOfAccounts.objects.filter(is_active=True)

        # Create chart of accounts for the entity
        coa = ChartOfAccountModel.objects.create(entity=entity, slug=f"{entity.slug}-coa")

        # Create accounts based on templates
        for template in chart_templates:
            account_role = AccountingService._get_account_role(template.account_type)

            # Use add_root for tree structure
            AccountModel.add_root(
                coa_model=coa,
                code=template.account_code,
                name=template.name,
                role=account_role,
                balance_type=AccountingService._get_balance_type(template.account_type),
                active=template.is_active,
            )

    @staticmethod
    def _create_default_chart_templates() -> None:
        """
        Create default chart of accounts templates for jewelry business.
        """
        default_accounts = [
            # Assets (1000-1999)
            ("1001", "Cash - Checking Account", "CASH", "Primary checking account"),
            ("1002", "Cash - Credit Card Processing", "CASH", "Credit card merchant account"),
            ("1003", "Cash - Petty Cash", "CASH", "Petty cash fund"),
            ("1100", "Accounts Receivable", "ACCOUNTS_RECEIVABLE", "Customer receivables"),
            ("1200", "Inventory - Finished Goods", "INVENTORY", "Finished jewelry inventory"),
            ("1201", "Inventory - Raw Materials", "INVENTORY", "Gold, silver, gems inventory"),
            ("1202", "Inventory - Work in Process", "INVENTORY", "Custom orders in progress"),
            ("1300", "Equipment - Store Fixtures", "EQUIPMENT", "Display cases, lighting"),
            ("1301", "Equipment - Tools", "EQUIPMENT", "Jewelry making tools"),
            ("1302", "Equipment - Security System", "EQUIPMENT", "Security cameras, safes"),
            ("1400", "Prepaid Insurance", "PREPAID_EXPENSES", "Prepaid insurance premiums"),
            ("1401", "Prepaid Rent", "PREPAID_EXPENSES", "Prepaid rent expenses"),
            # Liabilities (2000-2999)
            ("2001", "Accounts Payable", "ACCOUNTS_PAYABLE", "Supplier payables"),
            ("2002", "Accrued Wages", "ACCRUED_EXPENSES", "Unpaid employee wages"),
            ("2003", "Sales Tax Payable", "SALES_TAX_PAYABLE", "Collected sales tax"),
            ("2100", "Business Loan", "LOANS_PAYABLE", "Bank loans"),
            ("2101", "Equipment Financing", "LOANS_PAYABLE", "Equipment loans"),
            # Equity (3000-3999)
            ("3001", "Owner's Equity", "OWNERS_EQUITY", "Owner's capital investment"),
            ("3002", "Retained Earnings", "RETAINED_EARNINGS", "Accumulated profits"),
            # Revenue (4000-4999)
            ("4001", "Jewelry Sales", "JEWELRY_SALES", "Sales of finished jewelry"),
            ("4002", "Repair Services", "REPAIR_REVENUE", "Jewelry repair revenue"),
            ("4003", "Custom Orders", "CUSTOM_ORDER_REVENUE", "Custom jewelry revenue"),
            ("4004", "Gift Card Sales", "GIFT_CARD_REVENUE", "Gift card sales"),
            # Expenses (5000-5999)
            ("5001", "Cost of Goods Sold", "COST_OF_GOODS_SOLD", "Direct cost of inventory sold"),
            ("5100", "Rent Expense", "RENT_EXPENSE", "Store rent"),
            ("5101", "Utilities", "UTILITIES_EXPENSE", "Electricity, water, gas"),
            ("5102", "Insurance", "INSURANCE_EXPENSE", "Business insurance"),
            ("5103", "Marketing & Advertising", "MARKETING_EXPENSE", "Promotional expenses"),
            ("5200", "Wages & Salaries", "EMPLOYEE_WAGES", "Employee compensation"),
            ("5201", "Professional Fees", "PROFESSIONAL_FEES", "Legal, accounting fees"),
            ("5202", "Bank Fees", "BANK_FEES", "Banking and credit card fees"),
            ("5300", "Depreciation Expense", "DEPRECIATION_EXPENSE", "Equipment depreciation"),
        ]

        for code, name, account_type, description in default_accounts:
            JewelryChartOfAccounts.objects.get_or_create(
                account_code=code,
                defaults={
                    "name": name,
                    "account_type": account_type,
                    "description": description,
                    "is_active": True,
                },
            )

    @staticmethod
    def _create_journal_templates() -> None:
        """
        Create journal entry templates for common transactions.
        """
        # Cash Sale Template
        cash_sale_template, created = JournalEntryTemplate.objects.get_or_create(
            template_type="CASH_SALE",
            defaults={
                "name": "Cash Sale",
                "description": "Journal entry for cash sales",
                "is_active": True,
            },
        )

        if created:
            # Debit Cash, Credit Sales Revenue
            JournalEntryTemplateLine.objects.create(
                template=cash_sale_template,
                account_code="1001",  # Cash - Checking
                debit_credit="DEBIT",
                amount_field="total",
                description_template="Cash sale #{sale_number}",
                order=1,
            )
            JournalEntryTemplateLine.objects.create(
                template=cash_sale_template,
                account_code="4001",  # Jewelry Sales
                debit_credit="CREDIT",
                amount_field="subtotal",
                description_template="Cash sale #{sale_number}",
                order=2,
            )
            # Sales tax if applicable
            JournalEntryTemplateLine.objects.create(
                template=cash_sale_template,
                account_code="2003",  # Sales Tax Payable
                debit_credit="CREDIT",
                amount_field="tax",
                description_template="Sales tax on sale #{sale_number}",
                order=3,
            )

        # Card Sale Template
        card_sale_template, created = JournalEntryTemplate.objects.get_or_create(
            template_type="CARD_SALE",
            defaults={
                "name": "Credit Card Sale",
                "description": "Journal entry for credit card sales",
                "is_active": True,
            },
        )

        if created:
            # Debit Credit Card Processing, Credit Sales Revenue
            JournalEntryTemplateLine.objects.create(
                template=card_sale_template,
                account_code="1002",  # Credit Card Processing
                debit_credit="DEBIT",
                amount_field="total",
                description_template="Card sale #{sale_number}",
                order=1,
            )
            JournalEntryTemplateLine.objects.create(
                template=card_sale_template,
                account_code="4001",  # Jewelry Sales
                debit_credit="CREDIT",
                amount_field="subtotal",
                description_template="Card sale #{sale_number}",
                order=2,
            )
            JournalEntryTemplateLine.objects.create(
                template=card_sale_template,
                account_code="2003",  # Sales Tax Payable
                debit_credit="CREDIT",
                amount_field="tax",
                description_template="Sales tax on sale #{sale_number}",
                order=3,
            )

    @staticmethod
    def _get_account_role(account_type: str) -> str:
        """
        Map account type to django-ledger account role.
        """
        role_mapping = {
            "CASH": "asset_ca_cash",
            "INVENTORY": "asset_ca_inv",
            "ACCOUNTS_RECEIVABLE": "asset_ca_recv",
            "EQUIPMENT": "asset_ppe_equip",
            "PREPAID_EXPENSES": "asset_ca_prepaid",
            "ACCOUNTS_PAYABLE": "lia_cl_acc_payable",
            "ACCRUED_EXPENSES": "lia_cl_other",
            "LOANS_PAYABLE": "lia_ltl_notes",
            "SALES_TAX_PAYABLE": "lia_cl_taxes_payable",
            "OWNERS_EQUITY": "eq_capital",
            "RETAINED_EARNINGS": "eq_adjustment",
            "JEWELRY_SALES": "in_operational",
            "REPAIR_REVENUE": "in_operational",
            "CUSTOM_ORDER_REVENUE": "in_operational",
            "GIFT_CARD_REVENUE": "in_operational",
            "COST_OF_GOODS_SOLD": "cogs_regular",
            "RENT_EXPENSE": "ex_regular",
            "UTILITIES_EXPENSE": "ex_regular",
            "INSURANCE_EXPENSE": "ex_regular",
            "MARKETING_EXPENSE": "ex_regular",
            "EMPLOYEE_WAGES": "ex_regular",
            "PROFESSIONAL_FEES": "ex_regular",
            "BANK_FEES": "ex_regular",
            "DEPRECIATION_EXPENSE": "ex_depreciation",
        }
        return role_mapping.get(account_type, "asset_ca_cash")

    @staticmethod
    def _get_balance_type(account_type: str) -> str:
        """
        Get balance type (debit/credit) for account type.
        """
        debit_accounts = [
            "CASH",
            "INVENTORY",
            "ACCOUNTS_RECEIVABLE",
            "EQUIPMENT",
            "PREPAID_EXPENSES",
            "COST_OF_GOODS_SOLD",
            "RENT_EXPENSE",
            "UTILITIES_EXPENSE",
            "INSURANCE_EXPENSE",
            "MARKETING_EXPENSE",
            "EMPLOYEE_WAGES",
            "PROFESSIONAL_FEES",
            "BANK_FEES",
            "DEPRECIATION_EXPENSE",
        ]

        return "debit" if account_type in debit_accounts else "credit"

    @staticmethod
    def create_sale_journal_entry(sale, user: User) -> Optional[JournalEntryModel]:
        """
        Create journal entry for a sale transaction.
        """
        try:
            # Get tenant's accounting entity
            jewelry_entity = JewelryEntity.objects.get(tenant=sale.tenant)
            entity = jewelry_entity.ledger_entity

            # Get accounting configuration
            config = AccountingConfiguration.objects.get(tenant=sale.tenant)

            if not config.use_automatic_journal_entries:
                return None

            # Determine template based on payment method
            template_type = "CASH_SALE" if sale.payment_method == "cash" else "CARD_SALE"
            template = JournalEntryTemplate.objects.get(template_type=template_type)

            # Create journal entry
            journal_entry = JournalEntryModel.objects.create(
                entity=entity,
                description=f"Sale #{sale.sale_number}",
                date=sale.created_at.date(),
                posted=True,
            )

            # Create transaction lines based on template
            for line_template in template.lines.all():
                amount = getattr(sale, line_template.amount_field, Decimal("0"))

                if amount > 0:  # Only create lines with positive amounts
                    account = AccountModel.objects.get(
                        coa_model__entity=entity, code=line_template.account_code
                    )

                    # Use correct transaction type constants
                    tx_type = "debit" if line_template.debit_credit == "DEBIT" else "credit"

                    TransactionModel.objects.create(
                        journal_entry=journal_entry,
                        account=account,
                        amount=amount,
                        tx_type=tx_type,
                        description=line_template.description_template.format(
                            sale_number=sale.sale_number
                        ),
                    )

            logger.info(f"Journal entry created for sale {sale.sale_number}")
            return journal_entry

        except Exception as e:
            logger.error(f"Failed to create journal entry for sale {sale.sale_number}: {str(e)}")
            return None

    @staticmethod
    def get_financial_reports(tenant: Tenant, start_date: date, end_date: date) -> Dict:
        """
        Generate financial reports for a tenant.
        """
        try:
            jewelry_entity = JewelryEntity.objects.get(tenant=tenant)
            entity = jewelry_entity.ledger_entity

            # Get balance sheet statement
            balance_sheet = entity.get_balance_sheet_statement(to_date=end_date)

            # Get income statement
            income_statement = entity.get_income_statement(to_date=end_date, from_date=start_date)

            # Get cash flow statement
            cash_flow = entity.get_cash_flow_statement(to_date=end_date, from_date=start_date)

            return {
                "balance_sheet": balance_sheet,
                "income_statement": income_statement,
                "cash_flow": cash_flow,
                "period": {"start_date": start_date, "end_date": end_date},
            }

        except Exception as e:
            logger.error(
                f"Failed to generate financial reports for tenant {tenant.company_name}: {str(e)}"
            )
            return {}

    @staticmethod
    def get_account_balance(tenant: Tenant, account_code: str, as_of_date: date = None) -> Decimal:
        """
        Get account balance for a specific account.
        """
        try:
            jewelry_entity = JewelryEntity.objects.get(tenant=tenant)
            entity = jewelry_entity.ledger_entity

            AccountModel.objects.get(coa_model__entity=entity, code=account_code)

            if as_of_date is None:
                as_of_date = date.today()

            # For now, return 0 as balance calculation requires transactions
            # This will be implemented in task 7.2 when we add journal entries
            return Decimal("0.00")

        except Exception as e:
            logger.error(f"Failed to get account balance for {account_code}: {str(e)}")
            return Decimal("0")
