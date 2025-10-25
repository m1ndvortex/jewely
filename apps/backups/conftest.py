"""
Pytest configuration and fixtures for backup tests.
"""

import uuid

import pytest

from apps.core.models import Tenant
from apps.core.tenant_context import bypass_rls, tenant_context


@pytest.fixture
def tenant():
    """
    Fixture for creating a test tenant.
    Uses RLS bypass to create tenant (only platform admins can create tenants).
    """
    unique_id = str(uuid.uuid4())[:8]
    slug = f"test-shop-{unique_id}"

    with bypass_rls():
        tenant = Tenant.objects.create(company_name="Test Jewelry Shop", slug=slug, status="ACTIVE")
    return tenant


@pytest.fixture
def platform_admin(django_user_model):
    """
    Fixture for creating a platform administrator user.

    Platform admins have no tenant and can manage all tenants.
    """
    unique_id = str(uuid.uuid4())[:8]
    username = f"admin-{unique_id}"
    email = f"admin-{unique_id}@example.com"

    with bypass_rls():
        user = django_user_model.objects.create_user(
            username=username,
            email=email,
            password="adminpass123",
            tenant=None,  # Platform admins have no tenant
            role="PLATFORM_ADMIN",
        )
    return user


@pytest.fixture
def branch(tenant):
    """
    Fixture for creating a test branch.
    """
    from apps.core.models import Branch

    with tenant_context(tenant.id):
        branch = Branch.objects.create(
            tenant=tenant,
            name="Main Branch",
            address="123 Main St",
            phone="555-0100",
        )
    return branch


@pytest.fixture
def inventory_item(tenant, branch):
    """
    Fixture for creating a test inventory item.
    """
    from decimal import Decimal

    from apps.inventory.models import InventoryItem, ProductCategory

    with tenant_context(tenant.id):
        category = ProductCategory.objects.create(
            tenant=tenant,
            name="Test Category",
        )

        item = InventoryItem.objects.create(
            tenant=tenant,
            sku="TEST-001",
            name="Test Gold Ring",
            category=category,
            branch=branch,
            karat=24,
            weight_grams=Decimal("10.5"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=10,
        )
    return item
