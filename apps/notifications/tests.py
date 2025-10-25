from datetime import time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.core.models import Tenant

from .models import (
    Notification,
    NotificationPreference,
    NotificationTemplate,
    SMSNotification,
    SMSOptOut,
    SMSTemplate,
)

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


class NotificationViewTests(TestCase):
    """Test cases for notification views"""

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
        self.client.force_login(self.user)

    def test_notification_center_view(self):
        """Test notification center view"""
        from apps.notifications.services import create_notification

        # Create test notifications
        create_notification(
            user=self.user,
            title="Test Notification 1",
            message="Message 1",
            notification_type="INFO",
        )
        create_notification(
            user=self.user,
            title="Test Notification 2",
            message="Message 2",
            notification_type="SUCCESS",
        )

        response = self.client.get("/notifications/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Notification 1")
        self.assertContains(response, "Test Notification 2")
        self.assertContains(response, "Notification Center")

    def test_notification_center_filtering(self):
        """Test notification center filtering"""
        from apps.notifications.services import create_notification

        # Create test notifications
        create_notification(
            user=self.user,
            title="Info Notification",
            message="Info message",
            notification_type="INFO",
        )
        create_notification(
            user=self.user,
            title="Success Notification",
            message="Success message",
            notification_type="SUCCESS",
        )

        # Test filtering by type
        response = self.client.get("/notifications/?type=SUCCESS")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Success Notification")
        self.assertNotContains(response, "Info Notification")

    def test_notification_count_view(self):
        """Test notification count HTMX endpoint"""
        from apps.notifications.services import create_notification

        # Create unread notifications
        create_notification(
            user=self.user, title="Unread 1", message="Message 1", notification_type="INFO"
        )
        create_notification(
            user=self.user, title="Unread 2", message="Message 2", notification_type="INFO"
        )

        response = self.client.get("/notifications/count/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2")  # Should show count of 2

    def test_notification_list_view(self):
        """Test notification list HTMX endpoint"""
        from apps.notifications.services import create_notification

        # Create test notifications
        create_notification(
            user=self.user, title="List Test 1", message="Message 1", notification_type="INFO"
        )
        create_notification(
            user=self.user, title="List Test 2", message="Message 2", notification_type="SUCCESS"
        )

        response = self.client.get("/notifications/list/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "List Test 1")
        self.assertContains(response, "List Test 2")

    def test_mark_as_read_view(self):
        """Test mark as read endpoint"""
        import json

        from apps.notifications.services import create_notification

        # Create test notifications
        notification1 = create_notification(
            user=self.user, title="Test 1", message="Message 1", notification_type="INFO"
        )
        notification2 = create_notification(
            user=self.user, title="Test 2", message="Message 2", notification_type="INFO"
        )

        # Mark all as read
        response = self.client.post("/notifications/mark-read/", content_type="application/json")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertEqual(data["marked_count"], 2)

        # Verify notifications are marked as read
        notification1.refresh_from_db()
        notification2.refresh_from_db()
        self.assertTrue(notification1.is_read)
        self.assertTrue(notification2.is_read)

    def test_mark_single_as_read_view(self):
        """Test mark single notification as read endpoint"""
        import json

        from apps.notifications.services import create_notification

        # Create test notification
        notification = create_notification(
            user=self.user, title="Single Test", message="Message", notification_type="INFO"
        )

        response = self.client.post(f"/notifications/mark-read/{notification.id}/")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])

        # Verify notification is marked as read
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_notification_preferences_view_get(self):
        """Test notification preferences view GET"""
        response = self.client.get("/notifications/preferences/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Notification Preferences")
        self.assertContains(response, "Notification Types")

    def test_notification_preferences_view_post(self):
        """Test notification preferences view POST"""
        # Submit preferences form
        response = self.client.post(
            "/notifications/preferences/",
            {
                "INFO_IN_APP": "on",
                "INFO_EMAIL": "on",
                "LOW_STOCK_IN_APP": "on",
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "08:00",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "updated successfully")

        # Verify preferences were created
        pref = NotificationPreference.objects.get(
            user=self.user, notification_type="INFO", channel="EMAIL"
        )
        self.assertTrue(pref.is_enabled)

    def test_notification_dropdown_view(self):
        """Test notification dropdown HTMX endpoint"""
        from apps.notifications.services import create_notification

        # Create test notifications
        create_notification(
            user=self.user, title="Dropdown Test", message="Message", notification_type="INFO"
        )

        response = self.client.get("/notifications/dropdown/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dropdown Test")
        self.assertContains(response, "Notifications")

    def test_unauthenticated_access(self):
        """Test that unauthenticated users cannot access notification views"""
        self.client.logout()

        # Test various endpoints
        endpoints = [
            "/notifications/",
            "/notifications/count/",
            "/notifications/list/",
            "/notifications/dropdown/",
            "/notifications/preferences/",
        ]

        for endpoint in endpoints:
            response = self.client.get(endpoint)
            # Should redirect to login or return 302/403
            self.assertIn(response.status_code, [302, 403])

    def test_cross_user_notification_access(self):
        """Test that users cannot access other users' notifications"""
        from apps.notifications.services import create_notification

        # Create another user
        other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            tenant=self.tenant,
            role="TENANT_EMPLOYEE",
        )

        # Create notification for other user
        other_notification = create_notification(
            user=other_user,
            title="Other User Notification",
            message="Message",
            notification_type="INFO",
        )

        # Try to mark other user's notification as read
        response = self.client.post(f"/notifications/mark-read/{other_notification.id}/")

        # Should return 404 (not found due to user filtering)
        self.assertEqual(response.status_code, 404)


class EmailNotificationModelTests(TestCase):
    """Test cases for email notification models"""

    def setUp(self):
        """Set up test data"""
        # Enable RLS bypass for tests
        from apps.core.tenant_context import enable_rls_bypass

        enable_rls_bypass()

        # Create tenant first
        self.tenant = Tenant.objects.create(company_name="Test Company", slug="test-company")

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_OWNER",
        )

    def test_email_notification_creation(self):
        """Test creating an email notification"""
        from .models import EmailNotification

        email_notification = EmailNotification.objects.create(
            user=self.user,
            subject="Test Email",
            to_email="test@example.com",
            from_email="noreply@example.com",
            template_name="test_template",
            email_type="TRANSACTIONAL",
        )

        self.assertEqual(email_notification.user, self.user)
        self.assertEqual(email_notification.subject, "Test Email")
        self.assertEqual(email_notification.to_email, "test@example.com")
        self.assertEqual(email_notification.status, "PENDING")

    def test_email_status_update(self):
        """Test updating email status"""
        from .models import EmailNotification

        email_notification = EmailNotification.objects.create(
            user=self.user,
            subject="Test Email",
            to_email="test@example.com",
            from_email="noreply@example.com",
            template_name="test_template",
        )

        # Update to sent
        email_notification.update_status("SENT")
        self.assertEqual(email_notification.status, "SENT")
        self.assertIsNotNone(email_notification.sent_at)

        # Update to delivered
        email_notification.update_status("DELIVERED")
        self.assertEqual(email_notification.status, "DELIVERED")
        self.assertIsNotNone(email_notification.delivered_at)

    def test_email_template_creation(self):
        """Test creating an email template"""
        from .models import EmailTemplate

        template = EmailTemplate.objects.create(
            name="test_template",
            subject_template="Test Subject: {{ name }}",
            html_template="<h1>Hello {{ name }}</h1>",
            text_template="Hello {{ name }}",
            email_type="TRANSACTIONAL",
        )

        self.assertEqual(template.name, "test_template")
        self.assertEqual(template.email_type, "TRANSACTIONAL")
        self.assertTrue(template.is_active)

    def test_email_template_rendering(self):
        """Test email template rendering"""
        from .models import EmailTemplate

        template = EmailTemplate.objects.create(
            name="test_template",
            subject_template="Hello {{ name }}",
            html_template="<h1>Welcome {{ name }}</h1><p>You have {{ count }} items.</p>",
            text_template="Welcome {{ name }}, you have {{ count }} items.",
        )

        context = {"name": "John", "count": 5}
        rendered = template.render(context)

        self.assertEqual(rendered["subject"], "Hello John")
        self.assertIn("Welcome John", rendered["html_body"])
        self.assertIn("5 items", rendered["html_body"])
        if rendered.get("text_body"):
            self.assertEqual(rendered["text_body"], "Welcome John, you have 5 items.")


class EmailServiceTests(TestCase):
    """Test cases for email services"""

    def setUp(self):
        """Set up test data"""
        # Enable RLS bypass for tests
        from apps.core.tenant_context import enable_rls_bypass

        from .models import EmailTemplate

        enable_rls_bypass()

        # Create tenant first
        self.tenant = Tenant.objects.create(company_name="Test Company", slug="test-company")

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_OWNER",
        )

        # Create email template
        self.email_template = EmailTemplate.objects.create(
            name="test_template",
            subject_template="Test Subject: {{ name }}",
            html_template="<h1>Hello {{ name }}</h1>",
            text_template="Hello {{ name }}",
            email_type="TRANSACTIONAL",
        )

    @patch("apps.notifications.services._send_email_now")
    def test_send_email_notification(self, mock_send):
        """Test sending email notification"""
        from .models import NotificationPreference
        from .services import send_email_notification

        # Create email preference to allow email notifications
        NotificationPreference.objects.create(
            user=self.user, notification_type="TRANSACTIONAL", channel="EMAIL", is_enabled=True
        )

        context = {"name": "John"}

        email_notification = send_email_notification(
            user=self.user,
            template_name="test_template",
            context=context,
            email_type="TRANSACTIONAL",
        )

        self.assertIsNotNone(email_notification)
        self.assertEqual(email_notification.user, self.user)
        self.assertEqual(email_notification.template_name, "test_template")
        self.assertEqual(email_notification.email_type, "TRANSACTIONAL")
        mock_send.assert_called_once()

    @patch("apps.notifications.services._send_email_now")
    def test_send_transactional_email(self, mock_send):
        """Test sending transactional email"""
        from .models import NotificationPreference
        from .services import send_transactional_email

        # Create email preference to allow email notifications
        NotificationPreference.objects.create(
            user=self.user, notification_type="TRANSACTIONAL", channel="EMAIL", is_enabled=True
        )

        context = {"name": "John"}

        email_notification = send_transactional_email(
            user=self.user, template_name="test_template", context=context
        )

        self.assertIsNotNone(email_notification)
        self.assertEqual(email_notification.email_type, "TRANSACTIONAL")
        mock_send.assert_called_once()

    def test_get_email_statistics(self):
        """Test getting email statistics"""
        from .models import EmailNotification
        from .services import get_email_statistics

        # Create test email notifications
        EmailNotification.objects.create(
            user=self.user,
            subject="Test 1",
            to_email="test@example.com",
            from_email="noreply@example.com",
            template_name="test_template",
            status="SENT",
        )
        EmailNotification.objects.create(
            user=self.user,
            subject="Test 2",
            to_email="test@example.com",
            from_email="noreply@example.com",
            template_name="test_template",
            status="DELIVERED",
        )
        EmailNotification.objects.create(
            user=self.user,
            subject="Test 3",
            to_email="test@example.com",
            from_email="noreply@example.com",
            template_name="test_template",
            status="OPENED",
        )

        stats = get_email_statistics(user=self.user)

        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["sent"], 3)
        self.assertEqual(stats["delivered"], 2)
        self.assertEqual(stats["opened"], 1)
        self.assertGreater(stats["delivery_rate"], 0)
        self.assertGreater(stats["open_rate"], 0)


class SMSNotificationModelTests(TestCase):
    """Test cases for SMS notification models"""

    def setUp(self):
        """Set up test data"""
        # Enable RLS bypass for tests
        from apps.core.tenant_context import enable_rls_bypass

        enable_rls_bypass()

        # Create tenant first
        self.tenant = Tenant.objects.create(company_name="Test Company", slug="test-company")

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            phone="+1234567890",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_OWNER",
        )

    def test_sms_notification_creation(self):
        """Test creating an SMS notification"""
        sms_notification = SMSNotification.objects.create(
            user=self.user,
            message="Test SMS message",
            to_phone="+1234567890",
            from_phone="+1987654321",
            template_name="test_template",
            sms_type="TRANSACTIONAL",
        )

        self.assertEqual(sms_notification.user, self.user)
        self.assertEqual(sms_notification.message, "Test SMS message")
        self.assertEqual(sms_notification.to_phone, "+1234567890")
        self.assertEqual(sms_notification.status, "PENDING")
        self.assertEqual(sms_notification.sms_type, "TRANSACTIONAL")

    def test_sms_notification_str_representation(self):
        """Test string representation of SMS notification"""
        sms_notification = SMSNotification.objects.create(
            user=self.user,
            message="Test SMS",
            to_phone="+1234567890",
            sms_type="TRANSACTIONAL",
        )

        expected_str = "SMS to +1234567890 (PENDING)"
        self.assertEqual(str(sms_notification), expected_str)

    def test_sms_status_update(self):
        """Test updating SMS status"""
        sms_notification = SMSNotification.objects.create(
            user=self.user,
            message="Test SMS",
            to_phone="+1234567890",
            sms_type="TRANSACTIONAL",
        )

        # Update to sent
        sms_notification.update_status("SENT")
        self.assertEqual(sms_notification.status, "SENT")
        self.assertIsNotNone(sms_notification.sent_at)

        # Update to delivered
        sms_notification.update_status("DELIVERED")
        self.assertEqual(sms_notification.status, "DELIVERED")
        self.assertIsNotNone(sms_notification.delivered_at)

        # Update to failed with error
        sms_notification.update_status(
            "FAILED", error_message="Invalid phone number", error_code="21211"
        )
        self.assertEqual(sms_notification.status, "FAILED")
        self.assertEqual(sms_notification.error_message, "Invalid phone number")
        self.assertEqual(sms_notification.error_code, "21211")
        self.assertIsNotNone(sms_notification.failed_at)

    def test_sms_template_creation(self):
        """Test creating an SMS template"""
        template = SMSTemplate.objects.create(
            name="test_sms_template",
            message_template="Hello {{ name }}, your order #{{ order_number }} is ready!",
            sms_type="TRANSACTIONAL",
        )

        self.assertEqual(template.name, "test_sms_template")
        self.assertEqual(template.sms_type, "TRANSACTIONAL")
        self.assertTrue(template.is_active)

    def test_sms_template_str_representation(self):
        """Test string representation of SMS template"""
        template = SMSTemplate.objects.create(
            name="order_ready",
            message_template="Your order is ready!",
            sms_type="TRANSACTIONAL",
        )

        expected_str = "order_ready (TRANSACTIONAL)"
        self.assertEqual(str(template), expected_str)

    def test_sms_template_rendering(self):
        """Test SMS template rendering"""
        template = SMSTemplate.objects.create(
            name="order_ready",
            message_template="Hello {{ name }}, your order #{{ order_number }} is ready for pickup!",
            sms_type="TRANSACTIONAL",
        )

        context = {"name": "John", "order_number": "ORD-123"}
        rendered = template.render(context)

        expected_message = "Hello John, your order #ORD-123 is ready for pickup!"
        self.assertEqual(rendered["message"], expected_message)

    def test_sms_opt_out_creation(self):
        """Test creating SMS opt-out record"""
        opt_out = SMSOptOut.objects.create(
            user=self.user,
            reason="User requested opt-out",
            marketing_opt_out=True,
            transactional_opt_out=False,
        )

        self.assertEqual(opt_out.user, self.user)
        self.assertEqual(opt_out.reason, "User requested opt-out")
        self.assertTrue(opt_out.marketing_opt_out)
        self.assertFalse(opt_out.transactional_opt_out)

    def test_sms_opt_out_str_representation(self):
        """Test string representation of SMS opt-out"""
        opt_out = SMSOptOut.objects.create(
            user=self.user,
            marketing_opt_out=True,
        )

        expected_str = f"SMS Opt-Out: {self.user.username}"
        self.assertEqual(str(opt_out), expected_str)

    def test_sms_opt_out_type_check(self):
        """Test checking opt-out status for specific SMS types"""
        opt_out = SMSOptOut.objects.create(
            user=self.user,
            marketing_opt_out=True,
            transactional_opt_out=False,
            system_opt_out=True,
            alert_opt_out=False,
        )

        self.assertTrue(opt_out.is_opted_out_for_type("MARKETING"))
        self.assertFalse(opt_out.is_opted_out_for_type("TRANSACTIONAL"))
        self.assertTrue(opt_out.is_opted_out_for_type("SYSTEM"))
        self.assertFalse(opt_out.is_opted_out_for_type("ALERT"))


class SMSServiceTests(TestCase):
    """Test cases for SMS services"""

    def setUp(self):
        """Set up test data"""
        # Enable RLS bypass for tests
        from apps.core.tenant_context import enable_rls_bypass

        enable_rls_bypass()

        # Create tenant first
        self.tenant = Tenant.objects.create(company_name="Test Company", slug="test-company")

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            phone="+1234567890",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_OWNER",
        )

        # Create SMS template
        self.sms_template = SMSTemplate.objects.create(
            name="test_sms_template",
            message_template="Hello {{ name }}, your order #{{ order_number }} is ready!",
            sms_type="TRANSACTIONAL",
        )

    def test_normalize_phone_number(self):
        """Test phone number normalization"""
        from .services import _normalize_phone_number

        # Test various phone number formats
        self.assertEqual(_normalize_phone_number("1234567890"), "+11234567890")
        self.assertEqual(_normalize_phone_number("11234567890"), "+11234567890")
        self.assertEqual(_normalize_phone_number("+1234567890"), "+1234567890")
        self.assertEqual(_normalize_phone_number("(123) 456-7890"), "+11234567890")
        self.assertEqual(_normalize_phone_number("123-456-7890"), "+11234567890")

    def test_is_user_opted_out_sms_default(self):
        """Test default SMS opt-out behavior"""
        from .services import is_user_opted_out_sms

        # By default, users should be opted out of marketing but not transactional
        self.assertTrue(is_user_opted_out_sms(self.user, "MARKETING"))
        self.assertFalse(is_user_opted_out_sms(self.user, "TRANSACTIONAL"))
        self.assertFalse(is_user_opted_out_sms(self.user, "SYSTEM"))
        self.assertFalse(is_user_opted_out_sms(self.user, "ALERT"))

    def test_opt_out_user_sms(self):
        """Test opting user out of SMS"""
        from .services import is_user_opted_out_sms, opt_out_user_sms

        # Opt user out of transactional SMS
        opt_out_user_sms(self.user, "TRANSACTIONAL", "User request")

        # Check that user is now opted out
        self.assertTrue(is_user_opted_out_sms(self.user, "TRANSACTIONAL"))

        # Verify opt-out record was created
        opt_out = SMSOptOut.objects.get(user=self.user)
        self.assertTrue(opt_out.transactional_opt_out)
        self.assertEqual(opt_out.reason, "User request")

    def test_opt_in_user_sms(self):
        """Test opting user back in to SMS"""
        from .services import is_user_opted_out_sms, opt_in_user_sms, opt_out_user_sms

        # First opt user out
        opt_out_user_sms(self.user, "MARKETING")
        self.assertTrue(is_user_opted_out_sms(self.user, "MARKETING"))

        # Then opt user back in
        opt_in_user_sms(self.user, "MARKETING")
        self.assertFalse(is_user_opted_out_sms(self.user, "MARKETING"))

    @patch("apps.notifications.services._send_sms_now")
    def test_send_sms_notification(self, mock_send):
        """Test sending SMS notification"""
        from .models import NotificationPreference
        from .services import send_sms_notification

        # Create SMS preference to allow SMS notifications
        NotificationPreference.objects.create(
            user=self.user, notification_type="TRANSACTIONAL", channel="SMS", is_enabled=True
        )

        sms_notification = send_sms_notification(
            user=self.user,
            message="Test SMS message",
            sms_type="TRANSACTIONAL",
        )

        self.assertIsNotNone(sms_notification)
        self.assertEqual(sms_notification.user, self.user)
        self.assertEqual(sms_notification.message, "Test SMS message")
        self.assertEqual(sms_notification.sms_type, "TRANSACTIONAL")
        self.assertEqual(sms_notification.to_phone, "+1234567890")  # Normalized
        mock_send.assert_called_once()

    def test_send_sms_notification_no_phone(self):
        """Test sending SMS to user without phone number"""
        from .services import send_sms_notification

        # Create user without phone
        user_no_phone = User.objects.create_user(
            username="nophone",
            email="nophone@example.com",
            tenant=self.tenant,
            role="TENANT_EMPLOYEE",
        )

        sms_notification = send_sms_notification(
            user=user_no_phone,
            message="Test SMS message",
            sms_type="TRANSACTIONAL",
        )

        self.assertIsNone(sms_notification)

    def test_send_sms_notification_opted_out(self):
        """Test sending SMS to opted-out user"""
        from .services import opt_out_user_sms, send_sms_notification

        # Opt user out of transactional SMS
        opt_out_user_sms(self.user, "TRANSACTIONAL")

        sms_notification = send_sms_notification(
            user=self.user,
            message="Test SMS message",
            sms_type="TRANSACTIONAL",
        )

        self.assertIsNone(sms_notification)

    @patch("apps.notifications.services._send_sms_now")
    def test_send_sms_from_template(self, mock_send):
        """Test sending SMS from template"""
        from .models import NotificationPreference
        from .services import send_sms_from_template

        # Create SMS preference to allow SMS notifications
        NotificationPreference.objects.create(
            user=self.user, notification_type="TRANSACTIONAL", channel="SMS", is_enabled=True
        )

        context = {"name": "John", "order_number": "ORD-123"}

        sms_notification = send_sms_from_template(
            user=self.user,
            template_name="test_sms_template",
            context=context,
            sms_type="TRANSACTIONAL",
        )

        self.assertIsNotNone(sms_notification)
        self.assertEqual(sms_notification.template_name, "test_sms_template")
        self.assertIn("John", sms_notification.message)
        self.assertIn("ORD-123", sms_notification.message)
        mock_send.assert_called_once()

    def test_send_sms_from_template_not_found(self):
        """Test sending SMS from non-existent template"""
        from .services import send_sms_from_template

        context = {"name": "John"}

        sms_notification = send_sms_from_template(
            user=self.user,
            template_name="nonexistent_template",
            context=context,
            sms_type="TRANSACTIONAL",
        )

        self.assertIsNone(sms_notification)

    @patch("apps.notifications.services._send_sms_now")
    def test_send_transactional_sms(self, mock_send):
        """Test sending transactional SMS"""
        from .models import NotificationPreference
        from .services import send_transactional_sms

        # Create SMS preference to allow SMS notifications
        NotificationPreference.objects.create(
            user=self.user, notification_type="TRANSACTIONAL", channel="SMS", is_enabled=True
        )

        context = {"name": "John", "order_number": "ORD-123"}

        sms_notification = send_transactional_sms(
            user=self.user,
            template_name="test_sms_template",
            context=context,
        )

        self.assertIsNotNone(sms_notification)
        self.assertEqual(sms_notification.sms_type, "TRANSACTIONAL")
        mock_send.assert_called_once()

    @patch("apps.notifications.services._send_sms_now")
    def test_send_alert_sms(self, mock_send):
        """Test sending alert SMS"""
        from .models import NotificationPreference
        from .services import send_alert_sms

        # Create SMS preference to allow SMS notifications
        NotificationPreference.objects.create(
            user=self.user, notification_type="ALERT", channel="SMS", is_enabled=True
        )

        context = {"name": "John", "order_number": "ORD-123"}

        sms_notification = send_alert_sms(
            user=self.user,
            template_name="test_sms_template",
            context=context,
        )

        self.assertIsNotNone(sms_notification)
        self.assertEqual(sms_notification.sms_type, "ALERT")
        mock_send.assert_called_once()

    def test_get_sms_statistics(self):
        """Test getting SMS statistics"""
        from .services import get_sms_statistics

        # Create test SMS notifications
        SMSNotification.objects.create(
            user=self.user,
            message="Test 1",
            to_phone="+1234567890",
            sms_type="TRANSACTIONAL",
            status="SENT",
            price=0.0075,
            price_unit="USD",
        )
        SMSNotification.objects.create(
            user=self.user,
            message="Test 2",
            to_phone="+1234567890",
            sms_type="TRANSACTIONAL",
            status="DELIVERED",
            price=0.0075,
            price_unit="USD",
        )
        SMSNotification.objects.create(
            user=self.user,
            message="Test 3",
            to_phone="+1234567890",
            sms_type="TRANSACTIONAL",
            status="FAILED",
        )

        stats = get_sms_statistics(user=self.user)

        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["sent"], 2)
        self.assertEqual(stats["delivered"], 1)
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(stats["total_cost"], 0.015)  # 2 * 0.0075
        self.assertGreater(stats["delivery_rate"], 0)

    @patch("apps.notifications.services._get_twilio_client")
    def test_send_sms_now_success(self, mock_get_client):
        """Test successful SMS sending via Twilio"""
        from unittest.mock import Mock

        from .services import _send_sms_now

        # Mock Twilio client and message
        mock_client = Mock()
        mock_message = Mock()
        mock_message.sid = "SM123456789"
        mock_message.status = "sent"
        mock_message.price = "0.0075"
        mock_message.price_unit = "USD"
        mock_client.messages.create.return_value = mock_message
        mock_get_client.return_value = mock_client

        # Create SMS notification
        sms_notification = SMSNotification.objects.create(
            user=self.user,
            message="Test SMS",
            to_phone="+1234567890",
            from_phone="+1987654321",
            sms_type="TRANSACTIONAL",
        )

        # Send SMS
        _send_sms_now(sms_notification)

        # Verify SMS was sent
        sms_notification.refresh_from_db()
        self.assertEqual(sms_notification.message_sid, "SM123456789")
        self.assertEqual(sms_notification.status, "SENT")
        self.assertEqual(float(sms_notification.price), 0.0075)
        self.assertEqual(sms_notification.price_unit, "USD")

    @patch("apps.notifications.services._get_twilio_client")
    def test_send_sms_now_failure(self, mock_get_client):
        """Test SMS sending failure"""
        from unittest.mock import Mock

        from .services import _send_sms_now

        # Mock Twilio client to raise exception
        mock_client = Mock()
        mock_client.messages.create.side_effect = Exception("Twilio error")
        mock_get_client.return_value = mock_client

        # Create SMS notification
        sms_notification = SMSNotification.objects.create(
            user=self.user,
            message="Test SMS",
            to_phone="+1234567890",
            sms_type="TRANSACTIONAL",
        )

        # Send SMS
        _send_sms_now(sms_notification)

        # Verify SMS failed
        sms_notification.refresh_from_db()
        self.assertEqual(sms_notification.status, "FAILED")
        self.assertEqual(sms_notification.error_message, "Twilio error")

    def test_send_sms_now_no_client(self):
        """Test SMS sending when Twilio client is not available"""
        from .services import _send_sms_now

        # Create SMS notification
        sms_notification = SMSNotification.objects.create(
            user=self.user,
            message="Test SMS",
            to_phone="+1234567890",
            sms_type="TRANSACTIONAL",
        )

        # Send SMS (should fail due to no Twilio client)
        _send_sms_now(sms_notification)

        # Verify SMS failed
        sms_notification.refresh_from_db()
        self.assertEqual(sms_notification.status, "FAILED")
        self.assertEqual(sms_notification.error_message, "Twilio client not available")


class SMSWebhookTests(TestCase):
    """Test cases for SMS webhook handling"""

    def setUp(self):
        """Set up test data"""
        # Enable RLS bypass for tests
        from apps.core.tenant_context import enable_rls_bypass

        enable_rls_bypass()

        # Create tenant first
        self.tenant = Tenant.objects.create(company_name="Test Company", slug="test-company")

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            phone="+1234567890",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_OWNER",
        )

        # Create SMS notification
        self.sms_notification = SMSNotification.objects.create(
            user=self.user,
            message="Test SMS",
            to_phone="+1234567890",
            sms_type="TRANSACTIONAL",
            message_sid="SM123456789",
            status="SENT",
        )

    def test_sms_webhook_delivered(self):
        """Test SMS webhook for delivered status"""
        response = self.client.post(
            "/notifications/webhooks/sms/",
            {
                "MessageSid": "SM123456789",
                "MessageStatus": "delivered",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "OK")

        # Verify SMS status was updated
        self.sms_notification.refresh_from_db()
        self.assertEqual(self.sms_notification.status, "DELIVERED")
        self.assertIsNotNone(self.sms_notification.delivered_at)

    def test_sms_webhook_failed(self):
        """Test SMS webhook for failed status"""
        response = self.client.post(
            "/notifications/webhooks/sms/",
            {
                "MessageSid": "SM123456789",
                "MessageStatus": "failed",
                "ErrorCode": "30008",
                "ErrorMessage": "Unknown error",
            },
        )

        self.assertEqual(response.status_code, 200)

        # Verify SMS status was updated
        self.sms_notification.refresh_from_db()
        self.assertEqual(self.sms_notification.status, "FAILED")
        self.assertEqual(self.sms_notification.error_code, "30008")
        self.assertEqual(self.sms_notification.error_message, "Unknown error")

    def test_sms_webhook_missing_params(self):
        """Test SMS webhook with missing parameters"""
        response = self.client.post("/notifications/webhooks/sms/", {})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing required parameters", response.content.decode())

    def test_sms_webhook_nonexistent_message(self):
        """Test SMS webhook for non-existent message"""
        response = self.client.post(
            "/notifications/webhooks/sms/",
            {
                "MessageSid": "SM999999999",
                "MessageStatus": "delivered",
            },
        )

        # Should still return 200 (webhook should not fail)
        self.assertEqual(response.status_code, 200)


class EmailCampaignModelTests(TestCase):
    """Test cases for email campaign models and functionality"""

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

        # Create email template
        from .models import EmailTemplate

        self.email_template = EmailTemplate.objects.create(
            name="marketing_template",
            subject_template="Special Offer for {{ name }}",
            html_template="<h1>Hello {{ name }}</h1><p>Check out our special offer!</p>",
            text_template="Hello {{ name }}, check out our special offer!",
            email_type="MARKETING",
        )

    def test_email_campaign_creation(self):
        """Test creating an email campaign"""
        from .models import EmailCampaign

        campaign = EmailCampaign.objects.create(
            name="Spring Sale Campaign",
            subject="Spring Sale - 20% Off All Items",
            template=self.email_template,
            created_by=self.user,
            target_roles=["TENANT_OWNER", "TENANT_MANAGER"],
        )

        self.assertEqual(campaign.name, "Spring Sale Campaign")
        self.assertEqual(campaign.template, self.email_template)
        self.assertEqual(campaign.status, "DRAFT")
        self.assertEqual(campaign.created_by, self.user)
        self.assertEqual(campaign.target_roles, ["TENANT_OWNER", "TENANT_MANAGER"])

    def test_email_campaign_str_representation(self):
        """Test string representation of email campaign"""
        from .models import EmailCampaign

        campaign = EmailCampaign.objects.create(
            name="Test Campaign",
            subject="Test Subject",
            template=self.email_template,
            created_by=self.user,
        )

        expected_str = "Test Campaign (DRAFT)"
        self.assertEqual(str(campaign), expected_str)

    def test_email_campaign_get_target_users(self):
        """Test getting target users for email campaign"""
        from .models import EmailCampaign

        # Create additional users
        user2 = User.objects.create_user(
            username="manager",
            email="manager@example.com",
            tenant=self.tenant,
            role="TENANT_MANAGER",
        )
        user3 = User.objects.create_user(
            username="employee",
            email="employee@example.com",
            tenant=self.tenant,
            role="TENANT_EMPLOYEE",
        )

        # Create campaign targeting specific roles
        campaign = EmailCampaign.objects.create(
            name="Manager Campaign",
            subject="Manager Update",
            template=self.email_template,
            created_by=self.user,
            target_roles=["TENANT_OWNER", "TENANT_MANAGER"],
        )

        target_users = campaign.get_target_users()
        target_usernames = [user.username for user in target_users]

        self.assertIn("testuser", target_usernames)  # TENANT_OWNER
        self.assertIn("manager", target_usernames)  # TENANT_MANAGER
        self.assertNotIn("employee", target_usernames)  # TENANT_EMPLOYEE not targeted

    def test_email_campaign_update_statistics(self):
        """Test updating email campaign statistics"""
        from .models import EmailCampaign, EmailNotification

        campaign = EmailCampaign.objects.create(
            name="Stats Test Campaign",
            subject="Test Subject",
            template=self.email_template,
            created_by=self.user,
        )

        # Create email notifications for this campaign
        EmailNotification.objects.create(
            user=self.user,
            subject="Test Email 1",
            to_email="test1@example.com",
            from_email="noreply@example.com",
            template_name="marketing_template",
            email_type="MARKETING",
            campaign_id=str(campaign.id),
            status="SENT",
        )
        EmailNotification.objects.create(
            user=self.user,
            subject="Test Email 2",
            to_email="test2@example.com",
            from_email="noreply@example.com",
            template_name="marketing_template",
            email_type="MARKETING",
            campaign_id=str(campaign.id),
            status="DELIVERED",
        )
        EmailNotification.objects.create(
            user=self.user,
            subject="Test Email 3",
            to_email="test3@example.com",
            from_email="noreply@example.com",
            template_name="marketing_template",
            email_type="MARKETING",
            campaign_id=str(campaign.id),
            status="OPENED",
        )

        # Update statistics
        campaign.update_statistics()

        self.assertEqual(campaign.total_recipients, 3)
        self.assertEqual(campaign.emails_sent, 3)
        self.assertEqual(campaign.emails_delivered, 2)
        self.assertEqual(campaign.emails_opened, 1)


class SMSCampaignModelTests(TestCase):
    """Test cases for SMS campaign models and functionality"""

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
            phone="+1234567890",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_OWNER",
        )

        # Create SMS template
        self.sms_template = SMSTemplate.objects.create(
            name="marketing_sms_template",
            message_template="Hi {{ name }}! Special offer: {{ offer }}. Reply STOP to opt out.",
            sms_type="MARKETING",
        )

    def test_sms_campaign_creation(self):
        """Test creating an SMS campaign"""
        from .models import SMSCampaign

        campaign = SMSCampaign.objects.create(
            name="Flash Sale SMS",
            template=self.sms_template,
            created_by=self.user,
            target_roles=["TENANT_OWNER"],
        )

        self.assertEqual(campaign.name, "Flash Sale SMS")
        self.assertEqual(campaign.template, self.sms_template)
        self.assertEqual(campaign.status, "DRAFT")
        self.assertEqual(campaign.created_by, self.user)

    def test_sms_campaign_str_representation(self):
        """Test string representation of SMS campaign"""
        from .models import SMSCampaign

        campaign = SMSCampaign.objects.create(
            name="Test SMS Campaign",
            template=self.sms_template,
            created_by=self.user,
        )

        expected_str = "Test SMS Campaign (DRAFT)"
        self.assertEqual(str(campaign), expected_str)

    def test_sms_campaign_update_statistics(self):
        """Test updating SMS campaign statistics"""
        from .models import SMSCampaign

        campaign = SMSCampaign.objects.create(
            name="SMS Stats Test",
            template=self.sms_template,
            created_by=self.user,
        )

        # Create SMS notifications for this campaign
        SMSNotification.objects.create(
            user=self.user,
            message="Test SMS 1",
            to_phone="+1234567890",
            sms_type="MARKETING",
            campaign_id=str(campaign.id),
            status="SENT",
            price=0.0075,
            price_unit="USD",
        )
        SMSNotification.objects.create(
            user=self.user,
            message="Test SMS 2",
            to_phone="+1234567890",
            sms_type="MARKETING",
            campaign_id=str(campaign.id),
            status="DELIVERED",
            price=0.0075,
            price_unit="USD",
        )
        SMSNotification.objects.create(
            user=self.user,
            message="Test SMS 3",
            to_phone="+1234567890",
            sms_type="MARKETING",
            campaign_id=str(campaign.id),
            status="FAILED",
        )

        # Update statistics
        campaign.update_statistics()

        self.assertEqual(campaign.total_recipients, 3)
        self.assertEqual(campaign.sms_sent, 2)  # SENT and DELIVERED
        self.assertEqual(campaign.sms_delivered, 1)  # Only DELIVERED
        self.assertEqual(campaign.sms_failed, 1)  # FAILED
        self.assertEqual(float(campaign.total_cost), 0.015)  # 2 * 0.0075


class CustomerSegmentModelTests(TestCase):
    """Test cases for customer segmentation models and functionality"""

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

        # Create test customers (mock CRM customers)
        from apps.crm.models import Customer, LoyaltyTier

        # Create loyalty tiers
        self.bronze_tier = LoyaltyTier.objects.create(
            tenant=self.tenant,
            name="Bronze",
            min_spending=0,
            discount_percentage=5,
        )
        self.gold_tier = LoyaltyTier.objects.create(
            tenant=self.tenant,
            name="Gold",
            min_spending=5000,
            discount_percentage=10,
        )

        # Create test customers
        self.customer1 = Customer.objects.create(
            tenant=self.tenant,
            customer_number="CUST001",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            phone="+1234567890",
            loyalty_tier=self.bronze_tier,
            total_purchases=1000,
        )
        self.customer2 = Customer.objects.create(
            tenant=self.tenant,
            customer_number="CUST002",
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            phone="+1234567891",
            loyalty_tier=self.gold_tier,
            total_purchases=7500,
        )

    def test_static_customer_segment_creation(self):
        """Test creating a static customer segment"""
        from .models import CustomerSegment

        segment = CustomerSegment.objects.create(
            name="VIP Customers",
            description="Our most valued customers",
            segment_type="STATIC",
            created_by=self.user,
        )

        # Add customers to static segment
        segment.customers.set([self.customer1, self.customer2])
        segment.update_customer_count()

        self.assertEqual(segment.name, "VIP Customers")
        self.assertEqual(segment.segment_type, "STATIC")
        self.assertEqual(segment.customer_count, 2)
        self.assertTrue(segment.is_active)

    def test_dynamic_customer_segment_creation(self):
        """Test creating a dynamic customer segment"""
        from .models import CustomerSegment

        # Create dynamic segment for high-value customers
        criteria = {
            "min_total_purchases": 5000,
            "loyalty_tiers": ["Gold"],
        }

        segment = CustomerSegment.objects.create(
            name="High Value Customers",
            description="Customers with high purchase amounts",
            segment_type="DYNAMIC",
            criteria=criteria,
            created_by=self.user,
        )

        segment.update_customer_count()

        self.assertEqual(segment.name, "High Value Customers")
        self.assertEqual(segment.segment_type, "DYNAMIC")
        self.assertEqual(segment.criteria, criteria)
        # Should match customer2 (Gold tier, 7500 purchases)
        self.assertEqual(segment.customer_count, 1)

    def test_customer_segment_str_representation(self):
        """Test string representation of customer segment"""
        from .models import CustomerSegment

        segment = CustomerSegment.objects.create(
            name="Test Segment",
            segment_type="STATIC",
            created_by=self.user,
        )
        segment.update_customer_count()

        expected_str = "Test Segment (0 customers)"
        self.assertEqual(str(segment), expected_str)

    def test_dynamic_segment_criteria_application(self):
        """Test dynamic segment criteria application"""
        from .models import CustomerSegment

        # Test minimum purchase criteria
        criteria = {"min_total_purchases": 2000}
        segment = CustomerSegment.objects.create(
            name="Mid-Value Customers",
            segment_type="DYNAMIC",
            criteria=criteria,
            created_by=self.user,
        )

        customers = segment.get_customers()
        # Should only match customer2 (7500 > 2000)
        self.assertEqual(customers.count(), 1)
        self.assertEqual(customers.first(), self.customer2)

    def test_segment_get_customers_static(self):
        """Test getting customers from static segment"""
        from .models import CustomerSegment

        segment = CustomerSegment.objects.create(
            name="Static Test",
            segment_type="STATIC",
            created_by=self.user,
        )
        segment.customers.set([self.customer1])

        customers = segment.get_customers()
        self.assertEqual(customers.count(), 1)
        self.assertEqual(customers.first(), self.customer1)


class CampaignAnalyticsModelTests(TestCase):
    """Test cases for campaign analytics models and functionality"""

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

    def test_campaign_analytics_creation(self):
        """Test creating campaign analytics record"""
        from .models import CampaignAnalytics

        analytics = CampaignAnalytics.objects.create(
            campaign_id="CAMP001",
            campaign_name="Spring Sale",
            campaign_type="EMAIL",
            total_recipients=1000,
            messages_sent=950,
            messages_delivered=900,
            emails_opened=450,
            emails_clicked=90,
            conversions=18,
            conversion_value=3600.00,
            total_cost=50.00,
            campaign_sent_at=timezone.now(),
        )

        self.assertEqual(analytics.campaign_id, "CAMP001")
        self.assertEqual(analytics.campaign_name, "Spring Sale")
        self.assertEqual(analytics.campaign_type, "EMAIL")
        self.assertEqual(analytics.total_recipients, 1000)

    def test_campaign_analytics_str_representation(self):
        """Test string representation of campaign analytics"""
        from .models import CampaignAnalytics

        analytics = CampaignAnalytics.objects.create(
            campaign_id="CAMP001",
            campaign_name="Test Campaign",
            campaign_type="EMAIL",
            campaign_sent_at=timezone.now(),
        )

        expected_str = "Test Campaign Analytics"
        self.assertEqual(str(analytics), expected_str)

    def test_campaign_analytics_calculate_rates(self):
        """Test calculating campaign performance rates"""
        from .models import CampaignAnalytics

        analytics = CampaignAnalytics.objects.create(
            campaign_id="CAMP001",
            campaign_name="Rate Test Campaign",
            campaign_type="EMAIL",
            total_recipients=1000,
            messages_sent=950,
            messages_delivered=900,
            emails_opened=450,
            emails_clicked=90,
            conversions=18,
            conversion_value=3600.00,
            total_cost=50.00,
            campaign_sent_at=timezone.now(),
        )

        analytics.calculate_rates()

        # Check calculated rates
        self.assertAlmostEqual(float(analytics.delivery_rate), 94.74, places=2)  # 900/950 * 100
        self.assertAlmostEqual(float(analytics.open_rate), 50.0, places=2)  # 450/900 * 100
        self.assertAlmostEqual(float(analytics.click_rate), 20.0, places=2)  # 90/450 * 100
        self.assertAlmostEqual(float(analytics.conversion_rate), 2.0, places=2)  # 18/900 * 100
        self.assertAlmostEqual(float(analytics.roi), 7100.0, places=2)  # (3600-50)/50 * 100

    def test_campaign_analytics_zero_division_handling(self):
        """Test handling of zero division in rate calculations"""
        from .models import CampaignAnalytics

        analytics = CampaignAnalytics.objects.create(
            campaign_id="CAMP002",
            campaign_name="Zero Test Campaign",
            campaign_type="EMAIL",
            total_recipients=0,
            messages_sent=0,
            messages_delivered=0,
            campaign_sent_at=timezone.now(),
        )

        analytics.calculate_rates()

        # All rates should be 0 when there are no messages
        self.assertEqual(float(analytics.delivery_rate), 0.0)
        self.assertEqual(float(analytics.open_rate), 0.0)
        self.assertEqual(float(analytics.click_rate), 0.0)
        self.assertEqual(float(analytics.conversion_rate), 0.0)
        self.assertEqual(float(analytics.roi), 0.0)


class CommunicationLogModelTests(TestCase):
    """Test cases for communication log models and functionality"""

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

        # Create test customer
        from apps.crm.models import Customer

        self.customer = Customer.objects.create(
            tenant=self.tenant,
            customer_number="CUST001",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            phone="+1234567890",
        )

    def test_communication_log_creation(self):
        """Test creating a communication log entry"""
        from .models import CommunicationLog

        comm_log = CommunicationLog.objects.create(
            customer=self.customer,
            communication_type="EMAIL",
            direction="OUTBOUND",
            subject="Welcome Email",
            content="Welcome to our jewelry store!",
            campaign_id="CAMP001",
            created_by=self.user,
        )

        self.assertEqual(comm_log.customer, self.customer)
        self.assertEqual(comm_log.communication_type, "EMAIL")
        self.assertEqual(comm_log.direction, "OUTBOUND")
        self.assertEqual(comm_log.subject, "Welcome Email")
        self.assertEqual(comm_log.campaign_id, "CAMP001")
        self.assertEqual(comm_log.created_by, self.user)

    def test_communication_log_str_representation(self):
        """Test string representation of communication log"""
        from .models import CommunicationLog

        comm_log = CommunicationLog.objects.create(
            customer=self.customer,
            communication_type="SMS",
            direction="OUTBOUND",
            subject="Order Update",
            content="Your order is ready for pickup",
            created_by=self.user,
        )

        expected_str = f"John Doe - SMS ({comm_log.communication_date.date()})"
        self.assertEqual(str(comm_log), expected_str)

    def test_communication_log_with_notifications(self):
        """Test communication log with linked email/SMS notifications"""
        from .models import CommunicationLog, EmailNotification

        # Create email notification
        email_notification = EmailNotification.objects.create(
            user=self.user,
            subject="Test Email",
            to_email="john@example.com",
            from_email="noreply@example.com",
            template_name="test_template",
            email_type="MARKETING",
        )

        # Create communication log linked to email
        comm_log = CommunicationLog.objects.create(
            customer=self.customer,
            communication_type="EMAIL",
            direction="OUTBOUND",
            subject="Marketing Email",
            content="Check out our new collection",
            email_notification=email_notification,
            created_by=self.user,
        )

        self.assertEqual(comm_log.email_notification, email_notification)
        self.assertIsNone(comm_log.sms_notification)

    def test_communication_log_engagement_tracking(self):
        """Test engagement tracking in communication log"""
        from .models import CommunicationLog

        comm_log = CommunicationLog.objects.create(
            customer=self.customer,
            communication_type="EMAIL",
            direction="OUTBOUND",
            subject="Promotional Email",
            content="Special offer just for you!",
            was_opened=True,
            was_clicked=True,
            resulted_in_conversion=True,
            conversion_value=299.99,
            created_by=self.user,
        )

        self.assertTrue(comm_log.was_opened)
        self.assertTrue(comm_log.was_clicked)
        self.assertTrue(comm_log.resulted_in_conversion)
        self.assertEqual(float(comm_log.conversion_value), 299.99)


class CampaignServiceTests(TestCase):
    """Test cases for campaign-related services"""

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
            phone="+1234567890",
            password="testpass123",
            tenant=self.tenant,
            role="TENANT_OWNER",
        )

        # Create email template
        from .models import EmailTemplate

        self.email_template = EmailTemplate.objects.create(
            name="campaign_template",
            subject_template="Campaign: {{ campaign_name }}",
            html_template="<h1>{{ campaign_name }}</h1><p>{{ message }}</p>",
            text_template="{{ campaign_name }}: {{ message }}",
            email_type="MARKETING",
        )

    @patch("apps.notifications.services._send_email_now")
    def test_create_email_campaign(self, mock_send):
        """Test creating an email campaign"""
        from .services import create_email_campaign

        campaign = create_email_campaign(
            name="Test Campaign",
            subject="Test Subject",
            template_name="campaign_template",
            created_by=self.user,
            target_roles=["TENANT_OWNER"],
        )

        self.assertEqual(campaign.name, "Test Campaign")
        self.assertEqual(campaign.subject, "Test Subject")
        self.assertEqual(campaign.template.name, "campaign_template")
        self.assertEqual(campaign.created_by, self.user)
        self.assertEqual(campaign.target_roles, ["TENANT_OWNER"])

    @patch("apps.notifications.services._send_email_now")
    def test_send_campaign(self, mock_send):
        """Test sending an email campaign"""
        from .models import NotificationPreference
        from .services import create_email_campaign, send_campaign

        # Create email preference to allow email notifications
        NotificationPreference.objects.create(
            user=self.user, notification_type="MARKETING", channel="EMAIL", is_enabled=True
        )

        campaign = create_email_campaign(
            name="Send Test Campaign",
            subject="Send Test Subject",
            template_name="campaign_template",
            created_by=self.user,
            target_users=[self.user],
        )

        context = {"campaign_name": "Send Test Campaign", "message": "Test message"}
        sent_count = send_campaign(campaign, context)

        self.assertEqual(sent_count, 1)
        self.assertEqual(campaign.status, "SENT")
        self.assertIsNotNone(campaign.sent_at)
        mock_send.assert_called_once()

    def test_create_email_campaign_invalid_template(self):
        """Test creating campaign with invalid template"""
        from .services import create_email_campaign

        with self.assertRaises(ValueError):
            create_email_campaign(
                name="Invalid Campaign",
                subject="Test Subject",
                template_name="nonexistent_template",
                created_by=self.user,
            )

    @patch("apps.notifications.services._send_sms_now")
    def test_create_sms_campaign(self, mock_send):
        """Test creating an SMS campaign"""
        from .models import SMSTemplate
        from .services import create_sms_campaign

        # Create SMS template
        sms_template = SMSTemplate.objects.create(
            name="sms_campaign_template",
            message_template="{{ campaign_name }}: {{ message }}",
            sms_type="MARKETING",
        )

        campaign = create_sms_campaign(
            name="SMS Test Campaign",
            template_name="sms_campaign_template",
            created_by=self.user,
            target_users=[self.user],
        )

        self.assertEqual(campaign.name, "SMS Test Campaign")
        self.assertEqual(campaign.template.name, "sms_campaign_template")
        self.assertEqual(campaign.created_by, self.user)
        self.assertEqual(campaign.total_recipients, 1)  # User has phone number

    @patch("apps.notifications.services._send_sms_now")
    def test_send_sms_campaign(self, mock_send):
        """Test sending an SMS campaign"""
        from .models import NotificationPreference, SMSTemplate
        from .services import create_sms_campaign, send_sms_campaign

        # Create SMS opt-out record and set marketing to False (opted in)
        SMSOptOut.objects.create(
            user=self.user,
            marketing_opt_out=False,  # Opt in to marketing SMS
        )

        # Create SMS preference to allow SMS notifications
        NotificationPreference.objects.create(
            user=self.user, notification_type="MARKETING", channel="SMS", is_enabled=True
        )

        # Create SMS template
        sms_template = SMSTemplate.objects.create(
            name="sms_send_template",
            message_template="{{ message }}",
            sms_type="MARKETING",
        )

        campaign = create_sms_campaign(
            name="SMS Send Test",
            template_name="sms_send_template",
            created_by=self.user,
            target_users=[self.user],
        )

        context = {"message": "Test SMS message"}
        sent_count = send_sms_campaign(campaign, context)

        self.assertEqual(sent_count, 1)
        self.assertEqual(campaign.status, "SENT")
        self.assertIsNotNone(campaign.sent_at)
        mock_send.assert_called_once()


class AnalyticsServiceTests(TestCase):
    """Test cases for analytics and reporting services"""

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

    def test_create_campaign_analytics(self):
        """Test creating campaign analytics record"""
        from .services import create_campaign_analytics

        analytics = create_campaign_analytics(
            campaign_id="ANALYTICS_TEST_001",
            campaign_name="Analytics Test Campaign",
            campaign_type="EMAIL",
            campaign_sent_at=timezone.now(),
        )

        self.assertEqual(analytics.campaign_id, "ANALYTICS_TEST_001")
        self.assertEqual(analytics.campaign_name, "Analytics Test Campaign")
        self.assertEqual(analytics.campaign_type, "EMAIL")

    def test_track_campaign_conversion(self):
        """Test tracking campaign conversions"""
        from .services import create_campaign_analytics, track_campaign_conversion

        # Create analytics record
        analytics = create_campaign_analytics(
            campaign_id="CONVERSION_TEST_001",
            campaign_name="Conversion Test Campaign",
            campaign_type="EMAIL",
            campaign_sent_at=timezone.now(),
        )

        # Track conversion (use Decimal for proper type handling)
        from decimal import Decimal

        success = track_campaign_conversion(
            campaign_id="CONVERSION_TEST_001",
            conversion_value=Decimal("199.99"),
        )

        self.assertTrue(success)

        # Refresh analytics
        analytics.refresh_from_db()
        self.assertEqual(analytics.conversions, 1)
        self.assertEqual(analytics.conversion_value, Decimal("199.99"))

    def test_track_campaign_conversion_nonexistent(self):
        """Test tracking conversion for non-existent campaign"""
        from .services import track_campaign_conversion

        success = track_campaign_conversion(
            campaign_id="NONEXISTENT_CAMPAIGN",
            conversion_value=100.00,
        )

        self.assertFalse(success)

    def test_get_campaign_performance_report(self):
        """Test getting campaign performance report"""
        from .models import CampaignAnalytics
        from .services import get_campaign_performance_report

        # Create test analytics data
        CampaignAnalytics.objects.create(
            campaign_id="REPORT_TEST_001",
            campaign_name="Report Test 1",
            campaign_type="EMAIL",
            total_recipients=1000,
            messages_sent=950,
            messages_delivered=900,
            emails_opened=450,
            emails_clicked=90,
            conversions=18,
            conversion_value=3600.00,
            total_cost=50.00,
            campaign_sent_at=timezone.now(),
        )
        CampaignAnalytics.objects.create(
            campaign_id="REPORT_TEST_002",
            campaign_name="Report Test 2",
            campaign_type="SMS",
            total_recipients=500,
            messages_sent=480,
            messages_delivered=470,
            conversions=12,
            conversion_value=2400.00,
            total_cost=30.00,
            campaign_sent_at=timezone.now(),
        )

        report = get_campaign_performance_report()

        self.assertEqual(report["total_campaigns"], 2)
        self.assertEqual(report["total_recipients"], 1500)
        self.assertEqual(report["total_sent"], 1430)
        self.assertEqual(report["total_delivered"], 1370)
        self.assertEqual(report["total_conversions"], 30)
        self.assertEqual(report["total_conversion_value"], 6000.00)
        self.assertEqual(report["total_cost"], 80.00)

    def test_get_campaign_performance_report_filtered(self):
        """Test getting filtered campaign performance report"""
        from .models import CampaignAnalytics
        from .services import get_campaign_performance_report

        # Create test analytics data
        CampaignAnalytics.objects.create(
            campaign_id="FILTER_TEST_001",
            campaign_name="Email Campaign",
            campaign_type="EMAIL",
            total_recipients=1000,
            messages_sent=950,
            campaign_sent_at=timezone.now(),
        )
        CampaignAnalytics.objects.create(
            campaign_id="FILTER_TEST_002",
            campaign_name="SMS Campaign",
            campaign_type="SMS",
            total_recipients=500,
            messages_sent=480,
            campaign_sent_at=timezone.now(),
        )

        # Filter by campaign type
        report = get_campaign_performance_report(campaign_type="EMAIL")

        self.assertEqual(report["total_campaigns"], 1)
        self.assertEqual(report["total_recipients"], 1000)
        self.assertEqual(report["total_sent"], 950)


class SegmentationServiceTests(TestCase):
    """Test cases for customer segmentation services"""

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

        # Create test customers
        from apps.crm.models import Customer, LoyaltyTier

        self.gold_tier = LoyaltyTier.objects.create(
            tenant=self.tenant,
            name="Gold",
            min_spending=5000,
            discount_percentage=10,
        )

        self.customer1 = Customer.objects.create(
            tenant=self.tenant,
            customer_number="SEG001",
            first_name="Alice",
            last_name="Johnson",
            email="alice@example.com",
            loyalty_tier=self.gold_tier,
            total_purchases=7500,
        )
        self.customer2 = Customer.objects.create(
            tenant=self.tenant,
            customer_number="SEG002",
            first_name="Bob",
            last_name="Wilson",
            email="bob@example.com",
            total_purchases=2500,
        )

    def test_create_static_customer_segment(self):
        """Test creating a static customer segment"""
        from .services import create_customer_segment

        segment = create_customer_segment(
            name="VIP Static Segment",
            description="Manually selected VIP customers",
            segment_type="STATIC",
            customers=[self.customer1, self.customer2],
            created_by=self.user,
        )

        self.assertEqual(segment.name, "VIP Static Segment")
        self.assertEqual(segment.segment_type, "STATIC")
        self.assertEqual(segment.customer_count, 2)
        self.assertEqual(segment.customers.count(), 2)

    def test_create_dynamic_customer_segment(self):
        """Test creating a dynamic customer segment"""
        from .services import create_customer_segment

        criteria = {
            "min_total_purchases": 5000,
            "loyalty_tiers": ["Gold"],
        }

        segment = create_customer_segment(
            name="High Value Dynamic Segment",
            description="Customers with high purchase amounts",
            segment_type="DYNAMIC",
            criteria=criteria,
            created_by=self.user,
        )

        self.assertEqual(segment.name, "High Value Dynamic Segment")
        self.assertEqual(segment.segment_type, "DYNAMIC")
        self.assertEqual(segment.criteria, criteria)
        # Should match customer1 (Gold tier, 7500 purchases)
        self.assertEqual(segment.customer_count, 1)

    def test_update_dynamic_segments(self):
        """Test updating dynamic segments"""
        from .services import create_customer_segment, update_dynamic_segments

        # Create dynamic segment
        criteria = {"min_total_purchases": 3000}
        segment = create_customer_segment(
            name="Mid Value Segment",
            segment_type="DYNAMIC",
            criteria=criteria,
            created_by=self.user,
        )

        # Initially should match customer1 (7500 > 3000)
        self.assertEqual(segment.customer_count, 1)

        # Update customer2's purchases to meet criteria
        self.customer2.total_purchases = 4000
        self.customer2.save()

        # Update dynamic segments
        updated_count = update_dynamic_segments()

        # Refresh segment
        segment.refresh_from_db()

        self.assertEqual(updated_count, 1)
        # Now should match both customers
        self.assertEqual(segment.customer_count, 2)

    def test_get_segment_customers(self):
        """Test getting customers from a segment"""
        from .services import create_customer_segment, get_segment_customers

        segment = create_customer_segment(
            name="Test Segment",
            segment_type="STATIC",
            customers=[self.customer1],
            created_by=self.user,
        )

        customers = get_segment_customers(str(segment.id))
        self.assertEqual(customers.count(), 1)
        self.assertEqual(customers.first(), self.customer1)

    def test_get_segment_customers_nonexistent(self):
        """Test getting customers from non-existent segment"""
        import uuid

        from .services import get_segment_customers

        customers = get_segment_customers(str(uuid.uuid4()))
        self.assertIsNone(customers)
