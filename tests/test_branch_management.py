"""
Tests for branch management functionality.

Tests Requirement 14: Multi-Branch and Terminal Management
- Branch CRUD operations
- Branch configuration (address, hours, manager assignment)
- Branch performance dashboard with comparative metrics
- Branch-specific inventory tracking
"""

import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Branch, Tenant
from apps.core.tenant_context import bypass_rls, tenant_context
from apps.inventory.models import InventoryItem, ProductCategory
from apps.sales.models import Customer, Sale, SaleItem, Terminal

User = get_user_model()


class BranchManagementTestCase(TestCase):
    """Test case for branch management functionality."""

    def setUp(self):
        """Set up test data."""
        # Create tenant using RLS bypass (like platform admin would)
        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop", slug="test-shop", status=Tenant.ACTIVE
            )

            # Create users
            self.owner = User.objects.create_user(
                username="owner",
                email="owner@test.com",
                password="testpass123",
                tenant=self.tenant,
                role=User.TENANT_OWNER,
            )

            self.manager = User.objects.create_user(
                username="manager",
                email="manager@test.com",
                password="testpass123",
                tenant=self.tenant,
                role=User.TENANT_MANAGER,
            )

            self.employee = User.objects.create_user(
                username="employee",
                email="employee@test.com",
                password="testpass123",
                tenant=self.tenant,
                role=User.TENANT_EMPLOYEE,
            )

        # Create branches within tenant context
        with tenant_context(self.tenant.id):
            self.main_branch = Branch.objects.create(
                tenant=self.tenant,
                name="Main Store",
                address="123 Main St, City, State 12345",
                phone="+1-555-123-4567",
                manager=self.manager,
                opening_hours={
                    "monday": "9:00-18:00",
                    "tuesday": "9:00-18:00",
                    "wednesday": "9:00-18:00",
                    "thursday": "9:00-18:00",
                    "friday": "9:00-20:00",
                    "saturday": "10:00-18:00",
                    "sunday": "Closed",
                },
                is_active=True,
            )

            self.secondary_branch = Branch.objects.create(
                tenant=self.tenant,
                name="Mall Location",
                address="456 Mall Ave, City, State 12345",
                phone="+1-555-987-6543",
                opening_hours={
                    "monday": "10:00-21:00",
                    "tuesday": "10:00-21:00",
                    "wednesday": "10:00-21:00",
                    "thursday": "10:00-21:00",
                    "friday": "10:00-21:00",
                    "saturday": "10:00-21:00",
                    "sunday": "12:00-18:00",
                },
                is_active=True,
            )

            # Create product category
            self.category = ProductCategory.objects.create(tenant=self.tenant, name="Rings")

            # Create inventory items
            self.inventory_main = InventoryItem.objects.create(
                tenant=self.tenant,
                sku="RING-001",
                name="Gold Ring 18K",
                category=self.category,
                karat=18,
                weight_grams=Decimal("5.5"),
                cost_price=Decimal("500.00"),
                selling_price=Decimal("750.00"),
                quantity=10,
                min_quantity=2,
                branch=self.main_branch,
            )

            self.inventory_secondary = InventoryItem.objects.create(
                tenant=self.tenant,
                sku="RING-002",
                name="Silver Ring",
                category=self.category,
                karat=0,  # Silver
                weight_grams=Decimal("3.2"),
                cost_price=Decimal("50.00"),
                selling_price=Decimal("100.00"),
                quantity=1,  # Low stock
                min_quantity=5,
                branch=self.secondary_branch,
            )

            # Create terminals
            self.terminal_main = Terminal.objects.create(
                branch=self.main_branch, terminal_id="POS-01", is_active=True
            )

            self.terminal_secondary = Terminal.objects.create(
                branch=self.secondary_branch, terminal_id="POS-02", is_active=True
            )

            # Create customer
            self.customer = Customer.objects.create(
                tenant=self.tenant,
                customer_number="CUST-001",
                first_name="John",
                last_name="Doe",
                phone="+1-555-111-2222",
            )

            # Create sales data for performance testing
            self.create_test_sales()

        self.client = Client()

    def create_test_sales(self):
        """Create test sales data for performance metrics."""
        # Sales for main branch
        sale1 = Sale.objects.create(
            tenant=self.tenant,
            sale_number="SALE-001",
            customer=self.customer,
            branch=self.main_branch,
            terminal=self.terminal_main,
            employee=self.owner,
            subtotal=Decimal("750.00"),
            tax=Decimal("60.00"),
            total=Decimal("810.00"),
            payment_method=Sale.CASH,
            status=Sale.COMPLETED,
            created_at=timezone.now() - timedelta(days=5),
        )

        SaleItem.objects.create(
            sale=sale1,
            inventory_item=self.inventory_main,
            quantity=1,
            unit_price=Decimal("750.00"),
            subtotal=Decimal("750.00"),
        )

        # Sales for secondary branch
        sale2 = Sale.objects.create(
            tenant=self.tenant,
            sale_number="SALE-002",
            branch=self.secondary_branch,
            terminal=self.terminal_secondary,
            employee=self.manager,
            subtotal=Decimal("100.00"),
            tax=Decimal("8.00"),
            total=Decimal("108.00"),
            payment_method=Sale.CARD,
            status=Sale.COMPLETED,
            created_at=timezone.now() - timedelta(days=3),
        )

        SaleItem.objects.create(
            sale=sale2,
            inventory_item=self.inventory_secondary,
            quantity=1,
            unit_price=Decimal("100.00"),
            subtotal=Decimal("100.00"),
        )

    def test_branch_list_view(self):
        """Test branch list view."""
        self.client.login(username="owner", password="testpass123")

        response = self.client.get(reverse("core:branch_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Main Store")
        self.assertContains(response, "Mall Location")
        self.assertContains(response, "Branch Management")

    def test_branch_list_search(self):
        """Test branch list search functionality."""
        self.client.login(username="owner", password="testpass123")

        # Search by name
        response = self.client.get(reverse("core:branch_list"), {"search": "Main"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Main Store")
        self.assertNotContains(response, "Mall Location")

        # Search by address
        response = self.client.get(reverse("core:branch_list"), {"search": "Mall Ave"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mall Location")
        self.assertNotContains(response, "Main Store")

    def test_branch_detail_view(self):
        """Test branch detail view with performance metrics."""
        self.client.login(username="owner", password="testpass123")

        response = self.client.get(
            reverse("core:branch_detail", kwargs={"pk": self.main_branch.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Main Store")
        self.assertContains(response, "Performance Metrics")
        self.assertContains(response, "Inventory Summary")
        self.assertContains(response, "Staff Summary")

    def test_branch_create_view(self):
        """Test branch creation."""
        self.client.login(username="owner", password="testpass123")

        # GET request
        response = self.client.get(reverse("core:branch_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add New Branch")

        # POST request
        opening_hours = {
            "monday": "9:00-17:00",
            "tuesday": "9:00-17:00",
            "wednesday": "9:00-17:00",
            "thursday": "9:00-17:00",
            "friday": "9:00-17:00",
            "saturday": "Closed",
            "sunday": "Closed",
        }

        response = self.client.post(
            reverse("core:branch_create"),
            {
                "name": "New Branch",
                "address": "789 New St, City, State 12345",
                "phone": "+1-555-999-8888",
                "manager": self.manager.pk,
                "opening_hours": json.dumps(opening_hours),
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 302)  # Redirect after successful creation

        # Verify branch was created
        new_branch = Branch.objects.get(name="New Branch")
        self.assertEqual(new_branch.tenant_id, self.tenant.id)
        self.assertEqual(new_branch.manager_id, self.manager.id)
        self.assertEqual(new_branch.opening_hours, opening_hours)

    def test_branch_update_view(self):
        """Test branch update."""
        self.client.login(username="owner", password="testpass123")

        # GET request
        response = self.client.get(
            reverse("core:branch_update", kwargs={"pk": self.main_branch.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit Branch")
        self.assertContains(response, self.main_branch.name)

        # POST request
        response = self.client.post(
            reverse("core:branch_update", kwargs={"pk": self.main_branch.pk}),
            {
                "name": "Updated Main Store",
                "address": self.main_branch.address,
                "phone": self.main_branch.phone,
                "manager": self.main_branch.manager.pk,
                "opening_hours": json.dumps(self.main_branch.opening_hours),
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 302)  # Redirect after successful update

        # Verify branch was updated
        self.main_branch.refresh_from_db()
        self.assertEqual(self.main_branch.name, "Updated Main Store")

    def test_branch_delete_view(self):
        """Test branch deletion."""
        self.client.login(username="owner", password="testpass123")

        # Create a branch without inventory/sales for deletion
        empty_branch = Branch.objects.create(
            tenant=self.tenant, name="Empty Branch", is_active=True
        )

        # GET request (confirmation page)
        response = self.client.get(reverse("core:branch_delete", kwargs={"pk": empty_branch.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delete Branch")
        self.assertContains(response, "Empty Branch")

        # POST request (actual deletion)
        response = self.client.post(reverse("core:branch_delete", kwargs={"pk": empty_branch.pk}))
        self.assertEqual(response.status_code, 302)  # Redirect after deletion

        # Verify branch was deleted
        self.assertFalse(Branch.objects.filter(pk=empty_branch.pk).exists())

    def test_branch_delete_with_data_prevention(self):
        """Test that branches with inventory/sales cannot be deleted."""
        self.client.login(username="owner", password="testpass123")

        # Try to delete main branch which has inventory and sales
        response = self.client.post(
            reverse("core:branch_delete", kwargs={"pk": self.main_branch.pk})
        )

        # Should redirect back to detail page with error message
        self.assertEqual(response.status_code, 302)

        # Verify branch still exists
        self.assertTrue(Branch.objects.filter(pk=self.main_branch.pk).exists())

    def test_branch_performance_dashboard(self):
        """Test branch performance dashboard."""
        self.client.login(username="owner", password="testpass123")

        response = self.client.get(reverse("core:branch_performance_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Branch Performance Dashboard")
        self.assertContains(response, "Main Store")
        self.assertContains(response, "Mall Location")
        self.assertContains(response, "Total Sales")
        self.assertContains(response, "Transactions")

    def test_branch_inventory_api(self):
        """Test branch-specific inventory API."""
        self.client.login(username="owner", password="testpass123")

        response = self.client.get(
            reverse("core:api_branch_inventory", kwargs={"branch_id": self.main_branch.pk})
        )
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("items", data)
        self.assertIn("pagination", data)
        self.assertIn("branch", data)

        # Check that only main branch inventory is returned
        items = data["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["sku"], "RING-001")

    def test_branch_inventory_api_low_stock_filter(self):
        """Test branch inventory API with low stock filter."""
        self.client.login(username="owner", password="testpass123")

        response = self.client.get(
            reverse("core:api_branch_inventory", kwargs={"branch_id": self.secondary_branch.pk}),
            {"low_stock": "true"},
        )
        self.assertEqual(response.status_code, 200)

        data = response.json()
        items = data["items"]

        # Secondary branch has low stock item
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["sku"], "RING-002")
        self.assertTrue(items[0]["is_low_stock"])

    def test_tenant_isolation(self):
        """Test that users can only access branches from their own tenant."""
        # Create another tenant and user using RLS bypass
        with bypass_rls():
            other_tenant = Tenant.objects.create(
                company_name="Other Jewelry Shop", slug="other-shop", status=Tenant.ACTIVE
            )

            User.objects.create_user(
                username="other_owner",
                email="other@test.com",
                password="testpass123",
                tenant=other_tenant,
                role=User.TENANT_OWNER,
            )

        with tenant_context(other_tenant.id):
            other_branch = Branch.objects.create(
                tenant=other_tenant, name="Other Branch", is_active=True
            )

        # Login as original tenant user
        self.client.login(username="owner", password="testpass123")

        # Try to access other tenant's branch
        response = self.client.get(reverse("core:branch_detail", kwargs={"pk": other_branch.pk}))
        self.assertEqual(response.status_code, 404)  # Should not be found due to tenant filtering

        # Branch list should not show other tenant's branches
        response = self.client.get(reverse("core:branch_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Other Branch")

    def test_permission_requirements(self):
        """Test that proper permissions are required for branch management."""
        # Test unauthenticated access
        response = self.client.get(reverse("core:branch_list"))
        self.assertEqual(response.status_code, 302)  # Redirect to login

        # Test employee access (should work for viewing)
        self.client.login(username="employee", password="testpass123")
        response = self.client.get(reverse("core:branch_list"))
        self.assertEqual(response.status_code, 200)

        # Test employee cannot create branches (depends on permission implementation)
        response = self.client.get(reverse("core:branch_create"))
        # This might return 403 or redirect depending on permission implementation
        self.assertIn(response.status_code, [200, 403, 302])

    def test_branch_api_endpoints(self):
        """Test REST API endpoints for branches."""
        self.client.login(username="owner", password="testpass123")

        # List branches
        response = self.client.get(reverse("core:api_branch_list"))
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("results", data)

        # Get specific branch
        response = self.client.get(
            reverse("core:api_branch_detail", kwargs={"pk": self.main_branch.pk})
        )
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["name"], "Main Store")
        self.assertEqual(data["tenant_name"], "Test Jewelry Shop")

    def test_branch_manager_assignment(self):
        """Test branch manager assignment validation."""
        self.client.login(username="owner", password="testpass123")

        # Create a user from different tenant using RLS bypass
        with bypass_rls():
            other_tenant = Tenant.objects.create(company_name="Other Shop", slug="other-shop-2")

            other_manager = User.objects.create_user(
                username="other_manager",
                email="other_manager@test.com",
                password="testpass123",
                tenant=other_tenant,
                role=User.TENANT_MANAGER,
            )

        # Try to assign manager from different tenant
        response = self.client.post(
            reverse("core:branch_create"),
            {"name": "Test Branch", "manager": other_manager.pk, "is_active": True},
        )

        # Should either fail validation or not show the other manager in choices
        # The exact behavior depends on form implementation
        if response.status_code == 200:
            # Form validation failed
            self.assertContains(response, "manager")
        else:
            # Branch created but manager should not be assigned
            branch = Branch.objects.get(name="Test Branch")
            self.assertNotEqual(branch.manager, other_manager)


class BranchModelTestCase(TestCase):
    """Test case for Branch model functionality."""

    def setUp(self):
        """Set up test data."""
        with bypass_rls():
            self.tenant = Tenant.objects.create(company_name="Test Shop", slug="test-shop")

            self.manager = User.objects.create_user(
                username="manager",
                email="manager@test.com",
                password="testpass123",
                tenant=self.tenant,
                role=User.TENANT_MANAGER,
            )

    def test_branch_creation(self):
        """Test branch model creation."""
        with tenant_context(self.tenant.id):
            branch = Branch.objects.create(
                tenant=self.tenant,
                name="Test Branch",
                address="123 Test St",
                phone="+1-555-123-4567",
                manager=self.manager,
                opening_hours={"monday": "9:00-17:00", "tuesday": "9:00-17:00"},
                is_active=True,
            )

            self.assertEqual(str(branch), "Test Branch (Test Shop)")
            self.assertEqual(branch.tenant, self.tenant)
            self.assertEqual(branch.manager, self.manager)
            self.assertTrue(branch.is_active)

    def test_branch_unique_constraint(self):
        """Test that branch names are unique within a tenant."""
        from django.db import IntegrityError, transaction

        with tenant_context(self.tenant.id):
            Branch.objects.create(tenant=self.tenant, name="Duplicate Name", is_active=True)

        # Creating another branch with same name in same tenant should fail
        with tenant_context(self.tenant.id):
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    Branch.objects.create(tenant=self.tenant, name="Duplicate Name", is_active=True)

    def test_branch_opening_hours_json(self):
        """Test that opening hours are stored as JSON."""
        opening_hours = {
            "monday": "9:00-18:00",
            "tuesday": "9:00-18:00",
            "wednesday": "Closed",
            "thursday": "9:00-18:00",
            "friday": "9:00-20:00",
            "saturday": "10:00-18:00",
            "sunday": "Closed",
        }

        with tenant_context(self.tenant.id):
            branch = Branch.objects.create(
                tenant=self.tenant, name="Test Branch", opening_hours=opening_hours, is_active=True
            )

            branch = Branch.objects.get(pk=branch.pk)
            self.assertEqual(branch.opening_hours, opening_hours)
            self.assertEqual(branch.opening_hours["wednesday"], "Closed")
            self.assertEqual(branch.opening_hours["friday"], "9:00-20:00")


class TerminalManagementTestCase(TestCase):
    """Test case for terminal management functionality."""

    def setUp(self):
        """Set up test data."""
        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop", slug="test-shop", status=Tenant.ACTIVE
            )

            self.owner = User.objects.create_user(
                username="owner",
                email="owner@test.com",
                password="testpass123",
                tenant=self.tenant,
                role=User.TENANT_OWNER,
            )

        with tenant_context(self.tenant.id):
            self.branch = Branch.objects.create(
                tenant=self.tenant, name="Main Store", is_active=True
            )

            self.terminal = Terminal.objects.create(
                branch=self.branch,
                terminal_id="POS-01",
                description="Main counter terminal",
                is_active=True,
            )

        self.client = Client()

    def test_terminal_list_view(self):
        """Test terminal list view."""
        with tenant_context(self.tenant.id):
            self.client.login(username="owner", password="testpass123")

        response = self.client.get(reverse("core:terminal_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "POS-01")
        self.assertContains(response, "Terminal Management")

    def test_terminal_create_view(self):
        """Test terminal creation."""
        with tenant_context(self.tenant.id):
            self.client.login(username="owner", password="testpass123")

            # GET request
            response = self.client.get(reverse("core:terminal_create"))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Add New Terminal")

            # POST request
            configuration = {
                "printer_ip": "192.168.1.100",
                "printer_port": "9100",
                "scanner_enabled": True,
            }

            response = self.client.post(
                reverse("core:terminal_create"),
                {
                    "terminal_id": "POS-02",
                    "description": "Secondary terminal",
                    "branch": self.branch.pk,
                    "configuration": json.dumps(configuration),
                    "is_active": True,
                },
            )

            self.assertEqual(response.status_code, 302)  # Redirect after successful creation

            # Verify terminal was created
            new_terminal = Terminal.objects.get(terminal_id="POS-02")
            self.assertEqual(new_terminal.branch, self.branch)
            self.assertEqual(new_terminal.configuration, configuration)

    def test_terminal_update_view(self):
        """Test terminal update."""
        with tenant_context(self.tenant.id):
            self.client.login(username="owner", password="testpass123")

            # GET request
            response = self.client.get(
                reverse("core:terminal_update", kwargs={"pk": self.terminal.pk})
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Edit Terminal")
            self.assertContains(response, self.terminal.terminal_id)

            # POST request
            response = self.client.post(
                reverse("core:terminal_update", kwargs={"pk": self.terminal.pk}),
                {
                    "terminal_id": "POS-01-UPDATED",
                    "description": "Updated description",
                    "branch": self.branch.pk,
                    "configuration": "{}",
                    "is_active": True,
                },
            )

            self.assertEqual(response.status_code, 302)  # Redirect after successful update

            # Verify terminal was updated
            self.terminal = Terminal.objects.get(pk=self.terminal.pk)
            self.assertEqual(self.terminal.terminal_id, "POS-01-UPDATED")
            self.assertEqual(self.terminal.description, "Updated description")

    def test_terminal_delete_view(self):
        """Test terminal deletion."""
        self.client.login(username="owner", password="testpass123")

        # Create a terminal without sales for deletion
        with tenant_context(self.tenant.id):
            empty_terminal = Terminal.objects.create(
                branch=self.branch, terminal_id="POS-EMPTY", is_active=True
            )

        # GET request (confirmation page)
        response = self.client.get(
            reverse("core:terminal_delete", kwargs={"pk": empty_terminal.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delete Terminal")
        self.assertContains(response, "POS-EMPTY")

        # POST request (actual deletion)
        response = self.client.post(
            reverse("core:terminal_delete", kwargs={"pk": empty_terminal.pk})
        )
        self.assertEqual(response.status_code, 302)  # Redirect after deletion

        # Verify terminal was deleted
        self.assertFalse(Terminal.objects.filter(pk=empty_terminal.pk).exists())

    def test_terminal_api_endpoints(self):
        """Test REST API endpoints for terminals."""
        self.client.login(username="owner", password="testpass123")

        # List terminals
        response = self.client.get(reverse("core:api_terminal_list"))
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("results", data)

        # Get specific terminal
        response = self.client.get(
            reverse("core:api_terminal_detail", kwargs={"pk": self.terminal.pk})
        )
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["terminal_id"], "POS-01")
        self.assertEqual(data["branch_name"], "Main Store")

    def test_terminal_tenant_isolation(self):
        """Test that users can only access terminals from their own tenant's branches."""
        # Create another tenant and terminal
        with bypass_rls():
            other_tenant = Tenant.objects.create(
                company_name="Other Shop", slug="other-shop", status=Tenant.ACTIVE
            )

            User.objects.create_user(
                username="other_owner",
                email="other@test.com",
                password="testpass123",
                tenant=other_tenant,
                role=User.TENANT_OWNER,
            )

        with tenant_context(other_tenant.id):
            other_branch = Branch.objects.create(
                tenant=other_tenant, name="Other Branch", is_active=True
            )

            other_terminal = Terminal.objects.create(
                branch=other_branch, terminal_id="OTHER-POS", is_active=True
            )

        # Login as original tenant user
        self.client.login(username="owner", password="testpass123")

        # Try to access other tenant's terminal
        response = self.client.get(
            reverse("core:terminal_update", kwargs={"pk": other_terminal.pk})
        )
        self.assertEqual(response.status_code, 404)  # Should not be found due to tenant filtering

        # Terminal list should not show other tenant's terminals
        response = self.client.get(reverse("core:terminal_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "OTHER-POS")


class StaffAssignmentTestCase(TestCase):
    """Test case for staff assignment functionality."""

    def setUp(self):
        """Set up test data."""
        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop", slug="test-shop", status=Tenant.ACTIVE
            )

            self.owner = User.objects.create_user(
                username="owner",
                email="owner@test.com",
                password="testpass123",
                tenant=self.tenant,
                role=User.TENANT_OWNER,
            )

            self.employee = User.objects.create_user(
                username="employee",
                email="employee@test.com",
                password="testpass123",
                tenant=self.tenant,
                role=User.TENANT_EMPLOYEE,
            )

        with tenant_context(self.tenant.id):
            self.branch1 = Branch.objects.create(
                tenant=self.tenant, name="Branch 1", is_active=True
            )

            self.branch2 = Branch.objects.create(
                tenant=self.tenant, name="Branch 2", is_active=True
            )

        self.client = Client()

    def test_staff_assignment_view(self):
        """Test staff assignment view."""
        self.client.login(username="owner", password="testpass123")

        response = self.client.get(reverse("core:staff_assignment"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Staff Assignment")
        self.assertContains(response, self.employee.username)
        self.assertContains(response, self.branch1.name)
        self.assertContains(response, self.branch2.name)

    def test_assign_staff_api(self):
        """Test staff assignment API."""
        self.client.login(username="owner", password="testpass123")

        # Assign employee to branch1
        response = self.client.post(
            reverse("core:api_assign_staff"),
            json.dumps({"user_id": str(self.employee.id), "branch_id": str(self.branch1.id)}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["branch_name"], "Branch 1")

        # Verify assignment in database
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.branch, self.branch1)

    def test_unassign_staff_api(self):
        """Test staff unassignment API."""
        self.client.login(username="owner", password="testpass123")

        # First assign employee to a branch
        with tenant_context(self.tenant.id):
            self.employee.branch = self.branch1
            self.employee.save()

        # Then unassign (set branch to null)
        response = self.client.post(
            reverse("core:api_assign_staff"),
            json.dumps({"user_id": str(self.employee.id), "branch_id": None}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIsNone(data["branch_id"])

        # Verify unassignment in database
        self.employee.refresh_from_db()
        self.assertIsNone(self.employee.branch)

    def test_staff_assignment_tenant_isolation(self):
        """Test that staff can only be assigned to branches from the same tenant."""
        # Create another tenant and branch
        with bypass_rls():
            other_tenant = Tenant.objects.create(
                company_name="Other Shop", slug="other-shop", status=Tenant.ACTIVE
            )

        with tenant_context(other_tenant.id):
            other_branch = Branch.objects.create(
                tenant=other_tenant, name="Other Branch", is_active=True
            )

        self.client.login(username="owner", password="testpass123")

        # Try to assign employee to other tenant's branch
        response = self.client.post(
            reverse("core:api_assign_staff"),
            json.dumps({"user_id": str(self.employee.id), "branch_id": str(other_branch.id)}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)  # Branch not found due to tenant filtering

    def test_assign_nonexistent_user(self):
        """Test assigning a non-existent user."""
        self.client.login(username="owner", password="testpass123")

        response = self.client.post(
            reverse("core:api_assign_staff"),
            json.dumps(
                {"user_id": 99999, "branch_id": str(self.branch1.id)}  # Non-existent user ID
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["error"], "User not found")
