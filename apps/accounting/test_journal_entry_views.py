"""
Tests for manual journal entry views (Task 1.2).

Tests the journal entry list, create, detail, post, and reverse views.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

import pytest

# JewelryEntity imported via services
from apps.accounting.services import AccountingService
from apps.core.models import Tenant

User = get_user_model()


@pytest.mark.django_db
class JournalEntryViewsTest(TestCase):
    """Test cases for journal entry views."""

    def setUp(self):
        """Set up test data."""
        # Create tenant
        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop",
            slug="test-jewelry-shop",
            status=Tenant.ACTIVE,
        )

        # Create user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_OWNER",
        )

        # Set up accounting
        self.jewelry_entity = AccountingService.setup_tenant_accounting(self.tenant, self.user)
        self.entity = self.jewelry_entity.ledger_entity

        # Set up client and login
        self.client = Client()
        self.client.login(username="testuser", password="testpass123")

    def test_journal_entry_list_view(self):
        """Test journal entry list view with tenant filtering."""
        response = self.client.get(reverse("accounting:journal_entry_list"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("entries", response.context)
        self.assertIn("accounts", response.context)

    def test_journal_entry_list_with_filters(self):
        """Test journal entry list view with status and account filters."""
        response = self.client.get(
            reverse("accounting:journal_entry_list") + "?status=posted&account=1001"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["status_filter"], "posted")
        self.assertEqual(response.context["account_filter"], "1001")

    def test_journal_entry_create_view_get(self):
        """Test journal entry create view GET request."""
        response = self.client.get(reverse("accounting:journal_entry_create"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertIn("formset", response.context)

    def test_journal_entry_create_view_post(self):
        """Test journal entry create view POST request."""
        # Prepare form data
        data = {
            "description": "Test Journal Entry",
            "date": "2025-10-31",
            # Formset management form
            "transactionmodel_set-TOTAL_FORMS": "2",
            "transactionmodel_set-INITIAL_FORMS": "0",
            "transactionmodel_set-MIN_NUM_FORMS": "2",
            "transactionmodel_set-MAX_NUM_FORMS": "1000",
            # Line 1: Debit Cash
            "transactionmodel_set-0-account": self.entity.chartofaccountmodel_set.first()
            .accountmodel_set.filter(code="1001")
            .first()
            .uuid,
            "transactionmodel_set-0-debit": "100.00",
            "transactionmodel_set-0-credit": "0.00",
            "transactionmodel_set-0-description": "Cash debit",
            # Line 2: Credit Revenue
            "transactionmodel_set-1-account": self.entity.chartofaccountmodel_set.first()
            .accountmodel_set.filter(code="4001")
            .first()
            .uuid,
            "transactionmodel_set-1-debit": "0.00",
            "transactionmodel_set-1-credit": "100.00",
            "transactionmodel_set-1-description": "Revenue credit",
        }

        response = self.client.post(reverse("accounting:journal_entry_create"), data)

        # Should redirect to detail view on success
        self.assertEqual(response.status_code, 302)

    def test_journal_entry_detail_view(self):
        """Test journal entry detail view."""
        # Create a journal entry first
        from django_ledger.models import JournalEntryModel, TransactionModel

        ledger = self.entity.ledgermodel_set.first()
        entry = JournalEntryModel.objects.create(
            ledger=ledger,
            description="Test Entry",
            posted=False,
        )

        # Add transactions
        cash_account = (
            self.entity.chartofaccountmodel_set.first().accountmodel_set.filter(code="1001").first()
        )
        revenue_account = (
            self.entity.chartofaccountmodel_set.first().accountmodel_set.filter(code="4001").first()
        )

        TransactionModel.objects.create(
            journal_entry=entry,
            account=cash_account,
            amount=Decimal("100.00"),
            tx_type="debit",
            description="Cash debit",
        )

        TransactionModel.objects.create(
            journal_entry=entry,
            account=revenue_account,
            amount=Decimal("100.00"),
            tx_type="credit",
            description="Revenue credit",
        )

        response = self.client.get(
            reverse("accounting:journal_entry_detail", kwargs={"pk": entry.uuid})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("entry", response.context)
        self.assertEqual(response.context["total_debits"], Decimal("100.00"))
        self.assertEqual(response.context["total_credits"], Decimal("100.00"))
        self.assertTrue(response.context["is_balanced"])

    def test_journal_entry_post_view(self):
        """Test posting a journal entry."""
        # Create an unposted journal entry
        from django_ledger.models import JournalEntryModel, TransactionModel

        ledger = self.entity.ledgermodel_set.first()
        entry = JournalEntryModel.objects.create(
            ledger=ledger,
            description="Test Entry to Post",
            posted=False,
        )

        # Add balanced transactions
        cash_account = (
            self.entity.chartofaccountmodel_set.first().accountmodel_set.filter(code="1001").first()
        )
        revenue_account = (
            self.entity.chartofaccountmodel_set.first().accountmodel_set.filter(code="4001").first()
        )

        TransactionModel.objects.create(
            journal_entry=entry,
            account=cash_account,
            amount=Decimal("100.00"),
            tx_type="debit",
        )

        TransactionModel.objects.create(
            journal_entry=entry,
            account=revenue_account,
            amount=Decimal("100.00"),
            tx_type="credit",
        )

        # Post the entry
        response = self.client.post(
            reverse("accounting:journal_entry_post", kwargs={"pk": entry.uuid})
        )

        # Should redirect to detail view
        self.assertEqual(response.status_code, 302)

        # Verify entry is posted
        entry.refresh_from_db()
        self.assertTrue(entry.posted)

    def test_journal_entry_reverse_view_get(self):
        """Test journal entry reverse view GET request."""
        # Create a posted journal entry
        from django_ledger.models import JournalEntryModel, TransactionModel

        ledger = self.entity.ledgermodel_set.first()
        entry = JournalEntryModel.objects.create(
            ledger=ledger,
            description="Test Entry to Reverse",
            posted=False,
        )

        # Add transactions
        cash_account = (
            self.entity.chartofaccountmodel_set.first().accountmodel_set.filter(code="1001").first()
        )
        revenue_account = (
            self.entity.chartofaccountmodel_set.first().accountmodel_set.filter(code="4001").first()
        )

        TransactionModel.objects.create(
            journal_entry=entry,
            account=cash_account,
            amount=Decimal("100.00"),
            tx_type="debit",
        )

        TransactionModel.objects.create(
            journal_entry=entry,
            account=revenue_account,
            amount=Decimal("100.00"),
            tx_type="credit",
        )

        # Post the entry
        entry.posted = True
        entry.save()

        response = self.client.get(
            reverse("accounting:journal_entry_reverse", kwargs={"pk": entry.uuid})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("original_entry", response.context)

    def test_journal_entry_reverse_view_post(self):
        """Test creating a reversing journal entry."""
        # Create a posted journal entry
        from django_ledger.models import JournalEntryModel, TransactionModel

        ledger = self.entity.ledgermodel_set.first()
        entry = JournalEntryModel.objects.create(
            ledger=ledger,
            description="Test Entry to Reverse",
            posted=False,
        )

        # Add transactions
        cash_account = (
            self.entity.chartofaccountmodel_set.first().accountmodel_set.filter(code="1001").first()
        )
        revenue_account = (
            self.entity.chartofaccountmodel_set.first().accountmodel_set.filter(code="4001").first()
        )

        TransactionModel.objects.create(
            journal_entry=entry,
            account=cash_account,
            amount=Decimal("100.00"),
            tx_type="debit",
        )

        TransactionModel.objects.create(
            journal_entry=entry,
            account=revenue_account,
            amount=Decimal("100.00"),
            tx_type="credit",
        )

        # Post the entry
        entry.posted = True
        entry.save()

        # Create reversing entry
        response = self.client.post(
            reverse("accounting:journal_entry_reverse", kwargs={"pk": entry.uuid})
        )

        # Should redirect to detail view of new entry
        self.assertEqual(response.status_code, 302)

        # Verify reversing entry was created
        reversing_entries = JournalEntryModel.objects.filter(
            ledger=ledger, description__contains="REVERSAL"
        )
        self.assertEqual(reversing_entries.count(), 1)

        reversing_entry = reversing_entries.first()
        self.assertFalse(reversing_entry.posted)  # Should be unposted for review

        # Verify transactions are reversed
        reversing_txns = reversing_entry.transactionmodel_set.all()
        self.assertEqual(reversing_txns.count(), 2)

        # Check that debits and credits are swapped
        for txn in reversing_txns:
            if txn.account == cash_account:
                self.assertEqual(txn.tx_type, "credit")  # Was debit, now credit
            elif txn.account == revenue_account:
                self.assertEqual(txn.tx_type, "debit")  # Was credit, now debit

    def test_tenant_isolation(self):
        """Test that users can only see their tenant's journal entries."""
        # Create another tenant and user
        other_tenant = Tenant.objects.create(
            company_name="Other Jewelry Shop",
            slug="other-jewelry-shop",
            status=Tenant.ACTIVE,
        )

        other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="testpass123",
            tenant=other_tenant,
            role="TENANT_OWNER",
        )

        # Set up accounting for other tenant
        other_jewelry_entity = AccountingService.setup_tenant_accounting(other_tenant, other_user)

        # Create journal entry for other tenant
        from django_ledger.models import JournalEntryModel

        other_ledger = other_jewelry_entity.ledger_entity.ledgermodel_set.first()
        other_entry = JournalEntryModel.objects.create(
            ledger=other_ledger,
            description="Other Tenant Entry",
            posted=False,
        )

        # Try to access other tenant's entry
        response = self.client.get(
            reverse("accounting:journal_entry_detail", kwargs={"pk": other_entry.uuid})
        )

        # Should not find the entry (404 or redirect)
        self.assertNotEqual(response.status_code, 200)

    def test_audit_logging(self):
        """Test that all operations are logged to audit trail."""
        from apps.core.audit_models import AuditLog

        # Clear existing audit logs
        AuditLog.objects.filter(tenant=self.tenant).delete()

        # Perform operations
        self.client.get(reverse("accounting:journal_entry_list"))

        # Verify audit log was created
        audit_logs = AuditLog.objects.filter(tenant=self.tenant)
        self.assertGreater(audit_logs.count(), 0)

        # Verify log details
        log = audit_logs.first()
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.category, AuditLog.CATEGORY_DATA)
        self.assertIn("journal entries", log.description.lower())

    def test_journal_entry_edit_unposted(self):
        """Test editing an unposted journal entry."""
        # Create an unposted journal entry
        from django_ledger.models import JournalEntryModel, TransactionModel

        ledger = self.entity.ledgermodel_set.first()
        entry = JournalEntryModel.objects.create(
            ledger=ledger,
            description="Test Entry to Edit",
            posted=False,
        )

        # Add transactions
        cash_account = (
            self.entity.chartofaccountmodel_set.first().accountmodel_set.filter(code="1001").first()
        )
        revenue_account = (
            self.entity.chartofaccountmodel_set.first().accountmodel_set.filter(code="4001").first()
        )

        TransactionModel.objects.create(
            journal_entry=entry,
            account=cash_account,
            amount=Decimal("100.00"),
            tx_type="debit",
        )

        TransactionModel.objects.create(
            journal_entry=entry,
            account=revenue_account,
            amount=Decimal("100.00"),
            tx_type="credit",
        )

        # Edit the entry
        response = self.client.get(
            reverse("accounting:journal_entry_edit", kwargs={"pk": entry.uuid})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertIn("formset", response.context)

    def test_journal_entry_edit_posted_prevented(self):
        """Test that editing a posted journal entry is prevented."""
        # Create a posted journal entry
        from django_ledger.models import JournalEntryModel, TransactionModel

        ledger = self.entity.ledgermodel_set.first()
        entry = JournalEntryModel.objects.create(
            ledger=ledger,
            description="Posted Entry",
            posted=False,
        )

        # Add transactions
        cash_account = (
            self.entity.chartofaccountmodel_set.first().accountmodel_set.filter(code="1001").first()
        )
        revenue_account = (
            self.entity.chartofaccountmodel_set.first().accountmodel_set.filter(code="4001").first()
        )

        TransactionModel.objects.create(
            journal_entry=entry,
            account=cash_account,
            amount=Decimal("100.00"),
            tx_type="debit",
        )

        TransactionModel.objects.create(
            journal_entry=entry,
            account=revenue_account,
            amount=Decimal("100.00"),
            tx_type="credit",
        )

        # Post the entry
        entry.posted = True
        entry.save()

        # Try to edit the posted entry
        response = self.client.get(
            reverse("accounting:journal_entry_edit", kwargs={"pk": entry.uuid})
        )

        # Should redirect to detail page with error message
        self.assertEqual(response.status_code, 302)

    def test_journal_entry_delete_unposted(self):
        """Test deleting an unposted journal entry."""
        # Create an unposted journal entry
        from django_ledger.models import JournalEntryModel, TransactionModel

        ledger = self.entity.ledgermodel_set.first()
        entry = JournalEntryModel.objects.create(
            ledger=ledger,
            description="Test Entry to Delete",
            posted=False,
        )

        # Add transactions
        cash_account = (
            self.entity.chartofaccountmodel_set.first().accountmodel_set.filter(code="1001").first()
        )
        revenue_account = (
            self.entity.chartofaccountmodel_set.first().accountmodel_set.filter(code="4001").first()
        )

        TransactionModel.objects.create(
            journal_entry=entry,
            account=cash_account,
            amount=Decimal("100.00"),
            tx_type="debit",
        )

        TransactionModel.objects.create(
            journal_entry=entry,
            account=revenue_account,
            amount=Decimal("100.00"),
            tx_type="credit",
        )

        entry_uuid = entry.uuid

        # Delete the entry
        response = self.client.post(
            reverse("accounting:journal_entry_delete", kwargs={"pk": entry_uuid})
        )

        # Should redirect to list view
        self.assertEqual(response.status_code, 302)

        # Verify entry is deleted
        self.assertFalse(
            JournalEntryModel.objects.filter(ledger__entity=self.entity, uuid=entry_uuid).exists()
        )

    def test_journal_entry_delete_posted_prevented(self):
        """Test that deleting a posted journal entry is prevented."""
        # Create a posted journal entry
        from django_ledger.models import JournalEntryModel, TransactionModel

        ledger = self.entity.ledgermodel_set.first()
        entry = JournalEntryModel.objects.create(
            ledger=ledger,
            description="Posted Entry",
            posted=False,
        )

        # Add transactions
        cash_account = (
            self.entity.chartofaccountmodel_set.first().accountmodel_set.filter(code="1001").first()
        )
        revenue_account = (
            self.entity.chartofaccountmodel_set.first().accountmodel_set.filter(code="4001").first()
        )

        TransactionModel.objects.create(
            journal_entry=entry,
            account=cash_account,
            amount=Decimal("100.00"),
            tx_type="debit",
        )

        TransactionModel.objects.create(
            journal_entry=entry,
            account=revenue_account,
            amount=Decimal("100.00"),
            tx_type="credit",
        )

        # Post the entry
        entry.posted = True
        entry.save()

        entry_uuid = entry.uuid

        # Try to delete the posted entry
        response = self.client.post(
            reverse("accounting:journal_entry_delete", kwargs={"pk": entry_uuid})
        )

        # Should redirect with error message
        self.assertEqual(response.status_code, 302)

        # Verify entry still exists
        self.assertTrue(
            JournalEntryModel.objects.filter(ledger__entity=self.entity, uuid=entry_uuid).exists()
        )
