from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.core.models import Tenant

from .models import Notification, NotificationPreference, NotificationTemplate

User = get_user_model()


class NotificationModelTest(TestCase):
    """Test cases for Notification model"""

    def setUp(self):
        """Set up test data"""
        # Enable RLS bypass for tests
        from apps.core.tenant_context import enable_rls_bypass

        enable_rls_bypass()

        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop", slug="test-shop", status="ACTIVE"
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_OWNER",
        )

    def test_notification_creation(self):
        """Test creating a notification"""
        notification = Notification.objects.create(
            user=self.user,
            title="Test Notification",
            message="This is a test notification",
            notification_type="INFO",
        )

        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.title, "Test Notification")
        self.assertEqual(notification.message, "This is a test notification")
        self.assertEqual(notification.notification_type, "INFO")
        self.assertFalse(notification.is_read)
        self.assertIsNotNone(notification.created_at)
        self.assertIsNone(notification.read_at)

    def test_notification_str_representation(self):
        """Test string representation of notification"""
        notification = Notification.objects.create(
            user=self.user,
            title="Test Notification",
            message="Test message",
            notification_type="INFO",
        )

        expected_str = f"Test Notification - {self.user.username}"
        self.assertEqual(str(notification), expected_str)

    def test_mark_as_read(self):
        """Test marking notification as read"""
        notification = Notification.objects.create(
            user=self.user,
            title="Test Notification",
            message="Test message",
            notification_type="INFO",
        )

        # Initially not read
        self.assertFalse(notification.is_read)
        self.assertIsNone(notification.read_at)

        # Mark as read
        notification.mark_as_read()

        # Should be marked as read with timestamp
        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)

    def test_is_expired(self):
        """Test notification expiration check"""
        # Create notification that expires in the future
        future_expiry = timezone.now() + timedelta(hours=1)
        notification = Notification.objects.create(
            user=self.user,
            title="Future Expiry",
            message="Test message",
            notification_type="INFO",
            expires_at=future_expiry,
        )

        self.assertFalse(notification.is_expired())

        # Create notification that has already expired
        past_expiry = timezone.now() - timedelta(hours=1)
        expired_notification = Notification.objects.create(
            user=self.user,
            title="Past Expiry",
            message="Test message",
            notification_type="INFO",
            expires_at=past_expiry,
        )

        self.assertTrue(expired_notification.is_expired())

        # Create notification without expiry
        no_expiry_notification = Notification.objects.create(
            user=self.user, title="No Expiry", message="Test message", notification_type="INFO"
        )

        self.assertFalse(no_expiry_notification.is_expired())


class NotificationPreferenceModelTest(TestCase):
    """Test cases for NotificationPreference model"""

    def setUp(self):
        """Set up test data"""
        # Enable RLS bypass for tests
        from apps.core.tenant_context import enable_rls_bypass

        enable_rls_bypass()

        self.tenant = Tenant.objects.create(
            company_name="Test Jewelry Shop", slug="test-shop", status="ACTIVE"
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_OWNER",
        )

    def test_notification_preference_creation(self):
        """Test creating a notification preference"""
        preference = NotificationPreference.objects.create(
            user=self.user, notification_type="LOW_STOCK", channel="EMAIL", is_enabled=True
        )

        self.assertEqual(preference.user, self.user)
        self.assertEqual(preference.notification_type, "LOW_STOCK")
        self.assertEqual(preference.channel, "EMAIL")
        self.assertTrue(preference.is_enabled)
        self.assertIsNotNone(preference.created_at)
        self.assertIsNotNone(preference.updated_at)

    def test_notification_preference_str_representation(self):
        """Test string representation of notification preference"""
        preference = NotificationPreference.objects.create(
            user=self.user, notification_type="LOW_STOCK", channel="EMAIL", is_enabled=True
        )

        expected_str = f"{self.user.username} - LOW_STOCK via EMAIL"
        self.assertEqual(str(preference), expected_str)

    def test_unique_constraint(self):
        """Test unique constraint on user, notification_type, channel"""
        # Create first preference
        NotificationPreference.objects.create(
            user=self.user, notification_type="LOW_STOCK", channel="EMAIL", is_enabled=True
        )

        # Try to create duplicate - should raise IntegrityError
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            NotificationPreference.objects.create(
                user=self.user, notification_type="LOW_STOCK", channel="EMAIL", is_enabled=False
            )

    def test_is_in_quiet_hours(self):
        """Test quiet hours functionality"""
        # Create preference with quiet hours
        preference = NotificationPreference.objects.create(
            user=self.user,
            notification_type="LOW_STOCK",
            channel="EMAIL",
            is_enabled=True,
            quiet_hours_start=time(22, 0),  # 10 PM
            quiet_hours_end=time(8, 0),  # 8 AM
        )

        # Mock current time to test different scenarios
        from unittest.mock import patch

        # Test time within quiet hours (midnight)
        with patch("django.utils.timezone.now") as mock_now:
            mock_now.return_value.time.return_value = time(0, 0)
            self.assertTrue(preference.is_in_quiet_hours())

        # Test time outside quiet hours (noon)
        with patch("django.utils.timezone.now") as mock_now:
            mock_now.return_value.time.return_value = time(12, 0)
            self.assertFalse(preference.is_in_quiet_hours())

        # Test preference without quiet hours
        preference_no_quiet = NotificationPreference.objects.create(
            user=self.user, notification_type="INFO", channel="EMAIL", is_enabled=True
        )

        self.assertFalse(preference_no_quiet.is_in_quiet_hours())


class NotificationTemplateModelTest(TestCase):
    """Test cases for NotificationTemplate model"""

    def test_notification_template_creation(self):
        """Test creating a notification template"""
        template = NotificationTemplate.objects.create(
            name="low_stock_alert",
            notification_type="LOW_STOCK",
            title_template="Low Stock Alert: {{ item_name }}",
            message_template="Item {{ item_name }} is running low. Current stock: {{ current_stock }}",
            action_text_template="Restock Now",
            action_url_template="/inventory/{{ item_id }}/",
            is_active=True,
        )

        self.assertEqual(template.name, "low_stock_alert")
        self.assertEqual(template.notification_type, "LOW_STOCK")
        self.assertTrue(template.is_active)
        self.assertIsNotNone(template.created_at)
        self.assertIsNotNone(template.updated_at)

    def test_notification_template_str_representation(self):
        """Test string representation of notification template"""
        template = NotificationTemplate.objects.create(
            name="low_stock_alert",
            notification_type="LOW_STOCK",
            title_template="Low Stock Alert",
            message_template="Stock is low",
            is_active=True,
        )

        expected_str = "low_stock_alert (LOW_STOCK)"
        self.assertEqual(str(template), expected_str)

    def test_template_rendering(self):
        """Test template rendering with context"""
        template = NotificationTemplate.objects.create(
            name="low_stock_alert",
            notification_type="LOW_STOCK",
            title_template="Low Stock Alert: {{ item_name }}",
            message_template="Item {{ item_name }} is running low. Current stock: {{ current_stock }}",
            action_text_template="Restock {{ item_name }}",
            action_url_template="/inventory/{{ item_id }}/",
            is_active=True,
        )

        context = {"item_name": "Gold Ring", "current_stock": 5, "item_id": 123}

        rendered = template.render(context)

        self.assertEqual(rendered["title"], "Low Stock Alert: Gold Ring")
        self.assertEqual(rendered["message"], "Item Gold Ring is running low. Current stock: 5")
        self.assertEqual(rendered["action_text"], "Restock Gold Ring")
        self.assertEqual(rendered["action_url"], "/inventory/123/")

    def test_template_rendering_without_action(self):
        """Test template rendering without action templates"""
        template = NotificationTemplate.objects.create(
            name="simple_alert",
            notification_type="INFO",
            title_template="Simple Alert",
            message_template="This is a simple message",
            is_active=True,
        )

        context = {}
        rendered = template.render(context)

        self.assertEqual(rendered["title"], "Simple Alert")
        self.assertEqual(rendered["message"], "This is a simple message")
        self.assertNotIn("action_text", rendered)
        self.assertNotIn("action_url", rendered)
