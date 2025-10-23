"""
Tests for repair and custom order models.

Tests cover model creation, FSM transitions, RLS policies, and business logic.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from django_fsm import can_proceed

from apps.core.models import Tenant
from apps.core.tenant_context import bypass_rls, tenant_context
from apps.crm.models import Customer

from .models import CustomOrder, RepairOrder, RepairOrderPhoto

User = get_user_model()


class RepairOrderModelTest(TestCase):
    """Test RepairOrder model functionality."""

    def setUp(self):
        """Set up test data."""
        # Create tenant using RLS bypass (only platform admins can create tenants)
        with bypass_rls():
            self.tenant = Tenant.objects.create(company_name="Test Jewelry Shop", slug="test-shop")

            # Create users
            self.owner = User.objects.create_user(
                username="owner",
                email="owner@test.com",
                password="testpass123",
                tenant=self.tenant,
                role="TENANT_OWNER",
            )

            self.employee = User.objects.create_user(
                username="employee",
                email="employee@test.com",
                password="testpass123",
                tenant=self.tenant,
                role="TENANT_EMPLOYEE",
            )

        # Create customer with tenant context
        with tenant_context(self.tenant.id):
            self.customer = Customer.objects.create(
                tenant=self.tenant,
                customer_number="CUST-001",
                first_name="John",
                last_name="Doe",
                email="john@example.com",
                phone="+1234567890",
            )

    def test_repair_order_creation(self):
        """Test creating a repair order."""
        with tenant_context(self.tenant.id):
            repair_order = RepairOrder.objects.create(
                tenant=self.tenant,
                order_number="REP-001",
                customer=self.customer,
                item_description="Gold ring needs resizing",
                service_type="RESIZING",
                cost_estimate=Decimal("50.00"),
                estimated_completion=date.today() + timedelta(days=7),
                created_by=self.owner,
            )

            self.assertEqual(repair_order.order_number, "REP-001")
            self.assertEqual(repair_order.customer, self.customer)
            self.assertEqual(repair_order.status, "received")
            self.assertEqual(repair_order.service_type, "RESIZING")
            self.assertEqual(repair_order.cost_estimate, Decimal("50.00"))
            self.assertFalse(repair_order.is_overdue)

    def test_repair_order_fsm_transitions(self):
        """Test FSM state transitions."""
        with tenant_context(self.tenant.id):
            repair_order = RepairOrder.objects.create(
                tenant=self.tenant,
                order_number="REP-002",
                customer=self.customer,
                item_description="Chain repair",
                service_type="CHAIN_REPAIR",
                cost_estimate=Decimal("75.00"),
                estimated_completion=date.today() + timedelta(days=5),
                created_by=self.owner,
            )

            # Test initial state
            self.assertEqual(repair_order.status, "received")
            self.assertTrue(can_proceed(repair_order.start_work))

            # Start work
            repair_order.start_work(user=self.employee)
            self.assertEqual(repair_order.status, "in_progress")
            self.assertEqual(repair_order.assigned_to, self.employee)

            # Submit for quality check
            self.assertTrue(can_proceed(repair_order.submit_for_quality_check))
            repair_order.submit_for_quality_check()
            self.assertEqual(repair_order.status, "quality_check")

            # Complete work
            self.assertTrue(can_proceed(repair_order.complete_work))
            repair_order.complete_work()
            self.assertEqual(repair_order.status, "completed")
            self.assertIsNotNone(repair_order.actual_completion)

            # Deliver to customer
            self.assertTrue(can_proceed(repair_order.deliver_to_customer))
            repair_order.deliver_to_customer()
            self.assertEqual(repair_order.status, "delivered")
            self.assertIsNotNone(repair_order.delivered_date)

    def test_repair_order_overdue_logic(self):
        """Test overdue detection logic."""
        with tenant_context(self.tenant.id):
            # Create overdue repair order
            overdue_order = RepairOrder.objects.create(
                tenant=self.tenant,
                order_number="REP-003",
                customer=self.customer,
                item_description="Overdue repair",
                service_type="CLEANING",
                cost_estimate=Decimal("25.00"),
                estimated_completion=date.today() - timedelta(days=2),
                created_by=self.owner,
            )

            self.assertTrue(overdue_order.is_overdue)
            self.assertEqual(overdue_order.days_until_due, -2)

            # Create future repair order
            future_order = RepairOrder.objects.create(
                tenant=self.tenant,
                order_number="REP-004",
                customer=self.customer,
                item_description="Future repair",
                service_type="POLISHING",
                cost_estimate=Decimal("30.00"),
                estimated_completion=date.today() + timedelta(days=3),
                created_by=self.owner,
            )

            self.assertFalse(future_order.is_overdue)
            self.assertEqual(future_order.days_until_due, 3)

    def test_repair_order_cancellation(self):
        """Test repair order cancellation."""
        with tenant_context(self.tenant.id):
            repair_order = RepairOrder.objects.create(
                tenant=self.tenant,
                order_number="REP-005",
                customer=self.customer,
                item_description="To be cancelled",
                service_type="OTHER",
                cost_estimate=Decimal("100.00"),
                estimated_completion=date.today() + timedelta(days=10),
                created_by=self.owner,
            )

            # Can cancel from received state
            self.assertTrue(can_proceed(repair_order.cancel_order))
            repair_order.cancel_order()
            self.assertEqual(repair_order.status, "cancelled")

            # Cannot transition from cancelled state
            self.assertFalse(can_proceed(repair_order.start_work))


class RepairOrderPhotoModelTest(TestCase):
    """Test RepairOrderPhoto model functionality."""

    def setUp(self):
        """Set up test data."""
        # Create tenant using RLS bypass
        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop", slug="test-shop-photo"
            )

            # Create user
            self.user = User.objects.create_user(
                username="photographer",
                email="photo@test.com",
                password="testpass123",
                tenant=self.tenant,
                role="TENANT_EMPLOYEE",
            )

        # Create customer and repair order with tenant context
        with tenant_context(self.tenant.id):
            self.customer = Customer.objects.create(
                tenant=self.tenant,
                customer_number="CUST-001",
                first_name="Jane",
                last_name="Smith",
                email="jane@example.com",
                phone="+1234567890",
            )

            # Create repair order
            self.repair_order = RepairOrder.objects.create(
                tenant=self.tenant,
                order_number="REP-PHOTO-001",
                customer=self.customer,
                item_description="Ring with damage",
                service_type="PRONG_REPAIR",
                cost_estimate=Decimal("80.00"),
                estimated_completion=date.today() + timedelta(days=7),
                created_by=self.user,
            )

    def test_repair_order_photo_creation(self):
        """Test creating repair order photos."""
        with tenant_context(self.tenant.id):
            photo = RepairOrderPhoto.objects.create(
                repair_order=self.repair_order,
                photo_type="BEFORE",
                description="Damage to prongs visible",
                taken_by=self.user,
            )

            self.assertEqual(photo.repair_order, self.repair_order)
            self.assertEqual(photo.photo_type, "BEFORE")
            self.assertEqual(photo.description, "Damage to prongs visible")
            self.assertEqual(photo.taken_by, self.user)
            self.assertIsNotNone(photo.taken_at)


class CustomOrderModelTest(TestCase):
    """Test CustomOrder model functionality."""

    def setUp(self):
        """Set up test data."""
        # Create tenant using RLS bypass
        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop", slug="test-shop-custom"
            )

            # Create users
            self.designer = User.objects.create_user(
                username="designer",
                email="designer@test.com",
                password="testpass123",
                tenant=self.tenant,
                role="TENANT_EMPLOYEE",
            )

            self.craftsman = User.objects.create_user(
                username="craftsman",
                email="craftsman@test.com",
                password="testpass123",
                tenant=self.tenant,
                role="TENANT_EMPLOYEE",
            )

        # Create customer with tenant context
        with tenant_context(self.tenant.id):
            self.customer = Customer.objects.create(
                tenant=self.tenant,
                customer_number="CUST-002",
                first_name="Alice",
                last_name="Johnson",
                email="alice@example.com",
                phone="+1234567890",
            )

    def test_custom_order_creation(self):
        """Test creating a custom order."""
        with tenant_context(self.tenant.id):
            custom_order = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-001",
                customer=self.customer,
                design_description="Custom engagement ring with emerald",
                design_specifications={
                    "metal": "18k white gold",
                    "stone": "2ct emerald",
                    "setting": "cathedral",
                },
                complexity="COMPLEX",
                quoted_price=Decimal("2500.00"),
                deposit_amount=Decimal("500.00"),
                estimated_completion=date.today() + timedelta(days=30),
                created_by=self.designer,
            )

            self.assertEqual(custom_order.order_number, "CUSTOM-001")
            self.assertEqual(custom_order.customer, self.customer)
            self.assertEqual(custom_order.status, "quote_requested")
            self.assertEqual(custom_order.complexity, "COMPLEX")
            self.assertEqual(custom_order.quoted_price, Decimal("2500.00"))
            self.assertEqual(custom_order.deposit_amount, Decimal("500.00"))
            self.assertEqual(custom_order.remaining_balance, Decimal("2000.00"))

    def test_custom_order_fsm_workflow(self):
        """Test custom order FSM workflow."""
        with tenant_context(self.tenant.id):
            custom_order = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-002",
                customer=self.customer,
                design_description="Custom wedding band",
                complexity="MODERATE",
                created_by=self.designer,
            )

            # Initial state
            self.assertEqual(custom_order.status, "quote_requested")

            # Provide quote
            self.assertTrue(can_proceed(custom_order.provide_quote))
            custom_order.provide_quote()
            self.assertEqual(custom_order.status, "quote_provided")

            # Approve quote
            self.assertTrue(can_proceed(custom_order.approve_quote))
            custom_order.approve_quote()
            self.assertEqual(custom_order.status, "approved")

            # Start design
            self.assertTrue(can_proceed(custom_order.start_design))
            custom_order.start_design()
            self.assertEqual(custom_order.status, "in_design")

            # Approve design
            self.assertTrue(can_proceed(custom_order.approve_design))
            custom_order.approve_design()
            self.assertEqual(custom_order.status, "design_approved")

            # Start production
            self.assertTrue(can_proceed(custom_order.start_production))
            custom_order.start_production()
            self.assertEqual(custom_order.status, "in_production")

            # Quality check
            self.assertTrue(can_proceed(custom_order.submit_for_quality_check))
            custom_order.submit_for_quality_check()
            self.assertEqual(custom_order.status, "quality_check")

            # Complete order
            self.assertTrue(can_proceed(custom_order.complete_order))
            custom_order.complete_order()
            self.assertEqual(custom_order.status, "completed")
            self.assertIsNotNone(custom_order.actual_completion)

            # Deliver
            self.assertTrue(can_proceed(custom_order.deliver_to_customer))
            custom_order.deliver_to_customer()
            self.assertEqual(custom_order.status, "delivered")
            self.assertIsNotNone(custom_order.delivered_date)

    def test_custom_order_pricing_logic(self):
        """Test custom order pricing calculations."""
        with tenant_context(self.tenant.id):
            custom_order = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-003",
                customer=self.customer,
                design_description="Simple pendant",
                complexity="SIMPLE",
                quoted_price=Decimal("800.00"),
                deposit_amount=Decimal("200.00"),
                created_by=self.designer,
            )

            # Test remaining balance calculation
            self.assertEqual(custom_order.remaining_balance, Decimal("600.00"))

            # Update final price
            custom_order.final_price = Decimal("850.00")
            custom_order.save()

            # Remaining balance should use final price
            self.assertEqual(custom_order.remaining_balance, Decimal("650.00"))


class RepairOrderRLSTest(TestCase):
    """Test Row-Level Security for repair orders."""

    def test_rls_policies_exist(self):
        """Test that RLS policies are properly configured."""
        from django.db import connection

        with connection.cursor() as cursor:
            # Check that RLS is enabled on repair tables
            cursor.execute(
                """
                SELECT tablename, rowsecurity
                FROM pg_tables
                WHERE tablename IN ('repair_orders', 'custom_orders', 'repair_order_photos')
                AND schemaname = 'public'
            """
            )

            tables = cursor.fetchall()
            self.assertEqual(len(tables), 3)

            # All tables should have RLS enabled
            for table_name, rls_enabled in tables:
                self.assertTrue(rls_enabled, f"RLS not enabled on {table_name}")

            # Check that tenant isolation policies exist
            cursor.execute(
                """
                SELECT tablename, policyname
                FROM pg_policies
                WHERE tablename IN ('repair_orders', 'custom_orders', 'repair_order_photos')
                AND policyname = 'tenant_isolation_policy'
            """
            )

            policies = cursor.fetchall()
            self.assertEqual(len(policies), 3, "Missing tenant isolation policies")

    def test_model_tenant_relationships(self):
        """Test that models have proper tenant relationships."""
        # Test RepairOrder has tenant FK
        repair_order_tenant_field = RepairOrder._meta.get_field("tenant")
        self.assertEqual(repair_order_tenant_field.related_model.__name__, "Tenant")

        # Test CustomOrder has tenant FK
        custom_order_tenant_field = CustomOrder._meta.get_field("tenant")
        self.assertEqual(custom_order_tenant_field.related_model.__name__, "Tenant")

        # Test RepairOrderPhoto is linked through repair_order
        photo_repair_field = RepairOrderPhoto._meta.get_field("repair_order")
        self.assertEqual(photo_repair_field.related_model, RepairOrder)
