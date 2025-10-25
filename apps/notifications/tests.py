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
        sms_notification.update_status("FAILED", error_message="Invalid phone number", error_code="21211")
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
        from .services import opt_out_user_sms, is_user_opted_out_sms

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
        from .services import opt_out_user_sms, opt_in_user_sms, is_user_opted_out_sms

        # First opt user out
        opt_out_user_sms(self.user, "MARKETING")
        self.assertTrue(is_user_opted_out_sms(self.user, "MARKETING"))

        # Then opt user back in
        opt_in_user_sms(self.user, "MARKETING")
        self.assertFalse(is_user_opted_out_sms(self.user, "MARKETING"))

    @patch("apps.notifications.services._send_sms_now")
    def test_send_sms_notification(self, mock_send):
        """Test sending SMS notification"""
        from .services import send_sms_notification
        from .models import NotificationPreference

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
        from .services import send_sms_notification, opt_out_user_sms

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
        from .services import send_sms_from_template
        from .models import NotificationPreference

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
        from .services import send_transactional_sms
        from .models import NotificationPreference

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
        from .services import send_alert_sms
        from .models import NotificationPreference

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
