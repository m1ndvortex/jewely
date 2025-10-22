"""
Tests for inventory CRUD operations.

Tests Requirement 9: Advanced Inventory Management
- Inventory list view with search and filters
- Inventory detail view
- Inventory create/edit operations with validation
- Stock adjustment functionality
"""

from decimal import Decimal

from django.urls import reverse

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import Branch, Tenant, User
from apps.inventory.models import InventoryItem, ProductCategory


@pytest.mark.django_db
class TestInventoryItemCRUD:
    """Test inventory item CRUD operations."""

    @pytest.fixture
    def setup_data(self):
        """Set up test data."""
        # Create tenant
        tenant = Tenant.objects.create(company_name="Test Jewelry Shop", slug="test-shop")

        # Create branch
        branch = Branch.objects.create(tenant=tenant, name="Main Branch")

        # Create category
        category = ProductCategory.objects.create(tenant=tenant, name="Rings")

        # Create user
        user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            email="test@example.com",
            tenant=tenant,
            role=User.TENANT_MANAGER,
            branch=branch,
        )

        # Create API client
        client = APIClient()
        client.force_authenticate(user=user)

        return {
            "tenant": tenant,
            "branch": branch,
            "category": category,
            "user": user,
            "client": client,
        }

    def test_list_inventory_items(self, setup_data):
        """Test listing inventory items."""
        # Create test items
        InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=5,
            branch=setup_data["branch"],
        )

        InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-002",
            name="22K Gold Ring",
            category=setup_data["category"],
            karat=22,
            weight_grams=Decimal("8.000"),
            cost_price=Decimal("800.00"),
            selling_price=Decimal("1000.00"),
            quantity=3,
            branch=setup_data["branch"],
        )

        # Make request
        url = reverse("inventory:item_list")
        response = setup_data["client"].get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        assert len(response.data["results"]) == 2

    def test_list_inventory_with_search(self, setup_data):
        """Test listing inventory items with search."""
        # Create test items
        InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=5,
            branch=setup_data["branch"],
        )

        InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="NL-001",
            name="Diamond Necklace",
            category=setup_data["category"],
            karat=18,
            weight_grams=Decimal("15.000"),
            cost_price=Decimal("2000.00"),
            selling_price=Decimal("2500.00"),
            quantity=2,
            branch=setup_data["branch"],
        )

        # Search for "Ring"
        url = reverse("inventory:item_list")
        response = setup_data["client"].get(url, {"search": "Ring"})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["name"] == "24K Gold Ring"

    def test_list_inventory_with_filters(self, setup_data):
        """Test listing inventory items with filters."""
        # Create test items with different karats
        InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=5,
            branch=setup_data["branch"],
        )

        InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-002",
            name="22K Gold Ring",
            category=setup_data["category"],
            karat=22,
            weight_grams=Decimal("8.000"),
            cost_price=Decimal("800.00"),
            selling_price=Decimal("1000.00"),
            quantity=3,
            branch=setup_data["branch"],
        )

        # Filter by karat=24
        url = reverse("inventory:item_list")
        response = setup_data["client"].get(url, {"karat": 24})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["karat"] == 24

    def test_list_inventory_low_stock_filter(self, setup_data):
        """Test filtering low stock items."""
        # Create items with different stock levels
        InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=2,
            min_quantity=5,
            branch=setup_data["branch"],
        )

        InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-002",
            name="22K Gold Ring",
            category=setup_data["category"],
            karat=22,
            weight_grams=Decimal("8.000"),
            cost_price=Decimal("800.00"),
            selling_price=Decimal("1000.00"),
            quantity=10,
            min_quantity=5,
            branch=setup_data["branch"],
        )

        # Filter low stock items
        url = reverse("inventory:item_list")
        response = setup_data["client"].get(url, {"low_stock": "true"})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["sku"] == "GR-001"

    def test_get_inventory_item_detail(self, setup_data):
        """Test retrieving a single inventory item."""
        item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=5,
            branch=setup_data["branch"],
        )

        url = reverse("inventory:item_detail", kwargs={"id": item.id})
        response = setup_data["client"].get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["sku"] == "GR-001"
        assert response.data["name"] == "24K Gold Ring"
        assert Decimal(response.data["cost_price"]) == Decimal("1000.00")

    def test_create_inventory_item(self, setup_data):
        """Test creating a new inventory item."""
        url = reverse("inventory:item_create")
        data = {
            "tenant": str(setup_data["tenant"].id),
            "sku": "GR-003",
            "name": "18K Gold Ring",
            "category": str(setup_data["category"].id),
            "karat": 18,
            "weight_grams": "12.500",
            "cost_price": "1500.00",
            "selling_price": "1800.00",
            "quantity": 10,
            "min_quantity": 5,
            "branch": str(setup_data["branch"].id),
            "craftsmanship_level": "HANDMADE",
            "is_active": True,
        }

        response = setup_data["client"].post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert InventoryItem.objects.filter(sku="GR-003").exists()

        item = InventoryItem.objects.get(sku="GR-003")
        assert item.name == "18K Gold Ring"
        assert item.karat == 18

    def test_create_inventory_item_duplicate_sku(self, setup_data):
        """Test creating inventory item with duplicate SKU fails."""
        # Create first item
        InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=5,
            branch=setup_data["branch"],
        )

        # Try to create another with same SKU
        url = reverse("inventory:item_create")
        data = {
            "tenant": str(setup_data["tenant"].id),
            "sku": "GR-001",
            "name": "Another Ring",
            "category": str(setup_data["category"].id),
            "karat": 22,
            "weight_grams": "8.000",
            "cost_price": "800.00",
            "selling_price": "1000.00",
            "quantity": 3,
            "branch": str(setup_data["branch"].id),
            "is_active": True,
        }

        response = setup_data["client"].post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "sku" in response.data

    def test_create_inventory_item_selling_price_validation(self, setup_data):
        """Test that selling price must be >= cost price."""
        url = reverse("inventory:item_create")
        data = {
            "tenant": str(setup_data["tenant"].id),
            "sku": "GR-003",
            "name": "18K Gold Ring",
            "category": str(setup_data["category"].id),
            "karat": 18,
            "weight_grams": "12.500",
            "cost_price": "1500.00",
            "selling_price": "1000.00",  # Less than cost price
            "quantity": 10,
            "branch": str(setup_data["branch"].id),
            "is_active": True,
        }

        response = setup_data["client"].post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "selling_price" in response.data

    def test_update_inventory_item(self, setup_data):
        """Test updating an inventory item."""
        item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=5,
            branch=setup_data["branch"],
        )

        url = reverse("inventory:item_update", kwargs={"id": item.id})
        data = {
            "tenant": str(setup_data["tenant"].id),
            "sku": "GR-001",
            "name": "24K Gold Ring - Updated",
            "category": str(setup_data["category"].id),
            "karat": 24,
            "weight_grams": "11.000",
            "cost_price": "1100.00",
            "selling_price": "1300.00",
            "quantity": 5,
            "branch": str(setup_data["branch"].id),
            "is_active": True,
        }

        response = setup_data["client"].put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK

        item.refresh_from_db()
        assert item.name == "24K Gold Ring - Updated"
        assert item.weight_grams == Decimal("11.000")

    def test_delete_inventory_item(self, setup_data):
        """Test soft deleting an inventory item."""
        item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=5,
            branch=setup_data["branch"],
        )

        url = reverse("inventory:item_delete", kwargs={"id": item.id})
        response = setup_data["client"].delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        item.refresh_from_db()
        assert item.is_active is False

    def test_stock_adjustment_add(self, setup_data):
        """Test adding stock to an item."""
        item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=5,
            branch=setup_data["branch"],
        )

        url = reverse("inventory:stock_adjustment", kwargs={"item_id": item.id})
        data = {
            "adjustment_type": "ADD",
            "quantity": 10,
            "reason": "New purchase",
        }

        response = setup_data["client"].post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK

        item.refresh_from_db()
        assert item.quantity == 15

    def test_stock_adjustment_deduct(self, setup_data):
        """Test deducting stock from an item."""
        item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=10,
            branch=setup_data["branch"],
        )

        url = reverse("inventory:stock_adjustment", kwargs={"item_id": item.id})
        data = {
            "adjustment_type": "DEDUCT",
            "quantity": 3,
            "reason": "Sale",
        }

        response = setup_data["client"].post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK

        item.refresh_from_db()
        assert item.quantity == 7

    def test_stock_adjustment_set(self, setup_data):
        """Test setting stock to a specific level."""
        item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=10,
            branch=setup_data["branch"],
        )

        url = reverse("inventory:stock_adjustment", kwargs={"item_id": item.id})
        data = {
            "adjustment_type": "SET",
            "quantity": 20,
            "reason": "Physical count adjustment",
        }

        response = setup_data["client"].post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK

        item.refresh_from_db()
        assert item.quantity == 20

    def test_stock_adjustment_insufficient_stock(self, setup_data):
        """Test deducting more stock than available fails."""
        item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=5,
            branch=setup_data["branch"],
        )

        url = reverse("inventory:stock_adjustment", kwargs={"item_id": item.id})
        data = {
            "adjustment_type": "DEDUCT",
            "quantity": 10,
            "reason": "Sale",
        }

        response = setup_data["client"].post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "quantity" in response.data

    def test_stock_adjustment_serialized_item_validation(self, setup_data):
        """Test that serialized items cannot have quantity > 1."""
        item = InventoryItem.objects.create(
            tenant=setup_data["tenant"],
            sku="GR-001",
            name="24K Gold Ring",
            category=setup_data["category"],
            karat=24,
            weight_grams=Decimal("10.500"),
            cost_price=Decimal("1000.00"),
            selling_price=Decimal("1200.00"),
            quantity=1,
            branch=setup_data["branch"],
            serial_number="SN-12345",
        )

        url = reverse("inventory:stock_adjustment", kwargs={"item_id": item.id})
        data = {
            "adjustment_type": "SET",
            "quantity": 5,
            "reason": "Adjustment",
        }

        response = setup_data["client"].post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestProductCategoryCRUD:
    """Test product category CRUD operations."""

    @pytest.fixture
    def setup_data(self):
        """Set up test data."""
        # Create tenant
        tenant = Tenant.objects.create(company_name="Test Jewelry Shop", slug="test-shop")

        # Create branch
        branch = Branch.objects.create(tenant=tenant, name="Main Branch")

        # Create user
        user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            email="test@example.com",
            tenant=tenant,
            role=User.TENANT_MANAGER,
            branch=branch,
        )

        # Create API client
        client = APIClient()
        client.force_authenticate(user=user)

        return {
            "tenant": tenant,
            "branch": branch,
            "user": user,
            "client": client,
        }

    def test_list_categories(self, setup_data):
        """Test listing product categories."""
        ProductCategory.objects.create(tenant=setup_data["tenant"], name="Rings")
        ProductCategory.objects.create(tenant=setup_data["tenant"], name="Necklaces")

        url = reverse("inventory:category_list")
        response = setup_data["client"].get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        assert len(response.data["results"]) == 2

    def test_create_category(self, setup_data):
        """Test creating a new category."""
        url = reverse("inventory:category_create")
        data = {
            "tenant": str(setup_data["tenant"].id),
            "name": "Bracelets",
            "description": "Gold and silver bracelets",
            "is_active": True,
            "parent": None,
        }

        response = setup_data["client"].post(url, data, format="json")

        if response.status_code != status.HTTP_201_CREATED:
            print(f"Error response: {response.data}")
        assert response.status_code == status.HTTP_201_CREATED
        assert ProductCategory.objects.filter(name="Bracelets").exists()

    def test_update_category(self, setup_data):
        """Test updating a category."""
        category = ProductCategory.objects.create(
            tenant=setup_data["tenant"], name="Rings", description="Gold rings"
        )

        url = reverse("inventory:category_update", kwargs={"id": category.id})
        data = {
            "tenant": str(setup_data["tenant"].id),
            "name": "Rings",
            "description": "Gold and diamond rings",
            "is_active": True,
        }

        response = setup_data["client"].put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK

        category.refresh_from_db()
        assert category.description == "Gold and diamond rings"

    def test_delete_category(self, setup_data):
        """Test soft deleting a category."""
        category = ProductCategory.objects.create(tenant=setup_data["tenant"], name="Rings")

        url = reverse("inventory:category_delete", kwargs={"id": category.id})
        response = setup_data["client"].delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        category.refresh_from_db()
        assert category.is_active is False
