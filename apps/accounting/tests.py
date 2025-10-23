"""
Tests for the accounting module.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

import pytest
from django_ledger.models import EntityModel

from apps.core.models import Tenant
from apps.core.tenant_context import bypass_rls, set_tenant_context

from .models import (
    AccountingConfiguration,
    JewelryChartOfAccounts,
    JewelryEntity,
    JournalEntryTemplate,
    JournalEntryTemplateLine,
)
from .services import AccountingService

User = get_user_model()


class AccountingServiceTest(TestCase):
    """Test cases for AccountingService."""

    def setUp(self):
        """Set up test data."""
        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop", slug="test-shop", status="ACTIVE"
            )

            self.user = User.objects.create_user(
                username="testowner",
                email="owner@test.com",
                password="testpass123",
                tenant=self.tenant,
                role="TENANT_OWNER",
            )

    def test_create_default_chart_templates(self):
        """Test creation of default chart of accounts templates."""
        # Ensure no templates exist initially
        JewelryChartOfAccounts.objects.all().delete()

        AccountingService._create_default_chart_templates()

        # Check that templates were created
        templates = JewelryChartOfAccounts.objects.all()
        self.assertGreater(templates.count(), 0)

        # Check specific accounts
        cash_account = JewelryChartOfAccounts.objects.get(account_code="1001")
        self.assertEqual(cash_account.name, "Cash - Checking Account")
        self.assertEqual(cash_account.account_type, "CASH")

        sales_account = JewelryChartOfAccounts.objects.get(account_code="4001")
        self.assertEqual(sales_account.name, "Jewelry Sales")
        self.assertEqual(sales_account.account_type, "JEWELRY_SALES")

    def test_create_journal_templates(self):
        """Test creation of journal entry templates."""
        # Ensure no templates exist initially
        JournalEntryTemplate.objects.all().delete()

        AccountingService._create_journal_templates()

        # Check that templates were created
        cash_sale_template = JournalEntryTemplate.objects.get(template_type="CASH_SALE")
        self.assertEqual(cash_sale_template.name, "Cash Sale")

        card_sale_template = JournalEntryTemplate.objects.get(template_type="CARD_SALE")
        self.assertEqual(card_sale_template.name, "Credit Card Sale")

        # Check template lines
        cash_lines = cash_sale_template.lines.all()
        self.assertGreater(cash_lines.count(), 0)

    def test_setup_tenant_accounting(self):
        """Test setting up accounting for a tenant."""
        jewelry_entity = AccountingService.setup_tenant_accounting(self.tenant, self.user)

        # Check that JewelryEntity was created
        self.assertIsInstance(jewelry_entity, JewelryEntity)
        self.assertEqual(jewelry_entity.tenant, self.tenant)

        # Check that EntityModel was created
        self.assertIsInstance(jewelry_entity.ledger_entity, EntityModel)
        self.assertEqual(jewelry_entity.ledger_entity.name, self.tenant.company_name)

        # Check that AccountingConfiguration was created
        config = AccountingConfiguration.objects.get(tenant=self.tenant)
        self.assertTrue(config.use_automatic_journal_entries)
        self.assertEqual(config.inventory_valuation_method, "FIFO")

        # Check that chart of accounts was created
        coa = jewelry_entity.ledger_entity.chartofaccountmodel_set.first()
        self.assertIsNotNone(coa)

        accounts = coa.accountmodel_set.all()
        self.assertGreater(accounts.count(), 0)

    def test_get_account_role_mapping(self):
        """Test account role mapping."""
        # Test asset accounts
        self.assertEqual(AccountingService._get_account_role("CASH"), "asset_ca_cash")

        # Test liability accounts
        self.assertEqual(
            AccountingService._get_account_role("ACCOUNTS_PAYABLE"), "lia_cl_acc_payable"
        )

        # Test revenue accounts
        self.assertEqual(AccountingService._get_account_role("JEWELRY_SALES"), "in_operational")

        # Test expense accounts
        self.assertEqual(AccountingService._get_account_role("COST_OF_GOODS_SOLD"), "cogs_regular")

    def test_get_balance_type(self):
        """Test balance type determination."""
        # Test debit accounts
        self.assertEqual(AccountingService._get_balance_type("CASH"), "debit")

        self.assertEqual(AccountingService._get_balance_type("INVENTORY"), "debit")

        # Test credit accounts
        self.assertEqual(AccountingService._get_balance_type("ACCOUNTS_PAYABLE"), "credit")

        self.assertEqual(AccountingService._get_balance_type("JEWELRY_SALES"), "credit")


class AccountingModelsTest(TestCase):
    """Test cases for accounting models."""

    def setUp(self):
        """Set up test data."""
        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop", slug="test-shop", status="ACTIVE"
            )

            self.user = User.objects.create_user(
                username="testowner",
                email="owner@test.com",
                password="testpass123",
                tenant=self.tenant,
                role="TENANT_OWNER",
            )

    def test_jewelry_chart_of_accounts_model(self):
        """Test JewelryChartOfAccounts model."""
        account = JewelryChartOfAccounts.objects.create(
            name="Test Cash Account",
            account_type="CASH",
            account_code="1001",
            description="Test cash account",
            is_active=True,
        )

        self.assertEqual(str(account), "1001 - Test Cash Account")
        self.assertTrue(account.is_active)

    def test_accounting_configuration_model(self):
        """Test AccountingConfiguration model."""
        config = AccountingConfiguration.objects.create(
            tenant=self.tenant,
            use_automatic_journal_entries=True,
            inventory_valuation_method="FIFO",
        )

        self.assertEqual(str(config), f"Accounting Config for {self.tenant.company_name}")
        self.assertTrue(config.use_automatic_journal_entries)
        self.assertEqual(config.inventory_valuation_method, "FIFO")

    def test_journal_entry_template_model(self):
        """Test JournalEntryTemplate model."""
        template = JournalEntryTemplate.objects.create(
            name="Test Sale Template",
            template_type="CASH_SALE",
            description="Test template for cash sales",
            is_active=True,
        )

        self.assertEqual(str(template), "Test Sale Template")
        self.assertTrue(template.is_active)

    def test_journal_entry_template_line_model(self):
        """Test JournalEntryTemplateLine model."""
        template = JournalEntryTemplate.objects.create(
            name="Test Sale Template",
            template_type="CASH_SALE",
            description="Test template",
            is_active=True,
        )

        line = JournalEntryTemplateLine.objects.create(
            template=template,
            account_code="1001",
            debit_credit="DEBIT",
            amount_field="total",
            description_template="Sale #{sale_number}",
            order=1,
        )

        self.assertEqual(str(line), "Test Sale Template - 1001 (DEBIT)")
        self.assertEqual(line.order, 1)


@pytest.mark.django_db
class AccountingJournalEntryTest:
    """Test cases for automatic journal entry creation."""

    @pytest.fixture(autouse=True)
    def setup_test_data(self, tenant, tenant_user, branch):
        """Set up test data using fixtures."""
        from apps.core.tenant_context import tenant_context
        from apps.inventory.models import InventoryItem, ProductCategory
        from apps.sales.models import Customer, Terminal

        self.tenant = tenant
        self.user = tenant_user
        self.branch = branch

        # Set up accounting for tenant
        with tenant_context(tenant.id):
            self.jewelry_entity = AccountingService.setup_tenant_accounting(self.tenant, self.user)

            # Create terminal for sales
            self.terminal = Terminal.objects.create(
                branch=self.branch, terminal_id="POS-01", is_active=True
            )

            # Create customer
            self.customer = Customer.objects.create(
                tenant=self.tenant,
                customer_number="CUST-001",
                first_name="John",
                last_name="Doe",
                phone="555-1234",
            )

            # Create inventory item
            self.category = ProductCategory.objects.create(tenant=self.tenant, name="Rings")

            self.inventory_item = InventoryItem.objects.create(
                tenant=self.tenant,
                sku="RING-001",
                name="Gold Ring",
                category=self.category,
                karat=24,
                weight_grams=Decimal("10.5"),
                cost_price=Decimal("500.00"),
                selling_price=Decimal("800.00"),
                quantity=10,
                branch=self.branch,
            )

    def test_cash_sale_journal_entry_creation(self):
        """Test automatic journal entry creation for cash sales."""
        from django_ledger.models import JournalEntryModel, TransactionModel

        from apps.core.tenant_context import tenant_context
        from apps.sales.models import Sale, SaleItem

        with tenant_context(self.tenant.id):
            # Create a cash sale
            sale = Sale.objects.create(
                tenant=self.tenant,
                sale_number="SALE-001",
                customer=self.customer,
                branch=self.branch,
                terminal=self.terminal,
                employee=self.user,
                subtotal=Decimal("800.00"),
                tax=Decimal("64.00"),
                total=Decimal("864.00"),
                payment_method="CASH",
                status="COMPLETED",
            )

            # Create sale item
            SaleItem.objects.create(
                sale=sale,
                inventory_item=self.inventory_item,
                quantity=1,
                unit_price=Decimal("800.00"),
                subtotal=Decimal("800.00"),
            )

            # Check that journal entry was created
            journal_entries = JournalEntryModel.objects.filter(
                entity=self.jewelry_entity.ledger_entity, description__contains=sale.sale_number
            )
            assert journal_entries.count() == 1

            journal_entry = journal_entries.first()
            transactions = TransactionModel.objects.filter(journal_entry=journal_entry)

            # Should have 5 transactions: Cash (Dr), Sales (Cr), Tax (Cr), COGS (Dr), Inventory (Cr)
            assert transactions.count() == 5

            # Check cash debit
            cash_transaction = transactions.filter(tx_type="debit", account__code="1001").first()
            assert cash_transaction is not None
            assert cash_transaction.amount == Decimal("864.00")

            # Check sales credit
            sales_transaction = transactions.filter(tx_type="credit", account__code="4001").first()
            assert sales_transaction is not None
            assert sales_transaction.amount == Decimal("800.00")

            # Check tax credit
            tax_transaction = transactions.filter(tx_type="credit", account__code="2003").first()
            assert tax_transaction is not None
            assert tax_transaction.amount == Decimal("64.00")

            # Check COGS debit
            cogs_transaction = transactions.filter(tx_type="debit", account__code="5001").first()
            assert cogs_transaction is not None
            assert cogs_transaction.amount == Decimal("500.00")

            # Check inventory credit
            inventory_transaction = transactions.filter(
                tx_type="credit", account__code="1200"
            ).first()
            assert inventory_transaction is not None
            assert inventory_transaction.amount == Decimal("500.00")

    def test_card_sale_journal_entry_creation(self):
        """Test automatic journal entry creation for card sales."""
        from django_ledger.models import JournalEntryModel, TransactionModel

        from apps.core.tenant_context import tenant_context
        from apps.sales.models import Sale, SaleItem

        with tenant_context(self.tenant.id):
            # Create a card sale
            sale = Sale.objects.create(
                tenant=self.tenant,
                sale_number="SALE-002",
                customer=self.customer,
                branch=self.branch,
                terminal=self.terminal,
                employee=self.user,
                subtotal=Decimal("800.00"),
                tax=Decimal("64.00"),
                total=Decimal("864.00"),
                payment_method="CARD",
                status="COMPLETED",
            )

            # Create sale item
            SaleItem.objects.create(
                sale=sale,
                inventory_item=self.inventory_item,
                quantity=1,
                unit_price=Decimal("800.00"),
                subtotal=Decimal("800.00"),
            )

            # Check that journal entry was created
            journal_entries = JournalEntryModel.objects.filter(
                entity=self.jewelry_entity.ledger_entity, description__contains=sale.sale_number
            )
            assert journal_entries.count() == 1

            journal_entry = journal_entries.first()
            transactions = TransactionModel.objects.filter(journal_entry=journal_entry)

            # Check card processing account debit (should use account 1002)
            card_transaction = transactions.filter(tx_type="debit", account__code="1002").first()
            assert card_transaction is not None
            assert card_transaction.amount == Decimal("864.00")

    def test_expense_category_mapping(self):
        """Test that expense categories map to correct account codes."""
        test_cases = [
            ("RENT", "5100"),
            ("UTILITIES", "5101"),
            ("INSURANCE", "5102"),
            ("MARKETING", "5103"),
            ("WAGES", "5200"),
            ("PROFESSIONAL", "5201"),
            ("BANK_FEES", "5202"),
            ("OTHER", "5400"),
        ]

        for category, expected_code in test_cases:
            actual_code = AccountingService._get_expense_account_code(category)
            assert (
                actual_code == expected_code
            ), f"Category {category} should map to {expected_code}"


class AccountingViewsTest(TestCase):
    """Test cases for accounting views."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop", slug="test-shop", status="ACTIVE"
            )

            self.user = User.objects.create_user(
                username="testowner",
                email="owner@test.com",
                password="testpass123",
                tenant=self.tenant,
                role="TENANT_OWNER",
            )

        # Set up accounting
        self.jewelry_entity = AccountingService.setup_tenant_accounting(self.tenant, self.user)

        # Set tenant context and force login
        set_tenant_context(self.tenant.id)
        self.client.force_login(self.user)

    def test_financial_reports_view(self):
        """Test financial reports view."""
        response = self.client.get(reverse("accounting:financial_reports"))
        self.assertEqual(response.status_code, 200)
        # Check that the view returns successfully and has reports context
        self.assertIn("reports", response.context)

    def test_chart_of_accounts_view(self):
        """Test chart of accounts view."""
        response = self.client.get(reverse("accounting:chart_of_accounts"))
        self.assertEqual(response.status_code, 200)
        # Check that the view returns successfully and has accounts context
        self.assertIn("accounts", response.context)

    def test_accounting_configuration_view(self):
        """Test accounting configuration view."""
        response = self.client.get(reverse("accounting:configuration"))
        self.assertEqual(response.status_code, 200)
        # Check that the view returns successfully and has config context
        self.assertIn("config", response.context)

    def test_account_balance_api(self):
        """Test account balance API."""
        response = self.client.get(
            reverse("accounting:account_balance_api", kwargs={"account_code": "1001"})
        )
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["account_code"], "1001")
        self.assertIn("balance", data)
        self.assertIn("as_of_date", data)

    def test_setup_accounting_api(self):
        """Test setup accounting API."""
        # Create a new tenant without accounting
        with bypass_rls():
            new_tenant = Tenant.objects.create(
                company_name="New Test Shop", slug="new-test-shop", status="ACTIVE"
            )

            new_user = User.objects.create_user(
                username="newowner",
                email="newowner@test.com",
                password="testpass123",
                tenant=new_tenant,
                role="TENANT_OWNER",
            )

        # Create new client for this test
        new_client = Client()
        set_tenant_context(new_tenant.id)
        new_client.force_login(new_user)

        # Verify no accounting exists yet
        self.assertFalse(JewelryEntity.objects.filter(tenant=new_tenant).exists())

        response = new_client.post(reverse("accounting:setup_accounting_api"))
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("entity_id", data)

        # Verify accounting was set up
        self.assertTrue(JewelryEntity.objects.filter(tenant=new_tenant).exists())

    def test_account_balance_calculation_with_transactions(self):
        """Test account balance calculation with actual transactions."""
        from datetime import date

        from django_ledger.models import AccountModel, JournalEntryModel, TransactionModel

        from apps.core.tenant_context import tenant_context

        with tenant_context(self.tenant.id):
            # Get cash account
            entity = self.jewelry_entity.ledger_entity
            coa = entity.chartofaccountmodel_set.first()
            cash_account = AccountModel.objects.get(coa_model=coa, code="1001")

            # Create a manual journal entry to test balance calculation
            ledger = entity.ledgermodel_set.first()
            journal_entry = JournalEntryModel.objects.create(
                ledger=ledger,
                description="Test transaction for balance calculation",
                posted=False,
            )

            # Add a debit transaction to cash account
            TransactionModel.objects.create(
                journal_entry=journal_entry,
                account=cash_account,
                amount=Decimal("500.00"),
                tx_type="debit",
                description="Test cash debit",
            )

            # Add a credit transaction to balance the entry
            sales_account = AccountModel.objects.get(coa_model=coa, code="4001")
            TransactionModel.objects.create(
                journal_entry=journal_entry,
                account=sales_account,
                amount=Decimal("500.00"),
                tx_type="credit",
                description="Test sales credit",
            )

            # Post the journal entry
            journal_entry.posted = True
            journal_entry.save()

            # Calculate balance
            balance = AccountingService._get_account_balance_for_date(cash_account, date.today())

            # Cash account is a debit account, so debit increases balance
            self.assertEqual(balance, Decimal("500.00"))

    def test_fiscal_year_closing_comprehensive(self):
        """Test comprehensive fiscal year closing functionality."""
        from datetime import date

        from django_ledger.models import AccountModel, JournalEntryModel, TransactionModel

        from apps.core.tenant_context import tenant_context

        with tenant_context(self.tenant.id):
            entity = self.jewelry_entity.ledger_entity
            coa = entity.chartofaccountmodel_set.first()
            ledger = entity.ledgermodel_set.first()

            # Create some revenue and expense transactions
            # Revenue transaction
            revenue_entry = JournalEntryModel.objects.create(
                ledger=ledger,
                description="Test revenue for fiscal year closing",
                posted=False,
            )

            sales_account = AccountModel.objects.get(coa_model=coa, code="4001")  # Jewelry Sales
            cash_account = AccountModel.objects.get(coa_model=coa, code="1001")  # Cash

            TransactionModel.objects.create(
                journal_entry=revenue_entry,
                account=cash_account,
                amount=Decimal("1000.00"),
                tx_type="debit",
                description="Cash from sales",
            )

            TransactionModel.objects.create(
                journal_entry=revenue_entry,
                account=sales_account,
                amount=Decimal("1000.00"),
                tx_type="credit",
                description="Sales revenue",
            )

            # Post the revenue entry
            revenue_entry.posted = True
            revenue_entry.save()

            # Expense transaction
            expense_entry = JournalEntryModel.objects.create(
                ledger=ledger,
                description="Test expense for fiscal year closing",
                posted=False,
            )

            rent_account = AccountModel.objects.get(coa_model=coa, code="5100")  # Rent Expense

            TransactionModel.objects.create(
                journal_entry=expense_entry,
                account=rent_account,
                amount=Decimal("300.00"),
                tx_type="debit",
                description="Rent expense",
            )

            TransactionModel.objects.create(
                journal_entry=expense_entry,
                account=cash_account,
                amount=Decimal("300.00"),
                tx_type="credit",
                description="Cash paid for rent",
            )

            # Post the expense entry
            expense_entry.posted = True
            expense_entry.save()

            # Close fiscal year
            fiscal_year_end = date.today()
            result = AccountingService.close_fiscal_year(self.tenant, fiscal_year_end, self.user)

            # Verify closing was successful
            self.assertTrue(result["success"])
            self.assertEqual(result["net_income"], Decimal("700.00"))  # 1000 revenue - 300 expense
            self.assertEqual(result["total_revenue_closed"], Decimal("1000.00"))
            self.assertEqual(result["total_expenses_closed"], Decimal("300.00"))

            # Verify closing entry exists and is posted
            closing_entry = JournalEntryModel.objects.get(pk=result["closing_entry_id"])
            self.assertTrue(closing_entry.posted)
            self.assertIn("Fiscal Year End Closing", closing_entry.description)

            # Verify closing transactions were created
            closing_transactions = TransactionModel.objects.filter(journal_entry=closing_entry)
            self.assertGreater(closing_transactions.count(), 0)

    def test_financial_reports_accuracy(self):
        """Test accuracy of financial reports with known data."""
        from datetime import date, timedelta

        from django_ledger.models import AccountModel, JournalEntryModel, TransactionModel

        from apps.core.tenant_context import tenant_context

        with tenant_context(self.tenant.id):
            entity = self.jewelry_entity.ledger_entity
            coa = entity.chartofaccountmodel_set.first()
            ledger = entity.ledgermodel_set.first()

            # Create known transactions
            test_entry = JournalEntryModel.objects.create(
                ledger=ledger,
                description="Test entry for report accuracy",
                posted=False,
            )

            cash_account = AccountModel.objects.get(coa_model=coa, code="1001")
            sales_account = AccountModel.objects.get(coa_model=coa, code="4001")

            # $500 cash sale
            TransactionModel.objects.create(
                journal_entry=test_entry,
                account=cash_account,
                amount=Decimal("500.00"),
                tx_type="debit",
                description="Cash from test sale",
            )

            TransactionModel.objects.create(
                journal_entry=test_entry,
                account=sales_account,
                amount=Decimal("500.00"),
                tx_type="credit",
                description="Test sales revenue",
            )

            # Post the test entry
            test_entry.posted = True
            test_entry.save()

            # Generate reports
            end_date = date.today()
            start_date = end_date - timedelta(days=1)
            reports = AccountingService.get_financial_reports(self.tenant, start_date, end_date)

            # Verify balance sheet shows cash asset
            balance_sheet = reports["balance_sheet"]
            cash_found = False
            for asset in balance_sheet["assets"]["current_assets"]:
                if asset["code"] == "1001":
                    self.assertEqual(asset["balance"], Decimal("500.00"))
                    cash_found = True
                    break
            self.assertTrue(cash_found, "Cash account not found in balance sheet")

            # Verify income statement shows revenue
            income_statement = reports["income_statement"]
            revenue_found = False
            for revenue in income_statement["revenue"]["operating_revenue"]:
                if revenue["code"] == "4001":
                    self.assertEqual(revenue["balance"], Decimal("500.00"))
                    revenue_found = True
                    break
            self.assertTrue(revenue_found, "Sales revenue not found in income statement")

            # Verify net income
            self.assertEqual(income_statement["net_income"], Decimal("500.00"))

            # Verify trial balance is balanced
            trial_balance = reports["trial_balance"]
            self.assertTrue(trial_balance["is_balanced"])
            self.assertEqual(trial_balance["total_debits"], trial_balance["total_credits"])

    def test_accounting_model_validations(self):
        """Test accounting model validations and properties."""
        # Test JewelryChartOfAccounts model
        account = JewelryChartOfAccounts.objects.create(
            name="Test Validation Account",
            account_type="CASH",
            account_code="9999",
            description="Test account for validation",
            is_active=True,
        )

        # Test string representation
        self.assertEqual(str(account), "9999 - Test Validation Account")

        # Test AccountingConfiguration model
        config = AccountingConfiguration.objects.get(tenant=self.tenant)
        self.assertEqual(str(config), f"Accounting Config for {self.tenant.company_name}")
        self.assertTrue(config.use_automatic_journal_entries)
        self.assertEqual(config.inventory_valuation_method, "FIFO")

        # Test JournalEntryTemplate model
        template = JournalEntryTemplate.objects.create(
            name="Test Template",
            template_type="CASH_SALE",
            description="Test template for validation",
            is_active=True,
        )
        self.assertEqual(str(template), "Test Template")

        # Test JournalEntryTemplateLine model
        line = JournalEntryTemplateLine.objects.create(
            template=template,
            account_code="1001",
            debit_credit="DEBIT",
            amount_field="total",
            description_template="Test line #{sale_number}",
            order=1,
        )
        self.assertEqual(str(line), "Test Template - 1001 (DEBIT)")
        self.assertEqual(line.order, 1)

    def test_accounting_service_error_handling(self):
        """Test error handling in accounting service methods."""
        from datetime import date, timedelta

        # Test with invalid tenant
        with bypass_rls():
            invalid_tenant = Tenant.objects.create(
                company_name="Invalid Tenant", slug="invalid-tenant", status="ACTIVE"
            )

        # Test get_financial_reports with tenant that has no accounting setup
        reports = AccountingService.get_financial_reports(
            invalid_tenant, date.today() - timedelta(days=30), date.today()
        )
        self.assertEqual(reports, {})

        # Test get_account_balance with invalid account
        balance = AccountingService.get_account_balance(
            invalid_tenant, "INVALID_CODE", date.today()
        )
        self.assertEqual(balance, Decimal("0"))

    def test_chart_of_accounts_completeness(self):
        """Test that all required accounts are created in chart of accounts."""
        from django_ledger.models import AccountModel

        from apps.core.tenant_context import tenant_context

        with tenant_context(self.tenant.id):
            entity = self.jewelry_entity.ledger_entity
            coa = entity.chartofaccountmodel_set.first()
            accounts = AccountModel.objects.filter(coa_model=coa, active=True)

            # Required accounts for jewelry business
            required_accounts = {
                "1001": "Cash - Checking Account",
                "1002": "Cash - Credit Card Processing",
                "1200": "Inventory - Finished Goods",
                "2001": "Accounts Payable",
                "2003": "Sales Tax Payable",
                "3002": "Retained Earnings",
                "4001": "Jewelry Sales",
                "5001": "Cost of Goods Sold",
                "5100": "Rent Expense",
            }

            account_codes = {acc.code: acc.name for acc in accounts}

            for code, expected_name in required_accounts.items():
                self.assertIn(code, account_codes, f"Required account {code} not found")
                self.assertEqual(
                    account_codes[code],
                    expected_name,
                    f"Account {code} has wrong name: {account_codes[code]}",
                )
