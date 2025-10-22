"""
Tests for the accounting module.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

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
