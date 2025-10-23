"""
Integration tests for repair order views.

Tests the complete repair order management workflow including
creation, status updates, photo uploads, and work order generation.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from apps.core.models import Tenant
from apps.core.tenant_context import bypass_rls, tenant_context
from apps.crm.models import Customer
from apps.repair.models import RepairOrder, RepairOrderPhoto

User = get_user_model()


class RepairOrderViewsIntegrationTest(TestCase):
    """Integration tests for repair order views."""

    def setUp(self):
        """Set up test data."""
        # Create tenant using RLS bypass
        with bypass_rls():
            self.tenant = Tenant.objects.create(company_name="Test Jewelry Shop", slug="test-shop")

            # Create user
            self.user = User.objects.create_user(
                username="testuser",
                email="test@example.com",
                password="testpass123",
                tenant=self.tenant,
                role="TENANT_OWNER",
            )

        # Create customer with tenant context
        with tenant_context(self.tenant.id):
            self.customer = Customer.objects.create(
                tenant=self.tenant,
                customer_number="CUST-001",
                first_name="John",
                last_name="Doe",
                email="john.doe@example.com",
                phone="555-0123",
            )

        self.client = Client()

    def test_repair_order_list_view_access(self):
        """Test that repair order list view requires authentication."""
        # Test unauthenticated access
        response = self.client.get(reverse("repair:repair_list"))
        self.assertEqual(response.status_code, 302)  # Redirect to login

        # Test authenticated access
        self.client.force_login(self.user)
        response = self.client.get(reverse("repair:repair_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Repair Orders")

    def test_repair_order_create_workflow(self):
        """Test complete repair order creation workflow."""
        self.client.force_login(self.user)

        # Test GET request to create form
        response = self.client.get(reverse("repair:repair_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "New Repair Order")

        # Test POST request to create repair order
        form_data = {
            "customer": self.customer.id,
            "item_description": "Gold ring needs cleaning and polishing",
            "service_type": "CLEANING",
            "service_notes": "Customer mentioned ring is very dirty",
            "priority": "NORMAL",
            "estimated_completion": (date.today() + timedelta(days=7)).isoformat(),
            "cost_estimate": "75.00",
        }

        response = self.client.post(reverse("repair:repair_create"), form_data)
        self.assertEqual(response.status_code, 302)  # Redirect after creation

        # Verify repair order was created
        with tenant_context(self.tenant.id):
            repair_order = RepairOrder.objects.filter(
                tenant=self.tenant, customer=self.customer
            ).first()

            self.assertIsNotNone(repair_order)
            self.assertEqual(
                repair_order.item_description, "Gold ring needs cleaning and polishing"
            )
            self.assertEqual(repair_order.service_type, "CLEANING")
            self.assertEqual(repair_order.cost_estimate, Decimal("75.00"))
            self.assertEqual(repair_order.status, "received")

    def test_repair_order_detail_view(self):
        """Test repair order detail view."""
        # Create repair order
        with tenant_context(self.tenant.id):
            repair_order = RepairOrder.objects.create(
                tenant=self.tenant,
                order_number="REP-TEST-001",
                customer=self.customer,
                item_description="Test repair item",
                service_type="RESIZING",
                cost_estimate=Decimal("100.00"),
                estimated_completion=date.today() + timedelta(days=5),
                created_by=self.user,
            )

        self.client.force_login(self.user)

        # Test detail view
        response = self.client.get(reverse("repair:repair_detail", kwargs={"pk": repair_order.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, repair_order.order_number)
        self.assertContains(response, "Test repair item")
        self.assertContains(response, "Resizing")

    def test_status_update_ajax(self):
        """Test AJAX status update functionality."""
        # Create repair order using the same pattern as model tests
        with tenant_context(self.tenant.id):
            repair_order = RepairOrder.objects.create(
                tenant=self.tenant,
                order_number="REP-TEST-002",
                customer=self.customer,
                item_description="Test status update",
                service_type="POLISHING",
                cost_estimate=Decimal("50.00"),
                estimated_completion=date.today() + timedelta(days=3),
                created_by=self.user,
            )

        self.client.force_login(self.user)

        # Test status update
        response = self.client.post(
            reverse("repair:update_status", kwargs={"pk": repair_order.pk}),
            {"action": "start_work"},
        )

        self.assertEqual(response.status_code, 200)

        # Check response content
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["new_status"], "in_progress")

        # Verify status was updated in database
        with tenant_context(self.tenant.id):
            updated_repair_order = RepairOrder.objects.get(pk=repair_order.pk)
            self.assertEqual(updated_repair_order.status, "in_progress")
            self.assertEqual(updated_repair_order.assigned_to, self.user)

    def test_photo_upload_ajax(self):
        """Test AJAX photo upload functionality."""
        # Create repair order
        with tenant_context(self.tenant.id):
            repair_order = RepairOrder.objects.create(
                tenant=self.tenant,
                order_number="REP-TEST-003",
                customer=self.customer,
                item_description="Test photo upload",
                service_type="CHAIN_REPAIR",
                cost_estimate=Decimal("80.00"),
                estimated_completion=date.today() + timedelta(days=4),
                created_by=self.user,
            )

        self.client.force_login(self.user)

        # Create a simple test image using PIL
        from io import BytesIO

        from PIL import Image

        # Create a simple 1x1 pixel image
        img = Image.new("RGB", (1, 1), color="red")
        img_buffer = BytesIO()
        img.save(img_buffer, format="PNG")
        img_buffer.seek(0)

        test_image = SimpleUploadedFile(
            name="test_image.png", content=img_buffer.getvalue(), content_type="image/png"
        )

        # Test photo upload
        response = self.client.post(
            reverse("repair:upload_photo", kwargs={"pk": repair_order.pk}),
            {"photo": test_image, "photo_type": "BEFORE", "description": "Test photo description"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        if response.status_code != 200:
            print(f"Response status: {response.status_code}")
            print(f"Response content: {response.content.decode()}")

        self.assertEqual(response.status_code, 200)

        # Verify photo was created
        with tenant_context(self.tenant.id):
            photo = RepairOrderPhoto.objects.filter(repair_order=repair_order).first()
            self.assertIsNotNone(photo)
            self.assertEqual(photo.photo_type, "BEFORE")
            self.assertEqual(photo.description, "Test photo description")

    def test_work_order_generation_view(self):
        """Test work order generation view."""
        # Create multiple repair orders
        with tenant_context(self.tenant.id):
            repair_order1 = RepairOrder.objects.create(
                tenant=self.tenant,
                order_number="REP-WORK-001",
                customer=self.customer,
                item_description="First repair item",
                service_type="CLEANING",
                cost_estimate=Decimal("30.00"),
                estimated_completion=date.today() + timedelta(days=2),
                created_by=self.user,
            )

            repair_order2 = RepairOrder.objects.create(
                tenant=self.tenant,
                order_number="REP-WORK-002",
                customer=self.customer,
                item_description="Second repair item",
                service_type="POLISHING",
                cost_estimate=Decimal("40.00"),
                estimated_completion=date.today() + timedelta(days=3),
                created_by=self.user,
            )

        self.client.force_login(self.user)

        # Test GET request to work order form
        response = self.client.get(reverse("repair:generate_work_order"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Generate Work Order")

        # Test POST request to generate work order
        form_data = {
            "repair_orders": [repair_order1.id, repair_order2.id],
            "craftsman": self.user.id,
            "notes": "Please handle with care",
        }

        response = self.client.post(reverse("repair:generate_work_order"), form_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

        # Verify repair orders were assigned to craftsman
        repair_order1.refresh_from_db()
        repair_order2.refresh_from_db()
        self.assertEqual(repair_order1.assigned_to, self.user)
        self.assertEqual(repair_order2.assigned_to, self.user)

    def test_custom_order_views(self):
        """Test custom order views."""
        self.client.force_login(self.user)

        # Test custom order list view
        response = self.client.get(reverse("repair:custom_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Custom Orders")

        # Test custom order create view
        response = self.client.get(reverse("repair:custom_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "New Custom Order")

        # Test creating custom order
        form_data = {
            "customer": self.customer.id,
            "design_description": "Custom engagement ring with diamond setting",
            "complexity": "COMPLEX",
            "estimated_completion": (date.today() + timedelta(days=30)).isoformat(),
            "quoted_price": "2500.00",
            "deposit_amount": "500.00",
        }

        response = self.client.post(reverse("repair:custom_create"), form_data)
        self.assertEqual(response.status_code, 302)  # Redirect after creation

        # Verify custom order was created
        from apps.repair.models import CustomOrder

        with tenant_context(self.tenant.id):
            custom_order = CustomOrder.objects.filter(
                tenant=self.tenant, customer=self.customer
            ).first()

            self.assertIsNotNone(custom_order)
            self.assertEqual(
                custom_order.design_description, "Custom engagement ring with diamond setting"
            )
            self.assertEqual(custom_order.complexity, "COMPLEX")
            self.assertEqual(custom_order.quoted_price, Decimal("2500.00"))
            self.assertEqual(custom_order.deposit_amount, Decimal("500.00"))

    def test_tenant_isolation_in_views(self):
        """Test that views properly isolate tenant data."""
        # Create another tenant and user
        with bypass_rls():
            other_tenant = Tenant.objects.create(
                company_name="Other Jewelry Shop", slug="other-shop"
            )

            other_user = User.objects.create_user(
                username="otheruser",
                email="other@example.com",
                password="testpass123",
                tenant=other_tenant,
                role="TENANT_OWNER",
            )

        # Create repair order for other tenant
        with tenant_context(other_tenant.id):
            other_customer = Customer.objects.create(
                tenant=other_tenant,
                customer_number="OTHER-001",
                first_name="Jane",
                last_name="Smith",
                email="jane@example.com",
                phone="555-9999",
            )

            other_repair_order = RepairOrder.objects.create(
                tenant=other_tenant,
                order_number="REP-OTHER-001",
                customer=other_customer,
                item_description="Other tenant repair",
                service_type="CLEANING",
                cost_estimate=Decimal("25.00"),
                estimated_completion=date.today() + timedelta(days=1),
                created_by=other_user,
            )

        # Login as first tenant user
        self.client.force_login(self.user)

        # Try to access other tenant's repair order
        response = self.client.get(
            reverse("repair:repair_detail", kwargs={"pk": other_repair_order.pk})
        )
        self.assertEqual(response.status_code, 404)  # Should not be accessible

        # Verify repair list only shows current tenant's orders
        response = self.client.get(reverse("repair:repair_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "REP-OTHER-001")
        self.assertNotContains(response, "Other tenant repair")
