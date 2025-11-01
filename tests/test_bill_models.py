"""
Tests for Bill models and tenant isolation.

This module tests the Bill and BillLine models, with particular focus on:
- BillLine.clean() handling None values gracefully
- Tenant isolation and correct tenant_id assignment
- Bill creation flow end-to-end
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

import pytest

from apps.accounting.bill_models import Bill, BillLine
from apps.core.tenant_context import set_tenant_context
from apps.procurement.models import Supplier

User = get_user_model()


@pytest.mark.django_db
class TestBillLineClean:
    """Test BillLine.clean() method handles None values correctly."""

    def test_billline_clean_with_all_values_set(self, tenant_user):
        """Test BillLine.clean() works correctly with all values set."""
        # Create tenant and supplier
        tenant = tenant_user.tenant
        set_tenant_context(tenant.id)

        supplier = Supplier.objects.create(
            tenant=tenant,
            name="Test Supplier",
            email="test@supplier.com",
            phone="1234567890",
            created_by=tenant_user,
        )

        bill = Bill.objects.create(
            tenant=tenant,
            supplier=supplier,
            bill_date="2025-11-01",
            due_date="2025-11-30",
            created_by=tenant_user,
        )

        line = BillLine(
            bill=bill,
            account="1200",
            description="Test item",
            quantity=Decimal("5.00"),
            unit_price=Decimal("100.00"),
            amount=Decimal("500.00"),
        )

        # Should not raise any exception
        line.clean()
        assert True

    def test_billline_clean_with_none_unit_price(self, tenant_user):
        """Test BillLine.clean() handles None unit_price without TypeError."""
        tenant = tenant_user.tenant
        set_tenant_context(tenant.id)

        supplier = Supplier.objects.create(
            tenant=tenant,
            name="Test Supplier",
            email="test@supplier.com",
            phone="1234567890",
            created_by=tenant_user,
        )

        bill = Bill.objects.create(
            tenant=tenant,
            supplier=supplier,
            bill_date="2025-11-01",
            due_date="2025-11-30",
            created_by=tenant_user,
        )

        line = BillLine(
            bill=bill,
            account="1200",
            description="Test item",
            quantity=Decimal("5.00"),
            unit_price=None,  # This was causing TypeError before fix
            amount=Decimal("0.00"),
        )

        # Should not raise TypeError, but may raise ValidationError
        try:
            line.clean()
            # If clean passes, it means it treated None as 0.00
            assert True
        except ValidationError as e:
            # Validation error is acceptable (field required)
            assert "unit_price" in str(e) or "amount" in str(e)
        except TypeError:
            # This should NOT happen after our fix
            pytest.fail("BillLine.clean() raised TypeError with None unit_price - bug not fixed!")

    def test_billline_clean_with_none_quantity(self, tenant_user):
        """Test BillLine.clean() handles None quantity without TypeError."""
        tenant = tenant_user.tenant
        set_tenant_context(tenant.id)

        supplier = Supplier.objects.create(
            tenant=tenant,
            name="Test Supplier",
            email="test@supplier.com",
            phone="1234567890",
            created_by=tenant_user,
        )

        bill = Bill.objects.create(
            tenant=tenant,
            supplier=supplier,
            bill_date="2025-11-01",
            due_date="2025-11-30",
            created_by=tenant_user,
        )

        line = BillLine(
            bill=bill,
            account="1200",
            description="Test item",
            quantity=None,  # This could cause TypeError before fix
            unit_price=Decimal("100.00"),
            amount=Decimal("0.00"),
        )

        # Should not raise TypeError
        try:
            line.clean()
            assert True
        except ValidationError:
            # Validation error is acceptable
            assert True
        except TypeError:
            pytest.fail("BillLine.clean() raised TypeError with None quantity - bug not fixed!")

    def test_billline_clean_with_mismatched_amount(self, tenant_user):
        """Test BillLine.clean() raises ValidationError for mismatched amounts."""
        tenant = tenant_user.tenant
        set_tenant_context(tenant.id)

        supplier = Supplier.objects.create(
            tenant=tenant,
            name="Test Supplier",
            email="test@supplier.com",
            phone="1234567890",
            created_by=tenant_user,
        )

        bill = Bill.objects.create(
            tenant=tenant,
            supplier=supplier,
            bill_date="2025-11-01",
            due_date="2025-11-30",
            created_by=tenant_user,
        )

        line = BillLine(
            bill=bill,
            account="1200",
            description="Test item",
            quantity=Decimal("5.00"),
            unit_price=Decimal("100.00"),
            amount=Decimal("400.00"),  # Should be 500.00
        )

        # Should raise ValidationError about amount mismatch
        with pytest.raises(ValidationError) as exc_info:
            line.clean()
        assert "amount" in str(exc_info.value).lower()

    def test_billline_save_calculates_amount(self, tenant_user):
        """Test BillLine.save() auto-calculates amount from quantity * unit_price."""
        tenant = tenant_user.tenant
        set_tenant_context(tenant.id)

        supplier = Supplier.objects.create(
            tenant=tenant,
            name="Test Supplier",
            email="test@supplier.com",
            phone="1234567890",
            created_by=tenant_user,
        )

        bill = Bill.objects.create(
            tenant=tenant,
            supplier=supplier,
            bill_date="2025-11-01",
            due_date="2025-11-30",
            created_by=tenant_user,
        )

        line = BillLine(
            bill=bill,
            account="1200",
            description="Test item",
            quantity=Decimal("5.00"),
            unit_price=Decimal("100.00"),
            amount=Decimal("0.00"),  # Will be auto-calculated
        )

        line.save()

        # Amount should be auto-calculated to 500.00
        assert line.amount == Decimal("500.00")

    def test_billline_save_handles_none_values(self, tenant_user):
        """Test BillLine.save() handles None values by treating them as 0.00 for calculation.

        Note: Database has NOT NULL constraints on quantity/unit_price, so this will
        raise IntegrityError when trying to save. The important part is that our
        save() method doesn't raise TypeError during the calculation step.
        """
        from django.db.utils import IntegrityError

        tenant = tenant_user.tenant
        set_tenant_context(tenant.id)

        supplier = Supplier.objects.create(
            tenant=tenant,
            name="Test Supplier",
            email="test@supplier.com",
            phone="1234567890",
            created_by=tenant_user,
        )

        bill = Bill.objects.create(
            tenant=tenant,
            supplier=supplier,
            bill_date="2025-11-01",
            due_date="2025-11-30",
            created_by=tenant_user,
        )

        line = BillLine(
            bill=bill,
            account="1200",
            description="Test item",
            quantity=None,
            unit_price=None,
            amount=Decimal("0.00"),
        )

        # The save() method should handle None without TypeError during calculation,
        # but database constraints will prevent actual saving
        try:
            line.save()
            # If it saves somehow, verify amount calculation worked
            assert line.amount == Decimal("0.00")
        except IntegrityError:
            # Expected due to NOT NULL constraints - this is acceptable
            # The important thing is we didn't get TypeError during calculation
            assert True


@pytest.mark.django_db
class TestBillTenantIsolation:
    """Test that bills are properly isolated by tenant."""

    def test_bill_created_with_correct_tenant(self, tenant_user):
        """Test that bills are created with the correct tenant_id."""
        tenant = tenant_user.tenant
        set_tenant_context(tenant.id)

        supplier = Supplier.objects.create(
            tenant=tenant,
            name="Test Supplier",
            email="test@supplier.com",
            phone="1234567890",
            created_by=tenant_user,
        )

        bill = Bill.objects.create(
            tenant=tenant,
            supplier=supplier,
            bill_date="2025-11-01",
            due_date="2025-11-30",
            created_by=tenant_user,
        )

        # Verify tenant_id matches
        assert bill.tenant.id == tenant.id
        assert bill.tenant.id == tenant_user.tenant.id

    def test_billline_tenant_property(self, tenant_user):
        """Test that BillLine.tenant property returns parent bill's tenant."""
        tenant = tenant_user.tenant
        set_tenant_context(tenant.id)

        supplier = Supplier.objects.create(
            tenant=tenant,
            name="Test Supplier",
            email="test@supplier.com",
            phone="1234567890",
            created_by=tenant_user,
        )

        bill = Bill.objects.create(
            tenant=tenant,
            supplier=supplier,
            bill_date="2025-11-01",
            due_date="2025-11-30",
            created_by=tenant_user,
        )

        line = BillLine.objects.create(
            bill=bill,
            account="1200",
            description="Test item",
            quantity=Decimal("5.00"),
            unit_price=Decimal("100.00"),
            amount=Decimal("500.00"),
        )

        # Verify line.tenant returns bill's tenant
        assert line.tenant == bill.tenant
        assert line.tenant.id == tenant.id


@pytest.mark.django_db
class TestBillValidation:
    """Test Bill model validation."""

    def test_bill_due_date_before_bill_date_fails(self, tenant_user):
        """Test that bill with due_date before bill_date fails validation."""
        tenant = tenant_user.tenant
        set_tenant_context(tenant.id)

        supplier = Supplier.objects.create(
            tenant=tenant,
            name="Test Supplier",
            email="test@supplier.com",
            phone="1234567890",
            created_by=tenant_user,
        )

        bill = Bill(
            tenant=tenant,
            supplier=supplier,
            bill_date="2025-11-30",
            due_date="2025-11-01",  # Before bill_date
            created_by=tenant_user,
        )

        with pytest.raises(ValidationError) as exc_info:
            bill.clean()
        assert "due_date" in str(exc_info.value).lower()

    def test_bill_total_mismatch_fails(self, tenant_user):
        """Test that bill with total != subtotal + tax fails validation."""
        tenant = tenant_user.tenant
        set_tenant_context(tenant.id)

        supplier = Supplier.objects.create(
            tenant=tenant,
            name="Test Supplier",
            email="test@supplier.com",
            phone="1234567890",
            created_by=tenant_user,
        )

        bill = Bill(
            tenant=tenant,
            supplier=supplier,
            bill_date="2025-11-01",
            due_date="2025-11-30",
            subtotal=Decimal("1000.00"),
            tax=Decimal("100.00"),
            total=Decimal("1050.00"),  # Should be 1100.00
            created_by=tenant_user,
        )

        with pytest.raises(ValidationError) as exc_info:
            bill.clean()
        assert "total" in str(exc_info.value).lower()

    def test_bill_generates_unique_bill_number(self, tenant_user):
        """Test that bills auto-generate unique bill numbers per tenant."""
        tenant = tenant_user.tenant
        set_tenant_context(tenant.id)

        supplier = Supplier.objects.create(
            tenant=tenant,
            name="Test Supplier",
            email="test@supplier.com",
            phone="1234567890",
            created_by=tenant_user,
        )

        bill1 = Bill.objects.create(
            tenant=tenant,
            supplier=supplier,
            bill_date="2025-11-01",
            due_date="2025-11-30",
            created_by=tenant_user,
        )

        bill2 = Bill.objects.create(
            tenant=tenant,
            supplier=supplier,
            bill_date="2025-11-01",
            due_date="2025-11-30",
            created_by=tenant_user,
        )

        # Both should have bill numbers
        assert bill1.bill_number
        assert bill2.bill_number
        # They should be different
        assert bill1.bill_number != bill2.bill_number
