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

    def test_purchase_order_journal_entry(self):
        """Test journal entry creation for purchase orders."""
        from django_ledger.models import TransactionModel

        from apps.accounting.transaction_models import PurchaseOrder

        with tenant_context(self.tenant.id):
            # Create a purchase order
            purchase_order = PurchaseOrder.objects.create(
                tenant=self.tenant,
                po_number="PO-001",
                supplier_name="Test Supplier",
                total_amount=Decimal("2000.00"),
                status="APPROVED",
                created_by=self.user,
            )

            # Create journal entry for purchase
            journal_entry = AccountingService.create_purchase_journal_entry(
                purchase_order, self.user
            )

            # Verify journal entry was created
            self.assertIsNotNone(journal_entry)
            self.assertTrue(journal_entry.posted)

            # Verify transactions
            transactions = TransactionModel.objects.filter(journal_entry=journal_entry)
            self.assertEqual(transactions.count(), 2)

            # Check inventory debit
            inventory_debit = transactions.filter(tx_type="debit", account__code="1200").first()
            self.assertIsNotNone(inventory_debit)
            self.assertEqual(inventory_debit.amount, Decimal("2000.00"))

            # Check accounts payable credit
            payable_credit = transactions.filter(tx_type="credit", account__code="2001").first()
            self.assertIsNotNone(payable_credit)
            self.assertEqual(payable_credit.amount, Decimal("2000.00"))

    def test_payment_journal_entry(self):
        """Test journal entry creation for supplier payments."""
        from django_ledger.models import TransactionModel

        from apps.accounting.transaction_models import Payment

        with tenant_context(self.tenant.id):
            # Create a payment
            payment = Payment.objects.create(
                tenant=self.tenant,
                payment_number="PAY-001",
                supplier_name="Test Supplier",
                amount=Decimal("1500.00"),
                payment_method="CHECK",
                description="Payment for inventory",
                created_by=self.user,
            )

            # Create journal entry for payment
            journal_entry = AccountingService.create_payment_journal_entry(payment, self.user)

            # Verify journal entry was created
            self.assertIsNotNone(journal_entry)
            self.assertTrue(journal_entry.posted)

            # Verify transactions
            transactions = TransactionModel.objects.filter(journal_entry=journal_entry)
            self.assertEqual(transactions.count(), 2)

            # Check accounts payable debit (reducing liability)
            payable_debit = transactions.filter(tx_type="debit", account__code="2001").first()
            self.assertIsNotNone(payable_debit)
            self.assertEqual(payable_debit.amount, Decimal("1500.00"))

            # Check cash credit (reducing asset)
            cash_credit = transactions.filter(tx_type="credit", account__code="1001").first()
            self.assertIsNotNone(cash_credit)
            self.assertEqual(cash_credit.amount, Decimal("1500.00"))

    def test_expense_journal_entry(self):
        """Test journal entry creation for business expenses."""
        from django_ledger.models import TransactionModel

        from apps.accounting.transaction_models import Expense

        with tenant_context(self.tenant.id):
            # Create an expense
            expense = Expense.objects.create(
                tenant=self.tenant,
                description="Office rent payment",
                category="RENT",
                amount=Decimal("800.00"),
                payment_method="CASH",
                created_by=self.user,
            )

            # Create journal entry for expense
            journal_entry = AccountingService.create_expense_journal_entry(expense, self.user)

            # Verify journal entry was created
            self.assertIsNotNone(journal_entry)
            self.assertTrue(journal_entry.posted)

            # Verify transactions
            transactions = TransactionModel.objects.filter(journal_entry=journal_entry)
            self.assertEqual(transactions.count(), 2)

            # Check rent expense debit
            expense_debit = transactions.filter(tx_type="debit", account__code="5100").first()
            self.assertIsNotNone(expense_debit)
            self.assertEqual(expense_debit.amount, Decimal("800.00"))

            # Check cash credit
            cash_credit = transactions.filter(tx_type="credit", account__code="1001").first()
            self.assertIsNotNone(cash_credit)
            self.assertEqual(cash_credit.amount, Decimal("800.00"))

    def test_double_entry_validation(self):
        """Test that all journal entries maintain double-entry bookkeeping."""
        from django_ledger.models import JournalEntryModel, TransactionModel

        with tenant_context(self.tenant.id):
            # Create a sale to generate journal entries
            sale = Sale.objects.create(
                tenant=self.tenant,
                sale_number="SALE-VALIDATION",
                customer=self.customer,
                branch=self.branch,
                terminal=self.terminal,
                employee=self.user,
                subtotal=Decimal("750.00"),
                tax=Decimal("60.00"),
                total=Decimal("810.00"),
                payment_method="CARD",
                status="COMPLETED",
            )

            SaleItem.objects.create(
                sale=sale,
                inventory_item=self.inventory_item,
                quantity=1,
                unit_price=Decimal("750.00"),
                subtotal=Decimal("750.00"),
            )

            # Get the journal entry
            ledger = self.jewelry_entity.ledger_entity.ledgermodel_set.first()
            journal_entries = JournalEntryModel.objects.filter(
                ledger=ledger, description__contains=sale.sale_number
            )
            self.assertEqual(journal_entries.count(), 1)

            journal_entry = journal_entries.first()
            transactions = TransactionModel.objects.filter(journal_entry=journal_entry)

            # Calculate total debits and credits
            total_debits = sum(t.amount for t in transactions if t.tx_type == "debit")
            total_credits = sum(t.amount for t in transactions if t.tx_type == "credit")

            # Verify double-entry: debits must equal credits
            self.assertEqual(
                total_debits,
                total_credits,
                f"Debits ({total_debits}) must equal credits ({total_credits})",
            )

            # Verify we have both debits and credits
            debits = transactions.filter(tx_type="debit")
            credits = transactions.filter(tx_type="credit")
            self.assertGreater(debits.count(), 0, "Must have at least one debit transaction")
            self.assertGreater(credits.count(), 0, "Must have at least one credit transaction")
