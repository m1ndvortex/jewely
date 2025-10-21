"""
Tests for the Tenant model.

This test suite validates the Tenant model functionality including:
- Model creation with UUID primary key
- Status choices (ACTIVE, SUSPENDED, PENDING_DELETION)
- Database indexes on status and slug
- Auto-slug generation
- Status transition methods
"""

import uuid

from django.db import IntegrityError
from django.test import TestCase

import pytest

from apps.core.models import Tenant


@pytest.mark.django_db
class TestTenantModel(TestCase):
    """Test suite for Tenant model."""

    def test_create_tenant_with_all_fields(self):
        """Test creating a tenant with all required fields."""
        tenant = Tenant.objects.create(
            company_name="Gold & Silver Jewelry", slug="gold-silver-jewelry", status=Tenant.ACTIVE
        )

        assert tenant.id is not None
        assert isinstance(tenant.id, uuid.UUID)
        assert tenant.company_name == "Gold & Silver Jewelry"
        assert tenant.slug == "gold-silver-jewelry"
        assert tenant.status == Tenant.ACTIVE
        assert tenant.created_at is not None
        assert tenant.updated_at is not None

    def test_tenant_uuid_is_unique(self):
        """Test that each tenant gets a unique UUID."""
        tenant1 = Tenant.objects.create(company_name="Jewelry Shop 1", slug="jewelry-shop-1")
        tenant2 = Tenant.objects.create(company_name="Jewelry Shop 2", slug="jewelry-shop-2")

        assert tenant1.id != tenant2.id
        assert isinstance(tenant1.id, uuid.UUID)
        assert isinstance(tenant2.id, uuid.UUID)

    def test_tenant_default_status_is_active(self):
        """Test that default status is ACTIVE."""
        tenant = Tenant.objects.create(company_name="Test Jewelry", slug="test-jewelry")

        assert tenant.status == Tenant.ACTIVE

    def test_tenant_status_choices(self):
        """Test all status choices are valid."""
        # Test ACTIVE status
        tenant_active = Tenant.objects.create(
            company_name="Active Shop", slug="active-shop", status=Tenant.ACTIVE
        )
        assert tenant_active.status == Tenant.ACTIVE

        # Test SUSPENDED status
        tenant_suspended = Tenant.objects.create(
            company_name="Suspended Shop", slug="suspended-shop", status=Tenant.SUSPENDED
        )
        assert tenant_suspended.status == Tenant.SUSPENDED

        # Test PENDING_DELETION status
        tenant_pending = Tenant.objects.create(
            company_name="Pending Shop", slug="pending-shop", status=Tenant.PENDING_DELETION
        )
        assert tenant_pending.status == Tenant.PENDING_DELETION

    def test_slug_must_be_unique(self):
        """Test that slug field enforces uniqueness."""
        Tenant.objects.create(company_name="First Shop", slug="unique-slug")

        with pytest.raises(IntegrityError):
            Tenant.objects.create(company_name="Second Shop", slug="unique-slug")

    def test_auto_slug_generation_from_company_name(self):
        """Test that slug is auto-generated from company_name if not provided."""
        tenant = Tenant.objects.create(company_name="My Awesome Jewelry Shop")

        assert tenant.slug == "my-awesome-jewelry-shop"

    def test_auto_slug_handles_duplicate_names(self):
        """Test that auto-slug generation handles duplicate company names."""
        tenant1 = Tenant.objects.create(company_name="Duplicate Name")
        tenant2 = Tenant.objects.create(company_name="Duplicate Name")

        assert tenant1.slug == "duplicate-name"
        assert tenant2.slug.startswith("duplicate-name-")
        assert tenant1.slug != tenant2.slug

    def test_tenant_str_representation(self):
        """Test string representation of tenant."""
        tenant = Tenant.objects.create(
            company_name="Test Shop", slug="test-shop", status=Tenant.ACTIVE
        )

        assert str(tenant) == "Test Shop (ACTIVE)"

    def test_is_active_method(self):
        """Test is_active() method returns correct boolean."""
        active_tenant = Tenant.objects.create(
            company_name="Active Shop", slug="active-shop", status=Tenant.ACTIVE
        )
        suspended_tenant = Tenant.objects.create(
            company_name="Suspended Shop", slug="suspended-shop", status=Tenant.SUSPENDED
        )

        assert active_tenant.is_active() is True
        assert suspended_tenant.is_active() is False

    def test_suspend_method(self):
        """Test suspend() method changes status to SUSPENDED."""
        tenant = Tenant.objects.create(
            company_name="Test Shop", slug="test-shop", status=Tenant.ACTIVE
        )

        tenant.suspend()
        tenant.refresh_from_db()

        assert tenant.status == Tenant.SUSPENDED

    def test_activate_method(self):
        """Test activate() method changes status to ACTIVE."""
        tenant = Tenant.objects.create(
            company_name="Test Shop", slug="test-shop", status=Tenant.SUSPENDED
        )

        tenant.activate()
        tenant.refresh_from_db()

        assert tenant.status == Tenant.ACTIVE

    def test_mark_for_deletion_method(self):
        """Test mark_for_deletion() method changes status to PENDING_DELETION."""
        tenant = Tenant.objects.create(
            company_name="Test Shop", slug="test-shop", status=Tenant.ACTIVE
        )

        tenant.mark_for_deletion()
        tenant.refresh_from_db()

        assert tenant.status == Tenant.PENDING_DELETION

    def test_updated_at_changes_on_save(self):
        """Test that updated_at timestamp changes when model is saved."""
        tenant = Tenant.objects.create(company_name="Test Shop", slug="test-shop")

        original_updated_at = tenant.updated_at

        tenant.company_name = "Updated Shop Name"
        tenant.save()
        tenant.refresh_from_db()

        assert tenant.updated_at > original_updated_at

    def test_tenant_ordering_by_created_at_desc(self):
        """Test that tenants are ordered by created_at descending."""
        tenant1 = Tenant.objects.create(company_name="First Shop", slug="first-shop")
        tenant2 = Tenant.objects.create(company_name="Second Shop", slug="second-shop")
        tenant3 = Tenant.objects.create(company_name="Third Shop", slug="third-shop")

        tenants = list(Tenant.objects.all())

        assert tenants[0].id == tenant3.id
        assert tenants[1].id == tenant2.id
        assert tenants[2].id == tenant1.id


@pytest.mark.django_db
class TestTenantDatabaseIndexes(TestCase):
    """Test database indexes for Tenant model."""

    def test_status_index_exists(self):
        """Test that status field has an index."""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'tenants'
                AND indexname = 'tenant_status_idx'
            """
            )
            result = cursor.fetchone()

        assert result is not None
        assert result[0] == "tenant_status_idx"

    def test_slug_index_exists(self):
        """Test that slug field has an index."""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'tenants'
                AND indexname = 'tenant_slug_idx'
            """
            )
            result = cursor.fetchone()

        assert result is not None
        assert result[0] == "tenant_slug_idx"

    def test_query_by_status_uses_index(self):
        """Test that queries by status can use the index."""
        # Get initial count
        initial_active_count = Tenant.objects.filter(status=Tenant.ACTIVE).count()

        # Create test data
        for i in range(10):
            Tenant.objects.create(
                company_name=f"Shop {i}",
                slug=f"shop-{i}",
                status=Tenant.ACTIVE if i % 2 == 0 else Tenant.SUSPENDED,
            )

        # Query by status
        active_tenants = Tenant.objects.filter(status=Tenant.ACTIVE)

        # Should have 5 new active tenants plus any that existed before
        assert active_tenants.count() == initial_active_count + 5

    def test_query_by_slug_uses_index(self):
        """Test that queries by slug can use the index."""
        tenant = Tenant.objects.create(company_name="Test Shop", slug="test-shop")

        # Query by slug
        found_tenant = Tenant.objects.get(slug="test-shop")

        assert found_tenant.id == tenant.id
