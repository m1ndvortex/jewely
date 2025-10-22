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

            # Create default entity unit using django-ledger's API
            from django_ledger.models import EntityUnitModel, LedgerModel

            EntityUnitModel.add_root(
                entity=entity, name=f"{tenant.company_name} - Main Unit", slug=f"{tenant.slug}-main"
            )

            # Create a ledger for the entity unit
            LedgerModel.objects.create(
                entity=entity, name=f"{tenant.company_name} - General Ledger"
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

        # Inventory Purchase Template
        purchase_template, created = JournalEntryTemplate.objects.get_or_create(
            template_type="INVENTORY_PURCHASE",
            defaults={
                "name": "Inventory Purchase",
                "description": "Journal entry for inventory purchases",
                "is_active": True,
            },
        )

        if created:
            # Debit Inventory, Credit Accounts Payable
            JournalEntryTemplateLine.objects.create(
                template=purchase_template,
                account_code="1200",  # Inventory
                debit_credit="DEBIT",
                amount_field="total_amount",
                description_template="Inventory purchase - PO #{po_number}",
                order=1,
            )
            JournalEntryTemplateLine.objects.create(
                template=purchase_template,
                account_code="2001",  # Accounts Payable
                debit_credit="CREDIT",
                amount_field="total_amount",
                description_template="Amount owed to supplier - PO #{po_number}",
                order=2,
            )

        # Expense Payment Template
        expense_template, created = JournalEntryTemplate.objects.get_or_create(
            template_type="EXPENSE_PAYMENT",
            defaults={
                "name": "Expense Payment",
                "description": "Journal entry for expense payments",
                "is_active": True,
            },
        )

        if created:
            # Debit Expense Account, Credit Cash
            JournalEntryTemplateLine.objects.create(
                template=expense_template,
                account_code="5400",  # Other Expenses (default)
                debit_credit="DEBIT",
                amount_field="amount",
                description_template="Expense: {description}",
                order=1,
            )
            JournalEntryTemplateLine.objects.create(
                template=expense_template,
                account_code="1001",  # Cash
                debit_credit="CREDIT",
                amount_field="amount",
                description_template="Cash payment for: {description}",
                order=2,
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

        Creates double-entry bookkeeping entries for sales:
        - Debit: Cash/Card account (total amount)
        - Credit: Sales Revenue account (subtotal)
        - Credit: Sales Tax Payable account (tax amount)
        - Debit: Cost of Goods Sold (COGS)
        - Credit: Inventory (COGS)
        """
        try:
            # Get tenant's accounting entity
            jewelry_entity = JewelryEntity.objects.get(tenant=sale.tenant)
            entity = jewelry_entity.ledger_entity
            entity_unit = entity.entityunitmodel_set.first()

            if not entity_unit:
                logger.error(f"No entity unit found for tenant {sale.tenant.company_name}")
                return None

            # Get accounting configuration
            config = AccountingConfiguration.objects.get(tenant=sale.tenant)

            if not config.use_automatic_journal_entries:
                logger.info(
                    f"Automatic journal entries disabled for tenant {sale.tenant.company_name}"
                )
                return None

            with transaction.atomic():
                # Get the ledger for this entity
                ledger = entity.ledgermodel_set.first()
                if not ledger:
                    logger.error(f"No ledger found for entity {entity}")
                    return None

                # Create journal entry (unposted initially)
                journal_entry = JournalEntryModel.objects.create(
                    ledger=ledger,
                    description=f"Sale #{sale.sale_number}",
                    posted=False,
                )

                # 1. Record the sale revenue and payment
                AccountingService._create_sale_revenue_entries(journal_entry, sale, config)

                # 2. Record cost of goods sold and inventory reduction
                AccountingService._create_cogs_entries(journal_entry, sale, config)

                # Post the journal entry
                journal_entry.posted = True
                journal_entry.save()

                logger.info(f"Journal entry created for sale {sale.sale_number}")
                return journal_entry

        except Exception as e:
            logger.error(f"Failed to create journal entry for sale {sale.sale_number}: {str(e)}")
            return None

    @staticmethod
    def _create_sale_revenue_entries(
        journal_entry: JournalEntryModel, sale, config: AccountingConfiguration
    ):
        """Create revenue-related journal entries for a sale."""
        entity = journal_entry.ledger.entity

        # Debit: Cash or Card account (total amount received)
        if sale.payment_method.upper() == "CASH":
            cash_account = AccountModel.objects.get(
                coa_model__entity=entity, code=config.default_cash_account
            )
            TransactionModel.objects.create(
                journal_entry=journal_entry,
                account=cash_account,
                amount=sale.total,
                tx_type="debit",
                description=f"Cash received for sale #{sale.sale_number}",
            )
        elif sale.payment_method.upper() == "CARD":
            card_account = AccountModel.objects.get(
                coa_model__entity=entity, code=config.default_card_account
            )
            TransactionModel.objects.create(
                journal_entry=journal_entry,
                account=card_account,
                amount=sale.total,
                tx_type="debit",
                description=f"Card payment for sale #{sale.sale_number}",
            )
        elif sale.payment_method.upper() == "STORE_CREDIT":
            # For store credit, we debit accounts receivable or a store credit liability account
            # For now, use cash account as placeholder
            cash_account = AccountModel.objects.get(
                coa_model__entity=entity, code=config.default_cash_account
            )
            TransactionModel.objects.create(
                journal_entry=journal_entry,
                account=cash_account,
                amount=sale.total,
                tx_type="debit",
                description=f"Store credit used for sale #{sale.sale_number}",
            )

        # Credit: Sales Revenue (subtotal amount)
        if sale.subtotal > 0:
            sales_account = AccountModel.objects.get(
                coa_model__entity=entity, code=config.default_sales_account
            )
            TransactionModel.objects.create(
                journal_entry=journal_entry,
                account=sales_account,
                amount=sale.subtotal,
                tx_type="credit",
                description=f"Sales revenue for sale #{sale.sale_number}",
            )

        # Credit: Sales Tax Payable (tax amount)
        if sale.tax > 0:
            tax_account = AccountModel.objects.get(
                coa_model__entity=entity, code=config.default_tax_account
            )
            TransactionModel.objects.create(
                journal_entry=journal_entry,
                account=tax_account,
                amount=sale.tax,
                tx_type="credit",
                description=f"Sales tax collected for sale #{sale.sale_number}",
            )

    @staticmethod
    def _create_cogs_entries(
        journal_entry: JournalEntryModel, sale, config: AccountingConfiguration
    ):
        """Create cost of goods sold entries for a sale."""
        entity = journal_entry.ledger.entity

        # Calculate total COGS for all items in the sale
        total_cogs = Decimal("0.00")

        for sale_item in sale.items.all():
            item_cogs = sale_item.inventory_item.cost_price * sale_item.quantity
            total_cogs += item_cogs

        if total_cogs > 0:
            # Debit: Cost of Goods Sold
            cogs_account = AccountModel.objects.get(
                coa_model__entity=entity, code=config.default_cogs_account
            )
            TransactionModel.objects.create(
                journal_entry=journal_entry,
                account=cogs_account,
                amount=total_cogs,
                tx_type="debit",
                description=f"Cost of goods sold for sale #{sale.sale_number}",
            )

            # Credit: Inventory
            inventory_account = AccountModel.objects.get(
                coa_model__entity=entity, code=config.default_inventory_account
            )
            TransactionModel.objects.create(
                journal_entry=journal_entry,
                account=inventory_account,
                amount=total_cogs,
                tx_type="credit",
                description=f"Inventory reduction for sale #{sale.sale_number}",
            )

    @staticmethod
    def create_purchase_journal_entry(purchase_order, user: User) -> Optional[JournalEntryModel]:
        """
        Create journal entry for inventory purchase.

        Creates double-entry bookkeeping entries for purchases:
        - Debit: Inventory (purchase amount)
        - Credit: Accounts Payable (purchase amount)
        """
        try:
            # Get tenant's accounting entity
            jewelry_entity = JewelryEntity.objects.get(tenant=purchase_order.tenant)
            entity = jewelry_entity.ledger_entity

            # Get accounting configuration
            config = AccountingConfiguration.objects.get(tenant=purchase_order.tenant)

            if not config.use_automatic_journal_entries:
                logger.info(
                    f"Automatic journal entries disabled for tenant {purchase_order.tenant.company_name}"
                )
                return None

            with transaction.atomic():
                # Get the ledger for this entity
                ledger = entity.ledgermodel_set.first()
                if not ledger:
                    logger.error(f"No ledger found for entity {entity}")
                    return None

                # Create journal entry
                journal_entry = JournalEntryModel.objects.create(
                    ledger=ledger,
                    description=f"Purchase Order #{purchase_order.po_number}",
                    posted=False,
                )

                # Debit: Inventory
                inventory_account = AccountModel.objects.get(
                    coa_model__entity=entity, code=config.default_inventory_account
                )
                TransactionModel.objects.create(
                    journal_entry=journal_entry,
                    account=inventory_account,
                    amount=purchase_order.total_amount,
                    tx_type="debit",
                    description=f"Inventory purchase - PO #{purchase_order.po_number}",
                )

                # Credit: Accounts Payable
                payable_account = AccountModel.objects.get(
                    coa_model__entity=entity, code="2001"
                )  # Accounts Payable
                TransactionModel.objects.create(
                    journal_entry=journal_entry,
                    account=payable_account,
                    amount=purchase_order.total_amount,
                    tx_type="credit",
                    description=f"Amount owed to supplier - PO #{purchase_order.po_number}",
                )

                # Post the journal entry
                journal_entry.posted = True
                journal_entry.save()

                logger.info(f"Journal entry created for purchase order {purchase_order.po_number}")
                return journal_entry

        except Exception as e:
            logger.error(
                f"Failed to create journal entry for purchase order {purchase_order.po_number}: {str(e)}"
            )
            return None

    @staticmethod
    def create_payment_journal_entry(payment, user: User) -> Optional[JournalEntryModel]:
        """
        Create journal entry for payment to supplier.

        Creates double-entry bookkeeping entries for payments:
        - Debit: Accounts Payable (payment amount)
        - Credit: Cash/Bank (payment amount)
        """
        try:
            # Get tenant's accounting entity
            jewelry_entity = JewelryEntity.objects.get(tenant=payment.tenant)
            entity = jewelry_entity.ledger_entity

            # Get accounting configuration
            config = AccountingConfiguration.objects.get(tenant=payment.tenant)

            if not config.use_automatic_journal_entries:
                logger.info(
                    f"Automatic journal entries disabled for tenant {payment.tenant.company_name}"
                )
                return None

            with transaction.atomic():
                # Get the ledger for this entity
                ledger = entity.ledgermodel_set.first()
                if not ledger:
                    logger.error(f"No ledger found for entity {entity}")
                    return None

                # Create journal entry
                journal_entry = JournalEntryModel.objects.create(
                    ledger=ledger,
                    description=f"Payment #{payment.payment_number}",
                    posted=False,
                )

                # Debit: Accounts Payable (reducing the liability)
                payable_account = AccountModel.objects.get(
                    coa_model__entity=entity, code="2001"
                )  # Accounts Payable
                TransactionModel.objects.create(
                    journal_entry=journal_entry,
                    account=payable_account,
                    amount=payment.amount,
                    tx_type="debit",
                    description=f"Payment to supplier - {payment.supplier.name}",
                )

                # Credit: Cash/Bank (reducing the asset)
                if payment.payment_method.upper() == "CASH":
                    cash_account = AccountModel.objects.get(
                        coa_model__entity=entity, code=config.default_cash_account
                    )
                    account_description = "Cash payment"
                else:
                    # Assume bank/check payment
                    cash_account = AccountModel.objects.get(
                        coa_model__entity=entity, code=config.default_cash_account
                    )
                    account_description = f"{payment.payment_method} payment"

                TransactionModel.objects.create(
                    journal_entry=journal_entry,
                    account=cash_account,
                    amount=payment.amount,
                    tx_type="credit",
                    description=f"{account_description} to {payment.supplier.name}",
                )

                # Post the journal entry
                journal_entry.posted = True
                journal_entry.save()

                logger.info(f"Journal entry created for payment {payment.payment_number}")
                return journal_entry

        except Exception as e:
            logger.error(
                f"Failed to create journal entry for payment {payment.payment_number}: {str(e)}"
            )
            return None

    @staticmethod
    def create_expense_journal_entry(expense, user: User) -> Optional[JournalEntryModel]:
        """
        Create journal entry for business expense.

        Creates double-entry bookkeeping entries for expenses:
        - Debit: Expense Account (expense amount)
        - Credit: Cash/Bank (expense amount)
        """
        try:
            # Get tenant's accounting entity
            jewelry_entity = JewelryEntity.objects.get(tenant=expense.tenant)
            entity = jewelry_entity.ledger_entity

            # Get accounting configuration
            config = AccountingConfiguration.objects.get(tenant=expense.tenant)

            if not config.use_automatic_journal_entries:
                logger.info(
                    f"Automatic journal entries disabled for tenant {expense.tenant.company_name}"
                )
                return None

            with transaction.atomic():
                # Get the ledger for this entity
                ledger = entity.ledgermodel_set.first()
                if not ledger:
                    logger.error(f"No ledger found for entity {entity}")
                    return None

                # Create journal entry
                journal_entry = JournalEntryModel.objects.create(
                    ledger=ledger,
                    description=f"Expense: {expense.description}",
                    posted=False,
                )

                # Debit: Expense Account
                expense_account_code = AccountingService._get_expense_account_code(expense.category)
                expense_account = AccountModel.objects.get(
                    coa_model__entity=entity, code=expense_account_code
                )
                TransactionModel.objects.create(
                    journal_entry=journal_entry,
                    account=expense_account,
                    amount=expense.amount,
                    tx_type="debit",
                    description=f"{expense.category}: {expense.description}",
                )

                # Credit: Cash/Bank
                if expense.payment_method.upper() == "CASH":
                    cash_account = AccountModel.objects.get(
                        coa_model__entity=entity, code=config.default_cash_account
                    )
                    account_description = "Cash expense"
                else:
                    # Assume bank/check payment
                    cash_account = AccountModel.objects.get(
                        coa_model__entity=entity, code=config.default_cash_account
                    )
                    account_description = f"{expense.payment_method} expense"

                TransactionModel.objects.create(
                    journal_entry=journal_entry,
                    account=cash_account,
                    amount=expense.amount,
                    tx_type="credit",
                    description=f"{account_description}: {expense.description}",
                )

                # Post the journal entry
                journal_entry.posted = True
                journal_entry.save()

                logger.info(f"Journal entry created for expense {expense.description}")
                return journal_entry

        except Exception as e:
            logger.error(
                f"Failed to create journal entry for expense {expense.description}: {str(e)}"
            )
            return None

    @staticmethod
    def _get_expense_account_code(expense_category: str) -> str:
        """
        Map expense category to appropriate account code.
        """
        category_mapping = {
            "RENT": "5100",  # Rent Expense
            "UTILITIES": "5101",  # Utilities
            "INSURANCE": "5102",  # Insurance
            "MARKETING": "5103",  # Marketing & Advertising
            "WAGES": "5200",  # Wages & Salaries
            "PROFESSIONAL": "5201",  # Professional Fees
            "BANK_FEES": "5202",  # Bank Fees
            "OFFICE": "5300",  # Office Expenses (general)
            "TRAVEL": "5301",  # Travel Expenses
            "SUPPLIES": "5302",  # Office Supplies
            "EQUIPMENT": "5303",  # Equipment Expenses
            "OTHER": "5400",  # Other Expenses
        }
        return category_mapping.get(expense_category.upper(), "5400")  # Default to Other Expenses

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
