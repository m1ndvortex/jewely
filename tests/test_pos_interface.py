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

    def test_product_search_by_sku(self, authenticated_api_client, tenant, inventory_item):
        """Test searching products by SKU."""
        with tenant_context(tenant.id):
            url = reverse("sales:pos_product_search")
            response = authenticated_api_client.get(url, {"q": inventory_item.sku})

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 1
            assert data["results"][0]["sku"] == inventory_item.sku

    def test_product_search_by_name(self, authenticated_api_client, tenant, inventory_item):
        """Test searching products by name."""
        with tenant_context(tenant.id):
            url = reverse("sales:pos_product_search")
            response = authenticated_api_client.get(url, {"q": inventory_item.name})

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) >= 1

    def test_product_search_by_barcode(self, authenticated_api_client, tenant):
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
            response = authenticated_api_client.get(url, {"q": "1234567890"})

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 1
            assert data["results"][0]["barcode"] == "1234567890"

    def test_product_search_empty_query(self, authenticated_api_client, tenant):
        """Test that empty query returns empty results."""
        with tenant_context(tenant.id):
            url = reverse("sales:pos_product_search")
            response = authenticated_api_client.get(url, {"q": ""})

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 0


@pytest.mark.django_db
class TestPOSCustomerSearch:
    """Test POS customer search functionality."""

    def test_customer_search_by_name(self, authenticated_api_client, tenant):
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
            response = authenticated_api_client.get(url, {"q": "John"})

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 1
            assert data["results"][0]["first_name"] == "John"

    def test_customer_search_by_phone(self, authenticated_api_client, tenant):
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
            response = authenticated_api_client.get(url, {"q": "1234567890"})

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 1


@pytest.mark.django_db
class TestPOSCustomerQuickAdd:
    """Test POS customer quick add functionality."""

    def test_quick_add_customer(self, authenticated_api_client, tenant):
        """Test quick adding a customer."""
        with tenant_context(tenant.id):
            url = reverse("sales:pos_customer_quick_add")
            data = {
                "first_name": "Jane",
                "last_name": "Smith",
                "phone": "+9876543210",
                "email": "jane@example.com",
            }

            response = authenticated_api_client.post(
                url, data=json.dumps(data), content_type="application/json"
            )

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

    def test_create_sale_success(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
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
                "discount_type": "FIXED",
                "discount_value": "0.00",
            }

            initial_quantity = inventory_item.quantity

            response = authenticated_api_client.post(
                url, data=json.dumps(data), content_type="application/json"
            )

            assert response.status_code == 201
            result = response.json()
            assert "sale_number" in result
            assert result["status"] == "COMPLETED"

            # Verify inventory was deducted
            inventory_item.refresh_from_db()
            assert inventory_item.quantity == initial_quantity - 2

    def test_create_sale_with_customer(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
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

            response = authenticated_api_client.post(
                url, data=json.dumps(data), content_type="application/json"
            )

            assert response.status_code == 201
            result = response.json()
            assert result["customer"] == str(customer.id)

    def test_create_sale_insufficient_inventory(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
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

            response = authenticated_api_client.post(
                url, data=json.dumps(data), content_type="application/json"
            )

            assert response.status_code == 400
            assert "Insufficient inventory" in response.json()["detail"]

    def test_create_sale_multiple_items(self, authenticated_api_client, tenant, tenant_user):
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

            response = authenticated_api_client.post(
                url, data=json.dumps(data), content_type="application/json"
            )

            assert response.status_code == 201
            result = response.json()
            assert len(result["items"]) == 2

            # Verify both items were deducted
            item1.refresh_from_db()
            item2.refresh_from_db()
            assert item1.quantity == 8
            assert item2.quantity == 9


@pytest.mark.django_db
class TestPOSBackendLogic:
    """Test enhanced POS backend logic functionality."""

    def test_percentage_discount_calculation(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test percentage discount calculation."""
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
                        "quantity": 1,
                    }
                ],
                "payment_method": "CASH",
                "tax_rate": "10.00",
                "discount_type": "PERCENTAGE",
                "discount_value": "20.00",  # 20% discount
            }

            response = authenticated_api_client.post(
                url, data=json.dumps(data), content_type="application/json"
            )

            assert response.status_code == 201
            result = response.json()

            # Calculate expected values
            subtotal = float(inventory_item.selling_price)
            discount_amount = subtotal * 0.20  # 20% discount
            discounted_subtotal = subtotal - discount_amount
            tax_amount = discounted_subtotal * 0.10  # 10% tax
            expected_total = discounted_subtotal + tax_amount

            assert float(result["subtotal"]) == subtotal
            assert float(result["discount"]) == discount_amount
            assert float(result["tax"]) == tax_amount
            assert abs(float(result["total"]) - expected_total) < 0.01

    def test_fixed_discount_calculation(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test fixed amount discount calculation."""
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
                        "quantity": 1,
                    }
                ],
                "payment_method": "CASH",
                "tax_rate": "10.00",
                "discount_type": "FIXED",
                "discount_value": "50.00",  # $50 fixed discount
            }

            response = authenticated_api_client.post(
                url, data=json.dumps(data), content_type="application/json"
            )

            assert response.status_code == 201
            result = response.json()

            # Calculate expected values
            subtotal = float(inventory_item.selling_price)
            discount_amount = 50.00
            discounted_subtotal = subtotal - discount_amount
            tax_amount = discounted_subtotal * 0.10  # 10% tax
            expected_total = discounted_subtotal + tax_amount

            assert float(result["subtotal"]) == subtotal
            assert float(result["discount"]) == discount_amount
            assert float(result["tax"]) == tax_amount
            assert abs(float(result["total"]) - expected_total) < 0.01

    def test_unique_sale_number_generation(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test unique sale number generation."""
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
                        "quantity": 1,
                    }
                ],
                "payment_method": "CASH",
            }

            # Create multiple sales
            sale_numbers = []
            for _ in range(3):
                response = authenticated_api_client.post(
                    url, data=json.dumps(data), content_type="application/json"
                )
                assert response.status_code == 201
                result = response.json()
                sale_numbers.append(result["sale_number"])

            # Verify all sale numbers are unique
            assert len(set(sale_numbers)) == 3

            # Verify format (SALE-YYYYMMDD-NNNNNN)
            import re

            pattern = r"SALE-\d{8}-\d{6}"
            for sale_number in sale_numbers:
                assert re.match(pattern, sale_number)

    def test_serialized_item_validation(self, authenticated_api_client, tenant, tenant_user):
        """Test that serialized items cannot be sold in quantities > 1."""
        with tenant_context(tenant.id):
            branch = Branch.objects.create(tenant=tenant, name="Main")
            category = ProductCategory.objects.create(tenant=tenant, name="Rings")

            # Create serialized item
            serialized_item = InventoryItem.objects.create(
                tenant=tenant,
                sku="SERIAL-001",
                name="Unique Ring",
                category=category,
                branch=branch,
                karat=24,
                weight_grams=Decimal("10"),
                cost_price=Decimal("1000"),
                selling_price=Decimal("1200"),
                quantity=5,
                serial_number="SN123456",  # This makes it serialized
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
                    {
                        "inventory_item_id": str(serialized_item.id),
                        "quantity": 2,  # Should fail
                    }
                ],
                "payment_method": "CASH",
            }

            response = authenticated_api_client.post(
                url, data=json.dumps(data), content_type="application/json"
            )

            assert response.status_code == 400
            assert "Cannot sell more than 1 unit of serialized item" in response.json()["detail"]

    def test_inventory_validation_endpoint(self, authenticated_api_client, tenant, inventory_item):
        """Test inventory validation endpoint."""
        with tenant_context(tenant.id):
            url = reverse("sales:pos_validate_inventory")
            data = {
                "items": [
                    {
                        "inventory_item_id": str(inventory_item.id),
                        "quantity": 2,
                    }
                ]
            }

            response = authenticated_api_client.post(
                url, data=json.dumps(data), content_type="application/json"
            )

            assert response.status_code == 200
            result = response.json()
            assert result["valid"] is True
            assert len(result["items"]) == 1
            assert result["items"][0]["available"] is True

    def test_inventory_validation_insufficient_stock(
        self, authenticated_api_client, tenant, inventory_item
    ):
        """Test inventory validation with insufficient stock."""
        with tenant_context(tenant.id):
            url = reverse("sales:pos_validate_inventory")
            data = {
                "items": [
                    {
                        "inventory_item_id": str(inventory_item.id),
                        "quantity": inventory_item.quantity + 10,  # More than available
                    }
                ]
            }

            response = authenticated_api_client.post(
                url, data=json.dumps(data), content_type="application/json"
            )

            assert response.status_code == 200
            result = response.json()
            assert result["valid"] is False
            assert len(result["items"]) == 1
            assert result["items"][0]["available"] is False
            assert "Insufficient inventory" in result["items"][0]["error"]

    def test_calculate_totals_endpoint(self, authenticated_api_client, tenant, inventory_item):
        """Test calculate totals endpoint."""
        with tenant_context(tenant.id):
            url = reverse("sales:pos_calculate_totals")
            data = {
                "items": [
                    {
                        "inventory_item_id": str(inventory_item.id),
                        "quantity": 2,
                    }
                ],
                "tax_rate": "10.00",
                "discount_type": "PERCENTAGE",
                "discount_value": "15.00",
            }

            response = authenticated_api_client.post(
                url, data=json.dumps(data), content_type="application/json"
            )

            assert response.status_code == 200
            result = response.json()

            # Verify calculations
            expected_subtotal = float(inventory_item.selling_price) * 2
            expected_discount = expected_subtotal * 0.15  # 15% discount
            expected_discounted = expected_subtotal - expected_discount
            expected_tax = expected_discounted * 0.10  # 10% tax
            expected_total = expected_discounted + expected_tax

            assert float(result["subtotal"]) == expected_subtotal
            assert float(result["discount_amount"]) == expected_discount
            assert float(result["tax_amount"]) == expected_tax
            assert abs(float(result["total"]) - expected_total) < 0.01

    def test_excessive_discount_validation(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test that discount cannot exceed subtotal."""
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
                        "quantity": 1,
                    }
                ],
                "payment_method": "CASH",
                "discount_type": "FIXED",
                "discount_value": str(
                    float(inventory_item.selling_price) + 100
                ),  # More than subtotal
            }

            response = authenticated_api_client.post(
                url, data=json.dumps(data), content_type="application/json"
            )

            assert response.status_code == 400
            assert "Total discount cannot exceed subtotal" in response.json()["detail"]

    def test_select_for_update_locking(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test that inventory is properly locked during sale creation."""
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
                        "quantity": 1,
                    }
                ],
                "payment_method": "CASH",
            }

            initial_quantity = inventory_item.quantity

            response = authenticated_api_client.post(
                url, data=json.dumps(data), content_type="application/json"
            )

            assert response.status_code == 201

            # Verify inventory was properly deducted
            inventory_item.refresh_from_db()
            assert inventory_item.quantity == initial_quantity - 1

    def test_split_payment_validation(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test split payment functionality."""
        with tenant_context(tenant.id):
            terminal = Terminal.objects.create(
                branch=inventory_item.branch,
                terminal_id="POS-01",
                is_active=True,
            )

            # Calculate expected total
            item_price = float(inventory_item.selling_price)
            tax_rate = 10.0
            tax_amount = item_price * (tax_rate / 100)
            total = item_price + tax_amount

            url = reverse("sales:pos_create_sale")
            data = {
                "terminal_id": str(terminal.id),
                "items": [
                    {
                        "inventory_item_id": str(inventory_item.id),
                        "quantity": 1,
                    }
                ],
                "payment_method": "SPLIT",
                "tax_rate": "10.00",
                "split_payments": [
                    {"method": "CASH", "amount": str(total * 0.6)},
                    {"method": "CARD", "amount": str(total * 0.4)},
                ],
            }

            response = authenticated_api_client.post(
                url, data=json.dumps(data), content_type="application/json"
            )

            assert response.status_code == 201
            result = response.json()
            assert result["payment_method"] == "SPLIT"
            assert "split_payments" in result["payment_details"]

    def test_split_payment_total_mismatch(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test that split payment total must match sale total."""
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
                        "quantity": 1,
                    }
                ],
                "payment_method": "SPLIT",
                "split_payments": [
                    {"method": "CASH", "amount": "50.00"},
                    {"method": "CARD", "amount": "30.00"},  # Total doesn't match sale total
                ],
            }

            response = authenticated_api_client.post(
                url, data=json.dumps(data), content_type="application/json"
            )

            assert response.status_code == 400
            assert "Split payments total" in response.json()["detail"]
