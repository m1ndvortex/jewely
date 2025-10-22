"""
Tests for POS offline functionality.

Implements Requirement 35: Offline POS mode testing
- Test offline transaction storage
- Test sync validation and conflict resolution
- Test offline mode indicators
"""

from decimal import Decimal

from django.urls import reverse

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.tenant_context import tenant_context
from apps.inventory.models import InventoryItem, ProductCategory
from apps.sales.models import Terminal


@pytest.mark.django_db
def test_offline_sync_validation_success(tenant, tenant_user, branch):
    """Test offline sync validation with available inventory."""
    # Create terminal and inventory items
    with tenant_context(tenant.id):
        Terminal.objects.create(branch=branch, terminal_id="TERM001", is_active=True)

        category = ProductCategory.objects.create(tenant=tenant, name="Rings")

        inventory_item = InventoryItem.objects.create(
            tenant=tenant,
            sku="RING001",
            name="Gold Ring",
            category=category,
            karat=18,
            weight_grams=Decimal("5.5"),
            cost_price=Decimal("200.00"),
            selling_price=Decimal("300.00"),
            quantity=10,
            branch=branch,
        )

    # Set up API client
    client = APIClient()
    client.force_authenticate(user=tenant_user)

    with tenant_context(tenant.id):
        url = reverse("sales:pos_offline_sync_validation")

        data = {
            "transactions": [
                {
                    "id": "offline_123",
                    "items": [{"inventory_item_id": str(inventory_item.id), "quantity": 2}],
                }
            ]
        }

        response = client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK

        result = response.json()
        assert "validation_results" in result

        validation_result = result["validation_results"][0]
        assert validation_result["transaction_id"] == "offline_123"
        assert validation_result["valid"] is True
        assert len(validation_result["conflicts"]) == 0


@pytest.mark.django_db
def test_offline_sync_validation_insufficient_inventory(tenant, tenant_user, branch):
    """Test offline sync validation with insufficient inventory."""
    # Create terminal and inventory items
    with tenant_context(tenant.id):
        Terminal.objects.create(branch=branch, terminal_id="TERM001", is_active=True)

        category = ProductCategory.objects.create(tenant=tenant, name="Rings")

        inventory_item = InventoryItem.objects.create(
            tenant=tenant,
            sku="RING002",
            name="Silver Ring",
            category=category,
            karat=0,
            weight_grams=Decimal("3.0"),
            cost_price=Decimal("50.00"),
            selling_price=Decimal("80.00"),
            quantity=2,  # Low stock for conflict testing
            branch=branch,
        )

    # Set up API client
    client = APIClient()
    client.force_authenticate(user=tenant_user)

    with tenant_context(tenant.id):
        url = reverse("sales:pos_offline_sync_validation")

        data = {
            "transactions": [
                {
                    "id": "offline_456",
                    "items": [
                        {
                            "inventory_item_id": str(inventory_item.id),
                            "quantity": 5,  # More than available (2)
                        }
                    ],
                }
            ]
        }

        response = client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK

        result = response.json()
        validation_result = result["validation_results"][0]

        assert validation_result["transaction_id"] == "offline_456"
        assert validation_result["valid"] is False
        assert len(validation_result["conflicts"]) == 1

        conflict = validation_result["conflicts"][0]
        assert conflict["inventory_item_id"] == str(inventory_item.id)
        assert conflict["requested_quantity"] == 5
        assert conflict["available_quantity"] == 2
        assert conflict["conflict_type"] == "insufficient_inventory"


@pytest.mark.django_db
def test_offline_sync_validation_empty_transactions(tenant, tenant_user):
    """Test offline sync validation with empty transactions list."""
    # Set up API client
    client = APIClient()
    client.force_authenticate(user=tenant_user)

    with tenant_context(tenant.id):
        url = reverse("sales:pos_offline_sync_validation")

        data = {"transactions": []}

        response = client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Transactions list is required" in response.json()["detail"]


@pytest.mark.django_db
def test_pos_favorite_products(tenant, tenant_user, branch):
    """Test favorite products endpoint."""
    # Set up API client
    client = APIClient()
    client.force_authenticate(user=tenant_user)

    with tenant_context(tenant.id):
        url = reverse("sales:pos_favorite_products")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK

        result = response.json()
        assert "results" in result
        # Should return empty list if no sales history
        assert isinstance(result["results"], list)


@pytest.mark.django_db
def test_pos_recent_transactions(tenant, tenant_user, branch):
    """Test recent transactions endpoint."""
    # Set up API client
    client = APIClient()
    client.force_authenticate(user=tenant_user)

    with tenant_context(tenant.id):
        url = reverse("sales:pos_recent_transactions")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK

        result = response.json()
        assert "results" in result
        # Should return empty list if no completed sales
        assert isinstance(result["results"], list)


@pytest.mark.django_db
def test_pos_interface_loads_offline_scripts(tenant, tenant_user):
    """Test that POS interface loads offline functionality scripts."""
    from django.test import Client

    client = Client()
    client.force_login(tenant_user)

    with tenant_context(tenant.id):
        url = reverse("sales:pos_interface")
        response = client.get(url)

        assert response.status_code == 200

        # Check that offline scripts are included
        content = response.content.decode()
        assert "pos-indexeddb.js" in content
        assert "pos-offline.js" in content
        assert "POSOfflineManager" in content

        # Check that offline status indicators are present
        assert "isOnline" in content
        assert "pendingTransactions" in content
        assert "manualSync" in content

        # Check that favorite products functionality is present
        assert "favoriteProducts" in content
        assert "recentTransactions" in content
