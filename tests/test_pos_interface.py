"""
Tests for POS interface views.

Tests the POS interface functionality including:
- Product search with barcode support
- Cart management
- Customer selection and quick add
- Payment method selection
- Sale creation

Implements testing for Requirement 11: Point of Sale (POS) System
"""

import json
from decimal import Decimal

from django.urls import reverse

import pytest

from apps.core.models import Branch
from apps.core.tenant_context import tenant_context
from apps.inventory.models import InventoryItem, ProductCategory
from apps.sales.models import Customer, Terminal


@pytest.mark.django_db
class TestPOSInterface:
    """Test POS interface views."""

    def test_pos_interface_requires_authentication(self, client):
        """Test that POS interface requires authentication."""
        response = client.get(reverse("sales:pos_interface"))
        assert response.status_code == 302  # Redirect to login

    def test_pos_interface_renders(self, client, tenant_user):
        """Test that POS interface renders for authenticated user."""
        client.force_login(tenant_user)
        response = client.get(reverse("sales:pos_interface"))
        assert response.status_code == 200
        assert b"Point of Sale" in response.content


@pytest.mark.django_db
class TestPOSProductSearch:
    """Test POS product search functionality."""

    def test_product_search_by_sku(self, api_client, tenant, inventory_item):
        """Test searching products by SKU."""
        with tenant_context(tenant.id):
            url = reverse("sales:pos_product_search")
            response = api_client.get(url, {"q": inventory_item.sku})

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 1
            assert data["results"][0]["sku"] == inventory_item.sku

    def test_product_search_by_name(self, api_client, tenant, inventory_item):
        """Test searching products by name."""
        with tenant_context(tenant.id):
            url = reverse("sales:pos_product_search")
            response = api_client.get(url, {"q": inventory_item.name})

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) >= 1

    def test_product_search_by_barcode(self, api_client, tenant):
        """Test searching products by barcode (exact match)."""
        with tenant_context(tenant.id):
            # Create item with barcode
            branch = Branch.objects.create(tenant=tenant, name="Main")
            category = ProductCategory.objects.create(tenant=tenant, name="Rings")
            InventoryItem.objects.create(
                tenant=tenant,
                sku="TEST-001",
                name="Test Ring",
                category=category,
                branch=branch,
                karat=24,
                weight_grams=Decimal("10.5"),
                cost_price=Decimal("1000"),
                selling_price=Decimal("1200"),
                quantity=5,
                barcode="1234567890",
            )

            url = reverse("sales:pos_product_search")
            response = api_client.get(url, {"q": "1234567890"})

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 1
            assert data["results"][0]["barcode"] == "1234567890"

    def test_product_search_empty_query(self, api_client, tenant):
        """Test that empty query returns empty results."""
        with tenant_context(tenant.id):
            url = reverse("sales:pos_product_search")
            response = api_client.get(url, {"q": ""})

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 0


@pytest.mark.django_db
class TestPOSCustomerSearch:
    """Test POS customer search functionality."""

    def test_customer_search_by_name(self, api_client, tenant):
        """Test searching customers by name."""
        with tenant_context(tenant.id):
            Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-001",
                first_name="John",
                last_name="Doe",
                phone="+1234567890",
            )

            url = reverse("sales:pos_customer_search")
            response = api_client.get(url, {"q": "John"})

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 1
            assert data["results"][0]["first_name"] == "John"

    def test_customer_search_by_phone(self, api_client, tenant):
        """Test searching customers by phone."""
        with tenant_context(tenant.id):
            Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-001",
                first_name="John",
                last_name="Doe",
                phone="+1234567890",
            )

            url = reverse("sales:pos_customer_search")
            response = api_client.get(url, {"q": "1234567890"})

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 1


@pytest.mark.django_db
class TestPOSCustomerQuickAdd:
    """Test POS customer quick add functionality."""

    def test_quick_add_customer(self, api_client, tenant):
        """Test quick adding a customer."""
        with tenant_context(tenant.id):
            url = reverse("sales:pos_customer_quick_add")
            data = {
                "first_name": "Jane",
                "last_name": "Smith",
                "phone": "+9876543210",
                "email": "jane@example.com",
            }

            response = api_client.post(url, data=json.dumps(data), content_type="application/json")

            assert response.status_code == 201
            result = response.json()
            assert result["first_name"] == "Jane"
            assert result["last_name"] == "Smith"
            assert "customer_number" in result

            # Verify customer was created
            customer = Customer.objects.get(phone="+9876543210")
            assert customer.first_name == "Jane"


@pytest.mark.django_db
class TestPOSSaleCreation:
    """Test POS sale creation functionality."""

    def test_create_sale_success(self, api_client, tenant, tenant_user, inventory_item):
        """Test creating a sale through POS."""
        with tenant_context(tenant.id):
            # Create terminal
            terminal = Terminal.objects.create(
                branch=inventory_item.branch,
                terminal_id="POS-01",
                is_active=True,
            )

            url = reverse("sales:pos_create_sale")
            data = {
                "terminal_id": str(terminal.id),
                "items": [
                    {
                        "inventory_item_id": str(inventory_item.id),
                        "quantity": 2,
                    }
                ],
                "payment_method": "CASH",
                "tax_rate": "10.00",
                "discount": "0.00",
            }

            initial_quantity = inventory_item.quantity

            response = api_client.post(url, data=json.dumps(data), content_type="application/json")

            assert response.status_code == 201
            result = response.json()
            assert "sale_number" in result
            assert result["status"] == "COMPLETED"

            # Verify inventory was deducted
            inventory_item.refresh_from_db()
            assert inventory_item.quantity == initial_quantity - 2

    def test_create_sale_with_customer(self, api_client, tenant, tenant_user, inventory_item):
        """Test creating a sale with customer."""
        with tenant_context(tenant.id):
            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-001",
                first_name="John",
                last_name="Doe",
                phone="+1234567890",
            )

            terminal = Terminal.objects.create(
                branch=inventory_item.branch,
                terminal_id="POS-01",
                is_active=True,
            )

            url = reverse("sales:pos_create_sale")
            data = {
                "customer_id": str(customer.id),
                "terminal_id": str(terminal.id),
                "items": [
                    {
                        "inventory_item_id": str(inventory_item.id),
                        "quantity": 1,
                    }
                ],
                "payment_method": "CARD",
                "tax_rate": "10.00",
            }

            response = api_client.post(url, data=json.dumps(data), content_type="application/json")

            assert response.status_code == 201
            result = response.json()
            assert result["customer"] == str(customer.id)

    def test_create_sale_insufficient_inventory(
        self, api_client, tenant, tenant_user, inventory_item
    ):
        """Test that sale fails with insufficient inventory."""
        with tenant_context(tenant.id):
            terminal = Terminal.objects.create(
                branch=inventory_item.branch,
                terminal_id="POS-01",
                is_active=True,
            )

            url = reverse("sales:pos_create_sale")
            data = {
                "terminal_id": str(terminal.id),
                "items": [
                    {
                        "inventory_item_id": str(inventory_item.id),
                        "quantity": inventory_item.quantity + 10,  # More than available
                    }
                ],
                "payment_method": "CASH",
            }

            response = api_client.post(url, data=json.dumps(data), content_type="application/json")

            assert response.status_code == 400
            assert "Insufficient inventory" in response.json()["detail"]

    def test_create_sale_multiple_items(self, api_client, tenant, tenant_user):
        """Test creating a sale with multiple items."""
        with tenant_context(tenant.id):
            branch = Branch.objects.create(tenant=tenant, name="Main")
            category = ProductCategory.objects.create(tenant=tenant, name="Rings")

            item1 = InventoryItem.objects.create(
                tenant=tenant,
                sku="ITEM-001",
                name="Gold Ring",
                category=category,
                branch=branch,
                karat=24,
                weight_grams=Decimal("10"),
                cost_price=Decimal("1000"),
                selling_price=Decimal("1200"),
                quantity=10,
            )

            item2 = InventoryItem.objects.create(
                tenant=tenant,
                sku="ITEM-002",
                name="Silver Ring",
                category=category,
                branch=branch,
                karat=18,
                weight_grams=Decimal("8"),
                cost_price=Decimal("500"),
                selling_price=Decimal("600"),
                quantity=10,
            )

            terminal = Terminal.objects.create(
                branch=branch,
                terminal_id="POS-01",
                is_active=True,
            )

            url = reverse("sales:pos_create_sale")
            data = {
                "terminal_id": str(terminal.id),
                "items": [
                    {"inventory_item_id": str(item1.id), "quantity": 2},
                    {"inventory_item_id": str(item2.id), "quantity": 1},
                ],
                "payment_method": "CASH",
                "tax_rate": "10.00",
            }

            response = api_client.post(url, data=json.dumps(data), content_type="application/json")

            assert response.status_code == 201
            result = response.json()
            assert len(result["items"]) == 2

            # Verify both items were deducted
            item1.refresh_from_db()
            item2.refresh_from_db()
            assert item1.quantity == 8
            assert item2.quantity == 9
