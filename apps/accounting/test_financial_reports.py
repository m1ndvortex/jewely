"""
Tests for financial reports functionality.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

import pytest

from apps.core.models import Tenant
from apps.core.tenant_context import bypass_rls, tenant_context
from apps.inventory.models import InventoryItem, ProductCategory
from apps.sales.models import Customer, Sale, SaleItem, Terminal

from .services import AccountingService

User = get_user_model()


@pytest.mark.django_db
class FinancialReportsTest:
    """Test cases for financial reports functionality."""

    @pytest.fixture(autouse=True)
    def setup_test_data(self, tenant, tenant_user, branch):
        """Set up test data using fixtures."""
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

    def test_get_financial_reports_with_data(self):
        """Test financial reports generation with actual transaction data."""
        with tenant_context(self.tenant.id):
            # Create a sale to generate some data
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

            # Generate financial reports
            end_date = date.today()
            start_date = end_date - timedelta(days=30)

            reports = AccountingService.get_financial_reports(self.tenant, start_date, end_date)

            # Verify reports structure
            assert "balance_sheet" in reports
            assert "income_statement" in reports
            assert "cash_flow" in reports
            assert "trial_balance" in reports
            assert "period" in reports

            # Verify balance sheet structure
            balance_sheet = reports["balance_sheet"]
            assert "assets" in balance_sheet
            assert "liabilities" in balance_sheet
            assert "equity" in balance_sheet
            assert "as_of_date" in balance_sheet

            # Verify income statement structure
            income_statement = reports["income_statement"]
            assert "revenue" in income_statement
            assert "expenses" in income_statement
            assert "net_income" in income_statement
            assert "period" in income_statement

            # Verify cash flow structure
            cash_flow = reports["cash_flow"]
            assert "operating_activities" in cash_flow
            assert "investing_activities" in cash_flow
            assert "financing_activities" in cash_flow
            assert "net_change_in_cash" in cash_flow

            # Verify trial balance structure
            trial_balance = reports["trial_balance"]
            assert "accounts" in trial_balance
            assert "total_debits" in trial_balance
            assert "total_credits" in trial_balance
            assert "is_balanced" in trial_balance

    def test_balance_sheet_generation(self):
        """Test balance sheet generation with specific account data."""
        with tenant_context(self.tenant.id):
            end_date = date.today()

            balance_sheet = AccountingService._generate_balance_sheet(
                self.jewelry_entity.ledger_entity, end_date
            )

            # Verify structure
            assert "assets" in balance_sheet
            assert "liabilities" in balance_sheet
            assert "equity" in balance_sheet
            assert balance_sheet["as_of_date"] == end_date

            # Verify assets structure
            assets = balance_sheet["assets"]
            assert "current_assets" in assets
            assert "fixed_assets" in assets
            assert "total_assets" in assets

    def test_income_statement_generation(self):
        """Test income statement generation."""
        with tenant_context(self.tenant.id):
            end_date = date.today()
            start_date = end_date - timedelta(days=30)

            income_statement = AccountingService._generate_income_statement(
                self.jewelry_entity.ledger_entity, start_date, end_date
            )

            # Verify structure
            assert "revenue" in income_statement
            assert "expenses" in income_statement
            assert "net_income" in income_statement
            assert "period" in income_statement

            # Verify revenue structure
            revenue = income_statement["revenue"]
            assert "operating_revenue" in revenue
            assert "other_revenue" in revenue
            assert "total_revenue" in revenue

            # Verify expenses structure
            expenses = income_statement["expenses"]
            assert "cost_of_goods_sold" in expenses
            assert "operating_expenses" in expenses
            assert "other_expenses" in expenses
            assert "total_expenses" in expenses

    def test_trial_balance_generation(self):
        """Test trial balance generation."""
        with tenant_context(self.tenant.id):
            end_date = date.today()

            trial_balance = AccountingService._generate_trial_balance(
                self.jewelry_entity.ledger_entity, end_date
            )

            # Verify structure
            assert "accounts" in trial_balance
            assert "total_debits" in trial_balance
            assert "total_credits" in trial_balance
            assert "is_balanced" in trial_balance
            assert trial_balance["as_of_date"] == end_date

    def test_cash_flow_generation(self):
        """Test cash flow statement generation."""
        with tenant_context(self.tenant.id):
            end_date = date.today()
            start_date = end_date - timedelta(days=30)

            cash_flow = AccountingService._generate_cash_flow_statement(
                self.jewelry_entity.ledger_entity, start_date, end_date
            )

            # Verify structure
            assert "operating_activities" in cash_flow
            assert "investing_activities" in cash_flow
            assert "financing_activities" in cash_flow
            assert "net_change_in_cash" in cash_flow
            assert "cash_beginning" in cash_flow
            assert "cash_ending" in cash_flow
            assert "period" in cash_flow

    def test_export_financial_reports_to_pdf(self):
        """Test PDF export functionality."""
        with tenant_context(self.tenant.id):
            end_date = date.today()
            start_date = end_date - timedelta(days=30)

            # This should not raise an exception
            pdf_data = AccountingService.export_financial_reports_to_pdf(
                self.tenant, start_date, end_date
            )

            # Verify PDF data is returned
            assert isinstance(pdf_data, bytes)
            assert len(pdf_data) > 0
            # PDF files start with %PDF
            assert pdf_data.startswith(b"%PDF")

    def test_export_financial_reports_to_excel(self):
        """Test Excel export functionality."""
        with tenant_context(self.tenant.id):
            end_date = date.today()
            start_date = end_date - timedelta(days=30)

            # This should not raise an exception
            excel_data = AccountingService.export_financial_reports_to_excel(
                self.tenant, start_date, end_date
            )

            # Verify Excel data is returned
            assert isinstance(excel_data, bytes)
            assert len(excel_data) > 0
            # Excel files start with PK (ZIP signature)
            assert excel_data.startswith(b"PK")

    def test_fiscal_year_closing(self):
        """Test fiscal year closing functionality."""
        with tenant_context(self.tenant.id):
            # Create some transactions first
            sale = Sale.objects.create(
                tenant=self.tenant,
                sale_number="SALE-FY001",
                customer=self.customer,
                branch=self.branch,
                terminal=self.terminal,
                employee=self.user,
                subtotal=Decimal("1000.00"),
                tax=Decimal("80.00"),
                total=Decimal("1080.00"),
                payment_method="CASH",
                status="COMPLETED",
            )

            SaleItem.objects.create(
                sale=sale,
                inventory_item=self.inventory_item,
                quantity=1,
                unit_price=Decimal("1000.00"),
                subtotal=Decimal("1000.00"),
            )

            # Close fiscal year
            fiscal_year_end = date(date.today().year, 12, 31)
            result = AccountingService.close_fiscal_year(self.tenant, fiscal_year_end, self.user)

            # Verify closing was successful
            assert result["success"] is True
            assert "net_income" in result
            assert "total_revenue_closed" in result
            assert "total_expenses_closed" in result
            assert "closing_entry_id" in result

            # Verify closing journal entry was created
            from django_ledger.models import JournalEntryModel

            closing_entry = JournalEntryModel.objects.get(pk=result["closing_entry_id"])
            assert closing_entry.posted is True
            assert "Fiscal Year End Closing" in closing_entry.description

    def test_comprehensive_accounting_workflow(self):
        """Test complete accounting workflow from setup to reporting."""
        with tenant_context(self.tenant.id):
            # 1. Verify chart of accounts setup
            from django_ledger.models import AccountModel

            entity = self.jewelry_entity.ledger_entity
            coa = entity.chartofaccountmodel_set.first()
            accounts = AccountModel.objects.filter(coa_model=coa, active=True)

            # Verify we have all required account types
            account_codes = [acc.code for acc in accounts]
            required_accounts = ["1001", "1200", "2001", "2003", "3002", "4001", "5001", "5100"]
            for code in required_accounts:
                assert code in account_codes, f"Required account {code} not found"

            # 2. Test transaction creation and journal entries
            sale = Sale.objects.create(
                tenant=self.tenant,
                sale_number="SALE-WORKFLOW",
                customer=self.customer,
                branch=self.branch,
                terminal=self.terminal,
                employee=self.user,
                subtotal=Decimal("500.00"),
                tax=Decimal("40.00"),
                total=Decimal("540.00"),
                payment_method="CASH",
                status="COMPLETED",
            )

            SaleItem.objects.create(
                sale=sale,
                inventory_item=self.inventory_item,
                quantity=1,
                unit_price=Decimal("500.00"),
                subtotal=Decimal("500.00"),
            )

            # 3. Verify journal entries were created automatically
            from django_ledger.models import JournalEntryModel, TransactionModel

            ledger = entity.ledgermodel_set.first()
            journal_entries = JournalEntryModel.objects.filter(
                ledger=ledger, description__contains=sale.sale_number
            )
            assert journal_entries.count() == 1

            journal_entry = journal_entries.first()
            transactions = TransactionModel.objects.filter(journal_entry=journal_entry)

            # Verify double-entry bookkeeping
            total_debits = sum(t.amount for t in transactions if t.tx_type == "debit")
            total_credits = sum(t.amount for t in transactions if t.tx_type == "credit")
            assert total_debits == total_credits, "Double-entry bookkeeping violated"

            # 4. Test financial reports generation
            end_date = date.today()
            start_date = end_date - timedelta(days=30)
            reports = AccountingService.get_financial_reports(self.tenant, start_date, end_date)

            # Verify all required reports are generated
            assert "balance_sheet" in reports
            assert "income_statement" in reports
            assert "cash_flow" in reports
            assert "trial_balance" in reports

            # 5. Verify trial balance is balanced
            trial_balance = reports["trial_balance"]
            assert trial_balance["is_balanced"] is True
            assert trial_balance["total_debits"] == trial_balance["total_credits"]

            # 6. Test account balance calculations
            cash_account = AccountModel.objects.get(coa_model=coa, code="1001")
            balance = AccountingService._get_account_balance_for_date(cash_account, end_date)
            assert isinstance(balance, Decimal)

    def test_tenant_isolation_in_accounting(self):
        """Test that accounting data is properly isolated between tenants."""
        # Create a second tenant
        from apps.core.models import Tenant, User
        from apps.core.tenant_context import bypass_rls

        with bypass_rls():
            tenant2 = Tenant.objects.create(
                company_name="Second Jewelry Shop", slug="second-shop", status="ACTIVE"
            )

            user2 = User.objects.create_user(
                username="secondowner",
                email="owner2@test.com",
                password="testpass123",
                tenant=tenant2,
                role="TENANT_OWNER",
            )

        # Set up accounting for second tenant
        jewelry_entity2 = AccountingService.setup_tenant_accounting(tenant2, user2)

        # Test that each tenant has separate accounting entities
        assert self.jewelry_entity.tenant != jewelry_entity2.tenant
        assert self.jewelry_entity.ledger_entity != jewelry_entity2.ledger_entity

        # Test that financial reports are isolated
        with tenant_context(self.tenant.id):
            reports1 = AccountingService.get_financial_reports(
                self.tenant, date.today() - timedelta(days=30), date.today()
            )

        with tenant_context(tenant2.id):
            reports2 = AccountingService.get_financial_reports(
                tenant2, date.today() - timedelta(days=30), date.today()
            )

        # Reports should be different (tenant isolation)
        assert reports1 != reports2

    def test_account_balance_calculation(self):
        """Test account balance calculation."""
        with tenant_context(self.tenant.id):
            from django_ledger.models import AccountModel

            # Get a cash account
            coa = self.jewelry_entity.ledger_entity.chartofaccountmodel_set.first()
            cash_account = AccountModel.objects.filter(coa_model=coa, code="1001").first()

            if cash_account:
                end_date = date.today()
                balance = AccountingService._get_account_balance_for_date(cash_account, end_date)

                # Balance should be a Decimal
                assert isinstance(balance, Decimal)

    def test_account_period_balance_calculation(self):
        """Test account period balance calculation."""
        with tenant_context(self.tenant.id):
            from django_ledger.models import AccountModel

            # Get a revenue account
            coa = self.jewelry_entity.ledger_entity.chartofaccountmodel_set.first()
            revenue_account = AccountModel.objects.filter(coa_model=coa, code="4001").first()

            if revenue_account:
                end_date = date.today()
                start_date = end_date - timedelta(days=30)
                balance = AccountingService._get_account_period_balance(
                    revenue_account, start_date, end_date
                )

                # Balance should be a Decimal
                assert isinstance(balance, Decimal)


class FinancialReportsViewTest(TestCase):
    """Test cases for financial reports views."""

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

        # Set up accounting
        self.jewelry_entity = AccountingService.setup_tenant_accounting(self.tenant, self.user)

        # Force login
        self.client.force_login(self.user)

    def test_financial_reports_view_with_date_params(self):
        """Test financial reports view with date parameters."""
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        response = self.client.get(
            reverse("accounting:financial_reports"),
            {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("reports", response.context)
        self.assertEqual(response.context["start_date"], start_date)
        self.assertEqual(response.context["end_date"], end_date)

    def test_export_pdf_view(self):
        """Test PDF export view."""
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        response = self.client.get(
            reverse("accounting:export_reports_pdf"),
            {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])

    def test_export_excel_view(self):
        """Test Excel export view."""
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        response = self.client.get(
            reverse("accounting:export_reports_excel"),
            {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("attachment", response["Content-Disposition"])
