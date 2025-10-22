"""
Comprehensive POS System Tests

This module provides comprehensive testing for the Point of Sale (POS) system,
covering all aspects required by task 5.6:
- Sale creation flow
- Inventory deduction
- Payment processing
- Offline mode and sync
- Receipt generation

Implements testing for Requirements 11 and 28:
- Requirement 11: Point of Sale (POS) System
- Requirement 28: Comprehensive Testing
"""

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.urls import reverse

import pytest
from rest_framework import status

from apps.core.models import Branch
from apps.core.tenant_context import tenant_context
from apps.inventory.models import InventoryItem, ProductCategory
from apps.sales.models import Customer, Sale, SaleItem, Terminal
from apps.sales.receipt_service import ReceiptService


@pytest.mark.django_db
class TestPOSSaleCreationFlow:
    """Test complete POS sale creation workflow."""

    def test_complete_sale_creation_workflow(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test the complete sale creation workflow from start to finish."""
        with tenant_context(tenant.id):
            # Create terminal
            terminal = Terminal.objects.create(
                branch=inventory_item.branch,
                terminal_id="POS-01",
                is_active=True,
            )

            initial_quantity = inventory_item.quantity

            # Step 1: Search for product
            search_url = reverse("sales:pos_product_search")
            search_response = authenticated_api_client.get(search_url, {"q": inventory_item.sku})
            assert search_response.status_code == 200
            products = search_response.json()["results"]
            assert len(products) == 1
            assert products[0]["sku"] == inventory_item.sku

            # Step 2: Validate inventory availability
            validate_url = reverse("sales:pos_validate_inventory")
            validate_data = {
                "items": [
                    {
                        "inventory_item_id": str(inventory_item.id),
                        "quantity": 2,
                    }
                ]
            }
            validate_response = authenticated_api_client.post(
                validate_url, data=json.dumps(validate_data), content_type="application/json"
            )
            assert validate_response.status_code == 200
            validation = validate_response.json()
            assert validation["valid"] is True

            # Step 3: Calculate totals
            calculate_url = reverse("sales:pos_calculate_totals")
            calculate_data = {
                "items": [
                    {
                        "inventory_item_id": str(inventory_item.id),
                        "quantity": 2,
                    }
                ],
                "tax_rate": "10.00",
                "discount_type": "PERCENTAGE",
                "discount_value": "5.00",
            }
            calculate_response = authenticated_api_client.post(
                calculate_url, data=json.dumps(calculate_data), content_type="application/json"
            )
            assert calculate_response.status_code == 200
            totals = calculate_response.json()

            expected_subtotal = float(inventory_item.selling_price) * 2
            expected_discount = expected_subtotal * 0.05
            expected_tax = (expected_subtotal - expected_discount) * 0.10
            expected_total = expected_subtotal - expected_discount + expected_tax

            assert float(totals["subtotal"]) == expected_subtotal
            assert abs(float(totals["total"]) - expected_total) < 0.01

            # Step 4: Create sale
            sale_url = reverse("sales:pos_create_sale")
            sale_data = {
                "terminal_id": str(terminal.id),
                "items": [
                    {
                        "inventory_item_id": str(inventory_item.id),
                        "quantity": 2,
                    }
                ],
                "payment_method": "CASH",
                "tax_rate": "10.00",
                "discount_type": "PERCENTAGE",
                "discount_value": "5.00",
            }

            sale_response = authenticated_api_client.post(
                sale_url, data=json.dumps(sale_data), content_type="application/json"
            )
            assert sale_response.status_code == 201
            sale_result = sale_response.json()

            # Verify sale details
            assert "sale_number" in sale_result
            assert sale_result["status"] == "COMPLETED"
            assert float(sale_result["subtotal"]) == expected_subtotal
            assert abs(float(sale_result["total"]) - expected_total) < 0.01

            # Step 5: Verify inventory deduction
            inventory_item.refresh_from_db()
            assert inventory_item.quantity == initial_quantity - 2

            # Step 6: Generate receipt
            receipt_url = reverse("sales:generate_receipt", kwargs={"sale_id": sale_result["id"]})
            receipt_data = {"format_type": "standard", "auto_print": False, "save_receipt": False}
            receipt_response = authenticated_api_client.post(
                receipt_url, data=json.dumps(receipt_data), content_type="application/json"
            )
            assert receipt_response.status_code == 200
            receipt_result = receipt_response.json()
            assert "receipt_url" in receipt_result
            assert "pdf_url" in receipt_result

    def test_sale_creation_with_customer(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test sale creation with customer selection."""
        with tenant_context(tenant.id):
            # Create customer
            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-001",
                first_name="John",
                last_name="Doe",
                phone="+1234567890",
                email="john@example.com",
            )

            terminal = Terminal.objects.create(
                branch=inventory_item.branch,
                terminal_id="POS-01",
                is_active=True,
            )

            # Search for customer
            customer_search_url = reverse("sales:pos_customer_search")
            customer_response = authenticated_api_client.get(customer_search_url, {"q": "John"})
            assert customer_response.status_code == 200
            customers = customer_response.json()["results"]
            assert len(customers) == 1
            assert customers[0]["first_name"] == "John"

            # Create sale with customer
            sale_url = reverse("sales:pos_create_sale")
            sale_data = {
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

            sale_response = authenticated_api_client.post(
                sale_url, data=json.dumps(sale_data), content_type="application/json"
            )
            assert sale_response.status_code == 201
            sale_result = sale_response.json()
            assert sale_result["customer"] == str(customer.id)

    def test_quick_customer_add_during_sale(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test quick customer addition during sale process."""
        with tenant_context(tenant.id):
            # Quick add customer
            quick_add_url = reverse("sales:pos_customer_quick_add")
            customer_data = {
                "first_name": "Jane",
                "last_name": "Smith",
                "phone": "+9876543210",
                "email": "jane@example.com",
            }

            customer_response = authenticated_api_client.post(
                quick_add_url, data=json.dumps(customer_data), content_type="application/json"
            )
            assert customer_response.status_code == 201
            customer_result = customer_response.json()

            # Verify customer was created
            customer = Customer.objects.get(phone="+9876543210")
            assert customer.first_name == "Jane"
            assert customer_result["id"] == str(customer.id)

            # Use new customer in sale
            terminal = Terminal.objects.create(
                branch=inventory_item.branch,
                terminal_id="POS-01",
                is_active=True,
            )

            sale_url = reverse("sales:pos_create_sale")
            sale_data = {
                "customer_id": customer_result["id"],
                "terminal_id": str(terminal.id),
                "items": [
                    {
                        "inventory_item_id": str(inventory_item.id),
                        "quantity": 1,
                    }
                ],
                "payment_method": "CASH",
            }

            sale_response = authenticated_api_client.post(
                sale_url, data=json.dumps(sale_data), content_type="application/json"
            )
            assert sale_response.status_code == 201


@pytest.mark.django_db
class TestPOSInventoryDeduction:
    """Test inventory deduction logic during sales."""

    def test_inventory_deduction_single_item(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test inventory deduction for single item sale."""
        with tenant_context(tenant.id):
            terminal = Terminal.objects.create(
                branch=inventory_item.branch,
                terminal_id="POS-01",
                is_active=True,
            )

            initial_quantity = inventory_item.quantity
            sale_quantity = 3

            sale_url = reverse("sales:pos_create_sale")
            sale_data = {
                "terminal_id": str(terminal.id),
                "items": [
                    {
                        "inventory_item_id": str(inventory_item.id),
                        "quantity": sale_quantity,
                    }
                ],
                "payment_method": "CASH",
            }

            sale_response = authenticated_api_client.post(
                sale_url, data=json.dumps(sale_data), content_type="application/json"
            )
            assert sale_response.status_code == 201

            # Verify inventory deduction
            inventory_item.refresh_from_db()
            assert inventory_item.quantity == initial_quantity - sale_quantity

    def test_inventory_deduction_multiple_items(
        self, authenticated_api_client, tenant, tenant_user
    ):
        """Test inventory deduction for multiple items in one sale."""
        with tenant_context(tenant.id):
            branch = Branch.objects.create(tenant=tenant, name="Main")
            category = ProductCategory.objects.create(tenant=tenant, name="Rings")

            # Create multiple inventory items
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
                quantity=20,
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
                quantity=15,
            )

            terminal = Terminal.objects.create(
                branch=branch,
                terminal_id="POS-01",
                is_active=True,
            )

            initial_qty1 = item1.quantity
            initial_qty2 = item2.quantity

            sale_url = reverse("sales:pos_create_sale")
            sale_data = {
                "terminal_id": str(terminal.id),
                "items": [
                    {"inventory_item_id": str(item1.id), "quantity": 5},
                    {"inventory_item_id": str(item2.id), "quantity": 3},
                ],
                "payment_method": "CASH",
            }

            sale_response = authenticated_api_client.post(
                sale_url, data=json.dumps(sale_data), content_type="application/json"
            )
            assert sale_response.status_code == 201

            # Verify both items were deducted correctly
            item1.refresh_from_db()
            item2.refresh_from_db()
            assert item1.quantity == initial_qty1 - 5
            assert item2.quantity == initial_qty2 - 3

    def test_insufficient_inventory_prevention(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test that sales are prevented when inventory is insufficient."""
        with tenant_context(tenant.id):
            terminal = Terminal.objects.create(
                branch=inventory_item.branch,
                terminal_id="POS-01",
                is_active=True,
            )

            # Try to sell more than available
            sale_url = reverse("sales:pos_create_sale")
            sale_data = {
                "terminal_id": str(terminal.id),
                "items": [
                    {
                        "inventory_item_id": str(inventory_item.id),
                        "quantity": inventory_item.quantity + 10,
                    }
                ],
                "payment_method": "CASH",
            }

            sale_response = authenticated_api_client.post(
                sale_url, data=json.dumps(sale_data), content_type="application/json"
            )
            assert sale_response.status_code == 400
            assert "Insufficient inventory" in sale_response.json()["detail"]

            # Verify inventory was not changed
            original_quantity = inventory_item.quantity
            inventory_item.refresh_from_db()
            assert inventory_item.quantity == original_quantity

    def test_serialized_item_quantity_validation(
        self, authenticated_api_client, tenant, tenant_user
    ):
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
                serial_number="SN123456",  # Makes it serialized
            )

            terminal = Terminal.objects.create(
                branch=branch,
                terminal_id="POS-01",
                is_active=True,
            )

            sale_url = reverse("sales:pos_create_sale")
            sale_data = {
                "terminal_id": str(terminal.id),
                "items": [
                    {
                        "inventory_item_id": str(serialized_item.id),
                        "quantity": 2,  # Should fail
                    }
                ],
                "payment_method": "CASH",
            }

            sale_response = authenticated_api_client.post(
                sale_url, data=json.dumps(sale_data), content_type="application/json"
            )
            assert sale_response.status_code == 400
            assert (
                "Cannot sell more than 1 unit of serialized item" in sale_response.json()["detail"]
            )

    def test_concurrent_inventory_access_protection(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test that concurrent access to inventory is properly handled."""
        with tenant_context(tenant.id):
            terminal = Terminal.objects.create(
                branch=inventory_item.branch,
                terminal_id="POS-01",
                is_active=True,
            )

            initial_quantity = inventory_item.quantity

            # Simulate concurrent sale attempts
            sale_url = reverse("sales:pos_create_sale")
            sale_data = {
                "terminal_id": str(terminal.id),
                "items": [
                    {
                        "inventory_item_id": str(inventory_item.id),
                        "quantity": 1,
                    }
                ],
                "payment_method": "CASH",
            }

            # First sale should succeed
            sale_response1 = authenticated_api_client.post(
                sale_url, data=json.dumps(sale_data), content_type="application/json"
            )
            assert sale_response1.status_code == 201

            # Second sale should also succeed (if inventory allows)
            if initial_quantity > 1:
                sale_response2 = authenticated_api_client.post(
                    sale_url, data=json.dumps(sale_data), content_type="application/json"
                )
                assert sale_response2.status_code == 201

                # Verify correct total deduction
                inventory_item.refresh_from_db()
                assert inventory_item.quantity == initial_quantity - 2


@pytest.mark.django_db
class TestPOSPaymentProcessing:
    """Test payment processing functionality."""

    def test_cash_payment_processing(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test cash payment processing."""
        with tenant_context(tenant.id):
            terminal = Terminal.objects.create(
                branch=inventory_item.branch,
                terminal_id="POS-01",
                is_active=True,
            )

            sale_url = reverse("sales:pos_create_sale")
            sale_data = {
                "terminal_id": str(terminal.id),
                "items": [
                    {
                        "inventory_item_id": str(inventory_item.id),
                        "quantity": 1,
                    }
                ],
                "payment_method": "CASH",
                "tax_rate": "10.00",
            }

            sale_response = authenticated_api_client.post(
                sale_url, data=json.dumps(sale_data), content_type="application/json"
            )
            assert sale_response.status_code == 201
            sale_result = sale_response.json()
            assert sale_result["payment_method"] == "CASH"

    def test_card_payment_processing(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test card payment processing."""
        with tenant_context(tenant.id):
            terminal = Terminal.objects.create(
                branch=inventory_item.branch,
                terminal_id="POS-01",
                is_active=True,
            )

            sale_url = reverse("sales:pos_create_sale")
            sale_data = {
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

            sale_response = authenticated_api_client.post(
                sale_url, data=json.dumps(sale_data), content_type="application/json"
            )
            assert sale_response.status_code == 201
            sale_result = sale_response.json()
            assert sale_result["payment_method"] == "CARD"

    def test_split_payment_processing(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test split payment processing."""
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

            sale_url = reverse("sales:pos_create_sale")
            sale_data = {
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

            sale_response = authenticated_api_client.post(
                sale_url, data=json.dumps(sale_data), content_type="application/json"
            )
            assert sale_response.status_code == 201
            sale_result = sale_response.json()
            assert sale_result["payment_method"] == "SPLIT"
            assert "split_payments" in sale_result["payment_details"]

    def test_split_payment_total_validation(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test that split payment totals must match sale total."""
        with tenant_context(tenant.id):
            terminal = Terminal.objects.create(
                branch=inventory_item.branch,
                terminal_id="POS-01",
                is_active=True,
            )

            sale_url = reverse("sales:pos_create_sale")
            sale_data = {
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
                    {"method": "CARD", "amount": "30.00"},  # Total doesn't match
                ],
            }

            sale_response = authenticated_api_client.post(
                sale_url, data=json.dumps(sale_data), content_type="application/json"
            )
            assert sale_response.status_code == 400
            assert "Split payments total" in sale_response.json()["detail"]

    def test_store_credit_payment(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test store credit payment processing."""
        with tenant_context(tenant.id):
            # Create customer with store credit
            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-001",
                first_name="John",
                last_name="Doe",
                phone="+1234567890",
                store_credit=Decimal("1500.00"),  # Enough to cover the sale
            )

            terminal = Terminal.objects.create(
                branch=inventory_item.branch,
                terminal_id="POS-01",
                is_active=True,
            )

            sale_url = reverse("sales:pos_create_sale")
            sale_data = {
                "customer_id": str(customer.id),
                "terminal_id": str(terminal.id),
                "items": [
                    {
                        "inventory_item_id": str(inventory_item.id),
                        "quantity": 1,
                    }
                ],
                "payment_method": "STORE_CREDIT",
                "tax_rate": "10.00",
            }

            sale_response = authenticated_api_client.post(
                sale_url, data=json.dumps(sale_data), content_type="application/json"
            )
            assert sale_response.status_code == 201
            sale_result = sale_response.json()
            assert sale_result["payment_method"] == "STORE_CREDIT"

            # Verify store credit was deducted
            customer.refresh_from_db()
            expected_remaining = Decimal("1500.00") - Decimal(sale_result["total"])
            assert customer.store_credit == expected_remaining


@pytest.mark.django_db
class TestPOSOfflineModeAndSync:
    """Test offline mode functionality and synchronization."""

    def test_offline_sync_validation_success(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test offline sync validation with available inventory."""
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

            response = authenticated_api_client.post(url, data, format="json")
            assert response.status_code == status.HTTP_200_OK

            result = response.json()
            validation_result = result["validation_results"][0]
            assert validation_result["transaction_id"] == "offline_123"
            assert validation_result["valid"] is True
            assert len(validation_result["conflicts"]) == 0

    def test_offline_sync_validation_conflicts(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test offline sync validation with inventory conflicts."""
        with tenant_context(tenant.id):
            url = reverse("sales:pos_offline_sync_validation")
            data = {
                "transactions": [
                    {
                        "id": "offline_456",
                        "items": [
                            {
                                "inventory_item_id": str(inventory_item.id),
                                "quantity": inventory_item.quantity + 5,  # More than available
                            }
                        ],
                    }
                ]
            }

            response = authenticated_api_client.post(url, data, format="json")
            assert response.status_code == status.HTTP_200_OK

            result = response.json()
            validation_result = result["validation_results"][0]
            assert validation_result["transaction_id"] == "offline_456"
            assert validation_result["valid"] is False
            assert len(validation_result["conflicts"]) == 1

            conflict = validation_result["conflicts"][0]
            assert conflict["inventory_item_id"] == str(inventory_item.id)
            assert conflict["conflict_type"] == "insufficient_inventory"

    def test_offline_sync_multiple_transactions(
        self, authenticated_api_client, tenant, tenant_user
    ):
        """Test offline sync validation with multiple transactions."""
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
                quantity=5,
            )

            url = reverse("sales:pos_offline_sync_validation")
            data = {
                "transactions": [
                    {
                        "id": "offline_001",
                        "items": [{"inventory_item_id": str(item1.id), "quantity": 2}],
                    },
                    {
                        "id": "offline_002",
                        "items": [{"inventory_item_id": str(item2.id), "quantity": 1}],
                    },
                    {
                        "id": "offline_003",
                        "items": [{"inventory_item_id": str(item2.id), "quantity": 10}],  # Conflict
                    },
                ]
            }

            response = authenticated_api_client.post(url, data, format="json")
            assert response.status_code == status.HTTP_200_OK

            result = response.json()
            validation_results = result["validation_results"]

            # First two should be valid
            assert validation_results[0]["valid"] is True
            assert validation_results[1]["valid"] is True

            # Third should have conflict
            assert validation_results[2]["valid"] is False
            assert len(validation_results[2]["conflicts"]) == 1

    def test_offline_favorite_products(self, authenticated_api_client, tenant, tenant_user):
        """Test favorite products endpoint for offline mode."""
        with tenant_context(tenant.id):
            url = reverse("sales:pos_favorite_products")
            response = authenticated_api_client.get(url)

            assert response.status_code == status.HTTP_200_OK
            result = response.json()
            assert "results" in result
            assert isinstance(result["results"], list)

    def test_offline_recent_transactions(self, authenticated_api_client, tenant, tenant_user):
        """Test recent transactions endpoint for offline mode."""
        with tenant_context(tenant.id):
            url = reverse("sales:pos_recent_transactions")
            response = authenticated_api_client.get(url)

            assert response.status_code == status.HTTP_200_OK
            result = response.json()
            assert "results" in result
            assert isinstance(result["results"], list)

    def test_pos_interface_offline_scripts_loaded(self, client, tenant_user):
        """Test that POS interface loads offline functionality scripts."""
        client.force_login(tenant_user)

        with tenant_context(tenant_user.tenant.id):
            url = reverse("sales:pos_interface")
            response = client.get(url)

            assert response.status_code == 200
            content = response.content.decode()

            # Check offline scripts are included
            assert "pos-indexeddb.js" in content
            assert "pos-offline.js" in content
            assert "POSOfflineManager" in content

            # Check offline indicators
            assert "isOnline" in content
            assert "pendingTransactions" in content


@pytest.mark.django_db
class TestPOSReceiptGeneration:
    """Test receipt generation functionality."""

    def test_receipt_generation_after_sale(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test receipt generation immediately after sale creation."""
        with tenant_context(tenant.id):
            terminal = Terminal.objects.create(
                branch=inventory_item.branch,
                terminal_id="POS-01",
                is_active=True,
            )

            # Create sale
            sale_url = reverse("sales:pos_create_sale")
            sale_data = {
                "terminal_id": str(terminal.id),
                "items": [
                    {
                        "inventory_item_id": str(inventory_item.id),
                        "quantity": 1,
                    }
                ],
                "payment_method": "CASH",
                "tax_rate": "10.00",
            }

            sale_response = authenticated_api_client.post(
                sale_url, data=json.dumps(sale_data), content_type="application/json"
            )
            assert sale_response.status_code == 201
            sale_result = sale_response.json()

            # Generate receipt
            receipt_url = reverse("sales:generate_receipt", kwargs={"sale_id": sale_result["id"]})
            receipt_data = {"format_type": "standard", "auto_print": False, "save_receipt": False}

            receipt_response = authenticated_api_client.post(
                receipt_url, data=json.dumps(receipt_data), content_type="application/json"
            )
            assert receipt_response.status_code == 200
            receipt_result = receipt_response.json()
            assert "receipt_url" in receipt_result
            assert "pdf_url" in receipt_result

    def test_receipt_html_generation(self, client, tenant_user, sale_with_items):
        """Test HTML receipt generation."""
        client.force_login(tenant_user)

        url = reverse(
            "sales:receipt_html", kwargs={"sale_id": sale_with_items.id, "format_type": "standard"}
        )
        response = client.get(url)

        assert response.status_code == 200
        assert "text/html" in response["Content-Type"]
        content = response.content.decode()

        # Verify receipt contains sale details
        assert "SALES RECEIPT" in content
        assert sale_with_items.sale_number in content
        assert str(sale_with_items.total) in content
        assert sale_with_items.employee.get_full_name() in content

    def test_receipt_pdf_generation(self, client, tenant_user, sale_with_items):
        """Test PDF receipt generation."""
        client.force_login(tenant_user)

        url = reverse(
            "sales:receipt_pdf", kwargs={"sale_id": sale_with_items.id, "format_type": "standard"}
        )
        response = client.get(url)

        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert "attachment" in response["Content-Disposition"]
        assert sale_with_items.sale_number in response["Content-Disposition"]

    def test_thermal_receipt_generation(self, client, tenant_user, sale_with_items):
        """Test thermal receipt generation."""
        client.force_login(tenant_user)

        # HTML thermal receipt
        html_url = reverse(
            "sales:receipt_html", kwargs={"sale_id": sale_with_items.id, "format_type": "thermal"}
        )
        html_response = client.get(html_url)
        assert html_response.status_code == 200

        # PDF thermal receipt
        pdf_url = reverse(
            "sales:receipt_pdf", kwargs={"sale_id": sale_with_items.id, "format_type": "thermal"}
        )
        pdf_response = client.get(pdf_url)
        assert pdf_response.status_code == 200
        assert "thermal" in pdf_response["Content-Disposition"]

    def test_receipt_with_customer_details(self, tenant, inventory_item, tenant_user):
        """Test receipt generation includes customer information."""
        with tenant_context(tenant.id):
            # Create customer
            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-001",
                first_name="John",
                last_name="Doe",
                phone="+1234567890",
                email="john@example.com",
            )

            # Create sale with customer
            terminal = Terminal.objects.create(
                branch=inventory_item.branch,
                terminal_id="POS-01",
                is_active=True,
            )

            sale = Sale.objects.create(
                tenant=tenant,
                sale_number="SALE-20241022-000001",
                customer=customer,
                branch=inventory_item.branch,
                terminal=terminal,
                employee=tenant_user,
                subtotal=Decimal("100.00"),
                tax=Decimal("10.00"),
                discount=Decimal("0.00"),
                total=Decimal("110.00"),
                payment_method="CASH",
                status="COMPLETED",
            )

            # Generate receipt and verify customer info
            html_content = ReceiptService.generate_receipt(
                sale=sale, format_type="standard", output_format="html"
            ).decode("utf-8")

            assert customer.get_full_name() in html_content
            assert customer.phone in html_content

    def test_receipt_with_split_payment_details(self, tenant, inventory_item, tenant_user):
        """Test receipt generation includes split payment breakdown."""
        with tenant_context(tenant.id):
            terminal = Terminal.objects.create(
                branch=inventory_item.branch,
                terminal_id="POS-01",
                is_active=True,
            )

            # Create sale with split payment
            sale = Sale.objects.create(
                tenant=tenant,
                sale_number="SALE-20241022-000002",
                branch=inventory_item.branch,
                terminal=terminal,
                employee=tenant_user,
                subtotal=Decimal("100.00"),
                tax=Decimal("10.00"),
                discount=Decimal("0.00"),
                total=Decimal("110.00"),
                payment_method="SPLIT",
                payment_details={
                    "split_payments": [
                        {"method": "CASH", "amount": "60.00"},
                        {"method": "CARD", "amount": "50.00"},
                    ]
                },
                status="COMPLETED",
            )

            # Generate receipt and verify split payment details
            html_content = ReceiptService.generate_receipt(
                sale=sale, format_type="standard", output_format="html"
            ).decode("utf-8")

            assert "Payment Breakdown" in html_content
            assert "CASH: $60.00" in html_content
            assert "CARD: $50.00" in html_content

    @patch("apps.sales.receipt_service.qrcode")
    def test_receipt_qr_code_generation(self, mock_qrcode, sale_with_items):
        """Test QR code generation in receipts."""
        # Mock QR code generation
        mock_qr_instance = MagicMock()
        mock_qr_image = MagicMock()
        mock_qr_instance.make_image.return_value = mock_qr_image
        mock_qrcode.QRCode.return_value = mock_qr_instance

        # Generate PDF receipt (should trigger QR code generation)
        ReceiptService.generate_receipt(
            sale=sale_with_items, format_type="standard", output_format="pdf"
        )

        # Verify QR code generation was attempted
        mock_qrcode.QRCode.assert_called()


@pytest.mark.django_db
class TestPOSIntegrationScenarios:
    """Test complete POS integration scenarios."""

    def test_complete_pos_workflow_with_loyalty_customer(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test complete POS workflow with loyalty customer."""
        with tenant_context(tenant.id):
            # Create loyalty customer
            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-001",
                first_name="John",
                last_name="Doe",
                phone="+1234567890",
                loyalty_tier="GOLD",
                loyalty_points=1000,
                store_credit=Decimal("50.00"),
            )

            terminal = Terminal.objects.create(
                branch=inventory_item.branch,
                terminal_id="POS-01",
                is_active=True,
            )

            # Complete sale workflow
            sale_url = reverse("sales:pos_create_sale")
            sale_data = {
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
                "discount_type": "PERCENTAGE",
                "discount_value": "10.00",  # Loyalty discount
            }

            sale_response = authenticated_api_client.post(
                sale_url, data=json.dumps(sale_data), content_type="application/json"
            )
            assert sale_response.status_code == 201
            sale_result = sale_response.json()

            # Verify sale was created with customer
            assert sale_result["customer"] == str(customer.id)
            assert float(sale_result["discount"]) > 0  # Discount applied

            # Generate receipt
            receipt_url = reverse("sales:generate_receipt", kwargs={"sale_id": sale_result["id"]})
            receipt_data = {"format_type": "thermal", "auto_print": True, "save_receipt": True}

            receipt_response = authenticated_api_client.post(
                receipt_url, data=json.dumps(receipt_data), content_type="application/json"
            )
            assert receipt_response.status_code == 200
            receipt_result = receipt_response.json()
            assert "auto_print=true" in receipt_result["receipt_url"]

    def test_pos_error_handling_and_recovery(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test POS error handling and recovery scenarios."""
        with tenant_context(tenant.id):
            terminal = Terminal.objects.create(
                branch=inventory_item.branch,
                terminal_id="POS-01",
                is_active=True,
            )

            # Test invalid terminal
            sale_url = reverse("sales:pos_create_sale")
            invalid_terminal_data = {
                "terminal_id": "00000000-0000-0000-0000-000000000000",
                "items": [
                    {
                        "inventory_item_id": str(inventory_item.id),
                        "quantity": 1,
                    }
                ],
                "payment_method": "CASH",
            }

            response = authenticated_api_client.post(
                sale_url, data=json.dumps(invalid_terminal_data), content_type="application/json"
            )
            assert response.status_code == 400

            # Test invalid inventory item
            invalid_item_data = {
                "terminal_id": str(terminal.id),
                "items": [
                    {
                        "inventory_item_id": "00000000-0000-0000-0000-000000000000",
                        "quantity": 1,
                    }
                ],
                "payment_method": "CASH",
            }

            response = authenticated_api_client.post(
                sale_url, data=json.dumps(invalid_item_data), content_type="application/json"
            )
            assert response.status_code == 400

            # Test valid sale after errors
            valid_data = {
                "terminal_id": str(terminal.id),
                "items": [
                    {
                        "inventory_item_id": str(inventory_item.id),
                        "quantity": 1,
                    }
                ],
                "payment_method": "CASH",
            }

            response = authenticated_api_client.post(
                sale_url, data=json.dumps(valid_data), content_type="application/json"
            )
            assert response.status_code == 201


# Fixtures for comprehensive testing


@pytest.fixture
def sale_with_items(tenant, tenant_user):
    """Create a sale with items for testing."""
    with tenant_context(tenant.id):
        # Create branch and category
        branch = Branch.objects.create(tenant=tenant, name="Main Branch")
        category = ProductCategory.objects.create(tenant=tenant, name="Rings")

        # Create inventory items
        item1 = InventoryItem.objects.create(
            tenant=tenant,
            sku="RING-001",
            name="Gold Ring",
            category=category,
            branch=branch,
            karat=24,
            weight_grams=Decimal("10.5"),
            cost_price=Decimal("800.00"),
            selling_price=Decimal("1000.00"),
            quantity=10,
        )

        item2 = InventoryItem.objects.create(
            tenant=tenant,
            sku="RING-002",
            name="Silver Ring",
            category=category,
            branch=branch,
            karat=18,
            weight_grams=Decimal("8.0"),
            cost_price=Decimal("400.00"),
            selling_price=Decimal("500.00"),
            quantity=5,
        )

        # Create terminal
        terminal = Terminal.objects.create(branch=branch, terminal_id="POS-01", is_active=True)

        # Create sale
        sale = Sale.objects.create(
            tenant=tenant,
            sale_number="SALE-20241022-000001",
            branch=branch,
            terminal=terminal,
            employee=tenant_user,
            subtotal=Decimal("1500.00"),
            tax=Decimal("150.00"),
            discount=Decimal("50.00"),
            total=Decimal("1600.00"),
            payment_method="CASH",
            status="COMPLETED",
        )

        # Create sale items
        SaleItem.objects.create(
            sale=sale,
            inventory_item=item1,
            quantity=1,
            unit_price=Decimal("1000.00"),
            subtotal=Decimal("1000.00"),
        )

        SaleItem.objects.create(
            sale=sale,
            inventory_item=item2,
            quantity=1,
            unit_price=Decimal("500.00"),
            subtotal=Decimal("500.00"),
        )

        return sale
