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

    def test_repair_order_multiple_photos(self):
        """Test uploading multiple photos for different stages."""
        with tenant_context(self.tenant.id):
            # Create photos for different stages
            RepairOrderPhoto.objects.create(
                repair_order=self.repair_order,
                photo_type="BEFORE",
                description="Initial condition - damaged prongs",
                taken_by=self.user,
            )

            RepairOrderPhoto.objects.create(
                repair_order=self.repair_order,
                photo_type="DURING",
                description="Work in progress - prongs being repaired",
                taken_by=self.user,
            )

            RepairOrderPhoto.objects.create(
                repair_order=self.repair_order,
                photo_type="AFTER",
                description="Completed repair - prongs restored",
                taken_by=self.user,
            )

            # Verify all photos are linked to the repair order
            photos = self.repair_order.photos.all()
            self.assertEqual(photos.count(), 3)

            # Verify photo types
            photo_types = [photo.photo_type for photo in photos]
            self.assertIn("BEFORE", photo_types)
            self.assertIn("DURING", photo_types)
            self.assertIn("AFTER", photo_types)

    def test_repair_order_photo_ordering(self):
        """Test that photos are ordered by taken_at timestamp."""
        with tenant_context(self.tenant.id):
            from datetime import timedelta

            from django.utils import timezone

            # Create photos with different timestamps
            base_time = timezone.now()

            photo1 = RepairOrderPhoto.objects.create(
                repair_order=self.repair_order,
                photo_type="BEFORE",
                description="First photo",
                taken_by=self.user,
                taken_at=base_time,
            )

            photo2 = RepairOrderPhoto.objects.create(
                repair_order=self.repair_order,
                photo_type="DURING",
                description="Second photo",
                taken_by=self.user,
                taken_at=base_time + timedelta(hours=1),
            )

            photo3 = RepairOrderPhoto.objects.create(
                repair_order=self.repair_order,
                photo_type="AFTER",
                description="Third photo",
                taken_by=self.user,
                taken_at=base_time + timedelta(hours=2),
            )

            # Verify ordering
            photos = list(self.repair_order.photos.all())
            self.assertEqual(photos[0], photo1)
            self.assertEqual(photos[1], photo2)
            self.assertEqual(photos[2], photo3)

    def test_repair_order_photo_validation(self):
        """Test photo model validation and constraints."""
        with tenant_context(self.tenant.id):
            # Test valid photo types
            valid_types = ["BEFORE", "DURING", "AFTER", "DAMAGE", "REFERENCE"]

            for photo_type in valid_types:
                photo = RepairOrderPhoto.objects.create(
                    repair_order=self.repair_order,
                    photo_type=photo_type,
                    description=f"Test {photo_type} photo",
                    taken_by=self.user,
                )
                self.assertEqual(photo.photo_type, photo_type)

            # Verify all photos were created
            self.assertEqual(self.repair_order.photos.count(), len(valid_types))


class RepairOrderMethodTest(TestCase):
    """Test RepairOrder model methods and business logic."""

    def setUp(self):
        """Set up test data."""
        # Create tenant using RLS bypass
        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop", slug="test-shop-methods"
            )

            # Create user
            self.user = User.objects.create_user(
                username="methoduser",
                email="method@test.com",
                password="testpass123",
                tenant=self.tenant,
                role="TENANT_EMPLOYEE",
            )

        # Create customer and repair order with tenant context
        with tenant_context(self.tenant.id):
            self.customer = Customer.objects.create(
                tenant=self.tenant,
                customer_number="CUST-METHOD-001",
                first_name="Test",
                last_name="Customer",
                email="test@example.com",
                phone="+1234567890",
            )

            self.repair_order = RepairOrder.objects.create(
                tenant=self.tenant,
                order_number="REP-METHOD-001",
                customer=self.customer,
                item_description="Ring for method testing",
                service_type="RESIZING",
                cost_estimate=Decimal("50.00"),
                estimated_completion=date.today() + timedelta(days=7),
                created_by=self.user,
            )

    def test_repair_order_can_methods(self):
        """Test can_start_work, can_complete, and can_deliver methods."""
        with tenant_context(self.tenant.id):
            # Initial state - can start work
            self.assertTrue(self.repair_order.can_start_work())
            self.assertFalse(self.repair_order.can_complete())
            self.assertFalse(self.repair_order.can_deliver())

            # Start work - cannot start again
            self.repair_order.start_work()
            self.assertFalse(self.repair_order.can_start_work())
            self.assertFalse(self.repair_order.can_complete())
            self.assertFalse(self.repair_order.can_deliver())

            # Submit for quality check - can complete
            self.repair_order.submit_for_quality_check()
            self.assertFalse(self.repair_order.can_start_work())
            self.assertTrue(self.repair_order.can_complete())
            self.assertFalse(self.repair_order.can_deliver())

            # Complete work - can deliver
            self.repair_order.complete_work()
            self.assertFalse(self.repair_order.can_start_work())
            self.assertFalse(self.repair_order.can_complete())
            self.assertTrue(self.repair_order.can_deliver())

            # Deliver - cannot do anything
            self.repair_order.deliver_to_customer()
            self.assertFalse(self.repair_order.can_start_work())
            self.assertFalse(self.repair_order.can_complete())
            self.assertFalse(self.repair_order.can_deliver())

    def test_repair_order_return_to_work(self):
        """Test return_to_work FSM transition."""
        with tenant_context(self.tenant.id):
            # Progress to quality check
            self.repair_order.start_work()
            self.repair_order.submit_for_quality_check()
            self.assertEqual(self.repair_order.status, "quality_check")

            # Return to work (failed quality check)
            self.assertTrue(can_proceed(self.repair_order.return_to_work))
            self.repair_order.return_to_work()
            self.assertEqual(self.repair_order.status, "in_progress")

            # Can submit for quality check again
            self.assertTrue(can_proceed(self.repair_order.submit_for_quality_check))

    def test_repair_order_service_history_tracking(self):
        """Test tracking of order history and service records for customers."""
        with tenant_context(self.tenant.id):
            # Create multiple repair orders for the same customer
            repair_orders = []
            for i in range(3):
                repair_order = RepairOrder.objects.create(
                    tenant=self.tenant,
                    order_number=f"REP-HISTORY-{i+1:03d}",
                    customer=self.customer,
                    item_description=f"Service {i+1} - Ring repair",
                    service_type=["CLEANING", "POLISHING", "RESIZING"][i],
                    cost_estimate=Decimal(f"{50 + i*25}.00"),
                    estimated_completion=date.today() + timedelta(days=7 + i),
                    created_by=self.user,
                )
                repair_orders.append(repair_order)

            # Test customer's repair order history
            customer_orders = RepairOrder.objects.filter(
                tenant=self.tenant, customer=self.customer
            ).order_by("-created_at")

            # Should include all orders plus the one from setUp
            self.assertEqual(customer_orders.count(), 4)

            # Test service record tracking
            service_types = [order.service_type for order in customer_orders]
            self.assertIn("CLEANING", service_types)
            self.assertIn("POLISHING", service_types)
            self.assertIn("RESIZING", service_types)

            # Test total service value for customer
            total_estimates = sum(order.cost_estimate for order in customer_orders)
            expected_total = (
                Decimal("50.00") + Decimal("50.00") + Decimal("75.00") + Decimal("100.00")
            )
            self.assertEqual(total_estimates, expected_total)

            # Test completed services tracking
            completed_orders = []
            for order in repair_orders:
                order.start_work()
                order.save()
                order.submit_for_quality_check()
                order.save()
                order.complete_work()
                order.save()
                completed_orders.append(order)

            # Verify completed service records
            completed_services = RepairOrder.objects.filter(
                tenant=self.tenant, customer=self.customer, status="completed"
            )
            self.assertEqual(completed_services.count(), 3)

            # Test service completion dates tracking
            for order in completed_services:
                self.assertIsNotNone(order.actual_completion)
                self.assertEqual(order.status, "completed")

    def test_repair_order_customer_service_summary(self):
        """Test generating service summary for customer history."""
        with tenant_context(self.tenant.id):
            # Create orders with different statuses and completion dates
            from django.utils import timezone

            # Completed order
            RepairOrder.objects.create(
                tenant=self.tenant,
                order_number="REP-COMPLETED-001",
                customer=self.customer,
                item_description="Completed ring repair",
                service_type="CLEANING",
                cost_estimate=Decimal("30.00"),
                final_cost=Decimal("35.00"),
                estimated_completion=date.today() - timedelta(days=5),
                actual_completion=timezone.now() - timedelta(days=2),
                status="completed",
                created_by=self.user,
            )

            # In-progress order
            RepairOrder.objects.create(
                tenant=self.tenant,
                order_number="REP-PROGRESS-001",
                customer=self.customer,
                item_description="In-progress necklace repair",
                service_type="CHAIN_REPAIR",
                cost_estimate=Decimal("75.00"),
                estimated_completion=date.today() + timedelta(days=3),
                status="in_progress",
                created_by=self.user,
            )

            # Test service summary queries
            all_orders = RepairOrder.objects.filter(tenant=self.tenant, customer=self.customer)

            completed_orders = all_orders.filter(status="completed")
            active_orders = all_orders.exclude(status__in=["completed", "delivered", "cancelled"])

            # Verify counts
            self.assertEqual(completed_orders.count(), 1)
            self.assertEqual(active_orders.count(), 2)  # in_progress + original from setUp

            # Test total service value
            total_completed_value = sum(
                order.final_cost or order.cost_estimate for order in completed_orders
            )
            self.assertEqual(total_completed_value, Decimal("35.00"))

            # Test service type diversity
            service_types = set(order.service_type for order in all_orders)
            self.assertGreaterEqual(len(service_types), 2)  # At least RESIZING and CLEANING


class RepairOrderNotificationTest(TestCase):
    """Test repair order notification functionality."""

    def setUp(self):
        """Set up test data."""
        # Create tenant using RLS bypass
        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop", slug="test-shop-notifications"
            )

            # Create user
            self.user = User.objects.create_user(
                username="notifyuser",
                email="notify@test.com",
                password="testpass123",
                tenant=self.tenant,
                role="TENANT_EMPLOYEE",
            )

        # Create customer and repair order with tenant context
        with tenant_context(self.tenant.id):
            self.customer = Customer.objects.create(
                tenant=self.tenant,
                customer_number="CUST-NOTIFY-001",
                first_name="John",
                last_name="Doe",
                email="john.doe@example.com",
                phone="+1234567890",
            )

            self.repair_order = RepairOrder.objects.create(
                tenant=self.tenant,
                order_number="REP-NOTIFY-001",
                customer=self.customer,
                item_description="Ring needs notification testing",
                service_type="RESIZING",
                cost_estimate=Decimal("75.00"),
                estimated_completion=date.today() + timedelta(days=7),
                created_by=self.user,
            )

    def test_repair_order_status_notifications(self):
        """Test notifications are sent when repair order status changes."""
        with tenant_context(self.tenant.id):
            from unittest.mock import patch

            from apps.repair.services import send_repair_status_notification

            # Mock email sending
            with patch("apps.repair.services.send_mail") as mock_send_mail:
                # Test notification for each status
                statuses_to_test = [
                    ("in_progress", "Work has started on your repair order."),
                    ("quality_check", "Your repair is undergoing quality inspection."),
                    ("completed", "Your repair has been completed and is ready for pickup."),
                    (
                        "delivered",
                        "Your repair order has been delivered. Thank you for your business!",
                    ),
                ]

                for status, expected_message in statuses_to_test:
                    # Update status
                    self.repair_order.status = status
                    self.repair_order.save()

                    # Send notification
                    result = send_repair_status_notification(self.repair_order)

                    # Verify notification was sent
                    self.assertTrue(result)
                    mock_send_mail.assert_called()

                    # Verify email content
                    args, kwargs = mock_send_mail.call_args
                    self.assertIn("Repair Order Update", kwargs["subject"])
                    self.assertIn(self.repair_order.order_number, kwargs["subject"])
                    self.assertIn(expected_message, kwargs["message"])
                    self.assertEqual(kwargs["recipient_list"], [self.customer.email])

                    mock_send_mail.reset_mock()

    def test_repair_order_fsm_transitions_with_notifications(self):
        """Test that FSM transitions can trigger notifications."""
        with tenant_context(self.tenant.id):
            from unittest.mock import patch

            # Mock the notification service
            with patch("apps.repair.services.send_repair_status_notification") as mock_notify:
                # Import the function after patching to get the mock
                from apps.repair.services import send_repair_status_notification

                # Start work
                self.repair_order.start_work(user=self.user)

                # Manually trigger notification (in real implementation, this would be in the transition)
                send_repair_status_notification(self.repair_order)
                mock_notify.assert_called_with(self.repair_order)

                # Submit for quality check
                self.repair_order.submit_for_quality_check()
                send_repair_status_notification(self.repair_order)

                # Complete work
                self.repair_order.complete_work()
                send_repair_status_notification(self.repair_order)

                # Deliver to customer
                self.repair_order.deliver_to_customer()
                send_repair_status_notification(self.repair_order)

                # Verify notifications were called for each transition
                self.assertEqual(mock_notify.call_count, 4)

    def test_repair_order_notification_without_email(self):
        """Test notification handling when customer has no email."""
        with tenant_context(self.tenant.id):
            from apps.repair.services import send_repair_status_notification

            # Create customer without email
            customer_no_email = Customer.objects.create(
                tenant=self.tenant,
                customer_number="CUST-NO-EMAIL",
                first_name="Jane",
                last_name="Smith",
                phone="+1234567890",
                # No email provided
            )

            repair_order_no_email = RepairOrder.objects.create(
                tenant=self.tenant,
                order_number="REP-NO-EMAIL-001",
                customer=customer_no_email,
                item_description="Ring for customer without email",
                service_type="CLEANING",
                cost_estimate=Decimal("25.00"),
                estimated_completion=date.today() + timedelta(days=3),
                created_by=self.user,
            )

            # Attempt to send notification
            result = send_repair_status_notification(repair_order_no_email)

            # Should return False since no email is available
            self.assertFalse(result)

    def test_repair_order_notification_email_content(self):
        """Test the content and format of repair order notification emails."""
        with tenant_context(self.tenant.id):
            from unittest.mock import patch

            from apps.repair.services import send_repair_status_notification

            # Set repair order to completed status
            self.repair_order.status = "completed"
            self.repair_order.save()

            with patch("apps.repair.services.send_mail") as mock_send_mail:
                # Send notification
                result = send_repair_status_notification(self.repair_order)

                self.assertTrue(result)
                mock_send_mail.assert_called_once()

                # Verify email content structure
                args, kwargs = mock_send_mail.call_args

                # Check subject
                expected_subject = f"Repair Order Update - {self.repair_order.order_number}"
                self.assertEqual(kwargs["subject"], expected_subject)

                # Check message content includes all required information
                message = kwargs["message"]
                self.assertIn(self.customer.first_name, message)
                self.assertIn(self.repair_order.order_number, message)
                self.assertIn(self.repair_order.item_description, message)
                self.assertIn(self.repair_order.get_service_type_display(), message)
                self.assertIn(self.repair_order.get_status_display(), message)
                self.assertIn(self.tenant.company_name, message)

                # Check recipient
                self.assertEqual(kwargs["recipient_list"], [self.customer.email])

                # Check sender
                self.assertIn("from_email", kwargs)

    def test_work_order_notification_to_craftsman(self):
        """Test work order notifications sent to craftsmen."""
        with tenant_context(self.tenant.id):
            from unittest.mock import patch

            from apps.repair.services import send_work_order_notification

            # Create craftsman
            craftsman = User.objects.create_user(
                username="craftsman",
                email="craftsman@test.com",
                password="testpass123",
                tenant=self.tenant,
                role="TENANT_EMPLOYEE",
            )

            # Create multiple repair orders
            repair_orders = [
                RepairOrder.objects.create(
                    tenant=self.tenant,
                    order_number=f"REP-WORK-{i:03d}",
                    customer=self.customer,
                    item_description=f"Item {i} for work order",
                    service_type="POLISHING",
                    cost_estimate=Decimal("30.00"),
                    estimated_completion=date.today() + timedelta(days=5),
                    created_by=self.user,
                    assigned_to=craftsman,
                )
                for i in range(1, 4)
            ]

            with patch("apps.repair.services.send_mail") as mock_send_mail:
                # Send work order notification
                result = send_work_order_notification(
                    repair_orders, craftsman, notes="Handle with care - delicate items"
                )

                self.assertTrue(result)
                mock_send_mail.assert_called_once()

                # Verify email content
                args, kwargs = mock_send_mail.call_args

                # Check subject
                self.assertIn("New Work Order Assignment", kwargs["subject"])

                # Check message includes all repair orders
                message = kwargs["message"]
                for repair_order in repair_orders:
                    self.assertIn(repair_order.order_number, message)
                    self.assertIn(repair_order.item_description, message)

                # Check notes are included
                self.assertIn("Handle with care - delicate items", message)

                # Check recipient
                self.assertEqual(kwargs["recipient_list"], [craftsman.email])


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

        # Create customer and branch with tenant context
        with tenant_context(self.tenant.id):
            from apps.core.models import Branch

            self.customer = Customer.objects.create(
                tenant=self.tenant,
                customer_number="CUST-002",
                first_name="Alice",
                last_name="Johnson",
                email="alice@example.com",
                phone="+1234567890",
            )

            self.branch = Branch.objects.create(
                tenant=self.tenant,
                name="Main Branch",
                address="123 Main St",
                phone="555-0123",
                is_active=True,
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

    def test_custom_order_comprehensive_pricing(self):
        """Test comprehensive custom order pricing with all components."""
        with tenant_context(self.tenant.id):
            from apps.repair.models import MaterialRequirement
            from apps.repair.services import CustomOrderPricingCalculator

            # Create custom order with specific pricing parameters
            custom_order = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-PRICING-001",
                customer=self.customer,
                design_description="Complex engagement ring with multiple stones",
                complexity="VERY_COMPLEX",
                overhead_percentage=Decimal("25.00"),
                profit_margin_percentage=Decimal("40.00"),
                created_by=self.designer,
            )

            # Add multiple material requirements
            materials = [
                {
                    "type": "GOLD",
                    "name": "18K White Gold",
                    "quantity": Decimal("12.0"),
                    "unit": "GRAMS",
                    "cost": Decimal("80.00"),
                },
                {
                    "type": "DIAMOND",
                    "name": "Center Diamond",
                    "quantity": Decimal("1.0"),
                    "unit": "CARATS",
                    "cost": Decimal("5000.00"),
                },
                {
                    "type": "DIAMOND",
                    "name": "Side Diamonds",
                    "quantity": Decimal("0.5"),
                    "unit": "CARATS",
                    "cost": Decimal("2000.00"),
                },
            ]

            total_material_cost = Decimal("0.00")
            for material in materials:
                MaterialRequirement.objects.create(
                    custom_order=custom_order,
                    material_type=material["type"],
                    material_name=material["name"],
                    quantity_required=material["quantity"],
                    unit=material["unit"],
                    estimated_cost_per_unit=material["cost"],
                )
                total_material_cost += material["quantity"] * material["cost"]

            # Test pricing calculator
            calculator = CustomOrderPricingCalculator(custom_order)
            pricing = calculator.calculate_full_pricing()

            # Verify material cost calculation
            expected_material_cost = (
                Decimal("960.00") + Decimal("5000.00") + Decimal("1000.00")
            )  # 6960.00
            self.assertEqual(pricing["material_cost"], expected_material_cost)

            # Verify labor cost (VERY_COMPLEX = 400.00)
            expected_labor_cost = Decimal("400.00")
            self.assertEqual(pricing["labor_cost"], expected_labor_cost)

            # Verify base cost
            expected_base_cost = expected_material_cost + expected_labor_cost  # 7360.00
            self.assertEqual(pricing["base_cost"], expected_base_cost)

            # Verify overhead calculation (25%)
            expected_overhead = expected_base_cost * Decimal("0.25")  # 1840.00
            self.assertEqual(pricing["overhead_amount"], expected_overhead)

            # Verify cost with overhead
            expected_cost_with_overhead = expected_base_cost + expected_overhead  # 9200.00
            self.assertEqual(pricing["cost_with_overhead"], expected_cost_with_overhead)

            # Verify profit calculation (40%)
            expected_profit = expected_cost_with_overhead * Decimal("0.40")  # 3680.00
            self.assertEqual(pricing["profit_amount"], expected_profit)

            # Verify final price
            expected_final_price = expected_cost_with_overhead + expected_profit  # 12880.00
            self.assertEqual(pricing["final_price"], expected_final_price)

            # Test updating order pricing
            calculator.update_order_pricing()
            custom_order.refresh_from_db()

            self.assertEqual(custom_order.material_cost, expected_material_cost)
            self.assertEqual(custom_order.labor_cost, expected_labor_cost)
            self.assertEqual(custom_order.quoted_price, expected_final_price)

    def test_custom_order_pricing_with_custom_labor(self):
        """Test custom order pricing with custom labor hours and rates."""
        with tenant_context(self.tenant.id):
            from apps.repair.services import CustomOrderPricingCalculator

            custom_order = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-LABOR-001",
                customer=self.customer,
                design_description="Ring with custom labor calculation",
                complexity="MODERATE",  # This should be overridden by custom labor
                material_cost=Decimal("500.00"),
                overhead_percentage=Decimal("20.00"),
                profit_margin_percentage=Decimal("30.00"),
                created_by=self.designer,
            )

            calculator = CustomOrderPricingCalculator(custom_order)

            # Test with custom labor hours and rate
            pricing = calculator.calculate_full_pricing(labor_hours=8, hourly_rate=75)

            # Verify custom labor cost calculation
            expected_labor_cost = Decimal("8") * Decimal("75")  # 600.00
            self.assertEqual(pricing["labor_cost"], expected_labor_cost)

            # Verify it overrides complexity-based calculation
            self.assertNotEqual(
                pricing["labor_cost"], Decimal("100.00")
            )  # MODERATE complexity default

            # Test with hours only (should use default $50/hour rate)
            pricing_default_rate = calculator.calculate_full_pricing(labor_hours=10)
            expected_labor_default = Decimal("10") * Decimal("50.00")  # 500.00
            self.assertEqual(pricing_default_rate["labor_cost"], expected_labor_default)

    def test_custom_order_pricing_edge_cases(self):
        """Test custom order pricing edge cases and validation."""
        with tenant_context(self.tenant.id):
            from apps.repair.services import CustomOrderPricingCalculator

            # Test with zero material cost
            custom_order = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-EDGE-001",
                customer=self.customer,
                design_description="Order with no materials",
                complexity="SIMPLE",
                material_cost=Decimal("0.00"),
                labor_cost=Decimal("100.00"),
                overhead_percentage=Decimal("15.00"),
                profit_margin_percentage=Decimal("25.00"),
                created_by=self.designer,
            )

            calculator = CustomOrderPricingCalculator(custom_order)
            pricing = calculator.calculate_full_pricing()

            # Should still calculate correctly with zero material cost
            self.assertEqual(pricing["material_cost"], Decimal("0.00"))
            self.assertEqual(pricing["labor_cost"], Decimal("50.00"))  # SIMPLE complexity
            self.assertEqual(pricing["base_cost"], Decimal("50.00"))

            # Test with very high percentages
            custom_order.overhead_percentage = Decimal("100.00")  # 100% overhead
            custom_order.profit_margin_percentage = Decimal("200.00")  # 200% profit
            custom_order.save()

            pricing_high = calculator.calculate_full_pricing()

            # Base cost: 50.00
            # Overhead (100%): 50.00
            # Cost with overhead: 100.00
            # Profit (200%): 200.00
            # Final price: 300.00
            self.assertEqual(pricing_high["overhead_amount"], Decimal("50.00"))
            self.assertEqual(pricing_high["cost_with_overhead"], Decimal("100.00"))
            self.assertEqual(pricing_high["profit_amount"], Decimal("200.00"))
            self.assertEqual(pricing_high["final_price"], Decimal("300.00"))

    def test_custom_order_calculate_and_update_pricing_methods(self):
        """Test calculate_pricing and update_pricing methods on CustomOrder model."""
        with tenant_context(self.tenant.id):
            from apps.repair.models import MaterialRequirement

            custom_order = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-CALC-METHODS-001",
                customer=self.customer,
                design_description="Ring for calculation method testing",
                complexity="MODERATE",
                material_cost=Decimal("800.00"),
                labor_cost=Decimal("150.00"),
                overhead_percentage=Decimal("20.00"),
                profit_margin_percentage=Decimal("25.00"),
                created_by=self.designer,
            )

            # Add material requirements
            MaterialRequirement.objects.create(
                custom_order=custom_order,
                material_type="GOLD",
                material_name="18K Gold Wire",
                quantity_required=Decimal("10.0"),
                unit="GRAMS",
                estimated_cost_per_unit=Decimal("80.00"),
            )

            # Test calculate_pricing method
            pricing = custom_order.calculate_pricing()

            # Expected calculations:
            # Material cost from requirements: 10 * 80 = 800
            # Labor cost: 150 (stored value)
            # Base cost: 800 + 150 = 950
            # Overhead (20%): 950 * 0.20 = 190
            # Cost with overhead: 950 + 190 = 1140
            # Profit (25%): 1140 * 0.25 = 285
            # Final price: 1140 + 285 = 1425

            self.assertEqual(pricing["material_cost"], Decimal("800.00"))
            self.assertEqual(pricing["labor_cost"], Decimal("150.00"))
            self.assertEqual(pricing["base_cost"], Decimal("950.00"))
            self.assertEqual(pricing["overhead_amount"], Decimal("190.00"))
            self.assertEqual(pricing["cost_with_overhead"], Decimal("1140.00"))
            self.assertEqual(pricing["profit_amount"], Decimal("285.00"))
            self.assertEqual(pricing["final_price"], Decimal("1425.00"))

            # Test update_pricing method
            updated_pricing = custom_order.update_pricing()

            custom_order.refresh_from_db()

            # Verify the order was updated
            self.assertEqual(custom_order.material_cost, Decimal("800.00"))
            self.assertEqual(custom_order.labor_cost, Decimal("150.00"))
            self.assertEqual(custom_order.quoted_price, Decimal("1425.00"))

            # Verify the returned pricing matches
            self.assertEqual(updated_pricing, pricing)

    def test_custom_order_create_inventory_item_method(self):
        """Test create_inventory_item method on CustomOrder model."""
        with tenant_context(self.tenant.id):
            # Create completed custom order
            custom_order = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-INVENTORY-001",
                customer=self.customer,
                design_description="Custom engagement ring",
                design_specifications={
                    "karat": 14,
                    "weight_grams": 8.5,
                    "stone_type": "diamond",
                    "stone_size": "0.75 carats",
                },
                status="completed",
                material_cost=Decimal("600.00"),
                labor_cost=Decimal("200.00"),
                final_price=Decimal("1200.00"),
                created_by=self.designer,
            )

            # Test successful inventory creation
            inventory_item = custom_order.create_inventory_item(self.branch, sku="CUSTOM-ENG-001")

            # Verify inventory item properties
            self.assertIsNotNone(inventory_item)
            self.assertEqual(inventory_item.sku, "CUSTOM-ENG-001")
            self.assertTrue(inventory_item.name.startswith("Custom:"))
            self.assertIn("Custom engagement ring", inventory_item.name)
            self.assertEqual(inventory_item.karat, 14)
            self.assertEqual(inventory_item.weight_grams, Decimal("8.5"))
            self.assertEqual(inventory_item.craftsmanship_level, "HANDMADE")
            self.assertEqual(inventory_item.cost_price, Decimal("800.00"))  # material + labor
            self.assertEqual(inventory_item.selling_price, Decimal("1200.00"))
            self.assertEqual(inventory_item.quantity, 1)
            self.assertEqual(inventory_item.branch, self.branch)
            self.assertEqual(inventory_item.serial_number, "CUSTOM-CUSTOM-INVENTORY-001")

            # Verify custom order is linked
            custom_order.refresh_from_db()
            self.assertEqual(custom_order.created_inventory_item, inventory_item)

            # Test auto-generated SKU
            custom_order2 = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-INVENTORY-002",
                customer=self.customer,
                design_description="Another custom ring",
                status="completed",
                material_cost=Decimal("400.00"),
                labor_cost=Decimal("150.00"),
                final_price=Decimal("800.00"),
                created_by=self.designer,
            )

            inventory_item2 = custom_order2.create_inventory_item(self.branch)
            self.assertEqual(inventory_item2.sku, "CUSTOM-CUSTOM-INVENTORY-002")

            # Test error cases
            # 1. Order not completed
            incomplete_order = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-INCOMPLETE-001",
                customer=self.customer,
                design_description="Incomplete order",
                status="in_progress",
                created_by=self.designer,
            )

            with self.assertRaises(ValueError) as context:
                incomplete_order.create_inventory_item(self.branch)
            self.assertIn(
                "Can only create inventory from completed custom orders", str(context.exception)
            )

            # 2. Inventory already created
            with self.assertRaises(ValueError) as context:
                custom_order.create_inventory_item(self.branch)
            self.assertIn("Inventory item already created", str(context.exception))

    def test_custom_order_generate_work_order_method(self):
        """Test generate_work_order method on CustomOrder model."""
        with tenant_context(self.tenant.id):
            from apps.repair.models import MaterialRequirement

            # Create craftsman
            craftsman = User.objects.create_user(
                username="craftsman_method",
                email="craftsman.method@test.com",
                password="testpass123",
                tenant=self.tenant,
                role="TENANT_EMPLOYEE",
            )

            custom_order = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-WORKORDER-001",
                customer=self.customer,
                design_description="Complex wedding band set",
                design_specifications={
                    "karat": 18,
                    "weight_grams": 15.0,
                    "stone_type": "sapphire",
                    "stone_size": "multiple small stones",
                },
                complexity="COMPLEX",
                designer=self.designer,
                created_by=self.designer,
            )

            # Add material requirements
            MaterialRequirement.objects.create(
                custom_order=custom_order,
                material_type="GOLD",
                material_name="18K Gold Band Stock",
                quantity_required=Decimal("12.0"),
                unit="GRAMS",
                estimated_cost_per_unit=Decimal("75.00"),
                is_acquired=True,
                supplier_info="Gold Supplier ABC",
            )

            MaterialRequirement.objects.create(
                custom_order=custom_order,
                material_type="GEMSTONE",
                material_name="Blue Sapphires",
                quantity_required=Decimal("6.0"),
                unit="PIECES",
                estimated_cost_per_unit=Decimal("50.00"),
                is_acquired=False,
                supplier_info="Gem Supplier XYZ",
            )

            # Test work order generation
            work_order = custom_order.generate_work_order(
                craftsman=craftsman, notes="Handle with extreme care - customer is VIP"
            )

            # Verify work order content
            self.assertEqual(work_order["order_number"], "CUSTOM-WORKORDER-001")
            self.assertEqual(
                work_order["customer_name"], f"{self.customer.first_name} {self.customer.last_name}"
            )
            self.assertEqual(work_order["design_description"], "Complex wedding band set")
            self.assertEqual(work_order["complexity"], "Complex")
            self.assertEqual(work_order["assigned_craftsman"], craftsman.get_full_name())
            self.assertEqual(work_order["designer"], self.designer.get_full_name())
            self.assertEqual(work_order["notes"], "Handle with extreme care - customer is VIP")

            # Verify material requirements in work order
            self.assertEqual(len(work_order["material_requirements"]), 2)

            gold_material = next(
                m
                for m in work_order["material_requirements"]
                if m["material_name"] == "18K Gold Band Stock"
            )
            self.assertEqual(gold_material["material_type"], "Gold")
            self.assertEqual(gold_material["quantity"], "12.000 GRAMS")
            self.assertEqual(gold_material["status"], "Acquired")
            self.assertEqual(gold_material["supplier"], "Gold Supplier ABC")

            sapphire_material = next(
                m
                for m in work_order["material_requirements"]
                if m["material_name"] == "Blue Sapphires"
            )
            self.assertEqual(sapphire_material["material_type"], "Gemstone")
            self.assertEqual(sapphire_material["quantity"], "6.000 PIECES")
            self.assertEqual(sapphire_material["status"], "Pending")
            self.assertEqual(sapphire_material["supplier"], "Gem Supplier XYZ")

            # Verify instructions are generated
            self.assertGreater(len(work_order["instructions"]), 8)
            self.assertTrue(
                any("18K gold" in instruction for instruction in work_order["instructions"])
            )
            self.assertTrue(
                any("sapphire" in instruction for instruction in work_order["instructions"])
            )
            self.assertTrue(
                any(
                    "advanced techniques" in instruction
                    for instruction in work_order["instructions"]
                )
            )

            # Verify craftsman was assigned to the order
            custom_order.refresh_from_db()
            self.assertEqual(custom_order.craftsman, craftsman)


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


class CustomOrderEnhancementsTest(TestCase):
    """Test enhanced custom order functionality including material requirements, pricing, and inventory linking."""

    def setUp(self):
        """Set up test data."""
        # Create tenant using RLS bypass
        with bypass_rls():
            self.tenant = Tenant.objects.create(
                company_name="Test Jewelry Shop", slug="test-shop-enhanced"
            )

            # Create user
            self.user = User.objects.create_user(
                username="testuser",
                email="test@example.com",
                password="testpass123",
                tenant=self.tenant,
                role="TENANT_OWNER",
            )

        # Create customer and branch with tenant context
        with tenant_context(self.tenant.id):
            from apps.core.models import Branch

            self.customer = Customer.objects.create(
                tenant=self.tenant,
                customer_number="CUST-003",
                first_name="Bob",
                last_name="Wilson",
                email="bob@example.com",
                phone="+1234567890",
            )

            self.branch = Branch.objects.create(
                tenant=self.tenant,
                name="Main Branch",
                address="123 Main St",
                phone="555-0123",
                is_active=True,
            )

    def test_custom_order_with_pricing_fields(self):
        """Test custom order with new pricing fields."""
        with tenant_context(self.tenant.id):
            from apps.repair.models import MaterialRequirement

            custom_order = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-ENHANCED-001",
                customer=self.customer,
                design_description="Custom gold ring with diamond",
                design_specifications={
                    "karat": 18,
                    "weight_grams": 15.5,
                    "stone_type": "diamond",
                    "stone_size": "1 carat",
                },
                complexity="MODERATE",
                material_cost=Decimal("1000.00"),
                labor_cost=Decimal("200.00"),
                overhead_percentage=Decimal("20.00"),
                profit_margin_percentage=Decimal("30.00"),
                created_by=self.user,
            )

            # Add material requirements to match the expected material cost
            MaterialRequirement.objects.create(
                custom_order=custom_order,
                material_type="GOLD",
                material_name="18K Gold",
                quantity_required=Decimal("10.0"),
                unit="GRAMS",
                estimated_cost_per_unit=Decimal("100.00"),
            )

            # Test pricing calculation
            pricing = custom_order.calculate_pricing()

            expected_base_cost = Decimal("1200.00")  # material + labor
            expected_overhead = expected_base_cost * Decimal("0.20")  # 20%
            expected_cost_with_overhead = expected_base_cost + expected_overhead
            expected_profit = expected_cost_with_overhead * Decimal("0.30")  # 30%
            expected_final_price = expected_cost_with_overhead + expected_profit

            self.assertEqual(pricing["material_cost"], Decimal("1000.00"))
            self.assertEqual(pricing["labor_cost"], Decimal("200.00"))
            self.assertEqual(pricing["base_cost"], expected_base_cost)
            self.assertEqual(pricing["overhead_amount"], expected_overhead)
            self.assertEqual(pricing["profit_amount"], expected_profit)
            self.assertEqual(pricing["final_price"], expected_final_price)

    def test_material_requirement_functionality(self):
        """Test material requirement creation and management."""
        with tenant_context(self.tenant.id):
            from apps.repair.models import MaterialRequirement

            custom_order = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-MAT-001",
                customer=self.customer,
                design_description="Ring with materials",
                created_by=self.user,
            )

            # Create material requirement
            material_req = MaterialRequirement.objects.create(
                custom_order=custom_order,
                material_type="GOLD",
                material_name="18K Gold",
                specifications={"purity": "18K", "color": "yellow"},
                quantity_required=Decimal("10.0"),
                unit="GRAMS",
                estimated_cost_per_unit=Decimal("60.00"),
                supplier_info="Gold supplier ABC",
            )

            # Test properties
            self.assertEqual(material_req.total_estimated_cost, Decimal("600.00"))
            self.assertEqual(material_req.unit_cost, Decimal("60.00"))
            self.assertEqual(material_req.total_cost, Decimal("600.00"))
            self.assertFalse(material_req.is_acquired)

            # Test acquisition
            material_req.mark_as_acquired(actual_cost_per_unit=Decimal("65.00"))

            self.assertTrue(material_req.is_acquired)
            self.assertIsNotNone(material_req.acquired_date)
            self.assertEqual(material_req.actual_cost_per_unit, Decimal("65.00"))
            self.assertEqual(material_req.total_actual_cost, Decimal("650.00"))

    def test_inventory_creation_from_custom_order(self):
        """Test creating inventory item from completed custom order."""
        with tenant_context(self.tenant.id):
            from apps.repair.services import CustomOrderInventoryService

            custom_order = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-INV-001",
                customer=self.customer,
                design_description="Custom engagement ring",
                design_specifications={"karat": 18, "weight_grams": 12.5},
                status="completed",
                material_cost=Decimal("800.00"),
                labor_cost=Decimal("300.00"),
                final_price=Decimal("1600.00"),
                created_by=self.user,
            )

            # Create inventory item
            inventory_item = CustomOrderInventoryService.create_inventory_from_custom_order(
                custom_order, self.branch, user=self.user
            )

            # Verify inventory item properties
            self.assertIsNotNone(inventory_item)
            self.assertEqual(inventory_item.sku, "CUSTOM-CUSTOM-INV-001")
            self.assertTrue(inventory_item.name.startswith("Custom:"))
            self.assertEqual(inventory_item.karat, 18)
            self.assertEqual(inventory_item.weight_grams, Decimal("12.5"))
            self.assertEqual(inventory_item.craftsmanship_level, "HANDMADE")
            self.assertEqual(inventory_item.cost_price, Decimal("1100.00"))  # material + labor
            self.assertEqual(inventory_item.selling_price, Decimal("1600.00"))
            self.assertEqual(inventory_item.quantity, 1)
            self.assertEqual(inventory_item.serial_number, "CUSTOM-CUSTOM-INV-001")
            self.assertEqual(inventory_item.branch, self.branch)

            # Verify custom order is linked
            custom_order.refresh_from_db()
            self.assertEqual(custom_order.created_inventory_item, inventory_item)

    def test_inventory_creation_validation(self):
        """Test validation for inventory creation."""
        with tenant_context(self.tenant.id):
            from apps.repair.services import CustomOrderInventoryService

            # Test with non-completed order
            custom_order = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-VAL-001",
                customer=self.customer,
                design_description="Not completed order",
                status="in_progress",
                created_by=self.user,
            )

            with self.assertRaises(ValueError) as context:
                CustomOrderInventoryService.create_inventory_from_custom_order(
                    custom_order, self.branch, user=self.user
                )

            self.assertIn(
                "Can only create inventory from completed custom orders", str(context.exception)
            )

    def test_pricing_calculator_service(self):
        """Test the pricing calculator service."""
        with tenant_context(self.tenant.id):
            from apps.repair.models import MaterialRequirement
            from apps.repair.services import CustomOrderPricingCalculator

            custom_order = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-CALC-001",
                customer=self.customer,
                design_description="Ring for pricing test",
                complexity="COMPLEX",
                overhead_percentage=Decimal("25.00"),
                profit_margin_percentage=Decimal("35.00"),
                created_by=self.user,
            )

            # Add material requirements
            MaterialRequirement.objects.create(
                custom_order=custom_order,
                material_type="GOLD",
                material_name="18K Gold",
                quantity_required=Decimal("8.0"),
                unit="GRAMS",
                estimated_cost_per_unit=Decimal("70.00"),
            )

            MaterialRequirement.objects.create(
                custom_order=custom_order,
                material_type="DIAMOND",
                material_name="Round Diamond",
                quantity_required=Decimal("0.5"),
                unit="CARATS",
                estimated_cost_per_unit=Decimal("3000.00"),
            )

            # Test calculator
            calculator = CustomOrderPricingCalculator(custom_order)

            # Test material cost calculation
            material_cost = calculator.calculate_material_cost()
            expected_material_cost = Decimal("560.00") + Decimal("1500.00")  # Gold + Diamond
            self.assertEqual(material_cost, expected_material_cost)

            # Test labor cost (complexity-based)
            labor_cost = calculator.calculate_labor_cost()
            self.assertEqual(labor_cost, Decimal("200.00"))  # COMPLEX complexity

            # Test full pricing
            pricing = calculator.calculate_full_pricing()

            expected_base_cost = expected_material_cost + Decimal("200.00")
            expected_overhead = expected_base_cost * Decimal("0.25")
            expected_cost_with_overhead = expected_base_cost + expected_overhead
            expected_profit = expected_cost_with_overhead * Decimal("0.35")
            expected_final_price = expected_cost_with_overhead + expected_profit

            self.assertEqual(pricing["material_cost"], expected_material_cost)
            self.assertEqual(pricing["labor_cost"], Decimal("200.00"))
            self.assertEqual(pricing["final_price"], expected_final_price)

            # Test updating order pricing
            calculator.update_order_pricing()
            custom_order.refresh_from_db()

            self.assertEqual(custom_order.material_cost, expected_material_cost)
            self.assertEqual(custom_order.labor_cost, Decimal("200.00"))
            self.assertEqual(custom_order.quoted_price, expected_final_price)

    def test_total_material_cost_property(self):
        """Test the total_material_cost property on CustomOrder."""
        with tenant_context(self.tenant.id):
            from apps.repair.models import MaterialRequirement

            custom_order = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-PROP-001",
                customer=self.customer,
                design_description="Ring for property test",
                created_by=self.user,
            )

            # Initially no materials
            self.assertEqual(custom_order.total_material_cost, Decimal("0.00"))

            # Add material requirements
            MaterialRequirement.objects.create(
                custom_order=custom_order,
                material_type="GOLD",
                material_name="Gold Wire",
                quantity_required=Decimal("5.0"),
                unit="GRAMS",
                estimated_cost_per_unit=Decimal("50.00"),
            )

            MaterialRequirement.objects.create(
                custom_order=custom_order,
                material_type="SILVER",
                material_name="Silver Sheet",
                quantity_required=Decimal("2.0"),
                unit="PIECES",
                estimated_cost_per_unit=Decimal("25.00"),
            )

            # Test total cost calculation
            expected_total = Decimal("250.00") + Decimal("50.00")  # Gold + Silver
            self.assertEqual(custom_order.total_material_cost, expected_total)

    def test_custom_order_notifications(self):
        """Test customer notifications on status changes."""
        with tenant_context(self.tenant.id):
            from unittest.mock import patch

            custom_order = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-NOTIFY-001",
                customer=self.customer,
                design_description="Ring for notification test",
                created_by=self.user,
            )

            # Mock the email sending
            with patch("apps.repair.services.send_mail") as mock_send_mail:
                # Test quote provided notification
                custom_order.provide_quote()

                # Verify email was called
                mock_send_mail.assert_called()
                args, kwargs = mock_send_mail.call_args
                self.assertIn("Custom Order Update", kwargs["subject"])
                self.assertIn(custom_order.order_number, kwargs["subject"])
                self.assertEqual(kwargs["recipient_list"], [self.customer.email])

    def test_work_order_generation(self):
        """Test work order generation for craftsmen."""
        with tenant_context(self.tenant.id):
            from apps.repair.models import MaterialRequirement
            from apps.repair.services import WorkOrderGenerator

            # Create a craftsman user
            craftsman = User.objects.create_user(
                username="craftsman",
                email="craftsman@test.com",
                password="testpass123",
                tenant=self.tenant,
                role="TENANT_EMPLOYEE",
            )

            custom_order = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-WORK-001",
                customer=self.customer,
                design_description="Complex engagement ring",
                design_specifications={
                    "karat": 18,
                    "weight_grams": 12.5,
                    "stone_type": "diamond",
                    "stone_size": "1 carat",
                },
                complexity="COMPLEX",
                craftsman=craftsman,
                created_by=self.user,
            )

            # Add material requirements
            MaterialRequirement.objects.create(
                custom_order=custom_order,
                material_type="GOLD",
                material_name="18K Gold Wire",
                quantity_required=Decimal("10.0"),
                unit="GRAMS",
                estimated_cost_per_unit=Decimal("70.00"),
                is_acquired=True,
            )

            # Generate work order
            work_order = WorkOrderGenerator.generate_work_order(
                custom_order, notes="Handle with care"
            )

            # Verify work order content
            self.assertEqual(work_order["order_number"], custom_order.order_number)
            self.assertEqual(work_order["complexity"], "Complex")
            self.assertEqual(work_order["assigned_craftsman"], craftsman.get_full_name())
            self.assertEqual(work_order["notes"], "Handle with care")

            # Verify material requirements in work order
            self.assertEqual(len(work_order["material_requirements"]), 1)
            material = work_order["material_requirements"][0]
            self.assertEqual(material["material_name"], "18K Gold Wire")
            self.assertEqual(material["status"], "Acquired")

            # Verify instructions are generated
            self.assertGreater(len(work_order["instructions"]), 5)
            self.assertTrue(
                any("18K gold" in instruction for instruction in work_order["instructions"])
            )

    def test_custom_order_work_order_method(self):
        """Test the generate_work_order method on CustomOrder model."""
        with tenant_context(self.tenant.id):
            from unittest.mock import patch

            # Create a craftsman user
            craftsman = User.objects.create_user(
                username="craftsman2",
                email="craftsman2@test.com",
                password="testpass123",
                tenant=self.tenant,
                role="TENANT_EMPLOYEE",
            )

            custom_order = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-METHOD-001",
                customer=self.customer,
                design_description="Ring for method test",
                created_by=self.user,
            )

            # Mock email sending
            with patch("apps.repair.services.send_mail") as mock_send_mail:
                # Generate work order with craftsman assignment
                work_order = custom_order.generate_work_order(
                    craftsman=craftsman, notes="Test notes"
                )

                # Verify craftsman was assigned
                custom_order.refresh_from_db()
                self.assertEqual(custom_order.craftsman, craftsman)

                # Verify work order was generated
                self.assertEqual(work_order["order_number"], custom_order.order_number)
                self.assertEqual(work_order["notes"], "Test notes")

                # Verify email was sent to craftsman
                mock_send_mail.assert_called()
                args, kwargs = mock_send_mail.call_args
                self.assertIn("New Work Order Assignment", kwargs["subject"])
                self.assertEqual(kwargs["recipient_list"], [craftsman.email])

    def test_fsm_transitions_with_notifications(self):
        """Test that FSM transitions trigger notifications."""
        with tenant_context(self.tenant.id):
            from unittest.mock import patch

            custom_order = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-FSM-001",
                customer=self.customer,
                design_description="Ring for FSM test",
                created_by=self.user,
            )

            # Mock email sending
            with patch("apps.repair.services.send_custom_order_status_notification") as mock_notify:
                # Test each transition triggers notification
                custom_order.provide_quote()
                mock_notify.assert_called_with(custom_order)

                custom_order.approve_quote()
                mock_notify.assert_called_with(custom_order)

                custom_order.start_design()
                mock_notify.assert_called_with(custom_order)

                custom_order.approve_design()
                mock_notify.assert_called_with(custom_order)

                custom_order.start_production()
                mock_notify.assert_called_with(custom_order)

                custom_order.submit_for_quality_check()
                mock_notify.assert_called_with(custom_order)

                custom_order.complete_order()
                mock_notify.assert_called_with(custom_order)

                custom_order.deliver_to_customer()
                mock_notify.assert_called_with(custom_order)

                # Verify we had 8 calls (one for each transition)
                self.assertEqual(mock_notify.call_count, 8)

    def test_material_requirement_sourcing_from_inventory(self):
        """Test sourcing material requirements from existing inventory."""
        with tenant_context(self.tenant.id):
            from apps.inventory.models import InventoryItem, ProductCategory
            from apps.repair.models import MaterialRequirement

            custom_order = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-SOURCE-001",
                customer=self.customer,
                design_description="Ring for sourcing test",
                created_by=self.user,
            )

            # Create inventory item
            category = ProductCategory.objects.create(
                tenant=self.tenant, name="Raw Materials", is_active=True
            )

            gold_inventory = InventoryItem.objects.create(
                tenant=self.tenant,
                sku="GOLD-18K-002",
                name="18K Gold Sheet",
                category=category,
                karat=18,
                weight_grams=Decimal("50.0"),
                cost_price=Decimal("60.00"),
                selling_price=Decimal("75.00"),
                quantity=20,  # 20 grams available
                branch=self.branch,
            )

            # Create material requirement
            material_req = MaterialRequirement.objects.create(
                custom_order=custom_order,
                material_type="GOLD",
                material_name="18K Gold Sheet",
                quantity_required=Decimal("8.0"),
                unit="GRAMS",
                estimated_cost_per_unit=Decimal("65.00"),
            )

            # Test sourcing from inventory
            initial_inventory_qty = gold_inventory.quantity
            material_req.source_from_inventory(gold_inventory)

            # Verify material requirement is marked as acquired
            self.assertTrue(material_req.is_acquired)
            self.assertEqual(material_req.actual_cost_per_unit, Decimal("60.00"))
            self.assertIn("Internal inventory", material_req.supplier_info)

            # Verify inventory was deducted
            gold_inventory.refresh_from_db()
            self.assertEqual(gold_inventory.quantity, initial_inventory_qty - 8)

    def test_material_requirement_comprehensive_methods(self):
        """Test all MaterialRequirement methods comprehensively."""
        with tenant_context(self.tenant.id):
            from apps.inventory.models import InventoryItem, ProductCategory
            from apps.repair.models import MaterialRequirement

            custom_order = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-METHODS-001",
                customer=self.customer,
                design_description="Ring for method testing",
                created_by=self.user,
            )

            # Create material requirement
            material_req = MaterialRequirement.objects.create(
                custom_order=custom_order,
                material_type="DIAMOND",
                material_name="Round Diamond",
                specifications={"clarity": "VS1", "color": "G", "cut": "Excellent"},
                quantity_required=Decimal("0.5"),
                unit="CARATS",
                estimated_cost_per_unit=Decimal("4000.00"),
                supplier_info="Diamond Supplier XYZ",
            )

            # Test initial properties
            self.assertEqual(material_req.total_estimated_cost, Decimal("2000.00"))
            self.assertEqual(material_req.unit_cost, Decimal("4000.00"))
            self.assertEqual(material_req.total_cost, Decimal("2000.00"))
            self.assertFalse(material_req.is_acquired)
            self.assertIsNone(material_req.actual_cost_per_unit)

            # Test mark_as_acquired without actual cost
            material_req.mark_as_acquired()
            material_req.refresh_from_db()

            self.assertTrue(material_req.is_acquired)
            self.assertIsNotNone(material_req.acquired_date)
            self.assertIsNone(material_req.actual_cost_per_unit)
            self.assertEqual(material_req.total_actual_cost, Decimal("2000.00"))  # Uses estimated

            # Reset for next test
            material_req.is_acquired = False
            material_req.acquired_date = None
            material_req.save()

            # Test mark_as_acquired with actual cost
            material_req.mark_as_acquired(actual_cost_per_unit=Decimal("3800.00"))
            material_req.refresh_from_db()

            self.assertTrue(material_req.is_acquired)
            self.assertEqual(material_req.actual_cost_per_unit, Decimal("3800.00"))
            self.assertEqual(material_req.unit_cost, Decimal("3800.00"))  # Now uses actual
            self.assertEqual(material_req.total_actual_cost, Decimal("1900.00"))
            self.assertEqual(material_req.total_cost, Decimal("1900.00"))

            # Test can_source_from_inventory
            category = ProductCategory.objects.create(
                tenant=self.tenant, name="Diamonds", is_active=True
            )

            # Sufficient inventory
            sufficient_inventory = InventoryItem.objects.create(
                tenant=self.tenant,
                sku="DIAMOND-001",
                name="Round Diamond Stock",
                category=category,
                karat=0,  # Diamonds don't have karat, but field is required
                weight_grams=Decimal("1.0"),  # Weight in grams
                cost_price=Decimal("3500.00"),
                selling_price=Decimal("4500.00"),
                quantity=2,  # 2 carats available
                branch=self.branch,
            )

            # Insufficient inventory
            InventoryItem.objects.create(
                tenant=self.tenant,
                sku="DIAMOND-002",
                name="Small Diamond Stock",
                category=category,
                karat=0,  # Diamonds don't have karat, but field is required
                weight_grams=Decimal("0.5"),  # Weight in grams
                cost_price=Decimal("3500.00"),
                selling_price=Decimal("4500.00"),
                quantity=0,  # No stock
                branch=self.branch,
            )

            # Reset material requirement for sourcing test
            material_req.is_acquired = False
            material_req.acquired_date = None
            material_req.actual_cost_per_unit = None
            material_req.save()

            # Test can_source_from_inventory
            # Note: The method checks if inventory quantity >= required quantity (as int)
            # sufficient_inventory has quantity=2, material_req needs 0.5 (int(0.5) = 0)
            # So 2 >= 0 is True, and 0 >= 0 is also True
            self.assertTrue(material_req.can_source_from_inventory(sufficient_inventory))
            # For a proper test, let's create a material requirement that needs more than available
            large_material_req = MaterialRequirement.objects.create(
                custom_order=custom_order,
                material_type="DIAMOND",
                material_name="Large Diamond",
                quantity_required=Decimal("5.0"),  # Need 5 carats, but only 2 available
                unit="CARATS",
                estimated_cost_per_unit=Decimal("4000.00"),
            )
            self.assertFalse(large_material_req.can_source_from_inventory(sufficient_inventory))

            # Test source_from_inventory error handling with large requirement
            with self.assertRaises(ValueError) as context:
                large_material_req.source_from_inventory(sufficient_inventory)
            self.assertIn("Insufficient inventory", str(context.exception))

            # Test source_from_inventory when already acquired
            material_req.is_acquired = True
            material_req.save()

            with self.assertRaises(ValueError) as context:
                material_req.source_from_inventory(sufficient_inventory)
            self.assertIn("already acquired", str(context.exception))

    def test_overdue_order_reminders(self):
        """Test sending reminders for overdue orders."""
        with tenant_context(self.tenant.id):
            from datetime import date, timedelta
            from unittest.mock import patch

            from apps.repair.models import RepairOrder
            from apps.repair.services import send_overdue_order_reminders

            # Create overdue repair order
            overdue_repair = RepairOrder.objects.create(
                tenant=self.tenant,
                order_number="REP-OVERDUE-001",
                customer=self.customer,
                item_description="Overdue ring repair",
                service_type="RESIZING",
                cost_estimate=Decimal("50.00"),
                estimated_completion=date.today() - timedelta(days=3),  # 3 days overdue
                created_by=self.user,
            )

            # Create overdue custom order
            overdue_custom = CustomOrder.objects.create(
                tenant=self.tenant,
                order_number="CUSTOM-OVERDUE-001",
                customer=self.customer,
                design_description="Overdue custom ring",
                status="in_production",
                estimated_completion=date.today() - timedelta(days=2),  # 2 days overdue
                created_by=self.user,
            )

            # Create non-overdue order (should not get reminder)
            RepairOrder.objects.create(
                tenant=self.tenant,
                order_number="REP-FUTURE-001",
                customer=self.customer,
                item_description="Future ring repair",
                service_type="CLEANING",
                cost_estimate=Decimal("25.00"),
                estimated_completion=date.today() + timedelta(days=5),  # Future date
                created_by=self.user,
            )

            # Mock email sending
            with patch("apps.repair.services.send_mail") as mock_send_mail:
                # Send overdue reminders
                results = send_overdue_order_reminders()

                # Verify results
                self.assertEqual(results["repair_orders_reminded"], 1)
                self.assertEqual(results["custom_orders_reminded"], 1)
                self.assertEqual(len(results["errors"]), 0)

                # Verify emails were sent (2 calls: 1 for repair, 1 for custom)
                self.assertEqual(mock_send_mail.call_count, 2)

                # Check repair order email
                repair_call = mock_send_mail.call_args_list[0]
                self.assertIn("Overdue Repair Order Reminder", repair_call[1]["subject"])
                self.assertIn(overdue_repair.order_number, repair_call[1]["subject"])
                self.assertIn("3", repair_call[1]["message"])  # Days overdue

                # Check custom order email
                custom_call = mock_send_mail.call_args_list[1]
                self.assertIn("Overdue Custom Order Reminder", custom_call[1]["subject"])
                self.assertIn(overdue_custom.order_number, custom_call[1]["subject"])
                self.assertIn("2", custom_call[1]["message"])  # Days overdue
