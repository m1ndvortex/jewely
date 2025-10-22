"""
Simple integration test for journal entry creation.
"""

from decimal import Decimal

from django.test import TestCase

from apps.accounting.services import AccountingService
from apps.core.models import Branch, Tenant, User
from apps.core.tenant_context import bypass_rls, tenant_context
from apps.inventory.models import InventoryItem, ProductCategory
from apps.sales.models import Customer, Sale, SaleItem, Terminal


class JournalEntryIntegrationTest(TestCase):
    """Integration test for automatic journal entry creation."""

    def setUp(self):
        """Set up test data with proper RLS handling."""
        # Create tenant with RLS bypass
        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop", slug="test-jewelry-shop", status="ACTIVE"
            )

            # Create user
            self.user = User.objects.create_user(
                username="testuser", password="testpass123", tenant=self.tenant, role="TENANT_OWNER"
            )

        # Set up accounting for tenant
        with tenant_context(self.tenant.id):
            self.jewelry_entity = AccountingService.setup_tenant_accounting(self.tenant, self.user)
            # Get the entity unit for journal entries
            self.entity_unit = self.jewelry_entity.ledger_entity.entityunitmodel_set.first()

            # Create branch
            self.branch = Branch.objects.create(
                tenant=self.tenant, name="Main Store", address="123 Main St"
            )

            # Create terminal
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

    def test_cash_sale_creates_journal_entry(self):
        """Test that a cash sale automatically creates a journal entry."""
        from django_ledger.models import JournalEntryModel, TransactionModel

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
            ledger = self.jewelry_entity.ledger_entity.ledgermodel_set.first()
            journal_entries = JournalEntryModel.objects.filter(
                ledger=ledger, description__contains=sale.sale_number
            )

            # Should have created a journal entry
            self.assertEqual(journal_entries.count(), 1)

            journal_entry = journal_entries.first()
            transactions = TransactionModel.objects.filter(journal_entry=journal_entry)

            # Should have multiple transactions (cash, sales, tax, cogs, inventory)
            self.assertGreater(transactions.count(), 0)

            # Check that we have both debits and credits
            debits = transactions.filter(tx_type="debit")
            credits = transactions.filter(tx_type="credit")

            self.assertGreater(debits.count(), 0)
            self.assertGreater(credits.count(), 0)

            # Verify double-entry: total debits should equal total credits
            total_debits = sum(t.amount for t in debits)
            total_credits = sum(t.amount for t in credits)

            self.assertEqual(total_debits, total_credits)

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
            self.assertEqual(
                actual_code, expected_code, f"Category {category} should map to {expected_code}"
            )
